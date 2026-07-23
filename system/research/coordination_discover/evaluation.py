from __future__ import annotations

from typing import Any

from .contracts import DetectValidationRequest, DetectValidationResult


def run_detect_validation(
    request: DetectValidationRequest,
    discovery: Any | None = None,
) -> DetectValidationResult:
    del discovery
    labels_scores = _labels_and_scores(request)
    if labels_scores is None:
        return DetectValidationResult(
            status="missing_labels",
            metrics={
                "claim_boundary": "no_supervised_detect_claim_without_labels",
                "required_protocol": _required_protocol(),
            },
        )
    labels, scores = labels_scores
    if not labels or len(set(labels)) < 2:
        return DetectValidationResult(
            status="data_insufficient",
            metrics={
                "sample_count": len(labels),
                "claim_boundary": "needs_both_positive_and_negative_labeled_cases",
                "required_protocol": _required_protocol(),
            },
        )

    ranked = sorted(zip(scores, labels), key=lambda item: item[0], reverse=True)
    probability_scores = [_clip_probability(score) for score in scores]
    metrics = {
        "sample_count": len(labels),
        "positive_count": sum(labels),
        "auprc": round(_average_precision(ranked), 6),
        "max_f1": round(_max_f1(ranked), 6),
        "precision_at_k": {
            "5": round(_precision_at_k(ranked, 5), 6),
            "10": round(_precision_at_k(ranked, 10), 6),
        },
        "recall_at_k": {
            "5": round(_recall_at_k(ranked, 5), 6),
            "10": round(_recall_at_k(ranked, 10), 6),
        },
        "ece": round(_expected_calibration_error(labels=labels, scores=probability_scores), 6),
        "score_policy": {
            "ranking": "raw_scores",
            "calibration": "scores_clipped_to_probability_range",
        },
        "claim_readiness": _claim_readiness(request),
    }
    return DetectValidationResult(
        status="ok",
        metrics=metrics,
        ablation_rows=[
            {"name": "raw_evidence_graph", "role": "baseline"},
            {"name": "temporal_magnn_no_lm", "role": "ablation"},
            {"name": "temporal_magnn_no_time_encoding", "role": "ablation"},
            {"name": "temporal_magnn_leiden", "role": "deprecated_non_claimable_replay"},
            {"name": "detect_validation_with_discover_representation", "role": "validation_only"},
        ],
    )


def _labels_and_scores(request: DetectValidationRequest) -> tuple[list[int], list[float]] | None:
    labels: list[int] = []
    scores: list[float] = []
    for row in request.rows:
        if request.label_field not in row or request.score_field not in row:
            return None
        labels.append(1 if row.get(request.label_field) == request.positive_label else 0)
        try:
            value = row.get(request.score_field)
            scores.append(float(value) if value is not None else 0.0)
        except (TypeError, ValueError):
            scores.append(0.0)
    return labels, scores


def _claim_readiness(request: DetectValidationRequest) -> dict[str, Any]:
    missing_axes = []
    for axis in ("split", "campaign", "platform", "seed"):
        if not any(axis in row and row.get(axis) not in (None, "") for row in request.rows):
            missing_axes.append(axis)
    status = "claim_ready_protocol_metadata_present" if not missing_axes else "exploratory_metrics_only"
    return {
        "status": status,
        "missing_axes": missing_axes,
        "required_protocol": _required_protocol(),
        "boundary": "public_labeled_holdout_required_for_detect_claims",
    }


def _required_protocol() -> dict[str, Any]:
    return {
        "holdout_axes": ["campaign", "platform", "time"],
        "metrics": ["AUPRC", "MaxF1", "ECE", "abstain_rate", "5_seed_confidence_interval"],
        "local_unlabeled_policy": "return_missing_labels",
    }


def _clip_probability(value: float) -> float:
    return min(1.0, max(0.0, float(value)))


def _average_precision(ranked: list[tuple[float, int]]) -> float:
    positive_total = sum(label for _, label in ranked)
    if positive_total == 0:
        return 0.0
    hits = 0
    precision_sum = 0.0
    for index, (_, label) in enumerate(ranked, start=1):
        if label:
            hits += 1
            precision_sum += hits / index
    return precision_sum / positive_total


def _max_f1(ranked: list[tuple[float, int]]) -> float:
    positive_total = sum(label for _, label in ranked)
    if positive_total == 0:
        return 0.0
    true_positive = 0
    best = 0.0
    for index, (_, label) in enumerate(ranked, start=1):
        if label:
            true_positive += 1
        precision = true_positive / index
        recall = true_positive / positive_total
        if precision + recall:
            best = max(best, 2 * precision * recall / (precision + recall))
    return best


def _precision_at_k(ranked: list[tuple[float, int]], k: int) -> float:
    if not ranked:
        return 0.0
    top = ranked[: min(k, len(ranked))]
    return sum(label for _, label in top) / len(top)


def _recall_at_k(ranked: list[tuple[float, int]], k: int) -> float:
    positive_total = sum(label for _, label in ranked)
    if positive_total == 0:
        return 0.0
    top = ranked[: min(k, len(ranked))]
    return sum(label for _, label in top) / positive_total


def _expected_calibration_error(*, labels: list[int], scores: list[float], bins: int = 10) -> float:
    if not labels:
        return 0.0
    total = len(labels)
    ece = 0.0
    for bucket in range(bins):
        lower = bucket / bins
        upper = (bucket + 1) / bins
        indexes = [
            index
            for index, score in enumerate(scores)
            if lower <= score < upper or (bucket == bins - 1 and score == 1.0)
        ]
        if not indexes:
            continue
        confidence = sum(scores[index] for index in indexes) / len(indexes)
        accuracy = sum(labels[index] for index in indexes) / len(indexes)
        ece += (len(indexes) / total) * abs(accuracy - confidence)
    return ece


__all__ = ["run_detect_validation"]
