"""store account scope for frozen holdout memberships.

Revision ID: d6e1f7a9b3c2
Revises: c8d4a1f6b2e7
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "d6e1f7a9b3c2"
down_revision: Union[str, Sequence[str], None] = "c8d4a1f6b2e7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "account_frozen_holdout_memberships",
        sa.Column("account_id", sa.String(length=192), nullable=True),
    )
    op.create_index(
        "ix_account_frozen_holdout_memberships_account_id",
        "account_frozen_holdout_memberships",
        ["account_id"],
        unique=False,
    )
    # Existing memberships predate the account-scope field.  Populate rows
    # when the referenced case is still present; nullable keeps old imports
    # auditable without inventing an account identity.
    op.execute(
        sa.text(
            "UPDATE account_frozen_holdout_memberships AS membership "
            "JOIN account_detection_cases AS detection_case "
            "ON detection_case.case_id = membership.case_id "
            "SET membership.account_id = detection_case.account_id "
            "WHERE membership.account_id IS NULL"
        )
    )


def downgrade() -> None:
    op.drop_index(
        "ix_account_frozen_holdout_memberships_account_id",
        table_name="account_frozen_holdout_memberships",
    )
    op.drop_column("account_frozen_holdout_memberships", "account_id")
