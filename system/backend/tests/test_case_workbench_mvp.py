from __future__ import annotations

import asyncio
from copy import deepcopy
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.api.v2.cases import get_case_workbench_service, router
from app.core.security import get_current_user_or_local_preview
from app.services.case_workbench_service import CaseOperationConflict, CaseWorkbenchService


class FakeCaseWorkbenchService:
    async def list_cases(self, *, event_id: str | None = None) -> dict[str, Any]:
        assert event_id == "trump_visit_2026_05_21"
        return {
            "items": [
                {
                    "case_id": "case_trump_visit_2026_05_21",
                    "event_id": event_id,
                    "title": "特朗普访华案例闭环",
                    "state": "awaiting_review",
                    "primary_claim": {"claim_id": "claim_cctv_primary", "status": "approved"},
                    "active_blockers": [],
                }
            ],
            "total": 1,
        }

    async def get_case(self, case_id: str) -> dict[str, Any]:
        assert case_id == "case_trump_visit_2026_05_21"
        return {
            "case_id": case_id,
            "event_id": "trump_visit_2026_05_21",
            "title": "特朗普访华案例闭环",
            "state": "awaiting_review",
            "lifecycle": [
                {"key": "event", "label": "事件", "status": "done"},
                {"key": "evidence", "label": "证据", "status": "done"},
                {"key": "coordination", "label": "Coordination", "status": "done"},
                {"key": "propagation", "label": "Propagation", "status": "done"},
                {"key": "review", "label": "Review", "status": "active"},
                {"key": "action", "label": "处置", "status": "pending"},
                {"key": "feedback", "label": "反馈", "status": "pending"},
            ],
            "primary_claim": {
                "claim_id": "claim_cctv_primary",
                "role": "primary",
                "status": "approved",
                "excerpt": "推动中美关系这艘巨轮沿着正确航道平稳前行。",
                "source": {
                    "name": "央视新闻",
                    "tier": "central_mainstream_original",
                    "url": "https://news.cctv.com/example",
                },
            },
            "supplementary_claims": [
                {
                    "claim_id": "claim_xinhua_support",
                    "role": "supplementary",
                    "status": "approved",
                    "excerpt": "一次历史性访问。",
                    "source": {
                        "name": "新华社",
                        "tier": "central_mainstream_original",
                        "url": "https://www.news.cn/example",
                    },
                }
            ],
            "semantic_artifacts": [
                {
                    "artifact_id": "semantic_main_posts",
                    "artifact_type": "semantic_enrichment",
                    "status": "partial",
                    "model_status": "candidate_unvalidated",
                }
            ],
            "actions": [
                {"action_id": "action_review_public_response", "status": "required", "title": "复核公开回应口径"}
            ],
            "reports": [
                {"version": 1, "status": "frozen", "format": "html_pdf", "content_hash": "a" * 64}
            ],
            "active_blockers": [],
            "workflow_summary": {
                "closed_loop": "事件 -> 证据 -> Coordination -> Propagation -> Review -> 处置 -> 反馈",
                "core_claim_source": "official_media",
                "semantic_score_policy": "evidence_overlay_only",
            },
        }


class FakeCursor:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self.rows = rows

    async def to_list(self, length: int):
        return self.rows[:length]


class FakeCollection:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self.rows = rows

    def find(self, query: dict[str, Any], projection: dict[str, int] | None = None):
        event_id = query.get("event_id")
        platform = query.get("platform")
        rows = [
            row
            for row in self.rows
            if (not event_id or row.get("event_id") == event_id)
            and (not platform or row.get("platform") == platform)
        ]
        return FakeCursor(rows)


def _complete_demo_mongo() -> dict[str, Any]:
    return {
        "raw_posts": FakeCollection(
            [
                {
                    "event_id": "trump_visit_2026_05_21",
                    "platform": "weibo",
                    "post_id": "weibo_demo_1",
                    "author_id": "xinhua",
                    "author_name": "新华社",
                    "timestamp": "2026-05-14T12:00:00+00:00",
                    "content": "特朗普访华欢迎仪式开始，中美关系稳定前行引发关注。",
                },
                {
                    "event_id": "trump_visit_2026_05_21",
                    "platform": "xhs",
                    "post_id": "xhs_demo_1",
                    "author_id": "observer_1",
                    "author_name": "观察账号",
                    "timestamp": "2026-05-14T13:00:00+00:00",
                    "content": "小红书同事件归档样本关注特朗普访华行程。",
                },
            ]
        ),
        "raw_comments": FakeCollection([]),
    }


def test_case_v2_routes_return_closed_loop_projection():
    async def scenario():
        fake_service = FakeCaseWorkbenchService()
        app = FastAPI()
        app.include_router(router, prefix="/api/v2/cases")
        app.dependency_overrides[get_case_workbench_service] = lambda: fake_service
        app.dependency_overrides[get_current_user_or_local_preview] = lambda: None
        transport = ASGITransport(app=app)

        async with AsyncClient(transport=transport, base_url="http://test") as client:
            cases = await client.get("/api/v2/cases", params={"event_id": "trump_visit_2026_05_21"})
            detail = await client.get("/api/v2/cases/case_trump_visit_2026_05_21")

        assert cases.status_code == 200
        assert cases.json()["data"]["items"][0]["case_id"] == "case_trump_visit_2026_05_21"
        assert detail.status_code == 200
        payload = detail.json()["data"]
        assert [step["key"] for step in payload["lifecycle"]] == [
            "event",
            "evidence",
            "coordination",
            "propagation",
            "review",
            "action",
            "feedback",
        ]
        assert payload["primary_claim"]["source"]["name"] == "央视新闻"
        assert payload["supplementary_claims"][0]["source"]["name"] == "新华社"
        assert payload["semantic_artifacts"][0]["model_status"] == "candidate_unvalidated"
        assert payload["workflow_summary"]["semantic_score_policy"] == "evidence_overlay_only"

    asyncio.run(scenario())


