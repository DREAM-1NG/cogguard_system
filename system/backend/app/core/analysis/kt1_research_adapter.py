"""Compatibility wrapper for ``app.core.analysis.coordination_discover_adapter``."""

from app.core.analysis.coordination_discover_adapter import (
    try_load_coordination_discover_result,
    try_load_kt1_research_result,
)

__all__ = [
    "try_load_coordination_discover_result",
    "try_load_kt1_research_result",
]
