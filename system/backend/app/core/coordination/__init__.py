"""Compatibility package for `app.core.coordination_baseline`.

The Coordination Baseline package is the canonical CooRTweet-style fallback
boundary. This package is retained for one release window for legacy imports,
while newer research adapters use the governed Coordination Discover / Detect
method language.
"""

from importlib import import_module as _import_module
from typing import Any as _Any

_CANONICAL_PACKAGE = "app.core.coordination_baseline"
_COMPAT_MODULES = (
    "characterization",
    "characterization_runner",
    "deep_graph",
    "detector",
    "io_reproduction",
    "network",
    "pretrained_detect",
    "stats",
    "twitter_io_experiment",
)


def __getattr__(name: str) -> _Any:
    if name in _COMPAT_MODULES:
        return _import_module(f"{_CANONICAL_PACKAGE}.{name}")
    raise AttributeError(name)


# Preserve the historical package-level convenience exports.
from app.core.coordination_baseline.detector import detect_groups, flag_speed_share
from app.core.coordination_baseline.network import generate_coordinated_network
from app.core.coordination_baseline.stats import account_stats, group_stats
from app.core.coordination_baseline.characterization_runner import run_dyna_colm_characterize

__all__ = [
    "account_stats",
    "detect_groups",
    "flag_speed_share",
    "generate_coordinated_network",
    "group_stats",
    "run_dyna_colm_characterize",
    *_COMPAT_MODULES,
]