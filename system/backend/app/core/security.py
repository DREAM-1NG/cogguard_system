"""Authentication and authorization helpers."""

from datetime import datetime, timedelta, timezone

import bcrypt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.mysql import async_session_factory, get_db
from app.models.user import User
from app.utils.exceptions import AuthError

security_scheme = HTTPBearer()
optional_security_scheme = HTTPBearer(auto_error=False)
PREVIEW_ACCESS_TOKEN = "cogguard-preview-token"


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))


def create_access_token(user_id: int, role: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES
    )
    payload = {"sub": str(user_id), "role": role, "exp": expire, "type": "access"}
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def create_refresh_token(user_id: int) -> str:
    expire = datetime.now(timezone.utc) + timedelta(
        days=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS
    )
    payload = {"sub": str(user_id), "exp": expire, "type": "refresh"}
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
        )
    except JWTError as exc:
        raise AuthError(msg=f"Invalid token: {exc}") from exc


async def _get_active_user_by_id(user_id: int, db: AsyncSession) -> User:
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None or not user.is_active:
        raise AuthError(msg="User not found or inactive")
    return user


async def _get_preview_backing_user(db: AsyncSession) -> User:
    result = await db.execute(
        select(User).where(User.is_active.is_(True)).order_by(User.id.asc()).limit(1)
    )
    user = result.scalar_one_or_none()
    if user is None:
        raise AuthError(msg="Preview mode requires at least one active user")
    return user


async def _resolve_user_from_token(token: str, db: AsyncSession) -> User:
    payload = decode_token(token)
    if payload.get("type") != "access":
        raise AuthError(msg="Invalid token type")
    user_id = payload.get("sub")
    if user_id is None:
        raise AuthError(msg="Invalid token payload")
    return await _get_active_user_by_id(int(user_id), db)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    return await _resolve_user_from_token(credentials.credentials, db)


def require_roles(*allowed_roles: str):
    """FastAPI dependency factory for coarse role-gated endpoints."""
    allowed = {str(role) for role in allowed_roles}

    def _require_role(current_user: User = Depends(get_current_user)) -> User:
        role = str(getattr(current_user, "role", "") or "")
        if role not in allowed:
            expected = ", ".join(sorted(allowed))
            raise HTTPException(
                status_code=403,
                detail=f"KT3 operation requires role in [{expected}], current role: {role or 'unknown'}",
            )
        return current_user

    return _require_role


async def get_current_user_or_preview(
    credentials: HTTPAuthorizationCredentials = Depends(security_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    token = credentials.credentials
    if token == PREVIEW_ACCESS_TOKEN:
        return await _get_preview_backing_user(db)
    return await _resolve_user_from_token(token, db)


async def get_current_user_or_local_preview(
    credentials: HTTPAuthorizationCredentials | None = Depends(optional_security_scheme),
) -> User | None:
    """Allow the local preview token without forcing a backing DB user lookup."""
    if credentials is None:
        raise AuthError(msg="Authentication required")

    token = credentials.credentials
    if token == PREVIEW_ACCESS_TOKEN:
        return None

    async with async_session_factory() as session:
        return await _resolve_user_from_token(token, session)
