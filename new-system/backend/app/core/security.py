"""认证与鉴权核心模块。

提供密码哈希（bcrypt）、JWT 令牌生成 / 校验，以及 FastAPI
依赖注入函数 ``get_current_user``，用于保护需要登录的接口。

令牌体系：
- access_token：短时效（默认 60 min），用于接口鉴权
- refresh_token：长时效（默认 7 天），用于无感刷新
"""

from datetime import datetime, timedelta, timezone

import bcrypt
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.mysql import get_db
from app.models.user import User
from app.utils.exceptions import AuthError

security_scheme = HTTPBearer()


def hash_password(password: str) -> str:
    """对明文密码进行 bcrypt 哈希。"""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    """校验明文密码与哈希是否匹配。"""
    return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))


def create_access_token(user_id: int, role: str) -> str:
    """生成 JWT access token，payload 含 user_id、role 和过期时间。"""
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {"sub": str(user_id), "role": role, "exp": expire, "type": "access"}
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def create_refresh_token(user_id: int) -> str:
    """生成长时效 refresh token，仅含 user_id。"""
    expire = datetime.now(timezone.utc) + timedelta(days=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS)
    payload = {"sub": str(user_id), "exp": expire, "type": "refresh"}
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def decode_token(token: str) -> dict:
    """解码并验证 JWT token，失败抛出 AuthError。"""
    try:
        return jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
    except JWTError as e:
        raise AuthError(msg=f"Invalid token: {e}")


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """FastAPI 依赖注入：从 Authorization header 解析 token 并返回当前用户。"""
    payload = decode_token(credentials.credentials)
    if payload.get("type") != "access":
        raise AuthError(msg="Invalid token type")
    user_id = payload.get("sub")
    if user_id is None:
        raise AuthError(msg="Invalid token payload")
    result = await db.execute(select(User).where(User.id == int(user_id)))
    user = result.scalar_one_or_none()
    if user is None or not user.is_active:
        raise AuthError(msg="User not found or inactive")
    return user
