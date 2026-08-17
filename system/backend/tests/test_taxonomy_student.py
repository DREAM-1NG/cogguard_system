from __future__ import annotations

import importlib.util

import numpy as np
import pytest

from app.core.review.taxonomy_student import (
    DECEPTION_AXIS,
    INTERPERSONAL_AXIS,
    STANCE_AXIS,
    TextifiedStudentLoss,
    build_textified_input,
    build_textified_student_batch,
    build_textified_student_example,
)


def test_textified_input_uses_explicit_social_media_fields():
    case = {
        "text": "Main post",
        "hashtags": ["news", "A股"],
        "media": {"ocr": "image words", "asr": "spoken words", "caption": "video caption"},
    }

    text = build_textified_input(case)

    assert "[TEXT] Main post" in text
    assert "[HASHTAGS] news A股" in text
    assert "[OCR] image words" in text
    assert "[ASR] spoken words" in text
    assert "[CAPTION] video caption" in text


def test_hatexplain_maps_to_interpersonal_axis_only():
    example = build_textified_student_example(
        {
            "case_id": "hx-1",
            "dataset": "HateXplain",
            "split": "train",
            "text": "hateful text",
            "labels": {"raw_label": "hate", "target_groups": ["religion"]},
        }
    )

    assert example.task_mask[INTERPERSONAL_AXIS] == 1.0
    assert example.labels[INTERPERSONAL_AXIS] == 1.0
    assert example.task_mask[DECEPTION_AXIS] == 0.0


def test_hatecot_explanation_enables_rationale_lrkd_mask():
    batch = build_textified_student_batch(
        [
            {
                "case_id": "hc-1",
                "dataset": "HateCoT",
                "split": "train",
                "text": "attack text",
                "labels": {"label": "hate"},
                "explanation": "The post attacks a protected identity group.",
            },
            {
                "case_id": "ph-1",
                "dataset": "PHEME",
                "split": "train",
                "text": "rumor text",
                "labels": {"veracity": "false"},
                "claim_context": {"claim_text": "A disputed rumor"},
                "explanation": "This field must not be used for LRKD on PHEME in phase 1.",
            },
        ]
    )

    np.testing.assert_allclose(batch["task_mask"]["rationale"], np.asarray([1.0, 0.0], dtype="float32"))
    assert batch["rationale_texts"][0] == "The post attacks a protected identity group."


def test_student_examples_use_primary_text_fields_without_derived_media_text():
    example = build_textified_student_example(
        {
            "case_id": "text-only-1",
            "dataset": "HateXplain",
            "text": "post text",
            "hashtags": ["topic"],
            "media": {"ocr": "derived image text", "asr": "derived audio text", "caption": "derived caption"},
            "labels": {"raw_label": "normal"},
        }
    )

    assert "[TEXT] post text" in example.input_text
    assert "[HASHTAGS] topic" in example.input_text
    assert "derived image text" not in example.input_text
    assert "derived audio text" not in example.input_text
    assert "derived caption" not in example.input_text


def test_multioff_maps_to_interpersonal_offense_axis():
    example = build_textified_student_example(
        {
            "case_id": "mo-1",
            "dataset": "MultiOFF",
            "split": "train",
            "text": "offensive meme text",
            "labels": {"raw_label": "offensive"},
        }
    )

    assert example.task_mask[INTERPERSONAL_AXIS] == 1.0
    assert example.labels[INTERPERSONAL_AXIS] == 1.0
    assert example.fine_labels["insult"] == 1.0


@pytest.mark.parametrize("dataset", ["PHEME", "mcfend", "FakeSV", "Weibo21"])
def test_claim_datasets_map_to_deception_axis(dataset):
    example = build_textified_student_example(
        {
            "case_id": f"{dataset}-1",
            "dataset": dataset,
            "split": "train",
            "text": "claim text",
            "labels": {"veracity": "false"},
            "claim_context": {"claim_text": "A false claim"},
        }
    )

    assert example.task_mask[DECEPTION_AXIS] == 1.0
    assert example.labels[DECEPTION_AXIS] == 1.0
    assert example.task_mask[STANCE_AXIS] == 1.0
    assert example.labels[STANCE_AXIS] >= 0


