from __future__ import annotations

from app.core.review.agent_runtime import build_candidate_rule_hints
from app.core.review.agent_runtime import build_execution_plan_for_runtime
from app.core.review.agent_runtime import build_failure_mode_tags
from app.core.review.agent_runtime import has_multimodal_conflict
from app.core.review.agent_runtime import has_uncertain_stance_or_view
from app.core.review.agent_runtime import normalize_agent_names
from app.core.review.agent_runtime import recommend_runtime_mode
from app.core.review.agent_runtime import resolve_runtime_mode
from app.core.review.agent_runtime import should_postpone_countermeasure


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


def test_simple_plan_filters_inapplicable_experts_and_keeps_single_judge():
    plan = build_execution_plan_for_runtime(
        requested_agents=normalize_agent_names(
            ["PostHarmAgent", "ClaimEvidenceAgent", "MultimodalConsistencyAgent", "PropagationTreeAgent"]
        ),
        runtime_mode="simple",
        enable_deep_judge=True,
        report={"review_harmfulness": {"review_queue": {}}},
        context={"selected_posts": [{"post_id": "post-1", "content": "Plain text only."}]},
    )

    assert plan["requested_agents"] == [
        "PostHarmAgent",
        "MultimodalConsistencyAgent",
        "ClaimEvidenceAgent",
        "PropagationTreeAgent",
        "HarmfulnessJudgeAgent",
    ]
    assert plan["eligible_agents"] == ["PostHarmAgent"]
    assert plan["expert_agents"] == ["PostHarmAgent"]
    assert plan["executed_agents"] == ["PostHarmAgent", "HarmfulnessJudgeAgent"]
    assert plan["followup_agents"] == ["HarmfulnessJudgeAgent"]
    assert plan["skipped_agents"] == [
        {"agent_name": "MultimodalConsistencyAgent", "reason": "missing_usable_media_or_cross_view_conflict"},
        {"agent_name": "ClaimEvidenceAgent", "reason": "missing_claim_context"},
        {"agent_name": "PropagationTreeAgent", "reason": "missing_propagation_tree_or_post_post_edges"},
    ]
    assert plan["overrides"] == []
    assert plan["run_question_reflection"] is False
    assert plan["run_reflection_responses"] is False
    assert plan["deep_judge"] is False
    assert plan["run_countermeasure"] is False


def test_simple_plan_audits_forced_inapplicable_expert_selection():
    plan = build_execution_plan_for_runtime(
        requested_agents=normalize_agent_names(["ClaimEvidenceAgent"]),
        runtime_mode="simple",
        enable_deep_judge=False,
        report={"review_harmfulness": {"review_queue": {}}},
        context={"selected_posts": [{"post_id": "post-1", "content": "Plain text only."}]},
        forced_agent_names=["ClaimEvidenceAgent"],
    )

    assert plan["eligible_agents"] == []
    assert plan["expert_agents"] == ["ClaimEvidenceAgent"]
    assert plan["executed_agents"] == ["ClaimEvidenceAgent", "HarmfulnessJudgeAgent"]
    assert plan["skipped_agents"] == []
    assert plan["overrides"] == [
        {
            "agent_name": "ClaimEvidenceAgent",
            "reason": "analyst_forced_selection",
            "missing_capabilities": ["claim_context"],
        }
    ]


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


def test_countermeasure_trigger_recognizes_chinese_and_english_judge_recommendations():
    assert should_postpone_countermeasure(
        report={},
        reports_by_agent={"HarmfulnessJudgeAgent": {"report_text": "建议进入反制规划。"}},
    )
    assert should_postpone_countermeasure(
        report={},
        reports_by_agent={"HarmfulnessJudgeAgent": {"report_text": "Countermeasure planning is recommended."}},
    )


def test_complex_plan_executes_only_capable_experts_and_audits_forced_overrides():
    plan = build_execution_plan_for_runtime(
        requested_agents=normalize_agent_names(
            ["PostHarmAgent", "ClaimEvidenceAgent", "MultimodalConsistencyAgent", "PropagationTreeAgent"]
        ),
        runtime_mode="complex",
        enable_deep_judge=False,
        report={
            "review_harmfulness": {
                "review_queue": {"retrieval_tasks": [{"claim_id": "claim-1"}]},
                "graph_export": {"summary": {"edge_count": 4, "edge_types": ["account_object"]}},
            }
        },
        context={"selected_posts": [{"post_id": "post-1"}]},
        forced_agent_names=["PropagationTreeAgent"],
    )

    assert plan["capabilities"] == {
        "claim_context": True,
        "usable_media": False,
        "cross_view_conflict": False,
        "propagation_tree_or_post_post_edges": False,
    }
    assert plan["requested_agents"] == [
        "PostHarmAgent",
        "MultimodalConsistencyAgent",
        "ClaimEvidenceAgent",
        "PropagationTreeAgent",
    ]
    assert plan["eligible_agents"] == ["PostHarmAgent", "ClaimEvidenceAgent"]
    assert plan["expert_agents"] == ["PostHarmAgent", "ClaimEvidenceAgent", "PropagationTreeAgent"]
    assert plan["executed_agents"] == [
        "PostHarmAgent",
        "ClaimEvidenceAgent",
        "PropagationTreeAgent",
        "QuestionReflectionAgent",
        "HarmfulnessJudgeAgent",
    ]
    assert plan["skipped_agents"] == [
        {
            "agent_name": "MultimodalConsistencyAgent",
            "reason": "missing_usable_media_or_cross_view_conflict",
        }
    ]
    assert plan["overrides"] == [
        {
            "agent_name": "PropagationTreeAgent",
            "reason": "analyst_forced_selection",
            "missing_capabilities": ["propagation_tree_or_post_post_edges"],
        }
    ]
    assert plan["followup_agents"] == ["QuestionReflectionAgent", "HarmfulnessJudgeAgent"]


