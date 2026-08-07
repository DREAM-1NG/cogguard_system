import random
from pathlib import Path
from types import SimpleNamespace

import pytest
import torch

from research.social_bot_detection import dapt
from research.social_bot_detection.dapt import (
    DAPTConfig,
    build_versioned_dapt_corpus,
    load_dapt_checkpoint,
    save_dapt_checkpoint,
    train_dapt,
)


def test_dapt_config_uses_required_runtime_defaults():
    config = DAPTConfig()

    assert config.mlm_probability == 0.15
    assert config.max_length == 128
    assert config.micro_batch_size == 2
    assert config.gradient_accumulation_steps == 32
    assert config.mixed_precision is True
    assert config.gradient_checkpointing is True
    assert config.historical_replay_ratio == 0.20


def test_versioned_corpus_counts_chinese_tokens_deduplicates_exactly_and_mixes_replay():
    config = DAPTConfig(min_chinese_tokens=3)
    current = ["社会机器人检测", "社会机器人检测", "中文语料一号", "中文语料二号", "中文语料三号", "ab"]
    historical = ["历史回放一号", "历史回放二号", "历史回放三号"]

    first = build_versioned_dapt_corpus(current, historical, config=config)
    second = build_versioned_dapt_corpus(current, historical, config=config)

    assert first.documents == second.documents
    assert first.manifest.input_fingerprint == second.manifest.input_fingerprint
    assert first.manifest.eligible_chinese_token_count == sum(
        sum("\u4e00" <= character <= "\u9fff" for character in text)
        for text in first.documents
    )
    assert first.manifest.current_document_count == 4
    assert first.manifest.replay_document_count == 1
    assert first.manifest.exact_duplicate_count == 1
    assert first.manifest.rejected_document_count == 1
    assert len(first.documents) == 5


def test_corpus_input_fingerprint_changes_when_rejected_source_changes():
    config = DAPTConfig(min_chinese_tokens=3)
    first = build_versioned_dapt_corpus(["中文合格文本", "no"], config=config)
    second = build_versioned_dapt_corpus(["中文合格文本", "different"], config=config)

    assert first.manifest.input_fingerprint != second.manifest.input_fingerprint


def test_checkpoint_round_trip_preserves_runtime_state_and_rejects_different_input(tmp_path):
    corpus = build_versioned_dapt_corpus(["中文训练文本一", "中文训练文本二"], config=DAPTConfig(min_chinese_tokens=2))
    config = DAPTConfig(min_chinese_tokens=2, mixed_precision=False)
    model = torch.nn.Linear(2, 2)
    optimizer = torch.optim.AdamW(model.parameters(), lr=0.01)
    scheduler = torch.optim.lr_scheduler.LambdaLR(optimizer, lambda _: 1.0)
    scaler = _FakeScaler()
    random.seed(17)
    checkpoint_path = tmp_path / "dapt.pt"

    save_dapt_checkpoint(
        checkpoint_path,
        model=model,
        optimizer=optimizer,
        scheduler=scheduler,
        scaler=scaler,
        epoch=3,
        global_step=11,
        data_cursor=2,
        corpus=corpus,
        config=config,
    )

    payload = torch.load(checkpoint_path, map_location="cpu", weights_only=False)
    assert {
        "model_state_dict", "optimizer_state_dict", "scheduler_state_dict", "scaler_state_dict",
        "epoch", "global_step", "rng_state", "data_cursor", "input_fingerprint", "config_hash",
    } <= payload.keys()
    state = load_dapt_checkpoint(
        checkpoint_path,
        model=model,
        optimizer=optimizer,
        scheduler=scheduler,
        scaler=scaler,
        corpus=corpus,
        config=config,
    )
    assert (state.epoch, state.global_step, state.data_cursor) == (3, 11, 2)
    assert scaler.loaded == {"scale": 1.0}

    other_corpus = build_versioned_dapt_corpus(["完全不同的中文训练文本"], config=DAPTConfig(min_chinese_tokens=2))
    with pytest.raises(ValueError, match="input fingerprint"):
        load_dapt_checkpoint(checkpoint_path, corpus=other_corpus, config=config)


def test_checkpoint_with_missing_required_state_fails_clearly(tmp_path):
    corpus = build_versioned_dapt_corpus(["中文训练文本"], config=DAPTConfig(min_chinese_tokens=2))
    config = DAPTConfig(min_chinese_tokens=2)
    model = torch.nn.Linear(1, 1)
    optimizer = torch.optim.AdamW(model.parameters())
    scheduler = torch.optim.lr_scheduler.LambdaLR(optimizer, lambda _: 1.0)
    path = tmp_path / "missing.pt"
    save_dapt_checkpoint(
        path,
        model=model,
        optimizer=optimizer,
        scheduler=scheduler,
        scaler=_FakeScaler(),
        epoch=0,
        global_step=0,
        data_cursor=0,
        corpus=corpus,
        config=config,
    )
    payload = torch.load(path, map_location="cpu", weights_only=False)
    del payload["optimizer_state_dict"]
    torch.save(payload, path)

    with pytest.raises(ValueError, match="optimizer_state_dict"):
        load_dapt_checkpoint(path, corpus=corpus, config=config)


class _FakeScaler:
    def __init__(self) -> None:
        self.loaded = None

    def state_dict(self):
        return {"scale": 1.0}

    def load_state_dict(self, state):
        self.loaded = state


