"""Coordination model API schemas."""

from typing import Any, Literal

from pydantic import BaseModel, Field


class CoordinationRunRequest(BaseModel):
    dataset_id: int = Field(..., ge=1)


class CoordinationGroupLabelReviewRequest(BaseModel):
    case: dict[str, Any] = Field(..., description="完整的 CoordinationGroupLabelCase JSON")
    cluster_harm_label: Literal["harmful_coordination", "benign_coordination"]
    reviewer_notes: str = Field(default="", max_length=4000)
