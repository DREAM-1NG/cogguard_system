"""Focused features implementation."""

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
    DEFAULT_RELATIONS,
    DISCOVER_STRUCTURE_FILTERS,
    DISCOVER_STRUCTURE_FILTER_METRICS,
    LABEL_COLUMNS,
    PreparedDetectInputs,
    Split,
    TEXT_COLUMNS,
    _LM_FEATURE_CACHE,
    _append_metric_row,
    _clean_object_id,
    _detection_metric_dict,
    _metric_to_dict,
    _normalize_vector,
    _safe_divide,
    _sigmoid,
    _timestamp_to_float,
    _tokenize,
    binary_metrics,
    extract_labels,
    normalize_event_table,
)
from app.core.coordination_baseline.reproduction_graphs import (
    _apply_discover_structure_filter,
    _centrality_scores,
    _detect_communities,
    _fit_classifier_scores,
    _fit_numpy_logistic,
    _make_split,
    build_dynamic_relation_graphs,
    build_unmasking_similarity_graphs,
    dynamic_graph_summary,
    fuse_directed_graphs,
    fuse_similarity_graphs,
    graph_summary,
    node_embedding_classifier_baseline,
    node_pruning_baseline,
)


def run_unmasking_reproduction(
    events: pd.DataFrame,
    *,
    relations: Sequence[str] = DEFAULT_RELATIONS,
    include_text_similarity: bool = True,
    min_similarity: float = 0.0,
    max_edges_per_node: int | None = None,
    node_pruning_percentile: float = 90.0,
    embedding_dim: int = 128,
    seed: int = 42,
) -> dict[str, object]:
    labels = extract_labels(events)
    graphs = build_unmasking_similarity_graphs(
        events,
        relations=relations,
        include_text_similarity=include_text_similarity,
        min_similarity=min_similarity,
        max_edges_per_node=max_edges_per_node,
    )
    fused = fuse_similarity_graphs(graphs)
    graph_summaries = {relation: graph_summary(graph, labels) for relation, graph in graphs.items()}
    graph_summaries["fused"] = graph_summary(fused, labels)
    pruning = {
        relation: node_pruning_baseline(graph, labels, percentile=node_pruning_percentile)
        for relation, graph in {**graphs, "fused": fused}.items()
    }
    embedding_classifier = node_embedding_classifier_baseline(fused, labels, dim=embedding_dim, seed=seed) if labels else None
    return {
        "method": "unmasking_reproduction",
        "relations": list(relations),
        "include_text_similarity": include_text_similarity,
        "graph_summaries": graph_summaries,
        "node_pruning": pruning,
        "node_embedding_classifier": embedding_classifier,
    }

def _user_content(events: pd.DataFrame) -> dict[str, str]:
    text_column = next((column for column in TEXT_COLUMNS if column in events.columns), None)
    documents: dict[str, list[str]] = defaultdict(list)
    if text_column is None:
        return {}
    for row in events.itertuples(index=False):
        documents[str(getattr(row, "account_id"))].append(str(getattr(row, text_column)))
    return {account_id: " ".join(parts) for account_id, parts in documents.items()}

def _account_display_name_map(events: pd.DataFrame) -> dict[str, str]:
    display_names: dict[str, str] = {}
    candidate_columns = ("nickname", "screen_name", "author_name", "user_name")
    available_columns = [column for column in candidate_columns if column in events.columns]
    if not available_columns:
        return display_names
    for row in events.itertuples(index=False):
        account_id = str(getattr(row, "account_id", "")).strip()
        if not account_id or account_id in display_names:
            continue
        for column in available_columns:
            value = str(getattr(row, column, "") or "").strip()
            if value:
                display_names[account_id] = value
                break
    return display_names

def _metadata_text(events: pd.DataFrame) -> dict[str, str]:
    metadata: dict[str, list[str]] = defaultdict(list)
    for row in events.itertuples(index=False):
        relation = str(getattr(row, "relation"))
        object_id = str(getattr(row, "object_id"))
        account_id = str(getattr(row, "account_id"))
        metadata[account_id].append(f"{relation}:{object_id}")
    return {account_id: " ".join(items) for account_id, items in metadata.items()}

