"""Persistence models for the event review case product boundary."""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.mysql import Base


class ReviewCase(Base):
    """One durable analyst-facing case per collected event."""

    __tablename__ = "review_cases"
    __table_args__ = (
        UniqueConstraint("case_id", name="uq_review_cases_case_id"),
        UniqueConstraint("event_id", name="uq_review_cases_event_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    case_id: Mapped[str] = mapped_column(String(128), nullable=False)
    event_id: Mapped[str] = mapped_column(String(128), nullable=False)
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    preliminary_conclusion: Mapped[str] = mapped_column(
        String(32), nullable=False, default="insufficient_evidence"
    )
    evidence_sufficiency: Mapped[str] = mapped_column(String(32), nullable=False, default="insufficient")
    urgency: Mapped[str] = mapped_column(String(32), nullable=False, default="routine")
    disposition: Mapped[str] = mapped_column(String(32), nullable=False, default="gather_evidence")
    action_required: Mapped[str] = mapped_column(
        String(32), nullable=False, default="add_evidence", index=True
    )
    preliminary_finding_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    business_summary_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    created_by: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    updated_by: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
        index=True,
    )


class ReviewCaseSnapshotRevision(Base):
    """Immutable link from a case revision to its analysis event snapshot."""

    __tablename__ = "review_case_snapshot_revisions"
    __table_args__ = (
        UniqueConstraint(
            "snapshot_revision_id",
            name="uq_review_case_snapshot_revisions_revision_id",
        ),
        UniqueConstraint(
            "case_id",
            "data_fingerprint",
            name="uq_review_case_snapshot_revisions_case_fingerprint",
        ),
        UniqueConstraint(
            "case_id",
            "revision_number",
            name="uq_review_case_snapshot_revisions_case_revision",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    snapshot_revision_id: Mapped[str] = mapped_column(String(128), nullable=False)
    case_id: Mapped[str] = mapped_column(
        String(128),
        ForeignKey("review_cases.case_id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    snapshot_id: Mapped[str] = mapped_column(
        String(128),
        ForeignKey("analysis_event_snapshots.snapshot_id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    data_fingerprint: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    revision_number: Mapped[int] = mapped_column(Integer, nullable=False)
    core_window_start: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    core_window_end: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    context_window_start: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    context_window_end: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    quality_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    provenance_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    analysis_run_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    teacher_run_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    teacher_verdict_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    analysis_completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_by: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())


class ReviewDecisionDraft(Base):
    """Mutable autosave document with optimistic concurrency control."""

    __tablename__ = "review_decision_drafts"
    __table_args__ = (UniqueConstraint("case_id", name="uq_review_decision_drafts_case_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    case_id: Mapped[str] = mapped_column(
        String(128),
        ForeignKey("review_cases.case_id", ondelete="CASCADE"),
        nullable=False,
    )
    snapshot_revision_id: Mapped[str] = mapped_column(
        String(128),
        ForeignKey("review_case_snapshot_revisions.snapshot_revision_id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    conclusion: Mapped[str] = mapped_column(String(32), nullable=False)
    urgency: Mapped[str] = mapped_column(String(32), nullable=False)
    disposition: Mapped[str] = mapped_column(String(32), nullable=False)
    rationale: Mapped[str] = mapped_column(Text, nullable=False)
    key_evidence_refs_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    unresolved_items_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    created_by: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    updated_by: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class ReviewDecision(Base):
    """Append-only confirmed decision; corrections create a later version."""

    __tablename__ = "review_decisions"
    __table_args__ = (
        UniqueConstraint("decision_id", name="uq_review_decisions_decision_id"),
        UniqueConstraint("case_id", "version", name="uq_review_decisions_case_version"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    decision_id: Mapped[str] = mapped_column(String(128), nullable=False)
    case_id: Mapped[str] = mapped_column(
        String(128),
        ForeignKey("review_cases.case_id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    snapshot_revision_id: Mapped[str] = mapped_column(
        String(128),
        ForeignKey("review_case_snapshot_revisions.snapshot_revision_id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    supersedes_decision_id: Mapped[str | None] = mapped_column(
        String(128),
        ForeignKey("review_decisions.decision_id", ondelete="RESTRICT"),
        nullable=True,
    )
    conclusion: Mapped[str] = mapped_column(String(32), nullable=False)
    urgency: Mapped[str] = mapped_column(String(32), nullable=False)
    disposition: Mapped[str] = mapped_column(String(32), nullable=False)
    rationale: Mapped[str] = mapped_column(Text, nullable=False)
    key_evidence_refs_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    unresolved_items_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    confirmation_note: Mapped[str] = mapped_column(Text, nullable=False, default="")
    confirmed_by: Mapped[int] = mapped_column(Integer, nullable=False)
    confirmed_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    created_by: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())


class EvidenceAnnotation(Base):
    """Append-only analyst assessment attached to immutable source evidence."""

    __tablename__ = "review_evidence_annotations"
    __table_args__ = (
        UniqueConstraint("annotation_id", name="uq_review_evidence_annotations_annotation_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    annotation_id: Mapped[str] = mapped_column(String(128), nullable=False)
    case_id: Mapped[str] = mapped_column(
        String(128),
        ForeignKey("review_cases.case_id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    snapshot_revision_id: Mapped[str] = mapped_column(
        String(128),
        ForeignKey("review_case_snapshot_revisions.snapshot_revision_id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    evidence_ref: Mapped[str] = mapped_column(String(512), nullable=False, index=True)
    assessment: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    note: Mapped[str] = mapped_column(Text, nullable=False)
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())


class CaseActivity(Base):
    """Append-only business activity; the primary key is also the SSE cursor."""

    __tablename__ = "review_case_activities"
    __table_args__ = (
        UniqueConstraint(
            "case_id",
            "activity_type",
            "source_ref",
            name="uq_review_case_activities_case_type_source",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    case_id: Mapped[str] = mapped_column(
        String(128),
        ForeignKey("review_cases.case_id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    snapshot_revision_id: Mapped[str | None] = mapped_column(
        String(128),
        ForeignKey("review_case_snapshot_revisions.snapshot_revision_id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    activity_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    action_required: Mapped[str] = mapped_column(String(32), nullable=False, default="none")
    source_ref: Mapped[str | None] = mapped_column(String(128), nullable=True)
    summary: Mapped[str] = mapped_column(String(1000), nullable=False)
    detail_lines_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    evidence_refs_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    actor_name: Mapped[str] = mapped_column(String(128), nullable=False, default="系统")
    created_by: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.now(),
        index=True,
    )


__all__ = [
    "CaseActivity",
    "EvidenceAnnotation",
    "ReviewCase",
    "ReviewCaseSnapshotRevision",
    "ReviewDecision",
    "ReviewDecisionDraft",
]
