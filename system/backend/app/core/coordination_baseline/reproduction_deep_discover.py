"""Focused deep discover implementation."""

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
    _account_display_name_map,
    _bag_feature_matrix,
    _base_discover_feature_matrix,
    _centrality_feature_matrix,
    _community_evidence,
    _community_records_from_graph,
    _directed_feature_matrix,
    _embedding_row,
    _graph_with_deep_edge_scores,
    _label_free_events,
    _message_pass,
    _metadata_text,
    _relation_attention,
    _relation_degree_features,
    _serialize_observed_edge_scores,
    _user_content,
)

def _deep_discover_summary(
    events: pd.DataFrame,
    *,
    relations: Sequence[str],
    seed: int,
    config: DeepGraphDiscoverConfig,
    community_algorithm: str = "leiden",
    structure_filter: str = "none",
    structure_filter_metric: str = "eigenvector",
    structure_filter_percentile: float = 90.0,
    structure_filter_use_weights: bool = False,
) -> dict[str, object]:
    events = _label_free_events(events)
    display_names = _account_display_name_map(events)
    graphs = build_unmasking_similarity_graphs(events, relations=relations, include_text_similarity=False)
    fused = fuse_similarity_graphs(graphs)
    dynamic_relation_graphs = build_dynamic_relation_graphs(events, relations=relations)
    dynamic_fused = fuse_directed_graphs(dynamic_relation_graphs)
    nodes = sorted(set(events["account_id"].astype(str)).union(set(map(str, fused.nodes))))
    for node in nodes:
        fused.add_node(node)
        dynamic_fused.add_node(node)
        for graph in graphs.values():
            graph.add_node(node)
    features, relation_scores = _base_discover_feature_matrix(fused, dynamic_fused, graphs, nodes)
    if config.encoder == "lightweight":
        attention = _relation_attention(relation_scores, features[:, 4 : 4 + len(graphs)] if graphs else features, {}, nodes)
        embedding = _message_pass(graphs, nodes, features, attention)
        node_scores = _normalize_vector(np.linalg.norm(embedding, axis=1))
        deep_result = None
        weighted_fused = fused
    else:
        deep_result = run_deep_graph_discover(graphs, nodes, features, config)
        attention = deep_result.relation_attention
        embedding = deep_result.embeddings
        node_scores = _normalize_vector(np.linalg.norm(embedding, axis=1))
        weighted_fused = _graph_with_deep_edge_scores(fused, deep_result.edge_scores)
    node_score_map = {node: float(node_scores[index]) for index, node in enumerate(nodes)}

    # Discover is fixed to the full-graph stable encoder path. We keep the
    # old structure-filter arguments only so older scripts do not break, but
    # the requested pruning mode is ignored because it changes the task from
    # label-free community discovery into a structural screening variant and
    # empirically degraded community quality in our CoordinationDiscover runs.
    requested_structure_filter = {
        "mode": str(structure_filter),
        "metric": str(structure_filter_metric),
        "percentile": float(structure_filter_percentile),
        "use_weights": bool(structure_filter_use_weights),
    }
    filtered_graph, structure_filter_summary, selected_nodes, structure_filter_scores = _apply_discover_structure_filter(
        weighted_fused,
        mode="none",
        metric=structure_filter_metric,
        percentile=structure_filter_percentile,
        use_weights=False,
    )
    structure_filter_summary = {
        **structure_filter_summary,
        "mode": "none",
        "effective": False,
        "selection_graph": "weighted_fused_similarity_network" if config.encoder != "lightweight" else "fused_similarity_network",
        "selection_semantics": "full_graph_mainline",
        "requested_mode": requested_structure_filter["mode"],
        "requested_metric": requested_structure_filter["metric"],
        "requested_percentile": requested_structure_filter["percentile"],
        "requested_use_weights": requested_structure_filter["use_weights"],
        "deprecated_ignored": requested_structure_filter["mode"] != "none",
        "disabled_reason": (
            "CoordinationDiscover Discover is fixed to the stable full-graph encoder; "
            "Unmasking-style structural screening is no longer applied."
        ),
    }
    communities, cluster_by_node = _community_records_from_graph(
        filtered_graph,
        events,
        nodes,
        node_score_map,
        community_algorithm=community_algorithm,
        seed=seed,
    )
    graph_stats = graph_summary(filtered_graph, None, community_algorithm=community_algorithm, seed=seed)
    edge_graph = filtered_graph
    edge_records = _edge_records_from_graph(edge_graph, node_score_map)
    dynamic_edge_records = _dynamic_edge_records_from_graph(dynamic_fused, node_score_map)
    result = {
        "method": "dyna_colm_discover",
        "variant": "discover",
        "task": "coordination_community_discovery",
        "uses_lm_features": False,
        "uses_gnn_message_passing": config.encoder != "lightweight",
        "uses_direction_time_features": True,
        "uses_relation_attention": True,
        "relation_attention_mode": _discover_attention_mode(config.encoder),
        "community_algorithm": community_algorithm,
        "community_algorithm_effective": graph_stats.get("community_algorithm_effective"),
        "community_algorithm_backend": graph_stats.get("community_algorithm_backend"),
        "community_algorithm_fallback_reason": graph_stats.get("community_algorithm_fallback_reason"),
        "uses_community_features": False,
        "graph_summary": graph_stats,
        "dynamic_graph_summary": dynamic_graph_summary(dynamic_fused),
        "relation_attention": {key: round(float(value), 6) for key, value in attention.items()},
        "structure_filter": {
            **structure_filter_summary,
            "metric_scores_preview": {
                key: round(float(value), 6)
                for key, value in sorted(structure_filter_scores.items(), key=lambda item: (-float(item[1]), item[0]))[:20]
            },
        },
        "classifier_backend": f"{config.encoder}_discover_encoder",
        "metrics": None,
        "nodes": [
            {
                "account_id": node,
                "nickname": display_names.get(node),
                "node_score": round(node_score_map[node], 6),
                "deep_node_score": round(node_score_map[node], 6),
                "embedding_norm": round(float(np.linalg.norm(embedding[index])), 6) if embedding.size else 0.0,
                "discover_embedding": _embedding_row(embedding, index),
                "cluster_id": cluster_by_node.get(node),
                # These compatibility fields stay in the schema because Detect
                # feature builders and old reports expect them, but Discover
                # no longer prunes nodes so every node passes with a neutral
                # full-graph score.
                "passed_structure_filter": node in selected_nodes,
                "structure_filter_score": round(float(structure_filter_scores.get(node, 0.0)), 6),
                "directed_out_weight": round(float(dynamic_fused.out_degree(node, weight="weight")), 6),
                "directed_in_weight": round(float(dynamic_fused.in_degree(node, weight="weight")), 6),
            }
            for index, node in enumerate(nodes)
        ],
        "edges": edge_records,
        "dynamic_edges": dynamic_edge_records,
        "communities": communities,
        "deep_graph_model": _deep_graph_model_summary(config, deep_result),
        "model_governance": _discover_encoder_governance(config.encoder),
    }
    return result

