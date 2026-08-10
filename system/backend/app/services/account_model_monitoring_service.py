"""Persist and query version-bound account-model monitoring snapshots."""

from __future__ import annotations

import json
import hashlib
from datetime import datetime, timedelta, timezone
from typing import Any, Iterable
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.account_model_monitoring import (
    MonitoringThresholds,
    normalize_account_model_hard_error_reason,
    summarize_account_predictions,
)
from app.core.account_labeling import account_scope_key
from app.models.account_labeling import (
    AccountDetectionModelActivation,
    AccountDetectionModelVersion,
    AccountMonitorSnapshot,
    AccountPredictionAudit,
)
from app.utils.exceptions import AppException

__all__ = [
    "account_prediction_input_fingerprint",
    "create_account_monitor_snapshot",
    "list_account_monitor_snapshots",
    "record_account_prediction_audits",
    "record_account_runtime_error",
]

_MODEL_FAMILY = "chinese_account_detection"


async def record_account_prediction_audits(
    session: AsyncSession,
    *,
    posts: Iterable[dict[str, Any]],
    result: dict[str, Any],
    model: Any,
    event_id: str | None,
    platform: str | None,
    latency_ms: float,
) -> int:
    """Persist model-version-bound prediction summaries without raw text."""

    if model is None:
        return 0
    grouped: dict[str, list[dict[str, Any]]] = {}
    for post in posts:
        account_id = str(post.get("author_id") or post.get("user_id") or "").strip()
        if account_id:
            post_platform = str(post.get("platform") or platform or "unknown")
            grouped.setdefault(account_scope_key(post_platform, account_id), []).append(post)
    created = 0
    for row in result.get("accounts") or []:
        account_id = str(row.get("account_id") or "").strip()
        if not account_id:
            continue
        row_platform = str(row.get("platform") or platform or "unknown")
        scoped_posts = grouped.get(account_scope_key(row_platform, account_id), [])
        input_fingerprint = account_prediction_input_fingerprint(scoped_posts)
        audit_id = "account-prediction-" + _canonical_digest(
            (row_platform, account_id, input_fingerprint, model.model_version, model.pointer_revision)
        )[:32]
        exists_row = (
            await session.execute(
                select(AccountPredictionAudit).where(AccountPredictionAudit.audit_id == audit_id)
            )
        ).scalar_one_or_none()
        if exists_row is not None:
            continue
        payload = {
            "event_id": event_id,
            "platform": row_platform or _first_platform(scoped_posts),
            "artifact_hash": str(model.artifact_hash),
            "base_probability": row.get("base_bot_probability"),
            "final_probability": row.get("final_bot_probability"),
            "calibrated_probability": row.get("calibrated_probability"),
            "calibrated": bool(row.get("calibrated")),
            "calibration_source": row.get("calibration_source") or "",
            "prediction": row.get("final_prediction"),
            "routed": bool(row.get("routed", False)),
            "support_evidence": _support_evidence_projection(row.get("support_evidence")),
            "abstained": bool(row.get("abstained", False)),
            "latency_ms": float(latency_ms),
            "hard_error": False,
        }
        session.add(
            AccountPredictionAudit(
                audit_id=audit_id,
                case_id=_case_id(account_id, event_id, row_platform),
                account_id=account_id,
                platform=str(payload["platform"] or "unknown"),
                family=_MODEL_FAMILY,
                model_version=str(model.model_version),
                pointer_revision=int(model.pointer_revision),
                input_fingerprint=input_fingerprint,
                prediction_json=json.dumps(payload, ensure_ascii=False, sort_keys=True),
            )
        )
        created += 1
    if created:
        await session.flush()
    return created


async def record_account_runtime_error(
    session: AsyncSession,
    *,
    posts: Iterable[dict[str, Any]],
    model: Any,
    event_id: str | None,
    platform: str | None,
    latency_ms: float,
    reason: str,
) -> int:
    """Persist one model-version-bound hard error without storing raw content."""

    if model is None:
        return 0
    input_fingerprint = account_prediction_input_fingerprint(posts)
    audit_id = f"account-runtime-error-{uuid4().hex[:24]}"
    payload = {
        "event_id": event_id,
        "platform": platform or "unknown",
        "artifact_hash": str(model.artifact_hash),
        "probability": 0.5,
        "abstained": True,
        "latency_ms": float(latency_ms),
        "hard_error": True,
        "reason_category": normalize_account_model_hard_error_reason(reason),
    }
    session.add(
        AccountPredictionAudit(
            audit_id=audit_id,
            case_id=f"account-runtime-{uuid4().hex[:16]}",
            account_id="__account_model_runtime__",
            platform=str(payload["platform"]),
            family=_MODEL_FAMILY,
            model_version=str(model.model_version),
            pointer_revision=int(model.pointer_revision),
            input_fingerprint=input_fingerprint,
            prediction_json=json.dumps(payload, ensure_ascii=False, sort_keys=True),
        )
    )
    await session.flush()
    return 1


