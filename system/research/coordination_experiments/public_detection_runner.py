from __future__ import annotations

import csv
import hashlib
import json
import math
import os
import random
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any

import numpy as np

from research.coordination_detect.contracts import DetectionFeatureSchema, DetectionTrainingCase

from .baselines import HEURISTIC_BASELINE_ID, default_baseline_registry
from .protocol import DatasetCapability, ExperimentSplit, ResearchDatasetManifest
from .public_benchmark_registry import default_public_benchmark_registry
from .public_detection_sources import (
    clear_public_detection_sources,
    register_public_detection_sources,
)
from .runner import (
    CANONICAL_REPRODUCTION_OUTPUT_ROOT,
    ClaimGate,
    DetectionEvaluationInput,
    DetectionInferenceCase,
    DetectionPartitions,
    ResultRow,
    run_detection_method,
    validate_reproduction_output_dir,
    write_reproduction_artifacts,
)


PUBLIC_DETECTION_SCHEMA_VERSION = "cogguard.public-coordination-detection/v1"
PUBLIC_DETECTION_FEATURE_SCHEMA_VERSION = "cogguard.public-detection-features/v1"

_FEASIBILITY_STATUSES = {"ready", "adapter_required", "blocked"}
_DATASET_KINDS = {"len_graph_json_dir", "alclassification_arff"}
_SIGNALS = {
    "observed_timestamps",
    "temporal_edges",
    "multiplex_relations",
    "weighted_edges",
    "account_membership_labels",
    "control_accounts",
    "graph_labels",
    "handcrafted_feature_table",
    "coordination_edge_gold",
    "community_gold",
    "binary_detection_gold",
    "harmfulness_gold",
}
_STAGE1_NAMES = (
    "cluster_size",
    "tsgs_density",
    "mhcr_coherence",
    "temporal_sync_delta_seconds",
    "unsupervised_coordination_ranking",
    "evidence_coverage",
    "relation_diversity",
)
_LEN_GRAPH_NAMES = (
    "node_count",
    "edge_count",
    "density",
    "weighted_density",
    "reciprocity",
    "mean_interaction_count",
    "max_interaction_count",
    "timestamp_span_seconds",
    "mean_kcore",
    "mean_node_attr",
    "url_edge_ratio",
    "hashtag_edge_ratio",
)
_URL_RE = re.compile(r"https?://", re.IGNORECASE)
_HASHTAG_RE = re.compile(r"(?<!\w)#\w+", re.UNICODE)


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _fingerprint(value: Any) -> str:
    return "sha256:" + hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _atomic_write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    tmp.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def _text(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be non-empty text")
    return value.strip()


def _text_tuple(values: Sequence[str], field_name: str) -> tuple[str, ...]:
    if isinstance(values, (str, bytes)) or not isinstance(values, Sequence):
        raise ValueError(f"{field_name} must be a sequence")
    result = tuple(_text(value, field_name) for value in values)
    if len(result) != len(set(result)):
        raise ValueError(f"{field_name} contains duplicates")
    return result


def _finite(value: Any, default: float = 0.0) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return default
    result = float(value)
    return result if math.isfinite(result) else default


def _unit(value: float) -> float:
    if not math.isfinite(value):
        return 0.0
    return max(0.0, min(1.0, float(value)))


def _saturating(value: float, scale: float = 1.0) -> float:
    if not math.isfinite(value) or value <= 0.0:
        return 0.0
    return float(value / (value + scale))


def _metadata_checksum(path: Path) -> str:
    stat = path.stat()
    payload = {
        "path": path.as_posix(),
        "size": stat.st_size,
        "mtime_ns": stat.st_mtime_ns,
    }
    return _fingerprint(payload)


@dataclass(frozen=True, slots=True)
class PublicDetectionDatasetConfig:
    dataset_id: str
    kind: str
    path: str
    max_cases: int = 0

    def __post_init__(self) -> None:
        object.__setattr__(self, "dataset_id", _text(self.dataset_id, "dataset_id"))
        if self.kind not in _DATASET_KINDS:
            raise ValueError(f"unknown public Detection dataset kind: {self.kind}")
        object.__setattr__(self, "path", _text(self.path, "path"))
        if isinstance(self.max_cases, bool) or not isinstance(self.max_cases, int) or self.max_cases < 0:
            raise ValueError("max_cases must be a non-negative integer")


@dataclass(frozen=True, slots=True)
class PublicDetectionMethodSpec:
    method_id: str
    name: str
    family: str
    year: int
    primary_reference_url: str
    required_signals: tuple[str, ...]
    execution_method_id: str | None
    reproduction_note: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "method_id", _text(self.method_id, "method_id"))
        object.__setattr__(self, "name", _text(self.name, "name"))
        object.__setattr__(self, "family", _text(self.family, "family"))
        if isinstance(self.year, bool) or not isinstance(self.year, int) or self.year < 1900:
            raise ValueError("year must be a valid publication year")
        object.__setattr__(self, "primary_reference_url", _text(self.primary_reference_url, "primary_reference_url"))
        required = _text_tuple(self.required_signals, "required_signals")
        unknown = set(required) - _SIGNALS
        if unknown:
            raise ValueError(f"required_signals contains unknown values: {sorted(unknown)}")
        object.__setattr__(self, "required_signals", required)
        object.__setattr__(
            self,
            "execution_method_id",
            None if self.execution_method_id is None else _text(self.execution_method_id, "execution_method_id"),
        )
        object.__setattr__(self, "reproduction_note", _text(self.reproduction_note, "reproduction_note"))

    def to_dict(self) -> dict[str, Any]:
        return {
            "method_id": self.method_id,
            "name": self.name,
            "family": self.family,
            "year": self.year,
            "primary_reference_url": self.primary_reference_url,
            "required_signals": list(self.required_signals),
            "execution_method_id": self.execution_method_id,
            "reproduction_note": self.reproduction_note,
        }


