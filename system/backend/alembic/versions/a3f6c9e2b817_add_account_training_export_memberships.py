"""add account training export memberships

Revision ID: a3f6c9e2b817
Revises: f7b1e4a8c329
Create Date: 2026-08-07 05:15:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "a3f6c9e2b817"
down_revision: Union[str, Sequence[str], None] = "f7b1e4a8c329"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "account_training_export_memberships",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("export_membership_id", sa.String(length=128), nullable=False),
        sa.Column("dataset_version_id", sa.String(length=128), nullable=False),
        sa.Column("case_id", sa.String(length=128), nullable=False),
        sa.Column("label_id", sa.String(length=128), nullable=False),
        sa.Column("case_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("export_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("exported_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("export_membership_id", name="uq_account_training_export_memberships_id"),
        sa.UniqueConstraint(
            "dataset_version_id",
            "case_id",
            "label_id",
            "case_fingerprint",
            name="uq_account_training_export_memberships_dataset_case_label",
        ),
    )
    for column in (
        "export_membership_id",
        "dataset_version_id",
        "case_id",
        "label_id",
        "case_fingerprint",
        "export_fingerprint",
    ):
        op.create_index(f"ix_account_training_export_memberships_{column}", "account_training_export_memberships", [column])
    op.create_index(
        "ix_account_training_export_memberships_lookup",
        "account_training_export_memberships",
        ["case_id", "label_id", "case_fingerprint"],
    )


def downgrade() -> None:
    op.drop_index("ix_account_training_export_memberships_lookup", table_name="account_training_export_memberships")
    for column in reversed(
        (
            "export_membership_id",
            "dataset_version_id",
            "case_id",
            "label_id",
            "case_fingerprint",
            "export_fingerprint",
        )
    ):
        op.drop_index(f"ix_account_training_export_memberships_{column}", table_name="account_training_export_memberships")
    op.drop_table("account_training_export_memberships")
