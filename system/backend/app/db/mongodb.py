"""MongoDB 异步连接管理。

使用 Motor 驱动，维护全局单例 client，提供按库名获取 database 的工具函数。
"""

from functools import lru_cache
from typing import Any

from app.config import settings


@lru_cache(maxsize=1)
def _motor_types():
    from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
    return AsyncIOMotorClient, AsyncIOMotorDatabase


_client: Any | None = None


def get_mongo_client():
    """获取全局 Motor client 单例，首次调用时创建。"""
    global _client
    if _client is None:
        AsyncIOMotorClient, _ = _motor_types()
        _client = AsyncIOMotorClient(settings.mongo_url)
    return _client


def get_mongo_db(db_name: str | None = None):
    client = get_mongo_client()
    return client[db_name or settings.MONGO_DATABASE]


async def close_mongo():
    global _client
    if _client is not None:
        _client.close()
        _client = None
