"""Propagation Monitoring behavior shared by HTTP and Celery adapters."""

from __future__ import annotations

import asyncio
import copy
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any, Protocol


SUPPORTED_OBSERVATION_RATIOS = frozenset({0.1, 0.3, 0.5})
DEFAULT_CACHE_TTL_SECONDS = 300
DEFAULT_TEXT_PREVIEW_CHARS = 160


class MonitoringPersistencePort(Protocol):
    async def list_monitor_profiles(self, db: Any, *, event_id: str | None = None) -> list[dict]: ...

    async def upsert_monitor_profile(self, *, payload: dict, updated_by: int, db: Any) -> dict: ...

    async def unresolved_alert_count(self, db: Any) -> int: ...

    async def list_alerts(self, db: Any, **query: Any) -> list[dict]: ...

    async def get_alert_detail(self, db: Any, *, alert_id: int) -> dict: ...

    async def apply_alert_action(self, **command: Any) -> dict: ...

    async def run_due_monitor_profiles(self, db: Any) -> list[dict]: ...


@dataclass(frozen=True, slots=True)
class PropagationMonitoringPorts:
    observe: Callable[..., Awaitable[dict]]
    forecast: Callable[..., Awaitable[dict]]
    validate_cutoff: Callable[[str | None], Any]
    enforce_forecast: Callable[..., dict]
    persistence: MonitoringPersistencePort


