"""Schemas for account-detection active learning and labeling."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

__all__ = [
    "AccountLabelAdjudicationRequest",
    "AccountLabelRequest",
    "AccountModelActivationRequest",
    "AccountModelApprovalRequest",
    "AccountTrainingCandidateRequest",
    "ExportAccountDatasetRequest",
    "CreateAccountLabelBatchRequest",
]


class CreateAccountLabelBatchRequest(BaseModel):
    """Request to create an analyst labeling batch."""

    event_id: str | None = Field(default=None, description="Optional event scope")
    platform: str | None = Field(default=None, description="Optional platform scope")
    budget: int = Field(default=20, ge=1, le=500)
    cold_start: bool = False


class AccountLabelRequest(BaseModel):
    """Analyst-submitted observable behavior label."""

    case_id: str
    batch_id: str | None = None
    behavior_label: str
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    evidence_post_ids: list[str] = Field(default_factory=list)
    reason_tags: list[str] = Field(default_factory=list)
    notes: str = ""
    case_fingerprint: str = ""


class AccountLabelAdjudicationRequest(BaseModel):
    """Decision that promotes or rejects a submitted account label."""

    approved: bool
    behavior_label: str | None = None
    notes: str = ""


class AccountTrainingCandidateRequest(BaseModel):
    """Register a candidate model trained from an approved-label corpus."""

    model_version: str
    dataset_version_id: str
    artifact_uri: str = ""
    artifact_hash: str = ""
    metrics: dict[str, Any] = Field(default_factory=dict)


class AccountModelApprovalRequest(BaseModel):
    """Authenticated administrator approval for a shadow model."""

    approval_notes: str = ""


class ExportAccountDatasetRequest(BaseModel):
    """Request to export approved account labels into a versioned corpus."""

    dataset_version_id: str | None = None
    output_dir: str | None = None


class AccountModelActivationRequest(BaseModel):
    """Request to activate a candidate account-detection model."""

    activation_notes: str = ""
