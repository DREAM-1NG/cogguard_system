"""make account evaluator run identifiers globally unique

Revision ID: a1e9c7d4b605
Revises: f4b7c2d9e813
Create Date: 2026-08-06 20:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import context, op


revision: str = "a1e9c7d4b605"
down_revision: Union[str, Sequence[str], None] = "f4b7c2d9e813"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    if not context.is_offline_mode():
        duplicates = op.get_bind().execute(
            sa.text(
                "SELECT evaluation_run_id FROM account_model_evaluation_runs "
                "GROUP BY evaluation_run_id HAVING COUNT(*) > 1"
            )
        ).fetchall()
        if duplicates:
            raise RuntimeError(
                "Cannot make evaluation_run_id globally unique while existing evaluation runs are reused; "
                "remediate the conflicting evaluator evidence before retrying the migration."
            )
    op.drop_constraint(
        "uq_account_model_evaluation_runs_identity",
        "account_model_evaluation_runs",
        type_="unique",
    )
    op.create_unique_constraint(
        "uq_account_model_evaluation_runs_run_id",
        "account_model_evaluation_runs",
        ["evaluation_run_id"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_account_model_evaluation_runs_run_id",
        "account_model_evaluation_runs",
        type_="unique",
    )
    op.create_unique_constraint(
        "uq_account_model_evaluation_runs_identity",
        "account_model_evaluation_runs",
        ["evaluation_run_id", "model_version", "artifact_hash"],
    )
