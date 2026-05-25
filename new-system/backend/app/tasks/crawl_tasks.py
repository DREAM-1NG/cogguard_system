"""Celery tasks for crawl jobs.

根据 ``platform`` 路由到 MockCrawler、MediaCrawler 封装或 News 提取。
"""

import asyncio
import json
import traceback

from app.celery_app import celery_app
from app.core.crawler.factory import build_crawler
from app.core.crawler.news import NewsExtractCrawler
from app.core.crawler.social import COGGUARD_TO_MEDIA, MediaSocialCrawler
from app.db.mongodb import get_mongo_db


def apply_crawl_options(crawler, params: dict) -> None:
    """Apply optional crawl-time controls supported by concrete crawlers."""
    if isinstance(crawler, MediaSocialCrawler):
        crawler.configure_runtime_options(
            recursive_comments=bool(params.get("recursive_comments", False)),
            enrich_author_profiles=bool(params.get("enrich_author_profiles", False)),
            comment_sort=str(params.get("comment_sort", "none") or "none"),
        )


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
        mongo_db = get_mongo_db()
        if platform in COGGUARD_TO_MEDIA:
            crawler = MediaSocialCrawler(platform)
            crawler.post_ids = post_ids
            apply_crawl_options(crawler, params)
            batch = await crawler.execute_search_batch(keywords=keywords, max_posts=max_posts)

            post_dicts = []
            for post in batch.posts:
                data = post.model_dump(mode="json")
                data["crawl_job_id"] = job_id
                data["crawl_metadata"] = crawler.crawl_metadata
                post_dicts.append(data)
            if post_dicts:
                await mongo_db["raw_posts"].insert_many(post_dicts)

            all_comments: list = []
            if crawl_comments:
                for comment in batch.comments:
                    data = comment.model_dump(mode="json")
                    data["crawl_job_id"] = job_id
                    data["crawl_metadata"] = crawler.crawl_metadata
                    all_comments.append(data)
                if all_comments:
                    await mongo_db["raw_comments"].insert_many(all_comments)

            return {
                "posts_count": len(post_dicts),
                "comments_count": len(all_comments) if crawl_comments else 0,
                "platform": platform,
                "crawl_metadata": crawler.crawl_metadata,
            }

        crawler = build_crawler(platform)
        crawler.post_ids = post_ids
        apply_crawl_options(crawler, params)
        posts = await crawler.search(keywords=keywords, max_posts=max_posts)

        post_dicts = []
        for post in posts:
            data = post.model_dump(mode="json")
            data["crawl_job_id"] = job_id
            post_dicts.append(data)

        if post_dicts:
            await mongo_db["raw_posts"].insert_many(post_dicts)

        all_comments: list = []
        if crawl_comments:
            if isinstance(crawler, NewsExtractCrawler):
                pass
            else:
                for post in posts[:10]:
                    comments = await crawler.fetch_comments(post.post_id)
                    for comment in comments:
                        data = comment.model_dump(mode="json")
                        data["crawl_job_id"] = job_id
                        all_comments.append(data)
            if all_comments:
                await mongo_db["raw_comments"].insert_many(all_comments)

        return {
            "posts_count": len(post_dicts),
            "comments_count": len(all_comments) if crawl_comments else 0,
            "platform": platform,
            "crawl_metadata": {},
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
