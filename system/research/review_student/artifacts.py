"""Governed artifact export for trained Student Review checkpoints."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import torch
from torch import nn


def export_student_checkpoint(
    *,
    model: nn.Module,
    output_dir: str | Path,
    filename: str,
    version: str,
    backbone: str,
    rationale_dim: int,
    metrics: dict[str, Any],
) -> dict[str, str]:
    directory = Path(output_dir)
    directory.mkdir(parents=True, exist_ok=True)
    checkpoint_path = directory / filename
    torch.save({"state_dict": model.state_dict()}, checkpoint_path)
    digest = _sha256(checkpoint_path)
    manifest = {
        "schema": "cogguard.review_student.artifact.v1",
        "technology": "review_student",
        "version": str(version),
        "checkpoint_path": filename,
        "checkpoint_sha256": digest,
        "backbone": str(backbone),
        "stance_count": 3,
        "rationale_dim": int(rationale_dim),
        "metrics": dict(metrics),
    }
    manifest_path = directory / "manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return {
        "checkpoint_path": str(checkpoint_path),
        "checkpoint_sha256": digest,
        "manifest_path": str(manifest_path),
    }


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


__all__ = ["export_student_checkpoint"]
