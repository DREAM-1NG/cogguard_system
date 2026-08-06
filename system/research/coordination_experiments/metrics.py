from __future__ import annotations

import math
from collections import Counter
from collections.abc import Mapping, Sequence
from itertools import combinations
from types import MappingProxyType
from typing import Any

import numpy as np


_DIRECTIONS = MappingProxyType(
    {
        "candidate_recall": "maximize",
        "spectral_distortion": "minimize",
        "edge_auprc": "maximize",
        "b_cubed_precision": "maximize",
        "b_cubed_recall": "maximize",
        "b_cubed_f1": "maximize",
        "nmi": "maximize",
        "ari": "maximize",
        "cross_seed_stability": "maximize",
        "auprc": "maximize",
        "macro_f1": "maximize",
        "roc_auc": "maximize",
        "ece": "minimize",
        "selective_coverage": "maximize",
        "selective_risk": "minimize",
        "abstain_rate": "minimize",
        "runtime_seconds": "minimize",
        "peak_memory_bytes": "minimize",
    }
)


def _finite_vector(values: Sequence[float], field_name: str) -> np.ndarray:
    if isinstance(values, (str, bytes)) or not isinstance(values, Sequence) or not values:
        raise ValueError(f"{field_name} must be a non-empty sequence")
    result = np.asarray(values, dtype=np.float64)
    if result.ndim != 1 or not np.all(np.isfinite(result)):
        raise ValueError(f"{field_name} must contain finite scalars")
    return result


def _binary_labels(values: Sequence[int], field_name: str = "labels") -> np.ndarray:
    result = _finite_vector(values, field_name)
    if not np.all((result == 0.0) | (result == 1.0)):
        raise ValueError(f"{field_name} must contain only 0 and 1")
    if set(result.astype(int)) != {0, 1}:
        raise ValueError(f"{field_name} must contain both classes")
    return result.astype(np.int64)


def metric_direction(metric_name: str) -> str:
    try:
        return _DIRECTIONS[metric_name]
    except KeyError as exc:
        raise ValueError(f"unknown metric: {metric_name}") from exc


def metric_directions() -> Mapping[str, str]:
    return _DIRECTIONS


def bootstrap_confidence_interval(
    values: Sequence[float],
    *,
    seed: int = 0,
    resamples: int = 2_000,
    confidence: float = 0.95,
) -> tuple[float, float]:
    samples = _finite_vector(values, "bootstrap values")
    if isinstance(seed, bool) or not isinstance(seed, int) or seed < 0:
        raise ValueError("seed must be a non-negative integer")
    if isinstance(resamples, bool) or not isinstance(resamples, int) or resamples <= 0:
        raise ValueError("resamples must be a positive integer")
    if not 0.0 < confidence < 1.0:
        raise ValueError("confidence must be within (0, 1)")
    if samples.size == 1:
        value = float(samples[0])
        return value, value
    rng = np.random.default_rng(seed)
    indices = rng.integers(0, samples.size, size=(resamples, samples.size))
    means = np.mean(samples[indices], axis=1)
    alpha = (1.0 - confidence) / 2.0
    low, high = np.quantile(means, (alpha, 1.0 - alpha), method="linear")
    return float(low), float(high)


def candidate_recall(candidate_edges: Sequence[Sequence[Any]], reference_edges: Sequence[Sequence[Any]]) -> float:
    def normalize(edges: Sequence[Sequence[Any]], name: str) -> set[tuple[str, str]]:
        normalized: set[tuple[str, str]] = set()
        for edge in edges:
            if len(edge) != 2:
                raise ValueError(f"{name} edges must have two endpoints")
            left, right = sorted((str(edge[0]).strip(), str(edge[1]).strip()))
            if not left or not right or left == right:
                raise ValueError(f"{name} edges must have distinct non-empty endpoints")
            normalized.add((left, right))
        return normalized

    candidates = normalize(candidate_edges, "candidate")
    references = normalize(reference_edges, "reference")
    if not references:
        raise ValueError("reference edges must not be empty")
    return len(candidates & references) / len(references)


def spectral_distortion(reference: Sequence[float], approximate: Sequence[float]) -> float:
    expected = _finite_vector(reference, "reference quadratic forms")
    observed = _finite_vector(approximate, "approximate quadratic forms")
    if expected.shape != observed.shape:
        raise ValueError("quadratic-form vectors must have the same shape")
    scale = np.abs(expected)
    zero = scale <= np.finfo(np.float64).eps
    if np.any(zero & (np.abs(observed) > np.finfo(np.float64).eps)):
        return math.inf
    relative = np.zeros_like(scale)
    relative[~zero] = np.abs(observed[~zero] - expected[~zero]) / scale[~zero]
    return float(np.max(relative))


