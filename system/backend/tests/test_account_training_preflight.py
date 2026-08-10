from __future__ import annotations

import json
import hashlib

import pytest

from app.core import account_training_runtime
from app.utils.exceptions import AppException


def _encoder_config(tmp_path, **overrides):
    config = {
        "corpus_documents_path": str(tmp_path / "corpus.jsonl"),
        "model_name_or_path": str(tmp_path / "model"),
    }
    config.update(overrides)
    return config


def _write_detector_dataset(tmp_path):
    dataset_root = tmp_path / "dataset"
    dataset_root.mkdir()
    records = [
        {"account_id": "account-1", "text": "\u53ef\u8bad\u7ec3\u8bed\u6599", "training_target": "non_bot"},
        {"account_id": "account-2", "text": "\u53e6\u4e00\u6761\u8bad\u7ec3\u8bed\u6599", "training_target": "bot"},
    ]
    serialized = [json.dumps(record, ensure_ascii=False, sort_keys=True) for record in records]
    (dataset_root / "approved_account_labels.jsonl").write_text(
        "\n".join(serialized) + "\n", encoding="utf-8"
    )
    (dataset_root / "dataset_manifest.json").write_text(
        json.dumps(
            {
                "data_fingerprint": hashlib.sha256(("\n".join(serialized) + "\n").encode("utf-8")).hexdigest(),
                "record_count": 2,
                "class_counts": {"bot": 1, "non_bot": 1},
            }
        ),
        encoding="utf-8",
    )
    return dataset_root


def _detector_config(tmp_path, **overrides):
    dataset_root = _write_detector_dataset(tmp_path)
    dataset_manifest = json.loads((dataset_root / "dataset_manifest.json").read_text(encoding="utf-8"))
    encoder = tmp_path / "encoder"
    encoder.mkdir()
    payload = encoder / "payload"
    payload.write_bytes(b"encoder")
    config = {
        "strict_protocol": True,
        "dataset_name": "approved_account_corpus",
        "dataset_root": str(dataset_root),
        "input_fingerprint": dataset_manifest["data_fingerprint"],
        "encoder_version": "encoder-v1",
        "encoder_artifact_hash": "a" * 64,
        "text_model_path": str(encoder),
        "encoder_binding_payload_path": str(payload),
    }
    config.update(overrides)
    return config


def test_encoder_preflight_rejects_missing_corpus(tmp_path):
    with pytest.raises(AppException, match="corpus_documents_path.*not found"):
        account_training_runtime.preflight_account_training_artifact(
            family="chinese_social_encoder",
            config=_encoder_config(tmp_path),
        )


def test_encoder_preflight_rejects_empty_corpus(tmp_path):
    corpus = tmp_path / "corpus.jsonl"
    corpus.write_text('{"text": "   "}\n', encoding="utf-8")

    with pytest.raises(AppException, match="at least one trainable text"):
        account_training_runtime.preflight_account_training_artifact(
            family="chinese_social_encoder",
            config=_encoder_config(tmp_path),
        )


def test_encoder_preflight_rejects_incomplete_local_model(tmp_path):
    corpus = tmp_path / "corpus.jsonl"
    corpus.write_text('{"text": "\u53ef\u8bad\u7ec3\u8bed\u6599"}\n', encoding="utf-8")
    model_dir = tmp_path / "model"
    model_dir.mkdir()
    (model_dir / "config.json").write_text(
        json.dumps({"model_type": "bert", "architectures": ["BertForMaskedLM"]}),
        encoding="utf-8",
    )
    (model_dir / "tokenizer.json").write_text("{}", encoding="utf-8")

    with pytest.raises(AppException, match="model weights"):
        account_training_runtime.preflight_account_training_artifact(
            family="chinese_social_encoder",
            config=_encoder_config(tmp_path),
        )


def test_encoder_preflight_accepts_complete_local_model_without_creating_output(tmp_path):
    corpus = tmp_path / "corpus.jsonl"
    corpus.write_text('{"text": "\u53ef\u8bad\u7ec3\u8bed\u6599"}\n', encoding="utf-8")
    historical = tmp_path / "historical.jsonl"
    historical.write_text('{"content": "\u5386\u53f2\u8bed\u6599"}\n', encoding="utf-8")
    model_dir = tmp_path / "model"
    model_dir.mkdir()
    (model_dir / "config.json").write_text(
        json.dumps({"model_type": "bert", "architectures": ["BertForMaskedLM"]}),
        encoding="utf-8",
    )
    (model_dir / "tokenizer.json").write_text("{}", encoding="utf-8")
    (model_dir / "pytorch_model.bin").write_bytes(b"local-weight")

    result = account_training_runtime.preflight_account_training_artifact(
        family="chinese_social_encoder",
        config=_encoder_config(tmp_path, historical_documents_path=str(historical)),
    )

    assert result["family"] == "chinese_social_encoder"
    assert result["document_count"] == 1
    assert result["historical_document_count"] == 1
    assert not (tmp_path / "account_training").exists()


def test_encoder_preflight_rejects_refs_only_huggingface_cache(tmp_path):
    corpus = tmp_path / "corpus.jsonl"
    corpus.write_text('{"text": "\u53ef\u8bad\u7ec3\u8bed\u6599"}\n', encoding="utf-8")
    cache_dir = tmp_path / "models--hfl--chinese-roberta-wwm-ext"
    refs = cache_dir / "refs"
    refs.mkdir(parents=True)
    (refs / "main").write_text("snapshot-id", encoding="utf-8")

    with pytest.raises(AppException, match="local model config is unreadable"):
        account_training_runtime.preflight_account_training_artifact(
            family="chinese_social_encoder",
            config={"corpus_documents_path": str(corpus), "model_name_or_path": str(cache_dir)},
        )


