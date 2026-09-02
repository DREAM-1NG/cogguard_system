"""Celery tasks for periodic event-scoped propagation monitoring."""

from __future__ import annotations

import asyncio

from app.celery_app import celery_app
from app.db.mysql import async_session_factory
from app.services.propagation_monitoring_service import run_due_monitor_profiles


def _run_async(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


async def _run_due_profiles() -> list[dict]:
    async with async_session_factory() as db:
        result = await run_due_monitor_profiles(db)
        await db.commit()
        return result


@celery_app.task(name="propagation.monitor_due_profiles")
def execute_due_propagation_monitor_profiles():
    """Evaluate enabled monitoring profiles whose interval has elapsed."""
    return _run_async(_run_due_profiles())


__all__ = ["execute_due_propagation_monitor_profiles"]
