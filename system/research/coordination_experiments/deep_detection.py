from __future__ import annotations

import hashlib
import json
import math
import random
from collections import defaultdict
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import numpy as np

from research.coordination_detect.contracts import (
    DetectionFeatureSchema,
    DetectionModelArtifact,
    DetectionTrainingCase,
    case_id_fingerprint,
)
from research.coordination_detect.features import STAGE1_FEATURE_NAMES
from research.coordination_detect.learned import _fit_platt, _select_thresholds, _sigmoid

from .baselines import LearnedDetectionImplementation as _LearnedDetectionImplementation
from .public_detection_sources import (
    resolve_public_detection_graph_sketch,
    resolve_public_detection_source_path,
)
from .runner import (
    DetectionExecutionOutput,
    DetectionInferenceCase,
    DetectionPartitions,
    DetectionPrediction,
)


DEEP_PYG_DETECTION_METHODS = frozenset(
    {
        "deep_pyg_graphsage_fused_detector",
        "deep_pyg_gin_fused_detector",
        "deep_pyg_gcn_fused_detector",
    }
)
DEEP_TABULAR_DETECTION_METHODS = frozenset(
    {
        "deep_tabular_mlp_detector",
        "deep_tabular_residual_detector",
    }
)
DEEP_LEN_FUSED_DETECTION_METHODS = frozenset(
    {
        "deep_len_mlp_fused_detector",
        "deep_len_fast_mlp_fused_detector",
    }
)
DEEP_DETECTION_METHODS = (
    DEEP_PYG_DETECTION_METHODS
    | DEEP_TABULAR_DETECTION_METHODS
    | DEEP_LEN_FUSED_DETECTION_METHODS
)

_MAX_DEEP_GRAPH_NODES = 384
_MAX_DEEP_GRAPH_EDGES = 4096
_DEEP_NODE_FEATURE_WIDTH = 12
_SMOKE_THRESHOLD = 8


@dataclass(frozen=True, slots=True)
class _TrainConfig:
    hidden_dim: int
    layers: int
    dropout: float
    learning_rate: float
    weight_decay: float
    max_epochs: int
    patience: int
    search_budget: str


@dataclass(frozen=True, slots=True)
class _GraphSketch:
    node_features: tuple[tuple[float, ...], ...]
    edge_index: tuple[tuple[int, int], ...]
    edge_weight: tuple[float, ...]


@dataclass(frozen=True, slots=True)
class _DeepExample:
    case_id: str
    cluster_id: str
    label: int | None
    feature_values: tuple[float, ...]
    graph: _GraphSketch | None = None


@dataclass(frozen=True, slots=True)
class _FitResult:
    model: Any
    validation_logits: np.ndarray
    calibrator_slope: float
    calibrator_intercept: float
    lower_threshold: float
    upper_threshold: float
    calibration_mode: str
    selected_config: _TrainConfig
    searched_config_count: int
    model_state_hash: str
    global_mean: tuple[float, ...]
    global_scale: tuple[float, ...]
    device: str
    internal_feature_width: int = 0


def _finite(value: Any, default: float = 0.0) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return default
    result = float(value)
    return result if math.isfinite(result) else default


def _flatten_numeric(values: Any, out: list[float]) -> None:
    if isinstance(values, (int, float)) and not isinstance(values, bool):
        value = float(values)
        if math.isfinite(value):
            out.append(value)
    elif isinstance(values, list):
        for item in values:
            _flatten_numeric(item, out)


def _safe_mean(values: list[float]) -> float:
    return float(np.mean(values)) if values else 0.0


def _safe_std(values: list[float]) -> float:
    return float(np.std(values)) if values else 0.0


def _safe_max(values: list[float]) -> float:
    return float(np.max(values)) if values else 0.0


def _node_id(value: Any, fallback: int) -> str:
    text = str(value if value is not None else fallback).strip()
    return text or str(fallback)


@lru_cache(maxsize=256)
def _load_deep_graph_sketch(source_path: str) -> _GraphSketch:
    path = Path(source_path)
    with path.open("r", encoding="utf-8") as stream:
        data = json.load(stream)
    return build_deep_graph_sketch_from_node_link(data, source_name=path.name)


