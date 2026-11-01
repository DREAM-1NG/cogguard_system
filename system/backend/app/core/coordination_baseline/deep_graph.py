from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field
import hashlib
import math
import random
from typing import Literal, Mapping, Sequence

import networkx as nx
import numpy as np


DeepGraphEncoderName = Literal["han", "han_relation", "lightweight", "magnn_legacy", "magnn", "amdn_hage"]

STABLE_DISCOVER_ENCODER: DeepGraphEncoderName = "magnn_legacy"
DEPRECATED_DISCOVER_ENCODERS = {
    "magnn": "deprecated_non_claimable_recon_regression",
}


@dataclass(frozen=True)
class DeepGraphDiscoverConfig:
    # The newer MAGNN instance encoder is retained for historical replay only;
    # IOHunter validation showed severe reconstruction AUC/AP regression.
    encoder: DeepGraphEncoderName = STABLE_DISCOVER_ENCODER
    embedding_dim: int = 64
    hidden_dim: int = 64
    epochs: int = 80
    lr: float = 1e-3
    weight_decay: float = 1e-4
    dropout: float = 0.1
    negative_ratio: float = 1.0
    device: str = "auto"
    seed: int = 42


@dataclass
class DeepGraphDiscoverResult:
    encoder: str
    embeddings: np.ndarray
    node_index: dict[str, int]
    relation_attention: dict[str, float]
    edge_scores: dict[tuple[str, str], float]
    training_loss: list[float] = field(default_factory=list)
    reconstruction_metrics: dict[str, object] = field(default_factory=dict)
    device: str = "cpu"
    uses_labels: bool = False
    metapath_attention: dict[str, float] = field(default_factory=dict)
    intra_metapath_attention: dict[str, float] = field(default_factory=dict)
    metapath_instance_counts: dict[str, int] = field(default_factory=dict)
    object_node_count: int = 0
    edge_score_source: str = ""
    hidden_groups: dict[str, int] = field(default_factory=dict)
    temporal_nll: float | None = None


def _require_torch():
    try:
        import torch
        import torch.nn as nn
        import torch.nn.functional as functional
    except ModuleNotFoundError as exc:  # pragma: no cover - exercised only when env lacks torch
        raise ModuleNotFoundError(
            "Deep graph discover requires torch. Install backend dependencies from pyproject.toml/requirements.txt."
        ) from exc
    return torch, nn, functional


def _resolve_device(torch, requested: str) -> str:
    if requested == "auto":
        return "cuda" if torch.cuda.is_available() else "cpu"
    if requested == "cuda" and not torch.cuda.is_available():
        return "cpu"
    return requested


def _edge_key(source: str, target: str) -> tuple[str, str]:
    return tuple(sorted((str(source), str(target))))


def _stable_hash_bucket(value: str, buckets: int) -> int:
    digest = hashlib.sha1(value.encode("utf-8", errors="ignore")).hexdigest()
    return int(digest[:12], 16) % max(1, buckets)


def _roc_auc(y_true: np.ndarray, y_score: np.ndarray) -> float | None:
    positives = y_score[y_true == 1]
    negatives = y_score[y_true == 0]
    if positives.size == 0 or negatives.size == 0:
        return None
    greater = 0.0
    for positive_score in positives:
        greater += float(np.sum(positive_score > negatives))
        greater += 0.5 * float(np.sum(positive_score == negatives))
    return greater / float(positives.size * negatives.size)


def _average_precision(labels: np.ndarray, scores: np.ndarray) -> float | None:
    positive_count = int(np.sum(labels == 1))
    if labels.size == 0 or positive_count == 0:
        return None
    hits = 0
    precision_sum = 0.0
    for rank, index in enumerate(np.argsort(-scores), start=1):
        if labels[index] == 1:
            hits += 1
            precision_sum += hits / rank
    return precision_sum / positive_count


def _sample_training_edges(
    graphs: Mapping[str, nx.Graph],
    nodes: Sequence[str],
    *,
    negative_ratio: float,
    seed: int,
) -> tuple[list[tuple[int, int, int, float]], list[tuple[int, int, int, float]], list[str]]:
    node_index = {node: index for index, node in enumerate(nodes)}
    relation_names = [relation for relation, graph in graphs.items() if graph.number_of_edges() > 0]
    positive_edges: list[tuple[int, int, int, float]] = []
    observed_pairs: set[tuple[int, int]] = set()
    for relation_index, relation in enumerate(relation_names):
        graph = graphs[relation]
        for source, target, attrs in graph.edges(data=True):
            if source not in node_index or target not in node_index or source == target:
                continue
            source_index = node_index[str(source)]
            target_index = node_index[str(target)]
            pair = tuple(sorted((source_index, target_index)))
            observed_pairs.add(pair)
            positive_edges.append(
                (
                    source_index,
                    target_index,
                    relation_index,
                    max(float(attrs.get("weight", 1.0)), 1e-6),
                )
            )
    if not positive_edges or len(nodes) < 2:
        return positive_edges, [], relation_names

    rng = random.Random(seed)
    negative_count = max(1, int(math.ceil(len(positive_edges) * max(negative_ratio, 0.0))))
    negative_edges: list[tuple[int, int, int, float]] = []
    attempts = 0
    max_attempts = max(negative_count * 50, 100)
    while len(negative_edges) < negative_count and attempts < max_attempts:
        attempts += 1
        source_index = rng.randrange(len(nodes))
        target_index = rng.randrange(len(nodes))
        if source_index == target_index:
            continue
        pair = tuple(sorted((source_index, target_index)))
        if pair in observed_pairs:
            continue
        relation_index = rng.randrange(max(len(relation_names), 1))
        negative_edges.append((source_index, target_index, relation_index, 1.0))
        observed_pairs.add(pair)
    return positive_edges, negative_edges, relation_names