def test_encoder_preflight_accepts_shared_shard_index_entries(tmp_path):
    corpus = tmp_path / "corpus.jsonl"
    corpus.write_text('{"text": "\u53ef\u8bad\u7ec3\u8bed\u6599"}\n', encoding="utf-8")
    model_dir = tmp_path / "sharded-model"
    model_dir.mkdir()
    (model_dir / "config.json").write_text(json.dumps({"model_type": "bert"}), encoding="utf-8")
    (model_dir / "tokenizer.json").write_text("{}", encoding="utf-8")
    (model_dir / "pytorch_model-00001-of-00001.bin").write_bytes(b"weight-shard")
    (model_dir / "pytorch_model.bin.index.json").write_text(
        json.dumps({"weight_map": {"encoder.layer.0": "pytorch_model-00001-of-00001.bin", "cls.bias": "pytorch_model-00001-of-00001.bin"}}),
        encoding="utf-8",
    )

    result = account_training_runtime.preflight_account_training_artifact(
        family="chinese_social_encoder",
        config={"corpus_documents_path": str(corpus), "model_name_or_path": str(model_dir)},
    )

    assert result["document_count"] == 1


def test_detector_preflight_ignores_caller_holdout_manifest_contents(tmp_path, monkeypatch):
    config = _detector_config(tmp_path, frozen_holdout_manifest_path=str(tmp_path / "holdout.json"))
    (tmp_path / "holdout.json").write_text(json.dumps(["not", "an", "object"]), encoding="utf-8")
    monkeypatch.setattr(
        account_training_runtime,
        "load_verified_chinese_social_encoder_artifact",
        lambda *_args, **_kwargs: {"artifact_hash": "a" * 64, "encoder_payload": {"path": "payload"}},
        raising=False,
    )

    result = account_training_runtime.preflight_account_training_artifact(
        family="chinese_account_detector",
        config=config,
    )
    assert result["family"] == "chinese_account_detector"


def test_detector_preflight_translates_encoder_verifier_errors(tmp_path, monkeypatch):
    monkeypatch.setattr(
        account_training_runtime,
        "load_verified_chinese_social_encoder_artifact",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(ValueError("bad manifest")),
    )

    with pytest.raises(AppException, match="artifact verification failed") as error:
        account_training_runtime.preflight_account_training_artifact(
            family="chinese_account_detector",
            config=_detector_config(tmp_path),
        )

    assert error.value.code == 409


def test_detector_preflight_rejects_empty_dataset_root(tmp_path, monkeypatch):
    config = _detector_config(tmp_path)
    (tmp_path / "dataset" / "approved_account_labels.jsonl").write_text("", encoding="utf-8")
    monkeypatch.setattr(
        account_training_runtime,
        "load_verified_chinese_social_encoder_artifact",
        lambda *_args, **_kwargs: {"artifact_hash": "a" * 64, "encoder_payload": {"path": "payload"}},
    )

    with pytest.raises(AppException, match="approved_account_labels.jsonl.*trainable record"):
        account_training_runtime.preflight_account_training_artifact(
            family="chinese_account_detector", config=config
        )


def test_detector_preflight_rejects_json_object_without_trainable_fields(tmp_path, monkeypatch):
    config = _detector_config(tmp_path)
    (tmp_path / "dataset" / "approved_account_labels.jsonl").write_text('{"arbitrary": "object"}\n', encoding="utf-8")
    monkeypatch.setattr(
        account_training_runtime,
        "load_verified_chinese_social_encoder_artifact",
        lambda *_args, **_kwargs: {"artifact_hash": "a" * 64, "encoder_payload": {"path": "payload"}},
    )

    with pytest.raises(AppException, match="invalid record"):
        account_training_runtime.preflight_account_training_artifact(
            family="chinese_account_detector", config=config
        )


def test_detector_preflight_rejects_any_malformed_nonempty_dataset_record(tmp_path, monkeypatch):
    config = _detector_config(tmp_path)
    labels = tmp_path / "dataset" / "approved_account_labels.jsonl"
    labels.write_text(
        labels.read_text(encoding="utf-8") + '{"account_id":"missing-required-fields"}\n',
        encoding="utf-8",
    )
    monkeypatch.setattr(
        account_training_runtime,
        "load_verified_chinese_social_encoder_artifact",
        lambda *_args, **_kwargs: {"artifact_hash": "a" * 64, "encoder_payload": {"path": "payload"}},
    )

    with pytest.raises(AppException, match="invalid record"):
        account_training_runtime.preflight_account_training_artifact(
            family="chinese_account_detector", config=config
        )


def test_detector_preflight_ignores_caller_holdout_configuration(tmp_path, monkeypatch):
    config = _detector_config(tmp_path, frozen_holdout_manifest_path=str(tmp_path / "missing.json"))
    monkeypatch.setattr(
        account_training_runtime,
        "load_verified_chinese_social_encoder_artifact",
        lambda *_args, **_kwargs: {"artifact_hash": "a" * 64, "encoder_payload": {"path": "payload"}},
    )

    result = account_training_runtime.preflight_account_training_artifact(
        family="chinese_account_detector", config=config
    )
    assert "frozen_holdout_manifest" not in result
