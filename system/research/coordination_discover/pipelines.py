from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Literal, cast

from .artifacts import create_manifest, write_discover_artifact
from .contracts import (
    KT1_TECHNOLOGY,
    DiscoverResult,
    DynamicDiscoverRequest,
)
from .evidence import build_evidence_graph
from .evaluation import run_detect_validation as _run_detect_validation
from .models import build_account_pair_edges, fit_temporal_magnn, partition_learned_graph


def run_dynamic_discover(request: DynamicDiscoverRequest) -> DiscoverResult:
    graph = build_evidence_graph(request.snapshot)
    try:
        learned = fit_temporal_magnn(graph, config=request.model_config)
    except RuntimeError as exc:
        learned = {
            "status": "model_unavailable",
            "model_backend": "temporal_magnn_style",
            "device": "unavailable",
            "loss_history": [],
            "model_input": {"feature_names": [], "edge_count": 0},
            "account_object_edges": [],
            "pair_edges": [],
            "communities": [],
            "partition_backend": "none",
            "attention": {},
            "node_embeddings": {},
            "error": str(exc),
        }

    status = str(learned.get("status") or "data_insufficient")
    manifest = create_manifest(
        data_fingerprint=graph.data_fingerprint,
        model_version=request.model_version,
        config=request.model_config,
        artifact_dir=request.artifact_dir or ".",
        source_dataset=request.source_dataset,
        source_event=request.source_event or graph.event_id,
        status="ok" if status == "ok" else status,
        fallback_policy=request.fallback_policy,
        modality_policy=request.modality_policy,
        partition_backend=str(learned.get("partition_backend") or "none"),
    )
    learned_edge_graph = _learned_edge_graph(graph.accounts, learned)
    normalized_status = cast(
        Literal["ok", "data_insufficient", "model_unavailable"],
        status if status in {"ok", "data_insufficient", "model_unavailable"} else "data_insufficient",
    )
    result = DiscoverResult(
        status=normalized_status,
        snapshot_id=graph.snapshot_id,
        event_id=graph.event_id,
        data_fingerprint=graph.data_fingerprint,
        model_version=request.model_version,
        evidence_graph=graph.to_dict(),
        learned_edge_graph=learned_edge_graph,
        communities=list(learned.get("communities") or []),
        lineage=_community_lineage(
            account_object_edges=list(learned.get("account_object_edges") or []),
            accounts=graph.accounts,
            window_hours=request.window_hours,
            overlap_ratio=request.overlap_ratio,
            min_score=float(request.model_config.min_learned_edge_score),
        ),
        attention=dict(learned.get("attention") or {}),
        audit_metrics={
            "evidence_coverage": graph.coverage,
            "excluded_modality_fields": graph.excluded_fields,
            "excluded_modality_field_count": len(graph.excluded_fields),
            "topology_audit_feature_names": list(graph.topology_audit_features.get("feature_names", [])),
            "topology_feature_role": graph.topology_audit_features.get("feature_role", "audit_only"),
            "model_input": dict(learned.get("model_input") or {}),
            "loss_history": list(learned.get("loss_history") or []),
            "partition_backend": learned.get("partition_backend"),
            "device": learned.get("device"),
        },
        manifest=manifest,
        fallback_reason=learned.get("error"),
    )
    if request.artifact_dir:
        write_discover_artifact(
            result,
            artifact_dir=request.artifact_dir,
            coordination_result=export_coordination_result(result),
        )
    return result


def run_detect_validation(request: Any, discovery: Any | None = None) -> Any:
    return _run_detect_validation(request, discovery=discovery)


