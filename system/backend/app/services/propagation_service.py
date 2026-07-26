"""Backward-compatible Propagation Analysis service facade.

Observed propagation analysis is a system capability aligned with product
propagation analysis. Prediction is handled by the macro/micro sequence model
service.
New code should import ``propagation_observation_service`` for observed
analysis and ``propagation_model_service`` for predictive model calls.
"""

from __future__ import annotations

from app.services.propagation_model_service import (
    predict_current_event_model,
    predict_propagation_model_event,
)
from app.services.propagation_observation_service import (
    analyze_observed_propagation,
    analyze_propagation,
)


__all__ = [
    "analyze_observed_propagation",
    "analyze_propagation",
    "predict_current_event_model",
    "predict_propagation_model_event",
]
