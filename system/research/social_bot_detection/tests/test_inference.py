from __future__ import annotations

import json
import shutil

import pytest
import torch
from transformers import BertConfig, BertForMaskedLM, BertModel, BertTokenizer

from research.social_bot_detection.dapt import DAPTConfig, build_versioned_dapt_corpus, train_dapt
from research.social_bot_detection.inference import StrictBotRHGInference, create_botrhg_inference
from research.social_bot_detection.model_bundle import write_account_model_bundle
from research.social_bot_detection.strict_model import StrictBotRHGModel


def test_account_v3_checkpoint_reconstructs_strict_runtime_and_selection_payload(tmp_path):
    model_dir = tmp_path / "tiny-chinese-roberta"
    model_dir.mkdir()
    vocab_path = model_dir / "vocab.txt"
    vocab_path.write_text(
        "\n".join(("[PAD]", "[UNK]", "[CLS]", "[SEP]", "[MASK]", "测", "试", "账", "号")),
        encoding="utf-8",
    )
    tokenizer = BertTokenizer(str(vocab_path), do_lower_case=False)
    tokenizer.save_pretrained(model_dir)
    bert = BertModel(
        BertConfig(
            vocab_size=9,
            hidden_size=8,
            num_hidden_layers=1,
            num_attention_heads=2,
            intermediate_size=16,
        )
    )
    bert.save_pretrained(model_dir)

    model = StrictBotRHGModel(
        text_dim=8,
        property_dim=2,
        graph_dim=8,
        hidden_dim=8,
        projection_dim=4,
        dropout=0.0,
        num_relations=0,
    )
    checkpoint = tmp_path / "checkpoint.pt"
    torch.save(
        {
            "schema": "cogguard.botrhg.account.v3",
            "text_model_path": str(model_dir),
            "text_hidden_size": 8,
            "feature_schema": {
                "numeric_fields": ["post_count", "avg_tweet_length"],
                "categorical_fields": [],
                "categorical_vocab": {},
            },
            "numeric_stats": {
                "post_count": {"mean": 1.0, "std": 1.0},
                "avg_tweet_length": {"mean": 4.0, "std": 1.0},
            },
            "base_config": {"hidden_dim": 8, "dropout": 0.0},
            "correction_config": {"projection_dim": 4, "dropout": 0.0},
            "graph_relation_types": [],
            "property_state_dict": model.property_encoder.state_dict(),
            "graph_state_dict": model.graph_encoder.state_dict(),
            "support_projection_state_dict": model.support_projection.state_dict(),
            "base_state_dict": model.base_detector.state_dict(),
            "correction_state_dict": model.correction.state_dict(),
            "text_encoder_state_dict": bert.state_dict(),
            "training_config": {
                "model": {"max_length": 16, "batch_size": 2, "max_chunks_per_account": 2}
            },
            "routing_budget": 1.0,
            "support_k": 1,
            "calibration": {"method": "identity", "passed": True},
            "data_fingerprint": "d" * 64,
        },
        checkpoint,
    )

    runtime = create_botrhg_inference(checkpoint)
    assert isinstance(runtime, StrictBotRHGInference)
    result = runtime.predict(
        [
            {"author_id": "account-a", "content": "测试账号"},
            {"author_id": "account-b", "content": "另一个账号"},
        ]
    )

    assert result["runtime_mode"] == "strict_trained_checkpoint"
    assert len(result["accounts"]) == 2
    account = result["accounts"][0]
    assert 0.0 <= account["calibrated_probability"] <= 1.0
    assert len(account["representation"]) == 8
    assert len(account["badge_embedding"]) == 18
    assert "support_nodes" in account["hyperedge"]
    assert account["calibration_source"] == "identity"


def test_factory_deserializes_supplied_checkpoint_bytes_instead_of_reopening_path(tmp_path):
    checkpoint = _write_rich_strict_checkpoint(tmp_path)
    verified_bytes = checkpoint.read_bytes()
    checkpoint.write_bytes(b"replacement-after-verification")

    runtime = create_botrhg_inference(checkpoint, checkpoint_bytes=verified_bytes)

    assert isinstance(runtime, StrictBotRHGInference)
    assert runtime.payload["schema"] == "cogguard.botrhg.account.v3"


