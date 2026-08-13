from __future__ import annotations

import importlib.util
from pathlib import Path

import numpy as np


RUNNER_PATH = Path(__file__).resolve().parents[1] / "scripts" / "run_hatecot_lrkd_student.py"
SPEC = importlib.util.spec_from_file_location("hatecot_lrkd_student_runner", RUNNER_PATH)
assert SPEC and SPEC.loader
runner = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(runner)


def test_load_hatecot_csv_full_preserves_explanation_label_domain_and_target(tmp_path):
    csv_path = tmp_path / "hatecot.csv"
    csv_path.write_text(
        "id,explanation,domain,label,post,target,uid\n"
        "1,benign reason,toxigen,Benign,hello,,u1\n"
        "2,hate reason,dynahate,Hate Speech,attack text,group,u2\n",
        encoding="utf-8",
    )

    rows = runner.load_hatecot_csv_full(csv_path)

    assert len(rows) == 2
    assert rows[0]["case_id"] == "u1"
    assert rows[0]["binary_label"] == 0
    assert rows[1]["binary_label"] == 1
    assert rows[1]["explanation"] == "hate reason"
    assert rows[1]["domain"] == "dynahate"
    assert rows[1]["target"] == "group"


def test_split_hatecot_keeps_positive_and_negative_examples_in_each_split():
    rows = [
        {
            "case_id": f"case-{index}",
            "text": f"text {index}",
            "explanation": f"reason {index}",
            "binary_label": index % 2,
            "domain": "d",
            "target": "",
        }
        for index in range(60)
    ]

    splits = runner.split_hatecot(rows, random_state=7, max_cases_per_split=0)

    assert set(splits) == {"train", "validation", "test"}
    for split_rows in splits.values():
        assert {row["binary_label"] for row in split_rows} == {0, 1}


def test_build_reason_bank_uses_only_train_split_metadata():
    train_rows = [
        {"case_id": "train-1", "binary_label": 1, "domain": "d1", "target": "g", "explanation": "hate reason"},
        {"case_id": "train-2", "binary_label": 0, "domain": "d2", "target": "", "explanation": "benign reason"},
    ]
    vectors = np.asarray([[1.0, 0.0], [0.0, 1.0]], dtype="float32")

    bank = runner.build_reason_bank(train_rows, vectors)

    assert bank["vectors"].shape == (2, 2)
    assert [row["case_id"] for row in bank["metadata"]] == ["train-1", "train-2"]
    assert bank["metadata"][0]["split"] == "train"


def test_retrieve_nearest_reasons_excludes_same_case_id_and_reports_similarity():
    bank = {
        "vectors": np.asarray([[1.0, 0.0], [0.0, 1.0], [0.8, 0.2]], dtype="float32"),
        "metadata": [
            {"case_id": "same", "label": 1, "domain": "d", "target": "g", "explanation": "self"},
            {"case_id": "other-neg", "label": 0, "domain": "d", "target": "", "explanation": "negative"},
            {"case_id": "other-pos", "label": 1, "domain": "d", "target": "g", "explanation": "positive"},
        ],
    }

    results = runner.retrieve_nearest_reasons(
        np.asarray([1.0, 0.0], dtype="float32"),
        bank,
        top_k=2,
        exclude_case_id="same",
    )

    assert [row["case_id"] for row in results] == ["other-pos", "other-neg"]
    assert results[0]["similarity"] > results[1]["similarity"]


