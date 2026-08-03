from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.analysis.executor import AnalysisExecutor, default_analysis_engine_ports
from app.core.analysis.registry import AnalysisRegistry, SqlAlchemyAnalysisStore
from app.core.analysis.sse import iter_sse_events, parse_last_event_id
from app.core.security import require_roles
from app.db.mongodb import get_mongo_db
from app.db.mysql import get_db
from app.models.user import User
from app.schemas.analysis import (
    CanonicalVerdictApprovalRequest,
    ModelActivationRequest,
    ModelCandidateApprovalRequest,
    ModelRollbackRequest,
    ModelVersionCreateRequest,
    ReviewFeedbackCreateRequest,
)
from app.services import analysis_governance_service
from app.utils.response import success

router = APIRouter()


def get_analysis_registry(
    db: AsyncSession = Depends(get_db),
    mongo_db: Any = Depends(get_mongo_db),
) -> AnalysisRegistry:
    return AnalysisRegistry(mongo_db=mongo_db, store=SqlAlchemyAnalysisStore(db))


def get_analysis_executor(
    registry: AnalysisRegistry = Depends(get_analysis_registry),
) -> AnalysisExecutor:
    return AnalysisExecutor(registry=registry, engines=default_analysis_engine_ports())


@router.get("/runs/{run_id}")
async def get_run(
    run_id: str,
    registry: AnalysisRegistry = Depends(get_analysis_registry),
    _current_user: User = Depends(require_roles("admin")),
):
    run = await registry.get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Analysis run not found")
    return success(data=run)


@router.get("/runs/{run_id}/events")
async def list_run_events(
    run_id: str,
    after_id: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    registry: AnalysisRegistry = Depends(get_analysis_registry),
    _current_user: User = Depends(require_roles("admin")),
):
    events = await registry.list_run_events(run_id, after_id=after_id, limit=limit)
    return success(data={"run_id": run_id, "after_id": after_id, "events": events})


@router.get("/runs/{run_id}/events/stream")
async def stream_run_events(
    run_id: str,
    last_event_id: str | None = Header(default=None, alias="Last-Event-ID"),
    after_id: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    registry: AnalysisRegistry = Depends(get_analysis_registry),
    _current_user: User = Depends(require_roles("admin")),
):
    cursor = parse_last_event_id(last_event_id, fallback=after_id)
    events = await registry.list_run_events(run_id, after_id=cursor, limit=limit)
    return StreamingResponse(
        iter_sse_events(events),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache"},
    )


@router.post("/runs/{run_id}/verdicts/{verdict_id}/approve")
async def approve_verdict(
    run_id: str,
    verdict_id: str,
    body: CanonicalVerdictApprovalRequest,
    current_user: User = Depends(require_roles("admin", "analyst")),
    db: AsyncSession = Depends(get_db),
):
    try:
        result = await analysis_governance_service.approve_run_verdict(
            run_id=run_id,
            verdict_id=verdict_id,
            approved_by=int(current_user.id),
            approval_notes=body.approval_notes,
            db=db,
        )
        await db.commit()
    except ValueError as exc:
        detail = str(exc)
        raise HTTPException(status_code=404 if "not found" in detail else 400, detail=detail) from exc
    return success(data=result)


@router.post("/runs/{run_id}/feedback")
async def record_feedback(
    run_id: str,
    body: ReviewFeedbackCreateRequest,
    current_user: User = Depends(require_roles("admin", "analyst")),
    db: AsyncSession = Depends(get_db),
):
    if body.run_id != run_id:
        raise HTTPException(status_code=400, detail="Feedback run_id does not match the URL")
    try:
        result = await analysis_governance_service.create_feedback(
            run_id=run_id,
            snapshot_id=body.snapshot_id,
            verdict_id=body.verdict_id,
            feedback=body.feedback,
            created_by=int(current_user.id),
            db=db,
        )
        await db.commit()
    except ValueError as exc:
        detail = str(exc)
        raise HTTPException(status_code=404 if "not found" in detail else 400, detail=detail) from exc
    return success(data=result)


@router.post("/models")
async def register_model(
    body: ModelVersionCreateRequest,
    current_user: User = Depends(require_roles("admin")),
    db: AsyncSession = Depends(get_db),
):
    try:
        result = await analysis_governance_service.register_model_version(
            payload=body.model_dump(),
            created_by=int(current_user.id),
            db=db,
        )
        await db.commit()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return success(data=result)


@router.post("/models/{model_version_id}/activate")
async def activate_model(
    model_version_id: int,
    body: ModelActivationRequest,
    current_user: User = Depends(require_roles("admin")),
    db: AsyncSession = Depends(get_db),
):
    try:
        result = await analysis_governance_service.activate_model_version(
            model_version_id=model_version_id,
            operator_id=int(current_user.id),
            reason=body.reason,
            db=db,
        )
        await db.commit()
    except ValueError as exc:
        detail = str(exc)
        raise HTTPException(status_code=404 if "not found" in detail else 400, detail=detail) from exc
    return success(data=result)


@router.post("/models/{model_version_id}/approvals")
async def approve_model_candidate(
    model_version_id: int,
    body: ModelCandidateApprovalRequest,
    current_user: User = Depends(require_roles("admin")),
    db: AsyncSession = Depends(get_db),
):
    try:
        result = await analysis_governance_service.approve_model_candidate(
            model_version_id=model_version_id,
            approved_by=int(current_user.id),
            approval_notes=body.approval_notes,
            db=db,
        )
        await db.commit()
    except ValueError as exc:
        detail = str(exc)
        raise HTTPException(status_code=404 if "not found" in detail else 400, detail=detail) from exc
    return success(data=result)


@router.post("/models/{technology}/rollback")
async def rollback_model(
    technology: str,
    body: ModelRollbackRequest,
    current_user: User = Depends(require_roles("admin")),
    db: AsyncSession = Depends(get_db),
):
    try:
        result = await analysis_governance_service.rollback_model_version(
            technology=technology,
            reason=body.reason,
            requested_by=int(current_user.id),
            target_model_version_id=body.target_model_version_id,
            db=db,
        )
        await db.commit()
    except ValueError as exc:
        detail = str(exc)
        raise HTTPException(status_code=404 if "not found" in detail else 400, detail=detail) from exc
    return success(data=result)


@router.get("/models/{technology}/history")
async def model_governance_history(
    technology: str,
    limit: int = Query(100, ge=1, le=1000),
    _current_user: User = Depends(require_roles("admin")),
    db: AsyncSession = Depends(get_db),
):
    result = await analysis_governance_service.list_model_governance_history(
        technology=technology,
        db=db,
        limit=limit,
    )
    return success(data={"items": result, "total": len(result)})
