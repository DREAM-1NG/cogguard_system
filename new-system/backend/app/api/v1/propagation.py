"""传播归因与趋势预测 API 路由。"""

from fastapi import APIRouter, Depends, Query

from app.core.security import get_current_user
from app.models.user import User
from app.services import propagation_service
from app.utils.response import success

router = APIRouter()


@router.get("/analyze")
async def analyze(
    platform: str | None = Query(None),
    _current_user: User = Depends(get_current_user),
):
    result = await propagation_service.analyze_propagation(platform)
    return success(data=result)


@router.post("/predict-trend")
async def predict_trend(
    platform: str | None = Query(None),
    _current_user: User = Depends(get_current_user),
):
    """预测传播趋势（CascadeSwitch）。"""
    result = await propagation_service.predict_propagation_trend(platform)
    return success(data=result)