@dataclass(frozen=True, slots=True)
class PublicDetectionFeasibility:
    dataset_id: str
    method_id: str
    status: str
    reason: str
    missing_signals: tuple[str, ...] = ()
    execution_method_id: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "dataset_id", _text(self.dataset_id, "dataset_id"))
        object.__setattr__(self, "method_id", _text(self.method_id, "method_id"))
        if self.status not in _FEASIBILITY_STATUSES:
            raise ValueError(f"status must be one of {sorted(_FEASIBILITY_STATUSES)}")
        object.__setattr__(self, "reason", _text(self.reason, "reason"))
        object.__setattr__(self, "missing_signals", _text_tuple(self.missing_signals, "missing_signals"))
        object.__setattr__(
            self,
            "execution_method_id",
            None if self.execution_method_id is None else _text(self.execution_method_id, "execution_method_id"),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "dataset_id": self.dataset_id,
            "method_id": self.method_id,
            "status": self.status,
            "reason": self.reason,
            "missing_signals": list(self.missing_signals),
            "execution_method_id": self.execution_method_id,
        }


class PublicDetectionMethodRegistry:
    __slots__ = ("_methods", "_sealed")

    def __init__(self, methods: tuple[PublicDetectionMethodSpec, ...]) -> None:
        mapping = {method.method_id: method for method in methods}
        if len(mapping) != len(methods):
            raise ValueError("duplicate public Detection method ids")
        object.__setattr__(self, "_methods", MappingProxyType(mapping))
        object.__setattr__(self, "_sealed", True)

    def __setattr__(self, name: str, value: object) -> None:
        if getattr(self, "_sealed", False):
            raise AttributeError("PublicDetectionMethodRegistry is immutable")
        object.__setattr__(self, name, value)

    @property
    def method_ids(self) -> tuple[str, ...]:
        return tuple(self._methods)

    def method(self, method_id: str) -> PublicDetectionMethodSpec:
        try:
            return self._methods[_text(method_id, "method_id")]
        except KeyError as exc:
            raise ValueError(f"unknown public Detection method: {method_id}") from exc

    def execution_method_id(self, method_id: str) -> str | None:
        method_id = _text(method_id, "method_id")
        if method_id == HEURISTIC_BASELINE_ID:
            return HEURISTIC_BASELINE_ID
        for method in self._methods.values():
            if method.method_id == method_id or method.execution_method_id == method_id:
                return method.execution_method_id
        return method_id

    def feasibility(self, dataset_id: str, method_id: str) -> PublicDetectionFeasibility:
        dataset = default_public_benchmark_registry().dataset(dataset_id)
        method = self.method(method_id)
        available = dataset.available_signals
        missing = tuple(signal for signal in method.required_signals if signal not in available)
        if missing:
            return PublicDetectionFeasibility(
                dataset_id=dataset.dataset_id,
                method_id=method.method_id,
                status="blocked",
                reason="dataset is missing required labels or structural signals for this Detection method",
                missing_signals=missing,
                execution_method_id=method.execution_method_id,
            )
        if method.execution_method_id is None:
            return PublicDetectionFeasibility(
                dataset_id=dataset.dataset_id,
                method_id=method.method_id,
                status="adapter_required",
                reason="method is fixed as a paper baseline, but no local CogGuard execution adapter is bound yet",
                execution_method_id=None,
            )
        return PublicDetectionFeasibility(
            dataset_id=dataset.dataset_id,
            method_id=method.method_id,
            status="ready",
            reason="dataset signals and local execution adapter are available",
            execution_method_id=method.execution_method_id,
        )

    def feasibility_matrix(self, dataset_ids: Sequence[str] | None = None) -> tuple[PublicDetectionFeasibility, ...]:
        selected = tuple(dataset_ids) if dataset_ids is not None else (
            "large_engagement_networks",
            "astroturf_legitimate_classification",
            "iohunter",
            "twitter_state_backed_io_archive",
        )
        return tuple(
            self.feasibility(dataset_id, method_id)
            for dataset_id in selected
            for method_id in self.method_ids
        )


@dataclass(frozen=True, slots=True)
class PublicDetectionDataset:
    config: PublicDetectionDatasetConfig
    manifest: ResearchDatasetManifest
    capability: DatasetCapability
    schema: DetectionFeatureSchema
    split: ExperimentSplit
    partitions: DetectionPartitions
    evaluation: DetectionEvaluationInput
    labels: Mapping[str, int]