def _interaction_text(graph: nx.Graph) -> dict[str, str]:
    output: dict[str, str] = {}
    for node in graph.nodes:
        neighbors = sorted(graph.neighbors(node), key=lambda item: (-float(graph[node][item].get("weight", 1.0)), item))
        output[str(node)] = " ".join(f"connected:{neighbor}" for neighbor in neighbors[:25])
    return output

def _bag_feature_matrix(text_by_user: Mapping[str, str], nodes: Sequence[str], max_features: int = 128) -> np.ndarray:
    document_tokens = {node: _tokenize(text_by_user.get(node, "")) for node in nodes}
    document_frequency: Counter[str] = Counter()
    for tokens in document_tokens.values():
        document_frequency.update(set(tokens))
    vocabulary = [
        token
        for token, _ in sorted(document_frequency.items(), key=lambda item: (-item[1], item[0]))[:max_features]
    ]
    index = {token: offset for offset, token in enumerate(vocabulary)}
    matrix = np.zeros((len(nodes), len(vocabulary)), dtype=float)
    node_count = max(len(nodes), 1)
    for row_index, node in enumerate(nodes):
        counts = Counter(document_tokens[node])
        total = float(sum(counts.values())) or 1.0
        for token, count in counts.items():
            if token not in index:
                continue
            idf = math.log((1.0 + node_count) / (1.0 + document_frequency[token])) + 1.0
            matrix[row_index, index[token]] = (count / total) * idf
    return matrix

def _reduce_feature_dim(matrix: np.ndarray, max_dim: int) -> np.ndarray:
    if matrix.size == 0 or matrix.shape[1] <= max_dim:
        return matrix
    try:
        _, _, vt = np.linalg.svd(matrix, full_matrices=False)
        return matrix @ vt[:max_dim].T
    except Exception:
        return matrix[:, :max_dim]

def _lm_feature_matrix(
    events: pd.DataFrame,
    nodes: Sequence[str],
    *,
    backend: str = "sbert",
    max_dim: int = 32,
    cache_dir: Path | None = None,
) -> tuple[np.ndarray, str]:
    content = _user_content(events)
    metadata = _metadata_text(events)
    texts = [
        " ".join(part for part in (content.get(node, ""), metadata.get(node, "")) if part).strip()
        for node in nodes
    ]
    requested = backend.lower().strip()
    cache_key = (
        requested,
        int(max_dim),
        len(nodes),
        hash(tuple(texts)),
        tuple(str(node) for node in nodes[:10]),
    )
    disk_cache_path: Path | None = None
    if cache_dir is not None:
        try:
            import hashlib

            digest = hashlib.sha1(
                json.dumps(
                    {
                        "backend": requested,
                        "max_dim": int(max_dim),
                        "nodes": [str(node) for node in nodes],
                        "texts": texts,
                    },
                    ensure_ascii=False,
                    sort_keys=True,
                ).encode("utf-8")
            ).hexdigest()[:20]
            disk_cache_path = Path(cache_dir) / f"lm_features_{requested}_{max_dim}_{digest}.npz"
            if disk_cache_path.exists():
                cached_npz = np.load(disk_cache_path, allow_pickle=False)
                return np.asarray(cached_npz["features"], dtype=float), str(cached_npz["source"].item())
        except Exception:
            disk_cache_path = None
    cached = _LM_FEATURE_CACHE.get(cache_key)
    if cached is not None:
        matrix, source = cached
        return matrix.copy(), source
    if requested == "sbert":
        try:
            os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
            from sentence_transformers import SentenceTransformer

            model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
            embeddings = model.encode(
                texts,
                batch_size=128,
                show_progress_bar=False,
                convert_to_numpy=True,
                normalize_embeddings=True,
            )
            matrix = _reduce_feature_dim(np.asarray(embeddings, dtype=float), max_dim)
            source = "sbert:sentence-transformers/all-MiniLM-L6-v2"
            _LM_FEATURE_CACHE[cache_key] = (matrix.copy(), source)
            if disk_cache_path is not None:
                disk_cache_path.parent.mkdir(parents=True, exist_ok=True)
                np.savez_compressed(disk_cache_path, features=matrix, source=np.asarray(source))
            return matrix, source
        except Exception:
            pass
    content_features = _bag_feature_matrix(content, nodes, max_features=max_dim)
    metadata_features = _bag_feature_matrix(metadata, nodes, max_features=max_dim)
    features = np.concatenate([content_features, metadata_features], axis=1)
    if features.shape[1] == 0:
        features = np.zeros((len(nodes), 1), dtype=float)
    matrix = _reduce_feature_dim(features, max_dim)
    source = "tfidf_object_bag_fallback"
    _LM_FEATURE_CACHE[cache_key] = (matrix.copy(), source)
    if disk_cache_path is not None:
        disk_cache_path.parent.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(disk_cache_path, features=matrix, source=np.asarray(source))
    return matrix, source

