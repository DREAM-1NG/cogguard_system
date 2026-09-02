"""Persistence-oriented behavior tests for propagation monitoring."""

import asyncio
from datetime import datetime, timezone
from types import SimpleNamespace

from app.services import propagation_monitoring_service


class _Result:
    def __init__(self, value):
        self._value = value

    def scalar_one_or_none(self):
        return self._value


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


def test_monitor_window_uses_snapshot_deltas_and_keeps_three_previous_windows():
    current, previous_windows = propagation_monitoring_service.build_monitor_window(current_total_items=42, current_total_nodes=26, previous_snapshot={"total_items": 30, "total_nodes": 15, "window_history": [{"new_items": 4}, {"new_items": 6}, {"new_items": 8}]})
    assert current == {"new_items": 12, "new_propagation_nodes": 11}
    assert previous_windows == [{"new_items": 4}, {"new_items": 6}, {"new_items": 8}]
