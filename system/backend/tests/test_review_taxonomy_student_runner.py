from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import numpy as np


RUNNER_PATH = Path(__file__).resolve().parents[1] / "scripts" / "run_review_taxonomy_student.py"
SPEC = importlib.util.spec_from_file_location("review_taxonomy_student_runner", RUNNER_PATH)
assert SPEC and SPEC.loader
runner = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(runner)


def test_axis_metrics_are_masked_binary_metrics():
    metrics = runner._axis_metrics(
        np.asarray([0, 1, 1], dtype="float32"),
        np.asarray([0.1, 0.8, 0.4], dtype="float32"),
    )

    assert metrics["status"] == "evaluated"
    assert metrics["support"] == 3
    assert "macro_f1" in metrics["metrics"]


def test_select_threshold_maximizes_validation_macro_f1():
    labels = np.asarray([0, 0, 1, 1], dtype="float32")
    probabilities = np.asarray([0.1, 0.2, 0.35, 0.4], dtype="float32")

    selected = runner.select_threshold_by_macro_f1(labels, probabilities)

    assert selected["threshold"] == 0.35
    assert selected["metrics"]["macro_f1"] == 1.0


def test_axis_metrics_can_apply_calibrated_threshold():
    labels = np.asarray([0, 0, 1, 1], dtype="float32")
    probabilities = np.asarray([0.1, 0.2, 0.35, 0.4], dtype="float32")

    metrics = runner._axis_metrics(labels, probabilities, threshold=0.35)

    assert metrics["threshold"] == 0.35
    assert metrics["metrics"]["macro_f1"] == 1.0


def test_runner_defaults_include_hatecot_for_lrkd_phase():
    assert "HateCoT" in runner.DEFAULT_DATASETS


def test_taxonomy_split_validation_uses_axis_labels_not_legacy_harmfulness():
    split_cases = {
        split: [
            {
                "case_id": f"{split}-pos",
                "dataset": "HateCoT",
                "split": split,
                "text": "attack text",
                "labels": {"label": "hate"},
                "explanation": "identity attack explanation",
            },
            {
                "case_id": f"{split}-neg",
                "dataset": "HateCoT",
                "split": split,
                "text": "normal text",
                "labels": {"label": "normal"},
                "explanation": "no attack explanation",
            },
        ]
        for split in ("train", "validation", "test")
    }

    assert runner.validate_taxonomy_splits(split_cases, "HateCoT") == ""


def test_hatecot_csv_loader_maps_explanations_and_binary_axis_labels(tmp_path):
    csv_path = tmp_path / "hatecot.csv"
    csv_path.write_text(
        "id,explanation,domain,label,post,target,uid\n"
        "1,benign reason,toxigen,Benign,hello,,u1\n"
        "2,hate reason,dynahate,Hate Speech,attack text,group,u2\n",
        encoding="utf-8",
    )

    cases = runner.load_hatecot_csv(csv_path)

    assert [case["case_id"] for case in cases] == ["u1", "u2"]
    assert cases[0]["labels"]["raw_label"] == "normal"
    assert cases[1]["labels"]["raw_label"] == "hate"
    assert cases[1]["explanation"] == "hate reason"


def test_weibo21_loader_maps_fake_real_to_deception_labels(tmp_path):
    root = tmp_path / "weibo21"
    root.mkdir()
    (root / "fake_release_all.json").write_text(
        json.dumps({"id": "f1", "content": "fake claim", "comments": "debunk", "label": 1, "category": "科技"}, ensure_ascii=False)
        + "\n",
        encoding="utf-8",
    )
    (root / "real_release_all.json").write_text(
        json.dumps({"id": "r1", "content": "real claim", "comments": "comment", "label": 0, "category": "科技"}, ensure_ascii=False)
        + "\n",
        encoding="utf-8",
    )

    cases = runner.load_weibo21_jsonl(root)

    assert [case["case_id"] for case in cases] == ["f1", "r1"]
    assert cases[0]["labels"]["raw_label"] == "fake"
    assert cases[1]["labels"]["raw_label"] == "real"
    assert cases[0]["claim_context"]["claim_text"] == "fake claim"


def test_lrkd_scope_status_names_effective_explanation_usage():
    assert runner.lrkd_scope_status(False, 20) == "disabled"
    assert runner.lrkd_scope_status(True, 0) == "enabled_but_no_dataset_explanations"
    assert runner.lrkd_scope_status(True, 20) == "dataset_explanation_vectors_used"


def test_joint_training_requires_xlmr_backend(tmp_path):
    args = SimpleNamespace(
        datasets=["HateCoT"],
        hatecot_csv=str(tmp_path / "missing.csv"),
        weibo21_dir=str(tmp_path / "missing-weibo21"),
        random_state=42,
        max_cases_per_split=2,
        encoder_backend="hash",
    )

    result = runner.evaluate_joint_training(case_dir=tmp_path, args=args)

    assert result["status"] == "skipped"


def test_summarize_axis_metrics_keeps_task_specific_rows():
    rows = runner.summarize_axis_metrics(
        {
            "PHEME": {
                "status": "evaluated",
                "test": {
                    "ideological_deception": {
                        "status": "evaluated",
                        "support": 2,
                        "positive_count": 1,
                        "metrics": {"accuracy": 0.5, "macro_f1": 0.333333},
                        "pr_auc": 0.75,
                        "ece": 0.1,
                    }
                },
            }
        }
    )

    assert rows == [
        {
            "dataset": "PHEME",
            "split": "test",
            "axis": "ideological_deception",
            "support": 2,
            "positive_count": 1,
            "accuracy": 0.5,
            "macro_f1": 0.333333,
            "pr_auc": 0.75,
            "ece": 0.1,
        }
    ]


def test_runner_reports_missing_weibo21_without_failing_other_datasets(tmp_path, monkeypatch):
    case_dir = tmp_path / "cases"
    case_dir.mkdir()
    rows = [
        {"case_id": "h1", "dataset": "HateXplain", "split": "train", "text": "a", "labels": {"harmfulness": "harmful"}},
        {"case_id": "h2", "dataset": "HateXplain", "split": "train", "text": "b", "labels": {"harmfulness": "non_harmful"}},
    ]
    (case_dir / "HateXplain.jsonl").write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "sys.argv",
        [
            "run_review_taxonomy_student.py",
            "--case-dir",
            str(case_dir),
            "--output-dir",
            str(tmp_path / "out"),
            "--datasets",
            "Weibo21",
            "--encoder-backend",
            "hash",
            "--weibo21-dir",
            str(tmp_path / "missing-weibo21"),
            "--epochs",
            "1",
        ],
    )

    assert runner.main() == 1
    report = json.loads((tmp_path / "out" / "report.json").read_text(encoding="utf-8"))
    assert report["datasets"]["Weibo21"]["status"] == "skipped"
