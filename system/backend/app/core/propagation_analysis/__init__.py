"""Canonical Propagation Analysis facade.

The current KT2 implementation remains split between ``app.core.propagation``
and ``app.core.propagation_legacy`` during the semantic migration window. This
package exposes the current public analysis entry points without creating
independent business logic.
"""

from app.core.propagation import build_propagation_graph
from app.core.propagation.llm_context import extract_events
from app.core.propagation.regime_model import compute_regime_posterior
from app.core.propagation.regime_model import mixture_forecast
from app.core.propagation.trend_predictor import predict_trend
from app.core.propagation.ts_features import extract_ts_features

__all__ = [
    "build_propagation_graph",
    "compute_regime_posterior",
    "extract_events",
    "extract_ts_features",
    "mixture_forecast",
    "predict_trend",
]
