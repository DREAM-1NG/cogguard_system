from __future__ import annotations

import hashlib
import io
import json
import math
import os
import pickle
import tracemalloc
from collections.abc import Iterator, Mapping as MappingABC
from dataclasses import dataclass
from numbers import Real
from pathlib import Path
from types import MappingProxyType
from typing import Any, Mapping

import networkx as nx
import numpy as np

from .iohunter import IOHUNTER_CAMPAIGNS, IOHUNTER_LAYER_RELATIONS


COMPACT_IOHUNTER_VERSION = "iohunter-compact-v1"
COMPACT_SOURCE_LAYER_FINGERPRINT_SCOPE = "iohunter-source-layers/compact-v1"
COMPACT_EVALUATOR_FINGERPRINT_SCOPE = "iohunter-evaluator/compact-v1"
IOHUNTER_STATIC_TIME_SEMANTICS = "static_placeholder_not_observed_time"
DEFAULT_COMPACT_MEMORY_BUDGET_BYTES = 16 * 1024**3
_SOURCE_ESTIMATE_MULTIPLIER = 24
_EXPECTED_KEYS = frozenset(
    {"graph", "coRT", "coURL", "hashSeq", "fastRT", "tweetSim", "labels", "splits"}
)


def _canonical_json(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")


def _sha256(value: bytes) -> str:
    return f"sha256:{hashlib.sha256(value).hexdigest()}"


def _hash_parts(*parts: bytes) -> str:
    digest = hashlib.sha256()
    for part in parts:
        digest.update(len(part).to_bytes(8, "big"))
        digest.update(part)
    return f"sha256:{digest.hexdigest()}"


def _validate_campaign(value: str) -> str:
    if not isinstance(value, str) or value not in IOHUNTER_CAMPAIGNS:
        raise ValueError(f"campaign must be one of {list(IOHUNTER_CAMPAIGNS)}")
    return value


def _validate_sha256(value: str, field_name: str) -> str:
    if not isinstance(value, str) or len(value) != 71 or not value.startswith("sha256:"):
        raise ValueError(f"{field_name} must be sha256:<64 hex>")
    try:
        int(value[7:], 16)
    except ValueError as exc:
        raise ValueError(f"{field_name} must be sha256:<64 hex>") from exc
    return value.lower()


def _index_dtype(account_count: int) -> np.dtype:
    if account_count <= np.iinfo(np.uint16).max + 1:
        return np.dtype("<u2")
    if account_count <= np.iinfo(np.uint32).max + 1:
        return np.dtype("<u4")
    raise ValueError("account_count exceeds compact-v1 uint32 node capacity")


def _immutable_array(value: np.ndarray, *, dtype: np.dtype, shape: tuple[int, ...]) -> np.ndarray:
    normalized = np.ascontiguousarray(value, dtype=dtype).reshape(shape)
    result = np.frombuffer(normalized.tobytes(order="C"), dtype=dtype).reshape(shape)
    if result.flags.writeable:
        raise RuntimeError("compact array immutable backing was not established")
    return result


@dataclass(frozen=True, slots=True)
class CompactEdgeArray:
    endpoints: np.ndarray
    weights: np.ndarray

    def __post_init__(self) -> None:
        endpoints = np.asarray(self.endpoints)
        weights = np.asarray(self.weights)
        if endpoints.ndim != 2 or endpoints.shape[1:] != (2,) or endpoints.dtype not in {
            np.dtype("<u2"), np.dtype("<u4")
        }:
            raise ValueError("endpoints must be an E x 2 compact unsigned array")
        if weights.ndim != 1 or weights.shape[0] != endpoints.shape[0] or weights.dtype != np.dtype("<f4"):
            raise ValueError("weights must be an aligned compact float32 array")
        if endpoints.flags.writeable or weights.flags.writeable:
            raise ValueError("compact arrays must be read-only")

    @property
    def edge_count(self) -> int:
        return int(self.endpoints.shape[0])

    @property
    def nbytes(self) -> int:
        return int(self.endpoints.nbytes + self.weights.nbytes)

    def iter_chunks(self, chunk_size: int = 262_144) -> Iterator[tuple[np.ndarray, np.ndarray]]:
        if isinstance(chunk_size, bool) or not isinstance(chunk_size, int) or chunk_size <= 0:
            raise ValueError("chunk_size must be a positive integer")
        for start in range(0, self.edge_count, chunk_size):
            stop = min(start + chunk_size, self.edge_count)
            yield self.endpoints[start:stop], self.weights[start:stop]


@dataclass(frozen=True, slots=True)
class CompactRelationEdges(CompactEdgeArray):
    layer: str
    relation: str

    def __post_init__(self) -> None:
        CompactEdgeArray.__post_init__(self)
        if self.layer not in IOHUNTER_LAYER_RELATIONS:
            raise ValueError("layer is not a canonical IOHunter source layer")
        if self.relation != IOHUNTER_LAYER_RELATIONS[self.layer]:
            raise ValueError("relation must match the canonical source-layer relation")


@dataclass(frozen=True, slots=True)
class CompactIOHunterManifest:
    dataset_id: str
    source_size_bytes: int
    source_mtime_ns: int
    loader_version: str = COMPACT_IOHUNTER_VERSION
    fingerprint_scope: str = COMPACT_SOURCE_LAYER_FINGERPRINT_SCOPE
    time_semantics: str = IOHUNTER_STATIC_TIME_SEMANTICS

    def __post_init__(self) -> None:
        if not self.dataset_id.startswith("iohunter-"):
            raise ValueError("dataset_id must identify an IOHunter campaign")
        if self.source_size_bytes <= 0 or self.source_mtime_ns < 0:
            raise ValueError("source size and mtime must be valid")
        if self.loader_version != COMPACT_IOHUNTER_VERSION:
            raise ValueError("loader_version is fixed")
        if self.fingerprint_scope != COMPACT_SOURCE_LAYER_FINGERPRINT_SCOPE:
            raise ValueError("fingerprint_scope is fixed")
        if self.time_semantics != IOHUNTER_STATIC_TIME_SEMANTICS:
            raise ValueError("time_semantics is fixed")

    def to_dict(self) -> dict[str, Any]:
        return {
            "dataset_id": self.dataset_id,
            "source_size_bytes": self.source_size_bytes,
            "source_mtime_ns": self.source_mtime_ns,
            "loader_version": self.loader_version,
            "fingerprint_scope": self.fingerprint_scope,
            "time_semantics": self.time_semantics,
        }


@dataclass(frozen=True, slots=True)
class CompactIOHunterDiscoveryView:
    campaign: str
    account_count: int
    relation_edges: Mapping[str, CompactRelationEdges]
    time_semantics: str
    source_layer_fingerprint: str
    manifest: CompactIOHunterManifest

    def __post_init__(self) -> None:
        object.__setattr__(self, "campaign", _validate_campaign(self.campaign))
        if isinstance(self.account_count, bool) or not isinstance(self.account_count, int) or self.account_count <= 0:
            raise ValueError("account_count must be a positive integer")
        if not isinstance(self.relation_edges, MappingABC) or set(self.relation_edges) != set(IOHUNTER_LAYER_RELATIONS):
            raise ValueError("relation_edges must contain exactly the five canonical source layers")
        normalized = {}
        for layer in sorted(self.relation_edges):
            edges = self.relation_edges[layer]
            if not isinstance(edges, CompactRelationEdges) or edges.layer != layer:
                raise ValueError("relation_edges values must match their source layers")
            normalized[layer] = edges
        object.__setattr__(self, "relation_edges", MappingProxyType(normalized))
        if self.time_semantics != IOHUNTER_STATIC_TIME_SEMANTICS:
            raise ValueError("IOHunter compact discovery time semantics are static")
        object.__setattr__(
            self,
            "source_layer_fingerprint",
            _validate_sha256(self.source_layer_fingerprint, "source_layer_fingerprint"),
        )
        if not isinstance(self.manifest, CompactIOHunterManifest):
            raise ValueError("manifest must be CompactIOHunterManifest")


@dataclass(frozen=True, slots=True)
class CompactIOHunterFold:
    fold_id: str
    train_indices: np.ndarray
    validation_indices: np.ndarray
    test_indices: np.ndarray

    def __post_init__(self) -> None:
        if not isinstance(self.fold_id, str) or not self.fold_id.startswith("fold-") or not self.fold_id[5:].isdigit():
            raise ValueError("fold_id must be fold-NNN")
        object.__setattr__(self, "fold_id", f"fold-{int(self.fold_id[5:]):03d}")
        dtype = None
        for name in ("train_indices", "validation_indices", "test_indices"):
            values = np.asarray(getattr(self, name))
            if values.ndim != 1 or values.size == 0 or values.dtype not in {np.dtype("<u2"), np.dtype("<u4")}:
                raise ValueError(f"{name} must be a non-empty compact index array")
            if values.flags.writeable:
                raise ValueError(f"{name} must be read-only")
            dtype = dtype or values.dtype
            if values.dtype != dtype:
                raise ValueError("fold index arrays must share one dtype")

    def to_dict(self) -> dict[str, Any]:
        return {
            "fold_id": self.fold_id,
            "train_indices": self.train_indices.tolist(),
            "validation_indices": self.validation_indices.tolist(),
            "test_indices": self.test_indices.tolist(),
        }


@dataclass(frozen=True, slots=True)
class CompactIOHunterEvaluator:
    campaign: str
    account_labels: np.ndarray
    official_folds: tuple[CompactIOHunterFold, ...]
    fused_edges: CompactEdgeArray
    source_path: str
    source_sha256: str
    semantic_content_fingerprint: str
    content_fingerprint: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "campaign", _validate_campaign(self.campaign))
        labels = np.asarray(self.account_labels)
        if labels.ndim != 1 or labels.size == 0 or labels.dtype != np.dtype("u1") or labels.flags.writeable:
            raise ValueError("account_labels must be a non-empty read-only uint8 array")
        if len(self.official_folds) != 5 or not all(isinstance(fold, CompactIOHunterFold) for fold in self.official_folds):
            raise ValueError("evaluator requires exactly five official folds")
        if tuple(fold.fold_id for fold in self.official_folds) != tuple(f"fold-{index:03d}" for index in range(5)):
            raise ValueError("official folds must have stable fold-000 through fold-004 identities")
        if not isinstance(self.fused_edges, CompactEdgeArray):
            raise ValueError("fused_edges must be CompactEdgeArray")
        if not isinstance(self.source_path, str) or not self.source_path:
            raise ValueError("source_path must be non-empty")
        object.__setattr__(self, "source_sha256", _validate_sha256(self.source_sha256, "source_sha256"))
        object.__setattr__(
            self,
            "semantic_content_fingerprint",
            _validate_sha256(self.semantic_content_fingerprint, "semantic_content_fingerprint"),
        )
        object.__setattr__(
            self,
            "content_fingerprint",
            _validate_sha256(self.content_fingerprint, "content_fingerprint"),
        )


