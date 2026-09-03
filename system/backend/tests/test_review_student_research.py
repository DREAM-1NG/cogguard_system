from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import torch
from torch import nn


RESEARCH_ROOT = Path(__file__).resolve().parents[2] / "research" / "review_student"


def _load_research_package():
    name = "cogguard_review_student_research"
    existing = sys.modules.get(name)
    if existing is not None:
        return existing
    spec = importlib.util.spec_from_file_location(
        name,
        RESEARCH_ROOT / "__init__.py",
        submodule_search_locations=[str(RESEARCH_ROOT)],
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def test_joint_loss_masks_missing_targets_without_nan():
    research = _load_research_package()
    loss_fn = research.ReviewStudentJointLoss(lambda_soft=0.5, lambda_latent=1.0, stance_weight=0.2)
    outputs = {
        "attack_hate_offense": torch.tensor([0.0, 1.0]),
        "misinfo_claim_risk": torch.tensor([0.0, 1.0]),
        "stance": torch.tensor([[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]]),
        "rationale_proj": torch.tensor([[1.0, 0.0], [0.0, 1.0]]),
    }
    targets = {
        "attack_gold": torch.tensor([0.0, 1.0]),
        "attack_mask": torch.tensor([1.0, 1.0]),
        "misinfo_gold": torch.tensor([0.0, 0.0]),
        "misinfo_mask": torch.tensor([0.0, 0.0]),
        "stance_gold": torch.tensor([0, 1]),
        "stance_mask": torch.tensor([1.0, 1.0]),
        "attack_soft": torch.tensor([0.1, 0.9]),
        "attack_soft_mask": torch.tensor([1.0, 1.0]),
        "misinfo_soft": torch.tensor([0.0, 0.0]),
        "misinfo_soft_mask": torch.tensor([0.0, 0.0]),
        "stance_soft": torch.tensor([0, 1]),
        "stance_soft_mask": torch.tensor([0.0, 0.0]),
        "rationale_target": torch.tensor([[1.0, 0.0], [0.0, 1.0]]),
        "rationale_mask": torch.tensor([1.0, 0.0]),
    }

    losses = loss_fn(outputs, targets)

    assert set(losses) == {"total_loss", "gold_loss", "soft_loss", "latent_loss"}
    assert all(torch.isfinite(value) for value in losses.values())
    assert losses["latent_loss"].item() == 0.0


def test_hardcase_ranking_uses_entropy_outside_the_model():
    research = _load_research_package()
    rows = [
        {"case_id": "certain", "attack_hate_offense": 0.99, "misinfo_claim_risk": 0.01},
        {"case_id": "hard", "attack_hate_offense": 0.51, "misinfo_claim_risk": 0.49},
        {"case_id": "middle", "attack_hate_offense": 0.75, "misinfo_claim_risk": 0.25},
    ]

    selected = research.rank_hardcases(rows, ratio=1 / 3)

    assert [row["case_id"] for row in selected] == ["hard"]
    assert selected[0]["uncertainty"] > 0.99


def test_checkpoint_export_writes_activation_manifest_and_hash(tmp_path):
    research = _load_research_package()
    model = nn.Linear(2, 1)

    artifact = research.export_student_checkpoint(
        model=model,
        output_dir=tmp_path,
        filename="student.pt",
        version="student-test-v1",
        backbone="xlm-roberta-base",
        rationale_dim=8,
        metrics={"teacher_macro_f1_gap": 0.02, "ece": 0.05, "p95_latency_seconds": 1.2},
    )

    manifest = json.loads((tmp_path / "manifest.json").read_text(encoding="utf-8"))
    assert artifact["checkpoint_path"] == str(tmp_path / "student.pt")
    assert len(artifact["checkpoint_sha256"]) == 64
    assert manifest["technology"] == "review_student"
    assert manifest["checkpoint_path"] == "student.pt"
    assert manifest["version"] == "student-test-v1"
    assert manifest["metrics"]["ece"] == 0.05