def build_deep_graph_sketch_from_node_link(
    data: Any,
    *,
    source_name: str = "memory://public-detection-graph",
) -> _GraphSketch:
    nodes = data.get("nodes", ())
    links = data.get("links", data.get("edges", ()))
    if not isinstance(nodes, list) or not isinstance(links, list):
        raise ValueError(f"deep graph detector expects node-link LEN JSON: {source_name}")

    node_payloads: dict[str, dict[str, Any]] = {}
    for index, node in enumerate(nodes):
        if isinstance(node, dict):
            node_payloads[_node_id(node.get("id"), index)] = node
        else:
            node_payloads[str(index)] = {}

    in_degree: defaultdict[str, float] = defaultdict(float)
    out_degree: defaultdict[str, float] = defaultdict(float)
    strength: defaultdict[str, float] = defaultdict(float)
    first_seen: dict[str, float] = {}
    last_seen: dict[str, float] = {}
    observed_edges: list[tuple[str, str, float, float]] = []
    for link in links:
        if not isinstance(link, dict):
            continue
        source = str(link.get("source", "")).strip()
        target = str(link.get("target", "")).strip()
        if not source or not target:
            continue
        weight = max(0.0, _finite(link.get("Interaction_Count"), 1.0))
        timestamp = _finite(link.get("timestamp"), 0.0)
        out_degree[source] += 1.0
        in_degree[target] += 1.0
        strength[source] += weight
        strength[target] += weight
        for node_id in (source, target):
            first_seen[node_id] = min(first_seen.get(node_id, timestamp), timestamp)
            last_seen[node_id] = max(last_seen.get(node_id, timestamp), timestamp)
        observed_edges.append((source, target, weight, timestamp))

    candidates = set(node_payloads) | set(in_degree) | set(out_degree)
    if not candidates:
        return _GraphSketch(node_features=((0.0,) * 12,), edge_index=(), edge_weight=())

    ranked_nodes = sorted(
        candidates,
        key=lambda node_id: (
            -(in_degree[node_id] + out_degree[node_id]),
            -strength[node_id],
            node_id,
        ),
    )[:_MAX_DEEP_GRAPH_NODES]
    index_by_id = {node_id: index for index, node_id in enumerate(ranked_nodes)}
    edge_total = max(1.0, float(len(observed_edges)))
    strength_total = max(1.0, float(sum(strength.values())))
    timestamps = [timestamp for *_unused, timestamp in observed_edges if timestamp > 0.0]
    min_time = min(timestamps) if timestamps else 0.0
    max_span = max(1.0, (max(timestamps) - min_time) if timestamps else 1.0)

    node_features: list[tuple[float, ...]] = []
    for node_id in ranked_nodes:
        payload = node_payloads.get(node_id, {})
        node_attr: list[float] = []
        kcore: list[float] = []
        _flatten_numeric(payload.get("node_attr"), node_attr)
        _flatten_numeric(payload.get("kcore"), kcore)
        out_value = out_degree[node_id]
        in_value = in_degree[node_id]
        strength_value = strength[node_id]
        active_span = max(0.0, last_seen.get(node_id, 0.0) - first_seen.get(node_id, 0.0))
        first_offset = max(0.0, first_seen.get(node_id, min_time) - min_time)
        node_features.append(
            (
                math.log1p(out_value) / math.log1p(edge_total),
                math.log1p(in_value) / math.log1p(edge_total),
                math.log1p(out_value + in_value) / math.log1p(edge_total),
                math.log1p(strength_value) / math.log1p(strength_total),
                math.tanh(_safe_mean(node_attr)),
                math.tanh(_safe_std(node_attr)),
                math.tanh(_safe_max(node_attr)),
                math.tanh(_safe_mean(kcore)),
                math.tanh(_safe_std(kcore)),
                min(1.0, active_span / max_span),
                min(1.0, first_offset / max_span),
                1.0,
            )
        )

    edge_index: list[tuple[int, int]] = []
    edge_weight: list[float] = []
    sorted_edges = sorted(
        observed_edges,
        key=lambda item: (
            item[3],
            -item[2],
            item[0],
            item[1],
        ),
    )
    for source, target, weight, timestamp in sorted_edges:
        if source not in index_by_id or target not in index_by_id:
            continue
        time_offset = max(0.0, timestamp - min_time) if timestamp > 0.0 else 0.0
        time_weight = 1.0 + min(1.0, time_offset / max_span)
        edge_index.append((index_by_id[source], index_by_id[target]))
        edge_weight.append(math.log1p(weight) * time_weight)
        if len(edge_index) >= _MAX_DEEP_GRAPH_EDGES:
            break
    return _GraphSketch(
        node_features=tuple(node_features),
        edge_index=tuple(edge_index),
        edge_weight=tuple(edge_weight),
    )


def _coerce_graph_sketch(value: Any) -> _GraphSketch:
    if isinstance(value, _GraphSketch):
        return value
    if isinstance(value, dict):
        return _GraphSketch(
            node_features=tuple(tuple(float(item) for item in row) for row in value["node_features"]),
            edge_index=tuple(tuple(int(item) for item in edge) for edge in value["edge_index"]),
            edge_weight=tuple(float(item) for item in value["edge_weight"]),
        )
    raise ValueError("cached public Detection graph sketch has an unsupported type")


def _graph_for_case(case_id: str) -> _GraphSketch:
    cached = resolve_public_detection_graph_sketch(case_id)
    if cached is not None:
        return _coerce_graph_sketch(cached)
    return _load_deep_graph_sketch(resolve_public_detection_source_path(case_id).as_posix())


def _require_torch():
    try:
        import torch
        from torch import nn
        import torch.nn.functional as functional
    except ImportError as exc:
        raise ValueError("torch is required for deep Detection candidates") from exc
    return torch, nn, functional


def _require_pyg():
    try:
        from torch_geometric.data import Batch, Data
        from torch_geometric.nn import GCNConv, GINConv, SAGEConv, global_max_pool, global_mean_pool
    except ImportError as exc:
        raise ValueError("torch_geometric is required for deep PyG Detection candidates") from exc
    return Batch, Data, GCNConv, GINConv, SAGEConv, global_max_pool, global_mean_pool


def _device_for(torch) -> Any:
    return torch.device("cuda" if torch.cuda.is_available() else "cpu")


def _seed_torch(torch, seed: int) -> None:
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


def _seed_for(method_id: str, partitions: DetectionPartitions) -> int:
    payload = {
        "method_id": method_id,
        "train": partitions.train_fingerprint,
        "validation": partitions.validation_fingerprint,
    }
    digest = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return int(digest[:8], 16)


def _feature_matrix(examples: tuple[_DeepExample, ...]) -> np.ndarray:
    return np.asarray([example.feature_values for example in examples], dtype=np.float64)


def _labels(examples: tuple[_DeepExample, ...]) -> np.ndarray:
    return np.asarray([int(example.label) for example in examples], dtype=np.int64)


