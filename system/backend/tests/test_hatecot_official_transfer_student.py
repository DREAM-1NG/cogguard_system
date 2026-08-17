from __future__ import annotations

import importlib.util
from collections import Counter
from pathlib import Path

import numpy as np


RUNNER_PATH = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "run_hatecot_official_transfer_student.py"
)
SPEC = importlib.util.spec_from_file_location("hatecot_official_transfer_runner", RUNNER_PATH)
assert SPEC and SPEC.loader
runner = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(runner)


def test_hatecot_source_labels_use_official_three_way_mapping_and_reject_ambiguous():
    assert runner.map_hatecot_protocol_label("Normal") == 0
    assert runner.map_hatecot_protocol_label("Offensive") == 1
    assert runner.map_hatecot_protocol_label("Hate Speech") == 2
    assert runner.map_hatecot_protocol_label("Animosity") is None
    assert runner.map_hatecot_protocol_label("Threatening") is None


def test_target_label_mappings_preserve_official_three_class_spaces():
    assert runner.map_target_label("HateCheck", "Non-hateful") == 0
    assert runner.map_target_label("HateCheck", "Hateful") == 1
    assert runner.map_target_label("HateXplain", "Normal") == 0
    assert runner.map_target_label("HateXplain", "Offensive") == 1
    assert runner.map_target_label("HateXplain", "Hate Speech") == 2
    assert runner.map_target_label("Latent_Hate", "Not Hate") == 0
    assert runner.map_target_label("Latent_Hate", "Explicit Hate") == 1
    assert runner.map_target_label("Latent_Hate", "Implicit Hate") == 2


def test_latent_hate_source_proxy_is_explicit_about_the_non_equivalent_middle_class():
    assert runner.source_to_latent_hate_proxy_label(0) == 0
    assert runner.source_to_latent_hate_proxy_label(1) == 2
    assert runner.source_to_latent_hate_proxy_label(2) == 1


def test_balanced_protocol_sampling_has_k_examples_per_class_and_no_overlap():
    rows = [
        {"case_id": f"{label}-{index}", "protocol_label": label}
        for label in range(3)
        for index in range(300)
    ]
    support, test = runner.build_protocol_support_test(
        rows,
        classes=3,
        support_per_class=200,
        test_per_class=4,
        random_state=42,
    )

    assert len(support) == 600
    assert len(test) == 12
    assert {row["protocol_label"] for row in support} == {0, 1, 2}
    assert {row["protocol_label"] for row in test} == {0, 1, 2}
    assert not ({row["case_id"] for row in support} & {row["case_id"] for row in test})


def test_official_split_sampling_never_uses_hatexplain_test_rows_for_support():
    support_pool = [
        {"case_id": f"support-{label}-{index}", "protocol_label": label}
        for label in range(3)
        for index in range(8)
    ]
    test_pool = [
        {"case_id": f"test-{label}-{index}", "protocol_label": label}
        for label in range(3)
        for index in range(8)
    ]

    support, test = runner.build_protocol_support_from_pool(
        support_pool,
        test_pool,
        classes=3,
        support_per_class=4,
        test_per_class=4,
        random_state=42,
    )

    assert all(row["case_id"].startswith("support-") for row in support)
    assert all(row["case_id"].startswith("test-") for row in test)


def test_hatexplain_full_support_pool_excludes_all_official_test_case_ids():
    official_train = [
        {"case_id": f"train-{label}-{index}", "protocol_label": label, "split": "train"}
        for label in range(3)
        for index in range(300)
    ]
    official_test = [
        {"case_id": f"test-{label}-{index}", "protocol_label": label, "split": "test"}
        for label in range(3)
        for index in range(500)
    ]
    full_support = list(official_train)

    assert not ({row["case_id"] for row in full_support} & {row["case_id"] for row in official_test})


def test_k_shot_support_is_exactly_k_per_class_without_test_leakage():
    support = [
        {"case_id": f"{label}-{index}", "protocol_label": label}
        for label in range(3)
        for index in range(100)
    ]
    test = [{"case_id": "test-0", "protocol_label": 0}]
    selected = runner.select_k_shot(support, k=32, classes=3, random_state=7)

    assert len(selected) == 96
    assert {label: sum(row["protocol_label"] == label for row in selected) for label in range(3)} == {
        0: 32,
        1: 32,
        2: 32,
    }
    assert not ({row["case_id"] for row in selected} & {row["case_id"] for row in test})


def test_k_shot_256_pool_is_separate_from_development_support():
    rows = [
        {"case_id": f"{label}-{index}", "protocol_label": label}
        for label in range(3)
        for index in range(700)
    ]
    development, test = runner.build_protocol_support_test(
        rows,
        classes=3,
        support_per_class=200,
        test_per_class=400,
        random_state=42,
    )
    non_test_rows = [
        row for row in rows if row["case_id"] not in {item["case_id"] for item in test}
    ]
    pool = runner.select_k_shot(non_test_rows, k=256, classes=3, random_state=298)

    assert len(development) == 600
    assert len(pool) == 768
    assert not ({row["case_id"] for row in pool} & {row["case_id"] for row in test})


