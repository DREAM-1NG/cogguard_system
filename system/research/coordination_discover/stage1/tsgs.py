from __future__ import annotations

import hashlib
import math
import time
from collections import defaultdict
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import TypeAlias

import numpy as np

from .events import CoordinationEvent


Feature: TypeAlias = tuple[str, str, int]
SparseActivityVector: TypeAlias = dict[Feature, float]
AccountPair: TypeAlias = tuple[str, str]

EXACT_RESISTANCE_BACKEND = "exact_laplacian_pseudoinverse"
APPROXIMATE_RESISTANCE_BACKEND = "diagonal_degree_resistance_approximation"
GUARANTEE_SCOPE = "candidate_graph_only"


def _positive_int(value: object, field_name: str, *, minimum: int = 1) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise ValueError(f"{field_name} must be an integer >= {minimum}")
    return value


def _finite_float(value: object, field_name: str, *, minimum: float, maximum: float | None = None) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{field_name} must be numeric")
    number = float(value)
    if not math.isfinite(number) or number < minimum or (maximum is not None and number > maximum):
        raise ValueError(f"{field_name} is outside its supported finite range")
    return number


@dataclass(frozen=True, slots=True)
class TSGSConfig:
    time_bucket_seconds: int = 300
    hyperplane_count: int = 24
    band_size: int = 3
    bucket_cap: int = 64
    min_cosine_similarity: float = 0.0
    sampling_multiplier: float = 1.0
    exact_resistance_max_nodes: int = 256
    audit_vector_count: int = 64
    audit_tolerance: float = 0.35
    seed: int = 0

    def __post_init__(self) -> None:
        object.__setattr__(self, "time_bucket_seconds", _positive_int(self.time_bucket_seconds, "time_bucket_seconds"))
        object.__setattr__(self, "hyperplane_count", _positive_int(self.hyperplane_count, "hyperplane_count"))
        object.__setattr__(self, "band_size", _positive_int(self.band_size, "band_size"))
        object.__setattr__(self, "bucket_cap", _positive_int(self.bucket_cap, "bucket_cap", minimum=2))
        object.__setattr__(
            self,
            "min_cosine_similarity",
            _finite_float(self.min_cosine_similarity, "min_cosine_similarity", minimum=0.0, maximum=1.0),
        )
        object.__setattr__(
            self,
            "sampling_multiplier",
            _finite_float(self.sampling_multiplier, "sampling_multiplier", minimum=np.finfo(float).tiny),
        )
        object.__setattr__(
            self,
            "exact_resistance_max_nodes",
            _positive_int(self.exact_resistance_max_nodes, "exact_resistance_max_nodes"),
        )
        object.__setattr__(self, "audit_vector_count", _positive_int(self.audit_vector_count, "audit_vector_count"))
        object.__setattr__(
            self,
            "audit_tolerance",
            _finite_float(self.audit_tolerance, "audit_tolerance", minimum=0.0),
        )
        if isinstance(self.seed, bool) or not isinstance(self.seed, int):
            raise ValueError("seed must be an integer")


@dataclass(frozen=True, slots=True, order=True)
class WeightedEdge:
    source_account_id: str
    target_account_id: str
    weight: float

    def __post_init__(self) -> None:
        if self.source_account_id >= self.target_account_id:
            raise ValueError("weighted edge account IDs must be sorted and distinct")
        if not math.isfinite(self.weight) or self.weight <= 0.0:
            raise ValueError("weighted edge weight must be finite and positive")


@dataclass(frozen=True, slots=True)
class BucketDiagnostics:
    bucket_count: int
    non_singleton_bucket_count: int
    capped_bucket_count: int
    max_bucket_size: int
    dropped_membership_count: int
    generated_pair_occurrence_count: int


@dataclass(frozen=True, slots=True)
class TSGSTimings:
    vectorization_seconds: float
    candidate_discovery_seconds: float
    cosine_scoring_seconds: float
    resistance_sampling_seconds: float
    spectral_audit_seconds: float
    total_seconds: float


@dataclass(frozen=True, slots=True)
class SpectralAudit:
    empirical: bool
    reference_graph: str
    sample_count: int
    tolerance: float
    observed_min_ratio: float
    observed_max_ratio: float
    observed_min_distortion: float
    observed_max_distortion: float
    passed: bool


@dataclass(frozen=True, slots=True)
class TSGSResult:
    account_ids: tuple[str, ...]
    candidate_pair_count: int
    full_pair_count: int
    candidate_reduction: float
    bucket_diagnostics: BucketDiagnostics
    candidate_graph_edges: tuple[WeightedEdge, ...]
    sampled_edges: tuple[WeightedEdge, ...]
    timings: TSGSTimings
    memory_estimate_bytes: int
    resistance_backend: str
    guarantee_scope: str
    audit: SpectralAudit

    @property
    def candidate_graph_edge_count(self) -> int:
        return len(self.candidate_graph_edges)


