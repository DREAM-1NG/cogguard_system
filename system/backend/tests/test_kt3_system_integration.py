"""Risk Review main-system integration tests.

These tests lock the system-level contract before wiring Risk Review into the main
application: role-gated access, encrypted provider config, asynchronous jobs,
dataset ingestion summaries, normalized report persistence helpers, and
idempotent JSON backfill.
"""

from __future__ import annotations

import json

import pytest
from fastapi import HTTPException


def test_require_roles_allows_admin_and_blocks_viewer():
    from app.core.security import require_roles

    dependency = require_roles("admin", "analyst")

    admin = type("User", (), {"id": 1, "role": "admin"})()
    viewer = type("User", (), {"id": 2, "role": "viewer"})()

    assert dependency(admin) is admin
    with pytest.raises(HTTPException) as exc_info:
        dependency(viewer)

    assert exc_info.value.status_code == 403
    assert "requires role" in exc_info.value.detail


def test_provider_key_encryption_masks_and_round_trips(monkeypatch):
    from app.services.risk_review_system_service import decrypt_provider_api_key
    from app.services.risk_review_system_service import encrypted_provider_payload
    from app.services.risk_review_system_service import provider_public_view

    monkeypatch.setattr("app.services.risk_review_system_service.settings.KT3_CONFIG_ENCRYPTION_KEY", "unit-test-secret")

    payload = encrypted_provider_payload(
        {
            "name": "Vision GPT",
            "provider_type": "vision_llm",
            "base_url": "https://api.example.test/v1",
            "model": "gpt-vision",
            "wire_api": "responses",
            "api_key": "sk-test-secret-value",
            "supports_vision": True,
        }
    )

    assert payload["encrypted_api_key"] != "sk-test-secret-value"
    assert decrypt_provider_api_key(payload["encrypted_api_key"]) == "sk-test-secret-value"

    public = provider_public_view({**payload, "id": 7, "is_active": True})
    assert public["id"] == 7
    assert public["api_key_status"] == "configured"
    assert public["api_key_masked"].startswith("sk-")
    assert "secret-value" not in json.dumps(public)
    assert "encrypted_api_key" not in public


def test_missing_encryption_key_fails_closed(monkeypatch):
    from app.services.risk_review_system_service import encrypted_provider_payload

    monkeypatch.setattr("app.services.risk_review_system_service.settings.KT3_CONFIG_ENCRYPTION_KEY", "")

    with pytest.raises(ValueError) as exc_info:
        encrypted_provider_payload({"api_key": "sk-test"})

    assert "KT3_CONFIG_ENCRYPTION_KEY" in str(exc_info.value)


def test_env_retrieval_provider_public_view(monkeypatch):
    from app.services.risk_review_system_service import env_provider_public_view

    monkeypatch.setattr("app.services.risk_review_system_service.settings.KT3_RETRIEVAL_API_KEY", "exa-test-secret")
    monkeypatch.setattr("app.services.risk_review_system_service.settings.KT3_RETRIEVAL_BASE_URL", "https://api.exa.ai")
    monkeypatch.setattr("app.services.risk_review_system_service.settings.KT3_RETRIEVAL_SEARCH_PATH", "/search")
    monkeypatch.setattr("app.services.risk_review_system_service.settings.KT3_RETRIEVAL_PROVIDER_NAME", "Exa")
    monkeypatch.setattr("app.services.risk_review_system_service.settings.KT3_RETRIEVAL_ADAPTER", "exa")

    public = env_provider_public_view("retrieval")

    assert public["provider_type"] == "retrieval"
    assert public["is_active"] is True
    assert public["api_key_status"] == "configured"
    assert public["metadata"]["adapter"] == "exa"


def test_gate_dataset_payload_normalizes_cases_and_fingerprint():
    from app.services.risk_review_system_service import normalize_gate_dataset_upload

    dataset = {
        "metadata": {
            "dataset_id": "gate-smoke",
            "version": "v1",
            "source": "unit",
            "label_policy": "offline",
            "control_set_notes": "smoke",
        },
        "post_cases": [
            {
                "case_id": "case-post-1",
                "split": "validation",
                "posts": [{"post_id": "p1", "media_urls": ["G:/media/a.jpg"]}],
                "gold": {"p1": {"harm_label": "non_harmful"}},
            }
        ],
        "user_gold": {"u1": {"split": "held_out", "harmful": False}},
        "community_gold": {"c1": {"collective_harm": True}},
        "thresholds": {"post": {"harm_label_accuracy": 0.8}},
    }

    normalized = normalize_gate_dataset_upload(dataset, uploaded_by=42)

    assert normalized["dataset"]["dataset_id"] == "gate-smoke"
    assert len(normalized["dataset"]["manifest_fingerprint"]) == 64
    assert normalized["summary"]["case_count"] == 3
    assert normalized["summary"]["gold_label_count"] == 3
    assert normalized["summary"]["split_counts"]["validation"] == 1
    assert normalized["summary"]["split_counts"]["held_out"] == 1
    assert normalized["cases"][0]["media_refs"] == ["G:/media/a.jpg"]
    assert normalized["cases"][0]["media_hashes"][0]["uri"] == "G:/media/a.jpg"


