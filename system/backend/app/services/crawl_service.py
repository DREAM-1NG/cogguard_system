"""Data collection service layer."""

import json
import re
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.mongodb import get_mongo_db
from app.models.task import CrawlJob
from app.schemas.crawl import CrawlDataQuery, CrawlRequest


async def create_crawl_job(req: CrawlRequest, user_id: int, db: AsyncSession) -> CrawlJob:
    job_type = "news" if req.platform == "news" else "social"
    job = CrawlJob(
        job_type=job_type,
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
    db: AsyncSession,
    user_id: int,
    page: int = 1,
    page_size: int = 20,
    include_system_owned: bool = False,
) -> tuple[list[CrawlJob], int]:
    owner_ids = [user_id]
    if include_system_owned and 0 not in owner_ids:
        owner_ids.append(0)

    count_q = (
        select(func.count())
        .select_from(CrawlJob)
        .where(CrawlJob.created_by.in_(owner_ids))
    )
    total = (await db.execute(count_q)).scalar() or 0

    query = (
        select(CrawlJob)
        .where(CrawlJob.created_by.in_(owner_ids))
        .order_by(CrawlJob.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    result = await db.execute(query)
    return list(result.scalars().all()), total


async def delete_job(job_id: int, user_id: int, db: AsyncSession) -> bool:
    result = await db.execute(
        select(CrawlJob).where(CrawlJob.id == job_id, CrawlJob.created_by == user_id)
    )
    job = result.scalar_one_or_none()
    if job is None:
        return False

    if job.job_type != "media_download":
        mongo_db = get_mongo_db()
        await mongo_db["raw_posts"].delete_many({"crawl_job_id": job_id})
        await mongo_db["raw_comments"].delete_many({"crawl_job_id": job_id})

    await db.delete(job)
    await db.flush()
    return True


async def cancel_job(job_id: int, user_id: int, db: AsyncSession) -> bool:
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
    mongo_db = get_mongo_db()
    collection = mongo_db["raw_posts"]

    mongo_filter: dict = {}
    if query.platform:
        mongo_filter["platform"] = query.platform
    if query.keyword:
        # Escape the user-supplied keyword: an unescaped $regex lets callers
        # inject regex syntax (invalid patterns 500 the endpoint, and
        # catastrophic-backtracking patterns pin mongod).
        mongo_filter["content"] = {"$regex": re.escape(query.keyword), "$options": "i"}
    if query.event_id:
        mongo_filter["event_id"] = query.event_id
    if query.has_media is True:
        mongo_filter["media_urls.0"] = {"$exists": True}
    elif query.has_media is False:
        mongo_filter["media_urls.0"] = {"$exists": False}
    if query.start_time:
        mongo_filter.setdefault("timestamp", {})["$gte"] = query.start_time
    if query.end_time:
        mongo_filter.setdefault("timestamp", {})["$lte"] = query.end_time

    total = await collection.count_documents(mongo_filter)
    skip = (query.page - 1) * query.page_size
    cursor = (
        collection.find(mongo_filter, {"_id": 0})
        .sort("timestamp", -1)
        .skip(skip)
        .limit(query.page_size)
    )
    items = await cursor.to_list(length=query.page_size)
    return items, total
