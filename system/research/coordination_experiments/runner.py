from __future__ import annotations

import csv
import hashlib
import json
import math
import time
import tracemalloc
from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from types import MappingProxyType
from typing import Any

import numpy as np

from research.coordination_detect.contracts import (
    DetectionModelArtifact,
    DetectionTrainingCase,
    case_id_fingerprint,
)
from research.coordination_discover.stage1.events import CoordinationEvent

from .baselines import (
    BaselineRegistry,
    DiscoveryImplementation,
    HEURISTIC_BASELINE_ID,
    HEURISTIC_BASELINE_WARNING,
    HeuristicDetectionImplementation,
    LearnedDetectionImplementation,
)
from .iohunter import IOHUNTER_CAMPAIGNS
from .metrics import (
    bootstrap_confidence_interval,
    cross_seed_stability,
    detection_metrics,
    discovery_metrics,
    metric_direction,
)
from .protocol import DatasetCapability, ExperimentSplit, ResearchDatasetManifest


_STATUSES = {"success", "failed", "blocked"}
_GATE_STATUSES = {"supported", "not_supported", "blocked"}
_CLAIM_SCOPES = {"general", "harmful_cib", "observed_time", "auxiliary"}
_DISCOVERY_METRICS = frozenset(
    {
        "candidate_recall",
        "spectral_distortion",
        "edge_auprc",
        "b_cubed_precision",
        "b_cubed_recall",
        "b_cubed_f1",
        "nmi",
        "ari",
        "cross_seed_stability",
    }
)
_DETECTION_METRICS = frozenset(
    {
        "auprc",
        "macro_f1",
        "roc_auc",
        "ece",
        "selective_coverage",
        "selective_risk",
        "abstain_rate",
    }
)
def _text(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip() or value != value.strip():
        raise ValueError(f"{field_name} must be non-empty canonical text")
    return value


def _optional_text(value: Any, field_name: str) -> str | None:
    return None if value is None else _text(value, field_name)


def _non_negative_number(value: Any, field_name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{field_name} must be numeric")
    result = float(value)
    if not math.isfinite(result) or result < 0.0:
        raise ValueError(f"{field_name} must be finite and non-negative")
    return result


def _metric_number(value: Any, metric_name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"metric {metric_name} must be numeric")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"metric {metric_name} must be finite")
    if metric_name in {"ari", "cross_seed_stability"}:
        if not -1.0 <= result <= 1.0:
            raise ValueError(f"metric {metric_name} must be within [-1, 1]")
    elif result < 0.0:
        raise ValueError(f"metric {metric_name} must be non-negative")
    return result


def _canonical_json(value: Any) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")


def _fingerprint(value: Any) -> str:
    return f"sha256:{hashlib.sha256(_canonical_json(value)).hexdigest()}"


def _text_tuple(values: Sequence[str], field_name: str) -> tuple[str, ...]:
    if isinstance(values, (str, bytes)) or not isinstance(values, Sequence):
        raise ValueError(f"{field_name} must be a sequence")
    result = tuple(_text(value, field_name) for value in values)
    if len(result) != len(set(result)):
        raise ValueError(f"{field_name} contains duplicates")
    return result


def _freeze_json(value: Any, field_name: str) -> Any:
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float) and math.isfinite(value):
        return value
    if isinstance(value, Mapping):
        normalized: dict[str, Any] = {}
        for key, item in value.items():
            name = _text(key, field_name)
            normalized[name] = _freeze_json(item, field_name)
        return MappingProxyType(dict(sorted(normalized.items())))
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        return tuple(_freeze_json(item, field_name) for item in value)
    raise ValueError(f"{field_name} values must be finite JSON values")


