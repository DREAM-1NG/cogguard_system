from __future__ import annotations

import hashlib
import importlib.util
import math
import time
from collections.abc import Mapping as MappingABC
from dataclasses import dataclass, field, replace
from types import MappingProxyType
from typing import Any, Mapping

import numpy as np
import pandas as pd

from research.coordination_discover.stage1.contracts import (
    CoordinationMetricSet,
    DiscoveredCluster,
    DiscoveredClusterBatch,
    DiscoveryProvenance,
    DiscoveryRuntimeDiagnostics,
)

from .baselines import DiscoveryImplementation
from .compact_execution import (
    CompactDiscoveryExecutionInput,
    CompactDiscoveryPrediction,
)
from .iohunter import IOHUNTER_LAYER_RELATIONS
from .iohunter_compact import IOHUNTER_STATIC_TIME_SEMANTICS


_RELATION_LAYERS = tuple(IOHUNTER_LAYER_RELATIONS)
_RELATION_NAMES = tuple(IOHUNTER_LAYER_RELATIONS[layer] for layer in _RELATION_LAYERS)
_STATIC_CLAIM_MARKER = "static_placeholder_not_observed_time"
_EXPLICIT_UNION_GUARANTEE_SCOPE = "explicit_compact_source_union"
_EXACT_BACKEND = "exact_laplacian_pseudoinverse"
_APPROXIMATE_BACKEND = "degree_leverage_approximation"
_PRODUCTION_STATIC_PROXY_MAX_OCCURRENCES = 100_000
_COMPACT_METHOD_VARIANTS = frozenset(
    {
        "tsgs_mhcr_compact",
        "frozen_system_evidence_prior",
        "frozen_system_account_score_prior",
        "magnn_legacy",
        "edgebank",
        "dense_cosine_leiden",
        "magnn_leiden_hybrid_discovery",
        "no_tsgs",
        "no_mhcr",
        "no_relation_specific",
        "no_temporal_augmentation",
        "tgn_style_memory_prior",
    }
)
_EXECUTION_CONFIG_OVERRIDES = frozenset(
    {
        "seed",
        "max_candidate_edges",
        "hidden_dimension",
        "epochs",
        "batch_size",
        "edge_dropout_rate",
        "feature_mask_rate",
        "temperature",
        "exact_pseudoinverse_node_limit",
        "dense_feasible_account_limit",
    }
)


class CompactDiscoveryMethodBlocked(RuntimeError):
    """Signals a declared dataset or feasibility block, not a failed model run."""


def _positive_int(value: Any, field_name: str, *, minimum: int = 1) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise ValueError(f"{field_name} must be an integer >= {minimum}")
    return value


