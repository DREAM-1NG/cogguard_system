from __future__ import annotations

import hashlib
import json
from collections import Counter
from datetime import date, datetime, timezone
from typing import Any, Iterable

from app.core.analysis.contracts import (
    DataQualityReport,
    EventSnapshot,
    EvidenceRelation,
    ProvenanceRecord,
    TimeWindow,
)


def build_event_snapshot(
    *,
    event_id: str,
    posts: Iterable[dict[str, Any]],
    comments: Iterable[dict[str, Any]],
    core_window: TimeWindow,
    context_window: TimeWindow,
) -> EventSnapshot:
    event_key = event_id.strip()
    if not event_key:
        raise ValueError("event_id is required")
    if not (
        context_window.start <= core_window.start
        and core_window.end <= context_window.end
    ):
        raise ValueError("core_window must be contained by context_window")

    input_posts = [_canonical_mapping(row) for row in posts]
    input_comments = [_canonical_mapping(row) for row in comments]
    unique_posts, duplicate_posts, missing_post_ids = _dedupe_rows(input_posts, "post_id")
    unique_comments, duplicate_comments, missing_comment_ids = _dedupe_rows(input_comments, "comment_id")

    context_posts, excluded_posts, missing_post_timestamps = _filter_window(unique_posts, context_window)
    context_comments, excluded_comments, missing_comment_timestamps = _filter_window(unique_comments, context_window)
    context_posts.sort(key=lambda row: _row_sort_key(row, "post_id"))
    context_comments.sort(key=lambda row: _row_sort_key(row, "comment_id"))

    core_posts = sum(
        1
        for row in context_posts
        if (timestamp := _parse_timestamp(row.get("timestamp"))) is not None
        and core_window.contains(timestamp)
    )
    platform_counts = Counter(
        str(row.get("platform") or "unknown")
        for row in [*context_posts, *context_comments]
    )
    missing_authors = sum(
        1 for row in [*context_posts, *context_comments] if not str(row.get("author_id") or "").strip()
    )
    issues: list[str] = []
    if core_posts == 0:
        issues.append("no_core_posts")
    if missing_post_timestamps + missing_comment_timestamps:
        issues.append("missing_timestamps")
    if missing_authors:
        issues.append("missing_authors")
    quality_status = "reject" if core_posts == 0 else ("warn" if len(issues) > 0 else "pass")

    relationships = _build_relationships(context_posts, context_comments)
    provenance = _build_provenance([*context_posts, *context_comments])
    platforms = sorted(platform for platform in platform_counts if platform != "unknown")
    quality_report = DataQualityReport(
        status=quality_status,
        total_input_posts=len(input_posts),
        total_input_comments=len(input_comments),
        context_posts=len(context_posts),
        context_comments=len(context_comments),
        core_posts=core_posts,
        duplicate_posts=duplicate_posts,
        duplicate_comments=duplicate_comments,
        excluded_posts=excluded_posts,
        excluded_comments=excluded_comments,
        missing_post_ids=missing_post_ids,
        missing_comment_ids=missing_comment_ids,
        missing_timestamps=missing_post_timestamps + missing_comment_timestamps,
        missing_authors=missing_authors,
        platform_counts=dict(sorted(platform_counts.items())),
        issues=issues,
    )
    fingerprint_payload = {
        "event_id": event_key,
        "core_window": core_window.model_dump(mode="json"),
        "context_window": context_window.model_dump(mode="json"),
        "posts": context_posts,
        "comments": context_comments,
        "relationships": [edge.model_dump(mode="json") for edge in relationships],
        "provenance": [record.model_dump(mode="json") for record in provenance],
    }
    data_fingerprint = hashlib.sha256(_canonical_json(fingerprint_payload).encode("utf-8")).hexdigest()
    return EventSnapshot(
        snapshot_id=f"snapshot_{data_fingerprint[:24]}",
        event_id=event_key,
        platforms=platforms,
        core_window=core_window,
        context_window=context_window,
        posts=context_posts,
        comments=context_comments,
        relationships=relationships,
        quality_report=quality_report,
        provenance=provenance,
        data_fingerprint=data_fingerprint,
    )


def _dedupe_rows(
    rows: list[dict[str, Any]],
    id_field: str,
) -> tuple[list[dict[str, Any]], int, int]:
    selected: dict[tuple[str, str], dict[str, Any]] = {}
    duplicate_count = 0
    missing_ids = 0
    for row in rows:
        platform = str(row.get("platform") or "unknown").strip() or "unknown"
        row_id = str(row.get(id_field) or "").strip()
        if not row_id:
            missing_ids += 1
            row_id = f"missing:{hashlib.sha256(_canonical_json(row).encode('utf-8')).hexdigest()}"
        key = (platform, row_id)
        existing = selected.get(key)
        if existing is not None:
            duplicate_count += 1
            if _row_rank(row) > _row_rank(existing):
                selected[key] = row
        else:
            selected[key] = row
    return list(selected.values()), duplicate_count, missing_ids


