"""Event-prefix adapter for deployed Propagation Analysis inference.

This module owns only current-event rows, observed-prefix construction,
candidate buckets, and traceable user metadata. Checkpoint loading, model
definition, and output contract helpers live in sibling modules.
"""

from __future__ import annotations

import hashlib
import math
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np


PROPAGATION_ANALYSIS_ROOT = Path(__file__).resolve().parents[2]
ADAPTER_BOUNDARY = str(PROPAGATION_ANALYSIS_ROOT)
DEFAULT_TREND_STEPS = 4
DEFAULT_RELATION_NEIGHBORS = 4
DEFAULT_HYPEREDGE_COUNT = 4
DEFAULT_LIVE_OBSERVATION_RATIO = 0.5


def _stable_bucket(user_id: str, user_hash_buckets: int) -> int:
    if user_hash_buckets <= 3:
        return 2
    digest = hashlib.sha1(str(user_id).encode("utf-8", errors="ignore")).hexdigest()
    return 2 + (int(digest[:16], 16) % (int(user_hash_buckets) - 2))


def _pad(values: Sequence[int | float], length: int, pad_value: int | float = 0) -> list:
    row = list(values[:length])
    if len(row) < length:
        row.extend([pad_value] * (length - len(row)))
    return row


def build_event_inference_bundle(
    posts: Sequence[Mapping[str, Any]],
    comments: Sequence[Mapping[str, Any]] | None = None,
    *,
    max_sequence_len: int = 64,
    user_hash_buckets: int = 4096,
    relation_neighbor_count: int = DEFAULT_RELATION_NEIGHBORS,
    hyperedge_count: int = DEFAULT_HYPEREDGE_COUNT,
    relation_neighbors: Mapping[int | str, Sequence[int]] | None = None,
    train_user_buckets: Sequence[int] | None = None,
    observation_ratio: float = DEFAULT_LIVE_OBSERVATION_RATIO,
    prefix_is_preselected: bool = False,
) -> dict[str, Any]:
    try:
        normalized_observation_ratio = float(observation_ratio)
    except (TypeError, ValueError) as exc:
        raise ValueError("observation_ratio must be a finite number in (0, 1].") from exc
    if not math.isfinite(normalized_observation_ratio) or not 0.0 < normalized_observation_ratio <= 1.0:
        raise ValueError("observation_ratio must be a finite number in (0, 1].")

    records = _event_records(posts, comments or [])
    if len(records) < 3:
        return {"status": "data_insufficient", "note": "At least three timestamped observed user events are required."}

    observation_count = (
        len(records)
        if prefix_is_preselected
        else max(1, min(len(records), int(math.ceil(len(records) * normalized_observation_ratio))))
    )
    observed_records = records[:observation_count]
    candidate_meta: dict[str, dict[str, Any]] = {}
    bucket_to_users: dict[int, list[dict[str, Any]]] = defaultdict(list)
    observed_buckets = []
    for record in observed_records:
        author_id = record["author_id"]
        bucket = _stable_bucket(author_id, user_hash_buckets)
        observed_buckets.append(bucket)
        meta = candidate_meta.setdefault(
            author_id,
            {
                "author_id": author_id,
                "author_name": record["author_name"],
                "bucket": bucket,
                "first_seen_at": record["timestamp"].isoformat(),
                "last_seen_at": record["timestamp"].isoformat(),
                "event_count": 0,
                "evidence_refs": [],
                "activation_type": "reactivation",
            },
        )
        meta["event_count"] += 1
        meta["last_seen_at"] = record["timestamp"].isoformat()
        if record["evidence_ref"] not in meta["evidence_refs"]:
            meta["evidence_refs"].append(record["evidence_ref"])
        if not any(row["author_id"] == author_id for row in bucket_to_users[bucket]):
            bucket_to_users[bucket].append(meta)

    normalized_neighbors = {
        int(key): [int(value) for value in list(values)[:relation_neighbor_count]]
        for key, values in (relation_neighbors or {}).items()
    }
    relation_buckets = {
        neighbor
        for bucket in observed_buckets
        for neighbor in normalized_neighbors.get(bucket, [])
        if neighbor > 1
    }
    train_buckets = {int(bucket) for bucket in (train_user_buckets or []) if int(bucket) > 1}
    candidate_buckets = sorted(train_buckets | set(observed_buckets) | relation_buckets)
    if not candidate_buckets:
        return {"status": "data_insufficient", "note": "No legal candidate buckets were available."}

    observed = observed_buckets[:max_sequence_len]
    timestamps = [record["timestamp"] for record in observed_records[:max_sequence_len]]
    mapped_candidate_buckets = sorted(set(bucket_to_users).intersection(candidate_buckets))
    candidate_bucket_meta = {}
    for bucket in candidate_buckets:
        users = bucket_to_users.get(bucket, [])
        sources = []
        if bucket in train_buckets:
            sources.append("checkpoint_train_buckets")
        if bucket in observed_buckets:
            sources.append("observed_user_buckets")
        if bucket in relation_buckets:
            sources.append("observed_relation_neighbor_buckets")
        candidate_bucket_meta[bucket] = {
            "bucket": bucket,
            "mapped": bool(users),
            "author_ids": [user["author_id"] for user in users],
            "candidate_sources": sources,
            "activation_type": "reactivation" if users else None,
        }
    return {
        "status": "ok",
        "seq_user_ids": np.asarray([_pad(observed, max_sequence_len)], dtype=np.int64),
        "seq_time_features": np.asarray([_relative_time_offsets(timestamps, max_sequence_len)], dtype=np.float32),
        "relation_neighbor_ids": np.asarray(
            [[_pad(normalized_neighbors.get(bucket, []), relation_neighbor_count) for bucket in _pad(observed, max_sequence_len)]],
            dtype=np.int64,
        ),
        "hyperedge_user_ids": np.asarray([_hyperedges(observed, hyperedge_count, max_sequence_len)], dtype=np.int64),
        "observed_counts": np.asarray([float(len(observed_records))], dtype=np.float32),
        "obs_ratios": np.asarray([normalized_observation_ratio], dtype=np.float32),
        "candidate_buckets": candidate_buckets,
        "bucket_to_users": dict(bucket_to_users),
        "candidate_meta": candidate_meta,
        "candidate_bucket_meta": candidate_bucket_meta,
        "candidate_source_counts": {
            "checkpoint_train_buckets": len(train_buckets),
            "observed_user_buckets": len(set(observed_buckets)),
            "observed_relation_neighbor_buckets": len(relation_buckets),
            "legal_candidate_buckets": len(candidate_buckets),
            "mapped_candidate_buckets": len(mapped_candidate_buckets),
            "unmapped_candidate_buckets": len(candidate_buckets) - len(mapped_candidate_buckets),
        },
        "candidate_coverage": {
            "legal_candidate_buckets": len(candidate_buckets),
            "mapped_candidate_buckets": len(mapped_candidate_buckets),
            "unmapped_candidate_buckets": len(candidate_buckets) - len(mapped_candidate_buckets),
            "mapped_probability_mass": 0.0,
        },
        "latest_timestamp": observed_records[-1]["timestamp"],
        "loaded_event_count": len(records),
        "observed_event_count": len(observed_records),
        "prefix_is_preselected": bool(prefix_is_preselected),
        "adapter_boundary": ADAPTER_BOUNDARY,
    }


