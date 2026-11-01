"""add immutable model governance decisions

Revision ID: f1c9d6a4b730
Revises: e8b4c1d7a620
Create Date: 2026-08-03 16:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "f1c9d6a4b730"
down_revision: Union[str, Sequence[str], None] = "e8b4c1d7a620"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_unique_constraint(
        "uq_analysis_review_verdict_versions_canonical_source",
        "analysis_review_verdict_versions",
        ["canonical_source_id"],
    )
    op.create_table(
        "analysis_model_governance_decisions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("decision_id", sa.String(length=128), nullable=False),
        sa.Column("technology", sa.String(length=64), nullable=False),
        sa.Column("model_version_id", sa.Integer(), nullable=False),
        sa.Column("previous_model_version_id", sa.Integer(), nullable=True),
        sa.Column("decision_type", sa.String(length=32), nullable=False),
        sa.Column("decision_json", sa.Text(), nullable=False),
        sa.Column("decided_by", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "decision_id",
            name="uq_analysis_model_governance_decisions_decision_id",
        ),
    )
    for column_name in (
        "technology",
        "model_version_id",
        "previous_model_version_id",
        "decision_type",
        "decided_by",
    ):
        op.create_index(
            f"ix_analysis_model_governance_decisions_{column_name}",
            "analysis_model_governance_decisions",
            [column_name],
            unique=False,
        )


def downgrade() -> None:
    for column_name in reversed(
        (
            "technology",
            "model_version_id",
            "previous_model_version_id",
            "decision_type",
            "decided_by",
        )
    ):
        op.drop_index(
            f"ix_analysis_model_governance_decisions_{column_name}",
            table_name="analysis_model_governance_decisions",
        )
    op.drop_table("analysis_model_governance_decisions")
    op.drop_constraint(
        "uq_analysis_review_verdict_versions_canonical_source",
        "analysis_review_verdict_versions",
        type_="unique",
    )
