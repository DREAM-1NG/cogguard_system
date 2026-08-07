"""Product-facing contracts for event review cases.

These contracts intentionally expose business findings and analyst actions only.
Runtime orchestration, model governance, and artifact provenance stay behind the
review-case application boundary.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class ReviewConclusion(StrEnum):
    HARMFUL = "harmful"
    NON_HARMFUL = "non_harmful"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"


class EvidenceSufficiency(StrEnum):
    SUFFICIENT = "sufficient"
    LIMITED = "limited"
    INSUFFICIENT = "insufficient"


class ReviewUrgency(StrEnum):
    ROUTINE = "routine"
    WATCH = "watch"
    URGENT = "urgent"
    CRITICAL = "critical"


class Disposition(StrEnum):
    MONITOR = "monitor"
    GATHER_EVIDENCE = "gather_evidence"
    ESCALATE = "escalate"
    RESPOND = "respond"
    ARCHIVE = "archive"


class EvidenceAssessment(StrEnum):
    SUPPORTS = "supports"
    CONTRADICTS = "contradicts"
    IRRELEVANT = "irrelevant"
    UNRESOLVED = "unresolved"


class ActionRequired(StrEnum):
    NONE = "none"
    ADD_EVIDENCE = "add_evidence"
    REVIEW_AVAILABLE = "review_available"
    CONFIRM_DECISION = "confirm_decision"
    RECONFIRM_DECISION = "reconfirm_decision"


class CaseActivityType(StrEnum):
    CASE_CREATED = "case_created"
    SNAPSHOT_ADDED = "snapshot_added"
    EVIDENCE_ANNOTATED = "evidence_annotated"
    EVIDENCE_REQUESTED = "evidence_requested"
    REVIEW_REQUESTED = "review_requested"
    REVIEW_ADVISORY_AVAILABLE = "review_advisory_available"
    DECISION_DRAFT_SAVED = "decision_draft_saved"
    DECISION_CONFIRMED = "decision_confirmed"
    CORRECTION_RECORDED = "correction_recorded"
    RECONFIRMATION_REQUIRED = "reconfirmation_required"


class ProductContract(BaseModel):
    """Closed product contract that rejects accidental technical-field leaks."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class PreliminaryFinding(ProductContract):
    conclusion: ReviewConclusion
    rationale: str = Field(..., min_length=1, max_length=8000)
    key_evidence_refs: list[str] = Field(default_factory=list, max_length=100)


class CoordinationBusinessSummary(ProductContract):
    narrative: str = Field(..., min_length=1, max_length=8000)
    key_communities: list[str] = Field(default_factory=list, max_length=100)
    key_accounts: list[str] = Field(default_factory=list, max_length=100)


class PropagationBusinessSummary(ProductContract):
    narrative: str = Field(..., min_length=1, max_length=8000)
    trend: str = Field(..., min_length=1, max_length=256)
    forecast_range: str | None = Field(default=None, max_length=256)
    likely_next_targets: list[str] = Field(default_factory=list, max_length=100)


class ReviewAdvisory(ProductContract):
    conclusion: ReviewConclusion
    urgency: ReviewUrgency
    disposition: Disposition
    rationale: str = Field(..., min_length=1, max_length=8000)
    differences_from_preliminary: list[str] = Field(default_factory=list, max_length=100)
    key_evidence_refs: list[str] = Field(default_factory=list, max_length=100)
    received_at: datetime


class ConfirmedDecision(ProductContract):
    decision_id: str = Field(..., min_length=1, max_length=128)
    decision_version: int = Field(..., ge=1)
    conclusion: ReviewConclusion
    urgency: ReviewUrgency
    disposition: Disposition
    rationale: str = Field(..., min_length=1, max_length=8000)
    key_evidence_refs: list[str] = Field(default_factory=list, max_length=100)
    unresolved_items: list[str] = Field(default_factory=list, max_length=100)
    confirmed_by_name: str = Field(..., min_length=1, max_length=128)
    confirmed_at: datetime


class ReviewCaseSummary(ProductContract):
    case_id: str = Field(..., min_length=1, max_length=128)
    event_id: str = Field(..., min_length=1, max_length=128)
    title: str = Field(..., min_length=1, max_length=512)
    preliminary_finding: PreliminaryFinding
    evidence_sufficiency: EvidenceSufficiency
    sufficiency_reasons: list[str] = Field(default_factory=list, max_length=100)
    missing_evidence: list[str] = Field(default_factory=list, max_length=100)
    urgency: ReviewUrgency
    disposition: Disposition
    action_required: ActionRequired
    coordination_summary: CoordinationBusinessSummary
    propagation_summary: PropagationBusinessSummary
    updated_at: datetime


class ReviewCaseDetail(ReviewCaseSummary):
    review_advisory: ReviewAdvisory | None = None
    confirmed_decision: ConfirmedDecision | None = None
    decision_draft: DecisionDraft | None = None


class ReviewCaseList(ProductContract):
    items: list[ReviewCaseSummary]
    total: int = Field(..., ge=0)


class EvidenceAnnotationCreate(ProductContract):
    evidence_ref: str = Field(..., min_length=1, max_length=512)
    assessment: EvidenceAssessment
    note: str = Field(..., min_length=1, max_length=4000)
    source_url: str | None = Field(default=None, max_length=2048)


