"""Propagation prediction model orchestration service.

This service owns future trend and next-hop prediction for event-scoped
propagation data. Observed path reconstruction belongs in
``propagation_observation_service`` instead.
"""

from __future__ import annotations

import asyncio
import logging
import math
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Mapping

from pydantic import ValidationError

from app.db.mongodb import get_mongo_db
from app.schemas.propagation import PropagationPredictionData
from app.services.event_data import analysis_scope_metadata, load_event_comments, load_event_posts
from app.services import coordination_service, propagation_prediction_service


logger = logging.getLogger(__name__)

PREDICTION_EVENT_DATA_TIMEOUT_SECONDS = 15.0


PREDICTION_MODEL_CAPABILITY = {
    "name": "macro_micro_sequence_propagation_prediction",
    "type": "macro_micro_prediction",
    "boundary": "future_trend_and_next_hop_prediction",
    "predicts_future": True,
}

SUPPORTED_CHECKPOINT_OBSERVATION_RATIOS = (0.1, 0.3, 0.5)
PREDICTION_HORIZON_HOURS = (1, 6, 24)
CANDIDATE_SOURCE_PRIORITY = (
    "coordination_account",
    "explicit_interaction_neighbor",
    "shared_object_participant",
    "historical_interaction_account",
    "event_participant",
)
CANDIDATE_SOURCE_ORDER = (
    "event_participant",
    "explicit_interaction_neighbor",
    "shared_object_participant",
    "coordination_account",
    "historical_interaction_account",
)


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


def materialize_prediction_horizons(result: dict[str, Any], *, observed_until: str | None) -> dict[str, Any]:
    """Project normalized model trend steps onto the fixed product horizons.

    The checkpoint emits monotonic cumulative values at normalized steps. The
    system view always presents the same 1/6/24-hour checkpoints so an
    analyst can compare one event snapshot with another without a second
    model invocation.
    """
    if str(result.get("status") or "") != "ok":
        return result
    macro = result.get("macro")
    if not isinstance(macro, dict):
        return result
    observed_size = max(0, int(_as_number(macro.get("observed_size"))))
    raw_points = macro.get("trend_points")
    point_values = [
        max(observed_size, int(_as_number(point.get("predicted_size"))))
        for point in raw_points
        if isinstance(point, dict) and point.get("predicted_size") is not None
    ] if isinstance(raw_points, list) else []
    final_size = max(observed_size, int(_as_number(macro.get("predicted_size"))))
    if not point_values:
        point_values = [final_size]
    point_values[-1] = max(point_values[-1], final_size)
    point_values = _monotonic_values(point_values, floor=observed_size)

    # The model exposes steps rather than wall-clock times. Map its final
    # cumulative step to the system's 24-hour forecast window and interpolate
    # the interior values monotonically.
    anchors = [(0.0, observed_size)]
    step_count = len(point_values)
    anchors.extend(
        (24.0 * float(index) / float(step_count), value)
        for index, value in enumerate(point_values, start=1)
    )
    cutoff = _parse_timestamp(observed_until, require_timezone=True)
    projected_points = []
    for step, horizon in enumerate(PREDICTION_HORIZON_HOURS, start=1):
        projected_value = int(round(_interpolate_cumulative_value(anchors, float(horizon))))
        projected_points.append(
            {
                "step": step,
                "horizon_hours": horizon,
                "at": (cutoff + _hours_delta(horizon)).isoformat() if cutoff is not None else None,
                "predicted_size": projected_value,
            }
        )
    macro["trend_points"] = projected_points
    macro["predicted_size"] = max(final_size, projected_points[-1]["predicted_size"])
    return result


