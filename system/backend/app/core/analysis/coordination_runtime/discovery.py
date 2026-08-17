from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from datetime import datetime, timezone
from typing import Any

from app.config import PROJECT_ROOT
from app.core.analysis.contracts import EventSnapshot
from app.core.analysis.coordination_discover import analyze_coordination_discover_snapshot

from .types import CoordinationDiscoveryResult, ResolvedSnapshotView


_STAGE1_MODULE_NAME = "_cogguard_runtime_coordination_stage1"


def _load_stage1_runtime_modules() -> Any:
    cached = sys.modules.get(_STAGE1_MODULE_NAME)
    if cached is not None:
        return cached
    package_dir = PROJECT_ROOT / "research" / "coordination_discover" / "stage1"
    init_file = package_dir / "__init__.py"
    if not init_file.exists():
        raise ImportError(f"Coordination Stage 1 contracts package not found: {init_file}")
    spec = importlib.util.spec_from_file_location(
        _STAGE1_MODULE_NAME,
        init_file,
        submodule_search_locations=[str(package_dir)],
    )
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load Coordination Stage 1 contracts from {init_file}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[_STAGE1_MODULE_NAME] = module
    spec.loader.exec_module(module)
    contracts_module = sys.modules.get(f"{_STAGE1_MODULE_NAME}.contracts")
    if contracts_module is None:
        raise ImportError(f"Coordination Stage 1 contracts module was not loaded: {package_dir / 'contracts.py'}")
    module.contracts = contracts_module
    return module


class CoordinationGroupDiscovery:
    def analyze(self, resolved_view: ResolvedSnapshotView, options: dict[str, Any] | None = None) -> CoordinationDiscoveryResult:
        result = analyze_coordination_discover_snapshot(resolved_view.snapshot, options)
        batch = _result_to_batch(resolved_view.snapshot, resolved_view, result, dict(options or {}))
        return CoordinationDiscoveryResult(
            resolved_view=resolved_view,
            batch=batch,
            network=dict(result.get("network") or {}),
            result=result,
        )

    def discover(self, resolved_view: ResolvedSnapshotView, options: dict[str, Any] | None = None):
        return self.analyze(resolved_view, options).batch


def _result_to_batch(
    snapshot: EventSnapshot,
    resolved_view: ResolvedSnapshotView,
    result: dict[str, Any],
    options: dict[str, Any],
):
    stage1 = _load_stage1_runtime_modules()
    contracts = stage1.contracts
    network = dict(result.get("network") or {})
    clusters = [cluster for cluster in network.get("clusters", []) if isinstance(cluster, dict)]
    evidence_edges = [edge for edge in result.get("evidence_edges", []) if isinstance(edge, dict)]
    account_rows = [row for row in result.get("account_stats", []) if isinstance(row, dict)]
    account_rows_by_id = {str(row.get("account_id") or ""): row for row in account_rows}
    platforms = tuple(sorted(str(platform) for platform in snapshot.platforms))
    batch_id = _batch_id(snapshot, resolved_view, clusters)
    timestamp = datetime.now(timezone.utc).isoformat()
    candidate_clusters = []
    for cluster in clusters:
        members = tuple(sorted(str(member) for member in cluster.get("members", []) if str(member).strip()))
        if not members:
            continue
        cluster_edges = [
            edge for edge in evidence_edges if str(edge.get("source") or "").strip() in set(members)
        ]
        cluster_accounts = [account_rows_by_id.get(member, {}) for member in members]
        candidate_clusters.append(
            contracts.DiscoveredCluster(
                cluster_id=f"resolved-{cluster.get('cluster_id', len(candidate_clusters))}",
                member_account_ids=members,
                coordination_metrics=_cluster_metrics(stage1, members, cluster, cluster_accounts, cluster_edges, result),
                evidence_refs=tuple(
                    sorted(
                        {
                            str(edge.get("evidence_ref") or "")
                            for edge in cluster_edges
                            if str(edge.get("evidence_ref") or "").strip()
                        }
                    )
                ),
                sparsified_subgraph_ref=f"coordination://stage1/{batch_id}#cluster-{cluster.get('cluster_id', len(candidate_clusters))}",
                embedding_ref=f"coordination://stage1/{batch_id}#embedding-{cluster.get('cluster_id', len(candidate_clusters))}",
                artifact_hashes={
                    "stage1_network": _hash_dict(network),
                },
                relation_types=tuple(
                    sorted(
                        {
                            str(edge.get("evidence_kind") or "")
                            for edge in cluster_edges
                            if str(edge.get("evidence_kind") or "").strip()
                        }
                    )
                ),
                window_ids=tuple(
                    sorted(
                        {
                            str(window.get("slice_id") or f"window-{index}")
                            for index, window in enumerate(result.get("windows", []))
                            if isinstance(window, dict)
                        }
                    )
                ),
                evidence_kind_counts=_count_edges(cluster_edges),
            )
        )

    provenance = contracts.DiscoveryProvenance(
        snapshot_id=snapshot.snapshot_id,
        data_fingerprint=snapshot.data_fingerprint,
        source_dataset=str(options.get("source_dataset") or "coordination_snapshot"),
        source_event=str(options.get("source_event") or snapshot.event_id),
        stage1_model_version="coordination-evidence-runtime-v2",
        tsgs_version="baseline.detect_groups",
        mhcr_version="baseline.generate_coordinated_network",
        created_at=timestamp,
        seed=_seed(snapshot),
        split_policy=str(options.get("split_policy") or "platform_resolved"),
        input_event_count=len(snapshot.posts) + len(snapshot.comments),
        input_account_count=len(resolved_view.account_mapping) or len({row.get("resolved_account_id") for row in resolved_view.snapshot.posts + resolved_view.snapshot.comments}),
        method_config_hash=_hash_dict({"options": options, "resolution_report": dict(resolved_view.resolution_report)}),
    )
    runtime_diagnostics = result.get("runtime_seconds") if isinstance(result.get("runtime_seconds"), dict) else {}
    return contracts.DiscoveredClusterBatch(
        batch_id=batch_id,
        timestamp=timestamp,
        candidate_clusters=tuple(candidate_clusters),
        provenance=provenance,
        runtime_diagnostics=contracts.DiscoveryRuntimeDiagnostics(
            tsgs_seconds=float(runtime_diagnostics.get("tsgs_seconds", 0.0)),
            mhcr_seconds=float(runtime_diagnostics.get("mhcr_seconds", 0.0)),
            leiden_seconds=float(runtime_diagnostics.get("leiden_seconds", 0.0)),
            total_seconds=float(runtime_diagnostics.get("total_seconds", 0.0)),
        ),
        platforms=platforms,
        quality_flags=_quality_flags(snapshot),
        artifact_manifest_ref=f"coordination://manifest/{batch_id}",
    )


