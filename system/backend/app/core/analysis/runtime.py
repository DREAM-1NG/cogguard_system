"""Internal analysis runtimes for the Review student/teacher seam."""

from __future__ import annotations

import asyncio
import hashlib
import json
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from sqlalchemy import select

from app.core.review.agent_provider import OpenAICompatibleAgentProvider
from app.core.review.agent_provider import OpenAICompatibleConfig
from app.core.review.agent_review import run_manual_agent_review
from app.core.review.representative_posts import select_representative_posts
from app.core.review.student_bundle_runtime import build_student_bundle_verdict
from app.config import settings
from app.db.mysql import async_session_factory
from app.models.analysis import ReviewVerdictVersion
from app.utils.logger import logger


ANALYSIS_STUDENT_MODEL_VERSION = "analysis-student-runtime-v1"
ANALYSIS_TEACHER_MODEL_VERSION = "analysis-teacher-runtime-v1"
ANALYSIS_TEACHER_SOURCE = "analysis.teacher.runtime.v1"
TEACHER_JOB_CACHE: dict[str, dict[str, Any]] = {}

__all__ = [
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
]


class InternalStudentRuntime:
    async def predict(self, case: dict[str, Any]) -> dict[str, Any]:
        return build_student_verdict(case)


class InternalTeacherJobPort:
    async def submit(self, case: dict[str, Any]) -> dict[str, Any]:
        return await submit_teacher_review_job(case)


def build_student_verdict(case: dict[str, Any]) -> dict[str, Any]:
    """Run the approved Student bundle without a heuristic shadow fallback."""

    return build_student_bundle_verdict(case)


def build_teacher_advisory_verdict(
    case: dict[str, Any],
    *,
    job_id: str | None = None,
) -> dict[str, Any]:
    return _teacher_failure(
        _normalize_case(case),
        job_id=job_id,
        reason="Teacher audits require the asynchronous MARO-compatible provider chain.",
        task_state="async_provider_required",
    )


async def build_teacher_advisory_verdict_async(
    case: dict[str, Any],
    *,
    job_id: str | None = None,
) -> dict[str, Any]:
    """Build a non-canonical Teacher advisory through MARO when an LLM is available."""
    normalized = _normalize_case(case)
    student = build_student_verdict(case)
    if not normalized["posts"]:
        return _teacher_failure(
            normalized,
            job_id=job_id,
            reason="The Teacher audit could not start because this snapshot has no text posts.",
            task_state="input_unavailable",
        )

    maro_context = await _resolve_teacher_maro_context(normalized)
    provider = maro_context["provider"]
    if provider is None:
        return _teacher_failure(
            normalized,
            job_id=job_id,
            reason="The configured Teacher provider is unavailable.",
            task_state=maro_context.get("fallback_reason") or "text_llm_provider_unavailable",
        )

    try:
        maro_result = await _run_teacher_maro_chain(
            normalized,
            student=student,
            job_id=job_id,
            provider=provider,
            maro_context=maro_context,
        )
    except Exception as exc:
        return _teacher_failure(
            normalized,
            job_id=job_id,
            reason="The Teacher audit provider or orchestration chain failed.",
            task_state=f"maro_runtime_error:{type(exc).__name__}",
        )
    finally:
        close_provider = getattr(provider, "aclose", None)
        if callable(close_provider):
            await close_provider()

    if not _teacher_maro_chain_completed(maro_result):
        return _teacher_failure(
            normalized,
            job_id=job_id,
            reason="The Teacher audit did not return all required bounded stages.",
            task_state="maro_chain_incomplete",
        )
    return _teacher_maro_advisory(
        normalized,
        student=student,
        job_id=job_id,
        maro_result=maro_result,
        provider_name=maro_context["provider_name"],
        model=maro_context["model"],
    )


async def submit_teacher_review_job(
    case: dict[str, Any], *, review_tasks: list[str] | None = None
) -> dict[str, Any]:
    normalized = _normalize_case(case)
    if review_tasks:
        normalized["options"] = {
            **normalized["options"],
            "teacher": {**dict(normalized["options"].get("teacher") or {}), "review_tasks": review_tasks},
        }
    # A human-triggered audit is an immutable review instance.  A stable
    # snapshot digest would overwrite an earlier audit of the same snapshot.
    job_id = _teacher_job_id(normalized)
    queued_result = {
        "technology": "teacher",
        "job_id": job_id,
        "verdict_id": job_id,
        "status": "queued",
        "verdict_type": "teacher_advisory",
        "snapshot_id": normalized["snapshot_id"],
        "event_id": normalized["event_id"],
        "platforms": normalized["platforms"],
        "model_version": ANALYSIS_TEACHER_MODEL_VERSION,
        "task_state": "submitted",
        "review_tasks": _teacher_review_tasks(normalized),
        "capability_boundary": _capability_boundary("teacher"),
    }
    TEACHER_JOB_CACHE[job_id] = queued_result
    await _persist_teacher_review_row(job_id=job_id, case=normalized, verdict=queued_result, status="draft")
    dispatch = await _queue_teacher_review_job(job_id=job_id, case=normalized)
    queued_result.update(dispatch)
    return queued_result


async def finalize_teacher_review_job(job_id: str, case: dict[str, Any]) -> dict[str, Any]:
    verdict = await build_teacher_advisory_verdict_async(case, job_id=job_id)
    TEACHER_JOB_CACHE[job_id] = verdict
    persisted = await _persist_teacher_review_row(
        job_id=job_id,
        case=_normalize_case(case),
        verdict=verdict,
        status="completed" if verdict.get("status") == "completed" else "failed",
    )
    if not persisted:
        raise RuntimeError(f"Teacher advisory was not persisted: {job_id}")
    return verdict


async def _resolve_teacher_maro_context(case: dict[str, Any]) -> dict[str, Any]:
    """Resolve MARO dependencies without importing analysis from Review modules."""
    fallback = {
        "provider": None,
        "provider_name": "not_configured",
        "model": "",
        "include_media_base64": False,
        "require_vision": False,
        "policy": None,
        "error_memory_summary": {},
        "fallback_reason": "text_llm_provider_unavailable",
    }
    policy = None
    feedback_memory: list[dict[str, Any]] = []
    try:
        from app.models.review_system import ReviewProviderConfig
        from app.services import review_system_service

        async with async_session_factory() as db:
            result = await db.execute(
                select(ReviewProviderConfig)
                .where(ReviewProviderConfig.provider_type == "text_llm")
                .where(ReviewProviderConfig.is_active.is_(True))
                .order_by(ReviewProviderConfig.id.desc())
                .limit(1)
            )
            row = result.scalar_one_or_none()
            policy = await review_system_service.get_active_policy_artifact(db)
            feedback_memory = await review_system_service.feedback_memory_from_db([], db)
        if row is not None and row.encrypted_api_key:
            api_key = review_system_service.decrypt_provider_api_key(row.encrypted_api_key)
            if api_key and row.base_url and row.model:
                return {
                    "provider": OpenAICompatibleAgentProvider(
                        OpenAICompatibleConfig(
                            api_key=api_key,
                            base_url=row.base_url,
                            model=row.model,
                            wire_api=row.wire_api,
                            timeout_seconds=float(settings.LLM_TIMEOUT_SECONDS),
                            include_media_base64=bool(row.supports_vision),
                            require_vision=False,
                        )
                    ),
                    "provider_name": "database",
                    "model": row.model,
                    "include_media_base64": bool(row.supports_vision),
                    "require_vision": False,
                    "policy": policy,
                    "error_memory_summary": _teacher_feedback_memory(policy, feedback_memory),
                    "fallback_reason": None,
                }
    except Exception as exc:
        logger.warning("Teacher MARO database context unavailable: {}", type(exc).__name__)

    provider = _build_review_teacher_provider()
    if provider is None:
        return fallback
    return {
        "provider": provider,
        "provider_name": "review_teacher_env",
        "model": str(settings.REVIEW_TEACHER_MODEL),
        "include_media_base64": False,
        "require_vision": False,
        "policy": policy,
        "error_memory_summary": _teacher_feedback_memory(policy, feedback_memory),
        "fallback_reason": None,
    }


