"""Metadata contracts for account-detection training governance models."""

from sqlalchemy import Boolean, CheckConstraint, DateTime, Integer, String, Text, UniqueConstraint


TRAINING_RUN_STATUSES = (
    "queued",
    "preparing",
    "running",
    "evaluating",
    "completed",
    "failed",
    "cancelled",
    "interrupted",
)


def _column(table, name):
    return table.c[name]


def _unique_columns(table):
    return {
        tuple(column.name for column in constraint.columns)
        for constraint in table.constraints
        if isinstance(constraint, UniqueConstraint)
    }


def _check_sql(table):
    return {
        str(constraint.sqltext)
        for constraint in table.constraints
        if isinstance(constraint, CheckConstraint)
    }


def _assert_append_only(table):
    assert "created_at" in table.c
    assert "updated_at" not in table.c


def test_account_behavior_labels_keep_a_reviewable_append_only_revision_chain():
    from app.models.account_labeling import AccountBehaviorLabelRecord

    table = AccountBehaviorLabelRecord.__table__

    assert table.name == "account_behavior_labels"
    assert _column(table, "supersedes_id").type.length == 128
    assert _column(table, "supersedes_id").nullable
    assert isinstance(_column(table, "review_required").type, Boolean)
    assert not _column(table, "review_required").nullable
    assert _column(table, "second_review_status").type.length == 32
    assert not _column(table, "second_review_status").nullable
    assert "ix_account_behavior_labels_supersedes_id" in {index.name for index in table.indexes}
    _assert_append_only(table)


def test_corpus_review_and_frozen_holdout_records_preserve_governance_provenance():
    from app.models.account_labeling import (
        AccountCorpusVersion,
        AccountFrozenHoldoutMembership,
        AccountLabelReviewAssignment,
    )

    corpus = AccountCorpusVersion.__table__
    assignment = AccountLabelReviewAssignment.__table__
    membership = AccountFrozenHoldoutMembership.__table__

    assert corpus.name == "account_corpus_versions"
    assert _column(corpus, "corpus_version_id").type.length == 128
    assert _column(corpus, "input_fingerprint").type.length == 64
    assert isinstance(_column(corpus, "manifest_json").type, Text)
    assert ("corpus_version_id",) in _unique_columns(corpus)
    _assert_append_only(corpus)

    assert assignment.name == "account_label_review_assignments"
    assert _column(assignment, "assignment_id").type.length == 128
    assert _column(assignment, "label_id").type.length == 128
    assert isinstance(_column(assignment, "review_round").type, Integer)
    assert _column(assignment, "review_status").type.length == 32
    assert ("assignment_id",) in _unique_columns(assignment)
    _assert_append_only(assignment)

    assert membership.name == "account_frozen_holdout_memberships"
    assert _column(membership, "membership_id").type.length == 128
    assert _column(membership, "corpus_version_id").type.length == 128
    assert _column(membership, "case_id").type.length == 128
    assert _column(membership, "label_id").type.length == 128
    assert ("corpus_version_id", "case_id") in _unique_columns(membership)
    _assert_append_only(membership)


def test_training_runs_encode_the_resumable_lifecycle_contract():
    from app.models.account_labeling import AccountModelTrainingRun

    table = AccountModelTrainingRun.__table__

    assert table.name == "account_model_training_runs"
    assert _column(table, "run_id").type.length == 128
    assert _column(table, "family").type.length == 64
    assert _column(table, "status").type.length == 32
    assert "/".join(TRAINING_RUN_STATUSES) in _column(table, "status").comment
    for name in [
        "stage",
        "input_fingerprint",
        "config_hash",
        "attempt",
        "max_attempts",
        "heartbeat_at",
        "resume_checkpoint_uri",
        "cancel_requested_at",
        "created_at",
        "started_at",
        "finished_at",
    ]:
        assert name in table.c
    assert isinstance(_column(table, "attempt").type, Integer)
    assert isinstance(_column(table, "max_attempts").type, Integer)
    assert isinstance(_column(table, "heartbeat_at").type, DateTime)
    assert isinstance(_column(table, "resume_checkpoint_uri").type, Text)
    assert _column(table, "started_at").nullable
    assert _column(table, "finished_at").nullable
    assert ("run_id",) in _unique_columns(table)
    assert any("status" in sql and "interrupted" in sql for sql in _check_sql(table))
    assert "attempt >= 1" in _check_sql(table)
    assert "max_attempts >= 1" in _check_sql(table)


