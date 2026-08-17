from __future__ import annotations

import csv
import dataclasses
import gc
import hashlib
import importlib.metadata
import io
import json
import math
import os
import platform
import secrets
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
    CompactDiscoveryPrediction,
    IOHunterExternalEvaluationInput,
    evaluate_iohunter_external_account_recovery,
    execute_compact_discovery_method,
    validate_compact_discovery_prediction,
)
from ..coordination_discover.stage1.contracts import DiscoveredClusterBatch
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
IOHUNTER_COMPACT_FOLDS = tuple(f"fold-{index:03d}" for index in range(5))
IOHUNTER_COMPACT_METHODS = (
    "tsgs_mhcr_compact",
    "frozen_system_evidence_prior",
    "frozen_system_account_score_prior",
    "magnn_legacy",
    "magnn_leiden_hybrid_discovery",
    "edgebank",
    "dense_cosine_leiden",
    "no_tsgs",
    "no_mhcr",
    "no_relation_specific",
)
IOHUNTER_COMPACT_MATRIX_SCHEMA_VERSION = "cogguard.iohunter-compact-matrix/v4"
IOHUNTER_COMPACT_ROW_SCHEMA_VERSION = "cogguard.iohunter-compact-matrix-row/v4"
IOHUNTER_COMPACT_AGGREGATE_SCHEMA_VERSION = "cogguard.iohunter-compact-aggregates/v4"
IOHUNTER_COMPACT_CLAIM_SCHEMA_VERSION = "cogguard.iohunter-compact-claims/v6"
IOHUNTER_COMPACT_IMPLEMENTATION_VERSION = "full-crossed-compact-matrix-v7"
IOHUNTER_COMPACT_METHOD_CONFIG_VERSION = "compact-discovery-method-config/v1"
COMPACT_PREDICTION_ARTIFACT_SCHEMA_VERSION = "cogguard.compact-discovery-prediction-artifact/v2"
IOHUNTER_EXTERNAL_EVALUATION_SCOPE = "external_account_recovery_not_coordination_ground_truth"
IOHUNTER_STRUCTURAL_EVALUATION_SCOPE = "partition_quality_on_method_candidate_edge_score_graph"
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
    (campaign, seed, fold_id)
    for campaign in IOHUNTER_COMPACT_CAMPAIGNS
    for seed in IOHUNTER_COMPACT_SEEDS
    for fold_id in IOHUNTER_COMPACT_FOLDS
)
_PAIR_PROVENANCE_FIELDS = (
    "fold_id",
    "source_layer_fingerprint",
    "source_sha256",
    "evaluator_fingerprint",
    "fold_fingerprint",
    "evaluation_scope",
)
_PREDICTION_ARRAY_FIELDS = (
    "candidate_endpoints",
    "edge_scores",
    "account_scores",
    "cluster_assignments",
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
    temporary = path.with_name(f".{path.name}.{os.getpid()}.{secrets.token_hex(8)}.tmp")
    try:
        temporary.write_text(text, encoding="utf-8", newline="")
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


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


@dataclass(frozen=True, slots=True)
class _SpooledExecution:
    coordinate: CompactMatrixCoordinate
    method_version: str
    implementation_id: str
    execution_input_fingerprint: str
    runtime_seconds: float
    peak_memory_bytes: int
    status: str
    reason: str | None
    prediction_artifact: Mapping[str, Any] | None
    prediction_array_bytes: int


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
    folds: Sequence[str] | None = None,
    methods: Sequence[str] | None = None,
) -> tuple[CompactMatrixCoordinate, ...]:
    selected_campaigns = _canonical_subset(campaigns, IOHUNTER_COMPACT_CAMPAIGNS, "campaigns")
    selected_seeds = _canonical_subset(seeds, IOHUNTER_COMPACT_SEEDS, "seeds")
    selected_folds = _canonical_subset(folds, IOHUNTER_COMPACT_FOLDS, "folds")
    selected_methods = _canonical_subset(methods, IOHUNTER_COMPACT_METHODS, "methods")
    return tuple(
        CompactMatrixCoordinate(campaign, seed, fold_id, method)
        for campaign in selected_campaigns
        for seed in selected_seeds
        for fold_id in selected_folds
        for method in selected_methods
    )


def _execution_coordinate(coordinate: CompactMatrixCoordinate) -> dict[str, Any]:
    return {
        "campaign": coordinate.campaign,
        "seed": coordinate.seed,
        "method_id": coordinate.method_id,
    }


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


def _prediction_artifact_paths(
    output_dir: Path,
    coordinate: CompactMatrixCoordinate,
) -> tuple[Path, Path]:
    directory = (
        output_dir
        / "p"
        / coordinate.campaign
        / str(coordinate.seed)
    ).resolve(strict=False)
    directory.relative_to(output_dir)
    return (
        directory / f"{coordinate.method_id}.json",
        directory / f"{coordinate.method_id}.bin",
    )


def _atomic_write_prediction_arrays(
    path: Path,
    prediction: CompactDiscoveryPrediction,
) -> dict[str, dict[str, Any]]:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.{secrets.token_hex(8)}.tmp")
    layout: dict[str, dict[str, Any]] = {}
    offset = 0
    try:
        with temporary.open("wb") as stream:
            for field_name in _PREDICTION_ARRAY_FIELDS:
                array = np.asarray(getattr(prediction, field_name))
                if not array.flags.c_contiguous:
                    raise ValueError(f"{field_name} must be C-contiguous for artifact storage")
                raw = memoryview(array).cast("B")
                layout[field_name] = {
                    "dtype": array.dtype.str,
                    "shape": list(array.shape),
                    "offset": offset,
                    "nbytes": len(raw),
                }
                for start in range(0, len(raw), 8 * 1024 * 1024):
                    stream.write(raw[start : start + 8 * 1024 * 1024])
                offset += len(raw)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)
    return layout


def _prediction_artifact_descriptor(metadata_path: Path, metadata: Mapping[str, Any]) -> dict[str, Any]:
    arrays_path = Path(str(metadata["arrays_path"])).resolve(strict=False)
    return {
        "schema_version": COMPACT_PREDICTION_ARTIFACT_SCHEMA_VERSION,
        "metadata_path": str(metadata_path.resolve(strict=False)),
        "arrays_path": str(arrays_path),
        "metadata_checksum": _file_checksum(metadata_path),
        "arrays_checksum": str(metadata["arrays_checksum"]),
        "artifact_identity": str(metadata["artifact_identity"]),
        "array_bytes": int(metadata["array_bytes"]),
    }