def _discover_attention_mode(encoder: str) -> str:
    if encoder == "lightweight":
        return "lightweight"
    if encoder == "han_relation":
        return "relation_semantic_attention"
    if encoder == "han":
        return "metapath_hierarchical_attention"
    if encoder == "magnn_legacy":
        return "metapath_instance_attention_legacy_gated"
    if encoder == "magnn":
        return "metapath_instance_attention"
    if encoder == "amdn_hage":
        return "temporal_hidden_group_estimation"
    return encoder

def _discover_encoder_governance(encoder: str) -> dict[str, object]:
    if encoder in DEPRECATED_DISCOVER_ENCODERS:
        return {
            "encoder": encoder,
            "status": "deprecated_non_claimable",
            "reason": DEPRECATED_DISCOVER_ENCODERS[encoder],
            "stable_default_encoder": STABLE_DISCOVER_ENCODER,
            "activation_policy": "historical_replay_only",
        }
    return {
        "encoder": encoder,
        "status": "stable_default" if encoder == STABLE_DISCOVER_ENCODER else "experimental_comparison",
        "reason": "iohunter_reconstruction_gate_passed_baseline" if encoder == STABLE_DISCOVER_ENCODER else "explicit_non_default_encoder",
        "stable_default_encoder": STABLE_DISCOVER_ENCODER,
        "activation_policy": "claimable_only_after_reconstruction_and_detect_gates",
    }

