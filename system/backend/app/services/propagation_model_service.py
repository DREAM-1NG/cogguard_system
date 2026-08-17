"""Propagation prediction model orchestration service.

This service owns future trend and next-hop prediction for event-scoped
propagation data. Observed path reconstruction belongs in
``propagation_observation_service`` instead.
"""

from __future__ import annotations

import asyncio
import logging
import math
from datetime import datetime, timedelta, timezone
from typing import Any

from pydantic import ValidationError

from app.db.mongodb import get_mongo_db
from app.schemas.propagation import EventTimelineProjection, PropagationPredictionData
from app.services.event_data import (
    analysis_scope_metadata,
    event_data_fingerprint,
    load_event_comments,
    load_event_posts,
)
from app.services import propagation_prediction_service


logger = logging.getLogger(__name__)

PREDICTION_EVENT_DATA_TIMEOUT_SECONDS = 15.0
PREDICTION_CACHE_COLLECTION = "propagation_prediction_cache_v1"


PREDICTION_MODEL_CAPABILITY = {
    "name": "macro_micro_sequence_propagation_prediction",
    "type": "macro_micro_prediction",
    "boundary": "future_trend_and_next_hop_prediction",
    "predicts_future": True,
}

SUPPORTED_CHECKPOINT_OBSERVATION_RATIOS = (0.1, 0.3, 0.5)
MAX_CUMULATIVE_TIMELINE_POINTS = 24
ACTIVE_TIMELINE_WINDOW = timedelta(hours=6)
TIMELINE_RANGE_SPANS = {
    "24h": timedelta(hours=24),
    "7d": timedelta(days=7),
}
TIMELINE_RESOLUTIONS = {
    "active": "minute",
    "24h": "hour",
    "7d": "day",
    "all": "week",
}


def _prediction_cache_filter(
    *,
    event_id: str,
    platform: str | None,
    observed_until: str | None,
    observation_ratio: float,
    top_k: int,
) -> dict[str, Any]:
    return {
        "event_id": event_id,
        "platform": platform or "",
        "observed_until": observed_until or "",
        "observation_ratio": round(float(observation_ratio), 4),
        "top_k": int(top_k),
    }


def _prediction_cache_collection(mongo_db: Any) -> Any:
    if mongo_db is None:
        return None
    if isinstance(mongo_db, dict):
        return mongo_db.get(PREDICTION_CACHE_COLLECTION)
    return mongo_db[PREDICTION_CACHE_COLLECTION]


async def read_cached_current_event_prediction(
    *,
    event_id: str,
    platform: str | None,
    observed_until: str | None,
    observation_ratio: float,
    top_k: int,
) -> dict[str, Any]:
    """Return the latest event prediction without invoking the model runtime."""

    try:
        mongo_db = get_mongo_db()
    except Exception:
        logger.exception("MongoDB is unavailable while reading propagation prediction cache")
        mongo_db = None
    collection = _prediction_cache_collection(mongo_db)
    if collection is None:
        result = empty_prediction_result(event_id, platform)
        result.update({"status": "cache_miss", "note": "No cached prediction is available for this event."})
        result["cache"] = {"hit": False, "stale": False}
        return enforce_prediction_contract(result, event_id=event_id, platform=platform)

    cache_filter = _prediction_cache_filter(
        event_id=event_id,
        platform=platform,
        observed_until=observed_until,
        observation_ratio=observation_ratio,
        top_k=top_k,
    )
    try:
        document = await collection.find_one(cache_filter, {"_id": 0})
    except TypeError:
        document = await collection.find_one(cache_filter)
    except Exception:
        logger.exception("Unable to read propagation prediction cache for event_id=%r", event_id)
        document = None
    if not isinstance(document, dict) or not isinstance(document.get("result"), dict):
        result = empty_prediction_result(event_id, platform)
        result.update({"status": "cache_miss", "note": "No cached prediction is available for this event."})
        result["cache"] = {"hit": False, "stale": False}
        return enforce_prediction_contract(result, event_id=event_id, platform=platform)

    try:
        current_fingerprint = await event_data_fingerprint(mongo_db, event_id=event_id, platform=platform)
    except Exception:
        current_fingerprint = None
    result = dict(document["result"])
    result["cache"] = {
        "hit": True,
        "stale": bool(not current_fingerprint or current_fingerprint != document.get("snapshot_fingerprint")),
        "snapshot_fingerprint": document.get("snapshot_fingerprint"),
        "generated_at": document.get("generated_at"),
    }
    return enforce_prediction_contract(result, event_id=event_id, platform=platform)