def _json_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {key: _json_value(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_json_value(item) for item in value]
    return value


def _immutable_audit(value: Mapping[str, Any]) -> Mapping[str, Any]:
    if not isinstance(value, Mapping) or not value:
        raise ValueError("every result row requires a non-empty verified audit")
    return _freeze_json(value, "audit field")


def _canonical_iohunter_dataset(dataset_id: str) -> bool:
    return any(dataset_id == f"iohunter-{campaign}" for campaign in IOHUNTER_CAMPAIGNS)


def _rehydrate_and_verify_detection_artifact(
    serialized_artifact: Mapping[str, Any] | DetectionModelArtifact | None,
    *,
    train_partition_fingerprint: str | None,
    validation_partition_fingerprint: str | None,
    test_partition_fingerprint: str | None,
) -> tuple[DetectionModelArtifact, Mapping[str, Any]]:
    if serialized_artifact is None:
        raise ValueError(
            "successful learned Detection rows require a serialized Stage 2 model artifact"
        )
    if isinstance(serialized_artifact, DetectionModelArtifact):
        artifact = serialized_artifact
    elif isinstance(serialized_artifact, Mapping):
        artifact = DetectionModelArtifact.from_dict(_json_value(serialized_artifact))
    else:
        raise ValueError("model_artifact must be a serialized Stage 2 model artifact")
    if not all(
        isinstance(value, str) and value
        for value in (
            train_partition_fingerprint,
            validation_partition_fingerprint,
            test_partition_fingerprint,
        )
    ):
        raise ValueError("learned Detection rows require persisted partition fingerprints")
    expected = {
        "train_fit_case_ids_fingerprint": train_partition_fingerprint,
        "validation_calibration_case_ids_fingerprint": validation_partition_fingerprint,
        "validation_threshold_case_ids_fingerprint": validation_partition_fingerprint,
        "validation_ood_case_ids_fingerprint": validation_partition_fingerprint,
    }
    for field_name, fingerprint in expected.items():
        if getattr(artifact, field_name) != fingerprint:
            raise ValueError(f"Stage 2 artifact {field_name} does not match persisted partitions")
    return artifact, MappingProxyType(
        {
            "fit_provenance_source": "stage2_model_artifact",
            "model_artifact_hash": artifact.artifact_hash,
            "model_artifact_version": artifact.model_version,
            "train_partition_fingerprint": train_partition_fingerprint,
            "validation_partition_fingerprint": validation_partition_fingerprint,
            "test_partition_fingerprint": test_partition_fingerprint,
        }
    )


def validate_dataset_identity(
    manifest: ResearchDatasetManifest, capability: DatasetCapability
) -> None:
    if not isinstance(manifest, ResearchDatasetManifest) or not isinstance(
        capability, DatasetCapability
    ):
        raise ValueError("manifest and capability must use Task 5 contracts")
    if capability.dataset_id == "iohunter":
        if len(manifest.campaign_axis) != 1:
            raise ValueError("canonical IOHunter manifests require exactly one campaign")
        campaign = manifest.campaign_axis[0]
        if campaign not in IOHUNTER_CAMPAIGNS:
            raise ValueError("canonical IOHunter manifest campaign is invalid")
        if manifest.dataset_id != f"iohunter-{campaign}":
            raise ValueError("canonical IOHunter manifest dataset identity does not match campaign")
        return
    if capability.dataset_id.startswith("iohunter"):
        raise ValueError("canonical IOHunter capability identity must be exactly ioHunter family 'iohunter'")
    if manifest.dataset_id != capability.dataset_id:
        raise ValueError("manifest and capability dataset identities must match exactly")


@dataclass(frozen=True, slots=True)
class ResultRow:
    dataset_id: str
    dataset_manifest_fingerprint: str
    evaluator_fingerprint: str
    split_policy: str
    split_fingerprint: str
    method_id: str
    method_version: str
    model_role: str
    seed: int
    runtime_seconds: float
    peak_memory_bytes: int
    status: str
    metrics: Mapping[str, float] = field(default_factory=dict)
    reason: str | None = None
    warning: str | None = None
    claim_markers: tuple[str, ...] = ()
    task: str = "detection"
    selection_eligible: bool = False
    ablation_id: str | None = None
    audit: Mapping[str, Any] = field(default_factory=dict)
    model_artifact: Mapping[str, Any] | DetectionModelArtifact | None = None
    train_partition_fingerprint: str | None = None
    validation_partition_fingerprint: str | None = None
    test_partition_fingerprint: str | None = None

    def __post_init__(self) -> None:
        for field_name in (
            "dataset_id",
            "dataset_manifest_fingerprint",
            "evaluator_fingerprint",
            "split_policy",
            "split_fingerprint",
            "method_id",
            "method_version",
            "model_role",
        ):
            object.__setattr__(self, field_name, _text(getattr(self, field_name), field_name))
        if self.task not in {"discovery", "detection"}:
            raise ValueError("task must be discovery or detection")
        if _canonical_iohunter_dataset(self.dataset_id) and self.split_policy == "observed_time_holdout":
            raise ValueError("IOHunter rows cannot use observed_time_holdout")
        if isinstance(self.seed, bool) or not isinstance(self.seed, int) or self.seed < 0:
            raise ValueError("seed must be a non-negative integer")
        object.__setattr__(
            self,
            "runtime_seconds",
            _non_negative_number(self.runtime_seconds, "runtime_seconds"),
        )
        memory = _non_negative_number(self.peak_memory_bytes, "peak_memory_bytes")
        if not memory.is_integer():
            raise ValueError("peak_memory_bytes must be an integer")
        object.__setattr__(self, "peak_memory_bytes", int(memory))
        if self.status not in _STATUSES:
            raise ValueError("status must be success, failed, or blocked")
        if not isinstance(self.selection_eligible, bool):
            raise ValueError("selection_eligible must be boolean")
        if self.ablation_id is not None:
            object.__setattr__(self, "ablation_id", _text(self.ablation_id, "ablation_id"))
        if not isinstance(self.metrics, Mapping):
            raise ValueError("metrics must be a mapping")
        normalized_metrics: dict[str, float] = {}
        for name, value in self.metrics.items():
            metric_name = _text(name, "metric name")
            metric_direction(metric_name)
            normalized_metrics[metric_name] = _metric_number(value, metric_name)
        object.__setattr__(
            self, "metrics", MappingProxyType(dict(sorted(normalized_metrics.items())))
        )
        object.__setattr__(self, "reason", _optional_text(self.reason, "reason"))
        object.__setattr__(self, "warning", _optional_text(self.warning, "warning"))
        object.__setattr__(
            self,
            "claim_markers",
            tuple(sorted(_text_tuple(self.claim_markers, "claim_markers"))),
        )
        for field_name in (
            "train_partition_fingerprint",
            "validation_partition_fingerprint",
            "test_partition_fingerprint",
        ):
            object.__setattr__(
                self, field_name, _optional_text(getattr(self, field_name), field_name)
            )
        audit = _immutable_audit(self.audit)
        if self.status == "success":
            if self.reason is not None:
                raise ValueError("successful rows cannot have a reason")
            required = _DISCOVERY_METRICS if self.task == "discovery" else _DETECTION_METRICS
            missing = required - set(self.metrics)
            if missing:
                raise ValueError(
                    f"successful rows require the complete {self.task} metric suite; missing {sorted(missing)}"
                )
        elif self.metrics or self.reason is None:
            raise ValueError("failed and blocked rows require a reason and cannot contain metrics")
        heuristic_signal = (
            self.method_id == HEURISTIC_BASELINE_ID
            or self.method_version == HEURISTIC_BASELINE_ID
            or self.model_role == "heuristic_baseline"
        )
        heuristic_identity = (
            self.method_id == HEURISTIC_BASELINE_ID
            and self.method_version == HEURISTIC_BASELINE_ID
            and self.model_role == "heuristic_baseline"
        )
        if heuristic_signal and not heuristic_identity:
            raise ValueError("heuristic baseline identity fields must agree")
        if heuristic_identity and (
            self.warning != HEURISTIC_BASELINE_WARNING or self.selection_eligible
        ):
            raise ValueError(
                "heuristic baseline identity requires its warning and is never selection eligible"
            )
        if heuristic_identity:
            if self.model_artifact is not None:
                raise ValueError("heuristic baseline cannot contain a learned fit audit")
            if self.train_partition_fingerprint is not None or self.validation_partition_fingerprint is not None:
                raise ValueError("heuristic baseline cannot contain a learned fit audit")
            fit_source = audit.get("fit_provenance_source")
            source_claims_learned_fit = isinstance(fit_source, str) and (
                "artifact" in fit_source.lower() or "learned" in fit_source.lower()
            )
            contains_fit_fields = any(
                key.startswith(("train_", "validation_", "model_artifact"))
                for key in audit
            )
            if source_claims_learned_fit or contains_fit_fields:
                raise ValueError("heuristic baseline cannot contain a learned fit audit")
        learned_success = (
            self.status == "success"
            and self.task == "detection"
            and self.model_role in {"primary_learned", "learned_comparison"}
        )
        if learned_success:
            artifact, derived_audit = _rehydrate_and_verify_detection_artifact(
                self.model_artifact,
                train_partition_fingerprint=self.train_partition_fingerprint,
                validation_partition_fingerprint=self.validation_partition_fingerprint,
                test_partition_fingerprint=self.test_partition_fingerprint,
            )
            normalized_audit = _json_value(audit)
            if "verified" in normalized_audit:
                raise ValueError(
                    "learned Detection rows reject arbitrary verified audit mappings"
                )
            for field_name, expected in derived_audit.items():
                if field_name in normalized_audit and normalized_audit[field_name] != expected:
                    raise ValueError(
                        f"Detection fit audit {field_name} conflicts with serialized Stage 2 model artifact"
                    )
                normalized_audit[field_name] = expected
            audit = _immutable_audit(normalized_audit)
            object.__setattr__(self, "model_artifact", _freeze_json(artifact.to_dict(), "model_artifact"))
        elif self.model_artifact is not None:
            raise ValueError("only successful learned Detection rows may carry a model artifact")
        object.__setattr__(self, "audit", audit)

    def _identity_payload(self) -> dict[str, Any]:
        return {
            "dataset_id": self.dataset_id,
            "dataset_manifest_fingerprint": self.dataset_manifest_fingerprint,
            "evaluator_fingerprint": self.evaluator_fingerprint,
            "split_policy": self.split_policy,
            "split_fingerprint": self.split_fingerprint,
            "method_id": self.method_id,
            "method_version": self.method_version,
            "model_role": self.model_role,
            "seed": self.seed,
            "runtime_seconds": self.runtime_seconds,
            "peak_memory_bytes": self.peak_memory_bytes,
            "status": self.status,
            "metrics": dict(self.metrics),
            "reason": self.reason,
            "warning": self.warning,
            "claim_markers": list(self.claim_markers),
            "task": self.task,
            "selection_eligible": self.selection_eligible,
            "ablation_id": self.ablation_id,
            "audit": _json_value(self.audit),
            "model_artifact": _json_value(self.model_artifact),
            "train_partition_fingerprint": self.train_partition_fingerprint,
            "validation_partition_fingerprint": self.validation_partition_fingerprint,
            "test_partition_fingerprint": self.test_partition_fingerprint,
        }

    @property
    def artifact_identity(self) -> str:
        return _fingerprint(self._identity_payload())

    @property
    def series_identity(self) -> tuple[str, ...]:
        return (
            self.task,
            self.dataset_id,
            self.split_policy,
            self.method_id,
            self.method_version,
            self.ablation_id or "none",
        )

    def to_dict(self) -> dict[str, Any]:
        payload = self._identity_payload()
        payload["artifact_identity"] = self.artifact_identity
        return payload

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "ResultRow":
        if not isinstance(value, Mapping):
            raise ValueError("ResultRow must be a mapping")
        expected = {
            "dataset_id", "dataset_manifest_fingerprint", "evaluator_fingerprint",
            "split_policy", "split_fingerprint", "method_id", "method_version",
            "model_role", "seed", "runtime_seconds", "peak_memory_bytes", "status",
            "metrics", "reason", "warning", "claim_markers", "task",
            "selection_eligible", "ablation_id", "audit", "model_artifact",
            "train_partition_fingerprint", "validation_partition_fingerprint",
            "test_partition_fingerprint", "artifact_identity",
        }
        if set(value) != expected:
            raise ValueError("ResultRow serialized fields do not match the Task 6 schema")
        row = cls(**{key: value[key] for key in expected - {"artifact_identity"}})
        if value["artifact_identity"] != row.artifact_identity:
            raise ValueError("ResultRow artifact_identity does not match canonical payload")
        return row


@dataclass(frozen=True, slots=True)
class AggregateResult:
    task: str
    dataset_id: str
    split_policy: str
    method_id: str
    method_version: str
    model_role: str
    ablation_id: str | None
    metric_name: str
    direction: str
    successful_seed_count: int
    seeds: tuple[int, ...]
    mean: float
    std: float
    ci_low: float
    ci_high: float
    dataset_manifest_fingerprints: tuple[str, ...]
    evaluator_fingerprints: tuple[str, ...]
    split_fingerprints: tuple[str, ...]
    observed_artifact_identities: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "task": self.task,
            "dataset_id": self.dataset_id,
            "split_policy": self.split_policy,
            "method_id": self.method_id,
            "method_version": self.method_version,
            "model_role": self.model_role,
            "ablation_id": self.ablation_id,
            "metric_name": self.metric_name,
            "direction": self.direction,
            "successful_seed_count": self.successful_seed_count,
            "seeds": list(self.seeds),
            "mean": self.mean,
            "std": self.std,
            "ci_low": self.ci_low,
            "ci_high": self.ci_high,
            "dataset_manifest_fingerprints": list(self.dataset_manifest_fingerprints),
            "evaluator_fingerprints": list(self.evaluator_fingerprints),
            "split_fingerprints": list(self.split_fingerprints),
            "observed_artifact_identities": list(self.observed_artifact_identities),
        }


