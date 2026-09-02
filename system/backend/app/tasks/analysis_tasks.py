"""Celery tasks for internal analysis teacher review jobs."""

from __future__ import annotations

from typing import Any

from app.celery_app import celery_app
from app.core.analysis.runtime import finalize_teacher_review_job, mark_teacher_review_failed
from app.tasks.async_runtime import run_async


@celery_app.task(
    name="analysis.teacher_review",
    bind=True,
    acks_late=True,
    reject_on_worker_lost=True,
    max_retries=3,
)
def execute_analysis_teacher_review(self, job_id: str, case: dict[str, Any]):
    try:
        return run_async(finalize_teacher_review_job(job_id, case))
    except Exception as exc:
        if self.request.retries < self.max_retries:
            raise self.retry(exc=exc, countdown=min(2 ** self.request.retries, 60)) from exc
        return run_async(
            mark_teacher_review_failed(
                job_id,
                case,
                task_state="execution_failed",
                dispatch_backend="celery",
                error_type=type(exc).__name__,
            )
        )
