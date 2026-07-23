"""Compatibility package for `app.core.review`.

The Review package is the canonical Review implementation boundary. This package
is retained for one release window so legacy imports resolve to the same module
objects instead of copying business logic.
"""

from importlib import import_module as _import_module
from typing import Any as _Any

_CANONICAL_PACKAGE = "app.core.review"
_COMPAT_MODULES = (
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
    "selective_student",
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
    if name in _COMPAT_MODULES:
        return _import_module(f"{_CANONICAL_PACKAGE}.{name}")
    raise AttributeError(name)


__all__ = list(_COMPAT_MODULES)
