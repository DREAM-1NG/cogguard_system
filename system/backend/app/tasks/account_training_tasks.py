"""Celery orchestration for durable account-model training runs."""

from __future__ import annotations

import asyncio
import json
import threading
from concurrent.futures import Future
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

from sqlalchemy import select

from app.celery_app import celery_app
from app.config import settings
from app.core.account_training import AccountTrainingState, require_training_transition
from app.core.trained_bot_detection import invalidate_trained_botrhg_runtime_cache
from app.core.account_training_runtime import (
    AccountModelGpuOwnershipBusyError,
    AccountModelRuntimeOwnership,
    AccountTrainingOwnershipBusyError,
    acquire_account_model_gpu_ownership,
    acquire_account_training_ownership,
    execute_account_training_artifact,
)
from app.db.mysql import async_session_factory
from app.models.account_labeling import AccountModelTrainingEvent, AccountModelTrainingRun
from app.services.account_model_monitoring_service import create_account_monitor_snapshot
from app.services.account_model_governance_service import attempt_automatic_account_model_rollback
from app.tasks.async_runtime import run_async
from app.utils.exceptions import AppException

__all__ = [
    "enqueue_account_training_run",
    "enqueue_account_training_reconciliation",
    "execute_account_training_run",
    "monitor_active_account_model",
    "reconcile_account_training_heartbeats",
]


_HEARTBEAT_INTERVAL_SECONDS = 30


def enqueue_account_training_run(run_id: str, *, attempt: int, task_id: str | None = None):
    """Dispatch one durable run to the single-concurrency GPU queue."""

    return execute_account_training_run.apply_async(
        args=[str(run_id), int(attempt)],
        queue="account_training",
        task_id=str(task_id) if task_id is not None else None,
        retry=False,
    )


def enqueue_account_training_reconciliation(*, timeout_seconds: int | None = None):
    """Schedule a lease sweep; deployment cron/Celery Beat owns its cadence."""

    args = [] if timeout_seconds is None else [int(timeout_seconds)]
    return reconcile_account_training_heartbeats.apply_async(args=args, queue="account_training")


@celery_app.task(
    name="account_training.execute",
    bind=True,
    acks_late=True,
    reject_on_worker_lost=True,
    max_retries=None,
)
def execute_account_training_run(self, run_id: str, expected_attempt: int):
    result = run_async(_execute_account_training_run(str(run_id), expected_attempt=int(expected_attempt)))
    if result.get("status") == "gpu_busy":
        return self.retry(countdown=30)
    return result


@celery_app.task(name="account_training.reconcile_heartbeats", bind=True, acks_late=True, max_retries=0)
def reconcile_account_training_heartbeats(self, timeout_seconds: int | None = None):
    del self
    return run_async(_reconcile_account_training_heartbeats(timeout_seconds=timeout_seconds))


@celery_app.task(name="account_training.monitor_active_model", bind=True, acks_late=True, max_retries=0)
def monitor_active_account_model(self, window_seconds: int = 300):
    del self
    return run_async(_monitor_active_account_model(window_seconds=int(window_seconds)))