def test_cpu_training_uses_injected_mlm_and_completed_resume_is_idempotent(tmp_path):
    corpus = build_versioned_dapt_corpus(
        ["中文训练文本一号", "中文训练文本二号", "中文训练文本三号"],
        config=DAPTConfig(min_chinese_tokens=2),
    )
    config = DAPTConfig(
        min_chinese_tokens=2,
        micro_batch_size=2,
        gradient_accumulation_steps=1,
        mixed_precision=True,
    )
    model = _FakeMaskedLanguageModel()
    tokenizer = _FakeTokenizer()
    checkpoint_path = tmp_path / "runtime.pt"

    first = train_dapt(
        "unused-fake-model",
        corpus,
        output_dir=tmp_path,
        config=config,
        tokenizer=tokenizer,
        model=model,
        epochs=1,
        device="cpu",
        checkpoint_path=checkpoint_path,
    )
    second = train_dapt(
        "unused-fake-model",
        corpus,
        output_dir=tmp_path,
        config=config,
        tokenizer=tokenizer,
        model=model,
        epochs=1,
        device="cpu",
        checkpoint_path=checkpoint_path,
        resume_from=checkpoint_path,
    )

    assert model.gradient_checkpointing_enabled is True
    assert first.global_step == 2
    assert second.global_step == first.global_step
    assert second.completed_epochs == 1
    assert first.checkpoint_path == checkpoint_path


def test_completed_dapt_exports_a_verified_immutable_encoder_directory(tmp_path):
    corpus = build_versioned_dapt_corpus(
        ["\u4e2d\u6587\u8bad\u7ec3\u6587\u672c\u4e00\u53f7", "\u4e2d\u6587\u8bad\u7ec3\u6587\u672c\u4e8c\u53f7"],
        config=DAPTConfig(min_chinese_tokens=2),
    )
    config = DAPTConfig(
        min_chinese_tokens=2,
        micro_batch_size=2,
        gradient_accumulation_steps=1,
        mixed_precision=False,
    )
    output_dir = tmp_path / "dapt-output"
    result = train_dapt(
        "fixture-base-model",
        corpus,
        output_dir=output_dir,
        config=config,
        tokenizer=_FakeTokenizer(),
        model=_FakeMaskedLanguageModel(),
        epochs=1,
        device="cpu",
    )

    manifest = dapt.verify_chinese_social_encoder_artifact(
        result.encoder_artifact_dir,
        expected_hash=result.encoder_artifact_hash,
    )

    assert result.encoder_artifact_dir == output_dir / "chinese_social_encoder"
    assert result.encoder_manifest_path == result.encoder_artifact_dir / "encoder_manifest.json"
    assert result.encoder_payload_path == result.encoder_artifact_dir / "encoder_state.pt"
    assert manifest["artifact_hash"] == result.encoder_artifact_hash
    assert set(manifest["files"]) == {"encoder_state.pt", "pytorch_model.bin", "tokenizer.json"}
    assert manifest["encoder_payload"] == {
        "path": "encoder_state.pt",
        "schema": "cogguard.botrhg.account.v3",
        "sha256": result.encoder_artifact_hash,
    }
    payload = torch.load(result.encoder_payload_path, map_location="cpu", weights_only=True)
    assert payload["schema"] == "cogguard.botrhg.account.v3"
    assert payload["component"] == "encoder"
    assert payload["state_dict"]
    assert manifest["provenance"]["corpus"]["input_fingerprint"] == corpus.manifest.input_fingerprint
    assert manifest["provenance"]["dapt_config_hash"]
    assert manifest["base_model_identity"] == "fixture-base-model"

    (result.encoder_artifact_dir / "tokenizer.json").write_text("tampered", encoding="utf-8")
    with pytest.raises(ValueError, match="SHA-256 mismatch"):
        dapt.verify_chinese_social_encoder_artifact(
            result.encoder_artifact_dir,
            expected_hash=result.encoder_artifact_hash,
        )


class _FakeTokenizer:
    mask_token_id = 99
    pad_token_id = 0
    vocab_size = 128

    def __call__(self, documents, *, padding, truncation, max_length, return_tensors, return_special_tokens_mask):
        del padding, truncation, return_tensors, return_special_tokens_mask
        rows = [[1, *[(ord(character) % 20) + 2 for character in text][: max_length - 2], 2] for text in documents]
        width = max(len(row) for row in rows)
        return {
            "input_ids": torch.tensor([row + [0] * (width - len(row)) for row in rows]),
            "attention_mask": torch.tensor([[1] * len(row) + [0] * (width - len(row)) for row in rows]),
            "special_tokens_mask": torch.tensor([[1] + [0] * (len(row) - 2) + [1] + [1] * (width - len(row)) for row in rows]),
        }

    def save_pretrained(self, directory):
        root = Path(directory)
        root.mkdir(parents=True, exist_ok=True)
        (root / "tokenizer.json").write_text('{"fixture":true}', encoding="utf-8")


class _FakeMaskedLanguageModel(torch.nn.Module):
    def __init__(self) -> None:
        super().__init__()
        self.embedding = torch.nn.Embedding(128, 4)
        self.output = torch.nn.Linear(4, 128)
        self.gradient_checkpointing_enabled = False

    def gradient_checkpointing_enable(self) -> None:
        self.gradient_checkpointing_enabled = True

    def forward(self, *, input_ids, attention_mask, labels):
        del attention_mask
        logits = self.output(self.embedding(input_ids))
        return SimpleNamespace(loss=torch.nn.functional.cross_entropy(logits.reshape(-1, 128), labels.reshape(-1), ignore_index=-100))

    def save_pretrained(self, directory):
        root = Path(directory)
        root.mkdir(parents=True, exist_ok=True)
        torch.save(self.state_dict(), root / "pytorch_model.bin")
