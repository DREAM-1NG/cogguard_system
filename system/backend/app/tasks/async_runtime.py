"""Async runtime shared by synchronous worker tasks.

Celery invokes task functions synchronously. Reusing one event loop per worker
thread keeps loop-bound database pools valid across consecutive tasks.
"""

from __future__ import annotations

import asyncio
import threading
from collections.abc import Coroutine
from typing import Any, TypeVar

from app.db.mongodb import close_mongo
from app.db.mysql import close_mysql
from app.db.redis import close_redis
from app.utils.logger import logger


ResultT = TypeVar("ResultT")
_thread_runtime = threading.local()


def _event_loop() -> asyncio.AbstractEventLoop:
    loop = getattr(_thread_runtime, "event_loop", None)
    if loop is None or loop.is_closed():
        loop = asyncio.new_event_loop()
        _thread_runtime.event_loop = loop
    return loop


def run_async(coroutine: Coroutine[Any, Any, ResultT]) -> ResultT:
    """Run a coroutine on the persistent loop owned by the current thread."""
    loop = _event_loop()
    if loop.is_running():
        coroutine.close()
        raise RuntimeError("run_async cannot be called from its active worker event loop")
    return loop.run_until_complete(coroutine)


async def _close_connections() -> None:
    for name, closer in (
        ("MySQL", close_mysql),
        ("MongoDB", close_mongo),
        ("Redis", close_redis),
    ):
        try:
            await closer()
        except Exception:
            logger.exception("Failed to close {} worker connection", name)


def close_async_runtime() -> None:
    """Close loop-bound connections and the current thread's worker loop."""
    loop = getattr(_thread_runtime, "event_loop", None)
    if loop is None:
        return
    if loop.is_running():
        raise RuntimeError("Cannot close the async task runtime while it is running")
    try:
        if not loop.is_closed():
            loop.run_until_complete(_close_connections())
            loop.run_until_complete(loop.shutdown_asyncgens())
            loop.run_until_complete(loop.shutdown_default_executor())
    finally:
        if not loop.is_closed():
            loop.close()
        del _thread_runtime.event_loop


__all__ = ["close_async_runtime", "run_async"]
