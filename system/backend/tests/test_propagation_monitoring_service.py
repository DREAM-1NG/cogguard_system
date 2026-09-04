"""Persistence-oriented behavior tests for propagation monitoring."""

import asyncio
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.services import propagation_monitoring_service


class _Result:
    def __init__(self, value):
        self._value = value

    def scalar_one_or_none(self):
        return self._value


class _ScalarsResult:
    def __init__(self, values):
        self._values = list(values)

    def scalars(self):
        return self

    def all(self):
        return list(self._values)


class _RowcountResult:
    def __init__(self, rowcount):
        self.rowcount = rowcount


class _CompetingClaimDB:
    def __init__(self, profile):
        self.profile = profile
        self.claimed = False

    async def execute(self, statement):
        if getattr(statement, "__visit_name__", "") == "update":
            if self.claimed:
                return _RowcountResult(0)
            self.claimed = True
            return _RowcountResult(1)
        return _ScalarsResult([self.profile])

    async def flush(self):
        return None


class _ActionDB:
    def __init__(self, alert):
        self.alert = alert
        self.added = []

    async def execute(self, _statement):
        return _Result(self.alert)

    def add(self, value):
        self.added.append(value)

    async def flush(self):
        return None


def test_apply_alert_action_closes_alert_and_preserves_audit_actor_and_note():
    alert = SimpleNamespace(id=7, event_id="event-1", platform="weibo", alert_type="propagation_surge", severity="high", state="new", trigger_count=1, first_triggered_at=datetime(2026, 8, 15, tzinfo=timezone.utc), last_triggered_at=datetime(2026, 8, 15, tzinfo=timezone.utc), snapshot_id="snapshot-1", model_version_id=None, assigned_to=None, evidence_json="{}", closed_at=None)
    db = _ActionDB(alert)
    result = asyncio.run(propagation_monitoring_service.apply_alert_action(alert_id=7, action="close", note="已完成核验", actor_id=42, db=db))
    assert result["state"] == "closed"
    assert alert.state == "closed"
    assert alert.closed_at is not None
    assert len(db.added) == 1
    assert db.added[0].alert_id == 7
    assert db.added[0].action == "close"
    assert db.added[0].actor_id == 42
    assert db.added[0].note == "已完成核验"


def test_apply_alert_action_normalizes_omitted_note_to_none():
    alert = SimpleNamespace(id=7, event_id="event-1", platform="weibo", alert_type="propagation_surge", severity="high", state="new", trigger_count=1, first_triggered_at=datetime(2026, 8, 15, tzinfo=timezone.utc), last_triggered_at=datetime(2026, 8, 15, tzinfo=timezone.utc), snapshot_id="snapshot-1", model_version_id=None, assigned_to=None, evidence_json="{}", closed_at=None)
    db = _ActionDB(alert)

    asyncio.run(propagation_monitoring_service.apply_alert_action(alert_id=7, action="close", note=None, actor_id=42, db=db))

    assert db.added[0].note is None


@pytest.mark.parametrize("state", ["closed", "ignored"])
def test_apply_alert_action_rejects_reopening_terminal_alert(state):
    alert = SimpleNamespace(id=7, event_id="event-1", platform="weibo", alert_type="propagation_surge", severity="high", state=state, trigger_count=1, first_triggered_at=datetime(2026, 8, 15, tzinfo=timezone.utc), last_triggered_at=datetime(2026, 8, 15, tzinfo=timezone.utc), snapshot_id="snapshot-1", model_version_id=None, assigned_to=None, evidence_json="{}", closed_at=None)
    db = _ActionDB(alert)

    with pytest.raises(ValueError, match="terminal"):
        asyncio.run(propagation_monitoring_service.apply_alert_action(alert_id=7, action="acknowledge", note="retry", actor_id=42, db=db))

    assert alert.state == state
    assert db.added == []


