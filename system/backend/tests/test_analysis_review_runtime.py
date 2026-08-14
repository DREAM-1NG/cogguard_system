from __future__ import annotations

import asyncio
import json
from unittest.mock import AsyncMock

import pytest

from app.core.analysis import runtime
from app.core.analysis.governance import (
    approve_canonical_verdict,
    build_model_activation_decision,
    build_rollback_decision,
    select_active_learning_cases,
)
from app.core.analysis.runtime import build_student_verdict, build_teacher_advisory_verdict


def test_runtime_exposes_only_active_review_entry_points():
    assert set(runtime.__all__) == {
        "ANALYSIS_STUDENT_MODEL_VERSION",
        "ANALYSIS_TEACHER_MODEL_VERSION",
        "ANALYSIS_TEACHER_SOURCE",
        "InternalStudentRuntime",
        "InternalTeacherJobPort",
        "build_student_verdict",
        "build_teacher_advisory_verdict",
        "build_teacher_advisory_verdict_async",
        "submit_teacher_review_job",
        "finalize_teacher_review_job",
        "mark_teacher_review_failed",
    }
    assert not hasattr(runtime, "_legacy_build_student_verdict")
    assert not hasattr(runtime, "_legacy_build_teacher_advisory_verdict")


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
    assert verdict["schema"] == "cogguard.review.review_verdict.v2"
    assert verdict["verdict_type"] == "preliminary"
    assert verdict["model_version"] == "review-student-runtime-v2"
    assert verdict["model_status"] == "shadow_untrained"
    assert verdict["review_required"] is True
    assert verdict["architecture"]["post_encoder"] == "xlm-roberta-base"
    assert "teacher_kl" in verdict["distillation"]["losses"]
    assert verdict["signals"]["active_learning"]["policy"]["feedback_threshold"] == 200


def test_teacher_runtime_runs_5_plus_1_plus_1_dag_without_canonicalizing():
    student = build_student_verdict(_case())
    teacher = build_teacher_advisory_verdict(_case(), job_id="teacher_job_test")

    assert teacher["technology"] == "teacher"
    assert teacher["schema"] == "cogguard.review.teacher_dag.v2"
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


def test_teacher_job_uses_maro_chain_when_text_provider_is_available(monkeypatch):
    captured: dict = {}

    async def provider_context(_case):
        return {
            "provider": object(),
            "provider_name": "database",
            "model": "review-model",
            "include_media_base64": False,
            "require_vision": False,
            "policy": {"policy_id": "policy-active", "policy": {"review_threshold": 0.6}},
            "error_memory_summary": {"feedback_count": 2},
        }

    async def maro_review(**kwargs):
        captured.update(kwargs)
        return {
            "summary": {"completed": 6, "failed": 0},
            "audit": {"execution_plan": {"executed_agents": ["PostHarmAgent", "QuestionReflectionAgent", "HarmfulnessJudgeAgent"]}},
            "agent_reports": [
                {"agent_name": "PostHarmAgent", "status": "completed", "report_text": "Expert assessment."},
                {"agent_name": "QuestionReflectionAgent", "status": "completed", "report_text": "Ask for evidence."},
                {"agent_name": "PostHarmAgentReflectionResponse", "status": "completed", "report_role": "reflection_response", "report_text": "Expert response."},
                {"agent_name": "HarmfulnessJudgeAgent", "status": "completed", "report_text": "Needs human review."},
            ],
        }

    monkeypatch.setattr(runtime, "_resolve_teacher_maro_context", provider_context)
    monkeypatch.setattr(runtime, "run_manual_agent_review", maro_review)

    verdict = asyncio.run(runtime.build_teacher_advisory_verdict_async(_case(), job_id="teacher_maro"))

    assert verdict["execution_mode"] == "maro_llm"
    assert verdict["fallback_reason"] is None
    assert verdict["non_claimable"] is True
    assert verdict["canonical_allowed"] is False
    assert verdict["dag"]["version"] == "maro-expert-question-reflection-judge"
    assert captured["agent_names"] == [
        "PostHarmAgent",
        "MultimodalConsistencyAgent",
        "ClaimEvidenceAgent",
        "PropagationTreeAgent",
        "QuestionReflectionAgent",
        "HarmfulnessJudgeAgent",
    ]
    assert captured["policy"]["policy_id"] == "policy-active"
    assert captured["error_memory_summary"] == {"feedback_count": 2}


def test_teacher_job_marks_dag_fallback_as_non_claimable_when_provider_is_unavailable(monkeypatch):
    async def no_provider(_case):
        return {
            "provider": None,
            "provider_name": "not_configured",
            "model": "",
            "include_media_base64": False,
            "require_vision": False,
            "policy": None,
            "error_memory_summary": {},
        }

    monkeypatch.setattr(runtime, "_resolve_teacher_maro_context", no_provider)

    verdict = asyncio.run(runtime.build_teacher_advisory_verdict_async(_case(), job_id="teacher_fallback"))

    assert verdict["execution_mode"] == "deterministic_dag_fallback"
    assert verdict["fallback_reason"] == "text_llm_provider_unavailable"
    assert verdict["non_claimable"] is True
    assert verdict["canonical_allowed"] is False


