from __future__ import annotations

import numpy as np

from app.core.review.selective_student import ATTACK_AXIS, build_selective_student_targets


def test_teacher_confidence_becomes_soft_target_blended_with_dataset_label():
    case = {
        "case_id": "hx-1",
        "dataset": "HateXplain",
        "split": "train",
        "text": "fixture",
        "labels": {"harmfulness": "non_harmful"},
    }
    teacher = {
        "case_id": "hx-1",
        "dataset": "HateXplain",
        "split": "train",
        "confidence": 0.8,
        "review_required": False,
        "main_axes": {
            ATTACK_AXIS: {
                "available": True,
                "label": "harmful",
                "confidence": 0.8,
            }
        },
    }

    targets = build_selective_student_targets(
        [case],
        {"hx-1": teacher},
        distillation_alpha=0.75,
    )

    # (1 - alpha) * gold(0.0) + alpha * teacher_probability(0.8)
    np.testing.assert_allclose(targets["attack"], np.asarray([0.6], dtype="float32"))
    assert targets["attack_mask"].tolist() == [1.0]
    assert targets["teacher_supervision_mask"].tolist() == [1.0]


def test_no_teacher_keeps_dataset_supervision_unchanged():
    case = {
        "case_id": "hx-1",
        "dataset": "HateXplain",
        "split": "train",
        "text": "fixture",
        "labels": {"harmfulness": "harmful"},
    }

    targets = build_selective_student_targets([case], {}, distillation_alpha=0.75)

    assert targets["attack"].tolist() == [1.0]
    assert targets["teacher_supervision_mask"].tolist() == [0.0]
