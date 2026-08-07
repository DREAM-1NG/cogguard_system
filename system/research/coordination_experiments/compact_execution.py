from __future__ import annotations

import hashlib
import json
import re
import time
import tracemalloc
from collections.abc import Mapping as MappingABC
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Mapping, Protocol

import numpy as np

from ..coordination_discover.stage1.contracts import DiscoveredClusterBatch
from .iohunter import IOHUNTER_LABEL_SEMANTICS
from .iohunter_compact import (
    CompactIOHunterDiscoveryView,
    CompactIOHunterEvaluator,
    CompactIOHunterFold,
    compact_fold_fingerprint,
)
from .metrics import average_precision, roc_auc


_FORBIDDEN_TOKENS = (
    "evaluator",
    "label",
    "fold",
    "fused",
    "source_path",
    "source_sha",
    "bot",
    "harmful",
    "verdict",
    "account_risk",
    "raw",
    "path",
    "checksum",
)
_ACCOUNT_PREFIX = "account-"
_EVALUATION_SCOPE = "external_account_recovery_not_coordination_ground_truth"
_CLAIM_MARKERS = (
    "iohunter_no_ground_truth_coordination_edges",
    "iohunter_no_ground_truth_communities",
    "iohunter_no_causal_campaign_labels",
)


def _text(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string")
    return value.strip()


def _canonical_json(value: Any) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")


def _fingerprint(value: Any) -> str:
    return "sha256:" + hashlib.sha256(_canonical_json(value)).hexdigest()


def _detached_read_only_array(
    value: Any,
    *,
    dtype: np.dtype,
    shape: tuple[int, ...],
    field_name: str,
) -> np.ndarray:
    array = np.asarray(value)
    if array.dtype != dtype or array.shape != shape or array.flags.writeable:
        raise ValueError(f"{field_name} must be a read-only {dtype} array with shape {shape}")
    detached = np.frombuffer(array.tobytes(order="C"), dtype=dtype).reshape(shape)
    if detached.flags.writeable:
        raise RuntimeError(f"{field_name} immutable backing was not established")
    return detached


def _immutable_mapping(value: Mapping[str, Any], field_name: str) -> Mapping[str, Any]:
    if not isinstance(value, MappingABC):
        raise ValueError(f"{field_name} must be a mapping")
    normalized = {}
    for raw_key, item in value.items():
        key = _text(raw_key, f"{field_name} key")
        if key in normalized:
            raise ValueError(f"{field_name} contains duplicate canonical keys")
        normalized[key] = _freeze_value(item, f"{field_name}.{key}")
    normalized = dict(sorted(normalized.items()))
    return MappingProxyType(normalized)


def _freeze_value(value: Any, field_name: str) -> Any:
    if isinstance(value, MappingABC):
        return _immutable_mapping(value, field_name)
    if isinstance(value, (tuple, list)):
        return tuple(_freeze_value(item, f"{field_name}[]") for item in value)
    if isinstance(value, np.generic):
        return value.item()
    if value is None or isinstance(value, (str, bool, int, float)):
        if isinstance(value, float) and not np.isfinite(value):
            raise ValueError(f"{field_name} must be finite")
        return value
    raise ValueError(f"{field_name} contains a non-serializable value")


def _plain_value(value: Any) -> Any:
    if isinstance(value, MappingABC):
        return {key: _plain_value(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_plain_value(item) for item in value]
    return value


def _is_forbidden_config_key(key: Any) -> bool:
    key_text = str(key)
    tokens = [
        token.lower()
        for token in re.split(r"(?<!^)(?=[A-Z])|[^A-Za-z0-9]+", key_text)
        if token
    ]
    return any(token in _FORBIDDEN_TOKENS or re.fullmatch(r"sha\d+", token) for token in tokens)


def _assert_label_free(value: Any, path: str = "method_config") -> None:
    if isinstance(value, MappingABC):
        for key, item in value.items():
            if _is_forbidden_config_key(key):
                raise ValueError(f"{path} contains evaluator-only key {key!r}")
            _assert_label_free(item, f"{path}.{key}")
    elif isinstance(value, (tuple, list)):
        for index, item in enumerate(value):
            _assert_label_free(item, f"{path}[{index}]")


def _account_id(index: int) -> str:
    return f"{_ACCOUNT_PREFIX}{index:06d}"


def _cluster_members(batch: DiscoveredClusterBatch) -> set[str]:
    members: set[str] = set()
    for cluster in batch.candidate_clusters:
        overlap = members.intersection(cluster.member_account_ids)
        if overlap:
            raise ValueError("discovered cluster batch contains overlapping account members")
        members.update(cluster.member_account_ids)
    return members


@dataclass(frozen=True, slots=True)
class CompactDiscoveryExecutionInput:
    discovery_view: CompactIOHunterDiscoveryView
    seed: int
    method_config_version: str
    method_config: Mapping[str, Any]

    def __post_init__(self) -> None:
        if not isinstance(self.discovery_view, CompactIOHunterDiscoveryView):
            raise ValueError("discovery_view must be CompactIOHunterDiscoveryView")
        if isinstance(self.seed, bool) or not isinstance(self.seed, int) or self.seed < 0:
            raise ValueError("seed must be a non-negative integer")
        object.__setattr__(self, "method_config_version", _text(self.method_config_version, "method_config_version"))
        _assert_label_free(self.method_config)
        object.__setattr__(self, "method_config", _immutable_mapping(self.method_config, "method_config"))

    @property
    def fingerprint(self) -> str:
        relation_payload = {}
        for layer, edges in self.discovery_view.relation_edges.items():
            relation_payload[layer] = {
                "relation": edges.relation,
                "endpoints": edges.endpoints.tobytes().hex(),
                "weights": edges.weights.tobytes().hex(),
            }
        return _fingerprint(
            {
                "campaign": self.discovery_view.campaign,
                "account_count": self.discovery_view.account_count,
                "source_layer_fingerprint": self.discovery_view.source_layer_fingerprint,
                "relation_edges": relation_payload,
                "time_semantics": self.discovery_view.time_semantics,
                "seed": self.seed,
                "method_config_version": self.method_config_version,
                "method_config": _plain_value(self.method_config),
            }
        )


@dataclass(frozen=True, slots=True)
class CompactDiscoveryPrediction:
    account_count: int
    candidate_endpoints: np.ndarray
    edge_scores: np.ndarray
    account_scores: np.ndarray
    cluster_assignments: np.ndarray
    discovered_cluster_batch: DiscoveredClusterBatch
    method_id: str
    method_version: str
    implementation_id: str
    diagnostics: Mapping[str, Any] | None = None
    claim_markers: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if isinstance(self.account_count, bool) or not isinstance(self.account_count, int) or self.account_count <= 0:
            raise ValueError("account_count must be a positive integer")
        raw_endpoints = np.asarray(self.candidate_endpoints)
        endpoints = _detached_read_only_array(
            self.candidate_endpoints,
            dtype=raw_endpoints.dtype,
            shape=(raw_endpoints.shape[0], 2),
            field_name="candidate_endpoints",
        )
        if endpoints.dtype not in {np.dtype("<u2"), np.dtype("<u4")}:
            raise ValueError("candidate_endpoints must use compact unsigned integers")
        if endpoints.size:
            if np.any(endpoints[:, 0] >= self.account_count) or np.any(endpoints[:, 1] >= self.account_count):
                raise ValueError("candidate endpoint is outside the account universe")
            if np.any(endpoints[:, 0] >= endpoints[:, 1]):
                raise ValueError("candidate endpoints must be sorted distinct pairs")
            if len(endpoints) > 1:
                previous = endpoints[:-1]
                current = endpoints[1:]
                ordered = (previous[:, 0] < current[:, 0]) | (
                    (previous[:, 0] == current[:, 0]) & (previous[:, 1] < current[:, 1])
                )
                if not bool(np.all(ordered)):
                    raise ValueError("candidate endpoints must be sorted without duplicate pairs")
        raw_scores = np.asarray(self.edge_scores)
        scores = _detached_read_only_array(
            self.edge_scores,
            dtype=raw_scores.dtype,
            shape=(len(endpoints),),
            field_name="edge_scores",
        )
        if scores.dtype != np.dtype("<f4") or not bool(np.all(np.isfinite(scores))) or bool(np.any(scores < 0.0)):
            raise ValueError("edge_scores must be finite non-negative compact float32 values")
        raw_account_scores = np.asarray(self.account_scores)
        account_scores = _detached_read_only_array(
            self.account_scores,
            dtype=raw_account_scores.dtype,
            shape=(self.account_count,),
            field_name="account_scores",
        )
        if account_scores.dtype != np.dtype("<f4") or not bool(np.all(np.isfinite(account_scores))):
            raise ValueError("account_scores must be finite compact float32 values")
        raw_assignments = np.asarray(self.cluster_assignments)
        if raw_assignments.shape != (self.account_count,):
            raise ValueError("cluster_assignments must cover every account exactly once")
        assignments = _detached_read_only_array(
            self.cluster_assignments,
            dtype=raw_assignments.dtype,
            shape=(self.account_count,),
            field_name="cluster_assignments",
        )
        if assignments.dtype != np.dtype("<i4") or not bool(np.all(assignments >= 0)):
            raise ValueError("cluster_assignments must be non-negative compact int32 values")
        batch_members = _cluster_members(self.discovered_cluster_batch)
        expected_members = {_account_id(index) for index in range(self.account_count)}
        if batch_members != expected_members:
            raise ValueError("discovered batch member universe must cover every account exactly once")
        if self.discovered_cluster_batch.provenance.input_account_count != self.account_count:
            raise ValueError("batch member universe account count mismatch")
        assignment_partition = {
            frozenset(
                _account_id(index)
                for index, value in enumerate(assignments.tolist())
                if value == cluster_id
            )
            for cluster_id in set(assignments.tolist())
        }
        batch_partition = {
            frozenset(cluster.member_account_ids)
            for cluster in self.discovered_cluster_batch.candidate_clusters
        }
        if assignment_partition != batch_partition:
            raise ValueError("cluster assignments do not agree with the batch member universe")
        for field_name in ("method_id", "method_version", "implementation_id"):
            object.__setattr__(self, field_name, _text(getattr(self, field_name), field_name))
        object.__setattr__(self, "candidate_endpoints", endpoints)
        object.__setattr__(self, "edge_scores", scores)
        object.__setattr__(self, "account_scores", account_scores)
        object.__setattr__(self, "cluster_assignments", assignments)
        object.__setattr__(self, "diagnostics", _immutable_mapping(self.diagnostics or {}, "diagnostics"))
        markers = tuple(sorted({_text(value, "claim_marker") for value in self.claim_markers}))
        object.__setattr__(self, "claim_markers", markers)

    @property
    def artifact_identity(self) -> str:
        return _fingerprint(
            {
                "method_id": self.method_id,
                "method_version": self.method_version,
                "implementation_id": self.implementation_id,
                "account_count": self.account_count,
                "candidate_endpoints": self.candidate_endpoints.tobytes().hex(),
                "edge_scores": self.edge_scores.tobytes().hex(),
                "account_scores": self.account_scores.tobytes().hex(),
                "cluster_assignments": self.cluster_assignments.tobytes().hex(),
            }
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "artifact_identity": self.artifact_identity,
            "method_id": self.method_id,
            "method_version": self.method_version,
            "implementation_id": self.implementation_id,
            "account_count": self.account_count,
            "candidate_edge_count": int(len(self.candidate_endpoints)),
            "discovered_cluster_batch": self.discovered_cluster_batch.to_dict(),
            "diagnostics": _plain_value(self.diagnostics),
            "claim_markers": list(self.claim_markers),
        }


class CompactDiscoveryImplementation(Protocol):
    method_id: str
    method_version: str
    implementation_id: str
    unavailable_reason: str | None

    def execute(self, execution_input: CompactDiscoveryExecutionInput) -> CompactDiscoveryPrediction:
        ...


@dataclass(frozen=True, slots=True)
class CompactDiscoveryExecutionOutcome:
    method_id: str
    method_version: str
    implementation_id: str
    execution_input_fingerprint: str
    runtime_seconds: float
    peak_memory_bytes: int
    status: str
    prediction: CompactDiscoveryPrediction | None
    reason: str | None


def execute_compact_discovery_method(
    implementations: Mapping[str, CompactDiscoveryImplementation],
    method_id: str,
    execution_input: CompactDiscoveryExecutionInput,
) -> CompactDiscoveryExecutionOutcome:
    if not isinstance(implementations, MappingABC):
        raise ValueError("implementations must be a mapping")
    if not isinstance(execution_input, CompactDiscoveryExecutionInput):
        raise ValueError("execution_input must be CompactDiscoveryExecutionInput")
    implementation = implementations.get(method_id)
    if implementation is None:
        return CompactDiscoveryExecutionOutcome(
            method_id=_text(method_id, "method_id"),
            method_version="unavailable",
            implementation_id="unavailable",
            execution_input_fingerprint=execution_input.fingerprint,
            runtime_seconds=0.0,
            peak_memory_bytes=0,
            status="blocked",
            prediction=None,
            reason="compact Discovery implementation is unavailable",
        )
    unavailable = getattr(implementation, "unavailable_reason", None)
    common = {
        "method_id": _text(getattr(implementation, "method_id", method_id), "method_id"),
        "method_version": _text(getattr(implementation, "method_version", "unknown"), "method_version"),
        "implementation_id": _text(getattr(implementation, "implementation_id", "unknown"), "implementation_id"),
        "execution_input_fingerprint": execution_input.fingerprint,
    }
    if unavailable:
        return CompactDiscoveryExecutionOutcome(
            **common,
            runtime_seconds=0.0,
            peak_memory_bytes=0,
            status="blocked",
            prediction=None,
            reason=str(unavailable),
        )
    started_probe = not tracemalloc.is_tracing()
    if started_probe:
        tracemalloc.start()
    baseline_memory = tracemalloc.get_traced_memory()[0]
    tracemalloc.reset_peak()
    started = time.perf_counter()
    try:
        prediction = implementation.execute(execution_input)
        if not isinstance(prediction, CompactDiscoveryPrediction):
            raise ValueError("compact Discovery implementation returned an invalid prediction")
        expected_dataset = f"iohunter-{execution_input.discovery_view.campaign}"
        provenance = prediction.discovered_cluster_batch.provenance
        if provenance.source_dataset != expected_dataset:
            raise ValueError("compact Discovery prediction campaign does not match execution input")
        if provenance.data_fingerprint != execution_input.discovery_view.source_layer_fingerprint:
            raise ValueError("compact Discovery prediction data fingerprint does not match execution input")
        if prediction.account_count != execution_input.discovery_view.account_count:
            raise ValueError("compact Discovery prediction account universe does not match execution input")
        for field_name in ("method_id", "method_version", "implementation_id"):
            if getattr(prediction, field_name) != common[field_name]:
                raise ValueError(f"compact Discovery prediction {field_name} does not match implementation")
        _, peak = tracemalloc.get_traced_memory()
        return CompactDiscoveryExecutionOutcome(
            **common,
            runtime_seconds=time.perf_counter() - started,
            peak_memory_bytes=max(0, int(peak - baseline_memory)),
            status="success",
            prediction=prediction,
            reason=None,
        )
    except Exception as exc:
        _, peak = tracemalloc.get_traced_memory()
        return CompactDiscoveryExecutionOutcome(
            **common,
            runtime_seconds=time.perf_counter() - started,
            peak_memory_bytes=max(0, int(peak - baseline_memory)),
            status="failed",
            prediction=None,
            reason=f"{type(exc).__name__}: {exc}",
        )
    finally:
        if started_probe:
            tracemalloc.stop()


@dataclass(frozen=True, slots=True)
class IOHunterExternalEvaluationInput:
    evaluator: CompactIOHunterEvaluator
    fold: CompactIOHunterFold
    evaluation_config: Mapping[str, Any]

    def __post_init__(self) -> None:
        if not isinstance(self.evaluator, CompactIOHunterEvaluator):
            raise ValueError("evaluator must be CompactIOHunterEvaluator")
        if not isinstance(self.fold, CompactIOHunterFold):
            raise ValueError("fold must be CompactIOHunterFold")
        owned = {candidate.fold_id: candidate for candidate in self.evaluator.official_folds}
        canonical = owned.get(self.fold.fold_id)
        if canonical is None or any(
            not np.array_equal(getattr(self.fold, field_name), getattr(canonical, field_name))
            for field_name in ("train_indices", "validation_indices", "test_indices")
        ):
            raise ValueError("fold does not belong to evaluator")
        object.__setattr__(self, "evaluation_config", _immutable_mapping(self.evaluation_config, "evaluation_config"))

    @property
    def fingerprint(self) -> str:
        return _fingerprint(
            {
                "evaluator": self.evaluator.content_fingerprint,
                "fold": self.fold.fold_id,
                "evaluation_config": _plain_value(self.evaluation_config),
            }
        )


@dataclass(frozen=True, slots=True)
class IOHunterExternalEvaluationResult:
    status: str
    threshold: float | None
    threshold_source: str
    metrics: Mapping[str, float]
    evaluation_scope: str
    label_semantics: str
    claim_markers: tuple[str, ...]
    audit: Mapping[str, Any]
    execution_artifact_identity: str
    evaluator_fingerprint: str
    fold_id: str
    fold_fingerprint: str
    reason: str | None = None

    def __post_init__(self) -> None:
        if self.status not in {"success", "blocked", "failed"}:
            raise ValueError("status must be success, blocked, or failed")
        object.__setattr__(self, "metrics", _immutable_mapping(self.metrics, "metrics"))
        object.__setattr__(self, "audit", _immutable_mapping(self.audit, "audit"))
        object.__setattr__(
            self,
            "execution_artifact_identity",
            _text(self.execution_artifact_identity, "execution_artifact_identity"),
        )
        object.__setattr__(self, "evaluator_fingerprint", _text(self.evaluator_fingerprint, "evaluator_fingerprint"))
        object.__setattr__(self, "fold_id", _text(self.fold_id, "fold_id"))
        object.__setattr__(self, "fold_fingerprint", _text(self.fold_fingerprint, "fold_fingerprint"))
        object.__setattr__(
            self,
            "claim_markers",
            tuple(sorted({_text(value, "claim_marker") for value in self.claim_markers})),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "threshold": self.threshold,
            "threshold_source": self.threshold_source,
            "metrics": _plain_value(self.metrics),
            "evaluation_scope": self.evaluation_scope,
            "label_semantics": self.label_semantics,
            "claim_markers": list(self.claim_markers),
            "audit": _plain_value(self.audit),
            "execution_artifact_identity": self.execution_artifact_identity,
            "evaluator_fingerprint": self.evaluator_fingerprint,
            "fold_id": self.fold_id,
            "fold_fingerprint": self.fold_fingerprint,
            "reason": self.reason,
        }


def _macro_f1(labels: np.ndarray, predictions: np.ndarray) -> float:
    values = []
    for positive in (0, 1):
        truth = labels == positive
        guess = predictions == positive
        tp = int(np.sum(truth & guess))
        fp = int(np.sum(~truth & guess))
        fn = int(np.sum(truth & ~guess))
        denominator = 2 * tp + fp + fn
        values.append(0.0 if denominator == 0 else (2.0 * tp) / denominator)
    return float(np.mean(values))


def _validation_threshold(labels: np.ndarray, scores: np.ndarray) -> float:
    unique_scores = np.unique(scores.astype(np.float64))
    candidates = np.r_[unique_scores, np.nextafter(unique_scores[-1], np.inf)]
    best = (-1.0, float(candidates[0]))
    for threshold in candidates:
        value = _macro_f1(labels, (scores >= threshold).astype(np.int64))
        if value > best[0] or (value == best[0] and threshold < best[1]):
            best = (value, float(threshold))
    return best[1]


def _blocked_result(
    prediction: CompactDiscoveryPrediction,
    evaluation: IOHunterExternalEvaluationInput,
    reason: str,
) -> IOHunterExternalEvaluationResult:
    fold_fingerprint = compact_fold_fingerprint(evaluation.fold)
    return IOHunterExternalEvaluationResult(
        status="blocked",
        threshold=None,
        threshold_source="not_fitted",
        metrics={},
        evaluation_scope=_EVALUATION_SCOPE,
        label_semantics=IOHUNTER_LABEL_SEMANTICS,
        claim_markers=_CLAIM_MARKERS,
        audit={
            "evaluation_after_execution": True,
            "fit_provenance": "validation_only",
            "execution_artifact_identity": prediction.artifact_identity,
            "fold_fingerprint": fold_fingerprint,
        },
        execution_artifact_identity=prediction.artifact_identity,
        evaluator_fingerprint=evaluation.evaluator.content_fingerprint,
        fold_id=evaluation.fold.fold_id,
        fold_fingerprint=fold_fingerprint,
        reason=reason,
    )


def evaluate_iohunter_external_account_recovery(
    prediction: CompactDiscoveryPrediction,
    evaluation: IOHunterExternalEvaluationInput,
) -> IOHunterExternalEvaluationResult:
    if not isinstance(prediction, CompactDiscoveryPrediction):
        raise ValueError("prediction must be CompactDiscoveryPrediction")
    if not isinstance(evaluation, IOHunterExternalEvaluationInput):
        raise ValueError("evaluation must be IOHunterExternalEvaluationInput")
    expected_dataset = f"iohunter-{evaluation.evaluator.campaign}"
    if prediction.discovered_cluster_batch.provenance.source_dataset != expected_dataset:
        raise ValueError("prediction and evaluator campaign do not match")
    labels = evaluation.evaluator.account_labels
    if prediction.account_count != labels.size:
        raise ValueError("prediction and evaluator account universe do not match")
    validation = evaluation.fold.validation_indices
    test = evaluation.fold.test_indices
    validation_labels = labels[validation]
    test_labels = labels[test]
    if len(np.unique(validation_labels)) != 2:
        return _blocked_result(prediction, evaluation, "validation partition has one class")
    if len(np.unique(test_labels)) != 2:
        return _blocked_result(prediction, evaluation, "test partition has one class")
    threshold = _validation_threshold(validation_labels, prediction.account_scores[validation])
    test_scores = prediction.account_scores[test].astype(np.float64)
    decisions = (test_scores >= threshold).astype(np.int64)
    positives = int(np.sum(test_labels))
    ranking = np.argsort(-test_scores, kind="stable")
    top_k = ranking[:positives]
    recall_at_k = float(np.sum(test_labels[top_k])) / positives if positives else 0.0
    metrics = {
        "external_account_auprc": average_precision(test_labels.tolist(), test_scores.tolist()),
        "external_account_roc_auc": roc_auc(test_labels.tolist(), test_scores.tolist()),
        "external_account_macro_f1": _macro_f1(test_labels, decisions),
        "external_account_recall_at_k": recall_at_k,
        "external_account_evaluated_count": float(len(test)),
    }
    fold_fingerprint = compact_fold_fingerprint(evaluation.fold)
    return IOHunterExternalEvaluationResult(
        status="success",
        threshold=threshold,
        threshold_source="validation_only",
        metrics=metrics,
        evaluation_scope=_EVALUATION_SCOPE,
        label_semantics=IOHUNTER_LABEL_SEMANTICS,
        claim_markers=_CLAIM_MARKERS,
        audit={
            "evaluation_after_execution": True,
            "fit_provenance": "validation_only",
            "test_label_access": "metrics_only",
            "execution_artifact_identity": prediction.artifact_identity,
            "fold_fingerprint": fold_fingerprint,
        },
        execution_artifact_identity=prediction.artifact_identity,
        evaluator_fingerprint=evaluation.evaluator.content_fingerprint,
        fold_id=evaluation.fold.fold_id,
        fold_fingerprint=fold_fingerprint,
    )


__all__ = [
    "CompactDiscoveryExecutionInput",
    "CompactDiscoveryExecutionOutcome",
    "CompactDiscoveryImplementation",
    "CompactDiscoveryPrediction",
    "IOHunterExternalEvaluationInput",
    "IOHunterExternalEvaluationResult",
    "evaluate_iohunter_external_account_recovery",
    "execute_compact_discovery_method",
]
