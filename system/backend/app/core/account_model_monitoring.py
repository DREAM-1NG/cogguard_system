"""Version-scoped monitoring metrics for the deployed account detector."""

from __future__ import annotations

import math
from collections import Counter
from dataclasses import dataclass
from typing import Any, Iterable, Mapping, Sequence

__all__ = [
    "MonitoringThresholds",
    "normalize_account_model_hard_error_reason",
    "population_stability_index",
    "summarize_account_predictions",
]

_HARD_ERROR_REASON_CATEGORIES = frozenset(
    {
        "active_model_bundle_invalid",
        "account_model_runtime_load_failure",
        "other_runtime_failure",
    }
)
_MAX_HARD_ERROR_REASON_CATEGORIES = 8


@dataclass(frozen=True, slots=True)
class MonitoringThresholds:
    """Operational budgets evaluated without changing the active pointer."""

    max_ece: float = 0.05
    max_population_stability_index: float = 0.20
    max_hard_error_rate: float = 0.02
    max_p95_latency_ms: float = 5_000.0
    daily_prediction_volume: int = 0
    daily_review_capacity: int = 100


def summarize_account_predictions(
    rows: Iterable[Mapping[str, Any]],
    *,
    reference_probabilities: Sequence[float] = (),
    thresholds: MonitoringThresholds | None = None,
) -> dict[str, Any]:
    """Compute auditable deployment metrics from prediction audit records."""

    policy = thresholds or MonitoringThresholds()
    predictions = [_normalize_prediction(row) for row in rows]
    if not predictions:
        return _empty_summary(policy)

    covered = [row for row in predictions if not row["abstained"] and not row["hard_error"]]
    labeled = [row for row in predictions if row["target"] in {0, 1}]
    calibrated = [row for row in covered if row["target"] in {0, 1}]
    false_positives = [row for row in covered if row["target"] == 0 and row["probability"] >= 0.5]
    hard_errors = sum(1 for row in predictions if row["hard_error"])
    hard_error_reason_counts = _hard_error_reason_counts(predictions)
    probabilities = [row["probability"] for row in covered]
    p95_latency = _percentile([row["latency_ms"] for row in predictions], 0.95)
    ece = _expected_calibration_error(calibrated) if calibrated else None
    psi = (
        population_stability_index(reference_probabilities, probabilities)
        if reference_probabilities and probabilities
        else None
    )
    estimated_daily_false_positives = round(
        len(false_positives) / len(predictions) * max(0, policy.daily_prediction_volume)
    )

    status = "healthy"
    automatic_rollback_allowed = False
    if hard_errors / len(predictions) > policy.max_hard_error_rate:
        status = "hard_failure"
        automatic_rollback_allowed = True
    elif p95_latency > policy.max_p95_latency_ms:
        status = "latency_alert"
    elif estimated_daily_false_positives > policy.daily_review_capacity:
        status = "review_capacity_exceeded"
    elif ece is not None and ece > policy.max_ece:
        status = "calibration_alert"
    elif psi is not None and psi > policy.max_population_stability_index:
        status = "drift_alert"

    return {
        "prediction_count": len(predictions),
        "labeled_prediction_count": len(labeled),
        "coverage": len(covered) / len(predictions),
        "abstention_rate": sum(1 for row in predictions if row["abstained"]) / len(predictions),
        "hard_error_rate": hard_errors / len(predictions),
        "hard_error_reason_counts": hard_error_reason_counts,
        "false_positive_count": len(false_positives),
        "estimated_daily_false_positives": estimated_daily_false_positives,
        "ece": ece,
        "population_stability_index": psi,
        "latency_ms": {
            "p50": _percentile([row["latency_ms"] for row in predictions], 0.50),
            "p95": p95_latency,
            "max": max(row["latency_ms"] for row in predictions),
        },
        "status": status,
        "automatic_rollback_allowed": automatic_rollback_allowed,
        "thresholds": {
            "max_ece": policy.max_ece,
            "max_population_stability_index": policy.max_population_stability_index,
            "max_hard_error_rate": policy.max_hard_error_rate,
            "max_p95_latency_ms": policy.max_p95_latency_ms,
            "daily_review_capacity": policy.daily_review_capacity,
        },
    }