def test_case_actions_feedback_and_closeout_are_append_only_demo_state():
    async def scenario():
        service = CaseWorkbenchService(mongo_db=_complete_demo_mongo())

        initial = await service.get_case("case_trump_visit_2026_05_21")
        assert initial["state"] == "actioning"
        assert [action["status"] for action in initial["actions"]] == ["required", "required"]

        after_first = await service.complete_action(
            "case_trump_visit_2026_05_21",
            "action_review_public_response",
            actor_id="analyst",
            note="已复核公开回应口径",
        )
        assert after_first["actions"][0]["status"] == "completed"
        assert after_first["actions"][0]["history"][0]["note"] == "已复核公开回应口径"
        assert after_first["state"] == "actioning"

        await service.complete_action(
            "case_trump_visit_2026_05_21",
            "action_record_feedback",
            actor_id="analyst",
            note="已记录反馈入口",
        )
        with_feedback = await service.submit_feedback(
            "case_trump_visit_2026_05_21",
            actor_id="analyst",
            content="研判人员确认语义辅助只作为证据叠加。",
        )
        assert with_feedback["state"] == "ready_to_close"
        assert with_feedback["feedback"][0]["content"] == "研判人员确认语义辅助只作为证据叠加。"

        closed = await service.submit_closeout_review(
            "case_trump_visit_2026_05_21",
            actor_id="analyst",
            summary="已完成处置和反馈，原型闭环可归档。",
        )
        assert closed["state"] == "closed"
        assert closed["closeout_review"]["summary"] == "已完成处置和反馈，原型闭环可归档。"
        assert [event["action"] for event in closed["audit_events"]] == [
            "complete_case_action",
            "complete_case_action",
            "submit_case_feedback",
            "submit_closeout_review",
        ]

    asyncio.run(scenario())


def test_missing_primary_claim_blocks_stance_and_closeout_without_suppressing_other_semantics():
    async def scenario():
        service = CaseWorkbenchService(mongo_db=_complete_demo_mongo(), missing_primary_claim=True)
        case_id = "case_trump_visit_2026_05_21"

        initial = await service.get_case(case_id)
        semantic_summary = initial["semantic_artifacts"][0]["summary"]
        primary_claim_blocker = next(
            blocker
            for blocker in initial["active_blockers"]
            if blocker["code"] == "blocked_missing_primary_claim"
        )

        assert semantic_summary["stance"]["status"] == "blocked"
        assert semantic_summary["stance"]["code"] == "blocked_missing_primary_claim"
        assert primary_claim_blocker["scope"] == "claim"
        assert primary_claim_blocker["operation"] == "stance_review_closeout"
        assert semantic_summary["sentiment"]
        assert semantic_summary["top_keywords"]
        assert semantic_summary["topics"]

        for action in initial["actions"]:
            await service.complete_action(case_id, action["action_id"], actor_id="analyst")
        await service.submit_feedback(case_id, actor_id="analyst", content="Feedback recorded.")

        with pytest.raises(CaseOperationConflict, match="Closeout review requires"):
            await service.submit_closeout_review(case_id, actor_id="analyst", summary="Closeout is blocked.")

    asyncio.run(scenario())


def test_closeout_is_blocked_until_case_is_ready_to_close():
    async def scenario():
        service = CaseWorkbenchService(mongo_db={})

        with pytest.raises(CaseOperationConflict):
            await service.submit_closeout_review(
                "case_trump_visit_2026_05_21",
                actor_id="analyst",
                summary="不能在平台缺口仍存在时结案。",
            )

    asyncio.run(scenario())


def test_case_v2_mutations_update_shared_demo_projection():
    async def scenario():
        service = CaseWorkbenchService(mongo_db=_complete_demo_mongo())
        app = FastAPI()
        app.include_router(router, prefix="/api/v2/cases")
        app.dependency_overrides[get_case_workbench_service] = lambda: service
        app.dependency_overrides[get_current_user_or_local_preview] = lambda: None
        transport = ASGITransport(app=app)

        async with AsyncClient(transport=transport, base_url="http://test") as client:
            action = await client.post(
                "/api/v2/cases/case_trump_visit_2026_05_21/actions/action_review_public_response/complete",
                json={"note": "API 完成处置"},
            )
            feedback = await client.post(
                "/api/v2/cases/case_trump_visit_2026_05_21/feedback",
                json={"content": "API 写入反馈"},
            )
            premature_closeout = await client.post(
                "/api/v2/cases/case_trump_visit_2026_05_21/closeout",
                json={"summary": "处置未全部完成，不能结案。"},
            )
            detail = await client.get("/api/v2/cases/case_trump_visit_2026_05_21")

        assert action.status_code == 200
        assert feedback.status_code == 200
        assert premature_closeout.status_code == 409
        payload = detail.json()["data"]
        assert payload["actions"][0]["status"] == "completed"
        assert payload["feedback"][0]["content"] == "API 写入反馈"

    asyncio.run(scenario())


