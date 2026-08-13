"""Repair legacy KT3 review table names used by the running prototype.

The database was stamped at the review-system head after an earlier runtime
renamed those tables with a ``kt3_`` prefix.  Current ORM models use the
product-facing names, so this migration reconciles the schema without
discarding the existing rows.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "f8a1c2d3e4b5"
down_revision: Union[str, None] = "e5c1b7d9a204"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


TABLE_RENAMES = (
    ("kt3_provider_configs", "review_provider_configs"),
    ("kt3_gate_datasets", "gate_datasets"),
    ("kt3_gate_cases", "review_gate_cases"),
    ("kt3_gate_labels", "review_gate_labels"),
    ("kt3_jobs", "review_jobs"),
    ("kt3_agent_runs", "review_agent_runs"),
    ("kt3_agent_reports", "review_agent_reports"),
    ("kt3_agent_report_evidence_refs", "review_agent_report_evidence_refs"),
    ("kt3_agent_report_queries", "review_agent_report_queries"),
    ("kt3_agent_report_uncertainties", "review_agent_report_uncertainties"),
    ("kt3_agent_report_actions", "review_agent_report_actions"),
    ("kt3_agent_debate_traces", "review_agent_debate_traces"),
    ("kt3_agent_feedback", "review_agent_feedback"),
    ("kt3_policies", "review_policies"),
    ("kt3_policy_agent_weights", "review_policy_agent_weights"),
    ("kt3_policy_thresholds", "review_policy_thresholds"),
    ("kt3_policy_rules", "review_policy_rules"),
    ("kt3_policy_metrics", "review_policy_metrics"),
    ("kt3_policy_refinement_rounds", "review_policy_refinement_rounds"),
)


def _table_names() -> set[str]:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return set(inspector.get_table_names())


def upgrade() -> None:
    existing = _table_names()
    for old_name, new_name in TABLE_RENAMES:
        if old_name in existing and new_name not in existing:
            op.rename_table(old_name, new_name)
            existing.remove(old_name)
            existing.add(new_name)


def downgrade() -> None:
    existing = _table_names()
    for old_name, new_name in reversed(TABLE_RENAMES):
        if new_name in existing and old_name not in existing:
            op.rename_table(new_name, old_name)
            existing.remove(new_name)
            existing.add(old_name)
