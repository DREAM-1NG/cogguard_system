"""Pydantic contracts for Case Workbench prototype operations."""

from __future__ import annotations

from pydantic import BaseModel, Field


class CaseActionDecisionRequest(BaseModel):
    note: str = Field(default="", max_length=1000)


class CaseBlockerAcknowledgementRequest(BaseModel):
    reason: str = Field(min_length=1, max_length=4000)


class CaseFeedbackRequest(BaseModel):
    content: str = Field(min_length=1, max_length=4000)


class CaseSemanticCorrectionRequest(BaseModel):
    module: str = Field(min_length=1, max_length=80)
    target_ref: str = Field(min_length=1, max_length=200)
    original_value: str = Field(default="", max_length=1000)
    corrected_value: str = Field(min_length=1, max_length=1000)
    reason: str = Field(min_length=1, max_length=2000)


class CaseCloseoutReviewRequest(BaseModel):
    summary: str = Field(min_length=1, max_length=4000)


__all__ = [
    "CaseActionDecisionRequest",
    "CaseBlockerAcknowledgementRequest",
    "CaseCloseoutReviewRequest",
    "CaseFeedbackRequest",
    "CaseSemanticCorrectionRequest",
]
