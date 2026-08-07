from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "build_review_maro_case_manifest.py"


def load_runner_module():
    spec = importlib.util.spec_from_file_location("build_review_maro_case_manifest", SCRIPT_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")


def test_manifest_cli_builds_balanced_gold_free_population(tmp_path, monkeypatch):
    runner = load_runner_module()
    case_dir = tmp_path / "cases"
    rows = []
    eligible = []
    for index, label in enumerate(["harmful", "harmful", "non_harmful", "non_harmful"]):
        row = {
            "case_id": f"hx-{index}",
            "dataset": "HateXplain",
            "split": "test",
            "text": "fixture",
            "labels": {"harmfulness": label},
        }
        rows.append(row)
        eligible.append({"case_id": row["case_id"], "dataset": row["dataset"], "split": row["split"]})
    _write_jsonl(case_dir / "HateXplain.jsonl", rows)
    eligible_path = tmp_path / "student.jsonl"
    _write_jsonl(eligible_path, eligible)
    output_path = tmp_path / "manifest.jsonl"
    audit_path = tmp_path / "manifest.audit.json"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "build_review_maro_case_manifest.py",
            "--case-dir",
            str(case_dir),
            "--eligible-predictions",
            str(eligible_path),
            "--datasets",
            "HateXplain",
            "--max-per-dataset",
            "4",
            "--output",
            str(output_path),
            "--audit-output",
            str(audit_path),
        ],
    )

    assert runner.main() == 0
    manifest = [json.loads(line) for line in output_path.read_text(encoding="utf-8").splitlines()]
    audit = json.loads(audit_path.read_text(encoding="utf-8"))
    assert len(manifest) == 4
    assert all(set(row) == {"case_id", "dataset", "split"} for row in manifest)
    assert audit["datasets"]["HateXplain"]["selected_distribution"] == {
        "harmful": 2,
        "non_harmful": 2,
    }


def test_manifest_builder_rejects_non_test_population_for_horizontal_comparison(tmp_path, monkeypatch):
    runner = load_runner_module()
    case_dir = tmp_path / "cases"
    row = {
        "case_id": "hx-train-1",
        "dataset": "HateXplain",
        "split": "train",
        "text": "fixture",
        "labels": {"harmfulness": "harmful"},
    }
    _write_jsonl(case_dir / "HateXplain.jsonl", [row])
    eligible_path = tmp_path / "eligible.jsonl"
    _write_jsonl(eligible_path, [{"case_id": row["case_id"], "dataset": row["dataset"], "split": row["split"]}])
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "build_review_maro_case_manifest.py",
            "--case-dir", str(case_dir),
            "--eligible-predictions", str(eligible_path),
            "--datasets", "HateXplain",
            "--max-per-dataset", "1",
            "--output", str(tmp_path / "manifest.jsonl"),
            "--audit-output", str(tmp_path / "audit.json"),
        ],
    )

    with pytest.raises(SystemExit, match="test population"):
        runner.main()
