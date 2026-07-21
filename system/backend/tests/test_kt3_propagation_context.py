from __future__ import annotations

from app.core.risk.kt3_agent_review import _has_propagation_tree_context
from app.core.risk.kt3_agent_review import _agent_output_contract
from app.core.risk.kt3_agent_review import _agent_system_prompt
from app.core.risk.kt3_agent_review import _select_propagation_context
from app.core.risk.kt3_agent_contracts import AGENT_REPORT_SECTIONS
from app.core.risk.kt3_agent_contracts import build_agent_system_prompt
from app.core.risk.kt3_agent_contracts import build_agent_user_prompt
from app.core.risk.kt3_agent_contracts import build_default_report_role
from app.core.risk.kt3_agent_contracts import build_safety_flags
from app.core.risk.kt3_propagation_agent import PROPAGATION_AGENT_REPORT_SECTIONS
from app.core.risk.kt3_propagation_agent import build_propagation_agent_output_contract
from app.core.risk.kt3_propagation_agent import build_propagation_agent_prompt_note
from app.core.risk.kt3_propagation_agent import has_propagation_tree_context
from app.core.risk.kt3_propagation_agent import select_propagation_context
from app.core.risk.kt3_propagation_context import PROPAGATION_CONTEXT_SCHEMA
from app.core.risk.kt3_propagation_context import THREAD_CONTEXT_SCHEMA
from app.core.risk.kt3_propagation_context import build_propagation_context_for_case
from app.core.risk.kt3_propagation_context import build_thread_context_from_pheme


def test_pheme_thread_context_preserves_reply_tree():
    source = {
        "id_str": "root",
        "created_at": "Mon Jan 01 00:00:00 +0000 2024",
        "text": "Breaking claim",
        "user": {"id_str": "u0"},
    }
    reactions = [
        {
            "id_str": "r1",
            "in_reply_to_status_id_str": "root",
            "created_at": "Mon Jan 01 00:01:00 +0000 2024",
            "text": "Is this true?",
            "user": {"id_str": "u1"},
        },
        {
            "id_str": "r2",
            "in_reply_to_status_id_str": "r1",
            "created_at": "Mon Jan 01 00:02:00 +0000 2024",
            "text": "This is false",
            "user": {"id_str": "u2"},
        },
    ]

    thread = build_thread_context_from_pheme(
        source,
        reactions,
        event_name="unit-event",
        tree_id="tree-1",
        rumour_label="rumour",
        veracity="false",
    )

    assert thread["schema_version"] == THREAD_CONTEXT_SCHEMA
    assert thread["tree_id"] == "tree-1"
    assert thread["summary"]["node_count"] == 3
    assert thread["summary"]["edge_count"] == 2
    assert thread["summary"]["max_depth"] == 2
    assert thread["summary"]["stance_counts"]["query"] == 1
    assert thread["summary"]["stance_counts"]["deny"] == 1


def test_propagation_context_compacts_tree_for_agent_review():
    thread = build_thread_context_from_pheme(
        {"id_str": "root", "created_at": "2024-01-01T00:00:00+00:00", "text": "Claim"},
        [
            {
                "id_str": "r1",
                "in_reply_to_status_id_str": "root",
                "created_at": "2024-01-01T00:01:00+00:00",
                "text": "yes confirmed",
            },
            {
                "id_str": "r2",
                "in_reply_to_status_id_str": "r1",
                "created_at": "2024-01-01T00:02:00+00:00",
                "text": "not true",
            },
        ],
        tree_id="tree-2",
    )
    case = {"case_id": "c1", "thread_context": thread}

    context = build_propagation_context_for_case(case, claim_rank=[{"claim_id": "claim-1"}])

    assert context["schema_version"] == PROPAGATION_CONTEXT_SCHEMA
    assert context["has_thread_context"] is True
    assert context["tree_metrics"]["node_count"] == 3
    assert context["key_branches"][0]["path_node_ids"] == ["root", "r1", "r2"]
    assert context["stance_by_depth"]["1"]["support"] == 1
    assert context["temporal_snapshots"]
    assert context["missing_fields"] == []


