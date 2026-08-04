from __future__ import annotations

import asyncio

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


def test_active_retrieval_bounds_concurrency_preserves_order_and_isolates_failures():
    active_calls = 0
    maximum_active_calls = 0

    async def external_provider(*, query: str, context: dict[str, object], top_k: int) -> list[dict[str, object]]:
        nonlocal active_calls, maximum_active_calls
        active_calls += 1
        maximum_active_calls = max(maximum_active_calls, active_calls)
        try:
            await asyncio.sleep(0.03)
            if query == "query-2":
                raise RuntimeError("provider unavailable")
            return [{"doc_id": query, "text": f"evidence for {query}", "score": 0.8}]
        finally:
            active_calls -= 1

    result = asyncio.run(
        retrieve_active_evidence(
            context={
                "review_queue": {
                    "retrieval_tasks": [{"query": f"query-{index}"} for index in range(5)]
                }
            },
            external_provider=external_provider,
            external_enabled=True,
        )
    )

    assert maximum_active_calls == 4
    assert [item["query"] for item in result["external_results"]] == [
        "query-0",
        "query-1",
        "query-3",
        "query-4",
    ]
    assert result["audit"]["external_failures"] == [
        {
            "query": "query-2",
            "error_type": "RuntimeError",
            "message": "provider unavailable",
        }
    ]
