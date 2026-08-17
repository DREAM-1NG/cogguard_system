from __future__ import annotations

import asyncio
import json

from app.core.review.agent_contracts import CLAIM_EVIDENCE_BEGIN, CLAIM_EVIDENCE_END
from app.core.review.agent_contracts import JUDGE_DECISION_BEGIN, JUDGE_DECISION_END
from app.core.review.agent_review import run_manual_agent_review


def _claim_footer(*, relation: str, source_ref_ids: list[str], quoted_spans: list[str]) -> str:
    payload = {
        "claim_assessment": "checkable",
        "claim": "The event happened on the stated date.",
        "assessment_reason": "The post makes a time-bounded factual assertion.",
        "relation": relation,
        "source_ref_ids": source_ref_ids,
        "quoted_spans": quoted_spans,
    }
    return f"Claim assessment report\n{CLAIM_EVIDENCE_BEGIN}{json.dumps(payload)}{CLAIM_EVIDENCE_END}"


def _judge_footer(*, label: str) -> str:
    payload = {
        "main_axes": {
            "attack_hate_offense": {"available": False, "label": "unavailable", "confidence": 0.0},
            "misinfo_claim_risk": {"available": label != "unavailable", "label": label, "confidence": 0.8 if label != "unavailable" else 0.0},
        },
        "stance": {"available": False, "label": "unlinked", "confidence": 0.0},
        "review_required": True,
        "review_reason": ["claim_review"],
        "fine_labels": [],
    }
    return f"Judge report\n{JUDGE_DECISION_BEGIN}{json.dumps(payload)}{JUDGE_DECISION_END}"


def _report() -> dict:
    return {
        "report_id": "report-1",
        "post_semantics": {
            "posts": [
                {
                    "post_id": "post-1",
                    "content": "The event happened on the stated date.",
                }
            ]
        },
        "review_harmfulness": {"review_queue": {}},
    }


def test_claim_agent_assesses_then_retrieves_then_binds_a_traceable_relation():
    external_queries: list[str] = []

    async def provider(**kwargs: object) -> str:
        agent_name = str(kwargs["agent_name"])
        if agent_name == "ClaimEvidenceAgent":
            return _claim_footer(relation="not_applicable", source_ref_ids=[], quoted_spans=[])
        if agent_name == "ClaimEvidenceAgentReflectionResponse":
            return _claim_footer(
                relation="contradicted",
                source_ref_ids=["external-1"],
                quoted_spans=["The official record gives a different date."],
            )
        if agent_name == "QuestionReflectionAgent":
            return "Ask the claim expert to reconcile the retrieved official record."
        if agent_name == "HarmfulnessJudgeAgent":
            return _judge_footer(label="harmful")
        raise AssertionError(f"unexpected agent: {agent_name}")

    async def external_retriever(*, query: str, context: dict[str, object], top_k: int) -> list[dict[str, object]]:
        external_queries.append(query)
        return [
            {
                "doc_id": "external-1",
                "source": "official_record",
                "url": "https://authority.example/record",
                "text": "The official record gives a different date.",
                "score": 0.9,
            }
        ]

    result = asyncio.run(
        run_manual_agent_review(
            report=_report(),
            agent_names=["ClaimEvidenceAgent"],
            selected_post_ids=["post-1"],
            provider=provider,
            review_task="claim_deception",
            enable_active_retrieval=True,
            external_retrieval_enabled=True,
            active_retriever=external_retriever,
        )
    )

    bundle = result["evidence_bundle"]
    judge = next(item for item in result["agent_reports"] if item["agent_name"] == "HarmfulnessJudgeAgent")
    assert external_queries == [
        "The event happened on the stated date.",
        "The event happened on the stated date. evidence verification",
    ]
    assert bundle["claim_assessment"] == "checkable"
    assert bundle["retrieval_status"] == "completed"
    assert bundle["relation"] == "contradicted"
    assert [item["doc_id"] for item in bundle["source_refs"]] == ["external-1"]
    assert judge["structured_sidecar"]["teacher_prediction"]["main_axes"]["misinfo_claim_risk"] == {
        "available": True,
        "label": "harmful",
        "confidence": 0.8,
    }


def test_missing_claim_assessment_never_queries_or_exports_evidence_insufficient():
    external_calls = 0

    async def provider(**kwargs: object) -> str:
        agent_name = str(kwargs["agent_name"])
        if agent_name == "ClaimEvidenceAgent":
            return "The post has not been converted into a structured factual claim."
        if agent_name == "ClaimEvidenceAgentReflectionResponse":
            return "No additional factual evidence can be assessed."
        if agent_name == "QuestionReflectionAgent":
            return "No verified claim has been supplied."
        if agent_name == "HarmfulnessJudgeAgent":
            return _judge_footer(label="uncertain")
        raise AssertionError(f"unexpected agent: {agent_name}")

    async def external_retriever(*, query: str, context: dict[str, object], top_k: int) -> list[dict[str, object]]:
        nonlocal external_calls
        external_calls += 1
        return []

    result = asyncio.run(
        run_manual_agent_review(
            report=_report(),
            agent_names=["ClaimEvidenceAgent"],
            selected_post_ids=["post-1"],
            provider=provider,
            review_task="claim_deception",
            enable_active_retrieval=True,
            external_retrieval_enabled=True,
            active_retriever=external_retriever,
        )
    )

    bundle = result["evidence_bundle"]
    judge = next(item for item in result["agent_reports"] if item["agent_name"] == "HarmfulnessJudgeAgent")
    axis = judge["structured_sidecar"]["teacher_prediction"]["main_axes"]["misinfo_claim_risk"]
    assert external_calls == 0
    assert bundle["claim_assessment"] == "extraction_failed"
    assert bundle["retrieval_status"] == "skipped_non_eligible_claim"
    assert bundle["relation"] == "not_applicable"
    assert axis == {"available": False, "label": "unavailable", "confidence": 0.0}