def test_chinese_social_encoder_versions_bind_completed_artifacts_to_one_training_run():
    from app.models.account_labeling import ChineseSocialEncoderVersion, AccountDetectionModelVersion

    encoder = ChineseSocialEncoderVersion.__table__
    detector = AccountDetectionModelVersion.__table__

    assert encoder.name == "chinese_social_encoder_versions"
    for name in [
        "encoder_version",
        "corpus_version_id",
        "training_run_id",
        "artifact_uri",
        "artifact_hash",
        "base_model_identity",
        "manifest_json",
        "status",
        "created_by",
        "created_at",
        "updated_at",
    ]:
        assert name in encoder.c
    assert _column(encoder, "encoder_version").type.length == 128
    assert _column(encoder, "corpus_version_id").type.length == 128
    assert _column(encoder, "training_run_id").type.length == 128
    assert _column(encoder, "artifact_hash").type.length == 64
    assert isinstance(_column(encoder, "artifact_uri").type, Text)
    assert isinstance(_column(encoder, "manifest_json").type, Text)
    assert ("encoder_version",) in _unique_columns(encoder)
    assert ("training_run_id",) in _unique_columns(encoder)
    assert not _column(encoder, "updated_at").nullable

    assert _column(detector, "encoder_version").nullable
    assert _column(detector, "encoder_artifact_hash").nullable
    assert _column(detector, "encoder_artifact_hash").type.length == 64


def test_training_events_and_governance_decisions_are_append_only():
    from app.models.account_labeling import (
        AccountModelGovernanceDecision,
        AccountModelTrainingEvent,
    )

    event = AccountModelTrainingEvent.__table__
    decision = AccountModelGovernanceDecision.__table__

    assert event.name == "account_model_training_events"
    assert _column(event, "event_id").type.length == 128
    assert _column(event, "run_id").type.length == 128
    assert _column(event, "stage").type.length == 64
    assert isinstance(_column(event, "payload_json").type, Text)
    assert ("event_id",) in _unique_columns(event)
    _assert_append_only(event)

    assert decision.name == "account_model_governance_decisions"
    assert _column(decision, "decision_id").type.length == 128
    assert _column(decision, "family").type.length == 64
    assert isinstance(_column(decision, "pointer_revision").type, Integer)
    assert isinstance(_column(decision, "decision_json").type, Text)
    assert ("decision_id",) in _unique_columns(decision)
    _assert_append_only(decision)


def test_training_dispatch_outbox_has_one_intent_and_task_id_per_run_attempt():
    from app.models.account_labeling import AccountModelTrainingDispatchOutbox

    table = AccountModelTrainingDispatchOutbox.__table__

    assert table.name == "account_model_training_dispatch_outbox"
    for name in [
        "dispatch_id",
        "run_id",
        "attempt",
        "task_id",
        "status",
        "claim_token",
        "lease_expires_at",
        "publish_attempts",
        "available_at",
        "published_at",
        "last_error",
        "created_at",
        "updated_at",
    ]:
        assert name in table.c
    assert ("dispatch_id",) in _unique_columns(table)
    assert ("run_id", "attempt") in _unique_columns(table)
    assert ("task_id",) in _unique_columns(table)
    assert "ix_account_model_training_dispatch_outbox_status" in {index.name for index in table.indexes}
    assert "ix_account_training_dispatch_outbox_claim_lease" in {index.name for index in table.indexes}
    assert any("status" in sql and "publishing" in sql and "superseded" in sql for sql in _check_sql(table))
    assert not _column(table, "created_at").nullable
    assert not _column(table, "updated_at").nullable


def test_evaluation_job_contains_a_lease_aware_transactional_dispatch_intent():
    from app.models.account_labeling import AccountModelEvaluationJob

    table = AccountModelEvaluationJob.__table__

    for name in [
        "dispatch_status",
        "dispatch_claim_token",
        "dispatch_lease_expires_at",
        "dispatch_publish_attempts",
        "dispatch_available_at",
        "dispatch_published_at",
        "dispatch_last_error",
    ]:
        assert name in table.c
    assert "ix_account_model_evaluation_jobs_dispatch" in {index.name for index in table.indexes}
    assert any(
        "dispatch_status" in sql and "publishing" in sql and "superseded" in sql
        for sql in _check_sql(table)
    )
    assert not _column(table, "dispatch_status").nullable
    assert not _column(table, "dispatch_publish_attempts").nullable
    assert not _column(table, "dispatch_available_at").nullable


def test_prediction_audits_and_monitor_snapshots_capture_model_pointer_revision():
    from app.models.account_labeling import (
        AccountMonitorSnapshot,
        AccountPredictionAudit,
        AccountDetectionModelActivation,
    )

    audit = AccountPredictionAudit.__table__
    snapshot = AccountMonitorSnapshot.__table__
    activation = AccountDetectionModelActivation.__table__

    assert isinstance(_column(activation, "pointer_revision").type, Integer)
    assert not _column(activation, "pointer_revision").nullable

    assert audit.name == "account_prediction_audits"
    assert _column(audit, "audit_id").type.length == 128
    assert _column(audit, "case_id").type.length == 128
    assert _column(audit, "family").type.length == 64
    assert isinstance(_column(audit, "pointer_revision").type, Integer)
    assert isinstance(_column(audit, "prediction_json").type, Text)
    assert ("audit_id",) in _unique_columns(audit)
    _assert_append_only(audit)

    assert snapshot.name == "account_monitor_snapshots"
    assert _column(snapshot, "snapshot_id").type.length == 128
    assert _column(snapshot, "family").type.length == 64
    assert isinstance(_column(snapshot, "pointer_revision").type, Integer)
    assert isinstance(_column(snapshot, "metrics_json").type, Text)
    assert ("snapshot_id",) in _unique_columns(snapshot)
    _assert_append_only(snapshot)
