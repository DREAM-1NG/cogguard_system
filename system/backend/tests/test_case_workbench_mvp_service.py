import asyncio
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db.mysql import Base
from app.models.case_workbench import (
    AuthoritySource,
    CaseAction,
    CaseAnalysisLink,
    CaseAuditEvent,
    CaseClaim,
    CaseFeedback,
    CaseRecord,
    CaseReportVersion,
    SemanticArtifact,
    SemanticCorrection,
)
from app.schemas.case_workbench import CaseLifecycle
from app.services.case_workbench_service import CaseWorkbenchService


class AsyncSessionAdapter:
    def __init__(self, session: Session) -> None:
        self.session = session

    async def execute(self, statement):
        return self.session.execute(statement)

    def add(self, row) -> None:
        self.session.add(row)

    async def flush(self) -> None:
        self.session.flush()


def make_service() -> tuple[CaseWorkbenchService, Session]:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(
        engine,
        tables=[
            CaseRecord.__table__,
            AuthoritySource.__table__,
            CaseClaim.__table__,
            CaseAnalysisLink.__table__,
            SemanticArtifact.__table__,
            SemanticCorrection.__table__,
            CaseAction.__table__,
            CaseFeedback.__table__,
            CaseReportVersion.__table__,
            CaseAuditEvent.__table__,
        ],
    )
    session = Session(engine, expire_on_commit=False)
    return CaseWorkbenchService(AsyncSessionAdapter(session)), session


def test_case_lifecycle_values_are_the_approved_contract():
    assert [item.value for item in CaseLifecycle] == [
        "draft", "collecting", "evidence_ready", "analyzing", "awaiting_review",
        "actioning", "ready_to_close", "closed",
    ]


def test_case_workbench_closed_loop_and_frozen_report():
    async def scenario():
        actor = SimpleNamespace(id=9, username="analyst")
        service, session = make_service()
        try:
            case = await service.create_case(event_id="event-1", title="Case one", actor=actor)
            assert case.lifecycle == CaseLifecycle.DRAFT
            source = await service.register_authority_source(
                name="Official source", url="https://example.test/source", actor=actor
            )
            assert source.review_status == "pending_review"
            assert source.tier is None
            await service.review_authority_source(source.source_id, decision="allowlist", tier="government_official", actor=actor)
            claim = await service.add_claim(
                case.case_id, authority_source_id=source.source_id, exact_quote="Official statement.",
                quote_start=0, quote_end=19, source_url="https://example.test/post", account="official",
                published_at=datetime(2026, 8, 1, tzinfo=timezone.utc), role="primary", actor=actor,
            )
            assert claim.content_sha256
            run = await service.request_run(case.case_id, snapshot_or_run_id="snapshot-1", actor=actor)
            assert run.stages == ["semantic_enrichment", "coordination_discover", "propagation_analysis", "student", "teacher"]
            assert "blocked_missing_primary_claim" not in run.blockers
            await service.set_canonical_verdict(case.case_id, verdict={"conclusion": "confirmed"}, approved=True, actor=actor)
            action = await service.add_action(case.case_id, description="Notify owner", required=True, actor=actor)
            with pytest.raises(ValueError, match="required actions"):
                await service.close_case(case.case_id, closure_note="Completed", actor=actor)
            await service.update_action(action.action_id, state="waived", waiver_reason="Not applicable", actor=actor)
            report = await service.create_report(case.case_id, actor=actor)
            assert report.manifest_sha256
            assert "@media print" in report.html
            closed = await service.close_case(case.case_id, closure_note="Completed", actor=actor)
            assert closed.lifecycle == CaseLifecycle.CLOSED
            assert closed.closure_report_id
        finally:
            session.close()
    asyncio.run(scenario())


def test_claim_requires_exact_span_and_allowlisted_primary_source():
    async def scenario():
        actor = SimpleNamespace(id=9, username="analyst")
        service, session = make_service()
        try:
            case = await service.create_case(event_id="event-2", title="Case two", actor=actor)
            source = await service.register_authority_source(name="Pending", url="https://example.test/pending", actor=actor)
            with pytest.raises(ValueError, match="exact quote span"):
                await service.add_claim(case.case_id, authority_source_id=source.source_id, exact_quote="quoted", quote_start=1, quote_end=7, source_url="https://example.test/p", account="p", published_at=None, role="supporting", actor=actor)
            with pytest.raises(ValueError, match="allowlisted"):
                await service.add_claim(case.case_id, authority_source_id=source.source_id, exact_quote="quoted", quote_start=0, quote_end=6, source_url="https://example.test/p", account="p", published_at=None, role="primary", actor=actor)
            run = await service.request_run(case.case_id, snapshot_or_run_id=None, actor=actor)
            assert run.blockers == ["blocked_missing_primary_claim"]
        finally:
            session.close()
    asyncio.run(scenario())
