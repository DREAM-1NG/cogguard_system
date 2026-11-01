"""add monitoring profile leases and open alert dedupe key

Revision ID: c1d4e8f2a706
Revises: b9e4d2a7c610
Create Date: 2026-09-04 10:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c1d4e8f2a706"
down_revision: Union[str, None] = "b9e4d2a7c610"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "propagation_monitor_profiles",
        sa.Column("claim_token", sa.String(length=128), nullable=True),
    )
    op.add_column(
        "propagation_monitor_profiles",
        sa.Column("claim_expires_at", sa.DateTime(), nullable=True),
    )
    op.create_index(
        "ix_propagation_monitor_profiles_claim_token",
        "propagation_monitor_profiles",
        ["claim_token"],
    )
    op.create_index(
        "ix_propagation_monitor_profiles_claim_expires_at",
        "propagation_monitor_profiles",
        ["claim_expires_at"],
    )
    op.add_column(
        "propagation_alerts",
        sa.Column("open_dedupe_key", sa.String(length=320), nullable=True),
    )
    op.execute(
        sa.text(
            "UPDATE propagation_alerts SET open_dedupe_key = NULL "
            "WHERE state IN ('new', 'acknowledged')"
        )
    )
    op.execute(
        sa.text(
            "UPDATE propagation_alerts SET open_dedupe_key = dedupe_key "
            "WHERE id IN (SELECT keeper_id FROM ("
            "SELECT MAX(id) AS keeper_id FROM propagation_alerts "
            "WHERE state IN ('new', 'acknowledged') GROUP BY dedupe_key"
            ") AS open_alert_keepers)"
        )
    )
    op.create_index(
        "uq_propagation_alerts_open_dedupe_key",
        "propagation_alerts",
        ["open_dedupe_key"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index(
        "uq_propagation_alerts_open_dedupe_key",
        table_name="propagation_alerts",
    )
    op.drop_column("propagation_alerts", "open_dedupe_key")
    op.drop_index(
        "ix_propagation_monitor_profiles_claim_expires_at",
        table_name="propagation_monitor_profiles",
    )
    op.drop_index(
        "ix_propagation_monitor_profiles_claim_token",
        table_name="propagation_monitor_profiles",
    )
    op.drop_column("propagation_monitor_profiles", "claim_expires_at")
    op.drop_column("propagation_monitor_profiles", "claim_token")
