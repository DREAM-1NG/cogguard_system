"""Focused graphs implementation for coordination reproduction."""

from __future__ import annotations

import csv
import importlib.util
import json
import math
import os
import pickle
import re
import shlex
import shutil
import subprocess
import time
import urllib.request
import zipfile
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Mapping, Sequence
import networkx as nx
import numpy as np
import pandas as pd
from networkx.algorithms.community import greedy_modularity_communities, louvain_communities
from networkx.algorithms.community.quality import modularity
from app.core.coordination_baseline.characterization import CharacterizationConfig, characterize_detect_output
from app.core.coordination_baseline.deep_graph import (
    DEPRECATED_DISCOVER_ENCODERS,
    DeepGraphDiscoverConfig,
    DeepGraphDiscoverResult,
    STABLE_DISCOVER_ENCODER,
    run_deep_graph_discover,
)

from app.core.coordination_baseline.reproduction_common import (
    CommunityDetectionResult,
    DEFAULT_RELATIONS,
    Split,
    TARGET_RELATIONS,
    TEXT_COLUMNS,
    _clean_object_id,
    _looks_like_account_id,
    _metric_to_dict,
    _normalize_vector,
    _safe_divide,
    _timestamp_to_float,
    _tokenize,
    binary_metrics,
)

def build_user_entity_tfidf_vectors(
    events: pd.DataFrame,
    relation: str,
) -> dict[str, dict[str, float]]:
    relation_events = events[events["relation"] == relation]
    counts: dict[str, Counter[str]] = defaultdict(Counter)
    for row in relation_events.itertuples(index=False):
        account_id = str(getattr(row, "account_id"))
        object_id = str(getattr(row, "object_id"))
        if object_id and object_id.lower() != "nan":
            counts[account_id][object_id] += 1
    user_count = max(len(counts), 1)
    document_frequency: Counter[str] = Counter()
    for object_counts in counts.values():
        document_frequency.update(object_counts.keys())
    vectors: dict[str, dict[str, float]] = {}
    for account_id, object_counts in counts.items():
        total = float(sum(object_counts.values())) or 1.0
        vectors[account_id] = {}
        for object_id, count in object_counts.items():
            tf = count / total
            idf = math.log((1.0 + user_count) / (1.0 + document_frequency[object_id])) + 1.0
            vectors[account_id][object_id] = tf * idf
    return vectors


def attach_user_object_instances(
    graph: nx.Graph,
    vectors: Mapping[str, Mapping[str, float]],
    *,
    relation: str,
) -> nx.Graph:
    """Attach explicit U-O-U path instances to a projected user-user graph."""
    if graph.number_of_edges() == 0:
        return graph
    common_objects: dict[tuple[str, str], list[dict[str, object]]] = defaultdict(list)
    inverted: dict[str, list[tuple[str, float]]] = defaultdict(list)
    for account_id, vector in vectors.items():
        for object_id, value in vector.items():
            if value:
                inverted[str(object_id)].append((str(account_id), float(value)))
    for object_id, accounts in inverted.items():
        sorted_accounts = sorted(accounts)
        for left_index, (left, left_value) in enumerate(sorted_accounts):
            for right, right_value in sorted_accounts[left_index + 1 :]:
                key = tuple(sorted((str(left), str(right))))
                common_objects[key].append(
                    {
                        "relation": relation,
                        "object_id": object_id,
                        "left_weight": float(left_value),
                        "right_weight": float(right_value),
                        "path_weight": float(left_value * right_value),
                    }
                )
    for source, target, attrs in graph.edges(data=True):
        key = tuple(sorted((str(source), str(target))))
        instances = sorted(
            common_objects.get(key, []),
            key=lambda item: (-float(item["path_weight"]), str(item["object_id"])),
        )
        attrs["object_instances"] = instances
        attrs["objects"] = [str(item["object_id"]) for item in instances]
    return graph


def build_text_tfidf_vectors(events: pd.DataFrame) -> dict[str, dict[str, float]]:
    text_column = next((column for column in TEXT_COLUMNS if column in events.columns), None)
    if text_column is None:
        return {}
    documents: dict[str, list[str]] = defaultdict(list)
    for row in events.itertuples(index=False):
        documents[str(getattr(row, "account_id"))].extend(_tokenize(str(getattr(row, text_column))))
    user_count = max(len(documents), 1)
    document_frequency: Counter[str] = Counter()
    for tokens in documents.values():
        document_frequency.update(set(tokens))
    vectors: dict[str, dict[str, float]] = {}
    for account_id, tokens in documents.items():
        counts = Counter(tokens)
        total = float(sum(counts.values())) or 1.0
        vectors[account_id] = {}
        for token, count in counts.items():
            tf = count / total
            idf = math.log((1.0 + user_count) / (1.0 + document_frequency[token])) + 1.0
            vectors[account_id][token] = tf * idf
    return vectors


