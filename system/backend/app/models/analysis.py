"""Unified analysis persistence models."""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.mysql import Base


class EventSnapshotRecord(Base):
    """Immutable event snapshot manifest used as analysis input."""

    __tablename__ = "analysis_event_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    snapshot_id: Mapped[str] = mapped_column(String(128), nullable=False, unique=True, index=True)
    event_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    data_fingerprint: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    mongo_collection: Mapped[str] = mapped_column(String(128), nullable=False)
    mongo_key: Mapped[str] = mapped_column(String(256), nullable=False)
    platforms_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    windows_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    quality_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    provenance_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    created_by: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class AnalysisRun(Base):
    """Analyst or system requested unified analysis run."""

    __tablename__ = "analysis_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(String(128), nullable=False, unique=True, index=True)
    event_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    snapshot_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="queued",
        index=True,
        comment="queued/running/needs_evidence/awaiting_review/completed/failed/cancelled",
    )
    requested_stages_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    options_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    result_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    artifact_manifest_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    celery_task_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    created_by: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class AnalysisRunEvent(Base):
    """Append-only run event stream; id is the SSE cursor."""

    __tablename__ = "analysis_run_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="")
    payload_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class AnalysisModelVersion(Base):
    """Versioned model artifact available to the analysis stack."""

    __tablename__ = "analysis_model_versions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    technology: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    model: Mapped[str] = mapped_column(String(128), nullable=False)
    version: Mapped[str] = mapped_column(String(64), nullable=False)
    artifact_hash: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    artifact_uri: Mapped[str] = mapped_column(Text, nullable=False)
    config_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    metrics_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="candidate", index=True)
    created_by: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class AnalysisModelActivationApproval(Base):
    """Immutable approval written by one authenticated model administrator."""

    __tablename__ = "analysis_model_activation_approvals"
    __table_args__ = (
        UniqueConstraint(
            "approval_id",
            name="uq_analysis_model_activation_approvals_approval_id",
        ),
        UniqueConstraint(
            "model_version_id",
            "approver_id",
            name="uq_analysis_model_activation_approvals_model_approver",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    approval_id: Mapped[str] = mapped_column(String(128), nullable=False)
    model_version_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    approver_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    approval_notes: Mapped[str] = mapped_column(Text, nullable=False, default="")
    immutable_source: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
        default="analysis.governance.model_approval.v1",
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class AnalysisModelActivation(Base):
    """One active model-version pointer per analysis technology."""

    __tablename__ = "analysis_model_activations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    technology: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    model_version_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    provenance_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    activated_by: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    activated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class PropagationMonitorProfile(Base):
    """Event-level configuration and most recent monitoring snapshot."""

    __tablename__ = "propagation_monitor_profiles"
    __table_args__ = (
        UniqueConstraint("event_id", "platform", name="uq_propagation_monitor_profiles_event_platform"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    platform: Mapped[str] = mapped_column(String(32), nullable=False, default="", index=True)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)
    interval_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    thresholds_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    last_snapshot_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    last_snapshot_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_by: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())


class PropagationAlert(Base):
    """A deduplicated, evidence-backed propagation monitoring alert."""

    __tablename__ = "propagation_alerts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    platform: Mapped[str] = mapped_column(String(32), nullable=False, default="", index=True)
    alert_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    severity: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    state: Mapped[str] = mapped_column(String(16), nullable=False, default="new", index=True)
    dedupe_key: Mapped[str] = mapped_column(String(320), nullable=False, index=True)
    trigger_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    first_triggered_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    last_triggered_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    snapshot_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    model_version_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    assigned_to: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    evidence_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
    closed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class PropagationAlertAction(Base):
    """Append-only analyst disposition audit record."""

    __tablename__ = "propagation_alert_actions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    alert_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    action: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    actor_id: Mapped[int] = mapped_column(Integer, nullable=False, default=0, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class AnalysisModelGovernanceDecision(Base):
    """Append-only activation or rollback decision history."""

    __tablename__ = "analysis_model_governance_decisions"
    __table_args__ = (
        UniqueConstraint(
            "decision_id",
            name="uq_analysis_model_governance_decisions_decision_id",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    decision_id: Mapped[str] = mapped_column(String(128), nullable=False)
    technology: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    model_version_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    previous_model_version_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    decision_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    decision_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    decided_by: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class ReviewVerdictVersion(Base):
    """Versioned review verdict with human approval and provenance fields."""

    __tablename__ = "analysis_review_verdict_versions"
    __table_args__ = (
        UniqueConstraint(
            "verdict_id",
            "version",
            name="uq_analysis_review_verdict_versions_verdict_version",
        ),
        UniqueConstraint(
            "canonical_source_id",
            name="uq_analysis_review_verdict_versions_canonical_source",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    verdict_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    run_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    snapshot_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    verdict_type: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        index=True,
        comment="preliminary/teacher_advisory/canonical",
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="draft", index=True)
    verdict_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    immutable_source: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    canonical_source_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    provenance_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    approved_by: Mapped[int | None] = mapped_column(Integer, nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    approval_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class ReviewFeedback(Base):
    """Analyst feedback attached to a run, snapshot, and optional verdict."""

    __tablename__ = "analysis_review_feedback"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    feedback_id: Mapped[str] = mapped_column(String(128), nullable=False, unique=True, index=True)
    run_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    verdict_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    snapshot_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    feedback_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    immutable_source: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    provenance_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    created_by: Mapped[int] = mapped_column(Integer, nullable=False, default=0, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
