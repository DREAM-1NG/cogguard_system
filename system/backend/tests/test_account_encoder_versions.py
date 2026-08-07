"""Focused governance tests for immutable Chinese social encoder versions."""

from __future__ import annotations

import asyncio
import hashlib
import json
import sys
from pathlib import Path

import pytest
import torch

from app.config import settings
from app.core import account_model_artifact
from app.models.account_labeling import AccountModelTrainingRun, ChineseSocialEncoderVersion
from app.services import account_model_governance_service as governance
from app.utils.exceptions import AppException


SYSTEM_ROOT = Path(__file__).resolve().parents[2]
if str(SYSTEM_ROOT) not in sys.path:
    sys.path.insert(0, str(SYSTEM_ROOT))


class _Result:
    def __init__(self, value):
        self.value = value

    def scalar_one_or_none(self):
        return self.value


class _EncoderSession:
    def __init__(self) -> None:
        self.encoder = None
        self.added = []

    async def execute(self, statement):
        entity = statement.column_descriptions[0].get("entity")
        return _Result(self.encoder if entity is ChineseSocialEncoderVersion else None)

    def add(self, value) -> None:
        self.added.append(value)

    async def flush(self) -> None:
        for value in self.added:
            if isinstance(value, ChineseSocialEncoderVersion):
                self.encoder = value


def test_encoder_artifact_verification_requires_configured_root_and_exact_bytes(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "MODEL_ARTIFACT_ROOT", str(tmp_path))
    artifact_dir, artifact_hash = _write_encoder_artifact(tmp_path)

    manifest = account_model_artifact.load_verified_chinese_social_encoder_artifact(
        artifact_dir,
        expected_hash=artifact_hash,
    )

    assert manifest["artifact_hash"] == artifact_hash
    assert manifest["base_model_identity"] == "fixture-base-model"
    with pytest.raises(AppException, match="outside MODEL_ARTIFACT_ROOT"):
        account_model_artifact.load_verified_chinese_social_encoder_artifact(
            tmp_path.parent / "outside",
            expected_hash=artifact_hash,
        )
    (artifact_dir / "tokenizer.json").write_text("tampered", encoding="utf-8")
    with pytest.raises(AppException, match="verification failed"):
        account_model_artifact.load_verified_chinese_social_encoder_artifact(
            artifact_dir,
            expected_hash=artifact_hash,
        )


def test_detector_runtime_rejects_direct_external_text_model_paths(monkeypatch, tmp_path):
    from app.core import account_training_runtime

    dataset_root = tmp_path / "dataset"
    dataset_root.mkdir()
    holdout_path = tmp_path / "holdout.json"
    holdout_path.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(
        account_training_runtime,
        "_load_research_package",
        lambda: pytest.fail("an unbound detector configuration must fail before loading research training"),
    )

    with pytest.raises(AppException, match="registered encoder version"):
        account_training_runtime._execute_detector(
            {
                "dataset_root": str(dataset_root),
                "frozen_holdout_manifest_path": str(holdout_path),
                "text_model_path": "/untrusted/external/model",
            },
            tmp_path / "output",
        )


def test_detector_candidate_rejects_bundle_with_a_different_encoder_component(monkeypatch, tmp_path):
    from research.social_bot_detection.model_bundle import write_account_model_bundle

    monkeypatch.setattr(settings, "MODEL_ARTIFACT_ROOT", str(tmp_path))
    artifact_dir, artifact_hash = _write_encoder_artifact(tmp_path)
    manifest = account_model_artifact.load_verified_chinese_social_encoder_artifact(
        artifact_dir,
        expected_hash=artifact_hash,
    )
    session = _EncoderSession()
    session.encoder = ChineseSocialEncoderVersion(
        encoder_version="chinese-social-encoder-encoder-run-1",
        corpus_version_id="corpus-1",
        training_run_id="encoder-run-1",
        artifact_uri=str(artifact_dir),
        artifact_hash=artifact_hash,
        base_model_identity="fixture-base-model",
        manifest_json=json.dumps(manifest, sort_keys=True),
        status="completed",
        created_by=7,
    )
    unrelated_encoder = tmp_path / "unrelated-encoder.bin"
    unrelated_encoder.write_bytes(b"unrelated-encoder")
    detector = tmp_path / "detector.pt"
    detector.write_bytes(b"detector")
    bundle_dir = tmp_path / "detector-bundle"
    write_account_model_bundle(
        bundle_dir,
        encoder=unrelated_encoder,
        detector=detector,
        feature_schema={"numeric_fields": [], "categorical_fields": [], "categorical_vocab": {}},
        calibration={"method": "identity"},
        metrics={},
        data_fingerprints={"fixture": "a" * 64},
        source_schema="cogguard.botrhg.strict.v1",
    )

    async def scenario():
        with pytest.raises(AppException, match="encoder component"):
            await governance.register_account_training_result(
                session,
                run_id="detector-run-1",
                dataset_version_id="dataset-1",
                artifact_uri=str(bundle_dir),
                metrics={},
                operator_id=7,
                encoder_version=session.encoder.encoder_version,
                encoder_artifact_hash=artifact_hash,
            )

    asyncio.run(scenario())