def export_coordination_result(
    discovery: DiscoverResult | dict[str, Any],
    detect: Any | None = None,
) -> dict[str, Any]:
    payload = discovery.to_dict() if isinstance(discovery, DiscoverResult) else dict(discovery)
    learned_graph = dict(payload.get("learned_edge_graph") or {})
    evidence_graph = dict(payload.get("evidence_graph") or {})
    account_object_edges = list(learned_graph.get("account_object_edges") or [])
    pair_edges = list(learned_graph.get("edges") or [])
    communities = list(payload.get("communities") or [])
    audit_metrics = dict(payload.get("audit_metrics") or {})
    manifest = dict(payload.get("manifest") or {})
    status = str(payload.get("status") or "data_insufficient")

    result = {
        "status": status,
        "technology": KT1_TECHNOLOGY,
        "model_version": str(payload.get("model_version") or manifest.get("model_version") or ""),
        "model_role": "dynamic_discover",
        "detect_role": "validation_only",
        "snapshot_id": str(payload.get("snapshot_id") or ""),
        "event_id": str(payload.get("event_id") or ""),
        "summary": {
            "event_id": str(payload.get("event_id") or ""),
            "status": status,
            "coordinated_accounts": _coordinated_account_count(pair_edges),
            "coordinated_edges": len(pair_edges),
            "cluster_count": len(communities),
            "evidence_edge_count": len(evidence_graph.get("edges") or []),
            "evidence_object_count": len(evidence_graph.get("objects") or []),
            "excluded_modality_field_count": audit_metrics.get("excluded_modality_field_count", 0),
            "partition_backend": audit_metrics.get("partition_backend"),
        },
        "community_lineage": list(payload.get("lineage") or _lineage_from_communities(communities)),
        "communities": communities,
        "account_risk_tiers": _account_risk_tiers(pair_edges),
        "evidence_edges": _export_evidence_edges(account_object_edges),
        "evidence_coverage": dict(audit_metrics.get("evidence_coverage") or {}),
        "learned_edge_graph": learned_graph,
        "attention": dict(payload.get("attention") or {}),
        "audit_metrics": audit_metrics,
        "artifact_manifest": manifest,
        "abstain": status != "ok",
        "fallback": False,
        "fallback_reason": None,
        "error": payload.get("fallback_reason") if status != "ok" else None,
        "network": _network_compat(learned_graph),
    }
    if detect is not None:
        result["detect_validation"] = detect.to_dict() if hasattr(detect, "to_dict") else detect
    return result


def _learned_edge_graph(accounts: list[str], learned: dict[str, Any]) -> dict[str, Any]:
    pair_edges = list(learned.get("pair_edges") or [])
    return {
        "nodes": [{"id": account, "type": "account"} for account in sorted(accounts)],
        "edges": pair_edges,
        "node_count": len(accounts),
        "edge_count": len(pair_edges),
        "account_object_edges": list(learned.get("account_object_edges") or []),
        "partition_backend": learned.get("partition_backend"),
        "node_embeddings": dict(learned.get("node_embeddings") or {}),
    }


def _community_lineage(
    *,
    account_object_edges: list[dict[str, Any]],
    accounts: list[str],
    window_hours: tuple[int, ...],
    overlap_ratio: float,
    min_score: float,
) -> list[dict[str, Any]]:
    if not account_object_edges:
        return []
    timestamps = [float(edge.get("observed_at", 0.0)) for edge in account_object_edges]
    start = min(timestamps)
    end = max(timestamps)
    if start == end:
        end = start + 3600

    occurrences: list[dict[str, Any]] = []
    for hours in window_hours:
        width = max(1, int(hours)) * 3600
        step = max(1, int(width * max(0.05, 1.0 - float(overlap_ratio))))
        slice_start = start
        slice_index = 0
        while slice_start <= end and slice_index < 24:
            slice_end = min(end + 1, slice_start + width)
            rows = [
                edge
                for edge in account_object_edges
                if slice_start <= float(edge.get("observed_at", 0.0)) < slice_end
            ]
            if rows:
                pair_edges = build_account_pair_edges(rows, min_score=min_score)
                partition = partition_learned_graph(accounts=accounts, pair_edges=pair_edges, min_score=min_score)
                for community in partition["communities"]:
                    if int(community.get("size", 0)) < 2:
                        continue
                    occurrences.append(
                        {
                            "window_hours": int(hours),
                            "slice_index": slice_index,
                            "slice_start": _iso(slice_start),
                            "slice_end": _iso(slice_end),
                            "community": community,
                        }
                    )
            slice_start += step
            slice_index += 1

    lineages: list[dict[str, Any]] = []
    for occurrence in occurrences:
        members = tuple(sorted(occurrence["community"].get("members") or []))
        if not members:
            continue
        best = None
        best_score = 0.0
        for lineage in lineages:
            score = _jaccard(members, lineage["representative_members"])
            if score > best_score:
                best = lineage
                best_score = score
        if best is None or best_score < 0.45:
            best = {
                "lineage_id": f"lineage_{len(lineages) + 1}",
                "representative_members": members,
                "occurrences": [],
            }
            lineages.append(best)
        community = occurrence["community"]
        best["occurrences"].append(
            {
                "window_hours": occurrence["window_hours"],
                "slice_index": occurrence["slice_index"],
                "slice_start": occurrence["slice_start"],
                "slice_end": occurrence["slice_end"],
                "community_id": community.get("community_id"),
                "members": list(members),
                "learned_weight": community.get("learned_weight", 0.0),
                "evidence_objects": community.get("evidence_objects", []),
            }
        )

    rows = []
    for lineage in lineages:
        history = [tuple(item["members"]) for item in lineage["occurrences"]]
        stability_values = [_jaccard(left, right) for left, right in zip(history, history[1:])]
        evidence_objects = []
        for occurrence in lineage["occurrences"]:
            evidence_objects.extend(occurrence.get("evidence_objects", []))
        rows.append(
            {
                "lineage_id": lineage["lineage_id"],
                "support_count": len(lineage["occurrences"]),
                "stability_score": round(sum(stability_values) / len(stability_values), 6)
                if stability_values
                else 1.0,
                "members": list(lineage["representative_members"]),
                "shared_objects": sorted(set(evidence_objects))[:25],
                "windows": lineage["occurrences"],
            }
        )
    return sorted(rows, key=lambda item: (item["support_count"], item["stability_score"]), reverse=True)


