"""MySQL 异步数据库连接管理。

使用 SQLAlchemy 2.0 async engine + aiomysql 驱动，提供：
- ``Base``：所有 ORM 模型的声明基类
- ``get_db``：FastAPI 依赖注入用的 async session 生成器
"""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import settings

engine = create_async_engine(settings.mysql_url, echo=settings.BACKEND_DEBUG, pool_pre_ping=True)
async_session_factory = async_sessionmaker(engine, expire_on_commit=False)


class Base(DeclarativeBase):
    """所有 SQLAlchemy ORM 模型的声明基类。"""


async def get_db() -> AsyncGenerator[AsyncSession]:
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