def test_persist_agent_review_rows_preserves_natural_language_primary_output():
    from app.services.risk_review_system_service import normalize_agent_review_result

    review_result = {
        "audit": {"run_id": "run-1", "input_hash": "hash-1"},
        "agent_reports": [
            {
                "review_id": "review-1",
                "agent_name": "PostHarmAgent",
                "report_role": "expert_initial",
                "status": "completed",
                "model": "gpt-test",
                "analysis_report": {"text": "这是一段自然语言研判报告。"},
                "system_audit_sidecar": {
                    "evidence_refs": [{"doc_id": "post:p1", "text": "evidence"}],
                    "retrieval_queries": ["claim evidence"],
                    "uncertainties": ["cross_view_conflict"],
                    "suggested_actions": ["human_review_required"],
                    "confidence": 0.66,
                    "debate_trace_refs": ["debate:1"],
                },
            }
        ],
    }

    rows = normalize_agent_review_result(
        report_id="risk-1",
        case_id="case-1",
        result=review_result,
        created_by=42,
    )

    assert rows["run"]["run_id"] == "run-1"
    assert rows["reports"][0]["analysis_text"] == "这是一段自然语言研判报告。"
    assert rows["reports"][0]["analysis_text"] != json.dumps(rows["reports"][0], ensure_ascii=False)
    assert rows["evidence_refs"][0]["doc_id"] == "post:p1"
    assert rows["queries"][0]["query"] == "claim evidence"
    assert rows["uncertainties"][0]["uncertainty"] == "cross_view_conflict"
    assert rows["actions"][0]["suggested_action"] == "human_review_required"
    assert rows["debate_traces"][0]["trace_ref"] == "debate:1"


def test_backfill_report_json_is_idempotent():
    from app.services.risk_review_system_service import extract_kt3_backfill_records

    report_json = {
        "agent_reviews": [
            {
                "review_id": "review-1",
                "run_id": "run-1",
                "agent_name": "PostHarmAgent",
                "status": "completed",
                "analysis_report": {"text": "旧 JSON 报告"},
                "system_audit_sidecar": {"evidence_refs": [{"doc_id": "d1"}]},
            },
            {
                "review_id": "review-1",
                "run_id": "run-1",
                "agent_name": "PostHarmAgent",
                "status": "completed",
                "analysis_report": {"text": "重复报告"},
            },
        ],
        "agent_feedback": [
            {
                "feedback_id": "feedback-1",
                "run_id": "run-1",
                "case_id": "case-1",
                "corrected_label": "harmful",
                "error_types": ["false_negative"],
            },
            {
                "feedback_id": "feedback-1",
                "run_id": "run-1",
                "corrected_label": "harmful",
            },
        ],
    }

    records = extract_kt3_backfill_records("risk-1", report_json, created_by=7)

    assert records["summary"]["agent_reviews_seen"] == 2
    assert records["summary"]["agent_reports_extracted"] == 1
    assert records["summary"]["feedback_seen"] == 2
    assert records["summary"]["feedback_extracted"] == 1
    assert records["agent_reports"][0]["analysis_text"] == "旧 JSON 报告"
    assert records["feedback"][0]["error_types"] == ["false_negative"]


def test_run_agent_review_api_returns_async_job(monkeypatch):
    from app.api.v1 import risk as risk_api

    calls = {}
    committed = {"value": False}

    async def fake_create_job(**kwargs):
        calls.update(kwargs)
        return {"job_id": 123, "status": "pending", "poll_url": "/api/v1/risk/kt3/jobs/123"}

    class FakeDB:
        async def commit(self):
            committed["value"] = True

    monkeypatch.setattr(risk_api.risk_service, "create_kt3_agent_review_job", fake_create_job)

    response = __import__("asyncio").run(
        risk_api.run_kt3_agent_review(
            request=risk_api.KT3AgentReviewRunRequest(
                report_id="risk-1",
                selected_post_ids=["p1"],
                agent_names=["PostHarmAgent"],
                enable_active_retrieval=True,
            ),
            current_user=type("User", (), {"id": 42, "role": "analyst"})(),
            db=FakeDB(),
        )
    )

    assert response["data"] == {"job_id": 123, "status": "pending", "poll_url": "/api/v1/risk/kt3/jobs/123"}
    assert committed["value"] is True
    assert calls["job_type"] == "agent_review"
    assert calls["payload"]["report_id"] == "risk-1"
    assert calls["payload"]["selected_post_ids"] == ["p1"]
    assert calls["user_id"] == 42


def test_exa_retrieval_adapter_maps_request_and_response(monkeypatch):
    from app.tasks.risk_review_tasks import _build_http_retrieval_provider
    import asyncio

    captured = {}

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "results": [
                    {
                        "id": "exa-1",
                        "title": "Exa result",
                        "url": "https://example.com/doc",
                        "text": "Full text",
                        "highlights": ["Highlight A", "Highlight B"],
                        "score": 0.91,
                    }
                ]
            }

    class FakeAsyncClient:
        def __init__(self, timeout):
            captured["timeout"] = timeout

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def post(self, url, headers, json):
            captured["url"] = url
            captured["headers"] = headers
            captured["json"] = json
            return FakeResponse()

    monkeypatch.setattr("app.tasks.risk_review_tasks.httpx.AsyncClient", FakeAsyncClient)
    provider = _build_http_retrieval_provider(
        base_url="https://api.exa.ai",
        api_key="exa-key",
        search_path="/search",
        timeout_seconds=12.0,
        provider_name="Exa",
        adapter="exa",
    )
    result = asyncio.run(
        provider(
            query="claim verification",
            context={
                "input_refs": {"report_id": "r1", "post_ids": ["p1"], "tree_ids": []},
                "selected_posts": [{"post_id": "p1", "excerpt": "post text", "primary_claim": {"claim_text": "claim"}}],
            },
            top_k=2,
        )
    )

    assert captured["url"] == "https://api.exa.ai/search"
    assert captured["headers"]["x-api-key"] == "exa-key"
    assert captured["json"]["query"] == "claim verification"
    assert captured["json"]["numResults"] == 2
    assert captured["json"]["contents"]["text"] is True
    assert result[0]["title"] == "Exa result"
    assert result[0]["snippet"].startswith("Highlight A")
