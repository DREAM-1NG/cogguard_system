"""Celery execution for durable system-owned account model evaluation jobs."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import OperationalError

from app.celery_app import celery_app
from app.db.mysql import async_session_factory
from app.models.account_labeling import AccountModelEvaluationJob
from app.services.account_model_evaluation_service import (
    finalize_account_model_evaluation_job,
    prepare_account_model_evaluation_job,
    run_prepared_account_model_evaluation,
)
from app.tasks.async_runtime import run_async

__all__ = ["enqueue_account_model_evaluation_job", "execute_account_model_evaluation_job"]


def enqueue_account_model_evaluation_job(job_id: str, *, task_id: str):
    """Publish the task id already persisted with the durable job."""

    return execute_account_model_evaluation_job.apply_async(
        args=[str(job_id)],
        queue="account_evaluation",
        task_id=str(task_id),
        retry=False,
    )


@celery_app.task(
    name="account_evaluation.execute",
    bind=True,
    acks_late=True,
    reject_on_worker_lost=True,
    max_retries=3,
)
def execute_account_model_evaluation_job(self, job_id: str):
    try:
        result = run_async(_execute_account_model_evaluation_job(str(job_id)))
    except OperationalError as error:
        retries = int(self.request.retries)
        if retries >= int(self.max_retries):
            run_async(_record_failed_job_transaction(str(job_id), error))
            raise
        return self.retry(exc=error, countdown=min(60, 2 ** max(0, retries)))
    if result.get("status") == "missing":
        raise self.retry(countdown=min(30, 2 ** max(0, int(self.request.retries))))
    return result


async def _execute_account_model_evaluation_job(job_id: str) -> dict[str, Any]:
    try:
        async with async_session_factory() as prepare_session:
            prepared = await prepare_account_model_evaluation_job(prepare_session, job_id)
            await prepare_session.commit()
        if isinstance(prepared, dict):
            return prepared

        prediction_audits = await run_prepared_account_model_evaluation(prepared)

        async with async_session_factory() as finalize_session:
            result = await finalize_account_model_evaluation_job(
                finalize_session,
                prepared,
                prediction_audits,
            )
            await finalize_session.commit()
            return result
    except OperationalError:
        # A deadlock/transient database failure is retried by the Celery boundary.
        raise
    except Exception as error:
        await _record_failed_job_transaction(job_id, error)
        raise


async def _record_failed_job_transaction(job_id: str, error: Exception) -> None:
    async with async_session_factory() as session:
        try:
            await _record_failed_job(session, job_id=job_id, error=error)
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def _record_failed_job(session, *, job_id: str, error: Exception) -> None:
    job = (
        await session.execute(
            select(AccountModelEvaluationJob)
            .where(AccountModelEvaluationJob.job_id == job_id)
            .with_for_update()
        )
    ).scalar_one_or_none()
    if job is None or job.status in {"completed", "cancelled"}:
        return
    job.status = "failed"
    job.error = f"{type(error).__name__}: {error}"
    job.finished_at = datetime.now(timezone.utc).replace(tzinfo=None)
    await session.flush()