def default_public_detection_method_registry() -> PublicDetectionMethodRegistry:
    methods = (
        PublicDetectionMethodSpec(
            "cogguard_learned_fused_detector",
            "CogGuard learned fused Coordination Detection",
            "system_learned_detector",
            2026,
            "local:system/research/coordination_detect",
            ("binary_detection_gold",),
            "learned_fused_detector",
            "Production-facing Stage 2 learner over standardized cluster or graph features.",
        ),
        PublicDetectionMethodSpec(
            "coordination_only_logistic",
            "CogGuard coordination-only Stage 2 ablation",
            "system_ablation",
            2026,
            "local:system/research/coordination_experiments/detection_methods.py",
            ("binary_detection_gold",),
            "coordination_only_logistic",
            "Ablates Stage 2 to Discovery/coordination features only.",
        ),
        PublicDetectionMethodSpec(
            "detection_features_only_classifier",
            "CogGuard detection-feature-only Stage 2 ablation",
            "system_ablation",
            2026,
            "local:system/research/coordination_experiments/detection_methods.py",
            ("binary_detection_gold",),
            "detection_features_only_classifier",
            "Ablates Stage 2 to non-Discovery detection features only.",
        ),
        PublicDetectionMethodSpec(
            "cogguard_heuristic_bayesian",
            "CogGuard heuristic Bayesian baseline",
            "explicit_heuristic_baseline",
            2026,
            "local:system/research/coordination_detect/heuristic_baseline.py",
            ("binary_detection_gold",),
            HEURISTIC_BASELINE_ID,
            "Fixed weights and thresholds; never treated as a learned claimable model.",
        ),
        PublicDetectionMethodSpec(
            "len_graph_stat_logistic",
            "LEN graph-statistic logistic baseline",
            "graph_level_detection",
            2025,
            "https://arxiv.org/abs/2503.00599",
            ("graph_labels", "weighted_edges", "binary_detection_gold"),
            "len_graph_stat_logistic",
            "Local reproduction uses LEN graph statistics and the shared calibrated logistic runner.",
        ),
        PublicDetectionMethodSpec(
            "vargas_coordination_activity_classifier",
            "Coordination Activity Classifier",
            "coordination_activity_features",
            2020,
            "https://arxiv.org/abs/2005.13466",
            ("graph_labels", "binary_detection_gold"),
            "vargas_coordination_activity_classifier",
            "Local reproduction uses Stage-1 coordination/activity features as the classifier input.",
        ),
        PublicDetectionMethodSpec(
            "gcn_graph_classifier",
            "Graph Convolutional Network",
            "graph_neural_network",
            2017,
            "https://arxiv.org/abs/1609.02907",
            ("graph_labels", "weighted_edges", "binary_detection_gold"),
            "gcn_graph_classifier",
            "Local compact LEN graph adapter with GCN-style normalized message passing; not the official implementation.",
        ),
        PublicDetectionMethodSpec(
            "graphsage_graph_classifier",
            "GraphSAGE",
            "graph_neural_network",
            2017,
            "https://arxiv.org/abs/1706.02216",
            ("graph_labels", "weighted_edges", "binary_detection_gold"),
            "graphsage_graph_classifier",
            "Local compact LEN graph adapter with GraphSAGE-style mean aggregation; not the official implementation.",
        ),
        PublicDetectionMethodSpec(
            "gin_graph_classifier",
            "Graph Isomorphism Network",
            "graph_neural_network",
            2019,
            "https://openreview.net/forum?id=ryGs6iA5Km",
            ("graph_labels", "weighted_edges", "binary_detection_gold"),
            "gin_graph_classifier",
            "Local compact LEN graph adapter with GIN-style sum aggregation; not the official implementation.",
        ),
        PublicDetectionMethodSpec(
            "diffpool_graph_classifier",
            "Differentiable Pooling",
            "graph_neural_network",
            2018,
            "https://arxiv.org/abs/1806.08804",
            ("graph_labels", "weighted_edges", "binary_detection_gold"),
            "diffpool_graph_classifier",
            "Local compact LEN graph adapter with differentiable assignment pooling; not the official implementation.",
        ),
        PublicDetectionMethodSpec(
            "inductive_io_graph_learning",
            "Inductive graph learning for influence operation detection",
            "account_level_io_detection",
            2023,
            "https://doi.org/10.1038/s41598-023-49676-z",
            ("account_membership_labels", "control_accounts"),
            None,
            "Requires account-level IO/control adapter rather than graph-level LEN labels.",
        ),
        PublicDetectionMethodSpec(
            "iohunter_account_graph_learning",
            "IOHunter",
            "account_level_io_detection",
            2025,
            "https://arxiv.org/abs/2412.14663",
            ("account_membership_labels",),
            None,
            "Discovery/account recovery baseline, not harmful graph-level Detection without extra labels.",
        ),
        PublicDetectionMethodSpec(
            "truthy_classic_feature_classifier",
            "Truthy Astroturf/Meme feature classifier",
            "classic_feature_detection",
            2011,
            "https://arxiv.org/abs/1011.3768",
            ("handcrafted_feature_table", "binary_detection_gold"),
            "truthy_feature_logistic",
            "Local reproduction uses ALClassification ARFF features with the shared calibrated logistic runner.",
        ),
        PublicDetectionMethodSpec(
            "tgat",
            "Temporal Graph Attention Network",
            "temporal_graph_encoder",
            2020,
            "https://arxiv.org/abs/2002.07962",
            ("observed_timestamps", "temporal_edges", "binary_detection_gold"),
            None,
            "P2 temporal encoder; blocked until a timestamped binary Coordination Detection adapter exists.",
        ),
        PublicDetectionMethodSpec(
            "tgn",
            "Temporal Graph Networks",
            "temporal_graph_encoder",
            2020,
            "https://github.com/twitter-research/tgn",
            ("observed_timestamps", "temporal_edges", "binary_detection_gold"),
            None,
            "P2 temporal encoder; blocked until a timestamped binary Coordination Detection adapter exists.",
        ),
        PublicDetectionMethodSpec(
            "dygformer",
            "DyGFormer",
            "temporal_graph_transformer",
            2023,
            "https://arxiv.org/abs/2303.13047",
            ("observed_timestamps", "temporal_edges", "binary_detection_gold"),
            None,
            "P2 temporal encoder; blocked until a timestamped binary Coordination Detection adapter exists.",
        ),
    )
    return PublicDetectionMethodRegistry(methods)


