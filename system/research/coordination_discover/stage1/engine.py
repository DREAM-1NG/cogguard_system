from __future__ import annotations

import hashlib
import json
import math
import time
from collections import Counter
from collections.abc import Iterable, Mapping
from dataclasses import asdict, dataclass

import numpy as np

from .clustering import LeidenConfig, LeidenPartitioner
from .contracts import (
    CoordinationMetricSet,
    DiscoveredCluster,
    DiscoveredClusterBatch,
    DiscoveryProvenance,
    DiscoveryRuntimeDiagnostics,
)
from .events import CoordinationEvent, validate_coordination_relation
from .mhcr import MHCRConfig, MHCREncoder, MHCRRepresentation
from .tsgs import TSGSConfig, TSGSResult, TemporalSketchGraphSparsifier


def _canonical_hash(value: object) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"


@dataclass(frozen=True, slots=True)
class DiscoveryConfig:
    tsgs: TSGSConfig = TSGSConfig()
    mhcr: MHCRConfig = MHCRConfig()
    clustering: LeidenConfig = LeidenConfig()

    def __post_init__(self) -> None:
        if not isinstance(self.tsgs, TSGSConfig):
            raise ValueError("tsgs must be a TSGSConfig")
        if not isinstance(self.mhcr, MHCRConfig):
            raise ValueError("mhcr must be an MHCRConfig")
        if not isinstance(self.clustering, LeidenConfig):
            raise ValueError("clustering must be a LeidenConfig")
        if len({self.tsgs.seed, self.mhcr.seed, self.clustering.seed}) != 1:
            raise ValueError("all Stage 1 components must use the same seed")

    @property
    def fingerprint(self) -> str:
        return _canonical_hash(asdict(self))


def _ordered_events(events: Iterable[CoordinationEvent]) -> tuple[CoordinationEvent, ...]:
    materialized = tuple(events)
    if not all(isinstance(event, CoordinationEvent) for event in materialized):
        raise ValueError("events must contain CoordinationEvent values")
    for event in materialized:
        validate_coordination_relation(event.relation)
    return tuple(
        sorted(
            materialized,
            key=lambda event: (
                event.account_id,
                event.relation,
                event.object_id,
                event.observed_at,
                event.evidence_ref,
                event.weight,
            ),
        )
    )


def _embedding_hash(representation: MHCRRepresentation) -> str:
    return _canonical_hash(
        {
            "account_ids": representation.account_ids,
            "embeddings": representation.embeddings,
            "objective": representation.objective,
            "augmentations": representation.training_diagnostics.augmentations,
            "final_infonce_loss": representation.training_diagnostics.final_infonce_loss,
        }
    )


def _graph_hash(tsgs_result: TSGSResult) -> str:
    return _canonical_hash(
        [
            (edge.source_account_id, edge.target_account_id, edge.weight)
            for edge in tsgs_result.candidate_graph_edges
        ]
    )


def _cluster_metrics(
    members: tuple[str, ...],
    events: tuple[CoordinationEvent, ...],
    tsgs_result: TSGSResult,
    representation: MHCRRepresentation,
    fused_edges: tuple,
    global_relations: frozenset[str],
    time_bucket_seconds: int,
) -> CoordinationMetricSet:
    member_set = set(members)
    possible_edges = len(members) * (len(members) - 1) // 2
    internal_tsgs_edges = tuple(
        edge
        for edge in tsgs_result.candidate_graph_edges
        if edge.source_account_id in member_set and edge.target_account_id in member_set
    )
    density = len(internal_tsgs_edges) / possible_edges if possible_edges else 0.0
    internal_fused_edges = tuple(
        edge
        for edge in fused_edges
        if edge.source_account_id in member_set and edge.target_account_id in member_set
    )
    coherence = (
        math.fsum(edge.embedding_affinity for edge in internal_fused_edges)
        / len(internal_fused_edges)
        if internal_fused_edges
        else 0.0
    )
    cluster_events = tuple(event for event in events if event.account_id in member_set)
    timestamps = [event.observed_at.timestamp() for event in cluster_events]
    temporal_delta = max(timestamps) - min(timestamps) if len(timestamps) > 1 else 0.0
    accounts_with_evidence = {event.account_id for event in cluster_events}
    coverage = len(accounts_with_evidence) / len(members)
    cluster_relations = {event.relation for event in cluster_events}
    relation_diversity = (
        len(cluster_relations) / len(global_relations) if global_relations else 0.0
    )
    temporal_ranking = math.exp(-temporal_delta / max(1, time_bucket_seconds))
    overall = (
        0.30 * density
        + 0.30 * coherence
        + 0.20 * temporal_ranking
        + 0.10 * coverage
        + 0.10 * relation_diversity
    )
    return CoordinationMetricSet(
        tsgs_spectral_density=min(1.0, max(0.0, density)),
        mhcr_hyperedge_coherence=min(1.0, max(0.0, coherence)),
        temporal_sync_delta_seconds=float(temporal_delta),
        overall_coordination_score=min(1.0, max(0.0, overall)),
        evidence_coverage=min(1.0, max(0.0, coverage)),
        relation_diversity=min(1.0, max(0.0, relation_diversity)),
    )


