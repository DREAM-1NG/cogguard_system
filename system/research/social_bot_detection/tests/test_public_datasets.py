import io
import json
import tarfile
import zipfile

from research.social_bot_detection.datasets import (
    load_approved_account_corpus,
    load_cresci_2015_dataset,
    load_cresci_2017_dataset,
    load_midterm_2018_dataset,
)


def _zip_bytes(files: dict[str, str]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, content in files.items():
            archive.writestr(name, content)
    return buffer.getvalue()


def _tar_archive(path, files: dict[str, bytes]) -> None:
    with tarfile.open(path, "w:gz") as archive:
        for name, payload in files.items():
            info = tarfile.TarInfo(name)
            info.size = len(payload)
            archive.addfile(info, io.BytesIO(payload))


def test_cresci_2015_adapter_uses_official_subcorpus_labels(tmp_path):
    users = '"id","name","screen_name","description"\n"1","A","a","human profile"\n'
    tweets = '"user_id","text"\n"1","a post"\n'
    nested = _zip_bytes({"users.csv": users, "tweets.csv": tweets})
    archive = tmp_path / "cresci-2015.csv.tar.gz"
    _tar_archive(archive, {"E13.csv.zip": nested, "INT.csv.zip": nested})

    samples, manifest = load_cresci_2015_dataset(archive)

    assert [sample.label for sample in samples] == [0, 1]
    assert {sample.source_label for sample in samples} == {"E13", "INT"}
    assert manifest.dataset_name == "cresci_2015"
    assert "E13" in manifest.label_provenance


def test_cresci_2017_adapter_preserves_subcorpus_label(tmp_path):
    users = '"id","name","screen_name","description"\n"1","A","a","profile"\n'
    tweets = '"user_id","text"\n"1","post"\n'
    outer = tmp_path / "cresci-2017.csv.zip"
    with zipfile.ZipFile(outer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(
            "datasets_full.csv/genuine_accounts.csv.zip",
            _zip_bytes({"genuine_accounts.csv/users.csv": users, "genuine_accounts.csv/tweets.csv": tweets}),
        )
        archive.writestr(
            "datasets_full.csv/social_spambots_1.csv.zip",
            _zip_bytes({"social_spambots_1.csv/users.csv": users, "social_spambots_1.csv/tweets.csv": tweets}),
        )

    samples, manifest = load_cresci_2017_dataset(outer)

    assert {sample.label for sample in samples} == {0, 1}
    assert {sample.source_label for sample in samples} == {"genuine_accounts", "social_spambots_1"}
    assert manifest.class_counts == {"0": 1, "1": 1}


def test_midterm_2018_adapter_uses_tsv_labels_and_profile_text(tmp_path):
    payload = json.dumps(
        [
            {"user_id": 1, "screen_name": "bot_user", "name": "Bot", "description": "bot profile"},
            {"user_id": 2, "screen_name": "human_user", "name": "Human", "description": "human profile"},
        ]
    ).encode("utf-8")
    archive = tmp_path / "midterm-2018.tar.gz"
    _tar_archive(archive, {"midterm-2018.tsv": b"1\tbot\n2\thuman\n", "midterm-2018_processed_user_objects.json": payload})

    samples, manifest = load_midterm_2018_dataset(archive)

    assert {sample.label for sample in samples} == {0, 1}
    assert manifest.class_counts == {"0": 1, "1": 1}
    assert all(sample.post_count == 0 for sample in samples)


def test_approved_account_corpus_loader_excludes_abstain_from_binary_training(tmp_path):
    rows = [
        {
            "case_id": "case-1",
            "account_id": "u1",
            "platform": "weibo",
            "event_id": "event-1",
            "text": "可观察自动化行为文本",
            "behavior_label": "bot",
            "training_target": "bot",
            "evidence_post_ids": ["p1"],
            "case_fingerprint": "f1",
            "label_id": "label-1",
        },
        {
            "case_id": "case-2",
            "account_id": "u2",
            "platform": "weibo",
            "event_id": "event-1",
            "text": "普通账号公开发言",
            "behavior_label": "human",
            "training_target": "non_bot",
            "evidence_post_ids": ["p2"],
            "case_fingerprint": "f2",
            "label_id": "label-2",
        },
        {
            "case_id": "case-3",
            "account_id": "u3",
            "platform": "weibo",
            "event_id": "event-1",
            "text": "证据不足",
            "behavior_label": "insufficient_evidence",
            "training_target": "abstain",
            "evidence_post_ids": ["p3"],
            "case_fingerprint": "f3",
            "label_id": "label-3",
        },
    ]
    corpus = tmp_path / "approved_account_labels.jsonl"
    corpus.write_text(
        "\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n",
        encoding="utf-8",
    )

    samples, manifest = load_approved_account_corpus(tmp_path)

    assert [sample.label for sample in samples] == [1, 0]
    assert manifest.dataset_name == "approved_account_corpus"
    assert manifest.labeled_account_count == 3
    assert manifest.usable_account_count == 2
    assert manifest.skipped_empty_text_count == 1
    assert "abstain rows excluded" in manifest.label_provenance
