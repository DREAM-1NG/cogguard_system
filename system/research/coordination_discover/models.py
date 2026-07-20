from __future__ import annotations

import itertools
import math
import random
from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Any, cast

from .contracts import EvidenceEdge, EvidenceGraph, TemporalMAGNNConfig

MODEL_INPUT_FEATURE_NAMES = (
    "source_account_id",
    "evidence_object_id",
    "relation_type",
    "time_bucket",
)


@dataclass(slots=True)
class TemporalMAGNNTensors:
    account_ids: list[str]
    object_ids: list[str]
    relation_types: list[str]
    time_buckets: list[int]
    edge_sources: Any
    edge_objects: Any
    edge_relations: Any
    edge_times: Any
    feature_names: tuple[str, ...] = MODEL_INPUT_FEATURE_NAMES


def build_temporal_magnn_tensors(
    graph: EvidenceGraph,
    config: TemporalMAGNNConfig | None = None,
) -> TemporalMAGNNTensors:
    config = config or TemporalMAGNNConfig(device="cpu")
    torch = _torch()
    account_ids = sorted(graph.accounts)
    object_ids = sorted({edge.evidence_object_id for edge in graph.edges})
    relation_types = sorted({edge.relation_type or edge.evidence_kind for edge in graph.edges})
    min_time = min((edge.observed_at for edge in graph.edges), default=0.0)
    bucket_values = sorted({_time_bucket(edge.observed_at, min_time=min_time, config=config) for edge in graph.edges})

    account_index = {value: index for index, value in enumerate(account_ids)}
    object_index = {value: index for index, value in enumerate(object_ids)}
    relation_index = {value: index for index, value in enumerate(relation_types)}
    bucket_index = {value: index for index, value in enumerate(bucket_values)}

    edge_sources = []
    edge_objects = []
    edge_relations = []
    edge_times = []
    for edge in graph.edges:
        if edge.source_account_id not in account_index or edge.evidence_object_id not in object_index:
            continue
        edge_sources.append(account_index[edge.source_account_id])
        edge_objects.append(object_index[edge.evidence_object_id])
        edge_relations.append(relation_index[edge.relation_type or edge.evidence_kind])
        edge_times.append(bucket_index[_time_bucket(edge.observed_at, min_time=min_time, config=config)])

    return TemporalMAGNNTensors(
        account_ids=account_ids,
        object_ids=object_ids,
        relation_types=relation_types,
        time_buckets=bucket_values,
        edge_sources=torch.tensor(edge_sources, dtype=torch.long),
        edge_objects=torch.tensor(edge_objects, dtype=torch.long),
        edge_relations=torch.tensor(edge_relations, dtype=torch.long),
        edge_times=torch.tensor(edge_times, dtype=torch.long),
    )


def fit_temporal_magnn(
    graph: EvidenceGraph,
    config: TemporalMAGNNConfig | None = None,
) -> dict[str, Any]:
    config = config or TemporalMAGNNConfig()
    if len(graph.accounts) < 2 or not graph.edges:
        return _empty_learned_result(status="data_insufficient")

    torch = _torch()
    torch.manual_seed(config.seed)
    random.seed(config.seed)
    tensors = build_temporal_magnn_tensors(graph, config=config)
    if tensors.edge_sources.numel() == 0:
        return _empty_learned_result(status="data_insufficient")

    device = _resolve_device(torch, config.device)
    model = cast(Any, _TemporalMAGNNScorer(
        account_count=max(1, len(tensors.account_ids)),
        object_count=max(1, len(tensors.object_ids)),
        relation_count=max(1, len(tensors.relation_types)),
        time_bucket_count=max(1, len(tensors.time_buckets)),
        embedding_dim=max(4, int(config.embedding_dim)),
    ))
    model = model.to(device)

    source = tensors.edge_sources.to(device)
    obj = tensors.edge_objects.to(device)
    relation = tensors.edge_relations.to(device)
    time_bucket = tensors.edge_times.to(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=float(config.learning_rate))
    loss_history: list[float] = []

    for _ in range(max(1, int(config.epochs))):
        optimizer.zero_grad()
        positive_logits = model(source, obj, relation, time_bucket)
        negative_source, negative_object, negative_relation, negative_time = _negative_samples(
            torch=torch,
            source=source,
            obj=obj,
            relation=relation,
            time_bucket=time_bucket,
            object_count=max(1, len(tensors.object_ids)),
            ratio=max(1, int(config.negative_ratio)),
            seed=config.seed + len(loss_history),
        )
        negative_logits = model(negative_source, negative_object, negative_relation, negative_time)
        logits = torch.cat([positive_logits, negative_logits])
        labels = torch.cat([torch.ones_like(positive_logits), torch.zeros_like(negative_logits)])
        loss = torch.nn.functional.binary_cross_entropy_with_logits(logits, labels)
        loss.backward()
        optimizer.step()
        loss_history.append(round(float(loss.detach().cpu().item()), 6))

    with torch.no_grad():
        probabilities = torch.sigmoid(model(source, obj, relation, time_bucket)).detach().cpu().tolist()
        account_embeddings = model.account_embedding.weight.detach().cpu().tolist()

    account_object_edges = _account_object_scores(graph=graph, tensors=tensors, scores=probabilities)
    pair_edges = build_account_pair_edges(account_object_edges, min_score=float(config.min_learned_edge_score))
    communities = partition_learned_graph(
        accounts=tensors.account_ids,
        pair_edges=pair_edges,
        min_score=float(config.min_learned_edge_score),
        require_leiden=bool(config.require_leiden),
    )

    return {
        "status": "ok",
        "model_backend": "temporal_magnn_style",
        "device": device,
        "loss_history": loss_history,
        "model_input": {
            "feature_names": list(tensors.feature_names),
            "account_count": len(tensors.account_ids),
            "object_count": len(tensors.object_ids),
            "relation_count": len(tensors.relation_types),
            "time_bucket_count": len(tensors.time_buckets),
            "edge_count": int(tensors.edge_sources.numel()),
        },
        "account_object_edges": account_object_edges,
        "pair_edges": pair_edges,
        "communities": communities["communities"],
        "partition_backend": communities["partition_backend"],
        "attention": _attention_summaries(account_object_edges),
        "node_embeddings": _node_embedding_preview(
            account_ids=tensors.account_ids,
            account_embeddings=account_embeddings,
            dims=max(1, int(config.export_embedding_dims)),
        ),
    }