def test_reason_retrieval_metrics_count_label_domain_and_target_consistency():
    cases = [
        {"case_id": "q1", "binary_label": 1, "domain": "d", "target": "g", "explanation": "gold"},
        {"case_id": "q2", "binary_label": 0, "domain": "x", "target": "", "explanation": "gold"},
    ]
    projected = np.asarray([[1.0, 0.0], [0.0, 1.0]], dtype="float32")
    bank = {
        "vectors": np.asarray([[0.9, 0.1], [0.0, 1.0]], dtype="float32"),
        "metadata": [
            {"case_id": "train-pos", "label": 1, "domain": "d", "target": "g", "explanation": "positive"},
            {"case_id": "train-neg", "label": 0, "domain": "x", "target": "", "explanation": "negative"},
        ],
    }

    metrics, examples = runner.evaluate_reason_retrieval(cases, projected, bank, top_k=1, max_examples=10)

    assert metrics["support"] == 2
    assert metrics["top1_label_consistency"] == 1.0
    assert metrics["topk_same_domain_rate"] == 1.0
    assert metrics["topk_target_consistency_when_present"] == 1.0
    assert len(examples) == 2
    assert examples[0]["retrieved_reasons"][0]["explanation"] == "positive"


def test_build_checkpoint_payload_records_threshold_and_model_config():
    class Args:
        backbone = "FacebookAI/xlm-roberta-base"
        hf_cache_dir = "G:/CISCN/hf_models"
        allow_model_download = False
        max_length = 256
        rationale_dim = 768

    payload = runner.build_checkpoint_payload(
        args=Args(),
        model_state_dict={"weight": "placeholder"},
        train_info={"lrkd_valid_count": 10},
        threshold=0.7,
        validation_metrics={"macro_f1": 0.9},
    )

    assert payload["schema"] == "hatecot-lrkd-student-checkpoint-v1"
    assert payload["model_state_dict"] == {"weight": "placeholder"}
    assert payload["model_config"]["backbone"] == "FacebookAI/xlm-roberta-base"
    assert payload["model_config"]["rationale_dim"] == 768
    assert payload["decision_threshold"] == 0.7
    assert payload["validation_metrics"] == {"macro_f1": 0.9}


def test_should_step_optimizer_respects_accumulation_and_final_batch():
    assert not runner.should_step_optimizer(batch_index=0, batch_count=5, gradient_accumulation_steps=2)
    assert runner.should_step_optimizer(batch_index=1, batch_count=5, gradient_accumulation_steps=2)
    assert not runner.should_step_optimizer(batch_index=2, batch_count=5, gradient_accumulation_steps=2)
    assert runner.should_step_optimizer(batch_index=3, batch_count=5, gradient_accumulation_steps=2)
    assert runner.should_step_optimizer(batch_index=4, batch_count=5, gradient_accumulation_steps=2)


def test_prepare_tokenized_text_batch_keeps_all_rows_and_attention_masks():
    class Tokenizer:
        def __call__(self, texts, **kwargs):
            assert kwargs["padding"] == "max_length"
            assert kwargs["truncation"] is True
            return {
                "input_ids": np.asarray([[len(text)] for text in texts], dtype="int64"),
                "attention_mask": np.ones((len(texts), 1), dtype="int64"),
            }

    rows = [
        {"text": "alpha", "case_id": "a"},
        {"text": "beta", "case_id": "b"},
    ]

    encoded = runner.prepare_tokenized_text_batch(rows, Tokenizer(), max_length=16)

    assert set(encoded) == {"input_ids", "attention_mask"}
    assert encoded["input_ids"].shape[0] == len(rows)
    assert encoded["attention_mask"].shape == encoded["input_ids"].shape


def test_write_epoch_checkpoint_persists_latest_epoch(tmp_path):
    path = tmp_path / "checkpoint.pt"

    runner.write_epoch_checkpoint(
        path,
        model_state_dict={"weight": "epoch-2"},
        args=type(
            "Args",
            (),
            {
                "backbone": "FacebookAI/xlm-roberta-base",
                "hf_cache_dir": "G:/CISCN/hf_models",
                "allow_model_download": False,
                "max_length": 256,
                "rationale_dim": 768,
            },
        )(),
        train_info={"epoch": 2},
        threshold=0.7,
        validation_metrics={"macro_f1": 0.9},
    )

    assert path.exists()
    assert runner.load_checkpoint_payload(path)["train_info"]["epoch"] == 2
