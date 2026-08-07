"""Persistence and dispatch service for governed account-model training."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.account_training import (
    AccountTrainingFamily,
    AccountTrainingPolicy,
    AccountTrainingState,
    TrainingTriggerContext,
    evaluate_training_trigger,
    is_training_heartbeat_stale,
    recovery_attempt_allowed,
    require_training_transition,
)
from app.config import settings
from app.core.account_training_runtime import account_training_run_is_live
from app.models.account_labeling import (
    AccountCorpusVersion,
    AccountDetectionDatasetVersion,
    AccountModelTrainingDispatchOutbox,
    AccountModelTrainingEvent,
    AccountModelTrainingRun,
)
from app.services.account_training_dispatch_outbox import (
    create_account_training_dispatch,
    dispatch_projection,
)
from app.utils.exceptions import AppException

__all__ = [
    "cancel_account_training_run",
    "create_account_training_run",
    "get_account_training_run",
    "interrupt_stale_account_training_runs",
    "list_account_training_events",
    "list_account_training_runs",
    "resume_account_training_run",
]


async def create_account_training_run(
    session: AsyncSession,
    *,
    family: str,
    corpus_version_id: str,
    input_fingerprint: str,
    config: dict[str, Any],
    manual: bool,
    operator_id: int,
    dispatch: bool = True,
) -> dict[str, Any]:
    """Validate trigger policy and persist a run with its dispatch intent."""

    try:
        training_family = AccountTrainingFamily(family)
    except ValueError as error:
        raise AppException(code=400, msg=f"Unsupported account training family: {family}") from error

    source_model = (
        AccountCorpusVersion
        if training_family == AccountTrainingFamily.CHINESE_SOCIAL_ENCODER
        else AccountDetectionDatasetVersion
    )
    corpus = (
        await session.execute(
            select(source_model).where(source_model.corpus_version_id == corpus_version_id)
            if source_model is AccountCorpusVersion
            else select(source_model).where(source_model.dataset_version_id == corpus_version_id)
        )
    ).scalar_one_or_none()
    if corpus is None:
        raise AppException(code=404, msg="Account corpus version not found.")
    manifest = _loads(corpus.manifest_json)
    eligible_count = _eligible_count(training_family, corpus, manifest)
    source_fingerprint = (
        corpus.input_fingerprint
        if training_family == AccountTrainingFamily.CHINESE_SOCIAL_ENCODER
        else corpus.data_fingerprint
    )
    if input_fingerprint != source_fingerprint:
        raise AppException(code=409, msg="Training input_fingerprint does not match the corpus version.")

    latest = (
        await session.execute(
            select(AccountModelTrainingRun)
            .where(AccountModelTrainingRun.family == training_family.value)
            .order_by(AccountModelTrainingRun.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    policy = _account_training_policy()
    decision = evaluate_training_trigger(
        TrainingTriggerContext(
            family=training_family,
            eligible_item_count=eligible_count,
            last_dispatched_at=latest.created_at if latest else None,
            now=datetime.now(timezone.utc),
            manual=manual,
            input_ready=corpus.status in {"candidate", "approved", "training_ready"},
        ),
        policy=policy,
    )
    if not decision.allowed:
        raise AppException(code=409, msg=f"Account training cannot be dispatched: {decision.reason}.")

    config_payload = _persisted_config(
        config,
        family=training_family,
        corpus_version_id=corpus_version_id,
        input_fingerprint=input_fingerprint,
        trigger=decision.reason,
    )
    if training_family == AccountTrainingFamily.CHINESE_SOCIAL_ENCODER:
        config_payload.setdefault("corpus_documents_path", manifest.get("corpus_path"))
    else:
        config_payload.setdefault("dataset_root", corpus.artifact_uri)
    config_hash = _fingerprint(config_payload)
    created_at = datetime.now(timezone.utc).replace(tzinfo=None)
    run = AccountModelTrainingRun(
        run_id=f"account-training-{uuid4().hex[:16]}",
        family=training_family.value,
        status=AccountTrainingState.QUEUED.value,
        stage="queued",
        corpus_version_id=corpus_version_id,
        input_fingerprint=input_fingerprint,
        config_hash=config_hash,
        config_json=json.dumps(config_payload, ensure_ascii=False, default=str),
        attempt=1,
        # The persisted field includes the initial execution. Its policy name
        # remains max resumes so operators can reason about recovery directly.
        max_attempts=1 + policy.max_resumes,
        created_by=int(operator_id),
        created_at=created_at,
        updated_at=created_at,
        error=None,
    )
    session.add(run)
    await session.flush()
    await _append_event(
        session,
        run,
        event_type="created",
        payload={"config": config_payload, "trigger": _decision_projection(decision)},
    )
    training_dispatch = None
    if dispatch:
        training_dispatch = create_account_training_dispatch(run)
        session.add(training_dispatch)
        await _append_event(
            session,
            run,
            event_type="dispatch_pending",
            payload={
                "dispatch_id": training_dispatch.dispatch_id,
                "attempt": training_dispatch.attempt,
                "task_id": training_dispatch.task_id,
            },
        )
        await session.flush()
    return _run_projection(run, decision=decision, dispatch=training_dispatch)


async def get_account_training_run(session: AsyncSession, run_id: str) -> dict[str, Any] | None:
    run = (
        await session.execute(select(AccountModelTrainingRun).where(AccountModelTrainingRun.run_id == run_id))
    ).scalar_one_or_none()
    return _run_projection(run) if run else None


async def list_account_training_runs(session: AsyncSession) -> list[dict[str, Any]]:
    rows = (
        await session.execute(select(AccountModelTrainingRun).order_by(AccountModelTrainingRun.created_at.desc()))
    ).scalars().all()
    return [_run_projection(row) for row in rows]


async def list_account_training_events(session: AsyncSession, run_id: str) -> list[dict[str, Any]]:
    rows = (
        await session.execute(
            select(AccountModelTrainingEvent)
            .where(AccountModelTrainingEvent.run_id == run_id)
            .order_by(AccountModelTrainingEvent.created_at.asc(), AccountModelTrainingEvent.id.asc())
        )
    ).scalars().all()
    return [_event_projection(row) for row in rows]


async def cancel_account_training_run(
    session: AsyncSession,
    *,
    run_id: str,
    operator_id: int,
) -> dict[str, Any] | None:
    run = await _locked_training_run(session, run_id)
    if run is None:
        return None
    if run.status in {
        state.value
        for state in (
            AccountTrainingState.COMPLETED,
            AccountTrainingState.FAILED,
            AccountTrainingState.CANCELLED,
        )
    }:
        raise AppException(code=409, msg="Terminal account training runs cannot be cancelled.")

    # Cancellation is linearized against publication by locking the current
    # attempt's dispatch after the run. A pending intent is prevented from
    # reaching the broker; a claimed intent has already crossed that boundary.
    dispatch = await _locked_training_dispatch(session, run_id=run.run_id, attempt=run.attempt)
    if dispatch is not None and dispatch.status == "publishing":
        raise AppException(
            code=409,
            msg="Account training dispatch is currently publishing; retry cancellation after publication resolves.",
        )

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    run.cancel_requested_at = now
    run.cancelled_by = int(operator_id)
    dispatch_superseded = False
    if run.status in {AccountTrainingState.QUEUED.value, AccountTrainingState.INTERRUPTED.value}:
        if dispatch is not None and dispatch.status == "pending":
            dispatch.status = "superseded"
            dispatch.claim_token = None
            dispatch.lease_expires_at = None
            dispatch.last_error = "superseded by cancellation before broker publication"
            dispatch_superseded = True
        require_training_transition(run.status, AccountTrainingState.CANCELLED.value)
        run.status = AccountTrainingState.CANCELLED.value
        run.stage = "cancelled"
        run.finished_at = now
    await _append_event(session, run, event_type="cancel_requested", payload={"operator_id": operator_id})
    if dispatch_superseded:
        await _append_event(
            session,
            run,
            event_type="dispatch_superseded",
            payload={
                "dispatch_id": dispatch.dispatch_id,
                "attempt": dispatch.attempt,
                "reason": "cancelled_before_broker_publication",
            },
        )
    if run.status == AccountTrainingState.CANCELLED.value:
        await _append_event(session, run, event_type="cancelled", payload={"reason": "cancelled_before_execution"})
    await session.flush()
    return _run_projection(run)


async def resume_account_training_run(
    session: AsyncSession,
    *,
    run_id: str,
    operator_id: int,
    dispatch: bool = True,
) -> dict[str, Any] | None:
    run = await _locked_training_run(session, run_id)
    if run is None:
        return None
    if run.status != AccountTrainingState.INTERRUPTED.value:
        raise AppException(code=409, msg="Only interrupted account training runs can be resumed.")
    configured_max_attempts = _configured_max_attempts()
    if not _normalize_persisted_attempt_limit(run, configured_max_attempts):
        raise AppException(code=409, msg="Account training has an invalid persisted attempt ordinal.")
    if not recovery_attempt_allowed(attempt=run.attempt, max_attempts=configured_max_attempts):
        raise AppException(code=409, msg="Account training retry limit has been exhausted.")
    if account_training_run_is_live(run.run_id):
        raise AppException(code=409, msg="Account training run is still owned by a live runtime.")
    require_training_transition(run.status, AccountTrainingState.QUEUED.value)
    run.status = AccountTrainingState.QUEUED.value
    run.stage = "resume_queued"
    run.attempt += 1
    run.cancel_requested_at = None
    run.cancelled_by = None
    run.error = None
    await _append_event(session, run, event_type="resumed", payload={"operator_id": operator_id, "attempt": run.attempt})
    training_dispatch = None
    if dispatch:
        training_dispatch = create_account_training_dispatch(run)
        session.add(training_dispatch)
        await _append_event(
            session,
            run,
            event_type="dispatch_pending",
            payload={
                "dispatch_id": training_dispatch.dispatch_id,
                "attempt": training_dispatch.attempt,
                "task_id": training_dispatch.task_id,
            },
        )
    await session.flush()
    return _run_projection(run, dispatch=training_dispatch)


async def interrupt_stale_account_training_runs(
    session: AsyncSession,
    *,
    now: datetime | None = None,
    timeout_seconds: int | None = None,
) -> list[dict[str, Any]]:
    """Lease-expire active work after a worker crash without auto-retrying it."""

    observed_at = now or datetime.now(timezone.utc)
    effective_timeout = (
        int(timeout_seconds)
        if timeout_seconds is not None
        else _account_training_policy().heartbeat_timeout_seconds
    )
    candidates = (
        await session.execute(
            select(AccountModelTrainingRun).where(
                AccountModelTrainingRun.status.in_(
                    [
                        AccountTrainingState.PREPARING.value,
                        AccountTrainingState.RUNNING.value,
                        AccountTrainingState.EVALUATING.value,
                    ]
                )
            )
        )
    ).scalars().all()
    interrupted: list[dict[str, Any]] = []
    for candidate in candidates:
        run = await _locked_training_run(session, candidate.run_id)
        if run is None:
            continue
        if not is_training_heartbeat_stale(
            state=run.status,
            heartbeat_at=run.heartbeat_at,
            now=observed_at,
            timeout_seconds=effective_timeout,
        ):
            continue
        require_training_transition(run.status, AccountTrainingState.INTERRUPTED.value)
        run.status = AccountTrainingState.INTERRUPTED.value
        run.stage = "heartbeat_expired"
        run.error = "worker heartbeat expired; explicit resume is required"
        run.finished_at = observed_at.replace(tzinfo=None)
        await _append_event(
            session,
            run,
            event_type="interrupted",
            payload={"reason": "heartbeat_expired", "timeout_seconds": effective_timeout},
        )
        interrupted.append(_run_projection(run))
    if interrupted:
        await session.flush()
    return interrupted


async def _locked_training_run(session: AsyncSession, run_id: str) -> AccountModelTrainingRun | None:
    return (
        await session.execute(
            select(AccountModelTrainingRun)
            .where(AccountModelTrainingRun.run_id == run_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
    ).scalar_one_or_none()


async def _locked_training_dispatch(
    session: AsyncSession,
    *,
    run_id: str,
    attempt: int,
) -> AccountModelTrainingDispatchOutbox | None:
    """Lock the dispatch belonging to the run state being cancelled."""

    return (
        await session.execute(
            select(AccountModelTrainingDispatchOutbox)
            .where(
                AccountModelTrainingDispatchOutbox.run_id == run_id,
                AccountModelTrainingDispatchOutbox.attempt == int(attempt),
            )
            .with_for_update()
            .execution_options(populate_existing=True)
        )
    ).scalar_one_or_none()


def _configured_max_attempts() -> int:
    return 1 + max(0, int(settings.ACCOUNT_TRAINING_MAX_RESUMES))


def _normalize_persisted_attempt_limit(run: AccountModelTrainingRun, configured_max_attempts: int) -> bool:
    try:
        attempt = int(run.attempt)
    except (TypeError, ValueError):
        return False
    run.max_attempts = configured_max_attempts
    return attempt >= 1


async def _append_event(
    session: AsyncSession,
    run: AccountModelTrainingRun,
    *,
    event_type: str,
    payload: dict[str, Any],
) -> None:
    session.add(
        AccountModelTrainingEvent(
            event_id=f"account-training-event-{uuid4().hex[:16]}",
            run_id=run.run_id,
            event_type=event_type,
            status=run.status,
            stage=run.stage,
            payload_json=json.dumps(payload, ensure_ascii=False, default=str),
        )
    )


def _eligible_count(family: AccountTrainingFamily, corpus: AccountCorpusVersion, manifest: dict[str, Any]) -> int:
    if family == AccountTrainingFamily.CHINESE_SOCIAL_ENCODER:
        return int(manifest.get("eligible_chinese_token_count") or manifest.get("token_count") or 0)
    return int(corpus.source_label_count)


def _run_projection(
    run: AccountModelTrainingRun,
    *,
    decision: Any | None = None,
    dispatch=None,
) -> dict[str, Any]:
    return {
        "run_id": run.run_id,
        "family": run.family,
        "status": run.status,
        "stage": run.stage,
        "corpus_version_id": run.corpus_version_id,
        "input_fingerprint": run.input_fingerprint,
        "config_hash": run.config_hash,
        "config": _loads(run.config_json),
        "attempt": run.attempt,
        "max_attempts": run.max_attempts,
        "heartbeat_at": run.heartbeat_at.isoformat() if run.heartbeat_at else None,
        "resume_checkpoint_uri": run.resume_checkpoint_uri,
        "error": run.error,
        "dispatch": dispatch_projection(dispatch),
        "created_at": run.created_at.isoformat() if run.created_at else None,
        "decision": {
            "allowed": decision.allowed,
            "reason": decision.reason,
            "threshold": decision.threshold,
            "eligible_item_count": decision.eligible_item_count,
            "quantity_bypassed": decision.quantity_bypassed,
        } if decision else None,
    }


def _event_projection(event: AccountModelTrainingEvent) -> dict[str, Any]:
    return {
        "event_id": event.event_id,
        "run_id": event.run_id,
        "event_type": event.event_type,
        "status": event.status,
        "stage": event.stage,
        "payload": _loads(event.payload_json),
        "created_at": event.created_at.isoformat() if event.created_at else None,
    }


def _decision_projection(decision: Any) -> dict[str, Any]:
    return {
        "allowed": bool(decision.allowed),
        "reason": str(decision.reason),
        "threshold": int(decision.threshold),
        "eligible_item_count": int(decision.eligible_item_count),
        "quantity_bypassed": bool(decision.quantity_bypassed),
    }


def _persisted_config(
    config: dict[str, Any],
    *,
    family: AccountTrainingFamily,
    corpus_version_id: str,
    input_fingerprint: str,
    trigger: str,
) -> dict[str, Any]:
    """Make the effective execution configuration immutable and self-describing."""

    payload = dict(config)
    payload.update(
        {
            "schema": "cogguard.account-training-config.v1",
            "family": family.value,
            "corpus_version_id": corpus_version_id,
            "input_fingerprint": input_fingerprint,
            "trigger": trigger,
        }
    )
    return payload


def _loads(value: str) -> dict[str, Any]:
    try:
        payload = json.loads(value)
        return payload if isinstance(payload, dict) else {}
    except (TypeError, json.JSONDecodeError):
        return {}


def _fingerprint(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")).hexdigest()


def _account_training_policy() -> AccountTrainingPolicy:
    return AccountTrainingPolicy(
        dapt_token_threshold=settings.ACCOUNT_TRAINING_DAPT_TOKEN_THRESHOLD,
        supervised_label_threshold=settings.ACCOUNT_TRAINING_SUPERVISED_LABEL_THRESHOLD,
        cooldown_days=settings.ACCOUNT_TRAINING_COOLDOWN_DAYS,
        heartbeat_timeout_seconds=settings.ACCOUNT_TRAINING_HEARTBEAT_TIMEOUT_SECONDS,
        max_resumes=settings.ACCOUNT_TRAINING_MAX_RESUMES,
    )
