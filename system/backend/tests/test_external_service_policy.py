from __future__ import annotations

import pytest

from tests import conftest


def test_external_service_policy_is_opt_in(monkeypatch):
    monkeypatch.delenv("COGGUARD_REQUIRE_EXTERNAL_SERVICES", raising=False)
    assert conftest.external_services_required() is False


def test_external_service_policy_fails_when_strict_dependency_is_unavailable(monkeypatch):
    monkeypatch.setenv("COGGUARD_REQUIRE_EXTERNAL_SERVICES", "1")

    with pytest.raises(RuntimeError, match="MySQL test database is required"):
        conftest.require_external_service("MySQL test database", available=False)


def test_external_service_policy_preserves_explicit_local_skip(monkeypatch):
    monkeypatch.delenv("COGGUARD_REQUIRE_EXTERNAL_SERVICES", raising=False)

    with pytest.raises(pytest.skip.Exception, match="MongoDB integration service not available"):
        conftest.require_external_service("MongoDB integration service", available=False)
