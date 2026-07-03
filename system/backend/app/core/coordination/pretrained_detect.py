from __future__ import annotations

import csv
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Sequence

import networkx as nx
import numpy as np
import pandas as pd

from app.config import PROJECT_ROOT
from app.core.coordination.io_reproduction import (
    DEFAULT_RELATIONS,
    _apply_discover_edge_scores_to_relation_graphs,
    _community_scores,
    _detect_discovery_snapshot,
    _discover_node_feature_table,
    _label_free_events,
    _lm_feature_matrix,
    _normalize_vector,
    _split_detect_feature_groups,
    build_unmasking_similarity_graphs,
    prepare_dyna_colm_detect_inputs,
    read_event_table,
)

KT1_EXPERIMENT_ROOT = PROJECT_ROOT / "backend" / "experiments" / "kt1_io_reproduction"
CHINA_EVENTS_PATH = KT1_EXPERIMENT_ROOT / "accept_detect_lm_gnn_6d_s5_ep20" / "china" / "events.csv"
CHINA_DISCOVERY_PATH = (
    KT1_EXPERIMENT_ROOT
    / "accept_discover_magnn_full_embeddings_6d_s5_ep20"
    / "china"
    / "seed_42"
    / "magnn"
    / "discovery_summary.json"
)
PRETRAINED_ROOT = PROJECT_ROOT / "output" / "coordination_pretrained"
PRETRAINED_CHECKPOINT_PATH = PRETRAINED_ROOT / "china_fusion_gnn_sbert.pt"
PRETRAINED_METADATA_PATH = PRETRAINED_ROOT / "china_fusion_gnn_sbert.json"


@dataclass(slots=True)
class PretrainedFusionInputs:
    nodes: list[str]
    node_records: dict[str, dict[str, object]]
    discover_feature_count: int
    lm_feature_count: int
    features: np.ndarray
    graphs: dict[str, nx.Graph]
    lm_feature_source: str


def _require_torch():
    try:
        import torch
        import torch.nn as nn
        import torch.nn.functional as functional
    except ModuleNotFoundError as exc:  # pragma: no cover - depends on env
        raise RuntimeError("KT1 Detect requires torch for fusion_gnn checkpoint inference") from exc
    return torch, nn, functional


def _resolve_device(torch, requested: str) -> str:
    if requested == "auto":
        return "cuda" if torch.cuda.is_available() else "cpu"
    if requested == "cuda" and not torch.cuda.is_available():
        return "cpu"
    return requested


def _seed_everything(torch, seed: int) -> None:
    torch.manual_seed(seed)
    np.random.seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


def _ordered_adjacency_tensors(torch, graphs: Mapping[str, nx.Graph], nodes: Sequence[str], relation_names: Sequence[str], device: str):
    node_index = {str(node): index for index, node in enumerate(nodes)}
    tensors = []
    for relation in relation_names:
        graph = graphs.get(relation, nx.Graph())
        rows: list[int] = []
        cols: list[int] = []
        vals: list[float] = []
        for source, target, attrs in graph.edges(data=True):
            if str(source) not in node_index or str(target) not in node_index:
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
        indices = torch.as_tensor(np.vstack([row_array, col_array]), dtype=torch.long, device=device)
        values = torch.as_tensor(val_array, dtype=torch.float32, device=device)
        tensors.append(torch.sparse_coo_tensor(indices, values, (len(nodes), len(nodes)), device=device).coalesce())
    return tensors


