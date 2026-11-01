"""Propagation Analysis research package boundary."""

from __future__ import annotations

from typing import Any

from . import benchmark, runtime


PropagationAnalysisForecast = dict[str, Any]

__all__ = [
    "PropagationAnalysisForecast",
    "benchmark",
    "runtime",
]
