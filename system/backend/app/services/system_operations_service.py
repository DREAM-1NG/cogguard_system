"""Business-safe projections for authenticated system operations."""

from __future__ import annotations

from collections import Counter
from typing import Any

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.review_system import ReviewJob
from app.services import review_system_service


PURPOSE_TO_PROVIDER_TYPE = {
    "text_review": "text_llm",
    "media_verification": "vision_llm",
    "source_retrieval": "retrieval",
}
PROVIDER_TYPE_TO_PURPOSE = {
    provider_type: purpose
    for purpose, provider_type in PURPOSE_TO_PROVIDER_TYPE.items()
}


def provider_payload(payload: dict[str, Any]) -> dict[str, Any]:
    purpose = str(payload.get("purpose") or "")
    try:
        provider_type = PURPOSE_TO_PROVIDER_TYPE[purpose]
    except KeyError as exc:
        raise ValueError(f"Unsupported service purpose: {purpose}") from exc
    return {
        "name": payload.get("name"),
        "provider_type": provider_type,
        "base_url": payload.get("endpoint"),
        "model": payload.get("service_identifier"),
        "wire_api": payload.get("protocol"),
        "api_key": payload.get("credential"),
        "supports_vision": bool(payload.get("supports_media")),
        "metadata": {},
    }


def service_config_projection(provider: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": provider.get("id"),
        "name": provider.get("name"),
        "purpose": PROVIDER_TYPE_TO_PURPOSE.get(
            str(provider.get("provider_type") or ""),
            "text_review",
        ),
        "endpoint": provider.get("base_url") or "",
        "enabled": bool(provider.get("is_active")),
        "credential_configured": provider.get("api_key_status") == "configured",
        "supports_media": bool(provider.get("supports_vision")),
        "source": "environment" if provider.get("source") == "env_fallback" else "configured",
    }


async def list_service_configs(db: AsyncSession) -> dict[str, Any]:
    result = await review_system_service.list_provider_configs(db)
    return {
        "items": [service_config_projection(item) for item in result.get("items", [])]
    }


async def create_service_config(
    *,
    payload: dict[str, Any],
    user_id: int,
    db: AsyncSession,
) -> dict[str, Any]:
    provider = await review_system_service.create_provider_config(
        payload=provider_payload(payload),
        user_id=user_id,
        db=db,
    )
    return service_config_projection(provider)


async def activate_service_config(
    *,
    service_id: int,
    enabled: bool,
    db: AsyncSession,
) -> dict[str, Any]:
    provider = await review_system_service.activate_provider_config(
        provider_id=service_id,
        is_active=enabled,
        db=db,
    )
    return service_config_projection(provider)


async def check_service_config(service_id: int, db: AsyncSession) -> dict[str, Any]:
    result = await review_system_service.test_provider_config(service_id, db)
    available = result.get("status") == "ready"
    return {
        "availability": "available" if available else "needs_configuration",
        "message": (
            "Service connection settings are complete."
            if available
            else "Service connection settings need attention."
        ),
        "supports_media": bool(result.get("supports_vision")),
    }


async def operation_health(db: AsyncSession, *, recent_limit: int = 50) -> dict[str, Any]:
    result = await db.execute(
        select(ReviewJob.status)
        .order_by(desc(ReviewJob.created_at))
        .limit(recent_limit)
    )
    counts = Counter(str(status) for status in result.scalars().all())
    processing = counts["running"]
    waiting = counts["pending"] + counts["queued"]
    completed = counts["completed"]
    attention_required = counts["failed"]
    if attention_required:
        message = "Some recent background work needs operator attention."
    elif processing or waiting:
        message = "Background work is being processed normally."
    else:
        message = "No recent background work needs operator attention."
    return {
        "processing_count": processing,
        "waiting_count": waiting,
        "completed_count": completed,
        "attention_required_count": attention_required,
        "message": message,
    }


__all__ = [
    "activate_service_config",
    "check_service_config",
    "create_service_config",
    "list_service_configs",
    "operation_health",
    "provider_payload",
    "service_config_projection",
]
