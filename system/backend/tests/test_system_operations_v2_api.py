from __future__ import annotations

import asyncio
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.api.v2 import system_operations as system_operations_api
from app.api.v2.router import api_router as api_v2_router
from app.core.security import get_current_user
from app.db.mysql import get_db
from app.services import system_operations_service


def _load_review_table_repair():
    path = Path(__file__).parents[1] / "alembic" / "versions" / "f8a1c2d3e4b5_repair_review_table_names.py"
    spec = importlib.util.spec_from_file_location("review_table_repair", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


FORBIDDEN_RESPONSE_FIELDS = {
    "agent",
    "artifact_hash",
    "artifact_uri",
    "checkpoint",
    "confidence",
    "job_id",
    "model",
    "model_version",
    "run_id",
    "status",
    "student",
    "task_id",
    "teacher",
}


def _field_names(value) -> set[str]:
    if isinstance(value, dict):
        return set(value) | {
            field
            for child in value.values()
            for field in _field_names(child)
        }
    if isinstance(value, list):
        return {
            field
            for child in value
            for field in _field_names(child)
        }
    return set()


def test_service_config_projection_hides_internal_provider_fields():
    projected = system_operations_service.service_config_projection(
        {
            "id": 7,
            "name": "Primary Review",
            "provider_type": "text_llm",
            "base_url": "https://service.example.test/v1",
            "model": "internal-routing-name",
            "is_active": True,
            "api_key_status": "configured",
            "supports_vision": False,
            "source": "database",
        }
    )

    assert projected["purpose"] == "text_review"
    assert projected["enabled"] is True
    assert not (_field_names(projected) & FORBIDDEN_RESPONSE_FIELDS)
    assert "internal-routing-name" not in json.dumps(projected)


def test_service_config_request_maps_identifier_only_at_internal_boundary():
    payload = system_operations_service.provider_payload(
        {
            "name": "Primary Review",
            "purpose": "text_review",
            "endpoint": "https://service.example.test/v1",
            "service_identifier": "routing-name",
            "protocol": "responses",
            "credential": "secret",
            "supports_media": False,
        }
    )

    assert payload["provider_type"] == "text_llm"
    assert payload["model"] == "routing-name"
    assert payload["api_key"] == "secret"


def test_operation_health_returns_counts_without_raw_jobs():
    class ScalarResult:
        def scalars(self):
            return self

        def all(self):
            return ["running", "queued", "completed", "failed"]

    class FakeDB:
        async def execute(self, _statement):
            return ScalarResult()

    result = asyncio.run(system_operations_service.operation_health(FakeDB()))

    assert result == {
        "processing_count": 1,
        "waiting_count": 1,
        "completed_count": 1,
        "attention_required_count": 1,
        "message": "Some recent background work needs operator attention.",
    }
    assert not (_field_names(result) & FORBIDDEN_RESPONSE_FIELDS)


def test_analyst_can_read_system_status_but_cannot_change_service_configuration(monkeypatch):
    """The analyst-facing operations page is a read-only health dashboard."""

    async def scenario():
        app = FastAPI()
        app.include_router(system_operations_api.router, prefix="/system")

        async def override_db():
            yield SimpleNamespace()

        app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=7, role="analyst")
        app.dependency_overrides[get_db] = override_db

        async def fake_operation_health(_db):
            return {"processing_count": 0, "waiting_count": 0, "completed_count": 1, "attention_required_count": 0, "message": "ok"}

        async def fake_list_services(_db):
            return {"items": []}

        monkeypatch.setattr(system_operations_api.system_operations_service, "operation_health", fake_operation_health)
        monkeypatch.setattr(system_operations_api.system_operations_service, "list_service_configs", fake_list_services)

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            health = await client.get("/system/operation-health")
            services = await client.get("/system/services")
            mutation = await client.post(
                "/system/services",
                json={"name": "not-allowed", "purpose": "text_review"},
            )

        assert health.status_code == 200
        assert services.status_code == 200
        assert mutation.status_code == 403

    asyncio.run(scenario())


def test_system_operations_are_reachable_through_the_full_v2_router(monkeypatch):
    """Keep the frontend's /api/v2 client base aligned with the mounted API."""

    async def scenario():
        app = FastAPI()
        app.include_router(api_v2_router)

        async def override_db():
            yield SimpleNamespace()

        app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=7, role="analyst")
        app.dependency_overrides[get_db] = override_db

        async def fake_operation_health(_db):
            return {
                "processing_count": 0,
                "waiting_count": 0,
                "completed_count": 1,
                "attention_required_count": 0,
                "message": "ok",
            }

        monkeypatch.setattr(system_operations_api.system_operations_service, "operation_health", fake_operation_health)

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            health = await client.get("/api/v2/system/operation-health")

        assert health.status_code == 200
        assert health.json()["data"]["completed_count"] == 1

    asyncio.run(scenario())


def test_review_table_repair_maps_legacy_kt3_names_to_current_orm_names():
    review_table_repair = _load_review_table_repair()
    mapping = dict(review_table_repair.TABLE_RENAMES)

    assert mapping["kt3_jobs"] == "review_jobs"
    assert mapping["kt3_provider_configs"] == "review_provider_configs"
    assert mapping["kt3_gate_datasets"] == "gate_datasets"
    assert len(mapping) == 19