def test_case_service_falls_back_with_platform_gap_when_evidence_is_missing():
    async def scenario():
        service = CaseWorkbenchService(mongo_db={})

        payload = await service.get_case("case_trump_visit_2026_05_21")
        semantic_summary = payload["semantic_artifacts"][0]["summary"]
        decision_support = semantic_summary["decision_support"]

        assert payload["state"] == "evidence_ready"
        assert payload["evidence"]["source_mode"] == "demo_fixture"
        assert payload["platforms"] == ["weibo"]
        assert payload["active_blockers"][0]["code"] == "platform_gap"
        assert payload["active_blockers"][0]["missing_platforms"] == ["xhs"]
        assert semantic_summary["near_duplicates"] == []
        assert "community_comparison" in semantic_summary
        assert decision_support["coverage"]["total_texts"] == payload["evidence"]["posts"] + payload["evidence"]["comments"]
        assert decision_support["coverage"]["covered_texts"] == decision_support["coverage"]["total_texts"]
        assert decision_support["coverage"]["coverage_ratio"] == 1.0
        assert decision_support["confidence"]["status"] == "candidate_unvalidated"
        assert decision_support["confidence"]["level"] in {"low", "medium", "high"}
        assert decision_support["operator_prompt"] == "Use semantic outputs as triage hints, not as risk-score inputs."
        assert [item["platform"] for item in decision_support["platform_slices"]] == ["weibo"]
        assert decision_support["time_slices"][0]["texts"] >= 1
        assert "sentiment" in decision_support["module_coverage"]
        assert decision_support["module_coverage"]["stance"]["status"] == "available"
        assert "near_duplicates" in payload["evidence_matrix"]["semantic"]
        assert "community_comparison" in payload["evidence_matrix"]["semantic"]
        assert "decision_support" in payload["evidence_matrix"]["semantic"]
        assert payload["reports"][0]["status"] == "prototype_preview"
        assert payload["reports"][0]["html_url"].endswith("/reports/1.html")
        assert payload["reports"][0]["pdf_url"].endswith("/reports/1.pdf")

    asyncio.run(scenario())


def test_case_graph_evidence_layers_project_coordination_propagation_review():
    async def scenario():
        service = CaseWorkbenchService(mongo_db=_complete_demo_mongo())
        case = await service.get_case("case_trump_visit_2026_05_21")

        layers = case["graph"]["evidence_layers"]

        assert [layer["key"] for layer in layers] == ["coordination", "propagation", "review"]
        for layer in layers:
            assert layer["label"]
            assert layer["status"] in {"available", "partial"}
            assert layer["summary"]
            assert layer["metrics"]
        assert layers[0]["metrics"]["accounts"] >= 2
        assert layers[1]["metrics"]["posts"] >= 2
        assert layers[2]["metrics"]["canonical_verdict_status"] == "approved"

    asyncio.run(scenario())


def test_platform_gap_acknowledgement_unblocks_default_fallback_without_fabricating_evidence():
    async def scenario():
        service = CaseWorkbenchService(mongo_db={})
        case_id = "case_trump_visit_2026_05_21"
        initial = await service.get_case(case_id)
        blocker = initial["active_blockers"][0]

        acknowledged = await service.acknowledge_blocker(
            case_id,
            blocker["blocker_id"],
            actor_id="analyst",
            reason="Prototype review accepts the documented XHS collection gap.",
        )

        assert acknowledged["platforms"] == ["weibo"]
        assert acknowledged["state"] == "actioning"
        assert acknowledged["active_blockers"] == []
        record = acknowledged["blocker_acknowledgements"][0]
        assert record["blocker_id"] == blocker["blocker_id"]
        assert record["actor_id"] == "analyst"
        assert record["reason"] == "Prototype review accepts the documented XHS collection gap."
        assert record["missing_platforms"] == ["xhs"]
        assert record["status"] == "policy_acknowledged"
        assert acknowledged["audit_events"][-1]["action"] == "acknowledge_case_blocker"

    asyncio.run(scenario())


def test_acknowledged_platform_gap_allows_actions_feedback_and_closeout():
    async def scenario():
        service = CaseWorkbenchService(mongo_db={})
        case_id = "case_trump_visit_2026_05_21"
        blocker_id = (await service.get_case(case_id))["active_blockers"][0]["blocker_id"]
        await service.acknowledge_blocker(case_id, blocker_id, actor_id="analyst", reason="Documented demo gap.")
        await service.complete_action(case_id, "action_review_public_response", actor_id="analyst")
        await service.complete_action(case_id, "action_record_feedback", actor_id="analyst")
        ready = await service.submit_feedback(case_id, actor_id="analyst", content="Feedback recorded.")
        closed = await service.submit_closeout_review(case_id, actor_id="analyst", summary="Closeout approved.")

        assert ready["state"] == "ready_to_close"
        assert closed["state"] == "closed"
        assert closed["platforms"] == ["weibo"]
        assert closed["blocker_acknowledgements"][0]["missing_platforms"] == ["xhs"]

    asyncio.run(scenario())


def test_report_preview_keeps_acknowledged_platform_gap_visible():
    async def scenario():
        service = CaseWorkbenchService(mongo_db={})
        case_id = "case_trump_visit_2026_05_21"
        blocker_id = (await service.get_case(case_id))["active_blockers"][0]["blocker_id"]

        await service.acknowledge_blocker(
            case_id,
            blocker_id,
            actor_id="analyst",
            reason="Documented XHS platform gap is acknowledged for prototype review.",
        )

        html = await service.render_report_html(case_id, 1)

        assert "Policy acknowledgements" in html
        assert "Documented XHS platform gap is acknowledged for prototype review." in html
        assert "xhs" in html

    asyncio.run(scenario())


