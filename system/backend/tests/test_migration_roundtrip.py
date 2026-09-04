from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest


BACKEND_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = BACKEND_ROOT / "scripts" / "verify_migration_roundtrip.py"


def _run_script(*args: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=BACKEND_ROOT,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=60,
    )


def test_migration_roundtrip_command_exposes_real_database_contract():
    result = _run_script("--help")

    assert result.returncode == 0, result.stderr
    assert "MYSQL_DATABASE_TEST" in result.stdout
    assert "--check-services" in result.stdout
    assert "upgrade head" in result.stdout
    assert "downgrade base" in result.stdout


def test_service_readiness_reports_exact_endpoints_and_failure_reasons():
    env = os.environ.copy()
    env.update(
        {
            "MYSQL_HOST": "127.0.0.1",
            "MYSQL_PORT": "1",
            "MONGO_HOST": "127.0.0.1",
            "MONGO_PORT": "1",
            "REDIS_HOST": "127.0.0.1",
            "REDIS_PORT": "1",
            "COGGUARD_SERVICE_TIMEOUT_SECONDS": "0.2",
        }
    )

    result = _run_script("--check-services", env=env)
    output = f"{result.stdout}\n{result.stderr}"

    assert result.returncode != 0
    assert "MySQL 127.0.0.1:1" in output
    assert "MongoDB 127.0.0.1:1" in output
    assert "Redis 127.0.0.1:1" in output
    assert "reason:" in output
    assert "PASS" not in output


@pytest.mark.integration
def test_real_migration_roundtrip_uses_disposable_test_database_only():
    if os.environ.get("COGGUARD_RUN_MIGRATION_ROUNDTRIP") != "1":
        pytest.skip(
            "real MySQL migration round-trip is opt-in; set "
            "COGGUARD_RUN_MIGRATION_ROUNDTRIP=1"
        )

    env = os.environ.copy()
    env["COGGUARD_REQUIRE_EXTERNAL_SERVICES"] = "1"
    result = _run_script(env=env)
    output = f"{result.stdout}\n{result.stderr}"

    assert result.returncode == 0, output
    assert "MYSQL_DATABASE_TEST" in output
    assert "upgrade head" in output
    assert "downgrade base" in output
    assert "Final Alembic head: c1d4e8f2a706" in output
    assert "propagation_monitor_profiles" in output
    assert "propagation_alerts" in output
    assert "propagation_alert_actions" in output
    assert "analysis_model_governance_decisions" in output
    assert "analysis_model_activation_approvals" in output