def _deep_graph_model_summary(
    config: DeepGraphDiscoverConfig,
    result: DeepGraphDiscoverResult | None,
) -> dict[str, object]:
    if result is None:
        return {
            "encoder": config.encoder,
            "training_loss": [],
            "reconstruction_metrics": {},
            "device": config.device,
            "epochs": int(config.epochs),
            "embedding_dim": int(config.embedding_dim),
            "uses_labels": False,
            "observed_edge_scores": {},
        }
    return {
        "encoder": result.encoder,
        "training_loss": result.training_loss,
        "reconstruction_metrics": result.reconstruction_metrics,
        "device": result.device,
        "epochs": int(config.epochs),
        "embedding_dim": int(config.embedding_dim),
        "uses_labels": result.uses_labels,
        "metapath_attention": result.metapath_attention,
        "intra_metapath_attention": result.intra_metapath_attention,
        "intra_metapath_attention_summary": {
            key: value
            for key, value in result.reconstruction_metrics.items()
            if key in {"attention_mechanism", "mean_target_attention_entropy", "max_instance_attention"}
        },
        "metapath_instance_counts": result.metapath_instance_counts,
        "object_node_count": result.object_node_count,
        "edge_score_source": result.edge_score_source,
        "observed_edge_scores": _serialize_observed_edge_scores(result.edge_scores),
        "hidden_group_count": len(set(result.hidden_groups.values())) if result.hidden_groups else 0,
        "temporal_nll": result.temporal_nll,
    }

def _edge_records_from_graph(graph: nx.Graph, node_score_map: Mapping[str, float]) -> list[dict[str, object]]:
    edge_records = []
    for source, target, attrs in graph.edges(data=True):
        edge_weight = float(attrs.get("weight", 1.0))
        learned_score = attrs.get("edge_score")
        edge_score = (
            float(learned_score)
            if learned_score is not None and float(learned_score) > 0.0
            else _sigmoid(math.log1p(edge_weight) + 0.5 * (float(node_score_map[source]) + float(node_score_map[target])))
        )
        edge_records.append(
            {
                "source": source,
                "target": target,
                "edge_score": round(edge_score, 6),
                "weight": edge_weight,
                "relations": attrs.get("relations", []),
            }
        )
    return sorted(edge_records, key=lambda item: (-float(item["edge_score"]), item["source"], item["target"]))[:100]

def _dynamic_edge_records_from_graph(graph: nx.DiGraph, node_score_map: Mapping[str, float]) -> list[dict[str, object]]:
    dynamic_edge_records = []
    for source, target, attrs in graph.edges(data=True):
        deltas = [float(delta) for delta in attrs.get("time_deltas", [])]
        edge_weight = float(attrs.get("weight", 1.0))
        # Target-only accounts can appear in directed retweet/reply/mention edges
        # even when they were not observed as event authors in the Discover graph.
        source_score = float(node_score_map.get(source, 0.0))
        target_score = float(node_score_map.get(target, 0.0))
        edge_score = _sigmoid(math.log1p(edge_weight) + 0.5 * (source_score + target_score))
        dynamic_edge_records.append(
            {
                "source": source,
                "target": target,
                "edge_score": round(edge_score, 6),
                "weight": round(edge_weight, 6),
                "count": int(attrs.get("count", 1)),
                "relations": attrs.get("relations", []),
                "objects": attrs.get("objects", [])[:10],
                "avg_time_delta": round(float(np.mean(deltas)), 6) if deltas else None,
            }
        )
    return sorted(
        dynamic_edge_records,
        key=lambda item: (-float(item["edge_score"]), item["source"], item["target"]),
    )[:100]

