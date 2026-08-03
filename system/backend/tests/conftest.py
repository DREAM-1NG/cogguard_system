"""pytest 公共 fixtures 配置。

提供测试用 MySQL 数据库自动建表/销表、httpx 异步测试客户端、
预认证客户端等 fixture，所有测试文件均可直接引用。

测试策略：
- 不依赖 Docker 的测试（Mock 爬虫、Normalizer）可直接运行
- 需要 MySQL 的测试（认证、采集任务）在 DB 不可用时自动跳过
"""

import asyncio
import os
import sys
import warnings
from collections.abc import AsyncGenerator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.pool import NullPool
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings
from app.db.mysql import Base, get_db
from app.db.mongodb import get_mongo_db
from app.main import app

if sys.platform.startswith("win"):
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

_DB_AVAILABLE = None


def _check_db_available() -> bool:
    """Quick sync check to see if MySQL test database is reachable."""
    global _DB_AVAILABLE
    if _DB_AVAILABLE is not None:
        return _DB_AVAILABLE
    try:
        from sqlalchemy import create_engine, text
        sync_url = settings.mysql_url_test.replace("+aiomysql", "+pymysql")
        eng = create_engine(sync_url, pool_pre_ping=True)
        with eng.connect() as conn:
            conn.execute(text("SELECT 1"))
        eng.dispose()
        _DB_AVAILABLE = True
    except Exception:
        _DB_AVAILABLE = False
    return _DB_AVAILABLE


needs_db = pytest.mark.skipif(
    not _check_db_available() if os.environ.get("COGGUARD_TEST_DB") != "1" else False,
    reason="MySQL test database not available (set COGGUARD_TEST_DB=1 to force)",
)

test_engine = create_async_engine(settings.mysql_url_test, echo=False, poolclass=NullPool) if _check_db_available() else None
test_session_factory = async_sessionmaker(test_engine, expire_on_commit=False) if test_engine else None


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(autouse=True)
def ensure_default_event_loop():
    """Keep legacy get_event_loop() tests working after asyncio.run() closes a loop."""
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            asyncio.get_event_loop()
    except RuntimeError:
        asyncio.set_event_loop(asyncio.new_event_loop())
    yield
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            asyncio.get_event_loop()
    except RuntimeError:
        asyncio.set_event_loop(asyncio.new_event_loop())


@pytest.fixture
async def setup_database():
    """Create and tear down all tables. Only used by tests that request it."""
    if test_engine is None:
        pytest.skip("MySQL not available")
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture
async def db_session(setup_database) -> AsyncGenerator[AsyncSession]:
    """Provide a committed test MySQL session for persistence-backed tests."""
    if test_session_factory is None:
        pytest.skip("MySQL not available")
    async with test_session_factory() as session:
        yield session
        await session.commit()


async def override_get_db() -> AsyncGenerator[AsyncSession]:
    if test_session_factory is None:
        pytest.skip("MySQL not available")
    async with test_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture
async def client() -> AsyncGenerator[AsyncClient]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
async def auth_client(setup_database, client: AsyncClient) -> AsyncClient:
    """Client pre-authenticated with a test user. Requires DB."""
    await client.post(
        "/api/v1/auth/register",
        json={"username": "testuser", "email": "test@example.com", "password": "testpass123"},
    )
    resp = await client.post(
        "/api/v1/auth/login",
        json={"username": "testuser", "password": "testpass123"},
    )
    token = resp.json()["data"]["access_token"]
    client.headers["Authorization"] = f"Bearer {token}"
    return client


@pytest.fixture
def mongo_db():
    return get_mongo_db(settings.MONGO_DATABASE_TEST)
