from __future__ import annotations

import asyncio
import inspect
import json

from app.core.review.agent_contracts import build_agent_system_prompt
from app.core.review.agent_contracts import build_agent_user_prompt
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
        "activation_status": "activated",
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


def test_question_reflection_responds_only_to_explicit_completed_targets():
    parameters = inspect.signature(run_manual_agent_review).parameters

    assert "reflection_target_agent_names" in parameters

    provider = RecordingAsyncProvider()
    result = asyncio.run(
        run_manual_agent_review(
            report=_report(),
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

    result = asyncio.run(
        run_manual_agent_review(
            report=_report(),
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
    assert payload["policy_decision_frame"] == {
        "active_policy_id": "review-policy-2026-08",
        "threshold_comparisons": {
            "review": {"threshold": 0.52},
            "abstain": {"threshold": 0.45},
            "retrieval": {"threshold": 0.58},
            "countermeasure": {"threshold": 0.72},
        },
        "matched_accepted_rules": [
            {
                "rule_id": "accepted-multimodal-conflict",
                "explanation": "Escalate when image and text conflict.",
            }
        ],
        "weighted_expert_contribution_refs": [
            {"agent_name": "PostHarmAgent", "weight": 0.4, "evidence_refs": [{"doc_id": "post:post-1"}]}
        ],
        "historical_failure_memory_cautions": ["Do not overrule missing primary evidence."],
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