def average_precision(labels: Sequence[int], scores: Sequence[float]) -> float:
    truth = _binary_labels(labels)
    values = _finite_vector(scores, "scores")
    if truth.shape != values.shape:
        raise ValueError("labels and scores must have the same length")
    order = np.argsort(-values, kind="stable")
    ranked = truth[order]
    ranked_scores = values[order]
    group_ends = np.flatnonzero(np.r_[ranked_scores[1:] != ranked_scores[:-1], True])
    cumulative = np.cumsum(ranked)
    true_positives = cumulative[group_ends]
    precisions = true_positives / (group_ends + 1)
    recall_increments = np.diff(np.r_[0, true_positives]) / int(np.sum(truth))
    return float(np.sum(recall_increments * precisions))


def roc_auc(labels: Sequence[int], scores: Sequence[float]) -> float:
    truth = _binary_labels(labels)
    values = _finite_vector(scores, "scores")
    if truth.shape != values.shape:
        raise ValueError("labels and scores must have the same length")
    positive = values[truth == 1]
    negative = values[truth == 0]
    comparisons = positive[:, None] - negative[None, :]
    return float(np.mean((comparisons > 0.0) + 0.5 * (comparisons == 0.0)))


def _mapping_pair(
    true_clusters: Mapping[str, Any], predicted_clusters: Mapping[str, Any]
) -> tuple[tuple[str, ...], tuple[Any, ...], tuple[Any, ...]]:
    if not isinstance(true_clusters, Mapping) or not isinstance(predicted_clusters, Mapping):
        raise ValueError("cluster assignments must be mappings")
    if not true_clusters or set(true_clusters) != set(predicted_clusters):
        raise ValueError("cluster assignments must cover the same non-empty item universe")
    items = tuple(sorted(str(item) for item in true_clusters))
    if set(items) != set(true_clusters):
        raise ValueError("cluster item IDs must be canonical strings")
    return items, tuple(true_clusters[item] for item in items), tuple(predicted_clusters[item] for item in items)


def b_cubed_scores(
    true_clusters: Mapping[str, Any], predicted_clusters: Mapping[str, Any]
) -> tuple[float, float, float]:
    items, truth, predicted = _mapping_pair(true_clusters, predicted_clusters)
    true_sizes = Counter(truth)
    predicted_sizes = Counter(predicted)
    intersections = Counter(zip(truth, predicted, strict=True))
    precision = sum(intersections[(actual, guess)] / predicted_sizes[guess] for actual, guess in zip(truth, predicted, strict=True)) / len(items)
    recall = sum(intersections[(actual, guess)] / true_sizes[actual] for actual, guess in zip(truth, predicted, strict=True)) / len(items)
    f1 = 0.0 if precision + recall == 0.0 else 2.0 * precision * recall / (precision + recall)
    return float(precision), float(recall), float(f1)


def normalized_mutual_information(
    true_clusters: Mapping[str, Any], predicted_clusters: Mapping[str, Any]
) -> float:
    items, truth, predicted = _mapping_pair(true_clusters, predicted_clusters)
    count = len(items)
    true_sizes = Counter(truth)
    predicted_sizes = Counter(predicted)
    intersections = Counter(zip(truth, predicted, strict=True))
    mutual_information = sum(
        (joint / count) * math.log((joint * count) / (true_sizes[actual] * predicted_sizes[guess]))
        for (actual, guess), joint in intersections.items()
    )
    true_entropy = -sum((size / count) * math.log(size / count) for size in true_sizes.values())
    predicted_entropy = -sum((size / count) * math.log(size / count) for size in predicted_sizes.values())
    denominator = true_entropy + predicted_entropy
    return 1.0 if denominator == 0.0 else float(2.0 * mutual_information / denominator)


def adjusted_rand_index(
    true_clusters: Mapping[str, Any], predicted_clusters: Mapping[str, Any]
) -> float:
    items, truth, predicted = _mapping_pair(true_clusters, predicted_clusters)
    if len(items) < 2:
        return 1.0
    choose_two = lambda value: value * (value - 1) / 2
    true_sizes = Counter(truth)
    predicted_sizes = Counter(predicted)
    intersections = Counter(zip(truth, predicted, strict=True))
    joint = sum(choose_two(size) for size in intersections.values())
    true_pairs = sum(choose_two(size) for size in true_sizes.values())
    predicted_pairs = sum(choose_two(size) for size in predicted_sizes.values())
    total_pairs = choose_two(len(items))
    expected = true_pairs * predicted_pairs / total_pairs
    maximum = 0.5 * (true_pairs + predicted_pairs)
    return 1.0 if maximum == expected else float((joint - expected) / (maximum - expected))


