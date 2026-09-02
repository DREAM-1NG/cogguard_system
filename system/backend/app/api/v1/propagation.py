"""Propagation Analysis API routes.

The route surface intentionally separates observed propagation analysis from
predictive model calls. Observed analysis explains what has happened; the
prediction endpoint estimates future trend and next-hop candidates.
"""

from inspect import Parameter, signature

import copy
import asyncio
import time
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_current_user
from app.db.mysql import get_db
from app.models.user import User
from app.schemas.propagation import (
    PropagationAlertActionRequest,
    PropagationMonitorProfileRequest,
    PropagationPredictionResponse,
)
from app.services import (
    propagation_model_service,
    propagation_monitoring_service,
    propagation_observation_service,
)
from app.utils.response import success

router = APIRouter()

SUPPORTED_OBSERVATION_RATIOS = frozenset({0.1, 0.3, 0.5})
OBSERVED_ANALYSIS_CACHE_TTL_SECONDS = 300
_OBSERVED_ANALYSIS_CACHE: dict[tuple[str, str, int], tuple[float, dict]] = {}
_OBSERVED_ANALYSIS_IN_FLIGHT: dict[tuple[str, str, int], asyncio.Task] = {}
_TEXT_PREVIEW_CHARS = 160


def _require_monitor_role(current_user: User | None, *, allow_admin_only: bool = False) -> int:
    """Apply monitoring roles while preserving local preview access."""
    if current_user is None:
        return 0
    allowed = {"admin"} if allow_admin_only else {"admin", "analyst"}
    if str(current_user.role or "") not in allowed:
        raise HTTPException(status_code=403, detail="Propagation monitoring operation is not permitted for this role.")
    return int(current_user.id)


def clear_observed_analysis_cache() -> None:
    _OBSERVED_ANALYSIS_CACHE.clear()
    _OBSERVED_ANALYSIS_IN_FLIGHT.clear()


def _observed_cache_key(platform: str | None, event_id: str | None, node_limit: int) -> tuple[str, str, int]:
    return (platform or "", event_id or "", int(node_limit))


def _get_cached_observed_analysis(platform: str | None, event_id: str | None, node_limit: int) -> dict | None:
    item = _OBSERVED_ANALYSIS_CACHE.get(_observed_cache_key(platform, event_id, node_limit))
    if item is None:
        return None
    created_at, payload = item
    if time.monotonic() - created_at >= OBSERVED_ANALYSIS_CACHE_TTL_SECONDS:
        _OBSERVED_ANALYSIS_CACHE.pop(_observed_cache_key(platform, event_id, node_limit), None)
        return None
    return copy.deepcopy(payload)


def _set_cached_observed_analysis(platform: str | None, event_id: str | None, node_limit: int, payload: dict) -> None:
    _OBSERVED_ANALYSIS_CACHE[_observed_cache_key(platform, event_id, node_limit)] = (
        time.monotonic(),
        copy.deepcopy(payload),
    )


def _truncate_text(value, *, max_chars: int = _TEXT_PREVIEW_CHARS):
    if not isinstance(value, str):
        return value
    if len(value) <= max_chars:
        return value
    return value[:max_chars].rstrip() + "…"


def _compact_post_like(item: object) -> object:
    if not isinstance(item, dict):
        return item
    compact = copy.deepcopy(item)
    if "content" in compact:
        compact["content"] = _truncate_text(compact.get("content"))
    if "raw_data" in compact:
        compact.pop("raw_data", None)
    return compact


def _compact_timeline(result: dict, *, node_limit: int) -> None:
    timeline = result.get("timeline")
    if isinstance(timeline, list):
        result["timeline"] = [_compact_post_like(item) for item in timeline[:node_limit]]
        result.setdefault("response_meta", {})["timeline_total_count"] = len(timeline)
        result["response_meta"]["timeline_visible_count"] = len(result["timeline"])


