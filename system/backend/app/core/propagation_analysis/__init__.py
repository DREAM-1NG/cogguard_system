"""Canonical Propagation Analysis facade.

The current observed-analysis implementation remains split between
``app.core.propagation`` and ``app.core.propagation_legacy`` during the
semantic migration window. This package exposes public observed-analysis entry
points without exposing legacy trend-prediction scaffolds.
"""

from app.core.propagation import build_propagation_graph

__all__ = [
    "build_propagation_graph",
]
