"""Coordination model API schemas."""

from pydantic import BaseModel, Field


class CoordinationRunRequest(BaseModel):
    dataset_id: int = Field(..., ge=1)
