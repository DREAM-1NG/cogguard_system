"""Persistence layer for automatic review case orchestration."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any, Protocol

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.analysis import EventSnapshot
from app.models.analysis import ReviewVerdictVersion
from app.models.review_case import (
    CaseActivity,
    ReviewCase,
    ReviewCaseSnapshotRevision,
    ReviewDecision,
)
from app.schemas.review_case import (
    ActionRequired,
    CaseActivityType,
    Disposition,
    EvidenceSufficiency,
    ReviewConclusion,
    ReviewUrgency,
)
from app.services.review_case_analysis_projection import (
    AnalysisProjection,
    _empty_business_summary,
    _json_dumps,
    _now,
)


@dataclass(frozen=True, slots=True)
class CaseRevisionRef:
    case_id: str
    snapshot_revision_id: str
    revision_number: int
    created_case: bool
    created_revision: bool


class ReviewCaseRepository(Protocol):
    async def upsert_revision(self, **kwargs: Any) -> CaseRevisionRef: ...

    async def apply_analysis_projection(self, **kwargs: Any) -> None: ...

    async def has_active_teacher(self, **kwargs: Any) -> bool: ...

    async def record_teacher_submission(self, **kwargs: Any) -> None: ...


class SqlAlchemyReviewCaseRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def upsert_revision(
        self, *, snapshot: EventSnapshot, title: str, created_by: int
    ) -> CaseRevisionRef:
        case_result = await self.db.execute(
            select(ReviewCase)
            .where(ReviewCase.event_id == snapshot.event_id)
            .with_for_update()
        )
        case = case_result.scalar_one_or_none()
        created_case = False
        if case is None:
            case = ReviewCase(
                case_id=_case_id(snapshot.event_id),
                event_id=snapshot.event_id,
                title=title or snapshot.event_id,
                preliminary_conclusion=ReviewConclusion.INSUFFICIENT_EVIDENCE.value,
                evidence_sufficiency=EvidenceSufficiency.INSUFFICIENT.value,
                urgency=ReviewUrgency.ROUTINE.value,
                disposition=Disposition.GATHER_EVIDENCE.value,
                action_required=ActionRequired.ADD_EVIDENCE.value,
                preliminary_finding_json=_json_dumps(
                    {
                        "conclusion": ReviewConclusion.INSUFFICIENT_EVIDENCE.value,
                        "rationale": "Analysis is pending.",
                        "key_evidence_refs": [],
                    }
                ),
                business_summary_json=_json_dumps(_empty_business_summary()),
                created_by=created_by,
                updated_by=created_by,
            )
            try:
                async with self.db.begin_nested():
                    self.db.add(case)
                    await self.db.flush()
                created_case = True
            except IntegrityError:
                case = (
                    await self.db.execute(
                        select(ReviewCase)
                        .where(ReviewCase.event_id == snapshot.event_id)
                        .with_for_update()
                    )
                ).scalar_one()

        existing = (
            await self.db.execute(
                select(ReviewCaseSnapshotRevision).where(
                    ReviewCaseSnapshotRevision.case_id == case.case_id,
                    ReviewCaseSnapshotRevision.data_fingerprint
                    == snapshot.data_fingerprint,
                )
            )
        ).scalar_one_or_none()
        if existing is not None:
            return CaseRevisionRef(
                case_id=case.case_id,
                snapshot_revision_id=existing.snapshot_revision_id,
                revision_number=existing.revision_number,
                created_case=created_case,
                created_revision=False,
            )

        max_revision = (
            await self.db.execute(
                select(func.max(ReviewCaseSnapshotRevision.revision_number)).where(
                    ReviewCaseSnapshotRevision.case_id == case.case_id
                )
            )
        ).scalar_one_or_none()
        revision_number = int(max_revision or 0) + 1
        revision = ReviewCaseSnapshotRevision(
            snapshot_revision_id=f"case_snapshot_{uuid_digest(case.case_id, snapshot.data_fingerprint)}",
            case_id=case.case_id,
            snapshot_id=snapshot.snapshot_id,
            data_fingerprint=snapshot.data_fingerprint,
            revision_number=revision_number,
            core_window_start=snapshot.core_window.start,
            core_window_end=snapshot.core_window.end,
            context_window_start=snapshot.context_window.start,
            context_window_end=snapshot.context_window.end,
            quality_json=_json_dumps(snapshot.quality_report.model_dump(mode="json")),
            provenance_json=_json_dumps(
                [item.model_dump(mode="json") for item in snapshot.provenance]
            ),
            created_by=created_by,
        )
        self.db.add(revision)
        await self.db.flush()

        case.title = title or case.title
        case.updated_by = created_by
        has_decision = (
            await self.db.execute(
                select(ReviewDecision.id)
                .where(ReviewDecision.case_id == case.case_id)
                .limit(1)
            )
        ).first() is not None
        if has_decision:
            case.action_required = ActionRequired.RECONFIRM_DECISION.value

        if created_case:
            await self._append_activity(
                case_id=case.case_id,
                snapshot_revision_id=revision.snapshot_revision_id,
                activity_type=CaseActivityType.CASE_CREATED,
                action_required=ActionRequired.ADD_EVIDENCE,
                summary="Event review case created.",
                source_ref=case.case_id,
                created_by=created_by,
            )
        await self._append_activity(
            case_id=case.case_id,
            snapshot_revision_id=revision.snapshot_revision_id,
            activity_type=(
                CaseActivityType.RECONFIRMATION_REQUIRED
                if has_decision
                else CaseActivityType.SNAPSHOT_ADDED
            ),
            action_required=(
                ActionRequired.RECONFIRM_DECISION
                if has_decision
                else ActionRequired.ADD_EVIDENCE
            ),
            summary=(
                "New evidence requires decision reconfirmation."
                if has_decision
                else "New event evidence added."
            ),
            source_ref=snapshot.data_fingerprint,
            created_by=created_by,
        )
        return CaseRevisionRef(
            case_id=case.case_id,
            snapshot_revision_id=revision.snapshot_revision_id,
            revision_number=revision_number,
            created_case=created_case,
            created_revision=True,
        )

    async def apply_analysis_projection(
        self,
        *,
        ref: CaseRevisionRef,
        analysis_run_id: str,
        projection: AnalysisProjection,
        created_by: int,
    ) -> None:
        case = (
            await self.db.execute(
                select(ReviewCase)
                .where(ReviewCase.case_id == ref.case_id)
                .with_for_update()
            )
        ).scalar_one()
        revision = (
            await self.db.execute(
                select(ReviewCaseSnapshotRevision).where(
                    ReviewCaseSnapshotRevision.snapshot_revision_id
                    == ref.snapshot_revision_id
                )
            )
        ).scalar_one()
        revision.analysis_run_id = analysis_run_id
        revision.analysis_completed_at = _now()
        case.preliminary_conclusion = projection.conclusion.value
        case.evidence_sufficiency = projection.evidence_sufficiency.value
        case.urgency = projection.urgency.value
        case.disposition = projection.disposition.value
        if case.action_required != ActionRequired.RECONFIRM_DECISION.value:
            case.action_required = projection.action_required.value
        case.preliminary_finding_json = _json_dumps(projection.preliminary_finding)
        case.business_summary_json = _json_dumps(projection.business_summary)
        case.updated_by = created_by
        if projection.action_required == ActionRequired.ADD_EVIDENCE:
            await self._append_activity(
                case_id=case.case_id,
                snapshot_revision_id=revision.snapshot_revision_id,
                activity_type=CaseActivityType.EVIDENCE_REQUESTED,
                action_required=ActionRequired.ADD_EVIDENCE,
                summary="Additional evidence is required.",
                source_ref=revision.data_fingerprint,
                created_by=created_by,
                detail_lines=projection.business_summary.get("missing_evidence", []),
            )
        await self.db.flush()

    async def has_active_teacher(self, *, ref: CaseRevisionRef) -> bool:
        revision = (
            await self.db.execute(
                select(ReviewCaseSnapshotRevision).where(
                    ReviewCaseSnapshotRevision.snapshot_revision_id
                    == ref.snapshot_revision_id
                )
            )
        ).scalar_one()
        if not revision.teacher_verdict_id:
            return False
        result = await self.db.execute(
            select(ReviewVerdictVersion.status).where(
                ReviewVerdictVersion.verdict_id == revision.teacher_verdict_id
            )
        )
        state = result.scalar_one_or_none()
        return state is None or str(state) in {"draft", "queued", "running"}

    async def record_teacher_submission(
        self,
        *,
        ref: CaseRevisionRef,
        teacher_run_id: str,
        teacher_verdict_id: str,
    ) -> None:
        revision = (
            await self.db.execute(
                select(ReviewCaseSnapshotRevision)
                .where(
                    ReviewCaseSnapshotRevision.snapshot_revision_id
                    == ref.snapshot_revision_id
                )
                .with_for_update()
            )
        ).scalar_one()
        revision.teacher_run_id = teacher_run_id
        revision.teacher_verdict_id = teacher_verdict_id
        await self.db.flush()

    async def _append_activity(
        self,
        *,
        case_id: str,
        snapshot_revision_id: str | None,
        activity_type: CaseActivityType,
        action_required: ActionRequired,
        summary: str,
        source_ref: str,
        created_by: int,
        detail_lines: list[str] | None = None,
    ) -> None:
        existing = (
            await self.db.execute(
                select(CaseActivity.id).where(
                    CaseActivity.case_id == case_id,
                    CaseActivity.activity_type == activity_type.value,
                    CaseActivity.source_ref == source_ref,
                )
            )
        ).first()
        if existing is not None:
            return
        self.db.add(
            CaseActivity(
                case_id=case_id,
                snapshot_revision_id=snapshot_revision_id,
                activity_type=activity_type.value,
                action_required=action_required.value,
                source_ref=source_ref,
                summary=summary,
                detail_lines_json=_json_dumps(detail_lines or []),
                evidence_refs_json="[]",
                actor_name="System",
                created_by=created_by,
            )
        )
        await self.db.flush()


def _case_id(event_id: str) -> str:
    return f"case_{hashlib.sha256(event_id.encode('utf-8')).hexdigest()[:24]}"


def uuid_digest(*parts: str) -> str:
    return hashlib.sha256("\x1f".join(parts).encode("utf-8")).hexdigest()[:24]


__all__ = [
    "CaseRevisionRef",
    "ReviewCaseRepository",
    "SqlAlchemyReviewCaseRepository",
]
