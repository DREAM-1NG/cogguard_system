"""Propagation Analysis API routes.

The route surface intentionally separates observed propagation analysis from
predictive model calls. Observed analysis explains what has happened; the
prediction endpoint estimates future trend and next-hop candidates.
"""

from inspect import Parameter, signature

from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_current_user
from app.db.mongodb import get_mongo_db
from app.db.mysql import get_db
from app.models.user import User
from app.schemas.propagation import (
    ClaimResponseLandscapeResponse,
    PropagationAlertActionRequest,
    PropagationMonitorProfileRequest,
    PropagationPredictionResponse,
)
from app.services import (
    claim_response_landscape_service,
    propagation_model_service,
    propagation_monitoring_service,
    propagation_observation_service,
)
from app.utils.response import success

router = APIRouter()

SUPPORTED_OBSERVATION_RATIOS = frozenset({0.1, 0.3, 0.5})


async def _call_observed_analysis(
    *,
    platform: str | None,
    event_id: str | None,
    node_limit: int,
    first_layer_limit: int | None = None,
    second_layer_limit: int | None = None,
) -> dict:
    analyze_fn = propagation_observation_service.analyze_observed_propagation
    try:
        parameters = signature(analyze_fn).parameters
    except (TypeError, ValueError):
        parameters = {}
    supports_node_limit = "node_limit" in parameters or any(
        param.kind == Parameter.VAR_KEYWORD for param in parameters.values()
    )
    layer_budget = {
        "total": node_limit,
        "parallel_roots": 8,
        "first_layer": first_layer_limit if first_layer_limit is not None else 40,
        "second_layer": second_layer_limit if second_layer_limit is not None else 80,
    }
    if supports_node_limit:
        if "layer_budget" in parameters or any(param.kind == Parameter.VAR_KEYWORD for param in parameters.values()):
            return await analyze_fn(
                platform=platform,
                event_id=event_id,
                node_limit=node_limit,
                layer_budget=layer_budget,
            )
        return await analyze_fn(platform=platform, event_id=event_id, node_limit=node_limit)
    return await analyze_fn(platform=platform, event_id=event_id)


@router.get("/analyze")
async def analyze(
    platform: str | None = Query(None, description="Limit analysis to one platform."),
    event_id: str | None = Query(None, description="Limit analysis to one event id."),
    node_limit: int = Query(160, ge=0, description="Maximum diffusion-summary nodes; 0 means all summary nodes."),
    first_layer_limit: int = Query(40, ge=1, le=160),
    second_layer_limit: int = Query(80, ge=1, le=160),
    _current_user: User = Depends(get_current_user),
):
    """Analyze observed propagation paths, roles, objects, and evidence."""
    result = await _call_observed_analysis(
        platform=platform,
        event_id=event_id,
        node_limit=node_limit,
        first_layer_limit=first_layer_limit,
        second_layer_limit=second_layer_limit,
    )
    return success(data=result)


@router.get("/observed-analysis")
async def observed_analysis(
    platform: str | None = Query(None, description="Limit analysis to one platform."),
    event_id: str | None = Query(None, description="Limit analysis to one event id."),
    node_limit: int = Query(160, ge=0, description="Maximum diffusion-summary nodes; 0 means all summary nodes."),
    first_layer_limit: int = Query(40, ge=1, le=160),
    second_layer_limit: int = Query(80, ge=1, le=160),
    _current_user: User = Depends(get_current_user),
):
    """Canonical observed-only Propagation Analysis endpoint."""
    result = await _call_observed_analysis(
        platform=platform,
        event_id=event_id,
        node_limit=node_limit,
        first_layer_limit=first_layer_limit,
        second_layer_limit=second_layer_limit,
    )
    return success(data=result)


