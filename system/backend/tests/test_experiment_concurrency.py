from __future__ import annotations

import asyncio

import pytest

from app.core.review.experiment_concurrency import ExperimentConcurrency, run_ordered_bounded


def test_ordered_bounded_execution_preserves_input_order_and_limit():
    active = 0
    peak = 0

    async def worker(value: int) -> int:
        nonlocal active, peak
        active += 1
        peak = max(peak, active)
        await asyncio.sleep(0.01)
        active -= 1
        return value * 10

    result = asyncio.run(run_ordered_bounded([1, 2, 3, 4, 5], worker, concurrency=2))

    assert result == [10, 20, 30, 40, 50]
    assert peak == 2


def test_experiment_concurrency_records_provider_retries_and_rate_limits():
    class Provider:
        last_call_telemetry = {
            "attempt_count": 3,
            "retry_count": 2,
            "rate_limit_retry_count": 1,
            "http_status": 200,
        }

        async def __call__(self, **_: object) -> str:
            return "ok"

    gate = ExperimentConcurrency(llm_concurrency=2, retrieval_concurrency=1)
    result = asyncio.run(
        gate.invoke(
            service="deepseek",
            operation=Provider(),
            agent_name="test",
        )
    )

    assert result == "ok"
    record = gate.snapshot()["deepseek"]
    assert record["logical_calls"] == 1
    assert record["attempt_count"] == 3
    assert record["retry_count"] == 2
    assert record["rate_limit_event_count"] == 1
    assert record["rate_limit_ratio"] == 1.0


def test_experiment_concurrency_retries_retryable_retrieval_failure():
    attempts = 0

    async def transient_retriever(**_: object) -> list[dict[str, str]]:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise RuntimeError("HTTP 429")
        return [{"url": "https://example.test", "text": "evidence"}]

    gate = ExperimentConcurrency(llm_concurrency=1, retrieval_concurrency=1, retry_backoff_seconds=0.0)
    result = asyncio.run(
        gate.invoke(
            service="exa",
            operation=transient_retriever,
            max_retries=1,
            query="query",
            context={},
            top_k=1,
        )
    )

    assert result[0]["url"] == "https://example.test"
    assert attempts == 2
    record = gate.snapshot()["exa"]
    assert record["logical_calls"] == 1
    assert record["attempt_count"] == 2
    assert record["retry_count"] == 1
    assert record["rate_limit_event_count"] == 1


def test_experiment_concurrency_rejects_invalid_limits():
    with pytest.raises(ValueError, match="llm_concurrency"):
        ExperimentConcurrency(llm_concurrency=0, retrieval_concurrency=1)
    with pytest.raises(ValueError, match="concurrency"):
        asyncio.run(run_ordered_bounded([1], lambda value: value, concurrency=0))