def _build_sparse_activity_vectors(
    events: Iterable[CoordinationEvent], time_bucket_seconds: int
) -> dict[str, SparseActivityVector]:
    vectors: defaultdict[str, defaultdict[Feature, float]] = defaultdict(lambda: defaultdict(float))
    for event in events:
        if not isinstance(event, CoordinationEvent):
            raise ValueError("events must contain CoordinationEvent values")
        time_bucket = math.floor(event.observed_at.timestamp() / time_bucket_seconds)
        feature = (event.relation, event.object_id, time_bucket)
        vector = vectors[event.account_id]
        if event.weight > 0.0:
            vector[feature] += event.weight
    return {
        account_id: dict(sorted(vector.items()))
        for account_id, vector in sorted(vectors.items())
    }


def _projection_sign(seed: int, plane_index: int, feature: Feature) -> float:
    relation, object_id, time_bucket = feature
    payload = f"{seed}\0{plane_index}\0{relation}\0{object_id}\0{time_bucket}".encode("utf-8")
    digest = hashlib.blake2b(payload, digest_size=8, person=b"tsgs-plane").digest()
    return 1.0 if digest[0] & 1 else -1.0


def _signature(vector: Mapping[Feature, float], config: TSGSConfig) -> tuple[int, ...]:
    ordered_features = tuple(sorted(vector.items()))
    return tuple(
        int(sum(weight * _projection_sign(config.seed, plane_index, feature) for feature, weight in ordered_features) >= 0.0)
        for plane_index in range(config.hyperplane_count)
    )


def _cap_rank(seed: int, band_index: int, band_signature: tuple[int, ...], account_id: str) -> tuple[bytes, str]:
    bits = "".join(map(str, band_signature))
    payload = f"{seed}\0{band_index}\0{bits}\0{account_id}".encode("utf-8")
    digest = hashlib.blake2b(payload, digest_size=16, person=b"tsgs-cap").digest()
    return digest, account_id


def _discover_candidate_pairs(
    vectors: Mapping[str, SparseActivityVector], config: TSGSConfig
) -> tuple[tuple[AccountPair, ...], BucketDiagnostics]:
    buckets: defaultdict[tuple[int, tuple[int, ...]], list[str]] = defaultdict(list)
    for account_id in sorted(vectors):
        signature = _signature(vectors[account_id], config)
        for band_index, start in enumerate(range(0, config.hyperplane_count, config.band_size)):
            band_signature = signature[start : start + config.band_size]
            buckets[(band_index, band_signature)].append(account_id)

    candidates: set[AccountPair] = set()
    capped_bucket_count = 0
    dropped_membership_count = 0
    generated_pair_occurrence_count = 0
    max_bucket_size = 0
    non_singleton_bucket_count = 0
    for (band_index, band_signature), raw_members in sorted(buckets.items()):
        max_bucket_size = max(max_bucket_size, len(raw_members))
        if len(raw_members) < 2:
            continue
        non_singleton_bucket_count += 1
        members = raw_members
        if len(members) > config.bucket_cap:
            capped_bucket_count += 1
            dropped_membership_count += len(members) - config.bucket_cap
            members = sorted(
                members,
                key=lambda account_id: _cap_rank(config.seed, band_index, band_signature, account_id),
            )[: config.bucket_cap]
        else:
            members = sorted(members)
        generated_pair_occurrence_count += len(members) * (len(members) - 1) // 2
        for left_index in range(len(members) - 1):
            for right_index in range(left_index + 1, len(members)):
                left, right = members[left_index], members[right_index]
                candidates.add((left, right) if left < right else (right, left))

    diagnostics = BucketDiagnostics(
        bucket_count=len(buckets),
        non_singleton_bucket_count=non_singleton_bucket_count,
        capped_bucket_count=capped_bucket_count,
        max_bucket_size=max_bucket_size,
        dropped_membership_count=dropped_membership_count,
        generated_pair_occurrence_count=generated_pair_occurrence_count,
    )
    return tuple(sorted(candidates)), diagnostics


def _exact_cosine(left: Mapping[Feature, float], right: Mapping[Feature, float]) -> float:
    left_norm = math.sqrt(sum(value * value for value in left.values()))
    right_norm = math.sqrt(sum(value * value for value in right.values()))
    if left_norm == 0.0 or right_norm == 0.0:
        return 0.0
    smaller, larger = (left, right) if len(left) <= len(right) else (right, left)
    dot_product = sum(smaller[feature] * larger.get(feature, 0.0) for feature in sorted(smaller))
    return min(1.0, max(0.0, dot_product / (left_norm * right_norm)))


