"""merge_analysis_and_review_heads

Revision ID: d2f7a8b9c0e1
Revises: 9a2e4b7c1d55, c6e8a5d4b2f1
Create Date: 2026-08-01 12:00:00.000000
"""

from typing import Sequence, Union


revision: str = "d2f7a8b9c0e1"
down_revision: Union[str, Sequence[str], None] = ("9a2e4b7c1d55", "c6e8a5d4b2f1")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Join the analysis persistence and review-report migration branches."""


def downgrade() -> None:
    """Keep both historical branches reversible independently."""
