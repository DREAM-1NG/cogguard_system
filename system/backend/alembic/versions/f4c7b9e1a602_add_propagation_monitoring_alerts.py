"""add propagation monitoring profiles and alert audit tables

Revision ID: f4c7b9e1a602
Revises: f8a1c2d3e4b5
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "f4c7b9e1a602"
down_revision: Union[str, None] = "f8a1c2d3e4b5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "propagation_monitor_profiles",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("event_id", sa.String(length=128), nullable=False),
        sa.Column("platform", sa.String(length=32), nullable=False, server_default=""),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.Column("interval_minutes", sa.Integer(), nullable=False, server_default="5"),
        sa.Column("thresholds_json", sa.Text(), nullable=False),
        sa.Column("last_snapshot_id", sa.String(length=128), nullable=True),
        sa.Column("last_snapshot_json", sa.Text(), nullable=False),
        sa.Column("last_success_at", sa.DateTime(), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("updated_by", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=True),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("event_id", "platform", name="uq_propagation_monitor_profiles_event_platform"),
    )
    for column in ("event_id", "platform", "enabled", "last_snapshot_id"):
        op.create_index(f"ix_propagation_monitor_profiles_{column}", "propagation_monitor_profiles", [column])

    op.create_table(
        "propagation_alerts",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("event_id", sa.String(length=128), nullable=False),
        sa.Column("platform", sa.String(length=32), nullable=False, server_default=""),
        sa.Column("alert_type", sa.String(length=64), nullable=False),
        sa.Column("severity", sa.String(length=16), nullable=False),
        sa.Column("state", sa.String(length=16), nullable=False, server_default="new"),
        sa.Column("dedupe_key", sa.String(length=320), nullable=False),
        sa.Column("trigger_count", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("first_triggered_at", sa.DateTime(), nullable=False),
        sa.Column("last_triggered_at", sa.DateTime(), nullable=False),
        sa.Column("snapshot_id", sa.String(length=128), nullable=True),
        sa.Column("model_version_id", sa.Integer(), nullable=True),
        sa.Column("assigned_to", sa.Integer(), nullable=True),
        sa.Column("evidence_json", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=True),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=True),
        sa.Column("closed_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in ("event_id", "platform", "alert_type", "severity", "state", "dedupe_key", "last_triggered_at"):
        op.create_index(f"ix_propagation_alerts_{column}", "propagation_alerts", [column])

    op.create_table(
        "propagation_alert_actions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("alert_id", sa.Integer(), nullable=False),
        sa.Column("action", sa.String(length=32), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("actor_id", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in ("alert_id", "action", "actor_id"):
        op.create_index(f"ix_propagation_alert_actions_{column}", "propagation_alert_actions", [column])


def downgrade() -> None:
    op.drop_table("propagation_alert_actions")
    op.drop_table("propagation_alerts")
    op.drop_table("propagation_monitor_profiles")
