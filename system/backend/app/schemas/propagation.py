"""Typed response contract for event-scoped propagation prediction."""

from __future__ import annotations

from typing import Annotated, Any, Literal, Self

from pydantic import BaseModel, Field, model_validator


class TrendPoint(BaseModel):
    step: int
    at: str | None = None
    predicted_size: int


class CumulativeTimelinePoint(BaseModel):
    """Timestamp-window cumulative count backed by event evidence."""

    at: str
    cumulative_size: int = Field(ge=0)


class TimelineWindow(BaseModel):
    start: str
    end: str


class EventTimelineProjection(BaseModel):
    """Evidence timeline rendered independently from checkpoint inference."""

    range: Literal["active", "24h", "7d", "all"]
    resolution: Literal["minute", "hour", "day", "week"]
    active_window: TimelineWindow | None = None
    window: TimelineWindow | None = None
    observed_points: list[CumulativeTimelinePoint] = Field(default_factory=list)
    realized_points: list[CumulativeTimelinePoint] = Field(default_factory=list)


NonEmptyString = Annotated[str, Field(min_length=1)]
ClaimAnchorString = Annotated[str, Field(min_length=1, pattern=r".*\S.*")]
EvidenceReference = Annotated[
    str,
    Field(
        min_length=1,
        pattern=r"^(?:case:[^:\s]+:claim:[^:\s]+|[^:\s]+:(?:post|comment):[^:\s]+)$",
    ),
]
EvidenceReferenceList = Annotated[list[EvidenceReference], Field(min_length=1)]


class ClaimResponseClaimAnchor(BaseModel):
    case_id: ClaimAnchorString
    claim_id: ClaimAnchorString
    authority_source_id: ClaimAnchorString
    text: ClaimAnchorString
    source_url: ClaimAnchorString
    account: ClaimAnchorString
    published_at: str | None
    role: ClaimAnchorString
    source_review_status: ClaimAnchorString
    source_tier: str | None
    evidence_refs: EvidenceReferenceList


class ClaimResponseAuthorityBinding(BaseModel):
    source_id: NonEmptyString
    platform: NonEmptyString
    author_id: NonEmptyString


class ClaimResponsePathReference(BaseModel):
    path_id: NonEmptyString
    evidence_refs: EvidenceReferenceList
    nodes: list[NonEmptyString] | None = None
    score: float | int | None = None
    semantic_overlay: dict[str, Any] | None = None


class ClaimResponseOfficialPublication(BaseModel):
    post_id: NonEmptyString
    platform: NonEmptyString
    author_id: NonEmptyString
    author_name: NonEmptyString
    content: str
    published_at: str | None
    source_url: str | None
    authority_binding: ClaimResponseAuthorityBinding
    verification_context: dict[str, Any]
    engagement_percentile: float = Field(ge=0.0, le=1.0)
    evidence_refs: EvidenceReferenceList
    semantic: dict[str, Any] | None


class ClaimResponseInfluentialResponse(BaseModel):
    platform: NonEmptyString
    author_id: NonEmptyString
    author_name: NonEmptyString
    rank_scope: NonEmptyString
    downstream_reach: int | None = Field(default=None, ge=0)
    downstream_reach_status: Literal["available", "unavailable"] | None = None
    downstream_reach_reason: str | None = None
    path_contribution: float | int
    path_count: int = Field(ge=1)
    engagement_percentile: float = Field(ge=0.0, le=1.0)
    first_seen_at: str | None
    evidence_refs: EvidenceReferenceList
    path_refs: list[ClaimResponsePathReference]
    rank: int = Field(ge=1)
    semantic: dict[str, Any] | None = None
    stance: str | None = None


class ClaimResponseOfficialTimelineRow(BaseModel):
    type: Literal["official_publication"]
    at: str | None
    platform: NonEmptyString
    author_id: NonEmptyString
    post_id: NonEmptyString
    evidence_refs: EvidenceReferenceList


class ClaimResponseInfluentialTimelineRow(BaseModel):
    type: Literal["influential_response"]
    at: str | None
    platform: NonEmptyString
    author_id: NonEmptyString
    rank: int = Field(ge=1)
    evidence_refs: EvidenceReferenceList
    path_refs: list[ClaimResponsePathReference]


class ClaimResponseCoverageSection(BaseModel):
    status: Literal["available", "unavailable", "not_found", "blocked"]
    reason: str | None = None
    case_id: str | None = None
    claim_id: str | None = None
    source_id: str | None = None
    review_status: str | None = None
    binding_count: int | None = Field(default=None, ge=0)
    path_count: int | None = Field(default=None, ge=0)
    path_overlay_count: int | None = Field(default=None, ge=0)
    claim_response_path_overlay_count: int | None = Field(default=None, ge=0)


class ClaimResponseEvidenceRefsCoverage(BaseModel):
    status: Literal["available", "unavailable"]
    official_publication_count: int = Field(ge=0)
    response_count: int = Field(ge=0)


