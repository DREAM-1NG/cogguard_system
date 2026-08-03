"""add immutable per-administrator model activation approvals

Revision ID: a2d8e5c1b904
Revises: f1c9d6a4b730
Create Date: 2026-08-03 19:30:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "a2d8e5c1b904"
down_revision: Union[str, Sequence[str], None] = "f1c9d6a4b730"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "analysis_model_activation_approvals",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("approval_id", sa.String(length=128), nullable=False),
        sa.Column("model_version_id", sa.Integer(), nullable=False),
        sa.Column("approver_id", sa.Integer(), nullable=False),
        sa.Column("approval_notes", sa.Text(), nullable=False),
        sa.Column(
            "immutable_source",
            sa.String(length=128),
            nullable=False,
            server_default="analysis.governance.model_approval.v1",
        ),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "approval_id",
            name="uq_analysis_model_activation_approvals_approval_id",
        ),
        sa.UniqueConstraint(
            "model_version_id",
            "approver_id",
            name="uq_analysis_model_activation_approvals_model_approver",
        ),
    )
    op.create_index(
        "ix_analysis_model_activation_approvals_model_version_id",
        "analysis_model_activation_approvals",
        ["model_version_id"],
        unique=False,
    )
    op.create_index(
        "ix_analysis_model_activation_approvals_approver_id",
        "analysis_model_activation_approvals",
        ["approver_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_analysis_model_activation_approvals_approver_id",
        table_name="analysis_model_activation_approvals",
    )
    op.drop_index(
        "ix_analysis_model_activation_approvals_model_version_id",
        table_name="analysis_model_activation_approvals",
    )
    op.drop_table("analysis_model_activation_approvals")