def build_account_pair_edges(
    account_object_edges: list[dict[str, Any]],
    *,
    min_score: float = 0.0,
) -> list[dict[str, Any]]:
    by_object: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for edge in account_object_edges:
        by_object[str(edge["evidence_object_id"])].append(edge)

    pair_scores: dict[tuple[str, str], dict[str, Any]] = {}
    for object_id, edges in by_object.items():
        account_best: dict[str, dict[str, Any]] = {}
        for edge in edges:
            account = str(edge["source_account_id"])
            if account not in account_best or float(edge["learned_score"]) > float(account_best[account]["learned_score"]):
                account_best[account] = edge
        for left, right in itertools.combinations(sorted(account_best), 2):
            left_edge = account_best[left]
            right_edge = account_best[right]
            score = (float(left_edge["learned_score"]) + float(right_edge["learned_score"])) / 2.0
            key = (left, right)
            row = pair_scores.setdefault(
                key,
                {
                    "source": left,
                    "target": right,
                    "learned_weight_sum": 0.0,
                    "support_count": 0,
                    "evidence_objects": [],
                    "evidence_kind_counts": Counter(),
                    "first_observed_at": min(float(left_edge["observed_at"]), float(right_edge["observed_at"])),
                    "last_observed_at": max(float(left_edge["observed_at"]), float(right_edge["observed_at"])),
                },
            )
            row["learned_weight_sum"] += score
            row["support_count"] += 1
            row["evidence_objects"].append(object_id)
            row["evidence_kind_counts"][str(left_edge["evidence_kind"])] += 1
            row["first_observed_at"] = min(row["first_observed_at"], float(left_edge["observed_at"]), float(right_edge["observed_at"]))
            row["last_observed_at"] = max(row["last_observed_at"], float(left_edge["observed_at"]), float(right_edge["observed_at"]))

    results = []
    for row in pair_scores.values():
        support_count = max(1, int(row["support_count"]))
        learned_score = row["learned_weight_sum"] / support_count
        if learned_score < min_score:
            continue
        results.append(
            {
                "source": row["source"],
                "target": row["target"],
                "learned_score": round(learned_score, 6),
                "support_count": support_count,
                "evidence_objects": sorted(set(row["evidence_objects"]))[:25],
                "evidence_kind_counts": dict(row["evidence_kind_counts"]),
                "first_observed_at": round(float(row["first_observed_at"]), 6),
                "last_observed_at": round(float(row["last_observed_at"]), 6),
            }
        )
    return sorted(results, key=lambda item: (item["learned_score"], item["support_count"]), reverse=True)