def run_dyna_colm_gnn_prototype(
    events: pd.DataFrame,
    *,
    relations: Sequence[str] = DEFAULT_RELATIONS,
    seed: int = 42,
    variant: str = "full",
    use_lm_features: bool = True,
    use_gnn_message_passing: bool = True,
    use_direction_time_features: bool = True,
    use_relation_attention: bool = True,
    relation_attention_mode: str = "learned",
    use_community_features: bool = True,
) -> dict[str, object]:
    labels = extract_labels(events)
    graphs = build_unmasking_similarity_graphs(events, relations=relations, include_text_similarity=False)
    fused = fuse_similarity_graphs(graphs)
    dynamic_relation_graphs = build_dynamic_relation_graphs(events, relations=relations)
    dynamic_fused = fuse_directed_graphs(dynamic_relation_graphs)
    nodes = sorted(set(events["account_id"].astype(str)).union(set(map(str, fused.nodes))))
    for node in nodes:
        fused.add_node(node)
        dynamic_fused.add_node(node)
        for graph in graphs.values():
            graph.add_node(node)
    centrality_features = _centrality_feature_matrix(fused, nodes)
    relation_features, relation_scores = _relation_degree_features(graphs, nodes)
    if relation_attention_mode == "static":
        active_relations = [relation for relation, graph in graphs.items() if graph.number_of_edges() > 0]
        static_weight = _safe_divide(1.0, len(active_relations))
        attention = {relation: static_weight for relation in active_relations}
    elif not use_relation_attention:
        attention = {relation: 1.0 for relation in graphs}
    else:
        attention = _relation_attention(relation_scores, relation_features, labels, nodes)
    if not use_relation_attention and relation_attention_mode != "static":
        total_attention = float(sum(attention.values())) or 1.0
        attention = {relation: value / total_attention for relation, value in attention.items()}
    preliminary_scores = _normalize_vector(
        centrality_features[:, 0] + centrality_features[:, 1] + relation_features.sum(axis=1)
    )
    preliminary_score_map = {node: float(preliminary_scores[index]) for index, node in enumerate(nodes)}
    communities = (
        [set(map(str, community)) for community in greedy_modularity_communities(fused, weight="weight")]
        if fused.number_of_edges()
        else [{node} for node in nodes]
    )
    cluster_by_node: dict[str, int] = {}
    community_feature_by_node: dict[str, tuple[float, float, float, float]] = {}
    for cluster_id, community in enumerate(communities):
        for node in community:
            cluster_by_node[node] = cluster_id
        subgraph = fused.subgraph(community)
        evidence = _community_evidence(events, community)
        density = float(nx.density(subgraph)) if len(community) > 1 else 0.0
        mean_preliminary_score = float(np.mean([preliminary_score_map[node] for node in community]))
        for node in community:
            community_feature_by_node[node] = (
                float(len(community)),
                density,
                float(evidence["object_concentration"]),
                mean_preliminary_score,
            )
    feature_blocks = [centrality_features, relation_features]
    if use_direction_time_features:
        feature_blocks.append(_directed_feature_matrix(dynamic_fused, nodes))
    if use_lm_features:
        lm_features = np.concatenate(
            [
                _bag_feature_matrix(_user_content(events), nodes, max_features=64),
                _bag_feature_matrix(_metadata_text(events), nodes, max_features=64),
            ],
            axis=1,
        )
        if lm_features.shape[1] > 16:
            _, _, vt = np.linalg.svd(lm_features, full_matrices=False)
            lm_features = lm_features @ vt[:16].T
        feature_blocks.append(lm_features)
    if use_community_features:
        community_features = np.asarray(
            [community_feature_by_node.get(node, (1.0, 0.0, 0.0, 0.0)) for node in nodes],
            dtype=float,
        )
        for column in range(community_features.shape[1]):
            community_features[:, column] = _normalize_vector(community_features[:, column])
        feature_blocks.append(community_features)
    features = np.concatenate(feature_blocks, axis=1)
    embedding = _message_pass(graphs, nodes, features, attention) if use_gnn_message_passing else features
    if labels and len(set(labels.values())) >= 2:
        y = np.asarray([int(labels.get(node, 0)) for node in nodes], dtype=int)
        test_indices, scores, backend = _fit_classifier_scores(embedding, y, seed=seed)
        node_scores = np.zeros(len(nodes), dtype=float)
        if test_indices.size:
            node_scores[test_indices] = scores
        degree_scores = _normalize_vector(np.asarray([fused.degree(node, weight="weight") for node in nodes], dtype=float))
        node_scores = np.where(node_scores > 0.0, node_scores, degree_scores)
        metrics = binary_metrics(y[test_indices], scores) if test_indices.size else None
    else:
        backend = "unsupervised_degree_pagerank"
        metrics = None
        node_scores = preliminary_scores
    node_score_map = {node: float(node_scores[index]) for index, node in enumerate(nodes)}
    community_records = []
    for cluster_id, community in enumerate(communities):
        subgraph = fused.subgraph(community)
        evidence = _community_evidence(events, community)
        community_records.append(
            {
                "cluster_id": cluster_id,
                "size": len(community),
                "community_score": round(float(np.mean([node_score_map[node] for node in community])), 6),
                "density": round(float(nx.density(subgraph)), 6) if len(community) > 1 else 0.0,
                "top_nodes": sorted(community, key=lambda node: (-node_score_map[node], node))[:10],
                "top_objects": evidence["top_objects"],
                "object_concentration": evidence["object_concentration"],
                "relation_breakdown": evidence["relation_breakdown"],
            }
        )
    edge_records = []
    for source, target, attrs in fused.edges(data=True):
        edge_weight = float(attrs.get("weight", 1.0))
        edge_score = _sigmoid(
            math.log1p(edge_weight)
            + 0.5 * (node_score_map.get(source, 0.0) + node_score_map.get(target, 0.0))
        )
        edge_records.append(
            {
                "source": source,
                "target": target,
                "edge_score": round(edge_score, 6),
                "weight": edge_weight,
                "relations": attrs.get("relations", []),
            }
        )
    dynamic_edge_records = []
    for source, target, attrs in dynamic_fused.edges(data=True):
        deltas = [float(delta) for delta in attrs.get("time_deltas", [])]
        edge_weight = float(attrs.get("weight", 1.0))
        edge_score = _sigmoid(
            math.log1p(edge_weight)
            + 0.5 * (node_score_map.get(source, 0.0) + node_score_map.get(target, 0.0))
        )
        dynamic_edge_records.append(
            {
                "source": source,
                "target": target,
                "edge_score": round(edge_score, 6),
                "weight": round(edge_weight, 6),
                "count": int(attrs.get("count", 1)),
                "relations": attrs.get("relations", []),
                "objects": attrs.get("objects", [])[:10],
                "avg_time_delta": round(float(np.mean(deltas)), 6) if deltas else None,
            }
        )
    return {
        "method": "dyna_colm_gnn_prototype",
        "variant": variant,
        "task": "coordination_community_discovery_then_discrimination",
        "uses_lm_features": use_lm_features,
        "uses_gnn_message_passing": use_gnn_message_passing,
        "uses_direction_time_features": use_direction_time_features,
        "uses_relation_attention": use_relation_attention,
        "relation_attention_mode": relation_attention_mode,
        "uses_community_features": use_community_features,
        "graph_summary": graph_summary(fused, labels),
        "dynamic_graph_summary": dynamic_graph_summary(dynamic_fused),
        "relation_attention": {key: round(value, 6) for key, value in attention.items()},
        "classifier_backend": backend,
        "metrics": _metric_to_dict(metrics),
        "nodes": [
            {
                "account_id": node,
                "node_score": round(node_score_map[node], 6),
                "cluster_id": cluster_by_node.get(node),
                "directed_out_weight": round(float(dynamic_fused.out_degree(node, weight="weight")), 6),
                "directed_in_weight": round(float(dynamic_fused.in_degree(node, weight="weight")), 6),
            }
            for node in nodes
        ],
        "edges": sorted(edge_records, key=lambda item: (-float(item["edge_score"]), item["source"], item["target"]))[:100],
        "dynamic_edges": sorted(
            dynamic_edge_records,
            key=lambda item: (-float(item["edge_score"]), item["source"], item["target"]),
        )[:100],
        "communities": sorted(community_records, key=lambda item: (-float(item["community_score"]), item["cluster_id"])),
    }

