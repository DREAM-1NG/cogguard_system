from __future__ import annotations

import hashlib
import json
from dataclasses import is_dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .contracts import (
    FALLBACK_POLICY,
    COORDINATION_DISCOVER_MODEL_VERSION,
    DEPRECATED_COORDINATION_DISCOVER_MODEL_VERSIONS,
    MODALITY_POLICY,
    DiscoverResult,
    CoordinationDiscoverArtifactManifest,
)

MANIFEST_FILENAME = "manifest.json"
DISCOVER_RESULT_FILENAME = "discover_result.json"
COORDINATION_RESULT_FILENAME = "coordination_result.json"
METRICS_FILENAME = "metrics.json"
CHECKPOINT_FILENAME = "checkpoint.pt"


def config_hash(config: Any) -> str:
    return hashlib.sha256(_json_dumps(_to_jsonable(config)).encode("utf-8")).hexdigest()


def create_manifest(
    *,
    data_fingerprint: str,
    model_version: str = COORDINATION_DISCOVER_MODEL_VERSION,
    config: Any,
    artifact_dir: str | Path,
    source_dataset: str = "",
    source_event: str = "",
    status: str = "ok",
    fallback_policy: str = FALLBACK_POLICY,
    modality_policy: str = MODALITY_POLICY,
    partition_backend: str = "leiden",
) -> CoordinationDiscoverArtifactManifest:
    artifact_path = Path(artifact_dir)
    return CoordinationDiscoverArtifactManifest(
        data_fingerprint=data_fingerprint,
        model_version=model_version,
        config_hash=config_hash(config),
        source_dataset=source_dataset,
        source_event=source_event,
        checkpoint_path=str((artifact_path / CHECKPOINT_FILENAME).resolve()),
        metrics_path=str((artifact_path / METRICS_FILENAME).resolve()),
        result_path=str((artifact_path / DISCOVER_RESULT_FILENAME).resolve()),
        generated_at=datetime.now(timezone.utc).isoformat(),
        fallback_policy=fallback_policy,
        modality_policy=modality_policy,
        partition_backend=partition_backend,
        status=status,
    )


def write_discover_artifact(
    result: DiscoverResult,
    *,
    artifact_dir: str | Path,
    coordination_result: dict[str, Any] | None = None,
) -> CoordinationDiscoverArtifactManifest:
    artifact_path = Path(artifact_dir)
    artifact_path.mkdir(parents=True, exist_ok=True)

    result_payload = result.to_dict()
    _write_json(artifact_path / DISCOVER_RESULT_FILENAME, result_payload)
    _write_json(artifact_path / METRICS_FILENAME, result.audit_metrics)
    if coordination_result is not None:
        _write_json(artifact_path / COORDINATION_RESULT_FILENAME, coordination_result)

    # Hash the files that are actually written. A manifest without byte-level
    # integrity is only descriptive metadata and cannot support reproducibility.
    result.manifest.artifact_hashes = {
        name: _sha256_file(artifact_path / name)
        for name in (
            DISCOVER_RESULT_FILENAME,
            METRICS_FILENAME,
            COORDINATION_RESULT_FILENAME,
        )
        if (artifact_path / name).is_file()
    }
    _write_json(artifact_path / MANIFEST_FILENAME, result.manifest.to_dict())
    return result.manifest


def load_discover_artifact(artifact_dir: str | Path) -> dict[str, Any]:
    artifact_path = Path(artifact_dir)
    manifest_path = artifact_path / MANIFEST_FILENAME
    if not manifest_path.exists():
        raise FileNotFoundError(f"Coordination Discover manifest not found: {manifest_path}")
    manifest = CoordinationDiscoverArtifactManifest.from_dict(_read_json(manifest_path))
    integrity_error = _validate_artifact_hashes(artifact_path, manifest.artifact_hashes)
    if integrity_error:
        raise ValueError(integrity_error)
    result_path = Path(manifest.result_path) if manifest.result_path else artifact_path / DISCOVER_RESULT_FILENAME
    if not result_path.exists():
        result_path = artifact_path / DISCOVER_RESULT_FILENAME
    result = _read_json(result_path)
    coordination_path = artifact_path / COORDINATION_RESULT_FILENAME
    coordination_result = _read_json(coordination_path) if coordination_path.exists() else None
    return {
        "manifest": manifest.to_dict(),
        "result": result,
        "coordination_result": coordination_result,
        "artifact_dir": str(artifact_path.resolve()),
    }


def find_snapshot_artifact(*, artifact_root: str | Path, snapshot_id: str, data_fingerprint: str) -> Path | None:
    root = Path(artifact_root)
    candidates = [
        root,
        root / snapshot_id,
        root / data_fingerprint,
        root / f"{snapshot_id}-{data_fingerprint[:12]}",
    ]
    for candidate in candidates:
        if (candidate / MANIFEST_FILENAME).exists():
            return candidate
    if not root.exists():
        return None
    for manifest_path in root.glob("*/manifest.json"):
        try:
            manifest = CoordinationDiscoverArtifactManifest.from_dict(_read_json(manifest_path))
        except (OSError, ValueError, TypeError):
            continue
        if manifest.data_fingerprint == data_fingerprint:
            return manifest_path.parent
    return None


def validate_manifest_for_snapshot(manifest: dict[str, Any], *, data_fingerprint: str) -> str | None:
    if str(manifest.get("data_fingerprint") or "") != data_fingerprint:
        return "artifact_fingerprint_mismatch"
    model_version = str(manifest.get("model_version") or "")
    if model_version in DEPRECATED_COORDINATION_DISCOVER_MODEL_VERSIONS:
        return f"artifact_model_deprecated:{DEPRECATED_COORDINATION_DISCOVER_MODEL_VERSIONS[model_version]}"
    if str(manifest.get("modality_policy") or "") != MODALITY_POLICY:
        return "artifact_modality_policy_mismatch"
    if str(manifest.get("partition_backend") or "") != "leiden":
        return "artifact_partition_backend_not_leiden"
    if str(manifest.get("status") or "ok") != "ok":
        return "artifact_status_not_ok"
    claimability = str(manifest.get("claimability") or "non_claimable")
    if claimability not in {"claimable", "non_claimable"}:
        return "artifact_claimability_invalid"
    return None


def _write_json(path: Path, payload: Any) -> None:
    path.write_text(_json_dumps(_to_jsonable(payload)), encoding="utf-8")


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _validate_artifact_hashes(artifact_path: Path, hashes: dict[str, str]) -> str | None:
    for name, expected in hashes.items():
        path = artifact_path / name
        if not path.is_file():
            return f"artifact_integrity_missing:{name}"
        if _sha256_file(path) != str(expected).lower():
            return f"artifact_integrity_mismatch:{name}"
    return None


def _json_dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True, default=str)


def _to_jsonable(value: Any) -> Any:
    if hasattr(value, "to_dict"):
        return value.to_dict()
    if is_dataclass(value):
        return {key: _to_jsonable(item) for key, item in value.__dict__.items()}
    if isinstance(value, dict):
        return {str(key): _to_jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_to_jsonable(item) for item in value]
    return value


__all__ = [
    "CHECKPOINT_FILENAME",
    "COORDINATION_RESULT_FILENAME",
    "DISCOVER_RESULT_FILENAME",
    "MANIFEST_FILENAME",
    "config_hash",
    "create_manifest",
    "find_snapshot_artifact",
    "load_discover_artifact",
    "validate_manifest_for_snapshot",
    "write_discover_artifact",
]
