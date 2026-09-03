"""Service layer for account detection."""

from __future__ import annotations

import copy
import json
import time

from app.config import settings
from app.core.account_detection import build_nlpcc_method_card
from app.core.bot_detection import run_botrhg_detection
from app.core.trained_bot_detection import run_trained_botrhg_detection
from app.db.mongodb import get_mongo_db
from app.db.redis import get_redis
from app.services.event_data import load_event_posts

_DETECTION_CACHE: dict[tuple[str, str, float, int], tuple[float, dict]] = {}
_DETECTION_CACHE_PREFIX = "botrhg:detection"


def _cache_key(
    event_id: str | None,
    platform: str | None,
    routing_budget: float,
    support_k: int,
) -> tuple[str, str, float, int]:
    return (event_id or "", platform or "", round(float(routing_budget), 6), int(support_k))


def _cache_key_str(event_id: str | None, platform: str | None, routing_budget: float, support_k: int) -> str:
    event_part, platform_part, budget_part, support_part = _cache_key(
        event_id, platform, routing_budget, support_k
    )
    return f"{_DETECTION_CACHE_PREFIX}:{event_part}:{platform_part}:{budget_part}:{support_part}"


def clear_detection_cache() -> None:
    _DETECTION_CACHE.clear()


async def set_detection_cache(
    event_id: str | None,
    platform: str | None,
    result: dict,
    *,
    routing_budget: float = 0.2,
    support_k: int = 8,
) -> None:
    ttl_seconds = max(0, int(settings.BOTRHG_CACHE_TTL_SECONDS))
    if ttl_seconds == 0:
        return
    cache_key = _cache_key(event_id, platform, routing_budget, support_k)
    _DETECTION_CACHE[cache_key] = (time.monotonic(), copy.deepcopy(result))

    redis_key = _cache_key_str(event_id, platform, routing_budget, support_k)
    payload = json.dumps(result, ensure_ascii=False, separators=(",", ":"))
    try:
        await get_redis().setex(redis_key, ttl_seconds, payload)
    except Exception:
        return


async def get_cached_detection(
    event_id: str | None,
    platform: str | None,
    *,
    routing_budget: float = 0.2,
    support_k: int = 8,
) -> dict | None:
    key = _cache_key(event_id, platform, routing_budget, support_k)
    item = _DETECTION_CACHE.get(key)
    if item is not None:
        created, result = item
        if time.monotonic() - created < max(0, settings.BOTRHG_CACHE_TTL_SECONDS):
            return copy.deepcopy(result)
        _DETECTION_CACHE.pop(key, None)

    redis_key = _cache_key_str(event_id, platform, routing_budget, support_k)
    try:
        payload = await get_redis().get(redis_key)
    except Exception:
        return None
    if payload is None:
        return None
    if isinstance(payload, bytes):
        payload = payload.decode("utf-8")
    try:
        result = json.loads(payload)
    except (TypeError, ValueError):
        return None
    if not isinstance(result, dict):
        return None
    _DETECTION_CACHE[key] = (time.monotonic(), copy.deepcopy(result))
    return copy.deepcopy(result)


async def detect_social_bots(
    *,
    event_id: str | None = None,
    platform: str | None = None,
    routing_budget: float = 0.2,
    support_k: int = 8,
) -> dict:
    """Run the current account detection runtime over collected posts."""
    cached = await get_cached_detection(event_id, platform, routing_budget=routing_budget, support_k=support_k)
    if cached is not None:
        return cached
    mongo_db = get_mongo_db()
    posts = await load_event_posts(mongo_db, event_id=event_id, platform=platform)
    result = run_trained_botrhg_detection(posts)
    if result is None:
        result = run_botrhg_detection(posts, routing_budget=routing_budget, support_k=support_k)
    result["summary"]["event_id"] = event_id
    result["summary"]["platform"] = platform
    result["summary"]["post_count"] = len(posts)
    result["method_card"] = build_nlpcc_method_card()
    await set_detection_cache(event_id, platform, result, routing_budget=routing_budget, support_k=support_k)
    return result