def _filter_window(
    rows: list[dict[str, Any]],
    window: TimeWindow,
) -> tuple[list[dict[str, Any]], int, int]:
    included: list[dict[str, Any]] = []
    missing_timestamps = 0
    for row in rows:
        timestamp = _parse_timestamp(row.get("timestamp"))
        if timestamp is None:
            missing_timestamps += 1
            continue
        if window.contains(timestamp):
            included.append(row)
    return included, len(rows) - len(included), missing_timestamps


def _build_relationships(
    posts: list[dict[str, Any]],
    comments: list[dict[str, Any]],
) -> list[EvidenceRelation]:
    relationships: dict[tuple[str, str, str], EvidenceRelation] = {}
    comment_ids = {
        (str(row.get("platform") or "unknown"), str(row.get("comment_id") or ""))
        for row in comments
    }
    for row in posts:
        platform = str(row.get("platform") or "unknown")
        post_id = str(row.get("post_id") or "")
        for field, relation_type in (
            ("repost_id", "repost"),
            ("retweeted_post_id", "repost"),
            ("parent_post_id", "parent"),
            ("quote_post_id", "quote"),
        ):
            parent_id = str(row.get(field) or "").strip()
            if parent_id and post_id:
                edge = EvidenceRelation(
                    relation_type=relation_type,
                    source_id=_content_ref(platform, "post", parent_id),
                    target_id=_content_ref(platform, "post", post_id),
                    platform=platform,
                    observed_at=_parse_timestamp(row.get("timestamp")),
                    evidence_ref=_content_ref(platform, "post", post_id),
                )
                relationships[(edge.relation_type, edge.source_id, edge.target_id)] = edge
                break
    for row in comments:
        platform = str(row.get("platform") or "unknown")
        comment_id = str(row.get("comment_id") or "")
        parent_id = str(row.get("reply_to") or row.get("parent_comment_id") or "").strip()
        if not parent_id or not comment_id:
            continue
        parent_type = "comment" if (platform, parent_id) in comment_ids else "post"
        edge = EvidenceRelation(
            relation_type="reply",
            source_id=_content_ref(platform, parent_type, parent_id),
            target_id=_content_ref(platform, "comment", comment_id),
            platform=platform,
            observed_at=_parse_timestamp(row.get("timestamp")),
            evidence_ref=_content_ref(platform, "comment", comment_id),
        )
        relationships[(edge.relation_type, edge.source_id, edge.target_id)] = edge
    return sorted(
        relationships.values(),
        key=lambda edge: (edge.relation_type, edge.source_id, edge.target_id),
    )


def _build_provenance(rows: list[dict[str, Any]]) -> list[ProvenanceRecord]:
    records: dict[tuple[str, str, str, str], ProvenanceRecord] = {}
    for row in rows:
        platform = str(row.get("platform") or "unknown")
        crawl_job_id = str(row.get("crawl_job_id") or "").strip()
        source_keyword = str(row.get("source_keyword") or "").strip()
        metadata = row.get("crawl_metadata") if isinstance(row.get("crawl_metadata"), dict) else {}
        source_id = crawl_job_id or str(metadata.get("source_id") or "").strip()
        if not source_id and not source_keyword and not metadata:
            continue
        source_id = source_id or f"keyword:{source_keyword}"
        key = ("crawl", source_id, platform, source_keyword)
        records[key] = ProvenanceRecord(
            source_id=source_id,
            platform=platform,
            source_keyword=source_keyword,
            metadata=_canonical_mapping(metadata),
        )
    return [records[key] for key in sorted(records)]


def _canonical_mapping(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise TypeError("Snapshot content rows must be mappings")
    return {str(key): _canonical_value(item) for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))}


def _canonical_value(value: Any) -> Any:
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, datetime):
        return _as_utc(value).isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, dict):
        return _canonical_mapping(value)
    if isinstance(value, (list, tuple, set)):
        return [_canonical_value(item) for item in value]
    return str(value)


def _parse_timestamp(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return _as_utc(value)
    if value in (None, ""):
        return None
    text = str(value).strip()
    try:
        return _as_utc(datetime.fromisoformat(text.replace("Z", "+00:00")))
    except ValueError:
        return None


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _row_rank(row: dict[str, Any]) -> tuple[int, str]:
    populated = sum(value not in (None, "", [], {}) for value in row.values())
    return populated, _canonical_json(row)


def _row_sort_key(row: dict[str, Any], id_field: str) -> tuple[str, str, str]:
    timestamp = _parse_timestamp(row.get("timestamp"))
    timestamp_key = timestamp.isoformat() if timestamp else ""
    return timestamp_key, str(row.get("platform") or ""), str(row.get(id_field) or "")


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _content_ref(platform: str, kind: str, value: str) -> str:
    return f"{platform}:{kind}:{value}"
