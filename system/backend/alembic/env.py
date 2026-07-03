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
from app.models.kt3_system import KT3AgentDebateTrace  # noqa: F401
from app.models.kt3_system import KT3AgentFeedback  # noqa: F401
from app.models.kt3_system import KT3AgentReport  # noqa: F401
from app.models.kt3_system import KT3AgentReportAction  # noqa: F401
from app.models.kt3_system import KT3AgentReportEvidenceRef  # noqa: F401
from app.models.kt3_system import KT3AgentReportQuery  # noqa: F401
from app.models.kt3_system import KT3AgentReportUncertainty  # noqa: F401
from app.models.kt3_system import KT3AgentRun  # noqa: F401
from app.models.kt3_system import KT3GateCase  # noqa: F401
from app.models.kt3_system import KT3GateDataset  # noqa: F401
from app.models.kt3_system import KT3GateLabel  # noqa: F401
from app.models.kt3_system import KT3Job  # noqa: F401
from app.models.kt3_system import KT3Policy  # noqa: F401
from app.models.kt3_system import KT3PolicyAgentWeight  # noqa: F401
from app.models.kt3_system import KT3PolicyMetric  # noqa: F401
from app.models.kt3_system import KT3PolicyRefinementRound  # noqa: F401
from app.models.kt3_system import KT3PolicyRule  # noqa: F401
from app.models.kt3_system import KT3PolicyThreshold  # noqa: F401
from app.models.kt3_system import KT3ProviderConfig  # noqa: F401
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
