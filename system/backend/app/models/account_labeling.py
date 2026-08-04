"""Persistence models for account-detection active learning."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Float, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.mysql import Base

__all__ = [
    "AccountDetectionCaseRecord",
    "AccountLabelBatch",
    "AccountLabelBatchItem",
    "AccountBehaviorLabelRecord",
    "AccountDetectionDatasetVersion",
    "AccountDetectionModelActivation",
    "AccountDetectionModelApproval",
    "AccountDetectionModelVersion",
]


class AccountDetectionCaseRecord(Base):
    """Account-level case built from Chinese social-media posts."""

    __tablename__ = "account_detection_cases"
    __table_args__ = (
        UniqueConstraint("case_id", name="uq_account_detection_cases_case_id"),
        UniqueConstraint("case_fingerprint", name="uq_account_detection_cases_fingerprint"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    case_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    account_id: Mapped[str] = mapped_column(String(192), nullable=False, index=True)
    platform: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    event_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    author_name: Mapped[str] = mapped_column(String(256), nullable=False, default="")
    case_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    post_ids_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    evidence_post_ids_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    payload_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    model_output_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    label_status: Mapped[str] = mapped_column(String(32), nullable=False, default="unlabeled", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())


class AccountLabelBatch(Base):
    """One active-learning batch for analyst account labeling."""

    __tablename__ = "account_label_batches"
    __table_args__ = (UniqueConstraint("batch_id", name="uq_account_label_batches_batch_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    batch_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    strategy: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="open", index=True)
    budget: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    scope_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    selection_manifest_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    created_by: Mapped[int] = mapped_column(Integer, nullable=False, default=0, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class AccountLabelBatchItem(Base):
    """Selected case inside an account-labeling batch."""

    __tablename__ = "account_label_batch_items"
    __table_args__ = (
        UniqueConstraint("batch_id", "case_id", name="uq_account_label_batch_items_batch_case"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    batch_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    case_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    account_id: Mapped[str] = mapped_column(String(192), nullable=False, index=True)
    platform: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    event_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    priority_rank: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    selection_bucket: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    acquisition_scores_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="queued", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class AccountBehaviorLabelRecord(Base):
    """Human-submitted or adjudicated observable behavior label."""

    __tablename__ = "account_behavior_labels"
    __table_args__ = (UniqueConstraint("label_id", name="uq_account_behavior_labels_label_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    label_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    case_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    batch_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    behavior_label: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    training_target: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    label_status: Mapped[str] = mapped_column(String(32), nullable=False, default="submitted", index=True)
    analyst_id: Mapped[int] = mapped_column(Integer, nullable=False, default=0, index=True)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.5)
    evidence_post_ids_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    reason_tags_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    notes: Mapped[str] = mapped_column(Text, nullable=False, default="")
    case_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False, default="", index=True)
    adjudicated_by: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    adjudicated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class AccountDetectionDatasetVersion(Base):
    """Approved-label corpus exported for account-model training."""

    __tablename__ = "account_detection_dataset_versions"
    __table_args__ = (
        UniqueConstraint("dataset_version_id", name="uq_account_detection_dataset_versions_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    dataset_version_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    data_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    source_label_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    artifact_uri: Mapped[str] = mapped_column(Text, nullable=False, default="")
    manifest_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="candidate", index=True)
    created_by: Mapped[int] = mapped_column(Integer, nullable=False, default=0, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class AccountDetectionModelVersion(Base):
    """Candidate account-detection model produced from an approved dataset."""

    __tablename__ = "account_detection_model_versions"
    __table_args__ = (
        UniqueConstraint("model_version", name="uq_account_detection_model_versions_version"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    model_version: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    dataset_version_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    artifact_hash: Mapped[str] = mapped_column(String(128), nullable=False, default="", index=True)
    artifact_uri: Mapped[str] = mapped_column(Text, nullable=False, default="")
    metrics_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    gates_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="shadow", index=True)
    created_by: Mapped[int] = mapped_column(Integer, nullable=False, default=0, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class AccountDetectionModelApproval(Base):
    """Immutable administrator approval for an account model candidate."""

    __tablename__ = "account_detection_model_approvals"
    __table_args__ = (
        UniqueConstraint(
            "model_version",
            "approver_id",
            name="uq_account_detection_model_approvals_version_approver",
        ),
        UniqueConstraint("approval_id", name="uq_account_detection_model_approvals_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    approval_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    model_version: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    approver_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    artifact_hash: Mapped[str] = mapped_column(String(128), nullable=False, default="", index=True)
    metrics_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False, default="", index=True)
    approval_notes: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class AccountDetectionModelActivation(Base):
    """Active account-detection model pointer."""

    __tablename__ = "account_detection_model_activations"
    __table_args__ = (
        UniqueConstraint("model_family", name="uq_account_detection_model_activations_family"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    model_family: Mapped[str] = mapped_column(String(64), nullable=False, default="chinese_account_detection")
    model_version: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    activation_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    activated_by: Mapped[int] = mapped_column(Integer, nullable=False, default=0, index=True)
    activated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
