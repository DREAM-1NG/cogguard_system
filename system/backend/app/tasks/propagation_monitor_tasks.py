"""Celery tasks for periodic event-scoped propagation monitoring."""

from __future__ import annotations

import asyncio

from app.celery_app import celery_app
from app.core.propagation_monitoring import build_default_propagation_monitoring
from app.db.mysql import async_session_factory


_PROPAGATION_MONITORING = build_default_propagation_monitoring()


def _run_async(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


async def _run_due_profiles() -> list[dict]:
    async with async_session_factory() as db:
        result = await _PROPAGATION_MONITORING.run_due_monitor_profiles(db)
        await db.commit()
        return result


@celery_app.task(name="propagation.monitor_due_profiles")
def execute_due_propagation_monitor_profiles():
    """Evaluate enabled monitoring profiles whose interval has elapsed."""
    return _run_async(_run_due_profiles())


__all__ = ["execute_due_propagation_monitor_profiles"]