async def create_account_monitor_snapshot(
    session: AsyncSession,
    *,
    window_started_at: datetime,
    window_finished_at: datetime,
    thresholds: MonitoringThresholds | None = None,
    family: str = _MODEL_FAMILY,
) -> dict[str, Any]:
    """Aggregate prediction audits for the current activation and persist one snapshot.

    A snapshot is intentionally bound to the activation revision that generated its
    audits.  This prevents operators from assigning monitoring results to an
    arbitrary candidate model after the fact.
    """

    started_at = _database_time(window_started_at)
    finished_at = _database_time(window_finished_at)
    if finished_at <= started_at:
        raise AppException(code=400, msg="Monitoring window must end after it starts.")

    activation = await _active_pointer(session, family=family)
    model = await _bound_model(session, activation)
    rows = await _prediction_audits(
        session,
        family=family,
        model_version=model.model_version,
        pointer_revision=int(activation.pointer_revision),
        started_at=started_at,
        finished_at=finished_at,
    )
    reference_rows = await _prediction_audits(
        session,
        family=family,
        model_version=model.model_version,
        pointer_revision=int(activation.pointer_revision),
        started_at=started_at - (finished_at - started_at),
        finished_at=started_at,
    )
    summary = summarize_account_predictions(
        _prediction_rows(rows),
        reference_probabilities=_probabilities(reference_rows),
        thresholds=thresholds,
    )
    metrics = {
        **summary,
        "model_identity": {
            "family": family,
            "model_version": model.model_version,
            "artifact_hash": model.artifact_hash,
            "pointer_revision": int(activation.pointer_revision),
        },
        "reference_window": {
            "started_at": (started_at - (finished_at - started_at)).isoformat(),
            "finished_at": started_at.isoformat(),
            "prediction_count": len(reference_rows),
        },
    }
    snapshot = AccountMonitorSnapshot(
        snapshot_id=f"account-monitor-{uuid4().hex[:16]}",
        family=family,
        model_version=model.model_version,
        pointer_revision=int(activation.pointer_revision),
        window_started_at=started_at,
        window_finished_at=finished_at,
        status=str(summary["status"]),
        metrics_json=json.dumps(metrics, ensure_ascii=False, sort_keys=True),
        # MySQL does not always return a server default during flush.  Set this
        # explicitly because the task returns a projection before committing.
        created_at=_database_time(datetime.now(timezone.utc)),
    )
    session.add(snapshot)
    await session.flush()
    return _snapshot_projection(snapshot)


async def list_account_monitor_snapshots(
    session: AsyncSession,
    *,
    family: str = _MODEL_FAMILY,
    limit: int = 20,
) -> list[dict[str, Any]]:
    """Return recent immutable monitoring snapshots, newest first."""

    rows = (
        await session.execute(
            select(AccountMonitorSnapshot)
            .where(AccountMonitorSnapshot.family == family)
            .order_by(AccountMonitorSnapshot.window_finished_at.desc(), AccountMonitorSnapshot.id.desc())
            .limit(limit)
        )
    ).scalars().all()
    return [_snapshot_projection(row) for row in rows]


async def _active_pointer(session: AsyncSession, *, family: str) -> AccountDetectionModelActivation:
    activation = (
        await session.execute(
            select(AccountDetectionModelActivation).where(
                AccountDetectionModelActivation.model_family == family
            )
        )
    ).scalar_one_or_none()
    if activation is None:
        raise AppException(code=409, msg="Account monitoring requires an active model pointer.")
    if int(activation.pointer_revision) < 1:
        raise AppException(code=409, msg="Account monitoring requires a valid active pointer revision.")
    return activation


async def _bound_model(
    session: AsyncSession,
    activation: AccountDetectionModelActivation,
) -> AccountDetectionModelVersion:
    model = (
        await session.execute(
            select(AccountDetectionModelVersion).where(
                AccountDetectionModelVersion.model_version == activation.model_version
            )
        )
    ).scalar_one_or_none()
    if model is None:
        raise AppException(code=409, msg="Account model pointer references a missing model version.")
    if not str(model.artifact_hash).strip():
        raise AppException(code=409, msg="Account monitoring requires a pointer-bound artifact hash.")
    return model


