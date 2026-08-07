from __future__ import annotations

import asyncio
import json
from datetime import datetime

import pytest

from app.models.account_labeling import (
    AccountDetectionModelActivation,
    AccountDetectionModelVersion,
    AccountModelGovernanceDecision,
    AccountMonitorSnapshot,
)
from app.services import account_model_governance_service as governance
from app.utils.exceptions import AppException


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


class _AutomaticRollbackSession:
    def __init__(
        self,
        *,
        snapshot,
        pointer,
        source,
        target,
        prior_snapshots=(),
        reject_overlapping_predecessor_filter=False,
    ):
        self.snapshot = snapshot
        self.pointer = pointer
        self.source = source
        self.unlocked_source = source
        self.locked_source = source
        self.models = {
            pointer.model_version: AccountDetectionModelVersion(
                model_version=pointer.model_version,
                dataset_version_id="dataset-current",
                artifact_uri="current-bundle",
                artifact_hash="a" * 64,
                metrics_json="{}",
                gates_json="{}",
                status="active",
                created_by=1,
            ),
            target.model_version: target,
        }
        self.decisions = [source]
        self.added = []
        self.snapshot_queries = 0
        self.prior_snapshots = list(prior_snapshots)
        self.reject_overlapping_predecessor_filter = reject_overlapping_predecessor_filter
        self.lock_sequence = []

    async def execute(self, statement):
        entity = statement.column_descriptions[0].get("entity")
        parameters = {
            item
            for value in statement.compile().params.values()
            for item in (value if isinstance(value, (list, tuple, set)) else (value,))
        }
        if statement._for_update_arg is not None:
            self.lock_sequence.append((entity, parameters))
        if entity is AccountMonitorSnapshot:
            self.snapshot_queries += 1
            if self.snapshot_queries == 1:
                return _Result(scalar=self.snapshot)
            if self.reject_overlapping_predecessor_filter and "window_finished_at <=" in str(statement):
                return _Result(rows=[])
            return _Result(rows=self.prior_snapshots)
        if entity is AccountDetectionModelActivation:
            return _Result(scalar=self.pointer)
        if entity is AccountDetectionModelVersion:
            model_version = next(
                (value for value in parameters if value in self.models),
                self.pointer.model_version,
            )
            return _Result(scalar=self.models[model_version])
        if entity is AccountModelGovernanceDecision:
            source_revisions = {
                int(self.source.pointer_revision),
                int(self.unlocked_source.pointer_revision),
                int(self.locked_source.pointer_revision),
            }
            if source_revisions.intersection(parameters):
                source = self.locked_source if statement._for_update_arg is not None else self.unlocked_source
                return _Result(scalar=source)
            return _Result(rows=self.decisions)
        raise AssertionError(f"Unexpected entity: {entity}")

    def add(self, value):
        self.added.append(value)
        if isinstance(value, AccountModelGovernanceDecision):
            self.decisions.append(value)

    async def flush(self):
        return None


def _snapshot(*, snapshot_id="snapshot-1", record_id=2):
    return AccountMonitorSnapshot(
        id=record_id,
        snapshot_id=snapshot_id,
        family="chinese_account_detection",
        model_version="current-model",
        pointer_revision=4,
        window_started_at=datetime(2026, 8, 7, 9, 0, 0),
        window_finished_at=datetime(2026, 8, 7, 9, 5, 0),
        status="hard_failure",
        metrics_json=json.dumps(
            {
                "automatic_rollback_allowed": True,
                "hard_error_reason_counts": {"active_model_bundle_invalid": 1},
                "model_identity": {
                    "family": "chinese_account_detection",
                    "model_version": "current-model",
                    "artifact_hash": "a" * 64,
                    "pointer_revision": 4,
                },
            }
        ),
    )


def _active_pointer(*, model_version="current-model", revision=4):
    return AccountDetectionModelActivation(
        model_family="chinese_account_detection",
        model_version=model_version,
        pointer_revision=revision,
        activation_json="{}",
        activated_by=9,
    )


def _source_decision(*, model_version="current-model", previous_model_version="approved-previous-model", revision=4):
    return AccountModelGovernanceDecision(
        decision_id=f"activation-{model_version}",
        family="chinese_account_detection",
        model_version=model_version,
        previous_model_version=previous_model_version,
        pointer_revision=revision,
        decision_type="activation",
        decision_json="{}",
        decided_by=9,
    )


def _target(*, model_version="approved-previous-model", status="retired"):
    return AccountDetectionModelVersion(
        model_version=model_version,
        dataset_version_id="dataset-previous",
        artifact_uri="previous-bundle",
        artifact_hash="b" * 64,
        metrics_json="{}",
        gates_json="{}",
        status=status,
        created_by=1,
    )