def _validate_result_row_artifact_audit(row: ResultRow) -> None:
    if not (
        row.status == "success"
        and row.task == "detection"
        and row.model_role in {"primary_learned", "learned_comparison"}
    ):
        return
    _, derived_audit = _rehydrate_and_verify_detection_artifact(
        row.model_artifact,
        train_partition_fingerprint=row.train_partition_fingerprint,
        validation_partition_fingerprint=row.validation_partition_fingerprint,
        test_partition_fingerprint=row.test_partition_fingerprint,
    )
    for field_name, expected in derived_audit.items():
        if row.audit.get(field_name) != expected:
            raise ValueError("result row artifact-level fit audit is invalid")


def _reject_duplicate_successful_seeds(rows: Sequence[ResultRow]) -> None:
    seen: set[tuple[tuple[str, ...], int]] = set()
    for row in rows:
        if row.status != "success":
            continue
        identity = (row.series_identity, row.seed)
        if identity in seen:
            raise ValueError(
                f"duplicate successful seed {row.seed} for result series {row.series_identity}"
            )
        seen.add(identity)


def aggregate_result_rows(
    rows: Sequence[ResultRow],
    *,
    bootstrap_seed: int = 0,
    bootstrap_resamples: int = 2_000,
) -> tuple[AggregateResult, ...]:
    if not isinstance(rows, Sequence) or not all(isinstance(row, ResultRow) for row in rows):
        raise ValueError("rows must contain ResultRow values")
    for row in rows:
        _validate_result_row_artifact_audit(row)
    _reject_duplicate_successful_seeds(rows)
    groups: dict[tuple[str, ...], list[tuple[ResultRow, float]]] = defaultdict(list)
    for row in rows:
        if row.status != "success":
            continue
        values = {
            **row.metrics,
            "runtime_seconds": row.runtime_seconds,
            "peak_memory_bytes": float(row.peak_memory_bytes),
        }
        for metric_name, value in values.items():
            groups[(*row.series_identity, row.model_role, metric_name)].append((row, value))
    aggregates: list[AggregateResult] = []
    for key, observations in sorted(groups.items()):
        observations.sort(key=lambda item: (item[0].seed, item[0].artifact_identity))
        values = tuple(value for _, value in observations)
        low, high = bootstrap_confidence_interval(
            values, seed=bootstrap_seed, resamples=bootstrap_resamples
        )
        aggregates.append(
            AggregateResult(
                task=key[0],
                dataset_id=key[1],
                split_policy=key[2],
                method_id=key[3],
                method_version=key[4],
                ablation_id=None if key[5] == "none" else key[5],
                model_role=key[6],
                metric_name=key[7],
                direction=metric_direction(key[7]),
                successful_seed_count=len(observations),
                seeds=tuple(row.seed for row, _ in observations),
                mean=float(np.mean(values)),
                std=float(np.std(values, ddof=0)),
                ci_low=low,
                ci_high=high,
                dataset_manifest_fingerprints=tuple(
                    sorted({row.dataset_manifest_fingerprint for row, _ in observations})
                ),
                evaluator_fingerprints=tuple(
                    sorted({row.evaluator_fingerprint for row, _ in observations})
                ),
                split_fingerprints=tuple(
                    sorted({row.split_fingerprint for row, _ in observations})
                ),
                observed_artifact_identities=tuple(
                    row.artifact_identity for row, _ in observations
                ),
            )
        )
    return tuple(aggregates)