async def _prediction_audits(
    session: AsyncSession,
    *,
    family: str,
    model_version: str,
    pointer_revision: int,
    started_at: datetime,
    finished_at: datetime,
) -> list[AccountPredictionAudit]:
    statement = (
        select(AccountPredictionAudit)
        .where(
            AccountPredictionAudit.family == family,
            AccountPredictionAudit.model_version == model_version,
            AccountPredictionAudit.pointer_revision == pointer_revision,
            AccountPredictionAudit.created_at >= started_at,
            AccountPredictionAudit.created_at < finished_at,
        )
        .order_by(AccountPredictionAudit.created_at.asc(), AccountPredictionAudit.id.asc())
    )
    return list((await session.execute(statement)).scalars().all())


def _prediction_rows(rows: Iterable[AccountPredictionAudit]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for audit in rows:
        payload = _loads(audit.prediction_json)
        probability = payload.get("calibrated_probability", payload.get("probability", 0.5))
        normalized.append(
            {
                "probability": probability,
                "target": payload.get("target"),
                "abstained": payload.get("abstained", payload.get("deferred", False)),
                "latency_ms": payload.get("latency_ms", 0.0),
                "hard_error": payload.get("hard_error", False),
                "hard_error_reason": payload.get("reason_category", payload.get("reason")),
            }
        )
    return normalized


def _probabilities(rows: Iterable[AccountPredictionAudit]) -> list[float]:
    result: list[float] = []
    for row in _prediction_rows(rows):
        if row["hard_error"] or row["abstained"]:
            continue
        try:
            probability = float(row["probability"])
        except (TypeError, ValueError):
            continue
        if 0.0 <= probability <= 1.0:
            result.append(probability)
    return result


def _snapshot_projection(snapshot: AccountMonitorSnapshot) -> dict[str, Any]:
    metrics = _loads(snapshot.metrics_json)
    identity = metrics.get("model_identity") if isinstance(metrics, dict) else {}
    return {
        "snapshot_id": snapshot.snapshot_id,
        "family": snapshot.family,
        "model_version": snapshot.model_version,
        "artifact_hash": identity.get("artifact_hash") if isinstance(identity, dict) else None,
        "pointer_revision": int(snapshot.pointer_revision),
        "window_started_at": _isoformat(snapshot.window_started_at),
        "window_finished_at": _isoformat(snapshot.window_finished_at),
        "status": snapshot.status,
        "metrics": metrics,
        "created_at": _isoformat(snapshot.created_at),
    }


def _database_time(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value
    return value.astimezone(timezone.utc).replace(tzinfo=None)


def _isoformat(value: datetime | None) -> str | None:
    return value.isoformat() if value is not None else None


def _loads(payload: str) -> dict[str, Any]:
    try:
        value = json.loads(payload)
    except (TypeError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def account_prediction_input_fingerprint(posts: Iterable[dict[str, Any]]) -> str:
    """Return the stable model-input fingerprint used by prediction audits."""

    rows = sorted(
        (
            str(post.get("post_id") or post.get("id") or ""),
            str(post.get("timestamp") or ""),
            str(post.get("content") or post.get("text") or ""),
        )
        for post in posts
    )
    return _canonical_digest(rows)


def _support_evidence_projection(value: Any) -> list[dict[str, Any]]:
    """Persist bounded non-text neighbor evidence for account-profile display."""

    if not isinstance(value, list):
        return []
    projected: list[dict[str, Any]] = []
    for row in value[:10]:
        if not isinstance(row, dict):
            continue
        account_id = str(row.get("account_id") or "").strip()
        if not account_id:
            continue
        projected.append(
            {
                "account_id": account_id,
                "similarity": row.get("similarity"),
                "final_bot_probability": row.get("final_bot_probability"),
                "final_prediction": row.get("final_prediction"),
                "routed": bool(row.get("routed", False)),
            }
        )
    return projected


def _canonical_digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()


def _case_id(account_id: str, event_id: str | None, platform: str | None) -> str:
    return "account-detection-case-" + _canonical_digest((account_id, event_id or "", platform or ""))[:16]


def _first_platform(posts: Iterable[dict[str, Any]]) -> str:
    for post in posts:
        value = str(post.get("platform") or "").strip()
        if value:
            return value
    return "unknown"
