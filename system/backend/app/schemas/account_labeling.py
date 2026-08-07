"""Schemas for account-detection active learning and labeling."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

__all__ = [
    "AccountLabelAdjudicationRequest",
    "AccountLabelReviewAssignmentRequest",
    "AccountLabelRequest",
    "AccountModelActivationRequest",
    "AccountModelApprovalRequest",
    "AccountModelEvaluationWritebackRequest",
    "AccountModelEvaluationJobRequest",
    "AccountTrainingCandidateRequest",
    "AccountTrainingRunRequest",
    "AccountTrainingResumeRequest",
    "CreateAccountCorpusRequest",
    "FreezeAccountHoldoutRequest",
    "AccountModelRollbackRequest",
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
    assignment_id: str | None = Field(default=None, min_length=1)
    behavior_label: str | None = None
    notes: str = ""


class AccountLabelReviewAssignmentRequest(BaseModel):
    """Assign an independent analyst for a required second review."""

    reviewer_id: int = Field(gt=0)


class AccountTrainingCandidateRequest(BaseModel):
    """Register a candidate model trained from an approved-label corpus."""

    model_version: str
    dataset_version_id: str
    artifact_uri: str = ""
    artifact_hash: str = ""
    metrics: dict[str, Any] = Field(default_factory=dict)


class AccountModelEvaluationWritebackRequest(BaseModel):
    """Evaluator-owned prediction evidence for a shadow candidate."""

    artifact_hash: str = Field(min_length=64, max_length=128)
    evaluation_run_id: str = Field(min_length=1, max_length=128)
    prediction_audits: list[dict[str, Any]] = Field(default_factory=list, max_length=100_000)
    evaluation_protocol: dict[str, Any] | None = None
    evaluation_manifest: dict[str, Any]


class AccountModelEvaluationJobRequest(BaseModel):
    """Create a system-owned frozen-holdout evaluation job without evidence input."""

    model_config = ConfigDict(extra="forbid")

    corpus_version_id: str = Field(min_length=1, max_length=128)
    evaluator_config: dict[str, Any] = Field(default_factory=dict)


class AccountTrainingRunRequest(BaseModel):
    """Create a governed encoder or detector training run."""

    family: str
    corpus_version_id: str = Field(min_length=1)
    input_fingerprint: str = Field(min_length=1)
    config: dict[str, Any] = Field(default_factory=dict)
    manual: bool = False


class AccountTrainingResumeRequest(BaseModel):
    """Resume an interrupted training run."""

    force: bool = False


class CreateAccountCorpusRequest(BaseModel):
    """Create an immutable Chinese post/comment corpus from Mongo."""

    event_id: str | None = None
    platform: str | None = None
    corpus_version_id: str | None = None
    output_dir: str | None = None
    require_chinese: bool = True


class FreezeAccountHoldoutRequest(BaseModel):
    """Freeze approved account labels before dataset export."""

    fraction: float = Field(default=0.2, gt=0.0, lt=1.0)
    seed: int = 17


class AccountModelRollbackRequest(BaseModel):
    """Roll back to a previously approved account-model version."""

    reason: str = Field(min_length=1, max_length=2000)


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
