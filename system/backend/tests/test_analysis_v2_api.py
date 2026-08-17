from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import Any
from urllib.parse import quote

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.api.v2.analysis import get_analysis_registry, product_router, router
from app.api.v2.router import api_router
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


class SemanticProjectionRegistry:
    def __init__(
        self,
        runs: list[dict[str, Any]],
        artifacts: dict[tuple[str, str], Any],
        roots: list[dict[str, Any]] | None = None,
        errors=None,
        snapshot_fingerprints: dict[str, str] | None = None,
        current_fingerprints: dict[str, str] | None = None,
    ) -> None:
        self.runs = {str(run["run_id"]): dict(run) for run in runs}
        self.artifacts = dict(artifacts)
        self.errors = dict(errors or {})
        self.candidate_roots = list(roots or [])
        self.snapshot_fingerprints = dict(snapshot_fingerprints or {})
        self.current_fingerprints = dict(current_fingerprints or {})

    @property
    def mongo_db(self):
        raise AssertionError("API routes must not access registry.mongo_db")

    async def get_run(self, run_id: str):
        run = self.runs.get(run_id)
        return dict(run) if run is not None else None

    async def load_run_artifact(self, run_id: str, artifact_key: str):
        error = self.errors.get((run_id, artifact_key))
        if error is not None:
            raise error
        value = self.artifacts.get((run_id, artifact_key))
        if value is None:
            raise KeyError(f"missing artifact: {run_id}:{artifact_key}")
        return value

    async def list_semantic_artifact_candidates(self, event_id: str):
        candidates: list[tuple[dict[str, Any], str]] = []
        for root in self.candidate_roots:
            run_id = str(root.get("run_id") or "")
            run = self.runs.get(run_id)
            if run is not None and run.get("event_id") == event_id:
                candidates.append((dict(run), str(root.get("created_at") or "")))
        candidates.sort(
            key=lambda candidate: (
                str(candidate[0].get("created_at") or ""),
                candidate[1],
                str(candidate[0].get("run_id") or ""),
            ),
            reverse=True,
        )
        return [run for run, _created_at in candidates]

    async def load_event_snapshot(self, snapshot_id: str):
        fingerprint = self.snapshot_fingerprints[str(snapshot_id)]
        run = next(run for run in self.runs.values() if run.get("snapshot_id") == snapshot_id)
        return SimpleNamespace(
            snapshot_id=snapshot_id,
            event_id=run["event_id"],
            data_fingerprint=fingerprint,
            core_window=SimpleNamespace(),
            context_window=SimpleNamespace(),
        )

    async def build_current_event_snapshot(self, *, event_id: str, **_kwargs):
        fingerprint = self.current_fingerprints[event_id]
        return SimpleNamespace(event_id=event_id, data_fingerprint=fingerprint)


def _semantic_root(run_id: str, created_at: str) -> dict[str, str]:
    return {
        "run_id": run_id,
        "artifact_key": "stage:semantic_enrichment:result",
        "created_at": created_at,
    }


def _ready_semantic_artifact(fingerprint: str, **overrides: Any) -> dict[str, Any]:
    return {
        "technology": "semantic_enrichment",
        "status": "ok",
        "runtime_status": "ready",
        "embedding_manifest": {"snapshot_fingerprint": fingerprint},
        **overrides,
    }


def _product_app(registry, role: str = "analyst"):
    app = FastAPI()
    app.include_router(router, prefix="/api/v2/governance")
    from app.api.v2.analysis import execution_router

    app.include_router(execution_router, prefix="/api/v2/analysis")
    app.include_router(product_router, prefix="/api/v2/analysis")
    app.dependency_overrides[get_analysis_registry] = lambda: registry
    app.dependency_overrides[get_current_user] = lambda: FakeUser(role)
    return app


def _deployed_v2_app(registry, role: str = "analyst"):
    app = FastAPI()
    app.include_router(api_router)
    app.dependency_overrides[get_analysis_registry] = lambda: registry
    app.dependency_overrides[get_current_user] = lambda: FakeUser(role)
    return app


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