def _unit_interval(value: Any, field_name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{field_name} must be numeric")
    number = float(value)
    if not math.isfinite(number) or number < 0.0 or number > 1.0:
        raise ValueError(f"{field_name} must be finite within [0, 1]")
    return number


def _positive_float(value: Any, field_name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{field_name} must be numeric")
    number = float(value)
    if not math.isfinite(number) or number <= 0.0:
        raise ValueError(f"{field_name} must be finite and positive")
    return number


def _readonly(values: np.ndarray, dtype: np.dtype, shape: tuple[int, ...]) -> np.ndarray:
    normalized = np.ascontiguousarray(values, dtype=dtype).reshape(shape)
    result = np.frombuffer(normalized.tobytes(order="C"), dtype=dtype).reshape(shape)
    if result.flags.writeable:
        raise RuntimeError("immutable compact array backing was not established")
    return result


def _normalized(values: np.ndarray) -> np.ndarray:
    maximum = float(np.max(values)) if values.size else 0.0
    if maximum <= 0.0:
        return np.zeros(values.shape, dtype=np.float32)
    return (values / maximum).astype(np.float32, copy=False)


def _row_normalize(values: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(values, axis=1, keepdims=True)
    return values / np.maximum(norms, np.finfo(np.float32).eps)


def _config_fingerprint(config: "CompactDiscoveryMethodConfig") -> str:
    payload = repr(config).encode("utf-8")
    return "sha256:" + hashlib.sha256(payload).hexdigest()


@dataclass(frozen=True, slots=True)
class CompactDiscoveryMethodConfig:
    method_variant: str
    seed: int = 0
    max_candidate_edges: int = 100_000
    hidden_dimension: int = 16
    epochs: int = 3
    batch_size: int = 512
    edge_dropout_rate: float = 0.12
    feature_mask_rate: float = 0.10
    temperature: float = 0.20
    exact_pseudoinverse_node_limit: int = 256
    dense_feasible_account_limit: int = 2_048

    def __post_init__(self) -> None:
        if self.method_variant not in _COMPACT_METHOD_VARIANTS:
            raise ValueError("method_variant must be a supported compact Discovery method")
        if isinstance(self.seed, bool) or not isinstance(self.seed, int) or self.seed < 0:
            raise ValueError("seed must be a non-negative integer")
        for field_name, minimum in (
            ("max_candidate_edges", 1),
            ("hidden_dimension", 2),
            ("epochs", 1),
            ("batch_size", 2),
            ("exact_pseudoinverse_node_limit", 2),
            ("dense_feasible_account_limit", 2),
        ):
            object.__setattr__(
                self,
                field_name,
                _positive_int(getattr(self, field_name), field_name, minimum=minimum),
            )
        object.__setattr__(self, "edge_dropout_rate", _unit_interval(self.edge_dropout_rate, "edge_dropout_rate"))
        object.__setattr__(self, "feature_mask_rate", _unit_interval(self.feature_mask_rate, "feature_mask_rate"))
        object.__setattr__(self, "temperature", _positive_float(self.temperature, "temperature"))


@dataclass(frozen=True, slots=True)
class _FusedCompactGraph:
    endpoints: np.ndarray
    weights: np.ndarray
    relation_weights: np.ndarray
    source_layer_counts: Mapping[str, int]
    duplicate_relation_edges_collapsed: int


def _fuse_relation_layers(execution_input: CompactDiscoveryExecutionInput) -> _FusedCompactGraph:
    view = execution_input.discovery_view
    source_parts: list[np.ndarray] = []
    target_parts: list[np.ndarray] = []
    relation_parts: list[np.ndarray] = []
    weight_parts: list[np.ndarray] = []
    source_layer_counts: dict[str, int] = {}
    for relation_index, layer in enumerate(_RELATION_LAYERS):
        compact_edges = view.relation_edges[layer]
        endpoints = compact_edges.endpoints
        weights = compact_edges.weights.astype(np.float64, copy=False)
        if endpoints.shape[0] != weights.shape[0]:
            raise ValueError("compact relation endpoints and weights are not aligned")
        if endpoints.size and int(np.max(endpoints)) >= view.account_count:
            raise ValueError("compact relation endpoint is outside the canonical account universe")
        valid = np.isfinite(weights) & (weights > 0.0) & (endpoints[:, 0] != endpoints[:, 1])
        canonical = endpoints[valid].astype(np.uint32, copy=False)
        if canonical.size:
            source = np.minimum(canonical[:, 0], canonical[:, 1])
            target = np.maximum(canonical[:, 0], canonical[:, 1])
            retained_weights = weights[valid]
            maximum = float(np.max(retained_weights))
            normalized_weights = (retained_weights / maximum).astype(np.float32, copy=False)
        else:
            source = np.empty(0, dtype=np.uint32)
            target = np.empty(0, dtype=np.uint32)
            normalized_weights = np.empty(0, dtype=np.float32)
        source_parts.append(source)
        target_parts.append(target)
        relation_parts.append(np.full(source.shape, relation_index, dtype=np.uint8))
        weight_parts.append(normalized_weights)
        source_layer_counts[layer] = int(source.size)
    if not source_parts or not any(part.size for part in source_parts):
        return _FusedCompactGraph(
            endpoints=_readonly(np.empty((0, 2)), np.dtype("<u2"), (0, 2)),
            weights=_readonly(np.empty(0), np.dtype("<f4"), (0,)),
            relation_weights=_readonly(np.empty((0, len(_RELATION_LAYERS))), np.dtype("<f4"), (0, len(_RELATION_LAYERS))),
            source_layer_counts=MappingProxyType(source_layer_counts),
            duplicate_relation_edges_collapsed=0,
        )
    source = np.concatenate(source_parts)
    target = np.concatenate(target_parts)
    relation = np.concatenate(relation_parts)
    normalized_weight = np.concatenate(weight_parts)
    order = np.lexsort((relation, target, source))
    source = source[order]
    target = target[order]
    relation = relation[order]
    normalized_weight = normalized_weight[order]
    relation_starts = np.flatnonzero(
        np.r_[True, (source[1:] != source[:-1]) | (target[1:] != target[:-1]) | (relation[1:] != relation[:-1])]
    )
    source = source[relation_starts]
    target = target[relation_starts]
    relation = relation[relation_starts]
    normalized_weight = np.add.reduceat(normalized_weight, relation_starts).astype(np.float32)
    pair_starts = np.flatnonzero(
        np.r_[True, (source[1:] != source[:-1]) | (target[1:] != target[:-1])]
    )
    pair_index = np.cumsum(
        np.r_[True, (source[1:] != source[:-1]) | (target[1:] != target[:-1])]
    ).astype(np.int64) - 1
    pair_count = int(pair_starts.size)
    relation_weights = np.zeros((pair_count, len(_RELATION_LAYERS)), dtype=np.float32)
    np.add.at(relation_weights, (pair_index, relation.astype(np.int64)), normalized_weight)
    endpoints = np.column_stack((source[pair_starts], target[pair_starts]))
    relation_presence = np.count_nonzero(relation_weights, axis=1).astype(np.float32)
    weights = relation_weights.sum(axis=1) / np.sqrt(np.maximum(relation_presence, 1.0))
    index_dtype = np.dtype("<u2") if view.account_count <= np.iinfo(np.uint16).max + 1 else np.dtype("<u4")
    return _FusedCompactGraph(
        endpoints=_readonly(endpoints, index_dtype, (pair_count, 2)),
        weights=_readonly(weights, np.dtype("<f4"), (pair_count,)),
        relation_weights=_readonly(
            relation_weights,
            np.dtype("<f4"),
            (pair_count, len(_RELATION_LAYERS)),
        ),
        source_layer_counts=MappingProxyType(dict(source_layer_counts)),
        duplicate_relation_edges_collapsed=int(len(order) - len(relation_starts)),
    )


def _weighted_degree(account_count: int, endpoints: np.ndarray, weights: np.ndarray) -> np.ndarray:
    degree = np.zeros(account_count, dtype=np.float32)
    if endpoints.size:
        np.add.at(degree, endpoints[:, 0], weights)
        np.add.at(degree, endpoints[:, 1], weights)
    return degree


def _edge_selection(
    graph: _FusedCompactGraph,
    account_count: int,
    config: CompactDiscoveryMethodConfig,
    effective_seed: int,
    *,
    use_tsgs: bool,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, Mapping[str, Any]]:
    edge_count = int(graph.endpoints.shape[0])
    if edge_count == 0:
        empty_endpoints = np.empty((0, 2), dtype=graph.endpoints.dtype)
        empty_weights = np.empty(0, dtype=np.float32)
        empty_relations = np.empty((0, len(_RELATION_LAYERS)), dtype=np.float32)
        return empty_endpoints, empty_weights, empty_relations, MappingProxyType(
            {
                "resistance_backend": "not_run_empty_union",
                "spectral_guarantee": "not_applicable_empty_union",
                "guarantee_scope": _EXPLICIT_UNION_GUARANTEE_SCOPE,
                "input_union_edge_count": 0,
                "retained_edge_count": 0,
                "candidate_recall": 1.0,
            }
        )
    if not use_tsgs:
        order = np.lexsort((graph.endpoints[:, 1], graph.endpoints[:, 0], -graph.weights))
        selected = order[: config.max_candidate_edges]
        selected.sort()
        return (
            graph.endpoints[selected],
            graph.weights[selected],
            graph.relation_weights[selected],
            MappingProxyType(
                {
                    "resistance_backend": "not_run_input_union",
                    "spectral_guarantee": "not_run_ablation",
                    "guarantee_scope": _EXPLICIT_UNION_GUARANTEE_SCOPE,
                    "input_union_edge_count": edge_count,
                    "retained_edge_count": int(selected.size),
                    "candidate_recall": float(selected.size) / edge_count,
                }
            ),
        )
    degree = _weighted_degree(account_count, graph.endpoints, graph.weights)
    if account_count <= config.exact_pseudoinverse_node_limit:
        laplacian = np.zeros((account_count, account_count), dtype=np.float64)
        source = graph.endpoints[:, 0]
        target = graph.endpoints[:, 1]
        weights = graph.weights.astype(np.float64)
        np.add.at(laplacian, (source, source), weights)
        np.add.at(laplacian, (target, target), weights)
        np.add.at(laplacian, (source, target), -weights)
        np.add.at(laplacian, (target, source), -weights)
        pseudoinverse = np.linalg.pinv(laplacian, hermitian=True)
        resistance = (
            pseudoinverse[source, source]
            + pseudoinverse[target, target]
            - 2.0 * pseudoinverse[source, target]
        )
        leverage = np.maximum(weights * np.maximum(resistance, 0.0), np.finfo(np.float64).eps)
        backend = _EXACT_BACKEND
        guarantee = "exact_for_explicit_compact_source_union"
    else:
        source = graph.endpoints[:, 0]
        target = graph.endpoints[:, 1]
        leverage = graph.weights.astype(np.float64) * (
            1.0 / np.maximum(degree[source], np.finfo(np.float32).eps)
            + 1.0 / np.maximum(degree[target], np.finfo(np.float32).eps)
        )
        leverage = np.maximum(leverage, np.finfo(np.float64).eps)
        backend = _APPROXIMATE_BACKEND
        guarantee = "approximate_no_exact_guarantee"
    if edge_count <= config.max_candidate_edges:
        selected = np.arange(edge_count, dtype=np.int64)
        reweighted = graph.weights.copy()
    else:
        probabilities = leverage / np.sum(leverage)
        generator = np.random.default_rng(effective_seed)
        priorities = -np.log(
            np.maximum(generator.random(edge_count), np.finfo(np.float64).tiny)
        ) / probabilities
        selected = np.argpartition(priorities, config.max_candidate_edges - 1)[: config.max_candidate_edges]
        selected.sort()
        inclusion = np.minimum(1.0, config.max_candidate_edges * probabilities[selected])
        reweighted = graph.weights[selected] / inclusion.astype(np.float32)
    retained = int(selected.size)
    return (
        graph.endpoints[selected],
        reweighted.astype(np.float32, copy=False),
        graph.relation_weights[selected],
        MappingProxyType(
            {
                "resistance_backend": backend,
                "spectral_guarantee": guarantee,
                "guarantee_scope": _EXPLICIT_UNION_GUARANTEE_SCOPE,
                "input_union_edge_count": edge_count,
                "retained_edge_count": retained,
                "candidate_recall": float(retained) / edge_count,
                "sparsification_needed": edge_count > config.max_candidate_edges,
                "reference_weight_sum": float(np.sum(graph.weights)),
                "retained_weight_sum": float(np.sum(reweighted)),
            }
        ),
    )


def _relation_features(
    account_count: int,
    endpoints: np.ndarray,
    relation_weights: np.ndarray,
) -> np.ndarray:
    relation_count = len(_RELATION_LAYERS)
    weighted_degree = np.zeros((account_count, relation_count), dtype=np.float32)
    incident_count = np.zeros((account_count, relation_count), dtype=np.float32)
    for relation_index in range(relation_count):
        weights = relation_weights[:, relation_index]
        present = weights > 0.0
        source = endpoints[present, 0]
        target = endpoints[present, 1]
        current = weights[present]
        np.add.at(weighted_degree[:, relation_index], source, current)
        np.add.at(weighted_degree[:, relation_index], target, current)
        np.add.at(incident_count[:, relation_index], source, 1.0)
        np.add.at(incident_count[:, relation_index], target, 1.0)
    features = np.concatenate((np.log1p(weighted_degree), np.log1p(incident_count)), axis=1)
    scale = np.maximum(np.max(features, axis=0, keepdims=True), np.finfo(np.float32).eps)
    return (features / scale).astype(np.float32, copy=False)


def _relation_edge_arrays(
    endpoints: np.ndarray,
    relation_weights: np.ndarray,
) -> tuple[tuple[np.ndarray, np.ndarray, np.ndarray], ...]:
    result = []
    for relation_index in range(len(_RELATION_LAYERS)):
        weights = relation_weights[:, relation_index]
        present = weights > 0.0
        result.append(
            (
                endpoints[present, 0].astype(np.int64, copy=False),
                endpoints[present, 1].astype(np.int64, copy=False),
                weights[present].astype(np.float32, copy=False),
            )
        )
    return tuple(result)


def _relation_feature_names() -> list[str]:
    return [
        f"{layer}_{relation}_{kind}"
        for kind in ("weighted_degree", "incident_count")
        for layer, relation in zip(_RELATION_LAYERS, _RELATION_NAMES, strict=True)
    ]


def _mhcr_embeddings(
    features: np.ndarray,
    relation_edges: tuple[tuple[np.ndarray, np.ndarray, np.ndarray], ...],
    config: CompactDiscoveryMethodConfig,
    effective_seed: int,
    *,
    relation_specific: bool,
) -> tuple[np.ndarray, Mapping[str, Any]]:
    try:
        import torch
        from torch.nn import functional as functional
    except ImportError as exc:
        raise CompactDiscoveryMethodBlocked("MHCR requires the optional torch dependency") from exc
    account_count, feature_count = features.shape
    hidden_dimension = config.hidden_dimension
    generator = torch.Generator(device="cpu")
    generator.manual_seed(effective_seed)
    input_features = torch.as_tensor(features, dtype=torch.float32)
    base = torch.nn.Parameter(
        torch.randn(feature_count, hidden_dimension, generator=generator, dtype=torch.float32) / math.sqrt(feature_count)
    )
    transform_count = len(_RELATION_LAYERS) if relation_specific else 1
    relation_transform = torch.nn.Parameter(
        torch.randn(transform_count, feature_count, hidden_dimension, generator=generator, dtype=torch.float32)
        / math.sqrt(feature_count)
    )
    optimizer = torch.optim.Adam((base, relation_transform), lr=0.02)
    relation_tensors = tuple(
        (
            torch.as_tensor(source, dtype=torch.int64),
            torch.as_tensor(target, dtype=torch.int64),
            torch.as_tensor(weight, dtype=torch.float32),
        )
        for source, target, weight in relation_edges
    )

    def encode(feature_view: torch.Tensor, dropout_seed: int, dropout_rate: float) -> torch.Tensor:
        aggregate = torch.zeros((account_count, hidden_dimension), dtype=torch.float32)
        normalization = torch.zeros((account_count, 1), dtype=torch.float32)
        local_generator = torch.Generator(device="cpu")
        local_generator.manual_seed(dropout_seed)
        for relation_index, (source, target, weights) in enumerate(relation_tensors):
            if weights.numel() == 0:
                continue
            keep = torch.rand(weights.numel(), generator=local_generator) >= dropout_rate
            if not bool(torch.any(keep)):
                continue
            kept_source = source[keep]
            kept_target = target[keep]
            kept_weights = weights[keep]
            transform_index = relation_index if relation_specific else 0
            messages = feature_view @ relation_transform[transform_index]
            aggregate.index_add_(0, kept_source, messages[kept_target] * kept_weights[:, None])
            aggregate.index_add_(0, kept_target, messages[kept_source] * kept_weights[:, None])
            normalization.index_add_(0, kept_source, kept_weights[:, None])
            normalization.index_add_(0, kept_target, kept_weights[:, None])
        return torch.tanh(feature_view @ base + aggregate / normalization.clamp_min(1.0))

    losses = []
    for epoch in range(config.epochs):
        mask_a = (torch.rand(feature_count, generator=generator) >= config.feature_mask_rate).to(torch.float32)
        mask_b = (torch.rand(feature_count, generator=generator) >= config.feature_mask_rate).to(torch.float32)
        embedding_a = encode(input_features * mask_a, effective_seed + 101 * epoch + 1, config.edge_dropout_rate)
        embedding_b = encode(input_features * mask_b, effective_seed + 101 * epoch + 2, config.edge_dropout_rate)
        batch_size = min(config.batch_size, account_count)
        if batch_size < 2:
            losses.append(0.0)
            continue
        batch = torch.randperm(account_count, generator=generator)[:batch_size]
        normalized_a = functional.normalize(embedding_a[batch], p=2.0, dim=1)
        normalized_b = functional.normalize(embedding_b[batch], p=2.0, dim=1)
        logits = normalized_a @ normalized_b.T / config.temperature
        targets = torch.arange(batch_size, dtype=torch.int64)
        loss = 0.5 * (functional.cross_entropy(logits, targets) + functional.cross_entropy(logits.T, targets))
        optimizer.zero_grad(set_to_none=True)
        loss.backward()
        optimizer.step()
        losses.append(float(loss.detach().cpu()))
    with torch.no_grad():
        embeddings = encode(input_features, effective_seed + 10_000, 0.0)
    diagnostics = MappingProxyType(
        {
            "objective": "self_supervised_infonce",
            "relation_transform_count": transform_count,
            "relation_specific": relation_specific,
            "batch_negatives": min(config.batch_size, account_count) - 1,
            "seed": effective_seed,
            "feature_names": _relation_feature_names(),
            "augmentation": {
                "relation_edge_dropout": config.edge_dropout_rate,
                "feature_mask_rate": config.feature_mask_rate,
            },
            "epoch_infonce_losses": losses,
            "evaluator_labels_absent": True,
        }
    )
    return embeddings.cpu().numpy().astype(np.float32, copy=False), diagnostics


def _input_embeddings(features: np.ndarray) -> tuple[np.ndarray, Mapping[str, Any]]:
    return _row_normalize(features.astype(np.float32, copy=False)), MappingProxyType(
        {
            "objective": "not_run_normalized_input_representation",
            "relation_transform_count": 0,
            "relation_specific": False,
            "batch_negatives": 0,
            "feature_names": _relation_feature_names(),
            "augmentation": {"relation_edge_dropout": 0.0, "feature_mask_rate": 0.0},
            "evaluator_labels_absent": True,
        }
    )


def _magnn_leiden_embeddings(
    features: np.ndarray,
    relation_edges: tuple[tuple[np.ndarray, np.ndarray, np.ndarray], ...],
    config: CompactDiscoveryMethodConfig,
    effective_seed: int,
) -> tuple[np.ndarray, Mapping[str, Any]]:
    try:
        import torch
        from torch.nn import functional as functional
    except ImportError as exc:
        raise CompactDiscoveryMethodBlocked("MAGNN-Leiden hybrid requires the optional torch dependency") from exc
    account_count, feature_count = features.shape
    hidden_dimension = config.hidden_dimension
    generator = torch.Generator(device="cpu")
    generator.manual_seed(effective_seed)
    input_features = torch.as_tensor(features, dtype=torch.float32)
    base = torch.nn.Parameter(
        torch.randn(feature_count, hidden_dimension, generator=generator, dtype=torch.float32)
        / math.sqrt(max(feature_count, 1))
    )
    relation_transform = torch.nn.Parameter(
        torch.randn(len(_RELATION_LAYERS), feature_count, hidden_dimension, generator=generator, dtype=torch.float32)
        / math.sqrt(max(feature_count, 1))
    )
    relation_attention = torch.nn.Parameter(torch.zeros(len(_RELATION_LAYERS), dtype=torch.float32))
    optimizer = torch.optim.Adam((base, relation_transform, relation_attention), lr=0.02)
    relation_tensors = tuple(
        (
            torch.as_tensor(source, dtype=torch.int64),
            torch.as_tensor(target, dtype=torch.int64),
            torch.as_tensor(weight, dtype=torch.float32),
        )
        for source, target, weight in relation_edges
    )
    positive_sources = []
    positive_targets = []
    for source, target, weights in relation_tensors:
        present = weights > 0
        if bool(torch.any(present)):
            positive_sources.append(source[present])
            positive_targets.append(target[present])
    if positive_sources:
        edge_source = torch.cat(positive_sources)
        edge_target = torch.cat(positive_targets)
    else:
        edge_source = torch.empty(0, dtype=torch.int64)
        edge_target = torch.empty(0, dtype=torch.int64)

    def encode(feature_view: torch.Tensor, dropout_seed: int, dropout_rate: float) -> torch.Tensor:
        attention = torch.softmax(relation_attention, dim=0)
        aggregate = torch.zeros((account_count, hidden_dimension), dtype=torch.float32)
        normalization = torch.zeros((account_count, 1), dtype=torch.float32)
        local_generator = torch.Generator(device="cpu")
        local_generator.manual_seed(dropout_seed)
        for relation_index, (source, target, weights) in enumerate(relation_tensors):
            if weights.numel() == 0:
                continue
            keep = torch.rand(weights.numel(), generator=local_generator) >= dropout_rate
            if not bool(torch.any(keep)):
                continue
            kept_source = source[keep]
            kept_target = target[keep]
            kept_weights = weights[keep] * attention[relation_index]
            messages = feature_view @ relation_transform[relation_index]
            aggregate.index_add_(0, kept_source, messages[kept_target] * kept_weights[:, None])
            aggregate.index_add_(0, kept_target, messages[kept_source] * kept_weights[:, None])
            normalization.index_add_(0, kept_source, kept_weights[:, None])
            normalization.index_add_(0, kept_target, kept_weights[:, None])
        return torch.tanh(feature_view @ base + aggregate / normalization.clamp_min(1.0))

    losses = []
    for epoch in range(config.epochs):
        embedding = functional.normalize(
            encode(input_features, effective_seed + 313 * epoch + 1, config.edge_dropout_rate),
            p=2.0,
            dim=1,
        )
        if edge_source.numel() == 0 or account_count < 2:
            losses.append(0.0)
            continue
        edge_count = min(config.batch_size, int(edge_source.numel()))
        selected = torch.randperm(int(edge_source.numel()), generator=generator)[:edge_count]
        positive_source = edge_source[selected]
        positive_target = edge_target[selected]
        negative_source = positive_source
        negative_target = torch.randint(0, account_count, (edge_count,), generator=generator, dtype=torch.int64)
        negative_target = torch.where(
            negative_target == negative_source,
            (negative_target + 1) % account_count,
            negative_target,
        )
        positive_logits = torch.sum(embedding[positive_source] * embedding[positive_target], dim=1) / config.temperature
        negative_logits = torch.sum(embedding[negative_source] * embedding[negative_target], dim=1) / config.temperature
        logits = torch.cat((positive_logits, negative_logits))
        targets = torch.cat((torch.ones_like(positive_logits), torch.zeros_like(negative_logits)))
        loss = functional.binary_cross_entropy_with_logits(logits, targets)
        optimizer.zero_grad(set_to_none=True)
        loss.backward()
        optimizer.step()
        losses.append(float(loss.detach().cpu()))
    with torch.no_grad():
        embeddings = encode(input_features, effective_seed + 10_000, 0.0)
        attention = torch.softmax(relation_attention, dim=0).detach().cpu().numpy().astype(float)
    diagnostics = MappingProxyType(
        {
            "objective": "self_supervised_magnn_edge_reconstruction",
            "relation_transform_count": len(_RELATION_LAYERS),
            "relation_specific": True,
            "relation_attention": {
                _RELATION_NAMES[index]: float(attention[index])
                for index in range(len(_RELATION_LAYERS))
            },
            "batch_negatives": min(config.batch_size, account_count) - 1,
            "seed": effective_seed,
            "feature_names": _relation_feature_names(),
            "augmentation": {
                "relation_edge_dropout": config.edge_dropout_rate,
                "feature_mask_rate": 0.0,
            },
            "epoch_edge_reconstruction_losses": losses,
            "evaluator_labels_absent": True,
        }
    )
    return embeddings.cpu().numpy().astype(np.float32, copy=False), diagnostics


def _edge_affinity(embeddings: np.ndarray, endpoints: np.ndarray) -> np.ndarray:
    if endpoints.size == 0:
        return np.empty(0, dtype=np.float32)
    normalized = _row_normalize(embeddings)
    affinity = np.sum(normalized[endpoints[:, 0]] * normalized[endpoints[:, 1]], axis=1)
    return np.clip((affinity + 1.0) / 2.0, 0.0, 1.0).astype(np.float32)


def _dense_cosine_edges(
    features: np.ndarray,
    config: CompactDiscoveryMethodConfig,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    account_count = features.shape[0]
    if account_count > config.dense_feasible_account_limit:
        raise CompactDiscoveryMethodBlocked(
            f"dense_cosine_leiden exceeds declared feasibility limit {config.dense_feasible_account_limit}"
        )
    normalized = _row_normalize(features)
    similarity = normalized @ normalized.T
    source, target = np.triu_indices(account_count, k=1)
    scores = np.clip(similarity[source, target], 0.0, 1.0).astype(np.float32)
    positive = scores > 0.0
    source = source[positive]
    target = target[positive]
    scores = scores[positive]
    order = np.lexsort((target, source, -scores))[: config.max_candidate_edges]
    order = order[np.lexsort((target[order], source[order]))]
    endpoints = np.column_stack((source[order], target[order]))
    relation_weights = np.zeros((len(order), len(_RELATION_LAYERS)), dtype=np.float32)
    return endpoints, scores[order], relation_weights


def _leiden_assignments(
    account_count: int,
    endpoints: np.ndarray,
    weights: np.ndarray,
    seed: int,
) -> np.ndarray:
    if endpoints.size == 0:
        return np.arange(account_count, dtype=np.int32)
    try:
        import igraph
        import leidenalg
    except ImportError as exc:
        raise CompactDiscoveryMethodBlocked("Leiden interpretation requires igraph and leidenalg") from exc
    graph = igraph.Graph(n=account_count, directed=False)
    graph.add_edges(zip(endpoints[:, 0], endpoints[:, 1], strict=True))
    partition = leidenalg.find_partition(
        graph,
        leidenalg.RBConfigurationVertexPartition,
        weights=weights.astype(float, copy=False),
        seed=seed,
    )
    assignments = np.empty(account_count, dtype=np.int32)
    for cluster_id, members in enumerate(partition):
        assignments[np.asarray(members, dtype=np.int64)] = cluster_id
    return assignments


def _cluster_batch(
    *,
    execution_input: CompactDiscoveryExecutionInput,
    method_id: str,
    method_version: str,
    assignments: np.ndarray,
    endpoints: np.ndarray,
    edge_scores: np.ndarray,
    relation_weights: np.ndarray,
    candidate_weights: np.ndarray,
    tsgs_diagnostics: Mapping[str, Any],
    mhcr_diagnostics: Mapping[str, Any],
    timings: Mapping[str, float],
) -> tuple[DiscoveredClusterBatch, np.ndarray]:
    account_count = execution_input.discovery_view.account_count
    cluster_count = int(np.max(assignments)) + 1 if assignments.size else 0
    cluster_sizes = np.bincount(assignments, minlength=cluster_count)
    account_degree = _weighted_degree(account_count, endpoints, candidate_weights)
    incident_scores = _weighted_degree(account_count, endpoints, edge_scores)
    internal = assignments[endpoints[:, 0]] == assignments[endpoints[:, 1]] if endpoints.size else np.empty(0, dtype=bool)
    internal_cluster = assignments[endpoints[internal, 0]] if endpoints.size else np.empty(0, dtype=np.int32)
    internal_weight = np.bincount(
        internal_cluster,
        weights=candidate_weights[internal],
        minlength=cluster_count,
    )
    internal_score = np.bincount(
        internal_cluster,
        weights=edge_scores[internal],
        minlength=cluster_count,
    )
    internal_count = np.bincount(internal_cluster, minlength=cluster_count)
    coherence = internal_score / np.maximum(internal_count, 1)
    cluster_relations = np.zeros((cluster_count, len(_RELATION_LAYERS)), dtype=np.float32)
    if endpoints.size:
        for relation_index in range(len(_RELATION_LAYERS)):
            present = internal & (relation_weights[:, relation_index] > 0.0)
            np.add.at(
                cluster_relations[:, relation_index],
                assignments[endpoints[present, 0]],
                1.0,
            )
    relation_diversity = np.count_nonzero(cluster_relations, axis=1) / len(_RELATION_LAYERS)
    denominator = np.maximum(cluster_sizes * np.maximum(cluster_sizes - 1, 1) / 2, 1)
    density = np.clip(internal_weight / denominator, 0.0, 1.0)
    cluster_score = np.clip((density + np.clip(coherence, 0.0, 1.0) + relation_diversity) / 3.0, 0.0, 1.0)
    account_scores = np.clip(
        (_normalized(account_degree) + _normalized(incident_scores) + cluster_score[assignments]) / 3.0,
        0.0,
        1.0,
    ).astype(np.float32)
    clusters = []
    for cluster_id in range(cluster_count):
        member_indexes = np.flatnonzero(assignments == cluster_id)
        present_relations = np.flatnonzero(cluster_relations[cluster_id] > 0.0)
        relation_types = tuple(_RELATION_NAMES[index] for index in present_relations)
        evidence_counts = {
            _RELATION_NAMES[index]: int(cluster_relations[cluster_id, index])
            for index in present_relations
        }
        clusters.append(
            DiscoveredCluster(
                cluster_id=f"cluster-{cluster_id:06d}",
                member_account_ids=tuple(f"account-{index:06d}" for index in member_indexes),
                coordination_metrics=CoordinationMetricSet(
                    tsgs_spectral_density=float(density[cluster_id]),
                    mhcr_hyperedge_coherence=float(np.clip(coherence[cluster_id], 0.0, 1.0)),
                    temporal_sync_delta_seconds=0.0,
                    overall_coordination_score=float(cluster_score[cluster_id]),
                    evidence_coverage=float(min(1.0, member_indexes.size / max(account_count, 1))),
                    relation_diversity=float(relation_diversity[cluster_id]),
                ),
                evidence_refs=tuple(f"compact-layer:{layer}" for layer in _RELATION_LAYERS if IOHUNTER_LAYER_RELATIONS[layer] in relation_types),
                artifact_hashes={
                    "source_layer_fingerprint": execution_input.discovery_view.source_layer_fingerprint,
                    "method_config_fingerprint": _config_fingerprint_placeholder(execution_input),
                },
                relation_types=relation_types,
                evidence_kind_counts=evidence_counts,
            )
        )
    provenance = DiscoveryProvenance(
        snapshot_id=f"iohunter-{execution_input.discovery_view.campaign}-compact",
        data_fingerprint=execution_input.discovery_view.source_layer_fingerprint,
        source_dataset=f"iohunter-{execution_input.discovery_view.campaign}",
        source_event="compact_static_source_layers",
        stage1_model_version=method_version,
        tsgs_version=str(tsgs_diagnostics["resistance_backend"]),
        mhcr_version=str(mhcr_diagnostics["objective"]),
        created_at="1970-01-01T00:00:00Z",
        seed=execution_input.seed,
        split_policy="official_static_fold",
        input_event_count=0,
        input_account_count=account_count,
        method_config_hash=execution_input.fingerprint,
    )
    batch_hash = hashlib.sha256(
        f"{method_id}|{execution_input.fingerprint}|{len(clusters)}".encode("utf-8")
    ).hexdigest()[:20]
    batch = DiscoveredClusterBatch(
        batch_id=f"compact-{method_id}-{batch_hash}",
        timestamp="1970-01-01T00:00:00Z",
        candidate_clusters=tuple(clusters),
        provenance=provenance,
        runtime_diagnostics=DiscoveryRuntimeDiagnostics(
            tsgs_seconds=timings["tsgs_seconds"],
            mhcr_seconds=timings["mhcr_seconds"],
            leiden_seconds=timings["leiden_seconds"],
            total_seconds=timings["total_seconds"],
        ),
        quality_flags=("timestamp_imputed",),
    )
    return batch, account_scores


def _config_fingerprint_placeholder(execution_input: CompactDiscoveryExecutionInput) -> str:
    return execution_input.fingerprint


@dataclass(frozen=True, slots=True)
class GraphNativeDiscoveryImplementation(DiscoveryImplementation):
    method_id: str = ""
    method_version: str = ""
    implementation_id: str = ""
    config: CompactDiscoveryMethodConfig = field(
        default_factory=lambda: CompactDiscoveryMethodConfig(method_variant="tsgs_mhcr_compact")
    )
    unavailable_reason: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.config, CompactDiscoveryMethodConfig):
            raise ValueError("compact implementation config must be CompactDiscoveryMethodConfig")
        if not self.method_id or self.method_id != self.config.method_variant:
            raise ValueError("compact implementation method identity must match its method variant")
        if not self.method_version or not self.implementation_id:
            raise ValueError("compact implementation requires stable method and implementation versions")

    def _execution_config(
        self, execution_input: CompactDiscoveryExecutionInput
    ) -> CompactDiscoveryMethodConfig:
        unknown = set(execution_input.method_config) - _EXECUTION_CONFIG_OVERRIDES
        if unknown:
            raise ValueError(f"method_config contains unsupported compact fields: {sorted(unknown)}")
        overrides = {
            key: execution_input.method_config[key]
            for key in _EXECUTION_CONFIG_OVERRIDES
            if key in execution_input.method_config
        }
        return replace(self.config, **overrides)

    def execute(self, execution_input: CompactDiscoveryExecutionInput) -> CompactDiscoveryPrediction:
        if not isinstance(execution_input, CompactDiscoveryExecutionInput):
            raise ValueError("compact graph-native Discovery requires CompactDiscoveryExecutionInput")
        if self.unavailable_reason is not None:
            raise CompactDiscoveryMethodBlocked(self.unavailable_reason)
        if execution_input.discovery_view.time_semantics != IOHUNTER_STATIC_TIME_SEMANTICS:
            raise ValueError("compact IOHunter methods require explicit static time semantics")
        config = self._execution_config(execution_input)
        started = time.perf_counter()
        effective_seed = config.seed ^ execution_input.seed
        fused = _fuse_relation_layers(execution_input)
        tsgs_started = time.perf_counter()
        if config.method_variant == "dense_cosine_leiden":
            input_features = _relation_features(
                execution_input.discovery_view.account_count,
                fused.endpoints,
                fused.relation_weights,
            )
            endpoints, candidate_weights, relation_weights = _dense_cosine_edges(input_features, config)
            tsgs_diagnostics: Mapping[str, Any] = MappingProxyType(
                {
                    "resistance_backend": "dense_all_pairs_cosine_reference",
                    "spectral_guarantee": "not_a_spectral_sparsifier",
                    "guarantee_scope": "declared_dense_feasibility_only",
                    "input_union_edge_count": int(fused.endpoints.shape[0]),
                    "retained_edge_count": int(endpoints.shape[0]),
                    "candidate_recall": None,
                }
            )
        else:
            endpoints, candidate_weights, relation_weights, tsgs_diagnostics = _edge_selection(
                fused,
                execution_input.discovery_view.account_count,
                config,
                effective_seed,
                use_tsgs=config.method_variant
                not in {"no_tsgs", "edgebank", "magnn_leiden_hybrid_discovery", "magnn_legacy"},
            )
            if config.method_variant == "edgebank":
                tsgs_diagnostics = MappingProxyType(
                    {
                        **tsgs_diagnostics,
                        "resistance_backend": "not_run_static_edgebank",
                        "spectral_guarantee": "not_applicable_static_baseline",
                    }
                )
            elif config.method_variant == "magnn_leiden_hybrid_discovery":
                tsgs_diagnostics = MappingProxyType(
                    {
                        **tsgs_diagnostics,
                        "resistance_backend": "not_run_evidence_constrained_magnn_candidate_edges",
                        "spectral_guarantee": "not_applicable_hybrid_evidence_constraint",
                    }
                )
        tsgs_seconds = time.perf_counter() - tsgs_started
        mhcr_started = time.perf_counter()
        features = _relation_features(execution_input.discovery_view.account_count, endpoints, relation_weights)
        if config.method_variant in {"magnn_leiden_hybrid_discovery", "magnn_legacy"}:
            embeddings, mhcr_diagnostics = _magnn_leiden_embeddings(
                features,
                _relation_edge_arrays(endpoints, relation_weights),
                config,
                effective_seed,
            )
        elif config.method_variant in {"edgebank", "no_mhcr", "dense_cosine_leiden"}:
            embeddings, mhcr_diagnostics = _input_embeddings(features)
        else:
            embeddings, mhcr_diagnostics = _mhcr_embeddings(
                features,
                _relation_edge_arrays(endpoints, relation_weights),
                config,
                effective_seed,
                relation_specific=config.method_variant != "no_relation_specific",
            )
        mhcr_seconds = time.perf_counter() - mhcr_started
        affinity = _edge_affinity(embeddings, endpoints)
        normalized_weight = _normalized(candidate_weights)
        if config.method_variant in {"edgebank", "dense_cosine_leiden"}:
            edge_scores = normalized_weight
        elif config.method_variant == "magnn_leiden_hybrid_discovery":
            edge_scores = (0.5 * normalized_weight + 0.5 * affinity).astype(np.float32)
        elif config.method_variant == "magnn_legacy":
            edge_scores = affinity
        else:
            edge_scores = (normalized_weight * affinity).astype(np.float32)
        leiden_started = time.perf_counter()
        assignments = _leiden_assignments(
            execution_input.discovery_view.account_count,
            endpoints,
            edge_scores,
            effective_seed,
        )
        leiden_seconds = time.perf_counter() - leiden_started
        timings = {
            "tsgs_seconds": tsgs_seconds,
            "mhcr_seconds": mhcr_seconds,
            "leiden_seconds": leiden_seconds,
            "total_seconds": time.perf_counter() - started,
        }
        batch, account_scores = _cluster_batch(
            execution_input=execution_input,
            method_id=self.method_id,
            method_version=self.method_version,
            assignments=assignments,
            endpoints=endpoints,
            edge_scores=edge_scores,
            relation_weights=relation_weights,
            candidate_weights=candidate_weights,
            tsgs_diagnostics=tsgs_diagnostics,
            mhcr_diagnostics=mhcr_diagnostics,
            timings=timings,
        )
        diagnostics = {
            "method_role": (
                "static_edge_memory_baseline"
                if config.method_variant == "edgebank"
                else "research_only_magnn_leiden_hybrid_discovery"
                if config.method_variant == "magnn_leiden_hybrid_discovery"
                else "research_only_legacy_magnn_leiden_discovery"
                if config.method_variant == "magnn_legacy"
                else "research_only_graph_native_discovery"
            ),
            "time_semantics": IOHUNTER_STATIC_TIME_SEMANTICS,
            "source_layer_counts": dict(fused.source_layer_counts),
            "duplicate_relation_edges_collapsed": fused.duplicate_relation_edges_collapsed,
            "relation_count": len(_RELATION_LAYERS),
            "tsgs": dict(tsgs_diagnostics),
            "mhcr": dict(mhcr_diagnostics),
            "clustering": {
                "backend": "leiden_interpretation_partition",
                "candidate_edge_budget": config.max_candidate_edges,
            },
            "account_score_role": "unsupervised_ranking_not_probability",
            "edge_score_formula": (
                "static_normalized_edge_weight"
                if config.method_variant in {"edgebank", "dense_cosine_leiden"}
                else "0.5_normalized_evidence_weight_plus_0.5_magnn_edge_affinity"
                if config.method_variant == "magnn_leiden_hybrid_discovery"
                else "magnn_edge_affinity_only"
                if config.method_variant == "magnn_legacy"
                else "normalized_tsgs_evidence_weight_times_mhcr_affinity"
            ),
            "account_score_formula": "mean(normalized_weighted_degree,candidate_incident_strength,cluster_coherence)",
            "evaluator_labels_absent": True,
        }
        return CompactDiscoveryPrediction(
            account_count=execution_input.discovery_view.account_count,
            candidate_endpoints=_readonly(
                endpoints,
                np.dtype("<u2")
                if execution_input.discovery_view.account_count <= np.iinfo(np.uint16).max + 1
                else np.dtype("<u4"),
                (endpoints.shape[0], 2),
            ),
            edge_scores=_readonly(edge_scores, np.dtype("<f4"), (edge_scores.shape[0],)),
            account_scores=_readonly(account_scores, np.dtype("<f4"), (account_scores.shape[0],)),
            cluster_assignments=_readonly(assignments, np.dtype("<i4"), (assignments.shape[0],)),
            discovered_cluster_batch=batch,
            method_id=self.method_id,
            method_version=self.method_version,
            implementation_id=self.implementation_id,
            diagnostics=diagnostics,
            claim_markers=(
                _STATIC_CLAIM_MARKER,
                "iohunter_no_ground_truth_coordination_edges",
                "iohunter_no_ground_truth_communities",
                "iohunter_no_causal_campaign_labels",
            ),
        )


def _production_pair_frame(graph: _FusedCompactGraph) -> pd.DataFrame:
    pair_indices, relation_indices = np.nonzero(graph.relation_weights > 0.0)
    if pair_indices.size == 0:
        return pd.DataFrame(
            columns=(
                "account_id",
                "account_id_y",
                "content_id",
                "content_id_y",
                "time_delta",
            )
        )
    endpoints = graph.endpoints[pair_indices]
    occurrence_ids = np.arange(pair_indices.size, dtype=np.int64)
    return pd.DataFrame(
        {
            "account_id": [f"account-{int(index):06d}" for index in endpoints[:, 0]],
            "account_id_y": [f"account-{int(index):06d}" for index in endpoints[:, 1]],
            "content_id": occurrence_ids * 2,
            "content_id_y": occurrence_ids * 2 + 1,
            "time_delta": np.zeros(pair_indices.size, dtype=np.float64),
            "relation_index": relation_indices.astype(np.uint8, copy=False),
        }
    )


def _production_assignments(account_count: int, graph: Any) -> np.ndarray:
    assignments = np.full(account_count, -1, dtype=np.int32)
    for account_index in range(account_count):
        account_id = f"account-{account_index:06d}"
        if account_id in graph:
            assignments[account_index] = int(graph.nodes[account_id]["cluster_id"])
    next_cluster = int(np.max(assignments)) + 1 if np.any(assignments >= 0) else 0
    for account_index in np.flatnonzero(assignments < 0):
        assignments[account_index] = next_cluster
        next_cluster += 1
    return assignments


def _production_account_scores(account_count: int, graph: Any) -> np.ndarray:
    weighted_degree = np.zeros(account_count, dtype=np.float32)
    for account_index in range(account_count):
        account_id = f"account-{account_index:06d}"
        if account_id in graph:
            weighted_degree[account_index] = float(
                graph.nodes[account_id].get("weighted_degree", 0.0)
            )
    return _normalized(weighted_degree)


@dataclass(frozen=True, slots=True)
class _FrozenSystemProjection:
    fused: _FusedCompactGraph
    candidate_weights: np.ndarray
    edge_scores: np.ndarray
    assignments: np.ndarray
    account_scores: np.ndarray
    account_stat_count: int
    source_occurrence_upper_bound: int
    occurrence_count: int
    graph_seconds: float
    cold_projection_seconds: float


@dataclass(frozen=True, slots=True)
class FrozenSystemEvidencePriorImplementation(DiscoveryImplementation):
    method_id: str = "frozen_system_evidence_prior"
    method_version: str = "coordination-evidence-runtime-v2"
    implementation_id: str = "frozen-system-evidence-compact-adapter-v4"
    config: CompactDiscoveryMethodConfig = field(
        default_factory=lambda: CompactDiscoveryMethodConfig(
            method_variant="frozen_system_evidence_prior",
            epochs=1,
        )
    )
    unavailable_reason: str | None = None
    _projection_cache: dict[str, _FrozenSystemProjection] = field(
        default_factory=dict,
        init=False,
        repr=False,
        compare=False,
    )

    def execute(
        self, execution_input: CompactDiscoveryExecutionInput
    ) -> CompactDiscoveryPrediction:
        if not isinstance(execution_input, CompactDiscoveryExecutionInput):
            raise ValueError("frozen system baseline requires CompactDiscoveryExecutionInput")
        if self.unavailable_reason is not None:
            raise CompactDiscoveryMethodBlocked(self.unavailable_reason)
        if execution_input.discovery_view.time_semantics != IOHUNTER_STATIC_TIME_SEMANTICS:
            raise ValueError("frozen system compact comparison requires explicit static time semantics")

        try:
            from app.core.coordination_baseline import (
                account_stats as production_account_stats,
                generate_coordinated_network,
            )
        except ImportError as exc:
            raise CompactDiscoveryMethodBlocked(
                "backend production coordination core is unavailable"
            ) from exc

        cache_key = execution_input.discovery_view.source_layer_fingerprint
        if self._projection_cache and cache_key not in self._projection_cache:
            self._projection_cache.clear()
        source_occurrence_upper_bound = sum(
            int(layer.endpoints.shape[0])
            for layer in execution_input.discovery_view.relation_edges.values()
        )
        if source_occurrence_upper_bound > _PRODUCTION_STATIC_PROXY_MAX_OCCURRENCES:
            raise CompactDiscoveryMethodBlocked(
                "frozen production static proxy exceeds the "
                f"{_PRODUCTION_STATIC_PROXY_MAX_OCCURRENCES}-occurrence runtime budget; "
                "the adapter blocks before fusion and does not truncate or replace the production graph core"
            )
        projection = self._projection_cache.get(cache_key)
        cache_hit = projection is not None
        if projection is None:
            projection_started = time.perf_counter()
            fused = _fuse_relation_layers(execution_input)
            occurrence_count = int(np.count_nonzero(fused.relation_weights))
            if occurrence_count > _PRODUCTION_STATIC_PROXY_MAX_OCCURRENCES:
                raise CompactDiscoveryMethodBlocked(
                    "frozen production static proxy exceeds the "
                    f"{_PRODUCTION_STATIC_PROXY_MAX_OCCURRENCES}-occurrence runtime budget; "
                    "the adapter blocks and does not truncate or replace the production graph core"
                )
            pair_frame = _production_pair_frame(fused)
            graph_started = time.perf_counter()
            graph = generate_coordinated_network(pair_frame, edge_weight=0.5)
            account_rows = production_account_stats(graph, pair_frame)
            graph_seconds = time.perf_counter() - graph_started
            candidate_weights = np.count_nonzero(
                fused.relation_weights, axis=1
            ).astype(np.float32)
            projection = _FrozenSystemProjection(
                fused=fused,
                candidate_weights=candidate_weights,
                edge_scores=_normalized(candidate_weights),
                assignments=_production_assignments(
                    execution_input.discovery_view.account_count, graph
                ),
                account_scores=_production_account_scores(
                    execution_input.discovery_view.account_count, graph
                ),
                account_stat_count=int(len(account_rows)),
                source_occurrence_upper_bound=source_occurrence_upper_bound,
                occurrence_count=occurrence_count,
                graph_seconds=graph_seconds,
                cold_projection_seconds=time.perf_counter() - projection_started,
            )
            self._projection_cache.clear()
            self._projection_cache[cache_key] = projection

        fused = projection.fused
        candidate_weights = projection.candidate_weights
        edge_scores = projection.edge_scores
        assignments = projection.assignments
        account_scores = projection.account_scores
        timings = {
            "tsgs_seconds": 0.0,
            "mhcr_seconds": 0.0,
            "leiden_seconds": 0.0,
            "total_seconds": projection.cold_projection_seconds,
        }
        batch, _ = _cluster_batch(
            execution_input=execution_input,
            method_id=self.method_id,
            method_version=self.method_version,
            assignments=assignments,
            endpoints=fused.endpoints,
            edge_scores=edge_scores,
            relation_weights=fused.relation_weights,
            candidate_weights=candidate_weights,
            tsgs_diagnostics={
                "resistance_backend": "not_run_frozen_production_core",
                "guarantee_scope": "not_applicable_production_baseline",
            },
            mhcr_diagnostics={
                "objective": "not_run_frozen_production_core",
            },
            timings=timings,
        )
        diagnostics = {
            "method_role": "frozen_production_evidence_baseline",
            "system_model_version": self.method_version,
            "evaluation_adapter_scope": "post_evidence_projection_static_graph_only",
            "time_semantics": IOHUNTER_STATIC_TIME_SEMANTICS,
            "source_layer_counts": dict(fused.source_layer_counts),
            "duplicate_relation_edges_collapsed": fused.duplicate_relation_edges_collapsed,
            "source_weight_policy": "ignored_by_production_pair_count_core",
            "production_account_stat_count": projection.account_stat_count,
            "projection_cache_hit": cache_hit,
            "source_occurrence_upper_bound": projection.source_occurrence_upper_bound,
            "projected_relation_occurrence_count": projection.occurrence_count,
            "runtime_budget_occurrence_limit": _PRODUCTION_STATIC_PROXY_MAX_OCCURRENCES,
            "cold_projection_seconds": projection.cold_projection_seconds,
            "clustering": {
                "backend": "networkx_greedy_modularity",
                "runtime_seconds": projection.graph_seconds,
            },
            "edge_score_formula": "normalized_production_shared_relation_count",
            "account_score_formula": "normalized_production_weighted_degree",
            "account_score_role": "production_evidence_prior_not_probability",
            "seed_policy": "deterministic_seed_ignored",
            "evaluator_labels_absent": True,
        }
        index_dtype = (
            np.dtype("<u2")
            if execution_input.discovery_view.account_count <= np.iinfo(np.uint16).max + 1
            else np.dtype("<u4")
        )
        return CompactDiscoveryPrediction(
            account_count=execution_input.discovery_view.account_count,
            candidate_endpoints=_readonly(
                fused.endpoints, index_dtype, (fused.endpoints.shape[0], 2)
            ),
            edge_scores=_readonly(
                edge_scores, np.dtype("<f4"), (edge_scores.shape[0],)
            ),
            account_scores=_readonly(
                account_scores, np.dtype("<f4"), (account_scores.shape[0],)
            ),
            cluster_assignments=_readonly(
                assignments, np.dtype("<i4"), (assignments.shape[0],)
            ),
            discovered_cluster_batch=batch,
            method_id=self.method_id,
            method_version=self.method_version,
            implementation_id=self.implementation_id,
            diagnostics=diagnostics,
            claim_markers=(
                _STATIC_CLAIM_MARKER,
                "production_graph_core_only_no_event_snapshot_evidence_extraction",
                "production_dynamic_windows_not_evaluated",
                "production_account_score_is_adapter_projection",
                "production_runtime_budget_guard_active",
                "iohunter_no_ground_truth_coordination_edges",
                "iohunter_no_ground_truth_communities",
                "iohunter_no_causal_campaign_labels",
            ),
        )


@dataclass(frozen=True, slots=True)
class _FrozenSystemAccountScoreProjection:
    fused: _FusedCompactGraph
    candidate_weights: np.ndarray
    edge_scores: np.ndarray
    account_scores: np.ndarray


def _production_weighted_degree_scores(
    account_count: int,
    endpoints: np.ndarray,
    candidate_weights: np.ndarray,
) -> np.ndarray:
    weighted_degree = np.zeros(account_count, dtype=np.float32)
    if endpoints.size:
        np.add.at(weighted_degree, endpoints[:, 0], candidate_weights)
        np.add.at(weighted_degree, endpoints[:, 1], candidate_weights)
    return _normalized(weighted_degree)


@dataclass(frozen=True, slots=True)
class FrozenSystemAccountScorePriorImplementation(DiscoveryImplementation):
    """Metric-equivalent production account ranking without community inference."""

    method_id: str = "frozen_system_account_score_prior"
    method_version: str = "coordination-evidence-account-score-v2"
    implementation_id: str = "frozen-system-account-score-compact-adapter-v2"
    config: CompactDiscoveryMethodConfig = field(
        default_factory=lambda: CompactDiscoveryMethodConfig(
            method_variant="frozen_system_account_score_prior",
            epochs=1,
        )
    )
    unavailable_reason: str | None = None
    _projection_cache: dict[str, _FrozenSystemAccountScoreProjection] = field(
        default_factory=dict,
        init=False,
        repr=False,
        compare=False,
    )

    def execute(
        self, execution_input: CompactDiscoveryExecutionInput
    ) -> CompactDiscoveryPrediction:
        if not isinstance(execution_input, CompactDiscoveryExecutionInput):
            raise ValueError("frozen system account-score prior requires CompactDiscoveryExecutionInput")
        if execution_input.discovery_view.time_semantics != IOHUNTER_STATIC_TIME_SEMANTICS:
            raise ValueError("frozen system account-score comparison requires static time semantics")

        cache_key = execution_input.discovery_view.source_layer_fingerprint
        if self._projection_cache and cache_key not in self._projection_cache:
            self._projection_cache.clear()
        projection = self._projection_cache.get(cache_key)
        cache_hit = projection is not None
        started = time.perf_counter()
        if projection is None:
            fused = _fuse_relation_layers(execution_input)
            candidate_weights = np.count_nonzero(
                fused.relation_weights, axis=1
            ).astype(np.float32)
            projection = _FrozenSystemAccountScoreProjection(
                fused=fused,
                candidate_weights=candidate_weights,
                edge_scores=_normalized(candidate_weights),
                account_scores=_production_weighted_degree_scores(
                    execution_input.discovery_view.account_count,
                    fused.endpoints,
                    candidate_weights,
                ),
            )
            self._projection_cache.clear()
            self._projection_cache[cache_key] = projection

        account_count = execution_input.discovery_view.account_count
        assignments = np.arange(account_count, dtype=np.int32)
        elapsed = time.perf_counter() - started
        batch, _ = _cluster_batch(
            execution_input=execution_input,
            method_id=self.method_id,
            method_version=self.method_version,
            assignments=assignments,
            endpoints=projection.fused.endpoints,
            edge_scores=projection.edge_scores,
            relation_weights=projection.fused.relation_weights,
            candidate_weights=projection.candidate_weights,
            tsgs_diagnostics={
                "resistance_backend": "not_run_production_account_score_prior",
                "guarantee_scope": "account_ranking_equivalence_only",
            },
            mhcr_diagnostics={"objective": "not_run_production_account_score_prior"},
            timings={
                "tsgs_seconds": 0.0,
                "mhcr_seconds": 0.0,
                "leiden_seconds": 0.0,
                "total_seconds": elapsed,
            },
        )
        diagnostics = {
            "method_role": "frozen_production_account_score_equivalent_baseline",
            "system_model_version": "coordination-evidence-runtime-v2",
            "evaluation_adapter_scope": "post_evidence_projection_static_account_ranking_only",
            "equivalence_scope": "external_account_ranking_account_scores_only",
            "time_semantics": IOHUNTER_STATIC_TIME_SEMANTICS,
            "source_layer_counts": dict(projection.fused.source_layer_counts),
            "duplicate_relation_edges_collapsed": projection.fused.duplicate_relation_edges_collapsed,
            "source_weight_policy": "ignored_by_production_pair_count_core",
            "projection_cache_hit": cache_hit,
            "clustering": {"backend": "singleton_placeholder_partition"},
            "edge_score_formula": "normalized_production_shared_relation_count",
            "account_score_formula": "normalized_production_weighted_degree",
            "account_score_role": "production_evidence_prior_not_probability",
            "seed_policy": "deterministic_seed_ignored",
            "evaluator_labels_absent": True,
        }
        index_dtype = (
            np.dtype("<u2") if account_count <= np.iinfo(np.uint16).max + 1 else np.dtype("<u4")
        )
        return CompactDiscoveryPrediction(
            account_count=account_count,
            candidate_endpoints=_readonly(
                projection.fused.endpoints,
                index_dtype,
                (projection.fused.endpoints.shape[0], 2),
            ),
            edge_scores=_readonly(
                projection.edge_scores,
                np.dtype("<f4"),
                (projection.edge_scores.shape[0],),
            ),
            account_scores=_readonly(
                projection.account_scores,
                np.dtype("<f4"),
                (projection.account_scores.shape[0],),
            ),
            cluster_assignments=_readonly(assignments, np.dtype("<i4"), (account_count,)),
            discovered_cluster_batch=batch,
            method_id=self.method_id,
            method_version=self.method_version,
            implementation_id=self.implementation_id,
            diagnostics=diagnostics,
            claim_markers=(
                _STATIC_CLAIM_MARKER,
                "production_account_score_exact_for_static_projection",
                "singleton_placeholder_partition",
                "community_output_not_production_equivalent",
                "production_dynamic_windows_not_evaluated",
                "iohunter_no_ground_truth_coordination_edges",
                "iohunter_no_ground_truth_communities",
                "iohunter_no_causal_campaign_labels",
            ),
        )


@dataclass(frozen=True, slots=True)
class _BlockedCompactDiscoveryImplementation(DiscoveryImplementation):
    method_id: str = ""
    method_version: str = ""
    implementation_id: str = ""
    unavailable_reason: str = ""
    config: CompactDiscoveryMethodConfig = field(init=False)

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "config",
            CompactDiscoveryMethodConfig(method_variant=self.method_id, epochs=1),
        )

    def execute(self, execution_input: CompactDiscoveryExecutionInput) -> CompactDiscoveryPrediction:
        raise CompactDiscoveryMethodBlocked(self.unavailable_reason)


class CompactDiscoveryRegistry:
    __slots__ = ("_implementations", "_sealed")

    def __init__(self, implementations: Mapping[str, DiscoveryImplementation]) -> None:
        normalized = dict(implementations)
        if not normalized or any(
            not isinstance(implementation, DiscoveryImplementation)
            or key != implementation.method_id
            for key, implementation in normalized.items()
        ):
            raise ValueError("compact Discovery registry requires stable method identities")
        object.__setattr__(self, "_implementations", MappingProxyType(dict(sorted(normalized.items()))))
        object.__setattr__(self, "_sealed", True)

    def __setattr__(self, name: str, value: Any) -> None:
        if getattr(self, "_sealed", False):
            raise AttributeError("CompactDiscoveryRegistry is immutable")
        object.__setattr__(self, name, value)

    def method_ids(self) -> tuple[str, ...]:
        return tuple(self._implementations)

    def implementation(self, method_id: str) -> DiscoveryImplementation:
        try:
            return self._implementations[method_id]
        except KeyError as exc:
            raise ValueError(f"unknown compact Discovery method: {method_id}") from exc


def _dependency_unavailable_reason(*dependencies: str) -> str | None:
    missing = [
        dependency
        for dependency in dependencies
        if importlib.util.find_spec(dependency) is None
    ]
    return None if not missing else "compact Discovery dependencies unavailable: " + ", ".join(missing)


def default_compact_discovery_registry() -> CompactDiscoveryRegistry:
    leiden_reason = _dependency_unavailable_reason("igraph", "leidenalg")
    mhcr_reason = _dependency_unavailable_reason("igraph", "leidenalg", "torch")

    def implementation(
        method_id: str,
        version: str,
        *,
        unavailable_reason: str | None,
        **config_values: Any,
    ) -> GraphNativeDiscoveryImplementation:
        return GraphNativeDiscoveryImplementation(
            method_id=method_id,
            method_version=version,
            implementation_id=f"{method_id}-compact-implementation-v1",
            config=CompactDiscoveryMethodConfig(method_variant=method_id, **config_values),
            unavailable_reason=unavailable_reason,
        )

    return CompactDiscoveryRegistry(
        {
            "tsgs_mhcr_compact": implementation(
                "tsgs_mhcr_compact", "tsgs-mhcr-compact-v1", unavailable_reason=mhcr_reason
            ),
            "magnn_legacy": implementation(
                "magnn_legacy",
                "magnn-legacy-compact-v1",
                unavailable_reason=mhcr_reason,
            ),
            "magnn_leiden_hybrid_discovery": implementation(
                "magnn_leiden_hybrid_discovery",
                "magnn-leiden-hybrid-discovery-v1",
                unavailable_reason=mhcr_reason,
            ),
            "frozen_system_evidence_prior": FrozenSystemEvidencePriorImplementation(),
            "frozen_system_account_score_prior": FrozenSystemAccountScorePriorImplementation(),
            "edgebank": implementation(
                "edgebank", "edgebank-static-compact-v1", unavailable_reason=leiden_reason, epochs=1
            ),
            "dense_cosine_leiden": implementation(
                "dense_cosine_leiden", "dense-cosine-leiden-compact-v1", unavailable_reason=leiden_reason, epochs=1
            ),
            "no_tsgs": implementation(
                "no_tsgs", "tsgs-mhcr-compact-no-tsgs-v1", unavailable_reason=mhcr_reason
            ),
            "no_mhcr": implementation(
                "no_mhcr", "tsgs-mhcr-compact-no-mhcr-v1", unavailable_reason=leiden_reason, epochs=1
            ),
            "no_relation_specific": implementation(
                "no_relation_specific",
                "tsgs-mhcr-compact-shared-relation-v1",
                unavailable_reason=mhcr_reason,
            ),
            "no_temporal_augmentation": _BlockedCompactDiscoveryImplementation(
                "no_temporal_augmentation",
                "coordination-discovery-no-temporal-augmentation-v1",
                "no-temporal-augmentation-compact-v1",
                "IOHunter lacks observed timestamps; no_temporal_augmentation is not applicable",
            ),
            "tgn_style_memory_prior": _BlockedCompactDiscoveryImplementation(
                "tgn_style_memory_prior",
                "tgn-style-memory-prior-v1",
                "tgn-style-memory-compact-v1",
                "IOHunter lacks observed timestamps required by tgn_style_memory_prior",
            ),
        }
    )


__all__ = [
    "CompactDiscoveryMethodBlocked",
    "CompactDiscoveryMethodConfig",
    "CompactDiscoveryRegistry",
    "FrozenSystemEvidencePriorImplementation",
    "FrozenSystemAccountScorePriorImplementation",
    "GraphNativeDiscoveryImplementation",
    "default_compact_discovery_registry",
]
