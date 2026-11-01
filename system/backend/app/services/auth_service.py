"""认证业务逻辑服务。

封装用户注册、登录、令牌刷新和个人信息获取等业务操作，
供 API 路由层调用。所有数据库操作通过注入的 AsyncSession 执行。
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    spend_dummy_password_verify,
    verify_password,
)
from app.models.user import User
from app.schemas.auth import LoginRequest, RegisterRequest, TokenResponse, UserInfo
from app.utils.exceptions import AuthError, ConflictError


async def ensure_default_admin(db: AsyncSession) -> None:
    """Seed the local administrator account when it does not exist yet.

    An existing ``admin`` row is left untouched: rewriting its password, role and
    active flag on every startup would silently revert an operator's password
    rotation or account suspension back to the well-known seed credential.
    """
    if not settings.DEFAULT_ADMIN_PASSWORD.strip():
        return
    result = await db.execute(select(User).where(User.username == "admin"))
    user = result.scalar_one_or_none()
    if user is not None:
        return

    db.add(
        User(
            username="admin",
            email="admin@cogguard.local",
            hashed_password=hash_password(settings.DEFAULT_ADMIN_PASSWORD),
            role="admin",
            is_active=True,
        )
    )


async def register(req: RegisterRequest, db: AsyncSession) -> UserInfo:
    """注册新用户，用户名或邮箱重复时抛出 ConflictError。"""
    result = await db.execute(
        select(User).where((User.username == req.username) | (User.email == req.email))
    )
    if result.scalar_one_or_none() is not None:
        raise ConflictError(msg="Username or email already exists")

    user = User(
        username=req.username,
        email=req.email,
        hashed_password=hash_password(req.password),
    )
    db.add(user)
    await db.flush()
    await db.refresh(user)
    return UserInfo.model_validate(user)


async def login(req: LoginRequest, db: AsyncSession) -> TokenResponse:
    """验证用户名密码，成功返回 access + refresh token 对。"""
    result = await db.execute(select(User).where(User.username == req.username))
    user = result.scalar_one_or_none()
    if user is None:
        # Hash anyway so a missing username costs the same time as a wrong
        # password; otherwise response latency enumerates valid accounts.
        spend_dummy_password_verify()
        raise AuthError(msg="Invalid username or password")
    if not verify_password(req.password, user.hashed_password):
        raise AuthError(msg="Invalid username or password")
    if not user.is_active:
        raise AuthError(msg="User is inactive")

    return TokenResponse(
        access_token=create_access_token(user.id, user.role),
        refresh_token=create_refresh_token(user.id),
    )


async def refresh_token(token: str, db: AsyncSession) -> TokenResponse:
    """使用 refresh token 换取新的令牌对。"""
    payload = decode_token(token)
    if payload.get("type") != "refresh":
        raise AuthError(msg="Invalid token type, expected refresh token")

    user_id = int(payload["sub"])
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None or not user.is_active:
        raise AuthError(msg="User not found or inactive")

    return TokenResponse(
        access_token=create_access_token(user.id, user.role),
        refresh_token=create_refresh_token(user.id),
    )


async def get_profile(user: User) -> UserInfo:
    """将 User ORM 对象转换为脱敏的 UserInfo 响应。"""
    return UserInfo.model_validate(user)