async def _execute_account_training_run(run_id: str, *, expected_attempt: int) -> dict[str, Any]:
    async with async_session_factory() as session:
        run = (
            await session.execute(
                select(AccountModelTrainingRun)
                .where(AccountModelTrainingRun.run_id == run_id)
                .with_for_update()
            )
        ).scalar_one_or_none()
        if run is None:
            return {"run_id": run_id, "status": "missing"}
        if int(run.attempt) != int(expected_attempt):
            return {
                "run_id": run_id,
                "status": "stale_attempt",
                "expected_attempt": int(expected_attempt),
                "current_attempt": int(run.attempt),
            }
        if run.status != AccountTrainingState.QUEUED.value:
            return {"run_id": run_id, "status": f"already_{run.status}"}

        try:
            gpu_ownership = acquire_account_model_gpu_ownership(f"training:{run.run_id}:attempt:{run.attempt}")
        except AccountModelGpuOwnershipBusyError:
            return {"run_id": run_id, "status": "gpu_busy"}
        try:
            run_ownership = acquire_account_training_ownership(run.run_id, run.attempt)
        except AccountTrainingOwnershipBusyError:
            gpu_ownership.release()
            return {"run_id": run_id, "status": "runtime_still_owned"}
        except BaseException:
            gpu_ownership.release()
            raise
        ownership = AccountModelRuntimeOwnership(gpu_ownership, run_ownership)
        await _advance(session, run, AccountTrainingState.PREPARING, "preparing", "worker_claimed")
        await session.commit()
        try:
            config = _loads(run.config_json)
            if run.family == "chinese_account_detector" and not _has_governed_detector_binding(config):
                config = await _resolve_governed_detector_config(session, config)
            if run.family == "chinese_account_detector":
                config.pop("frozen_holdout_manifest_path", None)
                config.pop("frozen_holdout_manifest_sha256", None)
            await _advance(session, run, AccountTrainingState.RUNNING, "training", "training_started")
            run.started_at = run.started_at or _utc_now()
            await session.commit()

            result = await _run_with_heartbeats(session, run, config, ownership=ownership)
            await session.refresh(run)
            if run.status == AccountTrainingState.INTERRUPTED.value:
                return {"run_id": run_id, "status": "lease_lost"}
            if _cancel_requested(run):
                await _mark_cancelled(session, run, reason="cancel_requested_during_training")
                await session.commit()
                return {"run_id": run_id, "status": run.status}

            if run.family == "chinese_social_encoder":
                result = await _register_chinese_social_encoder_version(
                    session,
                    training_run=run,
                    result=result,
                )
            await _advance(session, run, AccountTrainingState.EVALUATING, "evaluating", "evaluation_started")
            if run.family == "chinese_account_detector":
                result = await _register_detector_candidate(session, run, result)
            run.resume_checkpoint_uri = _checkpoint_uri(result)
            await session.commit()
            await session.refresh(run)
            if _cancel_requested(run):
                await _mark_cancelled(session, run, reason="cancel_requested_before_completion")
                await session.commit()
                return {"run_id": run_id, "status": run.status}

            _transition(run, AccountTrainingState.COMPLETED)
            run.stage = "completed"
            run.finished_at = _utc_now()
            run.heartbeat_at = _utc_now()
            await _event(session, run, "completed", {"result": result})
            await session.commit()
            return {"run_id": run_id, "status": run.status, "result": result}
        except Exception as error:
            await session.refresh(run)
            if run.status == AccountTrainingState.INTERRUPTED.value:
                return {"run_id": run_id, "status": "lease_lost"}
            if _cancel_requested(run):
                await _mark_cancelled(session, run, reason="cancel_requested_after_runtime_error")
                await session.commit()
                return {"run_id": run_id, "status": run.status}
            if run.status not in {
                AccountTrainingState.COMPLETED.value,
                AccountTrainingState.CANCELLED.value,
                AccountTrainingState.FAILED.value,
            }:
                _transition(run, AccountTrainingState.FAILED)
                run.stage = "failed"
                run.error = f"{type(error).__name__}: {error}"
                run.finished_at = _utc_now()
                await _event(session, run, "failed", {"error": run.error})
                await session.commit()
            raise
        finally:
            if not ownership.release_deferred:
                ownership.release()


