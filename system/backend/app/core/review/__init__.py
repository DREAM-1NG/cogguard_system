"""Canonical KT3 Review implementation boundary.

The package owns Student/Teacher support code, review queues, active retrieval,
governance helpers, and legacy DISARM-style review evidence. The old
``app.core.risk`` package is a compatibility alias for this boundary.
"""

__all__ = [
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
]
