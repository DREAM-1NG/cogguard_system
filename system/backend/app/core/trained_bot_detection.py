"""Internal adapter for the repository-owned BotRHG checkpoint runtime."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any

from app.config import settings

__all__ = ["get_trained_botrhg_inference", "run_trained_botrhg_detection"]

_PACKAGE_NAME = "_cogguard_social_bot_detection"
_INFERENCE_CACHE: dict[tuple[str, str], Any] = {}


def run_trained_botrhg_detection(posts: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Run the approved internal checkpoint, or return ``None`` if unavailable."""

    inference = get_trained_botrhg_inference()
    if inference is None:
        return None
    return inference.predict(posts)


def get_trained_botrhg_inference() -> Any | None:
    """Load one local checkpoint after schema and fingerprint validation."""

    checkpoint_path = Path(settings.BOTRHG_CHECKPOINT_PATH).expanduser()
    if not checkpoint_path.is_file():
        return None
    try:
        package = _load_research_package()
        manifest = _load_dataset_manifest(package)
        expected_fingerprint = settings.BOTRHG_DATA_FINGERPRINT.strip()
        if expected_fingerprint and manifest != expected_fingerprint:
            return None
        key = (str(checkpoint_path.resolve()), settings.BOTRHG_DEVICE)
        if key not in _INFERENCE_CACHE:
            _INFERENCE_CACHE[key] = package.BotRHGInference(checkpoint_path, device=settings.BOTRHG_DEVICE)
        return _INFERENCE_CACHE[key]
    except (FileNotFoundError, ImportError, KeyError, OSError, RuntimeError, ValueError):
        return None


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
    spec.loader.exec_module(module)
    return module


def _load_dataset_manifest(package: Any) -> str:
    """Read the trained dataset fingerprint when a manifest is available."""

    checkpoint_path = Path(settings.BOTRHG_CHECKPOINT_PATH).expanduser()
    manifest_path = checkpoint_path.with_name("data_manifest.json")
    if not manifest_path.is_file():
        return ""
    import json

    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    return str(payload.get("data_fingerprint") or "")