@dataclass(frozen=True, slots=True)
class CompactIOHunterMemoryProfile:
    source_bytes: int
    compact_array_bytes: int
    measured_peak_bytes: int
    estimated_peak_bytes: int
    memory_budget_bytes: int
    within_budget: bool
    model_execution_started: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_bytes": self.source_bytes,
            "compact_array_bytes": self.compact_array_bytes,
            "measured_peak_bytes": self.measured_peak_bytes,
            "estimated_peak_bytes": self.estimated_peak_bytes,
            "memory_budget_bytes": self.memory_budget_bytes,
            "within_budget": self.within_budget,
            "model_execution_started": self.model_execution_started,
        }


class CompactIOHunterMemoryBudgetExceeded(MemoryError):
    def __init__(self, memory_profile: CompactIOHunterMemoryProfile) -> None:
        self.memory_profile = memory_profile
        super().__init__(
            "compact IOHunter estimated peak memory "
            f"{memory_profile.estimated_peak_bytes} exceeds configured budget "
            f"{memory_profile.memory_budget_bytes} before model execution"
        )


@dataclass(frozen=True, slots=True)
class CompactIOHunterLoadResult:
    discovery_view: CompactIOHunterDiscoveryView
    evaluator: CompactIOHunterEvaluator
    memory_profile: CompactIOHunterMemoryProfile