def test_case_payload_and_report_make_prototype_limitations_explicit():
    async def scenario():
        service = CaseWorkbenchService(mongo_db={})
        case_id = "case_trump_visit_2026_05_21"
        blocker_id = (await service.get_case(case_id))["active_blockers"][0]["blocker_id"]

        case = await service.acknowledge_blocker(
            case_id,
            blocker_id,
            actor_id="analyst",
            reason="Documented XHS platform gap is acknowledged for prototype review.",
        )
        html = await service.render_report_html(case_id, 1, pdf_fallback=True)

        assert case["prototype_constraints"] == {
            "platform_evidence_scope": "weibo_only_with_xhs_gap",
            "semantic_examples_text_scope": "excerpt_only_not_full_source_text",
            "semantic_score_policy": "evidence_overlay_only",
            "risk_score_boundary": "semantic_artifacts_do_not_mutate_coordination_propagation_review_scores",
            "model_validation_status": "candidate_unvalidated",
            "pdf_export_status": "html_pdf_fallback",
        }
        for value in (
            "Prototype limitations",
            "weibo_only_with_xhs_gap",
            "excerpt_only_not_full_source_text",
            "semantic_artifacts_do_not_mutate_coordination_propagation_review_scores",
            "html_pdf_fallback",
        ):
            assert value in html

    asyncio.run(scenario())


def test_case_v2_acknowledgement_route_updates_shared_projection_and_returns_404_for_unknown_blocker():
    async def scenario():
        service = CaseWorkbenchService(mongo_db={})
        app = FastAPI()
        app.include_router(router, prefix="/api/v2/cases")
        app.dependency_overrides[get_case_workbench_service] = lambda: service
        app.dependency_overrides[get_current_user_or_local_preview] = lambda: None
        transport = ASGITransport(app=app)
        case_id = "case_trump_visit_2026_05_21"
        blocker_id = (await service.get_case(case_id))["active_blockers"][0]["blocker_id"]

        async with AsyncClient(transport=transport, base_url="http://test") as client:
            acknowledged = await client.post(
                f"/api/v2/cases/{case_id}/blockers/{blocker_id}/acknowledge",
                json={"reason": "Recorded platform collection limitation."},
            )
            missing = await client.post(
                f"/api/v2/cases/{case_id}/blockers/not-a-blocker/acknowledge",
                json={"reason": "Recorded platform collection limitation."},
            )
            detail = await client.get(f"/api/v2/cases/{case_id}")

        assert acknowledged.status_code == 200
        assert acknowledged.json()["data"]["state"] == "actioning"
        assert missing.status_code == 404
        assert detail.json()["data"]["blocker_acknowledgements"][0]["blocker_id"] == blocker_id

    asyncio.run(scenario())


def test_case_service_uses_fixture_when_mongo_configuration_is_unavailable(monkeypatch):
    async def scenario():
        def raise_configuration_error():
            raise RuntimeError("mongo configuration unavailable")

        monkeypatch.setattr("app.services.case_workbench_service.get_mongo_db", raise_configuration_error)
        service = CaseWorkbenchService()

        payload = await service.get_case("case_trump_visit_2026_05_21")

        assert payload["case_id"] == "case_trump_visit_2026_05_21"
        assert payload["active_blockers"][0]["code"] == "platform_gap"

    asyncio.run(scenario())


def test_case_report_endpoints_expose_preview_provenance_and_pdf_fallback():
    async def scenario():
        service = CaseWorkbenchService(mongo_db=_complete_demo_mongo())
        app = FastAPI()
        app.include_router(router, prefix="/api/v2/cases")
        app.dependency_overrides[get_case_workbench_service] = lambda: service
        app.dependency_overrides[get_current_user_or_local_preview] = lambda: None
        transport = ASGITransport(app=app)

        async with AsyncClient(transport=transport, base_url="http://test") as client:
            detail = await client.get("/api/v2/cases/case_trump_visit_2026_05_21")
            html = await client.get("/api/v2/cases/case_trump_visit_2026_05_21/reports/1.html")
            pdf = await client.get("/api/v2/cases/case_trump_visit_2026_05_21/reports/1.pdf")

        report = detail.json()["data"]["reports"][0]
        assert report["status"] == "prototype_preview"
        assert report["html_url"] == "/api/v2/cases/case_trump_visit_2026_05_21/reports/1.html"
        assert report["pdf_url"] == "/api/v2/cases/case_trump_visit_2026_05_21/reports/1.pdf"
        assert html.status_code == 200
        assert html.headers["content-type"].startswith("text/html")
        for value in (
            "case_trump_visit_2026_05_21",
            "trump_visit_2026_05_21",
            "run_case_workbench_demo",
            "candidate_unvalidated",
            "artifact_sha256",
        ):
            assert value in html.text
        assert pdf.status_code == 200
        assert pdf.headers["content-type"].startswith("text/html")
        assert "Production PDF rendering is pending." in pdf.text
        assert 'filename="case_trump_visit_2026_05_21-report-1.html"' in pdf.headers["content-disposition"]

    asyncio.run(scenario())


