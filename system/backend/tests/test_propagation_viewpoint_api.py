from __future__ import annotations

import asyncio
from types import SimpleNamespace

from httpx import ASGITransport, AsyncClient

from app.api.v1 import propagation as propagation_api
from app.core.security import get_current_user
from app.main import app


def test_claim_response_landscape_route_is_registered_and_requires_authentication():
    async def scenario():
        paths = app.openapi()["paths"]
        assert "/api/v1/propagation/claim-response-landscape" in paths

        async def override_db():
            yield SimpleNamespace(name="db")

        app.dependency_overrides[propagation_api.get_db] = override_db
        app.dependency_overrides[propagation_api.get_mongo_db] = lambda: SimpleNamespace(name="mongo")
        transport = ASGITransport(app=app)
        try:
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.get("/api/v1/propagation/claim-response-landscape?event_id=event-1")
        finally:
            app.dependency_overrides.pop(propagation_api.get_db, None)
            app.dependency_overrides.pop(propagation_api.get_mongo_db, None)

        assert response.status_code == 401

    asyncio.run(scenario())


def test_claim_response_landscape_api_passes_authenticated_event_scope(monkeypatch):
    calls = {}
    fake_db = SimpleNamespace(name="db")
    fake_mongo = SimpleNamespace(name="mongo")

    async def override_db():
        yield fake_db

    async def fake_build_claim_response_landscape(event_id, platform=None, **kwargs):
        calls.update({"event_id": event_id, "platform": platform, **kwargs})
        return {
            "status": "ready",
            "event_id": event_id,
            "platform": platform,
            "claim_anchor": {"claim_id": "claim-1"},
            "official_publications": [],
            "influential_responses": [],
            "timeline": [],
            "coverage": {},
        }

    monkeypatch.setattr(
        propagation_api.claim_response_landscape_service,
        "build_claim_response_landscape",
        fake_build_claim_response_landscape,
    )
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=7, role="analyst", is_active=True)
    app.dependency_overrides[propagation_api.get_db] = override_db
    app.dependency_overrides[propagation_api.get_mongo_db] = lambda: fake_mongo

    async def scenario():
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(
                "/api/v1/propagation/claim-response-landscape?event_id=event-1&platform=weibo"
            )
        assert response.status_code == 200
        assert response.json()["data"]["status"] == "ready"

    try:
        asyncio.run(scenario())
    finally:
        app.dependency_overrides.pop(get_current_user, None)
        app.dependency_overrides.pop(propagation_api.get_db, None)
        app.dependency_overrides.pop(propagation_api.get_mongo_db, None)

    assert calls == {
        "event_id": "event-1",
        "platform": "weibo",
        "db": fake_db,
        "mongo_db": fake_mongo,
    }
