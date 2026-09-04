"""Event-scoped propagation monitoring alert rules and orchestration helpers."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timedelta, timezone
from statistics import median
from typing import Any


DEFAULT_ALERT_THRESHOLDS: dict[str, dict[str, float | int]] = {
    "propagation_surge": {"minimum_new_items": 10, "median_multiplier": 2.0},
    "forecast_scale_jump": {"growth_multiplier": 1.5, "minimum_increment": 20},
    "path_structure_change": {"minimum_depth_increase": 1, "minimum_new_nodes": 10},
    "coordination_spread": {"minimum_group_accounts": 3},
}

OPEN_ALERT_STATES = frozenset({"new", "acknowledged", "ignored"})
ALERT_STATE_LABELS = {"new": "新建", "acknowledged": "已确认", "closed": "已关闭", "ignored": "已忽略"}
ALERT_TYPE_LABELS = {
    "propagation_surge": "传播突增",
    "forecast_scale_jump": "预测规模跃升",
    "path_structure_change": "路径结构变化",
    "coordination_spread": "协同传播",
}
SEVERITY_LABELS = {"medium": "中", "high": "高", "critical": "严重"}
ALERT_DEDUPLICATION_WINDOW = timedelta(minutes=30)

__all__ = [
    "ALERT_DEDUPLICATION_WINDOW", "ALERT_STATE_LABELS", "ALERT_TYPE_LABELS", "DEFAULT_ALERT_THRESHOLDS",
    "OPEN_ALERT_STATES", "SEVERITY_LABELS", "evaluate_alert_signals", "is_deduplicated_alert", "severity_for_signals",
]


def _as_mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _number(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _nested_value(record: Mapping[str, Any], *path: str) -> Any:
    value: Any = record
    for key in path:
        if not isinstance(value, Mapping):
            return None
        value = value.get(key)
    return value


def _merge_thresholds(overrides: Mapping[str, Any] | None) -> dict[str, dict[str, float | int]]:
    merged = {name: dict(values) for name, values in DEFAULT_ALERT_THRESHOLDS.items()}
    for signal_type, values in _as_mapping(overrides).items():
        if signal_type in merged and isinstance(values, Mapping):
            merged[signal_type].update(values)
    return merged


def _analysis_depth(result: Mapping[str, Any]) -> int:
    meta = _nested_value(result, "diffusion_summary", "meta")
    if not isinstance(meta, Mapping):
        meta = _nested_value(result, "path_analysis", "meta")
    return max(0, int(_number(_as_mapping(meta).get("max_depth"))))


def _forecast_size(prediction: Mapping[str, Any]) -> tuple[int, int] | None:
    if str(prediction.get("status") or "") != "ok":
        return None
    macro = _as_mapping(prediction.get("macro"))
    observed_size = max(0, int(_number(macro.get("observed_size"))))
    predicted_size = macro.get("predicted_size")
    for point in macro.get("trend_points") if isinstance(macro.get("trend_points"), list) else []:
        item = _as_mapping(point)
        if int(_number(item.get("horizon_hours"))) == 24:
            predicted_size = item.get("predicted_size", predicted_size)
            break
    if predicted_size is None:
        return None
    return observed_size, max(0, int(_number(predicted_size)))


def _largest_coordination_group(coordination: Mapping[str, Any]) -> int:
    groups = coordination.get("group_stats")
    if not isinstance(groups, list):
        groups = _nested_value(coordination, "network", "clusters")
    largest = 0
    for group in groups if isinstance(groups, list) else []:
        values = _as_mapping(group)
        largest = max(largest, int(_number(values.get("account_count", values.get("member_count", values.get("size", 0))))))
    return largest


def evaluate_alert_signals(
    *, current_window: Mapping[str, Any], previous_windows: list[Mapping[str, Any]],
    current_observed_analysis: Mapping[str, Any], previous_observed_analysis: Mapping[str, Any] | None,
    prediction: Mapping[str, Any] | None, coordination: Mapping[str, Any] | None,
    thresholds: Mapping[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Evaluate the four evidence-backed propagation monitoring signals."""
    effective = _merge_thresholds(thresholds)
    signals: list[dict[str, Any]] = []
    current_items = max(0, int(_number(current_window.get("new_items"))))
    historical_items = [max(0, int(_number(window.get("new_items")))) for window in previous_windows[-3:]]
    surge_rule = effective["propagation_surge"]
    historical_median = median(historical_items) if historical_items else None
    if historical_median is not None and current_items >= int(surge_rule["minimum_new_items"]) and current_items >= historical_median * float(surge_rule["median_multiplier"]):
        signals.append({"type": "propagation_surge", "label": ALERT_TYPE_LABELS["propagation_surge"], "metrics": {"new_items": current_items, "previous_window_median": historical_median, "median_multiplier": float(surge_rule["median_multiplier"])}})

    forecast = _forecast_size(_as_mapping(prediction))
    forecast_rule = effective["forecast_scale_jump"]
    if forecast is not None:
        observed_size, predicted_size = forecast
        predicted_increment = predicted_size - observed_size
        if predicted_size >= observed_size * float(forecast_rule["growth_multiplier"]) and predicted_increment >= int(forecast_rule["minimum_increment"]):
            signals.append({"type": "forecast_scale_jump", "label": ALERT_TYPE_LABELS["forecast_scale_jump"], "metrics": {"observed_size": observed_size, "predicted_size_24h": predicted_size, "predicted_increment": predicted_increment}})

    previous_depth = _analysis_depth(_as_mapping(previous_observed_analysis))
    current_depth = _analysis_depth(current_observed_analysis)
    new_nodes = max(0, int(_number(current_window.get("new_propagation_nodes"))))
    structure_rule = effective["path_structure_change"]
    if current_depth - previous_depth >= int(structure_rule["minimum_depth_increase"]) and new_nodes >= int(structure_rule["minimum_new_nodes"]):
        signals.append({"type": "path_structure_change", "label": ALERT_TYPE_LABELS["path_structure_change"], "metrics": {"previous_max_depth": previous_depth, "current_max_depth": current_depth, "new_propagation_nodes": new_nodes}})

    largest_group = _largest_coordination_group(_as_mapping(coordination))
    coordination_rule = effective["coordination_spread"]
    if largest_group >= int(coordination_rule["minimum_group_accounts"]):
        signals.append({"type": "coordination_spread", "label": ALERT_TYPE_LABELS["coordination_spread"], "metrics": {"largest_group_accounts": largest_group}})
    return signals