def _edge_tensors(torch, positive_edges, negative_edges, device: str):
    edge_rows = positive_edges + negative_edges
    if not edge_rows:
        empty_long = torch.empty(0, dtype=torch.long, device=device)
        empty_float = torch.empty(0, dtype=torch.float32, device=device)
        return empty_long, empty_long, empty_long, empty_float, empty_float
    sources = torch.as_tensor([row[0] for row in edge_rows], dtype=torch.long, device=device)
    targets = torch.as_tensor([row[1] for row in edge_rows], dtype=torch.long, device=device)
    relations = torch.as_tensor([row[2] for row in edge_rows], dtype=torch.long, device=device)
    labels = torch.as_tensor(
        [1.0] * len(positive_edges) + [0.0] * len(negative_edges),
        dtype=torch.float32,
        device=device,
    )
    weights = torch.as_tensor(
        [max(float(row[3]), 1e-6) for row in positive_edges] + [1.0] * len(negative_edges),
        dtype=torch.float32,
        device=device,
    )
    weights = weights / weights.mean().clamp_min(1e-6)
    return sources, targets, relations, labels, weights


def _edge_logits(embeddings, source_indices, target_indices, relation_indices, relation_bias):
    logits = (embeddings[source_indices] * embeddings[target_indices]).sum(dim=1)
    if relation_indices.numel() > 0:
        logits = logits + relation_bias[relation_indices]
    return logits


def _reconstruction_metrics(
    labels: np.ndarray,
    probabilities: np.ndarray,
    positive_count: int,
    negative_count: int,
) -> dict[str, object]:
    if labels.size == 0:
        return {
            "positive_edge_count": int(positive_count),
            "negative_edge_count": int(negative_count),
            "auc": None,
            "average_precision": None,
            "accuracy": None,
            "mean_positive_score": None,
            "mean_negative_score": None,
        }
    predictions = (probabilities >= 0.5).astype(int)
    positive_scores = probabilities[labels == 1]
    negative_scores = probabilities[labels == 0]
    auc = _roc_auc(labels, probabilities)
    ap = _average_precision(labels, probabilities)
    return {
        "positive_edge_count": int(positive_count),
        "negative_edge_count": int(negative_count),
        "auc": round(float(auc), 6) if auc is not None else None,
        "average_precision": round(float(ap), 6) if ap is not None else None,
        "accuracy": round(float(np.mean(predictions == labels)), 6),
        "mean_positive_score": round(float(np.mean(positive_scores)), 6) if positive_scores.size else None,
        "mean_negative_score": round(float(np.mean(negative_scores)), 6) if negative_scores.size else None,
    }


def _observed_edge_scores(
    graphs: Mapping[str, nx.Graph],
    nodes: Sequence[str],
    relation_names: Sequence[str],
    embeddings: np.ndarray,
    relation_bias: np.ndarray,
) -> dict[tuple[str, str], float]:
    node_index = {node: index for index, node in enumerate(nodes)}
    relation_index = {relation: index for index, relation in enumerate(relation_names)}
    edge_scores: dict[tuple[str, str], float] = {}
    for relation, graph in graphs.items():
        bias = float(relation_bias[relation_index[relation]]) if relation in relation_index else 0.0
        for source, target in graph.edges():
            if source not in node_index or target not in node_index:
                continue
            source_index = node_index[str(source)]
            target_index = node_index[str(target)]
            logit = float(np.dot(embeddings[source_index], embeddings[target_index]) + bias)
            score = 1.0 / (1.0 + math.exp(-max(min(logit, 60.0), -60.0)))
            key = _edge_key(str(source), str(target))
            edge_scores[key] = max(edge_scores.get(key, 0.0), score)
    return {key: round(value, 6) for key, value in edge_scores.items()}


def _normalized_adjacency_tensor(torch, graph: nx.Graph, nodes: Sequence[str], device: str):
    node_index = {node: index for index, node in enumerate(nodes)}
    rows: list[int] = []
    columns: list[int] = []
    values: list[float] = []
    for source, target, attrs in graph.edges(data=True):
        if source not in node_index or target not in node_index:
            continue
        source_index = node_index[str(source)]
        target_index = node_index[str(target)]
        weight = max(float(attrs.get("weight", 1.0)), 1e-6)
        rows.extend((source_index, target_index))
        columns.extend((target_index, source_index))
        values.extend((weight, weight))
    for index in range(len(nodes)):
        rows.append(index)
        columns.append(index)
        values.append(1.0)
    row_array = np.asarray(rows, dtype=np.int64)
    value_array = np.asarray(values, dtype=np.float32)
    degree = np.bincount(row_array, weights=value_array, minlength=len(nodes)).astype(np.float32)
    degree[degree <= 0.0] = 1.0
    normalized_values = value_array / degree[row_array]
    indices = torch.as_tensor(np.vstack([row_array, np.asarray(columns, dtype=np.int64)]), dtype=torch.long, device=device)
    tensor_values = torch.as_tensor(normalized_values, dtype=torch.float32, device=device)
    return torch.sparse_coo_tensor(indices, tensor_values, (len(nodes), len(nodes)), device=device).coalesce()


def _relation_names(graphs: Mapping[str, nx.Graph]) -> list[str]:
    return [relation for relation, graph in graphs.items() if graph.number_of_edges() > 0] or list(graphs) or ["empty_relation"]


class HANRelationDiscoverEncoder:
    """Legacy relation-level semantic attention encoder kept as an ablation."""

    def __init__(self, config: DeepGraphDiscoverConfig):
        self.config = config

    def fit(
        self,
        graphs: Mapping[str, nx.Graph],
        nodes: Sequence[str],
        features: np.ndarray,
    ) -> DeepGraphDiscoverResult:
        torch, nn, functional = _require_torch()
        _seed_everything(torch, self.config.seed)

        nodes = [str(node) for node in nodes]
        features = _ensure_features(features, len(nodes))
        device = _resolve_device(torch, self.config.device)
        positive_edges, negative_edges, relation_names = _sample_training_edges(
            graphs,
            nodes,
            negative_ratio=self.config.negative_ratio,
            seed=self.config.seed,
        )
        if not relation_names:
            relation_names = _relation_names(graphs)
        adjacency_tensors = [
            _normalized_adjacency_tensor(torch, graphs.get(relation, nx.Graph()), nodes, device)
            for relation in relation_names
        ]
        model = _HANRelationModel(
            input_dim=features.shape[1],
            hidden_dim=max(1, int(self.config.hidden_dim)),
            embedding_dim=max(1, int(self.config.embedding_dim)),
            relation_count=len(relation_names),
            dropout=float(self.config.dropout),
            nn=nn,
            functional=functional,
        ).to(device)
        result = _train_edge_reconstruction(
            torch=torch,
            nn=nn,
            functional=functional,
            model=model,
            model_inputs=(torch.as_tensor(features, dtype=torch.float32, device=device), adjacency_tensors),
            relation_names=relation_names,
            graphs=graphs,
            nodes=nodes,
            positive_edges=positive_edges,
            negative_edges=negative_edges,
            config=self.config,
            device=device,
            encoder_name="han_relation",
        )
        result.relation_attention = result.metapath_attention.copy()
        return result


