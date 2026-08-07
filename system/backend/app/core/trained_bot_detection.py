"""Internal adapter for the repository-owned BotRHG checkpoint runtime."""

from __future__ import annotations

import gc
import hashlib
import importlib.util
import json
import sys
import threading
from pathlib import Path
from typing import Any

from app.config import resolve_project_path, settings
from app.core.account_model_artifact import (
    load_deployable_bundle_payloads,
    resolve_bundle_component,
)
from app.utils.exceptions import AppException

__all__ = [
    "get_trained_botrhg_inference",
    "invalidate_trained_botrhg_runtime_cache",
    "run_trained_botrhg_detection",
]

_PACKAGE_NAME = "_cogguard_social_bot_detection"
_INFERENCE_CACHE: dict[tuple[str, str, str, str], Any] = {}
_INFERENCE_CACHE_LOCK = threading.RLock()


def run_trained_botrhg_detection(
    posts: list[dict[str, Any]],
    model_source: Any | None = None,
    *,
    allow_legacy_fallback: bool = True,
) -> dict[str, Any] | None:
    """Run the approved internal checkpoint, or return ``None`` if unavailable."""

    if model_source is None and (
        not allow_legacy_fallback or not settings.account_model_local_bootstrap_allowed
    ):
        return None
    inference = get_trained_botrhg_inference(model_source, allow_legacy_fallback=allow_legacy_fallback)
    if inference is None:
        return None
    return inference.predict(posts)


def get_trained_botrhg_inference(
    model_source: Any | None = None,
    *,
    allow_legacy_fallback: bool = True,
) -> Any | None:
    """Load one local checkpoint after schema and fingerprint validation."""

    if model_source is None and (
        not allow_legacy_fallback or not settings.account_model_local_bootstrap_allowed
    ):
        return None
    try:
        package = _load_research_package()
        key = _inference_cache_key(model_source)
        with _INFERENCE_CACHE_LOCK:
            if key not in _INFERENCE_CACHE:
                checkpoint_path, checkpoint_bytes, manifest, runtime_kwargs = _verified_runtime_payload(
                    model_source
                )
                expected_fingerprint = str(
                    getattr(model_source, "data_fingerprint", None) or settings.BOTRHG_DATA_FINGERPRINT
                ).strip()
                if expected_fingerprint and manifest != expected_fingerprint:
                    return None
                factory = _runtime_factory(package)
                _release_cached_inference()
                _INFERENCE_CACHE[key] = factory(
                    checkpoint_path,
                    device=settings.BOTRHG_DEVICE,
                    checkpoint_bytes=checkpoint_bytes,
                    **runtime_kwargs,
                )
            return _INFERENCE_CACHE[key]
    except (AppException, AttributeError, FileNotFoundError, ImportError, KeyError, OSError, RuntimeError, ValueError):
        return None


def invalidate_trained_botrhg_runtime_cache() -> None:
    """Release cached account-detector runtime state after a pointer change."""

    with _INFERENCE_CACHE_LOCK:
        _release_cached_inference()


def _verified_runtime_payload(
    model_source: Any | None,
) -> tuple[Path, bytes, str, dict[str, Any]]:
    if _is_governed_source(model_source):
        bundle_dir = Path(str(getattr(model_source, "artifact_uri", ""))).expanduser().resolve()
        if not bundle_dir.is_dir():
            raise ValueError("governed account model runtime requires a deployable bundle")
        bundle_manifest, payloads = load_deployable_bundle_payloads(bundle_dir)
        checkpoint_path = resolve_bundle_component(bundle_dir, "detector")
        source_schema = str(bundle_manifest.get("source_schema") or "")
        expected_schema = str(getattr(model_source, "source_schema", "") or "")
        if expected_schema and source_schema != expected_schema:
            raise ValueError("active pointer schema does not match the deployable bundle")
        checkpoint_bytes = payloads["detector"]
        runtime_kwargs = _bundle_runtime_component_kwargs(
            bundle_dir,
            bundle_manifest,
            payloads,
        )
        data_fingerprint = _dataset_fingerprint_from_bytes(payloads.get("data_fingerprints"))
    else:
        checkpoint_path = resolve_project_path(
            getattr(model_source, "checkpoint_path", None) or settings.BOTRHG_CHECKPOINT_PATH
        )
        if not checkpoint_path.is_file():
            raise FileNotFoundError(checkpoint_path)
        checkpoint_bytes = checkpoint_path.read_bytes()
        runtime_kwargs = _runtime_component_kwargs(model_source)
        data_fingerprint = _load_dataset_manifest(checkpoint_path)

    expected_hash = str(getattr(model_source, "artifact_hash", "") or "").strip().lower()
    actual_hash = hashlib.sha256(checkpoint_bytes).hexdigest()
    if expected_hash and actual_hash != expected_hash:
        raise ValueError("account model detector bytes do not match the active pointer")
    return checkpoint_path, checkpoint_bytes, data_fingerprint, runtime_kwargs


