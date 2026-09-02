"""Celery tasks for crawl jobs."""

import json
import traceback

from pymongo import UpdateOne

from app.celery_app import celery_app
from app.config import settings
from app.core.crawler.factory import build_crawler
from app.core.crawler.types import CrawlRequestOptions
from app.services.review_case_orchestrator import process_successful_crawl
from app.tasks.async_runtime import run_async
from app.utils.logger import logger


def _create_task_mongo_client():
    """Create a Mongo client owned by the crawl task's event loop."""
    from motor.motor_asyncio import AsyncIOMotorClient

    return AsyncIOMotorClient(settings.mongo_url)


def _first_keyword(params: dict) -> str | None:
    keywords = params.get("keywords") or []
    for keyword in keywords:
        text = str(keyword).strip()
        if text:
            return text
    return None


def _resolve_event_id(params: dict, job_id: int) -> str:
    event_id = str(params.get("event_id") or "").strip()
    return event_id or f"crawl_job_{job_id}"


def _resolve_source_keyword(params: dict) -> str:
    return str(params.get("source_keyword") or _first_keyword(params) or "").strip()


def prepare_crawl_document(
    data: dict,
    *,
    params: dict,
    job_id: int,
    item_type: str,
    crawl_metadata: dict,
) -> dict:
    """Attach event metadata and deterministic dedupe keys before MongoDB writes."""
    document = dict(data)
    platform = str(document.get("platform") or params.get("platform") or "")
    item_id = str(document.get("post_id") if item_type == "post" else document.get("comment_id") or "")
    event_id = _resolve_event_id(params, job_id)

    document["crawl_job_id"] = job_id
    document["event_id"] = event_id
    document["source_keyword"] = _resolve_source_keyword(params)
    document["crawl_metadata"] = crawl_metadata
    if platform and item_id:
        document["dedupe_key"] = f"{event_id}:{platform}:{item_type}:{item_id}"
    return document


async def _write_documents(collection, documents: list[dict]) -> None:
    if not documents:
        return
    if all(document.get("dedupe_key") for document in documents):
        await collection.bulk_write(
            [
                UpdateOne({"dedupe_key": document["dedupe_key"]}, {"$set": document}, upsert=True)
                for document in documents
            ],
            ordered=False,
        )
        return
    await collection.insert_many(documents)


def _build_request_options(params: dict) -> CrawlRequestOptions:
    return CrawlRequestOptions(
        keywords=list(params.get("keywords") or []),
        post_ids=list(params.get("post_ids") or []),
        max_posts=int(params.get("max_posts", 50) or 50),
        crawl_comments=bool(params.get("crawl_comments", True)),
        recursive_comments=bool(
            params.get("recursive_comments", settings.MEDIACRAWLER_GET_SUB_COMMENTS)
        ),
        enrich_author_profiles=bool(params.get("enrich_author_profiles", False)),
        comment_sort=str(params.get("comment_sort", "none") or "none"),
        max_comments_per_post=int(
            params.get(
                "max_comments_per_post",
                settings.MEDIACRAWLER_MAX_COMMENTS_PER_POST,
            )
            or 0
        )
        or None,
    )