class FusionGNNModuleFactory:
    @staticmethod
    def build(nn, functional, *, struct_dim: int, lm_dim: int, hidden: int, relation_count: int):
        class FusionGNN(nn.Module):
            def __init__(self):
                super().__init__()
                self.struct_projection = nn.Linear(struct_dim, hidden)
                self.lm_projection = nn.Linear(lm_dim, hidden)
                self.struct_query = nn.Linear(hidden, hidden)
                self.struct_key = nn.Linear(hidden, hidden)
                self.lm_query = nn.Linear(hidden, hidden)
                self.lm_key = nn.Linear(hidden, hidden)
                self.graph_seed_projection = nn.Linear(hidden * 2, hidden)
                self.relation_linears = nn.ModuleList([nn.Linear(hidden, hidden) for _ in range(relation_count)])
                self.graph_semantic_context = nn.Parameter(nn.init.xavier_uniform_(__import__("torch").empty(hidden, 1)).squeeze(1))
                self.branch_projection = nn.Linear(hidden, hidden)
                self.branch_context = nn.Parameter(nn.init.xavier_uniform_(__import__("torch").empty(hidden, 1)).squeeze(1))
                self.output_hidden = nn.Linear(hidden, hidden)
                self.output = nn.Linear(hidden, 1)
                self.dropout = nn.Dropout(0.1)

            def forward(self, struct_x, lm_x, adjacency_tensors):
                torch = __import__("torch")
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

        return FusionGNN()


