"""Typed response contract for event-scoped propagation prediction."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class TrendPoint(BaseModel):
    step: int
    at: str | None = None
    predicted_size: int


class ClaimResponseLandscapeData(BaseModel):
    """Observed Event Review Case claim-response projection."""

    status: Literal["ready", "not_found", "blocked"]
    event_id: str
    platform: str | None = None
    blocking_reason: str | None = None
    claim_anchor: dict[str, Any] | None = None
    official_publications: list[dict[str, Any]] = Field(default_factory=list)
    influential_responses: list[dict[str, Any]] = Field(default_factory=list)
    timeline: list[dict[str, Any]] = Field(default_factory=list)
    coverage: dict[str, Any] = Field(default_factory=dict)
    capability: dict[str, Any] = Field(default_factory=dict)
    data_scope: dict[str, Any] = Field(default_factory=dict)


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