async def store_cached_current_event_prediction(
    result: dict[str, Any],
    *,
    event_id: str,
    platform: str | None,
    observed_until: str | None,
    observation_ratio: float,
    top_k: int,
    snapshot_fingerprint: str | None,
) -> None:
    """Persist a successful event prediction for a matching observation snapshot."""

    if result.get("status") != "ok":
        return
    try:
        mongo_db = get_mongo_db()
    except Exception:
        logger.exception("MongoDB is unavailable while storing propagation prediction cache")
        return
    collection = _prediction_cache_collection(mongo_db)
    if collection is None:
        return
    cache_filter = _prediction_cache_filter(
        event_id=event_id,
        platform=platform,
        observed_until=observed_until,
        observation_ratio=observation_ratio,
        top_k=top_k,
    )
    document = {
        **cache_filter,
        "snapshot_fingerprint": snapshot_fingerprint,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "result": {key: value for key, value in result.items() if key != "cache"},
    }
    try:
        await collection.update_one(cache_filter, {"$set": document}, upsert=True)
    except Exception:
        logger.exception("Unable to store propagation prediction cache for event_id=%r", event_id)


def empty_prediction_result(event_id: str | None, platform: str | None) -> dict:
    data_scope = analysis_scope_metadata(
        event_id=event_id,
        platform=platform,
        posts_count=0,
        comments_count=0,
    )
    data_scope.update({"event_id": event_id, "platform": platform})
    return {
        "status": "data_insufficient",
        "model_status": "unavailable",
        "note": "No timestamped observed posts are available for model inference.",
        "event_id": event_id,
        "platform": platform,
        "macro": {
            "observed_size": 0,
            "predicted_size": None,
            "trend_points": [],
            "observed_points": [],
            "realized_points": [],
            "intervals": None,
            "direction": None,
            "score_concentration": None,
            "calibration_status": "unavailable",
        },
        "micro": {
            "top_users": [],
            "candidate_count": 0,
            "candidate_bucket_count": 0,
            "candidate_source_counts": {},
            "reactivation_count": 0,
            "new_activation_count": 0,
            "coverage": {
                "mapped_candidate_buckets": 0,
                "unmapped_candidate_buckets": 0,
                "legal_candidate_buckets": 0,
                "mapped_probability_mass": 0.0,
                "new_activation_status": "abstain_no_identity_mapping",
            },
        },
        "capability": dict(PREDICTION_MODEL_CAPABILITY),
        "data_scope": data_scope,
    }


def nearest_checkpoint_observation_ratio(actual_ratio: float) -> float:
    """Select the checkpoint condition nearest to the real timestamp-cut prefix."""
    return min(
        SUPPORTED_CHECKPOINT_OBSERVATION_RATIOS,
        key=lambda supported: (abs(float(actual_ratio) - supported), supported),
    )


def normalize_prediction_result(
    result: Any,
    *,
    event_id: str | None,
    platform: str | None,
    observed_size: int,
) -> dict:
    """Keep adapter failures inside the public prediction response contract."""

    if not isinstance(result, dict) or not isinstance(result.get("macro"), dict) or not isinstance(result.get("micro"), dict):
        normalized = empty_prediction_result(event_id, platform)
        normalized["status"] = "model_error"
        normalized["note"] = "The propagation model returned an invalid result."
        normalized["macro"]["observed_size"] = observed_size
        return normalized

    normalized = dict(result)
    normalized.setdefault("status", "model_error")
    normalized["model_status"] = "available" if normalized["status"] == "ok" else "unavailable"
    return normalized