def population_stability_index(
    reference: Sequence[float],
    current: Sequence[float],
    *,
    bins: int = 10,
) -> float:
    """Measure score-distribution drift over fixed probability bins."""

    if bins < 2:
        raise ValueError("bins must be at least 2")
    reference_values = _validate_probabilities(reference)
    current_values = _validate_probabilities(current)
    if not reference_values or not current_values:
        raise ValueError("population stability index requires non-empty samples")
    reference_counts = _histogram(reference_values, bins)
    current_counts = _histogram(current_values, bins)
    epsilon = 1e-6
    result = 0.0
    for reference_count, current_count in zip(reference_counts, current_counts, strict=True):
        reference_share = max(reference_count / len(reference_values), epsilon)
        current_share = max(current_count / len(current_values), epsilon)
        result += (current_share - reference_share) * math.log(current_share / reference_share)
    return float(result)


def _normalize_prediction(row: Mapping[str, Any]) -> dict[str, Any]:
    probability = float(row.get("probability", 0.5))
    if not 0.0 <= probability <= 1.0:
        raise ValueError("prediction probability must be in [0, 1]")
    target_value = row.get("target")
    target = int(target_value) if target_value in {0, 1, False, True} else None
    latency = float(row.get("latency_ms", 0.0))
    if latency < 0:
        raise ValueError("prediction latency_ms cannot be negative")
    return {
        "probability": probability,
        "target": target,
        "abstained": bool(row.get("abstained", False)),
        "latency_ms": latency,
        "hard_error": bool(row.get("hard_error", False)),
        "hard_error_reason": normalize_account_model_hard_error_reason(row.get("hard_error_reason")),
    }


def _validate_probabilities(values: Sequence[float]) -> list[float]:
    normalized = [float(value) for value in values]
    if any(not 0.0 <= value <= 1.0 for value in normalized):
        raise ValueError("probabilities must be in [0, 1]")
    return normalized


def _histogram(values: Sequence[float], bins: int) -> list[int]:
    counts = [0] * bins
    for value in values:
        index = min(int(value * bins), bins - 1)
        counts[index] += 1
    return counts


def _expected_calibration_error(rows: Sequence[Mapping[str, Any]], bins: int = 10) -> float:
    total = len(rows)
    error = 0.0
    for index in range(bins):
        lower = index / bins
        upper = (index + 1) / bins
        bucket = [
            row
            for row in rows
            if lower <= row["probability"] < upper or (index == bins - 1 and row["probability"] == 1.0)
        ]
        if not bucket:
            continue
        confidence = sum(row["probability"] for row in bucket) / len(bucket)
        accuracy = sum(int((row["probability"] >= 0.5) == bool(row["target"])) for row in bucket) / len(bucket)
        error += len(bucket) / total * abs(accuracy - confidence)
    return float(error)


def _percentile(values: Sequence[float], quantile: float) -> float:
    ordered = sorted(float(value) for value in values)
    if not ordered:
        return 0.0
    position = (len(ordered) - 1) * quantile
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


def _empty_summary(policy: MonitoringThresholds) -> dict[str, Any]:
    return {
        "prediction_count": 0,
        "labeled_prediction_count": 0,
        "coverage": 0.0,
        "abstention_rate": 0.0,
        "hard_error_rate": 0.0,
        "hard_error_reason_counts": {},
        "false_positive_count": 0,
        "estimated_daily_false_positives": 0,
        "ece": None,
        "population_stability_index": None,
        "latency_ms": {"p50": 0.0, "p95": 0.0, "max": 0.0},
        "status": "insufficient_observations",
        "automatic_rollback_allowed": False,
        "thresholds": {"daily_review_capacity": policy.daily_review_capacity},
    }


def normalize_account_model_hard_error_reason(value: Any) -> str:
    """Return a bounded monitoring category without retaining exception text."""

    normalized = str(value or "").strip()
    if normalized in _HARD_ERROR_REASON_CATEGORIES:
        return normalized
    return "other_runtime_failure"


def _hard_error_reason_counts(predictions: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    counts = Counter(
        str(row["hard_error_reason"])
        for row in predictions
        if row["hard_error"]
    )
    return {
        reason: int(count)
        for reason, count in sorted(counts.items(), key=lambda item: (-item[1], item[0]))[
            :_MAX_HARD_ERROR_REASON_CATEGORIES
        ]
    }
