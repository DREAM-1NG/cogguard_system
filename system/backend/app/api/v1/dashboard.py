"""Dashboard overview API routes."""

from collections.abc import AsyncGenerator

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import llm_cache
from app.core.security import get_current_user_or_local_preview
from app.db.mysql import async_session_factory
from app.models.user import User
from app.services import dashboard_service
from app.utils.response import success

router = APIRouter()
async def get_optional_db() -> AsyncGenerator[AsyncSession | None]:
    """Yield a MySQL session when available; keep dashboard Mongo data usable otherwise."""
    session_factory = async_session_factory()
    try:
        session = await session_factory.__aenter__()
    except Exception:
        yield None
        return
    try:
        yield session
    except Exception as exc:
        await session_factory.__aexit__(type(exc), exc, exc.__traceback__)
        raise
    else:
        await session_factory.__aexit__(None, None, None)


async def get_dashboard_viewer(
    viewer: User | None = Depends(get_current_user_or_local_preview),
) -> User | None:
    """Use the shared authentication boundary for dashboard access."""
    return viewer


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


@router.get("/llm-cache-status")
async def llm_cache_status(
    _current_user: User | None = Depends(get_dashboard_viewer),
):
    """Report whether LLM responses are live or replayed from cache.

    A walkthrough may run with replay enabled for stability, so the active mode
    has to be inspectable rather than implied.
    """
    return success(data=llm_cache.cache_stats())
