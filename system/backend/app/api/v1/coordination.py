"""Coordination detection and CoordinationDiscover dataset model routes."""

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, Query, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_current_user
from app.db.mysql import get_db
from app.models.user import User
from app.schemas.coordination import CoordinationRunRequest
from app.services import coordination_service
from app.services.coordination_model_service import (
    create_coordination_run,
    get_coordination_community_detail,
    get_coordination_dataset_graph,
    get_coordination_dataset_detail,
    get_coordination_dataset_latest_result,
    get_coordination_run,
    list_coordination_datasets,
    run_coordination_model_job,
    upload_coordination_dataset,
)
from app.services.coordination_query_cache import (
    cached_coordination_query,
    clear_coordination_query_cache,
)
from app.utils.response import success

router = APIRouter()


def clear_coordination_response_cache() -> None:
    clear_coordination_query_cache()


@router.post("/detect")
async def run_detection(
    time_window: int = Query(60, ge=1, le=3600, description="时间窗口（秒）"),
    min_participation: int = Query(2, ge=1, description="最低参与次数"),
    edge_weight: float = Query(0.5, ge=0, le=1, description="边权阈值百分位"),
    platform: str | None = Query(None, description="限定平台"),
    event_id: str | None = Query(None, description="限定事件 ID"),
    _current_user: User = Depends(get_current_user),
):
    result = await coordination_service.run_coordination_detection(
        time_window=time_window,
        min_participation=min_participation,
        edge_weight=edge_weight,
        platform=platform,
        event_id=event_id,
    )
    return success(data=result)


@router.get("/datasets")
async def list_registered_datasets(
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(get_current_user),
):
    cache_key = ("datasets",)
    data = await cached_coordination_query(cache_key, lambda: list_coordination_datasets(db))
    return success(data=data)


@router.post("/datasets/upload")
async def upload_dataset(
    file: UploadFile = File(...),
    display_name: str | None = Form(default=None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    payload = await file.read()
    result = await upload_coordination_dataset(
        db=db,
        filename=file.filename or "dataset.csv",
        content=payload,
        created_by=current_user.id,
        display_name=display_name,
    )
    clear_coordination_response_cache()
    return success(data=result)


@router.get("/datasets/{dataset_id}/graph")
async def get_dataset_graph(
    dataset_id: int,
    node_limit: int = Query(200, ge=0, le=50000),
    min_node_score: float = Query(0.0, ge=0.0, le=1.0),
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(get_current_user),
):
    cache_key = ("graph", int(dataset_id), int(node_limit), round(float(min_node_score), 6))
    data = await cached_coordination_query(
        cache_key,
        lambda: get_coordination_dataset_graph(
            db,
            dataset_id,
            node_limit=node_limit,
            min_node_score=min_node_score,
        ),
    )
    return success(data=data)


@router.get("/datasets/{dataset_id}/communities/{cluster_id}")
async def get_dataset_community_detail(
    dataset_id: int,
    cluster_id: str,
    member_limit: int = Query(500, ge=1, le=2000),
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(get_current_user),
):
    return success(
        data=await get_coordination_community_detail(
            db,
            dataset_id,
            cluster_id,
            member_limit=member_limit,
        )
    )


@router.get("/datasets/{dataset_id}")
async def get_dataset_detail(
    dataset_id: int,
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(get_current_user),
):
    cache_key = ("detail", int(dataset_id))
    data = await cached_coordination_query(cache_key, lambda: get_coordination_dataset_detail(db, dataset_id))
    return success(data=data)


@router.get("/datasets/{dataset_id}/latest-result")
async def get_dataset_latest_result(
    dataset_id: int,
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(get_current_user),
):
    cache_key = ("latest", int(dataset_id))
    data = await cached_coordination_query(
        cache_key,
        lambda: get_coordination_dataset_latest_result(db, dataset_id),
    )
    return success(data=data)


@router.post("/runs")
async def create_run(
    body: CoordinationRunRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    clear_coordination_response_cache()
    run = await create_coordination_run(db=db, dataset_id=body.dataset_id, created_by=current_user.id)
    background_tasks.add_task(run_coordination_model_job, int(run["run_id"]))
    return success(data=run)


@router.get("/runs/{run_id}")
async def get_run(
    run_id: int,
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(get_current_user),
):
    return success(data=await get_coordination_run(db, run_id))
