from __future__ import annotations

import copy

from app.core.review.agent_contracts import JUDGE_DECISION_BEGIN, JUDGE_DECISION_END
from app.core.review.agent_contracts import parse_judge_decision_footer
from app.core.review.teacher_silver import build_teacher_silver_record, load_teacher_silver_index


def _case(label: str) -> dict:
    return {
        "case_id": "case-1",
        "dataset": "HateXplain",
        "split": "test",
        "text": "A reviewed post.",
        "labels": {"harmfulness": label, "raw_label": label},
    }


def _review_with_prediction() -> dict:
    prediction = {
        "schema_version": "review-judge-teacher-prediction-v1",
        "main_axes": {
            "attack_hate_offense": {"available": True, "label": "harmful", "confidence": 0.91},
            "misinfo_claim_risk": {"available": False, "label": "unavailable", "confidence": 0.0},
        },
        "stance": {"available": False, "label": "unlinked", "confidence": 0.0},
        "review_required": True,
        "review_reason": ["high_risk"],
        "fine_labels": ["hate_harassment"],
    }
    return {
        "summary": {"requested_agents": 1, "completed": 1, "effective_runtime_mode": "complex"},
        "agent_reports": [
            {
                "agent_name": "HarmfulnessJudgeAgent",
                "status": "completed",
                "structured_sidecar": {
                    "teacher_prediction": prediction,
                    "teacher_prediction_valid": True,
                },
            }
        ],
    }


def test_judge_footer_is_stripped_and_validated():
    footer = {
        "main_axes": {
            "attack_hate_offense": {"available": True, "label": "harmful", "confidence": 0.91},
            "misinfo_claim_risk": {"available": False, "label": "unavailable", "confidence": 0.0},
        },
        "stance": {"available": False, "label": "unlinked", "confidence": 0.0},
        "review_required": True,
        "review_reason": ["high_risk"],
        "fine_labels": ["hate_harassment"],
    }
    import json

    report, prediction, error = parse_judge_decision_footer(
        f"Chinese analyst report\n{JUDGE_DECISION_BEGIN}{json.dumps(footer)}{JUDGE_DECISION_END}"
    )

    assert report == "Chinese analyst report"
    assert error is None
    assert prediction["main_axes"]["attack_hate_offense"]["label"] == "harmful"


def test_judge_footer_rejects_string_boolean_fields():
    import json

    footer = {
        "main_axes": {
            "attack_hate_offense": {"available": "false", "label": "harmful", "confidence": 0.91},
            "misinfo_claim_risk": {"available": False, "label": "unavailable", "confidence": 0.0},
        },
        "stance": {"available": False, "label": "unlinked", "confidence": 0.0},
        "review_required": "false",
        "review_reason": [],
        "fine_labels": [],
    }

    _, prediction, error = parse_judge_decision_footer(
        f"Analyst report\n{JUDGE_DECISION_BEGIN}{json.dumps(footer)}{JUDGE_DECISION_END}"
    )

    assert prediction is None
    assert error == "invalid_judge_axis_available:attack_hate_offense"


def test_teacher_silver_prediction_is_independent_of_dataset_gold():
    harmful = build_teacher_silver_record(_case("harmful"), _review_with_prediction())
    benign = build_teacher_silver_record(_case("non_harmful"), _review_with_prediction())

    assert harmful["main_axes"] == benign["main_axes"]
    assert harmful["fine_labels"] == benign["fine_labels"] == ["hate_harassment"]
    assert harmful["distillation_eligible"] is True
    assert harmful["review_required"] is True


def test_missing_structured_judge_prediction_is_not_distillable():
    review = copy.deepcopy(_review_with_prediction())
    review["agent_reports"][0]["structured_sidecar"] = {}

    silver = build_teacher_silver_record(_case("harmful"), review)

    assert silver["distillation_eligible"] is False
    assert all(not axis["available"] for axis in silver["main_axes"].values())
    assert load_teacher_silver_index([silver]) == {}


def test_teacher_silver_index_rejects_wrong_schema_and_duplicate_case_ids():
    valid = build_teacher_silver_record(_case("harmful"), _review_with_prediction())
    wrong_schema = copy.deepcopy(valid)
    wrong_schema["schema_version"] = "legacy-teacher-silver"
    duplicate = copy.deepcopy(valid)
    duplicate["dataset"] = "OtherDataset"

    assert load_teacher_silver_index([wrong_schema]) == {}
    assert load_teacher_silver_index([valid, duplicate]) == {}


def test_deep_judge_silver_uses_final_prediction():
    review = _review_with_prediction()
    draft = copy.deepcopy(review["agent_reports"][0])
    draft["report_role"] = "judge_draft"
    draft["structured_sidecar"]["teacher_prediction"]["main_axes"]["attack_hate_offense"]["label"] = "non_harmful"
    final = copy.deepcopy(review["agent_reports"][0])
    final["report_role"] = "judge_final"
    review["agent_reports"] = [draft, final]

    silver = build_teacher_silver_record(_case("non_harmful"), review)

    assert silver["main_axes"]["attack_hate_offense"]["label"] == "harmful"


def test_teacher_silver_confidence_is_bounded_when_followup_reports_exceed_requested_agents():
    review = _review_with_prediction()
    review["summary"].update({"requested_agents": 1, "completed": 8, "reflection_response_reports": 2})

    silver = build_teacher_silver_record(_case("harmful"), review)

    assert 0.0 <= silver["confidence"] <= 1.0