class HANDiscoverEncoder:
    """Metapath HAN: node-level attention inside U-O-U metapaths plus semantic attention."""

    def __init__(self, config: DeepGraphDiscoverConfig):
        self.config = config

    def fit(
        self,
        graphs: Mapping[str, nx.Graph],
        nodes: Sequence[str],
        features: np.ndarray,
    ) -> DeepGraphDiscoverResult:
        torch, nn, functional = _require_torch()
        _seed_everything(torch, self.config.seed)

        nodes = [str(node) for node in nodes]
        features = _ensure_features(features, len(nodes))
        device = _resolve_device(torch, self.config.device)
        positive_edges, negative_edges, relation_names = _sample_training_edges(
            graphs,
            nodes,
            negative_ratio=self.config.negative_ratio,
            seed=self.config.seed,
        )
        if not relation_names:
            relation_names = _relation_names(graphs)
        adjacency_tensors = [
            _normalized_adjacency_tensor(torch, graphs.get(relation, nx.Graph()), nodes, device)
            for relation in relation_names
        ]
        model = _MetapathHANModel(
            input_dim=features.shape[1],
            hidden_dim=max(1, int(self.config.hidden_dim)),
            embedding_dim=max(1, int(self.config.embedding_dim)),
            metapath_count=len(relation_names),
            dropout=float(self.config.dropout),
            nn=nn,
            functional=functional,
        ).to(device)
        return _train_edge_reconstruction(
            torch=torch,
            nn=nn,
            functional=functional,
            model=model,
            model_inputs=(torch.as_tensor(features, dtype=torch.float32, device=device), adjacency_tensors),
            relation_names=relation_names,
            graphs=graphs,
            nodes=nodes,
            positive_edges=positive_edges,
            negative_edges=negative_edges,
            config=self.config,
            device=device,
            encoder_name="han",
        )


class MAGNNDiscoverEncoder:
    """MAGNN-style U-O-U instance aggregation with inter-metapath semantic attention."""

    def __init__(self, config: DeepGraphDiscoverConfig, *, legacy: bool = False):
        self.config = config
        self.legacy = legacy

    def fit(
        self,
        graphs: Mapping[str, nx.Graph],
        nodes: Sequence[str],
        features: np.ndarray,
    ) -> DeepGraphDiscoverResult:
        torch, nn, functional = _require_torch()
        _seed_everything(torch, self.config.seed)

        nodes = [str(node) for node in nodes]
        features = _ensure_features(features, len(nodes))
        device = _resolve_device(torch, self.config.device)
        positive_edges, negative_edges, relation_names = _sample_training_edges(
            graphs,
            nodes,
            negative_ratio=self.config.negative_ratio,
            seed=self.config.seed,
        )
        if not relation_names:
            relation_names = _relation_names(graphs)
        metapath_tensors, object_index, instance_counts = _magnn_metapath_instance_tensors(
            torch,
            graphs,
            relation_names,
            nodes,
            device,
        )
        model_class = _LegacyMAGNNModel if self.legacy else _MAGNNModel
        encoder_name = "magnn_legacy" if self.legacy else "magnn"
        model = model_class(
            input_dim=features.shape[1],
            hidden_dim=max(1, int(self.config.hidden_dim)),
            embedding_dim=max(1, int(self.config.embedding_dim)),
            metapath_count=len(relation_names),
            object_count=max(1, len(object_index)),
            dropout=float(self.config.dropout),
            nn=nn,
            functional=functional,
        ).to(device)
        result = _train_edge_reconstruction(
            torch=torch,
            nn=nn,
            functional=functional,
            model=model,
            model_inputs=(torch.as_tensor(features, dtype=torch.float32, device=device), metapath_tensors),
            relation_names=relation_names,
            graphs=graphs,
            nodes=nodes,
            positive_edges=positive_edges,
            negative_edges=negative_edges,
            config=self.config,
            device=device,
            encoder_name=encoder_name,
        )
        result.metapath_instance_counts = instance_counts
        result.object_node_count = len(object_index)
        result.reconstruction_metrics = {
            **result.reconstruction_metrics,
            "object_node_count": len(object_index),
            "metapath_instance_count": int(sum(instance_counts.values())),
        }
        return result


