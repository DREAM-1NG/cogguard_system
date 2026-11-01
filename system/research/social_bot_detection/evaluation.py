"""Evaluation reports for base and reliability-corrected predictions."""

from __future__ import annotations

from typing import Any

import numpy as np
from sklearn.metrics import (
    accuracy_score,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)

from .contracts import EvaluationReport

__all__ = ["evaluate_predictions"]


def evaluate_predictions(
    labels: list[int] | np.ndarray,
    probabilities: list[float] | np.ndarray,
    *,
    routed_count: int,
    routing_budget: float,
    split: str,
) -> EvaluationReport:
    """Compute thresholded and ranking metrics for one split."""

    y_true = np.asarray(labels, dtype=np.int64)
    y_score = np.asarray(probabilities, dtype=np.float64)
    y_pred = (y_score >= 0.5).astype(np.int64)
    try:
        auc: float | None = float(roc_auc_score(y_true, y_score))
    except ValueError:
        auc = None
    return EvaluationReport(
        sample_count=int(len(y_true)),
        accuracy=float(accuracy_score(y_true, y_pred)),
        macro_f1=float(f1_score(y_true, y_pred, average="macro", zero_division=0)),
        macro_precision=float(precision_score(y_true, y_pred, average="macro", zero_division=0)),
        macro_recall=float(recall_score(y_true, y_pred, average="macro", zero_division=0)),
        roc_auc=auc,
        confusion_matrix=confusion_matrix(y_true, y_pred, labels=[0, 1]).tolist(),
        routed_count=int(routed_count),
        routing_budget=float(routing_budget),
        split=split,
    )


def prediction_rows(
    account_ids: list[str],
    labels: list[int],
    base_probabilities: np.ndarray,
    corrected_probabilities: np.ndarray,
    routed: np.ndarray,
    source_labels: list[str] | None = None,
) -> list[dict[str, Any]]:
    """Build stable JSONL-friendly account predictions."""

    if source_labels is None:
        source_labels = [""] * len(account_ids)
    return [
        {
            "account_id": account_id,
            "label": int(label),
            "source_label": source_label,
            "base_bot_probability": round(float(base), 8),
            "corrected_bot_probability": round(float(corrected), 8),
            "base_prediction": int(base >= 0.5),
            "corrected_prediction": int(corrected >= 0.5),
            "routed": bool(is_routed),
        }
        for account_id, label, source_label, base, corrected, is_routed in zip(
            account_ids,
            labels,
            source_labels,
            base_probabilities,
            corrected_probabilities,
            routed,
            strict=True,
        )
    ]
