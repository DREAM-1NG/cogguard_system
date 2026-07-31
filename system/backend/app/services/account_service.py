"""Account profiling service."""

from __future__ import annotations

from typing import Any

from app.core.account_detection import build_account_detection_detail
from app.core.account_profiler import build_account_profiles
from app.db.mongodb import get_mongo_db
from app.services.event_data import build_event_filter, load_event_posts


async def get_account_profiles(platform: str | None = None, event_id: str | None = None) -> list[dict]:
    """Return account behavior profiles over optionally event-scoped posts."""
    mongo_db = get_mongo_db()
    posts = await load_event_posts(mongo_db, event_id=event_id, platform=platform)
    return build_account_profiles(posts)


async def get_account_detail(
    account_id: str,
    platform: str | None = None,
    event_id: str | None = None,
) -> dict | None:
    """Return one account profile and recent posts, optionally scoped to an event/platform."""
    mongo_db = get_mongo_db()
    mongo_filter: dict[str, Any] = build_event_filter(event_id=event_id, platform=platform)
    mongo_filter["author_id"] = account_id
    cursor = mongo_db["raw_posts"].find(mongo_filter, {"_id": 0})
    posts = await cursor.to_list(length=1000)

    if not posts:
        return None

    profiles = build_account_profiles(posts)
    profile = profiles[0] if profiles else {}
    detection = build_account_detection_detail(posts, account_id)

    recent_posts = sorted(posts, key=lambda p: p.get("timestamp", ""), reverse=True)[:20]
    for post in recent_posts:
        post.pop("raw_data", None)
        for key, value in list(post.items()):
            if hasattr(value, "isoformat"):
                post[key] = value.isoformat()

    return {
        **profile,
        "detection": detection,
        "detection_result": detection,
        "similar_users": detection.get("similar_users", []) if detection else [],
        "recent_posts": recent_posts,
    }
