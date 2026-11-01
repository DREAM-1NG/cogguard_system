"""Metadata contracts for event review case persistence."""

from sqlalchemy import create_engine
from sqlalchemy.schema import UniqueConstraint

from app.db.mysql import Base
from app.models.review_case import (
    CaseActivity,
    EvidenceAnnotation,
    ReviewCase,
    ReviewCaseSnapshotRevision,
    ReviewDecision,
    ReviewDecisionDraft,
)


REVIEW_CASE_TABLES = (
    ReviewCase.__table__,
    ReviewCaseSnapshotRevision.__table__,
    ReviewDecisionDraft.__table__,
    ReviewDecision.__table__,
    EvidenceAnnotation.__table__,
    CaseActivity.__table__,
)


def unique_constraint_columns(table) -> set[tuple[str, ...]]:
    return {
        tuple(column.name for column in constraint.columns)
        for constraint in table.constraints
        if isinstance(constraint, UniqueConstraint)
    }


def unique_index_columns(table) -> set[tuple[str, ...]]:
    return {
        tuple(column.name for column in index.columns)
        for index in table.indexes
        if index.unique
    }


def all_unique_columns(table) -> set[tuple[str, ...]]:
    return unique_constraint_columns(table) | unique_index_columns(table)


def test_review_case_table_names_and_identifiers():
    assert [table.name for table in REVIEW_CASE_TABLES] == [
        "review_cases",
        "review_case_snapshot_revisions",
        "review_decision_drafts",
        "review_decisions",
        "review_evidence_annotations",
        "review_case_activities",
    ]

    assert ("case_id",) in all_unique_columns(ReviewCase.__table__)
    assert ("event_id",) in all_unique_columns(ReviewCase.__table__)
    assert ("snapshot_revision_id",) in all_unique_columns(ReviewCaseSnapshotRevision.__table__)
    assert ("annotation_id",) in all_unique_columns(EvidenceAnnotation.__table__)
    assert ReviewCase.__table__.c.id.primary_key
    assert CaseActivity.__table__.c.id.primary_key
    assert CaseActivity.__table__.c.id.autoincrement


def test_snapshot_revision_and_decision_uniqueness_contracts():
    revision_uniques = all_unique_columns(ReviewCaseSnapshotRevision.__table__)
    assert ("case_id", "data_fingerprint") in revision_uniques
    assert ("case_id", "revision_number") in revision_uniques

    assert ("case_id",) in all_unique_columns(ReviewDecisionDraft.__table__)
    assert ("case_id", "version") in all_unique_columns(ReviewDecision.__table__)
    assert ("decision_id",) in all_unique_columns(ReviewDecision.__table__)
    assert (
        "case_id",
        "activity_type",
        "source_ref",
    ) in all_unique_columns(CaseActivity.__table__)


def test_mutable_draft_and_immutable_record_shapes():
    draft_columns = ReviewDecisionDraft.__table__.c
    assert "snapshot_revision_id" in draft_columns
    assert "version" in draft_columns
    assert not draft_columns.version.nullable
    assert "updated_at" in draft_columns
    assert "updated_by" in draft_columns

    for immutable_table in (
        ReviewCaseSnapshotRevision.__table__,
        ReviewDecision.__table__,
        EvidenceAnnotation.__table__,
        CaseActivity.__table__,
    ):
        assert "created_at" in immutable_table.c
        assert "created_by" in immutable_table.c
        assert "updated_at" not in immutable_table.c

    assert "confirmed_at" in ReviewDecision.__table__.c
    assert "confirmed_by" in ReviewDecision.__table__.c
    for name in (
        "analysis_run_id",
        "teacher_run_id",
        "teacher_verdict_id",
        "analysis_completed_at",
    ):
        assert name in ReviewCaseSnapshotRevision.__table__.c


def test_json_payloads_are_stored_as_text():
    expected_json_columns = {
        ReviewCase.__table__: {"preliminary_finding_json", "business_summary_json"},
        ReviewCaseSnapshotRevision.__table__: {"quality_json", "provenance_json"},
        ReviewDecisionDraft.__table__: {"key_evidence_refs_json", "unresolved_items_json"},
        ReviewDecision.__table__: {"key_evidence_refs_json", "unresolved_items_json"},
        CaseActivity.__table__: {"detail_lines_json", "evidence_refs_json"},
    }

    for table, column_names in expected_json_columns.items():
        for column_name in column_names:
            assert table.c[column_name].type.__class__.__name__ == "Text"
            assert not table.c[column_name].nullable


def test_review_case_metadata_can_create_all_tables_on_sqlite():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine, tables=list(REVIEW_CASE_TABLES), checkfirst=False)

    with engine.connect() as connection:
        created = {
            row[0]
            for row in connection.exec_driver_sql(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }

    assert {table.name for table in REVIEW_CASE_TABLES} <= created