def _compact_evidence_chains(result: dict, *, node_limit: int) -> None:
    chains = result.get("evidence_chains")
    if not isinstance(chains, list):
        return
    compact_chains = []
    per_chain_limit = max(1, min(node_limit, 20))
    for chain in chains[:per_chain_limit]:
        if not isinstance(chain, dict):
            compact_chains.append(chain)
            continue
        compact_chain = copy.deepcopy(chain)
        posts = compact_chain.get("supporting_posts")
        if isinstance(posts, list):
            compact_chain["supporting_posts"] = [_compact_post_like(post) for post in posts[:per_chain_limit]]
            compact_chain["supporting_post_total_count"] = len(posts)
        compact_chains.append(compact_chain)
    result["evidence_chains"] = compact_chains
    result.setdefault("response_meta", {})["evidence_chain_total_count"] = len(chains)
    result["response_meta"]["evidence_chain_visible_count"] = len(compact_chains)


def _compact_provenance_graph(result: dict) -> None:
    provenance_graph = result.get("provenance_graph")
    if not isinstance(provenance_graph, dict):
        return
    nodes = provenance_graph.get("nodes")
    edges = provenance_graph.get("edges")
    result["provenance_graph"] = {
        "summary": {
            "node_count": len(nodes) if isinstance(nodes, list) else provenance_graph.get("node_count", 0),
            "edge_count": len(edges) if isinstance(edges, list) else provenance_graph.get("edge_count", 0),
        },
        "response_compacted": True,
    }


async def _load_observed_analysis_cached(platform: str | None, event_id: str | None, node_limit: int) -> dict:
    cached = _get_cached_observed_analysis(platform, event_id, node_limit)
    if cached is not None:
        return cached

    cache_key = _observed_cache_key(platform, event_id, node_limit)
    task = _OBSERVED_ANALYSIS_IN_FLIGHT.get(cache_key)
    if task is None or task.done():
        async def compute() -> dict:
            result = await _call_observed_analysis(platform=platform, event_id=event_id, node_limit=node_limit)
            result = _compact_observed_result(result, node_limit=node_limit)
            _set_cached_observed_analysis(platform, event_id, node_limit, result)
            return copy.deepcopy(result)

        task = asyncio.create_task(compute())
        _OBSERVED_ANALYSIS_IN_FLIGHT[cache_key] = task
    try:
        return copy.deepcopy(await task)
    finally:
        if task.done():
            _OBSERVED_ANALYSIS_IN_FLIGHT.pop(cache_key, None)


def _compact_observed_result(result: dict, *, node_limit: int) -> dict:
    """Keep observed propagation responses bounded for the interactive page."""
    if node_limit <= 0:
        return result

    result = copy.deepcopy(result)
    _compact_provenance_graph(result)
    _compact_timeline(result, node_limit=node_limit)
    _compact_evidence_chains(result, node_limit=node_limit)

    graph = result.get("graph")
    if not isinstance(graph, dict):
        return result
    nodes = graph.get("nodes")
    if not isinstance(nodes, list) or len(nodes) <= node_limit:
        return result

    diffusion_summary = result.get("diffusion_summary")
    visible_nodes = []
    if isinstance(diffusion_summary, dict) and isinstance(diffusion_summary.get("visible_nodes"), list):
        visible_nodes = diffusion_summary.get("visible_nodes") or []

    visible_ids = [str(node.get("id")) for node in visible_nodes if isinstance(node, dict) and node.get("id") is not None]
    if not visible_ids:
        visible_ids = [str(node.get("id")) for node in nodes[:node_limit] if isinstance(node, dict) and node.get("id") is not None]
    visible_id_set = set(visible_ids[:node_limit])

    node_by_id = {str(node.get("id")): node for node in nodes if isinstance(node, dict) and node.get("id") is not None}
    compact_nodes = []
    for visible_node in visible_nodes[:node_limit]:
        if not isinstance(visible_node, dict):
            continue
        node_id = str(visible_node.get("id"))
        merged = {**node_by_id.get(node_id, {}), **visible_node}
        compact_nodes.append(merged)
    if not compact_nodes:
        compact_nodes = [node for node in nodes if isinstance(node, dict) and str(node.get("id")) in visible_id_set][:node_limit]

    compact_edges = [
        edge
        for edge in graph.get("edges", [])
        if isinstance(edge, dict)
        and str(edge.get("source")) in visible_id_set
        and str(edge.get("target")) in visible_id_set
    ]

    result["graph"] = {
        **graph,
        "node_count": graph.get("node_count", len(nodes)),
        "edge_count": graph.get("edge_count", len(graph.get("edges", []) or [])),
        "nodes": compact_nodes,
        "edges": compact_edges,
        "visible_node_count": len(compact_nodes),
        "visible_edge_count": len(compact_edges),
        "response_compacted": True,
    }
    return result


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
    node_limit: Annotated[
        int,
        Query(ge=0, description="Maximum diffusion-summary nodes; 0 means all summary nodes."),
    ] = 80,
    _current_user: User | None = Depends(get_current_user),
):
    """Analyze observed propagation paths, roles, objects, and evidence."""
    result = await _load_observed_analysis_cached(platform, event_id, node_limit)
    return success(data=result)