def _standardize_arrays(
    train_x: np.ndarray,
    validation_x: np.ndarray,
    test_x: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, tuple[float, ...], tuple[float, ...]]:
    mean = np.mean(train_x, axis=0)
    scale = np.std(train_x, axis=0)
    scale = np.where(scale == 0.0, 1.0, scale)
    return (
        (train_x - mean) / scale,
        (validation_x - mean) / scale,
        (test_x - mean) / scale,
        tuple(float(value) for value in mean),
        tuple(float(value) for value in scale),
    )


def _standardize_train_only(
    train: tuple[_DeepExample, ...],
    validation: tuple[_DeepExample, ...],
    test: tuple[_DeepExample, ...],
) -> tuple[np.ndarray, np.ndarray, np.ndarray, tuple[float, ...], tuple[float, ...]]:
    return _standardize_arrays(_feature_matrix(train), _feature_matrix(validation), _feature_matrix(test))


def _configs(kind: str, train_count: int, method_id: str = "") -> tuple[_TrainConfig, ...]:
    if train_count <= _SMOKE_THRESHOLD:
        if kind == "graph":
            return (
                _TrainConfig(16, 2, 0.1, 0.003, 1.0e-4, 32, 8, "smoke_small_fixture"),
            )
        return (
            _TrainConfig(32, 2, 0.1, 0.003, 1.0e-4, 48, 10, "smoke_small_fixture"),
        )
    if kind == "graph":
        return tuple(
            _TrainConfig(hidden, layers, dropout, lr, 1.0e-4, 200, 25, "medium_5seed_grid")
            for hidden in (32, 64)
            for layers in (2, 3)
            for dropout in (0.1, 0.3)
            for lr in (0.001, 0.003)
        )
    if kind == "len_mlp":
        if method_id == "deep_len_fast_mlp_fused_detector":
            return (
                _TrainConfig(
                    16,
                    1,
                    0.0,
                    0.003,
                    1.0e-3,
                    80,
                    0,
                    "fast_len_sklearn_mlp_single_v1",
                ),
            )
        return tuple(
            _TrainConfig(hidden, layers, 0.0, lr, alpha, 250, 0, "fast_len_sklearn_mlp_grid_v2")
            for hidden in (16, 32)
            for layers in (1, 2)
            for lr in (0.001, 0.003)
            for alpha in (1.0e-4,)
        )
    if method_id == "deep_tabular_residual_detector":
        return (
            _TrainConfig(64, 2, 0.1, 0.003, 1.0e-4, 40, 5, "fast_tabular_single_v4"),
        )
    return (
        _TrainConfig(64, 2, 0.1, 0.003, 1.0e-4, 40, 5, "fast_tabular_single_v4"),
    )


def _calibration_and_score(
    logits: np.ndarray,
    labels: np.ndarray,
) -> tuple[float, float, float, float, str, float]:
    try:
        slope, intercept, _iterations = _fit_platt(
            logits,
            labels.astype(np.float64),
            regularization=0.001,
            max_iterations=256,
            tolerance=1.0e-10,
        )
        mode = "one_dimensional_platt_scaling"
    except ValueError:
        slope = 1.0
        intercept = 0.0
        mode = "identity_sigmoid_fallback"
    probabilities = _sigmoid(float(slope) * logits + float(intercept))
    try:
        lower, upper = _select_thresholds(probabilities, labels.astype(np.int64))
    except ValueError:
        lower, upper = 0.45, 0.55
        mode = f"{mode}_with_default_selective_thresholds"
    covered = (probabilities <= lower) | (probabilities >= upper)
    if not np.any(covered):
        score = 0.0
    else:
        predictions = (probabilities[covered] >= upper).astype(np.int64)
        covered_labels = labels[covered].astype(np.int64)
        score = _macro_f1(covered_labels, predictions) * float(np.mean(covered))
    return float(slope), float(intercept), float(lower), float(upper), mode, float(score)


def _binary_f1(labels: np.ndarray, predictions: np.ndarray, positive_label: int) -> float:
    true_positive = int(np.sum((labels == positive_label) & (predictions == positive_label)))
    false_positive = int(np.sum((labels != positive_label) & (predictions == positive_label)))
    false_negative = int(np.sum((labels == positive_label) & (predictions != positive_label)))
    denominator = 2 * true_positive + false_positive + false_negative
    return 0.0 if denominator == 0 else (2.0 * true_positive) / denominator


def _macro_f1(labels: np.ndarray, predictions: np.ndarray) -> float:
    return float((_binary_f1(labels, predictions, 0) + _binary_f1(labels, predictions, 1)) / 2.0)


def _state_hash(model: Any) -> str:
    payload: dict[str, list[float]] = {}
    for name, value in sorted(model.state_dict().items()):
        payload[name] = [
            round(float(item), 8)
            for item in value.detach().cpu().reshape(-1).tolist()[:512]
        ]
    return "sha256:" + hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    ).hexdigest()


def _sklearn_state_hash(model: Any) -> str:
    payload: dict[str, Any] = {
        "classes": [int(value) for value in getattr(model, "classes_", ())],
        "loss": float(getattr(model, "loss_", 0.0)),
        "n_iter": int(getattr(model, "n_iter_", 0)),
    }
    for prefix in ("coefs_", "intercepts_"):
        values = []
        for value in getattr(model, prefix, ()):
            array = np.asarray(value, dtype=np.float64).reshape(-1)
            values.append([round(float(item), 8) for item in array[:512].tolist()])
        payload[prefix] = values
    return "sha256:" + hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    ).hexdigest()