def enforce_prediction_contract(
    result: Any,
    *,
    event_id: str | None = None,
    platform: str | None = None,
) -> dict:
    """Validate nested model output before FastAPI response serialization."""

    try:
        return PropagationPredictionData.model_validate(result).model_dump(mode="json")
    except ValidationError as exc:
        logger.warning("Invalid propagation prediction contract; returning abstain: %s", exc)

    source = result if isinstance(result, dict) else {}
    source_macro = source.get("macro") if isinstance(source.get("macro"), dict) else {}
    try:
        observed_size = max(0, int(source_macro.get("observed_size", 0)))
    except (TypeError, ValueError):
        observed_size = 0

    fallback = empty_prediction_result(
        event_id if event_id is not None else source.get("event_id"),
        platform if platform is not None else source.get("platform"),
    )
    fallback["status"] = "model_error"
    fallback["model_status"] = "unavailable"
    fallback["note"] = "The propagation model returned an invalid result."
    fallback["macro"]["observed_size"] = observed_size

    if isinstance(source.get("data_scope"), dict):
        fallback["data_scope"] = dict(source["data_scope"])
    for key in ("capability", "methodology", "prediction_boundary"):
        if isinstance(source.get(key), dict):
            fallback[key] = dict(source[key])

    return PropagationPredictionData.model_validate(fallback).model_dump(mode="json")


def filter_rows_until(rows: list[dict[str, Any]], observed_until: str | None) -> list[dict[str, Any]]:
    """Keep only rows with a parseable timestamp at or before the cutoff."""
    cutoff = validate_observed_until(observed_until)
    if cutoff is None:
        return list(rows)
    return [row for row in rows if (timestamp := _row_timestamp(row)) is not None and timestamp <= cutoff]


def validate_observed_until(observed_until: str | None) -> datetime | None:
    """Validate the public observation boundary before any database or model work."""
    if observed_until is None or not str(observed_until).strip():
        return None
    cutoff = _parse_timestamp(observed_until, require_timezone=True)
    if cutoff is None:
        raise ValueError("observed_until must be a timezone-aware ISO-8601 timestamp")
    return cutoff


def _row_timestamp(row: dict[str, Any]) -> datetime | None:
    for field in ("timestamp", "created_at", "publish_time", "published_at", "time"):
        parsed = _parse_timestamp(row.get(field))
        if parsed is not None:
            return parsed
    return None


def _parse_timestamp(value: Any, *, require_timezone: bool = False) -> datetime | None:
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(float(value), tz=timezone.utc)
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if require_timezone and parsed.tzinfo is None:
        return None
    return (parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)).astimezone(timezone.utc)


def _timeline_event_records(posts: list[dict[str, Any]], comments: list[dict[str, Any]]) -> list[datetime]:
    """Return the same timestamped, authored event rows accepted by checkpoint inference."""

    records: list[tuple[datetime, int]] = []
    for index, row in enumerate([*posts, *comments]):
        author_id = str(row.get("author_id") or row.get("user_id") or row.get("account_id") or row.get("uid") or "").strip()
        timestamp = _row_timestamp(row)
        if author_id and timestamp is not None:
            records.append((timestamp, index))
    return [timestamp for timestamp, _index in sorted(records, key=lambda item: (item[0], item[1]))]


def _partition_timeline_records(
    records: list[datetime],
    *,
    observed_until: str | None,
    observation_ratio: float,
) -> tuple[list[datetime], list[datetime]]:
    """Partition evidence at the exact observation boundary without exposing holdout rows to inference."""

    if observed_until is not None:
        cutoff = validate_observed_until(observed_until)
        if cutoff is not None:
            return [timestamp for timestamp in records if timestamp <= cutoff], [timestamp for timestamp in records if timestamp > cutoff]

    observation_count = max(1, min(len(records), int(math.ceil(len(records) * float(observation_ratio))))) if records else 0
    return records[:observation_count], records[observation_count:]


