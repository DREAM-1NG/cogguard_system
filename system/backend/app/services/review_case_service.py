"""Application boundary for analyst-facing event review cases."""

from __future__ import annotations

import json
import hashlib
from collections.abc import Iterable
from typing import Any
from uuid import uuid4

from sqlalchemy import desc, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.analysis.registry import AnalysisRegistry, SqlAlchemyAnalysisStore
from app.models.risk_assessment import RiskAssessment
from app.models.review_system import ReviewAgentFeedback, ReviewAgentReport
from app.models.review_case import (
    CaseActivity as CaseActivityRecord,
    EvidenceAnnotation as EvidenceAnnotationRecord,
    ReviewCase,
    ReviewCaseSnapshotRevision,
    ReviewDecision as ReviewDecisionRecord,
    ReviewDecisionDraft as ReviewDecisionDraftRecord,
)
from app.models.analysis import ReviewFeedback, ReviewVerdictVersion
from app.models.user import User
from app.schemas.review_case import (
    ActionRequired,
    CaseActivity,
    CaseActivityList,
    CaseActivityType,
    ConfirmedDecision,
    DecisionConfirmation,
    DecisionConfirmRequest,
    DecisionDraft,
    DecisionDraftUpsert,
    Disposition,
    EvidenceAnnotation,
    EvidenceAnnotationCreate,
    EvidenceAssessment,
    ReviewAdvisory,
    ReviewCaseDetail,
    ReviewCaseEvidence,
    ReviewCaseList,
    ReviewCaseSummary,
    ReviewConclusion,
    ReviewRequestCreate,
    ReviewRequestReceipt,
    ReviewUrgency,
)
from app.services.review_case_decision_feedback import (
    _canonical_source_id,
    _decision_feedback_payload,
    _feedback_id,
)
from app.services.review_case_product_projection import (
    _activity_model,
    _advisory_model,
    _annotation_model,
    _confirmed_decision,
    _draft_model,
    _enum_value,
    _evidence_ref,
    _now,
    _optional_text,
    _product_text,
    _safe_string_list,
    build_case_summary,
    build_evidence_item,
)


class ReviewCaseConflict(ValueError):
    """Raised when an optimistic or immutable case boundary is violated."""


