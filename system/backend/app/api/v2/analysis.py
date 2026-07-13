from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.analysis import InvalidRunTransition
from app.core.analysis.executor import AnalysisExecutor, default_analysis_engine_ports
from app.core.analysis.registry import AnalysisRegistry, SqlAlchemyAnalysisStore
from app.core.analysis.sse import iter_sse_events, parse_last_event_id
from app.core.security import get_current_user_or_local_preview
from app.db.mongodb import get_mongo_db
from app.db.mysql import get_db
from app.models.user import User
from app.schemas.analysis import (
    AnalysisRunCreateRequest,
    AnalysisRunStatusUpdateRequest,
    AnalysisSnapshotCreateRequest,
)
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


@router.post("/snapshots")
async def create_snapshot(
    body: AnalysisSnapshotCreateRequest,
    registry: AnalysisRegistry = Depends(get_analysis_registry),
    current_user: User | None = Depends(get_current_user_or_local_preview),
):
    snapshot = await registry.create_event_snapshot(
        event_id=body.event_id,
        core_window=body.core_window,
        context_window=body.context_window,
        platform=body.platform,
        created_by=_user_id(current_user),
    )
    return success(data=_jsonable(snapshot))


@router.post("/runs")
async def create_run(
    body: AnalysisRunCreateRequest,
    registry: AnalysisRegistry = Depends(get_analysis_registry),
    current_user: User | None = Depends(get_current_user_or_local_preview),
):
    run = await registry.create_run(
        event_id=body.event_id,
        snapshot_id=body.snapshot_id,
        requested_stages=body.requested_stages,
        options=body.options,
        created_by=_user_id(current_user),
    )
    return success(data=run)


@router.post("/runs/{run_id}/execute")
async def execute_run(
    run_id: str,
    executor: AnalysisExecutor = Depends(get_analysis_executor),
    _current_user: User | None = Depends(get_current_user_or_local_preview),
):
    try:
        run = await executor.execute_run(run_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except InvalidRunTransition as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return success(data=run)


@router.get("/runs/{run_id}")
async def get_run(
    run_id: str,
    registry: AnalysisRegistry = Depends(get_analysis_registry),
    _current_user: User | None = Depends(get_current_user_or_local_preview),
):
    run = await registry.get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Analysis run not found")
    return success(data=run)


@router.patch("/runs/{run_id}/status")
async def update_run_status(
    run_id: str,
    body: AnalysisRunStatusUpdateRequest,
    registry: AnalysisRegistry = Depends(get_analysis_registry),
    _current_user: User | None = Depends(get_current_user_or_local_preview),
):
    try:
        run = await registry.transition_run_status(
            run_id,
            body.status,
            payload=body.payload,
            event_type=body.event_type,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except InvalidRunTransition as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return success(data=run)


@router.get("/runs/{run_id}/events")
async def list_run_events(
    run_id: str,
    after_id: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    registry: AnalysisRegistry = Depends(get_analysis_registry),
    _current_user: User | None = Depends(get_current_user_or_local_preview),
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
    _current_user: User | None = Depends(get_current_user_or_local_preview),
):
    cursor = parse_last_event_id(last_event_id, fallback=after_id)
    events = await registry.list_run_events(run_id, after_id=cursor, limit=limit)
    return StreamingResponse(
        iter_sse_events(events),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache"},
    )


def _jsonable(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    return value


def _user_id(user: User | None) -> int:
    return int(getattr(user, "id", 0) or 0)
