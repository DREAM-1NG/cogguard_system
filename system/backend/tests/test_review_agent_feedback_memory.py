import json
from types import SimpleNamespace

import pytest

from app.core.review.agent_policy import match_feedback_memory, summarize_feedback_memory
from app.services.review_system_service import feedback_memory_from_db


def test_feedback_summary_preserves_compatible_memory_records_for_matching():
    summary = summarize_feedback_memory(
        [
            {
                "memory_id": "memory-1",
                "review_id": "review-1",
                "case_tags": ["claim", "video"],
                "error_types": ["false_negative"],
                "corrected_label": "harmful",
                "evidence_refs": ["evidence-1"],
                "caution": "verify the source timestamp",
            },
            {"review_id": "legacy-1", "error_types": ["false_positive"]},
        ]
    )

    assert summary["memory_records"] == [
        {
            "memory_id": "memory-1",
            "review_id": "review-1",
            "case_tags": ["claim", "video"],
            "error_types": ["false_negative"],
            "corrected_label": "harmful",
            "evidence_refs": ["evidence-1"],
            "caution": "verify the source timestamp",
        },
        {
            "memory_id": None,
            "review_id": "legacy-1",
            "case_tags": [],
            "error_types": ["false_positive"],
            "corrected_label": None,
            "evidence_refs": [],
            "caution": None,
        },
    ]


def test_feedback_memory_matching_orders_tag_intersection_and_audits_legacy_records():
    summary = summarize_feedback_memory(
        [
            {"memory_id": "z", "case_tags": ["claim"], "error_types": ["false_negative"]},
            {"memory_id": "a", "case_tags": ["claim", "video"], "error_types": ["evidence_gap"]},
            {"review_id": "legacy", "error_types": ["false_positive"]},
        ]
    )

    result = match_feedback_memory(summary, ["video", "claim"], top_k=3)

    assert [record["memory_id"] for record in result["matched_records"]] == ["a", "z"]
    assert result["match_reasons"] == [
        {"memory_id": "a", "review_id": None, "matched_tags": ["claim", "video"], "match_count": 2},
        {"memory_id": "z", "review_id": None, "matched_tags": ["claim"], "match_count": 1},
    ]
    assert result["ignored_count"] == 1
    assert result["ignored_records"] == [
        {"memory_id": None, "review_id": "legacy", "reason": "missing_case_tags"}
    ]


@pytest.mark.asyncio
async def test_db_feedback_memory_derives_case_tags_that_match_review_signals():
    row = SimpleNamespace(
        feedback_id="feedback-memory-1",
        report_id="report-1",
        review_id="review-1",
        run_id="run-1",
        case_id="case-1",
        human_label="non_harmful",
        corrected_label="harmful",
        error_types_json=json.dumps(
            [
                "false_negative",
                "claim_unlinked",
                "evidence_gap",
                "fact_check",
                "source_verification",
                "image",
                "video",
                "audio",
                "ocr",
                "asr",
                "media",
                "multimodal",
                "cross_view_conflict",
                "media_mismatch",
                "propagation",
                "repost",
                "reply",
                "quote",
                "thread",
                "tree",
                "false_positive",
            ]
        ),
        notes="Manual audit follow-up.",
        evidence_refs_json=json.dumps([{"source": "citation"}]),
        reviewer_confidence=0.9,
    )

    class FakeResult:
        def scalars(self):
            return self

        def all(self):
            return [row]

    class FakeSession:
        async def execute(self, _statement):
            return FakeResult()

    memory = await feedback_memory_from_db(["report-1"], FakeSession())
    result = match_feedback_memory(
        summarize_feedback_memory(memory),
        ["claim_linked", "claim_uncertainty", "multimodal", "multimodal_conflict", "propagation_context"],
    )

    assert memory[0]["memory_id"] == "feedback-memory-1"
    assert set(memory[0]["case_tags"]) >= {
        "claim_linked",
        "claim_uncertainty",
        "multimodal",
        "multimodal_conflict",
        "propagation_context",
        "error:false_negative",
        "error:false_positive",
        "error:claim_unlinked",
        "evidence_source:citation",
        "label:non_harmful",
        "label:harmful",
        "label_transition:non_harmful_to_harmful",
    }
    assert "false_negative" not in memory[0]["case_tags"]
    assert "false_positive" not in memory[0]["case_tags"]
    assert result["match_reasons"] == [
        {
            "memory_id": "feedback-memory-1",
            "review_id": "review-1",
            "matched_tags": [
                "claim_linked",
                "claim_uncertainty",
                "multimodal",
                "multimodal_conflict",
                "propagation_context",
            ],
            "match_count": 5,
        }
    ]
