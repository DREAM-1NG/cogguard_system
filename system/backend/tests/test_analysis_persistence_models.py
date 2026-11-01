"""Metadata contracts for unified analysis persistence models."""

from sqlalchemy import DateTime, Integer, String, Text, UniqueConstraint


def column(table, name):
    return table.c[name]


def index_names(table):
    return {index.name for index in table.indexes}


def unique_index_names(table):
    return {index.name for index in table.indexes if index.unique}


def unique_constraint_column_sets(table):
    return {
        tuple(column.name for column in constraint.columns)
        for constraint in table.constraints
        if isinstance(constraint, UniqueConstraint)
    }


def assert_text_json_columns(table, names):
    for name in names:
        assert isinstance(column(table, name).type, Text)
        assert not column(table, name).nullable


def test_event_snapshot_record_metadata_contract():
    from app.models.analysis import EventSnapshotRecord

    table = EventSnapshotRecord.__table__

    assert table.name == "analysis_event_snapshots"
    assert column(table, "id").primary_key
    assert isinstance(column(table, "snapshot_id").type, String)
    assert column(table, "snapshot_id").type.length == 128
    assert isinstance(column(table, "event_id").type, String)
    assert column(table, "event_id").type.length == 128
    assert isinstance(column(table, "data_fingerprint").type, String)
    assert column(table, "data_fingerprint").type.length == 128
    assert isinstance(column(table, "mongo_collection").type, String)
    assert isinstance(column(table, "mongo_key").type, String)
    for name in [
        "platforms_json",
        "windows_json",
        "quality_json",
        "provenance_json",
    ]:
        assert isinstance(column(table, name).type, Text)
        assert not column(table, name).nullable
    assert isinstance(column(table, "created_by").type, Integer)
    assert "ix_analysis_event_snapshots_snapshot_id" in unique_index_names(table)
    assert "ix_analysis_event_snapshots_event_id" in index_names(table)
    assert "ix_analysis_event_snapshots_data_fingerprint" in index_names(table)


def test_analysis_run_metadata_contract():
    from app.models.analysis import AnalysisRun

    table = AnalysisRun.__table__

    assert table.name == "analysis_runs"
    assert column(table, "id").primary_key
    assert column(table, "run_id").type.length == 128
    assert column(table, "event_id").type.length == 128
    assert column(table, "snapshot_id").type.length == 128
    assert column(table, "status").type.length == 32
    assert "queued/running/needs_evidence/awaiting_review/completed/failed/cancelled" in column(
        table,
        "status",
    ).comment
    assert_text_json_columns(
        table,
        [
            "requested_stages_json",
            "options_json",
            "artifact_manifest_json",
        ],
    )
    assert isinstance(column(table, "result_json").type, Text)
    assert column(table, "result_json").nullable
    assert isinstance(column(table, "error").type, Text)
    assert column(table, "error").nullable
    assert column(table, "celery_task_id").type.length == 128
    assert "ix_analysis_runs_run_id" in unique_index_names(table)
    for name in ["event_id", "snapshot_id", "status", "celery_task_id"]:
        assert f"ix_analysis_runs_{name}" in index_names(table)


def test_analysis_run_event_metadata_contract():
    from app.models.analysis import AnalysisRunEvent

    table = AnalysisRunEvent.__table__

    assert table.name == "analysis_run_events"
    assert column(table, "id").primary_key
    assert column(table, "id").autoincrement
    assert column(table, "run_id").type.length == 128
    assert column(table, "event_type").type.length == 64
    assert column(table, "status").type.length == 32
    assert isinstance(column(table, "payload_json").type, Text)
    assert isinstance(column(table, "created_at").type, DateTime)
    assert "ix_analysis_run_events_run_id" in index_names(table)


def test_model_version_activation_metadata_contracts():
    from app.models.analysis import AnalysisModelActivation, AnalysisModelVersion

    version_table = AnalysisModelVersion.__table__
    activation_table = AnalysisModelActivation.__table__

    assert version_table.name == "analysis_model_versions"
    assert column(version_table, "id").primary_key
    assert column(version_table, "technology").type.length == 64
    assert column(version_table, "model").type.length == 128
    assert column(version_table, "version").type.length == 64
    assert column(version_table, "artifact_hash").type.length == 128
    assert isinstance(column(version_table, "artifact_uri").type, Text)
    assert_text_json_columns(version_table, ["config_json", "metrics_json"])
    assert column(version_table, "status").type.length == 32
    for name in ["technology", "artifact_hash", "status"]:
        assert f"ix_analysis_model_versions_{name}" in index_names(version_table)

    assert activation_table.name == "analysis_model_activations"
    assert column(activation_table, "id").primary_key
    assert column(activation_table, "technology").type.length == 64
    assert isinstance(column(activation_table, "model_version_id").type, Integer)
    assert_text_json_columns(activation_table, ["provenance_json"])
    assert "ix_analysis_model_activations_technology" in unique_index_names(activation_table)
    assert "ix_analysis_model_activations_model_version_id" in index_names(activation_table)


def test_review_verdict_feedback_metadata_contracts():
    from app.models.analysis import ReviewFeedback, ReviewVerdictVersion

    verdict_table = ReviewVerdictVersion.__table__
    feedback_table = ReviewFeedback.__table__

    assert verdict_table.name == "analysis_review_verdict_versions"
    assert column(verdict_table, "id").primary_key
    assert column(verdict_table, "verdict_id").type.length == 128
    assert column(verdict_table, "run_id").type.length == 128
    assert isinstance(column(verdict_table, "version").type, Integer)
    assert column(verdict_table, "verdict_type").type.length == 32
    assert "preliminary/teacher_advisory/canonical" in column(verdict_table, "verdict_type").comment
    assert_text_json_columns(verdict_table, ["verdict_json", "provenance_json"])
    assert column(verdict_table, "immutable_source").type.length == 128
    assert column(verdict_table, "canonical_source_id").type.length == 128
    assert column(verdict_table, "canonical_source_id").nullable
    assert isinstance(column(verdict_table, "approval_notes").type, Text)
    assert column(verdict_table, "approved_by").nullable
    assert column(verdict_table, "approved_at").nullable
    assert "ix_analysis_review_verdict_versions_verdict_id" in index_names(verdict_table)
    assert "ix_analysis_review_verdict_versions_verdict_id" not in unique_index_names(verdict_table)
    assert ("verdict_id", "version") in unique_constraint_column_sets(verdict_table)
    for name in ["run_id", "snapshot_id", "verdict_type", "status"]:
        assert f"ix_analysis_review_verdict_versions_{name}" in index_names(verdict_table)

    assert feedback_table.name == "analysis_review_feedback"
    assert column(feedback_table, "id").primary_key
    assert column(feedback_table, "feedback_id").type.length == 128
    assert column(feedback_table, "run_id").type.length == 128
    assert column(feedback_table, "verdict_id").type.length == 128
    assert_text_json_columns(feedback_table, ["feedback_json", "provenance_json"])
    assert column(feedback_table, "immutable_source").type.length == 128
    assert "ix_analysis_review_feedback_feedback_id" in unique_index_names(feedback_table)
    for name in ["run_id", "verdict_id", "snapshot_id", "created_by"]:
        assert f"ix_analysis_review_feedback_{name}" in index_names(feedback_table)