def similarity_graph_from_vectors(
    vectors: Mapping[str, Mapping[str, float]],
    *,
    relation: str,
    min_similarity: float = 0.0,
    max_edges_per_node: int | None = None,
) -> nx.Graph:
    graph = nx.Graph(relation=relation)
    for account_id in vectors:
        graph.add_node(account_id)
    norms = {
        account_id: math.sqrt(sum(value * value for value in vector.values()))
        for account_id, vector in vectors.items()
    }
    inverted: dict[str, list[tuple[str, float]]] = defaultdict(list)
    for account_id, vector in vectors.items():
        for object_id, value in vector.items():
            if value:
                inverted[object_id].append((account_id, float(value)))
    pair_dots: Counter[tuple[str, str]] = Counter()
    for accounts in inverted.values():
        sorted_accounts = sorted(accounts)
        for left_index, (left, left_value) in enumerate(sorted_accounts):
            for right, right_value in sorted_accounts[left_index + 1 :]:
                pair_dots[tuple(sorted((left, right)))] += left_value * right_value
    by_node: dict[str, list[tuple[str, str, float]]] = defaultdict(list)
    for (source, target), dot in pair_dots.items():
        similarity = _safe_divide(float(dot), norms.get(source, 0.0) * norms.get(target, 0.0))
        if similarity >= min_similarity and similarity > 0.0:
            by_node[source].append((source, target, similarity))
            by_node[target].append((source, target, similarity))
    if max_edges_per_node is None:
        selected = {(source, target, weight) for edges in by_node.values() for source, target, weight in edges}
    else:
        selected = set()
        for edges in by_node.values():
            selected.update(sorted(edges, key=lambda item: (-item[2], item[0], item[1]))[:max_edges_per_node])
    for source, target, weight in selected:
        graph.add_edge(source, target, weight=float(weight), relations={relation})
    return graph


def build_unmasking_similarity_graphs(
    events: pd.DataFrame,
    *,
    relations: Sequence[str] = DEFAULT_RELATIONS,
    include_text_similarity: bool = True,
    min_similarity: float = 0.0,
    max_edges_per_node: int | None = None,
) -> dict[str, nx.Graph]:
    graphs: dict[str, nx.Graph] = {}
    for relation in relations:
        vectors = build_user_entity_tfidf_vectors(events, relation)
        graph = similarity_graph_from_vectors(
            vectors,
            relation=relation,
            min_similarity=min_similarity,
            max_edges_per_node=max_edges_per_node,
        )
        graphs[relation] = attach_user_object_instances(graph, vectors, relation=relation)
    if include_text_similarity:
        vectors = build_text_tfidf_vectors(events)
        if vectors:
            graph = similarity_graph_from_vectors(
                vectors,
                relation="text_similarity",
                min_similarity=min_similarity,
                max_edges_per_node=max_edges_per_node,
            )
            graphs["text_similarity"] = attach_user_object_instances(graph, vectors, relation="text_similarity")
    return graphs


def fuse_similarity_graphs(graphs: Mapping[str, nx.Graph]) -> nx.Graph:
    fused = nx.Graph(relation="fused")
    for relation, graph in graphs.items():
        for node in graph.nodes:
            fused.add_node(node)
        for source, target, attrs in graph.edges(data=True):
            weight = float(attrs.get("weight", 1.0))
            if fused.has_edge(source, target):
                fused[source][target]["weight"] += weight
                fused[source][target]["relations"].add(relation)
            else:
                fused.add_edge(source, target, weight=weight, relations={relation})
    for source, target in fused.edges:
        fused[source][target]["relations"] = sorted(fused[source][target]["relations"])
    return fused


def build_dynamic_relation_graphs(
    events: pd.DataFrame,
    *,
    relations: Sequence[str] = DEFAULT_RELATIONS,
) -> dict[str, nx.DiGraph]:
    """Build directed relation graphs while preserving temporal object evidence."""
    known_accounts = set(events["account_id"].astype(str))
    graphs: dict[str, nx.DiGraph] = {relation: nx.DiGraph(relation=relation) for relation in relations}
    for relation, relation_events in events[events["relation"].isin(relations)].groupby("relation"):
        graph = graphs.setdefault(str(relation), nx.DiGraph(relation=str(relation)))
        for account_id in relation_events["account_id"].astype(str).unique():
            graph.add_node(account_id)

        if relation in TARGET_RELATIONS and "target_account_id" in relation_events.columns:
            target_events = relation_events[relation_events["target_account_id"].astype(str).str.len() > 0]
            for row in target_events.itertuples(index=False):
                source = str(getattr(row, "account_id"))
                target = str(getattr(row, "target_account_id"))
                object_id = _clean_object_id(getattr(row, "object_id", ""))
                timestamp = _timestamp_to_float(getattr(row, "timestamp", 0))
                if not target or source == target:
                    continue
                graph.add_node(source)
                graph.add_node(target)
                _upsert_dynamic_edge(graph, source, target, relation, object_id, timestamp, delta=0.0)
            continue

        if relation in TARGET_RELATIONS:
            keep_shared_object_rows = []
            for row in relation_events.itertuples(index=False):
                source = str(getattr(row, "account_id"))
                object_id = _clean_object_id(getattr(row, "object_id", ""))
                if not _looks_like_account_id(object_id, known_accounts) or source == object_id:
                    keep_shared_object_rows.append(True)
                    continue
                keep_shared_object_rows.append(False)
                graph.add_node(source)
                graph.add_node(object_id)
                _upsert_dynamic_edge(
                    graph,
                    source,
                    object_id,
                    relation,
                    object_id,
                    _timestamp_to_float(getattr(row, "timestamp", 0)),
                    delta=0.0,
                )
            relation_events = relation_events.loc[keep_shared_object_rows] if keep_shared_object_rows else relation_events.iloc[0:0]

        for object_id, object_events in relation_events.groupby("object_id"):
            clean_object_id = _clean_object_id(object_id)
            if not clean_object_id:
                continue
            ordered = sorted(
                (
                    (
                        str(row.account_id),
                        _timestamp_to_float(getattr(row, "timestamp", 0)),
                    )
                    for row in object_events.itertuples(index=False)
                ),
                key=lambda item: (item[1], item[0]),
            )
            for index, (source, source_time) in enumerate(ordered):
                for target, target_time in ordered[index + 1 :]:
                    if source == target:
                        continue
                    delta = max(0.0, target_time - source_time)
                    time_weight = 1.0 / (1.0 + math.log1p(delta)) if delta > 0 else 1.0
                    _upsert_dynamic_edge(
                        graph,
                        source,
                        target,
                        str(relation),
                        clean_object_id,
                        target_time,
                        delta=delta,
                        weight=time_weight,
                    )
    for relation in relations:
        graphs.setdefault(relation, nx.DiGraph(relation=relation))
    return graphs


