"""Behavior tests for event-scoped propagation monitoring alerts."""

from datetime import datetime, timedelta, timezone

from app.services.propagation_alert_service import (
    DEFAULT_ALERT_THRESHOLDS,
    evaluate_alert_signals,
    is_deduplicated_alert,
    severity_for_signals,
)


def _observed_analysis(*, max_depth: int = 3, node_count: int = 12) -> dict:
    return {"diffusion_summary": {"meta": {"max_depth": max_depth, "total_nodes": node_count}}}


def _prediction(*, observed_size: int = 20, predicted_size: int = 55) -> dict:
    return {"status": "ok", "macro": {"observed_size": observed_size, "predicted_size": predicted_size, "trend_points": [{"horizon_hours": 1, "predicted_size": 24}, {"horizon_hours": 6, "predicted_size": 35}, {"horizon_hours": 24, "predicted_size": predicted_size}]}}


def _coordination(*, largest_group_size: int = 0) -> dict:
    return {"group_stats": ([{"account_count": largest_group_size}] if largest_group_size else [])}


def test_evaluate_alert_signals_detects_all_four_event_signals():
    signals = evaluate_alert_signals(
        current_window={"new_items": 12, "new_propagation_nodes": 12},
        previous_windows=[{"new_items": 3}, {"new_items": 5}, {"new_items": 6}],
        current_observed_analysis=_observed_analysis(max_depth=4, node_count=25),
        previous_observed_analysis=_observed_analysis(max_depth=3, node_count=13),
        prediction=_prediction(), coordination=_coordination(largest_group_size=3),
    )
    assert [signal["type"] for signal in signals] == ["propagation_surge", "forecast_scale_jump", "path_structure_change", "coordination_spread"]
    assert severity_for_signals(signals) == "critical"


def test_evaluate_alert_signals_honors_event_threshold_overrides():
    signals = evaluate_alert_signals(
        current_window={"new_items": 12, "new_propagation_nodes": 0},
        previous_windows=[{"new_items": 3}, {"new_items": 5}, {"new_items": 6}],
        current_observed_analysis=_observed_analysis(), previous_observed_analysis=_observed_analysis(),
        prediction=_prediction(observed_size=20, predicted_size=50), coordination=_coordination(),
        thresholds={**DEFAULT_ALERT_THRESHOLDS, "propagation_surge": {"minimum_new_items": 13, "median_multiplier": 3.0}, "forecast_scale_jump": {"growth_multiplier": 3.0, "minimum_increment": 40}},
    )
    assert signals == []


def test_deduplicate_only_an_open_matching_alert_inside_thirty_minutes():
    now = datetime(2026, 8, 15, 8, 0, tzinfo=timezone.utc)
    open_alert = {"event_id": "event-1", "platform": "weibo", "alert_type": "propagation_surge", "state": "new", "last_triggered_at": now - timedelta(minutes=29)}
    assert is_deduplicated_alert(open_alert, event_id="event-1", platform="weibo", alert_type="propagation_surge", now=now)
    assert not is_deduplicated_alert({**open_alert, "state": "closed"}, event_id="event-1", platform="weibo", alert_type="propagation_surge", now=now)
    assert not is_deduplicated_alert({**open_alert, "last_triggered_at": now - timedelta(minutes=31)}, event_id="event-1", platform="weibo", alert_type="propagation_surge", now=now)
