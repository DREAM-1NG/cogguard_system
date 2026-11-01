"""Propagation Analysis package.

This package exposes spread, trend, source-tracing, and scope-estimation logic
while preserving the legacy propagation graph entry point.

``propagation_legacy`` imports from this package, so the compatibility entry
point is resolved lazily to keep that dependency acyclic.
"""


def build_propagation_graph(*args, **kwargs):
    from app.core.propagation_legacy import build_propagation_graph as _build_propagation_graph

    return _build_propagation_graph(*args, **kwargs)



__all__ = ["build_propagation_graph"]