def _record_target_activation(session, target):
    session.decisions.append(
        AccountModelGovernanceDecision(
            decision_id=f"activation-{target.model_version}",
            family="chinese_account_detection",
            model_version=target.model_version,
            previous_model_version="older-model",
            pointer_revision=3,
            decision_type="activation",
            decision_json="{}",
            decided_by=8,
        )
    )


def _allow_verified_target(monkeypatch, *, approvals=(11, 12)):
    async def active_approvals(_session, **_kwargs):
        return list(approvals)

    async def verified_evaluation(_session, **_kwargs):
        return None

    monkeypatch.setattr(governance, "_active_model_approval_ids", active_approvals)
    monkeypatch.setattr(governance, "_verify_persisted_evaluation_evidence", verified_evaluation)
    monkeypatch.setattr(governance, "_verify_artifact_hash", lambda *_args, **_kwargs: "b" * 64)
    monkeypatch.setattr(
        governance,
        "evaluate_account_model_activation_gates",
        lambda *_args, **_kwargs: {"activation_allowed": True, "gates": {"dual_approval": True}},
    )


@pytest.mark.parametrize(
    "reason",
    ["active_model_bundle_invalid", "account_model_runtime_load_failure"],
)
def test_immediate_runtime_failure_restores_only_the_source_decisions_previous_model(monkeypatch, reason):
    snapshot = _snapshot()
    snapshot_metrics = json.loads(snapshot.metrics_json)
    snapshot_metrics["hard_error_reason_counts"] = {reason: 1}
    snapshot.metrics_json = json.dumps(snapshot_metrics)
    pointer = _active_pointer()
    source = _source_decision()
    target = _target()
    session = _AutomaticRollbackSession(snapshot=snapshot, pointer=pointer, source=source, target=target)
    shadow = _target(model_version="unrelated-shadow-candidate", status="shadow")
    session.models[shadow.model_version] = shadow
    _record_target_activation(session, target)

    _allow_verified_target(monkeypatch)

    attempt = getattr(governance, "attempt_automatic_account_model_rollback", None)
    assert attempt is not None, "automatic rollback must be driven by a persisted monitor snapshot"

    result = asyncio.run(attempt(session, snapshot_id=snapshot.snapshot_id))

    assert result["status"] == "rolled_back"
    assert result["reason_category"] == reason
    assert pointer.model_version == "approved-previous-model"
    assert pointer.pointer_revision == 5
    decision = next(value for value in session.added if isinstance(value, AccountModelGovernanceDecision))
    assert decision.decision_type == "automatic_rollback"
    assert decision.decided_by == 0
    assert decision.model_version == "approved-previous-model"
    assert decision.previous_model_version == "current-model"
    assert decision.pointer_revision == 5
    payload = json.loads(decision.decision_json)
    assert payload["triggering_snapshot_id"] == snapshot.snapshot_id
    assert payload["reason_category"] == reason
    assert shadow.status == "shadow"
    assert source in session.decisions
    assert len([row for row in session.decisions if row.decision_type == "automatic_rollback"]) == 1


def test_sustained_non_immediate_hard_errors_require_two_consecutive_snapshots(monkeypatch):
    snapshot = _snapshot()
    metrics = json.loads(snapshot.metrics_json)
    metrics["hard_error_reason_counts"] = {"other_runtime_failure": 1}
    snapshot.metrics_json = json.dumps(metrics)
    previous = _snapshot(snapshot_id="snapshot-previous")
    previous.window_started_at = datetime(2026, 8, 7, 8, 50, 0)
    previous.window_finished_at = snapshot.window_started_at
    previous_metrics = json.loads(previous.metrics_json)
    previous_metrics["hard_error_reason_counts"] = {"other_runtime_failure": 2}
    previous.metrics_json = json.dumps(previous_metrics)
    pointer = _active_pointer()
    source = _source_decision()
    target = _target()
    session = _AutomaticRollbackSession(
        snapshot=snapshot,
        pointer=pointer,
        source=source,
        target=target,
        prior_snapshots=[previous],
    )
    _record_target_activation(session, target)
    _allow_verified_target(monkeypatch)

    result = asyncio.run(
        governance.attempt_automatic_account_model_rollback(session, snapshot_id=snapshot.snapshot_id)
    )

    assert result["status"] == "rolled_back"
    assert result["reason_category"] == "sustained_hard_error_budget"


