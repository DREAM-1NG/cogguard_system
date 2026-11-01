from __future__ import annotations

import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import torch
from torch import nn

from app.core.analysis.runtime import _load_review_student_runtime


student_module = _load_review_student_runtime()


def _case(*, options=None):
    return {
        "snapshot_id": "snapshot-1",
        "event_id": "event-1",
        "platforms": ["weibo"],
        "posts": [
            {
                "post_id": "p1",
                "author_id": "u1",
                "platform": "weibo",
                "content": "post text",
                "claim_context": "claim text",
                "ocr_text": "image text",
            }
        ],
        "comments": [],
        "relationships": [],
        "quality_report": {"status": "pass", "issues": []},
        "options": options or {},
    }


def _manifest_sha256(manifest):
    payload = {key: value for key, value in manifest.items() if key != "manifest_sha256"}
    return hashlib.sha256(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def test_review_student_input_serializes_claim_and_decodable_evidence():
    item = student_module.ReviewStudentInput.from_post(_case()["posts"][0])

    assert item.serialize() == "[TEXT] post text [CLAIM] claim text [OCR] image text"


def test_xlmr_student_has_prediction_and_rationale_heads_without_defer():
    class FakeEncoder(nn.Module):
        def forward(self, *, input_ids, attention_mask):
            batch, length = input_ids.shape
            return SimpleNamespace(last_hidden_state=torch.ones(batch, length, 4))

    model = student_module.XLMRReviewStudent(
        encoder=FakeEncoder(),
        hidden_size=4,
        stance_count=3,
        rationale_dim=6,
    )
    outputs = model(
        input_ids=torch.ones(2, 3, dtype=torch.long),
        attention_mask=torch.ones(2, 3, dtype=torch.long),
    )

    assert set(outputs) == {
        "attack_hate_offense",
        "misinfo_claim_risk",
        "stance",
        "rationale_proj",
    }
    assert outputs["attack_hate_offense"].shape == (2,)
    assert outputs["stance"].shape == (2, 3)
    assert outputs["rationale_proj"].shape == (2, 6)
    assert not hasattr(model, "defer")


def test_missing_checkpoint_abstains_without_heuristic_judgment():
    verdict = student_module.StudentRuntime().predict_sync(_case())

    assert verdict["status"] == "ok"
    assert verdict["model_status"] == "shadow_untrained"
    assert verdict["label"] == "uncertain"
    assert verdict["score"] == 0.5
    assert verdict["abstain"] is True
    assert verdict["review_required"] is True
    assert verdict["evidence"]["capability_boundary"]["canonical_allowed"] is False
    assert "matched_terms" not in json.dumps(verdict)


def test_active_checkpoint_uses_predictor_after_manifest_and_hash_validation(tmp_path):
    checkpoint = tmp_path / "checkpoint.pt"
    checkpoint.write_bytes(b"approved-checkpoint")
    digest = hashlib.sha256(checkpoint.read_bytes()).hexdigest()
    manifest = {
        "technology": "review_student",
        "checkpoint_path": checkpoint.name,
        "checkpoint_sha256": digest,
        "backbone": "xlm-roberta-base",
        "rationale_dim": 6,
    }
    manifest["manifest_sha256"] = _manifest_sha256(manifest)
    (tmp_path / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    calls = []

    class FakePredictor:
        def predict(self, inputs):
            calls.extend(inputs)
            return [{"attack_hate_offense": 0.8, "misinfo_claim_risk": 0.2, "stance": [0.1, 0.2, 0.7]}]

    runtime = student_module.StudentRuntime(predictor_factory=lambda descriptor: FakePredictor())
    verdict = runtime.predict_sync(
        _case(
            options={
                "active_model": {
                    "technology": "review_student",
                    "status": "active",
                    "version": "v1",
                    "checkpoint_path": str(checkpoint),
                    "artifact_uri": str(tmp_path),
                    "artifact_hash": digest,
                    "artifact_manifest_sha256": manifest["manifest_sha256"],
                }
            }
        )
    )

    assert verdict["model_status"] == "checkpoint_active"
    assert verdict["label"] == "harmful"
    assert verdict["score"] == 0.8
    assert verdict["abstain"] is False
    assert len(calls) == 1
    assert isinstance(calls[0], student_module.ReviewStudentInput)


def test_active_checkpoint_rejects_post_registration_manifest_mutation(tmp_path):
    checkpoint = tmp_path / "checkpoint.pt"
    checkpoint.write_bytes(b"approved-checkpoint")
    digest = hashlib.sha256(checkpoint.read_bytes()).hexdigest()
    manifest = {
        "technology": "review_student",
        "checkpoint_path": checkpoint.name,
        "checkpoint_sha256": digest,
        "backbone": "xlm-roberta-base",
        "rationale_dim": 6,
    }
    manifest["manifest_sha256"] = _manifest_sha256(manifest)
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    class FakePredictor:
        def predict(self, _inputs):
            return [{"attack_hate_offense": 0.8, "misinfo_claim_risk": 0.2, "stance": [0.1, 0.2, 0.7]}]

    active_model = {
        "technology": "review_student",
        "status": "active",
        "version": "v1",
        "checkpoint_path": str(checkpoint),
        "artifact_uri": str(tmp_path),
        "artifact_hash": digest,
        "artifact_manifest_sha256": manifest["manifest_sha256"],
    }
    runtime = student_module.StudentRuntime(predictor_factory=lambda _descriptor: FakePredictor())
    assert runtime.predict_sync(_case(options={"active_model": active_model}))[
        "model_status"
    ] == "checkpoint_active"

    manifest["backbone"] = "mutated-backbone"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    verdict = runtime.predict_sync(_case(options={"active_model": active_model}))

    assert verdict["model_status"] == "checkpoint_incompatible"
    assert verdict["abstain"] is True


def test_active_checkpoint_rejects_checkpoint_outside_artifact_directory(tmp_path):
    artifact_dir = tmp_path / "artifact"
    artifact_dir.mkdir()
    checkpoint = tmp_path / "outside.pt"
    checkpoint.write_bytes(b"outside-checkpoint")
    digest = hashlib.sha256(checkpoint.read_bytes()).hexdigest()
    manifest = {
        "technology": "review_student",
        "checkpoint_path": "../outside.pt",
        "checkpoint_sha256": digest,
        "backbone": "xlm-roberta-base",
        "rationale_dim": 6,
    }
    manifest["manifest_sha256"] = _manifest_sha256(manifest)
    (artifact_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    active_model = {
        "technology": "review_student",
        "status": "active",
        "version": "v1",
        "artifact_uri": str(artifact_dir),
        "checkpoint_path": str(checkpoint),
        "artifact_hash": digest,
        "artifact_manifest_sha256": manifest["manifest_sha256"],
    }

    class FakePredictor:
        def predict(self, _inputs):
            return [{"attack_hate_offense": 0.8, "misinfo_claim_risk": 0.2, "stance": [0.1, 0.2, 0.7]}]

    runtime = student_module.StudentRuntime(predictor_factory=lambda _descriptor: FakePredictor())
    verdict = runtime.predict_sync(_case(options={"active_model": active_model}))

    assert verdict["model_status"] == "checkpoint_incompatible"
    assert verdict["abstain"] is True


def test_incompatible_checkpoint_abstains_instead_of_loading(tmp_path):
    checkpoint = tmp_path / "checkpoint.pt"
    checkpoint.write_bytes(b"checkpoint")
    (tmp_path / "manifest.json").write_text(
        json.dumps({"technology": "propagation_analysis", "checkpoint_path": checkpoint.name}),
        encoding="utf-8",
    )

    verdict = student_module.StudentRuntime(
        predictor_factory=lambda descriptor: (_ for _ in ()).throw(AssertionError("must not load"))
    ).predict_sync(
        _case(
            options={
                "active_model": {
                    "technology": "review_student",
                    "status": "active",
                    "checkpoint_path": str(checkpoint),
                    "artifact_uri": str(tmp_path),
                    "artifact_hash": hashlib.sha256(checkpoint.read_bytes()).hexdigest(),
                }
            }
        )
    )

    assert verdict["model_status"] == "checkpoint_incompatible"
    assert verdict["abstain"] is True
