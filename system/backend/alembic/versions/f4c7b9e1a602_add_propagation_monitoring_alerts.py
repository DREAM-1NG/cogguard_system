"""add propagation monitoring profiles and alert audit tables

Revision ID: f4c7b9e1a602
Revises: f8a1c2d3e4b5
Create Date: 2026-08-15 18:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


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
    op.create_index("ix_propagation_monitor_profiles_event_id", "propagation_monitor_profiles", ["event_id"])
    op.create_index("ix_propagation_monitor_profiles_platform", "propagation_monitor_profiles", ["platform"])
    op.create_index("ix_propagation_monitor_profiles_enabled", "propagation_monitor_profiles", ["enabled"])
    op.create_index("ix_propagation_monitor_profiles_last_snapshot_id", "propagation_monitor_profiles", ["last_snapshot_id"])

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
    for name, columns in {
        "ix_propagation_alerts_event_id": ["event_id"], "ix_propagation_alerts_platform": ["platform"],
        "ix_propagation_alerts_alert_type": ["alert_type"], "ix_propagation_alerts_severity": ["severity"],
        "ix_propagation_alerts_state": ["state"], "ix_propagation_alerts_dedupe_key": ["dedupe_key"],
        "ix_propagation_alerts_first_triggered_at": ["first_triggered_at"],
        "ix_propagation_alerts_last_triggered_at": ["last_triggered_at"],
        "ix_propagation_alerts_snapshot_id": ["snapshot_id"],
        "ix_propagation_alerts_model_version_id": ["model_version_id"],
        "ix_propagation_alerts_assigned_to": ["assigned_to"],
    }.items():
        op.create_index(name, "propagation_alerts", columns)

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
    op.create_index("ix_propagation_alert_actions_alert_id", "propagation_alert_actions", ["alert_id"])
    op.create_index("ix_propagation_alert_actions_action", "propagation_alert_actions", ["action"])
    op.create_index("ix_propagation_alert_actions_actor_id", "propagation_alert_actions", ["actor_id"])


def downgrade() -> None:
    op.drop_table("propagation_alert_actions")
    op.drop_table("propagation_alerts")
    op.drop_table("propagation_monitor_profiles")