def _score_candidate_graph(
    candidate_pairs: Iterable[AccountPair],
    vectors: Mapping[str, SparseActivityVector],
    minimum_similarity: float,
) -> tuple[WeightedEdge, ...]:
    edges = []
    for left, right in candidate_pairs:
        similarity = _exact_cosine(vectors[left], vectors[right])
        if similarity > 0.0 and similarity >= minimum_similarity:
            edges.append(WeightedEdge(left, right, similarity))
    return tuple(edges)


def _exact_effective_resistances(
    account_ids: tuple[str, ...], edges: tuple[WeightedEdge, ...]
) -> tuple[float, ...]:
    node_index = {account_id: index for index, account_id in enumerate(account_ids)}
    laplacian = np.zeros((len(account_ids), len(account_ids)), dtype=float)
    for edge in edges:
        left = node_index[edge.source_account_id]
        right = node_index[edge.target_account_id]
        laplacian[left, left] += edge.weight
        laplacian[right, right] += edge.weight
        laplacian[left, right] -= edge.weight
        laplacian[right, left] -= edge.weight
    pseudoinverse = np.linalg.pinv(laplacian, hermitian=True)
    resistances = []
    for edge in edges:
        left = node_index[edge.source_account_id]
        right = node_index[edge.target_account_id]
        resistance = pseudoinverse[left, left] + pseudoinverse[right, right] - 2.0 * pseudoinverse[left, right]
        resistances.append(max(0.0, float(resistance)))
    return tuple(resistances)


def _diagonal_degree_resistance_approximation(
    account_ids: tuple[str, ...], edges: tuple[WeightedEdge, ...]
) -> tuple[float, ...]:
    degrees = dict.fromkeys(account_ids, 0.0)
    for edge in edges:
        degrees[edge.source_account_id] += edge.weight
        degrees[edge.target_account_id] += edge.weight
    return tuple(
        1.0 / degrees[edge.source_account_id] + 1.0 / degrees[edge.target_account_id]
        for edge in edges
    )


def _sample_candidate_graph(
    account_ids: tuple[str, ...], edges: tuple[WeightedEdge, ...], config: TSGSConfig
) -> tuple[tuple[WeightedEdge, ...], str]:
    if len(account_ids) <= config.exact_resistance_max_nodes:
        resistances = _exact_effective_resistances(account_ids, edges)
        backend = EXACT_RESISTANCE_BACKEND
    else:
        resistances = _diagonal_degree_resistance_approximation(account_ids, edges)
        backend = APPROXIMATE_RESISTANCE_BACKEND

    rng = np.random.default_rng(config.seed ^ 0x54534753)
    log_factor = math.log(max(2, len(account_ids)))
    sampled_edges = []
    for edge, resistance in zip(edges, resistances, strict=True):
        probability = min(1.0, config.sampling_multiplier * log_factor * edge.weight * resistance)
        if probability > 0.0 and rng.random() <= probability:
            sampled_edges.append(
                WeightedEdge(edge.source_account_id, edge.target_account_id, edge.weight / probability)
            )
    return tuple(sampled_edges), backend


def _quadratic_form(vector: np.ndarray, node_index: Mapping[str, int], edges: Iterable[WeightedEdge]) -> float:
    return float(
        sum(
            edge.weight
            * (vector[node_index[edge.source_account_id]] - vector[node_index[edge.target_account_id]]) ** 2
            for edge in edges
        )
    )


def _spectral_audit(
    account_ids: tuple[str, ...],
    candidate_edges: tuple[WeightedEdge, ...],
    sampled_edges: tuple[WeightedEdge, ...],
    config: TSGSConfig,
) -> SpectralAudit:
    node_index = {account_id: index for index, account_id in enumerate(account_ids)}
    rng = np.random.default_rng(config.seed ^ 0x41554449)
    ratios = []
    for _ in range(config.audit_vector_count):
        vector = rng.standard_normal(len(account_ids))
        candidate_energy = _quadratic_form(vector, node_index, candidate_edges)
        if candidate_energy <= np.finfo(float).eps:
            continue
        sampled_energy = _quadratic_form(vector, node_index, sampled_edges)
        ratios.append(sampled_energy / candidate_energy)

    if ratios:
        observed_min = min(ratios)
        observed_max = max(ratios)
        distortions = [abs(ratio - 1.0) for ratio in ratios]
        min_distortion = min(distortions)
        max_distortion = max(distortions)
    else:
        observed_min = observed_max = 1.0
        min_distortion = max_distortion = 0.0
    return SpectralAudit(
        empirical=True,
        reference_graph="candidate_graph",
        sample_count=len(ratios),
        tolerance=config.audit_tolerance,
        observed_min_ratio=float(observed_min),
        observed_max_ratio=float(observed_max),
        observed_min_distortion=float(min_distortion),
        observed_max_distortion=float(max_distortion),
        passed=max_distortion <= config.audit_tolerance,
    )


