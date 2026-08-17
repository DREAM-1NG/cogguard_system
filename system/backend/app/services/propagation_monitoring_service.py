"""Persistence operations for event-level propagation alert disposition."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Mapping

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.analysis import PropagationAlert, PropagationAlertAction, PropagationMonitorProfile


UNRESOLVED_ALERT_STATES = frozenset({"new", "acknowledged"})
ALERT_ACTION_STATES = {"acknowledge": "acknowledged", "close": "closed", "ignore": "ignored"}
DEFAULT_THRESHOLDS = {
    "propagation_surge": {"minimum_new_items": 10, "median_multiplier": 2.0},
    "forecast_scale_jump": {"growth_multiplier": 1.5, "minimum_increment": 20},
    "path_structure_change": {"minimum_depth_increase": 1, "minimum_new_nodes": 10},
    "coordination_spread": {"minimum_group_size": 3},
}

__all__ = [
    "apply_alert_action",
    "get_alert_detail",
    "list_alerts",
    "list_monitor_profiles",
    "unresolved_alert_count",
    "upsert_monitor_profile",
]


def _json_loads(value: str | None, default: Any) -> Any:
    try:
        return json.loads(value) if value else default
    except (TypeError, ValueError):
        return default


def _json_dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)


def _platform(value: str | None) -> str:
    return str(value or "").strip().lower()


def _thresholds(value: Mapping[str, Any] | None) -> dict[str, dict[str, float | int]]:
    merged = {name: dict(item) for name, item in DEFAULT_THRESHOLDS.items()}
    if not isinstance(value, Mapping):
        return merged
    for name, override in value.items():
        if name in merged and isinstance(override, Mapping):
            merged[name].update(override)
    return merged


def _profile_mapping(row: PropagationMonitorProfile) -> dict[str, Any]:
    return {
        "id": row.id,
        "event_id": row.event_id,
        "platform": row.platform or None,
        "enabled": bool(row.enabled),
        "interval_minutes": row.interval_minutes,
        "thresholds": _thresholds(_json_loads(row.thresholds_json, {})),
        "last_snapshot_id": row.last_snapshot_id,
        "last_snapshot": _json_loads(row.last_snapshot_json, {}),
        "last_success_at": row.last_success_at.isoformat() if row.last_success_at else None,
        "last_error": row.last_error,
    }


def _alert_mapping(row: PropagationAlert) -> dict[str, Any]:
    return {
        "id": row.id,
        "event_id": row.event_id,
        "platform": row.platform or None,
        "type": row.alert_type,
        "severity": row.severity,
        "state": row.state,
        "trigger_count": row.trigger_count,
        "first_triggered_at": row.first_triggered_at.isoformat() if row.first_triggered_at else None,
        "last_triggered_at": row.last_triggered_at.isoformat() if row.last_triggered_at else None,
        "snapshot_id": row.snapshot_id,
        "model_version_id": row.model_version_id,
        "assigned_to": row.assigned_to,
        "evidence": _json_loads(row.evidence_json, {}),
        "closed_at": row.closed_at.isoformat() if row.closed_at else None,
    }


def _action_mapping(row: PropagationAlertAction) -> dict[str, Any]:
    return {
        "id": row.id,
        "action": row.action,
        "note": row.note,
        "actor_id": row.actor_id,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


async def _find_profile(db: AsyncSession, *, event_id: str, platform: str | None) -> PropagationMonitorProfile | None:
    statement = select(PropagationMonitorProfile).where(
        PropagationMonitorProfile.event_id == event_id,
        PropagationMonitorProfile.platform == _platform(platform),
    )
    return (await db.execute(statement)).scalar_one_or_none()


async def list_monitor_profiles(db: AsyncSession, *, event_id: str | None = None) -> list[dict[str, Any]]:
    statement = select(PropagationMonitorProfile).order_by(
        PropagationMonitorProfile.event_id.asc(), PropagationMonitorProfile.platform.asc()
    )
    if event_id:
        statement = statement.where(PropagationMonitorProfile.event_id == str(event_id).strip())
    return [_profile_mapping(row) for row in (await db.execute(statement)).scalars().all()]


async def upsert_monitor_profile(*, payload: Mapping[str, Any], updated_by: int, db: AsyncSession) -> dict[str, Any]:
    event_id = str(payload.get("event_id") or "").strip()
    if not event_id:
        raise ValueError("event_id is required")
    interval = int(payload.get("interval_minutes", 5))
    if not 1 <= interval <= 1440:
        raise ValueError("interval_minutes must be between 1 and 1440")
    row = await _find_profile(db, event_id=event_id, platform=payload.get("platform"))
    if row is None:
        row = PropagationMonitorProfile(
            event_id=event_id,
            platform=_platform(payload.get("platform")),
            enabled=bool(payload.get("enabled", True)),
            interval_minutes=interval,
            thresholds_json=_json_dumps(_thresholds(payload.get("thresholds"))),
            updated_by=updated_by,
        )
        db.add(row)
    else:
        row.enabled = bool(payload.get("enabled", row.enabled))
        row.interval_minutes = interval
        row.thresholds_json = _json_dumps(_thresholds(payload.get("thresholds")))
        row.updated_by = updated_by
    await db.flush()
    return _profile_mapping(row)


async def list_alerts(
    db: AsyncSession,
    *,
    event_id: str | None = None,
    platform: str | None = None,
    unresolved_only: bool = False,
    limit: int = 100,
) -> list[dict[str, Any]]:
    statement = select(PropagationAlert).order_by(PropagationAlert.last_triggered_at.desc()).limit(limit)
    if event_id:
        statement = statement.where(PropagationAlert.event_id == str(event_id).strip())
    if platform is not None:
        statement = statement.where(PropagationAlert.platform == _platform(platform))
    if unresolved_only:
        statement = statement.where(PropagationAlert.state.in_(UNRESOLVED_ALERT_STATES))
    return [_alert_mapping(row) for row in (await db.execute(statement)).scalars().all()]


async def unresolved_alert_count(db: AsyncSession) -> int:
    statement = select(func.count(PropagationAlert.id)).where(PropagationAlert.state.in_(UNRESOLVED_ALERT_STATES))
    return int((await db.execute(statement)).scalar_one() or 0)


async def get_alert_detail(db: AsyncSession, *, alert_id: int) -> dict[str, Any]:
    alert = (await db.execute(select(PropagationAlert).where(PropagationAlert.id == alert_id))).scalar_one_or_none()
    if alert is None:
        raise ValueError("Propagation alert not found")
    actions = (await db.execute(
        select(PropagationAlertAction)
        .where(PropagationAlertAction.alert_id == alert.id)
        .order_by(PropagationAlertAction.created_at.asc())
    )).scalars().all()
    result = _alert_mapping(alert)
    result["actions"] = [_action_mapping(action) for action in actions]
    return result


async def apply_alert_action(
    *, alert_id: int, action: str, note: str | None, actor_id: int, db: AsyncSession
) -> dict[str, Any]:
    action = str(action or "").strip().lower()
    if action not in ALERT_ACTION_STATES:
        raise ValueError("action must be acknowledge, close, or ignore")
    alert = (await db.execute(select(PropagationAlert).where(PropagationAlert.id == alert_id))).scalar_one_or_none()
    if alert is None:
        raise ValueError("Propagation alert not found")
    alert.state = ALERT_ACTION_STATES[action]
    if action == "acknowledge":
        alert.assigned_to = actor_id
    if action == "close":
        alert.closed_at = datetime.now(timezone.utc)
    db.add(PropagationAlertAction(alert_id=alert.id, action=action, note=str(note or "").strip() or None, actor_id=actor_id))
    await db.flush()
    return _alert_mapping(alert)