async def _run_with_heartbeats(
    session,
    run: AccountModelTrainingRun,
    config: dict[str, Any],
    *,
    ownership=None,
) -> dict[str, Any]:
    """Keep the database lease alive while the blocking GPU runtime executes."""

    effective_config = dict(config)
    if run.resume_checkpoint_uri:
        effective_config["resume_checkpoint_uri"] = run.resume_checkpoint_uri
    effective_config.pop("output_dir", None)
    output_dir = f"account_training/{run.run_id}/attempt-{run.attempt}"
    blocking_execution = _start_blocking_training(
        family=run.family,
        config=effective_config,
        output_dir=output_dir,
    )
    execution = asyncio.wrap_future(blocking_execution)
    try:
        while True:
            done, _ = await asyncio.wait({execution}, timeout=_HEARTBEAT_INTERVAL_SECONDS)
            if execution in done:
                return await execution
            await session.refresh(run)
            if run.status == AccountTrainingState.INTERRUPTED.value:
                # The runtime is not force-killed because that can corrupt a
                # checkpoint. Detach it so the worker releases its DB session.
                if ownership is not None:
                    ownership.release_when_finished(blocking_execution)
                return {}
            if run.status not in {AccountTrainingState.RUNNING.value, AccountTrainingState.EVALUATING.value}:
                if ownership is not None:
                    ownership.release_when_finished(blocking_execution)
                return {}
            run.heartbeat_at = _utc_now()
            await session.commit()
    except BaseException:
        # asyncio.to_thread cannot stop an already running Python thread. Do
        # not let an outer cancellation or a database exception release the
        # artifact fence while that thread can still write its checkpoint.
        await _await_execution_completion(execution)
        raise


def _start_blocking_training(
    *,
    family: str,
    config: dict[str, Any],
    output_dir: str,
) -> Future[dict[str, Any]]:
    """Start training with a completion signal independent of asyncio."""

    execution: Future[dict[str, Any]] = Future()

    def invoke() -> None:
        if not execution.set_running_or_notify_cancel():
            return
        try:
            result = execute_account_training_artifact(
                family=family,
                config=config,
                output_dir=output_dir,
            )
        except BaseException as error:
            execution.set_exception(error)
        else:
            execution.set_result(result)

    threading.Thread(
        target=invoke,
        name="account-training-runtime",
        daemon=False,
    ).start()
    return execution


async def _await_execution_completion(execution: asyncio.Task[dict[str, Any]]) -> None:
    while not execution.done():
        try:
            await asyncio.shield(execution)
        except asyncio.CancelledError:
            # A second cancellation must not make the outer finally release
            # ownership before the blocking runtime has stopped.
            continue
        except Exception:
            break
    if execution.done() and not execution.cancelled():
        try:
            execution.exception()
        except asyncio.CancelledError:
            pass


async def _reconcile_account_training_heartbeats(*, timeout_seconds: int | None) -> dict[str, Any]:
    from app.services.account_training_service import interrupt_stale_account_training_runs

    async with async_session_factory() as session:
        interrupted = await interrupt_stale_account_training_runs(
            session,
            timeout_seconds=(
                int(timeout_seconds)
                if timeout_seconds is not None
                else settings.ACCOUNT_TRAINING_HEARTBEAT_TIMEOUT_SECONDS
            ),
        )
        await session.commit()
    return {"interrupted_run_ids": [row["run_id"] for row in interrupted]}


async def _monitor_active_account_model(*, window_seconds: int) -> dict[str, Any]:
    if int(window_seconds) <= 0:
        raise ValueError("Account model monitoring window must be positive.")
    finished_at = datetime.now(timezone.utc)
    started_at = finished_at - timedelta(seconds=int(window_seconds))
    async with async_session_factory() as session:
        try:
            snapshot = await create_account_monitor_snapshot(
                session,
                window_started_at=started_at,
                window_finished_at=finished_at,
            )
        except AppException as error:
            return {"status": "unavailable", "reason": error.msg}
        automatic_rollback = await attempt_automatic_account_model_rollback(
            session,
            snapshot_id=str(snapshot["snapshot_id"]),
        )
        await session.commit()
    if automatic_rollback["status"] == "rolled_back":
        invalidate_trained_botrhg_runtime_cache()
    return {
        "status": "completed",
        "snapshot": snapshot,
        "automatic_rollback": automatic_rollback,
    }