@dataclass(frozen=True, slots=True)
class _SourceSnapshot:
    size: int
    mtime_ns: int
    device: int
    inode: int

    @classmethod
    def from_stat(cls, value: os.stat_result) -> "_SourceSnapshot":
        return cls(
            size=int(value.st_size),
            mtime_ns=int(value.st_mtime_ns),
            device=int(value.st_dev),
            inode=int(value.st_ino),
        )

class _MemoryProbe:
    def __init__(self) -> None:
        self._started = not tracemalloc.is_tracing()
        if self._started:
            tracemalloc.start()
        self._baseline = tracemalloc.get_traced_memory()[0]
        tracemalloc.reset_peak()

    def peak_bytes(self) -> int:
        _, peak = tracemalloc.get_traced_memory()
        return max(1, int(peak - self._baseline))

    def close(self) -> None:
        if self._started and tracemalloc.is_tracing():
            tracemalloc.stop()


def _hash_mapped(mapped: io.BytesIO) -> str:
    digest = hashlib.sha256()
    view = mapped.getbuffer()
    try:
        for start in range(0, len(view), 8 * 1024 * 1024):
            digest.update(view[start : start + 8 * 1024 * 1024])
    finally:
        view.release()
    return f"sha256:{digest.hexdigest()}"


def _unpickle_mapped(mapped: io.BytesIO) -> Any:
    mapped.seek(0)
    return pickle.Unpickler(mapped).load()