def severity_for_signals(signals: list[Mapping[str, Any]]) -> str | None:
    if len(signals) <= 0:
        return None
    if len(signals) == 1:
        return "medium"
    if len(signals) == 2:
        return "high"
    return "critical"


def _alert_value(alert: Any, key: str) -> Any:
    return alert.get(key) if isinstance(alert, Mapping) else getattr(alert, key, None)


def _normalize_datetime(value: Any) -> datetime | None:
    if not isinstance(value, datetime):
        return None
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def is_deduplicated_alert(alert: Any, *, event_id: str, platform: str | None, alert_type: str, now: datetime | None = None) -> bool:
    """Return whether an open matching alert is still in the 30-minute window."""
    if str(_alert_value(alert, "event_id") or "") != str(event_id or ""):
        return False
    if str(_alert_value(alert, "platform") or "") != str(platform or ""):
        return False
    if str(_alert_value(alert, "alert_type") or "") != str(alert_type or ""):
        return False
    if str(_alert_value(alert, "state") or "") not in OPEN_ALERT_STATES:
        return False
    triggered_at = _normalize_datetime(_alert_value(alert, "last_triggered_at"))
    reference = _normalize_datetime(now) or datetime.now(timezone.utc)
    return triggered_at is not None and reference - triggered_at <= ALERT_DEDUPLICATION_WINDOW
