from __future__ import annotations

import asyncio
import inspect
import json

from app.core.review.agent_contracts import build_agent_system_prompt
from app.core.review.agent_contracts import build_agent_user_prompt
from app.core.review.agent_contracts import validate_judge_decision_against_policy
from app.core.review.agent_review import _build_agent_context
from app.core.review.agent_review import run_manual_agent_review


class RecordingAsyncProvider:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    async def __call__(
        self,
        *,
        agent_name: str,
        system_prompt: str,
        user_prompt: str,
        input_bundle: dict[str, object],
        model: str,
    ) -> str:
        self.calls.append(
            {
                "agent_name": agent_name,
                "system_prompt": system_prompt,
                "user_prompt": user_prompt,
                "input_bundle": input_bundle,
                "model": model,
            }
        )
        await asyncio.sleep(0.01)
        return f"completed: {agent_name}"


def _report() -> dict[str, object]:
    return {
        "report_id": "risk-1",
        "event_id": "event-1",
        "platform": "weibo",
        "post_semantics": {
            "posts": [
                {"post_id": "post-1", "content": "claim one"},
                {"post_id": "post-2", "content": "claim two"},
                {"post_id": "post-3", "content": "claim three"},
            ]
        },
    }


def _active_policy() -> dict[str, object]:
    return {
        "policy_id": "review-policy-2026-08",
        "activation_status": "active_human_approved",
        "policy": {
            "review_threshold": 0.52,
            "abstain_threshold": 0.45,
            "retrieval_threshold": 0.58,
            "countermeasure_threshold": 0.72,
            "agent_weights": {"PostHarmAgent": 0.4, "ClaimEvidenceAgent": 0.35},
        },
        "candidate_rules": [
            {
                "rule_id": "accepted-multimodal-conflict",
                "description": "Escalate when image and text conflict.",
                "source": "held-out-validation",
                "round": 2,
                "status": "accepted_for_round",
            }
        ],
    }


def test_manual_review_exposes_explicit_reflection_targets_api():
    parameters = inspect.signature(run_manual_agent_review).parameters

    assert "reflection_target_agent_names" in parameters


def test_agent_context_uses_review_harmfulness_queue_and_execution():
    report = _report()
    report["review_harmfulness"] = {
        "review_queue": {"retrieval_tasks": [{"query": "authoritative query"}]},
        "review_execution": {"local_results": [{"doc_id": "evidence-1"}]},
    }

    context = _build_agent_context(
        report,
        case_id="case-1",
        selected_post_ids=["post-1"],
        selected_tree_ids=[],
        include_media_base64=False,
        max_keyframes=1,
    )

    assert context["review_queue"] == report["review_harmfulness"]["review_queue"]
    assert context["review_execution"] == report["review_harmfulness"]["review_execution"]


def test_question_reflection_responds_only_to_explicit_completed_targets():
    parameters = inspect.signature(run_manual_agent_review).parameters

    assert "reflection_target_agent_names" in parameters

    provider = RecordingAsyncProvider()
    report = _report()
    report["review_harmfulness"] = {
        "review_queue": {"retrieval_tasks": [{"claim_id": "claim-1"}]},
        "propagation_context": {
            "has_thread_context": True,
            "tree_metrics": {"node_count": 2, "edge_count": 1},
        },
    }
    result = asyncio.run(
        run_manual_agent_review(
            report=report,
            agent_names=["PostHarmAgent", "ClaimEvidenceAgent", "PropagationTreeAgent"],
            reflection_target_agent_names=["ClaimEvidenceAgent"],
            provider=provider,
            runtime_mode="complex",
        )
    )

    reflection_responses = [
        report
        for report in result["agent_reports"]
        if report["report_role"] == "reflection_response"
    ]

    assert [report["parent_agent_name"] for report in reflection_responses] == ["ClaimEvidenceAgent"]


def test_question_reflection_fallback_requests_at_most_two_completed_experts():
    provider = RecordingAsyncProvider()
    report = _report()
    report["review_harmfulness"] = {
        "review_queue": {"retrieval_tasks": [{"claim_id": "claim-1"}]},
        "propagation_context": {
            "has_thread_context": True,
            "tree_metrics": {"node_count": 2, "edge_count": 1},
        },
    }

    result = asyncio.run(
        run_manual_agent_review(
            report=report,
            agent_names=["PostHarmAgent", "ClaimEvidenceAgent", "PropagationTreeAgent"],
            provider=provider,
            runtime_mode="complex",
        )
    )

    reflection_responses = [
        report
        for report in result["agent_reports"]
        if report["report_role"] == "reflection_response"
    ]

    assert [report["parent_agent_name"] for report in reflection_responses] == [
        "PostHarmAgent",
        "ClaimEvidenceAgent",
    ]


