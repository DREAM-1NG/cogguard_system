"""Dashboard aggregation service for event-scoped monitoring overview."""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.mongodb import get_mongo_db
from app.models.risk_assessment import RiskAssessment
from app.services.event_data import build_event_filter, load_event_comments, load_event_posts

DEFAULT_EVENT_ID = "trump_visit_2026_05_21"

EVENT_LABELS = {
    "trump_visit_2026_05_21": {
        "event_name": "特朗普访华",
        "keywords": ["特朗普访华", "Trump China visit", "trump_visit"],
    }
}

LOCATION_ALIASES: dict[str, dict[str, Any]] = {
    "北京": {"name": "北京", "region": "中国北京", "country": "China", "coordinates": [116.4074, 39.9042]},
    "北京市": {"name": "北京", "region": "中国北京", "country": "China", "coordinates": [116.4074, 39.9042]},
    "上海": {"name": "上海", "region": "中国上海", "country": "China", "coordinates": [121.4737, 31.2304]},
    "广东": {"name": "广东", "region": "中国广东", "country": "China", "coordinates": [113.2665, 23.1322]},
    "广州": {"name": "广州", "region": "中国广东", "country": "China", "coordinates": [113.2644, 23.1291]},
    "深圳": {"name": "深圳", "region": "中国广东", "country": "China", "coordinates": [114.0579, 22.5431]},
    "浙江": {"name": "浙江", "region": "中国浙江", "country": "China", "coordinates": [120.1551, 30.2741]},
    "杭州": {"name": "杭州", "region": "中国浙江", "country": "China", "coordinates": [120.1551, 30.2741]},
    "江苏": {"name": "江苏", "region": "中国江苏", "country": "China", "coordinates": [118.7969, 32.0603]},
    "南京": {"name": "南京", "region": "中国江苏", "country": "China", "coordinates": [118.7969, 32.0603]},
    "中国": {"name": "中国", "region": "中国", "country": "China", "coordinates": [104.1954, 35.8617]},
    "美国": {"name": "美国", "region": "美国", "country": "United States of America", "coordinates": [-95.7129, 37.0902]},
    "United States": {"name": "美国", "region": "美国", "country": "United States of America", "coordinates": [-95.7129, 37.0902]},
    "United States of America": {"name": "美国", "region": "美国", "country": "United States of America", "coordinates": [-95.7129, 37.0902]},
    "日本": {"name": "日本", "region": "日本", "country": "Japan", "coordinates": [138.2529, 36.2048]},
    "韩国": {"name": "韩国", "region": "韩国", "country": "South Korea", "coordinates": [126.978, 37.5665]},
    "South Korea": {"name": "韩国", "region": "韩国", "country": "South Korea", "coordinates": [126.978, 37.5665]},
}

IP_LOCATION_PATHS = [
    ("author_profile", "ip_location"),
    ("author_profile", "ip_location_text"),
    ("author_profile", "location"),
    ("author_profile", "province"),
    ("author_profile", "city"),
    ("raw_data", "ip_location"),
    ("raw_data", "ip_location_text"),
    ("raw_data", "location"),
    ("raw_data", "region_name"),
    ("raw_data", "post_details_raw", "ip_location"),
    ("raw_data", "post_details_raw", "region_name"),
    ("raw_data", "post_details_raw", "mblog", "region_name"),
    ("raw_data", "post_details_raw", "mblog", "ip_location"),
    ("post_details_raw", "mblog", "region_name"),
    ("post_details_raw", "mblog", "ip_location"),
    ("ip_location",),
    ("location",),
]


