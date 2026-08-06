from __future__ import annotations

import csv
import hashlib
import json
import math
import time
import tracemalloc
from collections import defaultdict
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from types import MappingProxyType
from typing import Any

import numpy as np

from .baselines import BaselineRegistry, HEURISTIC_BASELINE_ID, HEURISTIC_BASELINE_WARNING
from .metrics import bootstrap_confidence_interval, metric_direction
from .protocol import DatasetCapability, ExperimentSplit, ResearchDatasetManifest


_STATUSES = {"success", "failed", "blocked"}
_GATE_STATUSES = {"supported", "not_supported", "blocked"}


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


@dataclass(frozen=True, slots=True)
class FitAudit:
    transform_fit_ids: tuple[str, ...] = ()
    model_fit_ids: tuple[str, ...] = ()
    calibration_fit_ids: tuple[str, ...] = ()
    threshold_fit_ids: tuple[str, ...] = ()
    ood_fit_ids: tuple[str, ...] = ()
    prediction_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for field_name in (
            "transform_fit_ids", "model_fit_ids", "calibration_fit_ids",
            "threshold_fit_ids", "ood_fit_ids", "prediction_ids",
        ):
            object.__setattr__(self, field_name, _text_tuple(getattr(self, field_name), field_name))

    def to_dict(self) -> dict[str, list[str]]:
        return {
            field_name: list(getattr(self, field_name))
            for field_name in (
                "transform_fit_ids", "model_fit_ids", "calibration_fit_ids",
                "threshold_fit_ids", "ood_fit_ids", "prediction_ids",
            )
        }


def validate_fit_isolation(split: ExperimentSplit, audit: FitAudit, *, model_role: str) -> None:
    if not isinstance(split, ExperimentSplit) or not isinstance(audit, FitAudit):
        raise ValueError("split and audit must use the experiment contracts")
    role = _text(model_role, "model_role")
    fit_fields = (
        "transform_fit_ids", "model_fit_ids", "calibration_fit_ids", "threshold_fit_ids", "ood_fit_ids"
    )
    if role == "heuristic_baseline":
        if any(getattr(audit, field_name) for field_name in fit_fields):
            raise ValueError("heuristic_baseline must not fit transforms, parameters, thresholds, or bounds")
        if audit.prediction_ids != split.test_ids:
            raise ValueError("heuristic_baseline prediction_ids must equal test IDs exactly")
        return
    expected = {
        "transform_fit_ids": split.train_ids,
        "model_fit_ids": split.train_ids,
        "calibration_fit_ids": split.validation_ids,
        "threshold_fit_ids": split.validation_ids,
        "ood_fit_ids": split.validation_ids,
        "prediction_ids": split.test_ids,
    }
    for field_name, expected_ids in expected.items():
        if getattr(audit, field_name) != expected_ids:
            raise ValueError(f"{field_name} must equal its isolated split IDs exactly")


@dataclass(frozen=True, slots=True)
class RunObservation:
    metrics: Mapping[str, float]
    fit_audit: FitAudit | None = None


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

    def __post_init__(self) -> None:
        for field_name in (
            "dataset_id", "dataset_manifest_fingerprint", "evaluator_fingerprint",
            "split_policy", "split_fingerprint", "method_id", "method_version", "model_role",
        ):
            object.__setattr__(self, field_name, _text(getattr(self, field_name), field_name))
        if isinstance(self.seed, bool) or not isinstance(self.seed, int) or self.seed < 0:
            raise ValueError("seed must be a non-negative integer")
        object.__setattr__(self, "runtime_seconds", _non_negative_number(self.runtime_seconds, "runtime_seconds"))
        memory = _non_negative_number(self.peak_memory_bytes, "peak_memory_bytes")
        if not memory.is_integer():
            raise ValueError("peak_memory_bytes must be an integer")
        object.__setattr__(self, "peak_memory_bytes", int(memory))
        if self.status not in _STATUSES:
            raise ValueError("status must be success, failed, or blocked")
        if not isinstance(self.metrics, Mapping):
            raise ValueError("metrics must be a mapping")
        normalized_metrics: dict[str, float] = {}
        for name, value in self.metrics.items():
            metric_name = _text(name, "metric name")
            metric_direction(metric_name)
            normalized_metrics[metric_name] = _metric_number(value, metric_name)
        object.__setattr__(self, "metrics", MappingProxyType(dict(sorted(normalized_metrics.items()))))
        object.__setattr__(self, "reason", _optional_text(self.reason, "reason"))
        object.__setattr__(self, "warning", _optional_text(self.warning, "warning"))
        object.__setattr__(self, "claim_markers", tuple(sorted(_text_tuple(self.claim_markers, "claim_markers"))))
        if self.status == "success":
            if not self.metrics or self.reason is not None:
                raise ValueError("successful rows require metrics and cannot have a reason")
        elif self.metrics or self.reason is None:
            raise ValueError("failed and blocked rows require a reason and cannot contain metrics")
        if self.model_role == "heuristic_baseline":
            if (
                self.method_id != HEURISTIC_BASELINE_ID
                or self.method_version != HEURISTIC_BASELINE_ID
                or self.warning != HEURISTIC_BASELINE_WARNING
            ):
                raise ValueError("heuristic baseline rows require fixed identity and warning")

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
        }

    @property
    def artifact_identity(self) -> str:
        return _fingerprint(self._identity_payload())

    def to_dict(self) -> dict[str, Any]:
        payload = self._identity_payload()
        payload["artifact_identity"] = self.artifact_identity
        return payload


