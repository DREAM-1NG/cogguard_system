from __future__ import annotations

import asyncio
import json

from app.services import system_operations_service


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
