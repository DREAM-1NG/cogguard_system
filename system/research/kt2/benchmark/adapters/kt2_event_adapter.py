"""Compatibility wrapper for system/research/propagation_analysis event adapter."""

from __future__ import annotations

import importlib.util as _importlib_util
import sys as _sys
from pathlib import Path as _Path

_TARGET = _Path(__file__).resolve().parent / "../../../propagation_analysis/benchmark/adapters/kt2_event_adapter.py"
_MODULE_NAME = f"_cogguard_compat_{_TARGET.stem}_{abs(hash(str(_TARGET)))}"
_spec = _importlib_util.spec_from_file_location(_MODULE_NAME, _TARGET)
if _spec is None or _spec.loader is None:
    raise ImportError(f"Cannot load compatibility target: {_TARGET}")
_module = _importlib_util.module_from_spec(_spec)
_sys.modules[_MODULE_NAME] = _module
_spec.loader.exec_module(_module)
globals().update(_module.__dict__)
__all__ = list(getattr(_module, "__all__", [name for name in globals() if not name.startswith("_")]))