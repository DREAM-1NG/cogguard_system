"""Focused detect adapter implementation."""

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
    _label_free_events,
    _lm_feature_matrix,
)
from app.core.coordination_baseline.reproduction_deep_discover import (
    _discover_edge_score_lookup,
    _discover_embedding_dim,
    _discover_node_feature_table,
)
from app.core.coordination_baseline.reproduction_discover_runtime import (
    run_dyna_colm_discover,
)

def _apply_discover_edge_scores_to_relation_graphs(
    graphs: Mapping[str, nx.Graph],
    discovery: Mapping[str, object],
) -> tuple[dict[str, nx.Graph], int]:
    edge_scores = _discover_edge_score_lookup(discovery)
    reweighted: dict[str, nx.Graph] = {}
    changed = 0
    for relation, graph in graphs.items():
        relation_graph = graph.copy()
        for source, target, attrs in relation_graph.edges(data=True):
            key = tuple(sorted((str(source), str(target))))
            score = edge_scores.get(key)
            attrs["original_weight"] = float(attrs.get("weight", 1.0))
            if score is None:
                attrs["discover_edge_score"] = None
                continue
            attrs["discover_edge_score"] = float(score)
            attrs["weight"] = attrs["original_weight"] * float(score)
            changed += 1
        reweighted[relation] = relation_graph
    return reweighted, changed

def prepare_dyna_colm_detect_inputs(
    events: pd.DataFrame,
    *,
    relations: Sequence[str] = DEFAULT_RELATIONS,
    seed: int = 42,
    discover_encoder: str = STABLE_DISCOVER_ENCODER,
    discover_epochs: int = 20,
    embedding_dim: int = 32,
    hidden_dim: int = 32,
    device: str = "auto",
    lm_backend: str = "sbert",
    gnn_backend: str = "gfm_lm_gnn",
    precomputed_discovery: Mapping[str, object] | None = None,
    lm_cache_dir: Path | None = None,
) -> PreparedDetectInputs:
    labels = extract_labels(events)
    if not labels or len(set(labels.values())) < 2:
        raise ValueError("DynaCoLM-Detect requires at least two label classes")
    discovery = (
        dict(precomputed_discovery)
        if precomputed_discovery is not None
        else run_dyna_colm_discover(
            events,
            relations=relations,
            seed=seed,
            encoder=discover_encoder,
            epochs=discover_epochs,
            embedding_dim=embedding_dim,
            hidden_dim=hidden_dim,
            device=device,
        )
    )
    nodes, discover_features, y, node_records = _discover_node_feature_table(discovery, labels)
    lm_features, lm_feature_source = _lm_feature_matrix(
        events,
        nodes,
        backend=lm_backend,
        max_dim=max(8, embedding_dim),
        cache_dir=lm_cache_dir,
    )
    discover_feature_count = int(discover_features.shape[1]) if discover_features.ndim == 2 else 0
    lm_feature_count = int(lm_features.shape[1]) if lm_features.ndim == 2 else 0
    discover_embedding_dim = _discover_embedding_dim(discovery)
    features = np.concatenate([discover_features, lm_features], axis=1)
    for column in range(features.shape[1]):
        features[:, column] = _normalize_vector(features[:, column])
    graphs: dict[str, nx.Graph] = {}
    reweighted_edge_count = 0
    uses_discover_reweighted_edges = False
    if gnn_backend in {"relation_gnn", "fusion_gnn", "gfm_lm_gnn", "gfm_lm_gnn_cpu_light"}:
        raw_graphs = build_unmasking_similarity_graphs(_label_free_events(events), relations=relations, include_text_similarity=False)
        graphs, reweighted_edge_count = _apply_discover_edge_scores_to_relation_graphs(raw_graphs, discovery)
        uses_discover_reweighted_edges = reweighted_edge_count > 0
        for graph in graphs.values():
            graph.add_nodes_from(nodes)
    return PreparedDetectInputs(
        discovery=discovery,
        labels=labels,
        nodes=list(nodes),
        discover_features=discover_features,
        lm_features=lm_features,
        features=features,
        y=y,
        node_records=node_records,
        graphs=graphs,
        lm_feature_source=lm_feature_source,
        discover_feature_count=discover_feature_count,
        lm_feature_count=lm_feature_count,
        discover_embedding_dim=discover_embedding_dim,
        reweighted_edge_count=int(reweighted_edge_count),
        uses_discover_reweighted_edges=uses_discover_reweighted_edges,
    )

__all__ = [
    "prepare_dyna_colm_detect_inputs",
]
