"""add authority source account bindings

Revision ID: a7c5e9d2f481
Revises: f4c7b9e1a602
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "a7c5e9d2f481"
down_revision: Union[str, None] = "f4c7b9e1a602"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "authority_source_accounts",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("source_id", sa.String(length=128), nullable=False),
        sa.Column("platform", sa.String(length=32), nullable=False),
        sa.Column("author_id", sa.String(length=256), nullable=False),
        sa.Column("display_name_snapshot", sa.String(length=512), nullable=False),
        sa.Column("verification_snapshot", sa.Text(), nullable=False),
        sa.Column("reviewed_by", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("source_id", "platform", "author_id", name="uq_authority_source_accounts_identity"),
    )
    op.create_index("ix_authority_source_accounts_source_id", "authority_source_accounts", ["source_id"])
    op.create_index("ix_authority_source_accounts_platform", "authority_source_accounts", ["platform"])
    op.create_index("ix_authority_source_accounts_author_id", "authority_source_accounts", ["author_id"])


def downgrade() -> None:
    op.drop_index("ix_authority_source_accounts_author_id", table_name="authority_source_accounts")
    op.drop_index("ix_authority_source_accounts_platform", table_name="authority_source_accounts")
    op.drop_index("ix_authority_source_accounts_source_id", table_name="authority_source_accounts")
    op.drop_table("authority_source_accounts")