@dataclass(frozen=True, slots=True)
class ClaimGate:
    gate_id: str
    metric_name: str
    direction: str
    threshold: float
    claim_scope: str
    minimum_successful_seeds: int = 1
    dataset_id: str | None = None
    method_id: str | None = None
    required_split_policy: str | None = None
    forbidden_claim_markers: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "gate_id", _text(self.gate_id, "gate_id"))
        object.__setattr__(self, "metric_name", _text(self.metric_name, "metric_name"))
        expected = metric_direction(self.metric_name)
        if self.direction != expected:
            raise ValueError(f"claim gate direction for {self.metric_name} must be {expected}")
        object.__setattr__(self, "threshold", _non_negative_number(self.threshold, "threshold"))
        if self.claim_scope not in _CLAIM_SCOPES:
            raise ValueError(f"claim_scope must be one of {sorted(_CLAIM_SCOPES)}")
        if (
            isinstance(self.minimum_successful_seeds, bool)
            or not isinstance(self.minimum_successful_seeds, int)
            or self.minimum_successful_seeds <= 0
        ):
            raise ValueError("minimum_successful_seeds must be a positive integer")
        for field_name in ("dataset_id", "method_id", "required_split_policy"):
            object.__setattr__(
                self, field_name, _optional_text(getattr(self, field_name), field_name)
            )
        object.__setattr__(
            self,
            "forbidden_claim_markers",
            tuple(
                sorted(_text_tuple(self.forbidden_claim_markers, "forbidden_claim_markers"))
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "gate_id": self.gate_id,
            "metric_name": self.metric_name,
            "direction": self.direction,
            "threshold": self.threshold,
            "claim_scope": self.claim_scope,
            "minimum_successful_seeds": self.minimum_successful_seeds,
            "dataset_id": self.dataset_id,
            "method_id": self.method_id,
            "required_split_policy": self.required_split_policy,
            "forbidden_claim_markers": list(self.forbidden_claim_markers),
        }


@dataclass(frozen=True, slots=True)
class ClaimGateResult:
    gate_id: str
    metric_name: str
    direction: str
    threshold: float
    status: str
    observed_value: float | None
    observed_seed_count: int
    observed_artifact_identities: tuple[str, ...]
    reason: str | None
    gate_definition: Mapping[str, Any]

    def __post_init__(self) -> None:
        if self.status not in _GATE_STATUSES:
            raise ValueError("claim gate result status is invalid")
        object.__setattr__(self, "gate_definition", MappingProxyType(dict(self.gate_definition)))

    def to_dict(self) -> dict[str, Any]:
        return {
            "gate_id": self.gate_id,
            "metric_name": self.metric_name,
            "direction": self.direction,
            "threshold": self.threshold,
            "status": self.status,
            "observed_value": self.observed_value,
            "observed_seed_count": self.observed_seed_count,
            "observed_artifact_identities": list(self.observed_artifact_identities),
            "reason": self.reason,
            "gate_definition": dict(self.gate_definition),
        }


def _gate_result(
    gate: ClaimGate,
    status: str,
    rows: Sequence[ResultRow],
    *,
    value: float | None = None,
    reason: str | None = None,
) -> ClaimGateResult:
    return ClaimGateResult(
        gate_id=gate.gate_id,
        metric_name=gate.metric_name,
        direction=gate.direction,
        threshold=gate.threshold,
        status=status,
        observed_value=value,
        observed_seed_count=len({row.seed for row in rows}),
        observed_artifact_identities=tuple(sorted(row.artifact_identity for row in rows)),
        reason=reason,
        gate_definition=gate.to_dict(),
    )


def evaluate_claim_gate(gate: ClaimGate, rows: Sequence[ResultRow]) -> ClaimGateResult:
    if not isinstance(gate, ClaimGate) or not all(isinstance(row, ResultRow) for row in rows):
        raise ValueError("gate and rows must use Task 6 contracts")
    for row in rows:
        _validate_result_row_artifact_audit(row)
    scoped = [
        row
        for row in rows
        if (gate.dataset_id is None or row.dataset_id == gate.dataset_id)
        and (gate.method_id is None or row.method_id == gate.method_id)
    ]
    if gate.claim_scope == "harmful_cib":
        restricted = [
            row
            for row in scoped
            if "not_harmful_cib_claim" in row.claim_markers
            or row.dataset_id == "cresci-2017"
        ]
        if restricted:
            return _gate_result(
                gate,
                "blocked",
                (),
                reason="intrinsic not_harmful_cib_claim restriction blocks harmful-CIB claims",
            )
    if gate.claim_scope == "observed_time":
        restricted = [
            row
            for row in scoped
            if "static_placeholder_not_observed_time" in row.claim_markers
            or _canonical_iohunter_dataset(row.dataset_id)
        ]
        if restricted:
            return _gate_result(
                gate,
                "blocked",
                (),
                reason=(
                    "intrinsic static_placeholder_not_observed_time restriction blocks "
                    "observed-time claims"
                ),
            )
    forbidden = sorted(
        {
            marker
            for row in scoped
            for marker in row.claim_markers
            if marker in gate.forbidden_claim_markers
        }
    )
    if forbidden:
        return _gate_result(
            gate,
            "blocked",
            (),
            reason=f"forbidden claim markers observed: {', '.join(forbidden)}",
        )
    if gate.required_split_policy is not None:
        matching = [row for row in scoped if row.split_policy == gate.required_split_policy]
        if not matching:
            return _gate_result(
                gate,
                "blocked",
                (),
                reason=f"required split policy {gate.required_split_policy} has no observed rows",
            )
        scoped = matching

    def has_metric(row: ResultRow) -> bool:
        return gate.metric_name in row.metrics or gate.metric_name in {
            "runtime_seconds",
            "peak_memory_bytes",
        }

    def value_for(row: ResultRow) -> float:
        if gate.metric_name == "runtime_seconds":
            return row.runtime_seconds
        if gate.metric_name == "peak_memory_bytes":
            return float(row.peak_memory_bytes)
        return row.metrics[gate.metric_name]

    observed = sorted(
        (row for row in scoped if row.status == "success" and has_metric(row)),
        key=lambda row: (row.seed, row.artifact_identity),
    )
    series = {row.series_identity for row in observed}
    if len(series) > 1:
        return _gate_result(
            gate,
            "blocked",
            observed,
            reason="claim gate observations span multiple dataset/method/split/ablation series",
        )
    seed_counts: dict[int, int] = defaultdict(int)
    for row in observed:
        seed_counts[row.seed] += 1
    duplicates = sorted(seed for seed, count in seed_counts.items() if count > 1)
    if duplicates:
        return _gate_result(
            gate,
            "blocked",
            observed,
            reason=f"duplicate successful seed observations are not allowed: {duplicates}",
        )
    if len(seed_counts) < gate.minimum_successful_seeds:
        return _gate_result(
            gate,
            "blocked",
            observed,
            reason=(
                f"requires {gate.minimum_successful_seeds} distinct successful observed seeds; "
                f"found {len(seed_counts)}"
            ),
        )
    value = float(np.mean([value_for(row) for row in observed]))
    supported = value >= gate.threshold if gate.direction == "maximize" else value <= gate.threshold
    return _gate_result(
        gate, "supported" if supported else "not_supported", observed, value=value
    )


def _event_identity(event: CoordinationEvent) -> dict[str, Any]:
    return {
        "account_id": event.account_id,
        "relation": event.relation,
        "object_id": event.object_id,
        "observed_at": event.observed_at.isoformat(),
        "weight": event.weight,
        "evidence_ref": event.evidence_ref,
    }


@dataclass(frozen=True, slots=True)
class DiscoveryExecutionInput:
    manifest: ResearchDatasetManifest
    events: tuple[CoordinationEvent, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.manifest, ResearchDatasetManifest):
            raise ValueError("manifest must be a ResearchDatasetManifest")
        if isinstance(self.events, (str, bytes)) or not isinstance(self.events, Sequence) or not self.events:
            raise ValueError("events must be a non-empty label-free sequence")
        events: list[CoordinationEvent] = []
        for event in self.events:
            if type(event) is not CoordinationEvent:
                raise ValueError("Discovery requires exact canonical CoordinationEvent values")
            events.append(
                CoordinationEvent(
                    account_id=event.account_id,
                    relation=event.relation,
                    object_id=event.object_id,
                    observed_at=event.observed_at,
                    weight=event.weight,
                    evidence_ref=event.evidence_ref,
                )
            )
        object.__setattr__(self, "events", tuple(events))

    @property
    def fingerprint(self) -> str:
        return _fingerprint(
            {
                "manifest_fingerprint": self.manifest.fingerprint,
                "events": [_event_identity(event) for event in self.events],
            }
        )


@dataclass(frozen=True, slots=True)
class DiscoveryPrediction:
    candidate_edges: tuple[tuple[str, str], ...]
    approximate_quadratic_forms: tuple[float, ...]
    edge_score_edges: tuple[tuple[str, str], ...]
    edge_scores: tuple[float, ...]
    predicted_clusters: Mapping[str, str]
    artifact_identity: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "candidate_edges", tuple(tuple(edge) for edge in self.candidate_edges))
        object.__setattr__(self, "edge_score_edges", tuple(tuple(edge) for edge in self.edge_score_edges))
        object.__setattr__(self, "approximate_quadratic_forms", tuple(self.approximate_quadratic_forms))
        object.__setattr__(self, "edge_scores", tuple(self.edge_scores))
        if len(self.edge_score_edges) != len(self.edge_scores):
            raise ValueError("edge_score_edges and edge_scores must align")
        if not isinstance(self.predicted_clusters, Mapping) or not self.predicted_clusters:
            raise ValueError("predicted_clusters must be a non-empty mapping")
        object.__setattr__(
            self, "predicted_clusters", MappingProxyType(dict(sorted(self.predicted_clusters.items())))
        )
        object.__setattr__(self, "artifact_identity", _text(self.artifact_identity, "artifact_identity"))