def _cumulative_timeline_points(
    records: list[datetime],
    *,
    initial_size: int = 0,
    initial_at: datetime | None = None,
) -> list[dict[str, Any]]:
    """Downsample timestamped evidence into bounded, equally spaced cumulative windows."""

    points: list[dict[str, Any]] = []
    if initial_at is not None:
        points.append({"at": initial_at.isoformat(), "cumulative_size": int(initial_size)})
    if not records:
        return points

    start, end = records[0], records[-1]
    bucket_count = min(MAX_CUMULATIVE_TIMELINE_POINTS, len(records))
    if start == end:
        terminal = {"at": end.isoformat(), "cumulative_size": int(initial_size) + len(records)}
        if points and points[-1]["at"] == terminal["at"]:
            points[-1] = terminal
        else:
            points.append(terminal)
        return points

    span_seconds = (end - start).total_seconds()
    record_index = 0
    for bucket_index in range(1, bucket_count + 1):
        bucket_end = end if bucket_index == bucket_count else start + timedelta(seconds=span_seconds * bucket_index / bucket_count)
        while record_index < len(records) and records[record_index] <= bucket_end:
            record_index += 1
        point = {"at": bucket_end.isoformat(), "cumulative_size": int(initial_size) + record_index}
        if points and points[-1]["at"] == point["at"]:
            points[-1] = point
        else:
            points.append(point)
    return points


def _bucket_floor(timestamp: datetime, resolution: str) -> datetime:
    if resolution == "minute":
        return timestamp.replace(second=0, microsecond=0)
    if resolution == "hour":
        return timestamp.replace(minute=0, second=0, microsecond=0)
    if resolution == "day":
        return timestamp.replace(hour=0, minute=0, second=0, microsecond=0)
    week_start = timestamp - timedelta(days=timestamp.weekday())
    return week_start.replace(hour=0, minute=0, second=0, microsecond=0)


def _bucket_step(resolution: str) -> timedelta:
    return {
        "minute": timedelta(minutes=1),
        "hour": timedelta(hours=1),
        "day": timedelta(days=1),
        "week": timedelta(weeks=1),
    }[resolution]


def _densest_timeline_window(records: list[datetime]) -> tuple[datetime, datetime] | None:
    if not records:
        return None
    left = 0
    best_left = 0
    best_right = 0
    for right, timestamp in enumerate(records):
        while timestamp - records[left] > ACTIVE_TIMELINE_WINDOW:
            left += 1
        if right - left > best_right - best_left:
            best_left, best_right = left, right
    start = records[best_left]
    end = min(start + ACTIVE_TIMELINE_WINDOW, records[-1])
    return start, max(start, end)


def _timeline_window_for_range(
    records: list[datetime],
    active_window: tuple[datetime, datetime] | None,
    timeline_range: str,
) -> tuple[datetime, datetime] | None:
    if not records:
        return None
    if timeline_range == "all":
        return records[0], records[-1]
    if active_window is None:
        return records[0], records[-1]
    if timeline_range == "active":
        return active_window
    span = TIMELINE_RANGE_SPANS[timeline_range]
    end = active_window[1]
    return max(records[0], end - span), end


def _window_dict(window: tuple[datetime, datetime] | None) -> dict[str, str] | None:
    if window is None:
        return None
    return {"start": window[0].isoformat(), "end": window[1].isoformat()}


def _project_cumulative_series(
    records: list[datetime],
    *,
    window: tuple[datetime, datetime],
    resolution: str,
    initial_size: int = 0,
    anchor_at: datetime | None = None,
) -> list[dict[str, Any]]:
    if not records:
        return []
    window_start, window_end = window
    if window_end < records[0] or window_start > records[-1]:
        return []
    series_start = max(window_start, anchor_at or records[0])
    series_end = min(window_end, records[-1])
    if series_end < series_start:
        return []

    start_bucket = _bucket_floor(series_start, resolution)
    end_bucket = _bucket_floor(series_end, resolution)
    step = _bucket_step(resolution)
    record_index = 0
    while record_index < len(records) and records[record_index] < start_bucket:
        record_index += 1
    cumulative = initial_size + record_index
    points: list[dict[str, Any]] = []
    bucket = start_bucket
    while bucket <= end_bucket:
        bucket_end = bucket + step
        while record_index < len(records) and records[record_index] < bucket_end:
            record_index += 1
        cumulative = initial_size + record_index
        points.append({"at": bucket.isoformat(), "cumulative_size": cumulative})
        bucket = bucket_end
    return points


