from __future__ import annotations

import csv
import dataclasses
import gc
import hashlib
import importlib.metadata
import io
import json
import os
import platform
import sys
from collections import Counter, defaultdict
from collections.abc import Mapping as MappingABC, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

import numpy as np

from .compact_discovery_methods import (
    CompactDiscoveryMethodConfig,
    CompactDiscoveryRegistry,
    default_compact_discovery_registry,
)
from .compact_execution import (
    CompactDiscoveryExecutionInput,
    IOHunterExternalEvaluationInput,
    evaluate_iohunter_external_account_recovery,
    execute_compact_discovery_method,
)
from .iohunter_compact import (
    compact_fold_fingerprint,
    load_compact_iohunter_discovery,
    load_compact_iohunter_evaluator_result,
)
from .matrix_protocol import CANONICAL_IOHUNTER_PROCESSED_ROOT
from .metrics import bootstrap_confidence_interval
from .runner import CANONICAL_REPRODUCTION_OUTPUT_ROOT


IOHUNTER_COMPACT_CAMPAIGNS = ("china", "cuba", "iran", "russia", "UAE", "venezuela")
IOHUNTER_COMPACT_SEEDS = (42, 43, 44, 45, 46)
IOHUNTER_COMPACT_METHODS = (
    "tsgs_mhcr_compact",
    "edgebank",
    "dense_cosine_leiden",
    "no_tsgs",
    "no_mhcr",
    "no_relation_specific",
)
IOHUNTER_COMPACT_MATRIX_SCHEMA_VERSION = "cogguard.iohunter-compact-matrix/v1"
IOHUNTER_COMPACT_ROW_SCHEMA_VERSION = "cogguard.iohunter-compact-matrix-row/v1"
IOHUNTER_COMPACT_AGGREGATE_SCHEMA_VERSION = "cogguard.iohunter-compact-aggregates/v1"
IOHUNTER_COMPACT_CLAIM_SCHEMA_VERSION = "cogguard.iohunter-compact-claims/v1"
IOHUNTER_COMPACT_IMPLEMENTATION_VERSION = "task-7c-compact-matrix-v1"
IOHUNTER_COMPACT_METHOD_CONFIG_VERSION = "compact-discovery-method-config/v1"
IOHUNTER_EXTERNAL_EVALUATION_SCOPE = "external_account_recovery_not_coordination_ground_truth"
_EVALUATION_CONFIG = {"threshold_objective": "macro_f1"}
_CLAIMABLE_PROXY_METRICS = frozenset(
    {
        "external_account_auprc",
        "external_account_macro_f1",
        "external_account_recall_at_k",
        "external_account_roc_auc",
    }
)
_REQUIRED_PROXY_PAIRS = frozenset(
    (campaign, seed)
    for campaign in IOHUNTER_COMPACT_CAMPAIGNS
    for seed in IOHUNTER_COMPACT_SEEDS
)


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _fingerprint(value: Any) -> str:
    return "sha256:" + hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _file_checksum(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()


def _atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(text, encoding="utf-8", newline="")
    os.replace(temporary, path)


def _atomic_write_json(path: Path, value: Any) -> None:
    _atomic_write_text(
        path,
        json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n",
    )


def validate_compact_matrix_output_dir(output_dir: str | Path) -> Path:
    if not isinstance(output_dir, (str, Path)):
        raise ValueError("output_dir must be a filesystem path under the canonical G-drive reproduction output root")
    candidate = Path(output_dir)
    if not candidate.is_absolute() or any(part == ".." for part in candidate.parts):
        raise ValueError("output_dir must be absolute under the canonical G-drive reproduction output root")
    try:
        resolved = candidate.resolve(strict=False)
        root = CANONICAL_REPRODUCTION_OUTPUT_ROOT.resolve(strict=False)
        if resolved.drive.upper() != "G:" or root.drive.upper() != "G:":
            raise ValueError
        resolved.relative_to(root)
    except (OSError, ValueError) as exc:
        raise ValueError(
            "output_dir must resolve under the canonical G-drive reproduction output root"
        ) from exc
    if resolved == root:
        raise ValueError("output_dir must be a descendant of the canonical G-drive reproduction output root")
    return resolved


@dataclass(frozen=True, order=True, slots=True)
class CompactMatrixCoordinate:
    campaign: str
    seed: int
    fold_id: str
    method_id: str


@dataclass(frozen=True, slots=True)
class CompactIOHunterMatrixResult:
    output_dir: str
    rows: tuple[Mapping[str, Any], ...]
    status_counts: Mapping[str, int]
    resume_counts: Mapping[str, int]
    manifest_fingerprint: str

    def summary(self) -> dict[str, Any]:
        return {
            "manifest_fingerprint": self.manifest_fingerprint,
            "output": self.output_dir,
            "resume_counts": dict(self.resume_counts),
            "row_count": len(self.rows),
            "status_counts": dict(self.status_counts),
        }


def _canonical_subset(values: Sequence[Any] | None, canonical: tuple[Any, ...], field_name: str) -> tuple[Any, ...]:
    if values is None:
        return canonical
    if isinstance(values, (str, bytes)):
        values = (values,)
    requested = tuple(values)
    unknown = set(requested) - set(canonical)
    if not requested or unknown or len(set(requested)) != len(requested):
        raise ValueError(f"{field_name} must be a unique non-empty subset of {canonical}; unknown={sorted(unknown, key=str)}")
    return tuple(value for value in canonical if value in requested)


def compact_iohunter_matrix_coordinates(
    *,
    campaigns: Sequence[str] | None = None,
    seeds: Sequence[int] | None = None,
    methods: Sequence[str] | None = None,
) -> tuple[CompactMatrixCoordinate, ...]:
    selected_campaigns = _canonical_subset(campaigns, IOHUNTER_COMPACT_CAMPAIGNS, "campaigns")
    selected_seeds = _canonical_subset(seeds, IOHUNTER_COMPACT_SEEDS, "seeds")
    selected_methods = _canonical_subset(methods, IOHUNTER_COMPACT_METHODS, "methods")
    fold_by_seed = dict(zip(IOHUNTER_COMPACT_SEEDS, (f"fold-{index:03d}" for index in range(5)), strict=True))
    return tuple(
        CompactMatrixCoordinate(campaign, seed, fold_by_seed[seed], method)
        for campaign in selected_campaigns
        for seed in selected_seeds
        for method in selected_methods
    )


def _method_configs(
    registry: CompactDiscoveryRegistry,
    methods: Sequence[str],
    overrides: Mapping[str, Mapping[str, Any]] | None,
) -> dict[str, dict[str, Any]]:
    if overrides is None:
        overrides = {}
    if not isinstance(overrides, MappingABC) or set(overrides) - set(methods):
        raise ValueError("method_config_overrides must target only selected compact methods")
    config_fields = {field.name for field in dataclasses.fields(CompactDiscoveryMethodConfig)}
    allowed = config_fields - {"method_variant"}
    result: dict[str, dict[str, Any]] = {}
    for method_id in methods:
        implementation = registry.implementation(method_id)
        base = dataclasses.asdict(implementation.config)
        method_overrides = overrides.get(method_id, {})
        if not isinstance(method_overrides, MappingABC):
            raise ValueError(f"method_config_overrides[{method_id}] must be a mapping")
        unknown = set(method_overrides) - allowed
        if unknown:
            raise ValueError(f"unsafe compact method config fields for {method_id}: {sorted(unknown)}")
        effective = {**base, **dict(method_overrides)}
        validated = CompactDiscoveryMethodConfig(**effective)
        result[method_id] = dataclasses.asdict(validated)
    return result


def _row_path(output_dir: Path, coordinate: CompactMatrixCoordinate) -> Path:
    path = (
        output_dir
        / "runs"
        / coordinate.campaign
        / coordinate.fold_id
        / str(coordinate.seed)
        / f"{coordinate.method_id}.json"
    ).resolve(strict=False)
    path.relative_to(output_dir)
    return path


def _plain_compact(value: Any, *, depth: int = 0) -> Any:
    if depth > 8:
        return "summary_depth_limit"
    if isinstance(value, MappingABC):
        return {str(key): _plain_compact(item, depth=depth + 1) for key, item in sorted(value.items())}
    if isinstance(value, (tuple, list)):
        return [_plain_compact(item, depth=depth + 1) for item in value[:64]]
    if isinstance(value, np.generic):
        return value.item()
    if value is None or isinstance(value, (str, bool, int, float)):
        return value
    if isinstance(value, np.ndarray):
        return {"array_omitted": True, "dtype": str(value.dtype), "shape": list(value.shape)}
    return str(value)


def _row_checksum(row: Mapping[str, Any]) -> str:
    return _fingerprint({key: value for key, value in row.items() if key != "row_checksum"})


def _row_identity_checksum(row: Mapping[str, Any]) -> str:
    dynamic_fields = {
        "row_checksum",
        "row_path",
        "runtime_seconds",
        "peak_memory_bytes",
        "diagnostics_summary",
        "memory_profile",
    }
    return _fingerprint(
        {key: value for key, value in row.items() if key not in dynamic_fields}
    )


def _manifest_identity(manifest: Mapping[str, Any]) -> dict[str, Any]:
    sources = manifest.get("campaign_source_fingerprints", {})
    stable_sources = {
        campaign: {
            key: value
            for key, value in source.items()
            if key != "memory_profile"
        }
        for campaign, source in sources.items()
    }
    stable_rows = [
        {
            "run_identity": row["run_identity"],
            "row_path": row["row_path"],
            "row_identity_checksum": row["row_identity_checksum"],
            "status": row["status"],
        }
        for row in manifest.get("rows", ())
    ]
    return {
        key: value
        for key, value in manifest.items()
        if key not in {"manifest_fingerprint", "campaign_source_fingerprints", "rows", "derived_artifacts"}
    } | {
        "campaign_source_fingerprints": stable_sources,
        "rows": stable_rows,
        "derived_artifacts": {
            key: {"path": value["path"]}
            for key, value in manifest.get("derived_artifacts", {}).items()
        },
    }


def _prior_row_checksums(output_dir: Path) -> dict[str, str]:
    path = output_dir / "matrix_manifest.json"
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if manifest.get("schema_version") != IOHUNTER_COMPACT_MATRIX_SCHEMA_VERSION:
        return {}
    return {
        str(item["row_path"]): str(item["file_checksum"])
        for item in manifest.get("rows", ())
        if isinstance(item, MappingABC) and "row_path" in item and "file_checksum" in item
    }


def _resume_candidate(
    path: Path,
    *,
    prior_file_checksum: str | None,
    coordinate: CompactMatrixCoordinate,
    implementation: Any,
    source_layer_fingerprint: str,
    source_sha256: str,
    execution_input_fingerprint: str,
    method_config: Mapping[str, Any],
) -> dict[str, Any] | None:
    if prior_file_checksum is None or not path.is_file():
        return None
    try:
        if _file_checksum(path) != prior_file_checksum:
            return None
        row = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    expected_coordinate = dataclasses.asdict(coordinate)
    if (
        row.get("schema_version") != IOHUNTER_COMPACT_ROW_SCHEMA_VERSION
        or row.get("completion_status") != "complete"
        or row.get("coordinate") != expected_coordinate
        or row.get("source_layer_fingerprint") != source_layer_fingerprint
        or row.get("source_sha256") != source_sha256
        or row.get("method_version") != implementation.method_version
        or row.get("implementation_id") != implementation.implementation_id
        or row.get("implementation_version") != IOHUNTER_COMPACT_IMPLEMENTATION_VERSION
        or row.get("execution_input_fingerprint") != execution_input_fingerprint
        or row.get("method_config") != dict(method_config)
        or row.get("row_checksum") != _row_checksum(row)
    ):
        return None
    evaluator_fingerprint = row.get("evaluator_fingerprint")
    fold_fingerprint = row.get("fold_fingerprint")
    if not all(
        isinstance(value, str) and value.startswith("sha256:") and len(value) == 71
        for value in (evaluator_fingerprint, fold_fingerprint)
    ):
        return None
    expected_identity = _run_identity(
        coordinate,
        implementation=implementation,
        method_config=method_config,
        source_layer_fingerprint=source_layer_fingerprint,
        source_sha256=source_sha256,
        evaluator_fingerprint=evaluator_fingerprint,
        fold_fingerprint=fold_fingerprint,
        execution_input_fingerprint=execution_input_fingerprint,
    )
    if row.get("run_identity") != expected_identity:
        return None
    return row


def _run_identity(
    coordinate: CompactMatrixCoordinate,
    *,
    implementation: Any,
    method_config: Mapping[str, Any],
    source_layer_fingerprint: str,
    source_sha256: str,
    evaluator_fingerprint: str,
    fold_fingerprint: str,
    execution_input_fingerprint: str,
) -> str:
    return _fingerprint(
        {
            "coordinate": dataclasses.asdict(coordinate),
            "method_version": implementation.method_version,
            "implementation_id": implementation.implementation_id,
            "method_config_version": IOHUNTER_COMPACT_METHOD_CONFIG_VERSION,
            "method_config": dict(method_config),
            "source_layer_fingerprint": source_layer_fingerprint,
            "source_sha256": source_sha256,
            "evaluator_fingerprint": evaluator_fingerprint,
            "fold_fingerprint": fold_fingerprint,
            "execution_input_fingerprint": execution_input_fingerprint,
        }
    )


def _write_completed_row(path: Path, row: dict[str, Any]) -> dict[str, Any]:
    row["row_checksum"] = _row_checksum(row)
    _atomic_write_json(path, row)
    return row


def _blocked_load_row(
    output_dir: Path,
    coordinate: CompactMatrixCoordinate,
    implementation: Any,
    method_config: Mapping[str, Any],
    reason: str,
    memory_profile: Mapping[str, Any] | None,
) -> dict[str, Any]:
    path = _row_path(output_dir, coordinate)
    row = {
        "schema_version": IOHUNTER_COMPACT_ROW_SCHEMA_VERSION,
        "completion_status": "complete",
        "coordinate": dataclasses.asdict(coordinate),
        "run_identity": _fingerprint({"coordinate": dataclasses.asdict(coordinate), "load_failure": reason}),
        "campaign": coordinate.campaign,
        "seed": coordinate.seed,
        "fold_id": coordinate.fold_id,
        "method_id": coordinate.method_id,
        "method_version": implementation.method_version,
        "implementation_id": implementation.implementation_id,
        "implementation_version": IOHUNTER_COMPACT_IMPLEMENTATION_VERSION,
        "method_config_version": IOHUNTER_COMPACT_METHOD_CONFIG_VERSION,
        "method_config": dict(method_config),
        "source_layer_fingerprint": None,
        "source_sha256": None,
        "evaluator_fingerprint": None,
        "fold_fingerprint": None,
        "execution_input_fingerprint": None,
        "prediction_artifact_identity": None,
        "runtime_seconds": 0.0,
        "peak_memory_bytes": 0,
        "status": "blocked",
        "reason": reason,
        "diagnostics_summary": {},
        "proxy_metrics": {},
        "evaluation_scope": IOHUNTER_EXTERNAL_EVALUATION_SCOPE,
        "claim_markers": ["iohunter_compact_load_blocked"],
        "account_count": None,
        "candidate_edge_count": None,
        "memory_profile": _plain_compact(memory_profile or {}),
        "row_path": str(path),
    }
    return _write_completed_row(path, row)


def _prediction_compact_array_bytes(prediction: Any) -> int:
    if prediction is None:
        return 0
    return sum(
        int(np.asarray(getattr(prediction, field_name)).nbytes)
        for field_name in (
            "candidate_endpoints",
            "edge_scores",
            "account_scores",
            "cluster_assignments",
        )
    )


def _run_campaign(
    *,
    dataset_root: Path,
    output_dir: Path,
    campaign: str,
    coordinates: Sequence[CompactMatrixCoordinate],
    registry: CompactDiscoveryRegistry,
    method_configs: Mapping[str, Mapping[str, Any]],
    memory_budget_bytes: int,
    prior_checksums: Mapping[str, str],
) -> tuple[list[dict[str, Any]], Counter[str], dict[str, Any]]:
    source = dataset_root / campaign / "0.7_datasets.pkl"
    try:
        discovery_load = load_compact_iohunter_discovery(
            source,
            campaign=campaign,
            trusted_local=True,
            memory_budget_bytes=memory_budget_bytes,
        )
    except Exception as exc:
        profile = getattr(exc, "memory_profile", None)
        profile_dict = profile.to_dict() if profile is not None else None
        reason = f"blocked: compact IOHunter discovery load failed: {type(exc).__name__}: {exc}"
        existed_before = {
            coordinate: _row_path(output_dir, coordinate).exists()
            for coordinate in coordinates
        }
        rows = [
            _blocked_load_row(
                output_dir,
                coordinate,
                registry.implementation(coordinate.method_id),
                method_configs[coordinate.method_id],
                reason,
                profile_dict,
            )
            for coordinate in coordinates
        ]
        actions = Counter(
            "rewritten" if existed_before[coordinate] else "executed"
            for coordinate in coordinates
        )
        return rows, actions, {
            "load_status": "blocked",
            "reason": reason,
            "source_layer_fingerprint": None,
            "source_sha256": None,
            "evaluator_fingerprint": None,
            "memory_profile": profile_dict,
        }

    rows: list[dict[str, Any]] = []
    actions: Counter[str] = Counter()
    pending_executions = []
    view = discovery_load.discovery_view
    for coordinate in coordinates:
        path = _row_path(output_dir, coordinate)
        existed_before = path.exists()
        implementation = registry.implementation(coordinate.method_id)
        exact_config = method_configs[coordinate.method_id]
        execution_config = {key: value for key, value in exact_config.items() if key != "method_variant"}
        execution_input = CompactDiscoveryExecutionInput(
            discovery_view=view,
            seed=coordinate.seed,
            method_config_version=IOHUNTER_COMPACT_METHOD_CONFIG_VERSION,
            method_config=execution_config,
        )
        resumed = _resume_candidate(
            path,
            prior_file_checksum=prior_checksums.get(str(path)),
            coordinate=coordinate,
            implementation=implementation,
            source_layer_fingerprint=view.source_layer_fingerprint,
            source_sha256=discovery_load.source_sha256,
            execution_input_fingerprint=execution_input.fingerprint,
            method_config=exact_config,
        )
        if resumed is not None:
            rows.append(resumed)
            actions["resumed"] += 1
            continue

        outcome = execute_compact_discovery_method(
            {coordinate.method_id: implementation},
            coordinate.method_id,
            execution_input,
        )
        pending_executions.append(
            (coordinate, path, existed_before, implementation, exact_config, execution_input, outcome)
        )

    evaluator = None
    evaluator_memory_profile = discovery_load.memory_profile
    evaluator_load_error: Exception | None = None
    if pending_executions:
        try:
            retained_compact_array_bytes = int(discovery_load.memory_profile.compact_array_bytes)
            retained_compact_array_bytes += sum(
                _prediction_compact_array_bytes(outcome.prediction)
                for *_, outcome in pending_executions
            )
            evaluator_load = load_compact_iohunter_evaluator_result(
                source,
                campaign=campaign,
                trusted_local=True,
                memory_budget_bytes=memory_budget_bytes,
                retained_compact_array_bytes=retained_compact_array_bytes,
            )
            evaluator = evaluator_load.evaluator
            evaluator_memory_profile = evaluator_load.memory_profile
            if evaluator.source_sha256 != discovery_load.source_sha256:
                evaluator = None
                evaluator_load_error = RuntimeError(
                    "source changed between Discovery and evaluator phases"
                )
        except Exception as exc:
            memory_profile = getattr(exc, "memory_profile", None)
            if memory_profile is not None:
                evaluator_memory_profile = memory_profile
            if memory_profile is not None and (
                int(memory_profile.compact_array_bytes)
                > int(discovery_load.memory_profile.compact_array_bytes)
            ):
                evaluator_load_error = RuntimeError(
                    "combined compact IOHunter evaluator memory budget exceeded"
                )
            else:
                evaluator_load_error = exc

    for coordinate, path, existed_before, implementation, exact_config, execution_input, outcome in pending_executions:
        prediction = outcome.prediction
        metrics: Mapping[str, float] = {}
        claim_markers = set(prediction.claim_markers if prediction is not None else ())
        status = outcome.status
        reason = outcome.reason
        source_sha256 = discovery_load.source_sha256
        evaluator_fingerprint = None
        fold_fingerprint = None
        identity = _fingerprint(
            {
                "coordinate": dataclasses.asdict(coordinate),
                "evaluator_load_failure": type(evaluator_load_error).__name__ if evaluator_load_error else None,
                "execution_input_fingerprint": execution_input.fingerprint,
            }
        )
        if evaluator_load_error is not None:
            status = "failed"
            reason = (
                "external account-recovery evaluator load failed: "
                f"{type(evaluator_load_error).__name__}: {evaluator_load_error}"
            )
        elif evaluator is not None:
            evaluator_fingerprint = evaluator.content_fingerprint
            fold = evaluator.official_folds[IOHUNTER_COMPACT_SEEDS.index(coordinate.seed)]
            fold_fingerprint = compact_fold_fingerprint(fold)
            identity = _run_identity(
                coordinate,
                implementation=implementation,
                method_config=exact_config,
                source_layer_fingerprint=view.source_layer_fingerprint,
                source_sha256=evaluator.source_sha256,
                evaluator_fingerprint=evaluator.content_fingerprint,
                fold_fingerprint=fold_fingerprint,
                execution_input_fingerprint=execution_input.fingerprint,
            )
            if outcome.status == "success" and prediction is not None:
                try:
                    evaluation_input = IOHunterExternalEvaluationInput(
                        evaluator=evaluator,
                        fold=fold,
                        evaluation_config=_EVALUATION_CONFIG,
                    )
                    evaluation = evaluate_iohunter_external_account_recovery(prediction, evaluation_input)
                    status = evaluation.status
                    reason = evaluation.reason
                    metrics = evaluation.metrics
                    claim_markers.update(evaluation.claim_markers)
                except Exception as exc:
                    status = "failed"
                    reason = f"external account-recovery evaluation failed: {type(exc).__name__}: {exc}"
        row = {
            "schema_version": IOHUNTER_COMPACT_ROW_SCHEMA_VERSION,
            "completion_status": "complete",
            "coordinate": dataclasses.asdict(coordinate),
            "run_identity": identity,
            "campaign": coordinate.campaign,
            "seed": coordinate.seed,
            "fold_id": coordinate.fold_id,
            "method_id": coordinate.method_id,
            "method_version": outcome.method_version,
            "implementation_id": outcome.implementation_id,
            "implementation_version": IOHUNTER_COMPACT_IMPLEMENTATION_VERSION,
            "method_config_version": IOHUNTER_COMPACT_METHOD_CONFIG_VERSION,
            "method_config": dict(exact_config),
            "source_layer_fingerprint": view.source_layer_fingerprint,
            "source_sha256": source_sha256,
            "evaluator_fingerprint": evaluator_fingerprint,
            "fold_fingerprint": fold_fingerprint,
            "execution_input_fingerprint": outcome.execution_input_fingerprint,
            "prediction_artifact_identity": prediction.artifact_identity if prediction is not None else None,
            "runtime_seconds": outcome.runtime_seconds,
            "peak_memory_bytes": max(
                int(outcome.peak_memory_bytes),
                int(evaluator_memory_profile.estimated_peak_bytes),
            ),
            "status": status,
            "reason": reason,
            "diagnostics_summary": _plain_compact(prediction.diagnostics if prediction is not None else {}),
            "proxy_metrics": _plain_compact(metrics),
            "evaluation_scope": IOHUNTER_EXTERNAL_EVALUATION_SCOPE,
            "claim_markers": sorted(claim_markers),
            "account_count": view.account_count,
            "candidate_edge_count": int(len(prediction.candidate_endpoints)) if prediction is not None else None,
            "memory_profile": evaluator_memory_profile.to_dict(),
            "row_path": str(path),
        }
        rows.append(_write_completed_row(path, row))
        actions["rewritten" if existed_before else "executed"] += 1

    campaign_identity = {
        "load_status": "success",
        "source_layer_fingerprint": view.source_layer_fingerprint,
        "source_sha256": discovery_load.source_sha256,
        "evaluator_fingerprint": evaluator.content_fingerprint if evaluator is not None else None,
        "account_count": view.account_count,
        "memory_profile": evaluator_memory_profile.to_dict(),
    }
    if campaign_identity["evaluator_fingerprint"] is None:
        resumed_fingerprint = next(
            (row.get("evaluator_fingerprint") for row in rows if row.get("evaluator_fingerprint")),
            None,
        )
        campaign_identity["evaluator_fingerprint"] = resumed_fingerprint
    return rows, actions, campaign_identity


def aggregate_compact_matrix_rows(
    rows: Sequence[Mapping[str, Any]],
    *,
    bootstrap_seed: int = 0,
    bootstrap_resamples: int = 2_000,
) -> tuple[dict[str, Any], ...]:
    groups: dict[tuple[str, str | None, str, str], list[float]] = defaultdict(list)
    for row in rows:
        if row.get("status") != "success":
            continue
        for metric_name, raw_value in row.get("proxy_metrics", {}).items():
            value = float(raw_value)
            groups[("campaign", str(row["campaign"]), str(row["method_id"]), metric_name)].append(value)
            groups[("matrix", None, str(row["method_id"]), metric_name)].append(value)
    aggregates = []
    for (scope, campaign, method_id, metric_name), values in sorted(
        groups.items(), key=lambda item: tuple("" if part is None else part for part in item[0])
    ):
        low, high = bootstrap_confidence_interval(
            tuple(values), seed=bootstrap_seed, resamples=bootstrap_resamples
        )
        aggregates.append(
            {
                "scope": scope,
                "campaign": campaign,
                "method_id": method_id,
                "metric_name": metric_name,
                "count": len(values),
                "mean": float(np.mean(values)),
                "sample_std": float(np.std(values, ddof=1)) if len(values) > 1 else 0.0,
                "ci_95_low": low,
                "ci_95_high": high,
                "bootstrap_seed": bootstrap_seed,
                "bootstrap_resamples": bootstrap_resamples,
            }
        )
    return tuple(aggregates)


def build_compact_claim_decisions(
    rows: Sequence[Mapping[str, Any]],
    *,
    bootstrap_seed: int = 0,
    bootstrap_resamples: int = 2_000,
) -> dict[str, Any]:
    paired_values: dict[str, list[tuple[str, int, float]]] = defaultdict(list)
    successful = {
        (str(row["campaign"]), int(row["seed"]), str(row["method_id"])): row
        for row in rows
        if row.get("status") == "success"
    }
    pair_keys = sorted({(campaign, seed) for campaign, seed, _ in successful})
    for campaign, seed in pair_keys:
        candidate = successful.get((campaign, seed, "tsgs_mhcr_compact"))
        baseline = successful.get((campaign, seed, "edgebank"))
        if candidate is None or baseline is None:
            continue
        shared_metrics = (
            set(candidate.get("proxy_metrics", {}))
            & set(baseline.get("proxy_metrics", {}))
            & _CLAIMABLE_PROXY_METRICS
        )
        for metric_name in sorted(shared_metrics):
            difference = float(candidate["proxy_metrics"][metric_name]) - float(baseline["proxy_metrics"][metric_name])
            paired_values[metric_name].append((campaign, seed, difference))
    paired = []
    for metric_name in sorted(_CLAIMABLE_PROXY_METRICS):
        observations = paired_values.get(metric_name, [])
        differences = tuple(item[2] for item in observations)
        observed_pairs = {(campaign, seed) for campaign, seed, _ in observations}
        missing_pairs = _REQUIRED_PROXY_PAIRS - observed_pairs
        if differences:
            low, high = bootstrap_confidence_interval(
                differences, seed=bootstrap_seed, resamples=bootstrap_resamples
            )
            mean = float(np.mean(differences))
            sample_std = float(np.std(differences, ddof=1)) if len(differences) > 1 else 0.0
        else:
            low = None
            high = None
            mean = None
            sample_std = None
        if missing_pairs:
            decision = "blocked_incomplete_matrix"
            decision_reason = (
                "proxy comparison requires all 30 canonical campaign-seed pairs; "
                f"observed {len(observed_pairs)}"
            )
        elif low is not None and low > 0.0:
            decision = "supported_external_account_proxy_only"
            decision_reason = "paired 95% bootstrap confidence interval is strictly positive"
        else:
            decision = "not_supported"
            decision_reason = "paired 95% bootstrap confidence interval is not strictly positive"
        paired.append(
            {
                "metric_name": metric_name,
                "pair_count": len(differences),
                "required_pair_count": len(_REQUIRED_PROXY_PAIRS),
                "missing_pair_count": len(missing_pairs),
                "mean_candidate_minus_edgebank": mean,
                "sample_std": sample_std,
                "ci_95_low": low,
                "ci_95_high": high,
                "paired_campaign_seeds": [
                    {"campaign": campaign, "seed": seed} for campaign, seed, _ in observations
                ],
                "decision": decision,
                "decision_reason": decision_reason,
                "claim_scope": IOHUNTER_EXTERNAL_EVALUATION_SCOPE,
            }
        )
    fixed = (
        ("harmful_cib_detection", "IOHunter lacks harmful-CIB Gold labels and Stage 2 Detection was not executed"),
        ("true_coordination_edge_community_recovery", "IOHunter lacks true coordination-edge and community labels"),
        ("causal_campaign_claims", "IOHunter lacks causal campaign annotations"),
        ("observed_time_claims", "IOHunter processed graphs lack observed timestamps"),
        ("production_activation", "this matrix is research-only and the production Discovery runtime is frozen"),
    )
    return {
        "schema_version": IOHUNTER_COMPACT_CLAIM_SCHEMA_VERSION,
        "paired_external_account_proxy": paired,
        "fixed_blocked_claims": [
            {"claim_id": claim_id, "decision": "blocked", "missing_capability": reason}
            for claim_id, reason in fixed
        ],
        "numerical_document_targets": [],
    }


def _write_aggregate_csv(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    fields = (
        "scope", "campaign", "method_id", "metric_name", "count", "mean", "sample_std",
        "ci_95_low", "ci_95_high", "bootstrap_seed", "bootstrap_resamples",
    )
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    _atomic_write_text(path, output.getvalue())


def _package_versions() -> dict[str, str | None]:
    versions = {}
    for distribution in ("numpy", "networkx", "python-igraph", "leidenalg", "torch"):
        try:
            versions[distribution] = importlib.metadata.version(distribution)
        except importlib.metadata.PackageNotFoundError:
            versions[distribution] = None
    return versions


def run_compact_iohunter_matrix(
    dataset_root: str | Path = CANONICAL_IOHUNTER_PROCESSED_ROOT,
    output_dir: str | Path | None = None,
    *,
    campaigns: Sequence[str] | None = None,
    seeds: Sequence[int] | None = None,
    methods: Sequence[str] | None = None,
    memory_budget_bytes: int = 16 * 1024**3,
    method_config_overrides: Mapping[str, Mapping[str, Any]] | None = None,
    bootstrap_seed: int = 0,
    bootstrap_resamples: int = 2_000,
) -> CompactIOHunterMatrixResult:
    if output_dir is None:
        raise ValueError("output_dir is required under the canonical G-drive reproduction output root")
    output = validate_compact_matrix_output_dir(output_dir)
    if isinstance(memory_budget_bytes, bool) or not isinstance(memory_budget_bytes, int) or memory_budget_bytes <= 0:
        raise ValueError("memory_budget_bytes must be a positive integer")
    if isinstance(bootstrap_resamples, bool) or not isinstance(bootstrap_resamples, int) or bootstrap_resamples <= 0:
        raise ValueError("bootstrap_resamples must be a positive integer")
    dataset = Path(dataset_root).resolve(strict=False)
    coordinates = compact_iohunter_matrix_coordinates(campaigns=campaigns, seeds=seeds, methods=methods)
    selected_campaigns = tuple(dict.fromkeys(row.campaign for row in coordinates))
    selected_methods = tuple(dict.fromkeys(row.method_id for row in coordinates))
    registry = default_compact_discovery_registry()
    configs = _method_configs(registry, selected_methods, method_config_overrides)
    prior_checksums = _prior_row_checksums(output)
    all_rows: list[dict[str, Any]] = []
    resume_counts: Counter[str] = Counter()
    campaign_sources = {}
    for campaign in selected_campaigns:
        campaign_rows, actions, source_identity = _run_campaign(
            dataset_root=dataset,
            output_dir=output,
            campaign=campaign,
            coordinates=tuple(row for row in coordinates if row.campaign == campaign),
            registry=registry,
            method_configs=configs,
            memory_budget_bytes=memory_budget_bytes,
            prior_checksums=prior_checksums,
        )
        all_rows.extend(campaign_rows)
        resume_counts.update(actions)
        campaign_sources[campaign] = source_identity
        del campaign_rows, source_identity
        gc.collect()

    campaign_order = {value: index for index, value in enumerate(IOHUNTER_COMPACT_CAMPAIGNS)}
    seed_order = {value: index for index, value in enumerate(IOHUNTER_COMPACT_SEEDS)}
    method_order = {value: index for index, value in enumerate(IOHUNTER_COMPACT_METHODS)}
    all_rows.sort(
        key=lambda row: (
            campaign_order[row["campaign"]],
            seed_order[row["seed"]],
            row["fold_id"],
            method_order[row["method_id"]],
        )
    )
    aggregates = aggregate_compact_matrix_rows(
        all_rows, bootstrap_seed=bootstrap_seed, bootstrap_resamples=bootstrap_resamples
    )
    claims = build_compact_claim_decisions(
        all_rows, bootstrap_seed=bootstrap_seed, bootstrap_resamples=bootstrap_resamples
    )
    aggregate_json_path = output / "aggregate_table.json"
    aggregate_csv_path = output / "aggregate_table.csv"
    claims_path = output / "claim_decisions.json"
    _atomic_write_json(
        aggregate_json_path,
        {"schema_version": IOHUNTER_COMPACT_AGGREGATE_SCHEMA_VERSION, "rows": list(aggregates)},
    )
    _write_aggregate_csv(aggregate_csv_path, aggregates)
    _atomic_write_json(claims_path, claims)
    status_counts = dict(sorted(Counter(str(row["status"]) for row in all_rows).items()))
    manifest = {
        "schema_version": IOHUNTER_COMPACT_MATRIX_SCHEMA_VERSION,
        "implementation_version": IOHUNTER_COMPACT_IMPLEMENTATION_VERSION,
        "dataset_root": str(dataset),
        "output_dir": str(output),
        "campaigns": list(selected_campaigns),
        "seeds": list(dict.fromkeys(row.seed for row in coordinates)),
        "methods": list(selected_methods),
        "method_config_version": IOHUNTER_COMPACT_METHOD_CONFIG_VERSION,
        "method_configs": configs,
        "evaluation_config": dict(_EVALUATION_CONFIG),
        "evaluation_scope": IOHUNTER_EXTERNAL_EVALUATION_SCOPE,
        "campaign_source_fingerprints": campaign_sources,
        "environment": {
            "python": platform.python_version(),
            "python_implementation": platform.python_implementation(),
            "platform": platform.platform(),
            "packages": _package_versions(),
        },
        "bootstrap": {"seed": bootstrap_seed, "resamples": bootstrap_resamples, "confidence": 0.95},
        "status_counts": status_counts,
        "rows": [
            {
                "run_identity": row["run_identity"],
                "row_path": row["row_path"],
                "row_payload_checksum": row["row_checksum"],
                "row_identity_checksum": _row_identity_checksum(row),
                "file_checksum": _file_checksum(Path(row["row_path"])),
                "status": row["status"],
            }
            for row in all_rows
        ],
        "derived_artifacts": {
            "aggregate_json": {"path": str(aggregate_json_path), "checksum": _file_checksum(aggregate_json_path)},
            "aggregate_csv": {"path": str(aggregate_csv_path), "checksum": _file_checksum(aggregate_csv_path)},
            "claim_decisions": {"path": str(claims_path), "checksum": _file_checksum(claims_path)},
        },
    }
    manifest["manifest_fingerprint"] = _fingerprint(_manifest_identity(manifest))
    _atomic_write_json(output / "matrix_manifest.json", manifest)
    return CompactIOHunterMatrixResult(
        output_dir=str(output),
        rows=tuple(all_rows),
        status_counts=status_counts,
        resume_counts=dict(sorted(resume_counts.items())),
        manifest_fingerprint=manifest["manifest_fingerprint"],
    )


__all__ = [
    "IOHUNTER_COMPACT_AGGREGATE_SCHEMA_VERSION",
    "IOHUNTER_COMPACT_CAMPAIGNS",
    "IOHUNTER_COMPACT_CLAIM_SCHEMA_VERSION",
    "IOHUNTER_COMPACT_IMPLEMENTATION_VERSION",
    "IOHUNTER_COMPACT_MATRIX_SCHEMA_VERSION",
    "IOHUNTER_COMPACT_METHOD_CONFIG_VERSION",
    "IOHUNTER_COMPACT_METHODS",
    "IOHUNTER_COMPACT_ROW_SCHEMA_VERSION",
    "IOHUNTER_COMPACT_SEEDS",
    "CompactIOHunterMatrixResult",
    "CompactMatrixCoordinate",
    "aggregate_compact_matrix_rows",
    "build_compact_claim_decisions",
    "compact_iohunter_matrix_coordinates",
    "run_compact_iohunter_matrix",
    "validate_compact_matrix_output_dir",
]
