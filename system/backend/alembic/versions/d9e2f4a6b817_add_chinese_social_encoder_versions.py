"""add immutable Chinese social encoder versions

Revision ID: d9e2f4a6b817
Revises: c3a7e5d8f914
Create Date: 2026-08-07 12:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "d9e2f4a6b817"
down_revision: Union[str, Sequence[str], None] = "c3a7e5d8f914"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "chinese_social_encoder_versions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("encoder_version", sa.String(length=128), nullable=False),
        sa.Column("corpus_version_id", sa.String(length=128), nullable=False),
        sa.Column("training_run_id", sa.String(length=128), nullable=False),
        sa.Column("artifact_uri", sa.Text(), nullable=False),
        sa.Column("artifact_hash", sa.String(length=64), nullable=False),
        sa.Column("base_model_identity", sa.Text(), nullable=False),
        sa.Column("manifest_json", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="completed"),
        sa.Column("created_by", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("encoder_version", name="uq_chinese_social_encoder_versions_version"),
        sa.UniqueConstraint("training_run_id", name="uq_chinese_social_encoder_versions_training_run"),
    )
    for column in (
        "encoder_version",
        "corpus_version_id",
        "training_run_id",
        "artifact_hash",
        "status",
        "created_by",
    ):
        op.create_index(f"ix_chinese_social_encoder_versions_{column}", "chinese_social_encoder_versions", [column])

    op.add_column(
        "account_detection_model_versions",
        sa.Column("encoder_version", sa.String(length=128), nullable=True),
    )
    op.add_column(
        "account_detection_model_versions",
        sa.Column("encoder_artifact_hash", sa.String(length=64), nullable=True),
    )
    op.create_index(
        "ix_account_detection_model_versions_encoder_version",
        "account_detection_model_versions",
        ["encoder_version"],
    )
    op.create_index(
        "ix_account_detection_model_versions_encoder_artifact_hash",
        "account_detection_model_versions",
        ["encoder_artifact_hash"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_account_detection_model_versions_encoder_artifact_hash",
        table_name="account_detection_model_versions",
    )
    op.drop_index(
        "ix_account_detection_model_versions_encoder_version",
        table_name="account_detection_model_versions",
    )
    op.drop_column("account_detection_model_versions", "encoder_artifact_hash")
    op.drop_column("account_detection_model_versions", "encoder_version")

    for column in reversed(
        (
            "encoder_version",
            "corpus_version_id",
            "training_run_id",
            "artifact_hash",
            "status",
            "created_by",
        )
    ):
        op.drop_index(f"ix_chinese_social_encoder_versions_{column}", table_name="chinese_social_encoder_versions")
    op.drop_table("chinese_social_encoder_versions")
