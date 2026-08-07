"""Transactional outbox publisher for account-model training dispatches."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.mysql import async_session_factory
from app.models.account_labeling import AccountModelTrainingDispatchOutbox, AccountModelTrainingRun
from app.utils.logger import logger

__all__ = [
    "account_training_dispatch_task_id",
    "claim_account_training_dispatches",
    "create_account_training_dispatch",
    "dispatch_projection",
    "drain_account_training_dispatch_outbox",
    "finalize_account_training_dispatch_claim",
    "pending_account_training_dispatches_statement",
    "run_account_training_dispatch_outbox_publisher",
]


def account_training_dispatch_task_id(run_id: str, attempt: int) -> str:
    """Return the stable Celery task identifier for a run attempt."""

    return f"account-training:{run_id}:attempt:{int(attempt)}"


def create_account_training_dispatch(run: AccountModelTrainingRun) -> AccountModelTrainingDispatchOutbox:
    """Build the unique dispatch intent to persist with a run state transition."""

    attempt = int(run.attempt)
    return AccountModelTrainingDispatchOutbox(
        dispatch_id=f"account-training-dispatch:{run.run_id}:attempt:{attempt}",
        run_id=run.run_id,
        attempt=attempt,
        task_id=account_training_dispatch_task_id(run.run_id, attempt),
        status="pending",
        publish_attempts=0,
        available_at=_utc_now(),
    )


def dispatch_projection(dispatch: AccountModelTrainingDispatchOutbox | None) -> dict[str, Any] | None:
    if dispatch is None:
        return None
    return {
        "dispatch_id": dispatch.dispatch_id,
        "attempt": dispatch.attempt,
        "task_id": dispatch.task_id,
        "status": dispatch.status,
        "claim_token": dispatch.claim_token,
        "lease_expires_at": dispatch.lease_expires_at.isoformat() if dispatch.lease_expires_at else None,
        "publish_attempts": dispatch.publish_attempts,
        "available_at": dispatch.available_at.isoformat() if dispatch.available_at else None,
        "published_at": dispatch.published_at.isoformat() if dispatch.published_at else None,
        "last_error": dispatch.last_error,
    }


def pending_account_training_dispatches_statement(*, limit: int, now: datetime | None = None):
    """Select ready or expired claims under row locks for a short claim transaction."""

    ready_at = now or _utc_now()
    return (
        select(AccountModelTrainingDispatchOutbox)
        .where(
            or_(
                and_(
                    AccountModelTrainingDispatchOutbox.status == "pending",
                    AccountModelTrainingDispatchOutbox.available_at <= ready_at,
                ),
                and_(
                    AccountModelTrainingDispatchOutbox.status == "publishing",
                    AccountModelTrainingDispatchOutbox.lease_expires_at <= ready_at,
                ),
            ),
        )
        .order_by(
            AccountModelTrainingDispatchOutbox.available_at.asc(),
            AccountModelTrainingDispatchOutbox.id.asc(),
        )
        .limit(max(1, int(limit)))
        .with_for_update(skip_locked=True)
    )


async def claim_account_training_dispatches(
    *,
    session_factory=async_session_factory,
    limit: int = 20,
    lease_seconds: float | None = None,
) -> list[dict[str, str | int]]:
    """Claim ready dispatches and commit before any broker interaction."""

    lease = (
        float(lease_seconds)
        if lease_seconds is not None
        else float(settings.ACCOUNT_TRAINING_OUTBOX_CLAIM_LEASE_SECONDS)
    )
    now = _utc_now()
    claims: list[dict[str, str | int]] = []
    async with session_factory() as session:
        dispatches = (
            await session.execute(pending_account_training_dispatches_statement(limit=limit, now=now))
        ).scalars().all()
        for dispatch in dispatches:
            # Do not lock the run here. Service transitions own the run lock;
            # worker expected_attempt gating makes a post-claim state change safe.
            run = (
                await session.execute(
                    select(AccountModelTrainingRun).where(AccountModelTrainingRun.run_id == str(dispatch.run_id))
                )
            ).scalar_one_or_none()
            superseded_error = _superseded_dispatch_error(run, dispatch)
            if superseded_error is not None:
                dispatch.status = "superseded"
                dispatch.last_error = superseded_error
                dispatch.claim_token = None
                dispatch.lease_expires_at = None
                continue

            claim_token = uuid4().hex
            dispatch.status = "publishing"
            dispatch.claim_token = claim_token
            dispatch.lease_expires_at = now + timedelta(seconds=lease)
            dispatch.publish_attempts += 1
            dispatch.last_error = None
            claims.append(
                {
                    "dispatch_id": str(dispatch.dispatch_id),
                    "run_id": str(dispatch.run_id),
                    "attempt": int(dispatch.attempt),
                    "task_id": str(dispatch.task_id),
                    "claim_token": claim_token,
                }
            )
        await session.commit()
    return claims


async def finalize_account_training_dispatch_claim(
    *,
    session_factory=async_session_factory,
    claim: dict[str, str | int],
    published: bool,
    retry_delay_seconds: float | None = None,
    error: Exception | None = None,
) -> bool:
    """Finalize one claim only while its token still owns the dispatch row."""

    retry_delay = (
        float(retry_delay_seconds)
        if retry_delay_seconds is not None
        else float(settings.ACCOUNT_TRAINING_OUTBOX_POLL_INTERVAL_SECONDS)
    )
    async with session_factory() as session:
        dispatch = (
            await session.execute(
                select(AccountModelTrainingDispatchOutbox)
                .where(AccountModelTrainingDispatchOutbox.dispatch_id == str(claim["dispatch_id"]))
                .with_for_update()
            )
        ).scalar_one_or_none()
        if (
            dispatch is None
            or dispatch.status != "publishing"
            or dispatch.claim_token != str(claim["claim_token"])
        ):
            await session.commit()
            return False

        dispatch.claim_token = None
        dispatch.lease_expires_at = None
        if published:
            dispatch.status = "published"
            dispatch.published_at = _utc_now()
            dispatch.last_error = None
        else:
            dispatch.status = "pending"
            dispatch.available_at = _utc_now() + timedelta(seconds=max(0.0, retry_delay))
            dispatch.last_error = f"{type(error).__name__}: {error}" if error is not None else "broker publish failed"
        await session.commit()
    return True


async def drain_account_training_dispatch_outbox(
    *,
    session_factory=async_session_factory,
    publish: Callable[..., Any] | None = None,
    limit: int = 20,
    retry_delay_seconds: float | None = None,
) -> dict[str, int]:
    """Claim, publish outside transactions, then token-finalize each dispatch."""

    publish_dispatch = publish or _publish_account_training_dispatch
    retry_delay = (
        float(retry_delay_seconds)
        if retry_delay_seconds is not None
        else float(settings.ACCOUNT_TRAINING_OUTBOX_POLL_INTERVAL_SECONDS)
    )
    published = 0
    failed = 0
    claims = await claim_account_training_dispatches(session_factory=session_factory, limit=limit)
    for claim in claims:
        try:
            await asyncio.wait_for(
                asyncio.to_thread(
                    publish_dispatch,
                    str(claim["run_id"]),
                    attempt=int(claim["attempt"]),
                    task_id=str(claim["task_id"]),
                ),
                timeout=float(settings.ACCOUNT_TRAINING_OUTBOX_PUBLISH_TIMEOUT_SECONDS),
            )
        except Exception as error:
            if await finalize_account_training_dispatch_claim(
                session_factory=session_factory,
                claim=claim,
                published=False,
                retry_delay_seconds=retry_delay,
                error=error,
            ):
                failed += 1
        else:
            if await finalize_account_training_dispatch_claim(
                session_factory=session_factory,
                claim=claim,
                published=True,
            ):
                published += 1
    return {"published": published, "failed": failed}


async def run_account_training_dispatch_outbox_publisher(stop_event: asyncio.Event) -> None:
    """Poll committed dispatch intents until FastAPI lifecycle shutdown requests exit."""

    interval = float(settings.ACCOUNT_TRAINING_OUTBOX_POLL_INTERVAL_SECONDS)
    while not stop_event.is_set():
        try:
            await drain_account_training_dispatch_outbox()
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Account-training outbox publisher drain failed")
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=interval)
        except TimeoutError:
            continue


def _publish_account_training_dispatch(run_id: str, *, attempt: int, task_id: str) -> Any:
    # Import lazily so creating an outbox record never initializes Celery.
    from app.tasks.account_training_tasks import enqueue_account_training_run

    return enqueue_account_training_run(run_id, attempt=attempt, task_id=task_id)


def _superseded_dispatch_error(
    run: AccountModelTrainingRun | None,
    dispatch: AccountModelTrainingDispatchOutbox,
) -> str | None:
    if run is None:
        return "training run is missing"
    if run.status != "queued":
        return f"training run is not queued (status={run.status})"
    if int(run.attempt) != int(dispatch.attempt):
        return "training run attempt no longer matches dispatch"
    return None


def _utc_now() -> datetime:
    # MySQL DATETIME stores this field at second precision in the deployed schema.
    return datetime.now(timezone.utc).replace(tzinfo=None, microsecond=0)