class ClaimResponseCoverage(BaseModel):
    case: ClaimResponseCoverageSection
    primary_claim: ClaimResponseCoverageSection
    official_account_binding: ClaimResponseCoverageSection
    observed_paths: ClaimResponseCoverageSection
    semantic: ClaimResponseCoverageSection
    authority_source: ClaimResponseCoverageSection | None = None
    evidence_refs: ClaimResponseEvidenceRefsCoverage | None = None
    data_scope: dict[str, Any] | None = None


class ClaimResponseLandscapeData(BaseModel):
    """Observed Event Review Case claim-response projection."""

    status: Literal["ready", "not_found", "blocked"]
    event_id: NonEmptyString
    platform: str | None = None
    blocking_reason: str | None = None
    claim_anchor: ClaimResponseClaimAnchor | None = None
    official_publications: list[ClaimResponseOfficialPublication]
    influential_responses: list[ClaimResponseInfluentialResponse]
    timeline: list[ClaimResponseOfficialTimelineRow | ClaimResponseInfluentialTimelineRow]
    coverage: ClaimResponseCoverage
    capability: dict[str, Any]
    data_scope: dict[str, Any]

    @model_validator(mode="after")
    def ready_projection_requires_evidence_contract(self) -> Self:
        if self.status == "ready":
            if self.claim_anchor is None:
                raise ValueError("ready claim-response projection requires claim_anchor")
            if self.coverage.evidence_refs is None:
                raise ValueError("ready claim-response projection requires evidence_refs coverage")
        return self


class ClaimResponseLandscapeResponse(BaseModel):
    code: int = 0
    data: ClaimResponseLandscapeData
    msg: str = "ok"


class TrendInterval(BaseModel):
    step: int | str
    at: str | None = None
    timestamp: str | None = None
    lower: float | None = None
    upper: float | None = None


class MacroPrediction(BaseModel):
    observed_size: int = 0
    predicted_size: int | None = None
    trend_points: list[TrendPoint] = Field(default_factory=list)
    observed_points: list[CumulativeTimelinePoint] = Field(default_factory=list)
    realized_points: list[CumulativeTimelinePoint] = Field(default_factory=list)
    intervals: list[TrendInterval] | None = None
    direction: str | None = None
    score_concentration: float | None = None
    calibration_status: Literal["available", "unavailable"] = "unavailable"


class NextHopUser(BaseModel):
    rank: int
    author_id: str
    author_name: str
    score: float
    candidate_source: str
    activation_type: Literal["reactivation", "new_activation"]
    identity_resolution: str | None = None
    score_semantics: str | None = None
    bucket_collision_size: int = 1
    event_count: int = 0
    first_seen_at: str | None = None
    last_seen_at: str | None = None
    evidence_refs: list[dict[str, Any]] = Field(default_factory=list)
    trace_available: bool = True


class MicroCoverage(BaseModel):
    mapped_candidate_buckets: int = 0
    unmapped_candidate_buckets: int = 0
    legal_candidate_buckets: int = 0
    mapped_probability_mass: float = 0.0
    new_activation_status: str = "abstain_no_identity_mapping"
    identity_mapping_status: str = "unique_current_event_bucket_proxy_only"
    ambiguous_mapped_buckets: int = 0
    excluded_ambiguous_users: int = 0
    unique_identity_probability_mass: float = 0.0


class MicroPrediction(BaseModel):
    top_users: list[NextHopUser] = Field(default_factory=list)
    candidate_count: int = 0
    candidate_bucket_count: int = 0
    candidate_source_counts: dict[str, int] = Field(default_factory=dict)
    reactivation_count: int = 0
    new_activation_count: int = 0
    coverage: MicroCoverage = Field(default_factory=MicroCoverage)


class PredictionModelScope(BaseModel):
    """Identity and provenance scope for the model that produced a result."""

    name: str | None = None
    dataset: str | None = None
    checkpoint: str | None = None
    methodology: str | None = None
    scope: Literal["current_event", "research_benchmark"] | None = None


class PropagationPredictionData(BaseModel):
    status: str
    model_status: Literal["available", "unavailable"]
    event_id: str | None = None
    platform: str | None = None
    macro: MacroPrediction
    micro: MicroPrediction
    data_scope: dict[str, Any]
    model: PredictionModelScope | None = None
    capability: dict[str, Any] | None = None
    methodology: dict[str, Any] | None = None
    prediction_boundary: dict[str, Any] | None = None
    cache: dict[str, Any] | None = None
    note: str | None = None


class PropagationPredictionResponse(BaseModel):
    code: int = 0
    data: PropagationPredictionData
    msg: str = "ok"


class PropagationMonitorProfileRequest(BaseModel):
    event_id: str = Field(min_length=1, max_length=128)
    platform: str | None = Field(default=None, max_length=32)
    enabled: bool = True
    interval_minutes: int = Field(default=5, ge=1, le=1440)
    thresholds: dict[str, dict[str, float | int]] = Field(default_factory=dict)


class PropagationAlertActionRequest(BaseModel):
    action: Literal["acknowledge", "close", "ignore"]
    note: str | None = Field(default=None, max_length=2000)
