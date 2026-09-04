"""Run a real Alembic round-trip against the configured disposable test DB.

The command changes only the database named by ``MYSQL_DATABASE_TEST``. It
never uses the regular ``MYSQL_DATABASE`` value for migration operations.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable

from sqlalchemy import create_engine, inspect, text

BACKEND_ROOT = Path(__file__).resolve().parents[1]

EXPECTED_HEAD = "c1d4e8f2a706"
STRICT_VALUES = frozenset({"1", "true", "yes", "on"})

REQUIRED_TABLES = frozenset(
    {
        "propagation_monitor_profiles",
        "propagation_alerts",
        "propagation_alert_actions",
        "analysis_model_versions",
        "analysis_model_activations",
        "analysis_model_governance_decisions",
        "analysis_model_activation_approvals",
    }
)

REQUIRED_INDEXES: dict[str, frozenset[str]] = {
    "propagation_monitor_profiles": frozenset(
        {
            "ix_propagation_monitor_profiles_event_id",
            "ix_propagation_monitor_profiles_platform",
            "ix_propagation_monitor_profiles_enabled",
            "ix_propagation_monitor_profiles_last_snapshot_id",
            "ix_propagation_monitor_profiles_claim_token",
            "ix_propagation_monitor_profiles_claim_expires_at",
        }
    ),
    "propagation_alerts": frozenset(
        {
            "ix_propagation_alerts_event_id",
            "ix_propagation_alerts_platform",
            "ix_propagation_alerts_alert_type",
            "ix_propagation_alerts_severity",
            "ix_propagation_alerts_state",
            "ix_propagation_alerts_dedupe_key",
            "ix_propagation_alerts_first_triggered_at",
            "ix_propagation_alerts_last_triggered_at",
            "ix_propagation_alerts_snapshot_id",
            "ix_propagation_alerts_model_version_id",
            "ix_propagation_alerts_assigned_to",
            "uq_propagation_alerts_open_dedupe_key",
        }
    ),
    "propagation_alert_actions": frozenset(
        {
            "ix_propagation_alert_actions_alert_id",
            "ix_propagation_alert_actions_action",
            "ix_propagation_alert_actions_actor_id",
        }
    ),
    "analysis_model_versions": frozenset(
        {
            "ix_analysis_model_versions_technology",
            "ix_analysis_model_versions_artifact_hash",
            "ix_analysis_model_versions_status",
        }
    ),
    "analysis_model_activations": frozenset(
        {
            "ix_analysis_model_activations_technology",
            "ix_analysis_model_activations_model_version_id",
        }
    ),
    "analysis_model_governance_decisions": frozenset(
        {
            "ix_analysis_model_governance_decisions_technology",
            "ix_analysis_model_governance_decisions_model_version_id",
            "ix_analysis_model_governance_decisions_previous_model_version_id",
            "ix_analysis_model_governance_decisions_decision_type",
            "ix_analysis_model_governance_decisions_decided_by",
        }
    ),
    "analysis_model_activation_approvals": frozenset(
        {
            "ix_analysis_model_activation_approvals_model_version_id",
            "ix_analysis_model_activation_approvals_approver_id",
        }
    ),
}

REQUIRED_UNIQUE_CONSTRAINTS: dict[str, frozenset[str]] = {
    "propagation_monitor_profiles": frozenset(
        {"uq_propagation_monitor_profiles_event_platform"}
    ),
    "analysis_model_governance_decisions": frozenset(
        {"uq_analysis_model_governance_decisions_decision_id"}
    ),
    "analysis_model_activation_approvals": frozenset(
        {
            "uq_analysis_model_activation_approvals_approval_id",
            "uq_analysis_model_activation_approvals_model_approver",
        }
    ),
}


def _external_services_required() -> bool:
    return os.environ.get("COGGUARD_REQUIRE_EXTERNAL_SERVICES", "").strip().lower() in STRICT_VALUES


def _service_timeout() -> float:
    raw = os.environ.get("COGGUARD_SERVICE_TIMEOUT_SECONDS", "2")
    try:
        timeout = float(raw)
    except ValueError as exc:
        raise ValueError("COGGUARD_SERVICE_TIMEOUT_SECONDS must be a positive number") from exc
    if timeout <= 0:
        raise ValueError("COGGUARD_SERVICE_TIMEOUT_SECONDS must be a positive number")
    return timeout


def _reason(exc: BaseException) -> str:
    message = str(exc).strip().replace("\r", " ").replace("\n", " ")
    return message or exc.__class__.__name__


def _mysql_sync_url(settings: Any) -> str:
    return settings.mysql_url_test.replace("+aiomysql", "+pymysql")


def _mysql_check(settings: Any, timeout: float) -> tuple[bool, str]:
    engine = None
    try:
        engine = create_engine(
            _mysql_sync_url(settings),
            pool_pre_ping=True,
            connect_args={"connect_timeout": max(1, int(timeout))},
        )
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return True, "SELECT 1 succeeded"
    except Exception as exc:
        return False, _reason(exc)
    finally:
        if engine is not None:
            engine.dispose()


def _mongo_check(settings: Any, timeout: float) -> tuple[bool, str]:
    client = None
    try:
        from pymongo import MongoClient

        timeout_ms = max(1, int(timeout * 1000))
        client = MongoClient(
            host=settings.MONGO_HOST,
            port=settings.MONGO_PORT,
            username=settings.MONGO_USER,
            password=settings.MONGO_PASSWORD,
            authSource="admin",
            serverSelectionTimeoutMS=timeout_ms,
            connectTimeoutMS=timeout_ms,
        )
        client.admin.command("ping")
        return True, "admin ping succeeded"
    except Exception as exc:
        return False, _reason(exc)
    finally:
        if client is not None:
            client.close()


def _redis_check(settings: Any, timeout: float) -> tuple[bool, str]:
    client = None
    try:
        import redis

        client = redis.Redis.from_url(
            settings.redis_url,
            socket_connect_timeout=timeout,
            socket_timeout=timeout,
            decode_responses=True,
        )
        client.ping()
        return True, "PING succeeded"
    except Exception as exc:
        return False, _reason(exc)
    finally:
        if client is not None:
            client.close()


def _check_services() -> int:
    from app.config import settings

    try:
        timeout = _service_timeout()
    except ValueError as exc:
        print(f"FAIL service readiness: reason: {_reason(exc)}")
        return 1

    checks: tuple[tuple[str, str, int, Callable[[Any, float], tuple[bool, str]]], ...] = (
        ("MySQL", settings.MYSQL_HOST, settings.MYSQL_PORT, _mysql_check),
        ("MongoDB", settings.MONGO_HOST, settings.MONGO_PORT, _mongo_check),
        ("Redis", settings.REDIS_HOST, settings.REDIS_PORT, _redis_check),
    )
    failed = False
    for name, host, port, check in checks:
        try:
            ok, detail = check(settings, timeout)
        except Exception as exc:
            ok, detail = False, _reason(exc)
        status = "PASS" if ok else "FAIL"
        suffix = "ready" if ok else f"reason: {detail}"
        print(f"{status} {name} {host}:{port} {suffix}")
        failed = failed or not ok
    return 1 if failed else 0


def _run_alembic(action: str, revision: str, env: dict[str, str]) -> str:
    result = subprocess.run(
        [sys.executable, "-m", "alembic", action, revision],
        cwd=BACKEND_ROOT,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    output = (result.stdout or "") + (result.stderr or "")
    if result.returncode:
        raise RuntimeError(f"alembic {action} {revision} failed: {_reason(RuntimeError(output))}")
    return output


def _database_guard(settings: Any) -> str | None:
    test_database = settings.MYSQL_DATABASE_TEST.strip()
    production_database = settings.MYSQL_DATABASE.strip()
    if not test_database:
        return "MYSQL_DATABASE_TEST is empty; a dedicated disposable database is required"
    if test_database.casefold() == production_database.casefold():
        return (
            "MYSQL_DATABASE_TEST must differ from MYSQL_DATABASE; "
            "refusing to run against the production database"
        )
    return None


def _verify_schema(settings: Any) -> tuple[str, dict[str, list[str]]]:
    from alembic.runtime.migration import MigrationContext

    engine = create_engine(_mysql_sync_url(settings), pool_pre_ping=True)
    try:
        with engine.connect() as connection:
            current_heads = tuple(MigrationContext.configure(connection).get_current_heads())
            if current_heads != (EXPECTED_HEAD,):
                raise RuntimeError(
                    f"expected Alembic head {EXPECTED_HEAD}, found {', '.join(current_heads) or '(none)'}"
                )
            inspector = inspect(connection)
            tables = set(inspector.get_table_names())
            missing_tables = sorted(REQUIRED_TABLES - tables)
            if missing_tables:
                raise RuntimeError(f"missing required tables: {', '.join(missing_tables)}")

            missing_indexes: dict[str, list[str]] = {}
            missing_constraints: dict[str, list[str]] = {}
            for table, required in REQUIRED_INDEXES.items():
                found = {
                    index.get("name")
                    for index in inspector.get_indexes(table)
                    if index.get("name")
                }
                found.update(
                    constraint.get("name")
                    for constraint in inspector.get_unique_constraints(table)
                    if constraint.get("name")
                )
                missing = sorted(required - found)
                if missing:
                    missing_indexes[table] = missing
            for table, required in REQUIRED_UNIQUE_CONSTRAINTS.items():
                found = {
                    constraint.get("name")
                    for constraint in inspector.get_unique_constraints(table)
                    if constraint.get("name")
                }
                found.update(
                    index.get("name")
                    for index in inspector.get_indexes(table)
                    if index.get("unique") and index.get("name")
                )
                missing = sorted(required - found)
                if missing:
                    missing_constraints[table] = missing
            if missing_indexes or missing_constraints:
                details: list[str] = []
                if missing_indexes:
                    details.append(f"indexes={missing_indexes}")
                if missing_constraints:
                    details.append(f"unique_constraints={missing_constraints}")
                raise RuntimeError("missing required schema indexes: " + "; ".join(details))
            return EXPECTED_HEAD, {
                "tables": sorted(REQUIRED_TABLES),
                "indexes": sorted({name for names in REQUIRED_INDEXES.values() for name in names}),
            }
    finally:
        engine.dispose()


def _roundtrip() -> int:
    from app.config import settings

    guard_error = _database_guard(settings)
    if guard_error:
        print(f"FAIL migration target {settings.MYSQL_HOST}:{settings.MYSQL_PORT}: {guard_error}")
        return 1

    env = dict(os.environ)
    env["MYSQL_DATABASE"] = settings.MYSQL_DATABASE_TEST
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    target = f"{settings.MYSQL_HOST}:{settings.MYSQL_PORT}/{settings.MYSQL_DATABASE_TEST}"
    print(f"Migration target: MYSQL_DATABASE_TEST at {target}")

    try:
        timeout = _service_timeout()
    except ValueError as exc:
        print(f"FAIL MySQL test database {target} reason: {_reason(exc)}")
        return 1
    available, detail = _mysql_check(settings, timeout)
    if not available:
        strict = _external_services_required()
        status = "FAIL" if strict else "SKIP"
        print(f"{status} MySQL test database {target} reason: {detail}")
        return 1 if strict else 0

    for action, revision in (("upgrade", "head"), ("downgrade", "base"), ("upgrade", "head")):
        print(f"RUN alembic {action} {revision}")
        try:
            _run_alembic(action, revision, env)
        except Exception as exc:
            print(f"FAIL alembic {action} {revision}: {_reason(exc)}")
            return 1

    try:
        final_head, schema = _verify_schema(settings)
    except Exception as exc:
        print(f"FAIL schema inspection: {_reason(exc)}")
        return 1

    print(f"Final Alembic head: {final_head}")
    print("Required tables: " + ", ".join(schema["tables"]))
    print("Required indexes verified: " + str(len(schema["indexes"])))
    print("Migration round-trip: PASS")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Uses MYSQL_DATABASE_TEST only for destructive round-trip validation.\n"
            "Sequence: upgrade head -> downgrade base -> upgrade head.\n"
            "Use --check-services to probe MySQL, MongoDB, and Redis readiness."
        ),
    )
    parser.add_argument(
        "--check-services",
        action="store_true",
        help="check MySQL, MongoDB, and Redis endpoints without running migrations",
    )
    args = parser.parse_args(argv)
    return _check_services() if args.check_services else _roundtrip()


if __name__ == "__main__":
    raise SystemExit(main())