def _write_prediction_artifact(
    output_dir: Path,
    coordinate: CompactMatrixCoordinate,
    prediction: CompactDiscoveryPrediction,
    *,
    source_layer_fingerprint: str,
    source_sha256: str,
    method_config: Mapping[str, Any],
    execution_input_fingerprint: str,
    runtime_seconds: float,
    peak_memory_bytes: int,
    execution_status: str,
    execution_reason: str | None,
) -> dict[str, Any]:
    metadata_path, arrays_path = _prediction_artifact_paths(output_dir, coordinate)
    array_layout = _atomic_write_prediction_arrays(arrays_path, prediction)
    metadata = {
        "schema_version": COMPACT_PREDICTION_ARTIFACT_SCHEMA_VERSION,
        "execution_coordinate": _execution_coordinate(coordinate),
        "source_layer_fingerprint": source_layer_fingerprint,
        "source_sha256": source_sha256,
        "method_config_version": IOHUNTER_COMPACT_METHOD_CONFIG_VERSION,
        "method_config": dict(method_config),
        "method_version": prediction.method_version,
        "implementation_id": prediction.implementation_id,
        "execution_input_fingerprint": execution_input_fingerprint,
        "runtime_seconds": float(runtime_seconds),
        "peak_memory_bytes": int(peak_memory_bytes),
        "execution_status": execution_status,
        "execution_reason": execution_reason,
        "artifact_identity": prediction.artifact_identity,
        "array_bytes": _prediction_compact_array_bytes(prediction),
        "storage_format": "raw_array_bundle_v1",
        "array_layout": array_layout,
        "arrays_path": str(arrays_path),
        "arrays_checksum": _file_checksum(arrays_path),
        "discovered_cluster_batch": prediction.discovered_cluster_batch.to_dict(),
        "diagnostics": _plain_compact(prediction.diagnostics),
        "claim_markers": list(prediction.claim_markers),
    }
    _atomic_write_json(metadata_path, metadata)
    return _prediction_artifact_descriptor(metadata_path, metadata)


