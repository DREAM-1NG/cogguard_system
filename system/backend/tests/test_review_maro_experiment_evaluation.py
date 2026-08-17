from __future__ import annotations

from app.core.review.maro_experiment_evaluation import (
    MARO_REFERENCE_IMPLEMENTATION,
    compare_maro_profiles,
    evaluate_claim_decisions,
    evaluate_maro_reference_binary_metrics,
)


def _case(case_id: str, label: str) -> dict:
    return {"case_id": case_id, "dataset": "PHEME", "labels": {"harmfulness": label}}


def _row(case_id: str, label: str, *, runtime: str = "complex", calls: int = 4) -> dict:
    return {
        "case_id": case_id,
        "dataset": "PHEME",
        "elapsed_seconds": 12.0,
        "agent_summary": {"actual_llm_call_count": calls},
        "runtime_audit": {"effective_runtime_mode": runtime},
        "judge_sidecar": {
            "teacher_prediction_valid": True,
            "teacher_prediction": {
                "main_axes": {"misinfo_claim_risk": {"available": True, "label": label}},
            },
        },
    }


def test_claim_evaluation_keeps_uncertain_out_of_binary_metrics():
    report = evaluate_claim_decisions(
        [_case("one", "harmful"), _case("two", "non_harmful")],
        [_row("one", "harmful"), _row("two", "uncertain")],
    )

    overall = report["overall"]
    assert overall["valid_footer_rate"] == 1.0
    assert overall["decision_coverage"] == 0.5
    assert overall["uncertain_rate"] == 0.5
    assert overall["classification_metrics"]["evaluated_count"] == 1
    assert overall["classification_metrics"]["accuracy"] == 1.0


def test_profile_comparison_reports_runtime_without_claiming_accuracy():
    comparison = compare_maro_profiles(
        [_row("one", "harmful", runtime="complex", calls=4)],
        [_row("one", "harmful", runtime="simple", calls=2)],
    )

    assert comparison["shared_case_count"] == 1
    assert comparison["decision_agreement_rate"] == 1.0
    assert comparison["fixed"]["mean_llm_calls_per_case"] == 4.0
    assert comparison["routed"]["simple_rate"] == 1.0


def test_maro_reference_metrics_keep_undecided_cases_out_of_binary_formula():
    report = evaluate_maro_reference_binary_metrics(
        [_case("one", "harmful"), _case("two", "non_harmful")],
        [_row("one", "harmful"), _row("two", "uncertain")],
    )

    assert report["reference_implementation"] == MARO_REFERENCE_IMPLEMENTATION
    assert report["decision_coverage"] == 0.5
    assert report["skipped_by_reason"] == {"uncertain": 1}
    assert report["metrics"] == {
        "evaluated_count": 1,
        "accuracy": 1.0,
        "f1_positive_fake": 1.0,
        "precision_positive_fake": 1.0,
    }
