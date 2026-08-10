"""Service layer for account detection."""

from __future__ import annotations

import asyncio
import time

from app.core.trained_bot_detection import run_trained_botrhg_detection
from app.db.mongodb import get_mongo_db
from app.db.mysql import async_session_factory
from app.services.event_data import load_event_posts
from app.services.account_model_runtime_service import get_active_account_model_resolution
from app.services.account_model_monitoring_service import (
    record_account_prediction_audits,
    record_account_runtime_error,
)


async def detect_social_bots(
    *,
    event_id: str | None = None,
    platform: str | None = None,
) -> dict:
    """Run the trained account detector over collected posts."""

    mongo_db = get_mongo_db()
    posts = await load_event_posts(mongo_db, event_id=event_id, platform=platform)
    pointer = await get_active_account_model_resolution()
    active_model = pointer.model if pointer.status == "available" else None
    pointer_invalid = pointer.status == "invalid"
    started = time.perf_counter()
    if pointer_invalid:
        result = {
            "method": "BotRHG",
            "status": "unavailable",
            "reason": "account_model_pointer_invalid",
            "pointer_failure_reason": pointer.reason,
            "accounts": [],
            "summary": {
                "account_count": 0,
                "bot_count": 0,
                "post_count": len(posts),
            },
        }
    elif active_model is None:
        result = {
            "method": "BotRHG",
            "status": "unavailable",
            "reason": "no_active_account_model_pointer",
            "accounts": [],
            "summary": {
                "account_count": 0,
                "bot_count": 0,
                "post_count": len(posts),
            },
        }
    else:
        result = await _run_platform_scoped_detection(posts, active_model)
    runtime_failed = active_model is not None and result is None
    if runtime_failed:
        result = {
            "method": "BotRHG",
            "status": "unavailable",
            "reason": "account_model_runtime_unavailable",
            "accounts": [],
            "summary": {
                "account_count": 0,
                "bot_count": 0,
                "post_count": len(posts),
            },
        }
    audit_model = active_model
    if pointer_invalid and pointer.model_version and pointer.pointer_revision > 0:
        audit_model = pointer
    if audit_model is not None:
        latency_ms = (time.perf_counter() - started) * 1000.0
        async with async_session_factory() as audit_session:
            if pointer_invalid or runtime_failed:
                audit_count = await record_account_runtime_error(
                    audit_session,
                    posts=posts,
                    model=audit_model,
                    event_id=event_id,
                    platform=platform,
                    latency_ms=latency_ms,
                    reason=(
                        pointer.reason
                        if pointer_invalid
                        else "account_model_runtime_load_failure"
                    ),
                )
            else:
                audit_count = await record_account_prediction_audits(
                    audit_session,
                    posts=posts,
                    result=result,
                    model=audit_model,
                    event_id=event_id,
                    platform=platform,
                    latency_ms=latency_ms,
                )
            await audit_session.commit()
        result["audit_persisted_count"] = audit_count
        result["prediction_latency_ms"] = round(latency_ms, 3)
        if pointer_invalid or runtime_failed:
            result["audit_status"] = "runtime_hard_error"
    else:
        result["audit_persisted_count"] = 0
        result["audit_status"] = (
            "invalid_pointer_without_model_identity"
            if pointer_invalid
            else "unavailable_without_active_pointer"
        )
    result["summary"]["event_id"] = event_id
    result["summary"]["platform"] = platform
    result["summary"]["post_count"] = len(posts)
    return result


async def _run_platform_scoped_detection(posts: list[dict], active_model) -> dict | None:
    """Keep account identities and support hypergraphs inside one platform."""

    grouped: dict[str, list[dict]] = {}
    for post in posts:
        platform = str(post.get("platform") or "unknown").strip().lower()
        grouped.setdefault(platform, []).append(post)

    platform_results: list[tuple[str, dict]] = []
    for platform, scoped_posts in grouped.items():
        result = await asyncio.to_thread(
            run_trained_botrhg_detection,
            scoped_posts,
            active_model,
            allow_legacy_fallback=False,
        )
        if result is None:
            return None
        platform_results.append((platform, result))

    if not platform_results:
        return {
            "method": "BotRHG",
            "accounts": [],
            "summary": {"account_count": 0, "bot_count": 0, "post_count": 0},
        }

    accounts = [
        {**row, "platform": platform}
        for platform, platform_result in platform_results
        for row in platform_result.get("accounts", [])
    ]
    first_result = platform_results[0][1]
    summary = dict(first_result.get("summary") or {})
    summary.update(
        {
            "account_count": len(accounts),
            "bot_count": sum(row.get("final_prediction") == "bot" for row in accounts),
            "routed_count": sum(bool(row.get("routed")) for row in accounts),
            "post_count": len(posts),
            "platform_count": len(platform_results),
        }
    )
    merged = {
        key: first_result[key]
        for key in ("method", "runtime_mode", "model_card")
        if key in first_result
    }
    return {**merged, "accounts": accounts, "summary": summary}