def _validate_prediction_artifact(
    output_dir: Path,
    coordinate: CompactMatrixCoordinate,
    *,
    implementation: Any,
    source_layer_fingerprint: str,
    account_count: int,
    source_sha256: str,
    method_config: Mapping[str, Any],
    execution_input_fingerprint: str,
    descriptor: Mapping[str, Any] | None = None,
) -> tuple[dict[str, Any], dict[str, Any]] | None:
    expected_metadata_path, expected_arrays_path = _prediction_artifact_paths(output_dir, coordinate)
    if descriptor is not None:
        if not isinstance(descriptor, MappingABC):
            return None
        if descriptor.get("schema_version") != COMPACT_PREDICTION_ARTIFACT_SCHEMA_VERSION:
            return None
        try:
            declared_metadata_path = Path(str(descriptor["metadata_path"])).resolve(strict=False)
            declared_arrays_path = Path(str(descriptor["arrays_path"])).resolve(strict=False)
        except (KeyError, OSError, ValueError):
            return None
        if declared_metadata_path != expected_metadata_path or declared_arrays_path != expected_arrays_path:
            return None
    if not expected_metadata_path.is_file() or not expected_arrays_path.is_file():
        return None
    try:
        metadata_checksum = _file_checksum(expected_metadata_path)
        arrays_checksum = _file_checksum(expected_arrays_path)
        metadata = json.loads(expected_metadata_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(metadata, MappingABC):
        return None
    if descriptor is not None and (
        descriptor.get("metadata_checksum") != metadata_checksum
        or descriptor.get("arrays_checksum") != arrays_checksum
    ):
        return None
    expected = {
        "schema_version": COMPACT_PREDICTION_ARTIFACT_SCHEMA_VERSION,
        "execution_coordinate": _execution_coordinate(coordinate),
        "source_layer_fingerprint": source_layer_fingerprint,
        "source_sha256": source_sha256,
        "method_config_version": IOHUNTER_COMPACT_METHOD_CONFIG_VERSION,
        "method_config": dict(method_config),
        "method_version": implementation.method_version,
        "implementation_id": implementation.implementation_id,
        "execution_input_fingerprint": execution_input_fingerprint,
        "storage_format": "raw_array_bundle_v1",
        "arrays_path": str(expected_arrays_path),
        "arrays_checksum": arrays_checksum,
    }
    if any(metadata.get(key) != value for key, value in expected.items()):
        return None
    if not isinstance(metadata.get("array_bytes"), int) or metadata["array_bytes"] < 0:
        return None
    runtime_seconds = metadata.get("runtime_seconds")
    if (
        isinstance(runtime_seconds, bool)
        or not isinstance(runtime_seconds, (int, float))
        or not math.isfinite(runtime_seconds)
        or runtime_seconds < 0
        or not isinstance(metadata.get("peak_memory_bytes"), int)
        or metadata["peak_memory_bytes"] < 0
        or metadata.get("execution_status") != "success"
    ):
        return None
    if descriptor is not None and (
        descriptor.get("artifact_identity") != metadata.get("artifact_identity")
        or descriptor.get("array_bytes") != metadata.get("array_bytes")
    ):
        return None
    try:
        prediction = _load_prediction_artifact(output_dir, coordinate, metadata)
        validate_compact_discovery_prediction(
            prediction,
            campaign=coordinate.campaign,
            source_layer_fingerprint=source_layer_fingerprint,
            account_count=account_count,
            method_id=implementation.method_id,
            method_version=implementation.method_version,
            implementation_id=implementation.implementation_id,
        )
        if prediction.artifact_identity != metadata.get("artifact_identity"):
            return None
    except (KeyError, OSError, TypeError, ValueError):
        return None
    finally:
        if "prediction" in locals():
            del prediction
        gc.collect()
    return metadata, _prediction_artifact_descriptor(expected_metadata_path, metadata)


def _prediction_memmap(
    path: Path,
    layout: Mapping[str, Any],
    field_name: str,
    *,
    dtype: np.dtype | tuple[np.dtype, ...],
    shape: tuple[int, ...],
) -> np.ndarray:
    entry = layout.get(field_name)
    if not isinstance(entry, MappingABC):
        raise ValueError(f"prediction artifact is missing {field_name} layout")
    declared_dtype = np.dtype(entry.get("dtype"))
    allowed_dtypes = dtype if isinstance(dtype, tuple) else (dtype,)
    if declared_dtype not in allowed_dtypes:
        raise ValueError(f"prediction artifact {field_name} dtype is invalid")
    if entry.get("shape") != list(shape):
        raise ValueError(f"prediction artifact {field_name} shape is invalid")
    offset = entry.get("offset")
    nbytes = entry.get("nbytes")
    expected_nbytes = int(np.prod(shape, dtype=np.int64)) * declared_dtype.itemsize
    if (
        isinstance(offset, bool)
        or not isinstance(offset, int)
        or offset < 0
        or isinstance(nbytes, bool)
        or not isinstance(nbytes, int)
        or nbytes != expected_nbytes
    ):
        raise ValueError(f"prediction artifact {field_name} byte layout is invalid")
    if nbytes == 0:
        empty = np.empty(shape, dtype=declared_dtype)
        empty.setflags(write=False)
        return empty
    return np.memmap(path, dtype=declared_dtype, mode="r", offset=offset, shape=shape, order="C")


def _load_prediction_artifact(
    output_dir: Path,
    coordinate: CompactMatrixCoordinate,
    metadata: Mapping[str, Any],
) -> CompactDiscoveryPrediction:
    _metadata_path, arrays_path = _prediction_artifact_paths(output_dir, coordinate)
    if not isinstance(metadata, MappingABC):
        raise ValueError("prediction artifact metadata must be an object")
    if metadata.get("storage_format") != "raw_array_bundle_v1":
        raise ValueError("prediction artifact storage format is invalid")
    if _file_checksum(arrays_path) != metadata.get("arrays_checksum"):
        raise ValueError("prediction artifact array checksum does not match payload")
    layout = metadata.get("array_layout")
    if not isinstance(layout, MappingABC) or set(layout) != set(_PREDICTION_ARRAY_FIELDS):
        raise ValueError("prediction artifact array layout is incomplete")
    expected_offset = 0
    for field_name in _PREDICTION_ARRAY_FIELDS:
        entry = layout[field_name]
        if (
            not isinstance(entry, MappingABC)
            or entry.get("offset") != expected_offset
            or isinstance(entry.get("nbytes"), bool)
            or not isinstance(entry.get("nbytes"), int)
            or entry["nbytes"] < 0
        ):
            raise ValueError("prediction artifact array layout is not contiguous")
        expected_offset += entry["nbytes"]
    if (
        expected_offset != arrays_path.stat().st_size
        or metadata.get("array_bytes") != expected_offset
    ):
        raise ValueError("prediction artifact array byte total is invalid")
    batch = DiscoveredClusterBatch.from_dict(metadata["discovered_cluster_batch"])
    account_count = batch.provenance.input_account_count
    endpoint_layout = layout["candidate_endpoints"]
    if not isinstance(endpoint_layout, MappingABC):
        raise ValueError("prediction artifact endpoint layout is invalid")
    endpoint_shape = endpoint_layout.get("shape")
    if (
        not isinstance(endpoint_shape, list)
        or len(endpoint_shape) != 2
        or endpoint_shape[1] != 2
        or isinstance(endpoint_shape[0], bool)
        or not isinstance(endpoint_shape[0], int)
        or endpoint_shape[0] < 0
    ):
        raise ValueError("prediction artifact endpoint shape is invalid")
    edge_count = endpoint_shape[0]
    prediction = CompactDiscoveryPrediction(
        account_count=account_count,
        candidate_endpoints=_prediction_memmap(
            arrays_path,
            layout,
            "candidate_endpoints",
            dtype=(np.dtype("<u2"), np.dtype("<u4")),
            shape=(edge_count, 2),
        ),
        edge_scores=_prediction_memmap(
            arrays_path,
            layout,
            "edge_scores",
            dtype=np.dtype("<f4"),
            shape=(edge_count,),
        ),
        account_scores=_prediction_memmap(
            arrays_path,
            layout,
            "account_scores",
            dtype=np.dtype("<f4"),
            shape=(account_count,),
        ),
        cluster_assignments=_prediction_memmap(
            arrays_path,
            layout,
            "cluster_assignments",
            dtype=np.dtype("<i4"),
            shape=(account_count,),
        ),
        discovered_cluster_batch=batch,
        method_id=str(metadata["execution_coordinate"]["method_id"]),
        method_version=str(metadata["method_version"]),
        implementation_id=str(metadata["implementation_id"]),
        diagnostics=metadata.get("diagnostics") or {},
        claim_markers=tuple(metadata.get("claim_markers") or ()),
    )
    if prediction.artifact_identity != metadata.get("artifact_identity"):
        raise ValueError("prediction artifact identity does not match payload")
    return prediction


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
    output_dir: Path,
    prior_file_checksum: str | None,
    coordinate: CompactMatrixCoordinate,
    implementation: Any,
    source_layer_fingerprint: str,
    account_count: int,
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
    artifact_identity = row.get("prediction_artifact_identity")
    if artifact_identity is not None:
        validated = _validate_prediction_artifact(
            output_dir,
            coordinate,
            implementation=implementation,
            source_layer_fingerprint=source_layer_fingerprint,
            account_count=account_count,
            source_sha256=source_sha256,
            method_config=method_config,
            execution_input_fingerprint=execution_input_fingerprint,
            descriptor=row.get("prediction_artifact"),
        )
        if validated is None or validated[0].get("artifact_identity") != artifact_identity:
            return None
    elif row.get("prediction_artifact") is not None:
        return None
    if row.get("status") == "failed":
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
        "prediction_artifact": None,
        "runtime_seconds": 0.0,
        "peak_memory_bytes": 0,
        "status": "blocked",
        "reason": reason,
        "diagnostics_summary": {},
        "proxy_metrics": {},
        "structural_metrics": {},
        "structural_metric_scope": IOHUNTER_STRUCTURAL_EVALUATION_SCOPE,
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


def _compact_partition_structural_metrics(prediction: CompactDiscoveryPrediction) -> dict[str, float]:
    """Evaluate partition structure without consulting labels, folds, or evaluator state."""
    account_count = int(prediction.account_count)
    assignments = np.asarray(prediction.cluster_assignments, dtype=np.int64)
    endpoints = np.asarray(prediction.candidate_endpoints)
    edge_scores = np.asarray(prediction.edge_scores, dtype=np.float64)
    if assignments.shape != (account_count,):
        raise ValueError("cluster assignments must cover the account universe")
    cluster_count = int(np.max(assignments)) + 1 if assignments.size else 0
    if cluster_count <= 0:
        return {
            "cluster_count": 0.0,
            "mean_cluster_size": 0.0,
            "largest_cluster_ratio": 0.0,
            "singleton_ratio": 0.0,
            "candidate_edge_count": 0.0,
            "weighted_edge_sum": 0.0,
            "internal_edge_fraction": 0.0,
            "weighted_internal_edge_fraction": 0.0,
            "partition_density": 0.0,
            "weighted_partition_density": 0.0,
            "weighted_modularity": 0.0,
            "mean_conductance": 0.0,
            "median_conductance": 0.0,
        }

    cluster_sizes = np.bincount(assignments, minlength=cluster_count).astype(np.float64)
    possible_internal_pairs = np.maximum(cluster_sizes * (cluster_sizes - 1.0) / 2.0, 0.0)
    total_possible_internal_pairs = float(np.sum(possible_internal_pairs))
    edge_count = int(len(endpoints))
    total_weight = float(np.sum(edge_scores)) if edge_count else 0.0

    internal_count = np.zeros(cluster_count, dtype=np.float64)
    internal_weight = np.zeros(cluster_count, dtype=np.float64)
    degree_weight = np.zeros(account_count, dtype=np.float64)
    cut_weight = np.zeros(cluster_count, dtype=np.float64)
    if edge_count:
        left = endpoints[:, 0].astype(np.int64, copy=False)
        right = endpoints[:, 1].astype(np.int64, copy=False)
        np.add.at(degree_weight, left, edge_scores)
        np.add.at(degree_weight, right, edge_scores)
        same_cluster = assignments[left] == assignments[right]
        if np.any(same_cluster):
            internal_clusters = assignments[left[same_cluster]]
            np.add.at(internal_count, internal_clusters, 1.0)
            np.add.at(internal_weight, internal_clusters, edge_scores[same_cluster])
        if np.any(~same_cluster):
            cross_scores = edge_scores[~same_cluster]
            np.add.at(cut_weight, assignments[left[~same_cluster]], cross_scores)
            np.add.at(cut_weight, assignments[right[~same_cluster]], cross_scores)

    volume = np.bincount(assignments, weights=degree_weight, minlength=cluster_count)
    graph_volume = 2.0 * total_weight
    conductance_values = []
    for cluster_id in range(cluster_count):
        denominator = min(float(volume[cluster_id]), float(graph_volume - volume[cluster_id]))
        if denominator > 0.0:
            conductance_values.append(float(cut_weight[cluster_id] / denominator))
        elif cluster_count > 1 and cluster_sizes[cluster_id] > 0:
            conductance_values.append(0.0)

    if total_weight > 0.0:
        modularity = float(
            np.sum(
                (internal_weight / total_weight)
                - np.square(volume / graph_volume)
            )
        )
        weighted_internal_edge_fraction = float(np.sum(internal_weight) / total_weight)
    else:
        modularity = 0.0
        weighted_internal_edge_fraction = 0.0

    internal_edge_total = float(np.sum(internal_count))
    conductance_array = np.asarray(conductance_values, dtype=np.float64)
    return {
        "cluster_count": float(cluster_count),
        "mean_cluster_size": float(account_count / max(cluster_count, 1)),
        "largest_cluster_ratio": float(np.max(cluster_sizes) / max(account_count, 1)),
        "singleton_ratio": float(np.count_nonzero(cluster_sizes == 1.0) / max(cluster_count, 1)),
        "candidate_edge_count": float(edge_count),
        "weighted_edge_sum": total_weight,
        "internal_edge_fraction": float(internal_edge_total / max(edge_count, 1)),
        "weighted_internal_edge_fraction": weighted_internal_edge_fraction,
        "partition_density": float(internal_edge_total / total_possible_internal_pairs)
        if total_possible_internal_pairs > 0.0
        else 0.0,
        "weighted_partition_density": float(np.sum(internal_weight) / total_possible_internal_pairs)
        if total_possible_internal_pairs > 0.0
        else 0.0,
        "weighted_modularity": modularity,
        "mean_conductance": float(np.mean(conductance_array)) if conductance_array.size else 0.0,
        "median_conductance": float(np.median(conductance_array)) if conductance_array.size else 0.0,
    }


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
    pending_executions: list[_SpooledExecution] = []
    execution_cache: dict[tuple[int, str], _SpooledExecution] = {}
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
            output_dir=output_dir,
            prior_file_checksum=prior_checksums.get(str(path)),
            coordinate=coordinate,
            implementation=implementation,
            source_layer_fingerprint=view.source_layer_fingerprint,
            account_count=view.account_count,
            source_sha256=discovery_load.source_sha256,
            execution_input_fingerprint=execution_input.fingerprint,
            method_config=exact_config,
        )
        if resumed is not None:
            rows.append(resumed)
            actions["resumed"] += 1
            if resumed.get("prediction_artifact") is None:
                execution_cache.setdefault(
                    (coordinate.seed, coordinate.method_id),
                    _SpooledExecution(
                        coordinate=coordinate,
                        method_version=str(resumed["method_version"]),
                        implementation_id=str(resumed["implementation_id"]),
                        execution_input_fingerprint=str(resumed["execution_input_fingerprint"]),
                        runtime_seconds=float(resumed["runtime_seconds"]),
                        peak_memory_bytes=int(resumed["peak_memory_bytes"]),
                        status=str(resumed["status"]),
                        reason=resumed.get("reason"),
                        prediction_artifact=None,
                        prediction_array_bytes=0,
                    ),
                )
            continue

        execution_key = (coordinate.seed, coordinate.method_id)
        cached_execution = execution_cache.get(execution_key)
        if cached_execution is not None:
            pending_executions.append(dataclasses.replace(cached_execution, coordinate=coordinate))
            actions["rewritten" if existed_before else "executed"] += 1
            continue

        recovered = _validate_prediction_artifact(
            output_dir,
            coordinate,
            implementation=implementation,
            source_layer_fingerprint=view.source_layer_fingerprint,
            account_count=view.account_count,
            source_sha256=discovery_load.source_sha256,
            method_config=exact_config,
            execution_input_fingerprint=execution_input.fingerprint,
        )
        if recovered is not None:
            metadata, descriptor = recovered
            execution = _SpooledExecution(
                coordinate=coordinate,
                method_version=str(metadata["method_version"]),
                implementation_id=str(metadata["implementation_id"]),
                execution_input_fingerprint=str(metadata["execution_input_fingerprint"]),
                runtime_seconds=float(metadata["runtime_seconds"]),
                peak_memory_bytes=int(metadata["peak_memory_bytes"]),
                status=str(metadata["execution_status"]),
                reason=metadata.get("execution_reason"),
                prediction_artifact=descriptor,
                prediction_array_bytes=int(metadata["array_bytes"]),
            )
            execution_cache[execution_key] = execution
            pending_executions.append(execution)
            actions["rewritten" if existed_before else "executed"] += 1
            continue

        outcome = execute_compact_discovery_method(
            {coordinate.method_id: implementation},
            coordinate.method_id,
            execution_input,
        )
        descriptor = None
        prediction_array_bytes = 0
        if outcome.prediction is not None:
            descriptor = _write_prediction_artifact(
                output_dir,
                coordinate,
                outcome.prediction,
                source_layer_fingerprint=view.source_layer_fingerprint,
                source_sha256=discovery_load.source_sha256,
                method_config=exact_config,
                execution_input_fingerprint=outcome.execution_input_fingerprint,
                runtime_seconds=outcome.runtime_seconds,
                peak_memory_bytes=outcome.peak_memory_bytes,
                execution_status=outcome.status,
                execution_reason=outcome.reason,
            )
            prediction_array_bytes = int(descriptor["array_bytes"])
        execution = _SpooledExecution(
            coordinate=coordinate,
            method_version=outcome.method_version,
            implementation_id=outcome.implementation_id,
            execution_input_fingerprint=outcome.execution_input_fingerprint,
            runtime_seconds=outcome.runtime_seconds,
            peak_memory_bytes=outcome.peak_memory_bytes,
            status=outcome.status,
            reason=outcome.reason,
            prediction_artifact=descriptor,
            prediction_array_bytes=prediction_array_bytes,
        )
        execution_cache[execution_key] = execution
        pending_executions.append(execution)
        actions["rewritten" if existed_before else "executed"] += 1
        del outcome
        gc.collect()

    evaluator = None
    evaluator_memory_profile = discovery_load.memory_profile
    evaluator_load_error: Exception | None = None
    if pending_executions:
        try:
            retained_compact_array_bytes = int(discovery_load.memory_profile.compact_array_bytes)
            retained_compact_array_bytes += max(
                (execution.prediction_array_bytes for execution in pending_executions),
                default=0,
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

    for execution in pending_executions:
        coordinate = execution.coordinate
        path = _row_path(output_dir, coordinate)
        implementation = registry.implementation(coordinate.method_id)
        exact_config = method_configs[coordinate.method_id]
        prediction = None
        prediction_load_error: Exception | None = None
        if execution.prediction_artifact is not None:
            try:
                metadata_path = Path(str(execution.prediction_artifact["metadata_path"]))
                metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
                prediction = _load_prediction_artifact(output_dir, coordinate, metadata)
            except Exception as exc:
                prediction_load_error = exc
        metrics: Mapping[str, float] = {}
        structural_metrics: Mapping[str, float] = {}
        claim_markers = set(prediction.claim_markers if prediction is not None else ())
        status = execution.status
        reason = execution.reason
        source_sha256 = discovery_load.source_sha256
        evaluator_fingerprint = None
        fold_fingerprint = None
        identity = _fingerprint(
            {
                "coordinate": dataclasses.asdict(coordinate),
                "evaluator_load_failure": type(evaluator_load_error).__name__ if evaluator_load_error else None,
                "execution_input_fingerprint": execution.execution_input_fingerprint,
            }
        )
        if prediction_load_error is not None:
            status = "failed"
            reason = (
                "prediction artifact load failed: "
                f"{type(prediction_load_error).__name__}: {prediction_load_error}"
            )
        elif prediction is not None:
            structural_metrics = _compact_partition_structural_metrics(prediction)
        if prediction_load_error is not None:
            pass
        elif evaluator_load_error is not None:
            status = "failed"
            reason = (
                "external account-recovery evaluator load failed: "
                f"{type(evaluator_load_error).__name__}: {evaluator_load_error}"
            )
        elif evaluator is not None:
            evaluator_fingerprint = evaluator.content_fingerprint
            folds_by_id = {fold.fold_id: fold for fold in evaluator.official_folds}
            fold = folds_by_id[coordinate.fold_id]
            fold_fingerprint = compact_fold_fingerprint(fold)
            identity = _run_identity(
                coordinate,
                implementation=implementation,
                method_config=exact_config,
                source_layer_fingerprint=view.source_layer_fingerprint,
                source_sha256=evaluator.source_sha256,
                evaluator_fingerprint=evaluator.content_fingerprint,
                fold_fingerprint=fold_fingerprint,
                execution_input_fingerprint=execution.execution_input_fingerprint,
            )
            if execution.status == "success" and prediction is not None:
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
            "method_version": execution.method_version,
            "implementation_id": execution.implementation_id,
            "implementation_version": IOHUNTER_COMPACT_IMPLEMENTATION_VERSION,
            "method_config_version": IOHUNTER_COMPACT_METHOD_CONFIG_VERSION,
            "method_config": dict(exact_config),
            "source_layer_fingerprint": view.source_layer_fingerprint,
            "source_sha256": source_sha256,
            "evaluator_fingerprint": evaluator_fingerprint,
            "fold_fingerprint": fold_fingerprint,
            "execution_input_fingerprint": execution.execution_input_fingerprint,
            "prediction_artifact_identity": prediction.artifact_identity if prediction is not None else None,
            "prediction_artifact": dict(execution.prediction_artifact) if execution.prediction_artifact else None,
            "runtime_seconds": execution.runtime_seconds,
            "peak_memory_bytes": max(
                int(execution.peak_memory_bytes),
                int(evaluator_memory_profile.estimated_peak_bytes),
            ),
            "status": status,
            "reason": reason,
            "diagnostics_summary": _plain_compact(prediction.diagnostics if prediction is not None else {}),
            "proxy_metrics": _plain_compact(metrics),
            "structural_metrics": _plain_compact(structural_metrics),
            "structural_metric_scope": IOHUNTER_STRUCTURAL_EVALUATION_SCOPE,
            "evaluation_scope": IOHUNTER_EXTERNAL_EVALUATION_SCOPE,
            "claim_markers": sorted(claim_markers),
            "account_count": view.account_count,
            "candidate_edge_count": int(len(prediction.candidate_endpoints)) if prediction is not None else None,
            "memory_profile": evaluator_memory_profile.to_dict(),
            "row_path": str(path),
        }
        rows.append(_write_completed_row(path, row))
        del prediction
        gc.collect()

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
    groups: dict[
        tuple[str, str, str | None, str, str],
        list[tuple[str, int, str, float]],
    ] = defaultdict(list)
    for row in rows:
        if row.get("status") != "success":
            continue
        for metric_group, metric_values in (
            ("proxy", row.get("proxy_metrics", {})),
            ("structural", row.get("structural_metrics", {})),
        ):
            if not isinstance(metric_values, MappingABC):
                continue
            for metric_name, raw_value in metric_values.items():
                if isinstance(raw_value, bool) or not isinstance(raw_value, (int, float)):
                    continue
                value = float(raw_value)
                if not math.isfinite(value):
                    continue
                observation = (
                    str(row["campaign"]),
                    int(row["seed"]),
                    str(row["fold_id"]),
                    value,
                )
                groups[
                    (
                        metric_group,
                        "campaign",
                        str(row["campaign"]),
                        str(row["method_id"]),
                        str(metric_name),
                    )
                ].append(observation)
                groups[
                    (
                        metric_group,
                        "matrix",
                        None,
                        str(row["method_id"]),
                        str(metric_name),
                    )
                ].append(observation)
    aggregates = []
    for (metric_group, scope, campaign, method_id, metric_name), observations in sorted(
        groups.items(), key=lambda item: tuple("" if part is None else part for part in item[0])
    ):
        raw_values = tuple(value for _campaign, _seed, _fold, value in observations)
        grouped: dict[str | int, list[float]] = defaultdict(list)
        if scope == "campaign":
            for _campaign, seed, _fold, value in observations:
                grouped[seed].append(value)
            inference_values = tuple(float(np.mean(grouped[key])) for key in sorted(grouped))
            inference_unit = "model_seed_mean_over_official_folds_conditional_on_campaign"
        else:
            for observed_campaign, _seed, _fold, value in observations:
                grouped[observed_campaign].append(value)
            inference_values = tuple(float(np.mean(grouped[key])) for key in sorted(grouped))
            inference_unit = "campaign_mean_over_crossed_seed_fold_cells"
        low, high = bootstrap_confidence_interval(
            inference_values, seed=bootstrap_seed, resamples=bootstrap_resamples
        )
        aggregates.append(
            {
                "metric_group": metric_group,
                "scope": scope,
                "campaign": campaign,
                "method_id": method_id,
                "metric_name": metric_name,
                "count": len(raw_values),
                "mean": float(np.mean(inference_values)),
                "sample_std": float(np.std(inference_values, ddof=1)) if len(inference_values) > 1 else 0.0,
                "ci_95_low": low,
                "ci_95_high": high,
                "inference_unit": inference_unit,
                "inference_unit_count": len(inference_values),
                "seed_fold_policy": "fully_crossed_orthogonal_model_seed_and_official_fold",
                "bootstrap_seed": bootstrap_seed,
                "bootstrap_resamples": bootstrap_resamples,
            }
        )
    return tuple(aggregates)


