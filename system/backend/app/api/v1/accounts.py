"""Account monitoring API routes."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import APIRouter, Depends, Query

from app.core.security import get_current_user
from app.db.mysql import get_db
from app.models.user import User
from app.schemas.account_labeling import (
    AccountLabelAdjudicationRequest,
    AccountLabelRequest,
    AccountModelActivationRequest,
    AccountModelApprovalRequest,
    AccountTrainingCandidateRequest,
    CreateAccountLabelBatchRequest,
    ExportAccountDatasetRequest,
)
from app.services import account_active_learning_service, account_label_service
from app.services import account_dataset_service
from app.services import account_model_governance_service, account_service, bot_detection_service
from app.utils.exceptions import ForbiddenError
from app.utils.response import success

router = APIRouter()


@router.get("/profiles")
async def list_profiles(
    platform: str | None = Query(None, description="Optional platform filter"),
    event_id: str | None = Query(None, description="Optional event filter"),
    _current_user: User = Depends(get_current_user),
):
    profiles = await account_service.get_account_profiles(platform=platform, event_id=event_id)
    return success(data=profiles)


@router.post("/bot-detection")
async def detect_bots(
    platform: str | None = Query(None, description="Optional platform filter"),
    event_id: str | None = Query(None, description="Optional event filter"),
    _current_user: User = Depends(get_current_user),
):
    result = await bot_detection_service.detect_social_bots(
        event_id=event_id,
        platform=platform,
    )
    return success(data=result)


@router.get("/detail/{account_id}")
async def get_detail(
    account_id: str,
    platform: str | None = Query(None, description="Optional platform filter"),
    event_id: str | None = Query(None, description="Optional event filter"),
    _current_user: User = Depends(get_current_user),
):
    detail = await account_service.get_account_detail(account_id, platform=platform, event_id=event_id)
    if not detail:
        return success(data=None, msg="Account not found")
    return success(data=detail)


@router.post("/active-learning/batches")
async def create_active_learning_batch(
    payload: CreateAccountLabelBatchRequest,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    batch = await account_active_learning_service.create_account_label_batch(
        session,
        event_id=payload.event_id,
        platform=payload.platform,
        budget=payload.budget,
        cold_start=payload.cold_start,
        operator_id=int(current_user.id),
    )
    return success(data=batch)


@router.get("/active-learning/batches/{batch_id}")
async def get_active_learning_batch(
    batch_id: str,
    session: AsyncSession = Depends(get_db),
    _current_user: User = Depends(get_current_user),
):
    batch = await account_active_learning_service.get_account_label_batch(session, batch_id)
    if not batch:
        return success(data=None, msg="Account label batch not found")
    return success(data=batch)


@router.get("/label-queue")
async def list_label_queue(
    batch_id: str | None = Query(None, description="Optional label batch filter"),
    limit: int = Query(100, ge=1, le=500),
    session: AsyncSession = Depends(get_db),
    _current_user: User = Depends(get_current_user),
):
    rows = await account_active_learning_service.list_account_label_queue(
        session,
        batch_id=batch_id,
        limit=limit,
    )
    return success(data=rows)


@router.post("/labels")
async def submit_account_label(
    payload: AccountLabelRequest,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    label = await account_label_service.submit_account_label(
        session,
        case_id=payload.case_id,
        batch_id=payload.batch_id,
        behavior_label=payload.behavior_label,
        confidence=payload.confidence,
        evidence_post_ids=payload.evidence_post_ids,
        reason_tags=payload.reason_tags,
        notes=payload.notes,
        case_fingerprint=payload.case_fingerprint,
        analyst_id=int(current_user.id),
    )
    return success(data=label)


@router.post("/labels/{label_id}/adjudicate")
async def adjudicate_account_label(
    label_id: str,
    payload: AccountLabelAdjudicationRequest,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    label = await account_label_service.adjudicate_account_label(
        session,
        label_id=label_id,
        approved=payload.approved,
        behavior_label=payload.behavior_label,
        notes=payload.notes,
        adjudicator_id=int(current_user.id),
    )
    if not label:
        return success(data=None, msg="Account label not found")
    return success(data=label)


@router.get("/labels/stats")
async def get_account_label_stats(
    session: AsyncSession = Depends(get_db),
    _current_user: User = Depends(get_current_user),
):
    stats = await account_label_service.get_account_label_stats(session)
    return success(data=stats)


@router.post("/training/candidates")
async def register_training_candidate(
    payload: AccountTrainingCandidateRequest,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_account_model_administrator(current_user)
    candidate = await account_model_governance_service.register_account_training_candidate(
        session,
        model_version=payload.model_version,
        dataset_version_id=payload.dataset_version_id,
        artifact_uri=payload.artifact_uri,
        artifact_hash=payload.artifact_hash,
        metrics=payload.metrics,
        operator_id=int(current_user.id),
    )
    return success(data=candidate)


@router.post("/datasets/export")
async def export_account_dataset(
    payload: ExportAccountDatasetRequest,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    dataset = await account_dataset_service.export_approved_account_dataset(
        session,
        dataset_version_id=payload.dataset_version_id,
        output_dir=payload.output_dir,
        operator_id=int(current_user.id),
    )
    return success(data=dataset)


@router.get("/datasets")
async def list_account_datasets(
    session: AsyncSession = Depends(get_db),
    _current_user: User = Depends(get_current_user),
):
    datasets = await account_dataset_service.list_account_detection_datasets(session)
    return success(data=datasets)


@router.get("/models")
async def list_account_models(
    session: AsyncSession = Depends(get_db),
    _current_user: User = Depends(get_current_user),
):
    models = await account_model_governance_service.list_account_detection_models(session)
    return success(data=models)


@router.post("/models/{model_version}/approve")
async def approve_account_model(
    model_version: str,
    payload: AccountModelApprovalRequest,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_account_model_administrator(current_user)
    approval = await account_model_governance_service.approve_account_detection_model(
        session,
        model_version=model_version,
        approver_id=int(current_user.id),
        approval_notes=payload.approval_notes,
    )
    if not approval:
        return success(data=None, msg="Account model version not found")
    return success(data=approval)


@router.post("/models/{model_version}/activate")
async def activate_account_model(
    model_version: str,
    payload: AccountModelActivationRequest,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_account_model_administrator(current_user)
    activated = await account_model_governance_service.activate_account_detection_model(
        session,
        model_version=model_version,
        operator_id=int(current_user.id),
        activation_notes=payload.activation_notes,
    )
    if not activated:
        return success(data=None, msg="Account model version not found")
    return success(data=activated)


def _require_account_model_administrator(user: User) -> None:
    if getattr(user, "role", "") != "admin" or not getattr(user, "is_active", False):
        raise ForbiddenError("Account model governance requires an active administrator.")
