"""账户监测相关 API 路由。"""

from fastapi import APIRouter, Depends, Query

from app.core.security import get_current_user
from app.models.user import User
from app.services import account_service
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
