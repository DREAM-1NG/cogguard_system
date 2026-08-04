"""Service layer for account detection."""

from __future__ import annotations

import asyncio

from app.core.trained_bot_detection import run_trained_botrhg_detection
from app.db.mongodb import get_mongo_db
from app.services.event_data import load_event_posts


async def detect_social_bots(
    *,
    event_id: str | None = None,
    platform: str | None = None,
) -> dict:
    """Run the trained account detector over collected posts."""

    mongo_db = get_mongo_db()
    posts = await load_event_posts(mongo_db, event_id=event_id, platform=platform)
    result = await asyncio.to_thread(run_trained_botrhg_detection, posts)
    if result is None:
        result = {
            "method": "BotRHG",
            "accounts": [],
            "summary": {
                "account_count": 0,
                "bot_count": 0,
                "post_count": len(posts),
            },
        }
    result["summary"]["event_id"] = event_id
    result["summary"]["platform"] = platform
    result["summary"]["post_count"] = len(posts)
    return result