def run_crawl_job(job_id: int, params_json: str):
    params = json.loads(params_json)
    platform = params.get("platform", "mock_weibo")
    request = _build_request_options(params)

    async def _do_crawl():
        mongo_client = _create_task_mongo_client()
        try:
            mongo_db = mongo_client[settings.MONGO_DATABASE]
            crawler = build_crawler(platform)
            batch = await crawler.collect(request)

            post_dicts = []
            for post in batch.posts:
                post_dicts.append(
                    prepare_crawl_document(
                        post.model_dump(mode="json"),
                        params=params,
                        job_id=job_id,
                        item_type="post",
                        crawl_metadata=batch.crawl_metadata,
                    )
                )
            await _write_documents(mongo_db["raw_posts"], post_dicts)

            all_comments: list = []
            if request.crawl_comments:
                for comment in batch.comments:
                    all_comments.append(
                        prepare_crawl_document(
                            comment.model_dump(mode="json"),
                            params=params,
                            job_id=job_id,
                            item_type="comment",
                            crawl_metadata=batch.crawl_metadata,
                        )
                    )
                await _write_documents(mongo_db["raw_comments"], all_comments)

            result = {
                "posts_count": len(post_dicts),
                "comments_count": len(all_comments) if request.crawl_comments else 0,
                "platform": platform,
                "crawl_metadata": batch.crawl_metadata,
            }
            try:
                result["review_case"] = await _orchestrate_successful_crawl(
                    job_id=job_id,
                    params=params,
                    result=result,
                    mongo_db=mongo_db,
                )
            except Exception as exc:
                logger.exception("Review case orchestration failed after crawl job {}", job_id)
                result["review_case"] = {
                    "failed": True,
                    "reason": f"{type(exc).__name__}: {exc}",
                }
            return result
        finally:
            mongo_client.close()

    try:
        result = run_async(_do_crawl())
    except Exception:
        err = traceback.format_exc()
        _update_job_in_db(job_id, "failed", 0, json.dumps({"error": err[-8000:]}, ensure_ascii=False))
        raise

    _update_job_in_db(job_id, "completed", 100, json.dumps(result, ensure_ascii=False))
    return result


async def _orchestrate_successful_crawl(
    *,
    job_id: int,
    params: dict,
    result: dict,
    mongo_db,
    session_factory=None,
) -> dict:
    event_id = str(params.get("event_id") or "").strip()
    if not event_id:
        return {"skipped": True, "reason": "event_id_not_provided"}

    if session_factory is None:
        from app.db.mysql import async_session_factory

        session_factory = async_session_factory

    title = str(
        params.get("event_title")
        or params.get("source_keyword")
        or _first_keyword(params)
        or event_id
    ).strip()
    async with session_factory() as db:
        outcome = await process_successful_crawl(
            job_id=job_id,
            event_id=event_id,
            title=title,
            created_by=int(params.get("_created_by") or 0),
            db=db,
            mongo_db=mongo_db,
        )
        await db.commit()
        return outcome


@celery_app.task(name="crawl.execute", bind=True)
def execute_crawl_job(self, job_id: int, params_json: str):
    return run_crawl_job(job_id, params_json)


#: Statuses a job may still be moved out of. A job the user already cancelled
#: must not be flipped to completed/failed by a runner that could not be stopped
#: (local-mode "tasks" have no revocable Celery id).
_UPDATABLE_JOB_STATUSES = ("pending", "running")


def _update_job_in_db(
    job_id: int,
    status: str,
    progress: int,
    result_summary: str | None = None,
    *,
    only_if_active: bool = True,
):
    """Synchronously update job status in MySQL (from Celery worker context).

    ``only_if_active`` guards the terminal transition so a cancelled job stays
    cancelled instead of being reported as completed after the fact.
    """
    from sqlalchemy import create_engine, text
    from app.config import settings

    assignments = ["status=:s", "progress=:p"]
    payload: dict[str, object] = {"s": status, "p": progress, "id": job_id}
    if result_summary:
        assignments.append("result_summary=:r")
        payload["r"] = result_summary
        assignments.append("finished_at=NOW()")

    where = "id=:id"
    if only_if_active:
        placeholders = []
        for index, allowed in enumerate(_UPDATABLE_JOB_STATUSES):
            key = f"st{index}"
            payload[key] = allowed
            placeholders.append(f":{key}")
        where += f" AND status IN ({', '.join(placeholders)})"

    sync_url = settings.mysql_url.replace("+aiomysql", "+pymysql")
    engine = create_engine(sync_url)
    try:
        with engine.connect() as conn:
            conn.execute(
                text(f"UPDATE crawl_jobs SET {', '.join(assignments)} WHERE {where}"),
                payload,
            )
            conn.commit()
    finally:
        engine.dispose()