def partition_learned_graph(
    *,
    accounts: list[str],
    pair_edges: list[dict[str, Any]],
    min_score: float = 0.0,
    require_leiden: bool = True,
) -> dict[str, Any]:
    filtered_edges = [edge for edge in pair_edges if float(edge.get("learned_score", 0.0)) >= min_score]
    if not filtered_edges:
        return {
            "partition_backend": "singleton_fallback",
            "communities": [
                _community_row(index=index, members=[account], pair_edges=[])
                for index, account in enumerate(sorted(accounts), start=1)
            ],
        }

    leiden_result = _try_leiden_partition(accounts=accounts, pair_edges=filtered_edges)
    if leiden_result is not None:
        return leiden_result
    if require_leiden:
        raise RuntimeError("Strict KT1 discovery requires python-igraph and leidenalg for Leiden partitioning")
    return _networkx_partition(accounts=accounts, pair_edges=filtered_edges)


class _TemporalMAGNNScorer:
    def __new__(
        cls,
        *,
        account_count: int,
        object_count: int,
        relation_count: int,
        time_bucket_count: int,
        embedding_dim: int,
    ):
        torch = _torch()

        class Module(torch.nn.Module):  # type: ignore[name-defined]
            def __init__(self) -> None:
                super().__init__()
                self.account_embedding = torch.nn.Embedding(account_count, embedding_dim)
                self.object_embedding = torch.nn.Embedding(object_count, embedding_dim)
                self.relation_embedding = torch.nn.Embedding(relation_count, embedding_dim)
                self.time_embedding = torch.nn.Embedding(time_bucket_count, embedding_dim)
                self.bias = torch.nn.Parameter(torch.zeros(1))

            def forward(self, source: Any, obj: Any, relation: Any, time_bucket: Any) -> Any:
                account = self.account_embedding(source)
                evidence_object = self.object_embedding(obj)
                relation_vector = self.relation_embedding(relation)
                time_vector = self.time_embedding(time_bucket)
                context = account + relation_vector + time_vector
                return (context * evidence_object).sum(dim=-1) / math.sqrt(embedding_dim) + self.bias

        return Module()