def run_dyna_colm_gnn_ablations(
    events: pd.DataFrame,
    *,
    relations: Sequence[str] = DEFAULT_RELATIONS,
    seed: int = 42,
) -> dict[str, dict[str, object]]:
    """Run the first-version DynaCoLM-GNN ablations used in CoordinationDiscover comparison tables."""
    variants = {
        "full": {
            "use_lm_features": True,
            "use_gnn_message_passing": True,
            "use_direction_time_features": True,
        },
        "without_lm": {
            "use_lm_features": False,
            "use_gnn_message_passing": True,
            "use_direction_time_features": True,
        },
        "without_gnn": {
            "use_lm_features": True,
            "use_gnn_message_passing": False,
            "use_direction_time_features": True,
        },
        "without_direction_time": {
            "use_lm_features": True,
            "use_gnn_message_passing": True,
            "use_direction_time_features": False,
        },
        "without_relation_attention": {
            "use_lm_features": True,
            "use_gnn_message_passing": True,
            "use_direction_time_features": True,
            "use_relation_attention": False,
        },
        "static_relation_weight": {
            "use_lm_features": True,
            "use_gnn_message_passing": True,
            "use_direction_time_features": True,
            "relation_attention_mode": "static",
        },
        "no_community_features": {
            "use_lm_features": True,
            "use_gnn_message_passing": True,
            "use_direction_time_features": True,
            "use_community_features": False,
        },
    }
    return {
        name: run_dyna_colm_gnn_prototype(
            events,
            relations=relations,
            seed=seed,
            variant=name,
            **options,
        )
        for name, options in variants.items()
    }