def test_strict_runtime_uses_checkpoint_bound_text_assets_without_the_source_directory(tmp_path):
    checkpoint = _write_rich_strict_checkpoint(tmp_path)
    payload = torch.load(checkpoint, map_location="cpu", weights_only=True)
    shutil.rmtree(payload["text_model_path"])

    runtime = create_botrhg_inference(checkpoint)

    assert isinstance(runtime, StrictBotRHGInference)


def test_strict_runtime_derives_observable_properties_and_graph_edges(tmp_path):
    checkpoint = _write_rich_strict_checkpoint(tmp_path)
    runtime = create_botrhg_inference(checkpoint)

    result = runtime.predict(
        [
            {
                "author_id": "account-a",
                "post_id": "post-a",
                "content": "HTTPURL @friend #topic first post",
                "timestamp": "2024-01-10T00:00:00Z",
                "in_reply_to_user_id": "account-b",
                "author_profile": {
                    "followers_count": 11,
                    "friends_count": 12,
                    "statuses_count": 13,
                    "favourites_count": 14,
                    "listed_count": 15,
                    "description": "profile bio",
                    "verified": True,
                    "lang": "zh-cn",
                    "created_at": "2020-01-01T00:00:00Z",
                },
            },
            {
                "author_id": "account-a",
                "post_id": "post-a-repost",
                "content": "second post",
                "timestamp": "2024-01-11T00:00:00Z",
                "retweeted_status_id": "post-b",
            },
            {
                "author_id": "account-b",
                "post_id": "post-b",
                "content": "account b post",
                "timestamp": "2024-01-11T00:00:00Z",
                "author_profile": {
                    "followers_count": 1,
                    "friends_count": 2,
                    "statuses_count": 3,
                    "favourites_count": 4,
                    "listed_count": 5,
                    "description": "other profile",
                    "verified": False,
                    "lang": "en",
                    "created_at": "2021-01-01T00:00:00Z",
                },
            },
        ]
    )

    record = runtime._record("account-a", [
        {
            "author_id": "account-a",
            "content": "HTTPURL @friend #topic first post",
            "timestamp": "2024-01-10T00:00:00Z",
            "author_profile": {
                "followers_count": 11,
                "friends_count": 12,
                "statuses_count": 13,
                "favourites_count": 14,
                "listed_count": 15,
                "description": "profile bio",
                "verified": True,
                "lang": "zh-cn",
                "created_at": "2020-01-01T00:00:00Z",
            },
        },
        {"author_id": "account-a", "content": "second post", "timestamp": "2024-01-11T00:00:00Z"},
    ])
    account = result["accounts"][0]

    assert record.numeric_features["followers_count"] == 11.0
    assert record.numeric_features["friends_count"] == 12.0
    assert record.numeric_features["post_count"] == 2.0
    assert record.numeric_features["url_rate"] == 0.5
    assert record.numeric_features["mention_rate"] == 0.5
    assert record.numeric_features["hashtag_rate"] == 0.5
    assert record.categorical_features == {"verified": "true", "lang": "zh-cn"}
    assert account["feature_coverage"]["missing"] == []
    assert account["feature_coverage"]["observed_count"] == account["feature_coverage"]["total_count"]
    assert result["graph"] == {"available": True, "edge_count": 2, "relation_types": ["reply", "retweet"]}