def _save_json(path: Path, payload: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _load_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def _ensure_strict_sbert(lm_feature_source: str) -> None:
    if not str(lm_feature_source).startswith("sbert:"):
        raise RuntimeError(
            "SBERT is required for KT1 mainline runs, but the runtime fell back to a non-SBERT LM feature source."
        )


def ensure_china_pretrained_fusion_checkpoint(
    *,
    device: str = "auto",
    hidden_dim: int = 32,
    embedding_dim: int = 32,
    detect_epochs: int = 20,
) -> dict[str, object]:
    if PRETRAINED_CHECKPOINT_PATH.exists() and PRETRAINED_METADATA_PATH.exists():
        return _load_json(PRETRAINED_METADATA_PATH)

    if not CHINA_EVENTS_PATH.exists():
        raise FileNotFoundError(f"Missing China events file for pretrained Detect export: {CHINA_EVENTS_PATH}")
    if not CHINA_DISCOVERY_PATH.exists():
        raise FileNotFoundError(f"Missing China discovery summary for pretrained Detect export: {CHINA_DISCOVERY_PATH}")

    events = read_event_table(CHINA_EVENTS_PATH)
    discovery = _load_json(CHINA_DISCOVERY_PATH)
    prepared = prepare_dyna_colm_detect_inputs(
        events,
        relations=tuple(discovery.get("relations", DEFAULT_RELATIONS)),
        seed=42,
        discover_encoder="magnn",
        discover_epochs=20,
        embedding_dim=embedding_dim,
        hidden_dim=hidden_dim,
        device=device,
        lm_backend="sbert",
        gnn_backend="fusion_gnn",
        precomputed_discovery=discovery,
    )
    _ensure_strict_sbert(prepared.lm_feature_source)
    metadata = _train_and_export_checkpoint(
        features=prepared.features,
        y=prepared.y,
        graphs=prepared.graphs,
        nodes=prepared.nodes,
        discover_feature_count=prepared.discover_feature_count,
        lm_feature_count=prepared.lm_feature_count,
        lm_feature_source=prepared.lm_feature_source,
        checkpoint_path=PRETRAINED_CHECKPOINT_PATH,
        hidden_dim=hidden_dim,
        epochs=detect_epochs,
        device=device,
        seed=42,
    )
    _save_json(PRETRAINED_METADATA_PATH, metadata)
    return metadata


def _train_and_export_checkpoint(
    *,
    features: np.ndarray,
    y: np.ndarray,
    graphs: Mapping[str, nx.Graph],
    nodes: Sequence[str],
    discover_feature_count: int,
    lm_feature_count: int,
    lm_feature_source: str,
    checkpoint_path: Path,
    hidden_dim: int,
    epochs: int,
    device: str,
    seed: int,
) -> dict[str, object]:
    torch, nn, functional = _require_torch()
    _seed_everything(torch, seed)
    target_device = _resolve_device(torch, device)
    relation_names = [relation for relation, graph in graphs.items() if graph.number_of_edges() > 0] or list(graphs)
    struct_matrix, lm_matrix = _split_detect_feature_groups(
        features,
        discover_feature_count=discover_feature_count,
        lm_feature_count=lm_feature_count,
    )
    x_struct = torch.as_tensor(struct_matrix, dtype=torch.float32, device=target_device)
    x_lm = torch.as_tensor(lm_matrix, dtype=torch.float32, device=target_device)
    labels = torch.as_tensor(y.astype(np.float32), dtype=torch.float32, device=target_device)
    adjacency_tensors = _ordered_adjacency_tensors(torch, graphs, nodes, relation_names, target_device)
    model = FusionGNNModuleFactory.build(
        nn,
        functional,
        struct_dim=x_struct.shape[1],
        lm_dim=x_lm.shape[1],
        hidden=max(4, int(hidden_dim)),
        relation_count=len(relation_names),
    ).to(target_device)
    optimizer = torch.optim.Adam(model.parameters(), lr=1e-3, weight_decay=1e-4)
    positives = max(float(np.sum(y == 1)), 1.0)
    negatives = max(float(np.sum(y == 0)), 1.0)
    pos_weight = torch.as_tensor([negatives / positives], dtype=torch.float32, device=target_device)
    final_loss = 0.0
    for _ in range(max(1, int(epochs))):
        model.train()
        optimizer.zero_grad()
        logits, _, _, _ = model(x_struct, x_lm, adjacency_tensors)
        loss = functional.binary_cross_entropy_with_logits(logits, labels, pos_weight=pos_weight)
        loss.backward()
        optimizer.step()
        final_loss = float(loss.detach().cpu().item())

    checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
    torch.save(
        {
            "state_dict": model.state_dict(),
            "relation_names": relation_names,
            "discover_feature_count": int(discover_feature_count),
            "lm_feature_count": int(lm_feature_count),
            "hidden_dim": int(hidden_dim),
            "lm_feature_source": lm_feature_source,
            "seed": int(seed),
            "final_loss": round(final_loss, 6),
            "positive_count": int(np.sum(y == 1)),
            "node_count": int(len(nodes)),
        },
        checkpoint_path,
    )
    return {
        "checkpoint_path": str(checkpoint_path),
        "checkpoint_name": checkpoint_path.name,
        "dataset": "china",
        "detect_backend": "fusion_gnn",
        "lm_backend": "sbert",
        "lm_feature_source": lm_feature_source,
        "discover_encoder": "magnn",
        "community_algorithm": "leiden",
        "hidden_dim": int(hidden_dim),
        "discover_feature_count": int(discover_feature_count),
        "lm_feature_count": int(lm_feature_count),
        "relation_names": relation_names,
        "seed": int(seed),
        "final_loss": round(final_loss, 6),
    }


def _load_checkpoint_bundle(device: str = "auto") -> tuple[dict[str, object], object, object, object, str]:
    torch, nn, functional = _require_torch()
    target_device = _resolve_device(torch, device)
    if not PRETRAINED_CHECKPOINT_PATH.exists():
        raise FileNotFoundError(f"Missing pretrained checkpoint: {PRETRAINED_CHECKPOINT_PATH}")
    bundle = torch.load(PRETRAINED_CHECKPOINT_PATH, map_location=target_device)
    return bundle, torch, nn, functional, target_device


def prepare_unlabeled_fusion_inputs(
    events: pd.DataFrame,
    discovery: Mapping[str, object],
    *,
    relations: Sequence[str] = DEFAULT_RELATIONS,
    embedding_dim: int = 32,
    lm_cache_dir: Path | None = None,
) -> PretrainedFusionInputs:
    nodes, discover_features, _, node_records = _discover_node_feature_table(discovery, {})
    lm_features, lm_feature_source = _lm_feature_matrix(
        events,
        nodes,
        backend="sbert",
        max_dim=max(8, embedding_dim),
        cache_dir=lm_cache_dir,
    )
    _ensure_strict_sbert(lm_feature_source)
    features = np.concatenate([discover_features, lm_features], axis=1)
    for column in range(features.shape[1]):
        features[:, column] = _normalize_vector(features[:, column])
    graphs = build_unmasking_similarity_graphs(
        _label_free_events(events),
        relations=tuple(relations),
        include_text_similarity=False,
    )
    graphs, _ = _apply_discover_edge_scores_to_relation_graphs(graphs, discovery)
    for graph in graphs.values():
        graph.add_nodes_from(nodes)
    return PretrainedFusionInputs(
        nodes=nodes,
        node_records=node_records,
        discover_feature_count=int(discover_features.shape[1]) if discover_features.ndim == 2 else 0,
        lm_feature_count=int(lm_features.shape[1]) if lm_features.ndim == 2 else 0,
        features=features,
        graphs=graphs,
        lm_feature_source=lm_feature_source,
    )


def _fit_feature_width(matrix: np.ndarray, expected_width: int) -> np.ndarray:
    if matrix.shape[1] == expected_width:
        return matrix
    if matrix.shape[1] > expected_width:
        return np.asarray(matrix[:, :expected_width], dtype=float)
    padding = np.zeros((matrix.shape[0], expected_width - matrix.shape[1]), dtype=float)
    return np.concatenate([matrix, padding], axis=1)


def infer_with_china_pretrained_fusion(
    prepared: PretrainedFusionInputs,
    *,
    device: str = "auto",
) -> tuple[np.ndarray, dict[str, object]]:
    bundle, torch, nn, functional, target_device = _load_checkpoint_bundle(device=device)
    relation_names = [str(value) for value in bundle.get("relation_names", [])]
    discover_feature_count = int(bundle.get("discover_feature_count", prepared.discover_feature_count))
    lm_feature_count = int(bundle.get("lm_feature_count", prepared.lm_feature_count))
    hidden_dim = int(bundle.get("hidden_dim", 32))
    struct_matrix, lm_matrix = _split_detect_feature_groups(
        prepared.features,
        discover_feature_count=prepared.discover_feature_count,
        lm_feature_count=prepared.lm_feature_count,
    )
    struct_matrix = _fit_feature_width(struct_matrix, discover_feature_count)
    lm_matrix = _fit_feature_width(lm_matrix, lm_feature_count)
    x_struct = torch.as_tensor(struct_matrix, dtype=torch.float32, device=target_device)
    x_lm = torch.as_tensor(lm_matrix, dtype=torch.float32, device=target_device)
    adjacency_tensors = _ordered_adjacency_tensors(torch, prepared.graphs, prepared.nodes, relation_names, target_device)
    model = FusionGNNModuleFactory.build(
        nn,
        functional,
        struct_dim=discover_feature_count,
        lm_dim=lm_feature_count,
        hidden=max(4, hidden_dim),
        relation_count=len(relation_names),
    ).to(target_device)
    model.load_state_dict(bundle["state_dict"])
    model.eval()
    with torch.no_grad():
        logits, relation_attention, branch_attention, cross_means = model(x_struct, x_lm, adjacency_tensors)
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
    details = {
        "fusion_architecture": "discover_lm_graph_attention",
        "relation_attention": relation_attention_map,
        "branch_attention": branch_attention_map,
        "cross_attention_mean": {
            "struct_to_lm": round(float(cross_means[0].detach().cpu().item()), 6),
            "lm_to_struct": round(float(cross_means[1].detach().cpu().item()), 6),
        },
        "pretrained_dataset": "china",
        "pretrained_checkpoint": str(PRETRAINED_CHECKPOINT_PATH),
    }
    return probabilities, details


def run_china_pretrained_detect(
    events: pd.DataFrame,
    discovery: Mapping[str, object],
    *,
    output_dir: Path | None = None,
    relations: Sequence[str] = DEFAULT_RELATIONS,
    seed: int = 42,
    embedding_dim: int = 32,
    device: str = "auto",
    lm_cache_dir: Path | None = None,
) -> dict[str, object]:
    metadata = ensure_china_pretrained_fusion_checkpoint(device=device, hidden_dim=32, embedding_dim=embedding_dim)
    prepared = prepare_unlabeled_fusion_inputs(
        events,
        discovery,
        relations=relations,
        embedding_dim=embedding_dim,
        lm_cache_dir=lm_cache_dir,
    )
    scores, details = infer_with_china_pretrained_fusion(prepared, device=device)
    predictions = []
    for index, account_id in enumerate(prepared.nodes):
        node = prepared.node_records.get(account_id, {})
        score = float(scores[index]) if index < scores.size else 0.0
        predictions.append(
            {
                "account_id": account_id,
                "node_score": round(score, 6),
                "predicted_label": int(score >= 0.5),
                "label": None,
                "evaluation_split": "inference",
                "cluster_id": node.get("cluster_id"),
                "directed_out_weight": node.get("directed_out_weight"),
                "directed_in_weight": node.get("directed_in_weight"),
            }
        )
    predictions = sorted(predictions, key=lambda row: (-float(row["node_score"]), row["account_id"]))
    node_scores = np.asarray([float(row["node_score"]) for row in predictions], dtype=float)
    score_summary = {
        "score_mean": round(float(np.mean(node_scores)), 6) if node_scores.size else 0.0,
        "score_p90": round(float(np.quantile(node_scores, 0.9)), 6) if node_scores.size else 0.0,
        "score_max": round(float(np.max(node_scores)), 6) if node_scores.size else 0.0,
        "positive_at_0_5": int(np.sum(node_scores >= 0.5)),
        "node_count": int(node_scores.size),
    }
    summary = {
        "setting": "detect",
        "task": "coordination_discrimination",
        "method": "dyna_colm_detect_pretrained",
        "relations": list(relations),
        "detect_model": {
            "uses_discover_outputs": True,
            "discover_encoder": "magnn",
            "lm_backend": "sbert",
            "lm_feature_source": prepared.lm_feature_source,
            "gnn_backend": "fusion_gnn",
            "split_mode": "pretrained_inference",
            "split_detail": "china_pretrained_inference",
            "evaluation_protocol": "pretrained_inference_without_labels",
            "feature_count": int(prepared.features.shape[1]) if prepared.features.ndim == 2 else 0,
            "discover_feature_count": prepared.discover_feature_count,
            "lm_feature_count": prepared.lm_feature_count,
            "uses_community_features": True,
            "uses_dynamic_features": True,
            "uses_metapath_instance_features": True,
            "uses_discover_reweighted_edges": True,
            "edge_score_source": (
                discovery.get("deep_graph_model", {}).get("edge_score_source")
                if isinstance(discovery.get("deep_graph_model"), Mapping)
                else None
            ),
            "uses_lm_features": True,
            "uses_pretrained_weights": True,
            "pretrained_dataset": "china",
            "pretrained_metadata": metadata,
            "fusion_details": details,
        },
        "metrics": {},
        "all_node_metrics": {},
        "predictions": predictions,
        "node_scores": {row["account_id"]: row["node_score"] for row in predictions},
        "community_scores": _community_scores(discovery, predictions),
        "discovery": _detect_discovery_snapshot(discovery),
        "unlabeled_inference_summary": score_summary,
    }
    if output_dir is not None:
        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / "detection_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
        with (output_dir / "predictions.csv").open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(
                handle,
                fieldnames=[
                    "account_id",
                    "node_score",
                    "predicted_label",
                    "label",
                    "evaluation_split",
                    "cluster_id",
                    "directed_out_weight",
                    "directed_in_weight",
                ],
            )
            writer.writeheader()
            writer.writerows(predictions)
    return summary
