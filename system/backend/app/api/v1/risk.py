"""风险研判相关 API 路由。"""

import inspect
import json

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_current_user, require_roles
from app.core.risk.kt3_gate_dataset import get_kt3_gate_dataset_contract_spec
from app.core.risk.kt3_gate_dataset import validate_kt3_gate_dataset_contract
from app.db.mysql import get_db
from app.models.user import User
from app.schemas.risk import KT3AgentReviewRunRequest
from app.schemas.risk import KT3AgentFeedbackRequest
from app.schemas.risk import KT3BackfillRequest
from app.schemas.risk import KT3GateDatasetUploadRequest
from app.schemas.risk import KT3GateDatasetValidationRequest
from app.schemas.risk import KT3GateSuiteRequest
from app.schemas.risk import KT3ProviderActivateRequest
from app.schemas.risk import KT3ProviderConfigRequest
from app.schemas.risk import KT3ProviderUpdateRequest
from app.schemas.risk import KT3PolicyOptimizeRequest
from app.schemas.risk import KT3PolicyRefineRequest
from app.services import kt3_system_service
from app.services import risk_service
from app.utils.response import success

router = APIRouter()


async def _commit_if_supported(db: AsyncSession) -> None:
    commit = getattr(db, "commit", None)
    if commit is None:
        return
    result = commit()
    if inspect.isawaitable(result):
        await result


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


@router.post("/kt3/gate-datasets/upload")
async def upload_kt3_gate_dataset_file(
    file: UploadFile = File(...),
    current_user: User = Depends(require_roles("admin")),
    db: AsyncSession = Depends(get_db),
):
    """Upload and persist a KT3 Gate Dataset JSON file."""
    try:
        payload = json.loads((await file.read()).decode("utf-8"))
        result = await kt3_system_service.persist_gate_dataset_upload(
            dataset=payload,
            uploaded_by=current_user.id,
            db=db,
        )
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail=f"invalid JSON file: {exc}") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return success(data=result)


@router.post("/kt3/gate-datasets")
async def upload_kt3_gate_dataset_json(
    request: KT3GateDatasetUploadRequest,
    current_user: User = Depends(require_roles("admin")),
    db: AsyncSession = Depends(get_db),
):
    """Persist a KT3 Gate Dataset from a JSON request body."""
    result = await kt3_system_service.persist_gate_dataset_upload(
        dataset=request.kt3_gate_dataset,
        uploaded_by=current_user.id,
        db=db,
    )
    return success(data=result)


