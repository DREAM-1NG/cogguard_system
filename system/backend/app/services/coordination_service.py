"""Coordination detection service."""

from __future__ import annotations

from collections import Counter, defaultdict
from os.path import splitext
from typing import Any
from urllib.parse import urlparse

import pandas as pd

from app.core.coordination_detect import account_stats, detect_groups, group_stats
from app.core.coordination_discover import generate_coordinated_network, graph_to_dict
from app.db.mongodb import get_mongo_db
from app.services.event_data import build_event_filter, load_event_comments, load_event_posts

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".svg"}
VIDEO_EXTENSIONS = {".mp4", ".mov", ".avi", ".mkv", ".webm", ".m3u8"}
ACCOUNT_LABEL_PATHS = (
    ("author_name",),
    ("account_label",),
    ("account_name",),
    ("author_username",),
    ("author_screen_name",),
    ("author_nickname",),
    ("nickname",),
    ("screen_name",),
    ("user_name",),
    ("username",),
    ("display_name",),
    ("author_profile", "author_name"),
    ("author_profile", "display_name"),
    ("author_profile", "screen_name"),
    ("author_profile", "nickname"),
    ("author_profile", "user_name"),
    ("author_profile", "username"),
    ("author_profile", "name"),
    ("raw_data", "author_name"),
    ("raw_data", "display_name"),
    ("raw_data", "screen_name"),
    ("raw_data", "nickname"),
    ("raw_data", "username"),
    ("raw_data", "user_name"),
    ("raw_data", "user", "screen_name"),
    ("raw_data", "user", "nickname"),
    ("raw_data", "user", "name"),
    ("raw_data", "mblog", "user", "screen_name"),
    ("raw_data", "mblog", "user", "nickname"),
    ("raw_data", "mblog", "user", "name"),
    ("raw_data", "post_details_raw", "mblog", "user", "screen_name"),
    ("raw_data", "post_details_raw", "mblog", "user", "nickname"),
    ("raw_data", "post_details_raw", "mblog", "user", "name"),
)


def _summary(
    *,
    event_id: str | None,
    platform: str | None,
    total_posts: int,
    total_comments: int = 0,
    total_pairs: int = 0,
    coordinated_accounts: int = 0,
    coordinated_edges: int = 0,
    components: int = 0,
    clusters: int = 0,
) -> dict[str, Any]:
    return {
        "event_id": event_id,
        "platform": platform,
        "total_posts": total_posts,
        "total_comments": total_comments,
        "total_items": total_posts + total_comments,
        "total_pairs": total_pairs,
        "coordinated_accounts": coordinated_accounts,
        "coordinated_edges": coordinated_edges,
        "components": components,
        "cluster_count": clusters,
    }


def _empty_result(
    event_id: str | None,
    platform: str | None,
    total_posts: int,
    *,
    total_comments: int = 0,
    error: str | None = None,
) -> dict:
    result = {
        "network": {
            "nodes": [],
            "edges": [],
            "node_count": 0,
            "edge_count": 0,
            "component_count": 0,
            "components": [],
            "cluster_count": 0,
            "clusters": [],
        },
        "account_stats": [],
        "group_stats": [],
        "summary": _summary(
            event_id=event_id,
            platform=platform,
            total_posts=total_posts,
            total_comments=total_comments,
        ),
        "cluster_stats": [],
    }
    if error:
        result["error"] = error
    return result


def _iter_values(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value] if value else []
    if isinstance(value, dict):
        return [str(item) for item in value.values() if item]
    if isinstance(value, (list, tuple, set)):
        return [str(item) for item in value if item]
    return [str(value)]


def _string_from_path(record: dict[str, Any], path: tuple[str, ...]) -> str:
    current: Any = record
    for key in path:
        if not isinstance(current, dict):
            return ""
        current = current.get(key)
    return str(current or "").strip()


def _extract_account_label(record: dict[str, Any]) -> str:
    account_id = str(record.get("author_id") or "").strip()
    fallback = ""
    for path in ACCOUNT_LABEL_PATHS:
        value = _string_from_path(record, path)
        if not value:
            continue
        if not fallback:
            fallback = value
        if value != account_id:
            return value
    return fallback


