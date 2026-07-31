from __future__ import annotations

from app.core.review.agent_runtime import build_candidate_rule_hints
from app.core.review.agent_runtime import build_execution_plan_for_runtime
from app.core.review.agent_runtime import build_failure_mode_tags
from app.core.review.agent_runtime import normalize_agent_names
from app.core.review.agent_runtime import recommend_runtime_mode
from app.core.review.agent_runtime import resolve_runtime_mode


def test_agent_runtime_normalizes_and_plans_simple_mode():
    agents = normalize_agent_names(["ClaimEvidence", "PostHarm", "HarmfulnessJudge"])
    assert agents == ["PostHarmAgent", "ClaimEvidenceAgent", "HarmfulnessJudgeAgent"]

    decision = resolve_runtime_mode(
        report={"review_harmfulness": {"review_queue": {}}},
        context={"selected_posts": [{"post_id": "p1"}]},
        normalized_agents=agents,
        requested_runtime_mode="simple",
        enable_active_retrieval=False,
        enable_light_debate=False,
        enable_full_debate=False,
        enable_deep_judge=False,
    )
    plan = build_execution_plan_for_runtime(
        requested_agents=agents,
        runtime_mode=decision["effective_runtime_mode"],
        enable_deep_judge=True,
    )

    assert decision["effective_runtime_mode"] == "simple"
    assert decision["runtime_reasons"] == ["single_post_low_conflict"]
    assert plan["expert_agents"] == ["PostHarmAgent", "ClaimEvidenceAgent"]
    assert plan["followup_agents"] == ["HarmfulnessJudgeAgent"]
    assert plan["deep_judge"] is False


def test_agent_runtime_promotes_complex_mode_and_emits_audit_tags():
    report = {
        "scores": {"risk_level": "high"},
        "review_harmfulness": {
            "review_queue": {"retrieval_tasks": [{"claim_id": "c1"}]},
            "propagation_context": {
                "tree_id": "tree-1",
                "has_thread_context": True,
                "tree_metrics": {"node_count": 2, "edge_count": 1},
            },
        },
    }
    context = {
        "selected_posts": [
            {
                "post_id": "p1",
                "stance": {"label": "uncertain"},
                "post_view_detection": {"review_reason": ["media conflict"]},
            }
        ]
    }
    normalized_agents = normalize_agent_names(["PostHarmAgent", "CountermeasureAgent"])

    recommended, reasons = recommend_runtime_mode(report=report, context=context)
    decision = resolve_runtime_mode(
        report=report,
        context=context,
        normalized_agents=normalized_agents,
        requested_runtime_mode="simple",
        enable_active_retrieval=False,
        enable_light_debate=False,
        enable_full_debate=False,
        enable_deep_judge=False,
    )
    hints = build_candidate_rule_hints(
        report=report,
        context=context,
        retrieval_bundle={"local_results": [{"top_evidence": []}]},
        reports_by_agent={},
    )
    tags = build_failure_mode_tags(
        report=report,
        context=context,
        retrieval_bundle={"audit": {"failures": ["timeout"]}},
    )

    assert recommended == "complex"
    assert "propagation_context_present" in reasons
    assert decision["effective_runtime_mode"] == "complex"
    assert decision["runtime_upgraded_by_requested_features"] is True
    assert {hint["hint_type"] for hint in hints} >= {
        "multimodal_conflict",
        "uncertainty_cluster",
        "retrieval_gap",
        "countermeasure_context",
    }
    assert set(tags) >= {
        "multimodal_conflict",
        "uncertain_post_or_stance",
        "external_retrieval_failure",
        "propagation_context_present",
    }