def _account_object_scores(
    *,
    graph: EvidenceGraph,
    tensors: TemporalMAGNNTensors,
    scores: list[float],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    object_by_id = {item.object_id: item for item in graph.objects}
    for edge, score in zip(graph.edges, scores):
        evidence_object = object_by_id.get(edge.evidence_object_id)
        rows.append(
            {
                "source_account_id": edge.source_account_id,
                "evidence_object_id": edge.evidence_object_id,
                "evidence_kind": edge.evidence_kind,
                "relation_type": edge.relation_type,
                "content_id": edge.content_id,
                "platform": edge.platform,
                "observed_at": round(float(edge.observed_at), 6),
                "evidence_ref": edge.evidence_ref,
                "object_value": evidence_object.value if evidence_object else edge.evidence_object_id,
                "learned_score": round(float(score), 6),
            }
        )
    return sorted(rows, key=lambda item: (item["learned_score"], item["observed_at"]), reverse=True)


def _attention_summaries(account_object_edges: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "relation_attention": _mean_score_by_key(account_object_edges, "relation_type"),
        "evidence_kind_attention": _mean_score_by_key(account_object_edges, "evidence_kind"),
        "temporal_attention": _temporal_attention(account_object_edges),
    }


def _mean_score_by_key(rows: list[dict[str, Any]], key: str) -> list[dict[str, Any]]:
    grouped: dict[str, list[float]] = defaultdict(list)
    for row in rows:
        grouped[str(row.get(key) or "unknown")].append(float(row.get("learned_score", 0.0)))
    return [
        {"name": name, "mean_score": round(sum(values) / max(len(values), 1), 6), "support": len(values)}
        for name, values in sorted(grouped.items())
    ]


def _temporal_attention(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not rows:
        return []
    min_time = min(float(row.get("observed_at", 0.0)) for row in rows)
    grouped: dict[int, list[float]] = defaultdict(list)
    for row in rows:
        bucket = int((float(row.get("observed_at", 0.0)) - min_time) // 3600)
        grouped[bucket].append(float(row.get("learned_score", 0.0)))
    return [
        {"bucket": bucket, "mean_score": round(sum(values) / max(len(values), 1), 6), "support": len(values)}
        for bucket, values in sorted(grouped.items())
    ]


def _node_embedding_preview(*, account_ids: list[str], account_embeddings: list[list[float]], dims: int) -> dict[str, list[float]]:
    preview: dict[str, list[float]] = {}
    for account_id, embedding in zip(account_ids, account_embeddings):
        preview[account_id] = [round(float(value), 6) for value in embedding[:dims]]
    return preview


def _negative_samples(
    *,
    torch: Any,
    source: Any,
    obj: Any,
    relation: Any,
    time_bucket: Any,
    object_count: int,
    ratio: int,
    seed: int,
) -> tuple[Any, Any, Any, Any]:
    generator = torch.Generator(device=source.device)
    generator.manual_seed(seed)
    repeated_source = source.repeat_interleave(ratio)
    repeated_relation = relation.repeat_interleave(ratio)
    repeated_time = time_bucket.repeat_interleave(ratio)
    negative_object = torch.randint(0, object_count, (repeated_source.numel(),), generator=generator, device=source.device)
    if object_count > 1:
        positive_object = obj.repeat_interleave(ratio)
        collision = negative_object == positive_object
        negative_object = torch.where(collision, (negative_object + 1) % object_count, negative_object)
    return repeated_source, negative_object, repeated_relation, repeated_time


def _try_leiden_partition(*, accounts: list[str], pair_edges: list[dict[str, Any]]) -> dict[str, Any] | None:
    try:
        import igraph as ig  # type: ignore
        import leidenalg  # type: ignore
    except ImportError:
        return None

    account_index = {account: index for index, account in enumerate(accounts)}
    graph = ig.Graph()
    graph.add_vertices(len(accounts))
    graph.vs["name"] = accounts
    graph.add_edges([(account_index[edge["source"]], account_index[edge["target"]]) for edge in pair_edges])
    graph.es["weight"] = [float(edge["learned_score"]) for edge in pair_edges]
    partition = leidenalg.find_partition(graph, leidenalg.RBConfigurationVertexPartition, weights="weight")
    communities = [
        _community_row(
            index=index,
            members=[str(graph.vs[member]["name"]) for member in sorted(cluster)],
            pair_edges=pair_edges,
        )
        for index, cluster in enumerate(partition, start=1)
    ]
    return {"partition_backend": "leiden", "communities": communities}


def _networkx_partition(*, accounts: list[str], pair_edges: list[dict[str, Any]]) -> dict[str, Any]:
    import networkx as nx

    graph = nx.Graph()
    graph.add_nodes_from(accounts)
    for edge in pair_edges:
        graph.add_edge(edge["source"], edge["target"], weight=float(edge["learned_score"]))
    try:
        clusters = nx.algorithms.community.greedy_modularity_communities(graph, weight="weight")
    except ValueError:
        clusters = list(nx.connected_components(graph))
    communities = [
        _community_row(index=index, members=sorted(cluster), pair_edges=pair_edges)
        for index, cluster in enumerate(clusters, start=1)
    ]
    return {"partition_backend": "networkx_modularity_fallback", "communities": communities}


def _community_row(*, index: int, members: list[str], pair_edges: list[dict[str, Any]]) -> dict[str, Any]:
    member_set = set(members)
    supporting_edges = [
        edge for edge in pair_edges if edge.get("source") in member_set and edge.get("target") in member_set
    ]
    evidence_objects: list[str] = []
    kind_counts: Counter[str] = Counter()
    for edge in supporting_edges:
        evidence_objects.extend(str(item) for item in edge.get("evidence_objects", []))
        kind_counts.update(edge.get("evidence_kind_counts", {}))
    learned_weight = sum(float(edge.get("learned_score", 0.0)) for edge in supporting_edges)
    return {
        "community_id": f"kt1_c{index}",
        "members": sorted(members),
        "size": len(members),
        "learned_weight": round(learned_weight, 6),
        "score": round(learned_weight / max(len(supporting_edges), 1), 6) if supporting_edges else 0.0,
        "supporting_edge_count": len(supporting_edges),
        "evidence_objects": sorted(set(evidence_objects))[:25],
        "evidence_kind_counts": dict(kind_counts),
    }


def _time_bucket(timestamp: float, *, min_time: float, config: TemporalMAGNNConfig) -> int:
    width = max(1, int(config.time_bucket_seconds))
    return int((float(timestamp) - float(min_time)) // width)


def _resolve_device(torch: Any, requested: str) -> str:
    requested = str(requested or "cpu").lower()
    if requested == "cuda" and torch.cuda.is_available():
        return "cuda"
    return "cpu"


def _torch() -> Any:
    try:
        import torch
    except ImportError as exc:
        raise RuntimeError("PyTorch is required for KT1 Temporal MAGNN-style discovery") from exc
    return torch


def _empty_learned_result(*, status: str) -> dict[str, Any]:
    return {
        "status": status,
        "model_backend": "temporal_magnn_style",
        "device": "unavailable",
        "loss_history": [],
        "model_input": {"feature_names": list(MODEL_INPUT_FEATURE_NAMES), "edge_count": 0},
        "account_object_edges": [],
        "pair_edges": [],
        "communities": [],
        "partition_backend": "none",
        "attention": {"relation_attention": [], "evidence_kind_attention": [], "temporal_attention": []},
        "node_embeddings": {},
    }


__all__ = [
    "MODEL_INPUT_FEATURE_NAMES",
    "TemporalMAGNNTensors",
    "build_account_pair_edges",
    "build_temporal_magnn_tensors",
    "fit_temporal_magnn",
    "partition_learned_graph",
]
