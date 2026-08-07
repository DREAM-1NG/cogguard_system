from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from app.core.review.selective_student import SelectiveStudentEncoder, predict_selective_student_outputs


RUNNER_PATH = Path(__file__).resolve().parents[1] / "scripts" / "run_review_trainable_post.py"
SPEC = importlib.util.spec_from_file_location("review_trainable_post_runner", RUNNER_PATH)
assert SPEC and SPEC.loader
runner = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(runner)


@pytest.mark.skipif(importlib.util.find_spec("torch") is None, reason="torch not installed")
def test_student_checkpoint_reloads_with_matching_predictions(tmp_path):
    features = np.asarray([[0.2, 0.4, 0.1, 0.8], [0.8, 0.1, 0.7, 0.3]], dtype="float32")
    model = SelectiveStudentEncoder(input_dim=4, hidden_dim=3, stance_count=4)
    expected_outputs = predict_selective_student_outputs(model, features, device="cpu")
    checkpoint_path = tmp_path / "student_checkpoint.pt"

    runner.save_student_checkpoint(
        checkpoint_path,
        model,
        model_config={"input_dim": 4, "hidden_dim": 3, "stance_count": 4},
        metadata={"dataset": "unit"},
    )

    restored_model, metadata = runner.reload_student_checkpoint(checkpoint_path)
    restored_outputs = predict_selective_student_outputs(restored_model, features, device="cpu")

    assert metadata["dataset"] == "unit"
    for axis, expected in expected_outputs.items():
        np.testing.assert_allclose(restored_outputs[axis], expected, rtol=1e-6, atol=1e-6)


def test_strict_full_run_preflight_requires_uncapped_requested_cases(tmp_path):
    args = SimpleNamespace(
        max_cases_per_split=80,
        datasets=list(runner.DEFAULT_DATASETS),
        epochs=1,
        batch_size=2,
        hidden_dim=4,
        student_encoder_backend="hash",
        allow_model_download=False,
        student_backbone="xlm-r-base",
        hf_cache_dir=str(tmp_path),
        random_state=42,
    )

    errors = runner.strict_full_run_preflight(args, tmp_path / "cases", tmp_path / "output")

    assert "--strict-full-run requires --max-cases-per-split 0" in errors


def test_frozen_encoder_provenance_records_local_snapshot_fingerprints(tmp_path):
    snapshot = tmp_path / "models--FacebookAI--xlm-roberta-base" / "snapshots" / "complete"
    snapshot.mkdir(parents=True)
    (snapshot / "config.json").write_text('{"model_type":"xlm-roberta"}', encoding="utf-8")
    (snapshot / "model.safetensors").write_bytes(b"model-weights")
    (snapshot / "tokenizer.json").write_text('{"version":"1.0"}', encoding="utf-8")

    provenance = runner.build_frozen_encoder_provenance(
        "FacebookAI/xlm-roberta-base",
        tmp_path,
        pooling="cls",
    )

    assert provenance["encoder_frozen"] is True
    assert provenance["pooling"] == "cls"
    assert provenance["resolved_local_snapshot_path"] == str(snapshot)
    assert provenance["snapshot_files"]["config"]["sha256"] == runner.sha256_file(snapshot / "config.json")
    assert provenance["snapshot_files"]["model"]["sha256"] == runner.sha256_file(snapshot / "model.safetensors")
    assert provenance["snapshot_files"]["tokenizer"]["sha256"] == runner.sha256_file(snapshot / "tokenizer.json")
    assert "requires this frozen encoder" in provenance["checkpoint_reload_requirement"]


def test_requested_dataset_skip_returns_nonzero(tmp_path, monkeypatch):
    output_dir = tmp_path / "output"
    monkeypatch.setattr(
        "sys.argv",
        [
            "run_review_trainable_post.py",
            "--case-dir",
            str(tmp_path / "missing-cases"),
            "--output-dir",
            str(output_dir),
            "--datasets",
            "HateXplain",
            "--student-encoder-backend",
            "hash",
        ],
    )

    assert runner.main() == 1
    report = json.loads((output_dir / "report.json").read_text(encoding="utf-8"))
    assert report["started_at"].endswith("+00:00")
    assert report["completed_at"].endswith("+00:00")
    assert report["duration_seconds"] >= 0
    assert report["run_parameters"]["student_encoder_backend"] == "hash"


def test_teacher_silver_manifest_accepts_only_training_population(tmp_path):
    train_case = {
        "case_id": "train-1",
        "dataset": "HateXplain",
        "split": "train",
        "protocol_split": "train",
    }
    test_case = {
        "case_id": "test-1",
        "dataset": "HateXplain",
        "split": "test",
        "protocol_split": "test",
    }
    manifest_path = tmp_path / "teacher_manifest.jsonl"
    manifest_path.write_text(
        "".join(json.dumps(row) + "\n" for row in [train_case, test_case]),
        encoding="utf-8",
    )

    manifest = runner.load_population_manifest(manifest_path)

    with pytest.raises(ValueError, match="protocol_split=train"):
        runner.validate_teacher_silver_population(
            "HateXplain",
            [train_case],
            manifest,
        )


def test_evaluation_manifest_accepts_only_test_protocol_population(tmp_path):
    manifest_path = tmp_path / "evaluation_manifest.jsonl"
    manifest_path.write_text(
        json.dumps(
            {
                "case_id": "test-1",
                "dataset": "HateXplain",
                "split": "test",
                "protocol_split": "train",
            }
        ) + "\n",
        encoding="utf-8",
    )

    manifest = runner.load_population_manifest(manifest_path)

    with pytest.raises(ValueError, match="protocol_split=test"):
        runner.select_evaluation_population(
            "HateXplain",
            [{"case_id": "test-1", "split": "test"}],
            manifest,
        )


def test_protocol_manifests_survive_smoke_split_caps():
    split_cases = {
        "train": [
            {"case_id": f"train-{index}", "labels": {"harmfulness": "harmful" if index % 2 else "non_harmful"}}
            for index in range(6)
        ],
        "validation": [
            {"case_id": f"validation-{index}", "labels": {"harmfulness": "harmful" if index % 2 else "non_harmful"}}
            for index in range(6)
        ],
        "test": [
            {"case_id": f"test-{index}", "labels": {"harmfulness": "harmful" if index % 2 else "non_harmful"}}
            for index in range(6)
        ],
    }

    capped = runner.cap_student_splits(
        split_cases,
        2,
        required_train_case_ids={"train-5"},
        preserve_test=True,
    )

    assert len(capped["validation"]) == 2
    assert len(capped["test"]) == 6
    assert "train-5" in {case["case_id"] for case in capped["train"]}