def _len_label(path: Path) -> tuple[int, str]:
    name = path.name.lower()
    if "_noncampaign_fulldata.json" in name:
        return 0, "noncampaign"
    if "_campaign_fulldata.json" in name:
        return 1, "campaign"
    raise ValueError(f"LEN filename does not contain a supported graph label: {path.name}")


def _flatten_numeric(values: Any, out: list[float]) -> None:
    if isinstance(values, (int, float)) and not isinstance(values, bool):
        value = float(values)
        if math.isfinite(value):
            out.append(value)
    elif isinstance(values, list):
        for item in values:
            _flatten_numeric(item, out)


def _safe_mean(values: Sequence[float]) -> float:
    return float(np.mean(values)) if values else 0.0


def _safe_std(values: Sequence[float]) -> float:
    return float(np.std(values)) if values else 0.0


def _len_features(path: Path) -> tuple[dict[str, float], dict[str, Any]]:
    with path.open("r", encoding="utf-8") as stream:
        data = json.load(stream)
    nodes = data.get("nodes", ())
    links = data.get("links", data.get("edges", ()))
    if not isinstance(nodes, list) or not isinstance(links, list):
        raise ValueError(f"LEN graph must contain node-link arrays: {path.name}")
    node_count = len(nodes)
    edge_count = len(links)
    directed = bool(data.get("directed", True))
    possible_edges = node_count * (node_count - 1)
    density_denominator = possible_edges if directed else possible_edges / 2
    density = 0.0 if density_denominator <= 0 else edge_count / density_denominator

    weights: list[float] = []
    timestamps: list[float] = []
    edge_attr_values: list[float] = []
    pairs: set[tuple[str, str]] = set()
    url_edges = 0
    hashtag_edges = 0
    text_edges = 0
    for link in links:
        if not isinstance(link, Mapping):
            continue
        weights.append(max(0.0, _finite(link.get("Interaction_Count"), 1.0)))
        timestamp = _finite(link.get("timestamp"), math.nan)
        if math.isfinite(timestamp):
            timestamps.append(timestamp)
        source = str(link.get("source", "")).strip()
        target = str(link.get("target", "")).strip()
        if source and target and source != target:
            pairs.add((source, target))
        text = str(link.get("text", ""))
        if text:
            text_edges += 1
        if _URL_RE.search(text):
            url_edges += 1
        if _HASHTAG_RE.search(text):
            hashtag_edges += 1
        _flatten_numeric(link.get("edge_attr", ()), edge_attr_values)

    reciprocal_count = sum(1 for left, right in pairs if (right, left) in pairs)
    reciprocity = 0.0 if not pairs else reciprocal_count / len(pairs)
    timestamp_span = 0.0 if len(timestamps) < 2 else max(timestamps) - min(timestamps)
    temporal_delta = 86_400.0 if edge_count == 0 else timestamp_span / max(edge_count, 1)
    weight_sum = sum(weights)
    weighted_density = 0.0 if density_denominator <= 0 else weight_sum / density_denominator

    node_attr_values: list[float] = []
    kcore_values: list[float] = []
    for node in nodes:
        if not isinstance(node, Mapping):
            continue
        _flatten_numeric(node.get("node_attr", ()), node_attr_values)
        _flatten_numeric(node.get("kcore", ()), kcore_values)

    evidence_coverage = 0.0 if edge_count == 0 else text_edges / edge_count
    relation_presence = sum(value > 0 for value in (url_edges, hashtag_edges, edge_count - text_edges))
    relation_diversity = relation_presence / 3.0
    edge_attr_coherence = 1.0 / (1.0 + _safe_std(edge_attr_values))
    sync_score = 1.0 / (1.0 + temporal_delta / 3600.0)
    ranking = _unit((density * 50.0 + weighted_density * (2.0 * 5.0) + sync_score) / 3.0)
    features = {
        "cluster_size": float(node_count),
        "tsgs_density": _unit(density * 50.0),
        "mhcr_coherence": _unit(edge_attr_coherence),
        "temporal_sync_delta_seconds": float(max(0.0, temporal_delta)),
        "unsupervised_coordination_ranking": ranking,
        "evidence_coverage": _unit(evidence_coverage),
        "relation_diversity": _unit(relation_diversity),
        "node_count": float(node_count),
        "edge_count": float(edge_count),
        "density": float(max(0.0, density)),
        "weighted_density": float(max(0.0, weighted_density)),
        "reciprocity": _unit(reciprocity),
        "mean_interaction_count": _safe_mean(weights),
        "max_interaction_count": max(weights) if weights else 0.0,
        "timestamp_span_seconds": float(max(0.0, timestamp_span)),
        "mean_kcore": _safe_mean(kcore_values),
        "mean_node_attr": _safe_mean(node_attr_values),
        "url_edge_ratio": 0.0 if edge_count == 0 else url_edges / edge_count,
        "hashtag_edge_ratio": 0.0 if edge_count == 0 else hashtag_edges / edge_count,
    }
    provenance = {
        "source_name": path.name,
        "node_count": node_count,
        "edge_count": edge_count,
        "checksum_scope": "path_size_mtime_metadata",
    }
    return features, provenance


