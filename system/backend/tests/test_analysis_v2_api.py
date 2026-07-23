from __future__ import annotations

import asyncio
from typing import Any

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.api.v2.analysis import get_analysis_executor, get_analysis_registry, router
from app.core.security import PREVIEW_ACCESS_TOKEN
from app.main import app as main_app


class FakeAnalysisRegistry:
    def __init__(self) -> None:
        self.created_snapshots: list[dict[str, Any]] = []
        self.runs = {
            "run_a": {
                "run_id": "run_a",
                "event_id": "trump_visit",
                "snapshot_id": "snapshot_a",
                "status": "queued",
            }
        }
        self.events = [
            {
                "id": 1,
                "run_id": "run_a",
                "event_type": "run_queued",
                "status": "queued",
                "payload": {"snapshot_id": "snapshot_a"},
            },
            {
                "id": 2,
                "run_id": "run_a",
                "event_type": "run_status_changed",
                "status": "running",
                "payload": {"worker": "local"},
            },
        ]

    async def create_event_snapshot(self, **kwargs):
        self.created_snapshots.append(kwargs)
        return {
            "snapshot_id": "snapshot_a",
            "event_id": kwargs["event_id"],
            "platforms": ["weibo"],
            "quality_report": {"status": "pass", "core_posts": 1},
        }

    async def create_run(self, **kwargs):
        return dict(self.runs["run_a"])

    async def get_run(self, run_id: str):
        return self.runs.get(run_id)

    async def list_run_events(self, run_id: str, *, after_id: int = 0, limit: int = 100):
        return [event for event in self.events if event["run_id"] == run_id and event["id"] > after_id][:limit]


class FakeAnalysisExecutor:
    def __init__(self) -> None:
        self.calls: list[str] = []

    async def execute_run(self, run_id: str):
        self.calls.append(run_id)
        return {
            "run_id": run_id,
            "status": "awaiting_review",
            "results": {"teacher": {"job_id": "teacher_job_1"}},
        }


def test_v2_analysis_routes_create_runs_and_recover_events():
    async def scenario():
        fake_registry = FakeAnalysisRegistry()
        fake_executor = FakeAnalysisExecutor()
        app = FastAPI()
        app.include_router(router, prefix="/api/v2/analysis")
        app.dependency_overrides[get_analysis_registry] = lambda: fake_registry
        app.dependency_overrides[get_analysis_executor] = lambda: fake_executor
        headers = {"Authorization": f"Bearer {PREVIEW_ACCESS_TOKEN}"}
        transport = ASGITransport(app=app)

        async with AsyncClient(transport=transport, base_url="http://test") as client:
            snapshot = await client.post(
                "/api/v2/analysis/snapshots",
                headers=headers,
                json={
                    "event_id": "trump_visit",
                    "platform": "weibo",
                    "core_window": {
                        "start": "2026-05-11T00:00:00Z",
                        "end": "2026-05-22T00:00:00Z",
                    },
                    "context_window": {
                        "start": "2026-05-01T00:00:00Z",
                        "end": "2026-05-31T00:00:00Z",
                    },
                },
            )
            run = await client.post(
                "/api/v2/analysis/runs",
                headers=headers,
                json={
                    "event_id": "trump_visit",
                    "snapshot_id": "snapshot_a",
                    "requested_stages": ["coordination_discover", "propagation_analysis", "student"],
                    "options": {"priority": "demo"},
                },
            )
            run_detail = await client.get("/api/v2/analysis/runs/run_a", headers=headers)
            events = await client.get(
                "/api/v2/analysis/runs/run_a/events",
                headers=headers,
                params={"after_id": 1},
            )
            execute = await client.post("/api/v2/analysis/runs/run_a/execute", headers=headers)
            stream = await client.get(
                "/api/v2/analysis/runs/run_a/events/stream",
                headers={**headers, "Last-Event-ID": "1"},
            )

        assert snapshot.status_code == 200
        assert snapshot.json()["data"]["snapshot_id"] == "snapshot_a"
        assert fake_registry.created_snapshots[0]["platform"] == "weibo"
        assert run.status_code == 200
        assert run.json()["data"]["run_id"] == "run_a"
        assert run_detail.json()["data"]["status"] == "queued"
        assert [event["id"] for event in events.json()["data"]["events"]] == [2]
        assert execute.status_code == 200
        assert execute.json()["data"]["status"] == "awaiting_review"
        assert fake_executor.calls == ["run_a"]
        assert stream.status_code == 200
        assert stream.headers["content-type"].startswith("text/event-stream")
        assert "id: 2" in stream.text
        assert "event: run_status_changed" in stream.text
        assert "id: 1" not in stream.text

    asyncio.run(scenario())


def test_main_app_mounts_v2_router():
    async def scenario():
        transport = ASGITransport(app=main_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/v2/health")

        assert response.status_code == 200
        assert response.json() == {"status": "ok", "version": "v2"}

    asyncio.run(scenario())
