from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator


ANALYSIS_STAGE_ALIASES: dict[str, str] = {
    "coordination": "coordination_discover",
    "coordination_engine": "coordination_discover",
    "coordination_discover": "coordination_discover",
    "propagation": "propagation_analysis",
    "propagation_engine": "propagation_analysis",
    "propagation_analysis": "propagation_analysis",
    "review_student": "student",
    "review_teacher": "teacher",
    "review_student": "student",
    "review_teacher": "teacher",
}
ANALYSIS_STAGE_ALLOWLIST = frozenset({"coordination_discover", "propagation_analysis", "student", "teacher"})
# A prototype run should exercise the complete capability chain by default.
# Callers may still request a narrower stage list for focused diagnostics.
DEFAULT_ANALYSIS_STAGES = (
    "coordination_discover",
    "propagation_analysis",
    "student",
    "teacher",
)


class TimeWindow(BaseModel):
    start: datetime
    end: datetime

    @model_validator(mode="after")
    def validate_order(self) -> "TimeWindow":
        self.start = _as_utc(self.start)
        self.end = _as_utc(self.end)
        if self.start >= self.end:
            raise ValueError("TimeWindow.start must be earlier than TimeWindow.end")
        return self

    def contains(self, value: datetime) -> bool:
        timestamp = _as_utc(value)
        return self.start <= timestamp < self.end


class EvidenceRelation(BaseModel):
    relation_type: str
    source_id: str
    target_id: str
    platform: str
    observed_at: datetime | None = None
    evidence_ref: str


class ProvenanceRecord(BaseModel):
    source_type: str = "crawl"
    source_id: str
    platform: str
    source_keyword: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class DataQualityReport(BaseModel):
    status: Literal["pass", "warn", "reject"]
    total_input_posts: int
    total_input_comments: int
    context_posts: int
    context_comments: int
    core_posts: int
    duplicate_posts: int = 0
    duplicate_comments: int = 0
    excluded_posts: int = 0
    excluded_comments: int = 0
    missing_post_ids: int = 0
    missing_comment_ids: int = 0
    missing_timestamps: int = 0
    missing_authors: int = 0
    platform_counts: dict[str, int] = Field(default_factory=dict)
    issues: list[str] = Field(default_factory=list)


class EventSnapshot(BaseModel):
    snapshot_id: str
    event_id: str
    platforms: list[str]
    core_window: TimeWindow
    context_window: TimeWindow
    posts: list[dict[str, Any]]
    comments: list[dict[str, Any]]
    relationships: list[EvidenceRelation]
    quality_report: DataQualityReport
    provenance: list[ProvenanceRecord]
    data_fingerprint: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class AnalysisRunStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    NEEDS_EVIDENCE = "needs_evidence"
    AWAITING_REVIEW = "awaiting_review"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class InvalidRunTransition(ValueError):
    pass


class UnknownAnalysisStage(ValueError):
    pass


_ALLOWED_TRANSITIONS: dict[AnalysisRunStatus, frozenset[AnalysisRunStatus]] = {
    AnalysisRunStatus.QUEUED: frozenset(
        {AnalysisRunStatus.RUNNING, AnalysisRunStatus.FAILED, AnalysisRunStatus.CANCELLED}
    ),
    AnalysisRunStatus.RUNNING: frozenset(
        {
            AnalysisRunStatus.NEEDS_EVIDENCE,
            AnalysisRunStatus.AWAITING_REVIEW,
            AnalysisRunStatus.COMPLETED,
            AnalysisRunStatus.FAILED,
            AnalysisRunStatus.CANCELLED,
        }
    ),
    AnalysisRunStatus.NEEDS_EVIDENCE: frozenset(
        {AnalysisRunStatus.QUEUED, AnalysisRunStatus.RUNNING, AnalysisRunStatus.FAILED, AnalysisRunStatus.CANCELLED}
    ),
    AnalysisRunStatus.AWAITING_REVIEW: frozenset(
        {
            AnalysisRunStatus.NEEDS_EVIDENCE,
            AnalysisRunStatus.COMPLETED,
            AnalysisRunStatus.FAILED,
            AnalysisRunStatus.CANCELLED,
        }
    ),
    AnalysisRunStatus.COMPLETED: frozenset(),
    AnalysisRunStatus.FAILED: frozenset(),
    AnalysisRunStatus.CANCELLED: frozenset(),
}


def transition_run_status(
    current: AnalysisRunStatus | str,
    target: AnalysisRunStatus | str,
) -> AnalysisRunStatus:
    current_status = AnalysisRunStatus(current)
    target_status = AnalysisRunStatus(target)
    if current_status == target_status:
        return target_status
    if target_status not in _ALLOWED_TRANSITIONS[current_status]:
        raise InvalidRunTransition(f"Cannot transition analysis run from {current_status} to {target_status}")
    return target_status


def normalize_analysis_stage(stage: Any) -> str:
    value = str(stage or "").strip().lower()
    normalized = ANALYSIS_STAGE_ALIASES.get(value, value)
    if normalized not in ANALYSIS_STAGE_ALLOWLIST:
        raise UnknownAnalysisStage(f"Unknown analysis stage: {stage}")
    return normalized


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)
