from __future__ import annotations

import math
from dataclasses import dataclass

import igraph as ig
import leidenalg
import numpy as np

from .mhcr import MHCRRepresentation
from .tsgs import TSGSResult


def _finite_float(
    value: object,
    field_name: str,
    *,
    minimum: float,
    maximum: float | None = None,
) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{field_name} must be numeric")
    number = float(value)
    if not math.isfinite(number) or number < minimum or (
        maximum is not None and number > maximum
    ):
        raise ValueError(f"{field_name} is outside its supported finite range")
    return number


@dataclass(frozen=True, slots=True)
class LeidenConfig:
    resolution: float = 0.1
    embedding_affinity_weight: float = 0.5
    iterations: int = 4
    seed: int = 0

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "resolution",
            _finite_float(self.resolution, "resolution", minimum=np.finfo(float).tiny),
        )
        object.__setattr__(
            self,
            "embedding_affinity_weight",
            _finite_float(
                self.embedding_affinity_weight,
                "embedding_affinity_weight",
                minimum=0.0,
                maximum=1.0,
            ),
        )
        if isinstance(self.iterations, bool) or not isinstance(self.iterations, int) or self.iterations < 1:
            raise ValueError("iterations must be an integer >= 1")
        if isinstance(self.seed, bool) or not isinstance(self.seed, int):
            raise ValueError("seed must be an integer")


@dataclass(frozen=True, slots=True, order=True)
class FusedAffinityEdge:
    source_account_id: str
    target_account_id: str
    weight: float
    tsgs_weight: float
    embedding_affinity: float


@dataclass(frozen=True, slots=True)
class FusedAffinityGraph:
    account_ids: tuple[str, ...]
    edges: tuple[FusedAffinityEdge, ...]
    evaluated_embedding_pair_count: int
    source_graph: str = "explicit_tsgs_candidate_graph"


@dataclass(frozen=True, slots=True)
class LeidenPartition:
    communities: tuple[tuple[str, ...], ...]
    singleton_account_ids: tuple[str, ...]
    fused_graph: FusedAffinityGraph
    no_edge: bool
    status: str
    method: str = "leiden"
    role: str = "interpretation_partition_not_activation"


def fuse_candidate_edges(
    tsgs_result: TSGSResult,
    representation: MHCRRepresentation,
    config: LeidenConfig | None = None,
) -> FusedAffinityGraph:
    resolved = config or LeidenConfig()
    if tsgs_result.account_ids != representation.account_ids:
        raise ValueError("tsgs_result and representation account IDs must match")
    embeddings = np.asarray(representation.embeddings, dtype=float)
    if embeddings.size == 0:
        embeddings = np.empty((0, 0), dtype=float)
    if embeddings.ndim != 2 or embeddings.shape[0] != len(tsgs_result.account_ids):
        raise ValueError("representation embeddings must have one row per account")
    index = {account_id: position for position, account_id in enumerate(tsgs_result.account_ids)}
    norms = np.linalg.norm(embeddings, axis=1) if len(embeddings) else np.empty(0)
    fused_edges = []
    for edge in tsgs_result.candidate_graph_edges:
        left = index[edge.source_account_id]
        right = index[edge.target_account_id]
        denominator = norms[left] * norms[right]
        cosine = float(np.dot(embeddings[left], embeddings[right]) / denominator) if denominator > 0.0 else 0.0
        affinity = min(1.0, max(0.0, (cosine + 1.0) * 0.5))
        fused_edges.append(
            FusedAffinityEdge(
                source_account_id=edge.source_account_id,
                target_account_id=edge.target_account_id,
                weight=float(edge.weight * (1.0 + resolved.embedding_affinity_weight * affinity)),
                tsgs_weight=float(edge.weight),
                embedding_affinity=affinity,
            )
        )
    return FusedAffinityGraph(
        account_ids=tsgs_result.account_ids,
        edges=tuple(fused_edges),
        evaluated_embedding_pair_count=len(fused_edges),
    )


class LeidenPartitioner:
    def __init__(self, config: LeidenConfig | None = None) -> None:
        self.config = config or LeidenConfig()
        if not isinstance(self.config, LeidenConfig):
            raise ValueError("config must be a LeidenConfig")

    def partition(
        self,
        tsgs_result: TSGSResult,
        representation: MHCRRepresentation,
    ) -> LeidenPartition:
        fused = fuse_candidate_edges(tsgs_result, representation, self.config)
        if not fused.account_ids:
            return LeidenPartition(
                communities=(),
                singleton_account_ids=(),
                fused_graph=fused,
                no_edge=True,
                status="empty_graph",
            )
        if not fused.edges:
            communities = tuple((account_id,) for account_id in fused.account_ids)
            return LeidenPartition(
                communities=communities,
                singleton_account_ids=fused.account_ids,
                fused_graph=fused,
                no_edge=True,
                status="singleton_partition_no_edges",
            )

        node_index = {
            account_id: index for index, account_id in enumerate(fused.account_ids)
        }
        graph = ig.Graph(
            n=len(fused.account_ids),
            edges=[
                (node_index[edge.source_account_id], node_index[edge.target_account_id])
                for edge in fused.edges
            ],
            directed=False,
        )
        partition = leidenalg.find_partition(
            graph,
            leidenalg.RBConfigurationVertexPartition,
            weights=[edge.weight for edge in fused.edges],
            resolution_parameter=self.config.resolution,
            n_iterations=self.config.iterations,
            seed=self.config.seed,
        )
        communities = tuple(
            sorted(
                (
                    tuple(sorted(fused.account_ids[index] for index in community))
                    for community in partition
                ),
                key=lambda members: members,
            )
        )
        singletons = tuple(
            members[0] for members in communities if len(members) == 1
        )
        return LeidenPartition(
            communities=communities,
            singleton_account_ids=singletons,
            fused_graph=fused,
            no_edge=False,
            status="partitioned",
        )


__all__ = [
    "FusedAffinityEdge",
    "FusedAffinityGraph",
    "LeidenConfig",
    "LeidenPartition",
    "LeidenPartitioner",
    "fuse_candidate_edges",
]
