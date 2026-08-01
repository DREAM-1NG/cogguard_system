import json

import torch

from research.social_bot_detection.artifacts import load_training_artifact
from research.social_bot_detection.artifacts import write_training_artifacts
from research.social_bot_detection.contracts import DatasetManifest, ModelConfig, TrainingConfig


def test_checkpoint_artifact_round_trip(tmp_path):
    manifest = DatasetManifest(
        source_root="fixture",
        label_file="labels.xlsx",
        text_directory="texts",
        data_fingerprint="abc",
        labeled_account_count=2,
        usable_account_count=2,
        skipped_empty_text_count=0,
        missing_text_count=0,
        class_counts={"0": 1, "1": 1},
    )
    paths = write_training_artifacts(
        tmp_path,
        checkpoint={"schema": "cogguard.botrhg.weibo.v1", "tensor": torch.ones(2)},
        config=TrainingConfig(model=ModelConfig(text_model_path="fixture")),
        manifest=manifest,
        metrics={"test": {"macro_f1": 0.5}},
        predictions=[{"account_id": "a"}],
        history=[{"stage": "base", "epoch": 1}],
        model_card="# fixture",
    )
    loaded = load_training_artifact(paths["checkpoint_path"])
    assert loaded["schema"] == "cogguard.botrhg.weibo.v1"
    assert torch.equal(loaded["tensor"], torch.ones(2))
    assert json.loads((tmp_path / "data_manifest.json").read_text())["data_fingerprint"] == "abc"


def test_finetuned_encoder_state_is_optional_in_checkpoint(tmp_path):
    from research.social_bot_detection.artifacts import load_training_artifact

    path = tmp_path / "checkpoint.pt"
    torch.save({"schema": "cogguard.botrhg.account.v2", "text_encoder_state_dict": None}, path)
    loaded = load_training_artifact(path)
    assert loaded["text_encoder_state_dict"] is None