@dataclass(frozen=True, slots=True)
class DiscoveryStabilityPeer:
    seed: int
    prediction_artifact_identity: str
    predicted_clusters: Mapping[str, str]
    current_seed: int

    def __post_init__(self) -> None:
        for field_name in ("seed", "current_seed"):
            value = getattr(self, field_name)
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ValueError(f"{field_name} must be a non-negative integer")
        if self.seed == self.current_seed:
            raise ValueError("peer seed must differ from current seed")
        object.__setattr__(
            self,
            "prediction_artifact_identity",
            _text(self.prediction_artifact_identity, "prediction_artifact_identity"),
        )
        if not isinstance(self.predicted_clusters, Mapping) or not self.predicted_clusters:
            raise ValueError("predicted_clusters must be a non-empty mapping")
        object.__setattr__(
            self,
            "predicted_clusters",
            MappingProxyType(dict(sorted(self.predicted_clusters.items()))),
        )


@dataclass(frozen=True, slots=True)
class DiscoveryEvaluationInput:
    evaluator_fingerprint: str
    split: ExperimentSplit
    reference_edges: tuple[tuple[str, str], ...]
    reference_quadratic_forms: tuple[float, ...]
    edge_score_edges: tuple[tuple[str, str], ...]
    edge_labels: tuple[int, ...]
    true_clusters: Mapping[str, str]
    stability_peers: tuple[DiscoveryStabilityPeer, ...]

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "evaluator_fingerprint", _text(self.evaluator_fingerprint, "evaluator_fingerprint")
        )
        if not isinstance(self.split, ExperimentSplit):
            raise ValueError("split must be an ExperimentSplit")
        for field_name in (
            "reference_edges",
            "reference_quadratic_forms",
            "edge_score_edges",
            "edge_labels",
            "stability_peers",
        ):
            value = getattr(self, field_name)
            if isinstance(value, (str, bytes)) or not isinstance(value, Sequence) or not value:
                raise ValueError(f"{field_name} must be a non-empty sealed evaluation sequence")
            object.__setattr__(self, field_name, tuple(value))
        if len(self.edge_score_edges) != len(self.edge_labels):
            raise ValueError("sealed edge labels must align with edge_score_edges")
        if not isinstance(self.true_clusters, Mapping) or not self.true_clusters:
            raise ValueError("true_clusters must be a non-empty sealed mapping")
        object.__setattr__(
            self, "true_clusters", MappingProxyType(dict(sorted(self.true_clusters.items())))
        )
        if not all(isinstance(peer, DiscoveryStabilityPeer) for peer in self.stability_peers):
            raise ValueError("stability_peers must contain DiscoveryStabilityPeer values")
        if any(peer.current_seed != self.split.seed for peer in self.stability_peers):
            raise ValueError("stability peer current_seed must match the evaluation split seed")
        seeds = [peer.seed for peer in self.stability_peers]
        identities = [peer.prediction_artifact_identity for peer in self.stability_peers]
        if len(seeds) != len(set(seeds)) or len(identities) != len(set(identities)):
            raise ValueError("stability peer seeds and artifact identities must be distinct")

    @property
    def fingerprint(self) -> str:
        return _fingerprint(
            {
                "evaluator_fingerprint": self.evaluator_fingerprint,
                "split_fingerprint": self.split.fingerprint,
                "reference_edges": self.reference_edges,
                "reference_quadratic_forms": self.reference_quadratic_forms,
                "edge_score_edges": self.edge_score_edges,
                "edge_labels": self.edge_labels,
                "true_clusters": dict(self.true_clusters),
                "stability_peers": [
                    {
                        "seed": peer.seed,
                        "prediction_artifact_identity": peer.prediction_artifact_identity,
                        "predicted_clusters": dict(peer.predicted_clusters),
                    }
                    for peer in self.stability_peers
                ],
            }
        )


@dataclass(frozen=True, slots=True)
class DiscoveryExecutionOutcome:
    manifest: ResearchDatasetManifest
    method_id: str
    method_version: str
    model_role: str
    implementation_id: str
    selection_eligible: bool
    ablation_id: str | None
    claim_markers: tuple[str, ...]
    runtime_seconds: float
    peak_memory_bytes: int
    status: str
    prediction: DiscoveryPrediction | None
    reason: str | None
    execution_input_fingerprint: str


def execute_discovery_method(
    registry: BaselineRegistry,
    method_id: str,
    execution_input: DiscoveryExecutionInput,
    capability: DatasetCapability,
) -> DiscoveryExecutionOutcome:
    if not isinstance(registry, BaselineRegistry) or not isinstance(
        execution_input, DiscoveryExecutionInput
    ):
        raise ValueError("registry and execution_input must use Task 6 contracts")
    validate_dataset_identity(execution_input.manifest, capability)
    spec = registry.get(method_id)
    if spec.stage != "discovery":
        raise ValueError("method is not registered for Discovery execution")
    markers = tuple(
        sorted(
            set(execution_input.manifest.claim_markers)
            | set(capability.claim_markers)
            | ({execution_input.manifest.time_axis} if execution_input.manifest.time_axis == "static_placeholder_not_observed_time" else set())
        )
    )
    resolution = registry.resolve(method_id, capability=capability)
    common = {
        "manifest": execution_input.manifest,
        "method_id": spec.method_id,
        "method_version": spec.method_version,
        "model_role": spec.model_role,
        "implementation_id": spec.implementation_id,
        "selection_eligible": spec.selection_eligible,
        "ablation_id": spec.ablation_id,
        "claim_markers": markers,
        "execution_input_fingerprint": execution_input.fingerprint,
    }
    if resolution.status == "blocked":
        return DiscoveryExecutionOutcome(
            **common,
            runtime_seconds=0.0,
            peak_memory_bytes=0,
            status="blocked",
            prediction=None,
            reason=resolution.reason,
        )
    implementation = registry.implementation(method_id)
    if not isinstance(implementation, DiscoveryImplementation):
        raise ValueError("registered Discovery implementation type is invalid")
    tracemalloc.start()
    started = time.perf_counter()
    try:
        prediction = implementation.execute(execution_input)
        if not isinstance(prediction, DiscoveryPrediction):
            raise ValueError("Discovery implementation must return DiscoveryPrediction")
        runtime = time.perf_counter() - started
        _, peak = tracemalloc.get_traced_memory()
        return DiscoveryExecutionOutcome(
            **common,
            runtime_seconds=runtime,
            peak_memory_bytes=peak,
            status="success",
            prediction=prediction,
            reason=None,
        )
    except Exception as exc:
        runtime = time.perf_counter() - started
        _, peak = tracemalloc.get_traced_memory()
        return DiscoveryExecutionOutcome(
            **common,
            runtime_seconds=runtime,
            peak_memory_bytes=peak,
            status="failed",
            prediction=None,
            reason=f"{type(exc).__name__}: {exc}",
        )
    finally:
        tracemalloc.stop()