def test_protocol_metrics_report_three_class_confusion_and_per_class_f1():
    metrics = runner.multiclass_metrics(
        np.asarray([0, 1, 2, 2]),
        np.asarray([0, 2, 2, 1]),
        class_names=["normal", "offensive", "hate"],
    )

    assert metrics["accuracy"] == 0.5
    assert len(metrics["per_class_f1"]) == 3
    assert metrics["confusion_matrix"] == [[1, 0, 0], [0, 0, 1], [0, 1, 1]]


def test_finalized_experiment_record_keeps_predictions_as_jsonl_artifact(tmp_path):
    record = {
        "metrics": {"class_names": ["normal", "hate"], "confusion_matrix": [[1, 0], [0, 1]]},
        "predictions": [{"case_id": "case-1", "gold_label": 1, "predicted_label": 1}],
    }

    finalized = runner._finalize_experiment_record(tmp_path, "trial", record)

    assert "predictions" not in finalized
    assert Path(finalized["predictions_path"]).exists()
    assert Path(finalized["confusion_matrix_path"]).exists()


def test_source_subset_remains_class_balanced_when_capped():
    rows = [
        {"case_id": f"{label}-{index}", "protocol_label": label}
        for label in range(3)
        for index in range(10)
    ]

    subset = runner._source_subset(rows, max_cases=9)

    assert len(subset) == 9
    assert Counter(row["protocol_label"] for row in subset) == {0: 3, 1: 3, 2: 3}


def test_protocol_learning_rates_keep_source_and_target_training_separate():
    args = type("Args", (), {"source_lr": 2e-5, "target_lr": 1e-4})()

    assert runner.protocol_learning_rate(args, phase="source") == 2e-5
    assert runner.protocol_learning_rate(args, phase="target") == 1e-4


def test_experiment_seed_replays_torch_batch_order():
    import torch

    runner.seed_experiment(1949)
    first = torch.randperm(16)
    runner.seed_experiment(1949)
    second = torch.randperm(16)

    assert torch.equal(first, second)


def test_amp_is_enabled_only_for_opted_in_cuda_training():
    assert runner.amp_enabled(type("Args", (), {"amp": True})(), device="cuda")
    assert not runner.amp_enabled(type("Args", (), {"amp": True})(), device="cpu")
    assert not runner.amp_enabled(type("Args", (), {"amp": False})(), device="cuda")


def test_existing_source_protocol_checkpoint_is_explicitly_reusable(tmp_path):
    checkpoint = tmp_path / "hatecot_source_protocol_checkpoint.pt"
    checkpoint.touch()

    resolved = runner.source_protocol_checkpoint_path(
        type("Args", (), {"source_protocol_checkpoint": str(checkpoint)})()
    )

    assert resolved == checkpoint


def test_target_checkpoint_writes_can_be_disabled_for_metric_only_runs():
    assert runner.save_target_checkpoints(
        type("Args", (), {"save_target_checkpoints": True})()
    )
    assert not runner.save_target_checkpoints(
        type("Args", (), {"save_target_checkpoints": False})()
    )


def test_target_adamw_avoids_foreach_peak_memory_temporaries():
    assert runner.target_adamw_kwargs() == {"foreach": False, "fused": True}


def test_runtime_memory_release_is_safe_without_a_loaded_model():
    assert runner.release_runtime_memory() is None


def test_checkpoint_loading_uses_memory_mapping_to_limit_windows_peak_memory():
    assert runner.checkpoint_load_kwargs() == {
        "map_location": "cpu",
        "weights_only": False,
        "mmap": True,
    }


def test_protocol_prediction_moves_reloaded_model_to_requested_device():
    import torch

    class Tokenizer:
        def __call__(self, texts, **_kwargs):
            return {
                "input_ids": torch.ones((len(texts), 2), dtype=torch.long),
                "attention_mask": torch.ones((len(texts), 2), dtype=torch.long),
            }

    class Model:
        def __init__(self):
            self.device = None

        def to(self, device):
            self.device = str(device)
            return self

        def eval(self):
            return self

        def __call__(self, input_ids, **_kwargs):
            assert self.device == str(input_ids.device)
            return {"protocol_logits": {"hatexplain_3way": torch.zeros((len(input_ids), 3), device=input_ids.device)}}

    logits = runner._predict_model(
        Model(),
        Tokenizer(),
        [{"text": "example"}],
        head="hatexplain_3way",
        args=type("Args", (), {"batch_size": 1, "max_length": 8})(),
        device="cpu",
    )

    assert logits.shape == (1, 3)