def _estimate_memory_bytes(
    vectors: Mapping[str, SparseActivityVector],
    candidate_pair_count: int,
    candidate_edge_count: int,
    sampled_edge_count: int,
) -> int:
    nonzero_count = sum(len(vector) for vector in vectors.values())
    return (
        len(vectors) * 96
        + nonzero_count * 112
        + candidate_pair_count * 72
        + candidate_edge_count * 80
        + sampled_edge_count * 80
    )


class TemporalSketchGraphSparsifier:
    def __init__(self, config: TSGSConfig | None = None) -> None:
        self.config = config or TSGSConfig()
        if not isinstance(self.config, TSGSConfig):
            raise ValueError("config must be a TSGSConfig")

    def fit_transform(self, events: Iterable[CoordinationEvent]) -> TSGSResult:
        total_started = time.perf_counter()

        phase_started = time.perf_counter()
        vectors = _build_sparse_activity_vectors(events, self.config.time_bucket_seconds)
        vectorization_seconds = time.perf_counter() - phase_started
        account_ids = tuple(vectors)
        full_pair_count = len(account_ids) * (len(account_ids) - 1) // 2

        phase_started = time.perf_counter()
        candidate_pairs, bucket_diagnostics = _discover_candidate_pairs(vectors, self.config)
        candidate_discovery_seconds = time.perf_counter() - phase_started

        phase_started = time.perf_counter()
        candidate_edges = _score_candidate_graph(
            candidate_pairs, vectors, self.config.min_cosine_similarity
        )
        cosine_scoring_seconds = time.perf_counter() - phase_started

        phase_started = time.perf_counter()
        sampled_edges, resistance_backend = _sample_candidate_graph(
            account_ids, candidate_edges, self.config
        )
        resistance_sampling_seconds = time.perf_counter() - phase_started

        phase_started = time.perf_counter()
        audit = _spectral_audit(account_ids, candidate_edges, sampled_edges, self.config)
        spectral_audit_seconds = time.perf_counter() - phase_started
        total_seconds = time.perf_counter() - total_started

        candidate_pair_count = len(candidate_pairs)
        candidate_reduction = (
            1.0 - candidate_pair_count / full_pair_count if full_pair_count else 0.0
        )
        return TSGSResult(
            account_ids=account_ids,
            candidate_pair_count=candidate_pair_count,
            full_pair_count=full_pair_count,
            candidate_reduction=candidate_reduction,
            bucket_diagnostics=bucket_diagnostics,
            candidate_graph_edges=candidate_edges,
            sampled_edges=sampled_edges,
            timings=TSGSTimings(
                vectorization_seconds=vectorization_seconds,
                candidate_discovery_seconds=candidate_discovery_seconds,
                cosine_scoring_seconds=cosine_scoring_seconds,
                resistance_sampling_seconds=resistance_sampling_seconds,
                spectral_audit_seconds=spectral_audit_seconds,
                total_seconds=total_seconds,
            ),
            memory_estimate_bytes=_estimate_memory_bytes(
                vectors, candidate_pair_count, len(candidate_edges), len(sampled_edges)
            ),
            resistance_backend=resistance_backend,
            guarantee_scope=GUARANTEE_SCOPE,
            audit=audit,
        )


def build_dense_reference_graph(
    events: Iterable[CoordinationEvent], config: TSGSConfig | None = None
) -> tuple[WeightedEdge, ...]:
    """Build an all-pairs cosine graph for tests and benchmarks, never the runtime path."""
    resolved_config = config or TSGSConfig()
    vectors = _build_sparse_activity_vectors(events, resolved_config.time_bucket_seconds)
    account_ids = tuple(vectors)
    all_pairs = (
        (account_ids[left_index], account_ids[right_index])
        for left_index in range(len(account_ids) - 1)
        for right_index in range(left_index + 1, len(account_ids))
    )
    return _score_candidate_graph(all_pairs, vectors, resolved_config.min_cosine_similarity)


__all__ = [
    "BucketDiagnostics",
    "SpectralAudit",
    "TSGSConfig",
    "TSGSResult",
    "TSGSTimings",
    "TemporalSketchGraphSparsifier",
    "WeightedEdge",
    "build_dense_reference_graph",
]
