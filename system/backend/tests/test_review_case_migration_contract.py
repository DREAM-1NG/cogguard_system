from __future__ import annotations

import importlib.util
from pathlib import Path


class OperationRecorder:
    def __init__(self) -> None:
        self.created_tables: list[str] = []
        self.dropped_tables: list[str] = []

    def create_table(self, name: str, *_args, **_kwargs) -> None:
        self.created_tables.append(name)

    def create_index(self, *_args, **_kwargs) -> None:
        return None

    def drop_table(self, name: str) -> None:
        self.dropped_tables.append(name)


def test_review_case_migration_creates_and_drops_tables_in_dependency_order():
    migration_path = (
        Path(__file__).resolve().parents[1]
        / "alembic"
        / "versions"
        / "e8b4c1d7a620_add_review_case_tables.py"
    )
    spec = importlib.util.spec_from_file_location("review_case_migration_contract", migration_path)
    assert spec is not None and spec.loader is not None
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    recorder = OperationRecorder()
    migration.op = recorder

    migration.upgrade()
    migration.downgrade()

    expected = [
        "review_cases",
        "review_case_snapshot_revisions",
        "review_decision_drafts",
        "review_decisions",
        "review_evidence_annotations",
        "review_case_activities",
    ]
    assert recorder.created_tables == expected
    assert recorder.dropped_tables == list(reversed(expected))