class AMDNHAGEDiscoverEncoder:
    """AMDN-HAGE-inspired temporal hidden group baseline for label-free discovery."""

    def __init__(self, config: DeepGraphDiscoverConfig):
        self.config = config

    def fit(
        self,
        graphs: Mapping[str, nx.Graph],
        nodes: Sequence[str],
        features: np.ndarray,
    ) -> DeepGraphDiscoverResult:
        torch, nn, functional = _require_torch()
        _seed_everything(torch, self.config.seed)

        nodes = [str(node) for node in nodes]
        features = _ensure_features(features, len(nodes))
        device = _resolve_device(torch, self.config.device)
        positive_edges, negative_edges, relation_names = _sample_training_edges(
            graphs,
            nodes,
            negative_ratio=self.config.negative_ratio,
            seed=self.config.seed,
        )
        if not relation_names:
            relation_names = _relation_names(graphs)
        event_features = _temporal_event_features(graphs, nodes, relation_names, self.config.hidden_dim)
        model = _AMDNHAGEModel(
            input_dim=features.shape[1] + event_features.shape[1],
            hidden_dim=max(1, int(self.config.hidden_dim)),
            embedding_dim=max(1, int(self.config.embedding_dim)),
            group_count=min(max(2, int(math.sqrt(max(len(nodes), 2)))), 32),
            dropout=float(self.config.dropout),
            nn=nn,
            functional=functional,
        ).to(device)
        model_features = np.concatenate([features, event_features], axis=1).astype(np.float32)
        feature_tensor = torch.as_tensor(model_features, dtype=torch.float32, device=device)
        relation_bias = nn.Parameter(torch.zeros(len(relation_names), dtype=torch.float32, device=device))
        optimizer = torch.optim.Adam(
            list(model.parameters()) + [relation_bias],
            lr=float(self.config.lr),
            weight_decay=float(self.config.weight_decay),
        )
        source_indices, target_indices, relation_indices, labels, weights = _edge_tensors(
            torch,
            positive_edges,
            negative_edges,
            device,
        )
        losses: list[float] = []
        temporal_losses: list[float] = []
        if labels.numel() > 0:
            for _ in range(max(0, int(self.config.epochs))):
                model.train()
                optimizer.zero_grad()
                embeddings, group_probabilities = model(feature_tensor)
                logits = _edge_logits(embeddings, source_indices, target_indices, relation_indices, relation_bias)
                reconstruction_loss = functional.binary_cross_entropy_with_logits(logits, labels, weight=weights)
                group_affinity = (group_probabilities[source_indices] * group_probabilities[target_indices]).sum(dim=1)
                temporal_loss = functional.binary_cross_entropy(
                    group_affinity.clamp(1e-6, 1 - 1e-6),
                    labels,
                    weight=weights,
                )
                loss = reconstruction_loss + 0.2 * temporal_loss
                loss.backward()
                optimizer.step()
                losses.append(float(loss.detach().cpu().item()))
                temporal_losses.append(float(temporal_loss.detach().cpu().item()))

        model.eval()
        with torch.no_grad():
            embeddings, group_probabilities = model(feature_tensor)
            if labels.numel() > 0:
                logits = _edge_logits(embeddings, source_indices, target_indices, relation_indices, relation_bias)
                probabilities = torch.sigmoid(logits).detach().cpu().numpy()
                label_values = labels.detach().cpu().numpy().astype(int)
            else:
                probabilities = np.asarray([], dtype=float)
                label_values = np.asarray([], dtype=int)
            embedding_values = embeddings.detach().cpu().numpy()
            group_values = group_probabilities.detach().cpu().numpy()
        metrics = _reconstruction_metrics(label_values, probabilities, len(positive_edges), len(negative_edges))
        edge_scores = _observed_edge_scores(
            graphs,
            nodes,
            relation_names,
            embedding_values,
            relation_bias.detach().cpu().numpy(),
        )
        group_assignments = {
            node: int(np.argmax(group_values[index])) for index, node in enumerate(nodes)
        }
        group_counts = Counter(group_assignments.values())
        relation_attention = _softmax_dict({
            relation: float(graphs.get(relation, nx.Graph()).number_of_edges())
            for relation in relation_names
        })
        return DeepGraphDiscoverResult(
            encoder="amdn_hage",
            embeddings=embedding_values,
            node_index={node: index for index, node in enumerate(nodes)},
            relation_attention=relation_attention,
            metapath_attention=relation_attention.copy(),
            edge_scores=edge_scores,
            training_loss=[round(value, 6) for value in losses],
            reconstruction_metrics={
                **metrics,
                "hidden_group_count": len(group_counts),
                "largest_hidden_group_size": max(group_counts.values(), default=0),
            },
            device=device,
            uses_labels=False,
            hidden_groups=group_assignments,
            temporal_nll=round(float(temporal_losses[-1]), 6) if temporal_losses else None,
        )


def run_deep_graph_discover(
    graphs: Mapping[str, nx.Graph],
    nodes: Sequence[str],
    features: np.ndarray,
    config: DeepGraphDiscoverConfig,
) -> DeepGraphDiscoverResult:
    if config.encoder == "han_relation":
        return HANRelationDiscoverEncoder(config).fit(graphs, nodes, features)
    if config.encoder == "han":
        return HANDiscoverEncoder(config).fit(graphs, nodes, features)
    if config.encoder == "magnn_legacy":
        return MAGNNDiscoverEncoder(config, legacy=True).fit(graphs, nodes, features)
    if config.encoder == "magnn":
        return MAGNNDiscoverEncoder(config).fit(graphs, nodes, features)
    if config.encoder == "amdn_hage":
        return AMDNHAGEDiscoverEncoder(config).fit(graphs, nodes, features)
    raise ValueError(
        "run_deep_graph_discover supports encoder='han_relation', 'han', 'magnn_legacy', 'magnn', or 'amdn_hage'."
    )


def _ensure_features(features: np.ndarray, node_count: int) -> np.ndarray:
    if features.size == 0:
        return np.ones((node_count, 1), dtype=np.float32)
    return np.asarray(features, dtype=np.float32)


def _seed_everything(torch, seed: int) -> None:
    torch.manual_seed(seed)
    random.seed(seed)
    np.random.seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


def _softmax_dict(scores: Mapping[str, float]) -> dict[str, float]:
    if not scores:
        return {}
    keys = list(scores)
    values = np.asarray([float(scores[key]) for key in keys], dtype=float)
    values = values - float(np.max(values))
    exp_values = np.exp(values)
    total = float(np.sum(exp_values)) or 1.0
    return {key: round(float(exp_values[index] / total), 6) for index, key in enumerate(keys)}