def _community_avg_time_delta(dynamic_edges: Sequence[Mapping[str, object]], community_nodes: set[str]) -> float | None:
    values = [
        float(edge["avg_time_delta"])
        for edge in dynamic_edges
        if edge.get("avg_time_delta") is not None
        and str(edge.get("source")) in community_nodes
        and str(edge.get("target")) in community_nodes
    ]
    if not values:
        return None
    return round(float(np.mean(values)), 6)

def _discovery_metrics(result: Mapping[str, object]) -> dict[str, object]:
    graph = result.get("graph_summary") if isinstance(result.get("graph_summary"), Mapping) else {}
    dynamic_graph = result.get("dynamic_graph_summary") if isinstance(result.get("dynamic_graph_summary"), Mapping) else {}
    communities = result.get("communities") if isinstance(result.get("communities"), Sequence) else []
    structure_filter = result.get("structure_filter") if isinstance(result.get("structure_filter"), Mapping) else {}
    object_concentration = [
        float(community.get("object_concentration", 0.0))
        for community in communities
        if isinstance(community, Mapping)
    ]
    relation_counts: Counter[str] = Counter()
    for community in communities:
        if not isinstance(community, Mapping):
            continue
        breakdown = community.get("relation_breakdown")
        if isinstance(breakdown, Mapping):
            relation_counts.update({str(key): int(value) for key, value in breakdown.items()})
    deep_model = result.get("deep_graph_model") if isinstance(result.get("deep_graph_model"), Mapping) else {}
    reconstruction = deep_model.get("reconstruction_metrics") if isinstance(deep_model.get("reconstruction_metrics"), Mapping) else {}
    return {
        "modularity": graph.get("modularity"),
        "density": graph.get("density"),
        "conductance": graph.get("conductance"),
        "cluster_count": graph.get("cluster_count", len(communities)),
        "largest_cluster_size": graph.get("largest_cluster_size"),
        "dynamic_edge_count": dynamic_graph.get("edge_count"),
        "mean_object_concentration": round(float(np.mean(object_concentration)), 6) if object_concentration else 0.0,
        "max_object_concentration": round(float(np.max(object_concentration)), 6) if object_concentration else 0.0,
        "relation_entropy": _counter_entropy(relation_counts),
        "structure_filter_removed_fraction": structure_filter.get("removed_node_fraction"),
        "structure_filter_selected_fraction": structure_filter.get("selected_node_fraction"),
        "reconstruction_auc": reconstruction.get("auc"),
        "reconstruction_ap": reconstruction.get("average_precision"),
        "final_training_loss": _final_training_loss(deep_model),
    }

def _final_training_loss(deep_model: Mapping[str, object]) -> float | None:
    losses = deep_model.get("training_loss")
    if isinstance(losses, Sequence) and losses:
        return float(losses[-1])
    return None

def _counter_entropy(counter: Counter[str]) -> float:
    total = sum(counter.values())
    if total <= 0:
        return 0.0
    entropy = 0.0
    for value in counter.values():
        probability = value / total
        if probability > 0:
            entropy -= probability * math.log(probability, 2)
    return round(float(entropy), 6)

