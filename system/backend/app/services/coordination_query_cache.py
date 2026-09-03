"""Short-lived, defensive cache for Coordination query projections."""

from __future__ import annotations

import asyncio
import copy
import time
from collections.abc import Awaitable, Callable, Hashable
from typing import Any


COORDINATION_QUERY_CACHE_TTL_SECONDS = 300
_CACHE: dict[tuple[Hashable, ...], tuple[float, Any]] = {}
_IN_FLIGHT: dict[tuple[Hashable, ...], asyncio.Task] = {}


def clear_coordination_query_cache() -> None:
    _CACHE.clear()
    _IN_FLIGHT.clear()


async def cached_coordination_query(
    key: tuple[Hashable, ...],
    loader: Callable[[], Awaitable[Any]],
) -> Any:
    item = _CACHE.get(key)
    if item is not None:
        created_at, payload = item
        if time.monotonic() - created_at < COORDINATION_QUERY_CACHE_TTL_SECONDS:
            return copy.deepcopy(payload)
        _CACHE.pop(key, None)

    task = _IN_FLIGHT.get(key)
    if task is None or task.done():
        async def compute() -> Any:
            payload = await loader()
            _CACHE[key] = (time.monotonic(), copy.deepcopy(payload))
            return payload

        task = asyncio.create_task(compute())
        _IN_FLIGHT[key] = task
    try:
        return copy.deepcopy(await task)
    finally:
        if task.done():
            _IN_FLIGHT.pop(key, None)


__all__ = [
    "COORDINATION_QUERY_CACHE_TTL_SECONDS",
    "cached_coordination_query",
    "clear_coordination_query_cache",
]
