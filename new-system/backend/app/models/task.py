"""采集任务 ORM 模型（MySQL）。

记录每次数据采集任务的配置参数、执行状态、进度和结果摘要，
通过 ``celery_task_id`` 与 Celery 异步任务关联。
"""

from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.mysql import Base


class CrawlJob(Base):
    """采集任务表，跟踪社交媒体 / 新闻数据的采集生命周期。"""
    __tablename__ = "crawl_jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    job_type: Mapped[str] = mapped_column(String(32), nullable=False, comment="social / news")
    platform: Mapped[str] = mapped_column(String(32), nullable=False)
    params_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending", index=True, comment="pending/running/completed/failed")
    progress: Mapped[int] = mapped_column(Integer, default=0, comment="0-100")
    result_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    celery_task_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_by: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