def _matching_provenance(left: Mapping[str, Any], right: Mapping[str, Any]) -> bool:
    return all(
        field in left and field in right and left[field] == right[field]
        for field in _PAIR_PROVENANCE_FIELDS
    )


def _campaign_level_summary(
    observations: Sequence[tuple[str, int, str, float]],
    *,
    bootstrap_seed: int,
    bootstrap_resamples: int,
    family_size: int = 1,
) -> dict[str, Any]:
    if isinstance(family_size, bool) or not isinstance(family_size, int) or family_size <= 0:
        raise ValueError("family_size must be a positive integer")
    by_campaign: dict[str, list[float]] = defaultdict(list)
    for campaign, _seed, _fold_id, difference in observations:
        by_campaign[campaign].append(float(difference))
    campaign_differences = tuple(
        float(np.mean(by_campaign[campaign])) for campaign in sorted(by_campaign)
    )
    if campaign_differences:
        low, high = bootstrap_confidence_interval(
            campaign_differences,
            seed=bootstrap_seed,
            resamples=bootstrap_resamples,
        )
        simultaneous_low, simultaneous_high = bootstrap_confidence_interval(
            campaign_differences,
            seed=bootstrap_seed,
            resamples=bootstrap_resamples,
            confidence=1.0 - (0.05 / family_size),
        )
        mean = float(np.mean(campaign_differences))
        sample_std = (
            float(np.std(campaign_differences, ddof=1))
            if len(campaign_differences) > 1
            else 0.0
        )
    else:
        low = None
        high = None
        simultaneous_low = None
        simultaneous_high = None
        mean = None
        sample_std = None
    return {
        "mean": mean,
        "sample_std": sample_std,
        "ci_95_low": low,
        "ci_95_high": high,
        "simultaneous_ci_95_low": simultaneous_low,
        "simultaneous_ci_95_high": simultaneous_high,
        "multiplicity_adjustment": (
            "none" if family_size == 1 else f"bonferroni_{family_size}_metrics"
        ),
        "campaign_count": len(campaign_differences),
        "required_campaign_count": len(IOHUNTER_COMPACT_CAMPAIGNS),
        "missing_campaign_count": len(set(IOHUNTER_COMPACT_CAMPAIGNS) - set(by_campaign)),
        "inference_unit": "campaign_mean_over_crossed_seed_fold_cells",
        "seed_fold_policy": "fully_crossed_orthogonal_model_seed_and_official_fold",
    }