def test_strict_runtime_emits_calibrated_routed_hyperedge_and_classifier_badge(tmp_path):
    runtime = create_botrhg_inference(_write_rich_strict_checkpoint(tmp_path))
    result = runtime.predict(
        [
            {"author_id": "account-a", "post_id": "post-a", "content": "first", "author_profile": {"verified": True, "lang": "zh-cn"}},
            {"author_id": "account-b", "post_id": "post-b", "content": "second", "author_profile": {"verified": False, "lang": "en"}},
        ]
    )

    account = result["accounts"][0]
    representation = torch.tensor(account["representation"], dtype=torch.float32)
    probabilities = runtime.model.base_detector.classifier(representation).softmax(dim=0)
    pseudo_label = int(probabilities.argmax().item())
    one_hot = torch.zeros_like(probabilities)
    one_hot[pseudo_label] = 1.0
    expected_badge = torch.cat(
        [torch.outer(probabilities - one_hot, representation).flatten(), probabilities - one_hot]
    ).tolist()

    assert account["calibrated"] is True
    assert account["calibrated_probability"] == account["final_bot_probability"]
    assert len(account["representation"]) == 8
    assert torch.allclose(torch.tensor(account["badge_embedding"]), torch.tensor(expected_badge), atol=2e-7)
    assert all(row["routed"] for row in result["accounts"])
    assert all(row["hyperedge"]["support_k"] == 1 for row in result["accounts"])
    assert all(len(row["support_evidence"]) == 1 for row in result["accounts"])


def test_governed_runtime_rejects_bundle_components_that_differ_from_detector(tmp_path):
    checkpoint = _write_rich_strict_checkpoint(tmp_path)
    payload = torch.load(checkpoint, map_location="cpu", weights_only=False)
    encoder_path = tmp_path / "encoder.pt"
    feature_schema_path = tmp_path / "feature_schema.json"
    calibration_path = tmp_path / "calibration.json"
    torch.save(
        {
            "schema": payload["schema"],
            "component": "encoder",
            "state_dict": payload["text_encoder_state_dict"],
        },
        encoder_path,
    )
    feature_schema_path.write_text(json.dumps(payload["feature_schema"]), encoding="utf-8")
    calibration_path.write_text(json.dumps(payload["calibration"]), encoding="utf-8")

    runtime = create_botrhg_inference(
        checkpoint,
        encoder_path=encoder_path,
        feature_schema_path=feature_schema_path,
        calibration_path=calibration_path,
        expected_source_schema=payload["schema"],
    )
    assert runtime.calibration == payload["calibration"]

    calibration_path.write_text(
        json.dumps({"method": "temperature_scaling", "passed": True, "temperature": 2.0}),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="calibration"):
        create_botrhg_inference(
            checkpoint,
            encoder_path=encoder_path,
            feature_schema_path=feature_schema_path,
            calibration_path=calibration_path,
            expected_source_schema=payload["schema"],
        )


def test_dapt_bound_governed_bundle_loads_through_actual_strict_inference(tmp_path):
    model_dir = tmp_path / "dapt-base"
    model_dir.mkdir()
    vocab_path = model_dir / "vocab.txt"
    vocab_path.write_text(
        "\n".join(("[PAD]", "[UNK]", "[CLS]", "[SEP]", "[MASK]", "social", "account")),
        encoding="utf-8",
    )
    BertTokenizer(str(vocab_path), do_lower_case=False).save_pretrained(model_dir)
    BertForMaskedLM(
        BertConfig(
            vocab_size=7,
            hidden_size=8,
            num_hidden_layers=1,
            num_attention_heads=2,
            intermediate_size=16,
        )
    ).save_pretrained(model_dir)
    dapt_result = train_dapt(
        model_dir,
        build_versioned_dapt_corpus(["\u4e2d\u6587\u793e\u4ea4\u8d26\u53f7"], config=DAPTConfig(min_chinese_tokens=2)),
        output_dir=tmp_path / "dapt-output",
        config=DAPTConfig(min_chinese_tokens=2, mixed_precision=False),
        epochs=0,
        device="cpu",
    )
    encoder_payload = torch.load(dapt_result.encoder_payload_path, map_location="cpu", weights_only=True)
    strict_dir = tmp_path / "strict"
    strict_dir.mkdir()
    checkpoint = _write_rich_strict_checkpoint(strict_dir)
    checkpoint_payload = torch.load(checkpoint, map_location="cpu", weights_only=False)
    checkpoint_payload["text_model_path"] = str(model_dir)
    checkpoint_payload["text_runtime_assets"] = {
        path.name: path.read_bytes()
        for path in model_dir.iterdir()
        if path.is_file() and path.name not in {"model.safetensors", "pytorch_model.bin"}
    }
    checkpoint_payload["text_encoder_state_dict"] = encoder_payload["state_dict"]
    torch.save(checkpoint_payload, checkpoint)
    bundle_manifest_path = write_account_model_bundle(
        tmp_path / "bundle",
        encoder=dapt_result.encoder_payload_path,
        detector=checkpoint,
        feature_schema=checkpoint_payload["feature_schema"],
        calibration=checkpoint_payload["calibration"],
        metrics={},
        data_fingerprints={"fixture": "a" * 64},
        source_schema="cogguard.botrhg.account.v3",
    )
    bundle_dir = bundle_manifest_path.parent
    bundle_manifest = json.loads(bundle_manifest_path.read_text(encoding="utf-8"))

    runtime = create_botrhg_inference(
        bundle_dir / bundle_manifest["artifacts"]["detector"],
        encoder_path=bundle_dir / bundle_manifest["artifacts"]["encoder"],
        feature_schema_path=bundle_dir / bundle_manifest["artifacts"]["feature_schema"],
        calibration_path=bundle_dir / bundle_manifest["artifacts"]["calibration"],
        expected_source_schema="cogguard.botrhg.account.v3",
    )

    assert isinstance(runtime, StrictBotRHGInference)


