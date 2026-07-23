"""Alembic 迁移环境配置。

使用异步引擎执行数据库迁移，自动导入所有 ORM 模型以支持 autogenerate。
数据库连接信息从 app.config.settings 读取（与后端应用共享配置）。
"""

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import create_async_engine

from app.config import settings
from app.db.mysql import Base
from app.models.coordination_registry import CoordinationDataset, CoordinationRun  # noqa: F401
from app.models.review_system import ReviewAgentDebateTrace  # noqa: F401
from app.models.review_system import ReviewAgentFeedback  # noqa: F401
from app.models.review_system import ReviewAgentReport  # noqa: F401
from app.models.review_system import ReviewAgentReportAction  # noqa: F401
from app.models.review_system import ReviewAgentReportEvidenceRef  # noqa: F401
from app.models.review_system import ReviewAgentReportQuery  # noqa: F401
from app.models.review_system import ReviewAgentReportUncertainty  # noqa: F401
from app.models.review_system import ReviewAgentRun  # noqa: F401
from app.models.review_system import ReviewGateCase  # noqa: F401
from app.models.review_system import ReviewGateDataset  # noqa: F401
from app.models.review_system import ReviewGateLabel  # noqa: F401
from app.models.review_system import ReviewJob  # noqa: F401
from app.models.review_system import ReviewPolicy  # noqa: F401
from app.models.review_system import ReviewPolicyAgentWeight  # noqa: F401
from app.models.review_system import ReviewPolicyMetric  # noqa: F401
from app.models.review_system import ReviewPolicyRefinementRound  # noqa: F401
from app.models.review_system import ReviewPolicyRule  # noqa: F401
from app.models.review_system import ReviewPolicyThreshold  # noqa: F401
from app.models.review_system import ReviewProviderConfig  # noqa: F401
from app.models.risk_assessment import RiskAssessment  # noqa: F401
from app.models.user import User  # noqa: F401
from app.models.task import CrawlJob  # noqa: F401

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=settings.mysql_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "format"},
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection):
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    connectable = create_async_engine(settings.mysql_url, poolclass=pool.NullPool)
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