def _evidence_summary(result: Mapping[str, object], top_k: int = 10) -> dict[str, object]:
    relation_counts: Counter[str] = Counter()
    top_objects: Counter[tuple[str, str]] = Counter()
    communities = result.get("communities") if isinstance(result.get("communities"), Sequence) else []
    for community in communities:
        if not isinstance(community, Mapping):
            continue
        breakdown = community.get("relation_breakdown")
        if isinstance(breakdown, Mapping):
            relation_counts.update({str(key): int(value) for key, value in breakdown.items()})
        for item in community.get("top_objects", []):
            if isinstance(item, Mapping):
                top_objects[(str(item.get("relation", "") or ""), str(item.get("object_id")))] += int(item.get("count", 0))
    return {
        "top_objects": [
            {"relation": relation, "object_id": object_id, "count": count}
            for (relation, object_id), count in top_objects.most_common(top_k)
        ],
        "relation_breakdown": dict(relation_counts),
        "top_edges": result.get("edges", [])[:top_k],
        "top_dynamic_edges": result.get("dynamic_edges", [])[:top_k],
        "structure_filter": result.get("structure_filter", {}),
    }

def _prediction_rows(result: Mapping[str, object], labels: Mapping[str, int]) -> list[dict[str, object]]:
    rows = []
    for node in result.get("nodes", []):
        if not isinstance(node, Mapping):
            continue
        score = float(node.get("node_score", 0.0))
        account_id = str(node.get("account_id"))
        rows.append(
            {
                "account_id": account_id,
                "node_score": round(score, 6),
                "predicted_label": int(score >= 0.5),
                "label": int(labels.get(account_id, 0)),
                "cluster_id": node.get("cluster_id"),
                "directed_out_weight": node.get("directed_out_weight"),
                "directed_in_weight": node.get("directed_in_weight"),
            }
        )
    return sorted(rows, key=lambda row: (-float(row["node_score"]), row["account_id"]))

def _discover_node_feature_table(
    discovery: Mapping[str, object],
    labels: Mapping[str, int],
) -> tuple[list[str], np.ndarray, np.ndarray, dict[str, dict[str, object]]]:
    nodes = [str(node.get("account_id")) for node in discovery.get("nodes", []) if isinstance(node, Mapping)]
    node_records = {
        str(node.get("account_id")): dict(node)
        for node in discovery.get("nodes", [])
        if isinstance(node, Mapping)
    }
    community_records = {
        community.get("cluster_id"): community
        for community in discovery.get("communities", [])
        if isinstance(community, Mapping)
    }
    attention = discovery.get("relation_attention", {})
    attention_values = [
        float(attention[key])
        for key in sorted(attention)
    ] if isinstance(attention, Mapping) else []
    graph_metrics = discovery.get("graph_metrics", {}) if isinstance(discovery.get("graph_metrics"), Mapping) else {}
    dynamic_metrics = discovery.get("dynamic_graph_metrics", {}) if isinstance(discovery.get("dynamic_graph_metrics"), Mapping) else {}
    model = discovery.get("deep_graph_model", {}) if isinstance(discovery.get("deep_graph_model"), Mapping) else {}
    metapath_counts = model.get("metapath_instance_counts", {}) if isinstance(model.get("metapath_instance_counts"), Mapping) else {}
    metapath_values = [
        math.log1p(float(metapath_counts[key]))
        for key in sorted(metapath_counts)
    ]
    embedding_dim = 0
    for account_id in nodes:
        values = node_records.get(account_id, {}).get("discover_embedding", [])
        if isinstance(values, Sequence) and not isinstance(values, (str, bytes)):
            embedding_dim = max(embedding_dim, len(values))
    rows: list[list[float]] = []
    for account_id in nodes:
        node = node_records[account_id]
        cluster_id = node.get("cluster_id")
        community = community_records.get(cluster_id, {})
        relation_breakdown = community.get("relation_breakdown", {}) if isinstance(community, Mapping) else {}
        relation_total = float(sum(float(value) for value in relation_breakdown.values())) if isinstance(relation_breakdown, Mapping) else 0.0
        feature_row = [
            float(node.get("node_score", 0.0)),
            float(node.get("deep_node_score", node.get("node_score", 0.0))),
            math.log1p(float(node.get("embedding_norm", 0.0))),
            # Legacy placeholders preserved for Detect feature-shape stability.
            # Since Discover no longer performs structural filtering, these
            # fields stay neutral (score~=1, passed=True) on the full graph.
            float(node.get("structure_filter_score", 0.0)),
            float(bool(node.get("passed_structure_filter", False))),
            math.log1p(float(node.get("directed_out_weight", 0.0))),
            math.log1p(float(node.get("directed_in_weight", 0.0))),
            math.log1p(float(community.get("size", 1.0))) if isinstance(community, Mapping) else 0.0,
            float(community.get("community_score", 0.0)) if isinstance(community, Mapping) else 0.0,
            float(community.get("density", 0.0)) if isinstance(community, Mapping) else 0.0,
            float(community.get("object_concentration", 0.0)) if isinstance(community, Mapping) else 0.0,
            math.log1p(relation_total),
            float(graph_metrics.get("modularity", 0.0) or 0.0),
            float(graph_metrics.get("density", 0.0) or 0.0),
            math.log1p(float(dynamic_metrics.get("edge_count", 0.0) or 0.0)),
            math.log1p(float(model.get("object_node_count", 0.0) or 0.0)),
        ]
        feature_row.extend(attention_values)
        feature_row.extend(metapath_values)
        embedding_values = node.get("discover_embedding", [])
        if embedding_dim:
            if isinstance(embedding_values, Sequence) and not isinstance(embedding_values, (str, bytes)):
                padded_embedding = [float(value) for value in embedding_values[:embedding_dim]]
            else:
                padded_embedding = []
            padded_embedding.extend([0.0] * (embedding_dim - len(padded_embedding)))
            # Full Discover embeddings carry the MAGNN/HAN latent representation;
            # embedding_norm above is kept only as a backward-compatible summary.
            feature_row.extend(padded_embedding)
        rows.append(feature_row)
    if not rows:
        return [], np.empty((0, 0), dtype=float), np.empty(0, dtype=int), node_records
    features = np.asarray(rows, dtype=float)
    for column in range(features.shape[1]):
        features[:, column] = _normalize_vector(features[:, column])
    y = np.asarray([int(labels.get(node, 0)) for node in nodes], dtype=int)
    return nodes, features, y, node_records

