from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from types import SimpleNamespace

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.api.v2.review_cases import (
    get_review_case_service,
    require_case_reader,
    router,
)
from app.schemas.review_case import TeacherAudit
from app.services.review_case_service import _teacher_audit_model


NOW = datetime(2026, 8, 17, tzinfo=timezone.utc)


def _row(*, status: str = "completed") -> SimpleNamespace:
    return SimpleNamespace(
        status=status,
        verdict_id="teacher_verdict_1",
        run_id="analysis_run_1",
        created_at=NOW,
    )


def _completed_verdict() -> dict[str, object]:
    return {
        "status": "completed",
        "execution_mode": "maro_llm",
        "verdict_id": "teacher_verdict_1",
        "model_version": "review-teacher-v1",
        "non_claimable": True,
        "capability_boundary": {"analyst_approval_required": True},
        "signals": {"maro": {"provider_name": "configured", "model": "configured-model"}},
        "dag": {
            "nodes": [
                {"node": "PostHarmAgent", "status": "completed"},
                {"node": "HarmfulnessJudgeAgent", "status": "completed"},
            ]
        },
        "evidence": {
            "agent_reports": [
                {
                    "agent_name": "PostHarmAgent",
                    "report_role": "expert_initial",
                    "status": "completed",
                    "report_text": "Bounded analyst-facing summary.",
                    "system_audit_sidecar": {
                        "retrieval_queries": ["claim verification query"],
                        "source_refs": [
                            {
                                "doc_id": "source_1",
                                "source": "official-source",
                                "title": "Traceable source",
                                "url": "https://example.test/source",
                                "quoted_span": "Quoted evidence passage.",
                                "relation": "contradicted",
                                "retrieval_status": "completed",
                            }
                        ],
                        "rationale_capsule": {
                            "capsule_text": "A short, input-grounded rationale.",
                            "input_spans": ["source phrase"],
                            "evidence_refs": ["source_1"],
                            "capsule_quality_gate": True,
                            "citation_coverage": 1.0,
                        },
                    },
                },
                {
                    "agent_name": "HarmfulnessJudgeAgent",
                    "report_role": "judge",
                    "status": "completed",
                    "report_text": "Judge summary.",
                },
            ]
        },
    }


def test_teacher_audit_projection_is_bounded_and_source_traceable():
    audit = _teacher_audit_model(
        case_id="case_1",
        row=_row(),
        verdict=_completed_verdict(),
    )

    assert audit.status == "completed"
    assert audit.execution_mode == "maro_llm"
    assert [stage.name for stage in audit.stages] == [
        "PostHarmAgent",
        "HarmfulnessJudgeAgent",
    ]
    assert audit.queries == ["claim verification query"]
    assert audit.sources[0].source_id == "source_1"
    assert audit.sources[0].excerpt == "Quoted evidence passage."
    assert audit.rationale.available is True
    assert audit.rationale.quality_gate is True
    serialized = audit.model_dump(mode="json")
    assert "raw_confidence" not in serialized
    assert "system_prompt" not in serialized
    assert "full_chain_of_thought" not in serialized


def test_teacher_audit_projection_keeps_pending_state_without_invented_stages():
    audit = _teacher_audit_model(
        case_id="case_1",
        row=_row(status="draft"),
        verdict={"status": "queued", "verdict_id": "teacher_verdict_1"},
    )

    assert audit.status == "queued"
    assert audit.stages == []
    assert audit.sources == []
    assert audit.rationale.available is False


def test_teacher_audit_route_returns_the_read_only_projection():
    class FakeService:
        async def teacher_audit(self, case_id: str) -> TeacherAudit:
            return TeacherAudit(case_id=case_id, status="unavailable")

    async def scenario():
        app = FastAPI()
        app.include_router(router, prefix="/api/v2/review-cases")
        app.dependency_overrides[get_review_case_service] = lambda: FakeService()
        app.dependency_overrides[require_case_reader] = lambda: SimpleNamespace(id=7)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/v2/review-cases/case_1/teacher-audit")

        assert response.status_code == 200
        assert response.json()["data"] == {
            "case_id": "case_1",
            "status": "unavailable",
            "execution_mode": "",
            "verdict_id": None,
            "run_id": None,
            "model_version": "",
            "provider_name": "",
            "model": "",
            "non_claimable": True,
            "analyst_approval_required": True,
            "requested_at": None,
            "completed_at": None,
            "stages": [],
            "sources": [],
            "queries": [],
            "rationale": {
                "available": False,
                "text": "",
                "input_spans": [],
                "evidence_refs": [],
                "policy_refs": [],
                "quality_gate": False,
                "citation_coverage": None,
            },
            "quality": {},
        }

    asyncio.run(scenario())
