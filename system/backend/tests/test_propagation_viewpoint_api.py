from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest
from fastapi.exceptions import ResponseValidationError
from httpx import ASGITransport, AsyncClient

from app.api.v1 import propagation as propagation_api
from app.core.security import get_current_user
from app.main import app


def _valid_ready_claim_response_landscape(event_id: str, platform: str | None) -> dict:
    scoped_platform = platform or "weibo"
    official_ref = f"{scoped_platform}:post:p-official"
    response_ref = f"{scoped_platform}:post:p-responder-a"
    path_ref = {
        "path_id": "claim-1:0",
        "evidence_refs": [official_ref, response_ref],
        "nodes": ["official-1", "responder-a"],
        "score": 8.0,
    }
    return {
        "status": "ready",
        "event_id": event_id,
        "platform": platform,
        "blocking_reason": None,
        "claim_anchor": {
            "case_id": "case-1",
            "claim_id": "claim-1",
            "authority_source_id": "source-1",
            "text": "The primary authority claim.",
            "source_url": "https://authority.example/post",
            "account": "Official Desk",
            "published_at": "2026-08-15T00:00:00",
            "role": "primary",
            "source_review_status": "allowlisted",
            "source_tier": "government_official",
            "evidence_refs": ["case:case-1:claim:claim-1"],
        },
        "official_publications": [
            {
                "post_id": "p-official",
                "platform": scoped_platform,
                "author_id": "official-1",
                "author_name": "Official Desk",
                "content": "The primary authority claim.",
                "published_at": "2026-08-15T00:00:00+00:00",
                "source_url": "https://authority.example/post",
                "authority_binding": {
                    "source_id": "source-1",
                    "platform": scoped_platform,
                    "author_id": "official-1",
                },
                "verification_context": {"policy": "context_only_not_authority"},
                "engagement_percentile": 1.0,
                "evidence_refs": [official_ref],
                "semantic": None,
            }
        ],
        "influential_responses": [
            {
                "platform": scoped_platform,
                "author_id": "responder-a",
                "author_name": "Responder A",
                "rank_scope": "platform",
                "downstream_reach": 1,
                "path_contribution": 8.0,
                "path_count": 1,
                "engagement_percentile": 0.5,
                "first_seen_at": "2026-08-15T00:11:00+00:00",
                "evidence_refs": [response_ref],
                "path_refs": [path_ref],
                "rank": 1,
                "semantic": {
                    "evidence_item_count": 1,
                    "stance_distribution": {"support": 1},
                    "sentiment_distribution": {},
                    "dominant_stance": "support",
                },
                "stance": "support",
            }
        ],
        "timeline": [
            {
                "type": "official_publication",
                "at": "2026-08-15T00:00:00+00:00",
                "platform": scoped_platform,
                "author_id": "official-1",
                "post_id": "p-official",
                "evidence_refs": [official_ref],
            },
            {
                "type": "influential_response",
                "at": "2026-08-15T00:11:00+00:00",
                "platform": scoped_platform,
                "author_id": "responder-a",
                "rank": 1,
                "evidence_refs": [response_ref],
                "path_refs": [path_ref],
            },
        ],
        "coverage": {
            "case": {"status": "available", "case_id": "case-1"},
            "primary_claim": {"status": "available", "claim_id": "claim-1"},
            "authority_source": {
                "status": "available",
                "source_id": "source-1",
                "review_status": "allowlisted",
            },
            "official_account_binding": {"status": "available", "binding_count": 1},
            "observed_paths": {"status": "available", "path_count": 1},
            "semantic": {"status": "available", "path_overlay_count": 0},
            "evidence_refs": {
                "status": "available",
                "official_publication_count": 1,
                "response_count": 1,
            },
            "data_scope": {"posts": 2, "comments": 0},
        },
        "capability": {
            "name": "claim_response_landscape",
            "type": "system_projection",
            "boundary": "read_only_observed_evidence",
            "mutates_analysis_conclusions": False,
            "official_identity_policy": "allowlisted_authority_source_exact_platform_author_binding",
        },
        "data_scope": {"posts": 2, "comments": 0},
    }


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
        return _valid_ready_claim_response_landscape(event_id, platform)

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