@router.get("/claim-response-landscape", response_model=ClaimResponseLandscapeResponse)
async def get_claim_response_landscape(
    event_id: Annotated[str, Query(min_length=1, description="Event id required for the Event Review Case landscape.")],
    platform: Annotated[str | None, Query(description="Limit publications and responses to one platform.")] = None,
    db: AsyncSession = Depends(get_db),
    mongo_db: Any = Depends(get_mongo_db),
    _current_user: User = Depends(get_current_user),
):
    """Read observed authority-claim publications and path-backed responses."""
    result = await claim_response_landscape_service.build_claim_response_landscape(
        event_id,
        platform=platform,
        db=db,
        mongo_db=mongo_db,
    )
    return success(data=result)


@router.get("/model-event-timeline")
async def get_model_event_timeline(
    event_id: Annotated[str, Query(min_length=1, description="Event id required for event-scoped timeline.")],
    platform: Annotated[str | None, Query(description="Limit timeline to one platform.")] = None,
    timeline_range: Annotated[
        Literal["active", "24h", "7d", "all"],
        Query(description="Evidence range: active period, 24 hours, 7 days, or full history."),
    ] = "active",
    _current_user: User = Depends(get_current_user),
):
    """Read a range-scoped evidence timeline without running prediction inference."""
    result = await propagation_model_service.build_current_event_timeline(
        event_id=event_id,
        platform=platform,
        timeline_range=timeline_range,
    )
    return success(data=result)


@router.get("/monitor-profiles")
async def get_monitor_profiles(
    event_id: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(get_current_user),
):
    return success(data=await propagation_monitoring_service.list_monitor_profiles(db, event_id=event_id))


