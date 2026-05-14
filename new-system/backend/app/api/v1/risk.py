"""风险研判相关 API 路由。"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_current_user
from app.db.mysql import get_db
from app.models.user import User
from app.services import risk_service
from app.utils.response import success

router = APIRouter()


@router.post("/assess")
async def assess_risk(
    platform: str | None = Query(None, description="限定平台"),
    time_window: int = Query(60, ge=1, le=3600, description="协同检测时间窗口（秒）"),
    min_participation: int = Query(2, ge=1, description="最低参与次数"),
    edge_weight: float = Query(0.5, ge=0, le=1, description="边权百分位阈值"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """执行风险评估：阶段检测 + D-S 融合 + DISARM 攻击路径分析。"""
    report = await risk_service.assess_risk(
        platform=platform,
        time_window=time_window,
        min_participation=min_participation,
        edge_weight=edge_weight,
        user_id=current_user.id,
        db=db,
    )
    return success(data=report)


@router.get("/reports")
async def list_reports(
    platform: str | None = Query(None),
    risk_level: str | None = Query(None),
    phase: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    _current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """查询历史风险报告列表。"""
    items, total = await risk_service.list_reports(
        platform=platform,
        risk_level=risk_level,
        phase=phase,
        page=page,
        page_size=page_size,
        db=db,
    )
    return success(data={"total": total, "items": items})


@router.get("/reports/{report_id}")
async def get_report_detail(
    report_id: str,
    _current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取单个风险报告详情。"""
    report = await risk_service.get_report_detail(report_id, db)
    if report is None:
        return success(data=None, msg="报告不存在")
    return success(data=report)