def _paired_method_rows(
    successful: Mapping[tuple[str, int, str, str], Mapping[str, Any]],
    baseline_method_id: str,
    *,
    candidate_method_id: str = "tsgs_mhcr_compact",
) -> tuple[
    tuple[tuple[str, int, str, Mapping[str, Any], Mapping[str, Any]], ...],
    tuple[tuple[str, int, str], ...],
]:
    pairs = []
    provenance_mismatches = []
    for campaign, seed, fold_id in sorted(_REQUIRED_PROXY_PAIRS):
        candidate = successful.get((campaign, seed, fold_id, candidate_method_id))
        baseline = successful.get((campaign, seed, fold_id, baseline_method_id))
        if candidate is None or baseline is None:
            continue
        if not _matching_provenance(candidate, baseline):
            provenance_mismatches.append((campaign, seed, fold_id))
            continue
        pairs.append((campaign, seed, fold_id, candidate, baseline))
    return tuple(pairs), tuple(provenance_mismatches)


def _proxy_comparison_rows(
    pairs: Sequence[tuple[str, int, str, Mapping[str, Any], Mapping[str, Any]]],
    provenance_mismatches: Sequence[tuple[str, int, str]],
    *,
    baseline_method_id: str,
    candidate_method_id: str,
    mean_field: str,
    supported_decision: str,
    bootstrap_seed: int,
    bootstrap_resamples: int,
) -> list[dict[str, Any]]:
    values: dict[str, list[tuple[str, int, str, float]]] = defaultdict(list)
    for campaign, seed, fold_id, candidate, baseline in pairs:
        shared_metrics = (
            set(candidate.get("proxy_metrics", {}))
            & set(baseline.get("proxy_metrics", {}))
            & _CLAIMABLE_PROXY_METRICS
        )
        for metric_name in sorted(shared_metrics):
            values[metric_name].append(
                (
                    campaign,
                    seed,
                    fold_id,
                    float(candidate["proxy_metrics"][metric_name])
                    - float(baseline["proxy_metrics"][metric_name]),
                )
            )

    comparisons = []
    for metric_name in sorted(_CLAIMABLE_PROXY_METRICS):
        observations = values.get(metric_name, [])
        observed_pairs = {(campaign, seed, fold_id) for campaign, seed, fold_id, _ in observations}
        missing_pairs = _REQUIRED_PROXY_PAIRS - observed_pairs - set(provenance_mismatches)
        summary = _campaign_level_summary(
            observations,
            bootstrap_seed=bootstrap_seed,
            bootstrap_resamples=bootstrap_resamples,
            family_size=len(_CLAIMABLE_PROXY_METRICS),
        )
        if provenance_mismatches:
            decision = "blocked_provenance_mismatch"
            decision_reason = "paired rows do not share the same source and evaluator provenance"
        elif missing_pairs:
            decision = "blocked_incomplete_matrix"
            decision_reason = (
                "proxy comparison requires all 150 canonical campaign-seed-fold pairs; "
                f"observed {len(observed_pairs)}"
            )
        elif (
            summary["simultaneous_ci_95_low"] is not None
            and summary["simultaneous_ci_95_low"] > 0.0
        ):
            decision = supported_decision
            decision_reason = (
                "campaign-level paired Bonferroni simultaneous 95% bootstrap "
                "confidence interval is strictly positive"
            )
        else:
            decision = "not_supported"
            decision_reason = (
                "campaign-level paired Bonferroni simultaneous 95% bootstrap "
                "confidence interval does not show superiority"
            )
        comparisons.append(
            {
                "candidate_method_id": candidate_method_id,
                "baseline_method_id": baseline_method_id,
                "metric_name": metric_name,
                "pair_count": len(observations),
                "required_pair_count": len(_REQUIRED_PROXY_PAIRS),
                "missing_pair_count": len(missing_pairs),
                "provenance_mismatch_count": len(provenance_mismatches),
                "provenance_mismatch_coordinates": [
                    {"campaign": campaign, "seed": seed, "fold_id": fold_id}
                    for campaign, seed, fold_id in provenance_mismatches
                ],
                mean_field: summary.pop("mean"),
                **summary,
                "paired_coordinates": [
                    {"campaign": campaign, "seed": seed, "fold_id": fold_id}
                    for campaign, seed, fold_id, _ in observations
                ],
                "decision": decision,
                "decision_reason": decision_reason,
                "claim_scope": IOHUNTER_EXTERNAL_EVALUATION_SCOPE,
            }
        )
    return comparisons


