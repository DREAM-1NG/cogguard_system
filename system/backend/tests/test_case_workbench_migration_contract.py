from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any

import sqlalchemy as sa


class OperationRecorder:
    def __init__(self) -> None:
        self.created_tables: dict[str, tuple[Any, ...]] = {}
        self.created_table_order: list[str] = []
        self.created_indexes: list[tuple[str, str, tuple[str, ...], bool]] = []
        self.dropped_indexes: list[tuple[str, str | None]] = []
        self.dropped_tables: list[str] = []

    def create_table(self, name: str, *args: Any, **_kwargs: Any) -> None:
        self.created_tables[name] = args
        self.created_table_order.append(name)

    def create_index(
        self,
        name: str,
        table_name: str,
        columns: list[str] | tuple[str, ...],
        unique: bool = False,
        **_kwargs: Any,
    ) -> None:
        self.created_indexes.append((str(name), table_name, tuple(columns), unique))

    def drop_index(self, name: str, table_name: str | None = None, **_kwargs: Any) -> None:
        self.dropped_indexes.append((str(name), table_name))

    def drop_table(self, name: str) -> None:
        self.dropped_tables.append(name)

    def f(self, name: str) -> str:
        return name


def _load_migration():
    migration_path = (
        Path(__file__).resolve().parents[1]
        / "alembic"
        / "versions"
        / "b9e6c1a3d0f2_add_case_workbench_base_tables.py"
    )
    spec = importlib.util.spec_from_file_location("case_workbench_migration_contract", migration_path)
    assert spec is not None and spec.loader is not None
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    return migration


def _constraint_names(args: tuple[Any, ...], constraint_type: type) -> set[str]:
    return {
        str(item.name)
        for item in args
        if isinstance(item, constraint_type) and item.name is not None
    }


def _foreign_keys(args: tuple[Any, ...]) -> set[tuple[str, str]]:
    refs: set[tuple[str, str]] = set()
    for item in args:
        if isinstance(item, sa.ForeignKeyConstraint):
            for column_name, element in zip(item.column_keys, item.elements, strict=True):
                refs.add((column_name, element.target_fullname))
            continue
        if not isinstance(item, sa.Column):
            continue
        for foreign_key in item.foreign_keys:
            refs.add((item.name, foreign_key.target_fullname))
    return refs


def test_case_workbench_migration_creates_expected_base_tables_and_constraints():
    migration = _load_migration()
    recorder = OperationRecorder()
    migration.op = recorder

    migration.upgrade()
    migration.downgrade()

    expected_tables = [
        "case_records",
        "authority_sources",
        "case_claims",
        "case_analysis_links",
        "semantic_artifacts",
        "semantic_corrections",
        "case_actions",
        "case_feedback",
        "case_report_versions",
        "case_audit_events",
    ]
    assert migration.down_revision == "a7c5e9d2f481"
    assert recorder.created_table_order == expected_tables
    assert recorder.dropped_tables == list(reversed(expected_tables))

    case_record_uniques = _constraint_names(
        recorder.created_tables["case_records"],
        sa.UniqueConstraint,
    )
    assert {"uq_case_records_case_id", "uq_case_records_event_id"} <= case_record_uniques

    authority_uniques = _constraint_names(
        recorder.created_tables["authority_sources"],
        sa.UniqueConstraint,
    )
    assert "uq_authority_sources_source_id" in authority_uniques

    case_claim_uniques = _constraint_names(
        recorder.created_tables["case_claims"],
        sa.UniqueConstraint,
    )
    assert "uq_case_claims_claim_id" in case_claim_uniques
    assert ("case_id", "case_records.case_id") in _foreign_keys(recorder.created_tables["case_claims"])

    assert (
        "ix_case_records_lifecycle",
        "case_records",
        ("lifecycle",),
        False,
    ) in recorder.created_indexes
    assert (
        "ix_case_claims_case_id",
        "case_claims",
        ("case_id",),
        False,
    ) in recorder.created_indexes
