from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from types import SimpleNamespace

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.api.v2.review_cases import (
    get_review_case_service,
    require_case_editor,
    require_case_reader,
    router,
)
from app.schemas.review_case import (
    CountermeasureReport,
    StudentAssessment,
    StudentAxisAssessment,
    StudentReassessmentReceipt,
    TeacherAudit,
)
from app.services.review_case_service import _teacher_audit_model, _teacher_governance


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
        "audit_input_selection": {
            "source": "engagement_representative",
            "selection_criteria": ["reposts", "likes", "comments"],
            "items": [
                {
                    "post_id": "post_1",
                    "platform": "weibo",
                    "author_name": "Publisher",
                    "excerpt": "Representative post excerpt.",
                    "engagement": {"reposts": 50, "likes": 80, "comments": 12},
                }
            ],
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
                        "governance_report": {
                            "governance_category_id": "hate_harassment",
                            "governance_category": "Hate and harassment",
                            "recommended_actions": ["human review", "limit distribution"],
                            "human_confirmation_items": ["Confirm the target and surrounding context."],
                            "platform_reference_refs": [
                                {
                                    "ref_id": "policy_1",
                                    "platform": "Example Platform",
                                    "title": "Hateful conduct policy",
                                    "url": "https://example.test/policy",
                                    "reference_type": "policy",
                                    "governance_use": "Analyst review guidance",
                                }
                            ],
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
    assert audit.governance.available is True
    assert audit.governance.category_id == "hate_harassment"
    assert audit.governance.recommended_actions == ["human review", "limit distribution"]
    assert audit.governance.references[0].reference_id == "policy_1"
    assert audit.governance.references[0].url == "https://example.test/policy"
    assert audit.selection.source == "engagement_representative"
    assert audit.selection.criteria == ["reposts", "likes", "comments"]
    assert audit.selection.items[0].post_id == "post_1"
    assert audit.selection.items[0].likes == 80
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
    assert audit.governance.available is False


def test_teacher_governance_skips_empty_specialist_sidecars_for_judge_references():
    governance = _teacher_governance(
        [
            {
                "agent_name": "PostHarmAgent",
                "report_role": "expert_initial",
                "system_audit_sidecar": {"governance_report": {}},
            },
            {
                "agent_name": "HarmfulnessJudgeAgent",
                "report_role": "judge",
                "system_audit_sidecar": {
                    "governance_report": {
                        "governance_category": "Hateful conduct",
                        "platform_reference_refs": [
                            {
                                "ref_id": "policy_1",
                                "title": "Hateful conduct policy",
                                "url": "https://example.test/policy",
                            }
                        ],
                    }
                },
            },
        ]
    )

    assert governance.available is True
    assert governance.category == "Hateful conduct"
    assert governance.references[0].reference_id == "policy_1"


def test_teacher_audit_projection_keeps_persisted_failure_visible_without_static_governance():
    audit = _teacher_audit_model(
        case_id="case_1",
        row=_row(status="failed"),
        verdict={
            "status": "failed",
            "verdict_id": "teacher_verdict_1",
            "execution_mode": "maro_llm",
            "reason": "Provider request failed.",
        },
    )

    assert audit.status == "failed"
    assert audit.stages == []
    assert audit.sources == []
    assert audit.governance.available is False
    assert audit.quality["audit_source"] == "persisted_teacher_verdict"


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
            "governance": {
                "available": False,
                "category_id": "",
                "category": "",
                "recommended_actions": [],
                "human_confirmation_items": [],
                "references": [],
            },
            "selection": {
                "source": "",
                "criteria": [],
                "items": [],
            },
            "quality": {},
        }

    asyncio.run(scenario())


def test_student_and_countermeasure_routes_use_dedicated_snapshot_projections():
    class FakeDb:
        def __init__(self) -> None:
            self.commits = 0

        async def commit(self) -> None:
            self.commits += 1

        async def rollback(self) -> None:
            return None

    class FakeService:
        def __init__(self) -> None:
            self.db = FakeDb()
            self.reassessed_by = None

        async def student_assessment(self, case_id: str) -> StudentAssessment:
            return StudentAssessment(
                case_id=case_id,
                snapshot_id="snapshot_1",
                status="completed",
                axes=[
                    StudentAxisAssessment(
                        task="interpersonal_harm",
                        status="completed",
                        conclusion="harmful",
                        risk_score=0.82,
                        threshold=0.7,
                        rationale="A short harm rationale.",
                    ),
                    StudentAxisAssessment(
                        task="claim_deception",
                        status="unconfigured",
                        rationale="This axis has not been deployed.",
                    ),
                ],
            )

        async def reanalyze_student(self, case_id: str, *, actor) -> StudentReassessmentReceipt:
            self.reassessed_by = actor.id
            return StudentReassessmentReceipt(
                case_id=case_id,
                status="completed",
                message="Student assessment refreshed for the current snapshot.",
            )

        async def countermeasure_report(self, case_id: str) -> CountermeasureReport:
            return CountermeasureReport(
                case_id=case_id,
                snapshot_id="snapshot_1",
                teacher_audit_id="teacher_1",
                status="available",
                risk_summary="A bounded risk summary.",
                evidence_refs=["post:p1"],
                policy_refs=["policy:harassment"],
                recommended_actions=["Request analyst review."],
                response_draft="Prepare a factual correction draft.",
                limitations=["Internal advisory only."],
                quality_gate=True,
            )

        async def countermeasure_markdown(self, case_id: str) -> str:
            assert case_id == "case_1"
            return "# 反制建议草案\n\n仅供人工确认。\n"

    async def scenario():
        service = FakeService()
        app = FastAPI()
        app.include_router(router, prefix="/api/v2/review-cases")
        app.dependency_overrides[get_review_case_service] = lambda: service
        app.dependency_overrides[require_case_reader] = lambda: SimpleNamespace(id=7)
        app.dependency_overrides[require_case_editor] = lambda: SimpleNamespace(id=9)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            student = await client.get("/api/v2/review-cases/case_1/student-assessment")
            reassess = await client.post("/api/v2/review-cases/case_1/student-reassess")
            countermeasure = await client.get("/api/v2/review-cases/case_1/countermeasure-report")
            markdown = await client.get("/api/v2/review-cases/case_1/countermeasure-report.md")

        assert student.status_code == 200
        assert student.json()["data"]["axes"][1]["status"] == "unconfigured"
        assert reassess.status_code == 200
        assert service.reassessed_by == 9
        assert service.db.commits == 1
        assert countermeasure.status_code == 200
        assert countermeasure.json()["data"]["quality_gate"] is True
        assert markdown.status_code == 200
        assert markdown.headers["content-type"].startswith("text/markdown")
        assert markdown.headers["content-disposition"] == 'attachment; filename="case_1-countermeasure.md"'
        assert "反制建议草案" in markdown.text

    asyncio.run(scenario())
