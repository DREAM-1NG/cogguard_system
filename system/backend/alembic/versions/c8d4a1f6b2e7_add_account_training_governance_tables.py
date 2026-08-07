"""add account training governance tables

Revision ID: c8d4a1f6b2e7
Revises: b6c2e9d4a731
Create Date: 2026-08-05 12:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "c8d4a1f6b2e7"
down_revision: Union[str, Sequence[str], None] = "b6c2e9d4a731"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "account_behavior_labels",
        sa.Column("supersedes_id", sa.String(length=128), nullable=True),
    )
    op.add_column(
        "account_behavior_labels",
        sa.Column("review_required", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "account_behavior_labels",
        sa.Column(
            "second_review_status",
            sa.String(length=32),
            nullable=False,
            server_default="not_required",
        ),
    )
    _index("account_behavior_labels", "supersedes_id")

    op.add_column(
        "account_detection_model_activations",
        sa.Column("pointer_revision", sa.Integer(), nullable=False, server_default=sa.text("1")),
    )

    op.create_table(
        "account_corpus_versions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("corpus_version_id", sa.String(length=128), nullable=False),
        sa.Column("input_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("source_label_count", sa.Integer(), nullable=False),
        sa.Column("manifest_json", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("created_by", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("corpus_version_id", name="uq_account_corpus_versions_id"),
    )
    for column in ("corpus_version_id", "input_fingerprint", "status", "created_by"):
        _index("account_corpus_versions", column)

    op.create_table(
        "account_label_review_assignments",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("assignment_id", sa.String(length=128), nullable=False),
        sa.Column("label_id", sa.String(length=128), nullable=False),
        sa.Column("reviewer_id", sa.Integer(), nullable=False),
        sa.Column("review_round", sa.Integer(), nullable=False),
        sa.Column("review_status", sa.String(length=32), nullable=False),
        sa.Column("assignment_json", sa.Text(), nullable=False),
        sa.Column("assigned_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("assignment_id", name="uq_account_label_review_assignments_id"),
    )
    for column in ("assignment_id", "label_id", "reviewer_id", "review_status"):
        _index("account_label_review_assignments", column)

    op.create_table(
        "account_frozen_holdout_memberships",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("membership_id", sa.String(length=128), nullable=False),
        sa.Column("corpus_version_id", sa.String(length=128), nullable=False),
        sa.Column("case_id", sa.String(length=128), nullable=False),
        sa.Column("label_id", sa.String(length=128), nullable=False),
        sa.Column("stratum_json", sa.Text(), nullable=False),
        sa.Column("frozen_by", sa.Integer(), nullable=False),
        sa.Column("frozen_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("membership_id", name="uq_account_frozen_holdout_memberships_id"),
        sa.UniqueConstraint(
            "corpus_version_id",
            "case_id",
            name="uq_account_frozen_holdout_memberships_corpus_case",
        ),
    )
    for column in ("membership_id", "corpus_version_id", "case_id", "label_id", "frozen_by"):
        _index("account_frozen_holdout_memberships", column)

    op.create_table(
        "account_model_training_runs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("run_id", sa.String(length=128), nullable=False),
        sa.Column("family", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("stage", sa.String(length=64), nullable=False),
        sa.Column("corpus_version_id", sa.String(length=128), nullable=True),
        sa.Column("input_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("config_hash", sa.String(length=64), nullable=False),
        sa.Column("config_json", sa.Text(), nullable=False),
        sa.Column("attempt", sa.Integer(), nullable=False),
        sa.Column("max_attempts", sa.Integer(), nullable=False),
        sa.Column("heartbeat_at", sa.DateTime(), nullable=True),
        sa.Column("resume_checkpoint_uri", sa.Text(), nullable=True),
        sa.Column("cancel_requested_at", sa.DateTime(), nullable=True),
        sa.Column("cancelled_by", sa.Integer(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_by", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=True),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=True),
        sa.CheckConstraint(
            "status IN ('queued', 'preparing', 'running', 'evaluating', 'completed', "
            "'failed', 'cancelled', 'interrupted')",
            name="ck_account_model_training_runs_status",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("run_id", name="uq_account_model_training_runs_id"),
    )
    for column in (
        "run_id",
        "family",
        "status",
        "stage",
        "corpus_version_id",
        "input_fingerprint",
        "config_hash",
        "cancelled_by",
        "created_by",
    ):
        _index("account_model_training_runs", column)

    op.create_table(
        "account_model_training_events",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("event_id", sa.String(length=128), nullable=False),
        sa.Column("run_id", sa.String(length=128), nullable=False),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("stage", sa.String(length=64), nullable=False),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("event_id", name="uq_account_model_training_events_id"),
    )
    for column in ("event_id", "run_id", "event_type", "status", "stage"):
        _index("account_model_training_events", column)

    op.create_table(
        "account_model_governance_decisions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("decision_id", sa.String(length=128), nullable=False),
        sa.Column("family", sa.String(length=64), nullable=False),
        sa.Column("model_version", sa.String(length=128), nullable=False),
        sa.Column("previous_model_version", sa.String(length=128), nullable=True),
        sa.Column("pointer_revision", sa.Integer(), nullable=False),
        sa.Column("decision_type", sa.String(length=32), nullable=False),
        sa.Column("decision_json", sa.Text(), nullable=False),
        sa.Column("decided_by", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("decision_id", name="uq_account_model_governance_decisions_id"),
    )
    for column in (
        "decision_id",
        "family",
        "model_version",
        "previous_model_version",
        "decision_type",
        "decided_by",
    ):
        _index("account_model_governance_decisions", column)

    op.create_table(
        "account_prediction_audits",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("audit_id", sa.String(length=128), nullable=False),
        sa.Column("case_id", sa.String(length=128), nullable=False),
        sa.Column("account_id", sa.String(length=192), nullable=False),
        sa.Column("platform", sa.String(length=32), nullable=False),
        sa.Column("family", sa.String(length=64), nullable=False),
        sa.Column("model_version", sa.String(length=128), nullable=False),
        sa.Column("pointer_revision", sa.Integer(), nullable=False),
        sa.Column("input_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("prediction_json", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("audit_id", name="uq_account_prediction_audits_id"),
    )
    for column in (
        "audit_id",
        "case_id",
        "account_id",
        "platform",
        "family",
        "model_version",
        "pointer_revision",
        "input_fingerprint",
    ):
        _index("account_prediction_audits", column)

    op.create_table(
        "account_monitor_snapshots",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("snapshot_id", sa.String(length=128), nullable=False),
        sa.Column("family", sa.String(length=64), nullable=False),
        sa.Column("model_version", sa.String(length=128), nullable=False),
        sa.Column("pointer_revision", sa.Integer(), nullable=False),
        sa.Column("window_started_at", sa.DateTime(), nullable=False),
        sa.Column("window_finished_at", sa.DateTime(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("metrics_json", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("snapshot_id", name="uq_account_monitor_snapshots_id"),
    )
    for column in ("snapshot_id", "family", "model_version", "pointer_revision", "status"):
        _index("account_monitor_snapshots", column)


def downgrade() -> None:
    tables = (
        ("account_monitor_snapshots", ("snapshot_id", "family", "model_version", "pointer_revision", "status")),
        (
            "account_prediction_audits",
            (
                "audit_id",
                "case_id",
                "account_id",
                "platform",
                "family",
                "model_version",
                "pointer_revision",
                "input_fingerprint",
            ),
        ),
        (
            "account_model_governance_decisions",
            ("decision_id", "family", "model_version", "previous_model_version", "decision_type", "decided_by"),
        ),
        ("account_model_training_events", ("event_id", "run_id", "event_type", "status", "stage")),
        (
            "account_model_training_runs",
            (
                "run_id",
                "family",
                "status",
                "stage",
                "corpus_version_id",
                "input_fingerprint",
                "config_hash",
                "cancelled_by",
                "created_by",
            ),
        ),
        (
            "account_frozen_holdout_memberships",
            ("membership_id", "corpus_version_id", "case_id", "label_id", "frozen_by"),
        ),
        ("account_label_review_assignments", ("assignment_id", "label_id", "reviewer_id", "review_status")),
        ("account_corpus_versions", ("corpus_version_id", "input_fingerprint", "status", "created_by")),
    )
    for table_name, columns in tables:
        for column in reversed(columns):
            op.drop_index(f"ix_{table_name}_{column}", table_name=table_name)
        op.drop_table(table_name)

    op.drop_column("account_detection_model_activations", "pointer_revision")
    op.drop_index("ix_account_behavior_labels_supersedes_id", table_name="account_behavior_labels")
    op.drop_column("account_behavior_labels", "second_review_status")
    op.drop_column("account_behavior_labels", "review_required")
    op.drop_column("account_behavior_labels", "supersedes_id")


def _index(table_name: str, column_name: str) -> None:
    op.create_index(f"ix_{table_name}_{column_name}", table_name, [column_name], unique=False)
