"""add_review_case_tables

Revision ID: e8b4c1d7a620
Revises: d2f7a8b9c0e1
Create Date: 2026-08-03 01:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "e8b4c1d7a620"
down_revision: Union[str, None] = "d2f7a8b9c0e1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "review_cases",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("case_id", sa.String(length=128), nullable=False),
        sa.Column("event_id", sa.String(length=128), nullable=False),
        sa.Column("title", sa.String(length=512), nullable=False),
        sa.Column("preliminary_conclusion", sa.String(length=32), nullable=False),
        sa.Column("evidence_sufficiency", sa.String(length=32), nullable=False),
        sa.Column("urgency", sa.String(length=32), nullable=False),
        sa.Column("disposition", sa.String(length=32), nullable=False),
        sa.Column("action_required", sa.String(length=32), nullable=False),
        sa.Column("preliminary_finding_json", sa.Text(), nullable=False),
        sa.Column("business_summary_json", sa.Text(), nullable=False),
        sa.Column("created_by", sa.Integer(), nullable=False),
        sa.Column("updated_by", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("case_id", name="uq_review_cases_case_id"),
        sa.UniqueConstraint("event_id", name="uq_review_cases_event_id"),
    )
    op.create_index("ix_review_cases_action_required", "review_cases", ["action_required"], unique=False)
    op.create_index("ix_review_cases_updated_at", "review_cases", ["updated_at"], unique=False)

    op.create_table(
        "review_case_snapshot_revisions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("snapshot_revision_id", sa.String(length=128), nullable=False),
        sa.Column("case_id", sa.String(length=128), nullable=False),
        sa.Column("snapshot_id", sa.String(length=128), nullable=False),
        sa.Column("data_fingerprint", sa.String(length=128), nullable=False),
        sa.Column("revision_number", sa.Integer(), nullable=False),
        sa.Column("core_window_start", sa.DateTime(), nullable=False),
        sa.Column("core_window_end", sa.DateTime(), nullable=False),
        sa.Column("context_window_start", sa.DateTime(), nullable=False),
        sa.Column("context_window_end", sa.DateTime(), nullable=False),
        sa.Column("quality_json", sa.Text(), nullable=False),
        sa.Column("provenance_json", sa.Text(), nullable=False),
        sa.Column("analysis_run_id", sa.String(length=128), nullable=True),
        sa.Column("teacher_run_id", sa.String(length=128), nullable=True),
        sa.Column("teacher_verdict_id", sa.String(length=128), nullable=True),
        sa.Column("analysis_completed_at", sa.DateTime(), nullable=True),
        sa.Column("created_by", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(
            ["case_id"],
            ["review_cases.case_id"],
            name="fk_review_case_snapshot_revisions_case_id_review_cases",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["snapshot_id"],
            ["analysis_event_snapshots.snapshot_id"],
            name="fk_review_case_snapshot_revisions_snapshot_id_analysis_snapshots",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "snapshot_revision_id",
            name="uq_review_case_snapshot_revisions_revision_id",
        ),
        sa.UniqueConstraint(
            "case_id",
            "data_fingerprint",
            name="uq_review_case_snapshot_revisions_case_fingerprint",
        ),
        sa.UniqueConstraint(
            "case_id",
            "revision_number",
            name="uq_review_case_snapshot_revisions_case_revision",
        ),
    )
    op.create_index(
        "ix_review_case_snapshot_revisions_case_id",
        "review_case_snapshot_revisions",
        ["case_id"],
        unique=False,
    )
    op.create_index(
        "ix_review_case_snapshot_revisions_snapshot_id",
        "review_case_snapshot_revisions",
        ["snapshot_id"],
        unique=False,
    )
    op.create_index(
        "ix_review_case_snapshot_revisions_data_fingerprint",
        "review_case_snapshot_revisions",
        ["data_fingerprint"],
        unique=False,
    )
    op.create_index(
        "ix_review_case_snapshot_revisions_analysis_run_id",
        "review_case_snapshot_revisions",
        ["analysis_run_id"],
        unique=False,
    )
    op.create_index(
        "ix_review_case_snapshot_revisions_teacher_run_id",
        "review_case_snapshot_revisions",
        ["teacher_run_id"],
        unique=False,
    )
    op.create_index(
        "ix_review_case_snapshot_revisions_teacher_verdict_id",
        "review_case_snapshot_revisions",
        ["teacher_verdict_id"],
        unique=False,
    )

    op.create_table(
        "review_decision_drafts",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("case_id", sa.String(length=128), nullable=False),
        sa.Column("snapshot_revision_id", sa.String(length=128), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("conclusion", sa.String(length=32), nullable=False),
        sa.Column("urgency", sa.String(length=32), nullable=False),
        sa.Column("disposition", sa.String(length=32), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=False),
        sa.Column("key_evidence_refs_json", sa.Text(), nullable=False),
        sa.Column("unresolved_items_json", sa.Text(), nullable=False),
        sa.Column("created_by", sa.Integer(), nullable=False),
        sa.Column("updated_by", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(
            ["case_id"],
            ["review_cases.case_id"],
            name="fk_review_decision_drafts_case_id_review_cases",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["snapshot_revision_id"],
            ["review_case_snapshot_revisions.snapshot_revision_id"],
            name="fk_review_decision_drafts_snapshot_revision_id",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("case_id", name="uq_review_decision_drafts_case_id"),
    )
    op.create_index(
        "ix_review_decision_drafts_snapshot_revision_id",
        "review_decision_drafts",
        ["snapshot_revision_id"],
        unique=False,
    )

    op.create_table(
        "review_decisions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("decision_id", sa.String(length=128), nullable=False),
        sa.Column("case_id", sa.String(length=128), nullable=False),
        sa.Column("snapshot_revision_id", sa.String(length=128), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("supersedes_decision_id", sa.String(length=128), nullable=True),
        sa.Column("conclusion", sa.String(length=32), nullable=False),
        sa.Column("urgency", sa.String(length=32), nullable=False),
        sa.Column("disposition", sa.String(length=32), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=False),
        sa.Column("key_evidence_refs_json", sa.Text(), nullable=False),
        sa.Column("unresolved_items_json", sa.Text(), nullable=False),
        sa.Column("confirmation_note", sa.Text(), nullable=False),
        sa.Column("confirmed_by", sa.Integer(), nullable=False),
        sa.Column("confirmed_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("created_by", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(
            ["case_id"],
            ["review_cases.case_id"],
            name="fk_review_decisions_case_id_review_cases",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["snapshot_revision_id"],
            ["review_case_snapshot_revisions.snapshot_revision_id"],
            name="fk_review_decisions_snapshot_revision_id",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["supersedes_decision_id"],
            ["review_decisions.decision_id"],
            name="fk_review_decisions_supersedes_decision_id",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("decision_id", name="uq_review_decisions_decision_id"),
        sa.UniqueConstraint("case_id", "version", name="uq_review_decisions_case_version"),
    )
    op.create_index("ix_review_decisions_case_id", "review_decisions", ["case_id"], unique=False)
    op.create_index(
        "ix_review_decisions_snapshot_revision_id",
        "review_decisions",
        ["snapshot_revision_id"],
        unique=False,
    )

    op.create_table(
        "review_evidence_annotations",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("annotation_id", sa.String(length=128), nullable=False),
        sa.Column("case_id", sa.String(length=128), nullable=False),
        sa.Column("snapshot_revision_id", sa.String(length=128), nullable=False),
        sa.Column("evidence_ref", sa.String(length=512), nullable=False),
        sa.Column("assessment", sa.String(length=32), nullable=False),
        sa.Column("note", sa.Text(), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=True),
        sa.Column("created_by", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(
            ["case_id"],
            ["review_cases.case_id"],
            name="fk_review_evidence_annotations_case_id_review_cases",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["snapshot_revision_id"],
            ["review_case_snapshot_revisions.snapshot_revision_id"],
            name="fk_review_evidence_annotations_snapshot_revision_id",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("annotation_id", name="uq_review_evidence_annotations_annotation_id"),
    )
    op.create_index(
        "ix_review_evidence_annotations_case_id",
        "review_evidence_annotations",
        ["case_id"],
        unique=False,
    )
    op.create_index(
        "ix_review_evidence_annotations_snapshot_revision_id",
        "review_evidence_annotations",
        ["snapshot_revision_id"],
        unique=False,
    )
    op.create_index(
        "ix_review_evidence_annotations_evidence_ref",
        "review_evidence_annotations",
        ["evidence_ref"],
        unique=False,
    )
    op.create_index(
        "ix_review_evidence_annotations_assessment",
        "review_evidence_annotations",
        ["assessment"],
        unique=False,
    )

    op.create_table(
        "review_case_activities",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("case_id", sa.String(length=128), nullable=False),
        sa.Column("snapshot_revision_id", sa.String(length=128), nullable=True),
        sa.Column("activity_type", sa.String(length=64), nullable=False),
        sa.Column("action_required", sa.String(length=32), nullable=False),
        sa.Column("source_ref", sa.String(length=128), nullable=True),
        sa.Column("summary", sa.String(length=1000), nullable=False),
        sa.Column("detail_lines_json", sa.Text(), nullable=False),
        sa.Column("evidence_refs_json", sa.Text(), nullable=False),
        sa.Column("actor_name", sa.String(length=128), nullable=False),
        sa.Column("created_by", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(
            ["case_id"],
            ["review_cases.case_id"],
            name="fk_review_case_activities_case_id_review_cases",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["snapshot_revision_id"],
            ["review_case_snapshot_revisions.snapshot_revision_id"],
            name="fk_review_case_activities_snapshot_revision_id",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "case_id",
            "activity_type",
            "source_ref",
            name="uq_review_case_activities_case_type_source",
        ),
    )
    op.create_index(
        "ix_review_case_activities_case_id",
        "review_case_activities",
        ["case_id"],
        unique=False,
    )
    op.create_index(
        "ix_review_case_activities_snapshot_revision_id",
        "review_case_activities",
        ["snapshot_revision_id"],
        unique=False,
    )
    op.create_index(
        "ix_review_case_activities_activity_type",
        "review_case_activities",
        ["activity_type"],
        unique=False,
    )
    op.create_index(
        "ix_review_case_activities_created_at",
        "review_case_activities",
        ["created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_table("review_case_activities")
    op.drop_table("review_evidence_annotations")
    op.drop_table("review_decisions")
    op.drop_table("review_decision_drafts")
    op.drop_table("review_case_snapshot_revisions")
    op.drop_table("review_cases")
