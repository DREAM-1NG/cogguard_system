from __future__ import annotations

from scripts import prefetch_semantic_models


def test_select_required_snapshot_files_skips_auxiliary_exports_and_duplicate_weights():
    files = [
        ".gitattributes",
        "README.md",
        "config.json",
        "model.safetensors",
        "pytorch_model.bin",
        "onnx/config.json",
        "onnx/model.onnx",
        "tf_model.h5",
        "tokenizer.json",
        "tokenizer_config.json",
        "special_tokens_map.json",
        "vocab.txt",
        "training_args.bin",
        "modules.json",
        "config_sentence_transformers.json",
        "sentence_bert_config.json",
        "1_Pooling/config.json",
    ]

    selected = prefetch_semantic_models.select_required_snapshot_files(files)

    assert "model.safetensors" in selected
    assert "pytorch_model.bin" not in selected
    assert "onnx/model.onnx" not in selected
    assert "tf_model.h5" not in selected
    assert "training_args.bin" not in selected
    assert "README.md" not in selected
    assert "tokenizer.json" in selected
    assert "1_Pooling/config.json" in selected


def test_select_required_snapshot_files_keeps_pytorch_when_safetensors_absent():
    selected = prefetch_semantic_models.select_required_snapshot_files(
        ["config.json", "pytorch_model.bin", "tokenizer.json"]
    )

    assert "pytorch_model.bin" in selected

