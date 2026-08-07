from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "compare_review_maro_systems.py"


def load_runner_module():
    spec = importlib.util.spec_from_file_location("compare_review_maro_systems", SCRIPT_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")


def test_comparison_cli_uses_population_manifest_and_writes_machine_readable_report(tmp_path, monkeypatch):
    runner = load_runner_module()
    case_dir = tmp_path / "cases"
    agent_dir = tmp_path / "agents" / "hatexplain"
    output_path = tmp_path / "comparison" / "report.json"
    case = {
        "case_id": "hx-1",
        "dataset": "HateXplain",
        "split": "test",
        "text": "fixture",
        "labels": {"harmfulness": "harmful"},
    }
    _write_jsonl(case_dir / "HateXplain.jsonl", [case])
    _write_jsonl(
        agent_dir / "agent_predictions.jsonl",
        [
            {
                "case_id": "hx-1",
                "dataset": "HateXplain",
                "split": "test",
                "teacher_silver": {
                    "distillation_eligible": True,
                    "main_axes": {
                        "attack_hate_offense": {"available": True, "label": "harmful", "confidence": 0.9}
                    }
                },
            }
        ],
    )
    student_path = tmp_path / "student.jsonl"
    _write_jsonl(
        student_path,
        [
            {
                "case_id": "hx-1",
                "dataset": "HateXplain",
                "split": "test",
                "student": {
                    "attack_hate_offense": 0.8,
                    "misinfo_claim_risk": 0.1,
                    "stance": {"label": "unlinked", "probability": 1.0},
                    "defer_probability": 0.1,
                    "abstain": False,
                },
            }
        ],
    )
    manifest_path = tmp_path / "manifest.jsonl"
    _write_jsonl(manifest_path, [{"case_id": "hx-1", "dataset": "HateXplain", "split": "test"}])
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "compare_review_maro_systems.py",
            "--case-dir",
            str(case_dir),
            "--multi-agent-path",
            str(tmp_path / "agents"),
            "--student-predictions",
            str(student_path),
            "--population-manifest",
            str(manifest_path),
            "--output",
            str(output_path),
        ],
    )

    assert runner.main() == 0
    report = json.loads(output_path.read_text(encoding="utf-8"))
    assert report["population"]["case_count"] == 1
    assert report["paired"]["case_count"] == 1
    assert report["systems"]["multi_agent"]["metrics"]["macro_f1"] == 0.5
    assert report["inputs"]["population_manifest"] == str(manifest_path)


def test_comparison_cli_rejects_non_test_protocol_population(tmp_path, monkeypatch):
    runner = load_runner_module()
    manifest_path = tmp_path / "manifest.jsonl"
    _write_jsonl(
        manifest_path,
        [
            {
                "case_id": "hx-1",
                "dataset": "HateXplain",
                "split": "train",
                "protocol_split": "train",
            }
        ],
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "compare_review_maro_systems.py",
            "--case-dir", str(tmp_path / "cases"),
            "--multi-agent-path", str(tmp_path / "agents"),
            "--student-predictions", str(tmp_path / "student.jsonl"),
            "--population-manifest", str(manifest_path),
            "--output", str(tmp_path / "report.json"),
        ],
    )

    with pytest.raises(SystemExit, match="protocol_split=test"):
        runner.main()