def test_deployed_v2_router_registers_product_and_legacy_artifact_routes_for_analysts():
    async def scenario():
        artifact_key = "stage:semantic enrichment/result"
        registry = SemanticProjectionRegistry(
            runs=[{"run_id": "run_ready", "event_id": "event_1", "snapshot_id": "snap_1"}],
            artifacts={("run_ready", artifact_key): {"status": "ok", "value": 7}},
        )
        app = _deployed_v2_app(registry)
        transport = ASGITransport(app=app)
        encoded_key = quote(artifact_key, safe="")

        async with AsyncClient(transport=transport, base_url="http://test") as client:
            product = await client.get(f"/api/v2/analysis/runs/run_ready/artifacts/{encoded_key}")
            governance = await client.get(f"/api/v2/governance/runs/run_ready/artifacts/{encoded_key}")

        assert product.status_code == 200
        assert product.json()["data"] == {"status": "ok", "value": 7}
        assert governance.status_code == 200
        assert governance.json()["data"] == {"status": "ok", "value": 7}

    asyncio.run(scenario())


def test_semantic_event_projection_selects_latest_ready_artifact():
    async def scenario():
        artifact_key = "stage:semantic_enrichment:result"
        registry = SemanticProjectionRegistry(
            runs=[
                {
                    "run_id": "run_blocked_newer",
                    "event_id": "event_1",
                    "snapshot_id": "snap_blocked_newer",
                    "created_at": "2026-08-14T03:00:00+00:00",
                    "artifact_manifest": {"data_fingerprint": "fingerprint_blocked"},
                },
                {
                    "run_id": "run_new",
                    "event_id": "event_1",
                    "snapshot_id": "snap_new",
                    "created_at": "2026-08-14T02:00:00+00:00",
                    "artifact_manifest": {"data_fingerprint": "fingerprint_new"},
                },
                {
                    "run_id": "run_old",
                    "event_id": "event_1",
                    "snapshot_id": "snap_old",
                    "created_at": "2026-08-14T01:00:00+00:00",
                    "artifact_manifest": {"data_fingerprint": "fingerprint_old"},
                },
            ],
            artifacts={
                ("run_blocked_newer", artifact_key): {
                    "technology": "semantic_enrichment",
                    "status": "model_weights_blocked",
                    "runtime_status": "blocked",
                    "blocking_reason": "fixed local weights unavailable",
                },
                ("run_new", artifact_key): _ready_semantic_artifact(
                    "fingerprint_new", layers={"posts": [], "comments": []}
                ),
                ("run_old", artifact_key): {"status": "ok", "runtime_status": "ready", "marker": "old"},
            },
            roots=[
                _semantic_root("run_old", "2026-08-14T04:00:00+00:00"),
                _semantic_root("run_blocked_newer", "2026-08-14T03:00:00+00:00"),
                _semantic_root("run_new", "2026-08-14T01:00:00+00:00"),
            ],
            snapshot_fingerprints={"snap_new": "fingerprint_new"},
            current_fingerprints={"event_1": "fingerprint_new"},
        )
        app = _product_app(registry)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/v2/analysis/events/event_1/semantic")

        assert response.status_code == 200
        assert response.json()["data"] == {
            "event_id": "event_1",
            "run_id": "run_new",
            "snapshot_id": "snap_new",
            "status": "ready",
            "blocking_reason": None,
            "artifact": {
                "technology": "semantic_enrichment",
                "status": "ok",
                "runtime_status": "ready",
                "embedding_manifest": {"snapshot_fingerprint": "fingerprint_new"},
                "layers": {"posts": [], "comments": []},
            },
        }

    asyncio.run(scenario())