def _build_cluster(
    members: tuple[str, ...],
    events: tuple[CoordinationEvent, ...],
    provenance: DiscoveryProvenance,
    config: DiscoveryConfig,
    tsgs_result: TSGSResult,
    representation: MHCRRepresentation,
    fused_edges: tuple,
    global_relations: frozenset[str],
    graph_hash: str,
    embedding_hash: str,
) -> DiscoveredCluster:
    member_set = set(members)
    cluster_events = tuple(event for event in events if event.account_id in member_set)
    identity_hash = _canonical_hash(
        {"snapshot_id": provenance.snapshot_id, "members": members}
    ).split(":", 1)[1][:20]
    cluster_id = f"cluster-{identity_hash}"
    relation_counts = Counter(event.relation for event in cluster_events)
    window_ids = tuple(
        sorted(
            {
                f"window-{math.floor(event.observed_at.timestamp() / config.mhcr.time_bucket_seconds)}"
                for event in cluster_events
            }
        )
    )
    return DiscoveredCluster(
        cluster_id=cluster_id,
        member_account_ids=members,
        coordination_metrics=_cluster_metrics(
            members,
            events,
            tsgs_result,
            representation,
            fused_edges,
            global_relations,
            config.mhcr.time_bucket_seconds,
        ),
        evidence_refs=tuple(event.evidence_ref for event in cluster_events),
        sparsified_subgraph_ref=f"stage1://tsgs/{graph_hash.split(':', 1)[1]}#{cluster_id}",
        embedding_ref=f"stage1://mhcr/{embedding_hash.split(':', 1)[1]}#{cluster_id}",
        artifact_hashes={
            "mhcr_embeddings": embedding_hash,
            "tsgs_candidate_graph": graph_hash,
        },
        relation_types=tuple(relation_counts),
        window_ids=window_ids,
        evidence_kind_counts=dict(relation_counts),
    )


class CoordinationDiscoveryEngine:
    def __init__(self, config: DiscoveryConfig | None = None) -> None:
        self.config = config or DiscoveryConfig()
        if not isinstance(self.config, DiscoveryConfig):
            raise ValueError("config must be a DiscoveryConfig")

    def discover(
        self,
        events: Iterable[CoordinationEvent],
        provenance: DiscoveryProvenance,
    ) -> DiscoveredClusterBatch:
        if not isinstance(provenance, DiscoveryProvenance):
            raise ValueError("provenance must be a DiscoveryProvenance")
        total_started = time.perf_counter()
        ordered_events = _ordered_events(events)

        phase_started = time.perf_counter()
        tsgs_result = TemporalSketchGraphSparsifier(self.config.tsgs).fit_transform(
            ordered_events
        )
        tsgs_seconds = time.perf_counter() - phase_started

        phase_started = time.perf_counter()
        representation = MHCREncoder(self.config.mhcr).fit_transform(
            ordered_events, tsgs_result
        )
        mhcr_seconds = time.perf_counter() - phase_started

        phase_started = time.perf_counter()
        partition = LeidenPartitioner(self.config.clustering).partition(
            tsgs_result, representation
        )
        leiden_seconds = time.perf_counter() - phase_started
        graph_hash = _graph_hash(tsgs_result)
        embedding_hash = _embedding_hash(representation)
        global_relations = frozenset(event.relation for event in ordered_events)
        clusters = tuple(
            _build_cluster(
                members,
                ordered_events,
                provenance,
                self.config,
                tsgs_result,
                representation,
                partition.fused_graph.edges,
                global_relations,
                graph_hash,
                embedding_hash,
            )
            for members in partition.communities
        )
        batch_identity = _canonical_hash(
            {
                "snapshot_id": provenance.snapshot_id,
                "data_fingerprint": provenance.data_fingerprint,
                "config": self.config.fingerprint,
                "clusters": [cluster.cluster_id for cluster in clusters],
            }
        ).split(":", 1)[1][:24]
        quality_flags = ["platform_missing"]
        if not ordered_events or partition.no_edge:
            quality_flags.append("sparse_evidence")
        total_seconds = time.perf_counter() - total_started
        return DiscoveredClusterBatch(
            batch_id=f"discovery-{batch_identity}",
            timestamp=provenance.created_at,
            candidate_clusters=clusters,
            provenance=provenance,
            runtime_diagnostics=DiscoveryRuntimeDiagnostics(
                tsgs_seconds=tsgs_seconds,
                mhcr_seconds=mhcr_seconds,
                leiden_seconds=leiden_seconds,
                total_seconds=total_seconds,
            ),
            platforms=(),
            quality_flags=tuple(quality_flags),
            artifact_manifest_ref=f"stage1://manifest/{batch_identity}",
        )


__all__ = ["CoordinationDiscoveryEngine", "DiscoveryConfig"]