def _train_edge_reconstruction(
    *,
    torch,
    nn,
    functional,
    model,
    model_inputs,
    relation_names: Sequence[str],
    graphs: Mapping[str, nx.Graph],
    nodes: Sequence[str],
    positive_edges,
    negative_edges,
    config: DeepGraphDiscoverConfig,
    device: str,
    encoder_name: str,
) -> DeepGraphDiscoverResult:
    relation_bias = nn.Parameter(torch.zeros(len(relation_names), dtype=torch.float32, device=device))
    optimizer = torch.optim.Adam(
        list(model.parameters()) + [relation_bias],
        lr=float(config.lr),
        weight_decay=float(config.weight_decay),
    )
    source_indices, target_indices, relation_indices, labels, weights = _edge_tensors(
        torch,
        positive_edges,
        negative_edges,
        device,
    )
    losses: list[float] = []
    if labels.numel() > 0:
        for _ in range(max(0, int(config.epochs))):
            model.train()
            optimizer.zero_grad()
            embeddings, _ = model(*model_inputs)
            logits = _edge_logits(embeddings, source_indices, target_indices, relation_indices, relation_bias)
            loss = functional.binary_cross_entropy_with_logits(logits, labels, weight=weights)
            loss.backward()
            optimizer.step()
            losses.append(float(loss.detach().cpu().item()))

    model.eval()
    with torch.no_grad():
        embeddings, attention_bundle = model(*model_inputs)
        if labels.numel() > 0:
            logits = _edge_logits(embeddings, source_indices, target_indices, relation_indices, relation_bias)
            probabilities = torch.sigmoid(logits).detach().cpu().numpy()
            label_values = labels.detach().cpu().numpy().astype(int)
        else:
            probabilities = np.asarray([], dtype=float)
            label_values = np.asarray([], dtype=int)
        embedding_values = embeddings.detach().cpu().numpy()
    metapath_attention, intra_attention = _attention_bundle_to_dicts(attention_bundle, relation_names)
    attention_summary = _attention_bundle_summary(attention_bundle)
    metrics = {
        **_reconstruction_metrics(label_values, probabilities, len(positive_edges), len(negative_edges)),
        **attention_summary,
    }
    edge_scores = _observed_edge_scores(
        graphs,
        nodes,
        relation_names,
        embedding_values,
        relation_bias.detach().cpu().numpy(),
    )
    return DeepGraphDiscoverResult(
        encoder=encoder_name,
        embeddings=embedding_values,
        node_index={node: index for index, node in enumerate(nodes)},
        relation_attention=metapath_attention.copy(),
        metapath_attention=metapath_attention,
        intra_metapath_attention=intra_attention,
        edge_scores=edge_scores,
        training_loss=[round(value, 6) for value in losses],
        reconstruction_metrics=metrics,
        device=device,
        uses_labels=False,
        edge_score_source=f"{encoder_name}_edge_reconstruction",
    )


def _attention_bundle_to_dicts(attention_bundle, relation_names: Sequence[str]) -> tuple[dict[str, float], dict[str, float]]:
    if isinstance(attention_bundle, tuple):
        semantic_attention = attention_bundle[0]
        intra_attention = attention_bundle[1] if len(attention_bundle) > 1 else None
    else:
        semantic_attention, intra_attention = attention_bundle, None
    semantic_values = semantic_attention.detach().cpu().numpy() if hasattr(semantic_attention, "detach") else np.asarray(semantic_attention)
    metapath_attention = {
        relation: round(float(semantic_values[index]), 6)
        for index, relation in enumerate(relation_names)
    }
    intra_dict: dict[str, float] = {}
    if intra_attention is not None:
        values = intra_attention.detach().cpu().numpy() if hasattr(intra_attention, "detach") else np.asarray(intra_attention)
        for index, relation in enumerate(relation_names):
            if values.ndim == 0:
                intra_dict[relation] = round(float(values), 6)
            else:
                intra_dict[relation] = round(float(values[index]), 6)
    return metapath_attention, intra_dict


def _attention_bundle_summary(attention_bundle) -> dict[str, object]:
    if not isinstance(attention_bundle, tuple) or len(attention_bundle) < 3:
        return {}
    summary = attention_bundle[2]
    return dict(summary) if isinstance(summary, Mapping) else {}


def _magnn_metapath_tensors(torch, graph: nx.Graph, nodes: Sequence[str], device: str):
    node_index = {node: index for index, node in enumerate(nodes)}
    rows: list[int] = []
    columns: list[int] = []
    values: list[float] = []
    instance_counts = np.zeros(len(nodes), dtype=np.float32)
    for source, target, attrs in graph.edges(data=True):
        if source not in node_index or target not in node_index:
            continue
        source_index = node_index[str(source)]
        target_index = node_index[str(target)]
        object_count = max(1, len(attrs.get("objects", [])) if isinstance(attrs.get("objects"), list) else 1)
        weight = max(float(attrs.get("weight", 1.0)), 1e-6)
        instance_weight = weight * math.log1p(object_count)
        rows.extend((source_index, target_index))
        columns.extend((target_index, source_index))
        values.extend((instance_weight, instance_weight))
        instance_counts[source_index] += object_count
        instance_counts[target_index] += object_count
    for index in range(len(nodes)):
        rows.append(index)
        columns.append(index)
        values.append(1.0)
        instance_counts[index] = max(instance_counts[index], 1.0)
    row_array = np.asarray(rows, dtype=np.int64)
    column_array = np.asarray(columns, dtype=np.int64)
    value_array = np.asarray(values, dtype=np.float32)
    degree = np.bincount(row_array, weights=value_array, minlength=len(nodes)).astype(np.float32)
    degree[degree <= 0.0] = 1.0
    normalized_values = value_array / degree[row_array]
    indices = torch.as_tensor(np.vstack([row_array, column_array]), dtype=torch.long, device=device)
    tensor_values = torch.as_tensor(normalized_values, dtype=torch.float32, device=device)
    adjacency = torch.sparse_coo_tensor(indices, tensor_values, (len(nodes), len(nodes)), device=device).coalesce()
    counts = torch.as_tensor(np.log1p(instance_counts), dtype=torch.float32, device=device).view(-1, 1)
    return adjacency, counts


