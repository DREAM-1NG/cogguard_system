"""API v1 路由聚合。

将各业务模块的路由挂载到统一的 ``/api/v1`` 前缀下。
"""

from fastapi import APIRouter

from app.api.v1 import auth, crawl, coordination, accounts, propagation

api_router = APIRouter(prefix="/api/v1")

api_router.include_router(auth.router, prefix="/auth", tags=["认证"])
api_router.include_router(crawl.router, prefix="/crawl", tags=["数据采集"])
api_router.include_router(coordination.router, prefix="/coordination", tags=["协同检测"])
api_router.include_router(accounts.router, prefix="/accounts", tags=["账户监测"])
api_router.include_router(propagation.router, prefix="/propagation", tags=["传播归因"])


@api_router.get("/health", tags=["系统"])
async def health_check():
    return {"status": "ok"}
