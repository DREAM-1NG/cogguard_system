"""Deprecated V1 risk API routes."""

import inspect
import json

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_current_user, require_roles
from app.core.review.gate_dataset import get_gate_dataset_contract_spec
from app.core.review.gate_dataset import validate_gate_dataset_contract
from app.db.mongodb import get_mongo_db
from app.db.mysql import get_db
from app.models.user import User
from app.schemas.risk import ReviewAgentReviewRunRequest
from app.schemas.risk import ReviewAgentFeedbackRequest
from app.schemas.risk import ReviewBackfillRequest
from app.schemas.risk import ReviewGateDatasetUploadRequest
from app.schemas.risk import ReviewGateDatasetValidationRequest
from app.schemas.risk import ReviewGateSuiteRequest
from app.schemas.risk import ReviewProviderActivateRequest
from app.schemas.risk import ReviewProviderConfigRequest
from app.schemas.risk import ReviewProviderUpdateRequest
from app.schemas.risk import ReviewPolicyOptimizeRequest
from app.schemas.risk import ReviewPolicyRefineRequest
from app.services import review_system_service
from app.services import risk_service
from app.services.review_case_service import ReviewCaseService
from app.utils.response import success

router = APIRouter(deprecated=True)


def get_legacy_review_case_service(
    db: AsyncSession = Depends(get_db),
    mongo_db=Depends(get_mongo_db),
) -> ReviewCaseService:
    return ReviewCaseService(db=db, mongo_db=mongo_db)


async def _commit_if_supported(db: AsyncSession) -> None:
    commit = getattr(db, "commit", None)
    if commit is None:
        return
    result = commit()
    if inspect.isawaitable(result):
        await result


@router.post("/assess", deprecated=True)
async def assess_risk(
    platform: str | None = Query(None, description="Deprecated platform filter"),
    event_id: str | None = Query(None, description="Deprecated event id filter"),
    time_window: int = Query(60, ge=1, le=3600, description="Deprecated; ignored by ReviewCaseService facade"),
    min_participation: int = Query(2, ge=1, description="Deprecated; ignored by ReviewCaseService facade"),
    edge_weight: float = Query(0.5, ge=0, le=1, description="Deprecated; ignored by ReviewCaseService facade"),
    run_legacy_multi_agent: bool = Query(False, description="Deprecated; ignored by ReviewCaseService facade"),
    current_user: User = Depends(get_current_user),
    service: ReviewCaseService = Depends(get_legacy_review_case_service),
):
    """Deprecated V1 facade for the latest Event Review Case projection."""
    _ = (time_window, min_participation, edge_weight, run_legacy_multi_agent, current_user)
    try:
        report = await service.legacy_assess_risk(platform=platform, event_id=event_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return success(data=report)


@router.post("/review/gate-suite", deprecated=True)
async def assess_gate_suite(
    request: ReviewGateSuiteRequest,
    current_user: User = Depends(get_current_user),
    service: ReviewCaseService = Depends(get_legacy_review_case_service),
):
    """Deprecated V1 facade; gate-suite execution moved behind internal review tooling."""
    _ = (
        request.time_window,
        request.min_participation,
        request.edge_weight,
        request.gate_dataset,
        current_user,
    )
    try:
        report = await service.legacy_assess_risk(platform=request.platform, event_id=request.event_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    review_harmfulness = report.get("review_harmfulness") or {}
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
            "review_harmfulness": review_harmfulness,
            "gate_suite": review_harmfulness.get("gate_suite"),
            "persistence": {
                "persisted": False,
                "reason": "Deprecated V1 risk no longer executes the legacy Gate Suite business implementation.",
            },
        }
    )


@router.get("/review/gate-dataset/contract")
async def get_gate_dataset_contract(
    _current_user: User = Depends(get_current_user),
):
    """Return the machine-readable Review Gate Dataset contract."""
    return success(data=get_gate_dataset_contract_spec())


@router.post("/review/gate-dataset/validate")
async def validate_gate_dataset(
    request: ReviewGateDatasetValidationRequest,
    _current_user: User = Depends(get_current_user),
):
    """Validate a Review Gate Dataset without running risk assessment or persistence."""
    return success(data=validate_gate_dataset_contract(request.gate_dataset))


