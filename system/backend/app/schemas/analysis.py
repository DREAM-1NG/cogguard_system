from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, field_validator

from app.core.analysis.contracts import (
    AnalysisRunStatus,
    DEFAULT_ANALYSIS_STAGES,
    TimeWindow,
    normalize_analysis_stage,
)


class AnalysisSnapshotCreateRequest(BaseModel):
    event_id: str = Field(..., min_length=1)
    core_window: TimeWindow
    context_window: TimeWindow
    platform: str | None = None


class AnalysisRunCreateRequest(BaseModel):
    event_id: str = Field(..., min_length=1)
    snapshot_id: str = Field(..., min_length=1)
    requested_stages: list[str] = Field(default_factory=lambda: list(DEFAULT_ANALYSIS_STAGES))
    options: dict[str, Any] = Field(default_factory=dict)

    @field_validator("requested_stages")
    @classmethod
    def normalize_requested_stages(cls, value: list[str]) -> list[str]:
        if not value:
            raise ValueError("requested_stages must contain at least one stage")
        normalized: list[str] = []
        for stage in value:
            normalized_stage = normalize_analysis_stage(stage)
            if normalized_stage not in normalized:
                normalized.append(normalized_stage)
        return normalized


class AnalysisRunStatusUpdateRequest(BaseModel):
    status: AnalysisRunStatus
    event_type: str = "run_status_changed"
    payload: dict[str, Any] = Field(default_factory=dict)