def test_automatic_rollback_locks_target_before_pointer_and_rechecks_the_source_decision(monkeypatch):
    snapshot = _snapshot()
    pointer = _active_pointer()
    source = _source_decision()
    target = _target()
    session = _AutomaticRollbackSession(snapshot=snapshot, pointer=pointer, source=source, target=target)
    _record_target_activation(session, target)
    _allow_verified_target(monkeypatch)

    result = asyncio.run(
        governance.attempt_automatic_account_model_rollback(session, snapshot_id=snapshot.snapshot_id)
    )

    assert result["status"] == "rolled_back"
    assert [entity for entity, _parameters in session.lock_sequence[:4]] == [
        AccountDetectionModelVersion,
        AccountDetectionModelActivation,
        AccountDetectionModelVersion,
        AccountModelGovernanceDecision,
    ]
    assert target.model_version in session.lock_sequence[0][1]
    assert source.model_version in session.lock_sequence[2][1]
    assert source.pointer_revision in session.lock_sequence[3][1]


def test_sustained_failure_uses_the_immediate_overlapping_predecessor(monkeypatch):
    snapshot = _snapshot(record_id=3)
    metrics = json.loads(snapshot.metrics_json)
    metrics["hard_error_reason_counts"] = {"other_runtime_failure": 1}
    snapshot.metrics_json = json.dumps(metrics)
    previous = _snapshot(snapshot_id="snapshot-overlapping", record_id=2)
    previous.window_started_at = datetime(2026, 8, 7, 8, 58, 0)
    previous.window_finished_at = datetime(2026, 8, 7, 9, 2, 0)
    previous_metrics = json.loads(previous.metrics_json)
    previous_metrics["hard_error_reason_counts"] = {"other_runtime_failure": 1}
    previous.metrics_json = json.dumps(previous_metrics)
    pointer = _active_pointer()
    source = _source_decision()
    target = _target()
    session = _AutomaticRollbackSession(
        snapshot=snapshot,
        pointer=pointer,
        source=source,
        target=target,
        prior_snapshots=[previous],
        reject_overlapping_predecessor_filter=True,
    )
    _record_target_activation(session, target)
    _allow_verified_target(monkeypatch)

    result = asyncio.run(
        governance.attempt_automatic_account_model_rollback(session, snapshot_id=snapshot.snapshot_id)
    )

    assert result["status"] == "rolled_back"
    assert result["reason_category"] == "sustained_hard_error_budget"


def test_automatic_rollback_rechecks_the_locked_source_decision_before_updating_the_pointer(monkeypatch):
    snapshot = _snapshot()
    pointer = _active_pointer()
    source = _source_decision()
    target = _target()
    session = _AutomaticRollbackSession(snapshot=snapshot, pointer=pointer, source=source, target=target)
    session.locked_source = AccountModelGovernanceDecision(
        decision_id=source.decision_id,
        family=source.family,
        model_version=source.model_version,
        previous_model_version="changed-target",
        pointer_revision=source.pointer_revision,
        decision_type=source.decision_type,
        decision_json=source.decision_json,
        decided_by=source.decided_by,
    )
    _record_target_activation(session, target)
    _allow_verified_target(monkeypatch)

    result = asyncio.run(
        governance.attempt_automatic_account_model_rollback(session, snapshot_id=snapshot.snapshot_id)
    )

    assert result == {
        "status": "no_op",
        "reason": "source_decision_changed",
        "snapshot_id": snapshot.snapshot_id,
    }
    assert pointer.model_version == source.model_version
    assert pointer.pointer_revision == source.pointer_revision
    assert target.status == "retired"
    assert session.added == []


@pytest.mark.parametrize("predecessor_state", ["healthy", "different_identity", "not_eligible"])
def test_sustained_failure_never_skips_an_immediate_predecessor_that_is_not_eligible(
    monkeypatch,
    predecessor_state,
):
    snapshot = _snapshot(record_id=3)
    snapshot_metrics = json.loads(snapshot.metrics_json)
    snapshot_metrics["hard_error_reason_counts"] = {"other_runtime_failure": 1}
    snapshot.metrics_json = json.dumps(snapshot_metrics)
    previous = _snapshot(snapshot_id="snapshot-immediate", record_id=2)
    previous_metrics = json.loads(previous.metrics_json)
    previous_metrics["hard_error_reason_counts"] = {"other_runtime_failure": 1}
    if predecessor_state == "healthy":
        previous.status = "healthy"
    elif predecessor_state == "different_identity":
        previous.model_version = "different-model"
        previous_metrics["model_identity"] = {
            "family": "chinese_account_detection",
            "model_version": "different-model",
            "artifact_hash": "c" * 64,
            "pointer_revision": 9,
        }
        previous.pointer_revision = 9
    else:
        previous_metrics["automatic_rollback_allowed"] = False
    previous.metrics_json = json.dumps(previous_metrics)
    pointer = _active_pointer()
    source = _source_decision()
    target = _target()
    session = _AutomaticRollbackSession(
        snapshot=snapshot,
        pointer=pointer,
        source=source,
        target=target,
        prior_snapshots=[previous],
    )
    _record_target_activation(session, target)
    _allow_verified_target(monkeypatch)

    result = asyncio.run(
        governance.attempt_automatic_account_model_rollback(session, snapshot_id=snapshot.snapshot_id)
    )

    assert result == {
        "status": "no_op",
        "reason": "rollback_not_eligible",
        "snapshot_id": snapshot.snapshot_id,
    }
    assert pointer.model_version == "current-model"
    assert target.status == "retired"
    assert session.added == []