def _graph(value: Any, name: str) -> nx.Graph:
    if not isinstance(value, nx.Graph) or value.is_directed():
        raise ValueError(f"{name} must be an undirected NetworkX graph")
    return value


def _node(value: Any, graph_name: str) -> int:
    if isinstance(value, (bool, np.bool_)) or not isinstance(value, (int, np.integer)):
        raise ValueError(f"{graph_name} node IDs must be non-negative integers")
    result = int(value)
    if result < 0:
        raise ValueError(f"{graph_name} node IDs must be non-negative integers")
    return result


def _edge_records(graph: nx.Graph, graph_name: str, account_count: int) -> CompactEdgeArray:
    index_dtype = _index_dtype(account_count)
    record_dtype = np.dtype(
        [("left", index_dtype), ("right", index_dtype), ("weight", "<f4")], align=False
    )
    records = np.empty(graph.number_of_edges(), dtype=record_dtype)
    count = 0
    edges = graph.edges(data=True, keys=True) if graph.is_multigraph() else graph.edges(data=True)
    for raw_edge in edges:
        if graph.is_multigraph():
            left_raw, right_raw, _key, data = raw_edge
        else:
            left_raw, right_raw, data = raw_edge
        left = _node(left_raw, graph_name)
        right = _node(right_raw, graph_name)
        if left >= account_count or right >= account_count:
            raise ValueError(f"{graph_name} edge references an account outside the canonical universe")
        if left == right:
            continue
        if left > right:
            left, right = right, left
        raw_weight = data.get("weight", 1.0)
        if isinstance(raw_weight, (bool, np.bool_)) or not isinstance(raw_weight, Real):
            raise ValueError(f"{graph_name} edge weight must be numeric")
        weight = float(raw_weight)
        if (
            not math.isfinite(weight)
            or weight <= 0.0
            or weight > float(np.finfo(np.float32).max)
        ):
            raise ValueError(f"{graph_name} edge weight must be positive finite compact float32")
        records[count] = (left, right, weight)
        count += 1
    records = records[:count]
    records.sort(order=("left", "right"), kind="quicksort")
    if count > 1:
        duplicate = (records["left"][1:] == records["left"][:-1]) & (
            records["right"][1:] == records["right"][:-1]
        )
        if bool(np.any(duplicate)):
            raise ValueError(f"{graph_name} contains a duplicate normalized edge")
    endpoints = np.empty((count, 2), dtype=index_dtype)
    endpoints[:, 0] = records["left"]
    endpoints[:, 1] = records["right"]
    weights = np.asarray(records["weight"], dtype=np.dtype("<f4"))
    return CompactEdgeArray(
        endpoints=_immutable_array(endpoints, dtype=index_dtype, shape=(count, 2)),
        weights=_immutable_array(weights, dtype=np.dtype("<f4"), shape=(count,)),
    )