def test_judge_prompt_contains_deterministic_policy_decision_frame():
    prompt = build_agent_system_prompt("HarmfulnessJudgeAgent")
    payload = json.loads(
        build_agent_user_prompt(
            "HarmfulnessJudgeAgent",
            {
                "input_refs": {"post_ids": ["post-1"]},
                "case_score": 0.55,
                "case_uncertainty": 0.1,
                "active_policy": _active_policy(),
                "error_memory_summary": {
                    "historical_failure_cautions": ["Do not overrule missing primary evidence."],
                },
            },
            {
                "PostHarmAgent": {
                    "status": "completed",
                    "report_text": "Harmfulness evidence supports review.",
                    "system_audit_sidecar": {"evidence_refs": [{"doc_id": "post:post-1"}]},
                }
            },
            policy_guidance=_active_policy(),
        )
    )

    assert "DETERMINISTIC POLICY DECISION FRAME" in prompt
    frame = payload["policy_decision_frame"]
    assert frame["active_policy_id"] == "review-policy-2026-08"
    assert frame["policy_binding"] is True
    assert frame["advisory_only"] is True
    assert frame["threshold_comparisons"]["review"]["threshold"] == 0.52
    assert frame["policy_recommendation"] == {
        "review_required": True,
        "retrieval_required": False,
        "abstain": False,
        "countermeasure_recommended": False,
    }
    assert frame["matched_accepted_rules"][0]["rule_id"] == "accepted-multimodal-conflict"
    assert frame["matched_accepted_rules"][0]["source"] == "validation_metric"
    assert frame["weighted_expert_contribution_refs"] == [
        {
            "agent_name": "PostHarmAgent",
            "weight": 1.0,
            "evidence_refs": [{"doc_id": "post:post-1"}],
        }
    ]
    assert frame["historical_failure_memory_cautions"] == [
        "Do not overrule missing primary evidence."
    ]


def test_policy_conflict_forces_human_review_without_overwriting_detector():
    result = validate_judge_decision_against_policy(
        {
            "main_axes": {
                "attack_hate_offense": {
                    "available": True,
                    "label": "non_harmful",
                }
            },
            "review_required": False,
        },
        {
            "advisory_only": True,
            "policy_recommendation": {
                "review_required": True,
                "abstain": True,
            },
        },
    )

    assert result["conflict_detected"] is True
    assert result["effective_review_required"] is True
    assert result["detector_outputs_modified"] is False
    assert set(result["conflict_reasons"]) == {
        "judge_rejected_required_review",
        "judge_rejected_required_abstention",
    }


def test_role_prompt_compacts_heavy_context_and_preserves_evidence_refs():
    payload = json.loads(
        build_agent_user_prompt(
            "ClaimEvidenceAgent",
            {
                "input_refs": {"report_id": "risk-1", "post_ids": ["post-1"]},
                "media_inputs": [{"data_url": "data:image/png;base64," + "A" * 20_000}],
                "selected_posts": [{"post_id": "post-1", "content": "B" * 20_000}],
                "evidence_refs": [{"doc_id": "post:post-1"}],
            },
            {
                "PostHarmAgent": {
                    "status": "completed",
                    "report_text": "C" * 20_000,
                    "system_audit_sidecar": {"evidence_refs": [{"doc_id": "post:post-1"}]},
                }
            },
            policy_guidance={},
        )
    )

    encoded = json.dumps(payload, ensure_ascii=False)
    assert "data:image/" not in encoded
    assert len(payload["selected_context"]["selected_posts"][0]["content"]) <= 2_000
    assert len(payload["prior_agent_reports"]["PostHarmAgent"]["report_text"]) <= 2_000
    assert payload["selected_context"]["input_refs"] == {"report_id": "risk-1", "post_ids": ["post-1"]}
    assert payload["prior_agent_reports"]["PostHarmAgent"]["evidence_refs"] == [{"doc_id": "post:post-1"}]