@router.put("/monitor-profiles")
async def put_monitor_profile(
    body: PropagationMonitorProfileRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if str(current_user.role or "") != "admin":
        raise HTTPException(status_code=403, detail="Only administrators can manage propagation monitoring profiles.")
    return success(data=await propagation_monitoring_service.upsert_monitor_profile(
        payload=body.model_dump(), updated_by=int(current_user.id), db=db
    ))


@router.get("/alerts/unresolved-count")
async def get_unresolved_alert_count(
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(get_current_user),
):
    return success(data={"count": await propagation_monitoring_service.unresolved_alert_count(db)})


@router.get("/alerts")
async def get_alerts(
    event_id: str | None = Query(None),
    platform: str | None = Query(None),
    unresolved_only: bool = Query(False),
    limit: int = Query(100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(get_current_user),
):
    return success(data=await propagation_monitoring_service.list_alerts(
        db, event_id=event_id, platform=platform, unresolved_only=unresolved_only, limit=limit
    ))


@router.get("/alerts/{alert_id}")
async def get_alert(
    alert_id: int,
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(get_current_user),
):
    try:
        return success(data=await propagation_monitoring_service.get_alert_detail(db, alert_id=alert_id))
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/alerts/{alert_id}/actions")
async def post_alert_action(
    alert_id: int,
    body: PropagationAlertActionRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if str(current_user.role or "") not in {"admin", "analyst"}:
        raise HTTPException(status_code=403, detail="Propagation alert disposition is not permitted for this role.")
    try:
        result = await propagation_monitoring_service.apply_alert_action(
            alert_id=alert_id, action=body.action, note=body.note, actor_id=int(current_user.id), db=db
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return success(data=result)


@router.post("/model-event-predict", response_model=PropagationPredictionResponse)
async def predict_model_event(
    event_id: Annotated[str, Query(min_length=1, description="Event id required for event-scoped prediction.")],
    platform: Annotated[str | None, Query(description="Limit prediction to one platform.")] = None,
    top_k: Annotated[int, Query(ge=1, le=50, description="Number of next-hop candidates to return.")] = 10,
    observed_until: Annotated[
        str | None,
        Query(description="Inclusive timezone-aware ISO-8601 observation cutoff. Later rows are excluded."),
    ] = None,
    t_obs: Annotated[
        str | None,
        Query(description="Compatibility alias for observed_until; must include a timezone."),
    ] = None,
    prediction_horizon: Annotated[
        int | None,
        Query(
            ge=1,
            le=24 * 30,
            include_in_schema=False,
            description="Deprecated wall-clock horizon; the deployed checkpoint emits normalized steps.",
        ),
    ] = None,
    observation_ratio: Annotated[
        float,
        Query(ge=0.1, le=0.5, description="Supported observed-prefix ratio used by the deployed checkpoint."),
    ] = 0.5,
    force_refresh: bool = Query(True, include_in_schema=False),
    _current_user: User = Depends(get_current_user),
):
    """Run the prediction model for current-event propagation data."""
    try:
        observed_cutoff = propagation_model_service.validate_observed_until(observed_until)
        t_obs_cutoff = propagation_model_service.validate_observed_until(t_obs)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if observed_cutoff is not None and t_obs_cutoff is not None and observed_cutoff != t_obs_cutoff:
        raise HTTPException(
            status_code=422,
            detail="observed_until and t_obs must identify the same instant.",
        )
    effective_observed_until = observed_until or t_obs
    if round(float(observation_ratio), 4) not in SUPPORTED_OBSERVATION_RATIOS:
        raise HTTPException(
            status_code=422,
            detail="observation_ratio must be one of 0.1, 0.3, or 0.5.",
        )
    if prediction_horizon is not None:
        raise HTTPException(
            status_code=422,
            detail="The deployed checkpoint exposes normalized trajectory steps; wall-clock prediction_horizon is unsupported.",
        )
    if not force_refresh:
        result = await propagation_model_service.read_cached_current_event_prediction(
            event_id=event_id,
            platform=platform,
            observed_until=effective_observed_until,
            observation_ratio=observation_ratio,
            top_k=top_k,
        )
        return success(data=result)
    result = await propagation_model_service.predict_current_event_model(
        platform=platform,
        event_id=event_id,
        top_k=top_k,
        observed_until=effective_observed_until,
        observation_ratio=observation_ratio,
    )
    result = propagation_model_service.enforce_prediction_contract(
        result,
        event_id=event_id,
        platform=platform,
    )
    return success(data=result)


@router.get("/model-event-predict/cached", response_model=PropagationPredictionResponse)
async def get_cached_model_event_prediction(
    event_id: Annotated[str, Query(min_length=1, description="Event id required for event-scoped prediction.")],
    platform: Annotated[str | None, Query(description="Limit prediction to one platform.")] = None,
    top_k: Annotated[int, Query(ge=1, le=50)] = 10,
    observed_until: Annotated[str | None, Query(description="Inclusive timezone-aware ISO-8601 observation cutoff.")] = None,
    observation_ratio: Annotated[float, Query(ge=0.1, le=0.5)] = 0.5,
    _current_user: User = Depends(get_current_user),
):
    """Read a persisted prediction without invoking the event model."""
    try:
        propagation_model_service.validate_observed_until(observed_until)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    result = await propagation_model_service.read_cached_current_event_prediction(
        event_id=event_id,
        platform=platform,
        observed_until=observed_until,
        observation_ratio=observation_ratio,
        top_k=top_k,
    )
    return success(data=result)


@router.post("/research/model-predict", include_in_schema=False)
async def predict_macro_micro_model(
    dataset: str = Query("twitter", description="Experiment dataset: twitter, douban, or memetracker."),
    seed: int | None = Query(42, description="Experiment seed; empty aggregates all available seeds."),
    run_live: bool = Query(False, description="Run a local small-run instead of reading cached results."),
    _current_user: User = Depends(get_current_user),
):
    """Read macro-size and next-hop prediction-model experiment evidence."""
    result = await propagation_model_service.predict_benchmark_model_evidence(
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
        "label": "experimental_prediction",
        "is_experimental": bool(result.get("is_experimental", True)),
        "evidence_level": result.get("evidence_level"),
        "full_validation_passed": bool(result.get("full_validation_passed", False)),
        "methodology": result.get("methodology") or {},
        "macro": result.get("macro") or {},
        "micro": result.get("micro") or {},
        "candidate_protocol_audit": result.get("candidate_protocol_audit") or {},
    }
    if result.get("note"):
        public_result["note"] = result.get("note")
    return success(data=public_result)
