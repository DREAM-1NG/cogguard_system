"""Focused detect models implementation."""

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


def _fit_transductive_scores(features: np.ndarray, y: np.ndarray, *, seed: int = 42) -> tuple[np.ndarray, str]:
    return _fit_transductive_scores_with_split(features, y, seed=seed)

def _fit_transductive_scores_with_split(
    features: np.ndarray,
    y: np.ndarray,
    *,
    seed: int = 42,
    split: Split | None = None,
) -> tuple[np.ndarray, str]:
    if y.size == 0:
        return np.asarray([], dtype=float), "no_nodes"
    if len(set(y.tolist())) < 2:
        return np.zeros(y.size, dtype=float), "single_class"
    split = split or _make_split(y, seed=seed)
    scores = np.zeros(y.size, dtype=float)
    if split.test.size:
        try:
            from sklearn.ensemble import RandomForestClassifier

            classifier = RandomForestClassifier(n_estimators=200, random_state=seed, class_weight="balanced")
            classifier.fit(features[split.train], y[split.train])
            scores[split.test] = classifier.predict_proba(features[split.test])[:, 1]
            backend = "discover_features_random_forest"
        except Exception:
            scores[split.test] = _fit_numpy_logistic(features[split.train], y[split.train], features[split.test])
            backend = "discover_features_numpy_logistic"
    else:
        backend = "discover_features_no_test_split"
    if split.train.size:
        scores[split.train] = _fit_numpy_logistic(features[split.train], y[split.train], features[split.train])
    fallback = _normalize_vector(features[:, 0]) if features.shape[1] else np.zeros(y.size, dtype=float)
    scores = np.where(scores > 0.0, scores, fallback)
    return scores, backend

def _split_detect_feature_groups(
    features: np.ndarray,
    *,
    discover_feature_count: int,
    lm_feature_count: int,
) -> tuple[np.ndarray, np.ndarray]:
    node_count = int(features.shape[0]) if features.ndim == 2 else 0
    feature_width = int(features.shape[1]) if features.ndim == 2 else 0
    discover_stop = max(0, min(int(discover_feature_count), feature_width))
    lm_start = discover_stop
    lm_stop = max(lm_start, min(lm_start + max(0, int(lm_feature_count)), feature_width))
    struct_features = features[:, :discover_stop] if discover_stop > 0 else np.zeros((node_count, 1), dtype=float)
    lm_features = features[:, lm_start:lm_stop] if lm_stop > lm_start else np.zeros((node_count, 1), dtype=float)
    return np.asarray(struct_features, dtype=float), np.asarray(lm_features, dtype=float)

def _build_relation_adjacency_tensors(torch, graphs: Mapping[str, nx.Graph], nodes: Sequence[str], target_device: str):
    node_index = {node: index for index, node in enumerate(nodes)}
    relation_names = [relation for relation, graph in graphs.items() if graph.number_of_edges() > 0] or list(graphs) or ["empty_relation"]

    def adjacency_for(graph: nx.Graph):
        rows: list[int] = []
        cols: list[int] = []
        vals: list[float] = []
        for source, target, attrs in graph.edges(data=True):
            if source not in node_index or target not in node_index:
                continue
            left = node_index[str(source)]
            right = node_index[str(target)]
            weight = max(float(attrs.get("weight", 1.0)), 1e-6)
            rows.extend((left, right))
            cols.extend((right, left))
            vals.extend((weight, weight))
        for idx in range(len(nodes)):
            rows.append(idx)
            cols.append(idx)
            vals.append(1.0)
        row_array = np.asarray(rows, dtype=np.int64)
        col_array = np.asarray(cols, dtype=np.int64)
        val_array = np.asarray(vals, dtype=np.float32)
        degree = np.bincount(row_array, weights=val_array, minlength=len(nodes)).astype(np.float32)
        degree[degree <= 0.0] = 1.0
        val_array = val_array / degree[row_array]
        indices = torch.as_tensor(np.vstack([row_array, col_array]), dtype=torch.long, device=target_device)
        values = torch.as_tensor(val_array, dtype=torch.float32, device=target_device)
        return torch.sparse_coo_tensor(indices, values, (len(nodes), len(nodes)), device=target_device).coalesce()

    adjacency_tensors = [adjacency_for(graphs.get(relation, nx.Graph())) for relation in relation_names]
    return relation_names, adjacency_tensors

