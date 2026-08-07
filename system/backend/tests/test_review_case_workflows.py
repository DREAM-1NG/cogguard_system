from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

from app.models.analysis import ReviewFeedback, ReviewVerdictVersion
from app.models.review_case import EvidenceAnnotation, ReviewDecision, ReviewDecisionDraft
from app.schemas.review_case import (
    DecisionConfirmRequest,
    EvidenceAnnotationCreate,
    EvidenceAssessment,
    ReviewRequestCreate,
)
from app.services.review_case_service import ReviewCaseService


NOW = datetime(2026, 8, 3, tzinfo=timezone.utc)
ACTOR = SimpleNamespace(id=7, username="analyst")


class Result:
    def __init__(self, value=None, *, first=None) -> None:
        self.value = value
        self.first_value = first

    def scalar_one_or_none(self):
        return self.value

    def first(self):
        return self.first_value


class FakeSession:
    def __init__(self, results=()) -> None:
        self.results = list(results)
        self.added: list[object] = []

    async def execute(self, _statement):
        return self.results.pop(0)

    def add(self, row) -> None:
        self.added.append(row)

    async def flush(self) -> None:
        return None

    async def refresh(self, row) -> None:
        if hasattr(row, "created_at") and row.created_at is None:
            row.created_at = NOW
        if hasattr(row, "confirmed_at") and row.confirmed_at is None:
            row.confirmed_at = NOW


def make_service(db: FakeSession) -> ReviewCaseService:
    service = ReviewCaseService.__new__(ReviewCaseService)
    service.db = db
    service.registry = SimpleNamespace(mongo_db={})
    service._get_case = AsyncMock(
        return_value=SimpleNamespace(action_required="add_evidence", updated_by=0)
    )
    service._require_latest_revision = AsyncMock(
        return_value=SimpleNamespace(
            snapshot_revision_id="revision_1",
            snapshot_id="snapshot_1",
            analysis_run_id="analysis_1",
        )
    )
    service.append_activity = AsyncMock()
    return service


def test_review_request_records_business_activity_before_submission(monkeypatch):
    async def scenario():
        service = make_service(FakeSession())
        submit = AsyncMock(return_value={"submitted": True})
        monkeypatch.setattr(
            "app.services.review_case_orchestrator.submit_teacher_review_for_case",
            submit,
        )

        receipt = await service.request_review(
            "case_1",
            ReviewRequestCreate(reason="Contradictory sources require review."),
            actor=ACTOR,
        )

        assert receipt.case_id == "case_1"
        activity = service.append_activity.await_args.kwargs
        assert activity["summary"] == "Review advisory requested."
        assert activity["source_ref"].startswith("review_request_")
        submit.assert_awaited_once()

    asyncio.run(scenario())


def test_evidence_annotation_does_not_create_decision_or_feedback_records():
    async def scenario():
        db = FakeSession()
        service = make_service(db)
        service._evidence_ref_exists = AsyncMock(return_value=True)

        result = await service.add_annotation(
            "case_1",
            EvidenceAnnotationCreate(
                evidence_ref="weibo:post:p1",
                assessment=EvidenceAssessment.SUPPORTS,
                note="Supports the preliminary finding.",
            ),
            actor=ACTOR,
        )

        assert result.assessment == EvidenceAssessment.SUPPORTS
        service._evidence_ref_exists.assert_awaited_once_with("snapshot_1", "weibo:post:p1")
        assert [type(row) for row in db.added] == [EvidenceAnnotation]
        activity = service.append_activity.await_args.kwargs
        assert activity["source_ref"] == result.annotation_id

    asyncio.run(scenario())


def test_confirmed_decision_creates_canonical_verdict_and_feedback():
    async def scenario():
        draft = ReviewDecisionDraft(
            case_id="case_1",
            snapshot_revision_id="revision_1",
            version=3,
            conclusion="harmful",
            urgency="urgent",
            disposition="escalate",
            rationale="The evidence supports escalation.",
            key_evidence_refs_json='["weibo:post:p1"]',
            unresolved_items_json="[]",
            created_by=ACTOR.id,
            updated_by=ACTOR.id,
        )
        db = FakeSession(
            [
                Result(draft),
                Result(first=None),
                Result(None),
                Result(first=None),
            ]
        )
        service = make_service(db)

        result = await service.confirm_decision(
            "case_1",
            DecisionConfirmRequest(expected_draft_version=3),
            actor=ACTOR,
        )

        assert result.decision.decision_version == 1
        assert sum(isinstance(row, ReviewDecision) for row in db.added) == 1
        assert sum(isinstance(row, ReviewVerdictVersion) for row in db.added) == 1
        assert sum(isinstance(row, ReviewFeedback) for row in db.added) == 1
        activity = service.append_activity.await_args.kwargs
        assert activity["source_ref"] == result.decision.decision_id

    asyncio.run(scenario())