def test_unknown_case_report_version_returns_404():
    async def scenario():
        service = CaseWorkbenchService(mongo_db=_complete_demo_mongo())
        app = FastAPI()
        app.include_router(router, prefix="/api/v2/cases")
        app.dependency_overrides[get_case_workbench_service] = lambda: service
        app.dependency_overrides[get_current_user_or_local_preview] = lambda: None
        transport = ASGITransport(app=app)

        async with AsyncClient(transport=transport, base_url="http://test") as client:
            missing_version = await client.get("/api/v2/cases/case_trump_visit_2026_05_21/reports/2.html")
            missing_case = await client.get("/api/v2/cases/not-a-case/reports/1.html")

        assert missing_version.status_code == 404
        assert missing_case.status_code == 404

    asyncio.run(scenario())


def test_case_report_preview_hash_tracks_visible_mutation_state():
    async def scenario():
        service = CaseWorkbenchService(mongo_db=_complete_demo_mongo())

        initial = await service.get_case("case_trump_visit_2026_05_21")
        initial_hash = initial["reports"][0]["content_hash"]

        changed = await service.complete_action(
            "case_trump_visit_2026_05_21",
            "action_review_public_response",
            actor_id="analyst",
            note="report hash should reflect visible action status",
        )

        assert changed["reports"][0]["status"] == "prototype_preview"
        assert changed["actions"][0]["status"] == "completed"
        assert changed["reports"][0]["content_hash"] != initial_hash

    asyncio.run(scenario())


def test_semantic_correction_api_appends_advisory_overlay_without_changing_closeout_gates():
    async def scenario():
        service = CaseWorkbenchService(mongo_db={})
        app = FastAPI()
        app.include_router(router, prefix="/api/v2/cases")
        app.dependency_overrides[get_case_workbench_service] = lambda: service
        app.dependency_overrides[get_current_user_or_local_preview] = lambda: None
        transport = ASGITransport(app=app)
        case_id = "case_trump_visit_2026_05_21"
        before = await service.get_case(case_id)
        before_statuses = {item["key"]: item["status"] for item in before["closure_checklist"]}
        before_actions = [(action["action_id"], action["status"]) for action in before["actions"]]
        before_hash = before["reports"][0]["content_hash"]

        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                f"/api/v2/cases/{case_id}/semantic-artifacts/semantic_case_workbench_demo/corrections",
                json={
                    "module": "sentiment",
                    "target_ref": "weibo_demo_1",
                    "original_value": "positive",
                    "corrected_value": "neutral",
                    "reason": "Analyst correction during prototype review.",
                },
            )

        assert response.status_code == 200
        changed = response.json()["data"]
        correction = changed["semantic_corrections"][0]
        assert correction["correction_id"] == "semantic_correction_1"
        assert correction["artifact_id"] == "semantic_case_workbench_demo"
        assert correction["module"] == "sentiment"
        assert correction["target_ref"] == "weibo_demo_1"
        assert correction["original_value"] == "positive"
        assert correction["corrected_value"] == "neutral"
        assert correction["reason"] == "Analyst correction during prototype review."
        assert correction["status"] == "advisory_overlay"
        assert changed["audit_events"][-1]["action"] == "record_semantic_correction"
        assert changed["state"] == before["state"]
        assert changed["platforms"] == before["platforms"] == ["weibo"]
        assert [(action["action_id"], action["status"]) for action in changed["actions"]] == before_actions
        assert {item["key"]: item["status"] for item in changed["closure_checklist"]} == before_statuses
        assert changed["workflow_summary"]["semantic_score_policy"] == "evidence_overlay_only"
        assert changed["reports"][0]["content_hash"] != before_hash

        html = await service.render_report_html(case_id, 1)
        assert "Semantic corrections" in html
        assert "record_semantic_correction" in html
        assert "weibo_demo_1" in html
        assert "neutral" in html
        assert "advisory_overlay" in html

    asyncio.run(scenario())


def test_case_report_cpr_evidence_layers_are_printable():
    async def scenario():
        service = CaseWorkbenchService(mongo_db=_complete_demo_mongo())

        html = await service.render_report_html("case_trump_visit_2026_05_21", 1)

        assert "CPR evidence layers" in html
        assert "Coordination" in html
        assert "Propagation" in html
        assert "Review" in html
        assert "canonical_verdict_status: approved" in html

    asyncio.run(scenario())