class ReviewCaseService:
    """Own persistence and product-safe projections for Event Review Cases."""

    def __init__(self, *, db: AsyncSession, mongo_db: Any) -> None:
        self.db = db
        self.registry = AnalysisRegistry(
            mongo_db=mongo_db,
            store=SqlAlchemyAnalysisStore(db),
        )

    async def latest(self) -> ReviewCaseDetail:
        result = await self.db.execute(
            select(ReviewCase).order_by(ReviewCase.updated_at.desc(), ReviewCase.id.desc()).limit(1)
        )
        row = result.scalar_one_or_none()
        if row is None:
            raise KeyError("No event review case is available")
        return await self._detail_from_row(row)

    async def search(self, *, query: str = "", limit: int = 20) -> ReviewCaseList:
        statement = select(ReviewCase)
        normalized_query = str(query or "").strip()
        if normalized_query:
            pattern = f"%{normalized_query}%"
            statement = statement.where(
                or_(
                    ReviewCase.event_id.like(pattern),
                    ReviewCase.case_id.like(pattern),
                    ReviewCase.title.like(pattern),
                )
            )
        statement = statement.order_by(ReviewCase.updated_at.desc(), ReviewCase.id.desc()).limit(limit)
        rows = (await self.db.execute(statement)).scalars().all()
        return ReviewCaseList(items=[build_case_summary(row) for row in rows], total=len(rows))

    async def detail(self, case_id: str) -> ReviewCaseDetail:
        return await self._detail_from_row(await self._get_case(case_id))

    async def evidence(self, case_id: str) -> ReviewCaseEvidence:
        await self._get_case(case_id)
        revision = await self._latest_revision(case_id)
        if revision is None:
            return ReviewCaseEvidence(case_id=case_id)

        annotations = await self._annotations(case_id, revision.snapshot_revision_id)
        annotations_by_ref: dict[str, list[EvidenceAnnotation]] = {}
        for annotation in annotations:
            annotations_by_ref.setdefault(annotation.evidence_ref, []).append(annotation)

        snapshot = await self.registry.load_event_snapshot(revision.snapshot_id)
        items = [
            build_evidence_item(
                row,
                evidence_kind=kind,
                annotations=annotations_by_ref.get(_evidence_ref(row, kind), []),
            )
            for kind, rows in (("post", snapshot.posts), ("comment", snapshot.comments))
            for row in rows
        ]
        groups: dict[EvidenceAssessment, list[EvidenceItem]] = {
            assessment: [] for assessment in EvidenceAssessment
        }
        for item in items:
            groups[item.assessment].append(item)
        return ReviewCaseEvidence(
            case_id=case_id,
            supports=groups[EvidenceAssessment.SUPPORTS],
            contradicts=groups[EvidenceAssessment.CONTRADICTS],
            irrelevant=groups[EvidenceAssessment.IRRELEVANT],
            unresolved=groups[EvidenceAssessment.UNRESOLVED],
        )

    async def request_review(
        self,
        case_id: str,
        request: ReviewRequestCreate,
        *,
        actor: User,
    ) -> ReviewRequestReceipt:
        case = await self._get_case(case_id, for_update=True)
        revision = await self._require_latest_revision(case_id)
        case.action_required = ActionRequired.NONE.value
        case.updated_by = _actor_id(actor)
        await self.append_activity(
            case_id=case_id,
            snapshot_revision_id=revision.snapshot_revision_id,
            activity_type=CaseActivityType.REVIEW_REQUESTED,
            action_required=ActionRequired.NONE,
            summary="Review advisory requested.",
            detail_lines=[request.reason],
            evidence_refs=request.evidence_refs,
            actor=actor,
            source_ref=f"review_request_{uuid4().hex}",
        )
        from app.services.review_case_orchestrator import submit_teacher_review_for_case

        await submit_teacher_review_for_case(
            case_id=case_id,
            db=self.db,
            mongo_db=self.registry.mongo_db,
            requested_by=_actor_id(actor),
            routing_reasons=["manual_request"],
        )
        return ReviewRequestReceipt(
            case_id=case_id,
            action_required=ActionRequired.NONE,
            message="Review advisory requested.",
        )

    async def add_annotation(
        self,
        case_id: str,
        request: EvidenceAnnotationCreate,
        *,
        actor: User,
    ) -> EvidenceAnnotation:
        await self._get_case(case_id)
        revision = await self._require_latest_revision(case_id)
        available = await self.evidence(case_id)
        evidence_refs = {
            item.evidence_ref
            for group in (available.supports, available.contradicts, available.irrelevant, available.unresolved)
            for item in group
        }
        if request.evidence_ref not in evidence_refs:
            raise ValueError("Evidence reference does not belong to the current case snapshot")

        row = EvidenceAnnotationRecord(
            annotation_id=f"annotation_{uuid4().hex}",
            case_id=case_id,
            snapshot_revision_id=revision.snapshot_revision_id,
            evidence_ref=request.evidence_ref,
            assessment=request.assessment.value,
            note=request.note,
            source_url=request.source_url,
            created_by=_actor_id(actor),
        )
        self.db.add(row)
        await self.db.flush()
        await self.db.refresh(row)
        await self.append_activity(
            case_id=case_id,
            snapshot_revision_id=revision.snapshot_revision_id,
            activity_type=CaseActivityType.EVIDENCE_ANNOTATED,
            action_required=ActionRequired.NONE,
            summary="Evidence annotation added.",
            detail_lines=[request.note],
            evidence_refs=[request.evidence_ref],
            actor=actor,
            source_ref=row.annotation_id,
        )
        return _annotation_model(row, actor_name=_actor_name(actor))

    async def save_draft(
        self,
        case_id: str,
        request: DecisionDraftUpsert,
        *,
        actor: User,
    ) -> DecisionDraft:
        await self._get_case(case_id, for_update=True)
        revision = await self._require_latest_revision(case_id)
        result = await self.db.execute(
            select(ReviewDecisionDraftRecord)
            .where(ReviewDecisionDraftRecord.case_id == case_id)
            .with_for_update()
        )
        row = result.scalar_one_or_none()
        if row is None:
            if request.expected_version != 0:
                raise ReviewCaseConflict("Decision draft does not exist at the expected version")
            row = ReviewDecisionDraftRecord(
                case_id=case_id,
                snapshot_revision_id=revision.snapshot_revision_id,
                version=1,
                conclusion=request.conclusion.value,
                urgency=request.urgency.value,
                disposition=request.disposition.value,
                rationale=request.rationale,
                key_evidence_refs_json=_json_dumps(request.key_evidence_refs),
                unresolved_items_json=_json_dumps(request.unresolved_items),
                created_by=_actor_id(actor),
                updated_by=_actor_id(actor),
            )
            self.db.add(row)
        else:
            if int(row.version) != request.expected_version:
                raise ReviewCaseConflict("Decision draft was changed by another analyst")
            row.snapshot_revision_id = revision.snapshot_revision_id
            row.version = int(row.version) + 1
            row.conclusion = request.conclusion.value
            row.urgency = request.urgency.value
            row.disposition = request.disposition.value
            row.rationale = request.rationale
            row.key_evidence_refs_json = _json_dumps(request.key_evidence_refs)
            row.unresolved_items_json = _json_dumps(request.unresolved_items)
            row.updated_by = _actor_id(actor)
            row.updated_at = _now()
        await self.db.flush()
        await self.db.refresh(row)
        return _draft_model(row)

    async def confirm_decision(
        self,
        case_id: str,
        request: DecisionConfirmRequest,
        *,
        actor: User,
    ) -> DecisionConfirmation:
        case = await self._get_case(case_id, for_update=True)
        revision = await self._require_latest_revision(case_id)
        draft_result = await self.db.execute(
            select(ReviewDecisionDraftRecord)
            .where(ReviewDecisionDraftRecord.case_id == case_id)
            .with_for_update()
        )
        draft = draft_result.scalar_one_or_none()
        if draft is None or int(draft.version) != request.expected_draft_version:
            raise ReviewCaseConflict("Decision draft was changed or is unavailable")
        if draft.snapshot_revision_id != revision.snapshot_revision_id:
            raise ReviewCaseConflict("New evidence requires a decision draft for the latest snapshot")

        canonical_source_id = _canonical_source_id(
            case_id=case_id,
            snapshot_revision_id=revision.snapshot_revision_id,
            draft_version=int(draft.version),
        )
        existing_canonical = (
            await self.db.execute(
                select(ReviewVerdictVersion.id).where(
                    ReviewVerdictVersion.canonical_source_id == canonical_source_id
                )
            )
        ).first()
        if existing_canonical is not None:
            raise ReviewCaseConflict("This decision draft has already been confirmed")

        previous_result = await self.db.execute(
            select(ReviewDecisionRecord)
            .where(ReviewDecisionRecord.case_id == case_id)
            .order_by(ReviewDecisionRecord.version.desc())
            .limit(1)
            .with_for_update()
        )
        previous = previous_result.scalar_one_or_none()
        version = int(previous.version) + 1 if previous is not None else 1
        row = ReviewDecisionRecord(
            decision_id=f"decision_{uuid4().hex}",
            case_id=case_id,
            snapshot_revision_id=revision.snapshot_revision_id,
            version=version,
            supersedes_decision_id=previous.decision_id if previous is not None else None,
            conclusion=draft.conclusion,
            urgency=draft.urgency,
            disposition=draft.disposition,
            rationale=draft.rationale,
            key_evidence_refs_json=draft.key_evidence_refs_json,
            unresolved_items_json=draft.unresolved_items_json,
            confirmation_note=request.confirmation_note,
            confirmed_by=_actor_id(actor),
            created_by=_actor_id(actor),
        )
        self.db.add(row)
        case.action_required = ActionRequired.NONE.value
        case.updated_by = _actor_id(actor)
        await self.db.flush()
        await self.db.refresh(row)

        self.db.add(
            ReviewVerdictVersion(
                verdict_id=row.decision_id,
                run_id=revision.analysis_run_id or f"review_case:{case_id}",
                snapshot_id=revision.snapshot_id,
                version=1,
                verdict_type="canonical",
                status="approved",
                verdict_json=_json_dumps(_decision_feedback_payload(row)),
                immutable_source="review_case.confirmed_decision.v1",
                canonical_source_id=canonical_source_id,
                provenance_json=_json_dumps(
                    {
                        "case_id": case_id,
                        "snapshot_revision_id": revision.snapshot_revision_id,
                        "decision_version": version,
                    }
                ),
                approved_by=_actor_id(actor),
                approved_at=row.confirmed_at or _now(),
                approval_notes=request.confirmation_note,
                created_by=_actor_id(actor),
            )
        )

        feedback_id = _feedback_id(row.decision_id)
        existing_feedback = (
            await self.db.execute(
                select(ReviewFeedback.id).where(ReviewFeedback.feedback_id == feedback_id)
            )
        ).first()
        if existing_feedback is None:
            self.db.add(
                ReviewFeedback(
                    feedback_id=feedback_id,
                    run_id=revision.analysis_run_id or f"review_case:{case_id}",
                    verdict_id=row.decision_id,
                    snapshot_id=revision.snapshot_id,
                    feedback_json=_json_dumps(_decision_feedback_payload(row)),
                    immutable_source="review_case.confirmed_decision.feedback.v1",
                    provenance_json=_json_dumps(
                        {
                            "case_id": case_id,
                            "snapshot_revision_id": revision.snapshot_revision_id,
                        }
                    ),
                    created_by=_actor_id(actor),
                )
            )
        await self.db.flush()
        await self.append_activity(
            case_id=case_id,
            snapshot_revision_id=revision.snapshot_revision_id,
            activity_type=CaseActivityType.DECISION_CONFIRMED,
            action_required=ActionRequired.NONE,
            summary="Decision confirmed.",
            detail_lines=[request.confirmation_note] if request.confirmation_note else [],
            evidence_refs=_json_loads(row.key_evidence_refs_json, []),
            actor=actor,
            source_ref=row.decision_id,
        )
        return DecisionConfirmation(
            case_id=case_id,
            decision=_confirmed_decision(row, actor_name=_actor_name(actor)),
            action_required=ActionRequired.NONE,
        )

    async def activities(
        self,
        case_id: str,
        *,
        after_id: int = 0,
        limit: int = 100,
    ) -> CaseActivityList:
        case = await self._get_case(case_id)
        result = await self.db.execute(
            select(CaseActivityRecord)
            .where(
                CaseActivityRecord.case_id == case_id,
                CaseActivityRecord.id > after_id,
            )
            .order_by(CaseActivityRecord.id.asc())
            .limit(limit)
        )
        items = [_activity_model(row) for row in result.scalars().all()]
        if len(items) < limit:
            items.extend(
                await self._legacy_activities(
                    case,
                    after_id=after_id,
                    cursor_offset=items[-1].cursor if items else after_id,
                    limit=limit - len(items),
                )
            )
        return CaseActivityList(
            items=items[:limit],
            next_cursor=items[-1].cursor if items else None,
        )

    async def legacy_assess_risk(
        self,
        *,
        platform: str | None = None,
        event_id: str | None = None,
    ) -> dict[str, Any]:
        """Deprecated V1 assessment facade backed only by review-case projections."""

        case = await self._find_case_for_legacy(event_id=event_id)
        detail = await self._detail_from_row(case)
        return _legacy_report_payload(detail, platform=platform)

    async def legacy_list_reports(
        self,
        *,
        platform: str | None = None,
        event_id: str | None = None,
        risk_level: str | None = None,
        phase: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        """Deprecated V1 report list facade backed by review-case summaries."""

        statement = select(ReviewCase)
        if event_id:
            statement = statement.where(ReviewCase.event_id == event_id)
        rows = (
            await self.db.execute(
                statement.order_by(ReviewCase.updated_at.desc(), ReviewCase.id.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        ).scalars().all()
        items = []
        for row in rows:
            summary = build_case_summary(row)
            item = _legacy_report_summary(summary, platform=platform)
            if risk_level and item["risk_level"] != risk_level:
                continue
            if phase and item["current_phase"] != phase:
                continue
            items.append(item)
        return items, len(items)

    async def legacy_get_report_detail(self, report_id: str) -> dict[str, Any] | None:
        """Deprecated V1 detail facade; accepts a case id, event id, or legacy report id."""

        case = await self._find_case_for_legacy(event_id=report_id, case_id=report_id)
        detail = await self._detail_from_row(case)
        return _legacy_report_payload(detail)

    async def legacy_request_review(
        self,
        *,
        report_id: str,
        reason: str,
        evidence_refs: Iterable[str],
        actor: User,
    ) -> dict[str, Any]:
        case = await self._find_case_for_legacy(event_id=report_id, case_id=report_id)
        receipt = await self.request_review(
            case.case_id,
            ReviewRequestCreate(reason=reason, evidence_refs=_safe_string_list(evidence_refs)),
            actor=actor,
        )
        return {
            "case_id": receipt.case_id,
            "report_id": case.case_id,
            "message": receipt.message,
            "action_required": receipt.action_required.value,
            "deprecated": True,
        }

    async def legacy_record_feedback(
        self,
        *,
        report_id: str,
        feedback: dict[str, Any],
        actor: User,
    ) -> dict[str, Any]:
        """Map legacy feedback writes to a new business activity, never to old tables."""

        case = await self._find_case_for_legacy(
            event_id=str(feedback.get("case_id") or report_id),
            case_id=str(feedback.get("case_id") or report_id),
        )
        revision = await self._latest_revision(case.case_id)
        evidence_refs = []
        for item in feedback.get("evidence_refs") or []:
            if isinstance(item, dict):
                evidence_refs.append(item.get("evidence_ref") or item.get("id") or item.get("doc_id"))
            else:
                evidence_refs.append(item)
        activity = await self.append_activity(
            case_id=case.case_id,
            snapshot_revision_id=revision.snapshot_revision_id if revision is not None else None,
            activity_type=CaseActivityType.CORRECTION_RECORDED,
            action_required=ActionRequired.CONFIRM_DECISION,
            summary="Analyst correction recorded.",
            detail_lines=[
                feedback.get("human_label"),
                feedback.get("corrected_harmfulness") or feedback.get("corrected_label"),
                feedback.get("notes"),
            ],
            evidence_refs=evidence_refs,
            actor=actor,
            source_ref=_legacy_source_ref("feedback", report_id, _now().isoformat()),
        )
        return {
            "case_id": case.case_id,
            "report_id": case.case_id,
            "feedback": _activity_model(activity).model_dump(mode="json"),
            "summary": {"feedback_count": 1},
            "persistence": {"persisted": True, "target": "review_case_activities"},
            "deprecated": True,
        }

    async def append_activity(
        self,
        *,
        case_id: str,
        snapshot_revision_id: str | None,
        activity_type: CaseActivityType,
        action_required: ActionRequired,
        summary: str,
        detail_lines: Iterable[str] = (),
        evidence_refs: Iterable[str] = (),
        source_ref: str | None = None,
        actor: User | None = None,
        actor_name: str | None = None,
        created_by: int | None = None,
    ) -> CaseActivityRecord:
        row = CaseActivityRecord(
            case_id=case_id,
            snapshot_revision_id=snapshot_revision_id,
            activity_type=activity_type.value,
            action_required=action_required.value,
            source_ref=source_ref,
            summary=summary,
            detail_lines_json=_json_dumps(_safe_string_list(detail_lines)),
            evidence_refs_json=_json_dumps(_safe_string_list(evidence_refs)),
            actor_name=actor_name or _actor_name(actor),
            created_by=_actor_id(actor) if created_by is None else int(created_by),
        )
        self.db.add(row)
        await self.db.flush()
        await self.db.refresh(row)
        return row

    async def _detail_from_row(self, row: ReviewCase) -> ReviewCaseDetail:
        summary = build_case_summary(row)
        business = _json_loads(row.business_summary_json, {})
        advisory = _advisory_model(business.get("review_advisory"))
        if advisory is None:
            advisory = await self._legacy_review_advisory(row)
        revision = await self._latest_revision(row.case_id)
        if revision is not None and hasattr(self, "registry"):
            snapshot = await self.registry.load_event_snapshot(revision.snapshot_id)
            summary = _with_snapshot_account_names(summary, snapshot.posts)
        draft_result = await self.db.execute(
            select(ReviewDecisionDraftRecord).where(
                ReviewDecisionDraftRecord.case_id == row.case_id
            )
        )
        draft = draft_result.scalar_one_or_none()
        current_draft = (
            _draft_model(draft)
            if draft is not None
            and revision is not None
            and draft.snapshot_revision_id == revision.snapshot_revision_id
            else None
        )
        decision_result = await self.db.execute(
            select(ReviewDecisionRecord)
            .where(ReviewDecisionRecord.case_id == row.case_id)
            .order_by(ReviewDecisionRecord.version.desc())
            .limit(1)
        )
        decision = decision_result.scalar_one_or_none()
        confirmed = None
        if decision is not None:
            confirmed = _confirmed_decision(
                decision,
                actor_name=await self._username(decision.confirmed_by),
            )
        return ReviewCaseDetail(
            **summary.model_dump(),
            review_advisory=advisory,
            confirmed_decision=confirmed,
            decision_draft=current_draft,
        )

    async def _get_case(self, case_id: str, *, for_update: bool = False) -> ReviewCase:
        statement = select(ReviewCase).where(ReviewCase.case_id == case_id)
        if for_update:
            statement = statement.with_for_update()
        row = (await self.db.execute(statement)).scalar_one_or_none()
        if row is None:
            raise KeyError(f"Event review case not found: {case_id}")
        return row

    async def _latest_revision(self, case_id: str) -> ReviewCaseSnapshotRevision | None:
        result = await self.db.execute(
            select(ReviewCaseSnapshotRevision)
            .where(ReviewCaseSnapshotRevision.case_id == case_id)
            .order_by(ReviewCaseSnapshotRevision.revision_number.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def _require_latest_revision(self, case_id: str) -> ReviewCaseSnapshotRevision:
        row = await self._latest_revision(case_id)
        if row is None:
            raise ValueError("Event review case has no snapshot revision")
        return row

    async def _annotations(self, case_id: str, snapshot_revision_id: str) -> list[EvidenceAnnotation]:
        result = await self.db.execute(
            select(EvidenceAnnotationRecord)
            .where(
                EvidenceAnnotationRecord.case_id == case_id,
                EvidenceAnnotationRecord.snapshot_revision_id == snapshot_revision_id,
            )
            .order_by(EvidenceAnnotationRecord.created_at.asc(), EvidenceAnnotationRecord.id.asc())
        )
        rows = result.scalars().all()
        user_ids = {int(row.created_by) for row in rows if int(row.created_by or 0) > 0}
        names: dict[int, str] = {}
        if user_ids:
            user_result = await self.db.execute(select(User).where(User.id.in_(user_ids)))
            names = {int(user.id): str(user.username) for user in user_result.scalars().all()}
        return [
            _annotation_model(row, actor_name=names.get(int(row.created_by or 0), "System"))
            for row in rows
        ]

    async def _username(self, user_id: int) -> str:
        result = await self.db.execute(select(User.username).where(User.id == user_id))
        return str(result.scalar_one_or_none() or "Analyst")

    async def _find_case_for_legacy(
        self,
        *,
        event_id: str | None = None,
        case_id: str | None = None,
    ) -> ReviewCase:
        statement = select(ReviewCase)
        predicates = []
        if case_id:
            predicates.append(ReviewCase.case_id == case_id)
        if event_id:
            predicates.append(ReviewCase.event_id == event_id)
        if predicates:
            statement = statement.where(or_(*predicates))
        statement = statement.order_by(ReviewCase.updated_at.desc(), ReviewCase.id.desc()).limit(1)
        row = (await self.db.execute(statement)).scalar_one_or_none()
        if row is None and (event_id or case_id):
            legacy_id = event_id or case_id
            legacy_row = (
                await self.db.execute(
                    select(RiskAssessment)
                    .where(RiskAssessment.report_id == legacy_id)
                    .order_by(desc(RiskAssessment.assessed_at))
                    .limit(1)
                )
            ).scalar_one_or_none()
            if legacy_row is not None:
                row = (
                    await self.db.execute(
                        select(ReviewCase)
                        .where(ReviewCase.event_id == legacy_row.event_id)
                        .order_by(ReviewCase.updated_at.desc(), ReviewCase.id.desc())
                        .limit(1)
                    )
                ).scalar_one_or_none()
        if row is None:
            raise KeyError(f"Event review case not found: {case_id or event_id or 'latest'}")
        return row

    async def _legacy_report_ids(self, case: ReviewCase) -> list[str]:
        result = await self.db.execute(
            select(RiskAssessment.report_id)
            .where(RiskAssessment.event_id == case.event_id)
            .order_by(desc(RiskAssessment.assessed_at))
            .limit(20)
        )
        return [str(row[0]) for row in result.all()]

    async def _legacy_review_advisory(self, case: ReviewCase) -> ReviewAdvisory | None:
        try:
            report_ids = await self._legacy_report_ids(case)
            if not report_ids:
                return None
            result = await self.db.execute(
                select(ReviewAgentReport)
                .where(ReviewAgentReport.report_id.in_(report_ids))
                .order_by(desc(ReviewAgentReport.created_at), desc(ReviewAgentReport.id))
                .limit(1)
            )
            row = result.scalar_one_or_none()
        except Exception:
            return None
        if row is None:
            return None
        return ReviewAdvisory(
            conclusion=ReviewConclusion.INSUFFICIENT_EVIDENCE,
            urgency=ReviewUrgency.WATCH,
            disposition=Disposition.GATHER_EVIDENCE,
            rationale="复核建议已纳入当前事件研判。",
            differences_from_preliminary=[],
            key_evidence_refs=[],
            received_at=row.created_at or _now(),
        )

    async def _legacy_activities(
        self,
        case: ReviewCase,
        *,
        after_id: int,
        cursor_offset: int,
        limit: int,
    ) -> list[CaseActivity]:
        try:
            report_ids = await self._legacy_report_ids(case)
            rows: list[CaseActivity] = []
            cursor = max(after_id, cursor_offset)
            risk_rows = (
                await self.db.execute(
                    select(RiskAssessment)
                    .where(RiskAssessment.event_id == case.event_id)
                    .order_by(desc(RiskAssessment.assessed_at))
                    .limit(limit)
                )
            ).scalars().all()
            for row in risk_rows:
                cursor += 1
                rows.append(
                    CaseActivity(
                        cursor=cursor,
                        case_id=case.case_id,
                        activity_type=CaseActivityType.SNAPSHOT_ADDED,
                        action_required=ActionRequired.NONE,
                        summary="已更新事件材料",
                        detail_lines=[
                            "已同步事件研判结果。",
                        ],
                        evidence_refs=[],
                        actor_name="System",
                        occurred_at=row.assessed_at or _now(),
                    )
                )
            if len(rows) >= limit:
                return rows[:limit]
            if report_ids:
                advisory_rows = (
                    await self.db.execute(
                        select(ReviewAgentReport)
                        .where(ReviewAgentReport.report_id.in_(report_ids))
                        .order_by(desc(ReviewAgentReport.created_at), desc(ReviewAgentReport.id))
                        .limit(limit - len(rows))
                    )
                ).scalars().all()
                for row in advisory_rows:
                    cursor += 1
                    rows.append(
                        CaseActivity(
                            cursor=cursor,
                            case_id=case.case_id,
                        activity_type=CaseActivityType.REVIEW_ADVISORY_AVAILABLE,
                        action_required=ActionRequired.REVIEW_AVAILABLE,
                        summary="已收到复核建议",
                        detail_lines=["复核建议已纳入当前事件研判。"],
                        evidence_refs=[],
                        actor_name="系统",
                            occurred_at=row.created_at or _now(),
                        )
                    )
            if len(rows) >= limit:
                return rows[:limit]
            feedback_predicates = [ReviewAgentFeedback.case_id == case.case_id]
            if report_ids:
                feedback_predicates.append(ReviewAgentFeedback.report_id.in_(report_ids))
            feedback_rows = (
                await self.db.execute(
                    select(ReviewAgentFeedback)
                    .where(or_(*feedback_predicates))
                    .order_by(desc(ReviewAgentFeedback.created_at), desc(ReviewAgentFeedback.id))
                    .limit(limit - len(rows))
                )
            ).scalars().all()
            for row in feedback_rows:
                cursor += 1
                rows.append(
                    CaseActivity(
                        cursor=cursor,
                        case_id=case.case_id,
                        activity_type=CaseActivityType.CORRECTION_RECORDED,
                        action_required=ActionRequired.CONFIRM_DECISION,
                        summary="已记录分析员修正",
                        detail_lines=["已更新研判结论和相关说明。"],
                        evidence_refs=_safe_string_list(_json_loads(row.evidence_refs_json, [])),
                        actor_name="分析员",
                        occurred_at=row.created_at or _now(),
                    )
                )
            return rows[:limit]
        except Exception:
            return []


def _with_snapshot_account_names(
    summary: ReviewCaseSummary,
    posts: list[dict[str, Any]],
) -> ReviewCaseSummary:
    """Replace opaque account identifiers with collected display names."""

    display_names: dict[str, str] = {}
    for post in posts:
        account_id = str(post.get("author_id") or "").strip()
        name = str(post.get("author_name") or "").strip()
        if account_id and name and name != account_id and not name.isdigit():
            display_names.setdefault(account_id, name)

    resolved = []
    for value in summary.coordination_summary.key_accounts:
        name = display_names.get(str(value)) or str(value).strip()
        if not name or name.isdigit():
            continue
        if name not in resolved:
            resolved.append(name)

    coordination = summary.coordination_summary.model_copy(
        update={"key_accounts": resolved[:100]}
    )
    return summary.model_copy(update={"coordination_summary": coordination})


def _legacy_report_summary(summary: ReviewCaseSummary, *, platform: str | None = None) -> dict[str, Any]:
    risk_level_by_conclusion = {
        ReviewConclusion.HARMFUL: "high",
        ReviewConclusion.NON_HARMFUL: "low",
        ReviewConclusion.INSUFFICIENT_EVIDENCE: "medium",
    }
    return {
        "report_id": summary.case_id,
        "event_id": summary.event_id,
        "platform": platform or "all",
        "assessed_at": summary.updated_at.isoformat(),
        "overall_risk_score": 75.0 if summary.preliminary_finding.conclusion == ReviewConclusion.HARMFUL else 50.0,
        "risk_level": risk_level_by_conclusion[summary.preliminary_finding.conclusion],
        "current_phase": summary.action_required.value,
        "conflict_mass": 0.0,
        "escalation_required": summary.action_required
        in {ActionRequired.REVIEW_AVAILABLE, ActionRequired.CONFIRM_DECISION, ActionRequired.RECONFIRM_DECISION},
        "attack_path_score": 0.0,
        "deprecated": True,
    }


def _legacy_report_payload(detail: ReviewCaseDetail, *, platform: str | None = None) -> dict[str, Any]:
    summary = _legacy_report_summary(detail, platform=platform)
    return {
        **summary,
        "phase": {
            "current_phase": summary["current_phase"],
            "phase_confidence": 0.0,
            "hazard_scores": {},
            "window_count": 0,
        },
        "scores": {
            "overall_risk_score": summary["overall_risk_score"],
            "risk_level": summary["risk_level"],
            "manipulation": {"score": 0.0, "belief": 0.0, "plausibility": 0.0},
            "authenticity": {"score": 0.0, "belief": 0.0, "plausibility": 0.0},
            "impact": {"score": 0.0, "belief": 0.0, "plausibility": 0.0},
        },
        "fusion": {"conflict_mass": 0.0, "escalation_required": summary["escalation_required"], "per_source_masses": {}},
        "evidence": {},
        "claims": [],
        "review_case": detail.model_dump(mode="json"),
        "review_harmfulness": {
            "preliminary_finding": detail.preliminary_finding.model_dump(mode="json"),
            "review_advisory": detail.review_advisory.model_dump(mode="json") if detail.review_advisory else None,
            "confirmed_decision": detail.confirmed_decision.model_dump(mode="json") if detail.confirmed_decision else None,
        },
        "disarm_analysis": {
            "observed_techniques": [],
            "attack_path": {"depth": 0, "breadth": 0, "completeness": 0.0, "score": 0.0},
            "predicted_next": [],
            "countermeasures": [],
        },
        "risk_factors": {},
        "recommendations": [],
    }


def _legacy_source_ref(*parts: str) -> str:
    raw = "\x1f".join(parts)
    return f"legacy_{hashlib.sha256(raw.encode('utf-8')).hexdigest()[:32]}"


def _actor_id(actor: User | None) -> int:
    return int(getattr(actor, "id", 0) or 0)


def _actor_name(actor: User | None) -> str:
    return str(getattr(actor, "username", "") or "System")[:128]


def _json_dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)


def _json_loads(value: str | None, default: Any) -> Any:
    try:
        return json.loads(value) if value else default
    except (TypeError, json.JSONDecodeError):
        return default


__all__ = [
    "ReviewCaseConflict",
    "ReviewCaseService",
]