def _source_relations(payload: Mapping[str, Any], account_count: int) -> Mapping[str, CompactRelationEdges]:
    canonical_nodes = set(range(account_count))
    source_node_union: set[int] = set()
    result = {}
    for layer in sorted(IOHUNTER_LAYER_RELATIONS):
        graph = _graph(payload[layer], layer)
        layer_nodes = {_node(value, layer) for value in graph.nodes}
        if not layer_nodes <= canonical_nodes:
            raise ValueError(f"{layer} source-layer node universe exceeds the canonical contiguous account universe")
        source_node_union.update(layer_nodes)
        edges = _edge_records(graph, layer, account_count)
        result[layer] = CompactRelationEdges(
            endpoints=edges.endpoints,
            weights=edges.weights,
            layer=layer,
            relation=IOHUNTER_LAYER_RELATIONS[layer],
        )
    if source_node_union != canonical_nodes:
        raise ValueError(
            "source-layer node-universe union must equal the canonical contiguous account universe"
        )
    return MappingProxyType(result)


def _labels(value: Any) -> np.ndarray:
    if hasattr(value, "detach"):
        value = value.detach().cpu()
    labels = np.asarray(value)
    if labels.ndim != 1 or labels.size == 0:
        raise ValueError("labels must be a non-empty aligned one-dimensional array")
    if labels.dtype.kind not in {"i", "u", "f"}:
        raise ValueError("labels must be binary numeric values")
    numeric = labels.astype(np.float64, copy=False)
    if not bool(np.all(np.isfinite(numeric))) or not bool(np.all((numeric == 0.0) | (numeric == 1.0))):
        raise ValueError("labels must be binary numeric values")
    return _immutable_array(numeric.astype(np.uint8), dtype=np.dtype("u1"), shape=(labels.size,))


def _mask(value: Any, account_count: int, field_name: str) -> np.ndarray:
    if hasattr(value, "detach"):
        value = value.detach().cpu()
    result = np.asarray(value)
    if result.ndim != 1 or result.shape[0] != account_count or result.dtype.kind != "b":
        raise ValueError(f"{field_name} must be an aligned boolean mask")
    return result


def _folds(value: Any, account_count: int) -> tuple[CompactIOHunterFold, ...]:
    if not isinstance(value, MappingABC) or len(value) != 5:
        raise ValueError("IOHunter evaluator requires exactly five official folds")
    normalized: dict[int, Mapping[str, Any]] = {}
    for raw_id, raw_fold in value.items():
        if isinstance(raw_id, bool):
            raise ValueError("official fold IDs must be integers 0 through 4")
        try:
            fold_id = int(raw_id)
        except (TypeError, ValueError) as exc:
            raise ValueError("official fold IDs must be integers 0 through 4") from exc
        if str(raw_id) not in {str(fold_id), f"fold-{fold_id:03d}"} or fold_id not in range(5):
            raise ValueError("official fold IDs must be integers 0 through 4")
        if fold_id in normalized or not isinstance(raw_fold, MappingABC):
            raise ValueError("official folds must be unique partition mappings")
        normalized[fold_id] = raw_fold
    if set(normalized) != set(range(5)):
        raise ValueError("official folds must be fold-000 through fold-004")
    index_dtype = _index_dtype(account_count)
    result = []
    for fold_id in range(5):
        raw_fold = normalized[fold_id]
        keys = set(raw_fold)
        if keys == {"train", "val", "test"}:
            validation_name = "val"
        elif keys == {"train", "validation", "test"}:
            validation_name = "validation"
        else:
            raise ValueError(f"fold-{fold_id:03d} must contain train, validation/val, and test masks")
        train = _mask(raw_fold["train"], account_count, f"fold-{fold_id:03d} train")
        validation = _mask(raw_fold[validation_name], account_count, f"fold-{fold_id:03d} validation")
        test = _mask(raw_fold["test"], account_count, f"fold-{fold_id:03d} test")
        membership = train.astype(np.uint8) + validation.astype(np.uint8) + test.astype(np.uint8)
        if not bool(np.all(membership == 1)) or not bool(train.any() and validation.any() and test.any()):
            raise ValueError(f"fold-{fold_id:03d} partitions must be non-empty, disjoint, and cover the account universe")

        def indices(mask: np.ndarray) -> np.ndarray:
            raw = np.flatnonzero(mask).astype(index_dtype, copy=False)
            return _immutable_array(raw, dtype=index_dtype, shape=(raw.size,))

        result.append(
            CompactIOHunterFold(
                fold_id=f"fold-{fold_id:03d}",
                train_indices=indices(train),
                validation_indices=indices(validation),
                test_indices=indices(test),
            )
        )
    return tuple(result)


