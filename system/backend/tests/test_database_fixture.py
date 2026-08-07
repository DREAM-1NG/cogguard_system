from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.db.mysql import get_db
from app.main import app


def _fixture_module():
    fixture_path = Path(__file__).with_name("conftest.py").resolve()
    for module in sys.modules.values():
        module_path = getattr(module, "__file__", None)
        if module_path is not None and Path(module_path).resolve() == fixture_path:
            return module
    raise RuntimeError("pytest did not load the database fixture module")


class _Table:
    def delete(self):
        return object()


class _Connection:
    def __init__(self):
        self.driver_sql: list[str] = []

    async def exec_driver_sql(self, statement: str):
        self.driver_sql.append(statement)

    async def execute(self, _statement):
        raise RuntimeError("delete failed")


class _BeginContext:
    def __init__(self, connection: _Connection):
        self.connection = connection

    async def __aenter__(self):
        return self.connection

    async def __aexit__(self, *_args):
        return None


class _Engine:
    def __init__(self, connection: _Connection):
        self.connection = connection

    def begin(self):
        return _BeginContext(self.connection)


@pytest.mark.asyncio
async def test_database_cleanup_restores_foreign_key_checks_when_delete_fails(monkeypatch):
    conftest = _fixture_module()
    connection = _Connection()
    monkeypatch.setattr(conftest, "test_engine", _Engine(connection))
    monkeypatch.setattr(
        conftest,
        "Base",
        SimpleNamespace(metadata=SimpleNamespace(sorted_tables=[_Table()])),
    )

    with pytest.raises(RuntimeError, match="delete failed"):
        await conftest._clear_test_database()

    assert connection.driver_sql == ["SET FOREIGN_KEY_CHECKS=0", "SET FOREIGN_KEY_CHECKS=1"]


def test_dependency_override_fixture_restores_the_test_database_override():
    conftest = _fixture_module()
    lifecycle = conftest.isolate_dependency_overrides.__wrapped__()

    next(lifecycle)
    app.dependency_overrides.pop(get_db, None)

    with pytest.raises(StopIteration):
        next(lifecycle)

    assert app.dependency_overrides[get_db] is conftest.override_get_db


def test_database_session_lock_serializes_schema_setup(monkeypatch, tmp_path):
    conftest = _fixture_module()
    calls: list[tuple[str, object]] = []

    class _Lock:
        def __init__(self, path):
            self.path = path

        def acquire(self, *, timeout):
            calls.append(("acquire", (self.path, timeout)))

        def release(self):
            calls.append(("release", self.path))

    lock_path = tmp_path / "cogguard-test-schema.lock"
    monkeypatch.setattr(conftest, "FileLock", _Lock)
    monkeypatch.setattr(conftest, "_check_db_available", lambda: True)
    monkeypatch.setattr(conftest, "_test_database_lock_path", lambda: lock_path)

    lifecycle = conftest.serialize_test_database_session.__wrapped__()
    next(lifecycle)

    assert calls == [("acquire", (lock_path, conftest.TEST_DATABASE_LOCK_TIMEOUT_SECONDS))]

    with pytest.raises(StopIteration):
        next(lifecycle)

    assert calls[-1] == ("release", lock_path)