def _is_governed_source(model_source: Any | None) -> bool:
    return bool(
        model_source is not None
        and str(getattr(model_source, "governance_status", "") or "") == "governed_active"
    )


def _inference_cache_key(model_source: Any | None) -> tuple[str, str, str, str]:
    if model_source is None:
        checkpoint_path = resolve_project_path(settings.BOTRHG_CHECKPOINT_PATH)
        if not checkpoint_path.is_file():
            return ("bootstrap", str(checkpoint_path), "missing", settings.BOTRHG_DEVICE)
        checkpoint_hash = hashlib.sha256(checkpoint_path.read_bytes()).hexdigest()
        return ("bootstrap", str(checkpoint_path), checkpoint_hash, settings.BOTRHG_DEVICE)
    return (
        str(getattr(model_source, "model_version", "bootstrap")),
        str(getattr(model_source, "artifact_hash", "")),
        str(getattr(model_source, "pointer_revision", 0)),
        settings.BOTRHG_DEVICE,
    )


def _bundle_runtime_component_kwargs(
    bundle_dir: Path,
    manifest: dict[str, Any],
    payloads: dict[str, bytes],
) -> dict[str, Any]:
    source_schema = str(manifest.get("source_schema") or "").strip()
    paths = {
        f"{role}_path": str(resolve_bundle_component(bundle_dir, role))
        for role in ("encoder", "feature_schema", "calibration")
    }
    return {
        **paths,
        "encoder_bytes": payloads["encoder"],
        "feature_schema_bytes": payloads["feature_schema"],
        "calibration_bytes": payloads["calibration"],
        "expected_source_schema": source_schema,
    }


def _runtime_component_kwargs(model_source: Any | None) -> dict[str, Any]:
    if model_source is None:
        return {}
    source_schema = str(getattr(model_source, "source_schema", "") or "").strip()
    paths = {
        "encoder_path": getattr(model_source, "encoder_path", None),
        "feature_schema_path": getattr(model_source, "feature_schema_path", None),
        "calibration_path": getattr(model_source, "calibration_path", None),
    }
    if source_schema == "cogguard.botrhg.account.v3" and not all(paths.values()):
        raise ValueError("governed account.v3 runtime requires every verified bundle component")
    if not any(paths.values()):
        return {}
    if not all(paths.values()):
        raise ValueError("account model bundle runtime components are incomplete")
    return {
        **paths,
        "encoder_bytes": Path(str(paths["encoder_path"])).read_bytes(),
        "feature_schema_bytes": Path(str(paths["feature_schema_path"])).read_bytes(),
        "calibration_bytes": Path(str(paths["calibration_path"])).read_bytes(),
        "expected_source_schema": source_schema,
    }


def _runtime_factory(package: Any) -> Any:
    factory = getattr(package, "create_botrhg_inference", None)
    if factory is None:
        factory = getattr(package, "BotRHGInference", None)
    if not callable(factory):
        raise AttributeError("internal BotRHG research package has no inference factory")
    return factory


def _release_cached_inference() -> None:
    _INFERENCE_CACHE.clear()
    gc.collect()
    try:
        import torch

        if torch.cuda.is_available():
            torch.cuda.empty_cache()
    except (ImportError, RuntimeError):
        pass


def _load_research_package() -> Any:
    system_root = Path(__file__).resolve().parents[3]
    package_dir = system_root / "research" / "social_bot_detection"
    init_file = package_dir / "__init__.py"
    if not init_file.is_file():
        raise ImportError(f"internal BotRHG research package not found: {init_file}")
    existing = sys.modules.get(_PACKAGE_NAME)
    if existing is not None:
        return existing
    spec = importlib.util.spec_from_file_location(
        _PACKAGE_NAME,
        init_file,
        submodule_search_locations=[str(package_dir)],
    )
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load internal BotRHG package from {init_file}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[_PACKAGE_NAME] = module
    try:
        spec.loader.exec_module(module)
    except Exception:
        if sys.modules.get(_PACKAGE_NAME) is module:
            sys.modules.pop(_PACKAGE_NAME, None)
        raise
    return module


def _load_dataset_manifest(checkpoint_path: Path) -> str:
    """Read the trained dataset fingerprint when a manifest is available."""

    bundle_fingerprints = checkpoint_path.with_name("data_fingerprints.json")
    if bundle_fingerprints.is_file():
        payload = json.loads(bundle_fingerprints.read_text(encoding="utf-8"))
        if isinstance(payload, dict) and len(payload) == 1:
            return str(next(iter(payload.values())))
    manifest_path = checkpoint_path.with_name("data_manifest.json")
    if not manifest_path.is_file():
        return ""
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    return str(payload.get("data_fingerprint") or "")


def _dataset_fingerprint_from_bytes(payload_bytes: bytes | None) -> str:
    if payload_bytes is None:
        return ""
    payload = json.loads(payload_bytes.decode("utf-8"))
    if isinstance(payload, dict) and len(payload) == 1:
        return str(next(iter(payload.values())))
    return ""
