"""Normalization helpers for internal news runtime outputs."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.models.post import StandardPost

NEWS_PLATFORM_ID = "news"


def parse_time(value: Any) -> datetime:
    if value is None or value == "":
        return datetime.now(timezone.utc)
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    text = str(value).strip()
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return datetime.now(timezone.utc)


def news_data_to_post(data: dict[str, Any], detected: str | None) -> StandardPost:
    meta = data.get("meta_info") or {}
    if not isinstance(meta, dict):
        meta = {}
    title = str(data.get("title", ""))
    texts = data.get("texts") or []
    body = "\n".join(texts) if isinstance(texts, list) and texts else ""
    if not body:
        body = title
    author = str(meta.get("author_name", "") or "")
    nid = str(data.get("news_id", "") or "")
    url = str(data.get("news_url", "") or "")
    return StandardPost(
        platform=NEWS_PLATFORM_ID,
        post_id=nid or url or title[:32],
        content=body or title,
        author_id=author or "unknown",
        author_name=author or "unknown",
        timestamp=parse_time(meta.get("publish_time")),
        url=url,
        likes=0,
        reposts=0,
        comments_count=0,
        media_urls=list(data.get("images", []) or []),
        hashtags=[],
        raw_data={"news_extractor": data, "detected_platform": detected},
    )