def _centrality_feature_matrix(graph: nx.Graph, nodes: Sequence[str]) -> np.ndarray:
    degree = _centrality_scores(graph, "degree")
    pagerank = _centrality_scores(graph, "pagerank")
    eigenvector = _centrality_scores(graph, "eigenvector")
    matrix = np.asarray(
        [
            [
                float(degree.get(node, 0.0)),
                float(pagerank.get(node, 0.0)),
                float(eigenvector.get(node, 0.0)),
            ]
            for node in nodes
        ],
        dtype=float,
    )
    for column in range(matrix.shape[1]):
        matrix[:, column] = _normalize_vector(matrix[:, column])
    return matrix

def _directed_feature_matrix(graph: nx.DiGraph, nodes: Sequence[str]) -> np.ndarray:
    matrix = np.asarray(
        [
            [
                float(graph.out_degree(node, weight="weight")),
                float(graph.in_degree(node, weight="weight")),
                float(graph.out_degree(node)),
                float(graph.in_degree(node)),
            ]
            for node in nodes
        ],
        dtype=float,
    )
    for column in range(matrix.shape[1]):
        matrix[:, column] = _normalize_vector(matrix[:, column])
    return matrix

def _community_evidence(
    events: pd.DataFrame,
    community: set[str],
    *,
    top_k: int = 10,
) -> dict[str, object]:
    community_events = events[events["account_id"].astype(str).isin(community)]
    object_counts: Counter[tuple[str, str]] = Counter()
    relation_counts: Counter[str] = Counter()
    for row in community_events.itertuples(index=False):
        object_id = _clean_object_id(getattr(row, "object_id", ""))
        relation = str(getattr(row, "relation", ""))
        if object_id:
            object_counts[(relation, object_id)] += 1
        if relation:
            relation_counts[relation] += 1
    total_objects = sum(object_counts.values())
    top_objects = [
        {
            "relation": relation,
            "object_id": object_id,
            "count": count,
            "share": round(_safe_divide(count, total_objects), 6),
        }
        for (relation, object_id), count in object_counts.most_common(top_k)
    ]
    return {
        "top_objects": top_objects,
        "object_concentration": top_objects[0]["share"] if top_objects else 0.0,
        "relation_breakdown": dict(relation_counts.most_common()),
    }

def generate_llm_prompt_records(
    events: pd.DataFrame,
    graph: nx.Graph,
    *,
    mode: str,
    labels: Mapping[str, int] | None = None,
) -> list[dict[str, object]]:
    nodes = sorted(set(events["account_id"].astype(str)).union(set(map(str, graph.nodes))))
    centrality = _centrality_feature_matrix(graph, nodes)
    metadata = _metadata_text(events)
    content = _user_content(events)
    interaction = _interaction_text(graph)
    records: list[dict[str, object]] = []
    for index, node in enumerate(nodes):
        if mode == "centrality":
            input_text = (
                f"User {node} has degree centrality {centrality[index, 0]:.4f}, "
                f"PageRank {centrality[index, 1]:.4f}, and eigenvector centrality {centrality[index, 2]:.4f}."
            )
        elif mode == "metadata":
            input_text = f"User {node} has metadata: {metadata.get(node, '')}"
        elif mode == "content":
            input_text = f"User {node} shared content: {content.get(node, '')[:2000]}"
        elif mode == "interaction":
            input_text = f"User {node} is {interaction.get(node, '')}"
        elif mode == "multi_input":
            input_text = (
                f"{interaction.get(node, '')} {metadata.get(node, '')} "
                f"centrality={centrality[index].round(4).tolist()} content={content.get(node, '')[:1000]}"
            )
        else:
            raise ValueError(f"Unsupported LLM baseline mode: {mode}")
        record = {
            "account_id": node,
            "instruction": "Determine if the user is actively driving an influence campaign.",
            "input": input_text.strip(),
        }
        if labels:
            record["output"] = bool(labels.get(node, 0))
        records.append(record)
    return records

