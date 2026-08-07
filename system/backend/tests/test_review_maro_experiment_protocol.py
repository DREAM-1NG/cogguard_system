from __future__ import annotations

import importlib.util
import json
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "build_review_maro_experiment_protocol.py"


def load_runner_module():
    spec = importlib.util.spec_from_file_location("build_review_maro_experiment_protocol", SCRIPT_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _case(case_id: str, dataset: str, split: str, label: str) -> dict:
    return {
        "case_id": case_id,
        "dataset": dataset,
        "split": split,
        "text": case_id,
        "labels": {"harmfulness": label},
    }


def test_protocol_builds_disjoint_gold_free_populations(monkeypatch):
    runner = load_runner_module()
    cases_by_dataset = {}
    for dataset in runner.DEFAULT_DATASETS:
        rows = []
        for protocol_split in ("train", "validation", "test"):
            for index in range(8):
                label = "harmful" if index % 2 == 0 else "non_harmful"
                rows.append(_case(f"{dataset}-{protocol_split}-{index}", dataset, protocol_split, label))
        cases_by_dataset[dataset] = rows

    monkeypatch.setattr(
        runner,
        "build_splits",
        lambda dataset, cases, random_state: (
            {
                split: [case for case in cases if case["split"] == split]
                for split in ("train", "validation", "test")
            },
            "fixture",
        ),
    )

    manifests, audit = runner.build_experiment_protocol(
        cases_by_dataset,
        test_per_dataset=4,
        teacher_per_dataset=4,
        validation_tasks_per_axis=6,
        random_state=42,
    )

    assert len(manifests["test"]) == 20
    assert len(manifests["teacher"]) == 20
    assert len(manifests["rule_validation"]) == 12
    all_ids = [{row["case_id"] for row in manifests[name]} for name in manifests]
    assert all_ids[0].isdisjoint(all_ids[1])
    assert all_ids[0].isdisjoint(all_ids[2])
    assert all_ids[1].isdisjoint(all_ids[2])
    assert all(
        set(row) == {"case_id", "dataset", "split", "protocol_split"}
        for rows in manifests.values()
        for row in rows
    )
    assert {row["protocol_split"] for row in manifests["test"]} == {"test"}
    assert {row["protocol_split"] for row in manifests["teacher"]} == {"train"}
    assert {row["protocol_split"] for row in manifests["rule_validation"]} == {"validation"}
    assert audit["integrity"]["pairwise_overlap_count"] == 0
    assert audit["populations"]["test"]["selected_count"] == 20
    assert audit["populations"]["teacher"]["selected_count"] == 20
    assert audit["populations"]["rule_validation"]["axis_counts"] == {
        "attack_hate_offense": 6,
        "misinfo_claim_risk": 6,
    }


def test_write_protocol_records_fixed_research_scale(tmp_path, monkeypatch):
    runner = load_runner_module()
    case_dir = tmp_path / "cases"
    case_dir.mkdir()
    for dataset in runner.DEFAULT_DATASETS:
        rows = [
            _case(f"{dataset}-{split}-{index}", dataset, split, "harmful" if index % 2 == 0 else "non_harmful")
            for split in ("train", "validation", "test")
            for index in range(4)
        ]
        (case_dir / f"{dataset}.jsonl").write_text(
            "".join(json.dumps(row) + "\n" for row in rows),
            encoding="utf-8",
        )
    monkeypatch.setattr(
        runner,
        "build_splits",
        lambda dataset, cases, random_state: (
            {
                split: [case for case in cases if case["split"] == split]
                for split in ("train", "validation", "test")
            },
            "fixture",
        ),
    )

    output_dir = tmp_path / "protocol"
    audit = runner.write_experiment_protocol(
        case_dir=case_dir,
        output_dir=output_dir,
        datasets=runner.DEFAULT_DATASETS,
        test_per_dataset=2,
        teacher_per_dataset=2,
        validation_tasks_per_axis=2,
        random_state=42,
    )

    assert (output_dir / "test_manifest.jsonl").is_file()
    assert (output_dir / "teacher_silver_manifest.jsonl").is_file()
    assert (output_dir / "rule_validation_manifest.jsonl").is_file()
    assert audit["schema"] == "review-maro-experiment-protocol-v1"
    assert audit["requested_scale"] == {
        "test_per_dataset": 2,
        "teacher_per_dataset": 2,
        "validation_tasks_per_axis": 2,
    }
