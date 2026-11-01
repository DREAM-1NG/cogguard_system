"""Output contract helpers for Propagation Analysis checkpoint inference."""

from __future__ import annotations

import math
from collections import defaultdict
from pathlib import Path
from typing import Any, Mapping, Sequence


PROPAGATION_ANALYSIS_ROOT = Path(__file__).resolve().parents[2]
ADAPTER_BOUNDARY = str(PROPAGATION_ANALYSIS_ROOT)


def empty_prediction(status: str, note: str, checkpoint: Path | None = None) -> dict[str, Any]:
    """Return a model-unavailable response without heuristic fallback values."""
    return {
        "status": status,
        "model_status": "unavailable",
        "note": note,
        "adapter_boundary": ADAPTER_BOUNDARY,
        "checkpoint_path": str(checkpoint) if checkpoint else None,
        "macro": {
            "observed_size": 0,
            "predicted_size": None,
            "trend_points": [],
            "intervals": None,
            "direction": None,
            "score_concentration": None,
            "calibration_status": "unavailable",
        },
        "micro": {
            "top_users": [],
            "candidate_count": 0,
            "candidate_bucket_count": 0,
            "candidate_source_counts": {},
            "reactivation_count": 0,
            "new_activation_count": 0,
            "coverage": {
                "mapped_candidate_buckets": 0,
                "unmapped_candidate_buckets": 0,
                "legal_candidate_buckets": 0,
                "mapped_probability_mass": 0.0,
                "new_activation_status": "abstain_no_identity_mapping",
                "identity_mapping_status": "unique_current_event_bucket_proxy_only",
            },
        },
    }


def map_bucket_probabilities_to_unique_users(
    candidate_buckets: Sequence[int],
    probabilities: Sequence[float],
    bucket_to_users: Mapping[int, Sequence[Mapping[str, Any]]],
) -> dict[str, Any]:
    """Map bucket scores to uniquely identified current-event users only."""
    user_scores: dict[str, float] = defaultdict(float)
    mapped_bucket_count = 0
    mapped_probability_mass = 0.0
    ambiguous_mapped_buckets = 0
    excluded_ambiguous_users = 0
    unique_identity_probability_mass = 0.0

    for bucket, probability in zip(candidate_buckets, probabilities):
        users = list(bucket_to_users.get(int(bucket), []))
        if not users:
            continue
        mapped_bucket_count += 1
        mapped_probability_mass += float(probability)
        if len(users) != 1:
            ambiguous_mapped_buckets += 1
            excluded_ambiguous_users += len(users)
            continue
        author_id = str(users[0].get("author_id") or "").strip()
        if not author_id:
            continue
        user_scores[author_id] += float(probability)
        unique_identity_probability_mass += float(probability)

    return {
        "user_scores": dict(user_scores),
        "mapped_bucket_count": mapped_bucket_count,
        "mapped_probability_mass": mapped_probability_mass,
        "ambiguous_mapped_buckets": ambiguous_mapped_buckets,
        "excluded_ambiguous_users": excluded_ambiguous_users,
        "unique_identity_probability_mass": unique_identity_probability_mass,
    }


def trend_points(values: Sequence[float]) -> list[dict[str, Any]]:
    return [
        {
            "step": index + 1,
            "predicted_size": int(round(value)),
        }
        for index, value in enumerate(values)
    ]


def score_concentration(scores: Sequence[float]) -> float | None:
    if len(scores) < 2:
        return None
    total = sum(scores)
    if total <= 0:
        return None
    probabilities = [max(score / total, 1e-12) for score in scores]
    entropy = -sum(probability * math.log(probability) for probability in probabilities)
    return round(max(0.0, min(1.0, 1.0 - entropy / math.log(len(probabilities)))), 4)


__all__ = [
    "ADAPTER_BOUNDARY",
    "empty_prediction",
    "map_bucket_probabilities_to_unique_users",
    "score_concentration",
    "trend_points",
]
