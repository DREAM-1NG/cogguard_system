"""风险研判相关 API 路由。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.core.security import get_current_user
from app.models.user import User
from app.schemas.risk import RiskAssessRequest
from app.services import risk_service
from app.utils.response import success

router = APIRouter()


@router.post("/assess")
async def assess(
    req: RiskAssessRequest,
    _current_user: User = Depends(get_current_user),
):
    result = await risk_service.assess_risk(req)
    if result.get("error"):
        return success(data=None, msg=result["error"])
    return success(data=result)


@router.get("/reports")
async def list_history(
    platform: str | None = Query(None),
    limit: int = Query(20, ge=1, le=100),
    _current_user: User = Depends(get_current_user),
):
    reports = await risk_service.list_reports(platform=platform, limit=limit)
    return success(data=reports)


@router.get("/reports/{report_id}")
async def get_history(
    report_id: str,
    _current_user: User = Depends(get_current_user),
):
    report = await risk_service.get_report(report_id)
    if not report:
        return success(data=None, msg="报告不存在")
    return success(data=report)