def _shared_objects(post: dict[str, Any]) -> list[str]:
    objects: list[str] = []
    objects.extend(_iter_values(post.get("hashtags")))
    url = post.get("url")
    if url:
        objects.append(str(url))
    objects.extend(_iter_values(post.get("shared_urls")))
    objects.extend(_iter_values(post.get("media_urls")))
    return list(dict.fromkeys(objects))


def _compact_text(value: Any, limit: int = 72) -> str:
    text = " ".join(str(value or "").split())
    if len(text) <= limit:
        return text
    return f"{text[: limit - 1]}…"


def _classify_object(object_id: str) -> str:
    text = str(object_id or "").strip()
    if not text:
        return "内容"
    if text.startswith("#"):
        return "话题"

    parsed = urlparse(text)
    if parsed.scheme in {"http", "https"}:
        ext = splitext(parsed.path.lower())[1]
        if ext in IMAGE_EXTENSIONS:
            return "图片"
        if ext in VIDEO_EXTENSIONS:
            return "视频"
        return "链接"
    return "内容"


def _build_object_entry(object_id: str, count: int) -> dict[str, Any]:
    normalized = str(object_id or "").strip()
    return {
        "object_id": normalized,
        "object_type": _classify_object(normalized),
        "count": int(count),
        "preview": _compact_text(normalized),
    }


def _rank_object_entries(counter: Counter[str], limit: int = 5) -> list[dict[str, Any]]:
    return [
        _build_object_entry(object_id, count)
        for object_id, count in counter.most_common(limit)
        if object_id
    ]


def _content_preview(record: dict[str, Any]) -> str:
    text = _compact_text(record.get("content"))
    if text:
        return text

    shared_objects = _shared_objects(record)
    if shared_objects:
        return _compact_text(shared_objects[0])
    return ""


def _build_account_labels(records: list[dict[str, Any]]) -> dict[str, str]:
    labels: dict[str, Counter[str]] = defaultdict(Counter)
    for record in records:
        account_id = str(record.get("author_id") or "").strip()
        if not account_id:
            continue
        account_label = _extract_account_label(record)
        if account_label:
            labels[account_id][account_label] += 1

    result: dict[str, str] = {}
    for account_id, counter in labels.items():
        result[account_id] = counter.most_common(1)[0][0]
    return result


