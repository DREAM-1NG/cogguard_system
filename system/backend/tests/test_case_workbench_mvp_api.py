import asyncio
from types import SimpleNamespace

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.api.v2 import authority_sources, cases
from app.api.v2.router import api_router


def test_case_workbench_routes_are_registered_and_require_authentication():
    async def scenario():
        app = FastAPI()
        app.include_router(api_router)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/v2/cases")
        assert response.status_code == 401
        paths = set(app.openapi()["paths"])
        assert "/api/v2/cases" in paths
        assert "/api/v2/authority-sources" in paths
        assert "/api/v2/authority-sources/{source_id}/accounts" in paths
        assert set(app.openapi()["paths"]["/api/v2/authority-sources/{source_id}/accounts"]) == {"get", "post"}
    asyncio.run(scenario())


def test_case_create_uses_success_envelope_with_authenticated_user():
    class FakeService:
        db = SimpleNamespace(commit=lambda: None, rollback=lambda: None)

        async def create_case(self, **kwargs):
            return SimpleNamespace(model_dump=lambda mode: {"case_id": "case_1", "event_id": kwargs["event_id"]})

    async def scenario():
        app = FastAPI()
        app.include_router(cases.router, prefix="/api/v2/cases")
        app.dependency_overrides[cases.get_case_workbench_service] = lambda: FakeService()
        app.dependency_overrides[cases.require_case_reader] = lambda: SimpleNamespace(id=1, username="reader", role="analyst")
        app.dependency_overrides[cases.require_case_editor] = lambda: SimpleNamespace(id=1, username="analyst", role="analyst")
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post("/api/v2/cases", json={"event_id": "event-1", "title": "Case one"})
        assert response.status_code == 200
        assert response.json() == {"code": 0, "data": {"case_id": "case_1", "event_id": "event-1"}, "msg": "ok"}
    asyncio.run(scenario())


def test_authority_source_account_list_serializes_decoded_verification_snapshot():
    class FakeService:
        async def list_authority_source_accounts(self, source_id):
            assert source_id == "source_1"
            return [
                SimpleNamespace(
                    source_id=source_id,
                    platform="weibo",
                    author_id="author-1",
                    display_name_snapshot="Official Desk",
                    verification_snapshot='{"badge": true, "evidence": ["profile"]}',
                )
            ]

    async def scenario():
        app = FastAPI()
        app.include_router(authority_sources.router, prefix="/api/v2/authority-sources")
        app.dependency_overrides[authority_sources.get_case_workbench_service] = lambda: FakeService()
        app.dependency_overrides[authority_sources.require_authority_reader] = lambda: SimpleNamespace(
            id=1, username="reader", role="analyst"
        )
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/v2/authority-sources/source_1/accounts")
        assert response.status_code == 200
        assert response.json() == {
            "code": 0,
            "data": [
                {
                    "source_id": "source_1",
                    "platform": "weibo",
                    "author_id": "author-1",
                    "display_name_snapshot": "Official Desk",
                    "verification_snapshot": {"badge": True, "evidence": ["profile"]},
                }
            ],
            "msg": "ok",
        }

    asyncio.run(scenario())


def test_authority_source_account_list_unknown_source_returns_404():
    class FakeService:
        async def list_authority_source_accounts(self, source_id):
            assert source_id == "missing_source"
            raise KeyError("authority source not found")

    async def scenario():
        app = FastAPI()
        app.include_router(authority_sources.router, prefix="/api/v2/authority-sources")
        app.dependency_overrides[authority_sources.get_case_workbench_service] = lambda: FakeService()
        app.dependency_overrides[authority_sources.require_authority_reader] = lambda: SimpleNamespace(
            id=1, username="reader", role="analyst"
        )
        transport = ASGITransport(app=app, raise_app_exceptions=False)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/v2/authority-sources/missing_source/accounts")
        assert response.status_code == 404
        assert response.json()["detail"] == "'authority source not found'"

    asyncio.run(scenario())
