from __future__ import annotations

import asyncio
import hashlib
import json
from pathlib import Path

import pytest

from app.config import Settings, settings
from app.models.account_labeling import (
    AccountDetectionModelActivation,
    AccountDetectionModelVersion,
    AccountModelGovernanceDecision,
)
from app.services import account_model_runtime_service
from app.services.account_model_runtime_service import get_active_account_model, resolve_active_account_model
from app.utils.exceptions import AppException


class _Result:
    def __init__(self, value):
        self.value = value

    def scalar_one_or_none(self):
        return self.value


class _RuntimeSession:
    def __init__(self):
        self.activation = None
        self.model = None
        self.decisions = []

    async def execute(self, statement):
        entity = statement.column_descriptions[0].get("entity")
        if entity is AccountDetectionModelActivation:
            return _Result(self.activation)
        if entity is AccountDetectionModelVersion:
            return _Result(self.model)
        raise AssertionError(f"Unexpected entity: {entity}")

    def add(self, value):
        if isinstance(value, AccountDetectionModelActivation):
            self.activation = value
        elif isinstance(value, AccountDetectionModelVersion):
            self.model = value
        elif isinstance(value, AccountModelGovernanceDecision):
            self.decisions.append(value)

    async def flush(self):
        return None


def _production_settings(**overrides):
    values = {
        "BACKEND_ENV": "production",
        "JWT_SECRET_KEY": "j" * 64,
        "DEFAULT_ADMIN_PASSWORD": "not-a-placeholder-password",
        "ACCOUNT_MODEL_EVALUATION_HMAC_SECRET": "e" * 64,
        "ACCOUNT_MODEL_BOOTSTRAP_MODE": "disabled",
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


def test_production_requires_account_evaluator_secret():
    with pytest.raises(ValueError, match="ACCOUNT_MODEL_EVALUATION_HMAC_SECRET"):
        _production_settings(ACCOUNT_MODEL_EVALUATION_HMAC_SECRET="")


def test_active_pointer_driver_import_failure_is_fail_closed(monkeypatch):
    class BrokenSessionContext:
        async def __aenter__(self):
            raise ModuleNotFoundError("aiomysql")

        async def __aexit__(self, *_args):
            return None

    monkeypatch.setattr(
        account_model_runtime_service,
        "async_session_factory",
        lambda: BrokenSessionContext(),
    )

    assert asyncio.run(get_active_account_model()) is None


def test_active_pointer_uses_source_schema_from_verified_bundle(monkeypatch, tmp_path):
    bundle_dir = tmp_path / "bundle"
    bundle_dir.mkdir()
    (bundle_dir / "manifest.json").write_text("{}", encoding="utf-8")
    detector = bundle_dir / "detector.pt"
    detector.write_bytes(b"detector")
    detector_hash = hashlib.sha256(detector.read_bytes()).hexdigest()
    session = _RuntimeSession()
    session.activation = AccountDetectionModelActivation(
        model_family="chinese_account_detection",
        model_version="model-1",
        pointer_revision=3,
        activation_json="{}",
        activated_by=1,
    )
    session.model = AccountDetectionModelVersion(
        model_version="model-1",
        dataset_version_id="dataset-1",
        artifact_hash=detector_hash,
        artifact_uri=str(bundle_dir),
        metrics_json=json.dumps({"source_schema": "caller-controlled-schema"}),
        gates_json="{}",
        status="active",
        created_by=1,
    )
    monkeypatch.setattr(
        account_model_runtime_service,
        "load_deployable_bundle_manifest",
        lambda _path: {"source_schema": "cogguard.botrhg.account.v3"},
    )
    monkeypatch.setattr(account_model_runtime_service, "_checkpoint_path", lambda _uri: detector)

    result = asyncio.run(resolve_active_account_model(session))

    assert result is not None
    assert result.source_schema == "cogguard.botrhg.account.v3"


def test_governed_active_pointer_rejects_a_bare_checkpoint(tmp_path):
    checkpoint = tmp_path / "detector.pt"
    checkpoint.write_bytes(b"detector")
    session = _RuntimeSession()
    session.activation = AccountDetectionModelActivation(
        model_family="chinese_account_detection",
        model_version="model-bare",
        pointer_revision=1,
        activation_json="{}",
        activated_by=1,
    )
    session.model = AccountDetectionModelVersion(
        model_version="model-bare",
        dataset_version_id="dataset-1",
        artifact_hash=hashlib.sha256(checkpoint.read_bytes()).hexdigest(),
        artifact_uri=str(checkpoint),
        metrics_json=json.dumps({"source_schema": "cogguard.botrhg.account.v3"}),
        gates_json="{}",
        status="active",
        created_by=1,
    )

    with pytest.raises(AppException, match="deployable account model bundle"):
        asyncio.run(resolve_active_account_model(session))


def test_active_pointer_resolution_preserves_identity_for_an_invalid_bundle(tmp_path):
    checkpoint = tmp_path / "detector.pt"
    checkpoint.write_bytes(b"detector")
    artifact_hash = hashlib.sha256(checkpoint.read_bytes()).hexdigest()
    session = _RuntimeSession()
    session.activation = AccountDetectionModelActivation(
        model_family="chinese_account_detection",
        model_version="model-invalid",
        pointer_revision=7,
        activation_json="{}",
        activated_by=1,
    )
    session.model = AccountDetectionModelVersion(
        model_version="model-invalid",
        dataset_version_id="dataset-1",
        artifact_hash=artifact_hash,
        artifact_uri=str(checkpoint),
        metrics_json=json.dumps({"source_schema": "cogguard.botrhg.account.v3"}),
        gates_json="{}",
        status="active",
        created_by=1,
    )

    resolution = asyncio.run(
        account_model_runtime_service.resolve_active_account_model_resolution(session)
    )

    assert resolution.status == "invalid"
    assert resolution.model is None
    assert resolution.model_version == "model-invalid"
    assert resolution.artifact_hash == artifact_hash
    assert resolution.pointer_revision == 7
    assert resolution.reason == "active_model_bundle_invalid"


def test_production_rejects_local_bootstrap_mode():
    with pytest.raises(ValueError, match="ACCOUNT_MODEL_BOOTSTRAP_MODE"):
        _production_settings(ACCOUNT_MODEL_BOOTSTRAP_MODE="local_legacy")


def test_account_model_examples_document_production_governance_gates():
    system_root = Path(__file__).resolve().parents[2]
    production_example = (system_root / ".env.example").read_text(encoding="utf-8")
    local_example = (system_root / "backend" / ".env.example").read_text(encoding="utf-8")
    readme = (system_root / "README.md").read_text(encoding="utf-8")

    assert "ACCOUNT_MODEL_EVALUATION_HMAC_SECRET=" in production_example
    assert "ACCOUNT_MODEL_BOOTSTRAP_MODE=disabled" in production_example
    assert "ACCOUNT_MODEL_EVALUATION_HMAC_SECRET=" in local_example
    assert "ACCOUNT_MODEL_BOOTSTRAP_MODE=local_legacy" in local_example
    assert "ACCOUNT_MODEL_EVALUATION_HMAC_SECRET" in readme
    assert "ACCOUNT_MODEL_BOOTSTRAP_MODE=disabled" in readme


def test_production_without_pre_governed_pointer_fails_closed(monkeypatch, tmp_path):
    checkpoint = tmp_path / "checkpoint.pt"
    checkpoint.write_bytes(b"legacy-checkpoint")
    monkeypatch.setattr(settings, "BACKEND_ENV", "production")
    monkeypatch.setattr(settings, "BOTRHG_CHECKPOINT_PATH", str(checkpoint))
    monkeypatch.setattr(settings, "ACCOUNT_MODEL_BOOTSTRAP_MODE", "local_legacy", raising=False)
    session = _RuntimeSession()

    result = asyncio.run(resolve_active_account_model(session))

    assert result is None
    assert session.model is None
    assert session.activation is None
    assert session.decisions == []


def test_local_bootstrap_is_explicitly_unreviewed(monkeypatch, tmp_path):
    checkpoint = tmp_path / "checkpoint.pt"
    checkpoint.write_bytes(b"legacy-checkpoint")
    monkeypatch.setattr(settings, "BACKEND_ENV", "local")
    monkeypatch.setattr(settings, "BOTRHG_CHECKPOINT_PATH", str(checkpoint))
    monkeypatch.setattr(settings, "ACCOUNT_MODEL_BOOTSTRAP_MODE", "local_legacy", raising=False)
    session = _RuntimeSession()

    result = asyncio.run(resolve_active_account_model(session))

    assert result is not None
    assert result.governance_status == "local_bootstrap_unreviewed"
    assert result.research_approved is False
    assert session.model.status == "local_bootstrap"
    activation = json.loads(session.activation.activation_json)
    assert activation["research_approved"] is False
    assert activation["production_eligible"] is False
    decision = json.loads(session.decisions[0].decision_json)
    assert decision["governance_status"] == "local_bootstrap_unreviewed"


def test_local_bootstrap_is_disabled_without_explicit_mode(monkeypatch, tmp_path):
    checkpoint = tmp_path / "checkpoint.pt"
    checkpoint.write_bytes(b"legacy-checkpoint")
    monkeypatch.setattr(settings, "BACKEND_ENV", "local")
    monkeypatch.setattr(settings, "BOTRHG_CHECKPOINT_PATH", str(checkpoint))
    monkeypatch.setattr(settings, "ACCOUNT_MODEL_BOOTSTRAP_MODE", "disabled", raising=False)

    result = asyncio.run(resolve_active_account_model(_RuntimeSession()))

    assert result is None


def test_production_rejects_a_persisted_local_bootstrap_pointer(monkeypatch, tmp_path):
    checkpoint = tmp_path / "checkpoint.pt"
    checkpoint.write_bytes(b"legacy-checkpoint")
    monkeypatch.setattr(settings, "BACKEND_ENV", "local")
    monkeypatch.setattr(settings, "BOTRHG_CHECKPOINT_PATH", str(checkpoint))
    monkeypatch.setattr(settings, "ACCOUNT_MODEL_BOOTSTRAP_MODE", "local_legacy", raising=False)
    session = _RuntimeSession()
    asyncio.run(resolve_active_account_model(session))
    monkeypatch.setattr(settings, "BACKEND_ENV", "production")

    with pytest.raises(AppException, match="local bootstrap"):
        asyncio.run(resolve_active_account_model(session))