@dataclass(frozen=True, slots=True)
class AggregateResult:
    dataset_id: str
    split_policy: str
    method_id: str
    method_version: str
    model_role: str
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
            "dataset_id": self.dataset_id,
            "split_policy": self.split_policy,
            "method_id": self.method_id,
            "method_version": self.method_version,
            "model_role": self.model_role,
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


def aggregate_result_rows(
    rows: Sequence[ResultRow], *, bootstrap_seed: int = 0, bootstrap_resamples: int = 2_000
) -> tuple[AggregateResult, ...]:
    if not isinstance(rows, Sequence) or not all(isinstance(row, ResultRow) for row in rows):
        raise ValueError("rows must contain ResultRow values")
    groups: dict[tuple[str, ...], list[tuple[ResultRow, float]]] = defaultdict(list)
    for row in rows:
        if row.status != "success":
            continue
        values = {**row.metrics, "runtime_seconds": row.runtime_seconds, "peak_memory_bytes": float(row.peak_memory_bytes)}
        for metric_name, value in values.items():
            key = (
                row.dataset_id, row.split_policy, row.method_id, row.method_version,
                row.model_role, metric_name,
            )
            groups[key].append((row, value))
    aggregates: list[AggregateResult] = []
    for key, observations in sorted(groups.items()):
        observations.sort(key=lambda item: (item[0].seed, item[0].artifact_identity))
        values = tuple(value for _, value in observations)
        low, high = bootstrap_confidence_interval(
            values, seed=bootstrap_seed, resamples=bootstrap_resamples
        )
        aggregates.append(
            AggregateResult(
                dataset_id=key[0], split_policy=key[1], method_id=key[2],
                method_version=key[3], model_role=key[4], metric_name=key[5],
                direction=metric_direction(key[5]), successful_seed_count=len(observations),
                seeds=tuple(row.seed for row, _ in observations),
                mean=float(np.mean(values)), std=float(np.std(values, ddof=0)),
                ci_low=low, ci_high=high,
                dataset_manifest_fingerprints=tuple(sorted({row.dataset_manifest_fingerprint for row, _ in observations})),
                evaluator_fingerprints=tuple(sorted({row.evaluator_fingerprint for row, _ in observations})),
                split_fingerprints=tuple(sorted({row.split_fingerprint for row, _ in observations})),
                observed_artifact_identities=tuple(row.artifact_identity for row, _ in observations),
            )
        )
    return tuple(aggregates)


