"""Focused discover runtime implementation."""

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

from app.core.coordination_baseline.reproduction_features import (
    _centrality_feature_matrix,
    _community_records_from_graph,
    _label_free_events,
)
from app.core.coordination_baseline.reproduction_deep_discover import (
    _community_avg_time_delta,
    _deep_discover_summary,
    _discover_encoder_governance,
    _discovery_metrics,
    _dynamic_edge_records_from_graph,
    _edge_records_from_graph,
    _evidence_summary,
)

def run_zeyan_coexpression_discover(
    events: pd.DataFrame,
    *,
    relations: Sequence[str] = DEFAULT_RELATIONS,
    seed: int = 42,
    community_algorithm: str = "leiden",
    include_text_similarity: bool = False,
) -> dict[str, object]:
    """Zeyan-style co-expression baseline: static user-user graph plus community detection."""
    events = _label_free_events(events)
    graphs = build_unmasking_similarity_graphs(
        events,
        relations=relations,
        include_text_similarity=include_text_similarity,
    )
    fused = fuse_similarity_graphs(graphs)
    dynamic_relation_graphs = build_dynamic_relation_graphs(events, relations=relations)
    dynamic_fused = fuse_directed_graphs(dynamic_relation_graphs)
    nodes = sorted(set(events["account_id"].astype(str)).union(set(map(str, fused.nodes))))
    fused.add_nodes_from(nodes)
    dynamic_fused.add_nodes_from(nodes)
    for graph in graphs.values():
        graph.add_nodes_from(nodes)
    centrality = _centrality_feature_matrix(fused, nodes)
    degree_scores = _normalize_vector(
        np.asarray([float(fused.degree(node, weight="weight")) for node in nodes], dtype=float)
    )
    node_scores = _normalize_vector(centrality[:, 0] + centrality[:, 1] + degree_scores)
    node_score_map = {node: float(node_scores[index]) for index, node in enumerate(nodes)}
    communities, cluster_by_node = _community_records_from_graph(
        fused,
        events,
        nodes,
        node_score_map,
        community_algorithm=community_algorithm,
        seed=seed,
    )
    edge_records = _edge_records_from_graph(fused, node_score_map)
    dynamic_edge_records = _dynamic_edge_records_from_graph(dynamic_fused, node_score_map)
    active_relations = [relation for relation, graph in graphs.items() if graph.number_of_edges() > 0]
    relation_weight = _safe_divide(1.0, len(active_relations))
    graph_stats = graph_summary(fused, None, community_algorithm=community_algorithm, seed=seed)
    result = {
        "method": "zeyan_coexpression_discover",
        "variant": "zeyan_coexpression",
        "task": "coordination_community_discovery",
        "uses_lm_features": include_text_similarity,
        "uses_gnn_message_passing": False,
        "uses_direction_time_features": True,
        "uses_relation_attention": False,
        "relation_attention_mode": "static_zeyan_coexpression",
        "uses_community_features": False,
        "community_algorithm": community_algorithm,
        "community_algorithm_effective": graph_stats.get("community_algorithm_effective"),
        "community_algorithm_backend": graph_stats.get("community_algorithm_backend"),
        "community_algorithm_fallback_reason": graph_stats.get("community_algorithm_fallback_reason"),
        "graph_summary": graph_stats,
        "dynamic_graph_summary": dynamic_graph_summary(dynamic_fused),
        "relation_attention": {relation: round(relation_weight, 6) for relation in active_relations},
        "classifier_backend": "zeyan_static_coexpression",
        "metrics": None,
        "nodes": [
            {
                "account_id": node,
                "node_score": round(node_score_map[node], 6),
                "deep_node_score": round(node_score_map[node], 6),
                "embedding_norm": round(float(np.linalg.norm(centrality[index])), 6),
                "cluster_id": cluster_by_node.get(node),
                "directed_out_weight": round(float(dynamic_fused.out_degree(node, weight="weight")), 6),
                "directed_in_weight": round(float(dynamic_fused.in_degree(node, weight="weight")), 6),
            }
            for index, node in enumerate(nodes)
        ],
        "edges": edge_records,
        "dynamic_edges": dynamic_edge_records,
        "communities": communities,
        "deep_graph_model": {
            "encoder": "zeyan_coexpression",
            "training_loss": [],
            "reconstruction_metrics": {},
            "device": "cpu",
            "epochs": 0,
            "embedding_dim": int(centrality.shape[1]) if centrality.ndim == 2 else 0,
            "uses_labels": False,
            "metapath_attention": {},
            "intra_metapath_attention": {},
            "intra_metapath_attention_summary": {},
            "metapath_instance_counts": {},
            "object_node_count": 0,
            "edge_score_source": "static_coexpression_weight",
        },
    }
    return result