@router.post("/review/gate-datasets/upload")
async def upload_gate_dataset_file(
    file: UploadFile = File(...),
    current_user: User = Depends(require_roles("admin")),
    db: AsyncSession = Depends(get_db),
):
    """Upload and persist a Review Gate Dataset JSON file."""
    try:
        payload = json.loads((await file.read()).decode("utf-8"))
        result = await review_system_service.persist_gate_dataset_upload(
            dataset=payload,
            uploaded_by=current_user.id,
            db=db,
        )
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail=f"invalid JSON file: {exc}") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return success(data=result)


@router.post("/review/gate-datasets")
async def upload_gate_dataset_json(
    request: ReviewGateDatasetUploadRequest,
    current_user: User = Depends(require_roles("admin")),
    db: AsyncSession = Depends(get_db),
):
    """Persist a Review Gate Dataset from a JSON request body."""
    result = await review_system_service.persist_gate_dataset_upload(
        dataset=request.gate_dataset,
        uploaded_by=current_user.id,
        db=db,
    )
    return success(data=result)


@router.get("/review/gate-datasets")
async def list_gate_datasets(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    _current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return success(data=await review_system_service.list_gate_datasets(db, page=page, page_size=page_size))


@router.get("/review/gate-datasets/{dataset_db_id}")
async def get_gate_dataset_detail(
    dataset_db_id: int,
    _current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await review_system_service.get_gate_dataset_detail(dataset_db_id, db)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Review Gate Dataset not found: {dataset_db_id}")
    return success(data=result)


@router.get("/review/providers")
async def list_review_providers(
    _current_user: User = Depends(require_roles("admin")),
    db: AsyncSession = Depends(get_db),
):
    return success(data=await review_system_service.list_provider_configs(db))


@router.post("/review/providers")
async def create_review_provider(
    request: ReviewProviderConfigRequest,
    current_user: User = Depends(require_roles("admin")),
    db: AsyncSession = Depends(get_db),
):
    try:
        result = await review_system_service.create_provider_config(
            payload=request.model_dump(),
            user_id=current_user.id,
            db=db,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return success(data=result)


@router.put("/review/providers/{provider_id}")
async def update_review_provider(
    provider_id: int,
    request: ReviewProviderUpdateRequest,
    _current_user: User = Depends(require_roles("admin")),
    db: AsyncSession = Depends(get_db),
):
    try:
        result = await review_system_service.update_provider_config(
            provider_id=provider_id,
            payload=request.model_dump(exclude_unset=True),
            db=db,
        )
    except ValueError as exc:
        status_code = 404 if "not found" in str(exc) else 400
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc
    return success(data=result)


@router.post("/review/providers/{provider_id}/activate")
async def activate_review_provider(
    provider_id: int,
    request: ReviewProviderActivateRequest,
    _current_user: User = Depends(require_roles("admin")),
    db: AsyncSession = Depends(get_db),
):
    try:
        result = await review_system_service.activate_provider_config(
            provider_id=provider_id,
            is_active=request.is_active,
            db=db,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return success(data=result)


@router.post("/review/providers/{provider_id}/test")
async def test_review_provider(
    provider_id: int,
    _current_user: User = Depends(require_roles("admin")),
    db: AsyncSession = Depends(get_db),
):
    try:
        result = await review_system_service.test_provider_config(provider_id, db)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return success(data=result)


@router.post("/review/agent-reviews/run", deprecated=True)
async def run_agent_review(
    request: ReviewAgentReviewRunRequest,
    current_user: User = Depends(require_roles("admin", "analyst")),
    service: ReviewCaseService = Depends(get_legacy_review_case_service),
):
    """Deprecated V1 facade; records a case review request, not an old job."""
    try:
        result = await service.legacy_request_review(
            report_id=request.case_id or request.report_id,
            reason="Manual review requested from deprecated V1 risk endpoint.",
            evidence_refs=[*request.selected_post_ids, *request.selected_tree_ids],
            actor=current_user,
        )
        await _commit_if_supported(service.db)
    except ValueError as exc:
        detail = str(exc)
        status_code = 404 if "not found" in detail else 400
        raise HTTPException(status_code=status_code, detail=detail) from exc
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return success(data=result)


@router.post("/review/agent-feedback/record", deprecated=True)
async def record_review_agent_feedback(
    request: ReviewAgentFeedbackRequest,
    current_user: User = Depends(require_roles("admin", "analyst")),
    service: ReviewCaseService = Depends(get_legacy_review_case_service),
):
    """Deprecated V1 facade; records case activity, never old-table feedback."""
    try:
        result = await service.legacy_record_feedback(
            report_id=request.report_id,
            feedback=request.model_dump(),
            actor=current_user,
        )
        await _commit_if_supported(service.db)
    except ValueError as exc:
        detail = str(exc)
        status_code = 404 if "not found" in detail else 400
        raise HTTPException(status_code=status_code, detail=detail) from exc
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return success(data=result)


@router.post("/review/policies/optimize")
async def optimize_review_policy(
    request: ReviewPolicyOptimizeRequest,
    _current_user: User = Depends(get_current_user),
):
    """Optimize a Review MARO-style Agent review policy from an explicit validation split."""
    try:
        result = risk_service.optimize_review_policy(request.dataset_manifest)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return success(data=result)


@router.post("/review/policies/refine")
async def refine_review_policy(
    request: ReviewPolicyRefineRequest,
    current_user: User = Depends(require_roles("admin")),
    db: AsyncSession = Depends(get_db),
):
    """Create a MARO-style policy refinement background job."""
    try:
        result = await review_system_service.create_review_job(
            job_type="policy_refine",
            payload=request.model_dump(),
            user_id=current_user.id,
            db=db,
        )
        await _commit_if_supported(db)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return success(data=result)


@router.post("/review/policies/{policy_id}/activate")
async def activate_review_policy(
    policy_id: str,
    current_user: User = Depends(require_roles("admin")),
    db: AsyncSession = Depends(get_db),
):
    """Explicitly activate a Review policy for later manual Agent/Judge context."""
    try:
        result = await review_system_service.activate_policy_in_db(
            policy_id,
            user_id=current_user.id,
            db=db,
        )
    except ValueError as exc:
        detail = str(exc)
        status_code = 404 if "not found" in detail else 400
        raise HTTPException(status_code=status_code, detail=detail) from exc
    return success(data=result)


@router.get("/review/policies")
async def list_review_policies(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    _current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return success(data=await review_system_service.list_policies(db, page=page, page_size=page_size))


@router.post("/review/backfill")
async def start_review_backfill(
    request: ReviewBackfillRequest,
    current_user: User = Depends(require_roles("admin")),
    db: AsyncSession = Depends(get_db),
):
    result = await review_system_service.create_review_job(
        job_type="backfill",
        payload=request.model_dump(),
        user_id=current_user.id,
        db=db,
    )
    await _commit_if_supported(db)
    return success(data=result)


@router.get("/review/jobs")
async def list_review_jobs(
    job_type: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    _current_user: User = Depends(require_roles("admin", "analyst")),
    db: AsyncSession = Depends(get_db),
):
    result = await review_system_service.list_review_jobs(
        db,
        job_type=job_type,
        page=page,
        page_size=page_size,
    )
    return success(data=result)


@router.get("/review/jobs/{job_id}")
async def get_review_job(
    job_id: int,
    _current_user: User = Depends(require_roles("admin", "analyst")),
    db: AsyncSession = Depends(get_db),
):
    result = await review_system_service.get_review_job(job_id, db)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Review job not found: {job_id}")
    return success(data=result)


@router.get("/review/policies/{policy_id}")
async def get_review_policy(
    policy_id: str,
    _current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return an auditable Review Agent review policy artifact."""
    result = None
    if hasattr(db, "execute"):
        result = await review_system_service.get_policy_artifact_from_db(policy_id, db)
    if result is None:
        result = risk_service.get_review_policy(policy_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Review policy not found: {policy_id}")
    return success(data=result)


@router.get("/reports", deprecated=True)
async def list_reports(
    platform: str | None = Query(None),
    event_id: str | None = Query(None),
    risk_level: str | None = Query(None),
    phase: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    _current_user: User = Depends(get_current_user),
    service: ReviewCaseService = Depends(get_legacy_review_case_service),
):
    """Deprecated V1 facade for Event Review Case list projection."""
    items, total = await service.legacy_list_reports(
        platform=platform,
        event_id=event_id,
        risk_level=risk_level,
        phase=phase,
        page=page,
        page_size=page_size,
    )
    return success(data={"total": total, "items": items})


@router.get("/reports/{report_id}", deprecated=True)
async def get_report_detail(
    report_id: str,
    _current_user: User = Depends(get_current_user),
    service: ReviewCaseService = Depends(get_legacy_review_case_service),
):
    """Deprecated V1 facade for Event Review Case detail projection."""
    try:
        report = await service.legacy_get_report_detail(report_id)
    except KeyError:
        return success(data=None, msg="report not found")
    return success(data=report)
