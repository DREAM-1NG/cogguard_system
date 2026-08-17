"""Shared MARO-style evaluation protocol for MultiAgent and ReviewStudent."""

from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any, Callable

import numpy as np

from app.core.review.trainable_post import (
    ATTACK_AXIS,
    MISINFO_AXIS,
    NEGATIVE_LABEL,
    POSITIVE_LABEL,
    STANCE_ORDER,
    binary_classification_metrics,
    binary_label,
    binary_pr_auc,
    expected_calibration_error,
    stance_proxy_of,
)

__all__ = ["DATASET_AXIS_MAPPING", "build_maro_horizontal_comparison", "build_stratified_case_manifest"]


DATASET_AXIS_MAPPING = {
    "HateXplain": ATTACK_AXIS,
    "MultiOFF": ATTACK_AXIS,
    "PHEME": MISINFO_AXIS,
    "mcfend": MISINFO_AXIS,
    "FakeSV": MISINFO_AXIS,
    "Weibo21": MISINFO_AXIS,
}
_DATASET_LOOKUP = {name.lower(): (name, axis) for name, axis in DATASET_AXIS_MAPPING.items()}


def build_stratified_case_manifest(
    cases: list[dict[str, Any]],
    eligible_rows: list[dict[str, Any]],
    *,
    max_per_dataset: int,
    random_state: int = 42,
) -> tuple[list[dict[str, str]], dict[str, Any]]:
    """Build a deterministic, label-stratified manifest without exporting gold."""
    eligible = {
        (str(row.get("dataset") or "").lower(), str(row.get("case_id") or ""), str(row.get("split") or ""))
        for row in eligible_rows
        if str(row.get("case_id") or "") and str(row.get("dataset") or "")
    }
    grouped: dict[str, dict[str, list[dict[str, Any]]]] = defaultdict(lambda: defaultdict(list))
    for case in cases:
        dataset_value = str(case.get("dataset") or "")
        mapped = _DATASET_LOOKUP.get(dataset_value.lower())
        if mapped is None:
            continue
        dataset, _ = mapped
        identity = (dataset.lower(), str(case.get("case_id") or ""), str(case.get("split") or ""))
        if identity not in eligible:
            continue
        grouped[dataset][POSITIVE_LABEL if binary_label(case) else NEGATIVE_LABEL].append(case)
    rng = np.random.default_rng(random_state)
    manifest: list[dict[str, str]] = []
    audit: dict[str, Any] = {"random_state": random_state, "max_per_dataset": max_per_dataset, "datasets": {}}
    for dataset in DATASET_AXIS_MAPPING:
        by_label = grouped.get(dataset, {})
        positive = list(by_label.get(POSITIVE_LABEL, []))
        negative = list(by_label.get(NEGATIVE_LABEL, []))
        rng.shuffle(positive)
        rng.shuffle(negative)
        limit = len(positive) + len(negative) if max_per_dataset <= 0 else max_per_dataset
        positive_target = min(len(positive), (limit + 1) // 2)
        negative_target = min(len(negative), limit // 2)
        remaining = limit - positive_target - negative_target
        if remaining > 0:
            add_positive = min(remaining, len(positive) - positive_target)
            positive_target += add_positive
            remaining -= add_positive
        if remaining > 0:
            negative_target += min(remaining, len(negative) - negative_target)
        selected = [*positive[:positive_target], *negative[:negative_target]]
        selected.sort(key=lambda case: str(case.get("case_id") or ""))
        manifest.extend(
            {
                "case_id": str(case.get("case_id") or ""),
                "dataset": dataset,
                "split": str(case.get("split") or ""),
            }
            for case in selected
        )
        audit["datasets"][dataset] = {
            "eligible_count": len(positive) + len(negative),
            "eligible_distribution": {POSITIVE_LABEL: len(positive), NEGATIVE_LABEL: len(negative)},
            "selected_count": len(selected),
            "selected_distribution": {POSITIVE_LABEL: positive_target, NEGATIVE_LABEL: negative_target},
        }
    audit["selected_count"] = len(manifest)
    return manifest, audit


def build_maro_horizontal_comparison(
    cases: list[dict[str, Any]],
    multi_agent_rows: list[dict[str, Any]],
    student_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    """Compare both systems on identical cases under the shared 2+1 protocol.

    Dataset gold is read only from ``cases``. Prediction rows contribute scores,
    labels, and routing decisions but cannot override the evaluation target.
    """
    population, population_errors = _build_population(cases)
    agent_index, agent_index_errors = _index_predictions(multi_agent_rows, "multi_agent")
    student_index, student_index_errors = _index_predictions(student_rows, "review_student")
    multi_agent = _evaluate_system(
        population,
        agent_index,
        prediction_reader=_read_multi_agent_prediction,
        escalation_reader=_read_multi_agent_escalation,
        initial_errors=[*population_errors, *agent_index_errors],
    )
    review_student = _evaluate_system(
        population,
        student_index,
        prediction_reader=_read_student_prediction,
        escalation_reader=_read_student_escalation,
        initial_errors=[*population_errors, *student_index_errors],
    )
    paired_ids = [
        item["case_id"]
        for item in population
        if item["case_id"] in multi_agent["_valid_predictions"]
        and item["case_id"] in review_student["_valid_predictions"]
    ]
    paired_agent = _metrics_for_ids(population, multi_agent["_valid_predictions"], paired_ids)
    paired_student = _metrics_for_ids(population, review_student["_valid_predictions"], paired_ids)
    paired = {
        "case_count": len(paired_ids),
        "case_ids": paired_ids,
        "multi_agent": paired_agent,
        "review_student": paired_student,
        "macro_f1_delta_multi_agent_minus_student": round(
            float(paired_agent.get("macro_f1", 0.0)) - float(paired_student.get("macro_f1", 0.0)),
            6,
        ),
        "accuracy_delta_multi_agent_minus_student": round(
            float(paired_agent.get("accuracy", 0.0)) - float(paired_student.get("accuracy", 0.0)),
            6,
        ),
    }
    multi_agent.pop("_valid_predictions", None)
    review_student.pop("_valid_predictions", None)
    return {
        "schema": "review-maro-horizontal-comparison-v1",
        "protocol": {
            "name": "shared_2plus1_maro_evaluation",
            "dataset_axis_mapping": dict(DATASET_AXIS_MAPPING),
            "main_metrics": ["accuracy", "macro_f1", "precision", "recall", "pr_auc", "ece"],
            "auxiliary_task": "claim_linked_stance",
            "routing_metrics_separate_from_raw_classification": True,
            "gold_source": "source_case_labels_only",
            "pairing_key": "case_id + dataset + split",
        },
        "population": {
            "case_count": len(population),
            "dataset_counts": dict(Counter(item["dataset"] for item in population)),
            "axis_counts": dict(Counter(item["axis"] for item in population)),
            "gold_distribution": dict(Counter(item["gold_label"] for item in population)),
            "integrity_errors": population_errors,
        },
        "systems": {
            "multi_agent": multi_agent,
            "review_student": review_student,
        },
        "paired": paired,
        "interpretation_boundary": {
            "raw_decision_metrics": "Use the main-axis table for MARO-style classification comparison.",
            "coverage": "Missing or invalid Judge predictions reduce decision coverage and are not silently dropped.",
            "routing": "MultiAgent review_required and Student abstain/defer are reported separately.",
            "stance": "Stance is auxiliary and does not contribute to main-axis macro-F1.",
        },
    }


def _build_population(cases: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[str]]:
    population: list[dict[str, Any]] = []
    errors: list[str] = []
    seen: set[str] = set()
    for case in cases:
        case_id = str(case.get("case_id") or "").strip()
        dataset_value = str(case.get("dataset") or "").strip()
        mapped = _DATASET_LOOKUP.get(dataset_value.lower())
        if not case_id or not mapped:
            continue
        dataset, axis = mapped
        if case_id in seen:
            errors.append(f"duplicate_source_case_id:{case_id}")
            continue
        seen.add(case_id)
        population.append(
            {
                "case_id": case_id,
                "dataset": dataset,
                "split": str(case.get("split") or ""),
                "axis": axis,
                "gold_label": POSITIVE_LABEL if binary_label(case) else NEGATIVE_LABEL,
                "gold_stance": stance_proxy_of(case),
                "claim_linked": stance_proxy_of(case) != "unlinked",
            }
        )
    return population, errors


def _index_predictions(rows: list[dict[str, Any]], system_name: str) -> tuple[dict[str, dict[str, Any]], list[str]]:
    index: dict[str, dict[str, Any]] = {}
    duplicate_ids: set[str] = set()
    errors: list[str] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        case_id = str(row.get("case_id") or "").strip()
        if not case_id:
            continue
        if case_id in index:
            duplicate_ids.add(case_id)
            continue
        index[case_id] = row
    for case_id in sorted(duplicate_ids):
        index.pop(case_id, None)
        errors.append(f"duplicate_prediction_case_id:{system_name}:{case_id}")
    return index, errors


def _evaluate_system(
    population: list[dict[str, Any]],
    prediction_index: dict[str, dict[str, Any]],
    *,
    prediction_reader: Callable[[dict[str, Any], str], tuple[float, str] | None],
    escalation_reader: Callable[[dict[str, Any]], bool],
    initial_errors: list[str],
) -> dict[str, Any]:
    valid: dict[str, dict[str, Any]] = {}
    missing: list[str] = []
    errors = list(initial_errors)
    submitted_count = 0
    escalation_count = 0
    stance_correct = 0
    stance_available = 0
    stance_eligible = 0
    for item in population:
        row = prediction_index.get(item["case_id"])
        if row is None:
            missing.append(item["case_id"])
            continue
        submitted_count += 1
        actual_dataset = str(row.get("dataset") or "")
        actual_split = str(row.get("split") or "")
        if actual_dataset.lower() != item["dataset"].lower() or actual_split != item["split"]:
            errors.append(
                f"identity_mismatch:{item['case_id']}:expected={item['dataset']}/{item['split']}:"
                f"actual={actual_dataset}/{actual_split}"
            )
            missing.append(item["case_id"])
            continue
        if escalation_reader(row):
            escalation_count += 1
        prediction = prediction_reader(row, item["axis"])
        if prediction is None:
            missing.append(item["case_id"])
            continue
        probability, predicted_label = prediction
        valid[item["case_id"]] = {
            "probability": probability,
            "predicted_label": predicted_label,
        }
        if item["claim_linked"]:
            stance_eligible += 1
            stance_prediction = _read_stance_prediction(row)
            if stance_prediction in STANCE_ORDER:
                stance_available += 1
                stance_correct += int(stance_prediction == item["gold_stance"])
    metrics = _metrics_for_ids(population, valid, list(valid))
    population_count = len(population)
    return {
        "submitted_count": submitted_count,
        "valid_prediction_count": len(valid),
        "decision_coverage": round(len(valid) / population_count, 6) if population_count else 0.0,
        "escalation_count": escalation_count,
        "escalation_rate": round(escalation_count / population_count, 6) if population_count else 0.0,
        "missing_case_ids": missing,
        "integrity_errors": errors,
        "metrics": metrics,
        "stance": {
            "eligible_count": stance_eligible,
            "available_count": stance_available,
            "coverage": round(stance_available / stance_eligible, 6) if stance_eligible else 0.0,
            "accuracy": round(stance_correct / stance_available, 6) if stance_available else 0.0,
        },
        "_valid_predictions": valid,
    }


def _metrics_for_ids(
    population: list[dict[str, Any]],
    predictions: dict[str, dict[str, Any]],
    case_ids: list[str],
) -> dict[str, Any]:
    selected_ids = set(case_ids)
    selected = [item for item in population if item["case_id"] in selected_ids and item["case_id"] in predictions]
    if not selected:
        return {
            "case_count": 0,
            "macro_f1": 0.0,
            "accuracy": 0.0,
            "pr_auc": 0.0,
            "ece": 0.0,
            "axes": {},
            "datasets": {},
        }
    axes: dict[str, Any] = {}
    for axis in (ATTACK_AXIS, MISINFO_AXIS):
        axis_items = [item for item in selected if item["axis"] == axis]
        if axis_items:
            axes[axis] = _binary_metrics(axis_items, predictions)
    datasets = {
        dataset: _binary_metrics([item for item in selected if item["dataset"] == dataset], predictions)
        for dataset in DATASET_AXIS_MAPPING
        if any(item["dataset"] == dataset for item in selected)
    }
    pooled = _binary_metrics(selected, predictions)
    axis_macro_f1 = float(np.mean([item["macro_f1"] for item in axes.values()])) if axes else 0.0
    axis_pr_auc = float(np.mean([item["pr_auc"] for item in axes.values()])) if axes else 0.0
    return {
        "case_count": len(selected),
        "macro_f1": round(axis_macro_f1, 6),
        "accuracy": pooled["accuracy"],
        "pr_auc": round(axis_pr_auc, 6),
        "ece": pooled["ece"],
        "per_class": pooled["per_class"],
        "axes": axes,
        "datasets": datasets,
    }


def _binary_metrics(items: list[dict[str, Any]], predictions: dict[str, dict[str, Any]]) -> dict[str, Any]:
    labels = np.asarray([1 if item["gold_label"] == POSITIVE_LABEL else 0 for item in items], dtype=int)
    probabilities = np.asarray([predictions[item["case_id"]]["probability"] for item in items], dtype="float32")
    metrics = binary_classification_metrics(labels, probabilities)
    return {
        **metrics,
        "case_count": len(items),
        "pr_auc": binary_pr_auc(labels, probabilities),
        "ece": expected_calibration_error(labels, probabilities),
    }


def _read_multi_agent_prediction(row: dict[str, Any], axis: str) -> tuple[float, str] | None:
    nested_silver = isinstance(row.get("teacher_silver"), dict)
    silver = row.get("teacher_silver") if nested_silver else row
    if nested_silver and silver.get("distillation_eligible") is not True:
        return None
    if not nested_silver and "distillation_eligible" in silver and silver.get("distillation_eligible") is not True:
        return None
    main_axes = silver.get("main_axes") if isinstance(silver.get("main_axes"), dict) else None
    if main_axes is None:
        sidecar = row.get("judge_sidecar") or {}
        teacher_prediction = sidecar.get("teacher_prediction") or {}
        main_axes = teacher_prediction.get("main_axes") or {}
    axis_prediction = main_axes.get(axis) if isinstance(main_axes, dict) else None
    if not isinstance(axis_prediction, dict) or axis_prediction.get("available") is not True:
        return None
    label = str(axis_prediction.get("label") or "")
    if label not in {POSITIVE_LABEL, NEGATIVE_LABEL}:
        return None
    confidence = max(0.0, min(1.0, float(axis_prediction.get("confidence") or 0.0)))
    probability = confidence if label == POSITIVE_LABEL else 1.0 - confidence
    return probability, label


def _read_student_prediction(row: dict[str, Any], axis: str) -> tuple[float, str] | None:
    student = row.get("student") or {}
    if axis not in student:
        return None
    probability = max(0.0, min(1.0, float(student[axis])))
    return probability, POSITIVE_LABEL if probability >= 0.5 else NEGATIVE_LABEL


def _read_multi_agent_escalation(row: dict[str, Any]) -> bool:
    silver = row.get("teacher_silver") if isinstance(row.get("teacher_silver"), dict) else row
    if "review_required" in silver:
        return bool(silver.get("review_required"))
    sidecar = row.get("judge_sidecar") or {}
    prediction = sidecar.get("teacher_prediction") or {}
    return bool(prediction.get("review_required") or sidecar.get("review_required"))


def _read_student_escalation(row: dict[str, Any]) -> bool:
    student = row.get("student") or {}
    return bool(student.get("abstain") or float(student.get("defer_probability") or 0.0) >= 0.5)


def _read_stance_prediction(row: dict[str, Any]) -> str:
    student = row.get("student") or {}
    if isinstance(student.get("stance"), dict):
        return str(student["stance"].get("label") or "")
    silver = row.get("teacher_silver") if isinstance(row.get("teacher_silver"), dict) else row
    stance = silver.get("stance") or {}
    if isinstance(stance, dict) and stance.get("available") is True:
        return str(stance.get("label") or "")
    sidecar = row.get("judge_sidecar") or {}
    teacher_prediction = sidecar.get("teacher_prediction") or {}
    stance = teacher_prediction.get("stance") or {}
    return str(stance.get("label") or "") if isinstance(stance, dict) and stance.get("available") is True else ""
