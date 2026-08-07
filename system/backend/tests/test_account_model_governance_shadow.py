from __future__ import annotations

import asyncio
import hashlib
import json
import importlib.util
import sys

import pytest

from app.config import settings
from app.models.account_labeling import (
    AccountDetectionDatasetVersion,
    AccountDetectionModelActivation,
    AccountDetectionModelApproval,
    AccountDetectionModelVersion,
    AccountModelEvaluationRun,
    AccountModelGovernanceDecision,
    AccountMonitorSnapshot,
    AccountPredictionAudit,
)
from app.services import account_model_governance_service as governance
from app.services.account_model_governance_service import (
    register_account_training_candidate,
    write_account_model_evaluation,
)
from app.utils.exceptions import AppException


def test_failed_evaluation_package_import_does_not_leave_a_partial_module(monkeypatch):
    class FailingLoader:
        def create_module(self, _spec):
            return None

        def exec_module(self, _module):
            raise ImportError("transient import failure")

    spec = importlib.util.spec_from_loader(governance._EVALUATION_PACKAGE_NAME, FailingLoader(), is_package=True)
    monkeypatch.delitem(sys.modules, governance._EVALUATION_PACKAGE_NAME, raising=False)
    monkeypatch.setattr(importlib.util, "spec_from_file_location", lambda *_args, **_kwargs: spec)

    with pytest.raises(ImportError, match="transient"):
        governance._load_evaluation_package()

    assert governance._EVALUATION_PACKAGE_NAME not in sys.modules


_EVALUATOR_SECRET = "test-account-model-evaluator-secret-with-at-least-32-bytes"


class _Result:
    def __init__(self, *, scalar=None, rows=()):
        self.scalar = scalar
        self.rows = list(rows)

    def scalar_one_or_none(self):
        return self.scalar

    def scalars(self):
        return self

    def all(self):
        return self.rows


class _ShadowSession:
    def __init__(self, dataset):
        self.dataset = dataset
        self.model = None
        self.audits = []
        self.snapshots = []
        self.approvals = []
        self.evaluations = []

    async def execute(self, statement):
        entity = statement.column_descriptions[0].get("entity")
        parameter_values = set(statement.compile().params.values())
        if entity is AccountDetectionDatasetVersion:
            return _Result(scalar=self.dataset)
        if entity is AccountDetectionModelVersion:
            return _Result(scalar=self.model)
        if entity is AccountPredictionAudit:
            match = next((row for row in self.audits if row.audit_id in parameter_values), None)
            return _Result(scalar=match, rows=self.audits)
        if entity is AccountMonitorSnapshot:
            match = next((row for row in self.snapshots if row.snapshot_id in parameter_values), None)
            return _Result(scalar=match, rows=self.snapshots)
        if entity is AccountDetectionModelApproval:
            return _Result(rows=self.approvals)
        if entity is AccountModelEvaluationRun:
            match = next(
                (
                    row
                    for row in self.evaluations
                    if row.evaluation_run_id in parameter_values
                ),
                None,
            )
            return _Result(scalar=match, rows=self.evaluations)
        raise AssertionError(f"Unexpected entity: {entity}")

    def add(self, value):
        if isinstance(value, AccountDetectionModelVersion):
            self.model = value
        elif isinstance(value, AccountPredictionAudit):
            self.audits.append(value)
        elif isinstance(value, AccountMonitorSnapshot):
            self.snapshots.append(value)
        elif isinstance(value, AccountDetectionModelApproval):
            self.approvals.append(value)
        elif isinstance(value, AccountModelEvaluationRun):
            self.evaluations.append(value)

    async def flush(self):
        return None

    async def refresh(self, _value, attribute_names=None):
        return None


class _ActivationSession:
    def __init__(self, model):
        self.model = model
        self.candidate_lock_requested = False
        self.pointer_lock_requested = False
        self.added = []

    async def execute(self, statement):
        entity = statement.column_descriptions[0].get("entity")
        if entity is AccountDetectionModelVersion:
            self.candidate_lock_requested = statement._for_update_arg is not None
            return _Result(scalar=self.model)
        if entity is AccountDetectionModelActivation:
            self.pointer_lock_requested = statement._for_update_arg is not None
            return _Result(scalar=None)
        raise AssertionError(f"Unexpected entity: {entity}")

    def add(self, value):
        self.added.append(value)

    async def refresh(self, value, attribute_names=None):
        value.metrics_json = json.dumps({"changed_during_activation": True})

    async def flush(self):
        return None


