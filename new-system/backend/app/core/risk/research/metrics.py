"""分类评估工具。"""

from __future__ import annotations

from collections import Counter
from typing import Iterable


def _safe_div(numerator: float, denominator: float) -> float:
    if denominator == 0:
        return 0.0
    return numerator / denominator


def evaluate_classification(gold_labels: Iterable[str], pred_labels: Iterable[str]) -> dict[str, object]:
    gold = list(gold_labels)
    pred = list(pred_labels)
    if len(gold) != len(pred):
        raise ValueError("gold_labels 与 pred_labels 长度不一致")
    if not gold:
        raise ValueError("评估输入不能为空")

    labels = sorted(set(gold) | set(pred))
    confusion: dict[str, dict[str, int]] = {
        label: {other: 0 for other in labels} for label in labels
    }
    for g, p in zip(gold, pred):
        confusion[g][p] += 1

    per_label: dict[str, dict[str, float]] = {}
    f1_values: list[float] = []
    correct = 0
    for label in labels:
        tp = confusion[label][label]
        fp = sum(confusion[other][label] for other in labels if other != label)
        fn = sum(confusion[label][other] for other in labels if other != label)
        precision = _safe_div(tp, tp + fp)
        recall = _safe_div(tp, tp + fn)
        f1 = _safe_div(2 * precision * recall, precision + recall)
        support = sum(confusion[label].values())
        per_label[label] = {
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "f1": round(f1, 4),
            "support": support,
        }
        f1_values.append(f1)
        correct += tp

    accuracy = correct / len(gold)
    macro_f1 = sum(f1_values) / len(f1_values)

    return {
        "labels": labels,
        "accuracy": round(accuracy, 4),
        "macro_f1": round(macro_f1, 4),
        "per_label": per_label,
        "confusion_matrix": confusion,
        "gold_distribution": dict(Counter(gold)),
        "pred_distribution": dict(Counter(pred)),
    }


def format_metrics_summary(metrics: dict[str, object]) -> str:
    labels = ", ".join(metrics["labels"])
    return (
        f"labels=[{labels}] | accuracy={metrics['accuracy']} | macro_f1={metrics['macro_f1']}"
    )
