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
    include=[
        "app.tasks.analysis_tasks",
        "app.tasks.crawl_tasks",
        "app.tasks.review_tasks",
        "app.tasks.account_training_tasks",
        "app.tasks.account_evaluation_tasks",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Shanghai",
    enable_utc=True,
    task_track_started=True,
    task_publish_retry=False,
    broker_connection_timeout=float(settings.ACCOUNT_TRAINING_OUTBOX_PUBLISH_TIMEOUT_SECONDS),
    broker_transport_options={
        "socket_connect_timeout": float(settings.ACCOUNT_TRAINING_OUTBOX_PUBLISH_TIMEOUT_SECONDS),
        "socket_timeout": float(settings.ACCOUNT_TRAINING_OUTBOX_PUBLISH_TIMEOUT_SECONDS),
        "retry_on_timeout": False,
    },
    task_routes={
        "crawl.*": {"queue": "crawl"},
        "analysis.*": {"queue": "analysis"},
        "review.*": {"queue": "review"},
        "account_training.*": {"queue": "account_training"},
        "account_evaluation.*": {"queue": "account_evaluation"},
    },
    beat_schedule={
        "account-training-heartbeat-reconciliation": {
            "task": "account_training.reconcile_heartbeats",
            "schedule": max(30.0, float(settings.ACCOUNT_TRAINING_HEARTBEAT_TIMEOUT_SECONDS) / 2.0),
            "options": {"queue": "account_training"},
        },
        "account-model-monitoring-snapshot": {
            "task": "account_training.monitor_active_model",
            "schedule": 300.0,
            "kwargs": {"window_seconds": 300},
            "options": {"queue": "account_training"},
        },
        "account-evaluation-dispatch-reconciliation": {
            "task": "account_evaluation.reconcile_dispatches",
            "schedule": 60.0,
            "kwargs": {"limit": 100},
            "options": {"queue": "account_evaluation"},
        },
    },
)


@worker_process_shutdown.connect
@worker_shutdown.connect
def _close_worker_async_runtime(**_kwargs):
    close_async_runtime()

# Import side-effect registers the task on the app instance for workers and tests.
from app.tasks import analysis_tasks  # noqa: E402,F401
