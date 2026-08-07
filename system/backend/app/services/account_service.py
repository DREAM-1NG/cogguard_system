"""Business-facing account profile service."""

from __future__ import annotations

import asyncio
import hashlib
from typing import Any

from app.core.analysis.query_result_cache import (
    build_query_cache_key,
    get_or_build_query_result,
)
from app.core.account_profiler import build_account_profiles
from app.core.trained_bot_detection import run_trained_botrhg_detection
from app.config import settings
from app.db.mongodb import get_mongo_db
from app.services.event_data import load_event_posts
from app.services.account_model_runtime_service import get_active_account_model

_ASSESSMENT_CACHE_NAMESPACE = "account-assessment-v2"


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
    active_model = await get_active_account_model()
    fingerprint = _assessment_fingerprint(posts, active_model)
    cache_key = build_query_cache_key(_ASSESSMENT_CACHE_NAMESPACE, fingerprint)
    return await get_or_build_query_result(
        cache_key,
        lambda: _build_model_assessments(posts, active_model),
    )


async def _build_model_assessments(
    posts: list[dict[str, Any]],
    active_model: Any | None,
) -> dict[str, dict[str, str]]:
    """Run the detector only after the versioned projection cache misses."""

    if active_model is None:
        if not settings.account_model_local_bootstrap_allowed:
            return {}
        result = await asyncio.to_thread(run_trained_botrhg_detection, posts)
    else:
        result = await asyncio.to_thread(run_trained_botrhg_detection, posts, active_model, allow_legacy_fallback=False)
    if result is None:
        return {}
    assessments = {
        str(row.get("account_id") or ""): _assessment_projection(row)
        for row in result.get("accounts", [])
        if str(row.get("account_id") or "")
    }
    return assessments


def _assessment_fingerprint(posts: list[dict[str, Any]], model_source: Any | None = None) -> str:
    digest = hashlib.sha256()
    for value in (
        getattr(model_source, "model_version", "local_fallback"),
        getattr(model_source, "artifact_hash", ""),
        getattr(model_source, "pointer_revision", 0),
    ):
        digest.update(str(value).encode("utf-8"))
        digest.update(b"\0")
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