class _StableActivationSession(_ShadowSession):
    def __init__(self, model, evaluations, audits):
        super().__init__(AccountDetectionDatasetVersion(
            dataset_version_id="unused",
            data_fingerprint="d" * 64,
            source_label_count=1,
            artifact_uri=".",
            manifest_json="{}",
            status="candidate",
            created_by=1,
        ))
        self.model = model
        self.evaluations = evaluations
        self.audits = audits
        self.pointer_lock_requested = False
        self.added = []

    async def execute(self, statement):
        entity = statement.column_descriptions[0].get("entity")
        if entity is AccountDetectionModelVersion:
            return _Result(scalar=self.model)
        if entity is AccountModelEvaluationRun:
            parameter_values = set(statement.compile().params.values())
            return _Result(
                scalar=next(
                    (row for row in self.evaluations if row.evaluation_run_id in parameter_values),
                    None,
                )
            )
        if entity is AccountPredictionAudit:
            return _Result(rows=self.audits)
        if entity is AccountDetectionModelActivation:
            self.pointer_lock_requested = statement._for_update_arg is not None
            return _Result(scalar=None)
        raise AssertionError(f"Unexpected entity: {entity}")

    def add(self, value):
        self.added.append(value)

    async def refresh(self, _value, attribute_names=None):
        return None


class _RollbackSession:
    def __init__(self, model):
        self.model = model
        self.pointer = None
        self.target_lock_requested = False

    async def execute(self, statement):
        entity = statement.column_descriptions[0].get("entity")
        if entity is AccountDetectionModelVersion:
            self.target_lock_requested = statement._for_update_arg is not None
            return _Result(scalar=self.model)
        if entity is AccountDetectionModelActivation:
            return _Result(scalar=self.pointer)
        raise AssertionError(f"Unexpected entity: {entity}")

    def add(self, _value):
        return None

    async def flush(self):
        return None


@pytest.fixture(autouse=True)
def _configured_evaluator_secret(monkeypatch):
    monkeypatch.setattr(settings, "ACCOUNT_MODEL_EVALUATION_HMAC_SECRET", _EVALUATOR_SECRET, raising=False)


def _signed_manifest(candidate, evaluation_run_id, prediction_audits, *, evaluation_protocol=None):
    return governance.sign_account_model_evaluation_manifest(
        model_version=candidate["model_version"],
        artifact_hash=candidate["artifact_hash"],
        evaluation_run_id=evaluation_run_id,
        prediction_audits=prediction_audits,
        evaluation_protocol=evaluation_protocol,
        secret=_EVALUATOR_SECRET,
    )


async def _candidate(tmp_path, *, model_version: str = "shadow-detector-1"):
    artifact = tmp_path / f"{model_version}.pt"
    artifact.write_bytes(b"shadow-checkpoint")
    dataset = AccountDetectionDatasetVersion(
        dataset_version_id=f"{model_version}-dataset",
        data_fingerprint="d" * 64,
        source_label_count=3,
        artifact_uri=str(tmp_path),
        manifest_json="{}",
        status="candidate",
        created_by=1,
    )
    session = _ShadowSession(dataset)
    candidate = await register_account_training_candidate(
        session,
        model_version=model_version,
        dataset_version_id=dataset.dataset_version_id,
        artifact_uri=str(artifact),
        artifact_hash=hashlib.sha256(b"shadow-checkpoint").hexdigest(),
        metrics={
            "shadow_run_passed": True,
            "false_positive_burden_passed": True,
            "evaluation_protocol": {"schema": "caller-controlled"},
            "ece": 0.0,
            "calibration": {"passed": True, "ece": 0.0},
            "training_note": "caller supplied only",
        },
        operator_id=1,
    )
    return session, artifact, candidate


def test_candidate_registration_is_idempotent_and_caller_cannot_assert_shadow_gates(tmp_path):
    async def scenario():
        session, artifact, candidate = await _candidate(tmp_path)
        repeated = await register_account_training_candidate(
            session,
            model_version=candidate["model_version"],
            dataset_version_id=candidate["dataset_version_id"],
            artifact_uri=str(artifact),
            artifact_hash=candidate["artifact_hash"],
            metrics={"shadow_run_passed": True, "false_positive_burden_passed": True},
            operator_id=1,
        )
        return candidate, repeated

    candidate, repeated = asyncio.run(scenario())
    assert repeated["model_version"] == candidate["model_version"]
    assert repeated["metrics"]["training_note"] == "caller supplied only"
    assert "evaluation_protocol" not in repeated["metrics"]
    assert "ece" not in repeated["metrics"]
    assert "calibration" not in repeated["metrics"]
    assert repeated["gates"]["gates"]["calibration"] is False
    assert repeated["gates"]["gates"]["shadow_run"] is False
    assert repeated["gates"]["gates"]["false_positive_burden"] is False