def _discover_embedding_dim(discovery: Mapping[str, object]) -> int:
    for node in discovery.get("nodes", []):
        if not isinstance(node, Mapping):
            continue
        embedding = node.get("discover_embedding")
        if isinstance(embedding, Sequence) and not isinstance(embedding, (str, bytes)):
            return len(embedding)
    return 0

def _discover_edge_score_lookup(discovery: Mapping[str, object]) -> dict[tuple[str, str], float]:
    model = discovery.get("deep_graph_model", {}) if isinstance(discovery.get("deep_graph_model"), Mapping) else {}
    raw_scores = model.get("observed_edge_scores", {}) if isinstance(model.get("observed_edge_scores"), Mapping) else {}
    lookup: dict[tuple[str, str], float] = {}
    for key, value in raw_scores.items():
        try:
            score = float(value)
        except (TypeError, ValueError):
            continue
        if score <= 0.0:
            continue
        if isinstance(key, str) and "\t" in key:
            left, right = key.split("\t", 1)
        elif isinstance(key, str) and "|" in key:
            left, right = key.split("|", 1)
        elif isinstance(key, Sequence) and not isinstance(key, (str, bytes)) and len(key) == 2:
            left, right = str(key[0]), str(key[1])
        else:
            continue
        lookup[tuple(sorted((str(left), str(right))))] = score
    if lookup:
        return lookup
    # Backward compatibility: older cached discoveries only wrote top-K edge records.
    for edge in discovery.get("edges", []):
        if not isinstance(edge, Mapping):
            continue
        source = edge.get("source")
        target = edge.get("target")
        if source is None or target is None:
            continue
        try:
            score = float(edge.get("edge_score", 0.0))
        except (TypeError, ValueError):
            continue
        if score > 0.0:
            lookup[tuple(sorted((str(source), str(target))))] = score
    return lookup

__all__ = [
    "run_dyna_colm_gnn_ablations",
    "run_dyna_colm_gnn_prototype",
]
