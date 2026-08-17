"""Gold-aware, offline evaluation for MARO-compatible claim experiments.

Teacher footers may be schema-valid while deliberately returning ``uncertain``.
This module keeps footer validity, decision coverage, and label metrics
separate so an abstention is never silently converted into a binary error.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any

from sklearn.metrics import accuracy_score, f1_score, precision_score

__all__ = [
    "MARO_REFERENCE_IMPLEMENTATION",
    "compare_maro_profiles",
    "evaluate_claim_decisions",
    "evaluate_maro_reference_binary_metrics",
]


_BINARY_LABELS = {"harmful", "non_harmful"}

# The vendored MARO test.py uses sklearn's binary accuracy/F1/precision
# evaluator. This records the exact reference without importing that upstream
# script, which has placeholder provider configuration and executes work at
# module import time.
MARO_REFERENCE_IMPLEMENTATION = {
    "repository": "https://github.com/Brtulien/MARO",
    "commit": "20aea25462c5ee55af5bf777084a0eb8553b8920",
    "evaluator": "test.py:evaluate_predictions",
    "label_contract": {"0": "real", "1": "fake_or_rumor"},
    "metrics": ["accuracy_score", "f1_score(pos_label=1)", "precision_score(pos_label=1)"],
}


def evaluate_claim_decisions(
    cases: list[dict[str, Any]],
    prediction_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    """Evaluate the claim-deception axis without treating uncertainty as a label."""

    case_index = {
        (str(case.get("dataset") or "").lower(), str(case.get("case_id") or "")): case
        for case in cases
        if str(case.get("case_id") or "")
    }
    predictions = {
        (str(row.get("dataset") or "").lower(), str(row.get("case_id") or "")): row
        for row in prediction_rows
        if str(row.get("case_id") or "")
    }
    per_dataset: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for identity, case in case_index.items():
        row = predictions.get(identity)
        if row is not None:
            per_dataset[str(case.get("dataset") or "unknown")].append({"case": case, "row": row})

    dataset_reports = {
        dataset: _evaluate_dataset(rows)
        for dataset, rows in sorted(per_dataset.items())
    }
    all_rows = [item for rows in per_dataset.values() for item in rows]
    missing = [
        {"dataset": dataset, "case_id": case_id}
        for dataset, case_id in case_index
        if (dataset, case_id) not in predictions
    ]
    return {
        "schema": "maro-claim-decision-evaluation-v1",
        "axis": "misinfo_claim_risk",
        "rule": "Only harmful/non_harmful labels contribute to classification metrics; uncertain/unavailable remain coverage outcomes.",
        "submitted_case_count": len(case_index),
        "prediction_row_count": len(predictions),
        "missing_prediction_count": len(missing),
        "missing_predictions": missing,
        "overall": _evaluate_dataset(all_rows),
        "datasets": dataset_reports,
    }


def evaluate_maro_reference_binary_metrics(
    cases: list[dict[str, Any]],
    prediction_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    """Evaluate decided claim cases with MARO's upstream binary metric contract.

    ``uncertain`` and ``unavailable`` remain coverage outcomes. They cannot be
    coerced to either upstream binary label without changing the experiment.
    """

    case_index = {
        (str(case.get("dataset") or "").lower(), str(case.get("case_id") or "")): case
        for case in cases
        if str(case.get("case_id") or "")
    }
    prediction_index = {
        (str(row.get("dataset") or "").lower(), str(row.get("case_id") or "")): row
        for row in prediction_rows
        if str(row.get("case_id") or "")
    }
    y_true: list[int] = []
    y_pred: list[int] = []
    skipped_by_reason: Counter[str] = Counter()
    for identity, case in case_index.items():
        gold = str((case.get("labels") or {}).get("harmfulness") or "").strip().lower()
        if gold not in _BINARY_LABELS:
            skipped_by_reason["invalid_gold_label"] += 1
            continue
        row = prediction_index.get(identity)
        if row is None:
            skipped_by_reason["missing_prediction"] += 1
            continue
        prediction = ((row.get("judge_sidecar") or {}).get("teacher_prediction") or {})
        axis = (prediction.get("main_axes") or {}).get("misinfo_claim_risk") or {}
        label = str(axis.get("label") or "").strip().lower()
        if (row.get("judge_sidecar") or {}).get("teacher_prediction_valid") is not True:
            skipped_by_reason["invalid_footer"] += 1
            continue
        if axis.get("available") is not True or label not in _BINARY_LABELS:
            skipped_by_reason[label or "unavailable"] += 1
            continue
        y_true.append(1 if gold == "harmful" else 0)
        y_pred.append(1 if label == "harmful" else 0)

    submitted_count = len(case_index)
    metrics = None
    if y_true:
        metrics = {
            "evaluated_count": len(y_true),
            "accuracy": round(float(accuracy_score(y_true, y_pred)), 6),
            "f1_positive_fake": round(float(f1_score(y_true, y_pred, pos_label=1, zero_division=0)), 6),
            "precision_positive_fake": round(
                float(precision_score(y_true, y_pred, pos_label=1, zero_division=0)), 6
            ),
        }
    return {
        "schema": "maro-reference-binary-metrics-v1",
        "reference_implementation": dict(MARO_REFERENCE_IMPLEMENTATION),
        "axis": "misinfo_claim_risk",
        "submitted_case_count": submitted_count,
        "decision_coverage": _rate(len(y_true), submitted_count),
        "skipped_by_reason": dict(sorted(skipped_by_reason.items())),
        "metrics": metrics,
        "comparability_note": (
            "Metrics use MARO's upstream binary formula, but Weibo21 data conversion and "
            "CogGuard's structured Judge are a MARO-compatible adaptation rather than an official dataset reproduction."
        ),
    }
def compare_maro_profiles(
    fixed_rows: list[dict[str, Any]],
    routed_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    """Compare completed profile outputs on their shared cases without gold labels."""

    fixed_index = _prediction_index(fixed_rows)
    routed_index = _prediction_index(routed_rows)
    shared = sorted(set(fixed_index) & set(routed_index))
    fixed_only = sorted(set(fixed_index) - set(routed_index))
    routed_only = sorted(set(routed_index) - set(fixed_index))
    pairs = [
        _profile_pair(identity, fixed_index[identity], routed_index[identity])
        for identity in shared
    ]
    decided_pairs = [
        pair
        for pair in pairs
        if pair["fixed"]["decision_label"] in _BINARY_LABELS
        and pair["routed"]["decision_label"] in _BINARY_LABELS
    ]
    agreement_count = sum(
        pair["fixed"]["decision_label"] == pair["routed"]["decision_label"]
        for pair in decided_pairs
    )
    return {
        "schema": "maro-profile-comparison-v1",
        "comparison_boundary": "Compares runtime and decision coverage only. It is not a gold-label accuracy evaluation.",
        "shared_case_count": len(shared),
        "fixed_only_case_ids": [identity[1] for identity in fixed_only],
        "routed_only_case_ids": [identity[1] for identity in routed_only],
        "both_decided_count": len(decided_pairs),
        "decision_agreement_rate": round(agreement_count / len(decided_pairs), 6) if decided_pairs else None,
        "fixed": _profile_runtime_summary(fixed_index.values()),
        "routed": _profile_runtime_summary(routed_index.values()),
        "pairs": pairs,
    }


def _evaluate_dataset(rows: list[dict[str, Any]]) -> dict[str, Any]:
    footer_valid = 0
    uncertain = 0
    unavailable = 0
    decided: list[tuple[str, str]] = []
    gold_distribution: Counter[str] = Counter()
    for item in rows:
        case = item["case"]
        row = item["row"]
        gold = str((case.get("labels") or {}).get("harmfulness") or "")
        if gold in _BINARY_LABELS:
            gold_distribution[gold] += 1
        sidecar = row.get("judge_sidecar") or {}
        valid = sidecar.get("teacher_prediction_valid") is True
        footer_valid += int(valid)
        prediction = sidecar.get("teacher_prediction") or {}
        axis = (prediction.get("main_axes") or {}).get("misinfo_claim_risk") or {}
        label = str(axis.get("label") or "").strip().lower()
        if label == "uncertain":
            uncertain += 1
        elif label == "unavailable" or not axis.get("available"):
            unavailable += 1
        if valid and label in _BINARY_LABELS and gold in _BINARY_LABELS:
            decided.append((gold, label))
    count = len(rows)
    return {
        "case_count": count,
        "valid_footer_count": footer_valid,
        "valid_footer_rate": _rate(footer_valid, count),
        "decided_count": len(decided),
        "decision_coverage": _rate(len(decided), count),
        "uncertain_count": uncertain,
        "uncertain_rate": _rate(uncertain, count),
        "unavailable_count": unavailable,
        "gold_distribution": dict(gold_distribution),
        "classification_metrics": _binary_metrics(decided),
    }


def _binary_metrics(decided: list[tuple[str, str]]) -> dict[str, Any] | None:
    if not decided:
        return None
    labels = sorted(_BINARY_LABELS)
    per_class: dict[str, float] = {}
    correct = 0
    for label in labels:
        tp = sum(gold == label and predicted == label for gold, predicted in decided)
        fp = sum(gold != label and predicted == label for gold, predicted in decided)
        fn = sum(gold == label and predicted != label for gold, predicted in decided)
        denominator = 2 * tp + fp + fn
        per_class[label] = round((2 * tp / denominator) if denominator else 0.0, 6)
    correct = sum(gold == predicted for gold, predicted in decided)
    return {
        "evaluated_count": len(decided),
        "accuracy": round(correct / len(decided), 6),
        "macro_f1": round(sum(per_class.values()) / len(per_class), 6),
        "per_class_f1": per_class,
    }


def _prediction_index(rows: list[dict[str, Any]]) -> dict[tuple[str, str], dict[str, Any]]:
    return {
        (str(row.get("dataset") or "").lower(), str(row.get("case_id") or "")): row
        for row in rows
        if str(row.get("case_id") or "")
    }


def _profile_pair(
    identity: tuple[str, str],
    fixed: dict[str, Any],
    routed: dict[str, Any],
) -> dict[str, Any]:
    return {
        "dataset": identity[0],
        "case_id": identity[1],
        "fixed": _profile_row_summary(fixed),
        "routed": _profile_row_summary(routed),
    }


def _profile_runtime_summary(rows) -> dict[str, Any]:
    rows = list(rows)
    total = len(rows)
    runtime_counts = Counter(
        str((row.get("runtime_audit") or {}).get("effective_runtime_mode") or "unknown")
        for row in rows
    )
    calls = [int((row.get("agent_summary") or {}).get("actual_llm_call_count") or 0) for row in rows]
    elapsed = [float(row.get("elapsed_seconds") or 0.0) for row in rows]
    decided = sum(_profile_row_summary(row)["decision_label"] in _BINARY_LABELS for row in rows)
    return {
        "case_count": total,
        "runtime_counts": dict(runtime_counts),
        "simple_rate": _rate(runtime_counts.get("simple", 0), total),
        "complex_rate": _rate(runtime_counts.get("complex", 0), total),
        "mean_llm_calls_per_case": round(sum(calls) / total, 6) if total else 0.0,
        "mean_elapsed_seconds": round(sum(elapsed) / total, 6) if total else 0.0,
        "decision_coverage": _rate(decided, total),
    }


def _profile_row_summary(row: dict[str, Any]) -> dict[str, Any]:
    sidecar = row.get("judge_sidecar") or {}
    prediction = sidecar.get("teacher_prediction") or {}
    axis = (prediction.get("main_axes") or {}).get("misinfo_claim_risk") or {}
    return {
        "footer_valid": sidecar.get("teacher_prediction_valid") is True,
        "decision_label": str(axis.get("label") or "").strip().lower() or None,
        "runtime_mode": (row.get("runtime_audit") or {}).get("effective_runtime_mode"),
        "actual_llm_call_count": (row.get("agent_summary") or {}).get("actual_llm_call_count"),
        "elapsed_seconds": row.get("elapsed_seconds"),
    }


def _rate(numerator: int, denominator: int) -> float:
    return round(numerator / denominator, 6) if denominator else 0.0