def test_evaluator_writeback_derives_version_hash_and_run_bound_shadow_gates(tmp_path):
    async def scenario():
        session, _artifact, candidate = await _candidate(tmp_path)
        audits = [
            {
                "account_id": "account-1",
                "platform": "weibo",
                "input_fingerprint": "a" * 64,
                "probability": 1.0,
                "target": 1,
                "latency_ms": 12.0,
            },
        ]
        return await write_account_model_evaluation(
            session,
            model_version=candidate["model_version"],
            artifact_hash=candidate["artifact_hash"],
            evaluation_run_id="evaluation-run-1",
            prediction_audits=audits,
            evaluation_manifest=_signed_manifest(candidate, "evaluation-run-1", audits),
        )

    result = asyncio.run(scenario())
    assert result is not None
    provenance = result["metrics"]["shadow_evaluation"]
    assert provenance["evaluation_run_id"] == "evaluation-run-1"
    assert provenance["model_version"] == "shadow-detector-1"
    assert provenance["artifact_hash"] == hashlib.sha256(b"shadow-checkpoint").hexdigest()
    assert len(provenance["evaluation_fingerprint"]) == 64
    assert len(provenance["audit_fingerprint"]) == 64
    assert result["gates"]["gates"]["shadow_run"] is True
    assert result["gates"]["gates"]["false_positive_burden"] is True


def test_unsigned_or_forged_evaluator_writeback_is_rejected(tmp_path):
    async def scenario():
        session, _artifact, candidate = await _candidate(tmp_path)
        signed_audits = [
            {
                "account_id": "account-1",
                "platform": "weibo",
                "input_fingerprint": "a" * 64,
                "probability": 0.1,
                "target": 0,
            }
        ]
        favorable_audits = [{**signed_audits[0], "probability": 1.0, "target": 1}]
        with pytest.raises(AppException, match="signed evaluator manifest"):
            await write_account_model_evaluation(
                session,
                model_version=candidate["model_version"],
                artifact_hash=candidate["artifact_hash"],
                evaluation_run_id="unsigned-run",
                prediction_audits=favorable_audits,
                evaluation_manifest=None,
            )
        with pytest.raises(AppException, match="manifest"):
            await write_account_model_evaluation(
                session,
                model_version=candidate["model_version"],
                artifact_hash=candidate["artifact_hash"],
                evaluation_run_id="forged-run",
                prediction_audits=favorable_audits,
                evaluation_manifest=_signed_manifest(candidate, "forged-run", signed_audits),
            )

    asyncio.run(scenario())


def test_evaluation_run_replay_is_order_independent_idempotent_and_conflict_safe(tmp_path):
    async def scenario():
        session, _artifact, candidate = await _candidate(tmp_path)
        audits = [
            {
                "account_id": "account-2",
                "platform": "weibo",
                "input_fingerprint": "b" * 64,
                "probability": 0.2,
                "target": 0,
            },
            {
                "account_id": "account-1",
                "platform": "weibo",
                "input_fingerprint": "a" * 64,
                "probability": 0.9,
                "target": 1,
            },
        ]
        first_manifest = _signed_manifest(candidate, "replay-safe-run", audits)
        reversed_manifest = _signed_manifest(candidate, "replay-safe-run", list(reversed(audits)))
        assert reversed_manifest == first_manifest
        first = await write_account_model_evaluation(
            session,
            model_version=candidate["model_version"],
            artifact_hash=candidate["artifact_hash"],
            evaluation_run_id="replay-safe-run",
            prediction_audits=audits,
            evaluation_manifest=first_manifest,
        )
        repeated = await write_account_model_evaluation(
            session,
            model_version=candidate["model_version"],
            artifact_hash=candidate["artifact_hash"],
            evaluation_run_id="replay-safe-run",
            prediction_audits=list(reversed(audits)),
            evaluation_manifest=reversed_manifest,
        )
        changed_audits = [{**audits[0], "probability": 0.99}, audits[1]]
        with pytest.raises(AppException, match="conflicts with immutable evaluator evidence"):
            await write_account_model_evaluation(
                session,
                model_version=candidate["model_version"],
                artifact_hash=candidate["artifact_hash"],
                evaluation_run_id="replay-safe-run",
                prediction_audits=changed_audits,
                evaluation_manifest=_signed_manifest(candidate, "replay-safe-run", changed_audits),
            )
        return session, first, repeated

    session, first, repeated = asyncio.run(scenario())
    assert first is not None and repeated is not None
    assert first["metrics"]["shadow_evaluation"] == repeated["metrics"]["shadow_evaluation"]
    assert len(session.evaluations) == 1
    assert len(session.audits) == 2
    assert len(session.snapshots) == 1
    assert session.evaluations[0].evaluation_fingerprint == first["metrics"]["shadow_evaluation"]["evaluation_fingerprint"]
    assert session.evaluations[0].audit_fingerprint == first["metrics"]["shadow_evaluation"]["audit_fingerprint"]