def _upsert_dynamic_edge(
    graph: nx.DiGraph,
    source: str,
    target: str,
    relation: str,
    object_id: str,
    timestamp: float,
    *,
    delta: float,
    weight: float = 1.0,
) -> None:
    if graph.has_edge(source, target):
        attrs = graph[source][target]
        attrs["weight"] = float(attrs.get("weight", 0.0)) + float(weight)
        attrs["count"] = int(attrs.get("count", 0)) + 1
        attrs["objects"].add(object_id)
        attrs["timestamps"].append(timestamp)
        attrs["time_deltas"].append(delta)
    else:
        graph.add_edge(
            source,
            target,
            weight=float(weight),
            count=1,
            relation=relation,
            objects={object_id},
            timestamps=[timestamp],
            time_deltas=[delta],
        )


def fuse_directed_graphs(graphs: Mapping[str, nx.DiGraph]) -> nx.DiGraph:
    fused = nx.DiGraph(relation="dynamic_fused")
    for relation, graph in graphs.items():
        for node in graph.nodes:
            fused.add_node(node)
        for source, target, attrs in graph.edges(data=True):
            weight = float(attrs.get("weight", 1.0))
            objects = set(attrs.get("objects", set()))
            timestamps = list(attrs.get("timestamps", []))
            deltas = list(attrs.get("time_deltas", []))
            if fused.has_edge(source, target):
                fused[source][target]["weight"] += weight
                fused[source][target]["count"] += int(attrs.get("count", 1))
                fused[source][target]["relations"].add(relation)
                fused[source][target]["objects"].update(objects)
                fused[source][target]["timestamps"].extend(timestamps)
                fused[source][target]["time_deltas"].extend(deltas)
            else:
                fused.add_edge(
                    source,
                    target,
                    weight=weight,
                    count=int(attrs.get("count", 1)),
                    relations={relation},
                    objects=objects,
                    timestamps=timestamps,
                    time_deltas=deltas,
                )
    for _, _, attrs in fused.edges(data=True):
        attrs["relations"] = sorted(attrs["relations"])
        attrs["objects"] = sorted(object_id for object_id in attrs["objects"] if object_id)
    return fused


def dynamic_graph_summary(graph: nx.DiGraph) -> dict[str, object]:
    time_deltas = [
        float(delta)
        for _, _, attrs in graph.edges(data=True)
        for delta in attrs.get("time_deltas", [])
        if float(delta) >= 0.0
    ]
    relation_counts: Counter[str] = Counter()
    object_counts: Counter[str] = Counter()
    for _, _, attrs in graph.edges(data=True):
        relation_counts.update(attrs.get("relations", [attrs.get("relation", "")]))
        object_counts.update(attrs.get("objects", []))
    return {
        "node_count": graph.number_of_nodes(),
        "edge_count": graph.number_of_edges(),
        "density": round(float(nx.density(graph)), 6) if graph.number_of_nodes() > 1 else 0.0,
        "relation_counts": dict(sorted(relation_counts.items())),
        "object_count": len(object_counts),
        "top_objects": [
            {"object_id": object_id, "count": count}
            for object_id, count in object_counts.most_common(10)
        ],
        "avg_time_delta": round(float(np.mean(time_deltas)), 6) if time_deltas else None,
        "median_time_delta": round(float(np.median(time_deltas)), 6) if time_deltas else None,
    }