@router.get("/observed-analysis")
async def observed_analysis(
    platform: str | None = Query(None, description="Limit analysis to one platform."),
    event_id: str | None = Query(None, description="Limit analysis to one event id."),
    node_limit: Annotated[
        int,
        Query(ge=0, description="Maximum diffusion-summary nodes; 0 means all summary nodes."),
    ] = 80,
    _current_user: User | None = Depends(get_current_user),
):
    """Canonical observed-only Propagation Analysis endpoint."""
    result = await _load_observed_analysis_cached(platform, event_id, node_limit)
    return success(data=result)


@router.get("/monitor-profiles")
async def get_monitor_profiles(
    event_id: str | None = Query(None, description="Optionally limit profiles to one event."),
    db: AsyncSession = Depends(get_db),
    _current_user: User | None = Depends(get_current_user),
):
    """List event-level propagation monitoring configurations."""
    return success(data=await propagation_monitoring_service.list_monitor_profiles(db, event_id=event_id))


@router.put("/monitor-profiles")
async def put_monitor_profile(
    body: PropagationMonitorProfileRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User | None = Depends(get_current_user),
):
    """Create or update one event-level propagation monitoring configuration."""
    actor_id = _require_monitor_role(current_user, allow_admin_only=True)
    try:
        profile = await propagation_monitoring_service.upsert_monitor_profile(
            payload=body.model_dump(), updated_by=actor_id, db=db
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return success(data=profile)


@router.get("/alerts/unresolved-count")
async def get_unresolved_alert_count(
    db: AsyncSession = Depends(get_db),
    _current_user: User | None = Depends(get_current_user),
):
    """Return the global count of alerts awaiting analyst disposition."""
    return success(data={"count": await propagation_monitoring_service.unresolved_alert_count(db)})


@router.get("/alerts")
async def get_alerts(
    event_id: str | None = Query(None),
    platform: str | None = Query(None),
    state: str | None = Query(None),
    unresolved_only: bool = Query(False),
    limit: int = Query(100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
    _current_user: User | None = Depends(get_current_user),
):
    """List propagation alerts for monitoring and analyst disposition."""
    return success(data=await propagation_monitoring_service.list_alerts(
        db, event_id=event_id, platform=platform, state=state, unresolved_only=unresolved_only, limit=limit
    ))


@router.get("/alerts/{alert_id}")
async def get_alert(
    alert_id: int,
    db: AsyncSession = Depends(get_db),
    _current_user: User | None = Depends(get_current_user),
):
    """Read one propagation alert with its evidence snapshot and action audit."""
    try:
        return success(data=await propagation_monitoring_service.get_alert_detail(db, alert_id=alert_id))
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/alerts/{alert_id}/actions")
async def post_alert_action(
    alert_id: int,
    body: PropagationAlertActionRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User | None = Depends(get_current_user),
):
    """Record an analyst confirmation, closure, or ignore action for an alert."""
    actor_id = _require_monitor_role(current_user)
    try:
        alert = await propagation_monitoring_service.apply_alert_action(
            alert_id=alert_id, action=body.action, note=body.note, actor_id=actor_id, db=db
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return success(data=alert)


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
    _current_user: User | None = Depends(get_current_user),
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
