from sqlalchemy import UniqueConstraint

from app.models.analysis import (
    AnalysisModelActivationApproval,
    AnalysisModelGovernanceDecision,
    ReviewVerdictVersion,
)


def _unique_columns(table):
    return {
        tuple(column.name for column in constraint.columns)
        for constraint in table.constraints
        if isinstance(constraint, UniqueConstraint)
    }


def test_model_governance_decisions_are_append_only_records():
    table = AnalysisModelGovernanceDecision.__table__

    assert table.name == "analysis_model_governance_decisions"
    assert table.c.id.primary_key
    assert ("decision_id",) in _unique_columns(table)
    assert "technology" in table.c
    assert "model_version_id" in table.c
    assert "previous_model_version_id" in table.c
    assert "decision_type" in table.c
    assert "decision_json" in table.c
    assert "decided_by" in table.c
    assert "updated_at" not in table.c


def test_canonical_source_can_only_be_approved_once_at_database_boundary():
    assert ("canonical_source_id",) in _unique_columns(ReviewVerdictVersion.__table__)


def test_model_activation_approvals_are_append_only_and_unique_per_administrator():
    table = AnalysisModelActivationApproval.__table__

    assert table.name == "analysis_model_activation_approvals"
    assert ("approval_id",) in _unique_columns(table)
    assert ("model_version_id", "approver_id") in _unique_columns(table)
    assert "approval_notes" in table.c
    assert "updated_at" not in table.c