def test_case_closure_checklist_tracks_closeout_gates_without_fabricating_evidence():
    async def scenario():
        service = CaseWorkbenchService(mongo_db={})
        case_id = "case_trump_visit_2026_05_21"

        initial = await service.get_case(case_id)
        checklist = {item["key"]: item for item in initial["closure_checklist"]}

        assert list(checklist) == [
            "canonical_verdict",
            "required_actions",
            "feedback",
            "closeout_review",
            "active_blockers",
            "claim_archive",
            "semantic_overlay_policy",
        ]
        assert checklist["canonical_verdict"]["status"] == "passed"
        assert checklist["required_actions"]["status"] == "pending"
        assert checklist["feedback"]["status"] == "pending"
        assert checklist["closeout_review"]["status"] == "pending"
        assert checklist["active_blockers"]["status"] == "blocked"
        assert checklist["active_blockers"]["evidence"]["active_codes"] == ["platform_gap"]
        assert checklist["claim_archive"]["status"] == "passed"
        assert checklist["claim_archive"]["evidence"]["claim_statuses"] == [
            "candidate_unvalidated",
            "candidate_unvalidated",
        ]
        assert checklist["semantic_overlay_policy"]["status"] == "passed"
        assert initial["platforms"] == ["weibo"]

        blocker_id = initial["active_blockers"][0]["blocker_id"]
        await service.acknowledge_blocker(
            case_id,
            blocker_id,
            actor_id="analyst",
            reason="Documented XHS platform gap for prototype closure.",
        )
        for action in (await service.get_case(case_id))["actions"]:
            await service.complete_action(case_id, action["action_id"], actor_id="analyst")
        ready = await service.submit_feedback(case_id, actor_id="analyst", content="Feedback recorded.")
        ready_checklist = {item["key"]: item for item in ready["closure_checklist"]}

        assert ready["state"] == "ready_to_close"
        assert ready_checklist["active_blockers"]["status"] == "passed"
        assert ready_checklist["active_blockers"]["evidence"]["acknowledgement_count"] == 1
        assert ready_checklist["required_actions"]["status"] == "passed"
        assert ready_checklist["feedback"]["status"] == "passed"
        assert ready_checklist["closeout_review"]["status"] == "pending"
        assert ready["platforms"] == ["weibo"]

        closed = await service.submit_closeout_review(case_id, actor_id="analyst", summary="Closeout accepted.")
        assert {item["status"] for item in closed["closure_checklist"]} == {"passed"}
        assert closed["platforms"] == ["weibo"]

    asyncio.run(scenario())


def test_case_closure_checklist_exposes_missing_primary_claim_blocker():
    async def scenario():
        service = CaseWorkbenchService(mongo_db=_complete_demo_mongo(), missing_primary_claim=True)

        case = await service.get_case("case_trump_visit_2026_05_21")
        checklist = {item["key"]: item for item in case["closure_checklist"]}

        assert checklist["claim_archive"]["status"] == "blocked"
        assert checklist["claim_archive"]["evidence"]["primary"] == "missing_primary_claim"
        assert checklist["active_blockers"]["status"] == "blocked"
        assert "blocked_missing_primary_claim" in checklist["active_blockers"]["evidence"]["active_codes"]

    asyncio.run(scenario())


def test_case_report_prints_closure_checklist():
    async def scenario():
        service = CaseWorkbenchService(mongo_db={})

        html = await service.render_report_html("case_trump_visit_2026_05_21", 1)

        assert "Closure checklist" in html
        assert "canonical_verdict" in html
        assert "active_blockers" in html
        assert "claim_archive" in html
        assert "semantic_overlay_policy" in html

    asyncio.run(scenario())


def test_case_report_prints_acceptance_summary():
    async def scenario():
        service = CaseWorkbenchService(mongo_db={})
        case_id = "case_trump_visit_2026_05_21"
        blocker_id = (await service.get_case(case_id))["active_blockers"][0]["blocker_id"]
        await service.acknowledge_blocker(case_id, blocker_id, actor_id="analyst", reason="Documented XHS gap.")
        for action in (await service.get_case(case_id))["actions"]:
            await service.complete_action(case_id, action["action_id"], actor_id="analyst")
        await service.submit_feedback(case_id, actor_id="analyst", content="Feedback recorded.")
        await service.submit_closeout_review(case_id, actor_id="analyst", summary="Closeout accepted.")

        html = await service.render_report_html(case_id, 1)

        assert "Acceptance summary" in html
        assert "closed_loop_review_submitted" in html
        assert "cctv_xinhua_markitdown_archive" in html
        assert "coordination_propagation_review" in html
        assert "evidence_overlay_only" in html
        assert "weibo_only_with_platform_gap" in html

    asyncio.run(scenario())


def test_case_report_prints_semantic_decision_support_summary():
    async def scenario():
        service = CaseWorkbenchService(mongo_db={})

        html = await service.render_report_html("case_trump_visit_2026_05_21", 1)

        assert "Semantic decision support" in html
        assert "Coverage" in html
        assert "1.0" in html
        assert "Confidence" in html
        assert "candidate_unvalidated" in html
        assert "Platform slices" in html
        assert "weibo" in html
        assert "Time slices" in html
        assert "Use semantic outputs as triage hints, not as risk-score inputs." in html

    asyncio.run(scenario())


def test_case_report_prints_compact_semantic_evidence_appendix():
    async def scenario():
        service = CaseWorkbenchService(mongo_db={})

        html = await service.render_report_html("case_trump_visit_2026_05_21", 1)

        assert "Semantic evidence appendix" in html
        assert "Sentiment" in html
        assert "Keywords" in html
        assert "Topics" in html
        assert "Entities" in html
        assert "Stance" in html
        assert "Near duplicates" in html
        assert "Community comparison" in html
        assert "candidate_unvalidated" in html
        assert "evidence_overlay_only" in html
        assert "特朗普访华欢迎仪式开始" in html
        assert "positive: 3" in html
        assert "neutral: 3" in html
        assert "特朗普" in html
        assert "weibo" in html

    asyncio.run(scenario())


def test_case_report_prints_semantic_traceability_for_review_and_actions():
    async def scenario():
        service = CaseWorkbenchService(mongo_db={})

        html = await service.render_report_html("case_trump_visit_2026_05_21", 1)

        assert "Review hints" in html
        assert "Keep semantic evidence advisory until local calibration passes." in html
        assert "Module coverage" in html
        assert "sentiment: available 3/3" in html
        assert "stance: available 3/3" in html
        assert "Semantic examples" in html
        assert "weibo_demo_1" in html
        assert "sentiment:positive" in html
        assert "stance:neutral" in html
        assert "Semantic action evidence refs" in html
        assert "action_review_public_response" in html
        assert "semantic_case_workbench_demo" in html
        assert "candidate_unvalidated / evidence_overlay_only" in html

    asyncio.run(scenario())


