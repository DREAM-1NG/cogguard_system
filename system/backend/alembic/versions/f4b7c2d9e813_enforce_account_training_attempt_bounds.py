"""enforce account training attempt bounds

Revision ID: f4b7c2d9e813
Revises: e7a3c9d5f102
Create Date: 2026-08-06 12:30:00.000000
"""

from typing import Sequence, Union

from alembic import op


revision: str = "f4b7c2d9e813"
down_revision: Union[str, Sequence[str], None] = "e7a3c9d5f102"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("UPDATE account_model_training_runs SET attempt = 1 WHERE attempt < 1")
    op.execute("UPDATE account_model_training_runs SET max_attempts = 1 WHERE max_attempts < 1")
    op.create_check_constraint(
        "ck_account_model_training_runs_attempt_positive",
        "account_model_training_runs",
        "attempt >= 1",
    )
    op.create_check_constraint(
        "ck_account_model_training_runs_max_attempts_positive",
        "account_model_training_runs",
        "max_attempts >= 1",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_account_model_training_runs_max_attempts_positive",
        "account_model_training_runs",
        type_="check",
    )
    op.drop_constraint(
        "ck_account_model_training_runs_attempt_positive",
        "account_model_training_runs",
        type_="check",
    )
