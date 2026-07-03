"""账户监测相关 API 路由。"""

from fastapi import APIRouter, Depends, Query

from app.core.security import get_current_user, get_current_user_or_local_preview
from app.models.user import User
from app.services import account_service, bot_detection_service
from app.utils.response import success

router = APIRouter()


@router.get("/profiles")
async def list_profiles(
    platform: str | None = Query(None, description="限定平台"),
    event_id: str | None = Query(None, description="限定事件 ID"),
    _current_user: User = Depends(get_current_user),
):
    profiles = await account_service.get_account_profiles(platform=platform, event_id=event_id)
    return success(data=profiles)


@router.post("/bot-detection")
async def detect_bots(
    platform: str | None = Query(None, description="Limit to one platform"),
    event_id: str | None = Query(None, description="Limit to one event ID"),
    routing_budget: float = Query(0.2, ge=0, le=1, description="Share of accounts routed to BotRHG correction"),
    support_k: int = Query(8, ge=1, le=50, description="KNN support size for target-centered hyperedges"),
    _current_user: User | None = Depends(get_current_user_or_local_preview),
):
    result = await bot_detection_service.detect_social_bots(
        event_id=event_id,
        platform=platform,
        routing_budget=routing_budget,
        support_k=support_k,
    )
    return success(data=result)


@router.get("/detail/{account_id}")
async def get_detail(
    account_id: str,
    platform: str | None = Query(None, description="限定平台"),
    event_id: str | None = Query(None, description="限定事件 ID"),
    _current_user: User = Depends(get_current_user),
):
    detail = await account_service.get_account_detail(account_id, platform=platform, event_id=event_id)
    if not detail:
        return success(data=None, msg="账户不存在")
    return success(data=detail)