def test_evaluation_run_id_cannot_be_reused_by_another_candidate(tmp_path):
    async def scenario():
        session, _artifact, candidate = await _candidate(tmp_path)
        audits = [
            {
                "account_id": "account-1",
                "platform": "weibo",
                "input_fingerprint": "a" * 64,
                "probability": 1.0,
                "target": 1,
            }
        ]
        await write_account_model_evaluation(
            session,
            model_version=candidate["model_version"],
            artifact_hash=candidate["artifact_hash"],
            evaluation_run_id="globally-owned-run",
            prediction_audits=audits,
            evaluation_manifest=_signed_manifest(candidate, "globally-owned-run", audits),
        )
        other_artifact = tmp_path / "other.pt"
        other_artifact.write_bytes(b"other-checkpoint")
        other_hash = hashlib.sha256(b"other-checkpoint").hexdigest()
        other = {
            "model_version": "shadow-detector-2",
            "artifact_hash": other_hash,
        }
        session.model = AccountDetectionModelVersion(
            model_version=other["model_version"],
            dataset_version_id="other-dataset",
            artifact_uri=str(other_artifact),
            artifact_hash=other_hash,
            metrics_json="{}",
            gates_json="{}",
            status="shadow",
            created_by=1,
        )
        with pytest.raises(AppException, match="already belongs to another candidate"):
            await write_account_model_evaluation(
                session,
                model_version=other["model_version"],
                artifact_hash=other_hash,
                evaluation_run_id="globally-owned-run",
                prediction_audits=audits,
                evaluation_manifest=_signed_manifest(other, "globally-owned-run", audits),
            )

    asyncio.run(scenario())


def test_failed_evaluator_gates_and_changed_metrics_invalidate_approvals(tmp_path):
    async def scenario():
        session, _artifact, candidate = await _candidate(tmp_path)
        first_manifest = _signed_manifest(candidate, "evaluation-run-1", [])
        failed = await write_account_model_evaluation(
            session,
            model_version=candidate["model_version"],
            artifact_hash=candidate["artifact_hash"],
            evaluation_run_id="evaluation-run-1",
            prediction_audits=[],
            evaluation_manifest=first_manifest,
        )
        session.model.status = "approved"
        session.add(
            AccountDetectionModelApproval(
                approval_id="approval-1",
                model_version=candidate["model_version"],
                approver_id=1,
                artifact_hash=candidate["artifact_hash"],
                metrics_fingerprint="stale",
            )
        )
        changed = await write_account_model_evaluation(
            session,
            model_version=candidate["model_version"],
            artifact_hash=candidate["artifact_hash"],
            evaluation_run_id="evaluation-run-2",
            prediction_audits=[],
            evaluation_manifest=_signed_manifest(candidate, "evaluation-run-2", []),
        )
        return failed, changed

    failed, changed = asyncio.run(scenario())
    assert failed is not None and failed["gates"]["gates"]["shadow_run"] is False
    assert failed["gates"]["gates"]["false_positive_burden"] is False
    assert changed is not None and changed["approval_invalidated_count"] == 1
    assert changed["status"] == "shadow"


