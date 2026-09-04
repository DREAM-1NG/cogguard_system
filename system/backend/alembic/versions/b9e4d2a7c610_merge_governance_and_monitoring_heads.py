"""merge governance and propagation monitoring heads

Revision ID: b9e4d2a7c610
Revises: a2d8e5c1b904, f4c7b9e1a602
Create Date: 2026-09-02 22:10:00.000000
"""

from typing import Sequence, Union


revision: str = "b9e4d2a7c610"
down_revision: Union[str, tuple[str, str], None] = (
    "a2d8e5c1b904",
    "f4c7b9e1a602",
)
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Join the two schema lineages without changing tables."""


def downgrade() -> None:
    """Separate the lineages without changing tables."""