def _artifact(
    *,
    method_id: str,
    algorithm: str,
    fit: _FitResult,
    train: tuple[_DeepExample, ...],
    validation: tuple[_DeepExample, ...],
    feature_width: int,
) -> DetectionModelArtifact:
    return DetectionModelArtifact(
        feature_schema=DetectionFeatureSchema(
            version=f"cogguard.public-detection-deep/{method_id}/v1",
            names=("deep_model_logit",),
        ),
        scaler_mean=(0.0,),
        scaler_scale=(1.0,),
        coefficients=(1.0,),
        intercept=0.0,
        calibrator_slope=fit.calibrator_slope,
        calibrator_intercept=fit.calibrator_intercept,
        lower_decision_threshold=fit.lower_threshold,
        upper_decision_threshold=fit.upper_threshold,
        validation_ood_min=(float(np.min(fit.validation_logits)),),
        validation_ood_max=(float(np.max(fit.validation_logits)),),
        optimizer_config={
            "algorithm": algorithm,
            "method_id": method_id,
            "selected_hidden_dim": fit.selected_config.hidden_dim,
            "selected_layers": fit.selected_config.layers,
            "selected_dropout": fit.selected_config.dropout,
            "selected_learning_rate": fit.selected_config.learning_rate,
            "selected_weight_decay": fit.selected_config.weight_decay,
            "max_epochs": fit.selected_config.max_epochs,
            "patience": fit.selected_config.patience,
            "searched_config_count": fit.searched_config_count,
            "search_budget": fit.selected_config.search_budget,
            "feature_width": feature_width,
            "internal_feature_width": fit.internal_feature_width,
            "max_graph_nodes": _MAX_DEEP_GRAPH_NODES,
            "max_graph_edges": _MAX_DEEP_GRAPH_EDGES,
            "model_state_hash": fit.model_state_hash,
            "device": fit.device,
        },
        calibrator_config={
            "algorithm": fit.calibration_mode,
            "regularization": 0.001,
        },
        threshold_objective="maximize_covered_macro_f1_times_coverage",
        train_fit_case_ids_fingerprint=case_id_fingerprint(example.case_id for example in train),
        validation_calibration_case_ids_fingerprint=case_id_fingerprint(example.case_id for example in validation),
        validation_threshold_case_ids_fingerprint=case_id_fingerprint(example.case_id for example in validation),
        validation_ood_case_ids_fingerprint=case_id_fingerprint(example.case_id for example in validation),
    )


def _predictions(
    *,
    artifact: DetectionModelArtifact,
    examples: tuple[_DeepExample, ...],
    logits: np.ndarray,
) -> tuple[DetectionPrediction, ...]:
    probabilities = _sigmoid(artifact.calibrator_slope * logits + artifact.calibrator_intercept)
    low = artifact.validation_ood_min[0]
    high = artifact.validation_ood_max[0]
    predictions: list[DetectionPrediction] = []
    for example, logit, probability in zip(examples, logits, probabilities, strict=True):
        if logit < low or logit > high:
            decision = "abstain"
        elif probability <= artifact.lower_decision_threshold:
            decision = "benign_coordination"
        elif probability >= artifact.upper_decision_threshold:
            decision = "harmful_coordination"
        else:
            decision = "abstain"
        predictions.append(
            DetectionPrediction(
                case_id=example.case_id,
                harmful_probability=float(probability),
                decision=decision,
            )
        )
    return tuple(predictions)


def _case_feature_indices(feature_names: tuple[str, ...], *, tabular: bool) -> tuple[int, ...]:
    if tabular:
        indices = tuple(
            index for index, name in enumerate(feature_names) if name not in STAGE1_FEATURE_NAMES
        )
        if not indices:
            raise ValueError("tabular deep detector requires non-Stage-1 feature-table inputs")
        return indices
    return tuple(range(len(feature_names)))


def _project_values(values: tuple[float, ...], indices: tuple[int, ...]) -> tuple[float, ...]:
    return tuple(float(values[index]) for index in indices)


def _graph_node_features_for_pyg(graph: _GraphSketch) -> tuple[tuple[float, ...], ...]:
    rows: list[tuple[float, ...]] = []
    for row in graph.node_features:
        cleaned = tuple(_finite(value) for value in row[:_DEEP_NODE_FEATURE_WIDTH])
        if len(cleaned) < _DEEP_NODE_FEATURE_WIDTH:
            cleaned = cleaned + (0.0,) * (_DEEP_NODE_FEATURE_WIDTH - len(cleaned))
        rows.append(cleaned)
    if not rows:
        return ((0.0,) * _DEEP_NODE_FEATURE_WIDTH,)
    return tuple(rows)


def _graph_edges_for_pyg(graph: _GraphSketch, node_count: int) -> tuple[tuple[tuple[int, int], ...], tuple[float, ...]]:
    edge_index: list[tuple[int, int]] = []
    edge_weight: list[float] = []
    for index, edge in enumerate(graph.edge_index):
        if len(edge) != 2:
            continue
        source, target = int(edge[0]), int(edge[1])
        if source < 0 or target < 0 or source >= node_count or target >= node_count:
            continue
        weight = graph.edge_weight[index] if index < len(graph.edge_weight) else 1.0
        edge_index.append((source, target))
        edge_weight.append(max(0.0, _finite(weight, 1.0)))
    return tuple(edge_index), tuple(edge_weight)


def _graph_internal_features(graph: _GraphSketch) -> tuple[float, ...]:
    node_values = np.asarray(_graph_node_features_for_pyg(graph), dtype=np.float64)
    _, weights = _graph_edges_for_pyg(graph, int(node_values.shape[0]))
    edge_weights = np.asarray(weights, dtype=np.float64)
    if edge_weights.size == 0:
        edge_weights = np.zeros((1,), dtype=np.float64)
    node_count = float(node_values.shape[0])
    edge_count = float(len(graph.edge_index))
    possible_edges = max(1.0, node_count * max(1.0, node_count - 1.0))
    pooled = np.concatenate(
        (
            node_values.mean(axis=0),
            node_values.std(axis=0),
            node_values.max(axis=0),
            np.asarray(
                (
                    math.log1p(node_count),
                    math.log1p(edge_count),
                    edge_count / possible_edges,
                    float(edge_weights.mean()),
                    float(edge_weights.std()),
                    float(edge_weights.max()),
                ),
                dtype=np.float64,
            ),
        )
    )
    return tuple(float(value) for value in pooled)


