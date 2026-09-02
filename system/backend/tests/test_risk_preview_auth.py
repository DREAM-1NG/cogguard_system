import asyncio

from httpx import ASGITransport, AsyncClient

from app.config import settings
from app.db.mysql import get_db
from app.main import app
from app.services import risk_service
from app.services import review_system_service


PREVIEW_TOKEN = "cogguard-preview-token"


async def _fake_get_db():
    yield object()


def _enable_preview(monkeypatch):
    monkeypatch.setattr(settings, "PREVIEW_AUTH_ENABLED", True)
    monkeypatch.setattr(settings, "PREVIEW_AUTH_TOKEN", PREVIEW_TOKEN)
    monkeypatch.setattr(settings, "BACKEND_DEBUG", True)
    monkeypatch.setattr(settings, "BACKEND_ENV", "local")


def test_risk_reports_accept_local_preview_token(monkeypatch):
    _enable_preview(monkeypatch)
    calls = {}

    async def fake_list_reports(**kwargs):
        calls.update(kwargs)
        return ([{"report_id": "r1", "risk_level": "medium"}], 1)

    monkeypatch.setattr(risk_service, "list_reports", fake_list_reports)
    app.dependency_overrides[get_db] = _fake_get_db

    async def _request():
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            client.headers["Authorization"] = f"Bearer {PREVIEW_TOKEN}"
            return await client.get("/api/v1/risk/reports?page=1&page_size=10")

    try:
        response = asyncio.run(_request())
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 200
    assert response.json()["data"]["items"][0]["report_id"] == "r1"
    assert calls["page"] == 1
    assert calls["page_size"] == 10


def test_risk_assess_accepts_local_preview_token_without_backing_user(monkeypatch):
    _enable_preview(monkeypatch)
    calls = {}

    async def fake_assess_risk(**kwargs):
        calls.update(kwargs)
        return {"report_id": "r-preview", "scores": {"risk_level": "low"}}

    monkeypatch.setattr(risk_service, "assess_risk", fake_assess_risk)
    app.dependency_overrides[get_db] = _fake_get_db

    async def _request():
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            client.headers["Authorization"] = f"Bearer {PREVIEW_TOKEN}"
            return await client.post("/api/v1/risk/assess?platform=weibo&event_id=demo")

    try:
        response = asyncio.run(_request())
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 200
    assert response.json()["data"]["report_id"] == "r-preview"
    assert calls["platform"] == "weibo"
    assert calls["event_id"] == "demo"
    assert calls["user_id"] == 0


def test_system_management_lists_accept_local_preview_admin(monkeypatch):
    _enable_preview(monkeypatch)
    calls = {}

    async def fake_list_provider_configs(db):
        calls["providers_db"] = db
        return {"items": [{"id": 1, "name": "provider"}], "total": 1}

    monkeypatch.setattr(review_system_service, "list_provider_configs", fake_list_provider_configs)
    app.dependency_overrides[get_db] = _fake_get_db

    async def _request():
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            client.headers["Authorization"] = f"Bearer {PREVIEW_TOKEN}"
            return await client.get("/api/v1/risk/review/providers")

    try:
        response = asyncio.run(_request())
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 200
    assert response.json()["data"]["items"][0]["name"] == "provider"
    assert "providers_db" in calls


def test_system_management_provider_list_falls_back_when_review_tables_unavailable(monkeypatch):
    calls = {}

    class BrokenDb:
        async def execute(self, *_args, **_kwargs):
            calls["execute"] = True
            raise RuntimeError("review tables unavailable")

    monkeypatch.setattr(review_system_service, "env_provider_public_view", lambda provider_type: {
        "id": None,
        "name": f"env-{provider_type}",
        "provider_type": provider_type,
        "is_active": True,
        "source": "env_fallback",
    })

    result = asyncio.run(review_system_service.list_provider_configs(BrokenDb()))

    assert calls["execute"] is True
    assert [item["provider_type"] for item in result["items"]] == ["text_llm", "vision_llm", "retrieval"]


def test_system_management_empty_lists_when_review_tables_unavailable():
    class BrokenDb:
        async def execute(self, *_args, **_kwargs):
            raise RuntimeError("review tables unavailable")

    datasets = asyncio.run(review_system_service.list_gate_datasets(BrokenDb(), page=2, page_size=5))
    policies = asyncio.run(review_system_service.list_policies(BrokenDb(), page=2, page_size=5))
    jobs = asyncio.run(review_system_service.list_review_jobs(BrokenDb(), page=2, page_size=5))

    assert datasets == {"items": [], "page": 2, "page_size": 5, "unavailable": True}
    assert policies == {"items": [], "page": 2, "page_size": 5, "unavailable": True}
    assert jobs == {"items": [], "page": 2, "page_size": 5, "unavailable": True}
