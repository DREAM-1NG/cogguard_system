"""Shared MongoDB readers for event-scoped analysis services."""

from __future__ import annotations

from typing import Any

POST_ANALYSIS_LIMIT = 10_000
COMMENT_ANALYSIS_LIMIT = 50_000


def build_event_filter(event_id: str | None = None, platform: str | None = None) -> dict[str, Any]:
    mongo_filter: dict[str, Any] = {}
    if event_id:
        mongo_filter["event_id"] = event_id
    if platform:
        mongo_filter["platform"] = platform
    return mongo_filter


def _get_collection(mongo_db: Any, collection_name: str) -> Any | None:
    if isinstance(mongo_db, dict):
        collection = mongo_db.get(collection_name)
        if collection is not None:
            return collection
    try:
        return mongo_db[collection_name]
    except (KeyError, TypeError):
        return None


async def load_event_posts(
    mongo_db: Any,
    *,
    event_id: str | None = None,
    platform: str | None = None,
    limit: int = POST_ANALYSIS_LIMIT,
) -> list[dict[str, Any]]:
    collection = _get_collection(mongo_db, "raw_posts")
    if collection is None:
        return []
    cursor = collection.find(build_event_filter(event_id, platform), {"_id": 0})
    return await cursor.to_list(length=limit)


async def load_event_comments(
    mongo_db: Any,
    *,
    event_id: str | None = None,
    platform: str | None = None,
    limit: int = COMMENT_ANALYSIS_LIMIT,
) -> list[dict[str, Any]]:
    collection = _get_collection(mongo_db, "raw_comments")
    if collection is None:
        return []
    cursor = collection.find(build_event_filter(event_id, platform), {"_id": 0})
    return await cursor.to_list(length=limit)


def analysis_scope_metadata(
    *,
    event_id: str | None = None,
    platform: str | None = None,
    posts_count: int = 0,
    comments_count: int | None = None,
) -> dict[str, Any]:
    scope = {"posts": posts_count}
    if comments_count is not None:
        scope["comments"] = comments_count
    return scope
