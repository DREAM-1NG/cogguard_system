"""Versioned cache for immutable analysis query projections.

The cache is deliberately below the HTTP layer.  A product endpoint can keep
its existing response contract while avoiding repeated graph construction,
artifact parsing, and evidence projection.  Every caller supplies a versioned
key; freshness is therefore controlled by the source fingerprint or run
identity rather than by a guessed time-to-live.
"""

from __future__ import annotations

import asyncio
import copy
import hashlib
import json
import time
from collections import OrderedDict
from collections.abc import Awaitable, Callable, Mapping
from typing import Any

from app.config import settings
from app.db.redis import get_redis


_local_cache: OrderedDict[str, dict[str, Any]] = OrderedDict()
_single_flight_locks: dict[str, asyncio.Lock] = {}
_single_flight_refs: dict[str, int] = {}
_redis_disabled_until = 0.0


def build_query_cache_key(namespace: str, *parts: object) -> str:
    """Build a stable, opaque key from a projection version and identities."""

    subject = {
        "namespace": str(namespace),
        "parts": [str(part) for part in parts],
        "schema": 1,
    }
    digest = hashlib.sha256(
        json.dumps(subject, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return f"{settings.ANALYSIS_RESULT_CACHE_NAMESPACE}:{namespace}:{digest}"


def _copy_value(value: Mapping[str, Any]) -> dict[str, Any]:
    return copy.deepcopy(dict(value))


def _remember_local(key: str, value: Mapping[str, Any]) -> None:
    _local_cache[key] = _copy_value(value)
    _local_cache.move_to_end(key)
    limit = max(1, int(settings.ANALYSIS_RESULT_CACHE_MAX_ENTRIES))
    while len(_local_cache) > limit:
        _local_cache.popitem(last=False)


async def _redis_get(key: str) -> dict[str, Any] | None:
    global _redis_disabled_until
    if not settings.ANALYSIS_RESULT_CACHE_REDIS_ENABLED:
        return None
    if time.monotonic() < _redis_disabled_until:
        return None
    try:
        raw = await asyncio.wait_for(get_redis().get(key), timeout=0.75)
        if not raw:
            return None
        value = json.loads(raw)
        if not isinstance(value, dict):
            return None
        return value
    except Exception:
        # Redis is an acceleration layer, not a data dependency.  One failed
        # connection must not add a network timeout to every API request.
        _redis_disabled_until = time.monotonic() + 30.0
        return None


async def _redis_set(key: str, value: Mapping[str, Any]) -> None:
    global _redis_disabled_until
    if not settings.ANALYSIS_RESULT_CACHE_REDIS_ENABLED:
        return
    if time.monotonic() < _redis_disabled_until:
        return
    try:
        # Builders must return the same JSON-compatible shapes as the public
        # response. Do not coerce unsupported values to strings in Redis and
        # silently change numeric/date semantics on a cross-process hit.
        payload = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
        ttl_seconds = max(0, int(settings.ANALYSIS_RESULT_CACHE_TTL_SECONDS))
        if ttl_seconds:
            await asyncio.wait_for(
                get_redis().set(key, payload, ex=ttl_seconds),
                timeout=0.75,
            )
        else:
            await asyncio.wait_for(get_redis().set(key, payload), timeout=0.75)
    except (TypeError, ValueError):
        return
    except Exception:
        _redis_disabled_until = time.monotonic() + 30.0


async def get_query_result(key: str) -> dict[str, Any] | None:
    """Read a projection from process memory or shared Redis."""

    if not settings.ANALYSIS_RESULT_CACHE_ENABLED:
        return None
    value = _local_cache.get(key)
    if value is not None:
        _local_cache.move_to_end(key)
        return _copy_value(value)

    value = await _redis_get(key)
    if value is not None:
        _remember_local(key, value)
        return _copy_value(value)
    return None


async def put_query_result(key: str, value: Mapping[str, Any]) -> None:
    """Store a JSON-compatible projection in both cache layers."""

    if not settings.ANALYSIS_RESULT_CACHE_ENABLED:
        return
    normalized = _copy_value(value)
    _remember_local(key, normalized)
    await _redis_set(key, normalized)


async def get_or_build_query_result(
    key: str,
    builder: Callable[[], Awaitable[Mapping[str, Any]]],
) -> dict[str, Any]:
    """Return a cached projection and single-flight concurrent cache misses."""

    if not settings.ANALYSIS_RESULT_CACHE_ENABLED:
        return _copy_value(await builder())

    cached = await get_query_result(key)
    if cached is not None:
        return cached

    lock = _single_flight_locks.get(key)
    if lock is None:
        lock = asyncio.Lock()
        _single_flight_locks[key] = lock
    _single_flight_refs[key] = _single_flight_refs.get(key, 0) + 1
    try:
        async with lock:
            cached = await get_query_result(key)
            if cached is not None:
                return cached
            built = _copy_value(await builder())
            await put_query_result(key, built)
            return _copy_value(built)
    finally:
        references = _single_flight_refs.get(key, 1) - 1
        if references <= 0:
            _single_flight_refs.pop(key, None)
            _single_flight_locks.pop(key, None)
        else:
            _single_flight_refs[key] = references


def clear_local_query_result_cache() -> None:
    """Clear process-local entries for tests and controlled local restarts."""

    _local_cache.clear()
    _single_flight_refs.clear()
    _single_flight_locks.clear()


__all__ = [
    "build_query_cache_key",
    "clear_local_query_result_cache",
    "get_or_build_query_result",
    "get_query_result",
    "put_query_result",
]