def _shared_feature_names(partitions: DetectionPartitions) -> tuple[str, ...]:
    cases: tuple[Any, ...] = (
        *partitions.train_cases,
        *partitions.validation_cases,
        *partitions.test_cases,
    )
    first = cases[0]
    schema = DetectionFeatureSchema(version=first.feature_schema_version, names=first.feature_names)
    if first.feature_schema_fingerprint != schema.fingerprint:
        raise ValueError("deep Detection partitions contain an invalid feature schema fingerprint")
    for case in cases[1:]:
        if (
            case.feature_schema_version != schema.version
            or case.feature_schema_fingerprint != schema.fingerprint
            or tuple(case.feature_names) != schema.names
        ):
            raise ValueError("deep Detection partitions do not share one ordered feature schema")
    return schema.names


def _examples_from_partitions(
    partitions: DetectionPartitions,
    *,
    graph: bool,
    tabular: bool,
) -> tuple[tuple[_DeepExample, ...], tuple[_DeepExample, ...], tuple[_DeepExample, ...], int]:
    names = _shared_feature_names(partitions)
    indices = _case_feature_indices(names, tabular=tabular)

    def training(case: DetectionTrainingCase) -> _DeepExample:
        return _DeepExample(
            case_id=case.case_id,
            cluster_id=case.cluster_id,
            label=case.label,
            feature_values=_project_values(case.feature_values, indices),
            graph=_graph_for_case(case.case_id) if graph else None,
        )

    def inference(case: DetectionInferenceCase) -> _DeepExample:
        return _DeepExample(
            case_id=case.case_id,
            cluster_id=case.cluster_id,
            label=None,
            feature_values=_project_values(case.feature_values, indices),
            graph=_graph_for_case(case.case_id) if graph else None,
        )

    return (
        tuple(training(case) for case in partitions.train_cases),
        tuple(training(case) for case in partitions.validation_cases),
        tuple(inference(case) for case in partitions.test_cases),
        len(indices),
    )


def _fit_tabular(
    method_id: str,
    train: tuple[_DeepExample, ...],
    validation: tuple[_DeepExample, ...],
    test: tuple[_DeepExample, ...],
    *,
    seed: int,
) -> tuple[_FitResult, np.ndarray]:
    torch, nn, functional = _require_torch()
    device = _device_for(torch)
    residual = method_id == "deep_tabular_residual_detector"
    train_x, validation_x, test_x, mean, scale = _standardize_train_only(train, validation, test)
    train_y = _labels(train)
    validation_y = _labels(validation)
    input_dim = train_x.shape[1]

    class ResidualBlock(nn.Module):
        def __init__(self, hidden_dim: int, dropout: float) -> None:
            super().__init__()
            self.net = nn.Sequential(
                nn.LayerNorm(hidden_dim),
                nn.Linear(hidden_dim, hidden_dim),
                nn.ReLU(),
                nn.Dropout(dropout),
                nn.Linear(hidden_dim, hidden_dim),
            )

        def forward(self, values):
            return values + self.net(values)

    class Model(nn.Module):
        def __init__(self, config: _TrainConfig) -> None:
            super().__init__()
            if residual:
                blocks = [nn.Linear(input_dim, config.hidden_dim), nn.ReLU()]
                blocks.extend(
                    ResidualBlock(config.hidden_dim, config.dropout)
                    for _ in range(max(1, config.layers - 1))
                )
                blocks.append(nn.LayerNorm(config.hidden_dim))
                blocks.append(nn.ReLU())
                blocks.append(nn.Dropout(config.dropout))
                blocks.append(nn.Linear(config.hidden_dim, 1))
                self.net = nn.Sequential(*blocks)
            else:
                blocks = []
                width = input_dim
                for _ in range(config.layers):
                    blocks.extend(
                        [
                            nn.Linear(width, config.hidden_dim),
                            nn.ReLU(),
                            nn.Dropout(config.dropout),
                        ]
                    )
                    width = config.hidden_dim
                blocks.append(nn.Linear(width, 1))
                self.net = nn.Sequential(*blocks)

        def forward(self, values):
            return self.net(values).squeeze(-1)

    def fit_config(config: _TrainConfig, config_seed: int):
        random.seed(config_seed)
        np.random.seed(config_seed % (2**32 - 1))
        _seed_torch(torch, config_seed)
        model = Model(config).to(device)
        optimizer = torch.optim.Adam(
            model.parameters(), lr=config.learning_rate, weight_decay=config.weight_decay
        )
        x_train = torch.tensor(train_x, dtype=torch.float32, device=device)
        y_train = torch.tensor(train_y.astype(np.float32), dtype=torch.float32, device=device)
        x_validation = torch.tensor(validation_x, dtype=torch.float32, device=device)
        y_validation = torch.tensor(validation_y.astype(np.float32), dtype=torch.float32, device=device)
        positive = float(np.sum(train_y == 1))
        negative = float(np.sum(train_y == 0))
        pos_weight = torch.tensor(negative / max(positive, 1.0), dtype=torch.float32, device=device)
        best_state = None
        best_loss = math.inf
        stale = 0
        for _epoch in range(config.max_epochs):
            model.train()
            logits = model(x_train)
            loss = functional.binary_cross_entropy_with_logits(
                logits, y_train, pos_weight=pos_weight
            )
            optimizer.zero_grad()
            loss.backward()
            optimizer.step()
            model.eval()
            with torch.no_grad():
                validation_loss = functional.binary_cross_entropy_with_logits(
                    model(x_validation), y_validation
                )
            loss_value = float(validation_loss.item())
            if loss_value + 1.0e-8 < best_loss:
                best_loss = loss_value
                best_state = {
                    key: value.detach().clone()
                    for key, value in model.state_dict().items()
                }
                stale = 0
            else:
                stale += 1
                if stale >= config.patience:
                    break
        if best_state is not None:
            model.load_state_dict(best_state)
        return model

    best: tuple[float, _FitResult, int] | None = None
    configs = _configs("tabular", len(train), method_id)
    for index, config in enumerate(configs):
        model = fit_config(config, seed + index * 7919)
        model.eval()
        with torch.no_grad():
            validation_logits = (
                model(torch.tensor(validation_x, dtype=torch.float32, device=device))
                .detach()
                .cpu()
                .numpy()
                .astype(np.float64)
            )
        slope, intercept, lower, upper, mode, score = _calibration_and_score(
            validation_logits, validation_y
        )
        result = _FitResult(
            model=model,
            validation_logits=validation_logits,
            calibrator_slope=slope,
            calibrator_intercept=intercept,
            lower_threshold=lower,
            upper_threshold=upper,
            calibration_mode=mode,
            selected_config=config,
            searched_config_count=len(configs),
            model_state_hash=_state_hash(model),
            global_mean=mean,
            global_scale=scale,
            device=str(device),
            internal_feature_width=0,
        )
        rank = (score, -index)
        if best is None or rank > (best[0], -best[2]):
            best = (score, result, index)
    if best is None:
        raise ValueError("tabular deep detector did not train any candidate")
    fit = best[1]
    fit.model.eval()
    with torch.no_grad():
        test_logits = (
            fit.model(torch.tensor(test_x, dtype=torch.float32, device=device))
            .detach()
            .cpu()
            .numpy()
            .astype(np.float64)
        )
    return fit, test_logits


