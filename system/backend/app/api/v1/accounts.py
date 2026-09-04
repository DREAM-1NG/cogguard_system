"""Account monitoring API routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.core.security import get_current_user
from app.models.user import User
from app.services import account_service, bot_detection_service
from app.utils.response import success

router = APIRouter()

_LATEST_DETECTION_ACCOUNT_FIELDS = (
    "account_id",
    "account_label",
    "final_prediction",
    "base_prediction",
    "base_bot_probability",
    "final_bot_probability",
    "local_reliability",
    "routed",
    "post_count",
)


def _compact_latest_detection(result: dict | None) -> dict | None:
    if not isinstance(result, dict):
        return result
    compact = {
        key: value
        for key, value in result.items()
        if key not in {"accounts"}
    }
    compact["accounts"] = [
        {field: account[field] for field in _LATEST_DETECTION_ACCOUNT_FIELDS if field in account}
        for account in result.get("accounts", [])
        if isinstance(account, dict)
    ]
    compact["response_compacted"] = True
    return compact


@router.get("/profiles")
async def list_profiles(
    platform: str | None = Query(None, description="Optional platform filter"),
    event_id: str | None = Query(None, description="Optional event filter"),
    _current_user: User = Depends(get_current_user),
):
    profiles = await account_service.get_account_profiles(platform=platform, event_id=event_id)
    return success(data=profiles)


@router.post("/bot-detection")
async def detect_bots(
    platform: str | None = Query(None, description="Optional platform filter"),
    event_id: str | None = Query(None, description="Optional event filter"),
    routing_budget: float = Query(0.2, ge=0, le=1, description="Fraction routed to the correction stage"),
    support_k: int = Query(8, ge=1, le=50, description="Support neighborhood size"),
    _current_user: User = Depends(get_current_user),
):
    result = await bot_detection_service.detect_social_bots(
        event_id=event_id,
        platform=platform,
        routing_budget=routing_budget,
        support_k=support_k,
    )
    return success(data=result)


@router.get("/bot-detection/latest")
async def latest_detection(
    platform: str | None = Query(None, description="Optional platform filter"),
    event_id: str | None = Query(None, description="Optional event filter"),
    routing_budget: float = Query(0.2, ge=0, le=1),
    support_k: int = Query(8, ge=1, le=50),
    _current_user: User = Depends(get_current_user),
):
    result = await bot_detection_service.detect_social_bots(
        event_id=event_id,
        platform=platform,
        routing_budget=routing_budget,
        support_k=support_k,
    )
    return success(data=_compact_latest_detection(result))


@router.get("/detail/{account_id}")
async def get_detail(
    account_id: str,
    platform: str | None = Query(None, description="Optional platform filter"),
    event_id: str | None = Query(None, description="Optional event filter"),
    _current_user: User = Depends(get_current_user),
):
    detail = await account_service.get_account_detail(account_id, platform=platform, event_id=event_id)
    if not detail:
        return success(data=None, msg="Account not found")
    return success(data=detail)