def _case_id(prefix: str, source: str) -> str:
    digest = hashlib.sha256(source.encode("utf-8")).hexdigest()[:16]
    return f"{prefix}-{digest}"


def _load_len_cases(config: PublicDetectionDatasetConfig) -> tuple[dict[str, float], ...]:
    root = Path(config.path)
    files = sorted(root.glob("*.json"))
    if config.max_cases:
        files = files[: config.max_cases]
    cases: list[dict[str, float]] = []
    for path in files:
        label, label_text = _len_label(path)
        features, provenance = _len_features(path)
        case_id = _case_id("len", path.name)
        cases.append(
            {
                "case_id": case_id,
                "cluster_id": case_id,
                "label": label,
                "label_text": label_text,
                "source_path": path.as_posix(),
                "provenance": provenance,
                **features,
            }
        )
    if not cases:
        raise ValueError("LEN dataset adapter found no graph JSON files")
    return tuple(cases)


def _parse_arff(path: Path) -> tuple[tuple[str, ...], tuple[tuple[float, ...], ...], tuple[str, ...]]:
    attributes: list[str] = []
    rows: list[tuple[float, ...]] = []
    labels: list[str] = []
    in_data = False
    for raw_line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("%"):
            continue
        lower = line.lower()
        if lower.startswith("@attribute"):
            parts = line.split(None, 2)
            if len(parts) < 3:
                raise ValueError(f"invalid ARFF attribute line: {line}")
            name = parts[1].strip("'\"")
            if name.lower() != "class":
                attributes.append(name)
        elif lower.startswith("@data"):
            in_data = True
        elif in_data:
            parsed = next(csv.reader([line]))
            if len(parsed) != len(attributes) + 1:
                raise ValueError("ARFF data row width does not match attributes")
            values = tuple(0.0 if value.strip() == "?" else float(value) for value in parsed[:-1])
            label = parsed[-1].strip()
            if label not in {"truthy", "legitimate"}:
                raise ValueError(f"unsupported ALClassification label: {label}")
            rows.append(values)
            labels.append(label)
    if not attributes or not rows:
        raise ValueError("ARFF adapter found no attributes or data rows")
    return tuple(attributes), tuple(rows), tuple(labels)


def _load_al_cases(config: PublicDetectionDatasetConfig) -> tuple[tuple[str, ...], tuple[dict[str, Any], ...]]:
    path = Path(config.path)
    names, rows, labels = _parse_arff(path)
    if config.max_cases:
        rows = rows[: config.max_cases]
        labels = labels[: config.max_cases]
    cases: list[dict[str, Any]] = []
    name_index = {name: index for index, name in enumerate(names)}

    def get(row: tuple[float, ...], name: str) -> float:
        return row[name_index[name]] if name in name_index else 0.0

    for index, (row, label_text) in enumerate(zip(rows, labels, strict=True)):
        raw_features = dict(zip(names, row, strict=True))
        node_count = max(0.0, get(row, "meme_statistics.nodes"))
        edge_count = max(0.0, get(row, "meme_statistics.edges"))
        density = 0.0 if node_count <= 1 else edge_count / (node_count * (node_count - 1))
        mean_w = get(row, "meme_statistics.mean_w")
        num_truthy = get(row, "meme_display_statistics.num_truthy")
        case_id = f"al-{index:05d}"
        cases.append(
            {
                "case_id": case_id,
                "cluster_id": case_id,
                "label": 1 if label_text == "truthy" else 0,
                "label_text": label_text,
                "source_path": path.as_posix(),
                "provenance": {
                    "source_name": path.name,
                    "row_index": index,
                    "checksum_scope": "path_size_mtime_metadata",
                },
                "cluster_size": float(node_count),
                "tsgs_density": _unit(density * 500.0),
                "mhcr_coherence": _saturating(mean_w, 1.0),
                "temporal_sync_delta_seconds": 86_400.0,
                "unsupervised_coordination_ranking": _unit((density * 500.0 + _saturating(mean_w, 1.0) + _unit(num_truthy)) / 3.0),
                "evidence_coverage": 0.0,
                "relation_diversity": 0.0,
                **raw_features,
            }
        )
    return names, tuple(cases)


def _schema_for_cases(dataset_id: str, cases: Sequence[Mapping[str, Any]], extra_names: Sequence[str]) -> DetectionFeatureSchema:
    names = tuple(dict.fromkeys((*_STAGE1_NAMES, *extra_names)))
    for case in cases:
        missing = [name for name in names if name not in case]
        if missing:
            raise ValueError(f"{dataset_id} case {case.get('case_id')} is missing features: {missing}")
    return DetectionFeatureSchema(version=f"{PUBLIC_DETECTION_FEATURE_SCHEMA_VERSION}/{dataset_id}", names=names)


def _holdout_counts(class_count: int) -> tuple[int, int]:
    validation_count = max(1, int(round(class_count * 0.2)))
    test_count = max(1, int(round(class_count * 0.2)))
    while validation_count + test_count > class_count - 1:
        if validation_count >= test_count and validation_count > 1:
            validation_count -= 1
        elif test_count > 1:
            test_count -= 1
        else:
            break
    return validation_count, test_count