def _graph_internal_matrix(examples: tuple[_DeepExample, ...]) -> np.ndarray:
    values = [
        _graph_internal_features(example.graph)
        for example in examples
        if example.graph is not None
    ]
    if len(values) != len(examples):
        raise ValueError("LEN fused deep detector requires graph sketches for all partitions")
    return np.asarray(values, dtype=np.float64)


def _fit_len_mlp(
    method_id: str,
    train: tuple[_DeepExample, ...],
    validation: tuple[_DeepExample, ...],
    test: tuple[_DeepExample, ...],
    *,
    seed: int,
) -> tuple[_FitResult, np.ndarray]:
    try:
        from sklearn.exceptions import ConvergenceWarning
        from sklearn.neural_network import MLPClassifier
    except ImportError as exc:
        raise ValueError("sklearn is required for the LEN fused deep detector") from exc
    import warnings

    base_train_x = _feature_matrix(train)
    base_validation_x = _feature_matrix(validation)
    base_test_x = _feature_matrix(test)
    graph_train_x = _graph_internal_matrix(train)
    graph_validation_x = _graph_internal_matrix(validation)
    graph_test_x = _graph_internal_matrix(test)
    train_x, validation_x, test_x, mean, scale = _standardize_arrays(
        np.concatenate((base_train_x, graph_train_x), axis=1),
        np.concatenate((base_validation_x, graph_validation_x), axis=1),
        np.concatenate((base_test_x, graph_test_x), axis=1),
    )
    train_y = _labels(train)
    validation_y = _labels(validation)
    internal_feature_width = int(graph_train_x.shape[1])

    def probability_logits(model: Any, values: np.ndarray) -> np.ndarray:
        classes = list(getattr(model, "classes_", ()))
        if 1 not in classes:
            raise ValueError("LEN fused deep detector did not learn the positive class")
        positive_index = classes.index(1)
        probabilities = np.asarray(model.predict_proba(values), dtype=np.float64)[:, positive_index]
        probabilities = np.clip(probabilities, 1.0e-6, 1.0 - 1.0e-6)
        return np.log(probabilities / (1.0 - probabilities)).astype(np.float64)

    def fit_config(config: _TrainConfig, config_seed: int):
        random.seed(config_seed)
        np.random.seed(config_seed % (2**32 - 1))
        model = MLPClassifier(
            hidden_layer_sizes=(config.hidden_dim,) * config.layers,
            activation="relu",
            solver="adam",
            alpha=config.weight_decay,
            learning_rate_init=config.learning_rate,
            max_iter=config.max_epochs,
            early_stopping=False,
            random_state=config_seed,
            batch_size=min(32, max(2, len(train))),
            shuffle=True,
        )
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", ConvergenceWarning)
            model.fit(train_x, train_y)
        return model

    best: tuple[float, _FitResult, int] | None = None
    configs = _configs("len_mlp", len(train), method_id)
    for index, config in enumerate(configs):
        model = fit_config(config, seed + index * 3571)
        validation_logits = probability_logits(model, validation_x)
        slope, intercept, lower, upper, mode, score = _calibration_and_score(
            validation_logits,
            validation_y,
        )
        result = _FitResult(
            model=model,
            validation_logits=validation_logits,
            calibrator_slope=slope,
            calibrator_intercept=intercept,
            lower_threshold=lower,
            upper_threshold=upper,
            calibration_mode=mode,
            selected_config=config,
            searched_config_count=len(configs),
            model_state_hash=_sklearn_state_hash(model),
            global_mean=mean,
            global_scale=scale,
            device="cpu/sklearn",
            internal_feature_width=internal_feature_width,
        )
        rank = (score, -index)
        if best is None or rank > (best[0], -best[2]):
            best = (score, result, index)
    if best is None:
        raise ValueError("LEN fused deep detector did not train any candidate")
    fit = best[1]
    test_logits = probability_logits(fit.model, test_x)
    return fit, test_logits


