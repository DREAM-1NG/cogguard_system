from __future__ import annotations

from app.core.review.maro_comparison import build_maro_horizontal_comparison, build_stratified_case_manifest


def _case(case_id: str, dataset: str, label: str, *, split: str = "test") -> dict:
    return {
        "case_id": case_id,
        "dataset": dataset,
        "split": split,
        "text": f"fixture {case_id}",
        "labels": {"harmfulness": label},
    }


def _teacher_row(
    case: dict,
    *,
    axis: str,
    label: str,
    confidence: float,
    available: bool = True,
    review_required: bool = False,
) -> dict:
    other_axis = "misinfo_claim_risk" if axis == "attack_hate_offense" else "attack_hate_offense"
    return {
        "case_id": case["case_id"],
        "dataset": case["dataset"],
        "split": case["split"],
        "teacher_silver": {
            "distillation_eligible": available,
            "review_required": review_required,
            "main_axes": {
                axis: {"available": available, "label": label, "confidence": confidence},
                other_axis: {"available": False, "label": "unavailable", "confidence": 0.0},
            },
        },
    }


def _student_row(case: dict, *, attack: float, misinfo: float, abstain: bool = False) -> dict:
    return {
        "case_id": case["case_id"],
        "dataset": case["dataset"],
        "split": case["split"],
        # Deliberately wrong: comparison gold must come from the source case.
        "y_true": "harmful" if case["labels"]["harmfulness"] == "non_harmful" else "non_harmful",
        "student": {
            "attack_hate_offense": attack,
            "misinfo_claim_risk": misinfo,
            "stance": {"label": "unlinked", "probability": 1.0},
            "defer_probability": 0.9 if abstain else 0.1,
            "abstain": abstain,
        },
    }


def test_maro_comparison_uses_shared_2plus1_gold_protocol_and_paired_cases():
    attack_positive = _case("hx-1", "HateXplain", "harmful")
    attack_negative = _case("mo-1", "MultiOFF", "non_harmful")
    misinfo_positive = _case("ph-1", "PHEME", "harmful")
    misinfo_negative = _case("mc-1", "mcfend", "non_harmful")
    cases = [attack_positive, attack_negative, misinfo_positive, misinfo_negative]

    agent_rows = [
        _teacher_row(attack_positive, axis="attack_hate_offense", label="harmful", confidence=0.9),
        _teacher_row(attack_negative, axis="attack_hate_offense", label="non_harmful", confidence=0.8),
        _teacher_row(misinfo_positive, axis="misinfo_claim_risk", label="harmful", confidence=0.7),
        _teacher_row(misinfo_negative, axis="misinfo_claim_risk", label="non_harmful", confidence=0.9),
    ]
    student_rows = [
        _student_row(attack_positive, attack=0.8, misinfo=0.1),
        _student_row(attack_negative, attack=0.2, misinfo=0.1),
        _student_row(misinfo_positive, attack=0.1, misinfo=0.3),
        _student_row(misinfo_negative, attack=0.1, misinfo=0.2),
    ]

    report = build_maro_horizontal_comparison(cases, agent_rows, student_rows)

    assert report["schema"] == "review-maro-horizontal-comparison-v1"
    assert report["protocol"]["dataset_axis_mapping"] == {
        "HateXplain": "attack_hate_offense",
        "MultiOFF": "attack_hate_offense",
        "PHEME": "misinfo_claim_risk",
        "mcfend": "misinfo_claim_risk",
        "FakeSV": "misinfo_claim_risk",
    }
    assert report["population"]["case_count"] == 4
    assert report["population"]["axis_counts"] == {
        "attack_hate_offense": 2,
        "misinfo_claim_risk": 2,
    }
    assert report["systems"]["multi_agent"]["decision_coverage"] == 1.0
    assert report["systems"]["multi_agent"]["metrics"]["macro_f1"] == 1.0
    assert report["systems"]["review_student"]["metrics"]["macro_f1"] == 0.666667
    assert report["paired"]["case_count"] == 4
    assert report["paired"]["multi_agent"]["macro_f1"] == 1.0
    assert report["paired"]["review_student"]["macro_f1"] == 0.666667
    assert report["paired"]["macro_f1_delta_multi_agent_minus_student"] == 0.333333


