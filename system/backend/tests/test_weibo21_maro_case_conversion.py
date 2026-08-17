from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

from app.core.review.maro_comparison import DATASET_AXIS_MAPPING
from app.core.review.review_task_schema import MISINFO_AXIS


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "build_review_post_cases.py"
PROTOCOL_SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "build_review_maro_experiment_protocol.py"


def _load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _write_weibo21_source(path: Path, *, source_label: str) -> None:
    rows = [
        {
            "id": f"{source_label}-{index}",
            "content": f"{source_label} claim {index}",
            "comments": "later reply that must not reach the review input",
            "timestamp": str(index),
            "category": "科技",
            "piclists": ["https://example.invalid/image.jpg"],
        }
        for index in range(20)
    ]
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


def _read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def test_weibo21_converter_is_stratified_and_preserves_maro_dual_inputs(tmp_path):
    converter = _load_module(SCRIPT_PATH, "build_review_post_cases_weibo21_test")
    root = tmp_path / "dataset"
    source_root = root / "weibo21"
    source_root.mkdir(parents=True)
    _write_weibo21_source(source_root / "fake_release_all.json", source_label="fake")
    _write_weibo21_source(source_root / "real_release_all.json", source_label="real")

    output_path = tmp_path / "Weibo21.jsonl"
    manifest = converter.convert_weibo21(root, output_path, max_cases=0)
    cases = _read_jsonl(output_path)

    assert manifest["status"] == "converted"
    assert manifest["split_policy"] == converter.WEIBO21_SPLIT_VERSION
    assert manifest["split_counts"] == {"train": 28, "validation": 6, "test": 6}
    assert len(cases) == 40
    assert {case["labels"]["harmfulness"] for case in cases} == {"harmful", "non_harmful"}
    assert manifest["input_protocol"] == "weibo21_maro_post_and_comments_v1"
    assert all(case["metadata"]["comments_included_by_protocol"] is True for case in cases)
    assert all(case["metadata"]["comment_temporal_scope"] == "unknown" for case in cases)
    assert all(case["metadata"]["post_time_leakage_risk"] is True for case in cases)
    assert all(case["metadata"]["media_excluded_by_protocol"] is True for case in cases)
    assert all(case["text"] == case["maro_inputs"]["original_news"] for case in cases)
    assert all("later reply" not in case["text"] for case in cases)
    assert all("later reply" in case["maro_inputs"]["original_news_and_comment"] for case in cases)
    assert all(case["views"]["img"]["available"] is False for case in cases)
    assert all(case["claim_context"]["claim_text"] == case["text"] for case in cases)


def test_weibo21_post_only_protocol_does_not_emit_comment_input(tmp_path):
    converter = _load_module(SCRIPT_PATH, "build_review_post_cases_weibo21_post_only_test")
    root = tmp_path / "dataset"
    source_root = root / "weibo21"
    source_root.mkdir(parents=True)
    _write_weibo21_source(source_root / "fake_release_all.json", source_label="fake")
    _write_weibo21_source(source_root / "real_release_all.json", source_label="real")

    output_path = tmp_path / "Weibo21-post-only.jsonl"
    manifest = converter.convert_weibo21(root, output_path, max_cases=0, input_profile="post_only")
    cases = _read_jsonl(output_path)

    assert manifest["input_protocol"] == "weibo21_maro_post_only_v1"
    assert all(case["maro_inputs"]["comments"] == [] for case in cases)
    assert all(case["maro_inputs"]["comment_temporal_scope"] == "not_used" for case in cases)
    assert all(case["metadata"]["comments_excluded_by_protocol"] is True for case in cases)


def test_weibo21_protocol_has_disjoint_claim_axis_populations(tmp_path):
    protocol = _load_module(PROTOCOL_SCRIPT_PATH, "build_review_maro_protocol_weibo21_test")
    cases = []
    for split in ("train", "validation", "test"):
        for label in ("harmful", "non_harmful"):
            for index in range(14):
                cases.append(
                    {
                        "case_id": f"{split}-{label}-{index}",
                        "dataset": "Weibo21",
                        "split": split,
                        "text": "fixture claim",
                        "labels": {"harmfulness": label},
                        "claim_context": {"available": True, "claim_text": "fixture claim"},
                    }
                )

    manifests, audit = protocol.build_experiment_protocol(
        {"Weibo21": cases},
        datasets=["Weibo21"],
        test_per_dataset=8,
        teacher_per_dataset=8,
        validation_tasks_per_axis=8,
        random_state=42,
    )

    assert DATASET_AXIS_MAPPING["Weibo21"] == MISINFO_AXIS
    assert len(manifests["test"]) == 8
    assert len(manifests["teacher"]) == 8
    assert len(manifests["rule_validation"]) == 8
    identities = [{row["case_id"] for row in rows} for rows in manifests.values()]
    assert identities[0].isdisjoint(identities[1])
    assert identities[0].isdisjoint(identities[2])
    assert identities[1].isdisjoint(identities[2])
    assert audit["populations"]["rule_validation"]["axis_counts"] == {MISINFO_AXIS: 8}
