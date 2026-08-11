from __future__ import annotations

import asyncio
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

        assert payload["state"] == "evidence_ready"
        assert payload["evidence"]["source_mode"] == "demo_fixture"
        assert payload["platforms"] == ["weibo"]
        assert payload["active_blockers"][0]["code"] == "platform_gap"
        assert payload["active_blockers"][0]["missing_platforms"] == ["xhs"]
        assert payload["semantic_artifacts"][0]["summary"]["near_duplicates"] == []
        assert "community_comparison" in payload["semantic_artifacts"][0]["summary"]
        assert "near_duplicates" in payload["evidence_matrix"]["semantic"]
        assert "community_comparison" in payload["evidence_matrix"]["semantic"]
        assert payload["reports"][0]["status"] == "placeholder"
        assert "html_url" not in payload["reports"][0]
        assert "pdf_url" not in payload["reports"][0]

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
