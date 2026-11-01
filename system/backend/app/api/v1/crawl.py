"""Data collection API routes."""

from fastapi import APIRouter, BackgroundTasks, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_current_user
from app.db.mysql import get_db
from app.models.user import User
from app.schemas.crawl import (
    CrawlDataQuery,
    CrawlJobResponse,
    CrawlRequest,
    MediaDownloadRequest,
)
from app.services import crawl_service
from app.services import media_download_service
from app.tasks.crawl_tasks import execute_crawl_job, run_crawl_job
from app.utils.response import success

router = APIRouter()

SUPPORTED_PLATFORMS = [
    {
        "id": "weibo",
        "name": "微博",
        "status": "active",
        "hint": "使用仓库内置 social runtime，需准备 Cookie 或扫码登录环境",
    },
    {
        "id": "douyin",
        "name": "抖音",
        "status": "active",
        "hint": "使用仓库内置 social runtime",
    },
    {
        "id": "xhs",
        "name": "小红书",
        "status": "active",
        "hint": "使用仓库内置 social runtime",
    },
    {
        "id": "news",
        "name": "新闻链接",
        "status": "active",
        "hint": "在“链接”中填写文章 URL，系统将使用仓库内置 news runtime 提取内容",
    },
]


@router.get("/platforms")
async def list_platforms():
    return success(data=SUPPORTED_PLATFORMS)


@router.post("/social")
async def create_social_crawl(
    req: CrawlRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    job = await crawl_service.create_crawl_job(req, current_user.id, db)

    celery_task_id = f"local:{job.id}"
    if req.execution_mode == "queued":
        task = execute_crawl_job.delay(job.id, job.params_json)
        celery_task_id = task.id
    else:
        background_tasks.add_task(run_crawl_job, job.id, job.params_json)

    await crawl_service.update_job_status(
        job.id,
        "running",
        db,
        progress=0,
        celery_task_id=celery_task_id,
    )
    await db.commit()
    await db.refresh(job)

    return success(data=CrawlJobResponse.model_validate(job).model_dump(mode="json"))


@router.get("/jobs")
async def list_jobs(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    jobs, total = await crawl_service.list_jobs(
        db,
        current_user.id,
        page,
        page_size,
        include_system_owned=True,
    )
    items = [CrawlJobResponse.model_validate(job).model_dump(mode="json") for job in jobs]
    return success(data={"total": total, "items": items})


@router.post("/media-downloads")
async def create_media_download(
    req: MediaDownloadRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    job = await media_download_service.create_media_download_job(req, current_user.id, db)
    celery_task_id = f"local:{job.id}"
    background_tasks.add_task(media_download_service.run_media_download_job, job.id, job.params_json)
    await crawl_service.update_job_status(
        job.id,
        "running",
        db,
        progress=0,
        celery_task_id=celery_task_id,
    )
    await db.commit()
    await db.refresh(job)
    return success(data=CrawlJobResponse.model_validate(job).model_dump(mode="json"))


@router.get("/media-downloads/{job_id}")
async def get_media_download(
    job_id: int,
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(get_current_user),
):
    job = await media_download_service.get_media_download_job(job_id, db)
    if job is None:
        return success(data=None, msg="下载任务不存在")
    return success(data=job)


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
    event_id: str | None = None,
    has_media: bool | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    _current_user: User = Depends(get_current_user),
):
    query = CrawlDataQuery(
        platform=platform,
        keyword=keyword,
        event_id=event_id,
        has_media=has_media,
        page=page,
        page_size=page_size,
    )
    items, total = await crawl_service.query_posts(query)
    return success(data={"total": total, "items": items})