def test_maro_comparison_reports_missing_judge_predictions_without_silent_case_drop():
    available_case = _case("hx-1", "HateXplain", "harmful")
    unavailable_case = _case("hx-2", "HateXplain", "non_harmful")
    cases = [available_case, unavailable_case]
    agent_rows = [
        _teacher_row(available_case, axis="attack_hate_offense", label="harmful", confidence=0.9),
        _teacher_row(
            unavailable_case,
            axis="attack_hate_offense",
            label="unavailable",
            confidence=0.0,
            available=False,
        ),
    ]
    student_rows = [
        _student_row(available_case, attack=0.8, misinfo=0.1),
        _student_row(unavailable_case, attack=0.2, misinfo=0.1, abstain=True),
    ]

    report = build_maro_horizontal_comparison(cases, agent_rows, student_rows)

    multi_agent = report["systems"]["multi_agent"]
    student = report["systems"]["review_student"]
    assert multi_agent["submitted_count"] == 2
    assert multi_agent["valid_prediction_count"] == 1
    assert multi_agent["decision_coverage"] == 0.5
    assert multi_agent["missing_case_ids"] == ["hx-2"]
    assert student["decision_coverage"] == 1.0
    assert student["escalation_rate"] == 0.5
    assert report["paired"]["case_count"] == 1


def test_maro_comparison_rejects_prediction_identity_mismatch():
    case = _case("hx-1", "HateXplain", "harmful")
    bad_agent_row = _teacher_row(case, axis="attack_hate_offense", label="harmful", confidence=0.9)
    bad_agent_row["dataset"] = "MultiOFF"

    report = build_maro_horizontal_comparison(
        [case],
        [bad_agent_row],
        [_student_row(case, attack=0.8, misinfo=0.1)],
    )

    assert report["systems"]["multi_agent"]["valid_prediction_count"] == 0
    assert report["systems"]["multi_agent"]["integrity_errors"] == [
        "identity_mismatch:hx-1:expected=HateXplain/test:actual=MultiOFF/test"
    ]


def test_maro_comparison_rejects_legacy_teacher_rows_without_current_eligibility_gate():
    case = _case("hx-1", "HateXplain", "harmful")
    legacy_row = _teacher_row(case, axis="attack_hate_offense", label="harmful", confidence=0.9)
    legacy_row["teacher_silver"].pop("distillation_eligible")

    report = build_maro_horizontal_comparison(
        [case],
        [legacy_row],
        [_student_row(case, attack=0.8, misinfo=0.1)],
    )

    assert report["systems"]["multi_agent"]["valid_prediction_count"] == 0
    assert report["systems"]["multi_agent"]["decision_coverage"] == 0.0
    assert report["paired"]["case_count"] == 0


def test_shared_manifest_is_deterministic_balanced_and_contains_no_gold():
    cases = [
        _case(f"hx-pos-{index}", "HateXplain", "harmful")
        for index in range(4)
    ] + [
        _case(f"hx-neg-{index}", "HateXplain", "non_harmful")
        for index in range(4)
    ]
    eligible = [
        {"case_id": case["case_id"], "dataset": case["dataset"], "split": case["split"]}
        for case in reversed(cases)
    ]

    first, first_audit = build_stratified_case_manifest(cases, eligible, max_per_dataset=4, random_state=42)
    second, second_audit = build_stratified_case_manifest(cases, eligible, max_per_dataset=4, random_state=42)

    assert first == second
    assert first_audit == second_audit
    assert len(first) == 4
    assert all(set(row) == {"case_id", "dataset", "split"} for row in first)
    selected_ids = {row["case_id"] for row in first}
    assert sum(case["case_id"] in selected_ids and case["labels"]["harmfulness"] == "harmful" for case in cases) == 2
    assert sum(case["case_id"] in selected_ids and case["labels"]["harmfulness"] == "non_harmful" for case in cases) == 2
    assert first_audit["datasets"]["HateXplain"]["selected_distribution"] == {
        "harmful": 2,
        "non_harmful": 2,
    }
