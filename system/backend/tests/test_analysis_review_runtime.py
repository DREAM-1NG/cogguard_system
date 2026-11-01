from __future__ import annotations

import asyncio
import json
from pathlib import Path
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


def test_runtime_does_not_import_retired_deterministic_builder_dependencies():
    source = Path(runtime.__file__).read_text(encoding="utf-8")

    retired_imports = {
        "from collections import Counter, defaultdict",
        "from app.core.review.layered_harmfulness import assess_layered_harmfulness",
        "from app.core.review.multi_agent import execute_multi_agent_review",
        "from app.core.review.review_executor import execute_review_queue",
        "from app.core.review.review_queue import build_review_queue",
        "from app.core.review.trainable_post import build_agent_review",
        "from app.core.review.trainable_post import fuse_detector_outputs",
        "from app.core.review.trainable_post import standard_detector_output",
        "from app.core.review.post_semantics import assess_post_semantics",
    }

    assert all(import_line not in source for import_line in retired_imports)


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


def test_student_runtime_is_explicitly_unconfigured_without_an_approved_bundle():
    verdict = build_student_verdict(_case())

    assert verdict["technology"] == "student"
    assert verdict["schema"] == "cogguard.review.student_bundle.v1"
    assert verdict["verdict_type"] == "preliminary"
    assert verdict["status"] == "unconfigured"
    assert verdict["axes"]["interpersonal_harm"]["status"] == "unconfigured"
    assert verdict["axes"]["claim_deception"]["status"] == "unconfigured"
    assert verdict["fallback"] is False
    assert verdict["review_required"] is True


def test_synchronous_teacher_entry_point_never_substitutes_a_deterministic_dag():
    teacher = build_teacher_advisory_verdict(_case(), job_id="teacher_job_test")

    assert teacher["technology"] == "teacher"
    assert teacher["schema"] == "cogguard.review.teacher_audit.v1"
    assert teacher["verdict_type"] == "teacher_advisory"
    assert teacher["verdict_id"] == "teacher_job_test"
    assert teacher["canonical_allowed"] is False
    assert teacher["status"] == "failed"
    assert teacher["task_state"] == "async_provider_required"
    assert "dag" not in teacher


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
    assert captured["agent_names"] == ["HarmfulnessJudgeAgent", "CountermeasureAgent"]
    assert captured["run_experts"] is False
    assert captured["policy"]["policy_id"] == "policy-active"
    assert captured["error_memory_summary"] == {"feedback_count": 2}


def test_teacher_chain_limits_agents_to_the_explicitly_selected_posts(monkeypatch):
    case = _case()
    case["posts"] = [
        {"post_id": "p1", "platform": "weibo", "content": "first", "likes": 100},
        {"post_id": "p2", "platform": "douyin", "content": "second", "likes": 500},
    ]
    case["options"] = {
        "teacher": {
            "review_tasks": ["interpersonal_harm"],
            "evidence_refs": ["post:p1"],
        }
    }
    calls: list[dict] = []

    async def manual_review(**kwargs):
        calls.append(kwargs)
        agents = kwargs["agent_names"]
        reports = [
            {
                "agent_name": name,
                "status": "completed",
                "report_role": "judge" if name == "HarmfulnessJudgeAgent" else "expert_initial",
                "report_text": "Bounded result.",
            }
            for name in agents
        ]
        return {
            "summary": {"completed": len(reports), "failed": 0},
            "audit": {"execution_plan": {"executed_agents": agents}},
            "agent_reports": reports,
        }

    monkeypatch.setattr(runtime, "run_manual_agent_review", manual_review)

    result = asyncio.run(
        runtime._run_teacher_maro_chain(
            runtime._normalize_case(case),
            student={"label": "non_harmful", "score": 0.1},
            job_id="teacher_selection",
            provider=object(),
            maro_context={
                "model": "test-model",
                "provider_name": "test-provider",
                "policy": None,
                "error_memory_summary": {},
            },
        )
    )

    assert len(calls) == 2
    assert all(call["selected_post_ids"] == ["p1"] for call in calls)
    assert result["audit_input_selection"]["source"] == "analyst_selected"
    assert [item["post_id"] for item in result["audit_input_selection"]["items"]] == ["p1"]


