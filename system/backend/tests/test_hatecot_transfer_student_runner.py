from __future__ import annotations

import importlib.util
import json
from pathlib import Path


RUNNER_PATH = Path(__file__).resolve().parents[1] / "scripts" / "run_hatecot_transfer_student.py"
SPEC = importlib.util.spec_from_file_location("hatecot_transfer_student_runner", RUNNER_PATH)
assert SPEC and SPEC.loader
runner = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(runner)


def test_hatecheck_csv_loader_maps_labels(tmp_path):
    path = tmp_path / "hatecheck.csv"
    path.write_text(
        "case_id,test_case,label_gold,functionality\n"
        "hc1,\"I hate women\",hateful,F1\n"
        "hc2,\"I like women\",non-hateful,F2\n",
        encoding="utf-8",
    )

    rows = runner.load_hatecheck_csv(path)

    assert [row["case_id"] for row in rows] == ["hc1", "hc2"]
    assert [row["binary_label"] for row in rows] == [1, 0]
    assert rows[0]["dataset"] == "HateCheck"
    assert rows[0]["labels"]["raw_label"] == "hate"


def test_hatexplain_loader_uses_official_split_and_majority_label(tmp_path):
    root = tmp_path / "HateXplain" / "Data"
    root.mkdir(parents=True)
    (root / "post_id_divisions.json").write_text(
        json.dumps({"train": ["p1"], "val": ["p2"], "test": ["p3"]}),
        encoding="utf-8",
    )
    (root / "dataset.json").write_text(
        json.dumps(
            {
                "p1": {"post_tokens": ["normal"], "annotators": [{"label": "normal"}]},
                "p2": {"post_tokens": ["bad"], "annotators": [{"label": "offensive"}]},
                "p3": {"post_tokens": ["hate"], "annotators": [{"label": "hatespeech"}]},
            }
        ),
        encoding="utf-8",
    )

    rows = runner.load_hatexplain_official(root.parent)

    assert [(row["case_id"], row["split"], row["binary_label"]) for row in rows] == [
        ("p1", "train", 0),
        ("p2", "validation", 1),
        ("p3", "test", 1),
    ]


def test_hatexplain_transfer_loader_can_select_official_test_split(tmp_path):
    root = tmp_path / "HateXplain" / "Data"
    root.mkdir(parents=True)
    (root / "post_id_divisions.json").write_text(
        json.dumps({"train": ["p1"], "test": ["p2"]}),
        encoding="utf-8",
    )
    (root / "dataset.json").write_text(
        json.dumps(
            {
                "p1": {"post_tokens": ["train"], "annotators": [{"label": "normal"}]},
                "p2": {"post_tokens": ["test"], "annotators": [{"label": "offensive"}]},
            }
        ),
        encoding="utf-8",
    )

    rows = runner.load_hatexplain_official(root.parent, split="test")

    assert [(row["case_id"], row["split"]) for row in rows] == [("p2", "test")]


def test_implicit_hate_csv_loader_supports_coarse_and_implicit_splits(tmp_path):
    path = tmp_path / "implicit_hate.csv"
    path.write_text(
        "post,label,implicit_class\n"
        "\"plain text\",not_hate,\n"
        "\"coded text\",implicit_hate,incitement\n"
        "\"direct text\",explicit_hate,\n",
        encoding="utf-8",
    )

    latent_rows = runner.load_implicit_hate_csv(path, dataset_name="Latent_Hate", implicit_only=False)
    implicit_rows = runner.load_implicit_hate_csv(path, dataset_name="Implicit_Hate", implicit_only=True)

    assert [row["binary_label"] for row in latent_rows] == [0, 1, 1]
    assert [row["binary_label"] for row in implicit_rows] == [1]
    assert implicit_rows[0]["metadata"]["implicit_class"] == "incitement"
