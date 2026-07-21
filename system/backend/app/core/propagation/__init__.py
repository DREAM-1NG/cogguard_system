"""Propagation Analysis package.

This package exposes spread, trend, source-tracing, and scope-estimation logic
while preserving the legacy propagation graph entry point.
"""

# Public compatibility entry point from the legacy module.
from app.core.propagation_legacy import build_propagation_graph

__all__ = ["build_propagation_graph"]
