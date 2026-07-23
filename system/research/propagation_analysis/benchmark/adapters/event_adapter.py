"""Internal Propagation Analysis event-level bundle adapter.

This module stays inside ``system/research/propagation_analysis`` and exposes a small,
deterministic seam for the deployed backend. It prepares model-ready event
bundles from raw post/comment rows and keeps checkpoint handling conservative
until a real internal runtime is wired.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping


PROPAGATION_ANALYSIS_ROOT = Path(__file__).resolve().parents[2]
ADAPTER_BOUNDARY = str(PROPAGATION_ANALYSIS_ROOT)


def build_event_inference_bundle(
    posts: list[dict[str, Any]],
    comments: list[dict[str, Any]] | None = None,
    *,
    max_sequence_len: int = 64,
    user_hash_buckets: int = 4096,
    relation_neighbor_count: int = 4,
    hyperedge_count: int = 4,
    relation_neighbors: Mapping[int, list[int]] | None = None,
) -> dict[str, Any]:
    normalized_posts = [_normalize_content_row(row, default_kind="post") for row in posts if isinstance(row, Mapping)]
    normalized_comments = [
        _normalize_content_row(row, default_kind="comment")
        for row in comments or []
        if isinstance(row, Mapping)
    ]
    observed_rows = sorted(
        [*normalized_posts, *normalized_comments],
        key=_row_sort_key,
    )

    candidate_meta = _build_candidate_meta(observed_rows)
    candidate_buckets = {
        author_id: _stable_bucket(author_id, user_hash_buckets)
        for author_id in candidate_meta
    }
    for author_id, meta in candidate_meta.items():
        meta["bucket"] = candidate_buckets.get(author_id, 0)

    relation_neighbors = _normalize_relation_neighbors(
        relation_neighbors,
        relation_neighbor_count,
        user_hash_buckets,
    )
    relation_edges = _build_relation_edges(observed_rows)
    activity_sequence = _build_activity_sequence(
        observed_rows,
        candidate_buckets,
        max_sequence_len,
        relation_neighbor_count,
        hyperedge_count,
    )
    bundle_signature = _bundle_signature(
        normalized_posts=normalized_posts,
        normalized_comments=normalized_comments,
        relation_edges=relation_edges,
        candidate_meta=candidate_meta,
        candidate_buckets=candidate_buckets,
    )

    if not candidate_meta:
        return {
            "status": "data_insufficient",
            "model_status": "unavailable",
            "adapter_boundary": ADAPTER_BOUNDARY,
            "bundle_signature": bundle_signature,
            "max_sequence_len": max_sequence_len,
            "relation_neighbor_count": relation_neighbor_count,
            "hyperedge_count": hyperedge_count,
            "candidate_meta": {},
            "candidate_buckets": {},
            "relation_neighbors": relation_neighbors,
            "relation_edges": relation_edges,
            "sequence": activity_sequence,
            "summary": {
                "post_count": len(normalized_posts),
                "comment_count": len(normalized_comments),
                "candidate_count": 0,
                "observed_count": len(observed_rows),
            },
        }

    return {
        "status": "ok",
        "model_status": "unavailable",
        "adapter_boundary": ADAPTER_BOUNDARY,
        "bundle_signature": bundle_signature,
        "max_sequence_len": max_sequence_len,
        "relation_neighbor_count": relation_neighbor_count,
        "hyperedge_count": hyperedge_count,
        "candidate_meta": candidate_meta,
        "candidate_buckets": candidate_buckets,
        "relation_neighbors": relation_neighbors,
        "relation_edges": relation_edges,
        "sequence": activity_sequence,
        "summary": {
            "post_count": len(normalized_posts),
            "comment_count": len(normalized_comments),
            "candidate_count": len(candidate_meta),
            "observed_count": len(observed_rows),
            "active_sequence_length": len(activity_sequence["author_ids"]),
        },
    }


def predict_event_with_checkpoint(
    checkpoint_path: Path | str,
    posts: list[dict[str, Any]],
    comments: list[dict[str, Any]] | None = None,
    *,
    top_k: int = 10,
    max_sequence_len: int = 64,
    user_hash_buckets: int = 4096,
    relation_neighbor_count: int = 4,
    hyperedge_count: int = 4,
    relation_neighbors: Mapping[int, list[int]] | None = None,
) -> dict[str, Any]:
    checkpoint = Path(checkpoint_path)
    bundle = build_event_inference_bundle(
        posts,
        comments,
        max_sequence_len=max_sequence_len,
        user_hash_buckets=user_hash_buckets,
        relation_neighbor_count=relation_neighbor_count,
        hyperedge_count=hyperedge_count,
        relation_neighbors=relation_neighbors,
    )
    result = dict(bundle)
    result.update(
        {
            "checkpoint_path": str(checkpoint),
            "top_k": int(top_k),
            "technology": "propagation_analysis",
        }
    )

    if not checkpoint.exists():
        result.update(
            {
                "status": "missing_checkpoint",
                "model_status": "unavailable",
                "note": f"PropagationAnalysis event checkpoint not found inside system boundary: {checkpoint}",
            }
        )
        return result

    if result.get("status") != "ok":
        result.update(
            {
                "status": "data_insufficient",
                "model_status": "unavailable",
                "note": "PropagationAnalysis event checkpoint exists, but the event bundle is data-insufficient.",
            }
        )
        return result

    result.update(
        {
            "status": "model_unavailable",
            "model_status": "unavailable",
            "note": "PropagationAnalysis event checkpoint exists, but the internal deployed model runtime is not wired yet.",
        }
    )
    return result


def _build_candidate_meta(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    candidate_meta: dict[str, dict[str, Any]] = {}
    for row in rows:
        author_id = _canonical_author_id(row)
        if not author_id:
            continue
        author_name = _canonical_author_name(row) or author_id
        timestamp = _canonical_timestamp(row)
        meta = candidate_meta.setdefault(
            author_id,
            {
                "author_id": author_id,
                "author_name": author_name,
                "platforms": [],
                "post_count": 0,
                "comment_count": 0,
                "first_seen_at": timestamp,
                "last_seen_at": timestamp,
                "content_ids": [],
                "evidence_refs": [],
                "bucket": None,
            },
        )
        if author_name and meta["author_name"] == author_id:
            meta["author_name"] = author_name
        platform = str(row.get("platform") or "unknown").strip() or "unknown"
        if platform not in meta["platforms"]:
            meta["platforms"].append(platform)
        if row.get("kind") == "comment":
            meta["comment_count"] += 1
        else:
            meta["post_count"] += 1
        if timestamp is not None:
            if meta["first_seen_at"] is None or timestamp < meta["first_seen_at"]:
                meta["first_seen_at"] = timestamp
            if meta["last_seen_at"] is None or timestamp > meta["last_seen_at"]:
                meta["last_seen_at"] = timestamp
        content_id = _content_id(row)
        if content_id and content_id not in meta["content_ids"]:
            meta["content_ids"].append(content_id)
        evidence_ref = _evidence_ref(row)
        if evidence_ref and evidence_ref not in meta["evidence_refs"]:
            meta["evidence_refs"].append(evidence_ref)

    for meta in candidate_meta.values():
        meta["platforms"] = sorted(meta["platforms"])
        meta["content_ids"] = sorted(meta["content_ids"])
        meta["evidence_refs"] = sorted(meta["evidence_refs"])
        meta["first_seen_at"] = _serialize_timestamp(meta["first_seen_at"])
        meta["last_seen_at"] = _serialize_timestamp(meta["last_seen_at"])
        meta["activity_score"] = round(
            float(meta["post_count"]) * 2.0 + float(meta["comment_count"]) + min(len(meta["evidence_refs"]), 5) * 0.25,
            3,
        )
    return dict(sorted(candidate_meta.items(), key=lambda item: (item[1]["first_seen_at"] or "", item[0])))


def _build_relation_edges(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    edges: dict[tuple[str, str, str], dict[str, Any]] = {}
    for row in rows:
        current_ref = _content_id(row)
        if not current_ref:
            continue
        platform = str(row.get("platform") or "unknown").strip() or "unknown"
        timestamp = _canonical_timestamp(row)
        for relation_type, source_key in (
            ("repost", "repost_id"),
            ("repost", "retweeted_post_id"),
            ("parent", "parent_post_id"),
            ("quote", "quote_post_id"),
            ("reply", "reply_to"),
            ("reply", "parent_comment_id"),
        ):
            source_ref = str(row.get(source_key) or "").strip()
            if not source_ref:
                continue
            edge = {
                "relation_type": relation_type,
                "source_ref": source_ref,
                "target_ref": current_ref,
                "platform": platform,
                "observed_at": timestamp,
            }
            edges[(relation_type, source_ref, current_ref)] = edge
            break
    return sorted(edges.values(), key=lambda edge: (edge["relation_type"], edge["source_ref"], edge["target_ref"]))


def _build_activity_sequence(
    rows: list[dict[str, Any]],
    candidate_buckets: dict[str, int],
    max_sequence_len: int,
    relation_neighbor_count: int,
    hyperedge_count: int,
) -> dict[str, Any]:
    author_ids: list[str] = []
    author_buckets: list[int] = []
    timestamps: list[str | None] = []
    content_refs: list[str] = []
    kinds: list[str] = []

    for row in rows[:max_sequence_len]:
        author_id = _canonical_author_id(row)
        if not author_id:
            continue
        author_ids.append(author_id)
        author_buckets.append(candidate_buckets.get(author_id, _stable_bucket(author_id, 4096)))
        timestamps.append(_canonical_timestamp(row))
        content_refs.append(_content_id(row))
        kinds.append(str(row.get("kind") or "post"))

    relative_time = _relative_time_offsets(timestamps)
    hyperedges = _build_hyperedges(author_buckets, max_sequence_len, max(1, hyperedge_count))
    relation_matrix = _build_relation_neighbor_matrix(author_buckets, max_sequence_len, max(1, relation_neighbor_count))

    return {
        "author_ids": author_ids,
        "author_buckets": author_buckets,
        "timestamps": timestamps,
        "relative_time_offsets": relative_time,
        "content_refs": content_refs,
        "kinds": kinds,
        "hyperedge_author_buckets": hyperedges,
        "relation_neighbor_ids": relation_matrix,
    }


def _build_relation_neighbor_matrix(
    observed_buckets: list[int],
    max_sequence_len: int,
    relation_neighbor_count: int,
) -> list[list[int]]:
    rows: list[list[int]] = []
    for bucket in observed_buckets[:max_sequence_len]:
        rows.append([bucket] + [0] * max(0, relation_neighbor_count - 1))
    while len(rows) < max_sequence_len:
        rows.append([0] * relation_neighbor_count)
    return rows


def _build_hyperedges(
    observed_buckets: list[int],
    max_sequence_len: int,
    hyperedge_count: int,
) -> list[list[int]]:
    if hyperedge_count <= 0:
        hyperedge_count = 1
    if not observed_buckets:
        return [[0] * max_sequence_len for _ in range(hyperedge_count)]
    rows: list[list[int]] = []
    for stage in range(hyperedge_count):
        start = int(stage * len(observed_buckets) / hyperedge_count)
        end = int((stage + 1) * len(observed_buckets) / hyperedge_count)
        if stage == hyperedge_count - 1:
            end = len(observed_buckets)
        segment = observed_buckets[start:end]
        rows.append(_pad(segment, max_sequence_len))
    return rows


def _normalize_relation_neighbors(
    relation_neighbors: Mapping[int, list[int]] | None,
    relation_neighbor_count: int,
    user_hash_buckets: int,
) -> dict[int, list[int]]:
    if not relation_neighbors:
        return {}
    normalized: dict[int, list[int]] = {}
    for key, values in relation_neighbors.items():
        bucket_key = int(key)
        normalized[bucket_key] = [
            int(value) if int(value) > 0 else 0
            for value in list(values)[: max(1, relation_neighbor_count)]
        ]
    return dict(sorted(normalized.items(), key=lambda item: item[0]))


def _row_sort_key(row: dict[str, Any]) -> tuple[str, str, str]:
    return (
        _canonical_timestamp(row) or "",
        _canonical_author_id(row) or "",
        _content_id(row) or "",
    )


def _normalize_content_row(row: Mapping[str, Any], *, default_kind: str) -> dict[str, Any]:
    data = dict(row)
    kind = default_kind
    if data.get("comment_id") and not data.get("post_id"):
        kind = "comment"
    author_id = _canonical_author_id(data)
    author_name = _canonical_author_name(data) or author_id
    content_id = _content_id(data)
    timestamp = _canonical_timestamp(data)
    return {
        "kind": kind,
        "author_id": author_id,
        "author_name": author_name,
        "content_id": content_id,
        "timestamp": timestamp,
        "platform": str(data.get("platform") or "unknown").strip() or "unknown",
        "reply_to": _first_non_empty(data, ("reply_to", "parent_comment_id")),
        "parent_post_id": _first_non_empty(data, ("parent_post_id", "quote_post_id", "repost_id", "retweeted_post_id")),
        "raw": _canonical_json(data),
    }


def _canonical_author_id(row: Mapping[str, Any]) -> str:
    return _first_non_empty(
        row,
        ("author_id", "user_id", "account_id", "uid", "creator_id", "sec_user_id"),
    )


def _canonical_author_name(row: Mapping[str, Any]) -> str:
    return _first_non_empty(
        row,
        ("author_name", "nickname", "screen_name", "username", "user_name", "account_label", "user_nickname"),
    )


def _canonical_timestamp(row: Mapping[str, Any]) -> str | None:
    value = _first_value(row, ("timestamp", "created_at", "publish_time", "published_at", "time"))
    if isinstance(value, datetime):
        return _serialize_timestamp(value)
    if value in (None, ""):
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        return _serialize_timestamp(datetime.fromisoformat(text.replace("Z", "+00:00")))
    except ValueError:
        return text


def _serialize_timestamp(value: datetime | str | None) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        parsed = _parse_timestamp(value)
        return parsed.isoformat() if parsed is not None else value
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat()


def _content_id(row: Mapping[str, Any]) -> str:
    return _first_non_empty(row, ("post_id", "comment_id", "note_id", "item_id", "id"))


def _evidence_ref(row: Mapping[str, Any]) -> str:
    content_id = _content_id(row)
    if content_id:
        return f"{str(row.get('kind') or 'post')}:{content_id}"
    return ""


def _first_non_empty(row: Mapping[str, Any], keys: tuple[str, ...]) -> str:
    for key in keys:
        value = row.get(key)
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return ""


def _first_value(row: Mapping[str, Any], keys: tuple[str, ...]) -> Any:
    for key in keys:
        value = row.get(key)
        if value not in (None, ""):
            return value
    return None


def _stable_bucket(author_id: str, user_hash_buckets: int) -> int:
    bucket_count = max(1, int(user_hash_buckets))
    if bucket_count <= 2:
        return 1
    digest = hashlib.sha256(author_id.encode("utf-8")).hexdigest()
    return 2 + (int(digest, 16) % (bucket_count - 2))


def _relative_time_offsets(timestamps: list[str | None]) -> list[float]:
    parsed = [_parse_timestamp(value) for value in timestamps]
    present = [value for value in parsed if value is not None]
    if not present:
        return [0.0 for _ in timestamps]
    start = min(present)
    end = max(present)
    span = max((end - start).total_seconds(), 1.0)
    return [round(((value - start).total_seconds() / span) if value is not None else 0.0, 6) for value in parsed]


def _parse_timestamp(value: str | None) -> datetime | None:
    if value in (None, ""):
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _pad(values: list[int], length: int, pad_value: int = 0) -> list[int]:
    row = list(values[:length])
    if len(row) < length:
        row.extend([pad_value] * (length - len(row)))
    return row


def _bundle_signature(
    *,
    normalized_posts: list[dict[str, Any]],
    normalized_comments: list[dict[str, Any]],
    relation_edges: list[dict[str, Any]],
    candidate_meta: dict[str, dict[str, Any]],
    candidate_buckets: dict[str, int],
) -> str:
    payload = {
        "posts": normalized_posts,
        "comments": normalized_comments,
        "relations": relation_edges,
        "candidates": candidate_meta,
        "buckets": candidate_buckets,
    }
    return hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=_json_default)


def _json_default(value: Any) -> Any:
    if isinstance(value, datetime):
        return _serialize_timestamp(value)
    if isinstance(value, Path):
        return str(value)
    return str(value)
