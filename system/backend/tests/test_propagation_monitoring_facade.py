from __future__ import annotations

import asyncio
import importlib
from dataclasses import dataclass

import pytest

from app.core.propagation_monitoring import PropagationMonitoring, PropagationMonitoringPorts


def test_propagation_monitoring_is_a_public_core_module():
    core = importlib.import_module("app.core")
    monitoring = importlib.import_module("app.core.propagation_monitoring")

    assert "propagation_monitoring" in core.__all__
    assert monitoring.__all__ == [
        "PropagationMonitoring",
        "PropagationMonitoringPorts",
        "build_default_propagation_monitoring",
    ]


@dataclass
class FakePersistence:
    due_calls: int = 0

    async def run_due_monitor_profiles(self, db):
        self.due_calls += 1
        return [{"status": "ok", "db": db}]


def build_ports(*, observe, forecast=None, persistence=None):
    async def default_forecast(**kwargs):
        return {"status": "ok", **kwargs}

    return PropagationMonitoringPorts(
        observe=observe,
        forecast=forecast or default_forecast,
        validate_cutoff=lambda value: value,
        enforce_forecast=lambda result, **scope: {**result, **scope},
        persistence=persistence or FakePersistence(),
    )


def test_observed_cache_returns_defensive_copies():
    calls = 0

    async def observe(**kwargs):
        nonlocal calls
        calls += 1
        return {"timeline": [{"content": "x" * 200, "raw_data": {"secret": True}}]}

    monitoring = PropagationMonitoring(build_ports(observe=observe))
    first = asyncio.run(monitoring.observed(platform="weibo", event_id="event-1", node_limit=80))
    first["timeline"][0]["content"] = "mutated"
    second = asyncio.run(monitoring.observed(platform="weibo", event_id="event-1", node_limit=80))

    assert calls == 1
    assert second["timeline"][0]["content"].endswith("…")
    assert second["timeline"][0]["content"] != "mutated"
    assert "raw_data" not in second["timeline"][0]


def test_observed_coalesces_concurrent_calls():
    calls = 0

    async def scenario():
        gate = asyncio.Event()

        async def observe(**kwargs):
            nonlocal calls
            calls += 1
            await gate.wait()
            return {"graph": {"nodes": [], "edges": []}}

        monitoring = PropagationMonitoring(build_ports(observe=observe))
        first = asyncio.create_task(monitoring.observed(platform=None, event_id="event-1", node_limit=80))
        second = asyncio.create_task(monitoring.observed(platform=None, event_id="event-1", node_limit=80))
        await asyncio.sleep(0)
        gate.set()
        return await asyncio.gather(first, second)

    results = asyncio.run(scenario())
    assert calls == 1
    assert results[0] == results[1]
    assert results[0] is not results[1]


@pytest.mark.parametrize("ratio", [0.2, 0.4, 0.6])
def test_forecast_rejects_unsupported_observation_ratio(ratio):
    async def observe(**kwargs):
        return {}

    monitoring = PropagationMonitoring(build_ports(observe=observe))
    with pytest.raises(ValueError, match="0.1, 0.3, or 0.5"):
        asyncio.run(
            monitoring.forecast(
                event_id="event-1",
                platform=None,
                top_k=10,
                observed_until=None,
                t_obs=None,
                observation_ratio=ratio,
                prediction_horizon=None,
            )
        )


def test_due_profiles_uses_persistence_port():
    persistence = FakePersistence()

    async def observe(**kwargs):
        return {}

    monitoring = PropagationMonitoring(build_ports(observe=observe, persistence=persistence))
    result = asyncio.run(monitoring.run_due_monitor_profiles("db"))

    assert result == [{"status": "ok", "db": "db"}]
    assert persistence.due_calls == 1