def test_completed_teacher_job_fails_when_advisory_is_not_persisted(monkeypatch):
    verdict = {"verdict_id": "teacher_job_test", "status": "completed"}

    async def build_verdict(*_args, **_kwargs):
        return verdict

    async def persistence_failed(**_kwargs):
        return False

    monkeypatch.setattr(runtime, "build_teacher_advisory_verdict_async", build_verdict)
    monkeypatch.setattr(runtime, "_persist_teacher_review_row", persistence_failed)

    with pytest.raises(RuntimeError, match="was not persisted"):
        asyncio.run(runtime.finalize_teacher_review_job("teacher_job_test", _case()))


def test_completed_teacher_job_preserves_analysis_run_lineage(monkeypatch):
    captured: dict = {}
    verdict = {"verdict_id": "teacher_job_test", "status": "completed"}
    case = {**_case(), "run_id": "run_teacher_1"}

    async def build_verdict(*_args, **_kwargs):
        return verdict

    async def persisted(**kwargs):
        captured.update(kwargs)
        return True

    monkeypatch.setattr(runtime, "build_teacher_advisory_verdict_async", build_verdict)
    monkeypatch.setattr(runtime, "_persist_teacher_review_row", persisted)

    asyncio.run(runtime.finalize_teacher_review_job("teacher_job_test", case))

    assert captured["case"]["run_id"] == "run_teacher_1"


def test_queue_required_policy_persists_a_dispatch_failure(monkeypatch):
    class FailingTask:
        def delay(self, *_args, **_kwargs):
            raise ConnectionError("broker unavailable")

    async def scenario():
        persisted = AsyncMock(return_value=True)
        monkeypatch.setattr(
            "app.tasks.analysis_tasks.execute_analysis_teacher_review",
            FailingTask(),
        )
        monkeypatch.setattr(runtime, "_persist_teacher_review_row", persisted)
        monkeypatch.setattr(runtime.settings, "ANALYSIS_TEACHER_DISPATCH_MODE", "queue_required")
        monkeypatch.setattr(runtime.settings, "BACKEND_ENV", "production")
        runtime.TEACHER_JOB_CACHE.clear()

        result = await runtime._queue_teacher_review_job(
            job_id="teacher_failure",
            case={"snapshot_id": "snapshot_1", "event_id": "event_1", "platforms": ["weibo"]},
        )

        assert result["status"] == "failed"
        assert result["task_state"] == "dispatch_failed"
        assert result["dispatch_backend"] == "queue_required"
        assert result["retryable"] is True
        persisted.assert_awaited_once()
        assert persisted.await_args.kwargs["status"] == "failed"
        assert runtime.TEACHER_JOB_CACHE["teacher_failure"]["status"] == "failed"

    asyncio.run(scenario())


def test_local_dispatch_failure_uses_the_explicit_inline_fallback(monkeypatch):
    class FailingTask:
        def delay(self, *_args, **_kwargs):
            raise ConnectionError("broker unavailable")

    async def scenario():
        scheduled = []

        def capture_task(coroutine):
            scheduled.append(coroutine)
            coroutine.close()
            return object()

        monkeypatch.setattr(
            "app.tasks.analysis_tasks.execute_analysis_teacher_review",
            FailingTask(),
        )
        monkeypatch.setattr(runtime.asyncio, "create_task", capture_task)
        monkeypatch.setattr(runtime.settings, "ANALYSIS_TEACHER_DISPATCH_MODE", "local_inline_fallback")
        monkeypatch.setattr(runtime.settings, "BACKEND_ENV", "local")
        runtime.TEACHER_JOB_CACHE.clear()

        result = await runtime._queue_teacher_review_job(
            job_id="teacher_local_failure",
            case={"snapshot_id": "snapshot_1", "event_id": "event_1", "platforms": ["weibo"]},
        )

        assert result["dispatch_backend"] == "local_inline_fallback"
        assert "dispatch_error" in result
        assert len(scheduled) == 1

    asyncio.run(scenario())


def test_teacher_advisory_payload_is_serializable_for_persistence():
    verdict = build_teacher_advisory_verdict(_case(), job_id="teacher_job_test")

    persisted = json.loads(runtime._json_dumps(verdict))

    assert persisted["verdict_id"] == "teacher_job_test"
    assert persisted["status"] == "completed"


def test_governance_requires_analyst_approval_for_canonical_verdict():
    source = build_student_verdict(_case())
    canonical = approve_canonical_verdict(source, approved_by=7, approval_notes="reviewed evidence")

    assert canonical["verdict_type"] == "canonical"
    assert canonical["canonical_source_id"] == source["verdict_id"]
    assert canonical["approved_by"] == 7
    assert canonical["immutable_source"] == "analysis.governance.canonical_approval.v1"


def test_model_activation_and_rollback_decisions_are_auditable():
    candidate = {
        "technology": "review_student",
        "version": "student-v3",
        "quality_gates": {
            "latency_passed": True,
            "calibration_passed": True,
            "safety_passed": True,
        },
    }
    previous = {"technology": "review_student", "model_version_id": 11}

    activation = build_model_activation_decision(candidate, approved_by=[7, 8], previous_activation=previous)
    rollback = build_rollback_decision(
        {"technology": "review_student", "model_version_id": 12},
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
