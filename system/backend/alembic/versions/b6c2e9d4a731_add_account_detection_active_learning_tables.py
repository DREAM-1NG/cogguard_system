"""add account detection active-learning governance tables

Revision ID: b6c2e9d4a731
Revises: a2d8e5c1b904
Create Date: 2026-08-04 10:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "b6c2e9d4a731"
down_revision: Union[str, Sequence[str], None] = "a2d8e5c1b904"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "account_detection_cases",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("case_id", sa.String(length=128), nullable=False),
        sa.Column("account_id", sa.String(length=192), nullable=False),
        sa.Column("platform", sa.String(length=32), nullable=False),
        sa.Column("event_id", sa.String(length=128), nullable=False),
        sa.Column("author_name", sa.String(length=256), nullable=False),
        sa.Column("case_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("post_ids_json", sa.Text(), nullable=False),
        sa.Column("evidence_post_ids_json", sa.Text(), nullable=False),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.Column("model_output_json", sa.Text(), nullable=False),
        sa.Column("label_status", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=True),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("case_id", name="uq_account_detection_cases_case_id"),
        sa.UniqueConstraint("case_fingerprint", name="uq_account_detection_cases_fingerprint"),
    )
    _index("account_detection_cases", "case_id")
    _index("account_detection_cases", "account_id")
    _index("account_detection_cases", "platform")
    _index("account_detection_cases", "event_id")
    _index("account_detection_cases", "case_fingerprint")
    _index("account_detection_cases", "label_status")

    op.create_table(
        "account_label_batches",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("batch_id", sa.String(length=128), nullable=False),
        sa.Column("strategy", sa.String(length=128), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("budget", sa.Integer(), nullable=False),
        sa.Column("scope_json", sa.Text(), nullable=False),
        sa.Column("selection_manifest_json", sa.Text(), nullable=False),
        sa.Column("created_by", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("batch_id", name="uq_account_label_batches_batch_id"),
    )
    _index("account_label_batches", "batch_id")
    _index("account_label_batches", "status")
    _index("account_label_batches", "created_by")

    op.create_table(
        "account_label_batch_items",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("batch_id", sa.String(length=128), nullable=False),
        sa.Column("case_id", sa.String(length=128), nullable=False),
        sa.Column("account_id", sa.String(length=192), nullable=False),
        sa.Column("platform", sa.String(length=32), nullable=False),
        sa.Column("event_id", sa.String(length=128), nullable=False),
        sa.Column("priority_rank", sa.Integer(), nullable=False),
        sa.Column("selection_bucket", sa.String(length=64), nullable=False),
        sa.Column("acquisition_scores_json", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("batch_id", "case_id", name="uq_account_label_batch_items_batch_case"),
    )
    _index("account_label_batch_items", "batch_id")
    _index("account_label_batch_items", "case_id")
    _index("account_label_batch_items", "account_id")
    _index("account_label_batch_items", "platform")
    _index("account_label_batch_items", "event_id")
    _index("account_label_batch_items", "status")

    op.create_table(
        "account_behavior_labels",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("label_id", sa.String(length=128), nullable=False),
        sa.Column("case_id", sa.String(length=128), nullable=False),
        sa.Column("batch_id", sa.String(length=128), nullable=True),
        sa.Column("behavior_label", sa.String(length=64), nullable=False),
        sa.Column("training_target", sa.String(length=32), nullable=False),
        sa.Column("label_status", sa.String(length=32), nullable=False),
        sa.Column("analyst_id", sa.Integer(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("evidence_post_ids_json", sa.Text(), nullable=False),
        sa.Column("reason_tags_json", sa.Text(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=False),
        sa.Column("case_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("adjudicated_by", sa.Integer(), nullable=True),
        sa.Column("adjudicated_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("label_id", name="uq_account_behavior_labels_label_id"),
    )
    _index("account_behavior_labels", "label_id")
    _index("account_behavior_labels", "case_id")
    _index("account_behavior_labels", "batch_id")
    _index("account_behavior_labels", "behavior_label")
    _index("account_behavior_labels", "training_target")
    _index("account_behavior_labels", "label_status")
    _index("account_behavior_labels", "analyst_id")
    _index("account_behavior_labels", "case_fingerprint")
    _index("account_behavior_labels", "adjudicated_by")

    op.create_table(
        "account_detection_dataset_versions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("dataset_version_id", sa.String(length=128), nullable=False),
        sa.Column("data_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("source_label_count", sa.Integer(), nullable=False),
        sa.Column("artifact_uri", sa.Text(), nullable=False),
        sa.Column("manifest_json", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("created_by", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "dataset_version_id",
            name="uq_account_detection_dataset_versions_id",
        ),
    )
    _index("account_detection_dataset_versions", "dataset_version_id")
    _index("account_detection_dataset_versions", "data_fingerprint")
    _index("account_detection_dataset_versions", "status")
    _index("account_detection_dataset_versions", "created_by")

    op.create_table(
        "account_detection_model_versions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("model_version", sa.String(length=128), nullable=False),
        sa.Column("dataset_version_id", sa.String(length=128), nullable=False),
        sa.Column("artifact_hash", sa.String(length=128), nullable=False),
        sa.Column("artifact_uri", sa.Text(), nullable=False),
        sa.Column("metrics_json", sa.Text(), nullable=False),
        sa.Column("gates_json", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("created_by", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "model_version",
            name="uq_account_detection_model_versions_version",
        ),
    )
    _index("account_detection_model_versions", "model_version")
    _index("account_detection_model_versions", "dataset_version_id")
    _index("account_detection_model_versions", "artifact_hash")
    _index("account_detection_model_versions", "status")
    _index("account_detection_model_versions", "created_by")

    op.create_table(
        "account_detection_model_approvals",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("approval_id", sa.String(length=128), nullable=False),
        sa.Column("model_version", sa.String(length=128), nullable=False),
        sa.Column("approver_id", sa.Integer(), nullable=False),
        sa.Column("artifact_hash", sa.String(length=128), nullable=False),
        sa.Column("metrics_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("approval_notes", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("approval_id", name="uq_account_detection_model_approvals_id"),
        sa.UniqueConstraint(
            "model_version",
            "approver_id",
            name="uq_account_detection_model_approvals_version_approver",
        ),
    )
    _index("account_detection_model_approvals", "approval_id")
    _index("account_detection_model_approvals", "model_version")
    _index("account_detection_model_approvals", "approver_id")
    _index("account_detection_model_approvals", "artifact_hash")
    _index("account_detection_model_approvals", "metrics_fingerprint")

    op.create_table(
        "account_detection_model_activations",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column(
            "model_family",
            sa.String(length=64),
            nullable=False,
            server_default="chinese_account_detection",
        ),
        sa.Column("model_version", sa.String(length=128), nullable=False),
        sa.Column("activation_json", sa.Text(), nullable=False),
        sa.Column("activated_by", sa.Integer(), nullable=False),
        sa.Column("activated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "model_family",
            name="uq_account_detection_model_activations_family",
        ),
    )
    _index("account_detection_model_activations", "model_version")


def downgrade() -> None:
    op.drop_index("ix_account_detection_model_activations_model_version", table_name="account_detection_model_activations")
    op.drop_table("account_detection_model_activations")

    for column in reversed(("approval_id", "model_version", "approver_id", "artifact_hash", "metrics_fingerprint")):
        op.drop_index(f"ix_account_detection_model_approvals_{column}", table_name="account_detection_model_approvals")
    op.drop_table("account_detection_model_approvals")

    for column in reversed(("model_version", "dataset_version_id", "artifact_hash", "status", "created_by")):
        op.drop_index(f"ix_account_detection_model_versions_{column}", table_name="account_detection_model_versions")
    op.drop_table("account_detection_model_versions")

    for column in reversed(("dataset_version_id", "data_fingerprint", "status", "created_by")):
        op.drop_index(
            f"ix_account_detection_dataset_versions_{column}",
            table_name="account_detection_dataset_versions",
        )
    op.drop_table("account_detection_dataset_versions")

    for column in reversed(
        (
            "label_id",
            "case_id",
            "batch_id",
            "behavior_label",
            "training_target",
            "label_status",
            "analyst_id",
            "case_fingerprint",
            "adjudicated_by",
        )
    ):
        op.drop_index(f"ix_account_behavior_labels_{column}", table_name="account_behavior_labels")
    op.drop_table("account_behavior_labels")

    for column in reversed(("batch_id", "case_id", "account_id", "platform", "event_id", "status")):
        op.drop_index(f"ix_account_label_batch_items_{column}", table_name="account_label_batch_items")
    op.drop_table("account_label_batch_items")

    for column in reversed(("batch_id", "status", "created_by")):
        op.drop_index(f"ix_account_label_batches_{column}", table_name="account_label_batches")
    op.drop_table("account_label_batches")

    for column in reversed(("case_id", "account_id", "platform", "event_id", "case_fingerprint", "label_status")):
        op.drop_index(f"ix_account_detection_cases_{column}", table_name="account_detection_cases")
    op.drop_table("account_detection_cases")


def _index(table_name: str, column_name: str) -> None:
    op.create_index(f"ix_{table_name}_{column_name}", table_name, [column_name], unique=False)
