from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any

from app.config import PROJECT_ROOT, settings
from app.core.analysis.contracts import EventSnapshot

_MODULE_NAME = "_cogguard_research_coordination_discover"


def try_load_coordination_discover_result(
    snapshot: EventSnapshot,
    options: dict[str, Any] | None = None,
) -> tuple[dict[str, Any] | None, str | None]:
    options = dict(options or {})
    mode = str(options.get("kt1_mode") or options.get("mode") or settings.KT1_MODE).strip().lower()
    if mode in {"evidence_runtime_v2", "fallback", "disabled", "off"}:
        return None, "kt1_research_disabled"

    artifact_dir = _artifact_dir(snapshot=snapshot, options=options)
    if artifact_dir is None:
        return None, "kt1_artifact_not_found"

    try:
        discover = _load_coordination_discover_module()
        loaded = discover.load_discover_artifact(artifact_dir)
    except (FileNotFoundError, ImportError, RuntimeError, OSError, ValueError) as exc:
        return None, f"kt1_artifact_load_failed:{exc.__class__.__name__}"

    manifest = dict(loaded.get("manifest") or {})
    mismatch = discover.validate_manifest_for_snapshot(manifest, data_fingerprint=snapshot.data_fingerprint)
    if mismatch:
        return None, mismatch

    coordination_result = loaded.get("coordination_result")
    if isinstance(coordination_result, dict):
        result = dict(coordination_result)
    else:
        result = discover.export_coordination_result(dict(loaded.get("result") or {}))

    result["fallback"] = False
    result["fallback_reason"] = None
    result["artifact_dir"] = str(artifact_dir)
    result.setdefault("artifact_manifest", manifest)
    return result, None


def _artifact_dir(*, snapshot: EventSnapshot, options: dict[str, Any]) -> Path | None:
    explicit_dir = str(options.get("artifact_dir") or "").strip()
    if explicit_dir:
        path = Path(explicit_dir)
        return path if path.exists() else None

    artifact_root = Path(str(options.get("artifact_root") or settings.KT1_ARTIFACT_ROOT))
    if not artifact_root.exists():
        return None

    discover = _load_coordination_discover_module()
    return discover.find_snapshot_artifact(
        artifact_root=artifact_root,
        snapshot_id=snapshot.snapshot_id,
        data_fingerprint=snapshot.data_fingerprint,
    )


def _load_coordination_discover_module() -> Any:
    cached = sys.modules.get(_MODULE_NAME)
    if cached is not None:
        return cached

    package_dir = PROJECT_ROOT / "research" / "coordination_discover"
    init_file = package_dir / "__init__.py"
    if not init_file.exists():
        raise ImportError(f"Coordination Discover research package not found: {init_file}")
    spec = importlib.util.spec_from_file_location(
        _MODULE_NAME,
        init_file,
        submodule_search_locations=[str(package_dir)],
    )
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load Coordination Discover research package from {init_file}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[_MODULE_NAME] = module
    spec.loader.exec_module(module)
    return module


try_load_kt1_research_result = try_load_coordination_discover_result

__all__ = [
    "try_load_coordination_discover_result",
    "try_load_kt1_research_result",
]
