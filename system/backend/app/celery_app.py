"""Celery 异步任务队列配置。

使用 Redis 作为 broker 和 result backend，自动发现 ``app.tasks``
包下的任务模块。爬虫等耗时操作通过 Celery worker 异步执行，
避免阻塞 FastAPI 主进程。
"""

from celery import Celery
from celery.signals import worker_process_shutdown, worker_shutdown

from app.config import settings
from app.tasks.async_runtime import close_async_runtime

celery_app = Celery(
    "cogguard",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["app.tasks.analysis_tasks", "app.tasks.crawl_tasks", "app.tasks.review_tasks"],
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
        "review.*": {"queue": "review"},
    },
)


@worker_process_shutdown.connect
@worker_shutdown.connect
def _close_worker_async_runtime(**_kwargs):
    close_async_runtime()

# Import side-effect registers the task on the app instance for workers and tests.
from app.tasks import analysis_tasks  # noqa: E402,F401