def test_encoder_version_registration_is_idempotent_and_detector_resolution_fails_closed(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "MODEL_ARTIFACT_ROOT", str(tmp_path))
    artifact_dir, artifact_hash = _write_encoder_artifact(tmp_path)
    run = AccountModelTrainingRun(
        run_id="encoder-run-1",
        family="chinese_social_encoder",
        status="evaluating",
        stage="evaluating",
        corpus_version_id="corpus-1",
        input_fingerprint="a" * 64,
        config_hash="b" * 64,
        config_json="{}",
        attempt=1,
        max_attempts=3,
        created_by=7,
    )
    session = _EncoderSession()
    training_result = {
        "encoder_artifact_dir": str(artifact_dir),
        "encoder_artifact_hash": artifact_hash,
        "encoder_manifest_path": str(artifact_dir / "encoder_manifest.json"),
    }

    async def scenario():
        registered = await governance.register_chinese_social_encoder_version(
            session,
            run=run,
            training_result=training_result,
        )
        replayed = await governance.register_chinese_social_encoder_version(
            session,
            run=run,
            training_result=training_result,
        )
        resolved = await governance.resolve_governed_chinese_social_encoder(
            session,
            config={"encoder_version": registered["encoder_version"]},
        )

        assert replayed == registered
        assert len([item for item in session.added if isinstance(item, ChineseSocialEncoderVersion)]) == 1
        assert registered["training_run_id"] == run.run_id
        assert registered["corpus_version_id"] == run.corpus_version_id
        assert resolved["text_model_path"] == str(artifact_dir)
        assert resolved["encoder_binding_payload_path"] == str(artifact_dir / "encoder_state.pt")
        assert resolved["encoder_artifact_hash"] == artifact_hash
        assert resolved["model"]["encoder_trainable"] is False

        with pytest.raises(AppException, match="text_model_path is not accepted"):
            await governance.resolve_governed_chinese_social_encoder(
                session,
                config={
                    "encoder_version": registered["encoder_version"],
                    "text_model_path": "/untrusted/external/model",
                },
            )

    asyncio.run(scenario())


def _write_encoder_artifact(root: Path) -> tuple[Path, str]:
    artifact_dir = root / "account_training" / "encoder-run-1" / "chinese_social_encoder"
    artifact_dir.mkdir(parents=True)
    (artifact_dir / "pytorch_model.bin").write_bytes(b"fixture-model")
    (artifact_dir / "tokenizer.json").write_text('{"fixture":true}', encoding="utf-8")
    payload_path = artifact_dir / "encoder_state.pt"
    torch.save(
        {
            "schema": "cogguard.botrhg.account.v3",
            "component": "encoder",
            "state_dict": {"fixture.weight": torch.tensor([1.0])},
        },
        payload_path,
    )
    files = {
        path.name: hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(artifact_dir.iterdir())
        if path.is_file()
    }
    manifest = {
        "base_model_identity": "fixture-base-model",
        "encoder_payload": {
            "path": "encoder_state.pt",
            "schema": "cogguard.botrhg.account.v3",
            "sha256": hashlib.sha256(payload_path.read_bytes()).hexdigest(),
        },
        "files": files,
        "provenance": {
            "corpus": {"input_fingerprint": "a" * 64},
            "dapt_config": {},
            "dapt_config_hash": "b" * 64,
        },
        "schema": "cogguard.chinese-social-encoder.v1",
        "status": "completed",
    }
    manifest_path = artifact_dir / "encoder_manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=True, sort_keys=True, separators=(",", ":")),
        encoding="utf-8",
    )
    return artifact_dir, hashlib.sha256(payload_path.read_bytes()).hexdigest()
