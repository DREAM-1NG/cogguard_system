"""Canonical Risk Review implementation boundary.

The package owns Student/Teacher support code, review queues, active retrieval,
governance helpers, and legacy DISARM-style review evidence. The old
``app.core.risk`` package is a compatibility alias for this boundary.
"""

from importlib import import_module as _import_module
from typing import Any as _Any

_PUBLIC_MODULES = (
    "disarm_scorer",
    "ds_fusion",
    "evidence_builder",
    "active_retrieval",
    "agent_contracts",
    "agent_media",
    "agent_policy",
    "agent_provider",
    "agent_review",
    "agent_runtime",
    "community_gate",
    "gate_dataset",
    "gate_suite",
    "governance_reference",
    "graph_exporter",
    "multi_agent",
    "post_gate",
    "propagation_agent",
    "propagation_context",
    "rag",
    "review_queue",
    "review_executor",
    "legacy_smoke_adapter",
    "teacher_silver",
    "trainable_post",
    "user_gate",
    "user_mil",
    "layered_harmfulness",
    "llm_bridge",
    "phase_detector",
    "post_semantics",
    "report_builder",
)


def __getattr__(name: str) -> _Any:
    if name in _PUBLIC_MODULES:
        return _import_module(f"{__name__}.{name}")
    raise AttributeError(name)


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(_PUBLIC_MODULES))


__all__ = list(_PUBLIC_MODULES)
