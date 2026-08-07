"""FastAPI 应用入口。

负责应用实例创建、生命周期管理（启动/关闭时的资源初始化与释放）、
CORS 中间件、全局异常处理器以及路由挂载。
"""

import asyncio
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router as api_v1_router
from app.api.v2.router import api_router as api_v2_router
from app.config import settings
from app.db.mongodb import close_mongo
from app.db.mysql import async_session_factory, close_mysql
from app.db.redis import close_redis
from app.services.auth_service import ensure_default_admin
from app.services.account_training_dispatch_outbox import run_account_training_dispatch_outbox_publisher
from app.utils.exceptions import AppException, app_exception_handler, generic_exception_handler
from app.utils.logger import logger


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("CogGuard backend starting up...")
    async with async_session_factory() as session:
        await ensure_default_admin(session)
        await session.commit()
    stop_event = asyncio.Event()
    publisher_task = asyncio.create_task(
        run_account_training_dispatch_outbox_publisher(stop_event),
        name="account-training-outbox-publisher",
    )
    app.state.account_training_outbox_publisher_task = publisher_task
    try:
        yield
    finally:
        logger.info("CogGuard backend shutting down...")
        stop_event.set()
        await asyncio.sleep(0)
        if not publisher_task.done():
            publisher_task.cancel()
        with suppress(asyncio.CancelledError):
            await publisher_task
        await close_mongo()
        await close_redis()
        await close_mysql()


app = FastAPI(
    title="CogGuard API",
    description="面向跨域认知操纵的智能联合防御系统",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_exception_handler(AppException, app_exception_handler)
app.add_exception_handler(Exception, generic_exception_handler)

app.include_router(api_v1_router)
app.include_router(api_v2_router)
