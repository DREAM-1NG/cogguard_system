from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.mysql import Base


class CaseRecord(Base):
    __tablename__ = "case_records"
    __table_args__ = (UniqueConstraint("case_id"), UniqueConstraint("event_id"))
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    case_id: Mapped[str] = mapped_column(String(128), nullable=False)
    event_id: Mapped[str] = mapped_column(String(128), nullable=False)
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    lifecycle: Mapped[str] = mapped_column(String(32), nullable=False, default="draft", index=True)
    canonical_verdict_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    canonical_approved: Mapped[bool] = mapped_column(default=False, nullable=False)
    closure_note: Mapped[str] = mapped_column(Text, nullable=False, default="")
    closure_report_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_by: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)


class AuthoritySource(Base):
    __tablename__ = "authority_sources"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_id: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(512), nullable=False)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    review_status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending_review")
    tier: Mapped[str | None] = mapped_column(String(64), nullable=True)
    reviewed_by: Mapped[int | None] = mapped_column(Integer, nullable=True)


class CaseClaim(Base):
    __tablename__ = "case_claims"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    claim_id: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    case_id: Mapped[str] = mapped_column(String(128), ForeignKey("case_records.case_id"), nullable=False, index=True)
    authority_source_id: Mapped[str] = mapped_column(String(128), nullable=False)
    exact_quote: Mapped[str] = mapped_column(Text, nullable=False)
    quote_start: Mapped[int] = mapped_column(Integer, nullable=False)
    quote_end: Mapped[int] = mapped_column(Integer, nullable=False)
    source_url: Mapped[str] = mapped_column(Text, nullable=False)
    account: Mapped[str] = mapped_column(String(256), nullable=False)
    published_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    role: Mapped[str] = mapped_column(String(16), nullable=False)
    source_tier_snapshot: Mapped[str | None] = mapped_column(String(64), nullable=True)
    source_review_snapshot: Mapped[str] = mapped_column(String(32), nullable=False)
    content_sha256: Mapped[str] = mapped_column(String(64), nullable=False)


class CaseAnalysisLink(Base):
    __tablename__ = "case_analysis_links"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    link_id: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    case_id: Mapped[str] = mapped_column(String(128), ForeignKey("case_records.case_id"), nullable=False)
    snapshot_or_run_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    stages_json: Mapped[str] = mapped_column(Text, nullable=False)
    blockers_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")


class SemanticArtifact(Base):
    __tablename__ = "semantic_artifacts"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    artifact_id: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    case_id: Mapped[str] = mapped_column(String(128), nullable=False)
    artifact_type: Mapped[str] = mapped_column(String(128), nullable=False)
    payload_json: Mapped[str] = mapped_column(Text, nullable=False)
    model_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    model_revision: Mapped[str | None] = mapped_column(String(128), nullable=True)
    validation_status: Mapped[str] = mapped_column(String(32), nullable=False, default="unvalidated")
    scope_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    input_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    output_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)


class SemanticCorrection(Base):
    __tablename__ = "semantic_corrections"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    correction_id: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    case_id: Mapped[str] = mapped_column(String(128), nullable=False)
    artifact_id: Mapped[str] = mapped_column(String(128), nullable=False)
    original_payload_json: Mapped[str] = mapped_column(Text, nullable=False)
    corrected_payload_json: Mapped[str] = mapped_column(Text, nullable=False)


class CaseAction(Base):
    __tablename__ = "case_actions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    action_id: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    case_id: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    required: Mapped[bool] = mapped_column(default=False, nullable=False)
    state: Mapped[str] = mapped_column(String(16), default="pending", nullable=False)
    waiver_reason: Mapped[str] = mapped_column(Text, default="", nullable=False)


class CaseFeedback(Base):
    __tablename__ = "case_feedback"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    feedback_id: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    case_id: Mapped[str] = mapped_column(String(128), nullable=False)
    payload_json: Mapped[str] = mapped_column(Text, nullable=False)


class CaseReportVersion(Base):
    __tablename__ = "case_report_versions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    report_id: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    case_id: Mapped[str] = mapped_column(String(128), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    manifest_json: Mapped[str] = mapped_column(Text, nullable=False)
    html: Mapped[str] = mapped_column(Text, nullable=False)
    manifest_sha256: Mapped[str] = mapped_column(String(64), nullable=False)


class CaseAuditEvent(Base):
    __tablename__ = "case_audit_events"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    case_id: Mapped[str] = mapped_column(String(128), nullable=False)
    event_type: Mapped[str] = mapped_column(String(128), nullable=False)
    payload_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")


__all__ = ["CaseRecord", "AuthoritySource", "CaseClaim", "CaseAnalysisLink", "SemanticArtifact", "SemanticCorrection", "CaseAction", "CaseFeedback", "CaseReportVersion", "CaseAuditEvent"]