def test_initial_expert_prompt_excludes_failure_memory_but_judge_keeps_matched_memory():
    context = {
        "input_refs": {"post_ids": ["post-1"]},
        "error_memory_summary": {
            "matched_records": [{"memory_id": "memory-1", "caution": "verify the source"}],
            "match_reasons": [{"memory_id": "memory-1", "matched_tags": ["claim_linked"]}],
            "ignored_count": 3,
        },
    }

    expert_payload = json.loads(
        build_agent_user_prompt("PostHarmAgent", context, {}, policy_guidance={})
    )
    judge_payload = json.loads(
        build_agent_user_prompt("HarmfulnessJudgeAgent", context, {}, policy_guidance={})
    )

    assert "error_memory_summary" not in expert_payload
    assert judge_payload["error_memory_summary"]["matched_records"][0]["memory_id"] == "memory-1"


def test_run_summary_and_audit_report_llm_call_and_prompt_telemetry():
    provider = RecordingAsyncProvider()

    result = asyncio.run(
        run_manual_agent_review(
            report=_report(),
            agent_names=["PostHarmAgent"],
            provider=provider,
            model="fake-review-model",
            runtime_mode="simple",
        )
    )

    assert result["summary"]["planned_llm_call_count"] == 2
    assert result["summary"]["actual_llm_call_count"] == len(provider.calls) == 2
    assert result["audit"]["planned_llm_call_count"] == 2
    assert result["audit"]["actual_llm_call_count"] == 2
    for report in result["agent_reports"]:
        telemetry = report["prompt_telemetry"]
        assert telemetry["system_prompt_chars"] > 0
        assert telemetry["user_prompt_chars"] > 0
        assert telemetry["input_bundle_chars"] > 0
        assert telemetry["provider_duration_ms"] >= 0


def test_complex_text_case_filters_inapplicable_experts_before_provider_calls():
    provider = RecordingAsyncProvider()

    result = asyncio.run(
        run_manual_agent_review(
            report=_report(),
            agent_names=[
                "PostHarmAgent",
                "MultimodalConsistencyAgent",
                "ClaimEvidenceAgent",
                "PropagationTreeAgent",
            ],
            provider=provider,
            runtime_mode="complex",
        )
    )

    assert result["summary"]["planned_llm_call_count"] == 4
    assert result["summary"]["actual_llm_call_count"] == 4
    assert [call["agent_name"] for call in provider.calls] == [
        "PostHarmAgent",
        "QuestionReflectionAgent",
        "PostHarmAgentReflectionResponse",
        "HarmfulnessJudgeAgent",
    ]
    assert result["audit"]["execution_plan"]["eligible_agents"] == ["PostHarmAgent"]
    assert result["audit"]["execution_plan"]["skipped_agents"] == [
        {
            "agent_name": "MultimodalConsistencyAgent",
            "reason": "missing_usable_media_or_cross_view_conflict",
        },
        {
            "agent_name": "ClaimEvidenceAgent",
            "reason": "missing_claim_context",
        },
        {
            "agent_name": "PropagationTreeAgent",
            "reason": "missing_propagation_tree_or_post_post_edges",
        },
    ]


def test_parallel_experts_cannot_exceed_atomic_llm_call_budget():
    provider = RecordingAsyncProvider()

    result = asyncio.run(
        run_manual_agent_review(
            report=_report(),
            agent_names=[
                "PostHarmAgent",
                "MultimodalConsistencyAgent",
                "ClaimEvidenceAgent",
                "PropagationTreeAgent",
            ],
            provider=provider,
            runtime_mode="complex",
            max_agent_calls_per_case=1,
        )
    )

    assert len(provider.calls) == 1
    assert result["summary"]["actual_llm_call_count"] == 1
    assert any(item["status"] == "skipped_budget" for item in result["audit"]["llm_call_audit"])


def test_full_debate_calls_share_the_agent_call_budget():
    provider = RecordingAsyncProvider()
    report = _report()
    report["post_semantics"]["posts"][0]["post_view_detection"] = {
        "conflict": {"score": 0.8},
        "review_reason": ["media context unclosed"],
    }

    result = asyncio.run(
        run_manual_agent_review(
            report=report,
            agent_names=["MultimodalConsistencyAgent"],
            provider=provider,
            runtime_mode="complex",
            enable_full_debate=True,
            max_agent_calls_per_case=1,
        )
    )

    assert len(provider.calls) == 1
    assert result["summary"]["actual_llm_call_count"] == 1
    assert result["summary"]["full_debate_triggered"] is True
