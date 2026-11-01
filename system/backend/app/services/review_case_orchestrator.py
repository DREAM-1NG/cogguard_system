"""Automatic case creation and analysis after successful event collection.

This module stays as the stable orchestration facade. Repository persistence and
pure analysis projection helpers live in sibling modules and are reexported here
for existing imports and monkeypatch paths.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.analysis import EventSnapshot
from app.core.analysis.executor import AnalysisExecutor, default_analysis_engine_ports
from app.core.analysis.registry import AnalysisRegistry, SqlAlchemyAnalysisStore
from app.models.analysis import AnalysisRun
from app.models.review_case import (
    CaseActivity,
    ReviewCase,
    ReviewCaseSnapshotRevision,
    ReviewDecision,
)
from app.schemas.review_case import ActionRequired, CaseActivityType
from app.services.event_data import load_event_comments, load_event_posts
from app.services.review_case_analysis_projection import (
    AnalysisProjection,
    _empty_business_summary,
    _json_dumps,
    _json_loads,
    _teacher_business_advisory,
    derive_analysis_windows,
    project_analysis_results,
)
from app.services.review_case_repository import (
    CaseRevisionRef,
    ReviewCaseRepository,
    SqlAlchemyReviewCaseRepository,
    _case_id,
    uuid_digest,
)


CORE_ANALYSIS_STAGES = ["coordination_discover", "propagation_analysis", "student"]


@dataclass(frozen=True, slots=True)
class CaseOrchestrationOutcome:
    case_id: str
    snapshot_revision_id: str
    created_case: bool
    created_revision: bool
    analysis_run_id: str | None = None
    teacher_requested: bool = False
    teacher_reasons: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class ReviewCaseOrchestrator:
    def __init__(
        self,
        *,
        registry: AnalysisRegistry,
        executor: AnalysisExecutor,
        repository: ReviewCaseRepository,
    ) -> None:
        self.registry = registry
        self.executor = executor
        self.repository = repository

    async def analyze_snapshot(
        self,
        *,
        snapshot: EventSnapshot,
        title: str,
        created_by: int,
        defer_teacher: bool = False,
    ) -> CaseOrchestrationOutcome:
        ref = await self.repository.upsert_revision(
            snapshot=snapshot,
            title=title,
            created_by=created_by,
        )
        if not ref.created_revision:
            return CaseOrchestrationOutcome(
                case_id=ref.case_id,
                snapshot_revision_id=ref.snapshot_revision_id,
                created_case=ref.created_case,
                created_revision=False,
            )

        run = await self.registry.create_run(
            event_id=snapshot.event_id,
            snapshot_id=snapshot.snapshot_id,
            requested_stages=list(CORE_ANALYSIS_STAGES),
            options={"source": "review_case_automatic_analysis"},
            created_by=created_by,
        )
        analysis_run_id = str(run["run_id"])
        result = await self.executor.execute_run(analysis_run_id)
        stage_results = dict(result.get("results") or {})
        projection = project_analysis_results(snapshot=snapshot, results=stage_results)
        await self.repository.apply_analysis_projection(
            ref=ref,
            analysis_run_id=analysis_run_id,
            projection=projection,
            created_by=created_by,
        )

        return CaseOrchestrationOutcome(
            case_id=ref.case_id,
            snapshot_revision_id=ref.snapshot_revision_id,
            created_case=ref.created_case,
            created_revision=True,
            analysis_run_id=analysis_run_id,
            teacher_requested=False,
            teacher_reasons=(),
        )


async def process_successful_crawl(
    *,
    job_id: int,
    event_id: str,
    title: str,
    created_by: int,
    db: AsyncSession,
    mongo_db: Any,
) -> dict[str, Any]:
    posts = await load_event_posts(mongo_db, event_id=event_id)
    comments = await load_event_comments(mongo_db, event_id=event_id)
    core_window, context_window = derive_analysis_windows(
        posts=posts,
        comments=comments,
        crawl_job_id=job_id,
    )
    registry = AnalysisRegistry(mongo_db=mongo_db, store=SqlAlchemyAnalysisStore(db))
    snapshot = await registry.create_event_snapshot(
        event_id=event_id,
        core_window=core_window,
        context_window=context_window,
        created_by=created_by,
    )
    orchestrator = ReviewCaseOrchestrator(
        registry=registry,
        executor=AnalysisExecutor(
            registry=registry, engines=default_analysis_engine_ports()
        ),
        repository=SqlAlchemyReviewCaseRepository(db),
    )
    outcome = await orchestrator.analyze_snapshot(
        snapshot=snapshot,
        title=title or event_id,
        created_by=created_by,
        defer_teacher=True,
    )
    return outcome.to_dict()


async def submit_teacher_review_for_case(
    *,
    case_id: str,
    db: AsyncSession,
    mongo_db: Any,
    requested_by: int,
    review_tasks: list[str] | None = None,
    evidence_refs: list[str] | None = None,
    routing_reasons: list[str] | None = None,
) -> bool:
    case = (
        await db.execute(select(ReviewCase).where(ReviewCase.case_id == case_id))
    ).scalar_one_or_none()
    if case is None:
        raise KeyError(f"Event review case not found: {case_id}")
    revision = (
        await db.execute(
            select(ReviewCaseSnapshotRevision)
            .where(ReviewCaseSnapshotRevision.case_id == case_id)
            .order_by(ReviewCaseSnapshotRevision.revision_number.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if revision is None:
        raise ValueError("Event review case has no snapshot revision")

    ref = CaseRevisionRef(
        case_id=case_id,
        snapshot_revision_id=revision.snapshot_revision_id,
        revision_number=revision.revision_number,
        created_case=False,
        created_revision=False,
    )
    repository = SqlAlchemyReviewCaseRepository(db)
    if await repository.has_active_teacher(ref=ref):
        return False
    registry = AnalysisRegistry(mongo_db=mongo_db, store=SqlAlchemyAnalysisStore(db))
    run = await registry.create_run(
        event_id=case.event_id,
        snapshot_id=revision.snapshot_id,
        requested_stages=["teacher"],
        options={
            "teacher": {
                "review_tasks": list(review_tasks or ["interpersonal_harm"]),
                "evidence_refs": list(evidence_refs or []),
                "request_reason": list(routing_reasons or []),
                "human_triggered": True,
            }
        },
        created_by=requested_by,
    )
    run_id = str(run["run_id"])
    result = await AnalysisExecutor(
        registry=registry,
        engines=default_analysis_engine_ports(),
    ).execute_run(run_id)
    teacher = dict((result.get("results") or {}).get("teacher") or {})
    verdict_id = str(teacher.get("job_id") or teacher.get("verdict_id") or "")
    if not verdict_id:
        return False
    task_id = str(teacher.get("task_id") or "").strip()
    if task_id:
        run_row = (
            await db.execute(
                select(AnalysisRun)
                .where(AnalysisRun.run_id == run_id)
                .with_for_update()
            )
        ).scalar_one()
        run_row.celery_task_id = task_id
        await db.flush()
    await repository.record_teacher_submission(
        ref=ref,
        teacher_run_id=run_id,
        teacher_verdict_id=verdict_id,
    )
    return True


async def record_teacher_advisory(
    *,
    snapshot_id: str,
    verdict: dict[str, Any],
    db: AsyncSession,
) -> bool:
    revision = (
        await db.execute(
            select(ReviewCaseSnapshotRevision)
            .where(ReviewCaseSnapshotRevision.snapshot_id == snapshot_id)
            .order_by(ReviewCaseSnapshotRevision.revision_number.desc())
            .limit(1)
            .with_for_update()
        )
    ).scalar_one_or_none()
    if revision is None:
        return False
    case = (
        await db.execute(
            select(ReviewCase)
            .where(ReviewCase.case_id == revision.case_id)
            .with_for_update()
        )
    ).scalar_one()
    latest_revision = (
        await db.execute(
            select(ReviewCaseSnapshotRevision)
            .where(ReviewCaseSnapshotRevision.case_id == case.case_id)
            .order_by(ReviewCaseSnapshotRevision.revision_number.desc())
            .limit(1)
            .with_for_update()
        )
    ).scalar_one()
    verdict_id = str(verdict.get("verdict_id") or verdict.get("job_id") or "")
    source_ref = verdict_id or revision.snapshot_revision_id
    existing_activity = (
        await db.execute(
            select(CaseActivity.id).where(
                CaseActivity.case_id == case.case_id,
                CaseActivity.activity_type
                == CaseActivityType.REVIEW_ADVISORY_AVAILABLE.value,
                CaseActivity.source_ref == source_ref,
            )
        )
    ).first()
    if existing_activity is not None:
        return False

    revision.teacher_verdict_id = verdict_id or revision.teacher_verdict_id
    if latest_revision.snapshot_revision_id != revision.snapshot_revision_id:
        db.add(
            CaseActivity(
                case_id=case.case_id,
                snapshot_revision_id=revision.snapshot_revision_id,
                activity_type=CaseActivityType.REVIEW_ADVISORY_AVAILABLE.value,
                action_required=ActionRequired.NONE.value,
                source_ref=source_ref,
                summary="Review advisory received for an earlier evidence revision.",
                detail_lines_json=_json_dumps(
                    ["The current finding was not changed by this historical advisory."]
                ),
                evidence_refs_json="[]",
                actor_name="System",
                created_by=0,
            )
        )
        await db.flush()
        return True

    advisory = _teacher_business_advisory(verdict, case.preliminary_conclusion)
    business = _json_loads(case.business_summary_json, _empty_business_summary())
    business["review_advisory"] = advisory
    case.business_summary_json = _json_dumps(business)
    has_decision = (
        await db.execute(
            select(ReviewDecision.id)
            .where(ReviewDecision.case_id == case.case_id)
            .limit(1)
        )
    ).first() is not None
    action = (
        ActionRequired.RECONFIRM_DECISION
        if has_decision
        else ActionRequired.REVIEW_AVAILABLE
    )
    case.action_required = action.value
    db.add(
        CaseActivity(
            case_id=case.case_id,
            snapshot_revision_id=revision.snapshot_revision_id,
            activity_type=CaseActivityType.REVIEW_ADVISORY_AVAILABLE.value,
            action_required=action.value,
            source_ref=source_ref,
            summary=(
                "Review advisory requires decision reconfirmation."
                if has_decision
                else "Review advisory is available."
            ),
            detail_lines_json=_json_dumps(advisory["differences_from_preliminary"]),
            evidence_refs_json=_json_dumps(advisory["key_evidence_refs"]),
            actor_name="System",
            created_by=0,
        )
    )
    await db.flush()
    return True


async def record_teacher_review_failure(
    *,
    snapshot_id: str,
    verdict: dict[str, Any],
    db: AsyncSession,
) -> bool:
    """Project a persisted Teacher failure without changing case conclusions."""

    revision = (
        await db.execute(
            select(ReviewCaseSnapshotRevision)
            .where(ReviewCaseSnapshotRevision.snapshot_id == snapshot_id)
            .order_by(ReviewCaseSnapshotRevision.revision_number.desc())
            .limit(1)
            .with_for_update()
        )
    ).scalar_one_or_none()
    if revision is None:
        return False
    case = (
        await db.execute(
            select(ReviewCase)
            .where(ReviewCase.case_id == revision.case_id)
            .with_for_update()
        )
    ).scalar_one()
    verdict_id = str(verdict.get("verdict_id") or verdict.get("job_id") or "")
    source_ref = verdict_id or revision.snapshot_revision_id
    existing_activity = (
        await db.execute(
            select(CaseActivity.id).where(
                CaseActivity.case_id == case.case_id,
                CaseActivity.activity_type == CaseActivityType.TEACHER_REVIEW_FAILED.value,
                CaseActivity.source_ref == source_ref,
            )
        )
    ).first()
    if existing_activity is not None:
        return False

    revision.teacher_verdict_id = verdict_id or revision.teacher_verdict_id
    detail_lines = [
        str(verdict.get("reason") or "Independent review could not be completed."),
        str(verdict.get("task_state") or "failed"),
    ]
    db.add(
        CaseActivity(
            case_id=case.case_id,
            snapshot_revision_id=revision.snapshot_revision_id,
            activity_type=CaseActivityType.TEACHER_REVIEW_FAILED.value,
            action_required=ActionRequired.NONE.value,
            source_ref=source_ref,
            summary="Independent review did not complete; an analyst may retry it.",
            detail_lines_json=_json_dumps(detail_lines),
            evidence_refs_json="[]",
            actor_name="System",
            created_by=0,
        )
    )
    await db.flush()
    return True


async def record_countermeasure_report_available(
    *,
    snapshot_id: str,
    verdict: dict[str, Any],
    db: AsyncSession,
) -> bool:
    """Append an activity only for a quality-gated, persisted draft report."""

    report = verdict.get("countermeasure_report")
    if not isinstance(report, dict) or report.get("status") != "available" or report.get("quality_gate") is not True:
        return False
    revision = (
        await db.execute(
            select(ReviewCaseSnapshotRevision)
            .where(ReviewCaseSnapshotRevision.snapshot_id == snapshot_id)
            .order_by(ReviewCaseSnapshotRevision.revision_number.desc())
            .limit(1)
            .with_for_update()
        )
    ).scalar_one_or_none()
    if revision is None:
        return False
    case = (
        await db.execute(
            select(ReviewCase)
            .where(ReviewCase.case_id == revision.case_id)
            .with_for_update()
        )
    ).scalar_one()
    verdict_id = str(verdict.get("verdict_id") or verdict.get("job_id") or "")
    source_ref = verdict_id or revision.snapshot_revision_id
    existing_activity = (
        await db.execute(
            select(CaseActivity.id).where(
                CaseActivity.case_id == case.case_id,
                CaseActivity.activity_type == CaseActivityType.COUNTERMEASURE_REPORT_AVAILABLE.value,
                CaseActivity.source_ref == source_ref,
            )
        )
    ).first()
    if existing_activity is not None:
        return False

    db.add(
        CaseActivity(
            case_id=case.case_id,
            snapshot_revision_id=revision.snapshot_revision_id,
            activity_type=CaseActivityType.COUNTERMEASURE_REPORT_AVAILABLE.value,
            action_required=ActionRequired.NONE.value,
            source_ref=source_ref,
            summary="A quality-gated internal countermeasure draft is available.",
            detail_lines_json=_json_dumps(["The draft is advisory only and requires analyst confirmation."]),
            evidence_refs_json=_json_dumps(list(report.get("evidence_refs") or [])[:50]),
            actor_name="System",
            created_by=0,
        )
    )
    await db.flush()
    return True


__all__ = [
    "AnalysisProjection",
    "CaseOrchestrationOutcome",
    "CaseRevisionRef",
    "ReviewCaseOrchestrator",
    "ReviewCaseRepository",
    "SqlAlchemyReviewCaseRepository",
    "derive_analysis_windows",
    "process_successful_crawl",
    "project_analysis_results",
    "record_teacher_advisory",
    "record_countermeasure_report_available",
    "record_teacher_review_failure",
    "submit_teacher_review_for_case",
]
