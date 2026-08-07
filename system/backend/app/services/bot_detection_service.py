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
        result = await asyncio.to_thread(
            run_trained_botrhg_detection,
            posts,
            active_model,
            allow_legacy_fallback=False,
        )
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
