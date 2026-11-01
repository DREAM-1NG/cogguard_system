"""Reproducible BotRHG experiment artifact writer and loader."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

import torch

from .contracts import DatasetManifest, TrainingConfig, ensure_output_path

__all__ = ["write_training_artifacts", "load_training_artifact"]


def write_training_artifacts(
    output_dir: str | Path,
    *,
    checkpoint: dict[str, Any],
    config: TrainingConfig,
    manifest: DatasetManifest,
    metrics: dict[str, Any],
    predictions: list[dict[str, Any]],
    history: list[dict[str, Any]],
    model_card: str,
) -> dict[str, str]:
    """Write checkpoint and machine-readable experiment records."""

    output = ensure_output_path(output_dir)
    config_payload = _jsonable(asdict(config))
    (output / "config.json").write_text(json.dumps(config_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    (output / "data_manifest.json").write_text(json.dumps(manifest.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    (output / "metrics.json").write_text(json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8")
    with (output / "predictions.jsonl").open("w", encoding="utf-8") as stream:
        for row in predictions:
            stream.write(json.dumps(row, ensure_ascii=False) + "\n")
    (output / "training_history.json").write_text(json.dumps(history, ensure_ascii=False, indent=2), encoding="utf-8")
    (output / "model_card.md").write_text(model_card, encoding="utf-8")
    checkpoint_path = output / "checkpoint.pt"
    torch.save(checkpoint, checkpoint_path)
    checkpoint_hash = file_sha256(checkpoint_path)
    (output / "checkpoint.sha256").write_text(f"{checkpoint_hash}  checkpoint.pt\n", encoding="ascii")
    return {
        "output_dir": str(output.resolve()),
        "checkpoint_path": str(checkpoint_path.resolve()),
        "config_path": str((output / "config.json").resolve()),
        "metrics_path": str((output / "metrics.json").resolve()),
        "checkpoint_sha256": checkpoint_hash,
    }


def load_training_artifact(checkpoint_path: str | Path, *, map_location: str = "cpu") -> dict[str, Any]:
    """Load a trusted local checkpoint produced by this package."""

    payload = torch.load(Path(checkpoint_path), map_location=map_location, weights_only=False)
    if not isinstance(payload, dict) or payload.get("schema") not in {
        "cogguard.botrhg.account.v2",
        "cogguard.botrhg.weibo.v1",
    }:
        raise ValueError(f"unsupported BotRHG checkpoint: {checkpoint_path}")
    return payload


def file_sha256(path: str | Path) -> str:
    """Hash an artifact for model provenance."""

    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _jsonable(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    return value
