"""Focused detect implementation for coordination reproduction."""

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
    PreparedDetectInputs,
    _amdn_hage_style_metrics,
    _detection_metric_dict,
    _normalize_vector,
    extract_labels,
)
from app.core.coordination_baseline.reproduction_graphs import (
    _split_for_detect,
    build_unmasking_similarity_graphs,
)
from app.core.coordination_baseline.reproduction_discover import (
    _apply_discover_edge_scores_to_relation_graphs,
    _community_scores,
    _comparison_rows_for_detect,
    _cpu_light_gfm_lm_gnn_scores,
    _detect_discovery_snapshot,
    _discover_embedding_dim,
    _discover_encoder_governance,
    _discover_node_feature_table,
    _fit_transductive_scores_with_split,
    _label_free_events,
    _lm_feature_matrix,
    _prediction_rows,
    _prediction_rows_from_discover_features,
    _torch_fusion_gnn_scores,
    _torch_gfm_lm_gnn_scores,
    _torch_relation_gnn_scores,
    run_dyna_colm_discover,
    run_dyna_colm_gnn_ablations,
    run_dyna_colm_gnn_prototype,
)

def run_dyna_colm_ablation_suite(
    events: pd.DataFrame,
    *,
    relations: Sequence[str] = DEFAULT_RELATIONS,
    seed: int = 42,
) -> dict[str, dict[str, object]]:
    return run_dyna_colm_gnn_ablations(events, relations=relations, seed=seed)