def _detect_communities_with_metadata(
    graph: nx.Graph,
    *,
    algorithm: str = "leiden",
    seed: int = 42,
) -> CommunityDetectionResult:
    requested = algorithm.lower().strip()
    if graph.number_of_edges() == 0:
        return CommunityDetectionResult(
            communities=[{str(node)} for node in graph.nodes],
            requested_algorithm=requested,
            effective_algorithm=requested,
            backend=f"{requested}:no_edges_singletons",
        )
    if requested not in {"leiden", "louvain", "greedy"}:
        raise ValueError("community_algorithm must be one of: leiden, louvain, greedy")
    if requested == "leiden":
        leiden_result = _try_leiden_communities(graph, seed=seed)
        if leiden_result.fallback_reason is None:
            return leiden_result
        louvain_result = _try_louvain_communities(graph, requested_algorithm=requested, seed=seed)
        if louvain_result.fallback_reason is None:
            louvain_result.fallback_reason = leiden_result.fallback_reason
            return louvain_result
        greedy_result = _greedy_communities_result(
            graph,
            requested_algorithm=requested,
            fallback_reason=f"{leiden_result.fallback_reason}; {louvain_result.fallback_reason}",
        )
        return greedy_result
    if requested == "louvain":
        louvain_result = _try_louvain_communities(graph, requested_algorithm=requested, seed=seed)
        if louvain_result.fallback_reason is None:
            return louvain_result
        return _greedy_communities_result(
            graph,
            requested_algorithm=requested,
            fallback_reason=louvain_result.fallback_reason,
        )
    return _greedy_communities_result(graph, requested_algorithm=requested)


def _detect_communities(graph: nx.Graph, *, algorithm: str = "leiden", seed: int = 42) -> list[set[str]]:
    return _detect_communities_with_metadata(graph, algorithm=algorithm, seed=seed).communities


def _try_leiden_communities(graph: nx.Graph, *, seed: int = 42) -> CommunityDetectionResult:
    try:
        import igraph as ig  # type: ignore[import-not-found]
        import leidenalg  # type: ignore[import-not-found]
    except Exception as exc:
        return CommunityDetectionResult(
            communities=[],
            requested_algorithm="leiden",
            effective_algorithm="",
            backend="leidenalg",
            fallback_reason=f"leiden unavailable: {exc.__class__.__name__}",
        )
    try:
        nodes = [str(node) for node in graph.nodes]
        node_index = {node: index for index, node in enumerate(nodes)}
        edges = [(node_index[str(source)], node_index[str(target)]) for source, target in graph.edges]
        weights = [float(attrs.get("weight", 1.0)) for _, _, attrs in graph.edges(data=True)]
        igraph_graph = ig.Graph(n=len(nodes), edges=edges, directed=False)
        partition = leidenalg.find_partition(
            igraph_graph,
            leidenalg.RBConfigurationVertexPartition,
            weights=weights if weights else None,
            seed=int(seed),
        )
        communities = [
            {nodes[int(index)] for index in community}
            for community in partition
            if len(community) > 0
        ]
        return CommunityDetectionResult(
            communities=communities,
            requested_algorithm="leiden",
            effective_algorithm="leiden",
            backend="leidenalg.RBConfigurationVertexPartition",
        )
    except Exception as exc:
        return CommunityDetectionResult(
            communities=[],
            requested_algorithm="leiden",
            effective_algorithm="",
            backend="leidenalg",
            fallback_reason=f"leiden failed: {exc.__class__.__name__}: {exc}",
        )


def _try_louvain_communities(
    graph: nx.Graph,
    *,
    requested_algorithm: str,
    seed: int = 42,
) -> CommunityDetectionResult:
    try:
        communities = [
            set(map(str, community))
            for community in louvain_communities(graph, weight="weight", seed=seed)
        ]
        return CommunityDetectionResult(
            communities=communities,
            requested_algorithm=requested_algorithm,
            effective_algorithm="louvain",
            backend="networkx.louvain_communities",
        )
    except Exception as exc:
        return CommunityDetectionResult(
            communities=[],
            requested_algorithm=requested_algorithm,
            effective_algorithm="",
            backend="networkx.louvain_communities",
            fallback_reason=f"louvain failed: {exc.__class__.__name__}: {exc}",
        )


def _greedy_communities_result(
    graph: nx.Graph,
    *,
    requested_algorithm: str,
    fallback_reason: str | None = None,
) -> CommunityDetectionResult:
    communities = [
        set(map(str, community))
        for community in greedy_modularity_communities(graph, weight="weight")
    ]
    return CommunityDetectionResult(
        communities=communities,
        requested_algorithm=requested_algorithm,
        effective_algorithm="greedy",
        backend="networkx.greedy_modularity_communities",
        fallback_reason=fallback_reason,
    )


