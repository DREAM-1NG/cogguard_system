"""Business-facing account profile service."""

from __future__ import annotations

import asyncio
import hashlib
import json
from datetime import datetime, timezone
from typing import Any

from app.core.analysis.query_result_cache import (
    build_query_cache_key,
    get_or_build_query_result,
)
from app.core.account_profiler import build_account_profiles
from app.core.account_labeling import account_scope_key
from app.core.trained_bot_detection import run_trained_botrhg_detection
from app.config import settings
from app.db.mongodb import get_mongo_db
from app.db.mysql import async_session_factory
from app.models.account_labeling import AccountPredictionAudit
from app.services.event_data import load_event_posts
from app.services.account_model_runtime_service import get_active_account_model
from app.services.account_model_monitoring_service import account_prediction_input_fingerprint
from app.utils.exceptions import AppException
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

_ASSESSMENT_CACHE_NAMESPACE = "account-assessment-v2"


async def get_account_profiles(platform: str | None = None, event_id: str | None = None) -> list[dict]:
    """Return concise account profiles with the trained detector conclusion."""

    mongo_db = get_mongo_db()
    posts = await load_event_posts(mongo_db, event_id=event_id, platform=platform)
    assessments = await _model_assessments(posts)
    profiles = [
        _profile_projection(
            profile,
            assessments.get(
                account_scope_key(
                    str(profile.get("platform") or "unknown"),
                    str(profile.get("account_id") or ""),
                )
            ),
        )
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
    platforms = {
        str(post.get("platform") or "unknown").strip().lower()
        for post in posts
    }
    if not platform and len(platforms) > 1:
        raise AppException(
            code=400,
            msg="platform is required when an account id exists on multiple platforms.",
        )

    profiles = build_account_profiles(posts)
    profile = profiles[0] if profiles else {}
    assessments = await _model_assessments(scope_posts)

    recent_posts = sorted(posts, key=_post_timestamp, reverse=True)[:20]
    for post in recent_posts:
        post.pop("raw_data", None)
        for key, value in list(post.items()):
            if hasattr(value, "isoformat"):
                post[key] = value.isoformat()

    return {
        **_profile_projection(
            profile,
            assessments.get(
                account_scope_key(str(profile.get("platform") or "unknown"), account_id)
            ),
        ),
        "recent_posts": recent_posts,
    }


async def _model_assessments(posts: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Run the detector per platform and retain platform-scoped identities."""

    if not posts:
        return {}
    active_model = await get_active_account_model()
    stored_assessments = await _stored_model_assessments(posts, active_model)
    if stored_assessments:
        return stored_assessments
    grouped: dict[str, list[dict[str, Any]]] = {}
    for post in posts:
        platform = str(post.get("platform") or "unknown").strip().lower()
        grouped.setdefault(platform, []).append(post)

    assessments: dict[str, dict[str, Any]] = {}
    for platform, scoped_posts in grouped.items():
        fingerprint = _assessment_fingerprint(scoped_posts, active_model)
        cache_key = build_query_cache_key(_ASSESSMENT_CACHE_NAMESPACE, fingerprint)
        scoped_assessments = await get_or_build_query_result(
            cache_key,
            lambda scoped_posts=scoped_posts: _build_model_assessments(scoped_posts, active_model),
        )
        for account_id, assessment in scoped_assessments.items():
            assessments[account_scope_key(platform, str(account_id))] = assessment
    return assessments


async def _stored_model_assessments(
    posts: list[dict[str, Any]],
    active_model: Any | None,
) -> dict[str, dict[str, Any]]:
    """Load current-version prediction audits instead of rerunning slow inference."""

    if active_model is None:
        return {}
    grouped: dict[str, list[dict[str, Any]]] = {}
    for post in posts:
        account_id = str(post.get("author_id") or post.get("user_id") or "").strip()
        if not account_id:
            continue
        platform = str(post.get("platform") or "unknown").strip().lower() or "unknown"
        grouped.setdefault(account_scope_key(platform, account_id), []).append(post)
    if not grouped:
        return {}
    fingerprints = {
        scope_key: account_prediction_input_fingerprint(scoped_posts)
        for scope_key, scoped_posts in grouped.items()
    }
    try:
        async with async_session_factory() as session:
            rows = (
                await session.execute(
                    select(AccountPredictionAudit).where(
                        AccountPredictionAudit.family == "chinese_account_detection",
                        AccountPredictionAudit.model_version == str(active_model.model_version),
                        AccountPredictionAudit.pointer_revision == int(active_model.pointer_revision),
                        AccountPredictionAudit.input_fingerprint.in_(set(fingerprints.values())),
                    )
                )
            ).scalars().all()
    except (OSError, RuntimeError, SQLAlchemyError):
        return {}
    latest_by_scope: dict[str, AccountPredictionAudit] = {}
    for row in rows:
        scope_key = account_scope_key(row.platform, row.account_id)
        if fingerprints.get(scope_key) != row.input_fingerprint:
            continue
        previous = latest_by_scope.get(scope_key)
        if previous is None or (row.created_at, row.id) > (previous.created_at, previous.id):
            latest_by_scope[scope_key] = row
    if not latest_by_scope:
        return {}
    return {
        scope_key: _audit_assessment_projection(row, active_model)
        for scope_key, row in latest_by_scope.items()
    }


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
        str(row.get("account_id") or ""): _assessment_projection(row, active_model)
        for row in result.get("accounts", [])
        if str(row.get("account_id") or "")
    }
    return assessments


def _audit_assessment_projection(
    audit: AccountPredictionAudit,
    model_source: Any,
) -> dict[str, Any]:
    payload = _loads(audit.prediction_json)
    if payload.get("hard_error") or payload.get("abstained"):
        return {"level": "pending", "label": "暂无研判"}
    return _assessment_projection(
        {
            "final_prediction": payload.get("prediction"),
            "final_bot_probability": payload.get("final_probability"),
            "calibrated_bot_probability": payload.get("calibrated_probability"),
            "calibrated": payload.get("calibrated"),
            "routed": payload.get("routed"),
            "support_evidence": payload.get("support_evidence"),
        },
        model_source,
    )


def _assessment_fingerprint(posts: list[dict[str, Any]], model_source: Any | None = None) -> str:
    payload = {
        "model": {
            "model_version": getattr(model_source, "model_version", "local_fallback"),
            "artifact_hash": getattr(model_source, "artifact_hash", ""),
            "pointer_revision": getattr(model_source, "pointer_revision", 0),
        },
        # The strict runtime reads nested profile, interaction, and relation
        # fields; hash the complete Mongo projection so any of those changes
        # invalidate the detector result.
        # Preserve the sequence consumed by the runtime's account-text
        # linearizer; changing post order can change the model input.
        "posts": posts,
    }
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _assessment_projection(result: dict[str, Any] | None, model_source: Any | None) -> dict[str, Any]:
    """Reduce detector output to the conclusion needed by an analyst."""

    if result:
        prediction = str(result.get("final_prediction") or "").strip().lower()
        if prediction not in {"bot", "human"}:
            return {"level": "pending", "label": "暂无研判"}
        probability = _probability_or_none(result.get("calibrated_bot_probability"))
        if probability is None:
            probability = _probability_or_none(result.get("final_bot_probability"))
        return {
            "level": "attention" if prediction == "bot" else "normal",
            "label": "需关注" if prediction == "bot" else "未见异常",
            "prediction": prediction,
            "bot_probability": probability,
            "calibrated": bool(result.get("calibrated")),
            "routed": bool(result.get("routed")),
            "model_version": str(getattr(model_source, "model_version", "") or ""),
            "pointer_revision": int(getattr(model_source, "pointer_revision", 0) or 0),
            "similar_accounts": _similar_account_projection(result),
        }
    return {"level": "pending", "label": "暂无研判"}


def _similar_account_projection(result: dict[str, Any]) -> list[dict[str, Any]]:
    rows = result.get("support_evidence")
    if not isinstance(rows, list):
        return []
    projected = []
    for row in rows[:10]:
        if not isinstance(row, dict) or not str(row.get("account_id") or "").strip():
            continue
        projected.append(
            {
                "account_id": str(row["account_id"]),
                "similarity": _number_or_none(row.get("similarity")),
                "bot_probability": _probability_or_none(row.get("final_bot_probability")),
                "routed": bool(row.get("routed")),
            }
        )
    return projected


def _probability_or_none(value: Any) -> float | None:
    number = _number_or_none(value)
    return number if number is not None and 0.0 <= number <= 1.0 else None


def _number_or_none(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        return round(float(value), 6)
    except (TypeError, ValueError):
        return None


def _loads(payload: str) -> dict[str, Any]:
    try:
        value = json.loads(payload)
    except (TypeError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


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
        "assessment": assessment or _assessment_projection(None, None),
    }


def _profile_sort_key(profile: dict[str, Any]) -> tuple[int, int, str]:
    level = str((profile.get("assessment") or {}).get("level") or "pending")
    priority = {"attention": 0, "normal": 1, "pending": 2}.get(level, 2)
    return priority, -int(profile.get("post_count") or 0), str(profile.get("author_name") or "")


def _post_timestamp(post: dict[str, Any]) -> float:
    value = post.get("timestamp") or post.get("created_at")
    if isinstance(value, datetime):
        parsed = value
    else:
        text = str(value or "").strip()
        if not text:
            return 0.0
        try:
            parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError:
            return 0.0
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc).timestamp()