def _lineage_from_communities(communities: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "lineage_id": str(community.get("community_id") or index),
            "support_count": 1,
            "stability_score": 1.0,
            "members": list(community.get("members") or []),
            "shared_objects": list(community.get("evidence_objects") or []),
            "windows": [],
        }
        for index, community in enumerate(communities, start=1)
    ]


def _account_risk_tiers(pair_edges: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_account: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for edge in pair_edges:
        by_account[str(edge.get("source"))].append(edge)
        by_account[str(edge.get("target"))].append(edge)
    scores = {
        account: sum(float(edge.get("learned_score", 0.0)) for edge in edges) / max(len(edges), 1)
        for account, edges in by_account.items()
        if account
    }
    if not scores:
        return []
    sorted_scores = sorted(scores.values())
    high_cut = sorted_scores[int(0.75 * (len(sorted_scores) - 1))]
    medium_cut = sorted_scores[int(0.4 * (len(sorted_scores) - 1))]
    rows = []
    for account, score in sorted(scores.items(), key=lambda item: item[1], reverse=True):
        if score >= high_cut:
            tier = "high_learned_coordination"
        elif score >= medium_cut:
            tier = "medium_learned_coordination"
        else:
            tier = "light_learned_coordination"
        objects = []
        for edge in by_account[account]:
            objects.extend(edge.get("evidence_objects", []))
        rows.append(
            {
                "account_id": account,
                "account_label": account,
                "tier": tier,
                "evidence": {
                    "mean_learned_edge_score": round(score, 6),
                    "supporting_edge_count": len(by_account[account]),
                    "supporting_objects_preview": sorted(set(objects))[:10],
                },
            }
        )
    return rows


def _export_evidence_edges(account_object_edges: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "source": edge.get("source_account_id"),
            "target": edge.get("evidence_object_id"),
            "content_id": edge.get("content_id"),
            "evidence_kind": edge.get("evidence_kind"),
            "relation_type": edge.get("relation_type"),
            "evidence_ref": edge.get("evidence_ref"),
            "platform": edge.get("platform"),
            "observed_at": edge.get("observed_at"),
            "learned_score": edge.get("learned_score"),
        }
        for edge in account_object_edges
    ]


def _network_compat(learned_graph: dict[str, Any]) -> dict[str, Any]:
    edges = list(learned_graph.get("edges") or [])
    nodes = list(learned_graph.get("nodes") or [])
    return {
        "nodes": nodes,
        "edges": edges,
        "node_count": len(nodes),
        "edge_count": len(edges),
        "component_count": 0,
        "components": [],
        "cluster_count": 0,
        "clusters": [],
    }


def _coordinated_account_count(pair_edges: list[dict[str, Any]]) -> int:
    accounts = set()
    for edge in pair_edges:
        accounts.add(edge.get("source"))
        accounts.add(edge.get("target"))
    accounts.discard(None)
    accounts.discard("")
    return len(accounts)


def _jaccard(left: tuple[str, ...], right: tuple[str, ...]) -> float:
    left_set = set(left)
    right_set = set(right)
    if not left_set or not right_set:
        return 0.0
    return len(left_set & right_set) / len(left_set | right_set)


def _iso(timestamp: float) -> str:
    return datetime.fromtimestamp(timestamp, tz=timezone.utc).isoformat()


__all__ = ["export_coordination_result", "run_detect_validation", "run_dynamic_discover"]