def graph_summary(
    graph: nx.Graph,
    labels: Mapping[str, int] | None = None,
    *,
    community_algorithm: str = "leiden",
    seed: int = 42,
    communities: Sequence[set[str]] | None = None,
    community_algorithm_effective: str | None = None,
    community_algorithm_backend: str | None = None,
    community_algorithm_fallback_reason: str | None = None,
) -> dict[str, object]:
    partition = [set(map(str, community)) for community in communities] if communities is not None else []
    modularity_score = None
    conductance_score = None
    community_result = CommunityDetectionResult(
        communities=[],
        requested_algorithm=community_algorithm,
        effective_algorithm=community_algorithm,
        backend=f"{community_algorithm}:not_run",
    )
    if communities is not None:
        community_result = CommunityDetectionResult(
            communities=partition,
            requested_algorithm=community_algorithm,
            effective_algorithm=community_algorithm_effective or community_algorithm,
            backend=community_algorithm_backend or "provided_partition",
            fallback_reason=community_algorithm_fallback_reason,
        )
    elif graph.number_of_edges() > 0:
        community_result = _detect_communities_with_metadata(graph, algorithm=community_algorithm, seed=seed)
        partition = community_result.communities
    if partition:
        modularity_score = float(modularity(graph, partition, weight="weight")) if graph.number_of_edges() > 0 else None
        conductance_values = []
        for community in sorted(partition, key=len, reverse=True)[:100]:
            if community and len(community) < graph.number_of_nodes():
                try:
                    conductance_values.append(nx.algorithms.cuts.conductance(graph, community, weight="weight"))
                except Exception:
                    continue
        conductance_score = float(np.mean(conductance_values)) if conductance_values else None
    label_values = list(labels.values()) if labels else []
    return {
        "node_count": graph.number_of_nodes(),
        "edge_count": graph.number_of_edges(),
        "density": round(float(nx.density(graph)), 6) if graph.number_of_nodes() > 1 else 0.0,
        "component_count": nx.number_connected_components(graph) if graph.number_of_nodes() else 0,
        "cluster_count": len(partition),
        "largest_cluster_size": max((len(community) for community in partition), default=0),
        "modularity": round(modularity_score, 6) if modularity_score is not None else None,
        "conductance": round(conductance_score, 6) if conductance_score is not None else None,
        "community_algorithm": community_algorithm,
        "community_algorithm_effective": community_result.effective_algorithm,
        "community_algorithm_backend": community_result.backend,
        "community_algorithm_fallback_reason": community_result.fallback_reason,
        "positive_label_count": int(sum(label_values)) if label_values else None,
    }


def _centrality_scores(graph: nx.Graph, metric: str) -> dict[str, float]:
    if graph.number_of_nodes() == 0:
        return {}
    if metric == "degree":
        return {node: float(graph.degree(node, weight="weight")) for node in graph.nodes}
    if metric == "pagerank":
        try:
            return nx.pagerank(graph, weight="weight")
        except Exception:
            return _pagerank_fallback(graph)
    if metric == "eigenvector":
        try:
            return nx.eigenvector_centrality_numpy(graph, weight="weight")
        except Exception:
            return {node: float(graph.degree(node, weight="weight")) for node in graph.nodes}
    raise ValueError(f"Unsupported centrality metric: {metric}")


def _pagerank_fallback(
    graph: nx.Graph,
    *,
    alpha: float = 0.85,
    max_iter: int = 100,
    tol: float = 1e-9,
) -> dict[str, float]:
    nodes = list(graph.nodes)
    if not nodes:
        return {}
    index = {node: offset for offset, node in enumerate(nodes)}
    n = len(nodes)
    scores = np.full(n, 1.0 / n, dtype=float)
    adjacency = np.zeros((n, n), dtype=float)
    for source, target, attrs in graph.edges(data=True):
        weight = float(attrs.get("weight", 1.0))
        adjacency[index[source], index[target]] += weight
        adjacency[index[target], index[source]] += weight
    row_sum = adjacency.sum(axis=1, keepdims=True)
    dangling = row_sum[:, 0] <= 0.0
    row_sum[row_sum <= 0.0] = 1.0
    transition = adjacency / row_sum
    teleport = np.full(n, (1.0 - alpha) / n, dtype=float)
    for _ in range(max_iter):
        dangling_mass = float(np.sum(scores[dangling])) / n
        updated = teleport + alpha * (transition.T @ scores + dangling_mass)
        if float(np.sum(np.abs(updated - scores))) < tol:
            scores = updated
            break
        scores = updated
    total = float(np.sum(scores)) or 1.0
    return {node: float(scores[index[node]] / total) for node in nodes}


def node_pruning_baseline(
    graph: nx.Graph,
    labels: Mapping[str, int] | None = None,
    *,
    metric: str = "eigenvector",
    percentile: float = 90.0,
) -> dict[str, object]:
    scores = _centrality_scores(graph, metric)
    if not scores:
        return {"metric": metric, "selected_nodes": [], "threshold": None, "metrics": None}
    threshold = float(np.percentile(list(scores.values()), percentile))
    selected_nodes = sorted(node for node, value in scores.items() if value >= threshold)
    metrics = None
    if labels:
        ordered_nodes = sorted(scores)
        y_true = [int(labels.get(node, 0)) for node in ordered_nodes]
        y_score = [float(scores[node]) for node in ordered_nodes]
        metrics = binary_metrics(y_true, y_score, threshold=threshold)
    return {
        "metric": metric,
        "percentile": percentile,
        "threshold": threshold,
        "selected_nodes": selected_nodes,
        "metrics": _metric_to_dict(metrics),
    }


