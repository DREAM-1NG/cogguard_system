"""Celery tasks for crawl jobs.

In Phase 1, uses MockCrawler.  When real crawlers are integrated, the
crawler selection logic in ``_get_crawler`` will be extended.
"""

import asyncio
import json

from app.celery_app import celery_app
from app.core.crawler.mock import MockCrawler
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
    max_posts = params.get("max_posts", 50)
    crawl_comments = params.get("crawl_comments", True)

    async def _do_crawl():
        crawler = MockCrawler()
        mongo_db = get_mongo_db()

        posts = await crawler.search(keywords=keywords, max_posts=max_posts)

        post_dicts = []
        for p in posts:
            d = p.model_dump(mode="json")
            d["crawl_job_id"] = job_id
            post_dicts.append(d)

        if post_dicts:
            await mongo_db["raw_posts"].insert_many(post_dicts)

        if crawl_comments:
            all_comments = []
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
        }

    result = _run_async(_do_crawl())

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
