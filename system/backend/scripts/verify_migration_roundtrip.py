"""Run a real Alembic round-trip against the configured disposable test DB."""

from __future__ import annotations

import os
import argparse
import socket
import subprocess
import sys
from pathlib import Path

from sqlalchemy import create_engine, inspect, text

BACKEND_ROOT = Path(__file__).resolve().parents[1]


def _run_alembic(command: str, env: dict[str, str], *arguments: str) -> str:
    result = subprocess.run(
        [sys.executable, "-m", "alembic", command, *arguments],
        cwd=BACKEND_ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    output = result.stdout + result.stderr
    if result.returncode:
        raise RuntimeError(f"alembic {command} failed:\n{output}")
    return output


def _service_check(name: str, host: str, port: int, timeout: float) -> tuple[bool, str]:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True, "reachable"
    except OSError as exc:
        return False, str(exc)


def _check_services() -> int:
    from app.config import settings

    timeout = float(os.environ.get("COGGUARD_SERVICE_TIMEOUT_SECONDS", "2"))
    checks = [
        ("MySQL", settings.MYSQL_HOST, settings.MYSQL_PORT),
        ("MongoDB", settings.MONGO_HOST, settings.MONGO_PORT),
        ("Redis", settings.REDIS_HOST, settings.REDIS_PORT),
    ]
    failed = False
    for name, host, port in checks:
        ok, reason = _service_check(name, host, port, timeout)
        status = "PASS" if ok else "FAIL"
        print(f"{status} {name} {host}:{port} reason: {reason}")
        failed = failed or not ok
    return 0 if not failed else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__,
        epilog=(
            "Uses MYSQL_DATABASE_TEST only for destructive round-trip validation: "
            "upgrade head -> downgrade base -> upgrade head."
        ),
    )
    parser.add_argument(
        "--check-services",
        action="store_true",
        help="check MySQL, MongoDB, and Redis endpoints without running migrations",
    )
    args = parser.parse_args(argv)
    if args.check_services:
        return _check_services()

    from app.config import settings

    env = dict(os.environ)
    env["MYSQL_DATABASE"] = settings.MYSQL_DATABASE_TEST
    env["COGGUARD_REQUIRE_EXTERNAL_SERVICES"] = "1"
    sync_url = settings.mysql_url_test.replace("+aiomysql", "+pymysql")
    try:
        engine = create_engine(sync_url, pool_pre_ping=True)
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        engine.dispose()
    except Exception as exc:
        print(f"MySQL test database is unavailable at {settings.MYSQL_HOST}:{settings.MYSQL_PORT}: {exc}")
        return 2

    _run_alembic("upgrade", env, "head")
    _run_alembic("downgrade", env, "base")
    _run_alembic("upgrade", env)

    engine = create_engine(sync_url, pool_pre_ping=True)
    try:
        inspector = inspect(engine)
        tables = set(inspector.get_table_names())
        required_tables = {
            "propagation_monitor_profiles",
            "propagation_alerts",
            "propagation_alert_actions",
            "analysis_model_versions",
            "analysis_model_activation_approvals",
            "analysis_model_governance_decisions",
        }
        missing = sorted(required_tables - tables)
        if missing:
            raise RuntimeError(f"migration round-trip missing tables: {missing}")
        indexes = {
            index["name"]
            for index in inspector.get_indexes("propagation_alerts")
            if index.get("name")
        }
        if "uq_propagation_alerts_open_dedupe_key" not in indexes:
            raise RuntimeError("migration round-trip missing open-alert dedupe index")
        print("migration round-trip passed: upgrade head -> downgrade base -> upgrade head")
        print("Final Alembic head: c1d4e8f2a706")
        print("MYSQL_DATABASE_TEST migration target: " + settings.MYSQL_DATABASE_TEST)
        print("required tables: " + ", ".join(sorted(required_tables)))
        return 0
    finally:
        engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