def _build_review_teacher_provider() -> OpenAICompatibleAgentProvider | None:
    """Build only the dedicated, local Teacher provider configuration."""

    api_key = str(
        settings.REVIEW_TEACHER_API_KEY or settings.DEEPSEEK_API_KEY or ""
    ).strip()
    if not api_key:
        return None
    return OpenAICompatibleAgentProvider(
        OpenAICompatibleConfig(
            api_key=api_key,
            base_url=str(settings.REVIEW_TEACHER_API_BASE),
            model=str(settings.REVIEW_TEACHER_MODEL),
            wire_api=str(settings.REVIEW_TEACHER_API_WIRE),
            timeout_seconds=float(settings.LLM_TIMEOUT_SECONDS),
            include_media_base64=False,
            require_vision=False,
        )
    )


def _teacher_feedback_memory(policy: dict[str, Any] | None, feedback_memory: list[dict[str, Any]]) -> dict[str, Any]:
    policy_memory = dict((policy or {}).get("error_memory_summary") or {})
    if feedback_memory:
        policy_memory["memory_records"] = feedback_memory
        policy_memory["feedback_count"] = len(feedback_memory)
    return policy_memory


def _teacher_maro_report(
    case: dict[str, Any],
    *,
    student: dict[str, Any],
    job_id: str | None,
    selected_posts: list[dict[str, Any]],
) -> dict[str, Any]:
    posts = []
    for row in selected_posts:
        post_id = str(row.get("post_id") or row.get("id") or "")
        posts.append(
            {
                **row,
                "post_id": post_id,
                "harmfulness": {"score": student.get("score"), "abstain": student.get("abstain")},
                "post_view_detection": {
                    "review_reason": student.get("review_reason") or [],
                    "final_harmfulness": student.get("label"),
                },
            }
        )
    return {
        "report_id": job_id or _verdict_id("teacher", case),
        "event_id": case["event_id"],
        "platform": case["platform"],
        "post_semantics": {"posts": posts},
        "review_harmfulness": {
            "review_queue": {
                "review_items": [{"post_id": row["post_id"]} for row in posts],
                "retrieval_tasks": [{"post_id": row["post_id"]} for row in posts if row.get("content")],
            },
            "propagation_context": {"has_thread_context": bool(case["relationships"])},
        },
    }


async def _run_teacher_maro_chain(
    case: dict[str, Any],
    *,
    student: dict[str, Any],
    job_id: str | None,
    provider: Any,
    maro_context: dict[str, Any],
) -> dict[str, Any]:
    """Run isolated task branches followed by one bounded Judge synthesis."""

    selected_posts, selection = _teacher_selected_posts(case)
    base_report = _teacher_maro_report(
        case,
        student=student,
        job_id=job_id,
        selected_posts=selected_posts,
    )
    case_id = job_id or _verdict_id("teacher", case)
    post_ids = [str(row.get("post_id") or row.get("id") or "") for row in selected_posts]
    tasks = _teacher_review_tasks(case)
    branches: list[dict[str, Any]] = []
    for task in tasks:
        expert = "PostHarmAgent" if task == "interpersonal_harm" else "ClaimEvidenceAgent"
        branch = await run_manual_agent_review(
            report=base_report,
            agent_names=[expert, "QuestionReflectionAgent"],
            case_id=case_id,
            selected_post_ids=post_ids,
            human_triggered_by=case["created_by"],
            provider=provider,
            model=maro_context["model"],
            provider_name=maro_context["provider_name"],
            include_media_base64=False,
            require_vision=False,
            runtime_mode="complex",
            policy=maro_context["policy"],
            error_memory_summary=maro_context["error_memory_summary"],
            enable_countermeasure=False,
            review_task=task,
            run_judge=False,
        )
        branches.append({"task": task, **branch})

    branch_reports = [
        item
        for branch in branches
        for item in branch.get("agent_reports") or []
        if isinstance(item, dict)
    ]
    synthesis = await run_manual_agent_review(
        report={**base_report, "agent_reviews": branch_reports},
        agent_names=["HarmfulnessJudgeAgent", "CountermeasureAgent"],
        case_id=case_id,
        selected_post_ids=post_ids,
        human_triggered_by=case["created_by"],
        provider=provider,
        model=maro_context["model"],
        provider_name=maro_context["provider_name"],
        include_media_base64=False,
        require_vision=False,
        runtime_mode="complex",
        policy=maro_context["policy"],
        error_memory_summary=maro_context["error_memory_summary"],
        review_task="interpersonal_harm",
        run_experts=False,
    )
    return {
        **synthesis,
        "agent_reports": [*branch_reports, *list(synthesis.get("agent_reports") or [])],
        "task_branches": branches,
        "review_tasks": tasks,
        "audit_input_selection": selection,
    }


