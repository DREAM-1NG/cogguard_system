"""add_risk_assessments_table

Revision ID: a4d8c2b1f305
Revises: 7b4c2f9a0d31
Create Date: 2026-07-02 12:55:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision: str = "a4d8c2b1f305"
down_revision: Union[str, None] = "7b4c2f9a0d31"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_table(table_name: str) -> bool:
    return inspect(op.get_bind()).has_table(table_name)


def _has_index(table_name: str, index_name: str) -> bool:
    return any(index["name"] == index_name for index in inspect(op.get_bind()).get_indexes(table_name))


def _create_index_if_missing(index_name: str, table_name: str, columns: list[str], unique: bool = False) -> None:
    if not _has_index(table_name, index_name):
        op.create_index(index_name, table_name, columns, unique=unique)


def upgrade() -> None:
    if not _has_table("risk_assessments"):
        op.create_table(
            "risk_assessments",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("report_id", sa.String(length=36), nullable=False, comment="UUID"),
            sa.Column("event_id", sa.String(length=128), nullable=False),
            sa.Column("platform", sa.String(length=32), nullable=False),
            sa.Column(
                "current_phase",
                sa.String(length=20),
                nullable=False,
                comment="seed/synchronize/breakout/saturation/regeneration",
            ),
            sa.Column("phase_confidence", sa.Float(), nullable=False),
            sa.Column("hazard_breakout", sa.Float(), nullable=False),
            sa.Column("overall_risk_score", sa.Float(), nullable=False),
            sa.Column("risk_level", sa.String(length=16), nullable=False, comment="low/medium/high/critical"),
            sa.Column("manipulation_belief", sa.Float(), nullable=False),
            sa.Column("authenticity_belief", sa.Float(), nullable=False),
            sa.Column("impact_belief", sa.Float(), nullable=False),
            sa.Column("conflict_mass", sa.Float(), nullable=False),
            sa.Column("escalation_required", sa.Integer(), nullable=False, comment="0/1"),
            sa.Column("attack_path_score", sa.Float(), nullable=False),
            sa.Column("attack_path_depth", sa.Integer(), nullable=False),
            sa.Column("report_json", sa.Text(), nullable=False),
            sa.Column("assessed_by", sa.Integer(), nullable=False),
            sa.Column("assessed_at", sa.DateTime(), server_default=sa.text("now()"), nullable=True),
            sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=True),
            sa.PrimaryKeyConstraint("id"),
        )

    _create_index_if_missing("ix_risk_assessments_report_id", "risk_assessments", ["report_id"], unique=True)
    _create_index_if_missing("ix_risk_assessments_event_id", "risk_assessments", ["event_id"])
    _create_index_if_missing("ix_risk_assessments_platform", "risk_assessments", ["platform"])
    _create_index_if_missing("ix_risk_assessments_current_phase", "risk_assessments", ["current_phase"])
    _create_index_if_missing("ix_risk_assessments_risk_level", "risk_assessments", ["risk_level"])


def downgrade() -> None:
    if _has_table("risk_assessments"):
        op.drop_table("risk_assessments")
