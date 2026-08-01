"""Service layer for account detection."""

from __future__ import annotations

from app.core.account_detection import build_nlpcc_method_card
from app.core.bot_detection import run_botrhg_detection
from app.core.trained_bot_detection import run_trained_botrhg_detection
from app.db.mongodb import get_mongo_db
from app.services.event_data import load_event_posts


async def detect_social_bots(
    *,
    event_id: str | None = None,
    platform: str | None = None,
    routing_budget: float = 0.2,
    support_k: int = 8,
) -> dict:
    """Run the current account detection runtime over collected posts."""
    mongo_db = get_mongo_db()
    posts = await load_event_posts(mongo_db, event_id=event_id, platform=platform)
    result = run_trained_botrhg_detection(posts)
    if result is None:
        result = run_botrhg_detection(posts, routing_budget=routing_budget, support_k=support_k)
    result["summary"]["event_id"] = event_id
    result["summary"]["platform"] = platform
    result["summary"]["post_count"] = len(posts)
    result["method_card"] = build_nlpcc_method_card()
    return result