def _stratified_split(cases: Sequence[Mapping[str, Any]], *, seed: int) -> ExperimentSplit:
    by_label: dict[int, list[str]] = {0: [], 1: []}
    for case in cases:
        by_label[int(case["label"])].append(str(case["case_id"]))
    if any(len(values) < 3 for values in by_label.values()):
        raise ValueError("public Detection splits require at least three cases per class")
    rng = random.Random(seed)
    train: list[str] = []
    validation: list[str] = []
    test: list[str] = []
    for ids in by_label.values():
        shuffled = list(ids)
        rng.shuffle(shuffled)
        validation_count, test_count = _holdout_counts(len(shuffled))
        validation.extend(shuffled[:validation_count])
        test.extend(shuffled[validation_count: validation_count + test_count])
        train.extend(shuffled[validation_count + test_count:])
    return ExperimentSplit(
        policy="stratified_binary_label_holdout",
        seed=seed,
        train_ids=tuple(sorted(train)),
        validation_ids=tuple(sorted(validation)),
        test_ids=tuple(sorted(test)),
        train_group_ids=tuple(sorted(train)),
        validation_group_ids=tuple(sorted(validation)),
        test_group_ids=tuple(sorted(test)),
        transform_fit_ids=tuple(sorted(train)),
    )


def _build_manifest(
    *,
    config: PublicDetectionDatasetConfig,
    seed: int,
    cases: Sequence[Mapping[str, Any]],
    label_semantics: str,
    time_axis: str,
    quality_markers: tuple[str, ...],
    claim_markers: tuple[str, ...],
) -> ResearchDatasetManifest:
    source_paths = tuple(sorted({str(case["source_path"]) for case in cases}))
    checksums = {path: _metadata_checksum(Path(path)) for path in source_paths}
    return ResearchDatasetManifest(
        dataset_id=config.dataset_id,
        seed=seed,
        source_paths=source_paths,
        source_checksums=checksums,
        source_checksum_scope="path_size_mtime_metadata_sha256",
        label_semantics=label_semantics,
        sample_count=len(cases),
        source_case_ids=tuple(str(case["case_id"]) for case in cases),
        campaign_axis=tuple(sorted({str(case["label_text"]) for case in cases})),
        platform_axis=("x_twitter",),
        time_axis=time_axis,
        quality_markers=quality_markers,
        claim_markers=claim_markers,
    )


def _build_partitions(
    *,
    cases: Sequence[Mapping[str, Any]],
    schema: DetectionFeatureSchema,
    split: ExperimentSplit,
) -> tuple[DetectionPartitions, DetectionEvaluationInput, Mapping[str, int]]:
    by_id = {str(case["case_id"]): case for case in cases}
    labels = MappingProxyType(dict(sorted((case_id, int(case["label"])) for case_id, case in by_id.items())))

    def training_case(case_id: str, split_name: str) -> DetectionTrainingCase:
        case = by_id[case_id]
        return DetectionTrainingCase(
            case_id=case_id,
            cluster_id=str(case["cluster_id"]),
            split=split_name,
            label=int(case["label"]),
            feature_schema_version=schema.version,
            feature_schema_fingerprint=schema.fingerprint,
            feature_names=schema.names,
            feature_values=tuple(_finite(case[name]) for name in schema.names),
            provenance=case["provenance"],
        )

    def inference_case(case_id: str) -> DetectionInferenceCase:
        case = by_id[case_id]
        return DetectionInferenceCase(
            case_id=case_id,
            cluster_id=str(case["cluster_id"]),
            feature_schema_version=schema.version,
            feature_schema_fingerprint=schema.fingerprint,
            feature_names=schema.names,
            feature_values=tuple(_finite(case[name]) for name in schema.names),
            provenance={},
        )

    partitions = DetectionPartitions(
        train_cases=tuple(training_case(case_id, "train") for case_id in split.train_ids),
        validation_cases=tuple(training_case(case_id, "validation") for case_id in split.validation_ids),
        test_cases=tuple(inference_case(case_id) for case_id in split.test_ids),
    )
    evaluation = DetectionEvaluationInput(
        evaluator_fingerprint=_fingerprint(
            {
                "schema_version": PUBLIC_DETECTION_SCHEMA_VERSION,
                "split_fingerprint": split.fingerprint,
                "test_labels": {case_id: labels[case_id] for case_id in split.test_ids},
            }
        ),
        test_labels={case_id: labels[case_id] for case_id in split.test_ids},
    )
    return partitions, evaluation, labels


def build_public_detection_dataset(config: PublicDetectionDatasetConfig, *, seed: int = 42) -> PublicDetectionDataset:
    public_registry = default_public_benchmark_registry()
    dataset_spec = public_registry.dataset(config.dataset_id)
    if config.kind == "len_graph_json_dir":
        cases = _load_len_cases(config)
        register_public_detection_sources(cases)
        schema = _schema_for_cases(config.dataset_id, cases, _LEN_GRAPH_NAMES)
        label_semantics = "LEN graph label: campaign=1, noncampaign=0"
        time_axis = "graph_edge_timestamp_proxy_not_event_stream"
        quality_markers = ("local_len_graph_json", "graph_level_label")
        claim_markers = (
            "stage2_detection_candidate",
            "not_harmful_cib_claim",
            "not_observed_event_stream",
        )
    elif config.kind == "alclassification_arff":
        arff_names, cases = _load_al_cases(config)
        register_public_detection_sources(cases)
        schema = _schema_for_cases(config.dataset_id, cases, arff_names)
        label_semantics = "Truthy astroturf label: truthy=1, legitimate=0"
        time_axis = "static_placeholder_not_observed_time"
        quality_markers = ("local_alclassification_arff", "classic_feature_table")
        claim_markers = (
            "stage2_classic_smoke",
            "not_harmful_cib_claim",
            "static_placeholder_not_observed_time",
        )
    else:  # pragma: no cover - dataclass validation prevents this.
        raise ValueError(f"unsupported dataset kind: {config.kind}")

    split = _stratified_split(cases, seed=seed)
    manifest = _build_manifest(
        config=config,
        seed=seed,
        cases=cases,
        label_semantics=label_semantics,
        time_axis=time_axis,
        quality_markers=quality_markers,
        claim_markers=claim_markers,
    )
    partitions, evaluation, labels = _build_partitions(cases=cases, schema=schema, split=split)
    return PublicDetectionDataset(
        config=config,
        manifest=manifest,
        capability=dataset_spec.capability,
        schema=schema,
        split=split,
        partitions=partitions,
        evaluation=evaluation,
        labels=labels,
    )


