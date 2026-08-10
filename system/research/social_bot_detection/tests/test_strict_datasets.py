from pathlib import Path
import hashlib
import json

import pytest

from research.social_bot_detection import strict_datasets


@pytest.mark.parametrize(
    ("dataset_name", "loader_name"),
    [
        ("cresci-2015", "load_strict_cresci_2015_corpus"),
        ("cresci_2017", "load_strict_cresci_2017_corpus"),
        ("midterm-2018", "load_strict_midterm_2018_corpus"),
    ],
)
def test_strict_social_loader_dispatches_supported_dataset_names(monkeypatch, tmp_path, dataset_name, loader_name):
    sentinel = object()
    calls: list[tuple[Path, int]] = []

    def fake_loader(root, *, max_posts_per_account):
        calls.append((Path(root), max_posts_per_account))
        return sentinel

    monkeypatch.setattr(strict_datasets, loader_name, fake_loader)

    result = strict_datasets.load_strict_social_corpus(dataset_name, tmp_path, max_posts_per_account=7)

    assert result is sentinel
    assert calls == [(tmp_path, 7)]


def test_strict_social_loader_rejects_unknown_dataset(tmp_path):
    with pytest.raises(ValueError, match="unsupported strict social-bot dataset"):
        strict_datasets.load_strict_social_corpus("unknown", tmp_path)


def test_strict_loader_adapts_approved_corpus_without_graph_or_handcrafted_features(tmp_path):
    records = [
        {
            "account_id": "weibo\u001fhuman",
            "source_account_id": "human",
            "platform": "weibo",
            "event_id": "event-1",
            "observed_at": "2026-05-21T12:30:00+08:00",
            "community_id": "community-1",
            "text": "\u4eba\u7c7b\u8d26\u53f7\u6587\u672c",
            "training_target": "non_bot",
        },
        {
            "account_id": "douyin\u001fbot",
            "source_account_id": "bot",
            "platform": "douyin",
            "event_id": "event-1",
            "text": "\u673a\u5668\u4eba\u8d26\u53f7\u6587\u672c",
            "training_target": "bot",
        },
    ]
    lines = [json.dumps(record, ensure_ascii=False, sort_keys=True) for record in records]
    (tmp_path / "approved_account_labels.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (tmp_path / "dataset_manifest.json").write_text(
        json.dumps(
            {
                "data_fingerprint": hashlib.sha256(("\n".join(lines) + "\n").encode("utf-8")).hexdigest(),
                "record_count": 2,
                "class_counts": {"bot": 1, "non_bot": 1},
            }
        ),
        encoding="utf-8",
    )

    corpus = strict_datasets.load_strict_social_corpus("approved_account_corpus", tmp_path)

    assert {record.label for record in corpus.records} == {0, 1}
    assert corpus.graph.available is False
    assert all(not record.numeric_features and not record.categorical_features for record in corpus.records)
    assert corpus.manifest.data_fingerprint == hashlib.sha256(("\n".join(lines) + "\n").encode("utf-8")).hexdigest()
    by_id = {record.account_id: record for record in corpus.records}
    assert by_id["weibo\x1fhuman"].metadata["source_account_id"] == "human"
    assert by_id["weibo\x1fhuman"].metadata["observed_at"] == "2026-05-21T12:30:00+08:00"
    assert by_id["weibo\x1fhuman"].metadata["community_id"] == "community-1"
    assert "observed_at" not in by_id["douyin\x1fbot"].metadata
    assert "community_id" not in by_id["douyin\x1fbot"].metadata


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("data_fingerprint", "0" * 64),
        ("record_count", 3),
        ("class_counts", {"bot": 2}),
    ],
)
def test_approved_corpus_loader_rejects_tampered_manifest(tmp_path, field, value):
    records = [
        {"account_id": "weibo\u001fhuman", "text": "human", "training_target": "non_bot"},
        {"account_id": "weibo\u001fbot", "text": "bot", "training_target": "bot"},
    ]
    lines = [json.dumps(record, ensure_ascii=False, sort_keys=True) for record in records]
    payload = "\n".join(lines) + "\n"
    (tmp_path / "approved_account_labels.jsonl").write_text(payload, encoding="utf-8")
    manifest = {
        "data_fingerprint": hashlib.sha256(payload.encode("utf-8")).hexdigest(),
        "record_count": 2,
        "class_counts": {"bot": 1, "non_bot": 1},
    }
    manifest[field] = value
    (tmp_path / "dataset_manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(ValueError, match=field):
        strict_datasets.load_strict_approved_account_corpus(tmp_path)


def test_dataset_categorical_features_never_include_source_or_dataset_labels():
    features = strict_datasets._categorical_features(
        {"verified": True, "lang": "en"},
        "social_spambots_1",
    )

    assert features["verified"] == "true"
    assert "source_label" not in features
    assert all("label" not in name for name in features)
