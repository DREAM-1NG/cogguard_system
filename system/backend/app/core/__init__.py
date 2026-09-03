"""Core product domain packages for the CogGuard backend.

Core modules are independent from FastAPI route wiring and can be called by
services, tasks, scripts, and tests through explicit package boundaries.
"""

__all__ = [
    "account_profiler",
    "bot_training",
    "analysis",
    "bot_detection",
    "trained_bot_detection",
    "coordination",
    "coordination_baseline",
    "coordination_detect",
    "coordination_discover",
    "crawler",
    "propagation",
    "propagation_analysis",
    "propagation_legacy",
    "propagation_monitoring",
    "review",
    "risk",
    "security",
]