def _public_method_id_for_execution(execution_method_id: str) -> str:
    registry = default_public_detection_method_registry()
    try:
        registry.method(execution_method_id)
        return execution_method_id
    except ValueError:
        pass
    for method_id in registry.method_ids:
        method = registry.method(method_id)
        if method.execution_method_id == execution_method_id:
            return method.method_id
    if execution_method_id == "learned_fused_detector":
        return "cogguard_learned_fused_detector"
    if execution_method_id == HEURISTIC_BASELINE_ID:
        return "cogguard_heuristic_bayesian"
    if execution_method_id == "truthy_feature_logistic":
        return "truthy_classic_feature_classifier"
    return execution_method_id


def _blocked_row(
    *,
    execution_method_id: str,
    reason: str,
    dataset: PublicDetectionDataset,
) -> ResultRow:
    baseline_registry = default_baseline_registry()
    spec = baseline_registry.get(execution_method_id)
    audit = {
        "audit_version": "coordination-execution-audit/v2",
        "stage": "detection",
        "implementation_id": spec.implementation_id,
        "fit_provenance_source": "not_executed_dataset_method_incompatible",
        "test_partition_fingerprint": dataset.partitions.test_fingerprint,
        "evaluation_input_fingerprint": dataset.evaluation.fingerprint,
        "evaluation_after_execution": False,
        "test_evaluation_only": True,
    }
    if spec.model_role != "heuristic_baseline":
        audit["train_partition_fingerprint"] = dataset.partitions.train_fingerprint
        audit["validation_partition_fingerprint"] = dataset.partitions.validation_fingerprint
    markers = set(dataset.manifest.claim_markers) | set(dataset.capability.claim_markers)
    if dataset.manifest.time_axis == "static_placeholder_not_observed_time":
        markers.add(dataset.manifest.time_axis)
    return ResultRow(
        dataset_id=dataset.manifest.dataset_id,
        dataset_manifest_fingerprint=dataset.manifest.fingerprint,
        evaluator_fingerprint=dataset.evaluation.fingerprint,
        split_policy=dataset.split.policy,
        split_fingerprint=dataset.split.fingerprint,
        method_id=spec.method_id,
        method_version=spec.method_version,
        model_role=spec.model_role,
        seed=dataset.split.seed,
        runtime_seconds=0.0,
        peak_memory_bytes=0,
        status="blocked",
        metrics={},
        reason=reason,
        warning=spec.warning,
        claim_markers=tuple(sorted(markers)),
        task="detection",
        selection_eligible=spec.selection_eligible,
        ablation_id=spec.ablation_id,
        audit=audit,
        model_artifact=None,
        train_partition_fingerprint=None if spec.model_role == "heuristic_baseline" else dataset.partitions.train_fingerprint,
        validation_partition_fingerprint=None if spec.model_role == "heuristic_baseline" else dataset.partitions.validation_fingerprint,
        test_partition_fingerprint=dataset.partitions.test_fingerprint,
    )


def _dataset_method_reason(dataset_id: str, execution_method_id: str) -> str | None:
    public_registry = default_public_detection_method_registry()
    public_method_id = _public_method_id_for_execution(execution_method_id)
    try:
        feasibility = public_registry.feasibility(dataset_id, public_method_id)
    except ValueError:
        return None
    if feasibility.status != "ready":
        return feasibility.reason
    return None


def _run_ids(method_ids: Sequence[str] | None) -> tuple[str, ...]:
    public_registry = default_public_detection_method_registry()
    if method_ids is None:
        requested = []
        for method_id in public_registry.method_ids:
            execution = public_registry.execution_method_id(method_id)
            requested.append(method_id if execution is None else execution)
        return tuple(dict.fromkeys(requested))
    result: list[str] = []
    for method_id in method_ids:
        execution = public_registry.execution_method_id(method_id)
        if execution is None:
            execution = method_id
        result.append(execution)
    return tuple(dict.fromkeys(result))


def _public_detection_claim_gates(seeds: Sequence[int]) -> tuple[ClaimGate, ...]:
    minimum = len(tuple(seeds))
    return (
        ClaimGate(
            "public-detection-no-harmful-cib-generalization",
            "auprc",
            "maximize",
            0.0,
            claim_scope="harmful_cib",
            minimum_successful_seeds=minimum,
            forbidden_claim_markers=("not_harmful_cib_claim", "stage2_classic_smoke"),
        ),
        ClaimGate(
            "public-detection-no-observed-time-generalization",
            "auprc",
            "maximize",
            0.0,
            claim_scope="observed_time",
            minimum_successful_seeds=minimum,
            forbidden_claim_markers=(
                "not_observed_event_stream",
                "static_placeholder_not_observed_time",
            ),
        ),
    )


