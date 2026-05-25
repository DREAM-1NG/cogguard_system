"""Dashboard overview API routes."""

from collections.abc import AsyncGenerator

from fastapi import APIRouter, Depends, Query
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import decode_token
from app.db.mysql import async_session_factory
from app.models.user import User
from app.services import dashboard_service
from app.utils.exceptions import AuthError
from app.utils.response import success

router = APIRouter()
preview_security_scheme = HTTPBearer(auto_error=False)
PREVIEW_ACCESS_TOKEN = "cogguard-preview-token"


async def get_optional_db() -> AsyncGenerator[AsyncSession | None]:
    """Yield a MySQL session when available; keep dashboard Mongo data usable otherwise."""
    try:
        async with async_session_factory() as session:
            yield session
    except Exception:
        yield None


async def get_dashboard_viewer(
    credentials: HTTPAuthorizationCredentials | None = Depends(preview_security_scheme),
) -> User | None:
    """Allow the local preview token for the read-only dashboard overview."""
    if credentials is None:
        raise AuthError(msg="Authentication required")
    if credentials.credentials == PREVIEW_ACCESS_TOKEN:
        return None

    payload = decode_token(credentials.credentials)
    if payload.get("type") != "access":
        raise AuthError(msg="Invalid token type")
    user_id = payload.get("sub")
    if user_id is None:
        raise AuthError(msg="Invalid token payload")

    async with async_session_factory() as session:
        result = await session.execute(select(User).where(User.id == int(user_id)))
        user = result.scalar_one_or_none()
    if user is None or not user.is_active:
        raise AuthError(msg="User not found or inactive")
    return user


@router.get("/overview")
async def overview(
    event_id: str | None = Query(
        dashboard_service.DEFAULT_EVENT_ID,
        description="限定事件 ID；默认加载当前验收事件",
    ),
    _current_user: User | None = Depends(get_dashboard_viewer),
    db: AsyncSession | None = Depends(get_optional_db),
):
    """Return dashboard statistics and event map points."""
    data = await dashboard_service.get_dashboard_overview(event_id=event_id, db=db)
    return success(data=data)
