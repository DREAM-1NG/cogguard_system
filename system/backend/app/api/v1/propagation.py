"""Propagation Analysis API routes.

The route surface intentionally separates observed propagation analysis from
predictive model calls. Observed analysis explains what has happened; the
prediction endpoint estimates future trend and next-hop candidates.
"""

from inspect import Parameter, signature

from fastapi import APIRouter, Depends, Query

from app.core.security import get_current_user_or_local_preview
from app.models.user import User
from app.services import propagation_model_service, propagation_observation_service
from app.utils.response import success

router = APIRouter()


async def _call_observed_analysis(*, platform: str | None, event_id: str | None, node_limit: int) -> dict:
    analyze_fn = propagation_observation_service.analyze_observed_propagation
    try:
        parameters = signature(analyze_fn).parameters
    except (TypeError, ValueError):
        parameters = {}
    supports_node_limit = "node_limit" in parameters or any(
        param.kind == Parameter.VAR_KEYWORD for param in parameters.values()
    )
    if supports_node_limit:
        return await analyze_fn(platform=platform, event_id=event_id, node_limit=node_limit)
    return await analyze_fn(platform=platform, event_id=event_id)


@router.get("/analyze")
async def analyze(
    platform: str | None = Query(None, description="Limit analysis to one platform."),
    event_id: str | None = Query(None, description="Limit analysis to one event id."),
    node_limit: int = Query(300, ge=0, description="Maximum propagation graph nodes; 0 means no limit."),
    _current_user: User | None = Depends(get_current_user_or_local_preview),
):
    """Analyze observed propagation paths, roles, objects, and evidence."""
    result = await _call_observed_analysis(platform=platform, event_id=event_id, node_limit=node_limit)
    return success(data=result)


@router.get("/observed-analysis")
async def observed_analysis(
    platform: str | None = Query(None, description="Limit analysis to one platform."),
    event_id: str | None = Query(None, description="Limit analysis to one event id."),
    node_limit: int = Query(300, ge=0, description="Maximum propagation graph nodes; 0 means no limit."),
    _current_user: User | None = Depends(get_current_user_or_local_preview),
):
    """Canonical observed-only Propagation Analysis endpoint."""
    result = await _call_observed_analysis(platform=platform, event_id=event_id, node_limit=node_limit)
    return success(data=result)


@router.post("/model-event-predict")
async def predict_model_event(
    platform: str | None = Query(None, description="Limit prediction to one platform."),
    event_id: str | None = Query(None, description="Limit prediction to one event id."),
    top_k: int = Query(10, ge=1, le=50, description="Number of next-hop candidates to return."),
    _current_user: User | None = Depends(get_current_user_or_local_preview),
):
    """Run the prediction model for current-event propagation data."""
    result = await propagation_model_service.predict_current_event_model(
        platform=platform,
        event_id=event_id,
        top_k=top_k,
    )
    return success(data=result)


@router.post("/model-predict")
async def predict_macro_micro_model(
    dataset: str = Query("twitter", description="Experiment dataset: twitter, douban, or memetracker."),
    seed: int | None = Query(42, description="Experiment seed; empty aggregates all available seeds."),
    run_live: bool = Query(False, description="Run a local small-run instead of reading cached results."),
    _current_user: User | None = Depends(get_current_user_or_local_preview),
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