class PropagationMonitoring:
    """Expose complete monitoring use cases behind one testable interface."""

    def __init__(
        self,
        ports: PropagationMonitoringPorts,
        *,
        cache_ttl_seconds: int = DEFAULT_CACHE_TTL_SECONDS,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._ports = ports
        self._cache_ttl_seconds = cache_ttl_seconds
        self._clock = clock
        self._observed_cache: dict[tuple[str, str, int], tuple[float, dict]] = {}
        self._observed_in_flight: dict[tuple[str, str, int], asyncio.Task] = {}

    def clear_observed_cache(self) -> None:
        self._observed_cache.clear()
        self._observed_in_flight.clear()

    async def observed(
        self,
        *,
        platform: str | None,
        event_id: str | None,
        node_limit: int,
    ) -> dict:
        key = (platform or "", event_id or "", int(node_limit))
        cached = self._observed_cache.get(key)
        if cached is not None:
            created_at, payload = cached
            if self._clock() - created_at < self._cache_ttl_seconds:
                return copy.deepcopy(payload)
            self._observed_cache.pop(key, None)

        task = self._observed_in_flight.get(key)
        if task is None or task.done():
            async def compute() -> dict:
                result = await self._ports.observe(
                    platform=platform,
                    event_id=event_id,
                    node_limit=node_limit,
                )
                compact = _compact_observed_result(result, node_limit=node_limit)
                self._observed_cache[key] = (self._clock(), copy.deepcopy(compact))
                return compact

            task = asyncio.create_task(compute())
            self._observed_in_flight[key] = task

        try:
            return copy.deepcopy(await task)
        finally:
            if task.done():
                self._observed_in_flight.pop(key, None)

    async def forecast(
        self,
        *,
        event_id: str,
        platform: str | None,
        top_k: int,
        observed_until: str | None,
        t_obs: str | None,
        observation_ratio: float,
        prediction_horizon: int | None,
    ) -> dict:
        observed_cutoff = self._ports.validate_cutoff(observed_until)
        alias_cutoff = self._ports.validate_cutoff(t_obs)
        if observed_cutoff is not None and alias_cutoff is not None and observed_cutoff != alias_cutoff:
            raise ValueError("observed_until and t_obs must identify the same instant.")
        if round(float(observation_ratio), 4) not in SUPPORTED_OBSERVATION_RATIOS:
            raise ValueError("observation_ratio must be one of 0.1, 0.3, or 0.5.")
        if prediction_horizon is not None:
            raise ValueError(
                "The deployed checkpoint exposes normalized trajectory steps; "
                "wall-clock prediction_horizon is unsupported."
            )

        result = await self._ports.forecast(
            platform=platform,
            event_id=event_id,
            top_k=top_k,
            observed_until=observed_until or t_obs,
            observation_ratio=observation_ratio,
        )
        return self._ports.enforce_forecast(result, event_id=event_id, platform=platform)

    async def list_monitor_profiles(self, db: Any, *, event_id: str | None = None) -> list[dict]:
        return await self._ports.persistence.list_monitor_profiles(db, event_id=event_id)

    async def upsert_monitor_profile(self, *, payload: dict, updated_by: int, db: Any) -> dict:
        return await self._ports.persistence.upsert_monitor_profile(
            payload=payload,
            updated_by=updated_by,
            db=db,
        )

    async def unresolved_alert_count(self, db: Any) -> int:
        return await self._ports.persistence.unresolved_alert_count(db)

    async def list_alerts(self, db: Any, **query: Any) -> list[dict]:
        return await self._ports.persistence.list_alerts(db, **query)

    async def get_alert_detail(self, db: Any, *, alert_id: int) -> dict:
        return await self._ports.persistence.get_alert_detail(db, alert_id=alert_id)

    async def apply_alert_action(self, **command: Any) -> dict:
        return await self._ports.persistence.apply_alert_action(**command)

    async def run_due_monitor_profiles(self, db: Any) -> list[dict]:
        return await self._ports.persistence.run_due_monitor_profiles(db)


def build_default_propagation_monitoring(
    *,
    observe: Callable[..., Awaitable[dict]] | None = None,
    forecast: Callable[..., Awaitable[dict]] | None = None,
) -> PropagationMonitoring:
    from app.services import (
        propagation_model_service,
        propagation_monitoring_service,
        propagation_observation_service,
    )

    async def default_observe(**query: Any) -> dict:
        return await propagation_observation_service.analyze_observed_propagation(**query)

    async def default_forecast(**query: Any) -> dict:
        return await propagation_model_service.predict_current_event_model(**query)

    return PropagationMonitoring(
        PropagationMonitoringPorts(
            observe=observe or default_observe,
            forecast=forecast or default_forecast,
            validate_cutoff=propagation_model_service.validate_observed_until,
            enforce_forecast=propagation_model_service.enforce_prediction_contract,
            persistence=propagation_monitoring_service,
        )
    )


def _truncate_text(value: Any, *, max_chars: int = DEFAULT_TEXT_PREVIEW_CHARS) -> Any:
    if not isinstance(value, str) or len(value) <= max_chars:
        return value
    return value[:max_chars].rstrip() + "…"


def _compact_post_like(item: Any) -> Any:
    if not isinstance(item, dict):
        return item
    compact = copy.deepcopy(item)
    if "content" in compact:
        compact["content"] = _truncate_text(compact.get("content"))
    compact.pop("raw_data", None)
    return compact


def _compact_observed_result(result: dict, *, node_limit: int) -> dict:
    if node_limit <= 0:
        return result

    result = copy.deepcopy(result)
    _compact_provenance_graph(result)
    _compact_timeline(result, node_limit=node_limit)
    _compact_evidence_chains(result, node_limit=node_limit)
    _compact_graph(result, node_limit=node_limit)
    return result


def _compact_timeline(result: dict, *, node_limit: int) -> None:
    timeline = result.get("timeline")
    if not isinstance(timeline, list):
        return
    result["timeline"] = [_compact_post_like(item) for item in timeline[:node_limit]]
    meta = result.setdefault("response_meta", {})
    meta["timeline_total_count"] = len(timeline)
    meta["timeline_visible_count"] = len(result["timeline"])


def _compact_evidence_chains(result: dict, *, node_limit: int) -> None:
    chains = result.get("evidence_chains")
    if not isinstance(chains, list):
        return
    limit = max(1, min(node_limit, 20))
    compact_chains = []
    for chain in chains[:limit]:
        if not isinstance(chain, dict):
            compact_chains.append(chain)
            continue
        compact = copy.deepcopy(chain)
        posts = compact.get("supporting_posts")
        if isinstance(posts, list):
            compact["supporting_posts"] = [_compact_post_like(post) for post in posts[:limit]]
            compact["supporting_post_total_count"] = len(posts)
        compact_chains.append(compact)
    result["evidence_chains"] = compact_chains
    meta = result.setdefault("response_meta", {})
    meta["evidence_chain_total_count"] = len(chains)
    meta["evidence_chain_visible_count"] = len(compact_chains)


def _compact_provenance_graph(result: dict) -> None:
    graph = result.get("provenance_graph")
    if not isinstance(graph, dict):
        return
    nodes = graph.get("nodes")
    edges = graph.get("edges")
    result["provenance_graph"] = {
        "summary": {
            "node_count": len(nodes) if isinstance(nodes, list) else graph.get("node_count", 0),
            "edge_count": len(edges) if isinstance(edges, list) else graph.get("edge_count", 0),
        },
        "response_compacted": True,
    }


def _compact_graph(result: dict, *, node_limit: int) -> None:
    graph = result.get("graph")
    if not isinstance(graph, dict):
        return
    nodes = graph.get("nodes")
    if not isinstance(nodes, list) or len(nodes) <= node_limit:
        return

    diffusion = result.get("diffusion_summary")
    visible_nodes = (
        diffusion.get("visible_nodes")
        if isinstance(diffusion, dict) and isinstance(diffusion.get("visible_nodes"), list)
        else []
    )
    visible_ids = [str(node.get("id")) for node in visible_nodes if isinstance(node, dict) and node.get("id") is not None]
    if not visible_ids:
        visible_ids = [str(node.get("id")) for node in nodes[:node_limit] if isinstance(node, dict) and node.get("id") is not None]
    visible_ids = visible_ids[:node_limit]
    visible_id_set = set(visible_ids)
    node_by_id = {str(node.get("id")): node for node in nodes if isinstance(node, dict) and node.get("id") is not None}
    compact_nodes = [
        {**node_by_id.get(str(node.get("id")), {}), **node}
        for node in visible_nodes[:node_limit]
        if isinstance(node, dict)
    ]
    if not compact_nodes:
        compact_nodes = [node_by_id[node_id] for node_id in visible_ids if node_id in node_by_id]
    edges = graph.get("edges") if isinstance(graph.get("edges"), list) else []
    compact_edges = [
        edge
        for edge in edges
        if isinstance(edge, dict)
        and str(edge.get("source")) in visible_id_set
        and str(edge.get("target")) in visible_id_set
    ]
    result["graph"] = {
        **graph,
        "node_count": graph.get("node_count", len(nodes)),
        "edge_count": graph.get("edge_count", len(edges)),
        "nodes": compact_nodes,
        "edges": compact_edges,
        "visible_node_count": len(compact_nodes),
        "visible_edge_count": len(compact_edges),
        "response_compacted": True,
    }
