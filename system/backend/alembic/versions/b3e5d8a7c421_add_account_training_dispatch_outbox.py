"""add account training dispatch outbox

Revision ID: b3e5d8a7c421
Revises: a1e9c7d4b605
Create Date: 2026-08-06 21:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "b3e5d8a7c421"
down_revision: Union[str, Sequence[str], None] = "a1e9c7d4b605"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "account_model_training_dispatch_outbox",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("dispatch_id", sa.String(length=192), nullable=False),
        sa.Column("run_id", sa.String(length=128), nullable=False),
        sa.Column("attempt", sa.Integer(), nullable=False),
        sa.Column("task_id", sa.String(length=192), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="pending"),
        sa.Column("claim_token", sa.String(length=64), nullable=True),
        sa.Column("lease_expires_at", sa.DateTime(), nullable=True),
        sa.Column("publish_attempts", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("available_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("published_at", sa.DateTime(), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=True),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=True),
        sa.CheckConstraint(
            "status IN ('pending', 'publishing', 'published', 'superseded')",
            name="ck_account_training_dispatch_outbox_status",
        ),
        sa.CheckConstraint("attempt >= 1", name="ck_account_training_dispatch_outbox_attempt_positive"),
        sa.CheckConstraint(
            "publish_attempts >= 0",
            name="ck_account_training_dispatch_outbox_publish_attempts_nonnegative",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("dispatch_id", name="uq_account_training_dispatch_outbox_id"),
        sa.UniqueConstraint("run_id", "attempt", name="uq_account_training_dispatch_outbox_run_attempt"),
        sa.UniqueConstraint("task_id", name="uq_account_training_dispatch_outbox_task_id"),
    )
    for column in ("dispatch_id", "run_id", "task_id", "status", "available_at", "lease_expires_at"):
        op.create_index(
            f"ix_account_model_training_dispatch_outbox_{column}",
            "account_model_training_dispatch_outbox",
            [column],
            unique=False,
        )
    op.create_index(
        "ix_account_training_dispatch_outbox_pending",
        "account_model_training_dispatch_outbox",
        ["status", "available_at"],
        unique=False,
    )
    op.create_index(
        "ix_account_training_dispatch_outbox_claim_lease",
        "account_model_training_dispatch_outbox",
        ["status", "available_at", "lease_expires_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_account_training_dispatch_outbox_claim_lease",
        table_name="account_model_training_dispatch_outbox",
    )
    op.drop_index(
        "ix_account_training_dispatch_outbox_pending",
        table_name="account_model_training_dispatch_outbox",
    )
    for column in reversed(("dispatch_id", "run_id", "task_id", "status", "available_at", "lease_expires_at")):
        op.drop_index(
            f"ix_account_model_training_dispatch_outbox_{column}",
            table_name="account_model_training_dispatch_outbox",
        )
    op.drop_table("account_model_training_dispatch_outbox")