def _cluster_metrics(stage1: Any, members: tuple[str, ...], cluster: dict[str, Any], cluster_accounts: list[dict[str, Any]], cluster_edges: list[dict[str, Any]], result: dict[str, Any]):
    size = len(members)
    possible_edges = size * (size - 1) / 2.0
    edge_count = int(cluster.get("edge_count", 0) or 0)
    total_weight = float(cluster.get("total_weight", 0) or 0)
    density = edge_count / possible_edges if possible_edges else 0.0
    coherence = min(1.0, total_weight / max(edge_count, 1) / max(size, 1))
    avg_time_delta = 0.0
    time_values = [float(row.get("avg_time_delta", 0.0) or 0.0) for row in cluster_accounts if isinstance(row, dict)]
    if time_values:
        avg_time_delta = sum(time_values) / len(time_values)
    temporal_sync = min(1.0, 1.0 / (1.0 + avg_time_delta))
    evidence_accounts = {
        str(edge.get("source") or "").strip()
        for edge in cluster_edges
        if str(edge.get("source") or "").strip()
    }
    coverage = len(evidence_accounts) / max(size, 1)
    relation_types = {
        str(edge.get("evidence_kind") or "").strip()
        for edge in cluster_edges
        if str(edge.get("evidence_kind") or "").strip()
    }
    relation_diversity = len(relation_types) / 7.0
    overall = min(
        1.0,
        0.35 * density + 0.25 * coherence + 0.15 * temporal_sync + 0.15 * coverage + 0.10 * relation_diversity,
    )
    return stage1.CoordinationMetricSet(
        tsgs_spectral_density=max(0.0, min(1.0, density)),
        mhcr_hyperedge_coherence=max(0.0, min(1.0, coherence)),
        temporal_sync_delta_seconds=float(avg_time_delta),
        overall_coordination_score=max(0.0, min(1.0, overall)),
        evidence_coverage=max(0.0, min(1.0, coverage)),
        relation_diversity=max(0.0, min(1.0, relation_diversity)),
    )


def _quality_flags(snapshot: EventSnapshot) -> tuple[str, ...]:
    flags = set()
    if any(not str(platform or "").strip() for platform in snapshot.platforms):
        flags.add("platform_missing")
    if snapshot.quality_report.status != "pass":
        flags.add("sparse_evidence")
    return tuple(sorted(flags))


def _batch_id(snapshot: EventSnapshot, resolved_view: ResolvedSnapshotView, clusters: list[dict[str, Any]]) -> str:
    digest = _hash_dict(
        {
            "snapshot_id": snapshot.snapshot_id,
            "data_fingerprint": snapshot.data_fingerprint,
            "resolution_report": dict(resolved_view.resolution_report),
            "clusters": [str(cluster.get("cluster_id") or "") for cluster in clusters],
        }
    )
    return f"discovery-{digest[:24]}"


def _hash_dict(value: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")).hexdigest()


def _count_edges(edges: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for edge in edges:
        kind = str(edge.get("evidence_kind") or "").strip()
        if not kind:
            continue
        counts[kind] = counts.get(kind, 0) + 1
    return counts


def _seed(snapshot: EventSnapshot) -> int:
    digest = snapshot.data_fingerprint or snapshot.snapshot_id
    return int(hashlib.sha256(digest.encode("utf-8")).hexdigest()[:8], 16)


__all__ = ["CoordinationGroupDiscovery", "CoordinationDiscoveryResult", "_load_stage1_runtime_modules"]
