"""Celery tasks for crawl jobs.

根据 ``platform`` 路由到 MockCrawler、MediaCrawler 封装或 News 提取。
"""

from __future__ import annotations

import asyncio
import json
import traceback

from app.celery_app import celery_app
from app.core.crawler.factory import build_crawler
from app.core.crawler.news import NewsExtractCrawler
from app.core.crawler.social import MediaSocialCrawler
from app.db.mongodb import get_mongo_db


def _run_async(coro):
    """Run an async coroutine from synchronous Celery context."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@celery_app.task(name="crawl.execute", bind=True)
def execute_crawl_job(self, job_id: int, params_json: str):
    params = json.loads(params_json)
    platform = params.get("platform", "mock_weibo")
    keywords = params.get("keywords", [])
    post_ids = params.get("post_ids", []) or []
    max_posts = params.get("max_posts", 50)
    crawl_comments = params.get("crawl_comments", True)

    async def _do_crawl():
        crawler = build_crawler(platform)
        crawler.post_ids = post_ids
        mongo_db = get_mongo_db()

        posts = await crawler.search(keywords=keywords, max_posts=max_posts)

        post_dicts = []
        for p in posts:
            d = p.model_dump(mode="json")
            d["crawl_job_id"] = job_id
            post_dicts.append(d)

        if post_dicts:
            await mongo_db["raw_posts"].insert_many(post_dicts)

        all_comments: list = []
        if crawl_comments:
            if isinstance(crawler, MediaSocialCrawler):
                for c in crawler.last_comments:
                    d = c.model_dump(mode="json")
                    d["crawl_job_id"] = job_id
                    all_comments.append(d)
            elif isinstance(crawler, NewsExtractCrawler):
                pass
            else:
                for p in posts[:10]:
                    comments = await crawler.fetch_comments(p.post_id)
                    for c in comments:
                        d = c.model_dump(mode="json")
                        d["crawl_job_id"] = job_id
                        all_comments.append(d)
            if all_comments:
                await mongo_db["raw_comments"].insert_many(all_comments)

        return {
            "posts_count": len(post_dicts),
            "comments_count": len(all_comments) if crawl_comments else 0,
            "platform": platform,
        }

    try:
        result = _run_async(_do_crawl())
    except Exception:
        err = traceback.format_exc()
        _update_job_in_db(job_id, "failed", 0, json.dumps({"error": err[-8000:]}, ensure_ascii=False))
        raise

    _update_job_in_db(job_id, "completed", 100, json.dumps(result, ensure_ascii=False))
    return result


def _update_job_in_db(job_id: int, status: str, progress: int, result_summary: str | None = None):
    """Synchronously update job status in MySQL (from Celery worker context)."""
    from sqlalchemy import create_engine, text
    from app.config import settings

    sync_url = settings.mysql_url.replace("+aiomysql", "+pymysql")
    engine = create_engine(sync_url)
    with engine.connect() as conn:
        if result_summary:
            conn.execute(
                text("UPDATE crawl_jobs SET status=:s, progress=:p, result_summary=:r, finished_at=NOW() WHERE id=:id"),
                {"s": status, "p": progress, "r": result_summary, "id": job_id},
            )
        else:
            conn.execute(
                text("UPDATE crawl_jobs SET status=:s, progress=:p WHERE id=:id"),
                {"s": status, "p": progress, "id": job_id},
            )
        conn.commit()
    engine.dispose()
