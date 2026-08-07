"""add durable system-owned account model evaluation jobs

Revision ID: f7b1e4a8c329
Revises: d9e2f4a6b817
Create Date: 2026-08-07 04:45:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "f7b1e4a8c329"
down_revision: Union[str, Sequence[str], None] = "d9e2f4a6b817"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "account_model_evaluation_jobs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("job_id", sa.String(length=128), nullable=False),
        sa.Column("model_version", sa.String(length=128), nullable=False),
        sa.Column("artifact_hash", sa.String(length=64), nullable=False),
        sa.Column("corpus_version_id", sa.String(length=128), nullable=False),
        sa.Column("holdout_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("config_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("evaluator_config_json", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("task_id", sa.String(length=192), nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("operator_id", sa.Integer(), nullable=False),
        sa.Column("completed_evaluation_run_id", sa.String(length=128), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.CheckConstraint(
            "status IN ('queued', 'running', 'completed', 'failed', 'cancelled')",
            name="ck_account_model_evaluation_jobs_status",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("job_id", name="uq_account_model_evaluation_jobs_id"),
        sa.UniqueConstraint("task_id", name="uq_account_model_evaluation_jobs_task_id"),
        sa.UniqueConstraint(
            "model_version",
            "artifact_hash",
            "corpus_version_id",
            "holdout_fingerprint",
            "config_fingerprint",
            name="uq_account_model_evaluation_jobs_identity",
        ),
    )
    op.create_index("ix_account_model_evaluation_jobs_status_created", "account_model_evaluation_jobs", ["status", "created_at"])
    op.create_index("ix_account_model_evaluation_jobs_candidate", "account_model_evaluation_jobs", ["model_version", "artifact_hash"])
    for column in (
        "job_id",
        "model_version",
        "artifact_hash",
        "corpus_version_id",
        "holdout_fingerprint",
        "config_fingerprint",
        "status",
        "task_id",
        "operator_id",
        "completed_evaluation_run_id",
    ):
        op.create_index(f"ix_account_model_evaluation_jobs_{column}", "account_model_evaluation_jobs", [column])


def downgrade() -> None:
    for column in reversed(
        (
            "job_id",
            "model_version",
            "artifact_hash",
            "corpus_version_id",
            "holdout_fingerprint",
            "config_fingerprint",
            "status",
            "task_id",
            "operator_id",
            "completed_evaluation_run_id",
        )
    ):
        op.drop_index(f"ix_account_model_evaluation_jobs_{column}", table_name="account_model_evaluation_jobs")
    op.drop_index("ix_account_model_evaluation_jobs_candidate", table_name="account_model_evaluation_jobs")
    op.drop_index("ix_account_model_evaluation_jobs_status_created", table_name="account_model_evaluation_jobs")
    op.drop_table("account_model_evaluation_jobs")