async def build_current_event_timeline(
    *,
    event_id: str,
    platform: str | None = None,
    timeline_range: str = "active",
    observation_ratio: float = 0.5,
) -> dict[str, Any]:
    """Build a range-scoped evidence timeline without invoking checkpoint inference."""

    if timeline_range not in TIMELINE_RESOLUTIONS:
        raise ValueError("timeline_range must be one of active, 24h, 7d, or all")
    posts, comments = await _load_prediction_event_data(event_id=event_id, platform=platform)
    records = _timeline_event_records(posts, comments)
    active_window = _densest_timeline_window(records)
    window = _timeline_window_for_range(records, active_window, timeline_range)
    resolution = TIMELINE_RESOLUTIONS[timeline_range]
    if window is None:
        return EventTimelineProjection(
            range=timeline_range,
            resolution=resolution,
            active_window=None,
            window=None,
        ).model_dump(mode="json")

    observed_records, realized_records = _partition_timeline_records(
        records,
        observed_until=None,
        observation_ratio=observation_ratio,
    )
    observed_points = _project_cumulative_series(
        observed_records,
        window=window,
        resolution=resolution,
    )
    realized_anchor = observed_records[-1] if observed_records else None
    realized_points = _project_cumulative_series(
        realized_records,
        window=window,
        resolution=resolution,
        initial_size=len(observed_records),
        anchor_at=realized_anchor,
    )
    return EventTimelineProjection(
        range=timeline_range,
        resolution=resolution,
        active_window=_window_dict(active_window),
        window=_window_dict(window),
        observed_points=observed_points,
        realized_points=realized_points,
    ).model_dump(mode="json")


def attach_prediction_scope(
    result: dict,
    *,
    event_id: str | None,
    platform: str | None,
    posts_count: int,
    comments_count: int,
    observed_until: str | None = None,
    observation_ratio: float = 0.5,
    excluded_posts: int = 0,
    excluded_comments: int = 0,
) -> dict:
    result["event_id"] = event_id
    result["platform"] = platform
    result["capability"] = dict(PREDICTION_MODEL_CAPABILITY)
    result["data_scope"] = analysis_scope_metadata(
        event_id=event_id,
        platform=platform,
        posts_count=posts_count,
        comments_count=comments_count,
    )
    result["data_scope"].update(
        {
            "event_id": event_id,
            "platform": platform,
            "observed_until": observed_until,
            "prediction_horizon_hours": None,
            "trajectory_time_basis": "normalized_model_steps",
            "observation_ratio": float(observation_ratio),
            "excluded_after_cutoff": {"posts": int(excluded_posts), "comments": int(excluded_comments)},
        }
    )
    return result