@router.get("/kt3/gate-datasets")
async def list_kt3_gate_datasets(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    _current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return success(data=await kt3_system_service.list_gate_datasets(db, page=page, page_size=page_size))


@router.get("/kt3/gate-datasets/{dataset_db_id}")
async def get_kt3_gate_dataset_detail(
    dataset_db_id: int,
    _current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await kt3_system_service.get_gate_dataset_detail(dataset_db_id, db)
    if result is None:
        raise HTTPException(status_code=404, detail=f"KT3 Gate Dataset not found: {dataset_db_id}")
    return success(data=result)


@router.get("/kt3/providers")
async def list_kt3_providers(
    _current_user: User = Depends(require_roles("admin")),
    db: AsyncSession = Depends(get_db),
):
    return success(data=await kt3_system_service.list_provider_configs(db))


@router.post("/kt3/providers")
async def create_kt3_provider(
    request: KT3ProviderConfigRequest,
    current_user: User = Depends(require_roles("admin")),
    db: AsyncSession = Depends(get_db),
):
    try:
        result = await kt3_system_service.create_provider_config(
            payload=request.model_dump(),
            user_id=current_user.id,
            db=db,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return success(data=result)


@router.put("/kt3/providers/{provider_id}")
async def update_kt3_provider(
    provider_id: int,
    request: KT3ProviderUpdateRequest,
    _current_user: User = Depends(require_roles("admin")),
    db: AsyncSession = Depends(get_db),
):
    try:
        result = await kt3_system_service.update_provider_config(
            provider_id=provider_id,
            payload=request.model_dump(exclude_unset=True),
            db=db,
        )
    except ValueError as exc:
        status_code = 404 if "not found" in str(exc) else 400
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc
    return success(data=result)


@router.post("/kt3/providers/{provider_id}/activate")
async def activate_kt3_provider(
    provider_id: int,
    request: KT3ProviderActivateRequest,
    _current_user: User = Depends(require_roles("admin")),
    db: AsyncSession = Depends(get_db),
):
    try:
        result = await kt3_system_service.activate_provider_config(
            provider_id=provider_id,
            is_active=request.is_active,
            db=db,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return success(data=result)


@router.post("/kt3/providers/{provider_id}/test")
async def test_kt3_provider(
    provider_id: int,
    _current_user: User = Depends(require_roles("admin")),
    db: AsyncSession = Depends(get_db),
):
    try:
        result = await kt3_system_service.test_provider_config(provider_id, db)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return success(data=result)


@router.post("/kt3/agent-reviews/run")
async def run_kt3_agent_review(
    request: KT3AgentReviewRunRequest,
    current_user: User = Depends(require_roles("admin", "analyst")),
    db: AsyncSession = Depends(get_db),
):
    """Create an analyst-triggered MARO-style KT3 LLM Agent review job."""
    try:
        result = await risk_service.create_kt3_agent_review_job(
            job_type="agent_review",
            payload=request.model_dump(),
            user_id=current_user.id,
            db=db,
        )
        await _commit_if_supported(db)
    except ValueError as exc:
        detail = str(exc)
        status_code = 404 if "not found" in detail else 400
        raise HTTPException(status_code=status_code, detail=detail) from exc
    return success(data=result)


@router.post("/kt3/agent-feedback/record")
async def record_kt3_agent_feedback(
    request: KT3AgentFeedbackRequest,
    current_user: User = Depends(require_roles("admin", "analyst")),
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
    current_user: User = Depends(require_roles("admin")),
    db: AsyncSession = Depends(get_db),
):
    """Create a MARO-style policy refinement background job."""
    try:
        result = await kt3_system_service.create_kt3_job(
            job_type="policy_refine",
            payload=request.model_dump(),
            user_id=current_user.id,
            db=db,
        )
        await _commit_if_supported(db)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return success(data=result)


@router.post("/kt3/policies/{policy_id}/activate")
async def activate_kt3_policy(
    policy_id: str,
    current_user: User = Depends(require_roles("admin")),
    db: AsyncSession = Depends(get_db),
):
    """Explicitly activate a KT3 policy for later manual Agent/Judge context."""
    try:
        result = await kt3_system_service.activate_policy_in_db(
            policy_id,
            user_id=current_user.id,
            db=db,
        )
    except ValueError as exc:
        detail = str(exc)
        status_code = 404 if "not found" in detail else 400
        raise HTTPException(status_code=status_code, detail=detail) from exc
    return success(data=result)


@router.get("/kt3/policies")
async def list_kt3_policies(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    _current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return success(data=await kt3_system_service.list_policies(db, page=page, page_size=page_size))


@router.post("/kt3/backfill")
async def start_kt3_backfill(
    request: KT3BackfillRequest,
    current_user: User = Depends(require_roles("admin")),
    db: AsyncSession = Depends(get_db),
):
    result = await kt3_system_service.create_kt3_job(
        job_type="backfill",
        payload=request.model_dump(),
        user_id=current_user.id,
        db=db,
    )
    await _commit_if_supported(db)
    return success(data=result)


@router.get("/kt3/jobs")
async def list_kt3_jobs(
    job_type: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    _current_user: User = Depends(require_roles("admin", "analyst")),
    db: AsyncSession = Depends(get_db),
):
    result = await kt3_system_service.list_kt3_jobs(
        db,
        job_type=job_type,
        page=page,
        page_size=page_size,
    )
    return success(data=result)


@router.get("/kt3/jobs/{job_id}")
async def get_kt3_job(
    job_id: int,
    _current_user: User = Depends(require_roles("admin", "analyst")),
    db: AsyncSession = Depends(get_db),
):
    result = await kt3_system_service.get_kt3_job(job_id, db)
    if result is None:
        raise HTTPException(status_code=404, detail=f"KT3 job not found: {job_id}")
    return success(data=result)


@router.get("/kt3/policies/{policy_id}")
async def get_kt3_policy(
    policy_id: str,
    _current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return an auditable KT3 Agent review policy artifact."""
    result = None
    if hasattr(db, "execute"):
        result = await kt3_system_service.get_policy_artifact_from_db(policy_id, db)
    if result is None:
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