def _edge_object_instances(relation: str, attrs: Mapping[str, object]) -> list[dict[str, object]]:
    raw_instances = attrs.get("object_instances", [])
    instances: list[dict[str, object]] = []
    if isinstance(raw_instances, list):
        for item in raw_instances:
            if not isinstance(item, Mapping):
                continue
            object_id = str(item.get("object_id", "")).strip()
            if not object_id:
                continue
            instances.append(
                {
                    "relation": str(item.get("relation", relation)),
                    "object_id": object_id,
                    "path_weight": max(float(item.get("path_weight", attrs.get("weight", 1.0))), 1e-6),
                }
            )
    if instances:
        return instances
    raw_objects = attrs.get("objects", [])
    if isinstance(raw_objects, (set, tuple, list)):
        for object_id in raw_objects:
            text = str(object_id).strip()
            if text:
                instances.append(
                    {
                        "relation": relation,
                        "object_id": text,
                        "path_weight": max(float(attrs.get("weight", 1.0)), 1e-6),
                    }
                )
    if instances:
        return instances
    return [
        {
            "relation": relation,
            "object_id": f"{relation}:edge:{attrs.get('weight', 1.0)}",
            "path_weight": max(float(attrs.get("weight", 1.0)), 1e-6),
        }
    ]


def _magnn_metapath_instance_tensors(
    torch,
    graphs: Mapping[str, nx.Graph],
    relation_names: Sequence[str],
    nodes: Sequence[str],
    device: str,
):
    """Build explicit U-O-U metapath instance tensors for MAGNN.

    Each row is one path instance (source user, object node, target user). The
    resulting tensors keep the object id as a separate embedding lookup instead
    of collapsing it into a projected user-user edge weight.
    """
    node_index = {node: index for index, node in enumerate(nodes)}
    object_index: dict[str, int] = {}
    metapath_tensors = []
    instance_counts: dict[str, int] = {}
    empty_long = torch.empty(0, dtype=torch.long, device=device)
    empty_float = torch.empty(0, dtype=torch.float32, device=device)

    for relation in relation_names:
        graph = graphs.get(relation, nx.Graph())
        sources: list[int] = []
        targets: list[int] = []
        objects: list[int] = []
        weights: list[float] = []
        for source, target, attrs in graph.edges(data=True):
            if source not in node_index or target not in node_index:
                continue
            source_index = node_index[str(source)]
            target_index = node_index[str(target)]
            for instance in _edge_object_instances(str(relation), attrs):
                object_key = f"{instance['relation']}:{instance['object_id']}"
                if object_key not in object_index:
                    object_index[object_key] = len(object_index)
                object_id = object_index[object_key]
                path_weight = max(float(instance.get("path_weight", attrs.get("weight", 1.0))), 1e-6)
                sources.extend((source_index, target_index))
                targets.extend((target_index, source_index))
                objects.extend((object_id, object_id))
                weights.extend((path_weight, path_weight))
        instance_counts[str(relation)] = len(weights)
        if weights:
            weight_array = np.asarray(weights, dtype=np.float32)
            weight_array = weight_array / max(float(weight_array.mean()), 1e-6)
            metapath_tensors.append(
                (
                    torch.as_tensor(sources, dtype=torch.long, device=device),
                    torch.as_tensor(targets, dtype=torch.long, device=device),
                    torch.as_tensor(objects, dtype=torch.long, device=device),
                    torch.as_tensor(weight_array, dtype=torch.float32, device=device),
                )
            )
        else:
            metapath_tensors.append((empty_long, empty_long, empty_long, empty_float))
    return metapath_tensors, object_index, instance_counts


def _temporal_event_features(
    graphs: Mapping[str, nx.Graph],
    nodes: Sequence[str],
    relation_names: Sequence[str],
    hidden_dim: int,
) -> np.ndarray:
    relation_index = {relation: index for index, relation in enumerate(relation_names)}
    width = max(4, min(max(8, hidden_dim), 64))
    features = np.zeros((len(nodes), width), dtype=np.float32)
    node_index = {node: index for index, node in enumerate(nodes)}
    for relation, graph in graphs.items():
        rel_idx = relation_index.get(relation, 0)
        for source, target, attrs in graph.edges(data=True):
            if source not in node_index or target not in node_index:
                continue
            objects = attrs.get("objects", []) if isinstance(attrs.get("objects", []), list) else []
            weight = max(float(attrs.get("weight", 1.0)), 1e-6)
            object_signal = sum(_stable_hash_bucket(str(obj), width) for obj in objects[:8]) if objects else rel_idx
            bucket = int((object_signal + rel_idx) % width)
            for node in (source, target):
                features[node_index[str(node)], bucket] += math.log1p(weight)
                features[node_index[str(node)], rel_idx % width] += 0.5
    if features.size:
        max_values = np.maximum(features.max(axis=0, keepdims=True), 1.0)
        features = features / max_values
    return features


class _HANRelationModel:
    def __new__(cls, *args, **kwargs):
        nn = kwargs.pop("nn")
        functional = kwargs.pop("functional")

        class HANRelationModule(nn.Module):
            def __init__(
                self,
                input_dim: int,
                hidden_dim: int,
                embedding_dim: int,
                relation_count: int,
                dropout: float,
            ):
                super().__init__()
                self.functional = functional
                self.input_projection = nn.Linear(input_dim, hidden_dim)
                self.relation_linears = nn.ModuleList(
                    [nn.Linear(hidden_dim, hidden_dim) for _ in range(relation_count)]
                )
                self.semantic_projection = nn.Linear(hidden_dim, hidden_dim)
                self.semantic_context = nn.Parameter(
                    nn.init.xavier_uniform_(__import__("torch").empty(hidden_dim, 1)).squeeze(1)
                )
                self.output_projection = nn.Linear(hidden_dim, embedding_dim)
                self.dropout = nn.Dropout(dropout)

            def forward(self, features, adjacency_tensors):
                torch = __import__("torch")
                base = self.functional.relu(self.input_projection(features))
                relation_outputs = []
                for relation_index, adjacency in enumerate(adjacency_tensors):
                    aggregated = torch.sparse.mm(adjacency, base)
                    relation_outputs.append(
                        self.functional.relu(self.relation_linears[relation_index](aggregated))
                    )
                stacked = torch.stack(relation_outputs, dim=1)
                semantic_hidden = torch.tanh(self.semantic_projection(stacked))
                semantic_scores = (semantic_hidden * self.semantic_context.view(1, 1, -1)).sum(dim=2)
                relation_scores = semantic_scores.mean(dim=0)
                attention = torch.softmax(relation_scores, dim=0)
                combined = (stacked * attention.view(1, -1, 1)).sum(dim=1)
                embeddings = self.output_projection(self.dropout(combined))
                return embeddings, attention

        return HANRelationModule(*args, **kwargs)


