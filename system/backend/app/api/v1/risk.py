"""风险研判相关 API 路由。"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_current_user
from app.core.risk.kt3_gate_dataset import get_kt3_gate_dataset_contract_spec
from app.core.risk.kt3_gate_dataset import validate_kt3_gate_dataset_contract
from app.db.mysql import get_db
from app.models.user import User
from app.schemas.risk import KT3AgentReviewRunRequest
from app.schemas.risk import KT3AgentFeedbackRequest
from app.schemas.risk import KT3GateDatasetValidationRequest
from app.schemas.risk import KT3GateSuiteRequest
from app.schemas.risk import KT3PolicyOptimizeRequest
from app.schemas.risk import KT3PolicyRefineRequest
from app.services import risk_service
from app.utils.response import success

router = APIRouter()


@router.post("/assess")
async def assess_risk(
    platform: str | None = Query(None, description="限定平台"),
    event_id: str | None = Query(None, description="限定事件 ID"),
    time_window: int = Query(60, ge=1, le=3600, description="协同检测时间窗口（秒）"),
    min_participation: int = Query(2, ge=1, description="最低参与次数"),
    edge_weight: float = Query(0.5, ge=0, le=1, description="边权百分位阈值"),
    run_legacy_multi_agent: bool = Query(False, description="Run legacy deterministic KT3 multi-agent runtime"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """执行风险评估：阶段检测 + D-S 融合 + DISARM 攻击路径分析。"""
    legacy_multi_agent = getattr(run_legacy_multi_agent, "default", run_legacy_multi_agent)
    report = await risk_service.assess_risk(
        platform=platform,
        event_id=event_id,
        time_window=time_window,
        min_participation=min_participation,
        edge_weight=edge_weight,
        run_legacy_multi_agent=bool(legacy_multi_agent),
        user_id=current_user.id,
        db=db,
    )
    return success(data=report)


@router.post("/kt3/gate-suite")
async def assess_kt3_gate_suite(
    request: KT3GateSuiteRequest,
    current_user: User = Depends(get_current_user),
):
    """执行 KT3 三层 Gate Suite 离线评测，不持久化 gold/control 评测报告。"""
    report = await risk_service.assess_risk(
        platform=request.platform,
        event_id=request.event_id,
        time_window=request.time_window,
        min_participation=request.min_participation,
        edge_weight=request.edge_weight,
        user_id=current_user.id,
        db=None,
        kt3_gate_dataset=request.kt3_gate_dataset,
    )
    kt3_harmfulness = report.get("kt3_harmfulness") or {}
    return success(
        data={
            "report_context": {
                "report_id": report.get("report_id"),
                "event_id": report.get("event_id"),
                "platform": report.get("platform"),
                "assessed_at": report.get("assessed_at"),
                "risk_level": (report.get("scores") or {}).get("risk_level"),
            },
            "post_semantics": report.get("post_semantics"),
            "kt3_harmfulness": kt3_harmfulness,
            "gate_suite": kt3_harmfulness.get("gate_suite"),
            "persistence": {
                "persisted": False,
                "reason": "KT3 Gate Suite may contain gold labels and is returned for offline evaluation only.",
            },
        }
    )


@router.get("/kt3/gate-dataset/contract")
async def get_kt3_gate_dataset_contract(
    _current_user: User = Depends(get_current_user),
):
    """Return the machine-readable KT3 Gate Dataset contract."""
    return success(data=get_kt3_gate_dataset_contract_spec())


@router.post("/kt3/gate-dataset/validate")
async def validate_kt3_gate_dataset(
    request: KT3GateDatasetValidationRequest,
    _current_user: User = Depends(get_current_user),
):
    """Validate a KT3 Gate Dataset without running risk assessment or persistence."""
    return success(data=validate_kt3_gate_dataset_contract(request.kt3_gate_dataset))


@router.post("/kt3/agent-reviews/run")
async def run_kt3_agent_review(
    request: KT3AgentReviewRunRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Run analyst-triggered MARO-style KT3 LLM agent reports."""
    try:
        result = await risk_service.run_kt3_agent_review(
            report_id=request.report_id,
            agent_names=request.agent_names,
            case_id=request.case_id,
            selected_post_ids=request.selected_post_ids,
            selected_tree_ids=request.selected_tree_ids,
            enable_active_retrieval=request.enable_active_retrieval,
            enable_light_debate=request.enable_light_debate,
            enable_full_debate=request.enable_full_debate,
            debate_max_rounds=request.debate_max_rounds,
            policy_id=request.policy_id,
            active_policy_id=request.active_policy_id,
            retrieval_top_k=request.retrieval_top_k,
            user_id=current_user.id,
            db=db,
        )
    except ValueError as exc:
        detail = str(exc)
        status_code = 404 if "not found" in detail else 400
        raise HTTPException(status_code=status_code, detail=detail) from exc
    return success(data=result)


@router.post("/kt3/agent-feedback/record")
async def record_kt3_agent_feedback(
    request: KT3AgentFeedbackRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Record human audit feedback for the next KT3 policy refinement loop."""
    try:
        result = await risk_service.record_kt3_agent_feedback(
            report_id=request.report_id,
            feedback=request.model_dump(),
            user_id=current_user.id,
            db=db,
        )
    except ValueError as exc:
        detail = str(exc)
        status_code = 404 if "not found" in detail else 400
        raise HTTPException(status_code=status_code, detail=detail) from exc
    return success(data=result)


@router.post("/kt3/policies/optimize")
async def optimize_kt3_policy(
    request: KT3PolicyOptimizeRequest,
    _current_user: User = Depends(get_current_user),
):
    """Optimize a KT3 MARO-style Agent review policy from an explicit validation split."""
    try:
        result = risk_service.optimize_kt3_policy(request.dataset_manifest)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return success(data=result)


@router.post("/kt3/policies/refine")
async def refine_kt3_policy(
    request: KT3PolicyRefineRequest,
    _current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Run MARO-style rule refinement and store a human-approval candidate policy."""
    try:
        result = await risk_service.refine_kt3_policy(
            dataset_manifest=request.dataset_manifest,
            feedback_report_ids=request.feedback_report_ids,
            baseline_policy_id=request.baseline_policy_id,
            max_iterations=request.max_iterations,
            enable_llm_rule_generator=request.enable_llm_rule_generator,
            held_out_required=request.held_out_required,
            db=db,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return success(data=result)


@router.post("/kt3/policies/{policy_id}/activate")
async def activate_kt3_policy(
    policy_id: str,
    current_user: User = Depends(get_current_user),
):
    """Explicitly activate a KT3 policy for later manual Agent/Judge context."""
    try:
        result = risk_service.activate_kt3_policy(policy_id, user_id=current_user.id)
    except ValueError as exc:
        detail = str(exc)
        status_code = 404 if "not found" in detail else 400
        raise HTTPException(status_code=status_code, detail=detail) from exc
    return success(data=result)


@router.get("/kt3/policies/{policy_id}")
async def get_kt3_policy(
    policy_id: str,
    _current_user: User = Depends(get_current_user),
):
    """Return an auditable KT3 Agent review policy artifact."""
    result = risk_service.get_kt3_policy(policy_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"KT3 policy not found: {policy_id}")
    return success(data=result)


@router.get("/reports")
async def list_reports(
    platform: str | None = Query(None),
    event_id: str | None = Query(None),
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
        event_id=event_id,
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