def _sample_relation_edge_pairs(
    graphs: Mapping[str, nx.Graph],
    nodes: Sequence[str],
    relation_names: Sequence[str],
    *,
    seed: int = 42,
    max_positive: int = 4096,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Sample observed and unobserved user pairs for Detect graph-reconstruction loss."""
    node_index = {str(node): index for index, node in enumerate(nodes)}
    relation_index = {relation: index for index, relation in enumerate(relation_names)}
    positives: list[tuple[int, int, int, float]] = []
    connected: set[tuple[int, int]] = set()
    for relation in relation_names:
        graph = graphs.get(relation)
        if graph is None:
            continue
        rel_idx = relation_index.get(relation, 0)
        for source, target, attrs in graph.edges(data=True):
            if str(source) not in node_index or str(target) not in node_index:
                continue
            left = node_index[str(source)]
            right = node_index[str(target)]
            if left == right:
                continue
            pair = tuple(sorted((left, right)))
            connected.add(pair)
            weight = max(float(attrs.get("weight", 1.0)), 1e-6)
            positives.append((left, right, rel_idx, min(math.log1p(weight) + 1.0, 5.0)))
    if not positives or len(nodes) < 2:
        return (
            np.empty((0, 2), dtype=np.int64),
            np.empty(0, dtype=np.int64),
            np.empty(0, dtype=np.float32),
            np.empty(0, dtype=np.float32),
        )
    rng = np.random.default_rng(seed)
    if len(positives) > max_positive:
        keep = rng.choice(len(positives), size=max_positive, replace=False)
        positives = [positives[int(index)] for index in keep]
    negatives: set[tuple[int, int]] = set()
    attempts = 0
    target_negative_count = len(positives)
    while len(negatives) < target_negative_count and attempts < target_negative_count * 50:
        attempts += 1
        left = int(rng.integers(0, len(nodes)))
        right = int(rng.integers(0, len(nodes)))
        if left == right:
            continue
        pair = tuple(sorted((left, right)))
        if pair in connected or pair in negatives:
            continue
        negatives.add(pair)
    if len(negatives) < target_negative_count:
        for left in range(len(nodes)):
            for right in range(left + 1, len(nodes)):
                pair = (left, right)
                if pair in connected or pair in negatives:
                    continue
                negatives.add(pair)
                if len(negatives) >= target_negative_count:
                    break
            if len(negatives) >= target_negative_count:
                break
    relation_count = max(len(relation_names), 1)
    pairs: list[tuple[int, int]] = []
    relations: list[int] = []
    labels: list[float] = []
    weights: list[float] = []
    for left, right, rel_idx, weight in positives:
        pairs.append((left, right))
        relations.append(rel_idx)
        labels.append(1.0)
        weights.append(weight)
    for left, right in sorted(negatives):
        pairs.append((left, right))
        relations.append(int(rng.integers(0, relation_count)))
        labels.append(0.0)
        weights.append(1.0)
    return (
        np.asarray(pairs, dtype=np.int64),
        np.asarray(relations, dtype=np.int64),
        np.asarray(labels, dtype=np.float32),
        np.asarray(weights, dtype=np.float32),
    )

def _torch_relation_gnn_scores(
    features: np.ndarray,
    y: np.ndarray,
    graphs: Mapping[str, nx.Graph],
    nodes: Sequence[str],
    *,
    seed: int = 42,
    epochs: int = 120,
    hidden_dim: int = 32,
    lr: float = 1e-3,
    device: str = "auto",
    split: Split | None = None,
) -> tuple[np.ndarray, str, dict[str, object]]:
    if y.size == 0 or len(set(y.tolist())) < 2:
        return np.zeros(y.size, dtype=float), "relation_gnn_single_class", {}
    try:
        import torch
        import torch.nn as nn
        import torch.nn.functional as functional
    except Exception:
        scores, backend = _fit_transductive_scores(features, y, seed=seed)
        return scores, f"{backend}_fallback_no_torch", {}

    split = split or _make_split(y, seed=seed)
    if split.test.size == 0 or split.train.size == 0:
        return np.zeros(y.size, dtype=float), "relation_gnn_no_test_split", {}
    if len(set(y[split.train].tolist())) < 2:
        scores, backend = _fit_transductive_scores(features, y, seed=seed)
        return scores, f"{backend}_fallback_single_train_class", {}

    torch.manual_seed(seed)
    target_device = "cuda" if device == "auto" and torch.cuda.is_available() else ("cpu" if device == "auto" else device)
    if target_device == "cuda" and not torch.cuda.is_available():
        target_device = "cpu"

    relation_names, adjacency_tensors = _build_relation_adjacency_tensors(torch, graphs, nodes, target_device)
    x = torch.as_tensor(features, dtype=torch.float32, device=target_device)
    labels = torch.as_tensor(y.astype(np.float32), dtype=torch.float32, device=target_device)
    train_index = torch.as_tensor(split.train, dtype=torch.long, device=target_device)

    class RelationGNN(nn.Module):
        def __init__(self, input_dim: int, hidden: int, relation_count: int):
            super().__init__()
            self.input_projection = nn.Linear(input_dim, hidden)
            self.relation_linears = nn.ModuleList([nn.Linear(hidden, hidden) for _ in range(relation_count)])
            self.semantic_context = nn.Parameter(torch.empty(hidden))
            nn.init.xavier_uniform_(self.semantic_context.view(1, -1))
            self.output = nn.Linear(hidden, 1)

        def forward(self, feature_tensor):
            base = functional.relu(self.input_projection(feature_tensor))
            relation_outputs = []
            for relation_index, adjacency in enumerate(adjacency_tensors):
                aggregated = torch.sparse.mm(adjacency, base)
                relation_outputs.append(functional.relu(self.relation_linears[relation_index](aggregated)))
            stacked = torch.stack(relation_outputs, dim=1)
            semantic_scores = (torch.tanh(stacked) * self.semantic_context.view(1, 1, -1)).sum(dim=2).mean(dim=0)
            attention = torch.softmax(semantic_scores, dim=0)
            combined = (stacked * attention.view(1, -1, 1)).sum(dim=1)
            return self.output(combined).squeeze(1), attention

    model = RelationGNN(features.shape[1], max(2, int(hidden_dim)), len(relation_names)).to(target_device)
    optimizer = torch.optim.Adam(model.parameters(), lr=lr, weight_decay=1e-4)
    positives = max(float(np.sum(y[split.train] == 1)), 1.0)
    negatives = max(float(np.sum(y[split.train] == 0)), 1.0)
    pos_weight = torch.as_tensor([negatives / positives], dtype=torch.float32, device=target_device)
    for _ in range(max(1, int(epochs))):
        model.train()
        optimizer.zero_grad()
        logits, _ = model(x)
        loss = functional.binary_cross_entropy_with_logits(logits[train_index], labels[train_index], pos_weight=pos_weight)
        loss.backward()
        optimizer.step()

    model.eval()
    with torch.no_grad():
        logits, attention = model(x)
        probabilities = torch.sigmoid(logits).detach().cpu().numpy()
        attention_map = {
            relation: round(float(attention[index].detach().cpu().item()), 6)
            for index, relation in enumerate(relation_names)
        }
    scores = np.zeros(y.size, dtype=float)
    scores[split.test] = probabilities[split.test]
    details = {
        "fusion_architecture": "single_graph_branch",
        "relation_attention": attention_map,
        "branch_attention": {"graph": 1.0},
    }
    return scores, f"relation_gnn_torch:{json.dumps(attention_map, sort_keys=True)}", details

def _torch_fusion_gnn_scores(
    features: np.ndarray,
    y: np.ndarray,
    graphs: Mapping[str, nx.Graph],
    nodes: Sequence[str],
    *,
    discover_feature_count: int,
    lm_feature_count: int,
    seed: int = 42,
    epochs: int = 120,
    hidden_dim: int = 32,
    lr: float = 1e-3,
    device: str = "auto",
    split: Split | None = None,
) -> tuple[np.ndarray, str, dict[str, object]]:
    if y.size == 0 or len(set(y.tolist())) < 2:
        return np.zeros(y.size, dtype=float), "fusion_gnn_single_class", {}
    try:
        import torch
        import torch.nn as nn
        import torch.nn.functional as functional
    except Exception:
        scores, backend = _fit_transductive_scores(features, y, seed=seed)
        return scores, f"{backend}_fallback_no_torch", {}

    split = split or _make_split(y, seed=seed)
    if split.test.size == 0 or split.train.size == 0:
        return np.zeros(y.size, dtype=float), "fusion_gnn_no_test_split", {}
    if len(set(y[split.train].tolist())) < 2:
        scores, backend = _fit_transductive_scores(features, y, seed=seed)
        return scores, f"{backend}_fallback_single_train_class", {}

    torch.manual_seed(seed)
    target_device = "cuda" if device == "auto" and torch.cuda.is_available() else ("cpu" if device == "auto" else device)
    if target_device == "cuda" and not torch.cuda.is_available():
        target_device = "cpu"

    relation_names, adjacency_tensors = _build_relation_adjacency_tensors(torch, graphs, nodes, target_device)
    struct_matrix, lm_matrix = _split_detect_feature_groups(
        features,
        discover_feature_count=discover_feature_count,
        lm_feature_count=lm_feature_count,
    )
    x_struct = torch.as_tensor(struct_matrix, dtype=torch.float32, device=target_device)
    x_lm = torch.as_tensor(lm_matrix, dtype=torch.float32, device=target_device)
    labels = torch.as_tensor(y.astype(np.float32), dtype=torch.float32, device=target_device)
    train_index = torch.as_tensor(split.train, dtype=torch.long, device=target_device)

    class FusionGNN(nn.Module):
        def __init__(self, struct_dim: int, lm_dim: int, hidden: int, relation_count: int):
            super().__init__()
            self.struct_projection = nn.Linear(struct_dim, hidden)
            self.lm_projection = nn.Linear(lm_dim, hidden)
            self.struct_query = nn.Linear(hidden, hidden)
            self.struct_key = nn.Linear(hidden, hidden)
            self.lm_query = nn.Linear(hidden, hidden)
            self.lm_key = nn.Linear(hidden, hidden)
            self.graph_seed_projection = nn.Linear(hidden * 2, hidden)
            self.relation_linears = nn.ModuleList([nn.Linear(hidden, hidden) for _ in range(relation_count)])
            self.graph_semantic_context = nn.Parameter(torch.empty(hidden))
            nn.init.xavier_uniform_(self.graph_semantic_context.view(1, -1))
            self.branch_projection = nn.Linear(hidden, hidden)
            self.branch_context = nn.Parameter(torch.empty(hidden))
            nn.init.xavier_uniform_(self.branch_context.view(1, -1))
            self.output_hidden = nn.Linear(hidden, hidden)
            self.output = nn.Linear(hidden, 1)
            self.dropout = nn.Dropout(0.1)

        def forward(self, struct_x, lm_x):
            struct_base = functional.relu(self.struct_projection(struct_x))
            lm_base = functional.relu(self.lm_projection(lm_x))
            scale = math.sqrt(max(struct_base.shape[1], 1))
            struct_to_lm = torch.sigmoid(
                (self.struct_query(struct_base) * self.lm_key(lm_base)).sum(dim=1, keepdim=True) / scale
            )
            lm_to_struct = torch.sigmoid(
                (self.lm_query(lm_base) * self.struct_key(struct_base)).sum(dim=1, keepdim=True) / scale
            )
            struct_hidden = struct_base + struct_to_lm * lm_base
            lm_hidden = lm_base + lm_to_struct * struct_base
            graph_seed = functional.relu(self.graph_seed_projection(torch.cat([struct_hidden, lm_hidden], dim=1)))
            relation_outputs = []
            for relation_index, adjacency in enumerate(adjacency_tensors):
                aggregated = torch.sparse.mm(adjacency, graph_seed)
                relation_outputs.append(functional.relu(self.relation_linears[relation_index](aggregated)))
            stacked = torch.stack(relation_outputs, dim=1)
            graph_semantic_hidden = torch.tanh(stacked)
            graph_semantic_scores = (
                graph_semantic_hidden * self.graph_semantic_context.view(1, 1, -1)
            ).sum(dim=2).mean(dim=0)
            relation_attention = torch.softmax(graph_semantic_scores, dim=0)
            graph_hidden = (stacked * relation_attention.view(1, -1, 1)).sum(dim=1)
            branches = torch.stack([struct_hidden, lm_hidden, graph_hidden], dim=1)
            branch_scores = (
                torch.tanh(self.branch_projection(branches)) * self.branch_context.view(1, 1, -1)
            ).sum(dim=2)
            branch_attention = torch.softmax(branch_scores, dim=1)
            fused = (branches * branch_attention.unsqueeze(-1)).sum(dim=1)
            fused = functional.relu(self.output_hidden(self.dropout(fused)))
            logits = self.output(self.dropout(fused)).squeeze(1)
            cross_means = torch.stack([struct_to_lm.mean(), lm_to_struct.mean()])
            return logits, relation_attention, branch_attention.mean(dim=0), cross_means

    model = FusionGNN(
        x_struct.shape[1],
        x_lm.shape[1],
        max(4, int(hidden_dim)),
        len(relation_names),
    ).to(target_device)
    optimizer = torch.optim.Adam(model.parameters(), lr=lr, weight_decay=1e-4)
    positives = max(float(np.sum(y[split.train] == 1)), 1.0)
    negatives = max(float(np.sum(y[split.train] == 0)), 1.0)
    pos_weight = torch.as_tensor([negatives / positives], dtype=torch.float32, device=target_device)
    for _ in range(max(1, int(epochs))):
        model.train()
        optimizer.zero_grad()
        logits, _, _, _ = model(x_struct, x_lm)
        loss = functional.binary_cross_entropy_with_logits(logits[train_index], labels[train_index], pos_weight=pos_weight)
        loss.backward()
        optimizer.step()

    model.eval()
    with torch.no_grad():
        logits, relation_attention, branch_attention, cross_means = model(x_struct, x_lm)
        probabilities = torch.sigmoid(logits).detach().cpu().numpy()
        relation_attention_map = {
            relation: round(float(relation_attention[index].detach().cpu().item()), 6)
            for index, relation in enumerate(relation_names)
        }
        branch_names = ("struct", "lm", "graph")
        branch_attention_map = {
            branch_names[index]: round(float(branch_attention[index].detach().cpu().item()), 6)
            for index in range(len(branch_names))
        }
        cross_attention_mean = {
            "struct_to_lm": round(float(cross_means[0].detach().cpu().item()), 6),
            "lm_to_struct": round(float(cross_means[1].detach().cpu().item()), 6),
        }
    scores = np.zeros(y.size, dtype=float)
    scores[split.test] = probabilities[split.test]
    details = {
        "fusion_architecture": "discover_lm_graph_attention",
        "relation_attention": relation_attention_map,
        "branch_attention": branch_attention_map,
        "cross_attention_mean": cross_attention_mean,
        "feature_group_sizes": {
            "discover": int(discover_feature_count),
            "lm": int(lm_feature_count),
        },
    }
    backend = {
        "relation_attention": relation_attention_map,
        "branch_attention": branch_attention_map,
        "cross_attention_mean": cross_attention_mean,
    }
    return scores, f"fusion_gnn_torch:{json.dumps(backend, sort_keys=True)}", details

def _torch_gfm_lm_gnn_scores(
    features: np.ndarray,
    y: np.ndarray,
    graphs: Mapping[str, nx.Graph],
    nodes: Sequence[str],
    *,
    discover_feature_count: int,
    lm_feature_count: int,
    seed: int = 42,
    epochs: int = 120,
    hidden_dim: int = 32,
    lr: float = 1e-3,
    device: str = "auto",
    split: Split | None = None,
    max_edge_reconstruction_positive: int = 1024,
) -> tuple[np.ndarray, str, dict[str, object]]:
    if y.size == 0 or len(set(y.tolist())) < 2:
        return np.zeros(y.size, dtype=float), "gfm_lm_gnn_single_class", {}
    try:
        import torch
        import torch.nn as nn
        import torch.nn.functional as functional
    except Exception:
        scores, backend = _fit_transductive_scores_with_split(features, y, seed=seed, split=split)
        return scores, f"{backend}_fallback_no_torch", {}

    split = split or _make_split(y, seed=seed)
    if split.test.size == 0 or split.train.size == 0:
        return np.zeros(y.size, dtype=float), "gfm_lm_gnn_no_test_split", {}
    if len(set(y[split.train].tolist())) < 2:
        scores, backend = _fit_transductive_scores_with_split(features, y, seed=seed, split=split)
        return scores, f"{backend}_fallback_single_train_class", {}

    torch.manual_seed(seed)
    target_device = "cuda" if device == "auto" and torch.cuda.is_available() else ("cpu" if device == "auto" else device)
    if target_device == "cuda" and not torch.cuda.is_available():
        target_device = "cpu"

    relation_names, adjacency_tensors = _build_relation_adjacency_tensors(torch, graphs, nodes, target_device)
    edge_pairs, edge_relations, edge_labels, edge_weights = _sample_relation_edge_pairs(
        graphs,
        nodes,
        relation_names,
        seed=seed,
        max_positive=max(1, int(max_edge_reconstruction_positive)),
    )
    struct_matrix, lm_matrix = _split_detect_feature_groups(
        features,
        discover_feature_count=discover_feature_count,
        lm_feature_count=lm_feature_count,
    )
    x_struct = torch.as_tensor(struct_matrix, dtype=torch.float32, device=target_device)
    x_lm = torch.as_tensor(lm_matrix, dtype=torch.float32, device=target_device)
    labels = torch.as_tensor(y.astype(np.float32), dtype=torch.float32, device=target_device)
    train_index = torch.as_tensor(split.train, dtype=torch.long, device=target_device)
    if edge_pairs.size:
        edge_pair_tensor = torch.as_tensor(edge_pairs, dtype=torch.long, device=target_device)
        edge_relation_tensor = torch.as_tensor(edge_relations, dtype=torch.long, device=target_device)
        edge_label_tensor = torch.as_tensor(edge_labels, dtype=torch.float32, device=target_device)
        edge_weight_tensor = torch.as_tensor(edge_weights, dtype=torch.float32, device=target_device)
    else:
        edge_pair_tensor = torch.empty((0, 2), dtype=torch.long, device=target_device)
        edge_relation_tensor = torch.empty(0, dtype=torch.long, device=target_device)
        edge_label_tensor = torch.empty(0, dtype=torch.float32, device=target_device)
        edge_weight_tensor = torch.empty(0, dtype=torch.float32, device=target_device)

    class GFMLMGNN(nn.Module):
        def __init__(self, struct_dim: int, lm_dim: int, hidden: int, relation_count: int):
            super().__init__()
            self.discover_projection = nn.Sequential(nn.Linear(struct_dim, hidden), nn.ReLU(), nn.Dropout(0.1))
            self.lm_projection = nn.Sequential(nn.Linear(lm_dim, hidden), nn.ReLU(), nn.Dropout(0.1))
            self.discover_to_lm = nn.MultiheadAttention(hidden, num_heads=1, batch_first=True)
            self.lm_to_discover = nn.MultiheadAttention(hidden, num_heads=1, batch_first=True)
            self.graph_seed_projection = nn.Linear(hidden * 2, hidden)
            self.relation_linears = nn.ModuleList([nn.Linear(hidden, hidden) for _ in range(relation_count)])
            self.relation_context = nn.Parameter(torch.empty(hidden))
            nn.init.xavier_uniform_(self.relation_context.view(1, -1))
            self.branch_projection = nn.Linear(hidden, hidden)
            self.branch_context = nn.Parameter(torch.empty(hidden))
            nn.init.xavier_uniform_(self.branch_context.view(1, -1))
            self.output_hidden = nn.Linear(hidden, hidden)
            self.output = nn.Linear(hidden, 1)
            self.edge_relation_scale = nn.Embedding(relation_count, hidden)
            self.edge_relation_bias = nn.Embedding(relation_count, 1)
            nn.init.ones_(self.edge_relation_scale.weight)
            nn.init.zeros_(self.edge_relation_bias.weight)
            self.dropout = nn.Dropout(0.1)

        def forward(self, struct_x, lm_x):
            discover_base = self.discover_projection(struct_x)
            lm_base = self.lm_projection(lm_x)
            discover_context, discover_attention = self.discover_to_lm(
                discover_base.unsqueeze(1),
                lm_base.unsqueeze(1),
                lm_base.unsqueeze(1),
                need_weights=True,
            )
            lm_context, lm_attention = self.lm_to_discover(
                lm_base.unsqueeze(1),
                discover_base.unsqueeze(1),
                discover_base.unsqueeze(1),
                need_weights=True,
            )
            discover_hidden = discover_base + discover_context.squeeze(1)
            lm_hidden = lm_base + lm_context.squeeze(1)
            graph_seed = functional.relu(self.graph_seed_projection(torch.cat([discover_hidden, lm_hidden], dim=1)))
            relation_outputs = []
            for relation_index, adjacency in enumerate(adjacency_tensors):
                aggregated = torch.sparse.mm(adjacency, graph_seed)
                relation_outputs.append(functional.relu(self.relation_linears[relation_index](aggregated)))
            stacked = torch.stack(relation_outputs, dim=1)
            relation_scores = (torch.tanh(stacked) * self.relation_context.view(1, 1, -1)).sum(dim=2).mean(dim=0)
            relation_attention = torch.softmax(relation_scores, dim=0)
            graph_hidden = (stacked * relation_attention.view(1, -1, 1)).sum(dim=1)
            branches = torch.stack([discover_hidden, lm_hidden, graph_hidden], dim=1)
            branch_scores = (
                torch.tanh(self.branch_projection(branches)) * self.branch_context.view(1, 1, -1)
            ).sum(dim=2)
            branch_attention = torch.softmax(branch_scores, dim=1)
            fused = (branches * branch_attention.unsqueeze(-1)).sum(dim=1)
            hidden = functional.relu(self.output_hidden(self.dropout(fused)))
            logits = self.output(self.dropout(hidden)).squeeze(1)
            cross_attention_mean = torch.stack([discover_attention.mean(), lm_attention.mean()])
            return logits, fused, discover_hidden, lm_hidden, relation_attention, branch_attention.mean(dim=0), cross_attention_mean

        def edge_logits(self, node_embeddings, pairs, relation_ids):
            if pairs.numel() == 0:
                return torch.empty(0, dtype=node_embeddings.dtype, device=node_embeddings.device)
            left = node_embeddings[pairs[:, 0]]
            right = node_embeddings[pairs[:, 1]]
            relation_scale = self.edge_relation_scale(relation_ids)
            relation_bias = self.edge_relation_bias(relation_ids).squeeze(1)
            score = (left * right * relation_scale).sum(dim=1) / math.sqrt(max(node_embeddings.shape[1], 1))
            return score + relation_bias

    model = GFMLMGNN(
        x_struct.shape[1],
        x_lm.shape[1],
        max(4, int(hidden_dim)),
        len(relation_names),
    ).to(target_device)
    optimizer = torch.optim.Adam(model.parameters(), lr=lr, weight_decay=1e-4)
    positives = max(float(np.sum(y[split.train] == 1)), 1.0)
    negatives = max(float(np.sum(y[split.train] == 0)), 1.0)
    pos_weight = torch.as_tensor([negatives / positives], dtype=torch.float32, device=target_device)
    final_losses = {"classification": 0.0, "edge_reconstruction": 0.0, "discover_lm_alignment": 0.0}
    for _ in range(max(1, int(epochs))):
        model.train()
        optimizer.zero_grad()
        logits, fused, discover_hidden, lm_hidden, _, _, _ = model(x_struct, x_lm)
        classification_loss = functional.binary_cross_entropy_with_logits(
            logits[train_index],
            labels[train_index],
            pos_weight=pos_weight,
        )
        if edge_pair_tensor.numel():
            reconstruction_logits = model.edge_logits(fused, edge_pair_tensor, edge_relation_tensor)
            reconstruction_loss = functional.binary_cross_entropy_with_logits(
                reconstruction_logits,
                edge_label_tensor,
                weight=edge_weight_tensor,
            )
        else:
            reconstruction_loss = logits.sum() * 0.0
        alignment_loss = 1.0 - functional.cosine_similarity(discover_hidden[train_index], lm_hidden[train_index], dim=1).mean()
        loss = classification_loss + 0.15 * reconstruction_loss + 0.05 * alignment_loss
        loss.backward()
        optimizer.step()
        final_losses = {
            "classification": float(classification_loss.detach().cpu().item()),
            "edge_reconstruction": float(reconstruction_loss.detach().cpu().item()),
            "discover_lm_alignment": float(alignment_loss.detach().cpu().item()),
        }

    model.eval()
    with torch.no_grad():
        logits, fused, discover_hidden, lm_hidden, relation_attention, branch_attention, cross_attention_mean = model(x_struct, x_lm)
        probabilities = torch.sigmoid(logits).detach().cpu().numpy()
        relation_attention_map = {
            relation: round(float(relation_attention[index].detach().cpu().item()), 6)
            for index, relation in enumerate(relation_names)
        }
        branch_names = ("discover", "lm", "graph")
        branch_attention_map = {
            branch_names[index]: round(float(branch_attention[index].detach().cpu().item()), 6)
            for index in range(len(branch_names))
        }
        cross_attention_map = {
            "discover_to_lm": round(float(cross_attention_mean[0].detach().cpu().item()), 6),
            "lm_to_discover": round(float(cross_attention_mean[1].detach().cpu().item()), 6),
        }
        if edge_pair_tensor.numel():
            reconstruction_scores = torch.sigmoid(model.edge_logits(fused, edge_pair_tensor, edge_relation_tensor)).detach().cpu().numpy()
            reconstruction_labels = edge_labels.astype(float)
            reconstruction_metrics = _detection_metric_dict(reconstruction_labels.tolist(), reconstruction_scores.tolist())
        else:
            reconstruction_metrics = {}
    scores = np.zeros(y.size, dtype=float)
    scores[split.test] = probabilities[split.test]
    details = {
        "fusion_architecture": "iohunter_style_graph_foundation_lm_gnn",
        "relation_attention": relation_attention_map,
        "branch_attention": branch_attention_map,
        "cross_attention_mean": cross_attention_map,
        "feature_group_sizes": {
            "discover": int(discover_feature_count),
            "lm": int(lm_feature_count),
        },
        "pretraining_objectives": {
            "supervised_node_classification": True,
            "edge_reconstruction_auxiliary": bool(edge_pair_tensor.numel()),
            "discover_lm_alignment_auxiliary": True,
        },
        "auxiliary_loss_weights": {
            "edge_reconstruction": 0.15,
            "discover_lm_alignment": 0.05,
        },
        "final_training_losses": {key: round(value, 6) for key, value in final_losses.items()},
        "edge_reconstruction_metrics": reconstruction_metrics,
        "edge_reconstruction_pair_count": int(edge_pair_tensor.shape[0]),
        "paper_reference_style": "IOHunter/SocGFM supervised-scarce-cross-IO LM+GNN detection",
    }
    backend = {
        "relation_attention": relation_attention_map,
        "branch_attention": branch_attention_map,
        "cross_attention_mean": cross_attention_map,
        "edge_aux": bool(edge_pair_tensor.numel()),
    }
    return scores, f"gfm_lm_gnn_torch:{json.dumps(backend, sort_keys=True)}", details

def _cpu_light_gfm_lm_gnn_scores(
    features: np.ndarray,
    y: np.ndarray,
    graphs: Mapping[str, nx.Graph],
    nodes: Sequence[str],
    *,
    discover_feature_count: int,
    lm_feature_count: int,
    seed: int = 42,
    split: Split | None = None,
) -> tuple[np.ndarray, str, dict[str, object]]:
    if y.size == 0 or len(set(y.tolist())) < 2:
        return np.zeros(y.size, dtype=float), "gfm_lm_gnn_cpu_light_single_class", {}
    split = split or _make_split(y, seed=seed)
    if split.test.size == 0 or split.train.size == 0:
        return np.zeros(y.size, dtype=float), "gfm_lm_gnn_cpu_light_no_test_split", {}
    struct_matrix, lm_matrix = _split_detect_feature_groups(
        features,
        discover_feature_count=discover_feature_count,
        lm_feature_count=lm_feature_count,
    )
    node_index = {str(node): index for index, node in enumerate(nodes)}
    relation_names = [relation for relation, graph in graphs.items() if graph.number_of_edges() > 0] or list(graphs) or ["empty_relation"]
    relation_outputs: list[np.ndarray] = []
    relation_strength: dict[str, float] = {}
    seed_matrix = np.concatenate([struct_matrix, lm_matrix], axis=1)
    for relation in relation_names:
        graph = graphs.get(relation, nx.Graph())
        aggregated = np.zeros_like(seed_matrix, dtype=float)
        degree = np.ones(len(nodes), dtype=float)
        left_indices: list[int] = []
        right_indices: list[int] = []
        weights: list[float] = []
        for source, target, attrs in graph.edges(data=True):
            if str(source) not in node_index or str(target) not in node_index:
                continue
            left = node_index[str(source)]
            right = node_index[str(target)]
            weight = max(float(attrs.get("weight", 1.0)), 1e-6)
            left_indices.append(left)
            right_indices.append(right)
            weights.append(weight)
        if left_indices:
            left_array = np.asarray(left_indices, dtype=np.int64)
            right_array = np.asarray(right_indices, dtype=np.int64)
            weight_array = np.asarray(weights, dtype=float)
            np.add.at(aggregated, left_array, seed_matrix[right_array] * weight_array[:, None])
            np.add.at(aggregated, right_array, seed_matrix[left_array] * weight_array[:, None])
            np.add.at(degree, left_array, weight_array)
            np.add.at(degree, right_array, weight_array)
        aggregated = aggregated / degree[:, None]
        relation_outputs.append(aggregated)
        relation_strength[relation] = float(np.mean(np.linalg.norm(aggregated, axis=1)))
    strengths = np.asarray([relation_strength.get(relation, 0.0) for relation in relation_names], dtype=float)
    if np.all(strengths <= 1e-12):
        relation_attention = np.ones(len(relation_names), dtype=float) / max(len(relation_names), 1)
    else:
        shifted = strengths - float(np.max(strengths))
        exp_values = np.exp(shifted)
        relation_attention = exp_values / float(np.sum(exp_values))
    graph_branch = np.zeros_like(seed_matrix, dtype=float)
    for index, relation_matrix in enumerate(relation_outputs):
        graph_branch += float(relation_attention[index]) * relation_matrix
    fused = np.concatenate([struct_matrix, lm_matrix, graph_branch], axis=1)
    scores = np.zeros(y.size, dtype=float)
    scores[split.test] = _fit_numpy_logistic(
        fused[split.train],
        y[split.train],
        fused[split.test],
        epochs=80,
        learning_rate=0.08,
    )
    backend = "gfm_lm_gnn_cpu_light_numpy_logistic"
    relation_attention_map = {
        relation: round(float(relation_attention[index]), 6)
        for index, relation in enumerate(relation_names)
    }
    details = {
        "fusion_architecture": "iohunter_style_cpu_light_fixed_graph_lm_gnn",
        "relation_attention": relation_attention_map,
        "branch_attention": {"discover": 0.333333, "lm": 0.333333, "graph": 0.333333},
        "feature_group_sizes": {
            "discover": int(discover_feature_count),
            "lm": int(lm_feature_count),
            "graph": int(graph_branch.shape[1]),
        },
        "pretraining_objectives": {
            "supervised_node_classification": True,
            "fixed_relation_graph_propagation": True,
            "edge_reconstruction_auxiliary": False,
            "discover_lm_alignment_auxiliary": False,
        },
        "paper_reference_style": "IOHunter/SocGFM-inspired CPU-light LM+GNN full-matrix smoke",
    }
    return scores, f"gfm_lm_gnn_cpu_light:{backend}:{json.dumps(relation_attention_map, sort_keys=True)}", details

def _prediction_rows_from_discover_features(
    nodes: Sequence[str],
    scores: np.ndarray,
    labels: Mapping[str, int],
    node_records: Mapping[str, Mapping[str, object]],
    split: Split | None = None,
) -> list[dict[str, object]]:
    train_nodes = {nodes[int(index)] for index in split.train.tolist()} if split is not None else set()
    test_nodes = {nodes[int(index)] for index in split.test.tolist()} if split is not None else set()
    rows = []
    for index, account_id in enumerate(nodes):
        node = node_records.get(account_id, {})
        score = float(scores[index]) if index < scores.size else 0.0
        evaluation_split = "test" if account_id in test_nodes else "train" if account_id in train_nodes else "unassigned"
        rows.append(
            {
                "account_id": account_id,
                "node_score": round(score, 6),
                "predicted_label": int(score >= 0.5),
                "label": int(labels.get(account_id, 0)),
                "evaluation_split": evaluation_split,
                "cluster_id": node.get("cluster_id"),
                "passed_structure_filter": bool(node.get("passed_structure_filter", False)),
                "structure_filter_score": node.get("structure_filter_score"),
                "directed_out_weight": node.get("directed_out_weight"),
                "directed_in_weight": node.get("directed_in_weight"),
            }
        )
    return sorted(rows, key=lambda row: (-float(row["node_score"]), row["account_id"]))

def _community_scores(result: Mapping[str, object], predictions: Sequence[Mapping[str, object]]) -> list[dict[str, object]]:
    predictions_by_cluster: dict[object, list[Mapping[str, object]]] = defaultdict(list)
    for row in predictions:
        predictions_by_cluster[row.get("cluster_id")].append(row)
    output = []
    for community in result.get("communities", []):
        if not isinstance(community, Mapping):
            continue
        cluster_id = community.get("cluster_id")
        cluster_predictions = predictions_by_cluster.get(cluster_id, [])
        mean_score = (
            float(np.mean([float(row.get("node_score", 0.0)) for row in cluster_predictions]))
            if cluster_predictions
            else float(community.get("community_score", 0.0))
        )
        output.append(
            {
                "cluster_id": cluster_id,
                "community_score": round(mean_score, 6),
                "size": community.get("size"),
                "positive_prediction_count": int(sum(int(row.get("predicted_label", 0)) for row in cluster_predictions)),
                "top_objects": community.get("top_objects", []),
                "relation_breakdown": community.get("relation_breakdown", {}),
            }
        )
    return sorted(output, key=lambda row: (-float(row["community_score"]), row["cluster_id"]))

def _detect_discovery_snapshot(discovery: Mapping[str, object]) -> dict[str, object]:
    deep_model = (
        dict(discovery.get("deep_graph_model", {}))
        if isinstance(discovery.get("deep_graph_model"), Mapping)
        else {}
    )
    observed_edge_scores = deep_model.pop("observed_edge_scores", {})
    deep_model["observed_edge_score_count"] = (
        len(observed_edge_scores)
        if isinstance(observed_edge_scores, Mapping)
        else 0
    )
    return {
        "metrics": discovery["metrics"],
        "relation_attention": discovery["relation_attention"],
        "evidence_summary": discovery["evidence_summary"],
        "structure_filter": discovery.get("structure_filter", {}),
        # Full edge-score maps remain in cached discovery outputs. Detect keeps a
        # compact snapshot so batch runs do not duplicate multi-MB maps per split.
        "deep_graph_model": deep_model,
    }

def _comparison_rows_for_detect(result: Mapping[str, object]) -> list[dict[str, object]]:
    rows = []
    main_metric = result.get("metrics") if isinstance(result.get("metrics"), Mapping) else None
    _append_metric_row(
        rows,
        family="ours",
        method="dyna_colm_gnn:full",
        metric=main_metric,
        notes="detection",
    )
    ablations = result.get("ablations")
    if isinstance(ablations, Mapping):
        for variant, ablation in ablations.items():
            if isinstance(ablation, Mapping):
                _append_metric_row(
                    rows,
                    family="ours",
                    method=f"dyna_colm_gnn:{variant}",
                    metric=ablation.get("metrics") if isinstance(ablation.get("metrics"), Mapping) else None,
                    notes="ablation",
                )
    return rows

__all__ = [
]
