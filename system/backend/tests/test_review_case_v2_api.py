from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from types import SimpleNamespace

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.api.v1 import risk as risk_api
from app.api.v2.review_cases import (
    get_review_case_service,
    require_case_editor,
    require_case_reader,
    router,
)
from app.schemas.review_case import (
    ActionRequired,
    CaseActivity,
    CaseActivityList,
    CaseActivityType,
    ConfirmedDecision,
    CoordinationBusinessSummary,
    DecisionConfirmation,
    DecisionDraft,
    EvidenceAnnotation,
    EvidenceAssessment,
    EvidenceSufficiency,
    PreliminaryFinding,
    PropagationBusinessSummary,
    ReviewCaseDetail,
    ReviewCaseEvidence,
    ReviewCaseList,
    ReviewCaseSummary,
    ReviewConclusion,
    ReviewRequestReceipt,
    ReviewUrgency,
    Disposition,
)


NOW = datetime(2026, 8, 3, tzinfo=timezone.utc)


def _summary() -> ReviewCaseSummary:
    return ReviewCaseSummary(
        case_id="case_1",
        event_id="event_1",
        title="Event one",
        preliminary_finding=PreliminaryFinding(
            conclusion=ReviewConclusion.INSUFFICIENT_EVIDENCE,
            rationale="Available evidence is incomplete.",
        ),
        evidence_sufficiency=EvidenceSufficiency.LIMITED,
        sufficiency_reasons=["Only one source is available."],
        missing_evidence=["Independent source"],
        urgency=ReviewUrgency.WATCH,
        disposition=Disposition.GATHER_EVIDENCE,
        action_required=ActionRequired.ADD_EVIDENCE,
        coordination_summary=CoordinationBusinessSummary(
            narrative="No stable coordinated community is confirmed.",
        ),
        propagation_summary=PropagationBusinessSummary(
            narrative="Propagation remains observable.",
            trend="stable",
        ),
        updated_at=NOW,
    )


class FakeReviewCaseService:
    def __init__(self) -> None:
        self.calls: list[tuple[str, object]] = []
        self.db = FakeSession()

    async def latest(self):
        self.calls.append(("latest", None))
        return ReviewCaseDetail(**_summary().model_dump())

    async def search(self, *, query: str, limit: int):
        self.calls.append(("search", (query, limit)))
        return ReviewCaseList(items=[_summary()], total=1)

    async def detail(self, case_id: str):
        self.calls.append(("detail", case_id))
        return ReviewCaseDetail(**_summary().model_dump())

    async def evidence(self, case_id: str, **kwargs):
        self.calls.append(("evidence", (case_id, kwargs)))
        return ReviewCaseEvidence(case_id=case_id)

    async def request_review(self, case_id: str, request, *, actor):
        self.calls.append(("request_review", case_id))
        return ReviewRequestReceipt(
            case_id=case_id,
            action_required=ActionRequired.NONE,
            message="Review requested.",
        )

    async def add_annotation(self, case_id: str, request, *, actor):
        self.calls.append(("annotation", case_id))
        return EvidenceAnnotation(
            annotation_id="annotation_1",
            evidence_ref=request.evidence_ref,
            assessment=request.assessment,
            note=request.note,
            source_url=request.source_url,
            created_by_name=actor.username,
            created_at=NOW,
        )

    async def save_draft(self, case_id: str, request, *, actor):
        self.calls.append(("draft", case_id))
        return DecisionDraft(
            case_id=case_id,
            draft_version=1,
            conclusion=request.conclusion,
            urgency=request.urgency,
            disposition=request.disposition,
            rationale=request.rationale,
            key_evidence_refs=request.key_evidence_refs,
            unresolved_items=request.unresolved_items,
            saved_at=NOW,
        )

    async def confirm_decision(self, case_id: str, request, *, actor):
        self.calls.append(("confirm", case_id))
        return DecisionConfirmation(
            case_id=case_id,
            decision=ConfirmedDecision(
                decision_id="decision_1",
                decision_version=1,
                conclusion=ReviewConclusion.HARMFUL,
                urgency=ReviewUrgency.URGENT,
                disposition=Disposition.ESCALATE,
                rationale="Coordinated harmful activity is supported by evidence.",
                confirmed_by_name=actor.username,
                confirmed_at=NOW,
            ),
            action_required=ActionRequired.NONE,
        )

    async def activities(self, case_id: str, *, after_id: int, limit: int):
        self.calls.append(("activities", (case_id, after_id, limit)))
        activity = CaseActivity(
            cursor=2,
            case_id=case_id,
            activity_type=CaseActivityType.REVIEW_REQUESTED,
            action_required=ActionRequired.NONE,
            summary="Review requested.",
            actor_name="analyst",
            occurred_at=NOW,
        )
        return CaseActivityList(items=[activity], next_cursor=2)


class FakeSession:
    async def commit(self) -> None:
        return None

    async def rollback(self) -> None:
        return None


