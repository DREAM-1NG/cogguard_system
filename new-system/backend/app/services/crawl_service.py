"""数据采集业务逻辑服务。

管理采集任务生命周期（创建、状态更新、列表查询），
以及从 MongoDB 查询已采集的标准化数据。
"""

import json
from datetime import datetime, timezone

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.mongodb import get_mongo_db
from app.models.task import CrawlJob
from app.schemas.crawl import CrawlDataQuery, CrawlRequest


async def create_crawl_job(
    req: CrawlRequest, user_id: int, db: AsyncSession
) -> CrawlJob:
    """创建采集任务记录并写入 MySQL，返回新建的 CrawlJob 实例。"""
    job = CrawlJob(
        job_type="social",
        platform=req.platform,
        params_json=json.dumps(req.model_dump(), ensure_ascii=False, default=str),
        status="pending",
        created_by=user_id,
    )
    db.add(job)
    await db.flush()
    await db.refresh(job)
    return job


async def update_job_status(
    job_id: int,
    status: str,
    db: AsyncSession,
    progress: int = 0,
    result_summary: str | None = None,
    celery_task_id: str | None = None,
) -> None:
    """更新采集任务的状态、进度和结果摘要。"""
    result = await db.execute(select(CrawlJob).where(CrawlJob.id == job_id))
    job = result.scalar_one_or_none()
    if job is None:
        return
    job.status = status
    job.progress = progress
    if result_summary is not None:
        job.result_summary = result_summary
    if celery_task_id is not None:
        job.celery_task_id = celery_task_id
    if status in ("completed", "failed"):
        job.finished_at = datetime.now(timezone.utc)
    await db.flush()


async def list_jobs(
    db: AsyncSession, user_id: int, page: int = 1, page_size: int = 20
) -> tuple[list[CrawlJob], int]:
    """分页查询当前用户创建的采集任务列表，返回 (任务列表, 总数)。"""
    count_q = select(func.count()).select_from(CrawlJob).where(CrawlJob.created_by == user_id)
    total = (await db.execute(count_q)).scalar() or 0

    q = (
        select(CrawlJob)
        .where(CrawlJob.created_by == user_id)
        .order_by(CrawlJob.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    result = await db.execute(q)
    return list(result.scalars().all()), total


async def delete_job(job_id: int, user_id: int, db: AsyncSession) -> bool:
    """删除指定采集任务及其关联的 MongoDB 数据。"""
    result = await db.execute(
        select(CrawlJob).where(CrawlJob.id == job_id, CrawlJob.created_by == user_id)
    )
    job = result.scalar_one_or_none()
    if job is None:
        return False

    mongo_db = get_mongo_db()
    await mongo_db["raw_posts"].delete_many({"crawl_job_id": job_id})
    await mongo_db["raw_comments"].delete_many({"crawl_job_id": job_id})

    await db.delete(job)
    await db.flush()
    return True


async def cancel_job(job_id: int, user_id: int, db: AsyncSession) -> bool:
    """取消正在排队或执行中的采集任务。"""
    result = await db.execute(
        select(CrawlJob).where(CrawlJob.id == job_id, CrawlJob.created_by == user_id)
    )
    job = result.scalar_one_or_none()
    if job is None or job.status not in ("pending", "running"):
        return False

    if job.celery_task_id:
        from app.celery_app import celery_app
        celery_app.control.revoke(job.celery_task_id, terminate=True)

    job.status = "cancelled"
    job.finished_at = datetime.now(timezone.utc)
    await db.flush()
    return True


async def query_posts(query: CrawlDataQuery) -> tuple[list[dict], int]:
    """从 MongoDB 分页查询标准化帖子数据，支持平台、关键词和时间范围筛选。"""
    mongo_db = get_mongo_db()
    collection = mongo_db["raw_posts"]

    mongo_filter: dict = {}
    if query.platform:
        mongo_filter["platform"] = query.platform
    if query.keyword:
        mongo_filter["content"] = {"$regex": query.keyword, "$options": "i"}
    if query.start_time:
        mongo_filter.setdefault("timestamp", {})["$gte"] = query.start_time
    if query.end_time:
        mongo_filter.setdefault("timestamp", {})["$lte"] = query.end_time

    total = await collection.count_documents(mongo_filter)
    skip = (query.page - 1) * query.page_size
    cursor = collection.find(mongo_filter, {"_id": 0}).sort("timestamp", -1).skip(skip).limit(query.page_size)
    items = await cursor.to_list(length=query.page_size)
    return items, total