def _clean_location_text(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    cleaned = value.strip()
    if not cleaned:
        return None
    if cleaned.lower() in {"unknown", "unavailable", "none", "null"}:
        return None
    if cleaned in {"未知", "未解析", "未定位", "未知属地"}:
        return None
    return cleaned


def _safe_iso(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


def _timestamp_sort_key(post: dict[str, Any]) -> tuple[int, str]:
    value = post.get("timestamp") or post.get("created_at") or post.get("publish_time")
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return 0, value.isoformat()
    if value:
        return 0, str(value)
    return 1, str(post.get("post_id") or "")


def _nested_get(data: dict[str, Any], path: tuple[str, ...]) -> Any:
    current: Any = data
    for key in path:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def extract_ip_location(post: dict[str, Any]) -> str | None:
    """Extract a human-readable IP/location label from normalized or raw post fields."""
    for path in IP_LOCATION_PATHS:
        value = _nested_get(post, path)
        cleaned = _clean_location_text(value)
        if cleaned:
            return cleaned
    return None


def resolve_location(ip_location: str | None) -> dict[str, Any]:
    """Resolve a rough map coordinate from a location string using a local v1 alias table."""
    if not ip_location:
        return {
            "ip_location": None,
            "resolved": False,
            "name": "未解析",
            "region": "未知",
            "country": None,
            "coordinates": None,
        }

    normalized = ip_location.strip()
    for alias, resolved in LOCATION_ALIASES.items():
        if alias in normalized:
            return {
                "ip_location": normalized,
                "resolved": True,
                **resolved,
            }

    return {
        "ip_location": normalized,
        "resolved": False,
        "name": normalized,
        "region": normalized,
        "country": None,
        "coordinates": None,
    }


def _event_meta(event_id: str | None) -> dict[str, Any]:
    fallback_name = event_id or "全部事件"
    meta = EVENT_LABELS.get(event_id or "", {})
    return {
        "event_name": meta.get("event_name", fallback_name),
        "keywords": meta.get("keywords", [event_id] if event_id else []),
    }


def _first_located_post(posts: list[dict[str, Any]]) -> dict[str, Any]:
    for post in sorted(posts, key=_timestamp_sort_key):
        if extract_ip_location(post):
            return post
    return {}


def _platform_distribution(posts: list[dict[str, Any]], comments: list[dict[str, Any]]) -> list[dict[str, Any]]:
    post_counts = Counter(str(post.get("platform") or "unknown") for post in posts)
    comment_counts = Counter(str(comment.get("platform") or "unknown") for comment in comments)
    platforms = sorted(set(post_counts) | set(comment_counts))
    return [
        {
            "platform": platform,
            "posts": post_counts.get(platform, 0),
            "comments": comment_counts.get(platform, 0),
            "total": post_counts.get(platform, 0) + comment_counts.get(platform, 0),
        }
        for platform in platforms
    ]


def _recent_posts(posts: list[dict[str, Any]], limit: int = 8) -> list[dict[str, Any]]:
    sorted_posts = sorted(posts, key=_timestamp_sort_key)[:limit]
    return [
        {
            "post_id": post.get("post_id"),
            "platform": post.get("platform"),
            "author_id": post.get("author_id"),
            "author_name": post.get("author_name") or post.get("nickname") or post.get("author_id"),
            "timestamp": _safe_iso(post.get("timestamp")),
            "content": post.get("content") or post.get("text") or "",
            "ip_location": extract_ip_location(post),
        }
        for post in sorted_posts
    ]


def _event_location(event_id: str | None, posts: list[dict[str, Any]], comments: list[dict[str, Any]]) -> dict[str, Any]:
    meta = _event_meta(event_id)
    origin_post = sorted(posts, key=_timestamp_sort_key)[0] if posts else {}
    origin_ip_location = extract_ip_location(origin_post)
    location_post = origin_post if origin_ip_location else _first_located_post(posts)
    location_ip_location = extract_ip_location(location_post)
    resolved = resolve_location(location_ip_location)
    platforms = sorted({str(post.get("platform")) for post in posts if post.get("platform")})

    return {
        "event_id": event_id,
        "event_name": meta["event_name"],
        "keywords": meta["keywords"],
        "origin_author": origin_post.get("author_name") or origin_post.get("nickname") or origin_post.get("author_id"),
        "origin_author_id": origin_post.get("author_id"),
        "origin_platform": origin_post.get("platform"),
        "origin_post_id": origin_post.get("post_id"),
        "first_post_time": _safe_iso(origin_post.get("timestamp")),
        "ip_location": resolved["ip_location"],
        "origin_ip_location": origin_ip_location,
        "location_source_author": location_post.get("author_name") or location_post.get("nickname") or location_post.get("author_id"),
        "location_source_author_id": location_post.get("author_id"),
        "location_source_platform": location_post.get("platform"),
        "location_source_post_id": location_post.get("post_id"),
        "location_source_time": _safe_iso(location_post.get("timestamp")),
        "location_source_ip_location": location_ip_location,
        "location_resolution_method": "origin_post" if origin_ip_location else ("first_geolocated_post" if location_ip_location else "unresolved"),
        "location_name": resolved["name"],
        "location_region": resolved["region"],
        "location_country": resolved["country"],
        "coordinates": resolved["coordinates"],
        "resolved": resolved["resolved"],
        "posts": len(posts),
        "comments": len(comments),
        "platforms": platforms,
    }


def _event_locations(
    event_id: str | None,
    posts: list[dict[str, Any]],
    comments: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    if event_id:
        return [_event_location(event_id, posts, comments)] if posts else []

    posts_by_event: dict[str | None, list[dict[str, Any]]] = {}
    comments_by_event: dict[str | None, list[dict[str, Any]]] = {}
    for post in posts:
        posts_by_event.setdefault(post.get("event_id"), []).append(post)
    for comment in comments:
        comments_by_event.setdefault(comment.get("event_id"), []).append(comment)

    event_ids = sorted({event for event in posts_by_event if event is not None})
    return [
        _event_location(event, posts_by_event.get(event, []), comments_by_event.get(event, []))
        for event in event_ids
        if posts_by_event.get(event)
    ]


async def _count_risk_reports(db: AsyncSession | None, event_id: str | None) -> tuple[int, str]:
    if db is None:
        return 0, "unavailable"

    try:
        await db.execute(text("SELECT 1"))
    except Exception:
        return 0, "unavailable"

    try:
        stmt = select(func.count(RiskAssessment.id))
        if event_id:
            stmt = stmt.where(RiskAssessment.event_id == event_id)
        result = await db.execute(stmt)
        return int(result.scalar() or 0), "ok"
    except Exception:
        return 0, "ok"


async def get_dashboard_overview(
    *,
    event_id: str | None = DEFAULT_EVENT_ID,
    db: AsyncSession | None = None,
) -> dict[str, Any]:
    """Build dashboard cards, platform distribution, and map event points."""
    mongo_db = get_mongo_db()
    effective_event_id = event_id or None
    posts = await load_event_posts(mongo_db, event_id=effective_event_id)
    comments = await load_event_comments(mongo_db, event_id=effective_event_id)
    risk_report_count, mysql_status = await _count_risk_reports(db, effective_event_id)
    platforms = _platform_distribution(posts, comments)
    event_locations = _event_locations(effective_event_id, posts, comments)
    unresolved_locations = [item for item in event_locations if not item.get("resolved")]

    return {
        "summary": {
            "event_count": 1 if effective_event_id and posts else len({post.get("event_id") for post in posts if post.get("event_id")}),
            "posts": len(posts),
            "comments": len(comments),
            "collected_items": len(posts) + len(comments),
            "risk_reports": risk_report_count,
            "coordination_groups": 0,
            "platform_count": len(platforms),
        },
        "platforms": platforms,
        "event_locations": event_locations,
        "unresolved_locations": unresolved_locations,
        "recent_posts": _recent_posts(posts),
        "meta": {
            "event_id": effective_event_id,
            "default_event_id": DEFAULT_EVENT_ID,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "mongo_filter": build_event_filter(effective_event_id),
            "data_source_status": {
                "mongo": "ok",
                "mysql": mysql_status,
            },
        },
    }