def test_complex_plan_falls_back_to_post_harm_and_keeps_maro_chain_without_capable_selection():
    plan = build_execution_plan_for_runtime(
        requested_agents=normalize_agent_names(["MultimodalConsistencyAgent", "PropagationTreeAgent"]),
        runtime_mode="complex",
        enable_deep_judge=False,
        report={},
        context={"selected_posts": [{"post_id": "post-1"}]},
    )

    assert plan["eligible_agents"] == []
    assert plan["expert_agents"] == ["PostHarmAgent"]
    assert plan["executed_agents"] == [
        "PostHarmAgent",
        "QuestionReflectionAgent",
        "HarmfulnessJudgeAgent",
    ]
    assert plan["skipped_agents"] == [
        {
            "agent_name": "MultimodalConsistencyAgent",
            "reason": "missing_usable_media_or_cross_view_conflict",
        },
        {
            "agent_name": "PropagationTreeAgent",
            "reason": "missing_propagation_tree_or_post_post_edges",
        },
    ]


def test_complex_plan_recognizes_usable_media_and_post_post_propagation_edges():
    plan = build_execution_plan_for_runtime(
        requested_agents=normalize_agent_names(["MultimodalConsistencyAgent", "PropagationTreeAgent"]),
        runtime_mode="complex",
        enable_deep_judge=False,
        report={
            "review_harmfulness": {
                "graph_export": {"summary": {"edge_types": ["post_post"]}},
            }
        },
        context={
            "selected_posts": [{"post_id": "post-1", "media_urls": ["https://example.test/image.jpg"]}],
        },
    )

    assert plan["capabilities"]["usable_media"] is True
    assert plan["capabilities"]["propagation_tree_or_post_post_edges"] is True
    assert plan["expert_agents"] == ["MultimodalConsistencyAgent", "PropagationTreeAgent"]
    assert plan["skipped_agents"] == []


def test_media_missing_and_explicit_false_conflict_do_not_force_complex_mode():
    post = {
        "post_id": "post-1",
        "stance": {"label": "unlinked"},
        "post_view_detection": {
            "final_harmfulness": "uncertain",
            "conflict": {"has_conflict": False, "score": 0.0},
            "review_reason": ["video unavailable", "missing vision input"],
        },
    }

    assert has_multimodal_conflict(post) is False
    assert has_uncertain_stance_or_view(post, claim_context_valid=False) is False
    recommended, reasons = recommend_runtime_mode(
        report={"review_harmfulness": {"review_queue": {}}},
        context={"selected_posts": [post]},
    )
    assert recommended == "simple"
    assert reasons == ["single_post_low_conflict"]


def test_unlinked_stance_only_upgrades_when_claim_context_exists():
    post = {"post_id": "post-1", "stance": {"label": "unlinked", "abstain": True}}
    assert has_uncertain_stance_or_view(post, claim_context_valid=False) is False
    assert has_uncertain_stance_or_view(post, claim_context_valid=True) is True


def test_maro_benchmark_can_disable_countermeasure_without_forcing_complex_mode():
    agents = normalize_agent_names(["PostHarmAgent", "CountermeasureAgent"])
    decision = resolve_runtime_mode(
        report={"review_harmfulness": {"review_queue": {}}},
        context={"selected_posts": [{"post_id": "post-1"}]},
        normalized_agents=agents,
        requested_runtime_mode="auto",
        enable_active_retrieval=False,
        enable_light_debate=False,
        enable_full_debate=False,
        enable_deep_judge=False,
        enable_countermeasure=False,
    )
    plan = build_execution_plan_for_runtime(
        requested_agents=agents,
        runtime_mode=decision["effective_runtime_mode"],
        enable_deep_judge=False,
        enable_countermeasure=False,
    )
    assert decision["effective_runtime_mode"] == "simple"
    assert plan["run_countermeasure"] is False

