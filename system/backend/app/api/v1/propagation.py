"""传播归因与趋势预测 API 路由。"""

from fastapi import APIRouter, Depends, Query

from app.core.security import get_current_user_or_local_preview
from app.models.user import User
from app.services import propagation_prediction_service, propagation_service
from app.utils.response import success

router = APIRouter()


@router.get("/analyze")
async def analyze(
    platform: str | None = Query(None, description="限定平台"),
    event_id: str | None = Query(None, description="限定事件 ID"),
    node_limit: int = Query(300, ge=0, description="传播路径图节点数量；0 表示全量"),
    _current_user: User | None = Depends(get_current_user_or_local_preview),
):
    result = await propagation_service.analyze_propagation(
        platform=platform,
        event_id=event_id,
        node_limit=node_limit,
    )
    return success(data=result)


@router.post("/predict-trend")
async def predict_trend(
    platform: str | None = Query(None, description="限定平台"),
    event_id: str | None = Query(None, description="限定事件 ID"),
    _current_user: User | None = Depends(get_current_user_or_local_preview),
):
    """预测传播趋势（CascadeSwitch）。"""
    result = await propagation_service.predict_propagation_trend(platform=platform, event_id=event_id)
    return success(data=result)


@router.post("/model-event-predict")
async def predict_model_event(
    platform: str | None = Query(None, description="限定平台"),
    event_id: str | None = Query(None, description="限定事件 ID"),
    top_k: int = Query(10, ge=1, le=50, description="下一跳 Top-K 数量"),
    _current_user: User | None = Depends(get_current_user_or_local_preview),
):
    """使用本地 Twitter checkpoint 对当前事件数据进行规模趋势与下一跳预测。"""
    result = await propagation_service.predict_propagation_model_event(
        platform=platform,
        event_id=event_id,
        top_k=top_k,
    )
    return success(data=result)


@router.post("/model-predict")
async def predict_macro_micro_model(
    dataset: str = Query("twitter", description="实验数据集：twitter / douban / memetracker"),
    seed: int | None = Query(42, description="实验随机种子；为空时聚合该数据集全部可用种子"),
    run_live: bool = Query(False, description="是否触发本地 small-run；默认读取缓存实验结果"),
    _current_user: User | None = Depends(get_current_user_or_local_preview),
):
    """读取传播规模预测与下一跳预测的联合模型结果。"""
    result = await propagation_prediction_service.predict_propagation_analysis_macro_micro(
        dataset=dataset,
        seed=seed,
        run_live=run_live,
    )
    public_result = {
        "status": result.get("status"),
        "task": result.get("task", "multi_scale"),
        "dataset": result.get("dataset", dataset),
        "seed": result.get("seed", seed),
        "source": result.get("source"),
        "model_display_name": "Ours",
        "label": "实验预测",
        "is_experimental": bool(result.get("is_experimental", True)),
        "evidence_level": result.get("evidence_level"),
        "full_validation_passed": bool(result.get("full_validation_passed", False)),
        "macro": result.get("macro") or {},
        "micro": result.get("micro") or {},
        "candidate_protocol_audit": result.get("candidate_protocol_audit") or {},
    }
    if result.get("note"):
        public_result["note"] = result.get("note")
    return success(data=public_result)


@router.post("/propagation_analysis-predict")
async def predict_propagation_analysis_macro_micro(
    dataset: str = Query("twitter", description="PropagationAnalysis 实验数据集：twitter / douban / memetracker"),
    seed: int | None = Query(42, description="实验随机种子；为空时聚合该数据集全部可用种子"),
    run_live: bool = Query(False, description="是否触发本地 small-run；默认读取缓存实验结果"),
    _current_user: User | None = Depends(get_current_user_or_local_preview),
):
    """读取 PropagationAnalysis 规模预测/下一跳预测联合模型实验结果。"""
    result = await propagation_prediction_service.predict_propagation_analysis_macro_micro(
        dataset=dataset,
        seed=seed,
        run_live=run_live,
    )
    return success(data=result)
