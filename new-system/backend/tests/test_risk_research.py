"""阶段1：研究复现数据集与评估基线测试。"""

from __future__ import annotations

import json

from app.core.risk.research import (
    RiskTask,
    evaluate_classification,
    format_metrics_summary,
    load_dataset_file,
    summarize_samples,
)


def test_load_cold_jsonl_to_unified_schema(tmp_path):
    path = tmp_path / "cold_train.jsonl"
    path.write_text(
        "\n".join(
            [
                json.dumps({"id": "1", "text": "toxic sample", "label": "harmful", "split": "train"}, ensure_ascii=False),
                json.dumps({"id": "2", "text": "safe sample", "label": "safe", "split": "train"}, ensure_ascii=False),
            ]
        ),
        encoding="utf-8",
    )

    samples = load_dataset_file(path, "cold")
    assert len(samples) == 2
    assert all(sample.task == RiskTask.HARMFUL for sample in samples)
    assert samples[0].label == "harmful"
    assert samples[1].label == "safe"


def test_load_nlpcc_tsv_to_unified_schema(tmp_path):
    path = tmp_path / "nlpcc2016_dev.tsv"
    path.write_text(
        "id\ttarget\ttext\tlabel\tsplit\n"
        "1\t热点事件A\t我支持这个说法\tfavor\tdev\n"
        "2\t热点事件A\t这是真的吗\tquery\tdev\n",
        encoding="utf-8",
    )

    samples = load_dataset_file(path, "nlpcc2016")
    assert len(samples) == 2
    assert all(sample.task == RiskTask.STANCE for sample in samples)
    assert samples[0].target == "热点事件A"
    assert samples[0].label == "support"
    assert samples[1].label == "query"


def test_load_cstance_json_to_unified_schema(tmp_path):
    path = tmp_path / "cstance_test.json"
    path.write_text(
        json.dumps(
            {
                "records": [
                    {"sample_id": "a", "claim": "热点事件A", "content": "我反对这个说法", "stance": "against", "split": "test"},
                    {"sample_id": "b", "claim": "热点事件A", "content": "先观望", "stance": "neutral", "split": "test"},
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    samples = load_dataset_file(path, "cstance")
    assert len(samples) == 2
    assert samples[0].label == "deny"
    assert samples[1].label == "comment"


def test_summarize_samples_counts_labels_and_targets(tmp_path):
    path = tmp_path / "cold_train.jsonl"
    path.write_text(
        json.dumps({"id": "1", "text": "sample", "label": "harmful", "split": "train"}, ensure_ascii=False),
        encoding="utf-8",
    )

    samples = load_dataset_file(path, "cold")
    summary = summarize_samples(samples)
    assert summary["count"] == 1
    assert summary["labels"] == {"harmful": 1}
    assert summary["splits"] == {"train": 1}


def test_evaluate_classification_outputs_macro_f1_and_confusion():
    metrics = evaluate_classification(
        ["support", "support", "deny", "comment"],
        ["support", "query", "deny", "comment"],
    )
    assert metrics["accuracy"] == 0.75
    assert metrics["macro_f1"] == 0.6667
    assert metrics["confusion_matrix"]["support"]["query"] == 1
    assert "labels=[comment, deny, query, support]" in format_metrics_summary(metrics)