class EvidenceAnnotation(ProductContract):
    annotation_id: str = Field(..., min_length=1, max_length=128)
    evidence_ref: str = Field(..., min_length=1, max_length=512)
    assessment: EvidenceAssessment
    note: str = Field(..., min_length=1, max_length=4000)
    source_url: str | None = Field(default=None, max_length=2048)
    created_by_name: str = Field(..., min_length=1, max_length=128)
    created_at: datetime


class EvidenceItem(ProductContract):
    evidence_ref: str = Field(..., min_length=1, max_length=512)
    evidence_type: str = Field(..., min_length=1, max_length=64)
    assessment: EvidenceAssessment
    title: str = Field(..., min_length=1, max_length=512)
    excerpt: str = Field(..., max_length=8000)
    source_url: str | None = Field(default=None, max_length=2048)
    platform: str | None = Field(default=None, max_length=64)
    observed_at: datetime | None = None
    annotations: list[EvidenceAnnotation] = Field(default_factory=list)


class EvidencePage(ProductContract):
    """Cursor metadata for the evidence group returned by the current request."""

    assessment: EvidenceAssessment
    cursor: int = Field(default=0, ge=0)
    limit: int = Field(default=40, ge=1, le=100)
    total: int = Field(default=0, ge=0)
    next_cursor: int | None = Field(default=None, ge=0)


class ReviewCaseEvidence(ProductContract):
    case_id: str = Field(..., min_length=1, max_length=128)
    supports: list[EvidenceItem] = Field(default_factory=list)
    contradicts: list[EvidenceItem] = Field(default_factory=list)
    irrelevant: list[EvidenceItem] = Field(default_factory=list)
    unresolved: list[EvidenceItem] = Field(default_factory=list)
    group_counts: dict[EvidenceAssessment, int] = Field(default_factory=dict)
    page: EvidencePage | None = None


class ReviewRequestCreate(ProductContract):
    reason: str = Field(..., min_length=1, max_length=4000)
    evidence_refs: list[str] = Field(default_factory=list, max_length=100)


class ReviewRequestReceipt(ProductContract):
    case_id: str = Field(..., min_length=1, max_length=128)
    action_required: ActionRequired
    message: str = Field(..., min_length=1, max_length=1000)


class DecisionDraftUpsert(ProductContract):
    conclusion: ReviewConclusion
    urgency: ReviewUrgency
    disposition: Disposition
    rationale: str = Field(..., min_length=1, max_length=8000)
    key_evidence_refs: list[str] = Field(default_factory=list, max_length=100)
    unresolved_items: list[str] = Field(default_factory=list, max_length=100)
    expected_version: int = Field(..., ge=0)


class DecisionDraft(ProductContract):
    case_id: str = Field(..., min_length=1, max_length=128)
    draft_version: int = Field(..., ge=1)
    conclusion: ReviewConclusion
    urgency: ReviewUrgency
    disposition: Disposition
    rationale: str = Field(..., min_length=1, max_length=8000)
    key_evidence_refs: list[str] = Field(default_factory=list, max_length=100)
    unresolved_items: list[str] = Field(default_factory=list, max_length=100)
    saved_at: datetime


class DecisionConfirmRequest(ProductContract):
    expected_draft_version: int = Field(..., ge=1)
    confirmation_note: str = Field(default="", max_length=4000)


class DecisionConfirmation(ProductContract):
    case_id: str = Field(..., min_length=1, max_length=128)
    decision: ConfirmedDecision
    action_required: ActionRequired


class CaseActivity(ProductContract):
    cursor: int = Field(..., ge=1)
    case_id: str = Field(..., min_length=1, max_length=128)
    activity_type: CaseActivityType
    action_required: ActionRequired
    summary: str = Field(..., min_length=1, max_length=1000)
    detail_lines: list[str] = Field(default_factory=list, max_length=100)
    evidence_refs: list[str] = Field(default_factory=list, max_length=100)
    actor_name: str = Field(..., min_length=1, max_length=128)
    occurred_at: datetime


class CaseActivityList(ProductContract):
    items: list[CaseActivity]
    next_cursor: int | None = Field(default=None, ge=1)


class CaseEvent(ProductContract):
    """Business-safe event payload serialized over the case SSE stream."""

    cursor: int = Field(..., ge=1)
    case_id: str = Field(..., min_length=1, max_length=128)
    activity_type: CaseActivityType
    action_required: ActionRequired
    message: str = Field(..., min_length=1, max_length=1000)
    occurred_at: datetime


ReviewCaseDetail.model_rebuild()


__all__ = [
    "ActionRequired",
    "CaseActivity",
    "CaseActivityList",
    "CaseActivityType",
    "CaseEvent",
    "ConfirmedDecision",
    "CoordinationBusinessSummary",
    "DecisionConfirmation",
    "DecisionConfirmRequest",
    "DecisionDraft",
    "DecisionDraftUpsert",
    "Disposition",
    "EvidenceAnnotation",
    "EvidenceAnnotationCreate",
    "EvidenceAssessment",
    "EvidenceItem",
    "EvidencePage",
    "EvidenceSufficiency",
    "PreliminaryFinding",
    "PropagationBusinessSummary",
    "ReviewAdvisory",
    "ReviewCaseDetail",
    "ReviewCaseEvidence",
    "ReviewCaseList",
    "ReviewCaseSummary",
    "ReviewConclusion",
    "ReviewRequestCreate",
    "ReviewRequestReceipt",
    "ReviewUrgency",
]