def _build_content_metadata(
    posts: list[dict[str, Any]],
    comments: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    content_meta: dict[str, dict[str, Any]] = {}
    sources = (
        ("post", "post_id", "帖子", posts),
        ("comment", "comment_id", "评论", comments),
    )
    for prefix, item_id_key, content_type, records in sources:
        for record in records:
            item_id = str(record.get(item_id_key) or "").strip()
            if not item_id:
                continue
            content_id = f"{prefix}:{item_id}"
            shared_urls = list(dict.fromkeys(_iter_values(record.get("shared_urls"))))[:3]
            media_urls = list(dict.fromkeys(_iter_values(record.get("media_urls"))))[:3]
            primary_url = str(record.get("url") or "").strip()
            content_meta[content_id] = {
                "content_id": content_id,
                "content_type": content_type,
                "content_preview": _content_preview(record),
                "primary_url": primary_url or None,
                "shared_urls": shared_urls,
                "media_urls": media_urls,
            }
    return content_meta


def _top_content_entries(
    content_ids: list[str],
    content_meta: dict[str, dict[str, Any]],
    limit: int = 5,
) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    seen: set[str] = set()
    for content_id in content_ids:
        normalized = str(content_id or "").strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        meta = content_meta.get(normalized, {})
        entries.append(
            {
                "content_id": normalized,
                "content_type": meta.get("content_type", "内容"),
                "content_preview": meta.get("content_preview") or normalized,
                "primary_url": meta.get("primary_url"),
                "shared_urls": meta.get("shared_urls", []),
                "media_urls": meta.get("media_urls", []),
            }
        )
        if len(entries) >= limit:
            break
    return entries


def _normalize_timestamp(value: Any) -> float | None:
    """Coerce a record timestamp to epoch seconds, or None if unparseable.

    Every conversion stays inside the guard. A non-ISO string ("", "刚刚",
    "3分钟前") — reachable for data imported outside the pydantic-validated
    crawler path — would otherwise raise out of this helper and 500 the whole
    /coordination/detect request instead of skipping that single row.
    """
    if value is None:
        return None
    try:
        if isinstance(value, str):
            parsed = pd.to_datetime(value, errors="coerce", utc=True)
            if pd.isna(parsed):
                return None
            return float(parsed.timestamp())
        if hasattr(value, "timestamp"):
            return float(value.timestamp())
        return float(value)
    except (TypeError, ValueError, OverflowError):
        return None


def _build_coordination_rows(
    records: list[dict[str, Any]],
    *,
    item_id_key: str,
    item_prefix: str,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for record in records:
        item_id = str(record.get(item_id_key) or "").strip()
        author_id = str(record.get("author_id") or "").strip()
        timestamp = _normalize_timestamp(record.get("timestamp"))
        if not item_id or not author_id or timestamp is None:
            continue

        for object_id in _shared_objects(record):
            rows.append(
                {
                    "object_id": object_id,
                    "account_id": author_id,
                    "content_id": f"{item_prefix}:{item_id}",
                    "timestamp_share": timestamp,
                }
            )
    return rows


def _timestamp_to_iso(value: float) -> str:
    return pd.Timestamp(value, unit="s", tz="UTC").isoformat()


def _node_activity(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    if not rows:
        return {}

    df = pd.DataFrame(rows)
    if df.empty:
        return {}

    activity = (
        df.groupby("account_id")
        .agg(
            first_seen_ts=("timestamp_share", "min"),
            last_seen_ts=("timestamp_share", "max"),
            coordinated_object_count=("object_id", "nunique"),
            coordinated_content_count=("content_id", "nunique"),
        )
        .reset_index()
    )

    result: dict[str, dict[str, Any]] = {}
    for row in activity.to_dict(orient="records"):
        first_seen_ts = float(row["first_seen_ts"])
        last_seen_ts = float(row["last_seen_ts"])
        result[str(row["account_id"])] = {
            "first_seen_ts": first_seen_ts,
            "first_seen_at": _timestamp_to_iso(first_seen_ts),
            "last_seen_ts": last_seen_ts,
            "last_seen_at": _timestamp_to_iso(last_seen_ts),
            "activity_span_seconds": round(last_seen_ts - first_seen_ts, 4),
            "coordinated_object_count": int(row["coordinated_object_count"]),
            "coordinated_content_count": int(row["coordinated_content_count"]),
        }
    return result


def _annotate_graph_activity(graph, rows: list[dict[str, Any]]) -> None:
    activity = _node_activity(rows)
    if not activity:
        return
    for node in graph.nodes():
        attrs = activity.get(str(node))
        if attrs:
            graph.nodes[node].update(attrs)


def _annotate_graph_context(
    graph,
    pairs: pd.DataFrame,
    rows: list[dict[str, Any]],
    *,
    posts: list[dict[str, Any]],
    comments: list[dict[str, Any]],
) -> None:
    records = [*posts, *comments]
    account_labels = _build_account_labels(records)
    content_meta = _build_content_metadata(posts, comments)

    node_objects: defaultdict[str, Counter[str]] = defaultdict(Counter)
    node_contents: defaultdict[str, list[str]] = defaultdict(list)
    for row in rows:
        account_id = str(row.get("account_id") or "").strip()
        object_id = str(row.get("object_id") or "").strip()
        content_id = str(row.get("content_id") or "").strip()
        if account_id and object_id:
            node_objects[account_id][object_id] += 1
        if account_id and content_id:
            node_contents[account_id].append(content_id)

    edge_objects: defaultdict[tuple[str, str], Counter[str]] = defaultdict(Counter)
    edge_contents: defaultdict[tuple[str, str], list[str]] = defaultdict(list)
    if not pairs.empty:
        for row in pairs.to_dict(orient="records"):
            account_id = str(row.get("account_id") or "").strip()
            account_id_y = str(row.get("account_id_y") or "").strip()
            if not account_id or not account_id_y:
                continue
            edge_key = tuple(sorted((account_id, account_id_y)))
            object_id = str(row.get("object_id") or "").strip()
            if object_id:
                edge_objects[edge_key][object_id] += 1
            for field in ("content_id", "content_id_y"):
                content_id = str(row.get(field) or "").strip()
                if content_id:
                    edge_contents[edge_key].append(content_id)

    for node in graph.nodes():
        account_id = str(node)
        object_entries = _rank_object_entries(node_objects.get(account_id, Counter()))
        content_entries = _top_content_entries(node_contents.get(account_id, []), content_meta)
        graph.nodes[node]["account_label"] = account_labels.get(account_id, account_id)
        graph.nodes[node]["shared_object_entries"] = object_entries
        graph.nodes[node]["shared_objects_preview"] = [entry["preview"] for entry in object_entries]
        graph.nodes[node]["content_preview_entries"] = content_entries
        graph.nodes[node]["content_previews"] = [
            entry["content_preview"]
            for entry in content_entries
            if entry.get("content_preview")
        ]

    for u, v in graph.edges():
        edge_key = tuple(sorted((str(u), str(v))))
        object_entries = _rank_object_entries(edge_objects.get(edge_key, Counter()))
        content_entries = _top_content_entries(edge_contents.get(edge_key, []), content_meta)
        graph[u][v]["shared_object_count"] = len(edge_objects.get(edge_key, Counter()))
        graph[u][v]["shared_object_entries"] = object_entries
        graph[u][v]["shared_objects_preview"] = [entry["preview"] for entry in object_entries]
        graph[u][v]["shared_content_entries"] = content_entries
        graph[u][v]["shared_content_previews"] = [
            entry["content_preview"]
            for entry in content_entries
            if entry.get("content_preview")
        ]


def analyze_coordination_records(
    posts: list[dict[str, Any]],
    comments: list[dict[str, Any]],
    *,
    time_window: int = 60,
    min_participation: int = 2,
    edge_weight: float = 0.5,
    platform: str | None = None,
    event_id: str | None = None,
) -> dict:
    """Run the canonical coordination baseline over already-normalized records."""
    if not posts and not comments:
        return _empty_result(
            event_id,
            platform,
            0,
            total_comments=0,
            error="No analyzable posts or comments found. Run data collection or choose another event/platform.",
        )

    rows = _build_coordination_rows(posts, item_id_key="post_id", item_prefix="post")
    rows.extend(_build_coordination_rows(comments, item_id_key="comment_id", item_prefix="comment"))

    if not rows:
        return _empty_result(
            event_id,
            platform,
            len(posts),
            total_comments=len(comments),
            error="Posts and comments do not contain analyzable shared objects (hashtags, URLs, shared URLs, or media URLs).",
        )

    pairs = detect_groups(pd.DataFrame(rows), time_window=time_window, min_participation=min_participation)
    if pairs.empty:
        return _empty_result(event_id, platform, len(posts), total_comments=len(comments))

    graph = generate_coordinated_network(pairs, edge_weight=edge_weight)
    _annotate_graph_activity(graph, rows)
    _annotate_graph_context(graph, pairs, rows, posts=posts, comments=comments)
    network_data = graph_to_dict(graph)
    account_data = account_stats(graph, pairs)
    group_data = group_stats(graph, pairs)
    cluster_data = network_data.get("clusters", [])

    return {
        "network": network_data,
        "account_stats": account_data.to_dict(orient="records"),
        "group_stats": group_data.to_dict(orient="records"),
        "cluster_stats": cluster_data,
        "summary": _summary(
            event_id=event_id,
            platform=platform,
            total_posts=len(posts),
            total_comments=len(comments),
            total_pairs=len(pairs),
            coordinated_accounts=graph.number_of_nodes(),
            coordinated_edges=graph.number_of_edges(),
            components=network_data["component_count"],
            clusters=network_data["cluster_count"],
        ),
    }


async def run_coordination_detection(
    time_window: int = 60,
    min_participation: int = 2,
    edge_weight: float = 0.5,
    platform: str | None = None,
    event_id: str | None = None,
) -> dict:
    """Run coordination detection over optionally event-scoped MongoDB posts."""
    mongo_db = get_mongo_db()
    posts = await load_event_posts(mongo_db, event_id=event_id, platform=platform)
    comments = await load_event_comments(mongo_db, event_id=event_id, platform=platform)
    return analyze_coordination_records(
        posts,
        comments,
        time_window=time_window,
        min_participation=min_participation,
        edge_weight=edge_weight,
        platform=platform,
        event_id=event_id,
    )
