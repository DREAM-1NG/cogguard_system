"""Pydantic contracts for Case Workbench prototype operations."""

from __future__ import annotations

from pydantic import BaseModel, Field


class CaseActionDecisionRequest(BaseModel):
    note: str = Field(default="", max_length=1000)


class CaseFeedbackRequest(BaseModel):
    content: str = Field(min_length=1, max_length=4000)


class CaseCloseoutReviewRequest(BaseModel):
    summary: str = Field(min_length=1, max_length=4000)


__all__ = [
    "CaseActionDecisionRequest",
    "CaseCloseoutReviewRequest",
    "CaseFeedbackRequest",
]

