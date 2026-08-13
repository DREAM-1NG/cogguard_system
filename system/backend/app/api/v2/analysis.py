from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.analysis.executor import AnalysisExecutor, default_analysis_engine_ports
from app.core.analysis.registry import (
    RUN_ARTIFACT_COLLECTION,
    AnalysisRegistry,
    SqlAlchemyAnalysisStore,
)
from app.core.analysis.sse import iter_sse_events, parse_last_event_id
from app.core.security import require_roles
from app.db.mongodb import get_mongo_db
from app.db.mysql import get_db
from app.models.user import User
from app.schemas.analysis import (
    AnalysisRunCreateRequest,
    AnalysisSnapshotCreateRequest,
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
execution_router = APIRouter()
product_router = APIRouter()

SEMANTIC_ARTIFACT_KEY = "stage:semantic_enrichment:result"


def get_analysis_registry(
    db: AsyncSession = Depends(get_db),
    mongo_db: Any = Depends(get_mongo_db),
) -> AnalysisRegistry:
    return AnalysisRegistry(mongo_db=mongo_db, store=SqlAlchemyAnalysisStore(db))


def get_analysis_executor(
    registry: AnalysisRegistry = Depends(get_analysis_registry),
) -> AnalysisExecutor:
    return AnalysisExecutor(registry=registry, engines=default_analysis_engine_ports())


@execution_router.post("/snapshots")
async def create_snapshot(
    body: AnalysisSnapshotCreateRequest,
    registry: AnalysisRegistry = Depends(get_analysis_registry),
    current_user: User = Depends(require_roles("admin", "analyst")),
):
    try:
        snapshot = await registry.create_event_snapshot(
            event_id=body.event_id,
            core_window=body.core_window,
            context_window=body.context_window,
            platform=body.platform,
            created_by=int(current_user.id),
        )
    except (KeyError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return success(data=snapshot.model_dump(mode="json"))


@execution_router.post("/runs")
async def create_run(
    body: AnalysisRunCreateRequest,
    registry: AnalysisRegistry = Depends(get_analysis_registry),
    current_user: User = Depends(require_roles("admin", "analyst")),
):
    return success(
        data=await registry.create_run(
            event_id=body.event_id,
            snapshot_id=body.snapshot_id,
            requested_stages=body.requested_stages,
            options=body.options,
            created_by=int(current_user.id),
        )
    )


@execution_router.post("/runs/{run_id}/execute")
async def execute_run(
    run_id: str,
    executor: AnalysisExecutor = Depends(get_analysis_executor),
    _current_user: User = Depends(require_roles("admin", "analyst")),
):
    try:
        return success(data=await executor.execute_run(run_id))
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


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


@router.get("/runs/{run_id}/artifacts/{artifact_key:path}")
@product_router.get("/runs/{run_id}/artifacts/{artifact_key:path}")
async def get_run_artifact(
    run_id: str,
    artifact_key: str,
    registry: AnalysisRegistry = Depends(get_analysis_registry),
    _current_user: User = Depends(require_roles("admin", "analyst")),
):
    try:
        payload = await registry.load_run_artifact(run_id, artifact_key)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return success(data=payload)


@product_router.get("/events/{event_id}/semantic")
async def get_event_semantic_projection(
    event_id: str,
    registry: AnalysisRegistry = Depends(get_analysis_registry),
    _current_user: User = Depends(require_roles("admin", "analyst")),
):
    return success(data=await _event_semantic_projection(event_id, registry))


async def _event_semantic_projection(event_id: str, registry: AnalysisRegistry) -> dict[str, Any]:
    candidates, lookup_reason = await _semantic_artifact_runs(event_id, registry)
    if lookup_reason:
        return _semantic_projection(
            event_id=event_id,
            status="blocked",
            blocking_reason=lookup_reason,
        )
    if not candidates:
        return _semantic_projection(
            event_id=event_id,
            status="not_found",
            blocking_reason="semantic_artifact_not_found",
        )

    blocked: dict[str, Any] | None = None
    for run in candidates:
        run_id = str(run.get("run_id") or "")
        snapshot_id = _optional_text(run.get("snapshot_id"))
        try:
            artifact = await registry.load_run_artifact(run_id, SEMANTIC_ARTIFACT_KEY)
        except ValueError as exc:
            reason = (
                "semantic_artifact_integrity_failed"
                if "hash mismatch" in str(exc).lower()
                else "semantic_artifact_load_failed"
            )
        except KeyError:
            reason = "semantic_artifact_not_found"
        except Exception:
            reason = "semantic_artifact_load_failed"
        else:
            if _is_ready_semantic_artifact(artifact):
                return _semantic_projection(
                    event_id=event_id,
                    run_id=run_id,
                    snapshot_id=snapshot_id,
                    status="ready",
                    blocking_reason=None,
                    artifact=artifact,
                )
            payload = artifact if isinstance(artifact, dict) else {}
            reason = _optional_text(payload.get("blocking_reason")) or "semantic_artifact_not_ready"

        if blocked is None:
            blocked = _semantic_projection(
                event_id=event_id,
                run_id=run_id,
                snapshot_id=snapshot_id,
                status="blocked",
                blocking_reason=reason,
            )

    return blocked or _semantic_projection(
        event_id=event_id,
        status="not_found",
        blocking_reason="semantic_artifact_not_found",
    )


async def _semantic_artifact_runs(
    event_id: str,
    registry: AnalysisRegistry,
) -> tuple[list[dict[str, Any]], str | None]:
    try:
        collection = registry.mongo_db[RUN_ARTIFACT_COLLECTION]
        cursor = collection.find(
            {"artifact_key": SEMANTIC_ARTIFACT_KEY},
            {"_id": 0, "run_id": 1, "created_at": 1},
        )
        sorter = getattr(cursor, "sort", None)
        if sorter is not None:
            cursor = sorter("created_at", -1)
        artifacts = await cursor.to_list(length=None)
    except Exception:
        return [], "semantic_artifact_lookup_failed"

    candidates: list[tuple[dict[str, Any], str]] = []
    for artifact in artifacts:
        run_id = _optional_text(artifact.get("run_id")) if isinstance(artifact, dict) else None
        if not run_id:
            continue
        try:
            run = await registry.get_run(run_id)
        except Exception:
            return [], "semantic_artifact_lookup_failed"
        if run is not None and str(run.get("event_id") or "") == event_id:
            candidates.append((run, _optional_text(artifact.get("created_at")) or ""))
    candidates.sort(
        key=lambda candidate: (
            str(candidate[0].get("created_at") or ""),
            candidate[1],
            str(candidate[0].get("run_id") or ""),
        ),
        reverse=True,
    )
    return [run for run, _artifact_created_at in candidates], None


def _semantic_projection(
    *,
    event_id: str,
    status: str,
    blocking_reason: str | None,
    run_id: str | None = None,
    snapshot_id: str | None = None,
    artifact: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "event_id": event_id,
        "run_id": run_id,
        "snapshot_id": snapshot_id,
        "status": status,
        "blocking_reason": blocking_reason,
        "artifact": artifact,
    }


def _is_ready_semantic_artifact(artifact: Any) -> bool:
    return (
        isinstance(artifact, dict)
        and artifact.get("technology") == "semantic_enrichment"
        and artifact.get("status") == "ok"
        and artifact.get("runtime_status") == "ready"
        and not artifact.get("fallback")
    )


def _optional_text(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None


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
