"""store platform scope for frozen holdout memberships.

Revision ID: e5c1b7d9a204
Revises: c4f7a9d2e618
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "e5c1b7d9a204"
down_revision: Union[str, Sequence[str], None] = "c4f7a9d2e618"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "account_frozen_holdout_memberships",
        sa.Column("platform", sa.String(length=32), nullable=True),
    )
    op.create_index(
        "ix_account_frozen_holdout_memberships_platform",
        "account_frozen_holdout_memberships",
        ["platform"],
        unique=False,
    )
    # Preserve the scope of rows created before the dedicated column existed.
    op.execute(
        sa.text(
            "UPDATE account_frozen_holdout_memberships "
            "SET platform = JSON_UNQUOTE(JSON_EXTRACT(stratum_json, '$.platform')) "
            "WHERE platform IS NULL AND JSON_EXTRACT(stratum_json, '$.platform') IS NOT NULL"
        )
    )


def downgrade() -> None:
    op.drop_index(
        "ix_account_frozen_holdout_memberships_platform",
        table_name="account_frozen_holdout_memberships",
    )
    op.drop_column("account_frozen_holdout_memberships", "platform")
