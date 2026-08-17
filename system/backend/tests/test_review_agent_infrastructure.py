from __future__ import annotations

import asyncio
import json

import httpx

from app.core.review import agent_provider
from app.core.review.active_retrieval import retrieve_active_evidence
from app.core.review.agent_provider import OpenAICompatibleAgentProvider
from app.core.review.agent_provider import OpenAICompatibleConfig


def _agent_config() -> OpenAICompatibleConfig:
    return OpenAICompatibleConfig(
        api_key="test-key",
        base_url="https://provider.example/v1",
        model="test-model",
    )


def _mock_provider_client() -> tuple[httpx.AsyncClient, list[httpx.Request]]:
    requests: list[httpx.Request] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json={"choices": [{"message": {"content": "review complete"}}]})

    return httpx.AsyncClient(transport=httpx.MockTransport(handler)), requests


def test_openai_provider_reuses_owned_client_and_closes_it(monkeypatch):
    client, requests = _mock_provider_client()
    created_clients: list[httpx.AsyncClient] = []

    def create_client(**kwargs: object) -> httpx.AsyncClient:
        assert kwargs["timeout"] == 180.0
        created_clients.append(client)
        return client

    monkeypatch.setattr(agent_provider.httpx, "AsyncClient", create_client)
    monkeypatch.setattr(agent_provider.llm_cache, "load_cached_response", lambda cache_key: None)
    monkeypatch.setattr(agent_provider.llm_cache, "record_response", lambda *args, **kwargs: None)
    provider = OpenAICompatibleAgentProvider(_agent_config())

    async def exercise() -> None:
        for _ in range(2):
            assert await provider(
                agent_name="ClaimEvidenceAgent",
                system_prompt="system",
                user_prompt="user",
                input_bundle={},
                model="",
            ) == "review complete"
        await provider.aclose()

    asyncio.run(exercise())

    assert created_clients == [client]
    assert len(requests) == 2
    assert client.is_closed


def test_openai_provider_does_not_close_injected_client(monkeypatch):
    client, requests = _mock_provider_client()
    monkeypatch.setattr(agent_provider.llm_cache, "load_cached_response", lambda cache_key: None)
    monkeypatch.setattr(agent_provider.llm_cache, "record_response", lambda *args, **kwargs: None)
    provider = OpenAICompatibleAgentProvider(_agent_config(), client=client)

    async def exercise() -> None:
        assert await provider(
            agent_name="ClaimEvidenceAgent",
            system_prompt="system",
            user_prompt="user",
            input_bundle={},
            model="",
        ) == "review complete"
        await provider.aclose()

    asyncio.run(exercise())

    assert len(requests) == 1
    assert not client.is_closed
    asyncio.run(client.aclose())


def test_openai_provider_cache_off_records_usage_and_never_reads_cache(monkeypatch):
    requests: list[httpx.Request] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": "live response"}}],
                "usage": {"prompt_tokens": 11, "completion_tokens": 7, "total_tokens": 18},
            },
        )

    async def exercise() -> dict[str, object]:
        client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        config = OpenAICompatibleConfig(
            api_key="test-key",
            base_url="https://provider.example/v1",
            model="test-model",
            cache_enabled=False,
        )
        provider = OpenAICompatibleAgentProvider(config, client=client)
        monkeypatch.setattr(
            agent_provider.llm_cache,
            "load_cached_response",
            lambda key: (_ for _ in ()).throw(AssertionError("cache should be bypassed")),
        )
        assert await provider(
            agent_name="ClaimEvidenceAgent",
            system_prompt="system",
            user_prompt="user",
            input_bundle={},
            model="",
        ) == "live response"
        telemetry = dict(provider.last_call_telemetry)
        await client.aclose()
        return telemetry

    telemetry = asyncio.run(exercise())
    assert len(requests) == 1
    assert telemetry["cache_status"] == "disabled"
    assert telemetry["cache_hit"] is False
    assert telemetry["retry_count"] == 0
    assert telemetry["http_status"] == 200
    assert telemetry["usage_available"] is True
    assert telemetry["total_tokens"] == 18


def test_openai_provider_sends_configured_temperature():
    client, requests = _mock_provider_client()
    config = OpenAICompatibleConfig(
        api_key="test-key",
        base_url="https://provider.example/v1",
        model="test-model",
        temperature=1.0,
        cache_enabled=False,
    )
    provider = OpenAICompatibleAgentProvider(config, client=client)

    async def exercise() -> None:
        await provider(
            agent_name="MARODecisionRuleOptimizationAgent",
            system_prompt="system",
            user_prompt="user",
            input_bundle={},
            model="",
        )
        await client.aclose()

    asyncio.run(exercise())

    assert json.loads(requests[0].content)["temperature"] == 1.0


def test_active_retrieval_records_provider_failure_without_factual_relation():
    active_calls = 0
    maximum_active_calls = 0

    async def external_provider(*, query: str, context: dict[str, object], top_k: int) -> list[dict[str, object]]:
        nonlocal active_calls, maximum_active_calls
        active_calls += 1
        maximum_active_calls = max(maximum_active_calls, active_calls)
        try:
            await asyncio.sleep(0.03)
            if query.startswith("query-2"):
                raise RuntimeError("provider unavailable")
            return [{"doc_id": query, "text": f"evidence for {query}", "score": 0.8}]
        finally:
            active_calls -= 1

    result = asyncio.run(
        retrieve_active_evidence(
            context={
                "evidence_bundle": {
                    "claim": "query-2",
                    "claim_assessment": "checkable",
                }
            },
            external_provider=external_provider,
            external_enabled=True,
        )
    )

    assert maximum_active_calls == 2
    assert result["external_results"] == []
    assert result["audit"]["failures"] == [
        {
            "query": "query-2",
            "error_type": "RuntimeError",
            "message": "provider unavailable",
        },
        {
            "query": "query-2 evidence verification",
            "error_type": "RuntimeError",
            "message": "provider unavailable",
        },
    ]
    assert result["evidence_bundle"]["retrieval_status"] == "provider_failed"
    assert result["evidence_bundle"]["relation"] == "not_applicable"


def test_active_retrieval_does_not_call_a_provider_before_claim_assessment():
    calls = {"count": 0}

    async def external_provider(*, query: str, context: dict[str, object], top_k: int) -> list[dict[str, object]]:
        calls["count"] += 1
        return []

    result = asyncio.run(
        retrieve_active_evidence(
            context={"selected_posts": [{"content": "An unassessed post body."}]},
            external_provider=external_provider,
            external_enabled=True,
        )
    )

    assert calls["count"] == 0
    assert result["evidence_bundle"]["claim_assessment"] == "not_assessed"
    assert result["evidence_bundle"]["retrieval_status"] == "skipped_non_eligible_claim"
    assert result["evidence_bundle"]["relation"] == "not_applicable"