def test_semantic_event_projection_uses_registry_candidates_and_never_selects_other_event_root():
    async def scenario():
        artifact_key = "stage:semantic_enrichment:result"
        registry = SemanticProjectionRegistry(
            runs=[
                {
                    "run_id": "run_target_ready",
                    "event_id": "event_target",
                    "snapshot_id": "snapshot_target",
                    "created_at": "2026-08-14T02:00:00+00:00",
                    "artifact_manifest": {"data_fingerprint": "fingerprint_target"},
                },
                {
                    "run_id": "run_other_newer_ready",
                    "event_id": "event_other",
                    "snapshot_id": "snapshot_other",
                    "created_at": "2026-08-14T10:00:00+00:00",
                    "artifact_manifest": {"data_fingerprint": "fingerprint_other"},
                },
            ],
            artifacts={
                ("run_target_ready", artifact_key): _ready_semantic_artifact(
                    "fingerprint_target", marker="target"
                ),
                ("run_other_newer_ready", artifact_key): _ready_semantic_artifact(
                    "fingerprint_other", marker="other"
                ),
            },
            roots=[
                _semantic_root("run_target_ready", "2026-08-14T03:00:00+00:00"),
                _semantic_root("run_other_newer_ready", "2026-08-14T11:00:00+00:00"),
            ],
            snapshot_fingerprints={
                "snapshot_target": "fingerprint_target",
                "snapshot_other": "fingerprint_other",
            },
            current_fingerprints={"event_target": "fingerprint_target"},
        )
        app = _deployed_v2_app(registry)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/v2/analysis/events/event_target/semantic")

        assert response.status_code == 200
        assert response.json()["data"] == {
            "event_id": "event_target",
            "run_id": "run_target_ready",
            "snapshot_id": "snapshot_target",
            "status": "ready",
            "blocking_reason": None,
            "artifact": {
                "technology": "semantic_enrichment",
                "status": "ok",
                "runtime_status": "ready",
                "embedding_manifest": {"snapshot_fingerprint": "fingerprint_target"},
                "marker": "target",
            },
        }

    asyncio.run(scenario())


def test_semantic_event_projection_is_explicitly_blocked_for_blocked_or_tampered_artifacts():
    async def scenario():
        artifact_key = "stage:semantic_enrichment:result"
        runs = [
            {
                "run_id": "run_blocked",
                "event_id": "event_blocked",
                "snapshot_id": "snap_blocked",
                "created_at": "2026-08-14T02:00:00+00:00",
                "artifact_manifest": {"stages": {"semantic_enrichment": {"result_artifact": {"stored": True}}}},
            },
            {
                "run_id": "run_tampered",
                "event_id": "event_tampered",
                "snapshot_id": "snap_tampered",
                "created_at": "2026-08-14T02:00:00+00:00",
                "artifact_manifest": {"stages": {"semantic_enrichment": {"result_artifact": {"stored": True}}}},
            },
        ]
        registry = SemanticProjectionRegistry(
            runs=runs,
            artifacts={
                ("run_blocked", artifact_key): {
                    "technology": "semantic_enrichment",
                    "status": "model_weights_blocked",
                    "runtime_status": "blocked",
                    "blocking_reason": "fixed local weights unavailable",
                    "fallback": False,
                }
            },
            errors={("run_tampered", artifact_key): ValueError("Analysis artifact hash mismatch")},
            roots=[
                _semantic_root("run_blocked", "2026-08-14T02:00:00+00:00"),
                _semantic_root("run_tampered", "2026-08-14T02:00:00+00:00"),
            ],
        )
        app = _product_app(registry)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            blocked = await client.get("/api/v2/analysis/events/event_blocked/semantic")
            tampered = await client.get("/api/v2/analysis/events/event_tampered/semantic")

        assert blocked.status_code == 200
        assert blocked.json()["data"]["status"] == "blocked"
        assert blocked.json()["data"]["blocking_reason"] == "fixed local weights unavailable"
        assert blocked.json()["data"]["artifact"] is None
        assert tampered.status_code == 200
        assert tampered.json()["data"]["status"] == "blocked"
        assert tampered.json()["data"]["blocking_reason"] == "semantic_artifact_integrity_failed"
        assert tampered.json()["data"]["artifact"] is None

    asyncio.run(scenario())