class _MetapathHANModel:
    def __new__(cls, *args, **kwargs):
        nn = kwargs.pop("nn")
        functional = kwargs.pop("functional")

        class MetapathHANModule(nn.Module):
            def __init__(
                self,
                input_dim: int,
                hidden_dim: int,
                embedding_dim: int,
                metapath_count: int,
                dropout: float,
            ):
                super().__init__()
                self.functional = functional
                self.input_projection = nn.Linear(input_dim, hidden_dim)
                self.node_attention = nn.ModuleList(
                    [nn.Linear(hidden_dim * 2, 1) for _ in range(metapath_count)]
                )
                self.metapath_linears = nn.ModuleList(
                    [nn.Linear(hidden_dim, hidden_dim) for _ in range(metapath_count)]
                )
                self.semantic_projection = nn.Linear(hidden_dim, hidden_dim)
                self.semantic_context = nn.Parameter(
                    nn.init.xavier_uniform_(__import__("torch").empty(hidden_dim, 1)).squeeze(1)
                )
                self.output_projection = nn.Linear(hidden_dim, embedding_dim)
                self.dropout = nn.Dropout(dropout)

            def forward(self, features, adjacency_tensors):
                torch = __import__("torch")
                base = self.functional.elu(self.input_projection(features))
                metapath_outputs = []
                intra_scores = []
                for index, adjacency in enumerate(adjacency_tensors):
                    neighbor_mean = torch.sparse.mm(adjacency, base)
                    attention_input = torch.cat([base, neighbor_mean], dim=1)
                    node_gate = torch.sigmoid(self.node_attention[index](attention_input))
                    attended = node_gate * neighbor_mean + (1.0 - node_gate) * base
                    metapath_outputs.append(
                        self.functional.elu(self.metapath_linears[index](attended))
                    )
                    intra_scores.append(node_gate.mean())
                stacked = torch.stack(metapath_outputs, dim=1)
                semantic_hidden = torch.tanh(self.semantic_projection(stacked))
                semantic_scores = (semantic_hidden * self.semantic_context.view(1, 1, -1)).sum(dim=2).mean(dim=0)
                semantic_attention = torch.softmax(semantic_scores, dim=0)
                combined = (stacked * semantic_attention.view(1, -1, 1)).sum(dim=1)
                embeddings = self.output_projection(self.dropout(combined))
                intra_attention = torch.stack(intra_scores)
                return embeddings, (semantic_attention, intra_attention)

        return MetapathHANModule(*args, **kwargs)


class _MAGNNModel:
    def __new__(cls, *args, **kwargs):
        nn = kwargs.pop("nn")
        functional = kwargs.pop("functional")

        class MAGNNModule(nn.Module):
            def __init__(
                self,
                input_dim: int,
                hidden_dim: int,
                embedding_dim: int,
                metapath_count: int,
                object_count: int,
                dropout: float,
            ):
                super().__init__()
                self.functional = functional
                self.content_transform = nn.Linear(input_dim, hidden_dim)
                self.object_embeddings = nn.Embedding(max(1, object_count), hidden_dim)
                self.instance_transforms = nn.ModuleList(
                    [nn.Linear(hidden_dim * 3, hidden_dim) for _ in range(metapath_count)]
                )
                self.instance_attention = nn.ModuleList(
                    [nn.Linear(hidden_dim * 2, 1) for _ in range(metapath_count)]
                )
                self.semantic_projection = nn.Linear(hidden_dim, hidden_dim)
                self.semantic_context = nn.Parameter(
                    nn.init.xavier_uniform_(__import__("torch").empty(hidden_dim, 1)).squeeze(1)
                )
                self.output_projection = nn.Linear(hidden_dim, embedding_dim)
                self.dropout = nn.Dropout(dropout)

            def forward(self, features, metapath_tensors):
                torch = __import__("torch")
                base = self.functional.elu(self.content_transform(features))
                metapath_outputs = []
                intra_scores = []
                intra_summary: dict[str, object] = {
                    "attention_mechanism": "target_grouped_softmax",
                    "mean_target_attention_entropy": [],
                    "max_instance_attention": [],
                }
                for index, (sources, targets, objects, weights) in enumerate(metapath_tensors):
                    if sources.numel() == 0:
                        metapath_outputs.append(base)
                        intra_scores.append(base.new_tensor(0.0))
                        intra_summary["mean_target_attention_entropy"].append(0.0)
                        intra_summary["max_instance_attention"].append(0.0)
                        continue
                    object_vectors = self.object_embeddings(objects)
                    path_input = torch.cat([base[sources], object_vectors, base[targets]], dim=1)
                    path_hidden = self.functional.elu(self.instance_transforms[index](path_input))
                    attention_input = torch.cat([path_hidden, base[targets]], dim=1)
                    attention_logits = self.instance_attention[index](attention_input).squeeze(1)
                    attention_logits = attention_logits + torch.log(weights.clamp_min(1e-6))
                    attention_values = torch.zeros_like(attention_logits)
                    entropy_values = []
                    for target_id in torch.unique(targets):
                        mask = targets == target_id
                        group_attention = torch.softmax(attention_logits[mask], dim=0)
                        attention_values[mask] = group_attention
                        entropy_values.append(
                            -(group_attention * torch.log(group_attention.clamp_min(1e-9))).sum()
                        )
                    messages = path_hidden * attention_values.view(-1, 1)
                    aggregated = torch.zeros_like(base)
                    normalizer = torch.zeros(base.shape[0], 1, dtype=base.dtype, device=base.device)
                    aggregated.index_add_(0, targets, messages)
                    normalizer.index_add_(0, targets, attention_values.view(-1, 1))
                    instance_mean = aggregated / normalizer.clamp_min(1e-6)
                    active_gate = (normalizer > 0.0).to(base.dtype)
                    metapath_outputs.append(active_gate * instance_mean + (1.0 - active_gate) * base)
                    intra_scores.append(attention_values.mean())
                    entropy_tensor = torch.stack(entropy_values) if entropy_values else attention_values.new_tensor([0.0])
                    intra_summary["mean_target_attention_entropy"].append(
                        round(float(entropy_tensor.mean().detach().cpu().item()), 6)
                    )
                    intra_summary["max_instance_attention"].append(
                        round(float(attention_values.max().detach().cpu().item()), 6)
                    )
                stacked = torch.stack(metapath_outputs, dim=1)
                semantic_hidden = torch.tanh(self.semantic_projection(stacked))
                semantic_scores = (semantic_hidden * self.semantic_context.view(1, 1, -1)).sum(dim=2).mean(dim=0)
                semantic_attention = torch.softmax(semantic_scores, dim=0)
                combined = (stacked * semantic_attention.view(1, -1, 1)).sum(dim=1)
                embeddings = self.output_projection(self.dropout(combined))
                intra_attention = torch.stack(intra_scores)
                return embeddings, (semantic_attention, intra_attention, intra_summary)

        return MAGNNModule(*args, **kwargs)