def run_dyna_colm_detect(
    events: pd.DataFrame,
    *,
    output_dir: Path | None = None,
    relations: Sequence[str] = DEFAULT_RELATIONS,
    seed: int = 42,
    discover_encoder: str = STABLE_DISCOVER_ENCODER,
    discover_epochs: int = 20,
    embedding_dim: int = 32,
    hidden_dim: int = 32,
    device: str = "auto",
    lm_backend: str = "sbert",
    gnn_backend: str = "gfm_lm_gnn",
    detect_epochs: int | None = None,
    split_mode: str = "supervised",
    precomputed_discovery: Mapping[str, object] | None = None,
    include_diagnostics: bool = True,
    lm_cache_dir: Path | None = None,
) -> dict[str, object]:
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
    split, split_detail = _split_for_detect(events, nodes, y, split_mode=split_mode, seed=seed)
    reweighted_edge_count = 0
    uses_discover_reweighted_edges = False
    fusion_details: dict[str, object] = {}
    if gnn_backend in {"relation_gnn", "fusion_gnn", "gfm_lm_gnn", "gfm_lm_gnn_cpu_light"}:
        graphs = build_unmasking_similarity_graphs(_label_free_events(events), relations=relations, include_text_similarity=False)
        graphs, reweighted_edge_count = _apply_discover_edge_scores_to_relation_graphs(graphs, discovery)
        uses_discover_reweighted_edges = reweighted_edge_count > 0
        for graph in graphs.values():
            graph.add_nodes_from(nodes)
        supervised_epochs = max(1, int(detect_epochs)) if detect_epochs is not None else max(20, int(discover_epochs) * 5)
        if gnn_backend == "gfm_lm_gnn_cpu_light":
            scores, classifier_backend, fusion_details = _cpu_light_gfm_lm_gnn_scores(
                features,
                y,
                graphs,
                nodes,
                discover_feature_count=discover_feature_count,
                lm_feature_count=lm_feature_count,
                seed=seed,
                split=split,
            )
        elif gnn_backend == "gfm_lm_gnn":
            scores, classifier_backend, fusion_details = _torch_gfm_lm_gnn_scores(
                features,
                y,
                graphs,
                nodes,
                discover_feature_count=discover_feature_count,
                lm_feature_count=lm_feature_count,
                seed=seed,
                epochs=supervised_epochs,
                hidden_dim=hidden_dim,
                device=device,
                split=split,
            )
        elif gnn_backend == "fusion_gnn":
            scores, classifier_backend, fusion_details = _torch_fusion_gnn_scores(
                features,
                y,
                graphs,
                nodes,
                discover_feature_count=discover_feature_count,
                lm_feature_count=lm_feature_count,
                seed=seed,
                epochs=supervised_epochs,
                hidden_dim=hidden_dim,
                device=device,
                split=split,
            )
        else:
            scores, classifier_backend, fusion_details = _torch_relation_gnn_scores(
                features,
                y,
                graphs,
                nodes,
                seed=seed,
                epochs=supervised_epochs,
                hidden_dim=hidden_dim,
                device=device,
                split=split,
            )
    else:
        scores, classifier_backend = _fit_transductive_scores_with_split(features, y, seed=seed, split=split)
    predictions = _prediction_rows_from_discover_features(nodes, scores, labels, node_records, split=split)
    test_predictions = [row for row in predictions if row.get("evaluation_split") == "test"]
    test_y_true = [int(row["label"]) for row in test_predictions]
    test_y_score = [float(row["node_score"]) for row in test_predictions]
    all_y_true = [int(row["label"]) for row in predictions]
    all_y_score = [float(row["node_score"]) for row in predictions]
    # Paper-facing Detect metrics are held-out only. The all-node version is
    # retained for audits because train rows still receive diagnostic scores.
    metrics = _detection_metric_dict(test_y_true, test_y_score) if test_predictions else {}
    metrics["amdn_hage_style"] = _amdn_hage_style_metrics(test_y_true, test_y_score) if test_predictions else {}
    all_node_metrics = _detection_metric_dict(all_y_true, all_y_score)
    all_node_metrics["amdn_hage_style"] = _amdn_hage_style_metrics(all_y_true, all_y_score)
    legacy_full: dict[str, object] = {}
    ablations: dict[str, dict[str, object]] = {}
    if include_diagnostics:
        legacy_full = run_dyna_colm_gnn_prototype(events, relations=relations, seed=seed, variant="legacy_detect")
        ablations = run_dyna_colm_ablation_suite(events, relations=relations, seed=seed)
        for ablation in ablations.values():
            ablation_predictions = _prediction_rows(ablation, labels)
            ablation["metrics"] = _detection_metric_dict(
                [int(row["label"]) for row in ablation_predictions],
                [float(row["node_score"]) for row in ablation_predictions],
            )
    summary = {
        "setting": "detect",
        "task": "coordination_discrimination",
        "method": "dyna_colm_detect",
        "relations": list(relations),
        "detect_model": {
            "uses_discover_outputs": True,
            "discover_encoder": discover_encoder,
            "model_governance": _discover_encoder_governance(discover_encoder),
            "discover_epochs": discover_epochs,
            "detect_epochs": detect_epochs if detect_epochs is not None else max(20, int(discover_epochs) * 5),
            "lm_backend": lm_backend,
            "lm_feature_source": lm_feature_source,
            "gnn_backend": gnn_backend,
            "split_mode": split_mode,
            "split_detail": split_detail,
            "train_count": int(split.train.size),
            "test_count": int(split.test.size),
            "evaluation_protocol": "heldout_test_only",
            "feature_count": int(features.shape[1]) if features.ndim == 2 else 0,
            "discover_feature_count": discover_feature_count,
            "lm_feature_count": lm_feature_count,
            "discover_embedding_dim": discover_embedding_dim,
            "classifier_backend": classifier_backend,
            "uses_community_features": True,
            "uses_dynamic_features": True,
            "uses_metapath_instance_features": True,
            "uses_full_discover_embeddings": discover_embedding_dim > 0,
            "uses_discover_reweighted_edges": uses_discover_reweighted_edges,
            "reweighted_edge_count": int(reweighted_edge_count),
            "edge_score_source": (
                discovery.get("deep_graph_model", {}).get("edge_score_source")
                if isinstance(discovery.get("deep_graph_model"), Mapping)
                else None
            ),
            "uses_lm_features": True,
            "uses_precomputed_discovery": precomputed_discovery is not None,
            "uses_lm_disk_cache": lm_cache_dir is not None,
            "include_diagnostics": include_diagnostics,
            "fusion_details": fusion_details,
        },
        "metrics": metrics,
        "all_node_metrics": all_node_metrics,
        "predictions": predictions,
        "node_scores": {row["account_id"]: row["node_score"] for row in predictions},
        "community_scores": _community_scores(discovery, predictions),
        "discovery": _detect_discovery_snapshot(discovery),
        "legacy_prototype": (
            {
                "method": legacy_full.get("method"),
                "variant": legacy_full.get("variant"),
                "metrics": legacy_full.get("metrics"),
                "classifier_backend": legacy_full.get("classifier_backend"),
            }
            if include_diagnostics
            else {}
        ),
        "ablations": (
            {
                variant: {
                    "method": result.get("method"),
                    "variant": result.get("variant"),
                    "metrics": result.get("metrics"),
                    "uses_lm_features": result.get("uses_lm_features"),
                    "uses_gnn_message_passing": result.get("uses_gnn_message_passing"),
                    "uses_direction_time_features": result.get("uses_direction_time_features"),
                    "uses_relation_attention": result.get("uses_relation_attention"),
                    "relation_attention_mode": result.get("relation_attention_mode"),
                    "uses_community_features": result.get("uses_community_features"),
                    "relation_attention": result.get("relation_attention"),
                }
                for variant, result in ablations.items()
            }
            if include_diagnostics
            else {}
        ),
    }
    summary["characterization"] = characterize_detect_output(
        events=events,
        discovery=discovery,
        predictions=predictions,
        config=CharacterizationConfig(
            include_risk_report=include_diagnostics,
            include_observer_lens=True,
            observer_lens="network_security",
        ),
    )
    summary["comparison_rows"] = _comparison_rows_for_detect(summary)
    if output_dir is not None:
        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / "detection_summary.json").write_text(
            json.dumps(summary, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        fields = (
            "account_id",
            "label",
            "evaluation_split",
            "predicted_label",
            "node_score",
            "cluster_id",
            "directed_out_weight",
            "directed_in_weight",
        )
        with (output_dir / "predictions.csv").open("w", encoding="utf-8", newline="") as file_handle:
            writer = csv.DictWriter(file_handle, fieldnames=fields)
            writer.writeheader()
            for row in predictions:
                writer.writerow({field: row.get(field) for field in fields})
    return summary


def run_dyna_colm_detect_from_prepared(
    events: pd.DataFrame,
    prepared: PreparedDetectInputs,
    *,
    output_dir: Path | None = None,
    relations: Sequence[str] = DEFAULT_RELATIONS,
    seed: int = 42,
    discover_encoder: str = STABLE_DISCOVER_ENCODER,
    discover_epochs: int = 20,
    hidden_dim: int = 32,
    device: str = "auto",
    lm_backend: str = "sbert",
    gnn_backend: str = "gfm_lm_gnn",
    detect_epochs: int | None = None,
    split_mode: str = "supervised",
    uses_precomputed_discovery: bool = False,
    include_diagnostics: bool = True,
    include_characterization: bool = True,
    include_community_scores: bool = True,
    compact_summary: bool = False,
    uses_lm_disk_cache: bool = False,
) -> dict[str, object]:
    discovery = prepared.discovery
    labels = prepared.labels
    nodes = prepared.nodes
    features = prepared.features
    y = prepared.y
    node_records = prepared.node_records
    split, split_detail = _split_for_detect(events, nodes, y, split_mode=split_mode, seed=seed)
    fusion_details: dict[str, object] = {}
    if gnn_backend in {"relation_gnn", "fusion_gnn", "gfm_lm_gnn", "gfm_lm_gnn_cpu_light"}:
        graphs = prepared.graphs
        supervised_epochs = max(1, int(detect_epochs)) if detect_epochs is not None else max(20, int(discover_epochs) * 5)
        if gnn_backend == "gfm_lm_gnn_cpu_light":
            scores, classifier_backend, fusion_details = _cpu_light_gfm_lm_gnn_scores(
                features,
                y,
                graphs,
                nodes,
                discover_feature_count=prepared.discover_feature_count,
                lm_feature_count=prepared.lm_feature_count,
                seed=seed,
                split=split,
            )
        elif gnn_backend == "gfm_lm_gnn":
            scores, classifier_backend, fusion_details = _torch_gfm_lm_gnn_scores(
                features,
                y,
                graphs,
                nodes,
                discover_feature_count=prepared.discover_feature_count,
                lm_feature_count=prepared.lm_feature_count,
                seed=seed,
                epochs=supervised_epochs,
                hidden_dim=hidden_dim,
                device=device,
                split=split,
            )
        elif gnn_backend == "fusion_gnn":
            scores, classifier_backend, fusion_details = _torch_fusion_gnn_scores(
                features,
                y,
                graphs,
                nodes,
                discover_feature_count=prepared.discover_feature_count,
                lm_feature_count=prepared.lm_feature_count,
                seed=seed,
                epochs=supervised_epochs,
                hidden_dim=hidden_dim,
                device=device,
                split=split,
            )
        else:
            scores, classifier_backend, fusion_details = _torch_relation_gnn_scores(
                features,
                y,
                graphs,
                nodes,
                seed=seed,
                epochs=supervised_epochs,
                hidden_dim=hidden_dim,
                device=device,
                split=split,
            )
    else:
        scores, classifier_backend = _fit_transductive_scores_with_split(features, y, seed=seed, split=split)
    predictions = _prediction_rows_from_discover_features(nodes, scores, labels, node_records, split=split)
    test_predictions = [row for row in predictions if row.get("evaluation_split") == "test"]
    test_y_true = [int(row["label"]) for row in test_predictions]
    test_y_score = [float(row["node_score"]) for row in test_predictions]
    all_y_true = [int(row["label"]) for row in predictions]
    all_y_score = [float(row["node_score"]) for row in predictions]
    metrics = _detection_metric_dict(test_y_true, test_y_score) if test_predictions else {}
    metrics["amdn_hage_style"] = _amdn_hage_style_metrics(test_y_true, test_y_score) if test_predictions else {}
    all_node_metrics = _detection_metric_dict(all_y_true, all_y_score)
    all_node_metrics["amdn_hage_style"] = _amdn_hage_style_metrics(all_y_true, all_y_score)
    legacy_full: dict[str, object] = {}
    ablations: dict[str, dict[str, object]] = {}
    if include_diagnostics:
        legacy_full = run_dyna_colm_gnn_prototype(events, relations=relations, seed=seed, variant="legacy_detect")
        ablations = run_dyna_colm_ablation_suite(events, relations=relations, seed=seed)
        for ablation in ablations.values():
            ablation_predictions = _prediction_rows(ablation, labels)
            ablation["metrics"] = _detection_metric_dict(
                [int(row["label"]) for row in ablation_predictions],
                [float(row["node_score"]) for row in ablation_predictions],
            )
    summary = {
        "setting": "detect",
        "task": "coordination_discrimination",
        "method": "dyna_colm_detect",
        "relations": list(relations),
        "detect_model": {
            "uses_discover_outputs": True,
            "discover_encoder": discover_encoder,
            "model_governance": _discover_encoder_governance(discover_encoder),
            "discover_epochs": discover_epochs,
            "detect_epochs": detect_epochs if detect_epochs is not None else max(20, int(discover_epochs) * 5),
            "lm_backend": lm_backend,
            "lm_feature_source": prepared.lm_feature_source,
            "gnn_backend": gnn_backend,
            "split_mode": split_mode,
            "split_detail": split_detail,
            "train_count": int(split.train.size),
            "test_count": int(split.test.size),
            "evaluation_protocol": "heldout_test_only",
            "feature_count": int(features.shape[1]) if features.ndim == 2 else 0,
            "discover_feature_count": prepared.discover_feature_count,
            "lm_feature_count": prepared.lm_feature_count,
            "discover_embedding_dim": prepared.discover_embedding_dim,
            "classifier_backend": classifier_backend,
            "uses_community_features": True,
            "uses_dynamic_features": True,
            "uses_metapath_instance_features": True,
            "uses_full_discover_embeddings": prepared.discover_embedding_dim > 0,
            "uses_discover_reweighted_edges": prepared.uses_discover_reweighted_edges,
            "reweighted_edge_count": int(prepared.reweighted_edge_count),
            "edge_score_source": (
                discovery.get("deep_graph_model", {}).get("edge_score_source")
                if isinstance(discovery.get("deep_graph_model"), Mapping)
                else None
            ),
            "uses_lm_features": True,
            "uses_precomputed_discovery": uses_precomputed_discovery,
            "uses_lm_disk_cache": uses_lm_disk_cache,
            "uses_prepared_detect_inputs": True,
            "include_diagnostics": include_diagnostics,
            "include_characterization": include_characterization,
            "include_community_scores": include_community_scores,
            "compact_summary": compact_summary,
            "fusion_details": fusion_details,
        },
        "metrics": metrics,
        "all_node_metrics": all_node_metrics,
        "predictions": predictions,
        "node_scores": {row["account_id"]: row["node_score"] for row in predictions},
        "community_scores": _community_scores(discovery, predictions) if include_community_scores else [],
        "discovery": _detect_discovery_snapshot(discovery),
        "legacy_prototype": (
            {
                "method": legacy_full.get("method"),
                "variant": legacy_full.get("variant"),
                "metrics": legacy_full.get("metrics"),
                "classifier_backend": legacy_full.get("classifier_backend"),
            }
            if include_diagnostics
            else {}
        ),
        "ablations": (
            {
                variant: {
                    "method": result.get("method"),
                    "variant": result.get("variant"),
                    "metrics": result.get("metrics"),
                    "uses_lm_features": result.get("uses_lm_features"),
                    "uses_gnn_message_passing": result.get("uses_gnn_message_passing"),
                    "uses_direction_time_features": result.get("uses_direction_time_features"),
                    "uses_relation_attention": result.get("uses_relation_attention"),
                    "relation_attention_mode": result.get("relation_attention_mode"),
                    "uses_community_features": result.get("uses_community_features"),
                    "relation_attention": result.get("relation_attention"),
                }
                for variant, result in ablations.items()
            }
            if include_diagnostics
            else {}
        ),
    }
    if include_characterization:
        summary["characterization"] = characterize_detect_output(
            events=events,
            discovery=discovery,
            predictions=predictions,
            config=CharacterizationConfig(
                include_risk_report=include_diagnostics,
                include_observer_lens=True,
                observer_lens="network_security",
            ),
        )
    else:
        summary["characterization"] = {
            "task": "coordination_characterization",
            "method": "skipped_for_detect_only_batch",
            "communities": [],
            "summary": {
                "community_count": 0,
                "skip_reason": "CoordinationDiscover Detect acceptance reports held-out detection metrics; PropagationAnalysis handles heavy characterization.",
            },
        }
    summary["comparison_rows"] = _comparison_rows_for_detect(summary)
    prediction_rows_for_file = predictions
    if compact_summary:
        summary["prediction_count"] = len(predictions)
        summary["node_score_count"] = len(summary.get("node_scores", {}))
        summary["community_score_count"] = len(summary.get("community_scores", []))
        summary["compact_artifacts"] = {
            "predictions_csv": "predictions.csv",
            "omitted_from_json": ["predictions", "node_scores", "community_scores"],
        }
        summary["predictions"] = []
        summary["node_scores"] = {}
        summary["community_scores"] = []
    if output_dir is not None:
        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / "detection_summary.json").write_text(
            json.dumps(summary, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        fields = (
            "account_id",
            "label",
            "evaluation_split",
            "predicted_label",
            "node_score",
            "cluster_id",
            "directed_out_weight",
            "directed_in_weight",
        )
        with (output_dir / "predictions.csv").open("w", encoding="utf-8", newline="") as file_handle:
            writer = csv.DictWriter(file_handle, fieldnames=fields)
            writer.writeheader()
            for row in prediction_rows_for_file:
                writer.writerow({field: row.get(field) for field in fields})
    return summary


def run_setting_a_discovery(
    events: pd.DataFrame,
    *,
    output_dir: Path | None = None,
    relations: Sequence[str] = DEFAULT_RELATIONS,
    seed: int = 42,
) -> dict[str, object]:
    return run_dyna_colm_discover(events, output_dir=output_dir, relations=relations, seed=seed)


def run_setting_ablation_suite(
    events: pd.DataFrame,
    *,
    relations: Sequence[str] = DEFAULT_RELATIONS,
    seed: int = 42,
) -> dict[str, dict[str, object]]:
    return run_dyna_colm_ablation_suite(events, relations=relations, seed=seed)


def run_setting_b_detection(
    events: pd.DataFrame,
    *,
    output_dir: Path | None = None,
    relations: Sequence[str] = DEFAULT_RELATIONS,
    seed: int = 42,
) -> dict[str, object]:
    return run_dyna_colm_detect(events, output_dir=output_dir, relations=relations, seed=seed)


def run_dyna_colm_characterize(
    events: pd.DataFrame,
    *,
    output_dir: Path | None = None,
    relations: Sequence[str] = DEFAULT_RELATIONS,
    seed: int = 42,
    detect_result: Mapping[str, object] | None = None,
    include_risk_report: bool = True,
    observer_lens: str = "network_security",
) -> dict[str, object]:
    detect_summary = (
        dict(detect_result)
        if detect_result is not None
        else run_dyna_colm_detect(
            events,
            output_dir=output_dir,
            relations=relations,
            seed=seed,
        )
    )
    existing = detect_summary.get("characterization")
    if isinstance(existing, Mapping) and existing.get("communities"):
        characterization = dict(existing)
    else:
        full_discovery = detect_summary.get("_full_discovery_for_characterization")
        if not isinstance(full_discovery, Mapping):
            full_discovery = run_dyna_colm_discover(
                events,
                output_dir=None,
                relations=relations,
                seed=seed,
            )
        characterization = characterize_detect_output(
            events=events,
            discovery=full_discovery,
            predictions=detect_summary.get("predictions", []),
            config=CharacterizationConfig(
                include_risk_report=include_risk_report,
                include_observer_lens=True,
                observer_lens=observer_lens,
            ),
        )
    if output_dir is not None:
        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / "characterization_summary.json").write_text(
            json.dumps(characterization, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    return characterization

__all__ = [
    "run_dyna_colm_ablation_suite",
    "run_dyna_colm_characterize",
    "run_dyna_colm_detect",
    "run_dyna_colm_detect_from_prepared",
    "run_setting_a_discovery",
    "run_setting_ablation_suite",
    "run_setting_b_detection",
]
