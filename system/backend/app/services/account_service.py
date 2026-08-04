"""Business-facing account profile service."""

from __future__ import annotations

import asyncio
import hashlib
from collections import OrderedDict
from typing import Any

from app.core.account_profiler import build_account_profiles
from app.core.trained_bot_detection import run_trained_botrhg_detection
from app.db.mongodb import get_mongo_db
from app.services.event_data import load_event_posts

_ASSESSMENT_CACHE: OrderedDict[str, dict[str, dict[str, str]]] = OrderedDict()
_ASSESSMENT_CACHE_LIMIT = 4


async def get_account_profiles(platform: str | None = None, event_id: str | None = None) -> list[dict]:
    """Return concise account profiles with the trained detector conclusion."""

    mongo_db = get_mongo_db()
    posts = await load_event_posts(mongo_db, event_id=event_id, platform=platform)
    assessments = await _model_assessments(posts)
    profiles = [
        _profile_projection(profile, assessments.get(str(profile.get("account_id") or "")))
        for profile in build_account_profiles(posts)
    ]
    return sorted(profiles, key=_profile_sort_key)


async def get_account_detail(
    account_id: str,
    platform: str | None = None,
    event_id: str | None = None,
) -> dict | None:
    """Return one account's business profile and its recent public content."""

    mongo_db = get_mongo_db()
    scope_posts = await load_event_posts(mongo_db, event_id=event_id, platform=platform)
    posts = [post for post in scope_posts if str(post.get("author_id") or "") == account_id]

    if not posts:
        return None

    profiles = build_account_profiles(posts)
    profile = profiles[0] if profiles else {}
    assessments = await _model_assessments(scope_posts)

    recent_posts = sorted(posts, key=lambda p: p.get("timestamp", ""), reverse=True)[:20]
    for post in recent_posts:
        post.pop("raw_data", None)
        for key, value in list(post.items()):
            if hasattr(value, "isoformat"):
                post[key] = value.isoformat()

    return {
        **_profile_projection(profile, assessments.get(account_id)),
        "recent_posts": recent_posts,
    }


async def _model_assessments(posts: list[dict[str, Any]]) -> dict[str, dict[str, str]]:
    """Run the repository-owned account detector once for the selected corpus."""

    if not posts:
        return {}
    fingerprint = _assessment_fingerprint(posts)
    cached = _ASSESSMENT_CACHE.get(fingerprint)
    if cached is not None:
        _ASSESSMENT_CACHE.move_to_end(fingerprint)
        return cached
    result = await asyncio.to_thread(run_trained_botrhg_detection, posts)
    if result is None:
        return {}
    assessments = {
        str(row.get("account_id") or ""): _assessment_projection(row)
        for row in result.get("accounts", [])
        if str(row.get("account_id") or "")
    }
    _ASSESSMENT_CACHE[fingerprint] = assessments
    _ASSESSMENT_CACHE.move_to_end(fingerprint)
    while len(_ASSESSMENT_CACHE) > _ASSESSMENT_CACHE_LIMIT:
        _ASSESSMENT_CACHE.popitem(last=False)
    return assessments


def _assessment_fingerprint(posts: list[dict[str, Any]]) -> str:
    digest = hashlib.sha256()
    for post in sorted(
        posts,
        key=lambda row: (
            str(row.get("author_id") or ""),
            str(row.get("post_id") or row.get("id") or ""),
            str(row.get("timestamp") or ""),
        ),
    ):
        for value in (
            post.get("author_id"),
            post.get("post_id") or post.get("id"),
            post.get("timestamp"),
            post.get("content"),
        ):
            digest.update(str(value or "").encode("utf-8"))
            digest.update(b"\0")
    return digest.hexdigest()


def _assessment_projection(result: dict[str, Any] | None) -> dict[str, str]:
    """Reduce detector output to the conclusion needed by an analyst."""

    if result and result.get("final_prediction") == "bot":
        return {"level": "attention", "label": "需关注"}
    if result:
        return {"level": "normal", "label": "未见异常"}
    return {"level": "pending", "label": "暂无研判"}


def _profile_projection(profile: dict[str, Any], assessment: dict[str, str] | None) -> dict[str, Any]:
    """Keep rule-derived profile scores out of the analyst-facing response."""

    return {
        "account_id": str(profile.get("account_id") or ""),
        "author_name": str(profile.get("author_name") or profile.get("account_id") or "未命名账号"),
        "platform": str(profile.get("platform") or ""),
        "user_url": str(profile.get("user_url") or ""),
        "post_count": int(profile.get("post_count") or 0),
        "active_hours": int(profile.get("active_hours") or 0),
        "min_interval_seconds": round(float(profile.get("min_interval_seconds") or 0), 1),
        "assessment": assessment or _assessment_projection(None),
    }


def _profile_sort_key(profile: dict[str, Any]) -> tuple[int, int, str]:
    level = str((profile.get("assessment") or {}).get("level") or "pending")
    priority = {"attention": 0, "normal": 1, "pending": 2}.get(level, 2)
    return priority, -int(profile.get("post_count") or 0), str(profile.get("author_name") or "")