def test_case_report_handles_missing_primary_claim_without_hiding_semantic_support():
    async def scenario():
        service = CaseWorkbenchService(mongo_db=_complete_demo_mongo(), missing_primary_claim=True)

        html = await service.render_report_html("case_trump_visit_2026_05_21", 1)

        assert "Primary claim unavailable" in html
        assert "blocked_missing_primary_claim" in html
        assert "Semantic decision support" in html
        assert "Confidence" in html
        assert "candidate_unvalidated" in html
        assert "Use semantic outputs as triage hints, not as risk-score inputs." in html

    asyncio.run(scenario())


def test_case_report_appendix_keeps_stance_blocked_when_primary_claim_is_missing():
    async def scenario():
        service = CaseWorkbenchService(mongo_db=_complete_demo_mongo(), missing_primary_claim=True)

        html = await service.render_report_html("case_trump_visit_2026_05_21", 1)

        assert "Semantic evidence appendix" in html
        assert "Stance" in html
        assert "blocked_missing_primary_claim" in html
        assert "Stance requires an approved Primary Claim" in html
        assert "Sentiment" in html
        assert "Keywords" in html
        assert "Topics" in html
        assert "Entities" in html
        assert "Community comparison" in html

    asyncio.run(scenario())


async def _close_fallback_demo_case(service: CaseWorkbenchService) -> tuple[dict[str, Any], str]:
    case_id = "case_trump_visit_2026_05_21"
    initial = await service.get_case(case_id)
    blocker_id = initial["active_blockers"][0]["blocker_id"]
    case = await service.acknowledge_blocker(
        case_id,
        blocker_id,
        actor_id="analyst",
        reason="Documented XHS platform gap for prototype closure.",
    )
    for action in case["actions"]:
        case = await service.complete_action(case_id, action["action_id"], actor_id="analyst")
    await service.submit_feedback(case_id, actor_id="analyst", content="Feedback recorded for closure.")
    closed = await service.submit_closeout_review(
        case_id,
        actor_id="analyst",
        summary="Closeout review completed for the local prototype.",
    )
    return closed, blocker_id


def test_demo_claims_bind_verified_authority_archives_without_approving_claims():
    async def scenario():
        service = CaseWorkbenchService(mongo_db={})
        case = await service.get_case("case_trump_visit_2026_05_21")
        primary = case["primary_claim"]
        supplementary = case["supplementary_claims"][0]

        assert primary["source"]["url"] == "https://news.cctv.com/2026/05/14/ARTIKHqdq6wvI5Npz7H7UEPx260514.shtml"
        assert primary["source_archive_id"] == "archive_cctv_primary_claim_20260811"
        assert primary["span"] == {"start": 658, "end": 678}
        assert primary["source_content_hash"] == "a3e73ac60fe7c801972f609f84b883e067af1c448179f92602ac2d11023dfeb7"
        assert primary["source_markdown_hash"] == "266988c725168dc7d9c5147a8b777a8ff168db698dee6019c04f3342124b8622"
        assert supplementary["source"]["url"] == (
            "https://www.news.cn/politics/leaders/20260515/210c5d4fc07c413e8d2ba8e4519fe816/c.html"
        )
        assert supplementary["source_archive_id"] == "archive_xinhua_supplementary_claim_20260811"
        assert supplementary["span"] == {"start": 988, "end": 998}
        assert supplementary["source_content_hash"] == "0c26be8a705d2c5e2f8436e6f74a0b0661a79c0b3b46f702e30aed314bd5c222"
        assert supplementary["source_markdown_hash"] == "4097ff1f841ab550175e8f69f9b330ca7c0d12564f253d08b2366cc7179ee9c2"

        for claim in [primary, supplementary]:
            assert claim["status"] == "candidate_unvalidated"
            assert claim["source"]["status"] == "verified_archive"
            assert claim["source"]["content_capture"] == "markitdown_archive"
            assert claim["source_content_capture"] == "markitdown_archive"
            assert len(claim["excerpt_hash"]) == 64

        html = await service.render_report_html("case_trump_visit_2026_05_21", 1)
        assert "Claim verification" in html
        assert "Source verification" in html
        assert "Source content capture" in html
        assert "candidate_unvalidated" in html
        assert "archive_cctv_primary_claim_20260811" in html
        assert "a3e73ac60fe7c801972f609f84b883e067af1c448179f92602ac2d11023dfeb7" in html

    asyncio.run(scenario())


