"""Redis 异步连接管理。

提供全局单例 Redis 客户端，用于缓存、会话管理和 Celery 消息队列。
"""

from __future__ import annotations

import redis.asyncio as aioredis

from app.config import settings

_pool: aioredis.Redis | None = None


def get_redis() -> aioredis.Redis:
    """获取全局 Redis 客户端单例，首次调用时创建。"""
    global _pool
    if _pool is None:
        _pool = aioredis.from_url(settings.redis_url, decode_responses=True)
    return _pool


async def close_redis():
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None