def run_public_detection_comparison(
    configs: Sequence[PublicDetectionDatasetConfig],
    output_dir: str | Path,
    *,
    seeds: Sequence[int] = (11, 23, 37, 41, 53),
    method_ids: Sequence[str] | None = None,
    bootstrap_resamples: int = 2_000,
) -> dict[str, Any]:
    output = validate_reproduction_output_dir(output_dir)
    if not configs:
        raise ValueError("at least one public Detection dataset config is required")
    if isinstance(seeds, (str, bytes)) or not isinstance(seeds, Sequence) or not seeds:
        raise ValueError("seeds must be a non-empty integer sequence")
    normalized_seeds = tuple(int(seed) for seed in seeds)
    if any(seed < 0 for seed in normalized_seeds):
        raise ValueError("seeds must be non-negative")
    run_method_ids = _run_ids(method_ids)
    baseline_registry = default_baseline_registry()
    rows: list[ResultRow] = []
    datasets: list[PublicDetectionDataset] = []
    clear_public_detection_sources()
    for config in configs:
        for seed in normalized_seeds:
            dataset = build_public_detection_dataset(config, seed=seed)
            datasets.append(dataset)
            for execution_method_id in run_method_ids:
                reason = _dataset_method_reason(dataset.manifest.dataset_id, execution_method_id)
                if reason is not None:
                    rows.append(_blocked_row(execution_method_id=execution_method_id, reason=reason, dataset=dataset))
                    continue
                rows.append(
                    run_detection_method(
                        baseline_registry,
                        execution_method_id,
                        manifest=dataset.manifest,
                        capability=dataset.capability,
                        split=dataset.split,
                        partitions=dataset.partitions,
                        evaluation=dataset.evaluation,
                    )
                )
    artifact_paths = write_reproduction_artifacts(
        rows,
        output,
        claim_gates=_public_detection_claim_gates(normalized_seeds),
        bootstrap_seed=0,
        bootstrap_resamples=bootstrap_resamples,
    )
    public_registry = default_public_detection_method_registry()
    dataset_ids = tuple(dict.fromkeys(config.dataset_id for config in configs))
    feasibility = tuple(item.to_dict() for item in public_registry.feasibility_matrix(dataset_ids))
    manifest = {
        "schema_version": PUBLIC_DETECTION_SCHEMA_VERSION,
        "evaluation_scope": "coordination_detection_graph_or_feature_label_evaluation",
        "dataset_configs": [
            {
                "dataset_id": config.dataset_id,
                "kind": config.kind,
                "path": config.path,
                "max_cases": config.max_cases,
            }
            for config in configs
        ],
        "seeds": list(normalized_seeds),
        "requested_method_ids": list(method_ids) if method_ids is not None else None,
        "executed_method_ids": list(run_method_ids),
        "method_registry": [public_registry.method(method_id).to_dict() for method_id in public_registry.method_ids],
        "feasibility_matrix": feasibility,
        "dataset_manifests": [dataset.manifest.to_dict() for dataset in datasets],
        "dataset_protocols": [
            {
                "dataset_id": dataset.manifest.dataset_id,
                "seed": dataset.split.seed,
                "sample_count": dataset.manifest.sample_count,
                "train_count": len(dataset.partitions.train_cases),
                "validation_count": len(dataset.partitions.validation_cases),
                "test_count": len(dataset.partitions.test_cases),
                "test_label_counts": {
                    str(label): sum(1 for value in dataset.evaluation.test_labels.values() if value == label)
                    for label in (0, 1)
                },
                "feature_count": len(dataset.schema.names),
                "split_policy": dataset.split.policy,
            }
            for dataset in datasets
        ],
        "rows": [row.to_dict() for row in rows],
        "artifact_paths": {
            "per_seed_json": artifact_paths.per_seed_json.as_posix(),
            "per_seed_csv": artifact_paths.per_seed_csv.as_posix(),
            "aggregates_json": artifact_paths.aggregates_json.as_posix(),
            "aggregates_csv": artifact_paths.aggregates_csv.as_posix(),
            "claim_gates_json": artifact_paths.claim_gates_json.as_posix(),
            "identity": artifact_paths.artifact_identity,
        },
    }
    manifest["fingerprint"] = _fingerprint(manifest)
    _atomic_write_json(output / "public_detection_manifest.json", manifest)
    return manifest


def default_local_public_detection_configs(*, max_cases: int = 0) -> tuple[PublicDetectionDatasetConfig, ...]:
    return (
        PublicDetectionDatasetConfig(
            dataset_id="large_engagement_networks",
            kind="len_graph_json_dir",
            path="G:/CISCN/dataset/LEN",
            max_cases=max_cases,
        ),
        PublicDetectionDatasetConfig(
            dataset_id="astroturf_legitimate_classification",
            kind="alclassification_arff",
            path="G:/CISCN/dataset/ALClassification/data.arff",
            max_cases=max_cases,
        ),
    )


__all__ = [
    "PUBLIC_DETECTION_FEATURE_SCHEMA_VERSION",
    "PUBLIC_DETECTION_SCHEMA_VERSION",
    "PublicDetectionDataset",
    "PublicDetectionDatasetConfig",
    "PublicDetectionFeasibility",
    "PublicDetectionMethodRegistry",
    "PublicDetectionMethodSpec",
    "build_public_detection_dataset",
    "default_local_public_detection_configs",
    "default_public_detection_method_registry",
    "run_public_detection_comparison",
]
