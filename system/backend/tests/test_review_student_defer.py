from __future__ import annotations

import numpy as np

from app.core.review.selective_student import apply_defer_strategy, build_selective_student_targets


def _case(case_id: str) -> dict:
    return {
        "case_id": case_id,
        "dataset": "HateXplain",
        "split": "train",
        "text": "fixture",
        "labels": {"harmfulness": "non_harmful"},
    }


def test_dataset_gold_does_not_create_negative_defer_labels():
    targets = build_selective_student_targets([_case("plain")])

    assert targets["defer_mask"].tolist() == [0.0]


def test_teacher_review_required_is_the_defer_target():
    cases = [_case("accept"), _case("defer")]
    teacher = {
        "accept": {
            "dataset": "HateXplain",
            "split": "train",
            "confidence": 0.9,
            "review_required": False,
            "main_axes": {},
        },
        "defer": {
            "dataset": "HateXplain",
            "split": "train",
            "confidence": 0.9,
            "review_required": True,
            "main_axes": {},
        },
    }

    targets = build_selective_student_targets(cases, teacher)

    assert targets["defer_mask"].tolist() == [1.0, 1.0]
    assert targets["defer"].tolist() == [0.0, 1.0]


def test_uncertain_teacher_axis_is_masked_instead_of_becoming_negative_supervision():
    case = _case("uncertain-axis")
    teacher = {
        "uncertain-axis": {
            "dataset": "HateXplain",
            "split": "train",
            "confidence": 0.5,
            "review_required": True,
            "main_axes": {
                "attack_hate_offense": {
                    "available": True,
                    "label": "uncertain",
                    "confidence": 0.5,
                }
            },
        }
    }

    targets = build_selective_student_targets([case], teacher)

    assert targets["attack_mask"].tolist() == [0.0]


def test_teacher_supervision_requires_matching_dataset_and_split():
    case = _case("mismatch")
    teacher = {
        "mismatch": {
            "dataset": "OtherDataset",
            "split": "test",
            "confidence": 0.9,
            "review_required": True,
            "main_axes": {},
        }
    }

    targets = build_selective_student_targets([case], teacher)

    assert targets["defer_mask"].tolist() == [0.0]


def test_unsupervised_defer_uses_semantic_uncertainty():
    predictions = {
        "attack_hate_offense": np.asarray([0.5, 0.01], dtype="float32"),
        "misinfo_claim_risk": np.asarray([0.5, 0.01], dtype="float32"),
        "stance": np.asarray([[1, 0, 0, 0, 0], [1, 0, 0, 0, 0]], dtype="float32"),
        "defer": np.asarray([0.1, 0.9], dtype="float32"),
    }

    resolved = apply_defer_strategy([_case("uncertain"), _case("confident")], predictions, defer_head_supervised=False)

    assert resolved["defer"][0] > resolved["defer"][1]
    assert resolved["defer"][0] >= 0.5
    assert resolved["defer"][1] < 0.5
