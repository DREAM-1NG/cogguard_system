"""Compatibility package for `app.core.review`.

The Review package is the canonical KT3 implementation boundary. This package
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
    "kt3_active_retrieval",
    "kt3_agent_policy",
    "kt3_agent_review",
    "kt3_community_gate",
    "kt3_gate_dataset",
    "kt3_gate_suite",
    "kt3_governance_reference",
    "kt3_graph_exporter",
    "kt3_multi_agent",
    "kt3_post_gate",
    "kt3_rag",
    "kt3_reviewer",
    "kt3_review_executor",
    "kt3_trainable_post",
    "kt3_user_gate",
    "kt3_user_mil",
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