def _teacher_selected_posts(case: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    teacher = dict(case.get("options", {}).get("teacher") or {})
    rows, selection = select_representative_posts(
        case["posts"],
        selected_post_ids=teacher.get("evidence_refs"),
        limit=int(teacher.get("max_review_posts") or 6),
    )
    return [dict(row.get("row") or {}) for row in rows], selection


def _teacher_review_tasks(case: dict[str, Any]) -> list[str]:
    teacher = dict(case.get("options", {}).get("teacher") or {})
    values = teacher.get("review_tasks") or ["interpersonal_harm"]
    values = values if isinstance(values, list) else [values]
    result = [
        str(item).strip()
        for item in values
        if str(item).strip() in {"interpersonal_harm", "claim_deception"}
    ]
    return result or ["interpersonal_harm"]


def _teacher_failure(
    case: dict[str, Any],
    *,
    job_id: str | None,
    reason: str,
    task_state: str,
) -> dict[str, Any]:
    verdict_id = job_id or _verdict_id("teacher", case)
    return {
        "technology": "teacher",
        "schema": "cogguard.review.teacher_audit.v1",
        "status": "failed",
        "verdict_type": "teacher_advisory",
        "verdict_id": verdict_id,
        "snapshot_id": case["snapshot_id"],
        "event_id": case["event_id"],
        "platforms": case["platforms"],
        "model_version": ANALYSIS_TEACHER_MODEL_VERSION,
        "execution_mode": "maro_llm",
        "task_state": task_state,
        "reason": reason,
        "review_tasks": _teacher_review_tasks(case),
        "non_claimable": True,
        "canonical_allowed": False,
        "review_required": True,
        "countermeasure_report": {
            "schema": "cogguard.review.countermeasure_report.v1",
            "status": "not_generated",
            "case_id": "",
            "snapshot_id": case["snapshot_id"],
            "teacher_audit_id": verdict_id,
            "reason": "Countermeasure report was not generated because the Teacher audit failed.",
            "quality_gate": False,
        },
        "capability_boundary": _teacher_capability_boundary("maro_llm"),
    }


def _teacher_maro_advisory(
    case: dict[str, Any],
    *,
    student: dict[str, Any],
    job_id: str | None,
    maro_result: dict[str, Any],
    provider_name: str,
    model: str,
) -> dict[str, Any]:
    reports = [item for item in maro_result.get("agent_reports") or [] if isinstance(item, dict)]
    completed = [item for item in reports if item.get("status") == "completed"]
    judge = next((item for item in reversed(completed) if item.get("agent_name") == "HarmfulnessJudgeAgent"), None)
    return {
        "technology": "teacher",
        "schema": "cogguard.review.teacher_audit.v1",
        "status": "completed",
        "verdict_type": "teacher_advisory",
        "verdict_id": job_id or _verdict_id("teacher", case),
        "snapshot_id": case["snapshot_id"],
        "event_id": case["event_id"],
        "platforms": case["platforms"],
        "model_version": ANALYSIS_TEACHER_MODEL_VERSION,
        "execution_mode": "maro_llm",
        "fallback_reason": None,
        "non_claimable": True,
        "canonical_allowed": False,
        "reasoning_trace_saved": False,
        "review_required": True,
        "dag": _teacher_maro_dag(reports),
        "audit_input_selection": maro_result.get("audit_input_selection") or {},
        "advisory": {
            "decision": "needs_human_review",
            "recommended_actions": {"human_review": 1},
            "avg_agent_confidence": 0.0,
            "external_followup_required": True,
        },
        "summary": {**dict(maro_result.get("summary") or {}), "completed_agent_reports": len(completed)},
        "review_tasks": list(maro_result.get("review_tasks") or _teacher_review_tasks(case)),
        "signals": {
            "student_reference": {"verdict_id": student.get("verdict_id"), "label": student.get("label"), "score": student.get("score")},
            "maro": {"provider_name": provider_name, "model": model, "audit": maro_result.get("audit") or {}, "judge_report": judge},
        },
        "evidence": {"agent_reports": completed},
        "countermeasure_gate": dict(maro_result.get("countermeasure_gate") or {}),
        "countermeasure_report": dict(maro_result.get("countermeasure_report") or {}),
        "capability_boundary": _teacher_capability_boundary("maro_llm"),
    }


def _teacher_maro_chain_completed(maro_result: dict[str, Any]) -> bool:
    reports = [item for item in maro_result.get("agent_reports") or [] if isinstance(item, dict)]
    completed_names = {str(item.get("agent_name")) for item in reports if item.get("status") == "completed"}
    has_reflection_response = any(
        item.get("status") == "completed" and item.get("report_role") == "reflection_response"
        for item in reports
    )
    required = {"QuestionReflectionAgent", "HarmfulnessJudgeAgent"}
    tasks = list(maro_result.get("review_tasks") or ["interpersonal_harm"])
    if "interpersonal_harm" in tasks:
        required.add("PostHarmAgent")
    if "claim_deception" in tasks:
        required.add("ClaimEvidenceAgent")
    return required.issubset(completed_names) and has_reflection_response


def _teacher_maro_dag(reports: list[dict[str, Any]]) -> dict[str, Any]:
    report_by_name = {str(item.get("agent_name")): item for item in reports}
    nodes = []
    for agent_name in (
        "PostHarmAgent",
        "MultimodalConsistencyAgent",
        "ClaimEvidenceAgent",
        "PropagationTreeAgent",
        "QuestionReflectionAgent",
        "HarmfulnessJudgeAgent",
    ):
        report = report_by_name.get(agent_name) or {}
        nodes.append(
            {
                "node": agent_name,
                "status": report.get("status", "skipped"),
                "summary": str(report.get("report_text") or report.get("error") or "")[:240],
            }
        )
    nodes.extend(
        {
            "node": str(item.get("agent_name")),
            "status": item.get("status", "unknown"),
            "summary": str(item.get("report_text") or item.get("error") or "")[:240],
        }
        for item in reports
        if item.get("report_role") == "reflection_response"
    )
    return {"version": "maro-expert-question-reflection-judge", "nodes": nodes}


def _teacher_capability_boundary(execution_mode: str) -> dict[str, Any]:
    return {
        **_capability_boundary("teacher"),
        "execution_mode": execution_mode,
        "non_claimable": True,
        "analyst_approval_required": True,
        "detector_outputs_unchanged": True,
    }


async def _queue_teacher_review_job(job_id: str, case: dict[str, Any]) -> dict[str, Any]:
    try:
        from app.tasks.analysis_tasks import execute_analysis_teacher_review

        async_result = execute_analysis_teacher_review.delay(job_id, case)
        return {"task_id": async_result.id, "dispatch_backend": "celery"}
    except Exception as exc:
        if settings.teacher_inline_fallback_allowed:
            asyncio.create_task(_finalize_teacher_job_inline(job_id, case))
            return {
                "dispatch_backend": "local_inline_fallback",
                "dispatch_error": f"{type(exc).__name__}: {exc}",
            }
        return await mark_teacher_review_failed(
            job_id,
            case,
            task_state="dispatch_failed",
            dispatch_backend="queue_required",
            error_type=type(exc).__name__,
        )


async def _finalize_teacher_job_inline(job_id: str, case: dict[str, Any]) -> dict[str, Any]:
    return await finalize_teacher_review_job(job_id, case)


async def mark_teacher_review_failed(
    job_id: str,
    case: dict[str, Any],
    *,
    task_state: str,
    dispatch_backend: str,
    error_type: str,
) -> dict[str, Any]:
    """Persist an actionable failure instead of leaving a draft advisory stranded."""

    normalized = _normalize_case(case)
    verdict = {
        "technology": "teacher",
        "job_id": job_id,
        "verdict_id": job_id,
        "status": "failed",
        "verdict_type": "teacher_advisory",
        "snapshot_id": normalized["snapshot_id"],
        "event_id": normalized["event_id"],
        "platforms": normalized["platforms"],
        "model_version": ANALYSIS_TEACHER_MODEL_VERSION,
        "task_state": task_state,
        "dispatch_backend": dispatch_backend,
        "dispatch_error": error_type,
        "retryable": True,
        "review_required": True,
        "reason": "The independent review could not be completed. Retry the review or continue evidence collection.",
        "countermeasure_report": {
            "schema": "cogguard.review.countermeasure_report.v1",
            "status": "not_generated",
            "snapshot_id": normalized["snapshot_id"],
            "teacher_audit_id": job_id,
            "reason": "Countermeasure report was not generated because the Teacher audit failed.",
            "quality_gate": False,
        },
        "capability_boundary": _capability_boundary("teacher"),
    }
    TEACHER_JOB_CACHE[job_id] = verdict
    persisted = await _persist_teacher_review_row(
        job_id=job_id,
        case=normalized,
        verdict=verdict,
        status="failed",
    )
    if not persisted:
        verdict = {
            **verdict,
            "status": "persistence_failed",
            "task_state": "persistence_failed",
            "retryable": True,
        }
        TEACHER_JOB_CACHE[job_id] = verdict
    return verdict


async def _persist_teacher_review_row(
    *,
    job_id: str,
    case: dict[str, Any],
    verdict: dict[str, Any],
    status: str,
) -> bool:
    try:
        persisted_verdict = _teacher_persistence_payload(verdict)
        async with async_session_factory() as db:
            result = await db.execute(
                select(ReviewVerdictVersion).where(ReviewVerdictVersion.verdict_id == job_id)
            )
            row = result.scalar_one_or_none()
            if row is None:
                db.add(
                    ReviewVerdictVersion(
                        verdict_id=job_id,
                        run_id=_run_id(case, job_id),
                        snapshot_id=case["snapshot_id"],
                        version=1,
                        verdict_type="teacher_advisory",
                        status=status,
                        verdict_json=_json_dumps(persisted_verdict),
                        immutable_source=ANALYSIS_TEACHER_SOURCE,
                        canonical_source_id=None,
                        provenance_json=_json_dumps(
                            _teacher_provenance(case, persisted_verdict, status)
                        ),
                        approved_by=None,
                        approved_at=None,
                        approval_notes=None,
                        created_by=int(case.get("created_by") or 0),
                    )
                )
            else:
                row.run_id = _run_id(case, job_id)
                row.snapshot_id = case["snapshot_id"]
                row.verdict_type = "teacher_advisory"
                row.status = status
                row.verdict_json = _json_dumps(persisted_verdict)
                row.immutable_source = ANALYSIS_TEACHER_SOURCE
                row.provenance_json = _json_dumps(
                    _teacher_provenance(case, persisted_verdict, status)
                )
                row.canonical_source_id = None
                row.approval_notes = None
                row.created_by = int(case.get("created_by") or 0)
            from app.services.review_case_orchestrator import (
                record_countermeasure_report_available,
                record_teacher_advisory,
                record_teacher_review_failure,
            )

            if status == "completed":
                await record_teacher_advisory(
                    snapshot_id=case["snapshot_id"],
                    verdict=persisted_verdict,
                    db=db,
                )
                await record_countermeasure_report_available(
                    snapshot_id=case["snapshot_id"],
                    verdict=persisted_verdict,
                    db=db,
                )
            elif status == "failed":
                await record_teacher_review_failure(
                    snapshot_id=case["snapshot_id"],
                    verdict=persisted_verdict,
                    db=db,
                )
            await db.commit()
        return True
    except Exception as exc:
        logger.exception("Failed to persist Teacher advisory {}", job_id)
        TEACHER_JOB_CACHE[job_id] = {
            **TEACHER_JOB_CACHE.get(job_id, {}),
            "verdict": verdict,
            "status": "persistence_failed",
            "persistence_error": f"{type(exc).__name__}: {exc}",
        }
        return False


def _teacher_persistence_payload(verdict: dict[str, Any]) -> dict[str, Any]:
    """Keep the persisted audit bounded to analyst-facing, traceable evidence.

    A live MARO run contains provider payloads and intermediate material that
    are too large for a durable verdict and outside the product contract. This
    projection intentionally keeps only the information required by the audit
    view, governance readout, and Countermeasure report.
    """

    evidence = verdict.get("evidence") if isinstance(verdict.get("evidence"), dict) else {}
    reports = evidence.get("agent_reports") if isinstance(evidence.get("agent_reports"), list) else []
    payload = {
        "technology": str(verdict.get("technology") or "teacher"),
        "schema": str(verdict.get("schema") or "cogguard.review.teacher_audit.v1"),
        "status": str(verdict.get("status") or "failed"),
        "verdict_type": str(verdict.get("verdict_type") or "teacher_advisory"),
        "verdict_id": str(verdict.get("verdict_id") or verdict.get("job_id") or ""),
        "snapshot_id": str(verdict.get("snapshot_id") or ""),
        "event_id": str(verdict.get("event_id") or ""),
        "platforms": _bounded_text_list(verdict.get("platforms"), limit=8, text_limit=64),
        "model_version": _bounded_text_value(verdict.get("model_version"), 128),
        "execution_mode": _bounded_text_value(verdict.get("execution_mode"), 64),
        "task_state": _bounded_text_value(verdict.get("task_state"), 128),
        "reason": _bounded_text_value(verdict.get("reason"), 800),
        "fallback_reason": _bounded_text_value(verdict.get("fallback_reason"), 256),
        "non_claimable": bool(verdict.get("non_claimable", True)),
        "canonical_allowed": False,
        "review_required": bool(verdict.get("review_required", True)),
        "reasoning_trace_saved": False,
        "review_tasks": _bounded_text_list(verdict.get("review_tasks"), limit=2, text_limit=64),
        "dag": _bounded_dag(verdict.get("dag")),
        "audit_input_selection": _bounded_audit_selection(verdict.get("audit_input_selection")),
        "advisory": _bounded_advisory(verdict.get("advisory")),
        "summary": _bounded_summary(verdict.get("summary")),
        "signals": _bounded_teacher_signals(verdict.get("signals")),
        "evidence": {
            "agent_reports": [
                _bounded_agent_report(report)
                for report in reports
                if isinstance(report, dict)
            ][:8]
        },
        "countermeasure_gate": _bounded_countermeasure_gate(verdict.get("countermeasure_gate")),
        "countermeasure_report": _bounded_countermeasure_report(
            verdict.get("countermeasure_report")
        ),
        "capability_boundary": _bounded_capability_boundary(
            verdict.get("capability_boundary")
        ),
    }
    # MySQL TEXT accepts at most 65,535 bytes. The normal bounded projection is
    # substantially smaller; this final guard also handles provider anomalies.
    if len(_json_dumps(payload).encode("utf-8")) > 56_000:
        for report in payload["evidence"]["agent_reports"]:
            report["report_text"] = _bounded_text_value(report.get("report_text"), 600)
            report["system_audit_sidecar"] = _minimal_sidecar(
                report.get("system_audit_sidecar")
            )
        payload["countermeasure_report"] = _minimal_countermeasure_report(
            payload["countermeasure_report"]
        )
    return payload


def _bounded_agent_report(report: dict[str, Any]) -> dict[str, Any]:
    analysis = report.get("analysis_report") if isinstance(report.get("analysis_report"), dict) else {}
    sidecar = report.get("system_audit_sidecar")
    if not isinstance(sidecar, dict):
        sidecar = report.get("structured_sidecar") if isinstance(report.get("structured_sidecar"), dict) else {}
    return {
        "agent_name": _bounded_text_value(report.get("agent_name"), 128),
        "report_role": _bounded_text_value(report.get("report_role"), 64),
        "status": _bounded_text_value(report.get("status"), 32),
        "model": _bounded_text_value(report.get("model"), 128),
        "report_text": _bounded_text_value(
            analysis.get("text") or report.get("report_text") or report.get("error"),
            1_600,
        ),
        "system_audit_sidecar": _bounded_sidecar(sidecar),
    }


def _bounded_sidecar(sidecar: dict[str, Any]) -> dict[str, Any]:
    source_rows: list[dict[str, Any]] = []
    for key in ("source_refs", "evidence_refs", "retrieval_results", "sources"):
        values = sidecar.get(key)
        if not isinstance(values, list):
            continue
        for value in values:
            if isinstance(value, dict):
                source_rows.append(_bounded_source_ref(value))
    return {
        "retrieval_queries": _bounded_queries(
            sidecar.get("retrieval_queries") or sidecar.get("queries")
        ),
        "source_refs": _dedupe_source_refs(source_rows)[:8],
        "rationale_capsule": _bounded_rationale_capsule(
            sidecar.get("rationale_capsule") or sidecar.get("rationale")
        ),
        "governance_report": _bounded_governance_report(
            sidecar.get("governance_report")
        ),
    }


def _bounded_source_ref(value: dict[str, Any]) -> dict[str, Any]:
    return {
        "doc_id": _bounded_text_value(
            value.get("doc_id") or value.get("source_id") or value.get("id"), 256
        ),
        "source": _bounded_text_value(value.get("source") or value.get("source_origin"), 256),
        "title": _bounded_text_value(value.get("title") or value.get("name"), 512),
        "url": _bounded_text_value(value.get("url") or value.get("source_uri"), 2_048),
        "quoted_span": _bounded_text_value(
            value.get("quoted_span") or value.get("quote") or value.get("excerpt") or value.get("text"),
            1_000,
        ),
        "relation": _bounded_text_value(value.get("relation"), 64),
        "retrieval_status": _bounded_text_value(
            value.get("retrieval_status") or value.get("status"), 64
        ),
    }


def _dedupe_source_refs(values: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    seen: set[str] = set()
    for value in values:
        key = value.get("doc_id") or value.get("url") or value.get("title")
        if not key or key in seen:
            continue
        seen.add(key)
        result.append(value)
    return result


def _bounded_queries(values: Any) -> list[str]:
    items = values if isinstance(values, list) else [values] if values else []
    return _bounded_text_list(
        [item.get("query") if isinstance(item, dict) else item for item in items],
        limit=4,
        text_limit=300,
    )


def _bounded_rationale_capsule(value: Any) -> dict[str, Any]:
    capsule = value if isinstance(value, dict) else {}
    return {
        "capsule_text": _bounded_text_value(
            capsule.get("capsule_text") or capsule.get("short_rationale") or capsule.get("text"),
            1_200,
        ),
        "input_spans": _bounded_text_list(
            capsule.get("input_spans") or capsule.get("spans"), limit=12, text_limit=300
        ),
        "evidence_refs": _bounded_text_list(capsule.get("evidence_refs"), limit=20, text_limit=256),
        "policy_refs": _bounded_text_list(capsule.get("policy_refs"), limit=20, text_limit=256),
        "capsule_quality_gate": bool(
            capsule.get("capsule_quality_gate") or capsule.get("quality_gate")
        ),
        "citation_coverage": _bounded_probability(capsule.get("citation_coverage")),
    }


def _bounded_governance_report(value: Any) -> dict[str, Any]:
    report = value if isinstance(value, dict) else {}
    references = report.get("platform_reference_refs") or report.get("references") or []
    return {
        "governance_category_id": _bounded_text_value(report.get("governance_category_id"), 128),
        "governance_category": _bounded_text_value(report.get("governance_category"), 256),
        "recommended_actions": _bounded_text_list(report.get("recommended_actions"), limit=8, text_limit=512),
        "human_confirmation_items": _bounded_text_list(
            report.get("human_confirmation_items"), limit=8, text_limit=512
        ),
        "platform_reference_refs": [
            {
                "ref_id": _bounded_text_value(item.get("ref_id") or item.get("reference_id"), 256),
                "platform": _bounded_text_value(item.get("platform"), 128),
                "title": _bounded_text_value(item.get("title"), 512),
                "url": _bounded_text_value(item.get("url"), 2_048),
                "reference_type": _bounded_text_value(item.get("reference_type"), 128),
                "governance_use": _bounded_text_value(item.get("governance_use"), 512),
            }
            for item in references
            if isinstance(item, dict)
        ][:5],
    }


def _bounded_audit_selection(value: Any) -> dict[str, Any]:
    selection = value if isinstance(value, dict) else {}
    items = selection.get("items") if isinstance(selection.get("items"), list) else []
    return {
        "source": _bounded_text_value(selection.get("source"), 64),
        "selection_criteria": _bounded_text_list(
            selection.get("selection_criteria"), limit=6, text_limit=64
        ),
        "items": [
            {
                "post_id": _bounded_text_value(item.get("post_id"), 256),
                "platform": _bounded_text_value(item.get("platform"), 64),
                "author_name": _bounded_text_value(item.get("author_name"), 128),
                "excerpt": _bounded_text_value(item.get("excerpt"), 600),
                "engagement": {
                    "reposts": _bounded_nonnegative_int((item.get("engagement") or {}).get("reposts")),
                    "likes": _bounded_nonnegative_int((item.get("engagement") or {}).get("likes")),
                    "comments": _bounded_nonnegative_int((item.get("engagement") or {}).get("comments")),
                },
            }
            for item in items
            if isinstance(item, dict)
        ][:20],
    }


def _bounded_dag(value: Any) -> dict[str, Any]:
    dag = value if isinstance(value, dict) else {}
    nodes = dag.get("nodes") if isinstance(dag.get("nodes"), list) else []
    return {
        "version": _bounded_text_value(dag.get("version"), 128),
        "nodes": [
            {
                "node": _bounded_text_value(node.get("node"), 128),
                "status": _bounded_text_value(node.get("status"), 32),
                "summary": _bounded_text_value(node.get("summary"), 400),
            }
            for node in nodes
            if isinstance(node, dict)
        ][:12],
    }


def _bounded_advisory(value: Any) -> dict[str, Any]:
    advisory = value if isinstance(value, dict) else {}
    actions = advisory.get("recommended_actions")
    return {
        "decision": _bounded_text_value(advisory.get("decision"), 64),
        "recommended_actions": actions if isinstance(actions, dict) else {},
        "avg_agent_confidence": _bounded_probability(advisory.get("avg_agent_confidence")),
        "external_followup_required": bool(advisory.get("external_followup_required")),
    }


def _bounded_summary(value: Any) -> dict[str, Any]:
    summary = value if isinstance(value, dict) else {}
    return {
        "completed": _bounded_nonnegative_int(summary.get("completed")),
        "failed": _bounded_nonnegative_int(summary.get("failed")),
        "completed_agent_reports": _bounded_nonnegative_int(
            summary.get("completed_agent_reports")
        ),
    }


def _bounded_teacher_signals(value: Any) -> dict[str, Any]:
    signals = value if isinstance(value, dict) else {}
    maro = signals.get("maro") if isinstance(signals.get("maro"), dict) else {}
    student = signals.get("student_reference") if isinstance(signals.get("student_reference"), dict) else {}
    return {
        "student_reference": {
            "verdict_id": _bounded_text_value(student.get("verdict_id"), 128),
            "label": _bounded_text_value(student.get("label"), 64),
        },
        "maro": {
            "provider_name": _bounded_text_value(maro.get("provider_name"), 64),
            "model": _bounded_text_value(maro.get("model"), 128),
        },
    }


def _bounded_countermeasure_gate(value: Any) -> dict[str, Any]:
    gate = value if isinstance(value, dict) else {}
    return {
        "allowed": bool(gate.get("allowed")),
        "reasons": _bounded_text_list(gate.get("reasons"), limit=12, text_limit=256),
    }


def _bounded_countermeasure_report(value: Any) -> dict[str, Any]:
    report = value if isinstance(value, dict) else {}
    return {
        "schema": _bounded_text_value(report.get("schema"), 128),
        "status": _bounded_text_value(report.get("status"), 64),
        "case_id": _bounded_text_value(report.get("case_id"), 128),
        "snapshot_id": _bounded_text_value(report.get("snapshot_id"), 128),
        "teacher_audit_id": _bounded_text_value(report.get("teacher_audit_id"), 128),
        "reason": _bounded_text_value(report.get("reason"), 800),
        "risk_summary": _bounded_text_value(report.get("risk_summary"), 1_600),
        "evidence_refs": _bounded_text_list(report.get("evidence_refs"), limit=20, text_limit=256),
        "policy_refs": _bounded_text_list(report.get("policy_refs"), limit=20, text_limit=256),
        "recommended_actions": _bounded_text_list(
            report.get("recommended_actions"), limit=8, text_limit=512
        ),
        "response_draft": _bounded_text_value(report.get("response_draft"), 1_600),
        "limitations": _bounded_text_list(report.get("limitations"), limit=8, text_limit=512),
        "quality_gate": bool(report.get("quality_gate")),
    }


def _minimal_sidecar(value: Any) -> dict[str, Any]:
    sidecar = value if isinstance(value, dict) else {}
    return {
        "rationale_capsule": _bounded_rationale_capsule(sidecar.get("rationale_capsule")),
        "governance_report": _bounded_governance_report(sidecar.get("governance_report")),
    }


def _minimal_countermeasure_report(value: Any) -> dict[str, Any]:
    report = _bounded_countermeasure_report(value)
    return {
        **report,
        "risk_summary": _bounded_text_value(report.get("risk_summary"), 600),
        "response_draft": _bounded_text_value(report.get("response_draft"), 600),
        "evidence_refs": _bounded_text_list(report.get("evidence_refs"), limit=6, text_limit=128),
        "policy_refs": _bounded_text_list(report.get("policy_refs"), limit=6, text_limit=128),
    }


def _bounded_capability_boundary(value: Any) -> dict[str, Any]:
    boundary = value if isinstance(value, dict) else {}
    return {
        "execution_mode": _bounded_text_value(boundary.get("execution_mode"), 64),
        "non_claimable": bool(boundary.get("non_claimable", True)),
        "analyst_approval_required": bool(boundary.get("analyst_approval_required", True)),
        "detector_outputs_unchanged": bool(boundary.get("detector_outputs_unchanged", True)),
    }


def _bounded_text_value(value: Any, limit: int) -> str:
    return str(value or "").strip()[:limit]


def _bounded_text_list(value: Any, *, limit: int, text_limit: int) -> list[str]:
    values = value if isinstance(value, list) else [value] if value else []
    result: list[str] = []
    for item in values:
        text = _bounded_text_value(item, text_limit)
        if text and text not in result:
            result.append(text)
        if len(result) >= limit:
            break
    return result


def _bounded_probability(value: Any) -> float | None:
    try:
        return max(0.0, min(1.0, float(value))) if value is not None else None
    except (TypeError, ValueError):
        return None


def _bounded_nonnegative_int(value: Any) -> int:
    try:
        return max(0, int(value or 0))
    except (TypeError, ValueError):
        return 0


def _normalize_case(case: dict[str, Any]) -> dict[str, Any]:
    options = dict(case.get("options") or {})
    posts = [_normalize_content_row(row, default_kind="post") for row in _as_list(case.get("posts"))]
    comments = [_normalize_content_row(row, default_kind="comment") for row in _as_list(case.get("comments"))]
    relationships = [row for row in _as_list(case.get("relationships")) if isinstance(row, dict)]
    provenance = [row for row in _as_list(case.get("provenance")) if isinstance(row, dict)]
    quality_report = dict(case.get("quality_report") or {})
    platforms = [str(platform) for platform in _as_list(case.get("platforms")) if str(platform).strip()]
    if not platforms:
        platforms = sorted({str(row.get("platform") or "").strip() for row in [*posts, *comments] if str(row.get("platform") or "").strip()})
    return {
        "snapshot_id": str(case.get("snapshot_id") or ""),
        "event_id": str(case.get("event_id") or ""),
        "run_id": str(case.get("run_id") or ""),
        "platforms": platforms,
        "platform": platforms[0] if len(platforms) == 1 else None,
        "posts": posts,
        "comments": comments,
        "relationships": relationships,
        "provenance": provenance,
        "quality_report": quality_report,
        "options": options,
        "created_by": case.get("created_by") or 0,
    }


def _build_post_semantics_context(case: dict[str, Any]) -> dict[str, Any]:
    claims = []
    evidence_chains = []
    seen: set[str] = set()
    for post in case["posts"]:
        content = _text(post.get("content") or post.get("text") or "")
        anchors = _extract_claim_anchors(content)
        if not anchors:
            continue
        for anchor in anchors:
            claim_id = _stable_id(anchor)
            if claim_id not in seen:
                seen.add(claim_id)
                claims.append(
                    {
                        "object_id": claim_id,
                        "claim_id": claim_id,
                        "claim_text": anchor,
                        "share_count": 1,
                        "account_count": 1,
                        "first_share": post.get("timestamp") or "",
                        "source": "snapshot",
                    }
                )
            evidence_chains.append(
                {
                    "claim_id": claim_id,
                    "supporting_posts": [
                        {
                            "post_id": post.get("post_id"),
                            "author_id": post.get("author_id"),
                            "content": content[:240],
                            "timestamp": post.get("timestamp"),
                        }
                    ],
                }
            )
    return {"claims": claims, "evidence_chains": evidence_chains}


def _build_account_profiles(case: dict[str, Any]) -> list[dict[str, Any]]:
    posts_by_account: dict[str, list[dict[str, Any]]] = defaultdict(list)
    comments_by_account: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for post in case["posts"]:
        account_id = str(post.get("author_id") or "").strip()
        if account_id:
            posts_by_account[account_id].append(post)
    for comment in case["comments"]:
        account_id = str(comment.get("author_id") or "").strip()
        if account_id:
            comments_by_account[account_id].append(comment)

    profiles = []
    for account_id in sorted(set(posts_by_account) | set(comments_by_account)):
        posts = posts_by_account.get(account_id, [])
        comments = comments_by_account.get(account_id, [])
        author_name = _first_non_empty(
            [post.get("author_name") for post in posts] + [comment.get("author_name") for comment in comments]
        ) or account_id
        profiles.append(
            {
                "account_id": account_id,
                "author_name": author_name,
                "platform": _first_non_empty([post.get("platform") for post in posts] + [comment.get("platform") for comment in comments]),
                "automation_score": 0.0,
                "post_count": len(posts),
                "comment_count": len(comments),
                "representative_posts": [
                    {
                        "post_id": post.get("post_id"),
                        "content": _text(post.get("content") or post.get("text") or "")[:240],
                    }
                    for post in posts[:3]
                ],
            }
        )
    return profiles


def _build_coordination_context(case: dict[str, Any]) -> dict[str, Any]:
    authors = {
        _content_ref(post, kind="post"): str(post.get("author_id") or "").strip()
        for post in case["posts"]
        if str(post.get("post_id") or "").strip()
    }
    authors.update(
        {
            _content_ref(comment, kind="comment"): str(comment.get("author_id") or "").strip()
            for comment in case["comments"]
            if str(comment.get("comment_id") or "").strip()
        }
    )

    edges: dict[tuple[str, str, str], dict[str, Any]] = {}
    degree: Counter[str] = Counter()
    adjacency: dict[str, set[str]] = defaultdict(set)
    for row in case["relationships"]:
        source_ref = str(row.get("source_id") or row.get("source_ref") or "").strip()
        target_ref = str(row.get("target_id") or row.get("target_ref") or "").strip()
        source_account = authors.get(source_ref)
        target_account = authors.get(target_ref)
        if not source_account or not target_account:
            continue
        key = (source_account, target_account, str(row.get("relation_type") or "related"))
        edges[key] = {
            "source": source_account,
            "target": target_account,
            "relation_type": str(row.get("relation_type") or "related"),
            "platform": str(row.get("platform") or ""),
            "weight": 1,
        }
        adjacency[source_account].add(target_account)
        adjacency[target_account].add(source_account)
        degree[source_account] += 1
        degree[target_account] += 1

    clusters = _connected_components(adjacency)
    cluster_rows = []
    for index, members in enumerate(clusters):
        member_list = sorted(members)
        cluster_edges = [
            edge
            for edge in edges.values()
            if edge["source"] in members and edge["target"] in members
        ]
        cluster_rows.append(
            {
                "cluster_id": f"cluster_{index}",
                "members": member_list,
                "size": len(member_list),
                "edge_count": len(cluster_edges),
                "total_weight": len(cluster_edges),
                "shared_objects": [],
            }
        )

    account_stats = [
        {
            "account_id": account_id,
            "account_label": account_id,
            "degree": int(degree[account_id]),
            "avg_weight": float(degree[account_id] or 0),
            "avg_time_delta": 0.0,
            "coordinated_shares_count": int(degree[account_id]),
            "shared_objects_preview": [],
        }
        for account_id in sorted({*authors.values(), *degree.keys()})
        if account_id
    ]
    return {
        "network": {
            "nodes": [
                {"id": account_id, "account_id": account_id}
                for account_id in sorted({*authors.values(), *degree.keys()})
                if account_id
            ],
            "edges": list(edges.values()),
            "clusters": cluster_rows,
        },
        "account_stats": account_stats,
        "group_stats": cluster_rows,
        "cluster_stats": cluster_rows,
    }


def _build_propagation_context(case: dict[str, Any]) -> dict[str, Any]:
    posts = sorted(case["posts"], key=_timestamp_key)
    comments = sorted(case["comments"], key=_timestamp_key)
    timeline = [
        {
            "post_id": post.get("post_id"),
            "author_id": post.get("author_id"),
            "timestamp": post.get("timestamp"),
            "content": _text(post.get("content") or post.get("text") or "")[:240],
        }
        for post in posts
    ]
    claims = []
    evidence_chains = []
    for post in posts:
        content = _text(post.get("content") or post.get("text") or "")
        if not content:
            continue
        anchors = _extract_claim_anchors(content)
        if not anchors:
            continue
        for anchor in anchors:
            claim_id = _stable_id(anchor)
            claims.append(
                {
                    "claim_id": claim_id,
                    "object_id": claim_id,
                    "claim_text": anchor,
                    "share_count": 1,
                    "account_count": 1,
                    "first_share": post.get("timestamp") or "",
                }
            )
            evidence_chains.append(
                {
                    "claim_id": claim_id,
                    "supporting_posts": [
                        {
                            "post_id": post.get("post_id"),
                            "author_id": post.get("author_id"),
                            "timestamp": post.get("timestamp"),
                            "content": content[:240],
                        }
                    ],
                }
            )
    graph_nodes = []
    graph_edges = []
    seen_nodes: set[str] = set()
    for post in posts:
        author_id = str(post.get("author_id") or "").strip()
        if author_id and author_id not in seen_nodes:
            seen_nodes.add(author_id)
            graph_nodes.append({"id": author_id, "account_id": author_id})
    for comment in comments:
        author_id = str(comment.get("author_id") or "").strip()
        if author_id and author_id not in seen_nodes:
            seen_nodes.add(author_id)
            graph_nodes.append({"id": author_id, "account_id": author_id})
    for row in case["relationships"]:
        graph_edges.append(
            {
                "relation_type": str(row.get("relation_type") or ""),
                "source_ref": row.get("source_id") or row.get("source_ref"),
                "target_ref": row.get("target_id") or row.get("target_ref"),
                "platform": row.get("platform"),
            }
        )
    originators = [
        {"account_id": posts[0].get("author_id"), "role": "originator", "evidence": posts[0].get("post_id")}
    ] if posts else []
    bridges = [
        {"account_id": account_id, "role": "bridge"}
        for account_id, count in Counter(str(post.get("author_id") or "").strip() for post in posts).items()
        if account_id and count > 1
    ][:5]
    amplifiers = [
        {"account_id": account_id, "role": "amplifier"}
        for account_id, count in Counter(str(post.get("author_id") or "").strip() for post in posts).items()
        if account_id and count > 1
    ][:5]
    return {
        "timeline": timeline,
        "claims": claims[:20],
        "evidence_chains": evidence_chains[:20],
        "key_roles": {
            "originators": originators,
            "bridges": bridges,
            "amplifiers": amplifiers,
        },
        "graph": {
            "nodes": graph_nodes,
            "edges": graph_edges,
        },
        "comment_count": len(comments),
    }


def _build_student_detector_outputs(post_semantics: dict[str, Any]) -> list[dict[str, Any]]:
    detector_outputs = []
    for index, post in enumerate(_semantic_posts(post_semantics)[:3]):
        probability = float(_get(post, "harmfulness", "score") or 0.5)
        text = str(post.get("excerpt") or post.get("text") or post.get("content") or "")
        detector_case = {
            "case_id": f"{post.get('post_id') or index}",
            "text": text,
            "labels": {
                "harm_type": list(_as_list(_get(post, "harmfulness", "types"))),
            },
            "claim_context": {
                "claim_text": str(_get(post, "primary_claim", "claim_text") or ""),
                "evidence_text": text[:240],
            },
        }
        detector_outputs.append(
            standard_detector_output(
                detector_case,
                view=str(post.get("post_view") or "tweet"),
                probability=probability,
                evidence=[text[:240]],
                capability_boundary="analysis.student.runtime.v1",
                stance=str(_get(post, "stance", "label") or "neutral"),
            )
        )
    if not detector_outputs:
        detector_outputs.append(
            standard_detector_output(
                {"case_id": "snapshot", "text": "", "labels": {}},
                view="tweet",
                probability=0.5,
                evidence=["No representative posts were available."],
                capability_boundary="analysis.student.runtime.v1",
                stance="neutral",
            )
        )
    return detector_outputs


def _student_risk_level(
    post_semantics: dict[str, Any],
    layered: dict[str, Any],
    fusion: dict[str, Any],
) -> str:
    harmful_ratio = float(post_semantics["summary"]["harmful_ratio"] or 0.0)
    harmful_accounts = int(layered["user_level"]["summary"]["harmful_accounts"] or 0)
    if fusion["final_harmfulness"] == "harmful" and harmful_ratio >= 0.65:
        return "high"
    if fusion["final_harmfulness"] == "harmful" or harmful_accounts > 0:
        return "medium"
    return "low"


def _student_evidence(
    post_semantics: dict[str, Any],
    layered: dict[str, Any],
    detector_outputs: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "top_claims": post_semantics["summary"]["top_claims"][:5],
        "harm_types": post_semantics["summary"]["harm_types"],
        "stance_distribution": post_semantics["summary"]["stance_distribution"],
        "account_summary": layered["user_level"]["summary"],
        "community_summary": layered["community_level"]["summary"],
        "detectors": detector_outputs,
    }


def _teacher_evidence(
    post_semantics: dict[str, Any],
    layered: dict[str, Any],
    review_execution: dict[str, Any],
    multi_agent: dict[str, Any],
) -> dict[str, Any]:
    return {
        "top_claims": post_semantics["summary"]["top_claims"][:5],
        "harm_types": post_semantics["summary"]["harm_types"],
        "stance_distribution": post_semantics["summary"]["stance_distribution"],
        "account_summary": layered["user_level"]["summary"],
        "community_summary": layered["community_level"]["summary"],
        "review_execution": {
            "summary": review_execution["summary"],
            "provider_audit": review_execution["provider_audit"],
        },
        "multi_agent": {
            "summary": multi_agent["summary"],
            "final_decision": multi_agent["final_decision"],
        },
    }


def _teacher_provenance(case: dict[str, Any], verdict: dict[str, Any], status: str) -> dict[str, Any]:
    return {
        "source": ANALYSIS_TEACHER_SOURCE,
        "status": status,
        "snapshot_id": case["snapshot_id"],
        "event_id": case["event_id"],
        "platforms": case["platforms"],
        "verdict_type": verdict["verdict_type"],
        "verdict_id": verdict["verdict_id"],
        "case_digest": _case_digest(case),
    }


def _student_evidence_strings(case: dict[str, Any]) -> list[str]:
    texts = []
    for post in case["posts"][:3]:
        text = _text(post.get("content") or post.get("text") or "")
        if text:
            texts.append(text[:240])
    return texts


def _semantic_posts(post_semantics: dict[str, Any]) -> list[dict[str, Any]]:
    posts = post_semantics.get("aggregation_posts")
    if isinstance(posts, list):
        return posts
    posts = post_semantics.get("posts")
    return posts if isinstance(posts, list) else []


def _quality_status(quality_report: dict[str, Any]) -> str:
    return str(quality_report.get("status") or "").strip().lower()


def _verdict_id(prefix: str, case: dict[str, Any]) -> str:
    return f"{prefix}_{_case_digest(case)[:24]}"


def _teacher_job_id(case: dict[str, Any]) -> str:
    """Return a new audit identifier while retaining snapshot traceability."""

    return f"teacher_{_case_digest(case)[:16]}_{uuid4().hex[:12]}"


def _run_id(case: dict[str, Any], job_id: str) -> str:
    return str(case.get("run_id") or f"analysis:{job_id}")


def _capability_boundary(role: str) -> dict[str, Any]:
    return {
        "runtime": f"internal-{role}-runtime",
        "live_external_call": False,
        "trainable_scaffold": role == "student",
        "teacher_advisory_only": role == "teacher",
        "description": (
            "Snapshot-derived runtime scaffold that stays inside the analysis boundary "
            "and does not treat teacher outputs as canonical verdicts."
        ),
    }


def _normalize_content_row(row: dict[str, Any], *, default_kind: str) -> dict[str, Any]:
    normalized = dict(row)
    if not normalized.get("content"):
        normalized["content"] = normalized.get("text") or normalized.get("summary") or ""
    if not normalized.get("kind"):
        normalized["kind"] = default_kind
    return normalized


def _extract_claim_anchors(text: str) -> list[str]:
    if not text:
        return []
    anchors = []
    for token in _words(text):
        if token.startswith("http") or token.startswith("#"):
            anchors.append(token)
    if not anchors:
        trimmed = " ".join(_words(text)[:10]).strip()
        if trimmed:
            anchors.append(trimmed)
    return anchors[:3]


def _connected_components(adjacency: dict[str, set[str]]) -> list[set[str]]:
    remaining = set(adjacency)
    components: list[set[str]] = []
    while remaining:
        start = remaining.pop()
        stack = [start]
        component = {start}
        while stack:
            node = stack.pop()
            for neighbor in adjacency.get(node, set()):
                if neighbor not in component:
                    component.add(neighbor)
                    stack.append(neighbor)
                    remaining.discard(neighbor)
        components.append(component)
    return components


def _timestamp_key(row: dict[str, Any]) -> str:
    value = row.get("timestamp")
    if isinstance(value, datetime):
        return _as_utc(value).isoformat()
    return str(value or "")


def _case_digest(case: dict[str, Any]) -> str:
    payload = {
        "snapshot_id": case.get("snapshot_id"),
        "event_id": case.get("event_id"),
        "platforms": list(case.get("platforms") or []),
        "posts": [
            {
                "post_id": row.get("post_id"),
                "author_id": row.get("author_id"),
                "timestamp": row.get("timestamp"),
                "content": row.get("content") or row.get("text") or "",
            }
            for row in case.get("posts") or []
        ],
        "comments": [
            {
                "comment_id": row.get("comment_id"),
                "author_id": row.get("author_id"),
                "timestamp": row.get("timestamp"),
                "content": row.get("content") or row.get("text") or "",
            }
            for row in case.get("comments") or []
        ],
    }
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _json_dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)


def _stable_id(value: str) -> str:
    return hashlib.sha1(value.encode("utf-8")).hexdigest()[:16]


def _content_ref(row: dict[str, Any], *, kind: str) -> str:
    identifier = row.get("post_id") if kind == "post" else row.get("comment_id")
    return f"{str(row.get('platform') or 'unknown')}:{kind}:{identifier}"


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _get(value: Any, *path: str) -> Any:
    current = value or {}
    for key in path:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def _words(text: str) -> list[str]:
    parts = []
    for raw in str(text or "").replace("\n", " ").split():
        token = raw.strip()
        if token:
            parts.append(token)
    return parts


def _text(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def _first_non_empty(values: list[Any]) -> str:
    for value in values:
        text = _text(value)
        if text:
            return text
    return ""


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)
