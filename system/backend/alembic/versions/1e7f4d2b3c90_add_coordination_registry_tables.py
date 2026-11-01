"""add_coordination_registry_tables

Revision ID: 1e7f4d2b3c90
Revises: 8107cf7ab249
Create Date: 2026-07-02 18:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "1e7f4d2b3c90"
down_revision: Union[str, None] = "8107cf7ab249"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "coordination_datasets",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("slug", sa.String(length=128), nullable=False),
        sa.Column("display_name", sa.String(length=128), nullable=False),
        sa.Column("source_type", sa.String(length=32), nullable=False, comment="system_archive/uploaded"),
        sa.Column("source_format", sa.String(length=16), nullable=False, comment="csv/jsonl"),
        sa.Column("source_path", sa.Text(), nullable=False),
        sa.Column("metadata_json", sa.Text(), nullable=False),
        sa.Column("has_labels", sa.Boolean(), nullable=False),
        sa.Column("event_rows", sa.Integer(), nullable=False),
        sa.Column("account_nodes", sa.Integer(), nullable=False),
        sa.Column("object_ids", sa.Integer(), nullable=False),
        sa.Column("user_user_edges", sa.Integer(), nullable=False),
        sa.Column("available_relations", sa.Text(), nullable=False),
        sa.Column("latest_run_id", sa.Integer(), nullable=True),
        sa.Column("created_by", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_coordination_datasets_slug"), "coordination_datasets", ["slug"], unique=True)

    op.create_table(
        "coordination_runs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("dataset_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False, comment="pending/running/completed/failed"),
        sa.Column("progress", sa.Integer(), nullable=False),
        sa.Column("run_mode", sa.String(length=16), nullable=False, comment="archive/rerun"),
        sa.Column("discover_encoder", sa.String(length=32), nullable=False),
        sa.Column("community_algorithm", sa.String(length=32), nullable=False),
        sa.Column("lm_backend", sa.String(length=32), nullable=False),
        sa.Column("gnn_backend", sa.String(length=32), nullable=False),
        sa.Column(
            "label_mode",
            sa.String(length=32),
            nullable=False,
            comment="labeled_mainline/unlabeled_china_pretrained",
        ),
        sa.Column("artifact_dir", sa.Text(), nullable=False),
        sa.Column("metrics_json", sa.Text(), nullable=True),
        sa.Column("result_summary_json", sa.Text(), nullable=True),
        sa.Column("pretrained_weight_path", sa.Text(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_by", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_coordination_runs_dataset_id"), "coordination_runs", ["dataset_id"], unique=False)
    op.create_index(op.f("ix_coordination_runs_status"), "coordination_runs", ["status"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_coordination_runs_status"), table_name="coordination_runs")
    op.drop_index(op.f("ix_coordination_runs_dataset_id"), table_name="coordination_runs")
    op.drop_table("coordination_runs")
    op.drop_index(op.f("ix_coordination_datasets_slug"), table_name="coordination_datasets")
    op.drop_table("coordination_datasets")
