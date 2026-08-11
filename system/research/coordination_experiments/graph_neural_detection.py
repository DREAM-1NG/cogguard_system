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
from research.coordination_detect.learned import _fit_platt, _select_thresholds, _sigmoid

from .baselines import LearnedDetectionImplementation as _LearnedDetectionImplementation
from .public_detection_sources import resolve_public_detection_source_path
from .runner import (
    DetectionExecutionOutput,
    DetectionInferenceCase,
    DetectionPartitions,
    DetectionPrediction,
)


GRAPH_NEURAL_DETECTION_METHODS = frozenset(
    {
        "gcn_graph_classifier",
        "graphsage_graph_classifier",
        "gin_graph_classifier",
        "diffpool_graph_classifier",
    }
)

_GRAPH_NEURAL_EPOCHS = 48
_GRAPH_NEURAL_HIDDEN_DIM = 24
_MAX_SKETCH_NODES = 96
_MAX_SKETCH_EDGES = 512


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


@dataclass(frozen=True, slots=True)
class _GraphSketch:
    node_features: tuple[tuple[float, ...], ...]
    edge_index: tuple[tuple[int, int], ...]
    edge_weight: tuple[float, ...]


@dataclass(frozen=True, slots=True)
class _GraphExample:
    case_id: str
    cluster_id: str
    label: int | None
    graph: _GraphSketch


def _node_id(value: Any, fallback: int) -> str:
    text = str(value if value is not None else fallback).strip()
    return text or str(fallback)


@lru_cache(maxsize=256)
def _load_graph_sketch(source_path: str) -> _GraphSketch:
    path = Path(source_path)
    with path.open("r", encoding="utf-8") as stream:
        data = json.load(stream)
    nodes = data.get("nodes", ())
    links = data.get("links", data.get("edges", ()))
    if not isinstance(nodes, list) or not isinstance(links, list):
        raise ValueError(f"graph baseline expects node-link LEN JSON: {path.name}")

    node_payloads: dict[str, dict[str, Any]] = {}
    for index, node in enumerate(nodes):
        if isinstance(node, dict):
            node_payloads[_node_id(node.get("id"), index)] = node
        else:
            node_payloads[str(index)] = {}

    in_degree: defaultdict[str, float] = defaultdict(float)
    out_degree: defaultdict[str, float] = defaultdict(float)
    strength: defaultdict[str, float] = defaultdict(float)
    observed_edges: list[tuple[str, str, float]] = []
    for link in links:
        if not isinstance(link, dict):
            continue
        source = str(link.get("source", "")).strip()
        target = str(link.get("target", "")).strip()
        if not source or not target:
            continue
        weight = max(0.0, _finite(link.get("Interaction_Count"), 1.0))
        out_degree[source] += 1.0
        in_degree[target] += 1.0
        strength[source] += weight
        strength[target] += weight
        observed_edges.append((source, target, weight))

    candidates = set(node_payloads) | set(in_degree) | set(out_degree)
    if not candidates:
        return _GraphSketch(node_features=((0.0,) * 8,), edge_index=(), edge_weight=())
    ranked_nodes = sorted(
        candidates,
        key=lambda node_id: (
            -(in_degree[node_id] + out_degree[node_id]),
            -strength[node_id],
            node_id,
        ),
    )[:_MAX_SKETCH_NODES]
    index_by_id = {node_id: index for index, node_id in enumerate(ranked_nodes)}
    edge_total = max(1.0, float(len(observed_edges)))
    strength_total = max(1.0, float(sum(strength.values())))
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
        node_features.append(
            (
                math.log1p(out_value) / math.log1p(edge_total),
                math.log1p(in_value) / math.log1p(edge_total),
                math.log1p(out_value + in_value) / math.log1p(edge_total),
                math.log1p(strength_value) / math.log1p(strength_total),
                math.tanh(_safe_mean(node_attr)),
                math.tanh(_safe_std(node_attr)),
                math.tanh(_safe_mean(kcore)),
                1.0,
            )
        )

    edge_index: list[tuple[int, int]] = []
    edge_weight: list[float] = []
    for source, target, weight in observed_edges:
        if source not in index_by_id or target not in index_by_id:
            continue
        edge_index.append((index_by_id[source], index_by_id[target]))
        edge_weight.append(math.log1p(weight))
        if len(edge_index) >= _MAX_SKETCH_EDGES:
            break
    return _GraphSketch(
        node_features=tuple(node_features),
        edge_index=tuple(edge_index),
        edge_weight=tuple(edge_weight),
    )