def _fit_graph(
    method_id: str,
    train: tuple[_DeepExample, ...],
    validation: tuple[_DeepExample, ...],
    test: tuple[_DeepExample, ...],
    *,
    seed: int,
) -> tuple[_FitResult, np.ndarray]:
    torch, nn, functional = _require_torch()
    device = _device_for(torch)
    Batch, Data, GCNConv, GINConv, SAGEConv, global_max_pool, global_mean_pool = _require_pyg()
    base_train_x = _feature_matrix(train)
    base_validation_x = _feature_matrix(validation)
    base_test_x = _feature_matrix(test)
    graph_train_x = np.asarray(
        [_graph_internal_features(example.graph) for example in train if example.graph is not None],
        dtype=np.float64,
    )
    graph_validation_x = np.asarray(
        [_graph_internal_features(example.graph) for example in validation if example.graph is not None],
        dtype=np.float64,
    )
    graph_test_x = np.asarray(
        [_graph_internal_features(example.graph) for example in test if example.graph is not None],
        dtype=np.float64,
    )
    if (
        graph_train_x.shape[0] != len(train)
        or graph_validation_x.shape[0] != len(validation)
        or graph_test_x.shape[0] != len(test)
    ):
        raise ValueError("graph deep detector requires graph sketches for all partitions")
    train_x, validation_x, test_x, mean, scale = _standardize_arrays(
        np.concatenate((base_train_x, graph_train_x), axis=1),
        np.concatenate((base_validation_x, graph_validation_x), axis=1),
        np.concatenate((base_test_x, graph_test_x), axis=1),
    )
    train_y = _labels(train)
    validation_y = _labels(validation)
    global_dim = train_x.shape[1]
    internal_feature_width = int(graph_train_x.shape[1])
    node_dim = _DEEP_NODE_FEATURE_WIDTH

    def to_data(example: _DeepExample, global_features: np.ndarray, label: int | None = None):
        if example.graph is None:
            raise ValueError("graph deep detector requires graph sketches")
        graph = example.graph
        node_features = _graph_node_features_for_pyg(graph)
        edge_pairs, weights = _graph_edges_for_pyg(graph, len(node_features))
        x = torch.tensor(node_features, dtype=torch.float32)
        if edge_pairs:
            edge_index = torch.tensor(edge_pairs, dtype=torch.long).t().contiguous()
            edge_weight = torch.tensor(weights, dtype=torch.float32)
            edge_weight = edge_weight / edge_weight.mean().clamp_min(1.0e-6)
        else:
            edge_index = torch.empty((2, 0), dtype=torch.long)
            edge_weight = torch.empty((0,), dtype=torch.float32)
        data = Data(x=x, edge_index=edge_index, edge_weight=edge_weight)
        data.global_features = torch.tensor(global_features, dtype=torch.float32).reshape(1, -1)
        if label is not None:
            data.y = torch.tensor([float(label)], dtype=torch.float32)
        return data

    train_data = tuple(to_data(example, train_x[index], int(example.label)) for index, example in enumerate(train))
    validation_data = tuple(to_data(example, validation_x[index], int(example.label)) for index, example in enumerate(validation))
    test_data = tuple(to_data(example, test_x[index], None) for index, example in enumerate(test))

    class Model(nn.Module):
        def __init__(self, config: _TrainConfig) -> None:
            super().__init__()
            self.method_id = method_id
            self.dropout = config.dropout
            convs = []
            width = node_dim
            for layer_index in range(config.layers):
                if method_id == "deep_pyg_graphsage_fused_detector":
                    conv = SAGEConv(width, config.hidden_dim)
                elif method_id == "deep_pyg_gin_fused_detector":
                    conv = GINConv(
                        nn.Sequential(
                            nn.Linear(width, config.hidden_dim),
                            nn.ReLU(),
                            nn.Linear(config.hidden_dim, config.hidden_dim),
                        )
                    )
                else:
                    conv = GCNConv(width, config.hidden_dim)
                convs.append(conv)
                width = config.hidden_dim
            self.convs = nn.ModuleList(convs)
            self.classifier = nn.Sequential(
                nn.Linear(config.hidden_dim * 2 + global_dim, config.hidden_dim),
                nn.ReLU(),
                nn.Dropout(config.dropout),
                nn.Linear(config.hidden_dim, 1),
            )

        def forward(self, batch):
            hidden = batch.x
            for conv in self.convs:
                if self.method_id == "deep_pyg_gcn_fused_detector":
                    hidden = conv(hidden, batch.edge_index, batch.edge_weight)
                else:
                    hidden = conv(hidden, batch.edge_index)
                hidden = functional.relu(hidden)
                hidden = functional.dropout(hidden, p=self.dropout, training=self.training)
            pooled = torch.cat(
                (
                    global_mean_pool(hidden, batch.batch),
                    global_max_pool(hidden, batch.batch),
                    batch.global_features,
                ),
                dim=1,
            )
            return self.classifier(pooled).squeeze(-1)

    def make_batches(data_items: tuple[Any, ...], *, batch_size: int = 32) -> tuple[Any, ...]:
        return tuple(
            Batch.from_data_list(list(data_items[start:start + batch_size]))
            for start in range(0, len(data_items), batch_size)
        )

    train_batch = Batch.from_data_list(list(train_data)).to(device)
    validation_batches = tuple(batch.to(device) for batch in make_batches(validation_data, batch_size=32))
    test_batches = tuple(batch.to(device) for batch in make_batches(test_data, batch_size=32))

    def logits(model, batches: tuple[Any, ...]) -> np.ndarray:
        values: list[float] = []
        model.eval()
        with torch.no_grad():
            for batch in batches:
                output = model(batch).detach().cpu().numpy().reshape(-1)
                values.extend(float(item) for item in output)
        return np.asarray(values, dtype=np.float64)

    def fit_config(config: _TrainConfig, config_seed: int):
        random.seed(config_seed)
        np.random.seed(config_seed % (2**32 - 1))
        _seed_torch(torch, config_seed)
        model = Model(config).to(device)
        optimizer = torch.optim.Adam(
            model.parameters(), lr=config.learning_rate, weight_decay=config.weight_decay
        )
        positive = float(np.sum(train_y == 1))
        negative = float(np.sum(train_y == 0))
        pos_weight = torch.tensor(negative / max(positive, 1.0), dtype=torch.float32, device=device)
        best_state = None
        best_loss = math.inf
        stale = 0
        for _epoch in range(config.max_epochs):
            model.train()
            output = model(train_batch)
            loss = functional.binary_cross_entropy_with_logits(
                output,
                train_batch.y.reshape(-1),
                pos_weight=pos_weight,
            )
            optimizer.zero_grad()
            loss.backward()
            optimizer.step()
            model.eval()
            with torch.no_grad():
                losses = []
                for batch in validation_batches:
                    validation_loss = functional.binary_cross_entropy_with_logits(
                        model(batch), batch.y.reshape(-1)
                    )
                    losses.append(float(validation_loss.item()))
            loss_value = float(np.mean(losses)) if losses else math.inf
            if loss_value + 1.0e-8 < best_loss:
                best_loss = loss_value
                best_state = {
                    key: value.detach().clone()
                    for key, value in model.state_dict().items()
                }
                stale = 0
            else:
                stale += 1
                if stale >= config.patience:
                    break
        if best_state is not None:
            model.load_state_dict(best_state)
        return model

    best: tuple[float, _FitResult, int] | None = None
    configs = _configs("graph", len(train))
    for index, config in enumerate(configs):
        model = fit_config(config, seed + index * 6151)
        validation_logits = logits(model, validation_batches)
        slope, intercept, lower, upper, mode, score = _calibration_and_score(
            validation_logits, validation_y
        )
        result = _FitResult(
            model=model,
            validation_logits=validation_logits,
            calibrator_slope=slope,
            calibrator_intercept=intercept,
            lower_threshold=lower,
            upper_threshold=upper,
            calibration_mode=mode,
            selected_config=config,
            searched_config_count=len(configs),
            model_state_hash=_state_hash(model),
            global_mean=mean,
            global_scale=scale,
            device=str(device),
            internal_feature_width=internal_feature_width,
        )
        rank = (score, -index)
        if best is None or rank > (best[0], -best[2]):
            best = (score, result, index)
    if best is None:
        raise ValueError("graph deep detector did not train any candidate")
    fit = best[1]
    test_logits = logits(fit.model, test_batches)
    return fit, test_logits