def _event_records(posts: Sequence[Mapping[str, Any]], comments: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    records = []
    for index, row in enumerate([*posts, *comments]):
        author_id = str(row.get("author_id") or row.get("user_id") or row.get("account_id") or row.get("uid") or "").strip()
        if not author_id:
            continue
        timestamp = _row_timestamp(row)
        if timestamp is None:
            continue
        content_id = str(row.get("post_id") or row.get("comment_id") or row.get("id") or "")
        records.append(
            {
                "author_id": author_id,
                "author_name": str(
                    row.get("author_name")
                    or row.get("nickname")
                    or row.get("screen_name")
                    or row.get("username")
                    or row.get("account_label")
                    or author_id
                ),
                "timestamp": timestamp,
                "time_value": timestamp.timestamp(),
                "index": index,
                "evidence_ref": {
                    "post_id": content_id,
                    "timestamp": timestamp.isoformat(),
                    "content": str(row.get("content") or row.get("text") or "")[:180],
                    "url": str(row.get("url") or row.get("source_url") or ""),
                },
            }
        )
    return sorted(records, key=lambda row: (row["time_value"], row["index"]))


def _timestamp(value: Any) -> datetime | None:
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(float(value), tz=timezone.utc)
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    return (parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)).astimezone(timezone.utc)


def _row_timestamp(row: Mapping[str, Any]) -> datetime | None:
    for field in ("timestamp", "created_at", "publish_time", "published_at", "time"):
        parsed = _timestamp(row.get(field))
        if parsed is not None:
            return parsed
    return None


def _relative_time_offsets(timestamps: Sequence[datetime], max_sequence_len: int) -> list[float]:
    if not timestamps:
        return [0.0] * max_sequence_len
    start, end = timestamps[0], timestamps[-1]
    span = max((end - start).total_seconds(), 1.0)
    return _pad([(timestamp - start).total_seconds() / span for timestamp in timestamps], max_sequence_len, 0.0)


def _hyperedges(observed_buckets: Sequence[int], hyperedge_count: int, max_sequence_len: int) -> list[list[int]]:
    rows = []
    for stage in range(hyperedge_count):
        start = int(stage * len(observed_buckets) / hyperedge_count)
        end = len(observed_buckets) if stage == hyperedge_count - 1 else int((stage + 1) * len(observed_buckets) / hyperedge_count)
        rows.append(_pad(observed_buckets[start:end], max_sequence_len))
    return rows


__all__ = [
    "ADAPTER_BOUNDARY",
    "DEFAULT_HYPEREDGE_COUNT",
    "DEFAULT_LIVE_OBSERVATION_RATIO",
    "DEFAULT_RELATION_NEIGHBORS",
    "DEFAULT_TREND_STEPS",
    "build_event_inference_bundle",
]