@dataclass(frozen=True, slots=True)
class ClaimGate:
    gate_id: str
    metric_name: str
    direction: str
    threshold: float
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
        if (
            isinstance(self.minimum_successful_seeds, bool)
            or not isinstance(self.minimum_successful_seeds, int)
            or self.minimum_successful_seeds <= 0
        ):
            raise ValueError("minimum_successful_seeds must be a positive integer")
        for field_name in ("dataset_id", "method_id", "required_split_policy"):
            object.__setattr__(self, field_name, _optional_text(getattr(self, field_name), field_name))
        object.__setattr__(
            self, "forbidden_claim_markers",
            tuple(sorted(_text_tuple(self.forbidden_claim_markers, "forbidden_claim_markers"))),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "gate_id": self.gate_id,
            "metric_name": self.metric_name,
            "direction": self.direction,
            "threshold": self.threshold,
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
    reason: str | None = None
    gate_definition: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.status not in _GATE_STATUSES:
            raise ValueError("claim gate result status is invalid")
        if not isinstance(self.gate_definition, Mapping) or not self.gate_definition:
            raise ValueError("claim gate result requires its serialized gate definition")
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


def evaluate_claim_gate(gate: ClaimGate, rows: Sequence[ResultRow]) -> ClaimGateResult:
    if not isinstance(gate, ClaimGate) or not all(isinstance(row, ResultRow) for row in rows):
        raise ValueError("gate and rows must use Task 6 contracts")
    scoped = [
        row for row in rows
        if (gate.dataset_id is None or row.dataset_id == gate.dataset_id)
        and (gate.method_id is None or row.method_id == gate.method_id)
    ]
    forbidden = sorted({marker for row in scoped for marker in row.claim_markers if marker in gate.forbidden_claim_markers})
    if forbidden:
        return ClaimGateResult(
            gate.gate_id, gate.metric_name, gate.direction, gate.threshold, "blocked", None, 0, (),
            f"forbidden claim markers observed: {', '.join(forbidden)}",
            gate.to_dict(),
        )
    if gate.required_split_policy is not None:
        matching_policy = [row for row in scoped if row.split_policy == gate.required_split_policy]
        if not matching_policy:
            return ClaimGateResult(
                gate.gate_id, gate.metric_name, gate.direction, gate.threshold, "blocked", None, 0, (),
                f"required split policy {gate.required_split_policy} has no observed rows",
                gate.to_dict(),
            )
        scoped = matching_policy
    def has_metric(row: ResultRow) -> bool:
        return gate.metric_name in row.metrics or gate.metric_name in {"runtime_seconds", "peak_memory_bytes"}

    def observed_value(row: ResultRow) -> float:
        if gate.metric_name == "runtime_seconds":
            return row.runtime_seconds
        if gate.metric_name == "peak_memory_bytes":
            return float(row.peak_memory_bytes)
        return row.metrics[gate.metric_name]

    observed = sorted(
        (row for row in scoped if row.status == "success" and has_metric(row)),
        key=lambda row: (row.seed, row.artifact_identity),
    )
    if len(observed) < gate.minimum_successful_seeds:
        return ClaimGateResult(
            gate.gate_id, gate.metric_name, gate.direction, gate.threshold, "blocked", None,
            len(observed), tuple(row.artifact_identity for row in observed),
            f"requires {gate.minimum_successful_seeds} successful observed seeds; found {len(observed)}",
            gate.to_dict(),
        )
    value = float(np.mean([observed_value(row) for row in observed]))
    supported = value >= gate.threshold if gate.direction == "maximize" else value <= gate.threshold
    return ClaimGateResult(
        gate.gate_id, gate.metric_name, gate.direction, gate.threshold,
        "supported" if supported else "not_supported", value, len(observed),
        tuple(sorted(row.artifact_identity for row in observed)), None,
        gate.to_dict(),
    )


@dataclass(frozen=True, slots=True)
class RunContext:
    manifest: ResearchDatasetManifest
    evaluator_fingerprint: str
    split: ExperimentSplit
    capability: DatasetCapability

    def __post_init__(self) -> None:
        if not isinstance(self.manifest, ResearchDatasetManifest):
            raise ValueError("manifest must be a ResearchDatasetManifest")
        if not isinstance(self.split, ExperimentSplit) or not isinstance(self.capability, DatasetCapability):
            raise ValueError("split and capability must use Task 5 contracts")
        object.__setattr__(self, "evaluator_fingerprint", _text(self.evaluator_fingerprint, "evaluator_fingerprint"))
        if self.manifest.dataset_id != self.capability.dataset_id:
            raise ValueError("manifest and capability dataset IDs must match")
        if self.manifest.seed != self.split.seed:
            raise ValueError("manifest and split seeds must match")


def run_registered_method(
    registry: BaselineRegistry,
    method_id: str,
    context: RunContext,
    execute: Callable[[RunContext], RunObservation | Mapping[str, float]],
) -> ResultRow:
    if not isinstance(registry, BaselineRegistry) or not isinstance(context, RunContext):
        raise ValueError("registry and context must use Task 6 contracts")
    resolution = registry.resolve(method_id, capability=context.capability)
    spec = resolution.spec
    common = {
        "dataset_id": context.manifest.dataset_id,
        "dataset_manifest_fingerprint": context.manifest.fingerprint,
        "evaluator_fingerprint": context.evaluator_fingerprint,
        "split_policy": context.split.policy,
        "split_fingerprint": context.split.fingerprint,
        "method_id": spec.method_id,
        "method_version": spec.method_version,
        "model_role": spec.model_role,
        "seed": context.split.seed,
        "warning": spec.warning,
        "claim_markers": tuple(sorted(set(context.manifest.claim_markers) | set(context.capability.claim_markers))),
    }
    if resolution.status == "blocked":
        return ResultRow(**common, runtime_seconds=0.0, peak_memory_bytes=0, status="blocked", reason=resolution.reason)
    tracemalloc.start()
    started = time.perf_counter()
    try:
        produced = execute(context)
        observation = produced if isinstance(produced, RunObservation) else RunObservation(metrics=produced)
        if spec.stage == "detection":
            if observation.fit_audit is None:
                raise ValueError("detection methods require an explicit FitAudit")
            validate_fit_isolation(context.split, observation.fit_audit, model_role=spec.model_role)
        runtime = time.perf_counter() - started
        _, peak = tracemalloc.get_traced_memory()
        return ResultRow(
            **common, runtime_seconds=runtime, peak_memory_bytes=peak,
            status="success", metrics=observation.metrics,
        )
    except Exception as exc:  # Experiment failures are data, not missing artifact rows.
        runtime = time.perf_counter() - started
        _, peak = tracemalloc.get_traced_memory()
        return ResultRow(
            **common, runtime_seconds=runtime, peak_memory_bytes=peak,
            status="failed", reason=f"{type(exc).__name__}: {exc}",
        )
    finally:
        tracemalloc.stop()


def select_learned_artifact(rows: Sequence[ResultRow]) -> ResultRow:
    candidates = sorted(
        (
            row for row in rows
            if row.status == "success" and row.model_role == "primary_learned"
            and row.method_id != HEURISTIC_BASELINE_ID
        ),
        key=lambda row: (row.method_id, row.method_version, row.seed, row.artifact_identity),
    )
    if len(candidates) != 1:
        raise ValueError("learned artifact selection requires exactly one successful learned candidate")
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
            writer.writerow({
                name: json.dumps(row[name], ensure_ascii=False, sort_keys=True, separators=(",", ":"))
                if isinstance(row.get(name), (dict, list)) else row.get(name)
                for name in fieldnames
            })


def write_reproduction_artifacts(
    rows: Sequence[ResultRow],
    output_dir: str | Path,
    *,
    claim_gates: Sequence[ClaimGate] = (),
    bootstrap_seed: int = 0,
    bootstrap_resamples: int = 2_000,
) -> ArtifactPaths:
    normalized_rows = tuple(sorted(rows, key=lambda row: (
        row.dataset_id, row.method_id, row.method_version, row.seed, row.artifact_identity
    )))
    if not normalized_rows:
        raise ValueError("at least one result row is required")
    if len({row.artifact_identity for row in normalized_rows}) != len(normalized_rows):
        raise ValueError("result rows contain duplicate artifact identities")
    aggregates = aggregate_result_rows(
        normalized_rows, bootstrap_seed=bootstrap_seed, bootstrap_resamples=bootstrap_resamples
    )
    gate_results = tuple(evaluate_claim_gate(gate, normalized_rows) for gate in claim_gates)
    rows_payload = {"schema_version": "cogguard.coordination-reproduction-rows/v1", "rows": [row.to_dict() for row in normalized_rows]}
    aggregates_payload = {
        "schema_version": "cogguard.coordination-reproduction-aggregates/v1",
        "bootstrap": {"seed": bootstrap_seed, "resamples": bootstrap_resamples, "confidence": 0.95},
        "aggregates": [aggregate.to_dict() for aggregate in aggregates],
    }
    gates_payload = {
        "schema_version": "cogguard.coordination-reproduction-claim-gates/v1",
        "claim_gates": [result.to_dict() for result in gate_results],
    }
    identity = _fingerprint({"rows": rows_payload, "aggregates": aggregates_payload, "claim_gates": gates_payload})
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
        "dataset_id", "split_policy", "method_id", "method_version", "model_role",
        "metric_name", "direction", "successful_seed_count", "seeds", "mean", "std",
        "ci_low", "ci_high", "dataset_manifest_fingerprints", "evaluator_fingerprints",
        "split_fingerprints", "observed_artifact_identities",
    )
    _write_csv(aggregates_csv, aggregate_dicts, aggregate_fields)
    return ArtifactPaths(
        per_seed_json, per_seed_csv, aggregates_json, aggregates_csv, claim_gates_json, identity
    )


__all__ = [
    "AggregateResult", "ArtifactPaths", "ClaimGate", "ClaimGateResult", "FitAudit",
    "ResultRow", "RunContext", "RunObservation", "aggregate_result_rows",
    "evaluate_claim_gate", "run_registered_method", "select_learned_artifact",
    "validate_fit_isolation", "write_reproduction_artifacts",
]
