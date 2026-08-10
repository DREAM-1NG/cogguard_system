"""add account evaluation delivery acknowledgement

Revision ID: c4f7a9d2e618
Revises: b8d4e6f1a305
Create Date: 2026-08-07 14:20:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "c4f7a9d2e618"
down_revision: Union[str, Sequence[str], None] = "b8d4e6f1a305"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "account_model_evaluation_jobs",
        sa.Column("dispatch_acknowledged_at", sa.DateTime(), nullable=True),
    )
    op.create_index(
        "ix_account_model_evaluation_jobs_delivery_ack",
        "account_model_evaluation_jobs",
        ["dispatch_status", "status", "dispatch_published_at", "dispatch_acknowledged_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_account_model_evaluation_jobs_delivery_ack",
        table_name="account_model_evaluation_jobs",
    )
    op.drop_column("account_model_evaluation_jobs", "dispatch_acknowledged_at")
