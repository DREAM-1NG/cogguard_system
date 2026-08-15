"""add case workbench base tables

Revision ID: b9e6c1a3d0f2
Revises: a7c5e9d2f481
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b9e6c1a3d0f2"
down_revision: Union[str, None] = "a7c5e9d2f481"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "case_records",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("case_id", sa.String(length=128), nullable=False),
        sa.Column("event_id", sa.String(length=128), nullable=False),
        sa.Column("title", sa.String(length=512), nullable=False),
        sa.Column("lifecycle", sa.String(length=32), nullable=False),
        sa.Column("canonical_verdict_json", sa.Text(), nullable=False),
        sa.Column("canonical_approved", sa.Boolean(), nullable=False),
        sa.Column("closure_note", sa.Text(), nullable=False),
        sa.Column("closure_report_id", sa.String(length=128), nullable=True),
        sa.Column("created_by", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("case_id", name="uq_case_records_case_id"),
        sa.UniqueConstraint("event_id", name="uq_case_records_event_id"),
    )
    op.create_index("ix_case_records_lifecycle", "case_records", ["lifecycle"], unique=False)

    op.create_table(
        "authority_sources",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("source_id", sa.String(length=128), nullable=False),
        sa.Column("name", sa.String(length=512), nullable=False),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("review_status", sa.String(length=32), nullable=False),
        sa.Column("tier", sa.String(length=64), nullable=True),
        sa.Column("reviewed_by", sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("source_id", name="uq_authority_sources_source_id"),
    )

    op.create_table(
        "case_claims",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("claim_id", sa.String(length=128), nullable=False),
        sa.Column("case_id", sa.String(length=128), nullable=False),
        sa.Column("authority_source_id", sa.String(length=128), nullable=False),
        sa.Column("exact_quote", sa.Text(), nullable=False),
        sa.Column("quote_start", sa.Integer(), nullable=False),
        sa.Column("quote_end", sa.Integer(), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=False),
        sa.Column("account", sa.String(length=256), nullable=False),
        sa.Column("published_at", sa.DateTime(), nullable=True),
        sa.Column("role", sa.String(length=16), nullable=False),
        sa.Column("source_tier_snapshot", sa.String(length=64), nullable=True),
        sa.Column("source_review_snapshot", sa.String(length=32), nullable=False),
        sa.Column("content_sha256", sa.String(length=64), nullable=False),
        sa.ForeignKeyConstraint(["case_id"], ["case_records.case_id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("claim_id", name="uq_case_claims_claim_id"),
    )
    op.create_index("ix_case_claims_case_id", "case_claims", ["case_id"], unique=False)

    op.create_table(
        "case_analysis_links",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("link_id", sa.String(length=128), nullable=False),
        sa.Column("case_id", sa.String(length=128), nullable=False),
        sa.Column("snapshot_or_run_id", sa.String(length=128), nullable=True),
        sa.Column("stages_json", sa.Text(), nullable=False),
        sa.Column("blockers_json", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["case_id"], ["case_records.case_id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("link_id", name="uq_case_analysis_links_link_id"),
    )

    op.create_table(
        "semantic_artifacts",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("artifact_id", sa.String(length=128), nullable=False),
        sa.Column("case_id", sa.String(length=128), nullable=False),
        sa.Column("artifact_type", sa.String(length=128), nullable=False),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.Column("model_id", sa.String(length=128), nullable=True),
        sa.Column("model_revision", sa.String(length=128), nullable=True),
        sa.Column("validation_status", sa.String(length=32), nullable=False),
        sa.Column("scope_hash", sa.String(length=64), nullable=True),
        sa.Column("input_hash", sa.String(length=64), nullable=True),
        sa.Column("output_hash", sa.String(length=64), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("artifact_id", name="uq_semantic_artifacts_artifact_id"),
    )

    op.create_table(
        "semantic_corrections",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("correction_id", sa.String(length=128), nullable=False),
        sa.Column("case_id", sa.String(length=128), nullable=False),
        sa.Column("artifact_id", sa.String(length=128), nullable=False),
        sa.Column("original_payload_json", sa.Text(), nullable=False),
        sa.Column("corrected_payload_json", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("correction_id", name="uq_semantic_corrections_correction_id"),
    )

    op.create_table(
        "case_actions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("action_id", sa.String(length=128), nullable=False),
        sa.Column("case_id", sa.String(length=128), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("required", sa.Boolean(), nullable=False),
        sa.Column("state", sa.String(length=16), nullable=False),
        sa.Column("waiver_reason", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("action_id", name="uq_case_actions_action_id"),
    )

    op.create_table(
        "case_feedback",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("feedback_id", sa.String(length=128), nullable=False),
        sa.Column("case_id", sa.String(length=128), nullable=False),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("feedback_id", name="uq_case_feedback_feedback_id"),
    )

    op.create_table(
        "case_report_versions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("report_id", sa.String(length=128), nullable=False),
        sa.Column("case_id", sa.String(length=128), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("manifest_json", sa.Text(), nullable=False),
        sa.Column("html", sa.Text(), nullable=False),
        sa.Column("manifest_sha256", sa.String(length=64), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("report_id", name="uq_case_report_versions_report_id"),
    )

    op.create_table(
        "case_audit_events",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("case_id", sa.String(length=128), nullable=False),
        sa.Column("event_type", sa.String(length=128), nullable=False),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("case_audit_events")
    op.drop_table("case_report_versions")
    op.drop_table("case_feedback")
    op.drop_table("case_actions")
    op.drop_table("semantic_corrections")
    op.drop_table("semantic_artifacts")
    op.drop_table("case_analysis_links")
    op.drop_index("ix_case_claims_case_id", table_name="case_claims")
    op.drop_table("case_claims")
    op.drop_table("authority_sources")
    op.drop_index("ix_case_records_lifecycle", table_name="case_records")
    op.drop_table("case_records")