def test_agent_review_uses_explicit_propagation_context_not_claim_only():
    no_tree_report = {
        "post_semantics": {"summary": {"available_claims": 1}},
        "kt3_harmfulness": {
            "global_summary": {"claim_rank": [{"claim_id": "claim-1"}]},
            "propagation_context": {
                "schema_version": PROPAGATION_CONTEXT_SCHEMA,
                "has_thread_context": False,
                "tree_metrics": {"node_count": 0, "edge_count": 0},
            },
            "graph_export": {"summary": {}},
        },
    }
    assert _has_propagation_tree_context(no_tree_report) is False

    report = {
        "post_semantics": {"summary": {"available_claims": 1}},
        "kt3_harmfulness": {
            "global_summary": {"claim_rank": [{"claim_id": "claim-1"}]},
            "propagation_context": {
                "schema_version": PROPAGATION_CONTEXT_SCHEMA,
                "tree_id": "tree-1",
                "has_thread_context": True,
                "tree_metrics": {"node_count": 2, "edge_count": 1},
            },
            "graph_export": {"summary": {"node_count": 2, "edge_count": 1}},
        },
    }

    assert _has_propagation_tree_context(report) is True
    selected = _select_propagation_context(report, ["tree-1"])
    assert selected["schema_version"] == PROPAGATION_CONTEXT_SCHEMA
    assert selected["selected_tree_ids"] == ["tree-1"]
    assert selected["graph_summary"]["edge_count"] == 1


def test_propagation_agent_prompt_is_field_constrained():
    prompt = _agent_system_prompt("PropagationTreeAgent")
    contract = _agent_output_contract("PropagationTreeAgent")

    assert "field-constrained Chinese report" in prompt
    assert "selected_context.propagation_context" in prompt
    assert "tree_metrics.*" in prompt
    assert "do not infer diffusion" in prompt
    assert contract["format"] == "fixed_headed_chinese_report"
    assert contract["required_headings"] == [
        "输入证据状态",
        "树结构指标",
        "关键分支证据",
        "态度立场变化",
        "异常放大与缺证据",
        "给综合裁决的传播结论",
    ]
    assert "missing_fields" in contract["allowed_evidence_refs"]


def test_propagation_agent_boundary_module_owns_contract_and_routing_logic():
    report = {
        "kt3_harmfulness": {
            "propagation_context": {
                "tree_id": "tree-7",
                "has_thread_context": True,
                "tree_metrics": {"node_count": 2, "edge_count": 1},
            },
            "graph_export": {"summary": {"edge_count": 1}},
        },
        "post_semantics": {"summary": {"available_claims": 1}},
    }

    selected = select_propagation_context(report, [])
    prompt_note = build_propagation_agent_prompt_note("PropagationTreeAgent")
    contract = build_propagation_agent_output_contract("PropagationTreeAgent")

    assert selected["selected_tree_ids"] == ["tree-7"]
    assert has_propagation_tree_context(report) is True
    assert "selected_context.propagation_context" in prompt_note
    assert contract["required_headings"] == PROPAGATION_AGENT_REPORT_SECTIONS


def test_agent_contracts_module_owns_prompt_sections_roles_and_payloads():
    context = {"active_policy": {}, "error_memory_summary": {"known_issue": 1}}
    prompt = build_agent_system_prompt("HarmfulnessJudgeAgent")
    user_prompt = build_agent_user_prompt(
        "HarmfulnessJudgeAgent",
        context,
        {"PostHarmAgent": {"status": "completed", "report_text": "post report"}},
        policy_guidance={"active_policy_present": False},
    )

    assert AGENT_REPORT_SECTIONS["PropagationTreeAgent"] == PROPAGATION_AGENT_REPORT_SECTIONS
    assert "Required report sections" in prompt
    assert "HarmfulnessJudgeAgent" in prompt
    assert "\"policy_guidance\"" in user_prompt
    assert build_default_report_role("QuestionReflectionAgent") == "reflection"
    assert "advisory_judgement_only" in build_safety_flags("HarmfulnessJudgeAgent")
