"""Transactional dispatch outbox for system-owned account evaluations."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

from sqlalchemy import and_, or_, select

from app.config import settings
from app.db.mysql import async_session_factory
from app.models.account_labeling import AccountModelEvaluationJob
from app.utils.logger import logger

__all__ = [
    "acknowledge_account_model_evaluation_dispatch",
    "claim_account_model_evaluation_dispatches",
    "drain_account_model_evaluation_dispatch_outbox",
    "finalize_account_model_evaluation_dispatch_claim",
    "pending_account_model_evaluation_dispatches_statement",
    "run_account_model_evaluation_dispatch_outbox_publisher",
]


def pending_account_model_evaluation_dispatches_statement(
    *,
    limit: int,
    now: datetime | None = None,
):
    ready_at = now or _utc_now()
    return (
        select(AccountModelEvaluationJob)
        .where(
            or_(
                and_(
                    AccountModelEvaluationJob.dispatch_status == "pending",
                    AccountModelEvaluationJob.dispatch_available_at <= ready_at,
                ),
                and_(
                    AccountModelEvaluationJob.dispatch_status == "publishing",
                    AccountModelEvaluationJob.dispatch_lease_expires_at <= ready_at,
                ),
            )
        )
        .order_by(
            AccountModelEvaluationJob.dispatch_available_at.asc(),
            AccountModelEvaluationJob.id.asc(),
        )
        .limit(max(1, int(limit)))
        .with_for_update(skip_locked=True)
    )


async def claim_account_model_evaluation_dispatches(
    *,
    session_factory=async_session_factory,
    limit: int = 20,
    lease_seconds: float | None = None,
) -> list[dict[str, str]]:
    lease = (
        float(lease_seconds)
        if lease_seconds is not None
        else float(settings.ACCOUNT_TRAINING_OUTBOX_CLAIM_LEASE_SECONDS)
    )
    now = _utc_now()
    claims: list[dict[str, str]] = []
    async with session_factory() as session:
        jobs = (
            await session.execute(
                pending_account_model_evaluation_dispatches_statement(
                    limit=limit,
                    now=now,
                )
            )
        ).scalars().all()
        for job in jobs:
            if job.status != "queued":
                job.dispatch_status = "superseded"
                job.dispatch_claim_token = None
                job.dispatch_lease_expires_at = None
                job.dispatch_last_error = f"evaluation job is not queued (status={job.status})"
                continue
            claim_token = uuid4().hex
            job.dispatch_status = "publishing"
            job.dispatch_claim_token = claim_token
            job.dispatch_lease_expires_at = now + timedelta(seconds=lease)
            job.dispatch_publish_attempts = int(job.dispatch_publish_attempts or 0) + 1
            job.dispatch_acknowledged_at = None
            job.dispatch_last_error = None
            claims.append(
                {
                    "job_id": str(job.job_id),
                    "task_id": str(job.task_id),
                    "claim_token": claim_token,
                }
            )
        await session.commit()
    return claims


async def acknowledge_account_model_evaluation_dispatch(
    *,
    session_factory=async_session_factory,
    job_id: str,
    task_id: str | None,
) -> bool:
    """Record that the persisted Celery delivery reached an execution worker."""

    async with session_factory() as session:
        job = (
            await session.execute(
                select(AccountModelEvaluationJob)
                .where(AccountModelEvaluationJob.job_id == str(job_id))
                .with_for_update()
            )
        ).scalar_one_or_none()
        normalized_task_id = str(task_id or "").strip()
        if job is None or (normalized_task_id and str(job.task_id) != normalized_task_id):
            await session.commit()
            return False
        if job.status in {"completed", "failed", "cancelled"}:
            await session.commit()
            return True
        if job.dispatch_status not in {"publishing", "published"}:
            await session.commit()
            return False
        job.dispatch_acknowledged_at = _utc_now()
        await session.commit()
    return True


async def finalize_account_model_evaluation_dispatch_claim(
    *,
    session_factory=async_session_factory,
    claim: dict[str, str],
    published: bool,
    retry_delay_seconds: float | None = None,
    error: Exception | None = None,
) -> bool:
    retry_delay = (
        float(retry_delay_seconds)
        if retry_delay_seconds is not None
        else float(settings.ACCOUNT_TRAINING_OUTBOX_POLL_INTERVAL_SECONDS)
    )
    async with session_factory() as session:
        job = (
            await session.execute(
                select(AccountModelEvaluationJob)
                .where(AccountModelEvaluationJob.job_id == str(claim["job_id"]))
                .with_for_update()
            )
        ).scalar_one_or_none()
        if (
            job is None
            or job.dispatch_status != "publishing"
            or job.dispatch_claim_token != str(claim["claim_token"])
        ):
            await session.commit()
            return False
        job.dispatch_claim_token = None
        job.dispatch_lease_expires_at = None
        if published:
            job.dispatch_status = "published"
            job.dispatch_published_at = _utc_now()
            job.dispatch_last_error = None
        else:
            job.dispatch_status = "pending"
            job.dispatch_available_at = _utc_now() + timedelta(seconds=max(0.0, retry_delay))
            job.dispatch_published_at = None
            job.dispatch_acknowledged_at = None
            job.dispatch_last_error = (
                f"{type(error).__name__}: {error}" if error is not None else "broker publish failed"
            )
        await session.commit()
    return True


async def drain_account_model_evaluation_dispatch_outbox(
    *,
    session_factory=async_session_factory,
    publish: Callable[..., Any] | None = None,
    limit: int = 20,
    retry_delay_seconds: float | None = None,
) -> dict[str, int]:
    publish_dispatch = publish or _publish_account_model_evaluation
    retry_delay = (
        float(retry_delay_seconds)
        if retry_delay_seconds is not None
        else float(settings.ACCOUNT_TRAINING_OUTBOX_POLL_INTERVAL_SECONDS)
    )
    published = 0
    failed = 0
    for _ in range(max(1, int(limit))):
        claims = await claim_account_model_evaluation_dispatches(
            session_factory=session_factory,
            limit=1,
        )
        if not claims:
            break
        claim = claims[0]
        try:
            await asyncio.wait_for(
                asyncio.to_thread(
                    publish_dispatch,
                    str(claim["job_id"]),
                    task_id=str(claim["task_id"]),
                ),
                timeout=float(settings.ACCOUNT_TRAINING_OUTBOX_PUBLISH_TIMEOUT_SECONDS),
            )
        except Exception as error:
            if await finalize_account_model_evaluation_dispatch_claim(
                session_factory=session_factory,
                claim=claim,
                published=False,
                retry_delay_seconds=retry_delay,
                error=error,
            ):
                failed += 1
        else:
            if await finalize_account_model_evaluation_dispatch_claim(
                session_factory=session_factory,
                claim=claim,
                published=True,
            ):
                published += 1
    return {"published": published, "failed": failed}


async def run_account_model_evaluation_dispatch_outbox_publisher(stop_event: asyncio.Event) -> None:
    interval = float(settings.ACCOUNT_TRAINING_OUTBOX_POLL_INTERVAL_SECONDS)
    while not stop_event.is_set():
        try:
            await drain_account_model_evaluation_dispatch_outbox()
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Account-evaluation outbox publisher drain failed")
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=interval)
        except TimeoutError:
            continue


def _publish_account_model_evaluation(job_id: str, *, task_id: str) -> Any:
    from app.tasks.account_evaluation_tasks import enqueue_account_model_evaluation_job

    return enqueue_account_model_evaluation_job(job_id, task_id=task_id)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None, microsecond=0)
