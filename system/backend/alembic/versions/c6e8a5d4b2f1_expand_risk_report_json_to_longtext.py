"""expand_risk_report_json_to_longtext

Revision ID: c6e8a5d4b2f1
Revises: a4d8c2b1f305
Create Date: 2026-07-02 23:30:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql


revision: str = "c6e8a5d4b2f1"
down_revision: Union[str, None] = "a4d8c2b1f305"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        "risk_assessments",
        "report_json",
        existing_type=sa.Text(),
        type_=mysql.LONGTEXT(),
        existing_nullable=False,
    )


def downgrade() -> None:
    op.alter_column(
        "risk_assessments",
        "report_json",
        existing_type=mysql.LONGTEXT(),
        type_=sa.Text(),
        existing_nullable=False,
    )