def test_create_event_snapshot_registers_reconstructable_snapshot_with_stable_content_fingerprint(monkeypatch):
    registered = []

    class _Registry:
        def __init__(self, *, mongo_db, store):
            self.mongo_db = mongo_db
            self.store = store

        async def register_event_snapshot(self, snapshot, *, created_by):
            registered.append((snapshot, created_by))
            return snapshot

    monkeypatch.setattr(propagation_monitoring_service, "AnalysisRegistry", _Registry)
    monkeypatch.setattr(propagation_monitoring_service, "SqlAlchemyAnalysisStore", lambda db: db)
    posts = [{
        "event_id": "event-1",
        "platform": "weibo",
        "post_id": "post-1",
        "author_id": "user-1",
        "timestamp": "2026-08-15T08:00:00+00:00",
        "content": "same evidence",
    }]
    comments = [{
        "event_id": "event-1",
        "platform": "weibo",
        "comment_id": "comment-1",
        "post_id": "post-1",
        "author_id": "user-2",
        "timestamp": "2026-08-15T08:01:00+00:00",
        "content": "supporting reply",
    }]
    common = {
        "db": object(),
        "event_id": "event-1",
        "platform": "weibo",
        "observed": {"data_scope": {"posts": 1, "comments": 1}},
        "prediction": {"data_scope": {"posts": 1}},
        "posts": posts,
        "comments": comments,
    }

    first = asyncio.run(propagation_monitoring_service._create_event_snapshot(
        **common, captured_at=datetime(2026, 8, 15, 8, 5, tzinfo=timezone.utc)
    ))
    second = asyncio.run(propagation_monitoring_service._create_event_snapshot(
        **common, captured_at=datetime(2026, 8, 15, 8, 15, tzinfo=timezone.utc)
    ))

    assert len(registered) == 2
    assert registered[0][0].posts[0]["post_id"] == "post-1"
    assert registered[0][0].comments[0]["comment_id"] == "comment-1"
    assert registered[0][0].snapshot_id.startswith("snapshot_")
    assert first.data_fingerprint == second.data_fingerprint
    assert first.snapshot_id == second.snapshot_id


def test_due_monitor_profiles_allow_only_one_competing_claim(monkeypatch):
    profile = SimpleNamespace(
        id=1,
        event_id="event-1",
        platform="weibo",
        enabled=True,
        interval_minutes=5,
        last_success_at=None,
        claim_token=None,
        claim_expires_at=None,
    )
    db = _CompetingClaimDB(profile)
    calls = 0
    entered = asyncio.Event()
    release = asyncio.Event()

    async def fake_cycle(**_kwargs):
        nonlocal calls
        calls += 1
        entered.set()
        await release.wait()
        return {"status": "ok"}

    async def fake_release(*_args, **_kwargs):
        return None

    monkeypatch.setattr(propagation_monitoring_service, "run_monitoring_cycle", fake_cycle)
    monkeypatch.setattr(propagation_monitoring_service, "_release_profile_claim", fake_release, raising=False)

    async def scenario():
        now = datetime(2026, 8, 15, 8, 0, tzinfo=timezone.utc)
        first = asyncio.create_task(propagation_monitoring_service.run_due_monitor_profiles(db, now=now))
        await entered.wait()
        second = asyncio.create_task(propagation_monitoring_service.run_due_monitor_profiles(db, now=now))
        await asyncio.sleep(0)
        release.set()
        return await asyncio.gather(first, second)

    results = asyncio.run(scenario())

    assert calls == 1
    assert results[0] == [{"status": "ok"}]
    assert results[1] == []


def test_claim_recheck_reads_current_database_row_after_lease_commit():
    profile = SimpleNamespace(id=7, claim_token="claim-a")

    class _Result:
        def scalar_one_or_none(self):
            return None

    class _DB:
        async def execute(self, _statement):
            return _Result()

    assert asyncio.run(
        propagation_monitoring_service._claim_is_current(
            _DB(), profile=profile, claim_token="claim-a",
            reference=datetime(2026, 8, 15, 8, 0, tzinfo=timezone.utc),
        )
    ) is False


def test_propagation_alerts_have_nullable_unique_open_dedupe_key():
    from app.models.analysis import PropagationAlert

    column = PropagationAlert.__table__.c["open_dedupe_key"]
    assert column.nullable is True
    assert any(index.name == "uq_propagation_alerts_open_dedupe_key" and index.unique for index in PropagationAlert.__table__.indexes)


def test_monitoring_claim_and_alert_dedupe_columns_have_an_alembic_migration():
    versions = Path(__file__).resolve().parents[1] / "alembic" / "versions"
    migration_sources = "\n".join(
        path.read_text(encoding="utf-8")
        for path in versions.glob("*.py")
    )

    assert 'sa.Column("claim_token"' in migration_sources
    assert 'sa.Column("claim_expires_at"' in migration_sources
    assert 'sa.Column("open_dedupe_key"' in migration_sources
    assert '"uq_propagation_alerts_open_dedupe_key"' in migration_sources
    assert "UPDATE propagation_alerts" in migration_sources


def test_monitor_window_uses_snapshot_deltas_and_keeps_three_previous_windows():
    current, previous_windows = propagation_monitoring_service.build_monitor_window(current_total_items=42, current_total_nodes=26, previous_snapshot={"total_items": 30, "total_nodes": 15, "window_history": [{"new_items": 4}, {"new_items": 6}, {"new_items": 8}]})
    assert current == {"new_items": 12, "new_propagation_nodes": 11}
    assert previous_windows == [{"new_items": 4}, {"new_items": 6}, {"new_items": 8}]
