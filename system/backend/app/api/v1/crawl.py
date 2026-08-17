"""Data collection API routes."""

from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_current_user
from app.db.mysql import get_db
from app.models.user import User
from app.models.task import CrawlJob
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


async def _require_readable_job(
    *,
    job_id: int,
    db: AsyncSession,
    current_user: User,
    expected_job_type: str | None = None,
) -> CrawlJob:
    result = await db.execute(select(CrawlJob).where(CrawlJob.id == job_id))
    job = result.scalar_one_or_none()
    if job is None or (expected_job_type is not None and job.job_type != expected_job_type):
        raise HTTPException(status_code=404, detail="任务不存在")
    if job.created_by not in {current_user.id, 0}:
        raise HTTPException(status_code=403, detail="无权读取该任务")
    return job


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
    current_user: User = Depends(get_current_user),
):
    await _require_readable_job(
        job_id=job_id,
        db=db,
        current_user=current_user,
        expected_job_type=media_download_service.MEDIA_DOWNLOAD_JOB_TYPE,
    )
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
    crawl_job_id: int | None = None,
    platform: str | None = None,
    keyword: str | None = None,
    event_id: str | None = None,
    has_media: bool | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if crawl_job_id is not None:
        await _require_readable_job(job_id=crawl_job_id, db=db, current_user=current_user)
    query = CrawlDataQuery(
        crawl_job_id=crawl_job_id,
        platform=platform,
        keyword=keyword,
        event_id=event_id,
        has_media=has_media,
        page=page,
        page_size=page_size,
    )
    items, total = await crawl_service.query_posts(query)
    return success(data={"total": total, "items": items})


@router.get("/posts/{platform}/{post_id}/comments")
async def get_post_comments(
    platform: str,
    post_id: str,
    crawl_job_id: int = Query(..., ge=1),
    limit: int = Query(3, ge=1, le=3),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await _require_readable_job(job_id=crawl_job_id, db=db, current_user=current_user)
    items = await crawl_service.query_post_comments(
        platform=platform,
        post_id=post_id,
        crawl_job_id=crawl_job_id,
        limit=limit,
    )
    return success(data={"items": items})


@router.get("/posts/{platform}/{post_id}/media")
async def get_post_media(
    platform: str,
    post_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    items = await media_download_service.find_downloaded_post_media(
        platform=platform,
        post_id=post_id,
        user_id=current_user.id,
        db=db,
    )
    return success(data={"items": items})


@router.get("/media-downloads/{job_id}/items/{item_index}/content")
async def get_media_download_content(
    job_id: int,
    item_index: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    job = await _require_readable_job(
        job_id=job_id,
        db=db,
        current_user=current_user,
        expected_job_type=media_download_service.MEDIA_DOWNLOAD_JOB_TYPE,
    )
    item = media_download_service.resolve_manifest_media_item(
        media_download_service.read_job_manifest(job),
        item_index=item_index,
    )
    if item is None:
        raise HTTPException(status_code=404, detail="本地媒体文件不存在或不可用")
    content_type = media_download_service.preview_content_type(item)
    if content_type is None:
        raise HTTPException(status_code=415, detail="该本地媒体格式暂不支持浏览器预览")
    return FileResponse(Path(item["path"]), media_type=content_type)