def test_batch_exports_task_masks_for_non_flat_multitask_training():
    batch = build_textified_student_batch(
        [
            {"case_id": "hx", "dataset": "HateXplain", "text": "hate", "labels": {"raw_label": "hate"}},
            {
                "case_id": "ph",
                "dataset": "PHEME",
                "text": "rumor",
                "labels": {"raw_label": "rumor"},
                "claim_context": {"claim_text": "rumor claim"},
            },
        ]
    )

    np.testing.assert_allclose(batch["task_mask"][INTERPERSONAL_AXIS], np.asarray([1.0, 0.0], dtype="float32"))
    np.testing.assert_allclose(batch["task_mask"][DECEPTION_AXIS], np.asarray([0.0, 1.0], dtype="float32"))


@pytest.mark.skipif(importlib.util.find_spec("torch") is None, reason="torch not installed")
def test_textified_student_loss_is_task_masked():
    import torch

    outputs = {
        INTERPERSONAL_AXIS: torch.tensor([0.1, 0.2]),
        DECEPTION_AXIS: torch.tensor([0.3, 0.4]),
        STANCE_AXIS: torch.zeros((2, 5)),
        "fine_labels": torch.zeros((2, 13)),
    }
    targets = {
        INTERPERSONAL_AXIS: torch.tensor([1.0, 0.0]),
        f"{INTERPERSONAL_AXIS}_mask": torch.tensor([1.0, 0.0]),
        DECEPTION_AXIS: torch.tensor([0.0, 1.0]),
        f"{DECEPTION_AXIS}_mask": torch.tensor([0.0, 1.0]),
        STANCE_AXIS: torch.tensor([0, 1]),
        f"{STANCE_AXIS}_mask": torch.tensor([0.0, 1.0]),
        "fine_labels": torch.zeros((2, 13)),
        "fine_labels_mask": torch.tensor([1.0, 1.0]),
    }

    losses = TextifiedStudentLoss()(outputs, targets)

    assert losses["total_loss"].shape == torch.Size([])
    assert float(losses["total_loss"]) > 0.0


@pytest.mark.skipif(importlib.util.find_spec("torch") is None, reason="torch not installed")
def test_textified_student_forward_exports_protocol_head_dimensions_without_loading_backbone():
    import torch
    from torch import nn

    from app.core.review.taxonomy_student import XLMRTextifiedReviewStudent

    student = object.__new__(XLMRTextifiedReviewStudent)
    nn.Module.__init__(student)
    student.backbone = type("Backbone", (nn.Module,), {
        "forward": lambda self, input_ids, attention_mask, **kwargs: type(
            "Output", (), {"last_hidden_state": torch.ones((len(input_ids), 2, 4))}
        )()
    })()
    student.dropout = nn.Identity()
    student.interpersonal_aggression = nn.Linear(4, 1)
    student.ideological_deception = nn.Linear(4, 1)
    student.stance = nn.Linear(4, 5)
    student.fine_labels = nn.Linear(4, 13)
    student.rationale_proj = nn.Linear(4, 8)
    student.protocol_heads = nn.ModuleDict({
        "hatexplain_3way": nn.Linear(4, 3),
        "latent_hate_3way": nn.Linear(4, 3),
        "hatecheck_binary": nn.Linear(4, 2),
        "hatecot_universal_3way": nn.Linear(4, 3),
    })

    outputs = student(torch.ones((2, 2), dtype=torch.long), torch.ones((2, 2), dtype=torch.long))

    assert outputs["protocol_logits"]["hatexplain_3way"].shape == (2, 3)
    assert outputs["protocol_logits"]["latent_hate_3way"].shape == (2, 3)
    assert outputs["protocol_logits"]["hatecheck_binary"].shape == (2, 2)
