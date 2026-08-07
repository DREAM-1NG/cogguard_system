"""add immutable signed account model evaluation runs

Revision ID: e7a3c9d5f102
Revises: d6e1f7a9b3c2
Create Date: 2026-08-06 18:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "e7a3c9d5f102"
down_revision: Union[str, Sequence[str], None] = "d6e1f7a9b3c2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "account_model_evaluation_runs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("evaluation_run_id", sa.String(length=128), nullable=False),
        sa.Column("family", sa.String(length=64), nullable=False),
        sa.Column("model_version", sa.String(length=128), nullable=False),
        sa.Column("artifact_hash", sa.String(length=128), nullable=False),
        sa.Column("evaluation_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("audit_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("manifest_json", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "evaluation_run_id",
            "model_version",
            "artifact_hash",
            name="uq_account_model_evaluation_runs_identity",
        ),
    )
    for column in (
        "evaluation_run_id",
        "family",
        "model_version",
        "artifact_hash",
        "evaluation_fingerprint",
        "audit_fingerprint",
    ):
        op.create_index(
            f"ix_account_model_evaluation_runs_{column}",
            "account_model_evaluation_runs",
            [column],
            unique=False,
        )


def downgrade() -> None:
    for column in reversed(
        (
            "evaluation_run_id",
            "family",
            "model_version",
            "artifact_hash",
            "evaluation_fingerprint",
            "audit_fingerprint",
        )
    ):
        op.drop_index(
            f"ix_account_model_evaluation_runs_{column}",
            table_name="account_model_evaluation_runs",
        )
    op.drop_table("account_model_evaluation_runs")
