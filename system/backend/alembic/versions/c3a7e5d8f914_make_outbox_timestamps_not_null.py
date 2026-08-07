"""make account training dispatch outbox timestamps not null

Revision ID: c3a7e5d8f914
Revises: b3e5d8a7c421
Create Date: 2026-08-06 22:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "c3a7e5d8f914"
down_revision: Union[str, Sequence[str], None] = "b3e5d8a7c421"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # b3 permitted NULL despite ORM defaults. Backfill first so ALTER is safe
    # on deployed rows created by that revision.
    op.execute(
        "UPDATE account_model_training_dispatch_outbox "
        "SET created_at = COALESCE(created_at, CURRENT_TIMESTAMP), "
        "updated_at = COALESCE(updated_at, CURRENT_TIMESTAMP) "
        "WHERE created_at IS NULL OR updated_at IS NULL"
    )
    with op.batch_alter_table("account_model_training_dispatch_outbox") as batch_op:
        batch_op.alter_column(
            "created_at",
            existing_type=sa.DateTime(),
            existing_server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        )
        batch_op.alter_column(
            "updated_at",
            existing_type=sa.DateTime(),
            existing_server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        )


def downgrade() -> None:
    with op.batch_alter_table("account_model_training_dispatch_outbox") as batch_op:
        batch_op.alter_column(
            "updated_at",
            existing_type=sa.DateTime(),
            existing_server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=True,
        )
        batch_op.alter_column(
            "created_at",
            existing_type=sa.DateTime(),
            existing_server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=True,
        )