def test_activation_locks_candidate_and_rechecks_metrics_before_pointer_update(monkeypatch, tmp_path):
    artifact = tmp_path / "activation.pt"
    artifact.write_bytes(b"activation-checkpoint")
    artifact_hash = hashlib.sha256(b"activation-checkpoint").hexdigest()
    model = AccountDetectionModelVersion(
        model_version="activation-lock-model",
        dataset_version_id="dataset-1",
        artifact_uri=str(artifact),
        artifact_hash=artifact_hash,
        metrics_json=json.dumps({"stable": True}),
        gates_json="{}",
        status="approved",
        created_by=1,
    )
    session = _ActivationSession(model)

    async def require_admin(_session, _operator_id):
        return None

    async def approvals(_session, **_kwargs):
        return [1, 2]

    async def verify_evidence(_session, **_kwargs):
        return None

    monkeypatch.setattr(governance, "_require_active_admin", require_admin)
    monkeypatch.setattr(governance, "_active_model_approval_ids", approvals)
    monkeypatch.setattr(governance, "_verify_persisted_evaluation_evidence", verify_evidence, raising=False)
    monkeypatch.setattr(governance, "_verify_artifact_hash", lambda *_args, **_kwargs: artifact_hash)
    monkeypatch.setattr(
        governance,
        "evaluate_account_model_activation_gates",
        lambda *_args, **_kwargs: {"activation_allowed": True, "gates": {}},
    )

    with pytest.raises(AppException, match="metrics changed"):
        asyncio.run(
            governance.activate_account_detection_model(
                session,
                model_version=model.model_version,
                operator_id=1,
            )
        )

    assert session.candidate_lock_requested is True
    assert session.pointer_lock_requested is False
    assert not any(isinstance(value, AccountModelGovernanceDecision) for value in session.added)


def test_activation_rejects_a_tampered_persisted_evaluator_manifest(monkeypatch, tmp_path):
    async def scenario():
        shadow_session, _artifact, candidate = await _candidate(tmp_path)
        audits = [
            {
                "account_id": "account-1",
                "platform": "weibo",
                "input_fingerprint": "a" * 64,
                "probability": 1.0,
                "target": 1,
            }
        ]
        await write_account_model_evaluation(
            shadow_session,
            model_version=candidate["model_version"],
            artifact_hash=candidate["artifact_hash"],
            evaluation_run_id="tampered-manifest-run",
            prediction_audits=audits,
            evaluation_manifest=_signed_manifest(candidate, "tampered-manifest-run", audits),
        )
        shadow_session.model.status = "approved"
        persisted_manifest = json.loads(shadow_session.evaluations[0].manifest_json)
        persisted_manifest["signature_sha256"] = "0" * 64
        shadow_session.evaluations[0].manifest_json = json.dumps(persisted_manifest)
        session = _StableActivationSession(
            shadow_session.model,
            shadow_session.evaluations,
            shadow_session.audits,
        )

        async def require_admin(_session, _operator_id):
            return None

        async def approvals(_session, **_kwargs):
            return [1, 2]

        monkeypatch.setattr(governance, "_require_active_admin", require_admin)
        monkeypatch.setattr(governance, "_active_model_approval_ids", approvals)
        monkeypatch.setattr(
            governance,
            "_verify_artifact_hash",
            lambda *_args, **_kwargs: candidate["artifact_hash"],
        )
        monkeypatch.setattr(
            governance,
            "evaluate_account_model_activation_gates",
            lambda *_args, **_kwargs: {"activation_allowed": True, "gates": {}},
        )
        with pytest.raises(AppException, match="signature"):
            await governance.activate_account_detection_model(
                session,
                model_version=candidate["model_version"],
                operator_id=1,
            )
        return session

    session = asyncio.run(scenario())
    assert session.pointer_lock_requested is False
    assert not any(isinstance(value, AccountModelGovernanceDecision) for value in session.added)


def test_rollback_cannot_activate_an_approved_candidate(monkeypatch, tmp_path):
    artifact = tmp_path / "approved-only.pt"
    artifact.write_bytes(b"approved-only")
    target = AccountDetectionModelVersion(
        model_version="approved-only",
        dataset_version_id="dataset-1",
        artifact_uri=str(artifact),
        artifact_hash=hashlib.sha256(b"approved-only").hexdigest(),
        metrics_json="{}",
        gates_json="{}",
        status="approved",
        created_by=1,
    )
    session = _RollbackSession(target)

    async def require_admin(_session, _operator_id):
        return None

    monkeypatch.setattr(governance, "_require_active_admin", require_admin)

    with pytest.raises(AppException, match="previously governed active or retired"):
        asyncio.run(
            governance.rollback_account_detection_model(
                session,
                model_version=target.model_version,
                operator_id=1,
                reason="operator requested rollback",
            )
        )

    assert session.target_lock_requested is True
