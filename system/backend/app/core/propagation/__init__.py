"""Public entry points for propagation analysis."""


def build_propagation_graph(*args, **kwargs):
    from app.core.propagation_legacy import build_propagation_graph as _build_propagation_graph

    return _build_propagation_graph(*args, **kwargs)


__all__ = ["build_propagation_graph"]