class _LegacyMAGNNModel:
    def __new__(cls, *args, **kwargs):
        nn = kwargs.pop("nn")
        functional = kwargs.pop("functional")

        class LegacyMAGNNModule(nn.Module):
            def __init__(
                self,
                input_dim: int,
                hidden_dim: int,
                embedding_dim: int,
                metapath_count: int,
                object_count: int,
                dropout: float,
            ):
                super().__init__()
                self.functional = functional
                self.content_transform = nn.Linear(input_dim, hidden_dim)
                self.object_embeddings = nn.Embedding(max(1, object_count), hidden_dim)
                self.instance_transforms = nn.ModuleList(
                    [nn.Linear(hidden_dim * 3, hidden_dim) for _ in range(metapath_count)]
                )
                self.instance_attention = nn.ModuleList(
                    [nn.Linear(hidden_dim * 2, 1) for _ in range(metapath_count)]
                )
                self.semantic_projection = nn.Linear(hidden_dim, hidden_dim)
                self.semantic_context = nn.Parameter(
                    nn.init.xavier_uniform_(__import__("torch").empty(hidden_dim, 1)).squeeze(1)
                )
                self.output_projection = nn.Linear(hidden_dim, embedding_dim)
                self.dropout = nn.Dropout(dropout)

            def forward(self, features, metapath_tensors):
                torch = __import__("torch")
                base = self.functional.elu(self.content_transform(features))
                metapath_outputs = []
                intra_scores = []
                for index, (sources, targets, objects, weights) in enumerate(metapath_tensors):
                    if sources.numel() == 0:
                        metapath_outputs.append(base)
                        intra_scores.append(base.new_tensor(0.0))
                        continue
                    object_vectors = self.object_embeddings(objects)
                    path_input = torch.cat([base[sources], object_vectors, base[targets]], dim=1)
                    path_hidden = self.functional.elu(self.instance_transforms[index](path_input))
                    attention_input = torch.cat([path_hidden, base[targets]], dim=1)
                    attention_logits = self.instance_attention[index](attention_input).squeeze(1)
                    attention_values = torch.sigmoid(attention_logits) * weights
                    messages = path_hidden * attention_values.view(-1, 1)
                    aggregated = torch.zeros_like(base)
                    normalizer = torch.zeros(base.shape[0], 1, dtype=base.dtype, device=base.device)
                    aggregated.index_add_(0, targets, messages)
                    normalizer.index_add_(0, targets, attention_values.view(-1, 1))
                    instance_mean = aggregated / normalizer.clamp_min(1e-6)
                    node_gate = torch.clamp(normalizer / normalizer.max().clamp_min(1e-6), 0.0, 1.0)
                    metapath_outputs.append(node_gate * instance_mean + (1.0 - node_gate) * base)
                    intra_scores.append(attention_values.mean())
                stacked = torch.stack(metapath_outputs, dim=1)
                semantic_hidden = torch.tanh(self.semantic_projection(stacked))
                semantic_scores = (semantic_hidden * self.semantic_context.view(1, 1, -1)).sum(dim=2).mean(dim=0)
                semantic_attention = torch.softmax(semantic_scores, dim=0)
                combined = (stacked * semantic_attention.view(1, -1, 1)).sum(dim=1)
                embeddings = self.output_projection(self.dropout(combined))
                intra_attention = torch.stack(intra_scores)
                return embeddings, (
                    semantic_attention,
                    intra_attention,
                    {"attention_mechanism": "sigmoid_gated_legacy"},
                )

        return LegacyMAGNNModule(*args, **kwargs)


class _AMDNHAGEModel:
    def __new__(cls, *args, **kwargs):
        nn = kwargs.pop("nn")
        functional = kwargs.pop("functional")

        class AMDNHAGEModule(nn.Module):
            def __init__(
                self,
                input_dim: int,
                hidden_dim: int,
                embedding_dim: int,
                group_count: int,
                dropout: float,
            ):
                super().__init__()
                self.functional = functional
                self.encoder = nn.Sequential(
                    nn.Linear(input_dim, hidden_dim),
                    nn.ReLU(),
                    nn.Dropout(dropout),
                    nn.Linear(hidden_dim, embedding_dim),
                )
                self.group_head = nn.Linear(embedding_dim, group_count)

            def forward(self, features):
                embeddings = self.encoder(features)
                groups = self.functional.softmax(self.group_head(embeddings), dim=1)
                return embeddings, groups

        return AMDNHAGEModule(*args, **kwargs)
