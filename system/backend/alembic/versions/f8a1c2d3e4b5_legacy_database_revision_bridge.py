"""Bridge a locally deployed legacy Alembic revision into the active chain.

Revision ID: f8a1c2d3e4b5
Revises: d2f7a8b9c0e1

The local MySQL instance was stamped by the retired refactor runtime at this
revision. Its review-table repair is already reflected in that database. The
active system does not own the retired migration chain, so this bridge is a
deliberate no-op that lets future product migrations advance safely.
"""

from typing import Sequence, Union


revision: str = "f8a1c2d3e4b5"
down_revision: Union[str, None] = "d2f7a8b9c0e1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """No-op bridge for databases already stamped at this historical revision."""


def downgrade() -> None:
    """No schema changes were introduced by the compatibility bridge."""