async def _load_prediction_event_data(
    *,
    event_id: str | None,
    platform: str | None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    mongo_db = get_mongo_db()
    posts = await load_event_posts(mongo_db, event_id=event_id, platform=platform)
    comments = await load_event_comments(mongo_db, event_id=event_id, platform=platform)
    return posts, comments


async def predict_current_event_model(
    platform: str | None = None,
    event_id: str | None = None,
    *,
    top_k: int = 10,
    observed_until: str | None = None,
    observation_ratio: float = 0.5,
) -> dict:
    """Run the macro/micro prediction model over current event-scoped data."""
    event_id = str(event_id or "").strip()
    if not event_id:
        result = empty_prediction_result(None, platform)
        result["status"] = "invalid_scope"
        result["note"] = "A non-empty event_id is required for current-event prediction."
        result = attach_prediction_scope(
            result,
            event_id=None,
            platform=platform,
            posts_count=0,
            comments_count=0,
            observed_until=observed_until,
            observation_ratio=observation_ratio,
        )
        return enforce_prediction_contract(result, event_id=None, platform=platform)

    platform = str(platform).strip().lower() if platform is not None and str(platform).strip() else None
    effective_observation_ratio = observation_ratio
    try:
        mongo_db = get_mongo_db()
    except Exception:
        logger.exception("MongoDB is unavailable while preparing propagation prediction")
        mongo_db = None
    try:
        snapshot_fingerprint = (
            await event_data_fingerprint(mongo_db, event_id=event_id, platform=platform)
            if mongo_db is not None
            else None
        )
    except Exception:
        snapshot_fingerprint = None
    try:
        posts, comments = await asyncio.wait_for(
            _load_prediction_event_data(event_id=event_id, platform=platform),
            timeout=PREDICTION_EVENT_DATA_TIMEOUT_SECONDS,
        )
    except Exception:
        logger.exception(
            "Propagation event data is unavailable for event_id=%r platform=%r",
            event_id,
            platform,
        )
        result = empty_prediction_result(event_id, platform)
        result["status"] = "data_unavailable"
        result["note"] = "The current event data is temporarily unavailable."
        result = attach_prediction_scope(
            result,
            event_id=event_id,
            platform=platform,
            posts_count=0,
            comments_count=0,
            observed_until=observed_until,
            observation_ratio=effective_observation_ratio,
        )
        return enforce_prediction_contract(result, event_id=event_id, platform=platform)

    if not posts and not comments:
        return attach_prediction_scope(
            empty_prediction_result(event_id, platform),
            event_id=event_id,
            platform=platform,
            posts_count=0,
            comments_count=0,
            observed_until=observed_until,
            observation_ratio=effective_observation_ratio,
        )

    source_event_count = sum(1 for row in [*posts, *comments] if _row_timestamp(row) is not None)
    observed_posts = filter_rows_until(posts, observed_until)
    observed_comments = filter_rows_until(comments, observed_until)
    if not observed_posts and not observed_comments:
        result = empty_prediction_result(event_id, platform)
        result["status"] = "data_insufficient"
        result["model_status"] = "unavailable"
        return attach_prediction_scope(
            result,
            event_id=event_id,
            platform=platform,
            posts_count=0,
            comments_count=0,
            observed_until=observed_until,
            observation_ratio=effective_observation_ratio,
            excluded_posts=len(posts),
            excluded_comments=len(comments),
        )
    if observed_until is not None and source_event_count > 0:
        cutoff_event_count = sum(
            1 for row in [*observed_posts, *observed_comments] if _row_timestamp(row) is not None
        )
        effective_observation_ratio = nearest_checkpoint_observation_ratio(
            float(cutoff_event_count) / float(source_event_count)
        )
    timeline_records = _timeline_event_records(posts, comments)
    timeline_observed_records, timeline_realized_records = _partition_timeline_records(
        timeline_records,
        observed_until=observed_until,
        observation_ratio=effective_observation_ratio,
    )
    try:
        prediction_kwargs = {
            "posts": observed_posts,
            "comments": observed_comments,
            "top_k": top_k,
            "observation_ratio": effective_observation_ratio,
        }
        if observed_until is not None:
            prediction_kwargs["prefix_is_preselected"] = True
        result = await propagation_prediction_service.predict_event_macro_micro(**prediction_kwargs)
    except Exception:
        logger.exception(
            "Propagation model inference failed for event_id=%r platform=%r",
            event_id,
            platform,
        )
        result = empty_prediction_result(event_id, platform)
        result["status"] = "model_error"
        result["note"] = "The propagation model is temporarily unavailable for this event."
        result["macro"]["observed_size"] = len(observed_posts) + len(observed_comments)
    result = normalize_prediction_result(
        result,
        event_id=event_id,
        platform=platform,
        observed_size=len(observed_posts) + len(observed_comments),
    )
    inference_scope = result.get("inference_scope") if isinstance(result.get("inference_scope"), dict) else {}
    effective_cutoff = (
        observed_until
        or inference_scope.get("observed_until")
        or _latest_observed_timestamp([*observed_posts, *observed_comments])
    )
    result.setdefault(
        "methodology",
        propagation_prediction_service.prediction_methodology(
            source="current_event_service",
            protocol={
                "top_k": top_k,
                "observed_until": observed_until,
                "checkpoint_conditioning_ratio": effective_observation_ratio,
                "trajectory_time_basis": "normalized_model_steps",
            },
        ),
    )
    result["prediction_boundary"] = {
        "method": "macro_micro_sequence_model",
        "is_primary_model": True,
        "observed_input_only": True,
        "legacy_speed_acceleration_scaffold": "removed_from_public_prediction_api",
    }

    scoped_result = attach_prediction_scope(
        result,
        event_id=event_id,
        platform=platform,
        posts_count=len(observed_posts),
        comments_count=len(observed_comments),
        observed_until=effective_cutoff,
        observation_ratio=effective_observation_ratio,
        excluded_posts=len(posts) - len(observed_posts),
        excluded_comments=len(comments) - len(observed_comments),
    )
    model_input_event_count = int(
        inference_scope.get("loaded_event_count", len(observed_posts) + len(observed_comments))
    )
    model_observed_event_count = int(
        inference_scope.get(
            "observed_event_count",
            scoped_result.get("macro", {}).get("observed_size", 0),
        )
    )
    actual_observation_ratio = (
        float(model_observed_event_count) / float(source_event_count)
        if source_event_count > 0
        else 0.0
    )
    scoped_result["data_scope"].update(
        {
            "loaded_event_count": source_event_count,
            "model_input_event_count": model_input_event_count,
            "model_observed_event_count": model_observed_event_count,
            "observation_ratio": actual_observation_ratio,
            "actual_observation_ratio": actual_observation_ratio,
            "checkpoint_conditioning_ratio": float(effective_observation_ratio),
            "prefix_selection": "timestamp_cutoff" if observed_until is not None else "observation_ratio",
        }
    )
    macro = scoped_result.setdefault("macro", {})
    macro["observed_points"] = _cumulative_timeline_points(timeline_observed_records)
    macro["realized_points"] = _cumulative_timeline_points(
        timeline_realized_records,
        initial_size=len(timeline_observed_records),
        initial_at=timeline_observed_records[-1] if timeline_observed_records else None,
    )
    normalized = enforce_prediction_contract(scoped_result, event_id=event_id, platform=platform)
    await store_cached_current_event_prediction(
        normalized,
        event_id=event_id,
        platform=platform,
        observed_until=observed_until,
        observation_ratio=observation_ratio,
        top_k=top_k,
        snapshot_fingerprint=snapshot_fingerprint,
    )
    normalized["cache"] = {
        "hit": False,
        "stale": False,
        "snapshot_fingerprint": snapshot_fingerprint,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    return enforce_prediction_contract(normalized, event_id=event_id, platform=platform)


def _latest_observed_timestamp(rows: list[dict[str, Any]]) -> str | None:
    timestamps = [timestamp for row in rows if (timestamp := _row_timestamp(row)) is not None]
    return max(timestamps).isoformat() if timestamps else None


async def predict_benchmark_model_evidence(
    *,
    dataset: str = "twitter",
    seed: int | None = 42,
    run_live: bool = False,
) -> dict:
    """Return cached or small-run experiment evidence for the prediction model."""
    result = await propagation_prediction_service.predict_propagation_macro_micro(
        dataset=dataset,
        seed=seed,
        run_live=run_live,
    )
    result.setdefault(
        "methodology",
        propagation_prediction_service.prediction_methodology(
            source="benchmark_model_evidence",
            protocol={"dataset": dataset, "seed": seed, "run_live": run_live},
        ),
    )
    result["capability"] = dict(PREDICTION_MODEL_CAPABILITY)
    result["prediction_boundary"] = {
        "method": "benchmark_macro_micro_evidence",
        "is_primary_model": True,
        "current_event": False,
        "legacy_speed_acceleration_scaffold": "removed_from_public_prediction_api",
    }
    return result


# Backward-compatible service names for existing callers.
predict_propagation_model_event = predict_current_event_model
