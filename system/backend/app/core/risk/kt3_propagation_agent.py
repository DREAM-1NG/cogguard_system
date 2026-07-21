"""PropagationTreeAgent evidence boundary and prompt contract.

This module owns the KT3 propagation-review seam. It keeps thread evidence,
prompt constraints, and routing eligibility together so the large manual-agent
runner does not duplicate propagation-specific rules.
"""

from __future__ import annotations

from typing import Any


PROPAGATION_AGENT_NAME = "PropagationTreeAgent"
PROPAGATION_AGENT_REPORT_SECTIONS = [
    "输入证据状态",
    "树结构指标",
    "关键分支证据",
    "态度立场变化",
    "异常放大与缺证据",
    "给综合裁决的传播结论",
]

__all__ = [
    "PROPAGATION_AGENT_NAME",
    "PROPAGATION_AGENT_REPORT_SECTIONS",
    "build_propagation_agent_output_contract",
    "build_propagation_agent_prompt_note",
    "has_propagation_tree_context",
    "select_propagation_context",
]


def build_propagation_agent_prompt_note(agent_name: str) -> str:
    if agent_name != PROPAGATION_AGENT_NAME:
        return ""
    return (
        "\nFor PropagationTreeAgent: use a field-constrained Chinese report, not "
        "free-form essay writing. The authoritative evidence source is "
        "selected_context.propagation_context. Use the required headings exactly, "
        "and under each heading write short key-value lines. Every propagation "
        "claim must cite one supplied evidence field, such as "
        "tree_metrics.*, key_branches[].branch_id, central_nodes[].node_id, "
        "temporal_snapshots[].snapshot_id, evidence_nodes[].node_id, "
        "stance_by_depth.*, or graph_summary.edge_types. If "
        "has_thread_context=false or required fields are missing, state "
        "evidence is insufficient and do not infer diffusion, coordination, "
        "virality, or cross-platform amplification from claim lists, reaction "
        "counts, or repeated wording alone. Keep the report concise and separate "
        "observed structure from human verification needs.\n"
    )


def build_propagation_agent_output_contract(agent_name: str) -> dict[str, Any]:
    if agent_name != PROPAGATION_AGENT_NAME:
        return {}
    return {
        "format": "fixed_headed_chinese_report",
        "main_output_is_json": False,
        "required_headings": list(PROPAGATION_AGENT_REPORT_SECTIONS),
        "line_style": "每个标题下使用短字段行，例如 `结论：...`、`证据字段引用：...`、`证据不足：...`。",
        "evidence_source": "selected_context.propagation_context",
        "allowed_evidence_refs": [
            "tree_metrics.*",
            "key_branches[].branch_id",
            "central_nodes[].node_id",
            "temporal_snapshots[].snapshot_id",
            "evidence_nodes[].node_id",
            "stance_by_depth.*",
            "graph_summary.edge_types",
            "missing_fields",
        ],
        "must_not_infer_from": [
            "claim_rank without thread edges",
            "reaction_count without node-edge context",
            "similar wording without repost/quote/reply edges",
        ],
        "final_section_fields": ["传播结论", "置信度", "升级建议", "不可推断项"],
    }


def select_propagation_context(report: dict[str, Any], selected_tree_ids: list[str]) -> dict[str, Any]:
    kt3 = report.get("kt3_harmfulness") or {}
    graph_export = kt3.get("graph_export") or {}
    post_semantics = report.get("post_semantics") or {}
    propagation_context = kt3.get("propagation_context") if isinstance(kt3.get("propagation_context"), dict) else {}
    if propagation_context:
        return {
            **propagation_context,
            "selected_tree_ids": selected_tree_ids or _as_list(propagation_context.get("tree_id")),
            "claim_rank": _as_list(propagation_context.get("claim_rank")) or _as_list(_get(kt3, "global_summary", "claim_rank"))[:10],
            "graph_summary": propagation_context.get("graph_summary") or graph_export.get("summary") or {},
            "post_semantics_summary": propagation_context.get("post_semantics_summary") or post_semantics.get("summary") or {},
        }
    return {
        "selected_tree_ids": selected_tree_ids,
        "claim_rank": _as_list(_get(kt3, "global_summary", "claim_rank"))[:10],
        "graph_summary": graph_export.get("summary") or {},
        "post_semantics_summary": post_semantics.get("summary") or {},
        "note": (
            "If PHEME structure/reactions are available, pass their parsed tree "
            "overview here. Current runtime may only contain graph summaries."
        ),
    }


def has_propagation_tree_context(report: dict[str, Any]) -> bool:
    kt3 = report.get("kt3_harmfulness") or {}
    propagation_context = kt3.get("propagation_context") if isinstance(kt3.get("propagation_context"), dict) else {}
    if propagation_context:
        tree_metrics = propagation_context.get("tree_metrics") if isinstance(propagation_context.get("tree_metrics"), dict) else {}
        return bool(
            propagation_context.get("has_thread_context")
            or int(tree_metrics.get("edge_count") or 0) > 0
            or int(tree_metrics.get("node_count") or 0) > 1
        )
    graph_summary = _get(kt3, "graph_export", "summary") or {}
    return bool(
        graph_summary.get("graph_native_ready")
        or int(graph_summary.get("edge_count") or graph_summary.get("edges") or 0) > 0
    )


def _get(mapping: dict[str, Any], *path: str) -> Any:
    value: Any = mapping
    for part in path:
        if not isinstance(value, dict):
            return None
        value = value.get(part)
    return value


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]