def _source_layer_fingerprint(
    campaign: str, account_count: int, relation_edges: Mapping[str, CompactRelationEdges]
) -> str:
    parts = [
        _canonical_json(
            {
                "scope": COMPACT_SOURCE_LAYER_FINGERPRINT_SCOPE,
                "campaign": campaign,
                "account_count": account_count,
            }
        )
    ]
    for layer, edges in relation_edges.items():
        parts.extend(
            (
                _canonical_json({"layer": layer, "relation": edges.relation}),
                edges.endpoints.tobytes(order="C"),
                edges.weights.tobytes(order="C"),
            )
        )
    return _hash_parts(*parts)


def _fold_fingerprint(fold: CompactIOHunterFold) -> str:
    return _hash_parts(
        _canonical_json({"scope": "iohunter-official-fold/compact-v1", "fold_id": fold.fold_id}),
        fold.train_indices.tobytes(),
        fold.validation_indices.tobytes(),
        fold.test_indices.tobytes(),
    )


def compact_fold_fingerprint(fold: CompactIOHunterFold) -> str:
    if not isinstance(fold, CompactIOHunterFold):
        raise ValueError("fold must be CompactIOHunterFold")
    return _fold_fingerprint(fold)


def _evaluator_fingerprints(
    campaign: str,
    labels: np.ndarray,
    folds: tuple[CompactIOHunterFold, ...],
    fused_edges: CompactEdgeArray,
    source_path: str,
    source_sha256: str,
) -> tuple[str, str]:
    semantic = _hash_parts(
        _canonical_json(
            {
                "scope": COMPACT_EVALUATOR_FINGERPRINT_SCOPE,
                "campaign": campaign,
                "fold_ids": [fold.fold_id for fold in folds],
            }
        ),
        labels.tobytes(),
        *(
            part
            for fold in folds
            for part in (
                fold.train_indices.tobytes(),
                fold.validation_indices.tobytes(),
                fold.test_indices.tobytes(),
            )
        ),
        fused_edges.endpoints.tobytes(),
        fused_edges.weights.tobytes(),
    )
    content = _hash_parts(
        _canonical_json({"scope": COMPACT_EVALUATOR_FINGERPRINT_SCOPE, "source_path": source_path}),
        source_sha256.encode("ascii"),
        semantic.encode("ascii"),
    )
    return semantic, content


def _profile(
    *, source_bytes: int, compact_array_bytes: int, measured_peak_bytes: int, memory_budget_bytes: int
) -> CompactIOHunterMemoryProfile:
    estimated = max(
        measured_peak_bytes,
        source_bytes * _SOURCE_ESTIMATE_MULTIPLIER + compact_array_bytes * 2,
    )
    return CompactIOHunterMemoryProfile(
        source_bytes=source_bytes,
        compact_array_bytes=compact_array_bytes,
        measured_peak_bytes=measured_peak_bytes,
        estimated_peak_bytes=estimated,
        memory_budget_bytes=memory_budget_bytes,
        within_budget=estimated <= memory_budget_bytes,
    )