def test_case_service_rejects_blank_required_mutation_text():
    async def scenario():
        service = CaseWorkbenchService(mongo_db={})
        case_id = "case_trump_visit_2026_05_21"

        with pytest.raises(CaseOperationConflict, match="non-blank"):
            await service.waive_action(
                case_id,
                "action_review_public_response",
                actor_id="analyst",
                note=" \n ",
            )
        assert (await service.get_case(case_id))["actions"][0]["history"] == []

        blocker_id = (await service.get_case(case_id))["active_blockers"][0]["blocker_id"]
        with pytest.raises(CaseOperationConflict, match="non-blank"):
            await service.acknowledge_blocker(case_id, blocker_id, actor_id="analyst", reason=" \t ")
        assert (await service.get_case(case_id))["blocker_acknowledgements"] == []

        with pytest.raises(CaseOperationConflict, match="non-blank"):
            await service.submit_feedback(case_id, actor_id="analyst", content="  ")
        assert (await service.get_case(case_id))["feedback"] == []

        case = await service.acknowledge_blocker(
            case_id,
            blocker_id,
            actor_id="analyst",
            reason="Documented XHS platform gap.",
        )
        for action in case["actions"]:
            case = await service.complete_action(case_id, action["action_id"], actor_id="analyst")
        ready = await service.submit_feedback(case_id, actor_id="analyst", content="Feedback recorded.")
        assert ready["state"] == "ready_to_close"

        with pytest.raises(CaseOperationConflict, match="non-blank"):
            await service.submit_closeout_review(case_id, actor_id="analyst", summary=" \n ")
        after = await service.get_case(case_id)
        assert after["state"] == "ready_to_close"
        assert after["closeout_review"] is None

    asyncio.run(scenario())


def test_closed_case_rejects_all_mutations_without_changing_demo_state():
    async def scenario():
        service = CaseWorkbenchService(mongo_db={})
        closed, blocker_id = await _close_fallback_demo_case(service)
        case_id = closed["case_id"]
        state_before = deepcopy(service.demo_state)

        with pytest.raises(CaseOperationConflict, match="Closed cases"):
            await service.complete_action(case_id, "action_review_public_response", actor_id="analyst")
        with pytest.raises(CaseOperationConflict, match="Closed cases"):
            await service.waive_action(
                case_id,
                "action_record_feedback",
                actor_id="analyst",
                note="Late waiver is not permitted.",
            )
        with pytest.raises(CaseOperationConflict, match="Closed cases"):
            await service.acknowledge_blocker(
                case_id,
                blocker_id,
                actor_id="analyst",
                reason="Late acknowledgement is not permitted.",
            )
        with pytest.raises(CaseOperationConflict, match="Closed cases"):
            await service.submit_feedback(case_id, actor_id="analyst", content="Late feedback is not permitted.")
        with pytest.raises(CaseOperationConflict, match="Closed cases"):
            await service.submit_closeout_review(
                case_id,
                actor_id="analyst",
                summary="Late closeout is not permitted.",
            )
        with pytest.raises(CaseOperationConflict, match="Closed cases"):
            await service.record_semantic_correction(
                case_id,
                "semantic_case_workbench_demo",
                actor_id="analyst",
                module="sentiment",
                target_ref="weibo_demo_1",
                original_value="positive",
                corrected_value="neutral",
                reason="Late correction is not permitted.",
            )

        assert service.demo_state == state_before
        assert (await service.get_case(case_id))["state"] == "closed"

    asyncio.run(scenario())


def test_case_v2_rejects_blank_mutation_text_with_controlled_conflict():
    async def scenario():
        service = CaseWorkbenchService(mongo_db={})
        app = FastAPI()
        app.include_router(router, prefix="/api/v2/cases")
        app.dependency_overrides[get_case_workbench_service] = lambda: service
        app.dependency_overrides[get_current_user_or_local_preview] = lambda: None
        transport = ASGITransport(app=app, raise_app_exceptions=False)
        case_id = "case_trump_visit_2026_05_21"
        blocker_id = (await service.get_case(case_id))["active_blockers"][0]["blocker_id"]

        async with AsyncClient(transport=transport, base_url="http://test") as client:
            waived = await client.post(
                f"/api/v2/cases/{case_id}/actions/action_review_public_response/waive",
                json={"note": "  "},
            )
            acknowledged = await client.post(
                f"/api/v2/cases/{case_id}/blockers/{blocker_id}/acknowledge",
                json={"reason": "  "},
            )
            feedback = await client.post(f"/api/v2/cases/{case_id}/feedback", json={"content": "  "})

        assert waived.status_code == 409
        assert acknowledged.status_code == 409
        assert feedback.status_code == 409

    asyncio.run(scenario())


def test_case_v2_mutation_roles_allow_analyst_and_local_preview_but_reject_viewer():
    async def scenario():
        service = CaseWorkbenchService(mongo_db=_complete_demo_mongo())
        app = FastAPI()
        app.include_router(router, prefix="/api/v2/cases")
        app.dependency_overrides[get_case_workbench_service] = lambda: service
        transport = ASGITransport(app=app)
        case_id = "case_trump_visit_2026_05_21"

        app.dependency_overrides[get_current_user_or_local_preview] = lambda: SimpleNamespace(
            username="viewer", role="viewer"
        )
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            readable = await client.get(f"/api/v2/cases/{case_id}")
            viewer = await client.post(
                f"/api/v2/cases/{case_id}/actions/action_review_public_response/complete",
                json={"note": "Viewer must not mutate cases."},
            )

            app.dependency_overrides[get_current_user_or_local_preview] = lambda: SimpleNamespace(
                username="analyst", role="analyst"
            )
            analyst = await client.post(
                f"/api/v2/cases/{case_id}/actions/action_review_public_response/complete",
                json={"note": "Analyst can complete actions."},
            )

            app.dependency_overrides[get_current_user_or_local_preview] = lambda: None
            local_preview = await client.post(
                f"/api/v2/cases/{case_id}/feedback",
                json={"content": "Local preview can record feedback."},
            )

        assert readable.status_code == 200
        assert viewer.status_code == 403
        assert analyst.status_code == 200
        assert local_preview.status_code == 200

    asyncio.run(scenario())