def evaluate_discovery_execution(
    execution: DiscoveryExecutionOutcome, evaluation: DiscoveryEvaluationInput
) -> ResultRow:
    if not isinstance(execution, DiscoveryExecutionOutcome) or not isinstance(
        evaluation, DiscoveryEvaluationInput
    ):
        raise ValueError("execution and evaluation must use Discovery port contracts")
    if execution.manifest.seed != evaluation.split.seed:
        raise ValueError("Discovery manifest and evaluation split seeds must match")
    audit = {
        "audit_version": "coordination-execution-audit/v2",
        "stage": "discovery",
        "implementation_id": execution.implementation_id,
        "execution_input_fingerprint": execution.execution_input_fingerprint,
        "evaluation_input_fingerprint": evaluation.fingerprint,
        "label_free_execution": True,
        "evaluation_after_execution": execution.status == "success",
        "fit_provenance_source": "not_applicable_label_free_discovery",
    }
    common = {
        "dataset_id": execution.manifest.dataset_id,
        "dataset_manifest_fingerprint": execution.manifest.fingerprint,
        "evaluator_fingerprint": evaluation.evaluator_fingerprint,
        "split_policy": evaluation.split.policy,
        "split_fingerprint": evaluation.split.fingerprint,
        "method_id": execution.method_id,
        "method_version": execution.method_version,
        "model_role": execution.model_role,
        "seed": evaluation.split.seed,
        "runtime_seconds": execution.runtime_seconds,
        "peak_memory_bytes": execution.peak_memory_bytes,
        "claim_markers": execution.claim_markers,
        "task": "discovery",
        "selection_eligible": execution.selection_eligible,
        "ablation_id": execution.ablation_id,
        "audit": audit,
    }
    if execution.status != "success":
        return ResultRow(
            **common, status=execution.status, reason=execution.reason, metrics={}
        )
    prediction = execution.prediction
    assert prediction is not None
    if any(
        peer.prediction_artifact_identity == prediction.artifact_identity
        for peer in evaluation.stability_peers
    ):
        raise ValueError("stability peer artifact identity must differ from current artifact")
    if any(
        dict(peer.predicted_clusters) == dict(prediction.predicted_clusters)
        for peer in evaluation.stability_peers
    ):
        raise ValueError("duplicate current assignments cannot masquerade as a stability peer")
    try:
        if prediction.edge_score_edges != evaluation.edge_score_edges:
            raise ValueError("Discovery prediction edge-score universe does not match evaluator")
        metrics = discovery_metrics(
            candidate_edges=prediction.candidate_edges,
            reference_edges=evaluation.reference_edges,
            reference_quadratic_forms=evaluation.reference_quadratic_forms,
            approximate_quadratic_forms=prediction.approximate_quadratic_forms,
            edge_labels=evaluation.edge_labels,
            edge_scores=prediction.edge_scores,
            true_clusters=evaluation.true_clusters,
            predicted_clusters=prediction.predicted_clusters,
        )
        metrics["cross_seed_stability"] = cross_seed_stability(
            (
                prediction.predicted_clusters,
                *(peer.predicted_clusters for peer in evaluation.stability_peers),
            )
        )
        audit["prediction_artifact_identity"] = prediction.artifact_identity
        audit["stability_peer_provenance"] = tuple(
            {
                "seed": peer.seed,
                "prediction_artifact_identity": peer.prediction_artifact_identity,
            }
            for peer in evaluation.stability_peers
        )
        return ResultRow(**common, status="success", metrics=metrics)
    except Exception as exc:
        return ResultRow(
            **common,
            status="failed",
            reason=f"{type(exc).__name__}: {exc}",
            metrics={},
        )


@dataclass(frozen=True, slots=True)
class DetectionInferenceCase:
    case_id: str
    cluster_id: str
    feature_schema_version: str
    feature_schema_fingerprint: str
    feature_names: tuple[str, ...]
    feature_values: tuple[float, ...]
    provenance: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for field_name in (
            "case_id",
            "cluster_id",
            "feature_schema_version",
            "feature_schema_fingerprint",
        ):
            object.__setattr__(self, field_name, _text(getattr(self, field_name), field_name))
        object.__setattr__(self, "feature_names", _text_tuple(self.feature_names, "feature_names"))
        if not isinstance(self.feature_values, Sequence) or isinstance(
            self.feature_values, (str, bytes)
        ):
            raise ValueError("feature_values must be a sequence")
        values_list: list[float] = []
        for value in self.feature_values:
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise ValueError("inference features must be numeric")
            normalized = float(value)
            if not math.isfinite(normalized):
                raise ValueError("inference features must be finite")
            values_list.append(normalized)
        values = tuple(values_list)
        if len(values) != len(self.feature_names):
            raise ValueError("feature values must align with feature names")
        object.__setattr__(self, "feature_values", values)
        if not isinstance(self.provenance, Mapping):
            raise ValueError("provenance must be a mapping")
        object.__setattr__(self, "provenance", _freeze_json(self.provenance, "provenance"))

    @classmethod
    def from_training_case(cls, case: DetectionTrainingCase) -> "DetectionInferenceCase":
        if not isinstance(case, DetectionTrainingCase):
            raise ValueError("case must be a DetectionTrainingCase")
        return cls(
            case_id=case.case_id,
            cluster_id=case.cluster_id,
            feature_schema_version=case.feature_schema_version,
            feature_schema_fingerprint=case.feature_schema_fingerprint,
            feature_names=case.feature_names,
            feature_values=case.feature_values,
            provenance=_json_value(case.provenance),
        )


@dataclass(frozen=True, slots=True)
class DetectionPartitions:
    train_cases: tuple[DetectionTrainingCase, ...]
    validation_cases: tuple[DetectionTrainingCase, ...]
    test_cases: tuple[DetectionInferenceCase, ...]

    def __post_init__(self) -> None:
        for field_name, split_name in (("train_cases", "train"), ("validation_cases", "validation")):
            values = getattr(self, field_name)
            if isinstance(values, (str, bytes)) or not isinstance(values, Sequence) or not values:
                raise ValueError(f"{field_name} must be a non-empty DetectionTrainingCase sequence")
            cases = tuple(values)
            if not all(isinstance(case, DetectionTrainingCase) for case in cases):
                raise ValueError(f"{field_name} must contain DetectionTrainingCase values")
            if any(case.split != split_name for case in cases):
                raise ValueError(f"{field_name} contains a case from another split")
            ids = [case.case_id for case in cases]
            if len(ids) != len(set(ids)):
                raise ValueError(f"{field_name} contains duplicate case IDs")
            object.__setattr__(self, field_name, cases)
        if isinstance(self.test_cases, (str, bytes)) or not isinstance(
            self.test_cases, Sequence
        ) or not self.test_cases:
            raise ValueError("test_cases must be a non-empty unlabeled inference sequence")
        test_cases = tuple(self.test_cases)
        if not all(type(case) is DetectionInferenceCase for case in test_cases):
            raise ValueError("test_cases must contain exact DetectionInferenceCase values")
        test_ids = [case.case_id for case in test_cases]
        if len(test_ids) != len(set(test_ids)):
            raise ValueError("test_cases contains duplicate case IDs")
        object.__setattr__(self, "test_cases", test_cases)
        partitions = [
            {case.case_id for case in self.train_cases},
            {case.case_id for case in self.validation_cases},
            {case.case_id for case in self.test_cases},
        ]
        if any(
            left & right
            for index, left in enumerate(partitions)
            for right in partitions[index + 1 :]
        ):
            raise ValueError("Detection partition case IDs must be pairwise disjoint")

    @property
    def train_fingerprint(self) -> str:
        return case_id_fingerprint(case.case_id for case in self.train_cases)

    @property
    def validation_fingerprint(self) -> str:
        return case_id_fingerprint(case.case_id for case in self.validation_cases)

    @property
    def test_fingerprint(self) -> str:
        return case_id_fingerprint(case.case_id for case in self.test_cases)


@dataclass(frozen=True, slots=True)
class DetectionTestInput:
    test_cases: tuple[DetectionInferenceCase, ...]

    def __post_init__(self) -> None:
        if isinstance(self.test_cases, (str, bytes)) or not isinstance(
            self.test_cases, Sequence
        ) or not self.test_cases:
            raise ValueError("test_cases must be a non-empty unlabeled inference sequence")
        cases = tuple(self.test_cases)
        if not all(type(case) is DetectionInferenceCase for case in cases):
            raise ValueError("test_cases must contain exact DetectionInferenceCase values")
        object.__setattr__(self, "test_cases", cases)