def _runtime_comparison(
    pairs: Sequence[tuple[str, int, str, Mapping[str, Any], Mapping[str, Any]]],
    provenance_mismatches: Sequence[tuple[str, int, str]],
    *,
    candidate_method_id: str = "tsgs_mhcr_compact",
    bootstrap_seed: int,
    bootstrap_resamples: int,
) -> dict[str, Any]:
    observations = []
    ratios = []
    seen_executions: set[tuple[str, int]] = set()
    for campaign, seed, _fold_id, candidate, baseline in pairs:
        execution_key = (campaign, seed)
        if execution_key in seen_executions:
            continue
        seen_executions.add(execution_key)
        candidate_seconds = candidate.get("runtime_seconds")
        baseline_seconds = baseline.get("diagnostics_summary", {}).get(
            "cold_projection_seconds",
            baseline.get("runtime_seconds"),
        )
        if not isinstance(candidate_seconds, (int, float)) or not isinstance(
            baseline_seconds, (int, float)
        ):
            continue
        candidate_seconds = float(candidate_seconds)
        baseline_seconds = float(baseline_seconds)
        if not math.isfinite(candidate_seconds) or not math.isfinite(baseline_seconds):
            continue
        observations.append((campaign, seed, "all-folds", candidate_seconds - baseline_seconds))
        if baseline_seconds > 0.0:
            ratios.append(candidate_seconds / baseline_seconds)
    required_executions = {
        (campaign, seed)
        for campaign in IOHUNTER_COMPACT_CAMPAIGNS
        for seed in IOHUNTER_COMPACT_SEEDS
    }
    observed_pairs = {(campaign, seed) for campaign, seed, _fold_id, _ in observations}
    mismatched_executions = {(campaign, seed) for campaign, seed, _fold_id in provenance_mismatches}
    missing_pairs = required_executions - observed_pairs - mismatched_executions
    summary = _campaign_level_summary(
        observations,
        bootstrap_seed=bootstrap_seed,
        bootstrap_resamples=bootstrap_resamples,
    )
    if provenance_mismatches:
        decision = "blocked_provenance_mismatch"
        reason = "paired runtime rows do not share source and evaluator provenance"
    elif missing_pairs:
        decision = "blocked_incomplete_matrix"
        reason = "runtime comparison requires all 30 canonical campaign-seed pairs"
    else:
        decision = "blocked_noncomparable_measurement_boundary"
        reason = (
            "candidate wall-clock execution and production cold-projection timers "
            "do not cover identical boundaries"
        )
    return {
        "candidate_method_id": candidate_method_id,
        "baseline_method_id": "frozen_system_evidence_prior",
        "pair_count": len(observations),
        "required_pair_count": len(required_executions),
        "missing_pair_count": len(missing_pairs),
        "provenance_mismatch_count": len(provenance_mismatches),
        "mean_candidate_minus_baseline_seconds": summary.pop("mean"),
        "mean_candidate_over_baseline_ratio": float(np.mean(ratios)) if ratios else None,
        **summary,
        "decision": decision,
        "decision_reason": reason,
        "measurement_scope": "method_execution_only_excludes_shared_loader_and_evaluator",
        "measurement_boundary_comparable": False,
        "compute_budget_comparable": False,
        "adapter_scope": "post_evidence_projection_static_graph_only",
    }