def _unweighted_graph_copy(graph: nx.Graph) -> nx.Graph:
    copied = nx.Graph()
    copied.add_nodes_from(graph.nodes)
    copied.add_edges_from((source, target, {"weight": 1.0}) for source, target in graph.edges())
    return copied


def _apply_discover_structure_filter(
    graph: nx.Graph,
    *,
    mode: str,
    metric: str,
    percentile: float,
    use_weights: bool,
    min_selected_nodes: int = 2,
) -> tuple[nx.Graph, dict[str, object], set[str], dict[str, float]]:
    # Historical helper kept for compatibility with old experiment manifests.
    # CoordinationDiscover Discover now runs on the stable full-graph encoder
    # and does not perform Unmasking-style structural screening first.
    original_node_count = int(graph.number_of_nodes())
    original_edge_count = int(graph.number_of_edges())
    if mode == "none" or original_node_count == 0:
        all_nodes = set(map(str, graph.nodes))
        default_scores = {str(node): 1.0 for node in graph.nodes}
        return (
            graph,
            {
                "mode": "none",
                "metric": metric,
                "percentile": float(percentile),
                "use_weights": bool(use_weights),
                "effective": False,
                "threshold": None,
                "selected_node_count": original_node_count,
                "removed_node_count": 0,
                "selected_node_fraction": 1.0 if original_node_count else 0.0,
                "removed_node_fraction": 0.0,
                "graph_node_count_before": original_node_count,
                "graph_edge_count_before": original_edge_count,
                "graph_node_count_after": original_node_count,
                "graph_edge_count_after": original_edge_count,
                "selected_nodes_preview": sorted(all_nodes)[:20],
                "selection_graph": "fused_similarity_network",
                "fallback_reason": None,
            },
            all_nodes,
            default_scores,
        )
    if mode != "node_pruning":
        raise ValueError(f"Unsupported Discover structure filter: {mode}")
    centrality_graph = graph if use_weights else _unweighted_graph_copy(graph)
    scores = _centrality_scores(centrality_graph, metric)
    if not scores:
        return (
            graph,
            {
                "mode": mode,
                "metric": metric,
                "percentile": float(percentile),
                "use_weights": bool(use_weights),
                "effective": False,
                "threshold": None,
                "selected_node_count": original_node_count,
                "removed_node_count": 0,
                "selected_node_fraction": 1.0 if original_node_count else 0.0,
                "removed_node_fraction": 0.0,
                "graph_node_count_before": original_node_count,
                "graph_edge_count_before": original_edge_count,
                "graph_node_count_after": original_node_count,
                "graph_edge_count_after": original_edge_count,
                "selected_nodes_preview": sorted(map(str, graph.nodes))[:20],
                "selection_graph": "weighted_fused_similarity_network" if use_weights else "unweighted_fused_similarity_network",
                "fallback_reason": "empty_centrality_scores",
            },
            set(map(str, graph.nodes)),
            {str(node): 1.0 for node in graph.nodes},
        )
    threshold = float(np.percentile(list(scores.values()), percentile))
    selected_nodes = sorted(str(node) for node, value in scores.items() if float(value) >= threshold)
    if 0 < len(selected_nodes) < min_selected_nodes and len(scores) >= min_selected_nodes:
        selected_nodes = [
            str(node)
            for node, _ in sorted(scores.items(), key=lambda item: (-float(item[1]), str(item[0])))[:min_selected_nodes]
        ]
    selected_node_set = set(selected_nodes)
    filtered_graph = graph.subgraph(selected_nodes).copy()
    normalized_scores = _normalize_vector(np.asarray([float(scores[str(node)]) for node in scores], dtype=float))
    normalized_score_map = {
        str(node): float(normalized_scores[index])
        for index, node in enumerate(scores)
    }
    selected_node_count = int(filtered_graph.number_of_nodes())
    removed_node_count = max(0, original_node_count - selected_node_count)
    return (
        filtered_graph,
        {
            "mode": mode,
            "metric": metric,
            "percentile": float(percentile),
            "use_weights": bool(use_weights),
            "effective": selected_node_count < original_node_count,
            "threshold": round(threshold, 6),
            "selected_node_count": selected_node_count,
            "removed_node_count": removed_node_count,
            "selected_node_fraction": round(_safe_divide(selected_node_count, original_node_count), 6),
            "removed_node_fraction": round(_safe_divide(removed_node_count, original_node_count), 6),
            "graph_node_count_before": original_node_count,
            "graph_edge_count_before": original_edge_count,
            "graph_node_count_after": selected_node_count,
            "graph_edge_count_after": int(filtered_graph.number_of_edges()),
            "selected_nodes_preview": selected_nodes[:20],
            "selection_graph": "weighted_fused_similarity_network" if use_weights else "unweighted_fused_similarity_network",
            "fallback_reason": None,
        },
        selected_node_set,
        normalized_score_map,
    )