def test_stale_snapshot_is_an_idempotent_noop(monkeypatch):
    snapshot = _snapshot()
    pointer = _active_pointer(model_version="replacement-model", revision=5)
    source = _source_decision(model_version="replacement-model", revision=5)
    target = _target()
    session = _AutomaticRollbackSession(snapshot=snapshot, pointer=pointer, source=source, target=target)
    session.unlocked_source = _source_decision()

    result = asyncio.run(
        governance.attempt_automatic_account_model_rollback(session, snapshot_id=snapshot.snapshot_id)
    )

    assert result == {
        "status": "no_op",
        "reason": "snapshot_stale",
        "snapshot_id": snapshot.snapshot_id,
    }
    assert pointer.model_version == "replacement-model"
    assert pointer.pointer_revision == 5
    assert session.added == []


def test_auto_rollback_blocks_a_shadow_candidate_without_activating_it(monkeypatch):
    snapshot = _snapshot()
    pointer = _active_pointer()
    shadow = _target(model_version="shadow-candidate", status="shadow")
    source = _source_decision(previous_model_version=shadow.model_version)
    session = _AutomaticRollbackSession(snapshot=snapshot, pointer=pointer, source=source, target=shadow)

    result = asyncio.run(
        governance.attempt_automatic_account_model_rollback(session, snapshot_id=snapshot.snapshot_id)
    )

    assert result == {
        "status": "blocked",
        "reason": "previous_target_not_deployable",
        "snapshot_id": snapshot.snapshot_id,
    }
    assert pointer.model_version == "current-model"
    assert shadow.status == "shadow"
    assert session.added == []


@pytest.mark.parametrize(
    ("kind", "expected_reason"),
    [
        ("hash", "previous_target_hash_invalid"),
        ("evaluation", "previous_target_verification_failed"),
        ("approval", "previous_target_approvals_invalid"),
    ],
)
def test_auto_rollback_blocks_targets_that_fail_hash_evaluation_or_approval_verification(
    monkeypatch,
    kind,
    expected_reason,
):
    snapshot = _snapshot()
    pointer = _active_pointer()
    source = _source_decision()
    target = _target()
    session = _AutomaticRollbackSession(snapshot=snapshot, pointer=pointer, source=source, target=target)
    _record_target_activation(session, target)
    _allow_verified_target(monkeypatch, approvals=(11,) if kind == "approval" else (11, 12))
    if kind == "hash":
        monkeypatch.setattr(governance, "_verify_artifact_hash", lambda *_args, **_kwargs: "c" * 64)
    elif kind == "evaluation":
        async def rejected_evaluation(*_args, **_kwargs):
            raise AppException(code=409, msg="signed evidence rejected")

        monkeypatch.setattr(governance, "_verify_persisted_evaluation_evidence", rejected_evaluation)

    result = asyncio.run(
        governance.attempt_automatic_account_model_rollback(session, snapshot_id=snapshot.snapshot_id)
    )

    assert result == {
        "status": "blocked",
        "reason": expected_reason,
        "snapshot_id": snapshot.snapshot_id,
    }
    assert pointer.model_version == "current-model"
    assert target.status == "retired"
    assert session.added == []


def test_automatic_rollback_replay_returns_the_existing_decision_without_a_second_pointer_change():
    snapshot = _snapshot()
    pointer = _active_pointer()
    source = _source_decision()
    target = _target()
    session = _AutomaticRollbackSession(snapshot=snapshot, pointer=pointer, source=source, target=target)
    existing = AccountModelGovernanceDecision(
        decision_id="automatic-rollback-1",
        family="chinese_account_detection",
        model_version="approved-previous-model",
        previous_model_version="current-model",
        pointer_revision=5,
        decision_type="automatic_rollback",
        decision_json=json.dumps({"triggering_snapshot_id": snapshot.snapshot_id}),
        decided_by=0,
    )
    session.decisions.append(existing)

    result = asyncio.run(
        governance.attempt_automatic_account_model_rollback(session, snapshot_id=snapshot.snapshot_id)
    )

    assert result == {
        "status": "already_rolled_back",
        "snapshot_id": snapshot.snapshot_id,
        "decision_id": existing.decision_id,
        "pointer_revision": 5,
    }
    assert pointer.model_version == "current-model"
    assert pointer.pointer_revision == 4
    assert session.added == []
