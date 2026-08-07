"""Persistence models for account-detection active learning."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, Float, Index, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.mysql import Base

__all__ = [
    "AccountBehaviorLabelRecord",
    "AccountCorpusVersion",
    "ChineseSocialEncoderVersion",
    "AccountDetectionCaseRecord",
    "AccountDetectionDatasetVersion",
    "AccountDetectionModelActivation",
    "AccountDetectionModelApproval",
    "AccountDetectionModelVersion",
    "AccountFrozenHoldoutMembership",
    "AccountLabelBatch",
    "AccountLabelBatchItem",
    "AccountLabelReviewAssignment",
    "AccountModelGovernanceDecision",
    "AccountModelEvaluationJob",
    "AccountModelEvaluationRun",
    "AccountModelTrainingDispatchOutbox",
    "AccountModelTrainingEvent",
    "AccountModelTrainingRun",
    "AccountTrainingExportMembership",
    "AccountMonitorSnapshot",
    "AccountPredictionAudit",
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
    """Append-only observable behavior label revision."""

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
    supersedes_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    review_required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    second_review_status: Mapped[str] = mapped_column(String(32), nullable=False, default="not_required")
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


class AccountTrainingExportMembership(Base):
    """Append-only lineage for one label/case emitted in a training dataset export."""

    __tablename__ = "account_training_export_memberships"
    __table_args__ = (
        UniqueConstraint("export_membership_id", name="uq_account_training_export_memberships_id"),
        UniqueConstraint(
            "dataset_version_id",
            "case_id",
            "label_id",
            "case_fingerprint",
            name="uq_account_training_export_memberships_dataset_case_label",
        ),
        Index(
            "ix_account_training_export_memberships_lookup",
            "case_id",
            "label_id",
            "case_fingerprint",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    export_membership_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    dataset_version_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    case_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    label_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    case_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    export_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    exported_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())


class AccountDetectionModelVersion(Base):
    """Candidate account-detection model produced from an approved dataset."""

    __tablename__ = "account_detection_model_versions"
    __table_args__ = (
        UniqueConstraint("model_version", name="uq_account_detection_model_versions_version"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    model_version: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    dataset_version_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    encoder_version: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    encoder_artifact_hash: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
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
    pointer_revision: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    activation_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    activated_by: Mapped[int] = mapped_column(Integer, nullable=False, default=0, index=True)
    activated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class AccountCorpusVersion(Base):
    """Immutable source-label corpus manifest for account model training."""

    __tablename__ = "account_corpus_versions"
    __table_args__ = (UniqueConstraint("corpus_version_id", name="uq_account_corpus_versions_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    corpus_version_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    input_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    source_label_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    manifest_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="candidate", index=True)
    created_by: Mapped[int] = mapped_column(Integer, nullable=False, default=0, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class ChineseSocialEncoderVersion(Base):
    """Immutable portable Chinese social encoder produced by one DAPT run."""

    __tablename__ = "chinese_social_encoder_versions"
    __table_args__ = (
        UniqueConstraint("encoder_version", name="uq_chinese_social_encoder_versions_version"),
        UniqueConstraint("training_run_id", name="uq_chinese_social_encoder_versions_training_run"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    encoder_version: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    corpus_version_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    training_run_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    artifact_uri: Mapped[str] = mapped_column(Text, nullable=False)
    artifact_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    base_model_identity: Mapped[str] = mapped_column(Text, nullable=False)
    manifest_json: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="completed", index=True)
    created_by: Mapped[int] = mapped_column(Integer, nullable=False, default=0, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class AccountLabelReviewAssignment(Base):
    """Append-only assignment of a label revision to an independent reviewer."""

    __tablename__ = "account_label_review_assignments"
    __table_args__ = (UniqueConstraint("assignment_id", name="uq_account_label_review_assignments_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    assignment_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    label_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    reviewer_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    review_round: Mapped[int] = mapped_column(Integer, nullable=False, default=2)
    review_status: Mapped[str] = mapped_column(String(32), nullable=False, default="assigned", index=True)
    assignment_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    assigned_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class AccountFrozenHoldoutMembership(Base):
    """Immutable frozen-holdout membership for one corpus version and case."""

    __tablename__ = "account_frozen_holdout_memberships"
    __table_args__ = (
        UniqueConstraint("membership_id", name="uq_account_frozen_holdout_memberships_id"),
        UniqueConstraint("corpus_version_id", "case_id", name="uq_account_frozen_holdout_memberships_corpus_case"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    membership_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    corpus_version_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    account_id: Mapped[str | None] = mapped_column(String(192), nullable=True, index=True)
    case_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    label_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    stratum_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    frozen_by: Mapped[int] = mapped_column(Integer, nullable=False, default=0, index=True)
    frozen_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class AccountModelTrainingRun(Base):
    """Resumable account-model training lifecycle state."""

    __tablename__ = "account_model_training_runs"
    __table_args__ = (
        UniqueConstraint("run_id", name="uq_account_model_training_runs_id"),
        CheckConstraint(
            "status IN ('queued', 'preparing', 'running', 'evaluating', 'completed', "
            "'failed', 'cancelled', 'interrupted')",
            name="ck_account_model_training_runs_status",
        ),
        CheckConstraint("attempt >= 1", name="ck_account_model_training_runs_attempt_positive"),
        CheckConstraint("max_attempts >= 1", name="ck_account_model_training_runs_max_attempts_positive"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    family: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="queued", index=True,
        comment="queued/preparing/running/evaluating/completed/failed/cancelled/interrupted",
    )
    stage: Mapped[str] = mapped_column(String(64), nullable=False, default="queued", index=True)
    corpus_version_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    input_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    config_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    config_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    attempt: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    resume_checkpoint_uri: Mapped[str | None] = mapped_column(Text, nullable=True)
    cancel_requested_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    cancelled_by: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[int] = mapped_column(Integer, nullable=False, default=0, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())


class AccountModelTrainingEvent(Base):
    """Append-only event stream for account-model training runs."""

    __tablename__ = "account_model_training_events"
    __table_args__ = (UniqueConstraint("event_id", name="uq_account_model_training_events_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    run_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="", index=True)
    stage: Mapped[str] = mapped_column(String(64), nullable=False, default="", index=True)
    payload_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class AccountModelTrainingDispatchOutbox(Base):
    """Durable Celery dispatch intent for one account-training attempt."""

    __tablename__ = "account_model_training_dispatch_outbox"
    __table_args__ = (
        UniqueConstraint("dispatch_id", name="uq_account_training_dispatch_outbox_id"),
        UniqueConstraint("run_id", "attempt", name="uq_account_training_dispatch_outbox_run_attempt"),
        UniqueConstraint("task_id", name="uq_account_training_dispatch_outbox_task_id"),
        Index("ix_account_training_dispatch_outbox_pending", "status", "available_at"),
        Index("ix_account_training_dispatch_outbox_claim_lease", "status", "available_at", "lease_expires_at"),
        CheckConstraint(
            "status IN ('pending', 'publishing', 'published', 'superseded')",
            name="ck_account_training_dispatch_outbox_status",
        ),
        CheckConstraint("attempt >= 1", name="ck_account_training_dispatch_outbox_attempt_positive"),
        CheckConstraint("publish_attempts >= 0", name="ck_account_training_dispatch_outbox_publish_attempts_nonnegative"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    dispatch_id: Mapped[str] = mapped_column(String(192), nullable=False, index=True)
    run_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    attempt: Mapped[int] = mapped_column(Integer, nullable=False)
    task_id: Mapped[str] = mapped_column(String(192), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending", index=True)
    claim_token: Mapped[str | None] = mapped_column(String(64), nullable=True)
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)
    publish_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    available_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now(), index=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class AccountModelGovernanceDecision(Base):
    """Append-only activation, rollback, or retirement decision history."""

    __tablename__ = "account_model_governance_decisions"
    __table_args__ = (UniqueConstraint("decision_id", name="uq_account_model_governance_decisions_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    decision_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    family: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    model_version: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    previous_model_version: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    pointer_revision: Mapped[int] = mapped_column(Integer, nullable=False)
    decision_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    decision_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    decided_by: Mapped[int] = mapped_column(Integer, nullable=False, default=0, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class AccountModelEvaluationRun(Base):
    """Immutable signed evaluator evidence for one candidate evaluation run."""

    __tablename__ = "account_model_evaluation_runs"
    __table_args__ = (
        UniqueConstraint("evaluation_run_id", name="uq_account_model_evaluation_runs_run_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    evaluation_run_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    family: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    model_version: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    artifact_hash: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    evaluation_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    audit_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    manifest_json: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class AccountModelEvaluationJob(Base):
    """Durable system-owned evaluation work for one immutable candidate/holdout pair."""

    __tablename__ = "account_model_evaluation_jobs"
    __table_args__ = (
        UniqueConstraint("job_id", name="uq_account_model_evaluation_jobs_id"),
        UniqueConstraint("task_id", name="uq_account_model_evaluation_jobs_task_id"),
        UniqueConstraint(
            "model_version",
            "artifact_hash",
            "corpus_version_id",
            "holdout_fingerprint",
            "config_fingerprint",
            name="uq_account_model_evaluation_jobs_identity",
        ),
        CheckConstraint(
            "status IN ('queued', 'running', 'completed', 'failed', 'cancelled')",
            name="ck_account_model_evaluation_jobs_status",
        ),
        Index("ix_account_model_evaluation_jobs_status_created", "status", "created_at"),
        Index("ix_account_model_evaluation_jobs_candidate", "model_version", "artifact_hash"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    job_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    model_version: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    artifact_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    corpus_version_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    holdout_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    config_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    evaluator_config_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="queued", index=True)
    task_id: Mapped[str] = mapped_column(String(192), nullable=False, index=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    operator_id: Mapped[int] = mapped_column(Integer, nullable=False, default=0, index=True)
    completed_evaluation_run_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class AccountPredictionAudit(Base):
    """Append-only model prediction evidence tied to an activation revision."""

    __tablename__ = "account_prediction_audits"
    __table_args__ = (UniqueConstraint("audit_id", name="uq_account_prediction_audits_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    audit_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    case_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    account_id: Mapped[str] = mapped_column(String(192), nullable=False, index=True)
    platform: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    family: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    model_version: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    pointer_revision: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    input_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    prediction_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class AccountMonitorSnapshot(Base):
    """Append-only monitoring aggregate for an account-model activation revision."""

    __tablename__ = "account_monitor_snapshots"
    __table_args__ = (UniqueConstraint("snapshot_id", name="uq_account_monitor_snapshots_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    snapshot_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    family: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    model_version: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    pointer_revision: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    window_started_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    window_finished_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="healthy", index=True)
    metrics_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