def run_zeyan_coexpression_summary(
    events: pd.DataFrame,
    *,
    output_dir: Path | None = None,
    relations: Sequence[str] = DEFAULT_RELATIONS,
    seed: int = 42,
    community_algorithm: str = "leiden",
    include_text_similarity: bool = False,
) -> dict[str, object]:
    result = run_zeyan_coexpression_discover(
        events,
        relations=relations,
        seed=seed,
        community_algorithm=community_algorithm,
        include_text_similarity=include_text_similarity,
    )
    summary = {
        "setting": "discover",
        "task": "coordination_community_discovery",
        "method": "zeyan_coexpression_discover",
        "relations": list(relations),
        "community_algorithm": community_algorithm,
        "community_algorithm_effective": result.get("community_algorithm_effective"),
        "metrics": _discovery_metrics(result),
        "relation_attention": result.get("relation_attention", {}),
        "graph_metrics": result.get("graph_summary", {}),
        "dynamic_graph_metrics": result.get("dynamic_graph_summary", {}),
        "nodes": result.get("nodes", []),
        "edges": result.get("edges", []),
        "dynamic_edges": result.get("dynamic_edges", []),
        "communities": result.get("communities", []),
        "evidence_summary": _evidence_summary(result),
        "deep_graph_model": result.get("deep_graph_model", {}),
    }
    if output_dir is not None:
        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / "discovery_summary.json").write_text(
            json.dumps(summary, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    return summary

def run_discover_ablation_suite(
    events: pd.DataFrame,
    *,
    relations: Sequence[str] = DEFAULT_RELATIONS,
    seed: int = 42,
    epochs: int = 5,
    embedding_dim: int = 16,
    hidden_dim: int = 16,
    device: str = "auto",
    community_algorithm: str = "leiden",
) -> dict[str, dict[str, object]]:
    variants = {
        "raw_graph_community": lambda: run_dyna_colm_discover(
            events,
            relations=relations,
            seed=seed,
            encoder="lightweight",
            community_algorithm=community_algorithm,
        ),
        "zeyan_coexpression": lambda: {
            **run_zeyan_coexpression_summary(
                events,
                relations=relations,
                seed=seed,
                community_algorithm=community_algorithm,
            )
        },
        "magnn_legacy": lambda: run_dyna_colm_discover(
            events,
            relations=relations,
            seed=seed,
            encoder="magnn_legacy",
            epochs=epochs,
            embedding_dim=embedding_dim,
            hidden_dim=hidden_dim,
            device=device,
            community_algorithm=community_algorithm,
        ),
        "han": lambda: run_dyna_colm_discover(
            events,
            relations=relations,
            seed=seed,
            encoder="han",
            epochs=epochs,
            embedding_dim=embedding_dim,
            hidden_dim=hidden_dim,
            device=device,
            community_algorithm=community_algorithm,
        ),
        "amdn_hage": lambda: run_dyna_colm_discover(
            events,
            relations=relations,
            seed=seed,
            encoder="amdn_hage",
            epochs=epochs,
            embedding_dim=embedding_dim,
            hidden_dim=hidden_dim,
            device=device,
            community_algorithm=community_algorithm,
        ),
    }
    output: dict[str, dict[str, object]] = {}
    for name, factory in variants.items():
        summary = factory()
        output[name] = summary
    return output

def run_dyna_colm_discover(
    events: pd.DataFrame,
    *,
    output_dir: Path | None = None,
    relations: Sequence[str] = DEFAULT_RELATIONS,
    seed: int = 42,
    encoder: str = STABLE_DISCOVER_ENCODER,
    community_algorithm: str = "leiden",
    epochs: int = 80,
    embedding_dim: int = 64,
    hidden_dim: int = 64,
    lr: float = 1e-3,
    negative_ratio: float = 1.0,
    device: str = "auto",
    structure_filter: str = "none",
    structure_filter_metric: str = "eigenvector",
    structure_filter_percentile: float = 90.0,
    structure_filter_use_weights: bool = False,
) -> dict[str, object]:
    # The default stays on the stable legacy MAGNN path after the newer
    # instance encoder regressed IOHunter reconstruction AUC/AP.
    if structure_filter not in DISCOVER_STRUCTURE_FILTERS:
        raise ValueError(
            f"Discover structure_filter must be one of: {', '.join(DISCOVER_STRUCTURE_FILTERS)}"
        )
    if structure_filter_metric not in DISCOVER_STRUCTURE_FILTER_METRICS:
        raise ValueError(
            f"Discover structure_filter_metric must be one of: {', '.join(DISCOVER_STRUCTURE_FILTER_METRICS)}"
        )
    if structure_filter != "none":
        # Backward-compatible argument acceptance only. Mainline Discover is
        # fixed to the MAGNN full-graph workflow, so pruning requests are
        # recorded in the output summary but ignored during execution.
        structure_filter = "node_pruning"
    config = DeepGraphDiscoverConfig(
        encoder=encoder,  # type: ignore[arg-type]
        embedding_dim=embedding_dim,
        hidden_dim=hidden_dim,
        epochs=epochs,
        lr=lr,
        negative_ratio=negative_ratio,
        device=device,
        seed=seed,
    )
    if encoder == "lightweight":
        result = _deep_discover_summary(
            events,
            relations=relations,
            seed=seed,
            config=config,
            community_algorithm=community_algorithm,
            structure_filter=structure_filter,
            structure_filter_metric=structure_filter_metric,
            structure_filter_percentile=structure_filter_percentile,
            structure_filter_use_weights=structure_filter_use_weights,
        )
    elif encoder in {"han_relation", "han", "magnn_legacy", "magnn", "amdn_hage"}:
        result = _deep_discover_summary(
            events,
            relations=relations,
            seed=seed,
            config=config,
            community_algorithm=community_algorithm,
            structure_filter=structure_filter,
            structure_filter_metric=structure_filter_metric,
            structure_filter_percentile=structure_filter_percentile,
            structure_filter_use_weights=structure_filter_use_weights,
        )
    else:
        raise ValueError("Discover encoder must be one of: lightweight, han_relation, han, magnn_legacy, magnn, amdn_hage")
    dynamic_edges = result.get("dynamic_edges", [])
    communities = []
    for community in result.get("communities", []):
        if not isinstance(community, Mapping):
            continue
        community_nodes = set(map(str, community.get("top_nodes", [])))
        record = dict(community)
        record["avg_time_delta"] = _community_avg_time_delta(dynamic_edges, community_nodes)
        communities.append(record)
    summary = {
        "setting": "discover",
        "task": "coordination_community_discovery",
        "method": "dyna_colm_discover",
        "relations": list(relations),
        "community_algorithm": community_algorithm,
        "community_algorithm_effective": result.get("community_algorithm_effective"),
        "community_algorithm_backend": result.get("community_algorithm_backend"),
        "community_algorithm_fallback_reason": result.get("community_algorithm_fallback_reason"),
        "structure_filter": result.get("structure_filter", {}),
        "metrics": _discovery_metrics(result),
        "relation_attention": result.get("relation_attention", {}),
        "graph_metrics": result.get("graph_summary", {}),
        "dynamic_graph_metrics": result.get("dynamic_graph_summary", {}),
        "nodes": result.get("nodes", []),
        "edges": result.get("edges", []),
        "dynamic_edges": dynamic_edges,
        "communities": sorted(communities, key=lambda item: (-float(item.get("community_score", 0.0)), item.get("cluster_id"))),
        "evidence_summary": _evidence_summary(result),
        "deep_graph_model": result.get("deep_graph_model", {}),
        "model_governance": result.get("model_governance", _discover_encoder_governance(encoder)),
    }
    if output_dir is not None:
        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / "discovery_summary.json").write_text(
            json.dumps(summary, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    return summary

def run_discover_stability_analysis(
    events: pd.DataFrame,
    *,
    output_dir: Path | None = None,
    relations: Sequence[str] = DEFAULT_RELATIONS,
    seed: int = 42,
    encoder: str = STABLE_DISCOVER_ENCODER,
    community_algorithm: str = "leiden",
    epochs: int = 20,
    embedding_dim: int = 32,
    hidden_dim: int = 32,
    lr: float = 1e-3,
    negative_ratio: float = 1.0,
    device: str = "auto",
    window_sizes: Sequence[float] = (3600.0, 21600.0, 86400.0),
    min_events_per_window: int = 2,
) -> dict[str, object]:
    """Evaluate label-free Discover stability across time windows and scales."""
    events = _label_free_events(normalize_event_table(events))
    timestamp_values = events["timestamp"].map(_timestamp_to_float).astype(float).to_numpy()
    if timestamp_values.size == 0:
        raise ValueError("Stability analysis requires at least one event")
    min_time = float(np.min(timestamp_values))
    max_time = float(np.max(timestamp_values))
    windows: list[dict[str, object]] = []
    pairwise: list[dict[str, object]] = []
    window_cache: list[dict[str, object]] = []
    for window_size in [float(value) for value in window_sizes if float(value) > 0.0]:
        current = min_time
        scale_windows: list[dict[str, object]] = []
        window_index = 0
        while current <= max_time:
            end_time = current + window_size
            mask = (
                ((timestamp_values >= current) & (timestamp_values <= max_time))
                if end_time > max_time
                else ((timestamp_values >= current) & (timestamp_values < end_time))
            )
            window_events = events.loc[mask].copy()
            if len(window_events) >= int(min_events_per_window):
                window_output_dir = (
                    output_dir / "windows" / _safe_window_name(window_size, window_index)
                    if output_dir is not None
                    else None
                )
                summary = run_dyna_colm_discover(
                    window_events,
                    output_dir=window_output_dir,
                    relations=relations,
                    seed=seed,
                    encoder=encoder,
                    community_algorithm=community_algorithm,
                    epochs=epochs,
                    embedding_dim=embedding_dim,
                    hidden_dim=hidden_dim,
                    lr=lr,
                    negative_ratio=negative_ratio,
                    device=device,
                )
                row = _stability_window_row(
                    summary,
                    window_size=window_size,
                    window_index=window_index,
                    start_time=current,
                    end_time=min(end_time, max_time),
                    event_count=len(window_events),
                )
                record = {"row": row, "summary": summary}
                windows.append(row)
                scale_windows.append(record)
                window_cache.append(record)
            current = end_time
            window_index += 1
    for window_size in sorted({float(row["window_size_seconds"]) for row in windows}):
        scale_windows = [
            record
            for record in window_cache
            if float(record["row"]["window_size_seconds"]) == window_size
        ]
        pairwise.extend(_adjacent_window_stability(scale_windows, window_size=window_size))
    pairwise.extend(_multiscale_stability(window_cache))
    summary = {
        "setting": "discover",
        "task": "coordination_community_stability",
        "method": "dyna_colm_discover_stability",
        "encoder": encoder,
        "community_algorithm": community_algorithm,
        "window_sizes": [float(value) for value in window_sizes],
        "min_events_per_window": int(min_events_per_window),
        "window_count": len(windows),
        "pairwise_count": len(pairwise),
        "windows": windows,
        "pairwise_stability": pairwise,
        "summary": _stability_summary(windows, pairwise),
    }
    if output_dir is not None:
        output_dir.mkdir(parents=True, exist_ok=True)
        _write_dict_rows(output_dir / "discover_stability_windows.csv", windows)
        _write_dict_rows(output_dir / "discover_stability_pairwise.csv", pairwise)
        _write_dict_rows(output_dir / "discover_stability_summary.csv", [summary["summary"]])
        (output_dir / "stability_manifest.json").write_text(
            json.dumps(summary, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    return summary

def _safe_window_name(window_size: float, window_index: int) -> str:
    return f"w{int(round(window_size))}_idx{window_index}"

def _stability_window_row(
    summary: Mapping[str, object],
    *,
    window_size: float,
    window_index: int,
    start_time: float,
    end_time: float,
    event_count: int,
) -> dict[str, object]:
    metrics = summary.get("metrics") if isinstance(summary.get("metrics"), Mapping) else {}
    graph_metrics = summary.get("graph_metrics") if isinstance(summary.get("graph_metrics"), Mapping) else {}
    return {
        "window_size_seconds": float(window_size),
        "window_index": int(window_index),
        "window_start": round(float(start_time), 6),
        "window_end": round(float(end_time), 6),
        "event_count": int(event_count),
        "node_count": graph_metrics.get("node_count"),
        "edge_count": graph_metrics.get("edge_count"),
        "cluster_count": metrics.get("cluster_count"),
        "largest_cluster_size": metrics.get("largest_cluster_size"),
        "modularity": metrics.get("modularity"),
        "conductance": metrics.get("conductance"),
        "density": metrics.get("density"),
        "mean_object_concentration": metrics.get("mean_object_concentration"),
        "relation_entropy": metrics.get("relation_entropy"),
        "community_algorithm": summary.get("community_algorithm"),
        "community_algorithm_effective": summary.get("community_algorithm_effective"),
    }

def _adjacent_window_stability(
    scale_windows: Sequence[Mapping[str, object]],
    *,
    window_size: float,
) -> list[dict[str, object]]:
    rows = []
    for left, right in zip(scale_windows, scale_windows[1:]):
        left_row = left.get("row") if isinstance(left.get("row"), Mapping) else {}
        right_row = right.get("row") if isinstance(right.get("row"), Mapping) else {}
        rows.append(
            {
                **_community_assignment_stability(
                    left.get("summary") if isinstance(left.get("summary"), Mapping) else {},
                    right.get("summary") if isinstance(right.get("summary"), Mapping) else {},
                ),
                "comparison_type": "adjacent_time_windows",
                "left_window_size_seconds": float(window_size),
                "right_window_size_seconds": float(window_size),
                "left_window_index": left_row.get("window_index"),
                "right_window_index": right_row.get("window_index"),
            }
        )
    return rows

def _multiscale_stability(window_cache: Sequence[Mapping[str, object]]) -> list[dict[str, object]]:
    grouped: dict[int, list[Mapping[str, object]]] = defaultdict(list)
    for record in window_cache:
        row = record.get("row") if isinstance(record.get("row"), Mapping) else {}
        grouped[int(row.get("window_index", 0))].append(record)
    rows = []
    for window_index, group in grouped.items():
        sorted_group = sorted(
            group,
            key=lambda item: float(item.get("row", {}).get("window_size_seconds", 0.0))
            if isinstance(item.get("row"), Mapping)
            else 0.0,
        )
        for left, right in zip(sorted_group, sorted_group[1:]):
            left_row = left.get("row") if isinstance(left.get("row"), Mapping) else {}
            right_row = right.get("row") if isinstance(right.get("row"), Mapping) else {}
            rows.append(
                {
                    **_community_assignment_stability(
                        left.get("summary") if isinstance(left.get("summary"), Mapping) else {},
                        right.get("summary") if isinstance(right.get("summary"), Mapping) else {},
                    ),
                    "comparison_type": "multiscale_same_index",
                    "left_window_size_seconds": left_row.get("window_size_seconds"),
                    "right_window_size_seconds": right_row.get("window_size_seconds"),
                    "left_window_index": window_index,
                    "right_window_index": window_index,
                }
            )
    return rows

def _community_assignment_stability(
    left_summary: Mapping[str, object],
    right_summary: Mapping[str, object],
) -> dict[str, object]:
    left_assignment = _cluster_assignment(left_summary)
    right_assignment = _cluster_assignment(right_summary)
    common_nodes = sorted(set(left_assignment).intersection(right_assignment))
    if not common_nodes:
        return {"nmi": None, "ari": None, "jaccard": None, "common_node_count": 0}
    left_labels = [left_assignment[node] for node in common_nodes]
    right_labels = [right_assignment[node] for node in common_nodes]
    return {
        "nmi": _normalized_mutual_info(left_labels, right_labels),
        "ari": _adjusted_rand_index(left_labels, right_labels),
        "jaccard": _assignment_pair_jaccard(left_assignment, right_assignment, common_nodes),
        "common_node_count": len(common_nodes),
    }

def _cluster_assignment(summary: Mapping[str, object]) -> dict[str, int]:
    assignment: dict[str, int] = {}
    nodes = summary.get("nodes") if isinstance(summary.get("nodes"), Sequence) else []
    for node in nodes:
        if not isinstance(node, Mapping):
            continue
        account_id = str(node.get("account_id", ""))
        if not account_id:
            continue
        cluster_id = node.get("cluster_id")
        assignment[account_id] = int(cluster_id) if cluster_id is not None else -1
    return assignment

def _normalized_mutual_info(left_labels: Sequence[int], right_labels: Sequence[int]) -> float | None:
    try:
        from sklearn.metrics import normalized_mutual_info_score

        return round(float(normalized_mutual_info_score(left_labels, right_labels)), 6)
    except Exception:
        return _normalized_mutual_info_fallback(left_labels, right_labels)

def _adjusted_rand_index(left_labels: Sequence[int], right_labels: Sequence[int]) -> float | None:
    try:
        from sklearn.metrics import adjusted_rand_score

        return round(float(adjusted_rand_score(left_labels, right_labels)), 6)
    except Exception:
        return _adjusted_rand_index_fallback(left_labels, right_labels)

def _normalized_mutual_info_fallback(left_labels: Sequence[int], right_labels: Sequence[int]) -> float | None:
    if len(left_labels) != len(right_labels) or not left_labels:
        return None
    n = float(len(left_labels))
    left_counts = Counter(left_labels)
    right_counts = Counter(right_labels)
    joint_counts = Counter(zip(left_labels, right_labels))
    mutual_info = 0.0
    for (left, right), count in joint_counts.items():
        if count <= 0:
            continue
        mutual_info += (count / n) * math.log((count * n) / (left_counts[left] * right_counts[right]))
    left_entropy = -sum((count / n) * math.log(count / n) for count in left_counts.values() if count)
    right_entropy = -sum((count / n) * math.log(count / n) for count in right_counts.values() if count)
    denominator = (left_entropy + right_entropy) / 2.0
    if denominator <= 1e-12:
        return 1.0
    return round(float(mutual_info / denominator), 6)

def _adjusted_rand_index_fallback(left_labels: Sequence[int], right_labels: Sequence[int]) -> float | None:
    if len(left_labels) != len(right_labels) or not left_labels:
        return None
    n = len(left_labels)
    if n < 2:
        return 1.0
    left_counts = Counter(left_labels)
    right_counts = Counter(right_labels)
    joint_counts = Counter(zip(left_labels, right_labels))

    def comb2(value: int) -> float:
        return float(value * (value - 1) / 2)

    sum_comb_joint = sum(comb2(count) for count in joint_counts.values())
    sum_comb_left = sum(comb2(count) for count in left_counts.values())
    sum_comb_right = sum(comb2(count) for count in right_counts.values())
    total_pairs = comb2(n)
    if total_pairs <= 0:
        return 1.0
    expected_index = (sum_comb_left * sum_comb_right) / total_pairs
    max_index = 0.5 * (sum_comb_left + sum_comb_right)
    denominator = max_index - expected_index
    if abs(denominator) <= 1e-12:
        return 1.0
    return round(float((sum_comb_joint - expected_index) / denominator), 6)

def _assignment_pair_jaccard(
    left_assignment: Mapping[str, int],
    right_assignment: Mapping[str, int],
    common_nodes: Sequence[str],
) -> float:
    left_pairs = _co_cluster_pairs(left_assignment, common_nodes)
    right_pairs = _co_cluster_pairs(right_assignment, common_nodes)
    union = left_pairs.union(right_pairs)
    if not union:
        return 1.0
    return round(float(len(left_pairs.intersection(right_pairs)) / len(union)), 6)

def _co_cluster_pairs(assignment: Mapping[str, int], nodes: Sequence[str]) -> set[tuple[str, str]]:
    clusters: dict[int, list[str]] = defaultdict(list)
    for node in nodes:
        clusters[int(assignment[node])].append(node)
    pairs: set[tuple[str, str]] = set()
    for members in clusters.values():
        members = sorted(members)
        for index, source in enumerate(members):
            for target in members[index + 1 :]:
                pairs.add((source, target))
    return pairs

def _stability_summary(
    windows: Sequence[Mapping[str, object]],
    pairwise: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    adjacent = [row for row in pairwise if row.get("comparison_type") == "adjacent_time_windows"]
    return {
        "window_count": len(windows),
        "pairwise_count": len(pairwise),
        "mean_modularity": _mean_optional(row.get("modularity") for row in windows),
        "mean_conductance": _mean_optional(row.get("conductance") for row in windows),
        "mean_object_concentration": _mean_optional(row.get("mean_object_concentration") for row in windows),
        "mean_adjacent_nmi": _mean_optional(row.get("nmi") for row in adjacent),
        "mean_adjacent_ari": _mean_optional(row.get("ari") for row in adjacent),
        "mean_adjacent_jaccard": _mean_optional(row.get("jaccard") for row in adjacent),
    }

def _mean_optional(values: Iterable[object]) -> float | None:
    numeric = []
    for value in values:
        if value in {None, ""}:
            continue
        try:
            numeric.append(float(value))
        except (TypeError, ValueError):
            continue
    return round(float(np.mean(numeric)), 6) if numeric else None

def _write_dict_rows(path: Path, rows: Sequence[Mapping[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = sorted({key for row in rows for key in row.keys()})
    with path.open("w", encoding="utf-8", newline="") as file_handle:
        if not fields:
            return
        writer = csv.DictWriter(file_handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)

__all__ = [
    "run_discover_ablation_suite",
    "run_discover_stability_analysis",
    "run_dyna_colm_discover",
    "run_zeyan_coexpression_discover",
    "run_zeyan_coexpression_summary",
]
