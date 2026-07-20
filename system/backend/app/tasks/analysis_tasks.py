"""Celery tasks for internal analysis teacher review jobs."""

from __future__ import annotations

import asyncio
from typing import Any

from app.celery_app import celery_app
from app.core.analysis.runtime import finalize_teacher_review_job


def _run_async(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@celery_app.task(name="analysis.teacher_review", bind=True)
def execute_analysis_teacher_review(self, job_id: str, case: dict[str, Any]):
    return _run_async(finalize_teacher_review_job(job_id, case))