def test_teacher_job_persists_failure_when_provider_is_unavailable(monkeypatch):
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

    assert verdict["execution_mode"] == "maro_llm"
    assert verdict["status"] == "failed"
    assert verdict["task_state"] == "text_llm_provider_unavailable"
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
    assert persisted["status"] == "failed"


def test_queued_teacher_job_includes_verdict_id_for_provenance_persistence(monkeypatch):
    captured: dict = {}

    async def persisted(**kwargs):
        captured.update(kwargs)
        return True

    async def dispatched(**_kwargs):
        return {"dispatch_backend": "test"}

    monkeypatch.setattr(runtime, "_persist_teacher_review_row", persisted)
    monkeypatch.setattr(runtime, "_queue_teacher_review_job", dispatched)

    result = asyncio.run(runtime.submit_teacher_review_job(_case()))

    assert result["job_id"] == result["verdict_id"]
    assert captured["verdict"]["verdict_id"] == result["job_id"]


def test_each_human_triggered_teacher_audit_gets_an_independent_verdict_id(monkeypatch):
    persisted: list[dict] = []

    async def record(**kwargs):
        persisted.append(kwargs)
        return True

    async def dispatched(**_kwargs):
        return {"dispatch_backend": "test"}

    monkeypatch.setattr(runtime, "_persist_teacher_review_row", record)
    monkeypatch.setattr(runtime, "_queue_teacher_review_job", dispatched)

    first = asyncio.run(runtime.submit_teacher_review_job(_case()))
    second = asyncio.run(runtime.submit_teacher_review_job(_case()))

    assert first["job_id"] != second["job_id"]
    assert first["job_id"].startswith("teacher_")
    assert second["job_id"].startswith("teacher_")
    assert [item["verdict"]["verdict_id"] for item in persisted] == [
        first["job_id"],
        second["job_id"],
    ]


def test_dedicated_review_teacher_provider_does_not_inherit_generic_llm_gateway(monkeypatch):
    monkeypatch.setattr(runtime.settings, "REVIEW_TEACHER_API_KEY", "teacher-key")
    monkeypatch.setattr(runtime.settings, "REVIEW_TEACHER_API_BASE", "https://api.deepseek.com/v1")
    monkeypatch.setattr(runtime.settings, "REVIEW_TEACHER_MODEL", "deepseek-chat")
    monkeypatch.setattr(runtime.settings, "REVIEW_TEACHER_API_WIRE", "chat_completions")
    monkeypatch.setattr(runtime.settings, "LLM_API_BASE", "https://unrelated.example/v1")

    provider = runtime._build_review_teacher_provider()

    assert provider is not None
    assert provider.config.base_url == "https://api.deepseek.com/v1"
    assert provider.config.model == "deepseek-chat"
    assert provider.config.wire_api == "chat_completions"


def test_teacher_persistence_projection_drops_large_intermediate_agent_material():
    large_text = "x" * 200_000
    verdict = {
        "technology": "teacher",
        "status": "completed",
        "verdict_id": "teacher_1",
        "snapshot_id": "snapshot_1",
        "event_id": "event_1",
        "evidence": {
            "agent_reports": [
                {
                    "agent_name": "HarmfulnessJudgeAgent",
                    "report_role": "judge",
                    "status": "completed",
                    "report_text": large_text,
                    "system_audit_sidecar": {
                        "rationale_capsule": {
                            "capsule_text": "Bounded rationale.",
                            "input_spans": ["input span"],
                            "capsule_quality_gate": True,
                        },
                        "governance_report": {
                            "governance_category": "Hate and harassment",
                            "platform_reference_refs": [
                                {
                                    "ref_id": "policy_1",
                                    "title": "Policy reference",
                                    "url": "https://example.test/policy",
                                }
                            ],
                        },
                    },
                }
            ]
        },
    }

    persisted = runtime._teacher_persistence_payload(verdict)

    assert len(runtime._json_dumps(persisted).encode("utf-8")) < 56_000
    report = persisted["evidence"]["agent_reports"][0]
    assert len(report["report_text"]) == 1_600
    assert report["system_audit_sidecar"]["rationale_capsule"]["capsule_text"] == "Bounded rationale."
    assert report["system_audit_sidecar"]["governance_report"]["platform_reference_refs"][0]["ref_id"] == "policy_1"


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