def _write_jsonl(path: Path, records: Iterable[Mapping[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file_handle:
        for record in records:
            file_handle.write(json.dumps(record, ensure_ascii=False) + "\n")

def run_lightweight_llm_baselines(
    events: pd.DataFrame,
    graph: nx.Graph,
    *,
    output_dir: Path | None = None,
    seed: int = 42,
) -> dict[str, object]:
    labels = extract_labels(events)
    nodes = sorted(set(events["account_id"].astype(str)).union(set(map(str, graph.nodes))))
    if not labels or len(set(labels.values())) < 2:
        return {"method": "lightweight_llm_baselines", "modes": {}, "prompt_files": {}}
    y = np.asarray([int(labels.get(node, 0)) for node in nodes], dtype=int)
    feature_sources = {
        "interaction": _bag_feature_matrix(_interaction_text(graph), nodes),
        "centrality": _centrality_feature_matrix(graph, nodes),
        "metadata": _bag_feature_matrix(_metadata_text(events), nodes),
        "content": _bag_feature_matrix(_user_content(events), nodes),
    }
    feature_sources["multi_input"] = np.concatenate(
        [feature_sources[name] for name in ("interaction", "centrality", "metadata", "content")],
        axis=1,
    )
    results: dict[str, object] = {}
    prompt_files: dict[str, str] = {}
    for mode, matrix in feature_sources.items():
        test_indices, scores, backend = _fit_classifier_scores(matrix, y, seed=seed)
        metrics = binary_metrics(y[test_indices], scores) if test_indices.size else None
        results[mode] = {
            "backend": backend,
            "metrics": _metric_to_dict(metrics),
            "test_nodes": [nodes[int(index)] for index in test_indices.tolist()],
        }
        if output_dir is not None:
            records = generate_llm_prompt_records(events, graph, mode=mode, labels=labels)
            prompt_path = output_dir / "leveraging_llms" / f"{mode}_prompts.jsonl"
            _write_jsonl(prompt_path, records)
            prompt_files[mode] = str(prompt_path)
    return {"method": "lightweight_llm_baselines", "modes": results, "prompt_files": prompt_files}

def _relation_degree_features(
    graphs: Mapping[str, nx.Graph],
    nodes: Sequence[str],
) -> tuple[np.ndarray, dict[str, float]]:
    matrix = np.zeros((len(nodes), len(graphs)), dtype=float)
    relation_scores: dict[str, float] = {}
    for column, (relation, graph) in enumerate(graphs.items()):
        values = np.asarray([float(graph.degree(node, weight="weight")) for node in nodes], dtype=float)
        matrix[:, column] = _normalize_vector(values)
        relation_scores[relation] = float(np.mean(values) + graph.number_of_edges())
    return matrix, relation_scores

def _relation_attention(
    relation_scores: Mapping[str, float],
    relation_degrees: np.ndarray,
    labels: Mapping[str, int],
    nodes: Sequence[str],
) -> dict[str, float]:
    scores = np.asarray(list(relation_scores.values()), dtype=float)
    if labels and len(set(labels.values())) >= 2 and relation_degrees.size:
        y = np.asarray([int(labels.get(node, 0)) for node in nodes], dtype=float)
        for column in range(relation_degrees.shape[1]):
            x = relation_degrees[:, column]
            if np.std(x) > 1e-9 and np.std(y) > 1e-9:
                scores[column] += abs(float(np.corrcoef(x, y)[0, 1]))
    if scores.size == 0:
        return {}
    scores = scores - np.max(scores)
    exp_values = np.exp(scores)
    total = float(np.sum(exp_values)) or 1.0
    return {
        relation: float(exp_values[index] / total)
        for index, relation in enumerate(relation_scores)
    }

def _message_pass(
    graphs: Mapping[str, nx.Graph],
    nodes: Sequence[str],
    features: np.ndarray,
    attention: Mapping[str, float],
) -> np.ndarray:
    if features.size == 0:
        return features
    aggregate = np.zeros_like(features)
    node_index = {node: index for index, node in enumerate(nodes)}
    for relation, graph in graphs.items():
        if graph.number_of_edges() == 0:
            continue
        relation_weight = float(attention.get(relation, 0.0))
        if relation_weight <= 0.0:
            continue
        relation_aggregate = np.zeros_like(features)
        degree_weight = np.zeros((len(nodes), 1), dtype=float)
        for source, target, attrs in graph.edges(data=True):
            if source not in node_index or target not in node_index:
                continue
            source_index = node_index[source]
            target_index = node_index[target]
            weight = float(attrs.get("weight", 1.0))
            relation_aggregate[source_index] += weight * features[target_index]
            relation_aggregate[target_index] += weight * features[source_index]
            degree_weight[source_index, 0] += weight
            degree_weight[target_index, 0] += weight
        degree_weight[degree_weight <= 0.0] = 1.0
        aggregate += relation_weight * (relation_aggregate / degree_weight)
    return np.maximum(0.0, 0.5 * features + 0.5 * aggregate)

def _label_free_events(events: pd.DataFrame) -> pd.DataFrame:
    label_like_columns = [column for column in LABEL_COLUMNS if column in events.columns]
    return events.drop(columns=label_like_columns) if label_like_columns else events.copy()

def _base_discover_feature_matrix(
    fused: nx.Graph,
    dynamic_fused: nx.DiGraph,
    graphs: Mapping[str, nx.Graph],
    nodes: Sequence[str],
) -> tuple[np.ndarray, dict[str, float]]:
    centrality_features = _centrality_feature_matrix(fused, nodes)
    relation_features, relation_scores = _relation_degree_features(graphs, nodes)
    directed_features = _directed_feature_matrix(dynamic_fused, nodes)
    return np.concatenate([centrality_features, relation_features, directed_features], axis=1), relation_scores

def _community_records_from_graph(
    graph: nx.Graph,
    events: pd.DataFrame,
    nodes: Sequence[str],
    node_score_map: Mapping[str, float],
    *,
    community_algorithm: str = "leiden",
    seed: int = 42,
    communities: Sequence[set[str]] | None = None,
) -> tuple[list[dict[str, object]], dict[str, int]]:
    partition = (
        [set(map(str, community)) for community in communities]
        if communities is not None
        else (
            _detect_communities(graph, algorithm=community_algorithm, seed=seed)
            if graph.number_of_edges()
            else [{node} for node in nodes]
        )
    )
    cluster_by_node: dict[str, int] = {}
    community_records = []
    for cluster_id, community in enumerate(partition):
        for node in community:
            cluster_by_node[node] = cluster_id
        subgraph = graph.subgraph(community)
        evidence = _community_evidence(events, community)
        community_records.append(
            {
                "cluster_id": cluster_id,
                "size": len(community),
                "community_score": round(float(np.mean([float(node_score_map.get(node, 0.0)) for node in community])), 6),
                "density": round(float(nx.density(subgraph)), 6) if len(community) > 1 else 0.0,
                "top_nodes": sorted(community, key=lambda node: (-float(node_score_map.get(node, 0.0)), node))[:10],
                "top_objects": evidence["top_objects"],
                "object_concentration": evidence["object_concentration"],
                "relation_breakdown": evidence["relation_breakdown"],
            }
        )
    return sorted(community_records, key=lambda item: (-float(item["community_score"]), item["cluster_id"])), cluster_by_node

def _graph_with_deep_edge_scores(graph: nx.Graph, edge_scores: Mapping[tuple[str, str], float]) -> nx.Graph:
    weighted = graph.copy()
    for source, target, attrs in weighted.edges(data=True):
        key = tuple(sorted((str(source), str(target))))
        learned_score = float(edge_scores.get(key, 0.0))
        attrs["edge_score"] = learned_score
        attrs["original_weight"] = float(attrs.get("weight", 1.0))
        if learned_score > 0.0:
            attrs["weight"] = attrs["original_weight"] * learned_score
    return weighted

def _edge_key_text(source: object, target: object) -> str:
    left, right = sorted((str(source), str(target)))
    return f"{left}\t{right}"

def _serialize_observed_edge_scores(edge_scores: Mapping[tuple[str, str], float]) -> dict[str, float]:
    return {
        _edge_key_text(source, target): round(float(score), 6)
        for (source, target), score in sorted(edge_scores.items())
    }

def _embedding_row(embedding: np.ndarray, index: int) -> list[float]:
    if embedding.size == 0 or index >= embedding.shape[0]:
        return []
    return [round(float(value), 6) for value in embedding[index].tolist()]

__all__ = [
    "generate_llm_prompt_records",
    "run_lightweight_llm_baselines",
    "run_unmasking_reproduction",
]