def load_compact_iohunter(
    path: str | Path,
    *,
    campaign: str,
    trusted_local: bool = False,
    memory_budget_bytes: int = DEFAULT_COMPACT_MEMORY_BUDGET_BYTES,
) -> CompactIOHunterLoadResult:
    if trusted_local is not True:
        raise ValueError("pickle deserialization requires explicit trusted_local=True")
    campaign = _validate_campaign(campaign)
    if isinstance(memory_budget_bytes, bool) or not isinstance(memory_budget_bytes, int) or memory_budget_bytes <= 0:
        raise ValueError("memory_budget_bytes must be a positive integer")
    source = Path(path).resolve(strict=True)
    probe = _MemoryProbe()
    try:
        with source.open("rb") as handle:
            initial = _SourceSnapshot.from_stat(os.fstat(handle.fileno()))
            if _SourceSnapshot.from_stat(source.stat()) != initial:
                raise RuntimeError("mapped IOHunter source identity changed before loading")
            early = _profile(
                source_bytes=initial.size,
                compact_array_bytes=0,
                measured_peak_bytes=probe.peak_bytes(),
                memory_budget_bytes=memory_budget_bytes,
            )
            if not early.within_budget:
                raise CompactIOHunterMemoryBudgetExceeded(early)
            source_bytes = handle.read()
        if len(source_bytes) != initial.size:
            raise RuntimeError("mapped IOHunter source identity changed during loading")
        mapped = io.BytesIO(source_bytes)
        source_sha256 = _hash_mapped(mapped)
        payload = _unpickle_mapped(mapped)
        if _SourceSnapshot.from_stat(source.stat()) != initial:
            raise RuntimeError("mapped IOHunter source identity changed during loading")
        if not isinstance(payload, MappingABC) or set(payload) != _EXPECTED_KEYS:
            raise ValueError("IOHunter pickle payload must contain exactly the compact-v1 source fields")
        labels = _labels(payload["labels"])
        account_count = int(labels.size)
        fused_graph = _graph(payload["graph"], "fused graph")
        fused_nodes = {_node(value, "fused graph") for value in fused_graph.nodes}
        if fused_nodes != set(range(account_count)):
            raise ValueError("fused graph node universe must equal labels and contiguous account IDs")
        relation_edges = _source_relations(payload, account_count)
        folds = _folds(payload["splits"], account_count)
        fused_edges = _edge_records(fused_graph, "fused graph", account_count)
        source_fingerprint = _source_layer_fingerprint(campaign, account_count, relation_edges)
        semantic_evaluator, content_evaluator = _evaluator_fingerprints(
            campaign,
            labels,
            folds,
            fused_edges,
            str(source),
            source_sha256,
        )
        if _SourceSnapshot.from_stat(source.stat()) != initial:
            raise RuntimeError("mapped IOHunter source identity changed during loading")

        compact_array_bytes = sum(edges.nbytes for edges in relation_edges.values())
        compact_array_bytes += labels.nbytes + fused_edges.nbytes
        compact_array_bytes += sum(
            fold.train_indices.nbytes + fold.validation_indices.nbytes + fold.test_indices.nbytes
            for fold in folds
        )
        memory_profile = _profile(
            source_bytes=initial.size,
            compact_array_bytes=int(compact_array_bytes),
            measured_peak_bytes=probe.peak_bytes(),
            memory_budget_bytes=memory_budget_bytes,
        )
        if not memory_profile.within_budget:
            raise CompactIOHunterMemoryBudgetExceeded(memory_profile)
        manifest = CompactIOHunterManifest(
            dataset_id=f"iohunter-{campaign}",
            source_size_bytes=initial.size,
            source_mtime_ns=initial.mtime_ns,
        )
        discovery = CompactIOHunterDiscoveryView(
            campaign=campaign,
            account_count=account_count,
            relation_edges=relation_edges,
            time_semantics=IOHUNTER_STATIC_TIME_SEMANTICS,
            source_layer_fingerprint=source_fingerprint,
            manifest=manifest,
        )
        evaluator = CompactIOHunterEvaluator(
            campaign=campaign,
            account_labels=labels,
            official_folds=folds,
            fused_edges=fused_edges,
            source_path=str(source),
            source_sha256=source_sha256,
            semantic_content_fingerprint=semantic_evaluator,
            content_fingerprint=content_evaluator,
        )
        return CompactIOHunterLoadResult(
            discovery_view=discovery,
            evaluator=evaluator,
            memory_profile=memory_profile,
        )
    finally:
        probe.close()


__all__ = [
    "COMPACT_EVALUATOR_FINGERPRINT_SCOPE",
    "COMPACT_IOHUNTER_VERSION",
    "COMPACT_SOURCE_LAYER_FINGERPRINT_SCOPE",
    "DEFAULT_COMPACT_MEMORY_BUDGET_BYTES",
    "IOHUNTER_STATIC_TIME_SEMANTICS",
    "CompactEdgeArray",
    "CompactIOHunterDiscoveryView",
    "CompactIOHunterEvaluator",
    "CompactIOHunterFold",
    "CompactIOHunterLoadResult",
    "CompactIOHunterManifest",
    "CompactIOHunterMemoryBudgetExceeded",
    "CompactIOHunterMemoryProfile",
    "CompactRelationEdges",
    "compact_fold_fingerprint",
    "load_compact_iohunter",
]