def cross_seed_stability(assignments: Sequence[Mapping[str, Any]]) -> float:
    if not isinstance(assignments, Sequence) or len(assignments) < 2:
        raise ValueError("cross-seed stability requires at least two assignments")
    values = [adjusted_rand_index(left, right) for left, right in combinations(assignments, 2)]
    return float(np.mean(values))


def discovery_metrics(
    *,
    candidate_edges: Sequence[Sequence[Any]],
    reference_edges: Sequence[Sequence[Any]],
    reference_quadratic_forms: Sequence[float],
    approximate_quadratic_forms: Sequence[float],
    edge_labels: Sequence[int],
    edge_scores: Sequence[float],
    true_clusters: Mapping[str, Any],
    predicted_clusters: Mapping[str, Any],
) -> dict[str, float]:
    precision, recall, f1 = b_cubed_scores(true_clusters, predicted_clusters)
    return {
        "candidate_recall": candidate_recall(candidate_edges, reference_edges),
        "spectral_distortion": spectral_distortion(reference_quadratic_forms, approximate_quadratic_forms),
        "edge_auprc": average_precision(edge_labels, edge_scores),
        "b_cubed_precision": precision,
        "b_cubed_recall": recall,
        "b_cubed_f1": f1,
        "nmi": normalized_mutual_information(true_clusters, predicted_clusters),
        "ari": adjusted_rand_index(true_clusters, predicted_clusters),
    }


def _binary_f1(labels: np.ndarray, predictions: np.ndarray, positive: int) -> float:
    true_positive = int(np.sum((labels == positive) & (predictions == positive)))
    false_positive = int(np.sum((labels != positive) & (predictions == positive)))
    false_negative = int(np.sum((labels == positive) & (predictions != positive)))
    denominator = 2 * true_positive + false_positive + false_negative
    return 0.0 if denominator == 0 else (2.0 * true_positive) / denominator


def expected_calibration_error(labels: Sequence[int], probabilities: Sequence[float], *, bins: int = 10) -> float:
    truth = _binary_labels(labels)
    scores = _finite_vector(probabilities, "probabilities")
    if truth.shape != scores.shape or np.any((scores < 0.0) | (scores > 1.0)):
        raise ValueError("probabilities must match labels and be within [0, 1]")
    if isinstance(bins, bool) or not isinstance(bins, int) or bins <= 0:
        raise ValueError("bins must be a positive integer")
    predictions = (scores >= 0.5).astype(np.int64)
    confidence = np.maximum(scores, 1.0 - scores)
    correctness = (predictions == truth).astype(np.float64)
    bucket_ids = np.minimum((confidence * bins).astype(int), bins - 1)
    return float(sum(
        np.mean(bucket_ids == bucket) * abs(float(np.mean(correctness[bucket_ids == bucket])) - float(np.mean(confidence[bucket_ids == bucket])))
        for bucket in range(bins) if np.any(bucket_ids == bucket)
    ))


def detection_metrics(
    *,
    labels: Sequence[int],
    probabilities: Sequence[float],
    decisions: Sequence[str],
) -> dict[str, float]:
    truth = _binary_labels(labels)
    scores = _finite_vector(probabilities, "probabilities")
    if truth.shape != scores.shape or np.any((scores < 0.0) | (scores > 1.0)):
        raise ValueError("probabilities must match labels and be within [0, 1]")
    if not isinstance(decisions, Sequence) or len(decisions) != len(truth):
        raise ValueError("decisions must match labels")
    allowed = {"benign_coordination", "harmful_coordination", "abstain"}
    if set(decisions) - allowed:
        raise ValueError("decisions contain an unknown value")
    predictions = (scores >= 0.5).astype(np.int64)
    covered = np.asarray([decision != "abstain" for decision in decisions], dtype=bool)
    decision_predictions = np.asarray([decision == "harmful_coordination" for decision in decisions], dtype=np.int64)
    risk = 0.0 if not np.any(covered) else float(np.mean(decision_predictions[covered] != truth[covered]))
    return {
        "auprc": average_precision(labels, probabilities),
        "macro_f1": float((_binary_f1(truth, predictions, 0) + _binary_f1(truth, predictions, 1)) / 2.0),
        "roc_auc": roc_auc(labels, probabilities),
        "ece": expected_calibration_error(labels, probabilities),
        "selective_coverage": float(np.mean(covered)),
        "selective_risk": risk,
        "abstain_rate": float(np.mean(~covered)),
    }


__all__ = [
    "adjusted_rand_index", "average_precision", "b_cubed_scores",
    "bootstrap_confidence_interval", "candidate_recall", "cross_seed_stability",
    "detection_metrics", "discovery_metrics", "expected_calibration_error",
    "metric_direction", "metric_directions", "normalized_mutual_information",
    "roc_auc", "spectral_distortion",
]