def _expand_core_communities(
    graph: nx.Graph,
    *,
    core_communities: Sequence[set[str]],
    core_nodes: set[str],
    nodes: Sequence[str],
) -> tuple[list[set[str]], dict[str, int], dict[str, object]]:
    expanded = [set(map(str, community)) for community in core_communities if community]
    cluster_by_node: dict[str, int] = {}
    for cluster_id, community in enumerate(expanded):
        for node in community:
            cluster_by_node[str(node)] = cluster_id

    expanded_count = 0
    singleton_count = 0
    attachment_scores: list[float] = []
    for node in nodes:
        node = str(node)
        if node in cluster_by_node:
            continue
        best_cluster = None
        best_score = 0.0
        if node in graph:
            for cluster_id, community in enumerate(expanded):
                attachment = 0.0
                for neighbor, attrs in graph[node].items():
                    if str(neighbor) in community:
                        attachment += float(attrs.get("weight", 1.0))
                if attachment > best_score:
                    best_score = attachment
                    best_cluster = cluster_id
        if best_cluster is not None and best_score > 0.0:
            expanded[best_cluster].add(node)
            cluster_by_node[node] = best_cluster
            expanded_count += 1
            attachment_scores.append(best_score)
            continue
        cluster_id = len(expanded)
        expanded.append({node})
        cluster_by_node[node] = cluster_id
        singleton_count += 1

    return expanded, cluster_by_node, {
        "assignment_mode": "core_then_expand",
        "core_node_count": len(core_nodes),
        "expanded_node_count": expanded_count,
        "singleton_remainder_count": singleton_count,
        "mean_attachment_weight": round(float(np.mean(attachment_scores)), 6) if attachment_scores else 0.0,
        "max_attachment_weight": round(float(np.max(attachment_scores)), 6) if attachment_scores else 0.0,
    }


def _spectral_embedding(graph: nx.Graph, nodes: Sequence[str], dim: int = 16) -> np.ndarray:
    if not nodes:
        return np.zeros((0, dim), dtype=float)
    graph_for_embedding = graph.copy()
    graph_for_embedding.add_nodes_from(nodes)
    adjacency = nx.to_numpy_array(graph_for_embedding, nodelist=list(nodes), weight="weight", dtype=float)
    if not np.any(adjacency):
        return np.zeros((len(nodes), dim), dtype=float)
    values, vectors = np.linalg.eigh(adjacency)
    order = np.argsort(np.abs(values))[::-1][:dim]
    selected_values = np.sqrt(np.abs(values[order]))
    embedding = vectors[:, order] * selected_values
    if embedding.shape[1] < dim:
        embedding = np.pad(embedding, ((0, 0), (0, dim - embedding.shape[1])))
    return embedding.astype(float)


def _structural_embedding(graph: nx.Graph, nodes: Sequence[str], dim: int = 16) -> np.ndarray:
    graph_for_embedding = graph.copy()
    graph_for_embedding.add_nodes_from(nodes)
    degree = _centrality_scores(graph_for_embedding, "degree")
    pagerank = _centrality_scores(graph_for_embedding, "pagerank")
    weighted_degree = {
        node: float(graph_for_embedding.degree(node, weight="weight"))
        for node in nodes
    }
    matrix = np.asarray(
        [
            [
                degree.get(node, 0.0),
                pagerank.get(node, 0.0),
                weighted_degree.get(node, 0.0),
                float(graph_for_embedding.degree(node)),
            ]
            for node in nodes
        ],
        dtype=float,
    )
    for column in range(matrix.shape[1]):
        matrix[:, column] = _normalize_vector(matrix[:, column])
    if dim <= matrix.shape[1]:
        return matrix[:, :dim]
    return np.pad(matrix, ((0, 0), (0, dim - matrix.shape[1])))


def _make_split(y: np.ndarray, *, seed: int = 42, train_ratio: float = 0.7) -> Split:
    rng = np.random.default_rng(seed)
    train_indices: list[int] = []
    test_indices: list[int] = []
    for label in sorted(set(y.tolist())):
        indices = np.where(y == label)[0]
        rng.shuffle(indices)
        cut = max(1, int(round(len(indices) * train_ratio))) if len(indices) > 1 else len(indices)
        train_indices.extend(indices[:cut].tolist())
        test_indices.extend(indices[cut:].tolist())
    if not test_indices and len(y) > 1:
        test_indices.append(train_indices.pop())
    return Split(train=np.asarray(sorted(train_indices)), test=np.asarray(sorted(test_indices)))


