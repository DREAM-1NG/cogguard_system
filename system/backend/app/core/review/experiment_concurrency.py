"""Bounded asynchronous execution and telemetry for offline Review experiments.

The MARO rule trajectory remains sequential. This module only schedules
independent I/O-bound calls within one completed protocol phase and records
non-secret provider reliability metrics for experiment audit.
"""

from __future__ import annotations

import asyncio
import re
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from time import perf_counter
from typing import Any, TypeVar


__all__ = ["ExperimentConcurrency", "run_ordered_bounded"]


T = TypeVar("T")
R = TypeVar("R")
_RETRYABLE_STATUS_CODES = {408, 409, 429, 500, 502, 503, 504}


async def run_ordered_bounded(
    items: list[T],
    worker: Callable[[T], Awaitable[R]],
    *,
    concurrency: int,
) -> list[R]:
    """Run independent work with a bound while preserving input order."""

    if concurrency < 1:
        raise ValueError("concurrency must be >= 1")
    semaphore = asyncio.Semaphore(concurrency)

    async def run_one(item: T) -> R:
        async with semaphore:
            return await worker(item)

    return list(await asyncio.gather(*(run_one(item) for item in items)))


@dataclass
class _ServiceMetrics:
    concurrency_limit: int
    logical_calls: int = 0
    attempt_count: int = 0
    completed_calls: int = 0
    failed_calls: int = 0
    retry_count: int = 0
    rate_limit_event_count: int = 0
    total_latency_seconds: float = 0.0
    in_flight: int = 0
    max_in_flight: int = 0

    def as_dict(self) -> dict[str, Any]:
        completed = max(1, self.completed_calls)
        logical = max(1, self.logical_calls)
        return {
            "concurrency_limit": self.concurrency_limit,
            "logical_calls": self.logical_calls,
            "attempt_count": self.attempt_count,
            "completed_calls": self.completed_calls,
            "failed_calls": self.failed_calls,
            "retry_count": self.retry_count,
            "rate_limit_event_count": self.rate_limit_event_count,
            "rate_limit_ratio": round(self.rate_limit_event_count / logical, 6),
            "failure_ratio": round(self.failed_calls / logical, 6),
            "mean_completed_latency_seconds": round(self.total_latency_seconds / completed, 6),
            "max_in_flight": self.max_in_flight,
        }


class ExperimentConcurrency:
    """Share bounded DeepSeek and retrieval execution across one experiment."""

    def __init__(
        self,
        *,
        llm_concurrency: int,
        retrieval_concurrency: int,
        retry_backoff_seconds: float = 1.0,
    ) -> None:
        if llm_concurrency < 1:
            raise ValueError("llm_concurrency must be >= 1")
        if retrieval_concurrency < 1:
            raise ValueError("retrieval_concurrency must be >= 1")
        self._semaphores = {
            "deepseek": asyncio.Semaphore(llm_concurrency),
            "exa": asyncio.Semaphore(retrieval_concurrency),
        }
        self._metrics = {
            "deepseek": _ServiceMetrics(concurrency_limit=llm_concurrency),
            "exa": _ServiceMetrics(concurrency_limit=retrieval_concurrency),
        }
        self._retry_backoff_seconds = max(0.0, float(retry_backoff_seconds))

    async def invoke(
        self,
        *,
        service: str,
        operation: Callable[..., Awaitable[R]],
        max_retries: int = 0,
        **kwargs: Any,
    ) -> R:
        """Invoke one provider operation under its bound and collect telemetry."""

        if service not in self._semaphores:
            raise ValueError(f"unsupported experiment service: {service}")
        if max_retries < 0:
            raise ValueError("max_retries must be >= 0")
        metrics = self._metrics[service]
        metrics.logical_calls += 1
        for outer_attempt in range(max_retries + 1):
            started = perf_counter()
            error: Exception | None = None
            result: R | None = None
            async with self._semaphores[service]:
                metrics.in_flight += 1
                metrics.max_in_flight = max(metrics.max_in_flight, metrics.in_flight)
                try:
                    result = await operation(**kwargs)
                except Exception as exc:  # Provider details are redacted by the adapter.
                    error = exc
                finally:
                    metrics.in_flight -= 1
            latency = perf_counter() - started
            provider_telemetry = _provider_telemetry(operation)
            self._record_attempt(metrics, latency, provider_telemetry, error)
            if error is None:
                metrics.completed_calls += 1
                return result  # type: ignore[return-value]
            if outer_attempt >= max_retries or not _retryable(error, provider_telemetry):
                metrics.failed_calls += 1
                raise error
            metrics.retry_count += 1
            await asyncio.sleep(self._retry_backoff_seconds * (outer_attempt + 1))
        raise RuntimeError("unreachable experiment retry state")

    def snapshot(self) -> dict[str, dict[str, Any]]:
        """Return JSON-safe, non-secret provider metrics."""

        return {name: metrics.as_dict() for name, metrics in self._metrics.items()}

    @staticmethod
    def _record_attempt(
        metrics: _ServiceMetrics,
        latency: float,
        provider_telemetry: dict[str, Any],
        error: Exception | None,
    ) -> None:
        reported_attempts = _non_negative_int(provider_telemetry.get("attempt_count"), default=1)
        reported_retries = _non_negative_int(provider_telemetry.get("retry_count"), default=0)
        reported_rate_limits = _non_negative_int(provider_telemetry.get("rate_limit_retry_count"), default=0)
        status = _status_code(error, provider_telemetry)
        metrics.attempt_count += reported_attempts
        metrics.retry_count += reported_retries
        metrics.rate_limit_event_count += reported_rate_limits or int(status == 429)
        metrics.total_latency_seconds += latency


def _provider_telemetry(operation: Any) -> dict[str, Any]:
    value = getattr(operation, "last_call_telemetry", None)
    return dict(value) if isinstance(value, dict) else {}


def _retryable(error: Exception, telemetry: dict[str, Any]) -> bool:
    return _status_code(error, telemetry) in _RETRYABLE_STATUS_CODES


def _status_code(error: Exception | None, telemetry: dict[str, Any]) -> int | None:
    try:
        status = telemetry.get("http_status")
        if status is not None:
            return int(status)
    except (TypeError, ValueError):
        pass
    response = getattr(error, "response", None)
    status = getattr(response, "status_code", None)
    if status is not None:
        try:
            return int(status)
        except (TypeError, ValueError):
            pass
    match = re.search(r"\b([1-5]\d\d)\b", str(error or ""))
    return int(match.group(1)) if match else None


def _non_negative_int(value: Any, *, default: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return parsed if parsed >= 0 else default