@dataclass(frozen=True, slots=True)
class DetectionEvaluationInput:
    evaluator_fingerprint: str
    test_labels: Mapping[str, int]

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "evaluator_fingerprint",
            _text(self.evaluator_fingerprint, "evaluator_fingerprint"),
        )
        if not isinstance(self.test_labels, Mapping) or not self.test_labels:
            raise ValueError("test_labels must be a non-empty sealed mapping")
        labels: dict[str, int] = {}
        for case_id, label in self.test_labels.items():
            normalized_id = _text(case_id, "test label case_id")
            if isinstance(label, bool) or label not in (0, 1):
                raise ValueError("sealed test labels must be 0 or 1")
            labels[normalized_id] = label
        if len(labels) != len(self.test_labels):
            raise ValueError("test_labels contain duplicate normalized case IDs")
        object.__setattr__(self, "test_labels", MappingProxyType(dict(sorted(labels.items()))))

    @property
    def fingerprint(self) -> str:
        return _fingerprint(
            {
                "evaluator_fingerprint": self.evaluator_fingerprint,
                "test_labels": dict(self.test_labels),
            }
        )


@dataclass(frozen=True, slots=True)
class DetectionPrediction:
    case_id: str
    harmful_probability: float
    decision: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "case_id", _text(self.case_id, "case_id"))
        probability = _non_negative_number(self.harmful_probability, "harmful_probability")
        if probability > 1.0:
            raise ValueError("harmful_probability must be within [0, 1]")
        object.__setattr__(self, "harmful_probability", probability)
        if self.decision not in {"benign_coordination", "harmful_coordination", "abstain"}:
            raise ValueError("Detection prediction decision is invalid")


@dataclass(frozen=True, slots=True)
class DetectionExecutionOutput:
    model_artifact: DetectionModelArtifact | None
    predictions: tuple[DetectionPrediction, ...]

    def __post_init__(self) -> None:
        if self.model_artifact is not None and not isinstance(
            self.model_artifact, DetectionModelArtifact
        ):
            raise ValueError("model_artifact must use the Stage 2 artifact contract")
        if isinstance(self.predictions, (str, bytes)) or not isinstance(
            self.predictions, Sequence
        ) or not self.predictions:
            raise ValueError("predictions must be a non-empty sequence")
        predictions = tuple(self.predictions)
        if not all(isinstance(value, DetectionPrediction) for value in predictions):
            raise ValueError("predictions must contain DetectionPrediction values")
        ids = [value.case_id for value in predictions]
        if len(ids) != len(set(ids)):
            raise ValueError("predictions contain duplicate case IDs")
        object.__setattr__(self, "predictions", predictions)


def _validate_detection_split(partitions: DetectionPartitions, split: ExperimentSplit) -> None:
    expected = {
        "train": set(split.train_ids),
        "validation": set(split.validation_ids),
        "test": set(split.test_ids),
    }
    actual = {
        "train": {case.case_id for case in partitions.train_cases},
        "validation": {case.case_id for case in partitions.validation_cases},
        "test": {case.case_id for case in partitions.test_cases},
    }
    for name in expected:
        if actual[name] != expected[name]:
            raise ValueError(f"Detection {name} partition does not match ExperimentSplit")


def _detection_row_common(
    spec: Any,
    manifest: ResearchDatasetManifest,
    capability: DatasetCapability,
    evaluator_fingerprint: str,
    split: ExperimentSplit,
    runtime: float,
    peak: int,
    audit: Mapping[str, Any],
    partitions: DetectionPartitions,
) -> dict[str, Any]:
    markers = set(manifest.claim_markers) | set(capability.claim_markers)
    if manifest.time_axis == "static_placeholder_not_observed_time":
        markers.add(manifest.time_axis)
    return {
        "dataset_id": manifest.dataset_id,
        "dataset_manifest_fingerprint": manifest.fingerprint,
        "evaluator_fingerprint": evaluator_fingerprint,
        "split_policy": split.policy,
        "split_fingerprint": split.fingerprint,
        "method_id": spec.method_id,
        "method_version": spec.method_version,
        "model_role": spec.model_role,
        "seed": split.seed,
        "runtime_seconds": runtime,
        "peak_memory_bytes": peak,
        "warning": spec.warning,
        "claim_markers": tuple(sorted(markers)),
        "task": "detection",
        "selection_eligible": spec.selection_eligible,
        "ablation_id": spec.ablation_id,
        "audit": audit,
        "train_partition_fingerprint": (
            None if spec.model_role == "heuristic_baseline" else partitions.train_fingerprint
        ),
        "validation_partition_fingerprint": (
            None if spec.model_role == "heuristic_baseline" else partitions.validation_fingerprint
        ),
        "test_partition_fingerprint": partitions.test_fingerprint,
    }


def run_detection_method(
    registry: BaselineRegistry,
    method_id: str,
    *,
    manifest: ResearchDatasetManifest,
    capability: DatasetCapability,
    split: ExperimentSplit,
    partitions: DetectionPartitions,
    evaluation: DetectionEvaluationInput,
) -> ResultRow:
    if not isinstance(registry, BaselineRegistry) or not isinstance(
        partitions, DetectionPartitions
    ):
        raise ValueError("registry and partitions must use Task 6 contracts")
    if not isinstance(evaluation, DetectionEvaluationInput):
        raise ValueError("evaluation must be a sealed DetectionEvaluationInput")
    validate_dataset_identity(manifest, capability)
    if manifest.seed != split.seed:
        raise ValueError("Detection manifest and split seeds must match")
    _validate_detection_split(partitions, split)
    if set(evaluation.test_labels) != {case.case_id for case in partitions.test_cases}:
        raise ValueError("sealed test labels must cover exactly the test partition")
    spec = registry.get(method_id)
    if spec.stage != "detection":
        raise ValueError("method is not registered for Detection execution")
    execution_audit = {
        "audit_version": "coordination-execution-audit/v2",
        "stage": "detection",
        "implementation_id": spec.implementation_id,
        "test_partition_fingerprint": partitions.test_fingerprint,
        "evaluation_input_fingerprint": evaluation.fingerprint,
        "evaluation_after_execution": False,
        "test_evaluation_only": True,
    }
    if spec.model_role != "heuristic_baseline":
        execution_audit.update(
            {
                "train_partition_fingerprint": partitions.train_fingerprint,
                "validation_partition_fingerprint": partitions.validation_fingerprint,
            }
        )
    resolution = registry.resolve(method_id, capability=capability)
    if resolution.status == "blocked":
        audit = {**execution_audit, "fit_provenance_source": "not_executed_blocked"}
        return ResultRow(
            **_detection_row_common(
                spec, manifest, capability, evaluation.fingerprint, split, 0.0, 0, audit,
                partitions,
            ),
            status="blocked",
            reason=resolution.reason,
            metrics={},
        )
    implementation = registry.implementation(method_id)
    tracemalloc.start()
    started = time.perf_counter()
    try:
        artifact: DetectionModelArtifact | None = None
        if spec.model_role == "heuristic_baseline":
            if not isinstance(implementation, HeuristicDetectionImplementation):
                raise ValueError("registered heuristic implementation type is invalid")
            output = implementation.execute(DetectionTestInput(partitions.test_cases))
        else:
            if not isinstance(implementation, LearnedDetectionImplementation):
                raise ValueError("registered learned implementation type is invalid")
            output = implementation.execute(partitions)
        if not isinstance(output, DetectionExecutionOutput):
            raise ValueError("Detection implementation must return DetectionExecutionOutput")
        if spec.model_role == "heuristic_baseline":
            if output.model_artifact is not None:
                raise ValueError("heuristic execution has no model fit path or learned artifact")
            audit = {
                **execution_audit,
                "fit_provenance_source": "none_heuristic_test_only",
            }
        else:
            artifact = output.model_artifact
            if artifact is None:
                raise ValueError("learned Detection execution requires a Stage 2 model artifact")
            expected_artifact_fingerprints = {
                "train_fit_case_ids_fingerprint": partitions.train_fingerprint,
                "validation_calibration_case_ids_fingerprint": partitions.validation_fingerprint,
                "validation_threshold_case_ids_fingerprint": partitions.validation_fingerprint,
                "validation_ood_case_ids_fingerprint": partitions.validation_fingerprint,
            }
            for field_name, expected in expected_artifact_fingerprints.items():
                if getattr(artifact, field_name) != expected:
                    raise ValueError(
                        f"Stage 2 artifact {field_name} does not match supplied partitions"
                    )
            audit = {
                **execution_audit,
                "fit_provenance_source": "stage2_model_artifact",
                "model_artifact_hash": artifact.artifact_hash,
                "model_artifact_version": artifact.model_version,
            }
        expected_test_ids = {case.case_id for case in partitions.test_cases}
        prediction_ids = {prediction.case_id for prediction in output.predictions}
        if prediction_ids != expected_test_ids:
            raise ValueError("Detection predictions must cover exactly the test partition")
        ordered = tuple(sorted(output.predictions, key=lambda value: value.case_id))
        metrics = detection_metrics(
            labels=tuple(evaluation.test_labels[value.case_id] for value in ordered),
            probabilities=tuple(value.harmful_probability for value in ordered),
            decisions=tuple(value.decision for value in ordered),
        )
        runtime = time.perf_counter() - started
        _, peak = tracemalloc.get_traced_memory()
        audit["evaluation_after_execution"] = True
        audit["prediction_fingerprint"] = _fingerprint(
            [
                {
                    "case_id": value.case_id,
                    "harmful_probability": value.harmful_probability,
                    "decision": value.decision,
                }
                for value in ordered
            ]
        )
        return ResultRow(
            **_detection_row_common(
                spec,
                manifest,
                capability,
                evaluation.fingerprint,
                split,
                runtime,
                peak,
                audit,
                partitions,
            ),
            status="success",
            metrics=metrics,
            model_artifact=None if artifact is None else artifact.to_dict(),
        )
    except Exception as exc:
        runtime = time.perf_counter() - started
        _, peak = tracemalloc.get_traced_memory()
        audit = {
            **execution_audit,
            "fit_provenance_source": "verification_failed",
            "verification_error_type": type(exc).__name__,
        }
        return ResultRow(
            **_detection_row_common(
                spec,
                manifest,
                capability,
                evaluation.fingerprint,
                split,
                runtime,
                peak,
                audit,
                partitions,
            ),
            status="failed",
            reason=f"{type(exc).__name__}: {exc}",
            metrics={},
        )
    finally:
        tracemalloc.stop()


