"""Persistence and orchestration for event-scoped propagation monitoring."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any, Mapping
from uuid import uuid4

from sqlalchemy import and_, func, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.analysis import EventSnapshot, TimeWindow, build_event_snapshot
from app.core.analysis.registry import AnalysisRegistry, SqlAlchemyAnalysisStore
from app.db.mongodb import get_mongo_db
from app.models.analysis import (
    AnalysisModelActivation,
    AnalysisModelVersion,
    PropagationAlert,
    PropagationAlertAction,
    PropagationMonitorProfile,
)
from app.services import coordination_service, propagation_model_service, propagation_observation_service
from app.services.event_data import load_event_comments, load_event_posts
from app.services.propagation_alert_service import (
    ALERT_STATE_LABELS,
    ALERT_TYPE_LABELS,
    DEFAULT_ALERT_THRESHOLDS,
    SEVERITY_LABELS,
    evaluate_alert_signals,
    severity_for_signals,
)


MONITORING_TECHNOLOGY = "propagation_analysis"
DEFAULT_MONITOR_INTERVAL_MINUTES = 5
MONITOR_CLAIM_LEASE_MINUTES = 15
UNRESOLVED_ALERT_STATES = frozenset({"new", "acknowledged"})
MONITORING_OPEN_ALERT_STATES = frozenset({"new", "acknowledged"})
ALERT_ACTION_STATE = {"acknowledge": "acknowledged", "close": "closed", "ignore": "ignored"}

__all__ = [
    "ALERT_ACTION_STATE", "DEFAULT_MONITOR_INTERVAL_MINUTES", "MONITOR_CLAIM_LEASE_MINUTES", "apply_alert_action", "build_monitor_window",
    "get_alert_detail", "get_monitor_profile", "list_alerts", "list_monitor_profiles", "run_due_monitor_profiles",
    "run_monitoring_cycle", "unresolved_alert_count", "upsert_monitor_profile",
]


def _json_loads(value: str | None, default: Any) -> Any:
    try:
        return json.loads(value) if value else default
    except (TypeError, ValueError):
        return default


def _json_dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)


def _as_mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _as_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _as_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def _profile_platform(platform: str | None) -> str:
    return str(platform or "").strip().lower()


def _thresholds(value: Mapping[str, Any] | None) -> dict[str, dict[str, float | int]]:
    merged = {key: dict(item) for key, item in DEFAULT_ALERT_THRESHOLDS.items()}
    for key, item in _as_mapping(value).items():
        if key in merged and isinstance(item, Mapping):
            merged[key].update(item)
    return merged


def build_monitor_window(
    *, current_total_items: int, current_total_nodes: int, previous_snapshot: Mapping[str, Any] | None,
) -> tuple[dict[str, int], list[dict[str, int]]]:
    """Derive current deltas and the three preceding event windows."""
    prior = _as_mapping(previous_snapshot)
    current = {
        "new_items": max(0, int(current_total_items) - _as_int(prior.get("total_items"))),
        "new_propagation_nodes": max(0, int(current_total_nodes) - _as_int(prior.get("total_nodes"))),
    }
    history = [
        {"new_items": max(0, _as_int(item.get("new_items")))}
        for item in prior.get("window_history", [])
        if isinstance(item, Mapping)
    ]
    return current, history[-3:]


async def list_monitor_profiles(db: AsyncSession, *, event_id: str | None = None) -> list[dict[str, Any]]:
    statement = select(PropagationMonitorProfile).order_by(
        PropagationMonitorProfile.event_id.asc(), PropagationMonitorProfile.platform.asc()
    )
    if event_id:
        statement = statement.where(PropagationMonitorProfile.event_id == str(event_id).strip())
    return [_profile_mapping(row) for row in (await db.execute(statement)).scalars().all()]


async def get_monitor_profile(db: AsyncSession, *, event_id: str, platform: str | None) -> dict[str, Any] | None:
    row = await _find_profile(db, event_id=event_id, platform=platform)
    return _profile_mapping(row) if row else None


async def upsert_monitor_profile(*, payload: Mapping[str, Any], updated_by: int, db: AsyncSession) -> dict[str, Any]:
    event_id = str(payload.get("event_id") or "").strip()
    if not event_id:
        raise ValueError("event_id is required for a propagation monitor profile")
    platform = _profile_platform(payload.get("platform"))
    interval_minutes = _as_int(payload.get("interval_minutes"), DEFAULT_MONITOR_INTERVAL_MINUTES)
    if not 1 <= interval_minutes <= 24 * 60:
        raise ValueError("interval_minutes must be between 1 and 1440")
    row = await _find_profile(db, event_id=event_id, platform=platform)
    if row is None:
        row = PropagationMonitorProfile(
            event_id=event_id,
            platform=platform,
            enabled=bool(payload.get("enabled", True)),
            interval_minutes=interval_minutes,
            thresholds_json=_json_dumps(_thresholds(_as_mapping(payload.get("thresholds")))),
            updated_by=updated_by,
        )
        db.add(row)
    else:
        row.enabled = bool(payload.get("enabled", row.enabled))
        row.interval_minutes = interval_minutes
        if "thresholds" in payload:
            row.thresholds_json = _json_dumps(_thresholds(_as_mapping(payload.get("thresholds"))))
        row.updated_by = updated_by
    await db.flush()
    return _profile_mapping(row)


async def list_alerts(
    db: AsyncSession, *, event_id: str | None = None, platform: str | None = None,
    state: str | None = None, unresolved_only: bool = False, limit: int = 100,
) -> list[dict[str, Any]]:
    statement = select(PropagationAlert).order_by(PropagationAlert.last_triggered_at.desc()).limit(limit)
    if event_id:
        statement = statement.where(PropagationAlert.event_id == str(event_id).strip())
    if platform is not None:
        statement = statement.where(PropagationAlert.platform == _profile_platform(platform))
    if state:
        statement = statement.where(PropagationAlert.state == state)
    elif unresolved_only:
        statement = statement.where(PropagationAlert.state.in_(UNRESOLVED_ALERT_STATES))
    return [_alert_mapping(row) for row in (await db.execute(statement)).scalars().all()]


async def unresolved_alert_count(db: AsyncSession) -> int:
    statement = select(func.count(PropagationAlert.id)).where(PropagationAlert.state.in_(UNRESOLVED_ALERT_STATES))
    return int((await db.execute(statement)).scalar_one() or 0)


async def get_alert_detail(db: AsyncSession, *, alert_id: int) -> dict[str, Any]:
    alert = await _get_alert(db, alert_id)
    statement = select(PropagationAlertAction).where(PropagationAlertAction.alert_id == alert.id).order_by(
        PropagationAlertAction.created_at.asc()
    )
    payload = _alert_mapping(alert)
    payload["actions"] = [_action_mapping(row) for row in (await db.execute(statement)).scalars().all()]
    return payload


async def apply_alert_action(
    *, alert_id: int, action: str, note: str | None, actor_id: int, db: AsyncSession,
) -> dict[str, Any]:
    """Transition one alert and retain an immutable analyst action record."""
    action = str(action or "").strip().lower()
    if action not in ALERT_ACTION_STATE:
        raise ValueError("action must be acknowledge, close, or ignore")
    alert = await _get_alert(db, alert_id)
    if str(alert.state or "") in {"closed", "ignored"}:
        raise ValueError("Cannot apply an action to a terminal propagation alert")
    alert.state = ALERT_ACTION_STATE[action]
    if action == "acknowledge":
        alert.assigned_to = actor_id
    if action == "close":
        alert.closed_at = datetime.now(timezone.utc)
        if hasattr(alert, "open_dedupe_key"):
            alert.open_dedupe_key = None
    else:
        alert.closed_at = None
        if action == "ignore" and hasattr(alert, "open_dedupe_key"):
            alert.open_dedupe_key = None
    normalized_note = note.strip() if isinstance(note, str) and note.strip() else None
    db.add(PropagationAlertAction(alert_id=alert.id, action=action, note=normalized_note, actor_id=actor_id))
    await db.flush()
    return _alert_mapping(alert)


async def run_due_monitor_profiles(db: AsyncSession, *, now: datetime | None = None) -> list[dict[str, Any]]:
    """Run only enabled profiles whose configured cadence has elapsed."""
    reference = _as_utc(now) or datetime.now(timezone.utc)
    profiles = (
        await db.execute(
            select(PropagationMonitorProfile)
            .where(PropagationMonitorProfile.enabled.is_(True))
            .order_by(PropagationMonitorProfile.id.asc())
        )
    ).scalars().all()
    results = []
    for candidate in profiles:
        profile = await _claim_due_profile(db, candidate, reference)
        if profile is None:
            continue
        claim_token = profile.claim_token
        commit = getattr(db, "commit", None)
        if commit is not None:
            await commit()
        try:
            results.append(
                await run_monitoring_cycle(
                    profile=profile,
                    db=db,
                    now=reference,
                    claim_token=claim_token,
                )
            )
        finally:
            await _release_profile_claim(db, profile=profile, claim_token=claim_token)
    return results


async def _claim_due_profile(
    db: AsyncSession,
    candidate: PropagationMonitorProfile,
    reference: datetime,
) -> PropagationMonitorProfile | None:
    """Atomically lease a due profile before any external analysis starts."""
    previous_success = _as_utc(candidate.last_success_at)
    due_at = previous_success + timedelta(minutes=candidate.interval_minutes) if previous_success else None
    if due_at is not None and due_at > reference:
        return None

    claim_token = f"monitor_claim_{uuid4().hex}"
    claim_expires_at = reference + timedelta(minutes=MONITOR_CLAIM_LEASE_MINUTES)
    conditions = [
        PropagationMonitorProfile.id == candidate.id,
        PropagationMonitorProfile.enabled.is_(True),
        or_(
            PropagationMonitorProfile.claim_token.is_(None),
            PropagationMonitorProfile.claim_expires_at.is_(None),
            PropagationMonitorProfile.claim_expires_at <= reference,
        ),
    ]
    if candidate.last_success_at is None:
        conditions.append(PropagationMonitorProfile.last_success_at.is_(None))
    else:
        conditions.append(PropagationMonitorProfile.last_success_at == candidate.last_success_at)
    result = await db.execute(
        update(PropagationMonitorProfile)
        .where(and_(*conditions))
        .values(claim_token=claim_token, claim_expires_at=claim_expires_at)
    )
    await db.flush()
    if int(getattr(result, "rowcount", 0) or 0) != 1:
        return None
    candidate.claim_token = claim_token
    candidate.claim_expires_at = claim_expires_at
    return candidate


async def _release_profile_claim(
    db: AsyncSession,
    *,
    profile: PropagationMonitorProfile,
    claim_token: str | None,
) -> None:
    if not claim_token:
        return
    result = await db.execute(
        update(PropagationMonitorProfile)
        .where(
            PropagationMonitorProfile.id == profile.id,
            PropagationMonitorProfile.claim_token == claim_token,
        )
        .values(claim_token=None, claim_expires_at=None)
    )
    await db.flush()
    if int(getattr(result, "rowcount", 0) or 0) == 1:
        profile.claim_token = None
        profile.claim_expires_at = None


async def run_monitoring_cycle(
    *, profile: PropagationMonitorProfile, db: AsyncSession, now: datetime | None = None,
    claim_token: str | None = None,
) -> dict[str, Any]:
    """Capture one event snapshot, evaluate alert rules, and persist evidence."""
    if not profile.enabled:
        return {"profile_id": profile.id, "status": "disabled", "alerts": []}
    if claim_token is not None and profile.claim_token != claim_token:
        return {"profile_id": profile.id, "status": "claim_lost", "alerts": []}
    reference = _as_utc(now) or datetime.now(timezone.utc)
    platform = profile.platform or None
    try:
        observed = await propagation_observation_service.analyze_observed_propagation(
            event_id=profile.event_id, platform=platform, node_limit=300
        )
    except Exception as exc:
        profile.last_error = f"observed_analysis: {type(exc).__name__}: {exc}"
        await db.flush()
        return {"profile_id": profile.id, "status": "failed", "alerts": []}
    if observed.get("error"):
        profile.last_error = str(observed["error"])
        await db.flush()
        return {"profile_id": profile.id, "status": "data_insufficient", "alerts": []}

    prediction = await _safe_prediction(event_id=profile.event_id, platform=platform, observed_until=reference.isoformat())
    coordination = await _safe_coordination(event_id=profile.event_id, platform=platform)
    previous_snapshot = _json_loads(profile.last_snapshot_json, {})
    total_items = _analysis_total_items(observed)
    total_nodes = _analysis_total_nodes(observed)
    current_window, previous_windows = build_monitor_window(
        current_total_items=total_items, current_total_nodes=total_nodes, previous_snapshot=previous_snapshot
    )
    signals = evaluate_alert_signals(
        current_window=current_window,
        previous_windows=previous_windows,
        current_observed_analysis=observed,
        previous_observed_analysis=_as_mapping(previous_snapshot.get("observed_analysis")),
        prediction=prediction,
        coordination=coordination,
        thresholds=_json_loads(profile.thresholds_json, {}),
    )
    active_model = await _active_model(db)
    try:
        snapshot = await _create_event_snapshot(
            db=db, event_id=profile.event_id, platform=platform, observed=observed,
            prediction=prediction, captured_at=reference,
        )
    except Exception as exc:
        profile.last_error = f"snapshot_persist: {type(exc).__name__}: {exc}"
        await db.flush()
        return {"profile_id": profile.id, "status": "failed", "alerts": []}
    evidence = _evidence_snapshot(
        snapshot_id=snapshot.snapshot_id, captured_at=reference, current_window=current_window,
        observed=observed, prediction=prediction, coordination=coordination, signals=signals,
        thresholds=_json_loads(profile.thresholds_json, {}), model=active_model,
    )
    alerts = await _persist_triggered_alerts(
        db=db, event_id=profile.event_id, platform=_profile_platform(platform), signals=signals,
        severity=severity_for_signals(signals), snapshot_id=snapshot.snapshot_id,
        model_version_id=active_model.get("id") if active_model else None, evidence=evidence, now=reference,
    )
    history = [item for item in previous_windows if isinstance(item, Mapping)]
    history.append({"new_items": current_window["new_items"]})
    profile.last_snapshot_id = snapshot.snapshot_id
    profile.last_snapshot_json = _json_dumps({
        "snapshot_id": snapshot.snapshot_id, "captured_at": reference.isoformat(), "total_items": total_items,
        "total_nodes": total_nodes, "observed_analysis": _observed_summary(observed), "window_history": history[-3:],
    })
    profile.last_success_at = reference
    profile.last_error = None
    await db.flush()
    return {"profile_id": profile.id, "status": "ok", "snapshot_id": snapshot.snapshot_id, "alerts": alerts}


async def _safe_prediction(*, event_id: str, platform: str | None, observed_until: str) -> dict[str, Any]:
    try:
        return await propagation_model_service.predict_current_event_model(
            event_id=event_id, platform=platform, observed_until=observed_until
        )
    except Exception as exc:
        return {"status": "model_error", "note": f"prediction: {type(exc).__name__}"}


async def _safe_coordination(*, event_id: str, platform: str | None) -> dict[str, Any]:
    try:
        return await coordination_service.run_coordination_detection(event_id=event_id, platform=platform)
    except Exception as exc:
        return {"error": f"coordination: {type(exc).__name__}", "group_stats": []}


async def _find_profile(db: AsyncSession, *, event_id: str, platform: str | None) -> PropagationMonitorProfile | None:
    statement = select(PropagationMonitorProfile).where(
        PropagationMonitorProfile.event_id == str(event_id).strip(),
        PropagationMonitorProfile.platform == _profile_platform(platform),
    )
    return (await db.execute(statement)).scalar_one_or_none()


async def _get_alert(db: AsyncSession, alert_id: int) -> PropagationAlert:
    statement = select(PropagationAlert).where(PropagationAlert.id == alert_id)
    statement = statement.with_for_update()
    alert = (await db.execute(statement)).scalar_one_or_none()
    if alert is None:
        raise ValueError("Propagation alert not found")
    return alert


async def _active_model(db: AsyncSession) -> dict[str, Any] | None:
    activation = (await db.execute(select(AnalysisModelActivation).where(
        AnalysisModelActivation.technology == MONITORING_TECHNOLOGY
    ))).scalar_one_or_none()
    if activation is None:
        return None
    version = (await db.execute(select(AnalysisModelVersion).where(
        AnalysisModelVersion.id == activation.model_version_id
    ))).scalar_one_or_none()
    if version is None:
        return None
    return {"id": version.id, "name": version.model, "version": version.version, "artifact_hash": version.artifact_hash, "artifact_uri": version.artifact_uri}


async def _create_event_snapshot(
    *, db: AsyncSession, event_id: str, platform: str | None, observed: Mapping[str, Any],
    prediction: Mapping[str, Any], captured_at: datetime,
    posts: list[dict[str, Any]] | None = None,
    comments: list[dict[str, Any]] | None = None,
    mongo_db: Any | None = None,
) -> EventSnapshot:
    """Register a complete EventSnapshot instead of a raw-collection pointer."""
    source_db = mongo_db
    if posts is None or comments is None:
        source_db = source_db or get_mongo_db()
        try:
            if posts is None:
                posts = await load_event_posts(source_db, event_id=event_id, platform=platform)
            if comments is None:
                comments = await load_event_comments(source_db, event_id=event_id, platform=platform)
        except Exception as exc:
            raise RuntimeError("Unable to load raw evidence for monitoring snapshot") from exc
    if source_db is None:
        source_db = get_mongo_db()
    posts = list(posts or [])
    comments = list(comments or [])
    core_window, context_window = _snapshot_windows(posts, comments)
    snapshot = build_event_snapshot(
        event_id=event_id,
        posts=posts,
        comments=comments,
        core_window=core_window,
        context_window=context_window,
    ).model_copy(update={"created_at": _as_utc(captured_at)})
    registry = AnalysisRegistry(mongo_db=source_db, store=SqlAlchemyAnalysisStore(db))
    await registry.register_event_snapshot(snapshot, created_by=0)
    return snapshot


def _snapshot_windows(
    posts: list[Mapping[str, Any]], comments: list[Mapping[str, Any]],
) -> tuple[TimeWindow, TimeWindow]:
    timestamps = [
        timestamp
        for row in [*posts, *comments]
        if (timestamp := _snapshot_timestamp(row.get("timestamp"))) is not None
    ]
    if not timestamps:
        start = datetime(1970, 1, 1, tzinfo=timezone.utc)
        end = start + timedelta(seconds=1)
    else:
        start = min(timestamps)
        end = max(timestamps) + timedelta(microseconds=1)
        if start >= end:
            end = start + timedelta(seconds=1)
    window = TimeWindow(start=start, end=end)
    return window, window.model_copy()


def _snapshot_timestamp(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return _as_utc(value)
    if isinstance(value, (int, float)):
        seconds = float(value) / 1000 if float(value) > 10_000_000_000 else float(value)
        try:
            return datetime.fromtimestamp(seconds, tz=timezone.utc)
        except (OverflowError, OSError, ValueError):
            return None
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return _as_utc(datetime.fromisoformat(text.replace("Z", "+00:00")))
    except ValueError:
        return None


def _snapshot_posts_from_observed(
    observed: Mapping[str, Any], *, event_id: str, platform: str | None,
) -> list[dict[str, Any]]:
    fallback_platform = _profile_platform(platform) or "unknown"
    rows = observed.get("timeline")
    if not isinstance(rows, list):
        return []
    posts: list[dict[str, Any]] = []
    for index, item in enumerate(rows):
        if not isinstance(item, Mapping):
            continue
        row = dict(item)
        row.setdefault("event_id", event_id)
        row.setdefault("platform", fallback_platform)
        row.setdefault("post_id", row.get("id") or f"monitoring:{index}")
        row.setdefault("timestamp", "1970-01-01T00:00:00+00:00")
        posts.append(row)
    return posts


async def _persist_triggered_alerts(
    *, db: AsyncSession, event_id: str, platform: str, signals: list[Mapping[str, Any]], severity: str | None,
    snapshot_id: str, model_version_id: int | None, evidence: Mapping[str, Any], now: datetime,
) -> list[dict[str, Any]]:
    if not signals or severity is None:
        return []
    persisted = []
    for signal in signals:
        alert_type = str(signal.get("type") or "").strip()
        if not alert_type:
            continue
        dedupe_key = f"{event_id}:{platform}:{alert_type}"
        statement = select(PropagationAlert).where(
            PropagationAlert.event_id == event_id,
            PropagationAlert.platform == platform,
            PropagationAlert.alert_type == alert_type,
            PropagationAlert.state.in_(MONITORING_OPEN_ALERT_STATES),
        ).order_by(PropagationAlert.last_triggered_at.desc())
        existing = next(iter((await db.execute(statement)).scalars().all()), None)
        item_evidence = {**_as_mapping(evidence), "trigger_signal": _as_mapping(signal)}
        if existing is None:
            existing = await _insert_alert_with_dedupe(
                db=db,
                event_id=event_id,
                platform=platform,
                alert_type=alert_type,
                dedupe_key=dedupe_key,
                severity=severity,
                snapshot_id=snapshot_id,
                model_version_id=model_version_id,
                evidence=item_evidence,
                now=now,
            )
        else:
            existing.severity = severity
            existing.trigger_count += 1
            existing.last_triggered_at = now
            existing.snapshot_id = snapshot_id
            existing.model_version_id = model_version_id
            existing.evidence_json = _json_dumps(item_evidence)
            existing.open_dedupe_key = dedupe_key
            await db.flush()
        persisted.append(_alert_mapping(existing))
    return persisted


async def _insert_alert_with_dedupe(
    *,
    db: AsyncSession,
    event_id: str,
    platform: str,
    alert_type: str,
    dedupe_key: str,
    severity: str,
    snapshot_id: str,
    model_version_id: int | None,
    evidence: Mapping[str, Any],
    now: datetime,
) -> PropagationAlert:
    candidate = PropagationAlert(
        event_id=event_id,
        platform=platform,
        alert_type=alert_type,
        severity=severity,
        state="new",
        dedupe_key=dedupe_key,
        open_dedupe_key=dedupe_key,
        trigger_count=1,
        first_triggered_at=now,
        last_triggered_at=now,
        snapshot_id=snapshot_id,
        model_version_id=model_version_id,
        evidence_json=_json_dumps(evidence),
    )
    begin_nested = getattr(db, "begin_nested", None)
    if begin_nested is None:
        db.add(candidate)
        await db.flush()
        return candidate
    try:
        async with db.begin_nested():
            db.add(candidate)
            await db.flush()
    except IntegrityError:
        existing = (
            await db.execute(
                select(PropagationAlert).where(
                    PropagationAlert.open_dedupe_key == dedupe_key,
                )
            )
        ).scalar_one_or_none()
        if existing is None:
            raise
        existing.severity = severity
        existing.trigger_count += 1
        existing.last_triggered_at = now
        existing.snapshot_id = snapshot_id
        existing.model_version_id = model_version_id
        existing.evidence_json = _json_dumps(evidence)
        await db.flush()
        return existing
    return candidate


def _analysis_total_items(observed: Mapping[str, Any]) -> int:
    scope = _as_mapping(observed.get("data_scope"))
    return max(0, _as_int(scope.get("posts"))) + max(0, _as_int(scope.get("comments")))


def _analysis_total_nodes(observed: Mapping[str, Any]) -> int:
    meta = _as_mapping(_as_mapping(observed.get("diffusion_summary")).get("meta"))
    if meta:
        return max(0, _as_int(meta.get("total_nodes", meta.get("visible_node_count"))))
    graph = _as_mapping(observed.get("graph"))
    nodes = graph.get("nodes")
    return len(nodes) if isinstance(nodes, list) else 0


def _observed_summary(observed: Mapping[str, Any]) -> dict[str, Any]:
    diffusion = _as_mapping(observed.get("diffusion_summary"))
    return {
        "data_scope": _as_mapping(observed.get("data_scope")), "diffusion_meta": _as_mapping(diffusion.get("meta")),
        "path_analysis": _as_mapping(observed.get("path_analysis")), "evidence_chains": list(observed.get("evidence_chains") or [])[:5],
        "timeline": list(observed.get("timeline") or [])[:10],
    }


def _evidence_snapshot(
    *, snapshot_id: str, captured_at: datetime, current_window: Mapping[str, Any], observed: Mapping[str, Any],
    prediction: Mapping[str, Any], coordination: Mapping[str, Any], signals: list[Mapping[str, Any]],
    thresholds: Mapping[str, Any], model: Mapping[str, Any] | None,
) -> dict[str, Any]:
    macro, micro = _as_mapping(prediction.get("macro")), _as_mapping(prediction.get("micro"))
    return {
        "snapshot_id": snapshot_id, "captured_at": captured_at.isoformat(), "thresholds": _thresholds(thresholds),
        "window": dict(current_window), "signals": [dict(signal) for signal in signals], "observed": _observed_summary(observed),
        "prediction": {"status": prediction.get("status"), "macro": {"observed_size": macro.get("observed_size"), "predicted_size": macro.get("predicted_size"), "trend_points": list(macro.get("trend_points") or [])}, "top_users": list(micro.get("top_users") or [])[:10], "data_scope": _as_mapping(prediction.get("data_scope"))},
        "coordination": {"summary": _as_mapping(coordination.get("summary")), "group_stats": list(coordination.get("group_stats") or [])[:10]},
        "model": dict(model) if model else None,
    }


def _profile_mapping(row: PropagationMonitorProfile) -> dict[str, Any]:
    return {
        "id": row.id, "event_id": row.event_id, "platform": row.platform or None, "enabled": bool(row.enabled),
        "interval_minutes": row.interval_minutes, "thresholds": _thresholds(_json_loads(row.thresholds_json, {})),
        "last_snapshot_id": row.last_snapshot_id, "last_snapshot": _json_loads(row.last_snapshot_json, {}),
        "last_success_at": _iso(row.last_success_at), "last_error": row.last_error, "updated_by": row.updated_by,
    }


def _alert_mapping(row: PropagationAlert) -> dict[str, Any]:
    return {
        "id": row.id, "event_id": row.event_id, "platform": row.platform or None, "alert_type": row.alert_type,
        "alert_type_label": ALERT_TYPE_LABELS.get(row.alert_type, row.alert_type), "severity": row.severity,
        "severity_label": SEVERITY_LABELS.get(row.severity, row.severity), "state": row.state,
        "state_label": ALERT_STATE_LABELS.get(row.state, row.state), "trigger_count": row.trigger_count,
        "first_triggered_at": _iso(row.first_triggered_at), "last_triggered_at": _iso(row.last_triggered_at),
        "snapshot_id": row.snapshot_id, "model_version_id": row.model_version_id, "assigned_to": row.assigned_to,
        "evidence": _json_loads(row.evidence_json, {}), "closed_at": _iso(row.closed_at),
    }


def _action_mapping(row: PropagationAlertAction) -> dict[str, Any]:
    return {"id": row.id, "alert_id": row.alert_id, "action": row.action, "note": row.note, "actor_id": row.actor_id, "created_at": _iso(row.created_at)}


def _iso(value: datetime | None) -> str | None:
    normalized = _as_utc(value)
    return normalized.isoformat() if normalized else None
