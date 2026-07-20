from __future__ import annotations

from app.core.analysis.governance import (
    approve_canonical_verdict,
    build_model_activation_decision,
    build_rollback_decision,
    select_active_learning_cases,
)
from app.core.analysis.runtime import build_student_verdict, build_teacher_advisory_verdict


def _case() -> dict:
    return {
        "snapshot_id": "snap_trump",
        "event_id": "trump_visit",
        "platforms": ["weibo", "douyin", "xhs"],
        "posts": [
            {
                "post_id": "p1",
                "author_id": "u1",
                "platform": "weibo",
                "timestamp": "2026-05-11T00:00:00Z",
                "content": "rumor claim about Trump visit with fake attack framing",
                "media_urls": ["https://cdn.example.test/a.jpg"],
                "ocr_text": "fake attack",
            },
            {
                "post_id": "p2",
                "author_id": "u2",
                "platform": "douyin",
                "timestamp": "2026-05-11T00:05:00Z",
                "content": "Trump visit rumor repost",
                "repost_id": "p1",
            },
        ],
        "comments": [
            {
                "comment_id": "c1",
                "post_id": "p1",
                "author_id": "u3",
                "platform": "xhs",
                "timestamp": "2026-05-11T00:06:00Z",
                "content": "needs evidence",
            }
        ],
        "relationships": [
            {
                "relation_type": "repost",
                "source_id": "p1",
                "target_id": "p2",
                "platform": "douyin",
                "evidence_ref": "p1:p2",
            }
        ],
        "quality_report": {"status": "pass", "issues": []},
        "options": {},
    }


def test_student_runtime_returns_preliminary_verdict_and_active_learning_signal():
    verdict = build_student_verdict(_case())

    assert verdict["technology"] == "student"
    assert verdict["schema"] == "cogguard.kt3.review_verdict.v2"
    assert verdict["verdict_type"] == "preliminary"
    assert verdict["model_version"] == "kt3-student-runtime-v2"
    assert verdict["model_status"] == "shadow_untrained"
    assert verdict["review_required"] is True
    assert verdict["architecture"]["post_encoder"] == "xlm-roberta-base"
    assert "teacher_kl" in verdict["distillation"]["losses"]
    assert verdict["signals"]["active_learning"]["policy"]["feedback_threshold"] == 200


def test_teacher_runtime_runs_5_plus_1_plus_1_dag_without_canonicalizing():
    student = build_student_verdict(_case())
    teacher = build_teacher_advisory_verdict(_case(), job_id="teacher_job_test")

    assert teacher["technology"] == "teacher"
    assert teacher["schema"] == "cogguard.kt3.teacher_dag.v2"
    assert teacher["verdict_type"] == "teacher_advisory"
    assert teacher["verdict_id"] == "teacher_job_test"
    assert teacher["canonical_allowed"] is False
    assert teacher["reasoning_trace_saved"] is False
    assert [node["node"] for node in teacher["dag"]["nodes"]] == [
        "claim_planning",
        "trusted_retrieval",
        "text_verification",
        "multimodal_verification",
        "harm_stance_context",
        "gold_aggregator",
        "critic_judge",
    ]
    assert teacher["signals"]["student_reference"]["verdict_id"] == student["verdict_id"]


def test_governance_requires_analyst_approval_for_canonical_verdict():
    source = build_student_verdict(_case())
    canonical = approve_canonical_verdict(source, approved_by=7, approval_notes="reviewed evidence")

    assert canonical["verdict_type"] == "canonical"
    assert canonical["canonical_source_id"] == source["verdict_id"]
    assert canonical["approved_by"] == 7
    assert canonical["immutable_source"] == "analysis.governance.canonical_approval.v1"


def test_model_activation_and_rollback_decisions_are_auditable():
    candidate = {
        "technology": "kt3_student",
        "version": "student-v3",
        "quality_gates": {
            "latency_passed": True,
            "calibration_passed": True,
            "safety_passed": True,
        },
    }
    previous = {"technology": "kt3_student", "model_version_id": 11}

    activation = build_model_activation_decision(candidate, approved_by=[7, 8], previous_activation=previous)
    rollback = build_rollback_decision(
        {"technology": "kt3_student", "model_version_id": 12},
        previous,
        reason="calibration drift",
        requested_by=7,
    )

    assert activation["activation_allowed"] is True
    assert activation["rollback_pointer"] == 11
    assert rollback["to_model_version_id"] == 11
    assert rollback["rule_authority_preserved"] is True


def test_active_learning_selector_uses_runtime_priority():
    selected = select_active_learning_cases(
        [
            {"verdict_id": "a", "active_learning": {"priority": 0.1, "reasons": ["random_audit"]}},
            {"verdict_id": "b", "active_learning": {"priority": 0.9, "reasons": ["uncertainty"]}},
        ],
        budget=1,
    )

    assert selected["selected_count"] == 1
    assert selected["selected"][0]["case_id"] == "b"
    assert "uncertainty" in selected["selected"][0]["reasons"]
