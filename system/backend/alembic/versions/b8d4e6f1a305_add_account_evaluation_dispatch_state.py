"""add account evaluation dispatch state

Revision ID: b8d4e6f1a305
Revises: a3f6c9e2b817
Create Date: 2026-08-07 12:45:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "b8d4e6f1a305"
down_revision: Union[str, Sequence[str], None] = "a3f6c9e2b817"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "account_model_evaluation_jobs",
        sa.Column("dispatch_status", sa.String(length=32), server_default="pending", nullable=False),
    )
    op.add_column(
        "account_model_evaluation_jobs",
        sa.Column("dispatch_claim_token", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "account_model_evaluation_jobs",
        sa.Column("dispatch_lease_expires_at", sa.DateTime(), nullable=True),
    )
    op.add_column(
        "account_model_evaluation_jobs",
        sa.Column("dispatch_publish_attempts", sa.Integer(), server_default="0", nullable=False),
    )
    op.add_column(
        "account_model_evaluation_jobs",
        sa.Column(
            "dispatch_available_at",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
    )
    op.add_column(
        "account_model_evaluation_jobs",
        sa.Column("dispatch_published_at", sa.DateTime(), nullable=True),
    )
    op.add_column(
        "account_model_evaluation_jobs",
        sa.Column("dispatch_last_error", sa.Text(), nullable=True),
    )
    op.create_check_constraint(
        "ck_account_model_evaluation_jobs_dispatch_status",
        "account_model_evaluation_jobs",
        "dispatch_status IN ('pending', 'publishing', 'published', 'superseded')",
    )
    op.create_index(
        "ix_account_model_evaluation_jobs_dispatch_status",
        "account_model_evaluation_jobs",
        ["dispatch_status"],
        unique=False,
    )
    op.create_index(
        "ix_account_model_evaluation_jobs_dispatch_lease_expires_at",
        "account_model_evaluation_jobs",
        ["dispatch_lease_expires_at"],
        unique=False,
    )
    op.create_index(
        "ix_account_model_evaluation_jobs_dispatch",
        "account_model_evaluation_jobs",
        ["dispatch_status", "dispatch_available_at", "dispatch_lease_expires_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_account_model_evaluation_jobs_dispatch", table_name="account_model_evaluation_jobs")
    op.drop_index(
        "ix_account_model_evaluation_jobs_dispatch_lease_expires_at",
        table_name="account_model_evaluation_jobs",
    )
    op.drop_index("ix_account_model_evaluation_jobs_dispatch_status", table_name="account_model_evaluation_jobs")
    op.drop_constraint(
        "ck_account_model_evaluation_jobs_dispatch_status",
        "account_model_evaluation_jobs",
        type_="check",
    )
    op.drop_column("account_model_evaluation_jobs", "dispatch_last_error")
    op.drop_column("account_model_evaluation_jobs", "dispatch_published_at")
    op.drop_column("account_model_evaluation_jobs", "dispatch_available_at")
    op.drop_column("account_model_evaluation_jobs", "dispatch_publish_attempts")
    op.drop_column("account_model_evaluation_jobs", "dispatch_lease_expires_at")
    op.drop_column("account_model_evaluation_jobs", "dispatch_claim_token")
    op.drop_column("account_model_evaluation_jobs", "dispatch_status")