def _as_number(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _monotonic_values(values: list[int], *, floor: int) -> list[int]:
    current = floor
    normalized: list[int] = []
    for value in values:
        current = max(current, int(value))
        normalized.append(current)
    return normalized


def _interpolate_cumulative_value(anchors: list[tuple[float, int]], horizon: float) -> float:
    for (left_time, left_value), (right_time, right_value) in zip(anchors, anchors[1:]):
        if horizon <= right_time:
            span = max(right_time - left_time, 1e-9)
            proportion = max(0.0, min(1.0, (horizon - left_time) / span))
            return left_value + (right_value - left_value) * proportion
    return float(anchors[-1][1])


def _hours_delta(hours: int):
    from datetime import timedelta

    return timedelta(hours=hours)


def enrich_next_hop_traceability(
    result: dict[str, Any],
    *,
    posts: list[dict[str, Any]],
    comments: list[dict[str, Any]],
    coordinated_account_ids: set[str] | None = None,
) -> dict[str, Any]:
    """Attach observed-prefix evidence categories without changing model scores."""
    micro = result.get("micro")
    if not isinstance(micro, dict) or not isinstance(micro.get("top_users"), list):
        return result
    source_index = _candidate_source_index(
        [*posts, *comments],
        coordinated_account_ids=coordinated_account_ids,
    )
    for candidate in micro["top_users"]:
        if not isinstance(candidate, dict):
            continue
        author_id = str(candidate.get("author_id") or "").strip()
        sources = source_index.get(author_id, {"event_participant"})
        ordered_sources = [source for source in CANDIDATE_SOURCE_ORDER if source in sources]
        if not ordered_sources:
            ordered_sources = ["event_participant"]
        candidate["candidate_sources"] = ordered_sources
        primary_source = next(
            source for source in CANDIDATE_SOURCE_PRIORITY if source in ordered_sources
        )
        candidate["candidate_source"] = primary_source
        evidence_refs = candidate.get("evidence_refs")
        if isinstance(evidence_refs, list):
            candidate["evidence_refs"] = [
                ({**reference, "candidate_source": primary_source}
                 if isinstance(reference, dict) else reference)
                for reference in evidence_refs
            ]
    micro["candidate_source_counts"] = _candidate_source_counts(source_index)
    return result


def _candidate_source_index(
    records: list[dict[str, Any]],
    *,
    coordinated_account_ids: set[str] | None = None,
) -> dict[str, set[str]]:
    sources: defaultdict[str, set[str]] = defaultdict(set)
    object_members: defaultdict[str, set[str]] = defaultdict(set)
    for record in records:
        author_id = _candidate_author_id(record)
        if not author_id:
            continue
        sources[author_id].add("event_participant")
        for related_id in _relationship_account_ids(record):
            sources[author_id].add("explicit_interaction_neighbor")
            sources[related_id].add("explicit_interaction_neighbor")
        for object_id in _candidate_shared_objects(record):
            object_members[object_id].add(author_id)
        if _has_coordination_marker(record):
            sources[author_id].add("coordination_account")
        for account_id in _account_id_values(record.get("coordination_accounts")):
            sources[account_id].add("coordination_account")
        for account_id in _account_id_values(record.get("coordination_members")):
            sources[account_id].add("coordination_account")
        for account_id in _account_id_values(record.get("historical_interaction_accounts")):
            sources[account_id].add("historical_interaction_account")
        for account_id in _account_id_values(record.get("interacted_accounts")):
            sources[account_id].add("historical_interaction_account")
    for account_id in coordinated_account_ids or set():
        normalized_id = str(account_id).strip()
        if normalized_id:
            sources[normalized_id].add("coordination_account")
    for members in object_members.values():
        if len(members) > 1:
            for author_id in members:
                sources[author_id].add("shared_object_participant")
    return dict(sources)


def _candidate_source_counts(source_index: Mapping[str, set[str]]) -> dict[str, int]:
    return {
        source: sum(1 for sources in source_index.values() if source in sources)
        for source in CANDIDATE_SOURCE_ORDER
    }


def _model_observed_prefix_rows(
    posts: list[dict[str, Any]],
    comments: list[dict[str, Any]],
    *,
    observation_ratio: float,
    prefix_is_preselected: bool,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Mirror the adapter's prefix boundary before deriving evidence labels.

    The checkpoint ranks users from its observed prefix only. Source labels and
    coordination annotations must use that same prefix so future rows cannot
    influence a current-event next-hop assessment.
    """
    records: list[tuple[datetime, int, str, dict[str, Any]]] = []
    for index, row in enumerate(posts):
        timestamp = _row_timestamp(row)
        if timestamp is not None and _candidate_author_id(row):
            records.append((timestamp, index, "post", row))
    post_count = len(posts)
    for index, row in enumerate(comments):
        timestamp = _row_timestamp(row)
        if timestamp is not None and _candidate_author_id(row):
            records.append((timestamp, post_count + index, "comment", row))
    records.sort(key=lambda item: (item[0], item[1]))
    if not records:
        return [], []
    limit = len(records) if prefix_is_preselected else max(
        1,
        min(len(records), int(math.ceil(len(records) * float(observation_ratio)))),
    )
    selected_posts: list[dict[str, Any]] = []
    selected_comments: list[dict[str, Any]] = []
    for _timestamp_value, _index, record_type, row in records[:limit]:
        if record_type == "post":
            selected_posts.append(row)
        else:
            selected_comments.append(row)
    return selected_posts, selected_comments


async def _observed_coordination_account_ids(
    posts: list[dict[str, Any]],
    comments: list[dict[str, Any]],
    *,
    event_id: str,
    platform: str | None,
) -> set[str]:
    """Return coordinated accounts from the same observed prefix as inference."""
    if not posts and not comments:
        return set()
    try:
        coordination = await asyncio.to_thread(
            coordination_service.analyze_coordination_records,
            posts,
            comments,
            event_id=event_id,
            platform=platform,
        )
    except Exception:
        logger.warning(
            "Unable to derive coordination candidate context for event_id=%r platform=%r",
            event_id,
            platform,
            exc_info=True,
        )
        return set()
    return _coordination_account_ids(coordination)


def _coordination_account_ids(coordination: Mapping[str, Any]) -> set[str]:
    accounts: set[str] = set()
    network = coordination.get("network")
    if isinstance(network, Mapping):
        nodes = network.get("nodes")
        if isinstance(nodes, list):
            for node in nodes:
                if not isinstance(node, Mapping):
                    continue
                account_id = str(
                    node.get("account_id") or node.get("author_id") or node.get("id") or ""
                ).strip()
                if account_id:
                    accounts.add(account_id)
    account_stats = coordination.get("account_stats")
    if isinstance(account_stats, list):
        for account in account_stats:
            if not isinstance(account, Mapping):
                continue
            account_id = str(account.get("account_id") or account.get("author_id") or "").strip()
            if account_id:
                accounts.add(account_id)
    return accounts


def _candidate_author_id(record: Mapping[str, Any]) -> str:
    return str(
        record.get("author_id")
        or record.get("user_id")
        or record.get("account_id")
        or record.get("uid")
        or ""
    ).strip()


def _relationship_account_ids(record: Mapping[str, Any]) -> set[str]:
    values: set[str] = set()
    for key in (
        "parent_author_id",
        "reply_to_user_id",
        "reply_to_author_id",
        "target_author_id",
        "quoted_author_id",
        "repost_author_id",
    ):
        value = str(record.get(key) or "").strip()
        if value:
            values.add(value)
    return values


def _candidate_shared_objects(record: Mapping[str, Any]) -> set[str]:
    values: set[str] = set()
    for field in ("url", "claim_id", "object_id"):
        value = str(record.get(field) or "").strip()
        if value:
            values.add(value)
    for field in ("shared_urls", "hashtags", "keywords"):
        raw = record.get(field)
        if isinstance(raw, str):
            raw = [raw]
        if isinstance(raw, (list, tuple, set)):
            values.update(str(item).strip() for item in raw if str(item).strip())
    return values


def _account_id_values(value: Any) -> set[str]:
    if isinstance(value, str):
        return {value.strip()} if value.strip() else set()
    if isinstance(value, Mapping):
        return {
            str(item).strip()
            for item in value.values()
            if str(item).strip()
        }
    if isinstance(value, (list, tuple, set)):
        return {str(item).strip() for item in value if str(item).strip()}
    return set()


def _has_coordination_marker(record: Mapping[str, Any]) -> bool:
    return bool(
        record.get("coordination_group_id")
        or record.get("coordination_signal")
        or record.get("is_coordinated")
    )


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

    platform = str(platform or "").strip().lower() or None
    effective_observation_ratio = observation_ratio
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
    prefix_is_preselected = observed_until is not None
    trace_posts, trace_comments = _model_observed_prefix_rows(
        observed_posts,
        observed_comments,
        observation_ratio=effective_observation_ratio,
        prefix_is_preselected=prefix_is_preselected,
    )
    coordinated_account_ids = await _observed_coordination_account_ids(
        trace_posts,
        trace_comments,
        event_id=event_id,
        platform=platform,
    )
    enrich_next_hop_traceability(
        result,
        posts=trace_posts,
        comments=trace_comments,
        coordinated_account_ids=coordinated_account_ids,
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
    materialize_prediction_horizons(scoped_result, observed_until=effective_cutoff)
    scoped_result["data_scope"]["prediction_horizon_hours"] = 24
    scoped_result["data_scope"]["trajectory_time_basis"] = "fixed_wall_clock_horizons_1h_6h_24h"
    return enforce_prediction_contract(scoped_result, event_id=event_id, platform=platform)


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
