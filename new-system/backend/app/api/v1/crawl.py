"""数据采集相关 API 路由。

提供采集任务创建、任务列表查询、采集数据查询以及支持平台列表接口。
所有需要鉴权的接口通过 ``get_current_user`` 依赖保护。
"""

import json

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_current_user
from app.db.mysql import get_db
from app.models.user import User
from app.schemas.crawl import CrawlDataQuery, CrawlJobResponse, CrawlRequest, PostListResponse
from app.services import crawl_service
from app.tasks.crawl_tasks import execute_crawl_job
from app.utils.response import success

router = APIRouter()

SUPPORTED_PLATFORMS = [
    {"id": "mock_weibo", "name": "模拟微博（测试）", "status": "active"},
    {"id": "weibo", "name": "微博", "status": "coming_soon"},
    {"id": "douyin", "name": "抖音", "status": "coming_soon"},
    {"id": "xhs", "name": "小红书", "status": "coming_soon"},
]


@router.get("/platforms")
async def list_platforms():
    return success(data=SUPPORTED_PLATFORMS)


@router.post("/social")
async def create_social_crawl(
    req: CrawlRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    job = await crawl_service.create_crawl_job(req, current_user.id, db)

    task = execute_crawl_job.delay(job.id, job.params_json)

    await crawl_service.update_job_status(
        job.id, "running", db, progress=0, celery_task_id=task.id
    )

    return success(data=CrawlJobResponse.model_validate(job).model_dump(mode="json"))


@router.get("/jobs")
async def list_jobs(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    jobs, total = await crawl_service.list_jobs(db, current_user.id, page, page_size)
    items = [CrawlJobResponse.model_validate(j).model_dump(mode="json") for j in jobs]
    return success(data={"total": total, "items": items})


@router.delete("/jobs/{job_id}")
async def delete_job(
    job_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    deleted = await crawl_service.delete_job(job_id, current_user.id, db)
    if not deleted:
        return success(data=None, msg="任务不存在或无权操作")
    return success(msg="任务已删除")


@router.post("/jobs/{job_id}/cancel")
async def cancel_job(
    job_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    cancelled = await crawl_service.cancel_job(job_id, current_user.id, db)
    if not cancelled:
        return success(data=None, msg="任务不存在或无法取消")
    return success(msg="任务已取消")


@router.get("/data")
async def query_data(
    platform: str | None = None,
    keyword: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    _current_user: User = Depends(get_current_user),
):
    query = CrawlDataQuery(platform=platform, keyword=keyword, page=page, page_size=page_size)
    items, total = await crawl_service.query_posts(query)
    return success(data={"total": total, "items": items})