def test_review_case_routes_are_product_facing_and_resumable():
    async def scenario():
        fake = FakeReviewCaseService()
        user = SimpleNamespace(id=7, username="analyst", role="analyst")
        app = FastAPI()
        app.include_router(router, prefix="/api/v2/review-cases")
        app.dependency_overrides[get_review_case_service] = lambda: fake
        app.dependency_overrides[require_case_reader] = lambda: user
        app.dependency_overrides[require_case_editor] = lambda: user
        transport = ASGITransport(app=app)

        async with AsyncClient(transport=transport, base_url="http://test") as client:
            responses = [
                await client.get("/api/v2/review-cases/latest"),
                await client.get("/api/v2/review-cases", params={"query": "event", "limit": 10}),
                await client.get("/api/v2/review-cases/case_1"),
                await client.get("/api/v2/review-cases/case_1/evidence"),
                await client.post(
                    "/api/v2/review-cases/case_1/review-requests",
                    json={"reason": "Conflicting evidence."},
                ),
                await client.post(
                    "/api/v2/review-cases/case_1/evidence-annotations",
                    json={
                        "evidence_ref": "weibo:post:p1",
                        "assessment": "supports",
                        "note": "Supports the finding.",
                    },
                ),
                await client.put(
                    "/api/v2/review-cases/case_1/decision-draft",
                    json={
                        "conclusion": "harmful",
                        "urgency": "urgent",
                        "disposition": "escalate",
                        "rationale": "Evidence supports escalation.",
                        "expected_version": 0,
                    },
                ),
                await client.post(
                    "/api/v2/review-cases/case_1/decisions/confirm",
                    json={"expected_draft_version": 1},
                ),
                await client.get(
                    "/api/v2/review-cases/case_1/activities",
                    params={"after_id": 1},
                ),
                await client.get(
                    "/api/v2/review-cases/case_1/events/stream",
                    headers={"Last-Event-ID": "1"},
                ),
            ]

        assert all(response.status_code == 200 for response in responses)
        serialized = " ".join(response.text.lower() for response in responses)
        for forbidden in (
            "artifact_hash",
            "artifact_uri",
            "checkpoint",
            "model_version",
            "agent_name",
            "run_id",
            "job_id",
            "task_id",
            "raw_confidence",
            "runtime_status",
        ):
            assert forbidden not in serialized
        stream = responses[-1]
        assert stream.headers["content-type"].startswith("text/event-stream")
        assert "id: 2" in stream.text
        assert "event: review_requested" in stream.text
        assert "id: 1" not in stream.text

    asyncio.run(scenario())


def test_review_evidence_route_forwards_cursor_pagination():
    async def scenario():
        fake = FakeReviewCaseService()
        user = SimpleNamespace(id=7, username="analyst", role="analyst")
        app = FastAPI()
        app.include_router(router, prefix="/api/v2/review-cases")
        app.dependency_overrides[get_review_case_service] = lambda: fake
        app.dependency_overrides[require_case_reader] = lambda: user
        transport = ASGITransport(app=app)

        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(
                "/api/v2/review-cases/case_1/evidence",
                params={"assessment": "supports", "cursor": 40, "limit": 20},
            )

        assert response.status_code == 200
        assert fake.calls == [
            (
                "evidence",
                (
                    "case_1",
                    {
                        "assessment": EvidenceAssessment.SUPPORTS,
                        "cursor": 40,
                        "limit": 20,
                    },
                ),
            )
        ]

    asyncio.run(scenario())


def test_deprecated_v1_risk_assess_is_review_case_service_mapping(monkeypatch):
    async def forbidden_old_assessment(**_kwargs):
        raise AssertionError("deprecated v1 risk must not call risk_service.assess_risk")

    class FakeLegacyService:
        async def legacy_assess_risk(self, *, platform, event_id):
            return {
                "report_id": "case_1",
                "event_id": event_id,
                "platform": platform,
                "review_case": {"case_id": "case_1"},
                "deprecated": True,
            }

    async def scenario():
        monkeypatch.setattr(risk_api.risk_service, "assess_risk", forbidden_old_assessment)
        response = await risk_api.assess_risk(
            platform="weibo",
            event_id="event_1",
            current_user=SimpleNamespace(id=7, username="analyst"),
            service=FakeLegacyService(),
        )

        assert response["data"]["report_id"] == "case_1"
        assert response["data"]["review_case"] == {"case_id": "case_1"}
        assert response["data"]["deprecated"] is True

    asyncio.run(scenario())


def test_deprecated_v1_feedback_records_case_activity_not_legacy_feedback(monkeypatch):
    async def forbidden_old_feedback(**_kwargs):
        raise AssertionError("deprecated v1 feedback must not write old feedback tables")

    class FakeSession:
        def __init__(self):
            self.committed = False

        async def commit(self):
            self.committed = True

    class FakeLegacyService:
        def __init__(self):
            self.db = FakeSession()
            self.feedback = None

        async def legacy_record_feedback(self, *, report_id, feedback, actor):
            self.feedback = (report_id, feedback, actor.id)
            return {
                "case_id": "case_1",
                "report_id": "case_1",
                "persistence": {"target": "review_case_activities"},
                "deprecated": True,
            }

    async def scenario():
        monkeypatch.setattr(risk_api.risk_service, "record_review_agent_feedback", forbidden_old_feedback)
        service = FakeLegacyService()
        response = await risk_api.record_review_agent_feedback(
            request=SimpleNamespace(
                report_id="case_1",
                model_dump=lambda: {
                    "report_id": "case_1",
                    "notes": "correction",
                    "evidence_refs": [],
                },
            ),
            current_user=SimpleNamespace(id=7, username="analyst"),
            service=service,
        )

        assert service.feedback[0] == "case_1"
        assert service.db.committed is True
        assert response["data"]["persistence"]["target"] == "review_case_activities"

    asyncio.run(scenario())
