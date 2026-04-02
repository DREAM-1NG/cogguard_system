"""API v1 路由聚合。

将各业务模块的路由挂载到统一的 ``/api/v1`` 前缀下。
"""

from fastapi import APIRouter

from app.api.v1 import auth, crawl

api_router = APIRouter(prefix="/api/v1")

api_router.include_router(auth.router, prefix="/auth", tags=["认证"])
api_router.include_router(crawl.router, prefix="/crawl", tags=["数据采集"])


@api_router.get("/health", tags=["系统"])
async def health_check():
    return {"status": "ok"}