def _write_rich_strict_checkpoint(tmp_path):
    model_dir = tmp_path / "tiny-roberta"
    model_dir.mkdir()
    vocab_path = model_dir / "vocab.txt"
    vocab_path.write_text("\n".join(("[PAD]", "[UNK]", "[CLS]", "[SEP]", "[MASK]", "first", "second")), encoding="utf-8")
    BertTokenizer(str(vocab_path), do_lower_case=False).save_pretrained(model_dir)
    bert = BertModel(BertConfig(vocab_size=7, hidden_size=8, num_hidden_layers=1, num_attention_heads=2, intermediate_size=16))
    bert.save_pretrained(model_dir)
    runtime_assets = {
        path.name: path.read_bytes()
        for path in model_dir.iterdir()
        if path.is_file() and path.name not in {"model.safetensors", "pytorch_model.bin"}
    }

    numeric_fields = [
        "followers_count", "friends_count", "statuses_count", "favourites_count", "listed_count",
        "post_count", "description_length", "avg_tweet_length", "duplicate_ratio", "url_rate",
        "mention_rate", "hashtag_rate", "reply_rate", "retweet_rate", "account_age_days",
    ]
    categorical_vocab = {"verified": ["false", "true"], "lang": ["en", "zh-cn"]}
    property_dim = len(numeric_fields) + sum(len(values) + 1 for values in categorical_vocab.values())
    model = StrictBotRHGModel(
        text_dim=8,
        property_dim=property_dim,
        graph_dim=8,
        hidden_dim=8,
        projection_dim=4,
        dropout=0.0,
        num_relations=2,
    )
    checkpoint = tmp_path / "rich-checkpoint.pt"
    torch.save(
        {
            "schema": "cogguard.botrhg.account.v3",
            "text_model_path": str(model_dir),
            "text_runtime_assets": runtime_assets,
            "text_hidden_size": 8,
            "feature_schema": {
                "numeric_fields": numeric_fields,
                "categorical_fields": ["verified", "lang"],
                "categorical_vocab": categorical_vocab,
            },
            "numeric_stats": {field: {"mean": 0.0, "std": 1.0} for field in numeric_fields},
            "base_config": {"hidden_dim": 8, "dropout": 0.0},
            "correction_config": {"projection_dim": 4, "dropout": 0.0},
            "graph_relation_types": ["reply", "retweet"],
            "property_state_dict": model.property_encoder.state_dict(),
            "graph_state_dict": model.graph_encoder.state_dict(),
            "support_projection_state_dict": model.support_projection.state_dict(),
            "base_state_dict": model.base_detector.state_dict(),
            "correction_state_dict": model.correction.state_dict(),
            "text_encoder_state_dict": bert.state_dict(),
            "training_config": {"model": {"max_length": 16, "batch_size": 2, "max_chunks_per_account": 2}},
            "routing_budget": 1.0,
            "support_k": 1,
            "calibration": {"method": "identity", "passed": True},
            "data_fingerprint": "d" * 64,
        },
        checkpoint,
    )
    return checkpoint
