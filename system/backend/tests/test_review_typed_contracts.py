from __future__ import annotations

import asyncio

import pytest
from pydantic import ValidationError
from sqlalchemy.exc import SQLAlchemyError

from app.core.review.agent_contracts import (
    JudgeRationaleBundle,
    build_agent_output_contract,
)
from app.core.review.agent_review import _build_agent_context
from app.services import review_system_service


def test_agent_output_contracts_publish_typed_claim_and_judge_schemas():
    claim_schema = build_agent_output_contract("ClaimEvidenceAgent")
    judge_schema = build_agent_output_contract("HarmfulnessJudgeAgent")

    assert set(claim_schema["properties"]) == {
        "claims",
        "supporting_evidence",
        "contradicting_evidence",
        "evidence_gap",
    }
    assert judge_schema["properties"]["confidence"]["minimum"] == 0.0
    assert judge_schema["properties"]["confidence"]["maximum"] == 1.0
    with pytest.raises(ValidationError):
        JudgeRationaleBundle(
            risk_type="misinformation",
            confidence=1.1,
            rationale_report="evidence-bound report",
            human_confirmation_required=True,
        )


def test_agent_context_contains_only_accepted_or_active_policy_ids():
    context = _build_agent_context(
        {
            "report_id": "report-1",
            "event_id": "event-1",
            "platform": "weibo",
            "post_semantics": {"posts": [{"post_id": "p1", "content": "text"}]},
            "policy": {
                "candidate_rules": [
                    {"rule_id": "accepted", "status": "accepted_for_round"},
                    {"rule_id": "active", "status": "activated"},
                    {"rule_id": "rejected", "status": "rejected"},
                ]
            },
        },
        case_id="case-1",
        selected_post_ids=["p1"],
        selected_tree_ids=[],
        include_media_base64=False,
        max_keyframes=0,
    )

    assert context["schema_version"] == "review-agent-input-bundle-v2-typed"
    assert context["policy_bundle"]["active_policies"] == ["accepted", "active"]


def test_provider_list_marks_sqlalchemy_unavailable_but_propagates_programming_errors():
    class MissingTableDb:
        async def execute(self, _statement):
            raise SQLAlchemyError("missing table")

    class BrokenCodeDb:
        async def execute(self, _statement):
            raise RuntimeError("programming error")

    unavailable = asyncio.run(
        review_system_service.list_provider_configs(
            MissingTableDb(),
            include_env_fallback=False,
        )
    )
    assert unavailable == {"items": [], "unavailable": True}

    with pytest.raises(RuntimeError, match="programming error"):
        asyncio.run(
            review_system_service.list_provider_configs(
                BrokenCodeDb(),
                include_env_fallback=False,
            )
        )
