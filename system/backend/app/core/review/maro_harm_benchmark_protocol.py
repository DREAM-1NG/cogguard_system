"""Label-space-safe Judge primitives for external HateCoT harm benchmarks."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import re
from typing import Any, Mapping

from sklearn.metrics import accuracy_score, confusion_matrix, f1_score

from app.core.review.maro_rule_optimization import CrossDomainValidationTask


__all__ = [
    "BenchmarkJudgeTask",
    "benchmark_majority_vote",
    "build_benchmark_judge_prompt",
    "evaluate_benchmark_predictions",
    "parse_benchmark_judgment",
]


@dataclass(frozen=True)
class BenchmarkJudgeTask:
    """Unlabelled target input passed to a benchmark-specific final Judge."""

    task_id: str
    query_case_id: str
    query_text: str
    query_domain: str
    target_benchmark: str
    demonstrations: tuple[Any, ...] = ()


JudgeTask = CrossDomainValidationTask | BenchmarkJudgeTask


def build_benchmark_judge_prompt(
    *,
    label_space: tuple[str, ...],
    rule_text: str,
    task: JudgeTask,
    analysis: str,
) -> str:
    """Build a label-isolated prompt from declared task labels only."""

    labels = ", ".join(f"{index}={label}" for index, label in enumerate(label_space))
    demonstrations = "\n".join(
        "DEMO {}: domain={}; label={}; text={}".format(
            index,
            item.domain,
            _label_number(item.label, label_space),
            item.text[:1000],
        )
        for index, item in enumerate(task.demonstrations, start=1)
    )
    return (
        f"DECISION RULE:\n{rule_text}\n\n"
        f"LABEL SPACE: {labels}.\n"
        "The demonstrations are source-domain validation examples, not facts about the query.\n\n"
        f"DEMONSTRATIONS FROM OTHER DOMAINS:\n{demonstrations}\n\n"
        f"QUERY DOMAIN: {task.query_domain}\nQUERY TEXT:\n{task.query_text[:4000]}\n\n"
        f"POST-HARM ANALYSIS AND ADVISORY POLICY REFERENCES:\n{analysis[:12000]}\n\n"
        "Apply the rule to this query."
    )


def parse_benchmark_judgment(text: str, label_space: tuple[str, ...]) -> str | None:
    """Accept only an explicit final label index in the active benchmark space."""

    matches = re.findall(r"(?:JUDGMENT|LABEL|ANSWER)\s*[:：]\s*(\d+)\b", str(text or ""), flags=re.IGNORECASE)
    if not matches:
        return None
    try:
        return label_space[int(matches[-1])]
    except (ValueError, IndexError):
        return None


def benchmark_majority_vote(votes: list[str], label_space: tuple[str, ...]) -> str:
    """Vote over a declared odd rule pool with an auditable three-way tie rule."""

    if not votes or len(votes) % 2 == 0:
        raise ValueError("Benchmark voting requires a non-empty odd number of rule votes")
    if any(vote not in label_space for vote in votes):
        raise ValueError("Benchmark voting received a label outside the declared label space")
    counts = Counter(votes)
    best_count = max(counts.values())
    winners = [label for label in label_space if counts[label] == best_count]
    if len(winners) == 1:
        return winners[0]
    # Three labels and three ranked rules can produce 1-1-1. The first vote
    # belongs to the highest source-validation rule and is the fixed tie-break.
    if votes[0] not in winners:
        raise RuntimeError("The best returned rule is missing from the tied vote set")
    return votes[0]


def evaluate_benchmark_predictions(
    rows: list[Mapping[str, Any]],
    *,
    label_space: tuple[str, ...],
) -> dict[str, Any]:
    """Compute metrics over every frozen target item, without coverage filtering."""

    if not rows:
        raise ValueError("Benchmark evaluation requires at least one target prediction")
    for row in rows:
        if row.get("gold_label") not in label_space:
            raise ValueError(f"Invalid benchmark gold label: {row.get('gold_label')!r}")
        if row.get("prediction") not in label_space:
            raise ValueError(f"Invalid benchmark prediction: {row.get('prediction')!r}")
    gold = [str(row["gold_label"]) for row in rows]
    predicted = [str(row["prediction"]) for row in rows]
    per_class = f1_score(gold, predicted, labels=list(label_space), average=None, zero_division=0)
    return {
        "submitted_count": len(rows),
        "classification_metrics": {
            "accuracy": round(float(accuracy_score(gold, predicted)), 6),
            "macro_f1": round(float(f1_score(gold, predicted, labels=list(label_space), average="macro", zero_division=0)), 6),
            "per_class_f1": {
                label: round(float(score), 6)
                for label, score in zip(label_space, per_class, strict=True)
            },
        },
        "confusion_matrix": {
            "label_order": list(label_space),
            "rows_gold_columns_prediction": confusion_matrix(gold, predicted, labels=list(label_space)).tolist(),
        },
    }


def _label_number(label: str, label_space: tuple[str, ...]) -> int:
    try:
        return label_space.index(label)
    except ValueError as exc:
        raise ValueError(f"Demonstration label {label!r} is outside the declared benchmark space") from exc