class DeepDetectionImplementation(_LearnedDetectionImplementation):
    __slots__ = ("method_id", "implementation_id", "unavailable_reason")

    def __init__(self, *, method_id: str, implementation_id: str) -> None:
        if method_id not in DEEP_DETECTION_METHODS:
            raise ValueError("unknown deep Detection method")
        self.method_id = method_id
        self.implementation_id = implementation_id
        self.unavailable_reason = None

    def execute(self, partitions: DetectionPartitions) -> DetectionExecutionOutput:
        if not isinstance(partitions, DetectionPartitions):
            raise ValueError("deep Detection execution requires DetectionPartitions")
        seed = _seed_for(self.method_id, partitions)
        is_graph = self.method_id in DEEP_PYG_DETECTION_METHODS
        is_tabular = self.method_id in DEEP_TABULAR_DETECTION_METHODS
        is_len_fused = self.method_id in DEEP_LEN_FUSED_DETECTION_METHODS
        train, validation, test, feature_width = _examples_from_partitions(
            partitions,
            graph=is_graph or is_len_fused,
            tabular=is_tabular,
        )
        if {example.label for example in train} != {0, 1}:
            raise ValueError("deep Detection training split must contain both classes")
        if {example.label for example in validation} != {0, 1}:
            raise ValueError("deep Detection validation split must contain both classes")
        if is_graph:
            fit, test_logits = _fit_graph(self.method_id, train, validation, test, seed=seed)
            algorithm = "deep_pyg_graph_fused_detector"
        elif is_len_fused:
            fit, test_logits = _fit_len_mlp(self.method_id, train, validation, test, seed=seed)
            algorithm = "deep_len_graph_stat_mlp_fused_detector"
        else:
            fit, test_logits = _fit_tabular(self.method_id, train, validation, test, seed=seed)
            algorithm = "deep_tabular_feature_detector"
        artifact = _artifact(
            method_id=self.method_id,
            algorithm=algorithm,
            fit=fit,
            train=train,
            validation=validation,
            feature_width=feature_width,
        )
        return DetectionExecutionOutput(
            model_artifact=artifact,
            predictions=_predictions(artifact=artifact, examples=test, logits=test_logits),
        )


__all__ = [
    "DEEP_DETECTION_METHODS",
    "DEEP_LEN_FUSED_DETECTION_METHODS",
    "DEEP_PYG_DETECTION_METHODS",
    "DEEP_TABULAR_DETECTION_METHODS",
    "DeepDetectionImplementation",
]
