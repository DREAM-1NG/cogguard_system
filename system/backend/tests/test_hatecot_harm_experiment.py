from __future__ import annotations

import csv

from app.core.review.hatecot_harm_experiment import (
    HATECOT_EVALUATION_LABELS,
    eligible_target_domains,
    evaluate_predictions,
    load_hatecot_cases,
    map_hatecot_label,
    select_target_cases,
)


def _row(*, identifier: str, domain: str, label: str, post: str) -> dict[str, str]:
    return {
        "id": identifier,
        "explanation": "Dataset-provided explanation that is never Agent input.",
        "domain": domain,
        "label": label,
        "post": post,
        "target": "group",
        "uid": identifier,
    }


def test_loader_maps_audited_labels_and_excludes_animosity(tmp_path):
    path = tmp_path / "hatecot.csv"
    rows = [
        _row(identifier="1", domain="cad", label="Neutral", post="neutral"),
        _row(identifier="2", domain="cad", label="Person Directed Abuse", post="abuse"),
        _row(identifier="3", domain="cad", label="Identity Directed Abuse", post="identity abuse"),
        _row(identifier="4", domain="dynahate", label="Animosity", post="ambiguous"),
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)

    cases, manifest = load_hatecot_cases(path)

    assert [case["labels"]["interpersonal_harm"] for case in cases] == list(HATECOT_EVALUATION_LABELS)
    assert manifest["eligible_row_count"] == 3
    assert manifest["excluded_label_counts"] == {"Animosity": 1}
    assert all("explanation" not in case for case in cases)
    assert eligible_target_domains(cases) == ["cad"]
    assert map_hatecot_label("Animosity") is None


def test_loader_deduplicates_exact_source_repeats_but_rejects_conflicts(tmp_path):
    path = tmp_path / "hatecot_duplicates.csv"
    repeated = _row(identifier="1", domain="cad", label="Neutral", post="neutral")
    conflict = _row(identifier="1", domain="cad", label="Identity Directed Abuse", post="different text")
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=repeated.keys())
        writer.writeheader()
        writer.writerows([repeated, repeated])

    cases, manifest = load_hatecot_cases(path)
    assert len(cases) == 1
    assert manifest["mappable_source_row_count"] == 2
    assert manifest["duplicate_eligible_row_count"] == 1

    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=repeated.keys())
        writer.writeheader()
        writer.writerows([repeated, conflict])
    try:
        load_hatecot_cases(path)
    except ValueError as error:
        assert "Conflicting HateCoT duplicate case ID" in str(error)
    else:
        raise AssertionError("conflicting duplicate IDs must fail the protocol")


def test_target_sampling_is_exact_stratified_and_evaluation_is_three_way():
    cases = [
        {
            "case_id": f"cad::{label}::{index}",
            "source_id": f"{label}-{index}",
            "text": f"{label} text {index}",
            "labels": {"interpersonal_harm": label},
            "metadata": {"category": "cad"},
        }
        for label in HATECOT_EVALUATION_LABELS
        for index in range(3)
    ]

    selected = select_target_cases(cases, cases_per_label=2, random_state=42)
    selected_again = select_target_cases(cases, cases_per_label=2, random_state=42)
    assert [case["case_id"] for case in selected] == [case["case_id"] for case in selected_again]
    assert len(selected) == 6
    assert {label: sum(case["labels"]["interpersonal_harm"] == label for case in selected) for label in HATECOT_EVALUATION_LABELS} == {
        "non_harmful": 2,
        "offensive": 2,
        "hate": 2,
    }

    metrics = evaluate_predictions([
        {"gold_label": "non_harmful", "prediction": "non_harmful"},
        {"gold_label": "offensive", "prediction": "hate"},
        {"gold_label": "hate", "prediction": "hate"},
    ])
    assert metrics["submitted_count"] == 3
    assert set(metrics["classification_metrics"]["per_class_f1"]) == set(HATECOT_EVALUATION_LABELS)
    assert metrics["confusion_matrix"]["label_order"] == list(HATECOT_EVALUATION_LABELS)
