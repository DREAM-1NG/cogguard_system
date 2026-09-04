"""MySQL 异步数据库连接管理。

使用 SQLAlchemy 2.0 async engine + aiomysql 驱动，提供：
- ``Base``：所有 ORM 模型的声明基类
- ``get_db``：FastAPI 依赖注入用的 async session 生成器
"""

from collections.abc import AsyncGenerator
from functools import lru_cache

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import settings


@lru_cache(maxsize=1)
def _get_engine():
    return create_async_engine(settings.mysql_url, echo=settings.BACKEND_DEBUG, pool_pre_ping=True)


@lru_cache(maxsize=1)
def _get_session_factory():
    return async_sessionmaker(_get_engine(), expire_on_commit=False)


def async_session_factory():
    """Backward-compatible session factory accessor."""
    return _get_session_factory()()


async def close_mysql() -> None:
    """Dispose the cached async engine without creating one during shutdown."""
    try:
        if _get_engine.cache_info().currsize:
            await _get_engine().dispose()
    finally:
        _get_session_factory.cache_clear()
        _get_engine.cache_clear()


class Base(DeclarativeBase):
    """所有 SQLAlchemy ORM 模型的声明基类。"""


async def get_db() -> AsyncGenerator[AsyncSession]:
    async with _get_session_factory()() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


__all__ = ["Base", "async_session_factory", "close_mysql", "get_db"]
