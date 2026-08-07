"""Account monitoring API routes."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import APIRouter, Depends, Query

from app.core.security import get_current_user, require_roles
from app.db.mysql import get_db
from app.models.user import User
from app.schemas.account_labeling import (
    AccountLabelAdjudicationRequest,
    AccountLabelRequest,
    AccountLabelReviewAssignmentRequest,
    AccountModelActivationRequest,
    AccountModelRollbackRequest,
    AccountModelApprovalRequest,
    AccountModelEvaluationWritebackRequest,
    AccountModelEvaluationJobRequest,
    AccountTrainingCandidateRequest,
    AccountTrainingRunRequest,
    CreateAccountCorpusRequest,
    CreateAccountLabelBatchRequest,
    ExportAccountDatasetRequest,
    FreezeAccountHoldoutRequest,
)
from app.services import account_active_learning_service, account_label_service
from app.services import account_corpus_service, account_dataset_service
from app.services import (
    account_model_evaluation_service,
    account_model_governance_service,
    account_model_monitoring_service,
    account_service,
    bot_detection_service,
)
from app.services import account_training_service
from app.services.account_model_runtime_service import get_active_account_model
from app.tasks.account_evaluation_tasks import enqueue_account_model_evaluation_job
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
    _current_user: User = Depends(require_roles("analyst", "admin")),
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
    current_user: User = Depends(require_roles("analyst", "admin")),
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
    current_user: User = Depends(require_roles("analyst", "admin")),
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
    current_user: User = Depends(require_roles("analyst", "admin")),
):
    label = await account_label_service.adjudicate_account_label(
        session,
        label_id=label_id,
        approved=payload.approved,
        assignment_id=payload.assignment_id,
        behavior_label=payload.behavior_label,
        notes=payload.notes,
        adjudicator_id=int(current_user.id),
    )
    if not label:
        return success(data=None, msg="Account label not found")
    return success(data=label)


@router.post("/labels/{label_id}/review-assignment")
async def assign_account_label_review(
    label_id: str,
    payload: AccountLabelReviewAssignmentRequest,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles("admin")),
):
    assignment = await account_label_service.assign_account_label_review(
        session,
        label_id=label_id,
        reviewer_id=payload.reviewer_id,
        assigned_by=int(current_user.id),
    )
    if assignment is None:
        return success(data=None, msg="Account label not found")
    return success(data=assignment)


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
    current_user: User = Depends(require_roles("admin")),
):
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


@router.post("/training-runs")
async def create_account_training_run(
    payload: AccountTrainingRunRequest,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles("admin")),
):
    run = await account_training_service.create_account_training_run(
        session,
        family=payload.family,
        corpus_version_id=payload.corpus_version_id,
        input_fingerprint=payload.input_fingerprint,
        config=payload.config,
        manual=payload.manual,
        operator_id=int(current_user.id),
    )
    return success(data=run)


@router.post("/corpora")
async def create_account_corpus(
    payload: CreateAccountCorpusRequest,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles("admin")),
):
    corpus = await account_corpus_service.create_account_corpus_version(
        session,
        event_id=payload.event_id,
        platform=payload.platform,
        corpus_version_id=payload.corpus_version_id,
        output_dir=payload.output_dir,
        require_chinese=payload.require_chinese,
        operator_id=int(current_user.id),
    )
    return success(data=corpus)


@router.get("/corpora")
async def list_account_corpora(
    session: AsyncSession = Depends(get_db),
    _current_user: User = Depends(get_current_user),
):
    return success(data=await account_corpus_service.list_account_corpus_versions(session))


@router.post("/corpora/{corpus_version_id}/freeze-holdout")
async def freeze_account_holdout(
    corpus_version_id: str,
    payload: FreezeAccountHoldoutRequest,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles("admin")),
):
    result = await account_corpus_service.freeze_account_holdout(
        session,
        corpus_version_id=corpus_version_id,
        fraction=payload.fraction,
        seed=payload.seed,
        operator_id=int(current_user.id),
    )
    return success(data=result)


@router.get("/corpora/{corpus_version_id}/holdout")
async def list_account_holdout(
    corpus_version_id: str,
    session: AsyncSession = Depends(get_db),
    _current_user: User = Depends(get_current_user),
):
    return success(
        data=await account_corpus_service.list_frozen_account_holdout(
            session,
            corpus_version_id=corpus_version_id,
        )
    )


@router.get("/training-runs")
async def list_account_training_runs(
    session: AsyncSession = Depends(get_db),
    _current_user: User = Depends(get_current_user),
):
    return success(data=await account_training_service.list_account_training_runs(session))


@router.get("/training-runs/{run_id}")
async def get_account_training_run(
    run_id: str,
    session: AsyncSession = Depends(get_db),
    _current_user: User = Depends(get_current_user),
):
    run = await account_training_service.get_account_training_run(session, run_id)
    if run is None:
        return success(data=None, msg="Account training run not found")
    return success(data=run)


@router.get("/training-runs/{run_id}/events")
async def list_account_training_events(
    run_id: str,
    session: AsyncSession = Depends(get_db),
    _current_user: User = Depends(get_current_user),
):
    return success(data=await account_training_service.list_account_training_events(session, run_id))


@router.post("/training-runs/{run_id}/cancel")
async def cancel_account_training_run(
    run_id: str,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles("admin")),
):
    run = await account_training_service.cancel_account_training_run(
        session, run_id=run_id, operator_id=int(current_user.id)
    )
    if run is None:
        return success(data=None, msg="Account training run not found")
    return success(data=run)


@router.post("/training-runs/{run_id}/resume")
async def resume_account_training_run(
    run_id: str,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles("admin")),
):
    run = await account_training_service.resume_account_training_run(
        session, run_id=run_id, operator_id=int(current_user.id)
    )
    if run is None:
        return success(data=None, msg="Account training run not found")
    return success(data=run)


@router.post("/datasets/export")
async def export_account_dataset(
    payload: ExportAccountDatasetRequest,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles("admin")),
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
    current_user: User = Depends(require_roles("admin")),
):
    approval = await account_model_governance_service.approve_account_detection_model(
        session,
        model_version=model_version,
        approver_id=int(current_user.id),
        approval_notes=payload.approval_notes,
    )
    if not approval:
        return success(data=None, msg="Account model version not found")
    return success(data=approval)


@router.post("/models/{model_version}/evaluation-writeback-compatibility")
async def write_account_model_evaluation_compatibility(
    model_version: str,
    payload: AccountModelEvaluationWritebackRequest,
    session: AsyncSession = Depends(get_db),
    _current_user: User = Depends(require_roles("admin")),
):
    """Compatibility/admin-recovery path for externally produced signed evidence."""

    evaluation = await account_model_governance_service.write_account_model_evaluation(
        session,
        model_version=model_version,
        artifact_hash=payload.artifact_hash,
        evaluation_run_id=payload.evaluation_run_id,
        prediction_audits=payload.prediction_audits,
        evaluation_protocol=payload.evaluation_protocol,
        evaluation_manifest=payload.evaluation_manifest,
    )
    if evaluation is None:
        return success(data=None, msg="Account model version not found")
    return success(data=evaluation)


@router.post("/models/{model_version}/evaluation-jobs")
async def create_account_model_evaluation_job(
    model_version: str,
    payload: AccountModelEvaluationJobRequest,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles("admin")),
):
    """Create the normal system-owned frozen-holdout evaluation path."""

    job = await account_model_evaluation_service.create_account_model_evaluation_job(
        session,
        model_version=model_version,
        corpus_version_id=payload.corpus_version_id,
        evaluator_config=payload.evaluator_config,
        operator_id=int(current_user.id),
    )
    enqueue_account_model_evaluation_job(job["job_id"], task_id=job["task_id"])
    return success(data=job)


@router.get("/evaluation-jobs/{job_id}")
async def get_account_model_evaluation_job(
    job_id: str,
    session: AsyncSession = Depends(get_db),
    _current_user: User = Depends(require_roles("admin")),
):
    job = await account_model_evaluation_service.get_account_model_evaluation_job(session, job_id)
    if job is None:
        return success(data=None, msg="Account model evaluation job not found")
    return success(data=job)


@router.post("/models/{model_version}/activate")
async def activate_account_model(
    model_version: str,
    payload: AccountModelActivationRequest,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles("admin")),
):
    activated = await account_model_governance_service.activate_account_detection_model(
        session,
        model_version=model_version,
        operator_id=int(current_user.id),
        activation_notes=payload.activation_notes,
    )
    if not activated:
        return success(data=None, msg="Account model version not found")
    return success(data=activated)


@router.get("/models/active")
async def get_active_account_model_pointer(
    _current_user: User = Depends(get_current_user),
):
    pointer = await get_active_account_model()
    return success(
        data={
            "model_version": pointer.model_version,
            "artifact_uri": pointer.artifact_uri,
            "artifact_hash": pointer.artifact_hash,
            "data_fingerprint": pointer.data_fingerprint,
            "pointer_revision": pointer.pointer_revision,
            "source_schema": pointer.source_schema,
            "governance_status": pointer.governance_status,
            "research_approved": pointer.research_approved,
        }
        if pointer
        else None
    )


@router.post("/monitoring/snapshots")
async def create_account_monitoring_snapshot(
    window_hours: int = Query(24, ge=1, le=24 * 30),
    session: AsyncSession = Depends(get_db),
    _current_user: User = Depends(require_roles("admin")),
):
    """Persist an immutable monitoring aggregate for the active detector revision."""

    finished_at = datetime.now(timezone.utc).replace(tzinfo=None)
    snapshot = await account_model_monitoring_service.create_account_monitor_snapshot(
        session,
        window_started_at=finished_at - timedelta(hours=window_hours),
        window_finished_at=finished_at,
    )
    return success(data=snapshot)


@router.get("/monitoring")
async def list_account_monitoring_snapshots(
    limit: int = Query(20, ge=1, le=100),
    session: AsyncSession = Depends(get_db),
    _current_user: User = Depends(get_current_user),
):
    """Read recent model-version-bound monitoring snapshots."""

    snapshots = await account_model_monitoring_service.list_account_monitor_snapshots(session, limit=limit)
    return success(data=snapshots)


@router.post("/models/{model_version}/rollback")
async def rollback_account_model(
    model_version: str,
    payload: AccountModelRollbackRequest,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles("admin")),
):
    rolled_back = await account_model_governance_service.rollback_account_detection_model(
        session,
        model_version=model_version,
        operator_id=int(current_user.id),
        reason=payload.reason,
    )
    if rolled_back is None:
        return success(data=None, msg="Account model version not found")
    return success(data=rolled_back)