def _require_torch():
    try:
        import torch
        from torch import nn
        import torch.nn.functional as functional
    except ImportError as exc:  # pragma: no cover - registry blocks this path when torch is absent.
        raise ValueError("torch is required for graph neural Detection baselines") from exc
    return torch, nn, functional


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


def _example_from_training_case(case: DetectionTrainingCase) -> _GraphExample:
    source_path = resolve_public_detection_source_path(case.case_id)
    return _GraphExample(
        case_id=case.case_id,
        cluster_id=case.cluster_id,
        label=case.label,
        graph=_load_graph_sketch(source_path.as_posix()),
    )


def _example_from_inference_case(case: DetectionInferenceCase) -> _GraphExample:
    source_path = resolve_public_detection_source_path(case.case_id)
    return _GraphExample(
        case_id=case.case_id,
        cluster_id=case.cluster_id,
        label=None,
        graph=_load_graph_sketch(source_path.as_posix()),
    )


class _GraphClassifier:
    def __init__(self, method_id: str, *, seed: int, input_dim: int):
        torch, nn, functional = _require_torch()

        class Model(nn.Module):
            def __init__(self) -> None:
                super().__init__()
                self.method_id = method_id
                if method_id == "graphsage_graph_classifier":
                    self.layer1 = nn.Linear(input_dim * 2, _GRAPH_NEURAL_HIDDEN_DIM)
                    self.layer2 = nn.Linear(_GRAPH_NEURAL_HIDDEN_DIM * 2, _GRAPH_NEURAL_HIDDEN_DIM)
                elif method_id == "gin_graph_classifier":
                    self.layer1 = nn.Sequential(
                        nn.Linear(input_dim, _GRAPH_NEURAL_HIDDEN_DIM),
                        nn.ReLU(),
                        nn.Linear(_GRAPH_NEURAL_HIDDEN_DIM, _GRAPH_NEURAL_HIDDEN_DIM),
                    )
                    self.layer2 = nn.Sequential(
                        nn.Linear(_GRAPH_NEURAL_HIDDEN_DIM, _GRAPH_NEURAL_HIDDEN_DIM),
                        nn.ReLU(),
                        nn.Linear(_GRAPH_NEURAL_HIDDEN_DIM, _GRAPH_NEURAL_HIDDEN_DIM),
                    )
                    self.eps1 = nn.Parameter(torch.zeros(()))
                    self.eps2 = nn.Parameter(torch.zeros(()))
                else:
                    self.layer1 = nn.Linear(input_dim, _GRAPH_NEURAL_HIDDEN_DIM)
                    self.layer2 = nn.Linear(_GRAPH_NEURAL_HIDDEN_DIM, _GRAPH_NEURAL_HIDDEN_DIM)
                if method_id == "diffpool_graph_classifier":
                    self.assign = nn.Linear(_GRAPH_NEURAL_HIDDEN_DIM, 8)
                    self.classifier = nn.Sequential(
                        nn.Linear(_GRAPH_NEURAL_HIDDEN_DIM * 2, _GRAPH_NEURAL_HIDDEN_DIM),
                        nn.ReLU(),
                        nn.Linear(_GRAPH_NEURAL_HIDDEN_DIM, 1),
                    )
                else:
                    self.classifier = nn.Linear(_GRAPH_NEURAL_HIDDEN_DIM * 2, 1)

            @staticmethod
            def _aggregate(x, edge_index, edge_weight, *, mean: bool, normalize: bool):
                rows = x.shape[0]
                if edge_index.numel() == 0:
                    return x
                source = edge_index[0]
                target = edge_index[1]
                messages = x[source] * edge_weight.unsqueeze(1)
                out = torch.zeros_like(x)
                out.index_add_(0, target, messages)
                if mean or normalize:
                    degree = torch.zeros(rows, dtype=x.dtype, device=x.device)
                    degree.index_add_(0, target, edge_weight)
                    degree = degree.clamp_min(1.0)
                    out = out / degree.unsqueeze(1)
                if normalize:
                    return 0.5 * (x + out)
                return out

            def _layer(self, x, edge_index, edge_weight, layer, *, sage: bool = False, gin_eps=None):
                if sage:
                    aggregate = self._aggregate(x, edge_index, edge_weight, mean=True, normalize=False)
                    return functional.relu(layer(torch.cat((x, aggregate), dim=1)))
                if gin_eps is not None:
                    aggregate = self._aggregate(x, edge_index, edge_weight, mean=False, normalize=False)
                    return functional.relu(layer((1.0 + gin_eps) * x + aggregate))
                aggregate = self._aggregate(x, edge_index, edge_weight, mean=True, normalize=True)
                return functional.relu(layer(aggregate))

            def forward(self, x, edge_index, edge_weight):
                if self.method_id == "graphsage_graph_classifier":
                    hidden = self._layer(x, edge_index, edge_weight, self.layer1, sage=True)
                    hidden = self._layer(hidden, edge_index, edge_weight, self.layer2, sage=True)
                elif self.method_id == "gin_graph_classifier":
                    hidden = self._layer(x, edge_index, edge_weight, self.layer1, gin_eps=self.eps1)
                    hidden = self._layer(hidden, edge_index, edge_weight, self.layer2, gin_eps=self.eps2)
                else:
                    hidden = self._layer(x, edge_index, edge_weight, self.layer1)
                    hidden = self._layer(hidden, edge_index, edge_weight, self.layer2)
                if self.method_id == "diffpool_graph_classifier":
                    assignment = torch.softmax(self.assign(hidden), dim=1)
                    pooled = assignment.transpose(0, 1) @ hidden
                    pooled = pooled / assignment.sum(dim=0).clamp_min(1.0).unsqueeze(1)
                    readout = torch.cat((pooled.mean(dim=0), pooled.max(dim=0).values), dim=0)
                else:
                    readout = torch.cat((hidden.mean(dim=0), hidden.max(dim=0).values), dim=0)
                return self.classifier(readout).squeeze()

        random.seed(seed)
        np.random.seed(seed % (2**32 - 1))
        torch.manual_seed(seed)
        self.torch = torch
        self.nn = nn
        self.functional = functional
        self.model = Model()

    def _tensorize(self, graph: _GraphSketch):
        torch = self.torch
        x = torch.tensor(graph.node_features, dtype=torch.float32)
        if graph.edge_index:
            edge_index = torch.tensor(graph.edge_index, dtype=torch.long).t().contiguous()
            edge_weight = torch.tensor(graph.edge_weight, dtype=torch.float32)
            edge_weight = edge_weight / edge_weight.mean().clamp_min(1.0e-6)
        else:
            edge_index = torch.empty((2, 0), dtype=torch.long)
            edge_weight = torch.empty((0,), dtype=torch.float32)
        return x, edge_index, edge_weight

    def fit(self, train: tuple[_GraphExample, ...], validation: tuple[_GraphExample, ...], *, seed: int) -> None:
        torch = self.torch
        if {example.label for example in train} != {0, 1}:
            raise ValueError("graph neural Detection training split must contain both classes")
        labels = torch.tensor([int(example.label) for example in train], dtype=torch.long)
        class_counts = torch.bincount(labels, minlength=2).float().clamp_min(1.0)
        class_weights = labels.numel() / (2.0 * class_counts)
        optimizer = torch.optim.Adam(self.model.parameters(), lr=0.01, weight_decay=1.0e-4)
        best_state: dict[str, Any] | None = None
        best_loss = math.inf
        order = list(range(len(train)))
        rng = random.Random(seed)
        for _epoch in range(_GRAPH_NEURAL_EPOCHS):
            rng.shuffle(order)
            self.model.train()
            for index in order:
                example = train[index]
                x, edge_index, edge_weight = self._tensorize(example.graph)
                label = torch.tensor(float(example.label), dtype=torch.float32)
                weight = class_weights[int(example.label)]
                logit = self.model(x, edge_index, edge_weight)
                loss = self.functional.binary_cross_entropy_with_logits(
                    logit.reshape(()),
                    label,
                    weight=weight,
                )
                optimizer.zero_grad()
                loss.backward()
                optimizer.step()
            validation_loss = self._loss(validation)
            if validation_loss < best_loss:
                best_loss = validation_loss
                best_state = {
                    key: value.detach().clone()
                    for key, value in self.model.state_dict().items()
                }
        if best_state is not None:
            self.model.load_state_dict(best_state)

    def _loss(self, examples: tuple[_GraphExample, ...]) -> float:
        if not examples:
            return math.inf
        torch = self.torch
        losses: list[float] = []
        self.model.eval()
        with torch.no_grad():
            for example in examples:
                x, edge_index, edge_weight = self._tensorize(example.graph)
                label = torch.tensor(float(example.label), dtype=torch.float32)
                loss = self.functional.binary_cross_entropy_with_logits(
                    self.model(x, edge_index, edge_weight).reshape(()),
                    label,
                )
                losses.append(float(loss.item()))
        return float(np.mean(losses))

    def logits(self, examples: tuple[_GraphExample, ...]) -> np.ndarray:
        torch = self.torch
        values: list[float] = []
        self.model.eval()
        with torch.no_grad():
            for example in examples:
                x, edge_index, edge_weight = self._tensorize(example.graph)
                values.append(float(self.model(x, edge_index, edge_weight).item()))
        return np.asarray(values, dtype=np.float64)

    def state_hash(self) -> str:
        payload: dict[str, list[float]] = {}
        for name, value in sorted(self.model.state_dict().items()):
            payload[name] = [
                round(float(item), 8)
                for item in value.detach().cpu().reshape(-1).tolist()[:512]
            ]
        return "sha256:" + hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
        ).hexdigest()


