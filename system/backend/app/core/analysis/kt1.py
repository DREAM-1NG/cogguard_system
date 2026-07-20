"""Compatibility wrapper for ``app.core.analysis.coordination_discover``."""

from app.core.analysis.coordination_discover import (
    analyze_coordination_discover_snapshot,
    analyze_kt1_snapshot,
    build_coordination_discover_evidence_edges,
    build_kt1_evidence_edges,
)

__all__ = [
    "analyze_coordination_discover_snapshot",
    "analyze_kt1_snapshot",
    "build_coordination_discover_evidence_edges",
    "build_kt1_evidence_edges",
]
