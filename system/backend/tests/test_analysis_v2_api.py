from __future__ import annotations

import asyncio
from typing import Any

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.api.v2.analysis import get_analysis_registry, router
from app.core.security import get_current_user
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


class FakeUser:
    def __init__(self, role: str) -> None:
        self.role = role


def test_v2_governance_routes_are_read_only_and_recover_events():
    async def scenario():
        fake_registry = FakeAnalysisRegistry()
        app = FastAPI()
        app.include_router(router, prefix="/api/v2/governance")
        app.dependency_overrides[get_analysis_registry] = lambda: fake_registry
        app.dependency_overrides[get_current_user] = lambda: FakeUser("admin")
        headers: dict[str, str] = {}
        transport = ASGITransport(app=app)

        async with AsyncClient(transport=transport, base_url="http://test") as client:
            create_snapshot = await client.post(
                "/api/v2/governance/snapshots",
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
            create_run = await client.post(
                "/api/v2/governance/runs",
                headers=headers,
                json={
                    "event_id": "trump_visit",
                    "snapshot_id": "snapshot_a",
                    "requested_stages": ["coordination_discover", "propagation_analysis", "student"],
                    "options": {"priority": "demo"},
                },
            )
            run_detail = await client.get("/api/v2/governance/runs/run_a", headers=headers)
            events = await client.get(
                "/api/v2/governance/runs/run_a/events",
                headers=headers,
                params={"after_id": 1},
            )
            execute = await client.post("/api/v2/governance/runs/run_a/execute", headers=headers)
            status_update = await client.patch(
                "/api/v2/governance/runs/run_a/status",
                headers=headers,
                json={"status": "running"},
            )
            stream = await client.get(
                "/api/v2/governance/runs/run_a/events/stream",
                headers={**headers, "Last-Event-ID": "1"},
            )

        assert create_snapshot.status_code in {404, 405}
        assert create_run.status_code in {404, 405}
        assert run_detail.json()["data"]["status"] == "queued"
        assert [event["id"] for event in events.json()["data"]["events"]] == [2]
        assert execute.status_code in {404, 405}
        assert status_update.status_code in {404, 405}
        assert stream.status_code == 200
        assert stream.headers["content-type"].startswith("text/event-stream")
        assert "id: 2" in stream.text
        assert "event: run_status_changed" in stream.text
        assert "id: 1" not in stream.text

    asyncio.run(scenario())


def test_v2_governance_diagnostics_require_admin_role():
    async def scenario():
        app = FastAPI()
        app.include_router(router, prefix="/api/v2/governance")
        app.dependency_overrides[get_analysis_registry] = lambda: FakeAnalysisRegistry()
        app.dependency_overrides[get_current_user] = lambda: FakeUser("analyst")
        transport = ASGITransport(app=app)

        async with AsyncClient(transport=transport, base_url="http://test") as client:
            detail = await client.get("/api/v2/governance/runs/run_a")
            events = await client.get("/api/v2/governance/runs/run_a/events")
            stream = await client.get("/api/v2/governance/runs/run_a/events/stream")

        assert detail.status_code == 403
        assert events.status_code == 403
        assert stream.status_code == 403

    asyncio.run(scenario())


def test_main_app_mounts_v2_router():
    async def scenario():
        transport = ASGITransport(app=main_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/v2/health")
            removed_product_route = await client.get("/api/v2/analysis/runs/run_a")

        assert response.status_code == 200
        assert response.json() == {"status": "ok", "version": "v2"}
        assert removed_product_route.status_code == 404

    asyncio.run(scenario())