def _calibration(values: np.ndarray, labels: np.ndarray) -> tuple[float, float, float, float, str]:
    try:
        slope, intercept, _iterations = _fit_platt(
            values,
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
    probabilities = _sigmoid(slope * values + intercept)
    try:
        lower, upper = _select_thresholds(probabilities, labels.astype(np.int64))
    except ValueError:
        lower, upper = 0.45, 0.55
        mode = f"{mode}_with_default_selective_thresholds"
    return float(slope), float(intercept), float(lower), float(upper), mode


def _artifact(
    *,
    method_id: str,
    model_state_hash: str,
    seed: int,
    train: tuple[_GraphExample, ...],
    validation: tuple[_GraphExample, ...],
    validation_logits: np.ndarray,
    calibrator_slope: float,
    calibrator_intercept: float,
    lower: float,
    upper: float,
    calibration_mode: str,
) -> DetectionModelArtifact:
    schema = DetectionFeatureSchema(
        version=f"cogguard.public-detection-graph-neural/{method_id}/v1",
        names=("graph_neural_logit",),
    )
    return DetectionModelArtifact(
        feature_schema=schema,
        scaler_mean=(0.0,),
        scaler_scale=(1.0,),
        coefficients=(1.0,),
        intercept=0.0,
        calibrator_slope=calibrator_slope,
        calibrator_intercept=calibrator_intercept,
        lower_decision_threshold=lower,
        upper_decision_threshold=upper,
        validation_ood_min=(float(np.min(validation_logits)),),
        validation_ood_max=(float(np.max(validation_logits)),),
        optimizer_config={
            "algorithm": "local_compact_graph_neural_classifier",
            "method_id": method_id,
            "adapter_scope": "research_len_graph_classification",
            "epochs": _GRAPH_NEURAL_EPOCHS,
            "hidden_dim": _GRAPH_NEURAL_HIDDEN_DIM,
            "max_sketch_nodes": _MAX_SKETCH_NODES,
            "max_sketch_edges": _MAX_SKETCH_EDGES,
            "seed": seed,
            "model_state_hash": model_state_hash,
        },
        calibrator_config={
            "algorithm": calibration_mode,
            "regularization": 0.001,
        },
        threshold_objective="maximize_covered_macro_f1_times_coverage",
        train_fit_case_ids_fingerprint=case_id_fingerprint(example.case_id for example in train),
        validation_calibration_case_ids_fingerprint=case_id_fingerprint(example.case_id for example in validation),
        validation_threshold_case_ids_fingerprint=case_id_fingerprint(example.case_id for example in validation),
        validation_ood_case_ids_fingerprint=case_id_fingerprint(example.case_id for example in validation),
    )


class GraphNeuralDetectionImplementation(_LearnedDetectionImplementation):
    __slots__ = ("method_id", "implementation_id", "unavailable_reason")

    def __init__(self, *, method_id: str, implementation_id: str) -> None:
        if method_id not in GRAPH_NEURAL_DETECTION_METHODS:
            raise ValueError("unknown graph neural Detection method")
        self.method_id = method_id
        self.implementation_id = implementation_id
        self.unavailable_reason = None

    def execute(self, partitions: DetectionPartitions) -> DetectionExecutionOutput:
        if not isinstance(partitions, DetectionPartitions):
            raise ValueError("graph neural Detection execution requires DetectionPartitions")
        train = tuple(_example_from_training_case(case) for case in partitions.train_cases)
        validation = tuple(_example_from_training_case(case) for case in partitions.validation_cases)
        test = tuple(_example_from_inference_case(case) for case in partitions.test_cases)
        input_dim = len(train[0].graph.node_features[0])
        seed = _seed_for(self.method_id, partitions)
        classifier = _GraphClassifier(self.method_id, seed=seed, input_dim=input_dim)
        classifier.fit(train, validation, seed=seed)
        validation_logits = classifier.logits(validation)
        validation_labels = np.asarray([int(example.label) for example in validation], dtype=np.int64)
        slope, intercept, lower, upper, calibration_mode = _calibration(
            validation_logits,
            validation_labels,
        )
        artifact = _artifact(
            method_id=self.method_id,
            model_state_hash=classifier.state_hash(),
            seed=seed,
            train=train,
            validation=validation,
            validation_logits=validation_logits,
            calibrator_slope=slope,
            calibrator_intercept=intercept,
            lower=lower,
            upper=upper,
            calibration_mode=calibration_mode,
        )
        test_logits = classifier.logits(test)
        probabilities = _sigmoid(slope * test_logits + intercept)
        predictions: list[DetectionPrediction] = []
        low = artifact.validation_ood_min[0]
        high = artifact.validation_ood_max[0]
        for example, logit, probability in zip(test, test_logits, probabilities, strict=True):
            if logit < low or logit > high:
                decision = "abstain"
            elif probability <= lower:
                decision = "benign_coordination"
            elif probability >= upper:
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
        return DetectionExecutionOutput(model_artifact=artifact, predictions=tuple(predictions))


__all__ = ["GRAPH_NEURAL_DETECTION_METHODS", "GraphNeuralDetectionImplementation"]