def build_compact_claim_decisions(
    rows: Sequence[Mapping[str, Any]],
    *,
    bootstrap_seed: int = 0,
    bootstrap_resamples: int = 2_000,
) -> dict[str, Any]:
    successful = {
        (
            str(row["campaign"]),
            int(row["seed"]),
            str(row["fold_id"]),
            str(row["method_id"]),
        ): row
        for row in rows
        if row.get("status") == "success"
    }
    edgebank_pairs, edgebank_mismatches = _paired_method_rows(successful, "edgebank")
    system_pairs, system_mismatches = _paired_method_rows(
        successful, "frozen_system_evidence_prior"
    )
    system_score_pairs, system_score_mismatches = _paired_method_rows(
        successful, "frozen_system_account_score_prior"
    )
    ablation_pairs = {
        method_id: _paired_method_rows(successful, method_id)
        for method_id in ("no_tsgs", "no_mhcr", "no_relation_specific")
    }
    paired = _proxy_comparison_rows(
        edgebank_pairs,
        edgebank_mismatches,
        baseline_method_id="edgebank",
        candidate_method_id="tsgs_mhcr_compact",
        mean_field="mean_candidate_minus_edgebank",
        supported_decision="supported_external_account_proxy_only",
        bootstrap_seed=bootstrap_seed,
        bootstrap_resamples=bootstrap_resamples,
    )
    system_paired = _proxy_comparison_rows(
        system_pairs,
        system_mismatches,
        baseline_method_id="frozen_system_evidence_prior",
        candidate_method_id="tsgs_mhcr_compact",
        mean_field="mean_candidate_minus_baseline",
        supported_decision="supported_candidate_over_frozen_system_proxy_only",
        bootstrap_seed=bootstrap_seed,
        bootstrap_resamples=bootstrap_resamples,
    )
    for comparison in system_paired:
        comparison["adapter_scope"] = "post_evidence_projection_static_graph_only"
    system_score_paired = _proxy_comparison_rows(
        system_score_pairs,
        system_score_mismatches,
        baseline_method_id="frozen_system_account_score_prior",
        candidate_method_id="tsgs_mhcr_compact",
        mean_field="mean_candidate_minus_baseline",
        supported_decision="supported_candidate_over_frozen_system_account_score_only",
        bootstrap_seed=bootstrap_seed,
        bootstrap_resamples=bootstrap_resamples,
    )
    for comparison in system_score_paired:
        comparison["adapter_scope"] = "post_evidence_projection_static_account_ranking_only"
        comparison["equivalence_scope"] = "external_account_ranking_account_scores_only"
    paired_ablations = {
        method_id: _proxy_comparison_rows(
            pairs,
            mismatches,
            baseline_method_id=method_id,
            candidate_method_id="tsgs_mhcr_compact",
            mean_field="mean_candidate_minus_ablation",
            supported_decision="supported_candidate_over_ablation_proxy_only",
            bootstrap_seed=bootstrap_seed,
            bootstrap_resamples=bootstrap_resamples,
        )
        for method_id, (pairs, mismatches) in ablation_pairs.items()
    }
    hybrid_pairs = {
        baseline_method_id: _paired_method_rows(
            successful,
            baseline_method_id,
            candidate_method_id="magnn_leiden_hybrid_discovery",
        )
        for baseline_method_id in (
            "frozen_system_evidence_prior",
            "frozen_system_account_score_prior",
            "edgebank",
            "tsgs_mhcr_compact",
        )
    }
    paired_hybrid = {
        baseline_method_id: _proxy_comparison_rows(
            pairs,
            mismatches,
            baseline_method_id=baseline_method_id,
            candidate_method_id="magnn_leiden_hybrid_discovery",
            mean_field="mean_hybrid_minus_baseline",
            supported_decision="supported_hybrid_over_baseline_proxy_only",
            bootstrap_seed=bootstrap_seed,
            bootstrap_resamples=bootstrap_resamples,
        )
        for baseline_method_id, (pairs, mismatches) in hybrid_pairs.items()
    }
    fixed = (
        ("harmful_cib_detection", "IOHunter lacks harmful-CIB Gold labels and Stage 2 Detection was not executed"),
        ("true_coordination_edge_community_recovery", "IOHunter lacks true coordination-edge and community labels"),
        ("causal_campaign_claims", "IOHunter lacks causal campaign annotations"),
        ("observed_time_claims", "IOHunter processed graphs lack observed timestamps"),
        ("production_activation", "this matrix is research-only and the production Discovery runtime is frozen"),
        (
            "end_to_end_production_model_superiority",
            "the frozen adapter starts after evidence projection and omits production windows, null models, domain shift, and abstention",
        ),
        (
            "method_peak_memory_superiority",
            "tracemalloc and shared evaluator estimates are not comparable method-level peak-memory measurements",
        ),
        (
            "equal_compute_budget",
            "the research candidate caps selected edges while the frozen production graph core consumes the full projected graph",
        ),
    )
    return {
        "schema_version": IOHUNTER_COMPACT_CLAIM_SCHEMA_VERSION,
        "paired_external_account_proxy": paired,
        "paired_frozen_system_proxy": system_paired,
        "paired_frozen_system_account_score_proxy": system_score_paired,
        "paired_ablations": paired_ablations,
        "paired_magnn_leiden_hybrid_proxy": paired_hybrid,
        "paired_frozen_system_runtime": _runtime_comparison(
            system_pairs,
            system_mismatches,
            candidate_method_id="tsgs_mhcr_compact",
            bootstrap_seed=bootstrap_seed,
            bootstrap_resamples=bootstrap_resamples,
        ),
        "fixed_blocked_claims": [
            {"claim_id": claim_id, "decision": "blocked", "missing_capability": reason}
            for claim_id, reason in fixed
        ],
        "numerical_document_targets": [],
    }


def _write_aggregate_csv(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    fields = (
        "metric_group", "scope", "campaign", "method_id", "metric_name", "count", "mean",
        "sample_std", "ci_95_low", "ci_95_high", "inference_unit", "inference_unit_count",
        "seed_fold_policy", "bootstrap_seed", "bootstrap_resamples",
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
    folds: Sequence[str] | None = None,
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
    coordinates = compact_iohunter_matrix_coordinates(
        campaigns=campaigns,
        seeds=seeds,
        folds=folds,
        methods=methods,
    )
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
        "folds": list(dict.fromkeys(row.fold_id for row in coordinates)),
        "seed_fold_policy": "fully_crossed_orthogonal_model_seed_and_official_fold",
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
    "IOHUNTER_COMPACT_FOLDS",
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
