"""Celery 异步任务队列配置。

使用 Redis 作为 broker 和 result backend，自动发现 ``app.tasks``
包下的任务模块。爬虫等耗时操作通过 Celery worker 异步执行，
避免阻塞 FastAPI 主进程。
"""

from celery import Celery

from app.config import settings

celery_app = Celery(
    "cogguard",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["app.tasks.analysis_tasks", "app.tasks.crawl_tasks", "app.tasks.kt3_tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Shanghai",
    enable_utc=True,
    task_track_started=True,
    task_routes={
        "crawl.*": {"queue": "crawl"},
        "analysis.*": {"queue": "analysis"},
        "kt3.*": {"queue": "kt3"},
    },
)

# Import side-effect registers the task on the app instance for workers and tests.
from app.tasks import analysis_tasks  # noqa: E402,F401
