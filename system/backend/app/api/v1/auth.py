"""认证相关 API 路由。

提供用户注册、登录、令牌刷新和个人信息获取接口。
"""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_current_user
from app.db.mysql import get_db
from app.models.user import User
from app.schemas.auth import LoginRequest, RefreshRequest, RegisterRequest, TokenResponse, UserInfo
from app.services import auth_service
from app.utils.response import success

router = APIRouter()


@router.post("/register")
async def register(req: RegisterRequest, db: AsyncSession = Depends(get_db)):
    user_info = await auth_service.register(req, db)
    return success(data=user_info.model_dump())


@router.post("/login")
async def login(req: LoginRequest, db: AsyncSession = Depends(get_db)):
    tokens = await auth_service.login(req, db)
    return success(data=tokens.model_dump())


@router.post("/refresh")
async def refresh(req: RefreshRequest, db: AsyncSession = Depends(get_db)):
    tokens = await auth_service.refresh_token(req.refresh_token, db)
    return success(data=tokens.model_dump())


@router.get("/profile")
async def profile(current_user: User = Depends(get_current_user)):
    info = await auth_service.get_profile(current_user)
    return success(data=info.model_dump())