def _split_for_detect(
    events: pd.DataFrame,
    nodes: Sequence[str],
    y: np.ndarray,
    *,
    split_mode: str = "supervised",
    seed: int = 42,
) -> tuple[Split, str]:
    mode = split_mode.lower().strip()
    if mode == "scarce_supervised":
        return _make_split(y, seed=seed, train_ratio=0.2), "scarce_supervised"
    if mode != "cross_io":
        return _make_split(y, seed=seed), "supervised"

    group_column = next(
        (column for column in ("campaign", "dataset", "source_graph", "operation", "country") if column in events.columns),
        None,
    )
    if group_column is None:
        return _make_split(y, seed=seed), "cross_io_fallback_supervised_no_group"
    node_group = (
        events.groupby("account_id")[group_column]
        .agg(lambda values: str(values.iloc[0]))
        .to_dict()
    )
    groups = sorted({str(node_group.get(node, "")) for node in nodes if str(node_group.get(node, ""))})
    if len(groups) < 2:
        return _make_split(y, seed=seed), "cross_io_fallback_supervised_single_group"
    rng = np.random.default_rng(seed)
    test_group = groups[int(rng.integers(0, len(groups)))]
    test_indices = np.asarray([index for index, node in enumerate(nodes) if str(node_group.get(node, "")) == test_group], dtype=int)
    train_indices = np.asarray([index for index, node in enumerate(nodes) if str(node_group.get(node, "")) != test_group], dtype=int)
    if train_indices.size == 0 or test_indices.size == 0 or len(set(y[train_indices].tolist())) < 2:
        return _make_split(y, seed=seed), "cross_io_fallback_supervised_unusable_group"
    return Split(train=np.asarray(sorted(train_indices)), test=np.asarray(sorted(test_indices))), f"cross_io:{group_column}:{test_group}"


def _standardize_train_test(x_train: np.ndarray, x_test: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    mean = np.mean(x_train, axis=0, keepdims=True)
    std = np.std(x_train, axis=0, keepdims=True)
    std[std <= 1e-9] = 1.0
    return (x_train - mean) / std, (x_test - mean) / std


def _fit_numpy_logistic(
    x_train: np.ndarray,
    y_train: np.ndarray,
    x_test: np.ndarray,
    *,
    epochs: int = 300,
    learning_rate: float = 0.1,
    l2: float = 1e-3,
) -> np.ndarray:
    x_train, x_test = _standardize_train_test(x_train, x_test)
    weights = np.zeros(x_train.shape[1], dtype=float)
    bias = 0.0
    positives = max(float(np.sum(y_train == 1)), 1.0)
    negatives = max(float(np.sum(y_train == 0)), 1.0)
    class_weights = np.where(y_train == 1, len(y_train) / (2.0 * positives), len(y_train) / (2.0 * negatives))
    for _ in range(epochs):
        logits = x_train @ weights + bias
        probs = 1.0 / (1.0 + np.exp(-np.clip(logits, -30.0, 30.0)))
        error = (probs - y_train) * class_weights
        grad_w = (x_train.T @ error) / len(y_train) + l2 * weights
        grad_b = float(np.mean(error))
        weights -= learning_rate * grad_w
        bias -= learning_rate * grad_b
    return 1.0 / (1.0 + np.exp(-np.clip(x_test @ weights + bias, -30.0, 30.0)))


def _fit_classifier_scores(
    x: np.ndarray,
    y: np.ndarray,
    *,
    seed: int = 42,
) -> tuple[np.ndarray, np.ndarray, str]:
    split = _make_split(y, seed=seed)
    if split.test.size == 0:
        return np.asarray([], dtype=int), np.asarray([], dtype=float), "not_enough_test_data"
    x_train = x[split.train]
    x_test = x[split.test]
    y_train = y[split.train]
    try:
        from sklearn.ensemble import RandomForestClassifier

        classifier = RandomForestClassifier(n_estimators=200, random_state=seed, class_weight="balanced")
        classifier.fit(x_train, y_train)
        scores = classifier.predict_proba(x_test)[:, 1]
        backend = "sklearn_random_forest"
    except Exception:
        scores = _fit_numpy_logistic(x_train, y_train, x_test)
        backend = "numpy_logistic"
    return split.test, scores, backend


def node_embedding_classifier_baseline(
    graph: nx.Graph,
    labels: Mapping[str, int],
    *,
    dim: int = 128,
    spectral_node_limit: int = 1000,
    seed: int = 42,
) -> dict[str, object]:
    nodes = sorted(labels)
    if not nodes or len(set(labels.values())) < 2:
        return {"embedding_backend": "spectral", "classifier_backend": "not_applicable", "metrics": None}
    embedding_dim = min(dim, max(1, len(nodes)))
    if len(nodes) > spectral_node_limit:
        embedding = _structural_embedding(graph, nodes, dim=embedding_dim)
        embedding_backend = "structural_fallback"
    else:
        embedding = _spectral_embedding(graph, nodes, dim=embedding_dim)
        embedding_backend = "spectral_fallback"
    y = np.asarray([int(labels[node]) for node in nodes], dtype=int)
    test_indices, scores, classifier_backend = _fit_classifier_scores(embedding, y, seed=seed)
    metrics = binary_metrics(y[test_indices], scores) if test_indices.size else None
    return {
        "embedding_backend": embedding_backend,
        "classifier_backend": classifier_backend,
        "metrics": _metric_to_dict(metrics),
        "test_nodes": [nodes[int(index)] for index in test_indices.tolist()],
    }

__all__ = [
    "attach_user_object_instances",
    "build_dynamic_relation_graphs",
    "build_text_tfidf_vectors",
    "build_unmasking_similarity_graphs",
    "build_user_entity_tfidf_vectors",
    "dynamic_graph_summary",
    "fuse_directed_graphs",
    "fuse_similarity_graphs",
    "graph_summary",
    "node_embedding_classifier_baseline",
    "node_pruning_baseline",
    "similarity_graph_from_vectors",
]
