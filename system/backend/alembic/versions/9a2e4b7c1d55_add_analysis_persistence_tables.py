"""add_analysis_persistence_tables

Revision ID: 9a2e4b7c1d55
Revises: 7b4c2f9a0d31
Create Date: 2026-07-11 19:20:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "9a2e4b7c1d55"
down_revision: Union[str, None] = "7b4c2f9a0d31"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "analysis_event_snapshots",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("snapshot_id", sa.String(length=128), nullable=False),
        sa.Column("event_id", sa.String(length=128), nullable=False),
        sa.Column("data_fingerprint", sa.String(length=128), nullable=False),
        sa.Column("mongo_collection", sa.String(length=128), nullable=False),
        sa.Column("mongo_key", sa.String(length=256), nullable=False),
        sa.Column("platforms_json", sa.Text(), nullable=False),
        sa.Column("windows_json", sa.Text(), nullable=False),
        sa.Column("quality_json", sa.Text(), nullable=False),
        sa.Column("provenance_json", sa.Text(), nullable=False),
        sa.Column("created_by", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_analysis_event_snapshots_snapshot_id"),
        "analysis_event_snapshots",
        ["snapshot_id"],
        unique=True,
    )
    op.create_index(
        op.f("ix_analysis_event_snapshots_event_id"),
        "analysis_event_snapshots",
        ["event_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_analysis_event_snapshots_data_fingerprint"),
        "analysis_event_snapshots",
        ["data_fingerprint"],
        unique=False,
    )

    op.create_table(
        "analysis_runs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("run_id", sa.String(length=128), nullable=False),
        sa.Column("event_id", sa.String(length=128), nullable=False),
        sa.Column("snapshot_id", sa.String(length=128), nullable=False),
        sa.Column(
            "status",
            sa.String(length=32),
            nullable=False,
            comment="queued/running/needs_evidence/awaiting_review/completed/failed/cancelled",
        ),
        sa.Column("requested_stages_json", sa.Text(), nullable=False),
        sa.Column("options_json", sa.Text(), nullable=False),
        sa.Column("result_json", sa.Text(), nullable=True),
        sa.Column("artifact_manifest_json", sa.Text(), nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("celery_task_id", sa.String(length=128), nullable=True),
        sa.Column("created_by", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=True),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=True),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_analysis_runs_run_id"), "analysis_runs", ["run_id"], unique=True)
    op.create_index(op.f("ix_analysis_runs_event_id"), "analysis_runs", ["event_id"], unique=False)
    op.create_index(op.f("ix_analysis_runs_snapshot_id"), "analysis_runs", ["snapshot_id"], unique=False)
    op.create_index(op.f("ix_analysis_runs_status"), "analysis_runs", ["status"], unique=False)
    op.create_index(op.f("ix_analysis_runs_celery_task_id"), "analysis_runs", ["celery_task_id"], unique=False)

    op.create_table(
        "analysis_run_events",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("run_id", sa.String(length=128), nullable=False),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_analysis_run_events_run_id"), "analysis_run_events", ["run_id"], unique=False)

    op.create_table(
        "analysis_model_versions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("technology", sa.String(length=64), nullable=False),
        sa.Column("model", sa.String(length=128), nullable=False),
        sa.Column("version", sa.String(length=64), nullable=False),
        sa.Column("artifact_hash", sa.String(length=128), nullable=False),
        sa.Column("artifact_uri", sa.Text(), nullable=False),
        sa.Column("config_json", sa.Text(), nullable=False),
        sa.Column("metrics_json", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("created_by", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_analysis_model_versions_technology"),
        "analysis_model_versions",
        ["technology"],
        unique=False,
    )
    op.create_index(
        op.f("ix_analysis_model_versions_artifact_hash"),
        "analysis_model_versions",
        ["artifact_hash"],
        unique=False,
    )
    op.create_index(op.f("ix_analysis_model_versions_status"), "analysis_model_versions", ["status"], unique=False)

    op.create_table(
        "analysis_model_activations",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("technology", sa.String(length=64), nullable=False),
        sa.Column("model_version_id", sa.Integer(), nullable=False),
        sa.Column("provenance_json", sa.Text(), nullable=False),
        sa.Column("activated_by", sa.Integer(), nullable=False),
        sa.Column("activated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_analysis_model_activations_technology"),
        "analysis_model_activations",
        ["technology"],
        unique=True,
    )
    op.create_index(
        op.f("ix_analysis_model_activations_model_version_id"),
        "analysis_model_activations",
        ["model_version_id"],
        unique=False,
    )

    op.create_table(
        "analysis_review_verdict_versions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("verdict_id", sa.String(length=128), nullable=False),
        sa.Column("run_id", sa.String(length=128), nullable=False),
        sa.Column("snapshot_id", sa.String(length=128), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("verdict_type", sa.String(length=32), nullable=False, comment="preliminary/teacher_advisory/canonical"),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("verdict_json", sa.Text(), nullable=False),
        sa.Column("immutable_source", sa.String(length=128), nullable=False),
        sa.Column("canonical_source_id", sa.String(length=128), nullable=True),
        sa.Column("provenance_json", sa.Text(), nullable=False),
        sa.Column("approved_by", sa.Integer(), nullable=True),
        sa.Column("approved_at", sa.DateTime(), nullable=True),
        sa.Column("approval_notes", sa.Text(), nullable=True),
        sa.Column("created_by", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "verdict_id",
            "version",
            name="uq_analysis_review_verdict_versions_verdict_version",
        ),
    )
    op.create_index(
        op.f("ix_analysis_review_verdict_versions_verdict_id"),
        "analysis_review_verdict_versions",
        ["verdict_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_analysis_review_verdict_versions_run_id"),
        "analysis_review_verdict_versions",
        ["run_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_analysis_review_verdict_versions_snapshot_id"),
        "analysis_review_verdict_versions",
        ["snapshot_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_analysis_review_verdict_versions_verdict_type"),
        "analysis_review_verdict_versions",
        ["verdict_type"],
        unique=False,
    )
    op.create_index(
        op.f("ix_analysis_review_verdict_versions_status"),
        "analysis_review_verdict_versions",
        ["status"],
        unique=False,
    )

    op.create_table(
        "analysis_review_feedback",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("feedback_id", sa.String(length=128), nullable=False),
        sa.Column("run_id", sa.String(length=128), nullable=False),
        sa.Column("verdict_id", sa.String(length=128), nullable=True),
        sa.Column("snapshot_id", sa.String(length=128), nullable=False),
        sa.Column("feedback_json", sa.Text(), nullable=False),
        sa.Column("immutable_source", sa.String(length=128), nullable=False),
        sa.Column("provenance_json", sa.Text(), nullable=False),
        sa.Column("created_by", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_analysis_review_feedback_feedback_id"),
        "analysis_review_feedback",
        ["feedback_id"],
        unique=True,
    )
    op.create_index(op.f("ix_analysis_review_feedback_run_id"), "analysis_review_feedback", ["run_id"], unique=False)
    op.create_index(
        op.f("ix_analysis_review_feedback_verdict_id"),
        "analysis_review_feedback",
        ["verdict_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_analysis_review_feedback_snapshot_id"),
        "analysis_review_feedback",
        ["snapshot_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_analysis_review_feedback_created_by"),
        "analysis_review_feedback",
        ["created_by"],
        unique=False,
    )


def downgrade() -> None:
    for index_name, table_name in [
        ("ix_analysis_review_feedback_created_by", "analysis_review_feedback"),
        ("ix_analysis_review_feedback_snapshot_id", "analysis_review_feedback"),
        ("ix_analysis_review_feedback_verdict_id", "analysis_review_feedback"),
        ("ix_analysis_review_feedback_run_id", "analysis_review_feedback"),
        ("ix_analysis_review_feedback_feedback_id", "analysis_review_feedback"),
        ("ix_analysis_review_verdict_versions_status", "analysis_review_verdict_versions"),
        ("ix_analysis_review_verdict_versions_verdict_type", "analysis_review_verdict_versions"),
        ("ix_analysis_review_verdict_versions_snapshot_id", "analysis_review_verdict_versions"),
        ("ix_analysis_review_verdict_versions_run_id", "analysis_review_verdict_versions"),
        ("ix_analysis_review_verdict_versions_verdict_id", "analysis_review_verdict_versions"),
        ("ix_analysis_model_activations_model_version_id", "analysis_model_activations"),
        ("ix_analysis_model_activations_technology", "analysis_model_activations"),
        ("ix_analysis_model_versions_status", "analysis_model_versions"),
        ("ix_analysis_model_versions_artifact_hash", "analysis_model_versions"),
        ("ix_analysis_model_versions_technology", "analysis_model_versions"),
        ("ix_analysis_run_events_run_id", "analysis_run_events"),
        ("ix_analysis_runs_celery_task_id", "analysis_runs"),
        ("ix_analysis_runs_status", "analysis_runs"),
        ("ix_analysis_runs_snapshot_id", "analysis_runs"),
        ("ix_analysis_runs_event_id", "analysis_runs"),
        ("ix_analysis_runs_run_id", "analysis_runs"),
        ("ix_analysis_event_snapshots_data_fingerprint", "analysis_event_snapshots"),
        ("ix_analysis_event_snapshots_event_id", "analysis_event_snapshots"),
        ("ix_analysis_event_snapshots_snapshot_id", "analysis_event_snapshots"),
    ]:
        op.drop_index(op.f(index_name), table_name=table_name)
    for table in [
        "analysis_review_feedback",
        "analysis_review_verdict_versions",
        "analysis_model_activations",
        "analysis_model_versions",
        "analysis_run_events",
        "analysis_runs",
        "analysis_event_snapshots",
    ]:
        op.drop_table(table)
