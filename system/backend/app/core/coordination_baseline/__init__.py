"""Canonical coordination baseline implementation boundary."""

from __future__ import annotations

from importlib import import_module
from typing import Any


_EXPORTS = {
    "account_stats": ("app.core.coordination_baseline.stats", "account_stats"),
    "detect_groups": ("app.core.coordination_baseline.detector", "detect_groups"),
    "flag_speed_share": ("app.core.coordination_baseline.detector", "flag_speed_share"),
    "generate_coordinated_network": ("app.core.coordination_baseline.network", "generate_coordinated_network"),
    "group_stats": ("app.core.coordination_baseline.stats", "group_stats"),
    "run_dyna_colm_characterize": (
        "app.core.coordination_baseline.characterization_runner",
        "run_dyna_colm_characterize",
    ),
}


def __getattr__(name: str) -> Any:
    if name not in _EXPORTS:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module_name, attribute_name = _EXPORTS[name]
    value = getattr(import_module(module_name), attribute_name)
    globals()[name] = value
    return value


__all__ = sorted(_EXPORTS)