def test_semantic_event_projection_returns_not_found_without_a_ready_artifact():
    async def scenario():
        registry = SemanticProjectionRegistry(runs=[], artifacts={})
        app = _product_app(registry)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/v2/analysis/events/event_missing/semantic")

        assert response.status_code == 200
        assert response.json()["data"] == {
            "event_id": "event_missing",
            "run_id": None,
            "snapshot_id": None,
            "status": "not_found",
            "blocking_reason": "semantic_artifact_not_found",
            "artifact": None,
        }

    asyncio.run(scenario())


def test_semantic_event_projection_rejects_stale_artifact_and_uses_fresh_candidate():
    async def scenario():
        artifact_key = "stage:semantic_enrichment:result"
        registry = SemanticProjectionRegistry(
            runs=[
                {
                    "run_id": "run_stale_newer",
                    "event_id": "event_1",
                    "snapshot_id": "snapshot_stale",
                    "created_at": "2026-08-17T03:00:00+00:00",
                    "artifact_manifest": {"data_fingerprint": "fingerprint_stale"},
                },
                {
                    "run_id": "run_fresh_older",
                    "event_id": "event_1",
                    "snapshot_id": "snapshot_fresh",
                    "created_at": "2026-08-17T02:00:00+00:00",
                    "artifact_manifest": {"data_fingerprint": "fingerprint_fresh"},
                },
            ],
            artifacts={
                ("run_stale_newer", artifact_key): _ready_semantic_artifact("fingerprint_stale"),
                ("run_fresh_older", artifact_key): _ready_semantic_artifact("fingerprint_fresh"),
            },
            roots=[
                _semantic_root("run_stale_newer", "2026-08-17T03:00:00+00:00"),
                _semantic_root("run_fresh_older", "2026-08-17T02:00:00+00:00"),
            ],
            snapshot_fingerprints={
                "snapshot_stale": "fingerprint_stale",
                "snapshot_fresh": "fingerprint_fresh",
            },
            current_fingerprints={"event_1": "fingerprint_fresh"},
        )
        app = _product_app(registry)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/v2/analysis/events/event_1/semantic")

        assert response.status_code == 200
        assert response.json()["data"]["status"] == "ready"
        assert response.json()["data"]["run_id"] == "run_fresh_older"

    asyncio.run(scenario())


def test_semantic_event_projection_blocks_when_current_source_or_manifest_differs():
    async def scenario():
        artifact_key = "stage:semantic_enrichment:result"
        registry = SemanticProjectionRegistry(
            runs=[
                {
                    "run_id": "run_stale",
                    "event_id": "event_stale",
                    "snapshot_id": "snapshot_stale",
                    "created_at": "2026-08-17T03:00:00+00:00",
                    "artifact_manifest": {"data_fingerprint": "fingerprint_snapshot"},
                }
            ],
            artifacts={
                ("run_stale", artifact_key): _ready_semantic_artifact("fingerprint_snapshot"),
            },
            roots=[_semantic_root("run_stale", "2026-08-17T03:00:00+00:00")],
            snapshot_fingerprints={"snapshot_stale": "fingerprint_snapshot"},
            current_fingerprints={"event_stale": "fingerprint_current"},
        )
        app = _product_app(registry)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/v2/analysis/events/event_stale/semantic")

        assert response.status_code == 200
        assert response.json()["data"] == {
            "event_id": "event_stale",
            "run_id": "run_stale",
            "snapshot_id": "snapshot_stale",
            "status": "blocked",
            "blocking_reason": "semantic_artifact_snapshot_mismatch",
            "artifact": None,
        }

    asyncio.run(scenario())


def test_semantic_product_routes_require_analyst_or_admin_authorization():
    async def scenario():
        registry = SemanticProjectionRegistry(runs=[], artifacts={})
        app = _product_app(registry, role="reviewer")
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            artifact = await client.get("/api/v2/analysis/runs/run/artifacts/stage%3Asemantic_enrichment%3Aresult")
            semantic = await client.get("/api/v2/analysis/events/event/semantic")

        assert artifact.status_code == 403
        assert semantic.status_code == 403

    asyncio.run(scenario())