def test_claim_response_landscape_api_preserves_path_semantic_overlay_and_unavailable_reach(monkeypatch):
    fake_db = SimpleNamespace(name="db")
    fake_mongo = SimpleNamespace(name="mongo")
    expected_overlay = {
        "sentiment": {"positive": 1},
        "keywords": [{"term": "dialogue", "count": 1}],
        "topics": [{"id": "topic-1", "label": "public response", "count": 1}],
        "entities": [{"text": "Beijing", "label": "LOC", "count": 1}],
        "stance": {"neutral": 1},
        "platforms": ["weibo"],
        "time_range": {
            "start": "2026-08-15T00:00:00+00:00",
            "end": "2026-08-15T00:11:00+00:00",
        },
        "evidence_refs": ["weibo:post:p-official", "weibo:post:p-responder-a"],
    }

    async def override_db():
        yield fake_db

    async def fake_build_claim_response_landscape(event_id, platform=None, **kwargs):
        result = _valid_ready_claim_response_landscape(event_id, platform)
        result["influential_responses"][0]["downstream_reach"] = None
        result["influential_responses"][0]["downstream_reach_status"] = "unavailable"
        result["influential_responses"][0]["downstream_reach_reason"] = (
            "direct_comment_thread_network_reach_not_computed"
        )
        result["influential_responses"][0]["path_refs"][0]["semantic_overlay"] = expected_overlay
        result["coverage"]["semantic"]["claim_response_path_overlay_count"] = 1
        return result

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
        response_row = response.json()["data"]["influential_responses"][0]
        assert response_row["downstream_reach"] is None
        assert response_row["downstream_reach_status"] == "unavailable"
        assert response_row["downstream_reach_reason"] == "direct_comment_thread_network_reach_not_computed"
        assert response_row["path_refs"][0]["semantic_overlay"] == expected_overlay
        assert response.json()["data"]["coverage"]["semantic"]["claim_response_path_overlay_count"] == 1

    try:
        asyncio.run(scenario())
    finally:
        app.dependency_overrides.pop(get_current_user, None)
        app.dependency_overrides.pop(propagation_api.get_db, None)
        app.dependency_overrides.pop(propagation_api.get_mongo_db, None)


def test_claim_response_landscape_rejects_ready_payload_without_complete_claim_anchor(monkeypatch):
    fake_db = SimpleNamespace(name="db")
    fake_mongo = SimpleNamespace(name="mongo")

    async def override_db():
        yield fake_db

    async def fake_build_claim_response_landscape(event_id, platform=None, **kwargs):
        result = _valid_ready_claim_response_landscape(event_id, platform)
        result["claim_anchor"] = {"claim_id": "claim-1"}
        return result

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
            with pytest.raises(ResponseValidationError):
                await client.get(
                    "/api/v1/propagation/claim-response-landscape?event_id=event-1&platform=weibo"
                )

    try:
        asyncio.run(scenario())
    finally:
        app.dependency_overrides.pop(get_current_user, None)
        app.dependency_overrides.pop(propagation_api.get_db, None)
        app.dependency_overrides.pop(propagation_api.get_mongo_db, None)


@pytest.mark.parametrize(
    "claim_anchor_field",
    [
        "case_id",
        "claim_id",
        "authority_source_id",
        "text",
        "source_url",
        "account",
        "role",
        "source_review_status",
    ],
)
def test_claim_response_landscape_rejects_whitespace_only_required_claim_anchor_field(
    monkeypatch, claim_anchor_field
):
    fake_db = SimpleNamespace(name="db")
    fake_mongo = SimpleNamespace(name="mongo")

    async def override_db():
        yield fake_db

    async def fake_build_claim_response_landscape(event_id, platform=None, **kwargs):
        result = _valid_ready_claim_response_landscape(event_id, platform)
        result["claim_anchor"][claim_anchor_field] = "   "
        return result

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
            with pytest.raises(ResponseValidationError):
                await client.get(
                    "/api/v1/propagation/claim-response-landscape?event_id=event-1&platform=weibo"
                )

    try:
        asyncio.run(scenario())
    finally:
        app.dependency_overrides.pop(get_current_user, None)
        app.dependency_overrides.pop(propagation_api.get_db, None)
        app.dependency_overrides.pop(propagation_api.get_mongo_db, None)


@pytest.mark.parametrize("invalid_ref", ["   ", "not-an-evidence-reference"])
def test_claim_response_landscape_rejects_blank_or_malformed_evidence_reference(monkeypatch, invalid_ref):
    fake_db = SimpleNamespace(name="db")
    fake_mongo = SimpleNamespace(name="mongo")

    async def override_db():
        yield fake_db

    async def fake_build_claim_response_landscape(event_id, platform=None, **kwargs):
        result = _valid_ready_claim_response_landscape(event_id, platform)
        result["official_publications"][0]["evidence_refs"] = [invalid_ref]
        return result

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
            with pytest.raises(ResponseValidationError):
                await client.get(
                    "/api/v1/propagation/claim-response-landscape?event_id=event-1&platform=weibo"
                )

    try:
        asyncio.run(scenario())
    finally:
        app.dependency_overrides.pop(get_current_user, None)
        app.dependency_overrides.pop(propagation_api.get_db, None)
        app.dependency_overrides.pop(propagation_api.get_mongo_db, None)