def select_learned_artifact(
    rows: Sequence[ResultRow], registry: BaselineRegistry
) -> ResultRow:
    if not isinstance(registry, BaselineRegistry):
        raise ValueError("selection requires the registry that owns method eligibility")
    candidates: list[ResultRow] = []
    for row in rows:
        spec = registry.get(row.method_id)
        if (
            row.method_version != spec.method_version
            or row.model_role != spec.model_role
            or row.selection_eligible != spec.selection_eligible
            or row.ablation_id != spec.ablation_id
        ):
            raise ValueError("result row identity does not match its registered method spec")
        if row.status == "success" and spec.selection_eligible:
            candidates.append(row)
    if len(candidates) != 1:
        raise ValueError("learned artifact selection requires exactly one eligible fused result")
    return candidates[0]


@dataclass(frozen=True, slots=True)
class ArtifactPaths:
    per_seed_json: Path
    per_seed_csv: Path
    aggregates_json: Path
    aggregates_csv: Path
    claim_gates_json: Path
    artifact_identity: str


def _write_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def _write_csv(path: Path, rows: Sequence[Mapping[str, Any]], fieldnames: Sequence[str]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    name: json.dumps(
                        row[name],
                        ensure_ascii=False,
                        sort_keys=True,
                        separators=(",", ":"),
                    )
                    if isinstance(row.get(name), (dict, list))
                    else row.get(name)
                    for name in fieldnames
                }
            )


def write_reproduction_artifacts(
    rows: Sequence[ResultRow],
    output_dir: str | Path,
    *,
    claim_gates: Sequence[ClaimGate] = (),
    bootstrap_seed: int = 0,
    bootstrap_resamples: int = 2_000,
) -> ArtifactPaths:
    normalized_rows = tuple(
        sorted(
            rows,
            key=lambda row: (
                row.dataset_id,
                row.method_id,
                row.method_version,
                row.seed,
                row.artifact_identity,
            ),
        )
    )
    if not normalized_rows:
        raise ValueError("at least one result row is required")
    if len({row.artifact_identity for row in normalized_rows}) != len(normalized_rows):
        raise ValueError("result rows contain duplicate artifact identities")
    aggregates = aggregate_result_rows(
        normalized_rows,
        bootstrap_seed=bootstrap_seed,
        bootstrap_resamples=bootstrap_resamples,
    )
    gate_results = tuple(evaluate_claim_gate(gate, normalized_rows) for gate in claim_gates)
    rows_payload = {
        "schema_version": "cogguard.coordination-reproduction-rows/v2",
        "rows": [row.to_dict() for row in normalized_rows],
    }
    aggregates_payload = {
        "schema_version": "cogguard.coordination-reproduction-aggregates/v2",
        "bootstrap": {
            "seed": bootstrap_seed,
            "resamples": bootstrap_resamples,
            "confidence": 0.95,
        },
        "aggregates": [aggregate.to_dict() for aggregate in aggregates],
    }
    gates_payload = {
        "schema_version": "cogguard.coordination-reproduction-claim-gates/v2",
        "claim_gates": [result.to_dict() for result in gate_results],
    }
    identity = _fingerprint(
        {"rows": rows_payload, "aggregates": aggregates_payload, "claim_gates": gates_payload}
    )
    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    per_seed_json = destination / "per_seed_rows.json"
    per_seed_csv = destination / "per_seed_rows.csv"
    aggregates_json = destination / "aggregates.json"
    aggregates_csv = destination / "aggregates.csv"
    claim_gates_json = destination / "claim_gates.json"
    _write_json(per_seed_json, rows_payload)
    _write_json(aggregates_json, aggregates_payload)
    _write_json(claim_gates_json, gates_payload)
    row_dicts = [row.to_dict() for row in normalized_rows]
    _write_csv(per_seed_csv, row_dicts, tuple(row_dicts[0]))
    aggregate_dicts = [aggregate.to_dict() for aggregate in aggregates]
    aggregate_fields = tuple(aggregate_dicts[0]) if aggregate_dicts else (
        "task",
        "dataset_id",
        "split_policy",
        "method_id",
        "method_version",
        "model_role",
        "ablation_id",
        "metric_name",
        "direction",
        "successful_seed_count",
        "seeds",
        "mean",
        "std",
        "ci_low",
        "ci_high",
        "dataset_manifest_fingerprints",
        "evaluator_fingerprints",
        "split_fingerprints",
        "observed_artifact_identities",
    )
    _write_csv(aggregates_csv, aggregate_dicts, aggregate_fields)
    return ArtifactPaths(
        per_seed_json,
        per_seed_csv,
        aggregates_json,
        aggregates_csv,
        claim_gates_json,
        identity,
    )


__all__ = [
    "AggregateResult",
    "ArtifactPaths",
    "ClaimGate",
    "ClaimGateResult",
    "DetectionEvaluationInput",
    "DetectionExecutionOutput",
    "DetectionInferenceCase",
    "DetectionPartitions",
    "DetectionPrediction",
    "DetectionTestInput",
    "DiscoveryEvaluationInput",
    "DiscoveryExecutionInput",
    "DiscoveryExecutionOutcome",
    "DiscoveryPrediction",
    "DiscoveryStabilityPeer",
    "ResultRow",
    "aggregate_result_rows",
    "evaluate_claim_gate",
    "evaluate_discovery_execution",
    "execute_discovery_method",
    "run_detection_method",
    "select_learned_artifact",
    "validate_dataset_identity",
    "write_reproduction_artifacts",
]
