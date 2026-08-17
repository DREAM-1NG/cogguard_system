from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from dataclasses import replace
from pathlib import Path
from typing import Any, Mapping

from app.config import PROJECT_ROOT, settings
from app.services.analysis_governance_service import verify_registered_artifact

_DETECTION_MODULE_NAME = "_cogguard_runtime_coordination_detect"


def _load_detection_runtime_modules() -> Any:
    cached = sys.modules.get(_DETECTION_MODULE_NAME)
    if cached is not None:
        return cached
    package_dir = PROJECT_ROOT / "research" / "coordination_detect"
    init_file = package_dir / "__init__.py"
    if not init_file.exists():
        raise ImportError(f"Coordination detection research package not found: {init_file}")
    spec = importlib.util.spec_from_file_location(
        _DETECTION_MODULE_NAME,
        init_file,
        submodule_search_locations=[str(package_dir)],
    )
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load Coordination detection package from {init_file}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[_DETECTION_MODULE_NAME] = module
    spec.loader.exec_module(module)
    for submodule_name in ("contracts", "engine", "features", "learned", "heuristic_baseline", "socgfm"):
        submodule_spec = importlib.util.spec_from_file_location(
            f"{_DETECTION_MODULE_NAME}.{submodule_name}",
            package_dir / f"{submodule_name}.py",
        )
        if submodule_spec is None or submodule_spec.loader is None:
            continue
        submodule = importlib.util.module_from_spec(submodule_spec)
        sys.modules[f"{_DETECTION_MODULE_NAME}.{submodule_name}"] = submodule
        submodule_spec.loader.exec_module(submodule)
        setattr(module, submodule_name, submodule)
    return module


class CoordinationDetectionRuntime:
    def predict(
        self,
        batch: Any,
        feature_rows: Mapping[str, Mapping[str, float]] | None,
        active_model: dict[str, Any] | None,
    ) -> Any:
        detection = _load_detection_runtime_modules()
        if not active_model or str(active_model.get("status") or "").strip().lower() != "active":
            return _model_unavailable("coordination_detection", "coordination_detection_active_model_missing")
        if str(active_model.get("technology") or "").strip() != "coordination_detection":
            return _model_unavailable("coordination_detection", "coordination_detection_active_model_mismatch")
        try:
            verified = verify_registered_artifact(
                artifact_uri=str(active_model.get("artifact_uri") or ""),
                expected_hash=str(active_model.get("artifact_hash") or ""),
                technology="coordination_detection",
                artifact_root=settings.MODEL_ARTIFACT_ROOT,
            )
        except ValueError as exc:
            return _model_unavailable("coordination_detection", f"coordination_detection_active_model_invalid:{exc}")
        if _is_forbidden_drive(verified.artifact_path) or _is_forbidden_drive(verified.manifest_path) or _is_forbidden_drive(verified.checkpoint_path):
            return _model_unavailable("coordination_detection", "coordination_detection_forbidden_drive_path")
        backend = _active_detection_backend(active_model, verified.manifest)
        if backend != "socgfm_cross_attention":
            return _model_unavailable(
                "coordination_detection",
                f"coordination_detection_active_model_not_socgfm:{backend}",
            )
        try:
            artifact = detection.socgfm.SocGFMCrossAttentionArtifact.from_json(verified.checkpoint_path)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            return _model_unavailable(
                "coordination_detection",
                f"coordination_detection_socgfm_artifact_load_failed:{exc.__class__.__name__}",
            )
        return self._predict_socgfm(
            detection,
            artifact,
            batch,
            feature_rows,
            verified.checkpoint_sha256,
        )

    def _predict_socgfm(
        self,
        detection: Any,
        artifact: Any,
        batch: Any,
        feature_rows: Mapping[str, Mapping[str, float]] | None,
        checkpoint_sha256: str,
    ) -> Any:
        if batch is None:
            return _model_unavailable(
                "coordination_detection",
                "coordination_detection_batch_missing",
                model_role="primary_socgfm_cross_attention",
            )
        batch.validate()
        if not batch.candidate_clusters:
            return {
                "technology": "coordination_detection",
                "status": "data_insufficient",
                "model_version": artifact.model_version,
                "model_role": artifact.model_role,
                "fallback": False,
                "blocking_reason": "no_candidate_clusters",
                "source_batch_id": batch.batch_id,
                "source_batch_fingerprint": batch.batch_fingerprint,
            }
        detector = detection.socgfm.SocGFMCrossAttentionDetector(artifact)
        try:
            prediction = detector.predict(batch, dict(feature_rows or {}))
        except ValueError as exc:
            return _model_unavailable(
                "coordination_detection",
                f"coordination_detection_socgfm_prediction_failed:{exc}",
                model_role=artifact.model_role,
            )
        return _normalize_prediction_hash(prediction, checkpoint_sha256)


def _active_detection_backend(active_model: Mapping[str, Any], manifest: Mapping[str, Any]) -> str:
    values = (
        manifest.get("backend"),
        manifest.get("model"),
        active_model.get("model"),
        active_model.get("version"),
    )
    normalized = " ".join(str(value or "").strip().lower() for value in values)
    return "socgfm_cross_attention" if "socgfm_cross_attention" in normalized else "unsupported_non_socgfm"


def _model_unavailable(
    technology: str,
    reason: str,
    *,
    model_role: str = "primary_socgfm_cross_attention",
) -> dict[str, Any]:
    return {
        "technology": technology,
        "status": "model_unavailable",
        "fallback": False,
        "blocking_reason": reason,
        "model_version": "unavailable",
        "model_role": model_role,
    }


def _is_forbidden_drive(path: Path) -> bool:
    drive = path.drive.upper()
    return drive == "C:"


def _normalize_prediction_hash(batch: Any, checkpoint_sha256: str) -> Any:
    if not hasattr(batch, "verdicts"):
        return batch
    verdicts = tuple(
        replace(verdict, artifact_hash=checkpoint_sha256)
        if getattr(verdict, "artifact_hash", None) is not None
        else verdict
        for verdict in batch.verdicts
    )
    return replace(batch, model_artifact_hash=checkpoint_sha256, verdicts=verdicts)


__all__ = ["CoordinationDetectionRuntime", "_load_detection_runtime_modules"]