async def _advance(
    session,
    run: AccountModelTrainingRun,
    state: AccountTrainingState,
    stage: str,
    event_type: str,
) -> None:
    _transition(run, state)
    run.stage = stage
    run.heartbeat_at = _utc_now()
    await _event(session, run, event_type, {})


async def _mark_cancelled(session, run: AccountModelTrainingRun, *, reason: str) -> None:
    if run.status != AccountTrainingState.CANCELLED.value:
        _transition(run, AccountTrainingState.CANCELLED)
        run.stage = "cancelled"
        run.finished_at = _utc_now()
        run.heartbeat_at = _utc_now()
        await _event(session, run, "cancelled", {"reason": reason})


def _transition(run: AccountModelTrainingRun, target: AccountTrainingState) -> None:
    require_training_transition(run.status, target.value)
    run.status = target.value


async def _event(session, run: AccountModelTrainingRun, event_type: str, payload: dict[str, Any]) -> None:
    session.add(
        AccountModelTrainingEvent(
            event_id=f"account-training-event-{uuid4().hex}",
            run_id=run.run_id,
            event_type=event_type,
            status=run.status,
            stage=run.stage,
            payload_json=json.dumps(payload, ensure_ascii=False, default=str),
        )
    )


def _cancel_requested(run: AccountModelTrainingRun) -> bool:
    return run.cancel_requested_at is not None or run.status == AccountTrainingState.CANCELLED.value


def _checkpoint_uri(result: dict[str, Any]) -> str:
    return str(result.get("checkpoint_path") or result.get("artifact_paths", {}).get("checkpoint_path") or "")


async def _register_detector_candidate(
    session,
    run: AccountModelTrainingRun,
    result: dict[str, Any],
) -> dict[str, Any]:
    from pathlib import Path

    from app.services.account_model_governance_service import register_account_training_result

    artifact_paths = result.get("artifact_paths") or {}
    manifest_path = artifact_paths.get("model_bundle_manifest_path")
    if not manifest_path:
        raise RuntimeError("detector training did not produce an account model bundle manifest")
    bundle_dir = str(Path(manifest_path).resolve().parent)
    candidate = await register_account_training_result(
        session,
        run_id=run.run_id,
        dataset_version_id=str(run.corpus_version_id or ""),
        artifact_uri=bundle_dir,
        metrics=dict(result.get("metrics") or {}),
        operator_id=int(run.created_by),
        encoder_version=str(result.get("encoder_version") or ""),
        encoder_artifact_hash=str(result.get("encoder_artifact_hash") or ""),
    )
    return {**result, "candidate_model": candidate}


async def _register_chinese_social_encoder_version(
    session,
    *,
    training_run: AccountModelTrainingRun,
    result: dict[str, Any],
) -> dict[str, Any]:
    from app.services.account_model_governance_service import register_chinese_social_encoder_version

    encoder = await register_chinese_social_encoder_version(
        session,
        run=training_run,
        training_result=result,
    )
    return {
        **result,
        "encoder_version": encoder["encoder_version"],
        "encoder_artifact_hash": encoder["artifact_hash"],
    }


async def _resolve_governed_detector_config(session, config: dict[str, Any]) -> dict[str, Any]:
    from app.services.account_model_governance_service import resolve_governed_chinese_social_encoder

    return await resolve_governed_chinese_social_encoder(session, config=config)


def _has_governed_detector_binding(config: dict[str, Any]) -> bool:
    """Recognize immutable detector configs created by the service preflight."""

    return all(
        str(config.get(key) or "").strip()
        for key in (
            "encoder_version",
            "encoder_artifact_hash",
            "text_model_path",
            "encoder_binding_payload_path",
        )
    )


def _utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _loads(value: str) -> dict[str, Any]:
    try:
        payload = json.loads(value)
        return payload if isinstance(payload, dict) else {}
    except (TypeError, json.JSONDecodeError):
        return {}
