"""传播趋势预测器（CascadeSwitch）。

编排 ts_features → llm_context → regime_model → 输出结构化预测。
"""

from __future__ import annotations

from typing import Any

from .ts_features import extract_ts_features
from .llm_context import extract_events
from .regime_model import compute_regime_posterior, mixture_forecast


async def predict_trend(
    posts: list[dict],
    comments: list[dict] | None = None,
    coordination_signals: dict[str, Any] | None = None,
    *,
    mock_llm: bool = False,
) -> dict:
    """预测传播趋势。

    Parameters
    ----------
    posts : list[dict]
        帖子列表。
    comments : list[dict] | None
        评论列表（当前未直接使用，预留接口）。
    coordination_signals : dict | None
        CoordinationDiscover 协同检测信号。
    mock_llm : bool
        为 True 时跳过 LLM API 调用。

    Returns
    -------
    dict
        结构化趋势预测结果。
    """
    if not posts:
        return _empty_prediction()

    # Step 1: 时序特征提取
    ts = extract_ts_features(posts)
    if ts["total_posts"] < 2:
        return _empty_prediction()

    # Step 2: LLM 事件提取
    event_summary = _build_event_summary(posts)
    top_posts = [str(p.get("content", ""))[:200] for p in posts[-5:]]

    llm_result = await extract_events(
        event_summary=event_summary,
        volumes=ts["volumes"],
        top_posts=top_posts,
        coordination_signals=coordination_signals,
        mock=mock_llm,
    )

    # Step 3: 体制后验计算
    posterior = compute_regime_posterior(
        detected_events=llm_result["events"],
        history_features=ts,
    )

    # Step 4: 混合预测
    forecast = mixture_forecast(
        posterior=posterior,
        current_volume=ts["current_volume"],
        velocity=ts["velocity"],
        acceleration=ts["acceleration"],
    )

    # Step 5: 生成解释
    explanation = _generate_explanation(posterior, llm_result["events"], forecast)

    return {
        **forecast,
        "regime_posterior": posterior,
        "detected_events": llm_result["events"],
        "confidence": _compute_confidence(ts, posterior, llm_result),
        "explanation": explanation,
        "llm_available": llm_result["llm_available"],
        "ts_features": {
            "current_volume": ts["current_volume"],
            "velocity": ts["velocity"],
            "acceleration": ts["acceleration"],
            "burst_zscore": ts["burst_zscore"],
            "hours_since_start": ts["hours_since_start"],
        },
    }


def _build_event_summary(posts: list[dict]) -> str:
    """从帖子构建事件摘要。"""
    if not posts:
        return "无数据"
    n = len(posts)
    first = posts[0]
    last = posts[-1]
    return (
        f"共{n}条帖子，"
        f"最早发布于{first.get('timestamp', '未知')}，"
        f"最新发布于{last.get('timestamp', '未知')}。"
        f"涉及{len({p.get('author_id') for p in posts})}个账号。"
    )


def _compute_confidence(
    ts: dict, posterior: dict, llm_result: dict
) -> float:
    """计算预测置信度。"""
    # 数据充分性
    data_score = min(ts["total_posts"] / 50.0, 1.0)

    # 体制确定性（后验熵的反面）
    import math
    entropy = -sum(
        p * math.log(max(p, 1e-10)) for p in posterior.values()
    )
    max_entropy = math.log(4)  # 均匀分布
    regime_score = 1.0 - (entropy / max_entropy)

    # LLM 可用性
    llm_score = 0.8 if llm_result["llm_available"] else 0.4

    confidence = 0.4 * data_score + 0.3 * regime_score + 0.3 * llm_score
    return round(min(max(confidence, 0.0), 1.0), 2)


_REGIME_NAMES = {
    "seeding": "播种阶段",
    "amplification": "扩散阶段",
    "peak": "峰值阶段",
    "decay": "衰退阶段",
}

_EVENT_NAMES = {
    "kol_amplification": "KOL放大",
    "official_response": "官方回应",
    "platform_intervention": "平台干预",
    "narrative_mutation": "叙事变异",
    "coordinated_burst": "协同爆发",
}


def _generate_explanation(
    posterior: dict, events: list[dict], forecast: dict
) -> str:
    """生成中文趋势解释。"""
    top_regime = max(posterior, key=posterior.get)
    top_prob = posterior[top_regime]
    regime_name = _REGIME_NAMES.get(top_regime, top_regime)

    parts = [f"当前处于{regime_name}(概率{top_prob:.0%})"]

    if events:
        event_strs = [_EVENT_NAMES.get(e["type"], e["type"]) for e in events]
        parts.append(f"检测到事件：{'、'.join(event_strs)}")

    direction = forecast.get("direction", "stable")
    dir_map = {"rising": "上升", "stable": "稳定", "declining": "下降"}
    parts.append(f"预计趋势{dir_map.get(direction, direction)}")

    return "，".join(parts) + "。"


def _empty_prediction() -> dict:
    return {
        "volume_forecast": {"1h": 0, "6h": 0, "24h": 0},
        "confidence_interval": {"1h": [0, 0], "6h": [0, 0], "24h": [0, 0]},
        "direction": "stable",
        "speed": {"acceleration": 0.0, "phase": "seeding"},
        "regime_posterior": {"seeding": 0.25, "amplification": 0.25, "peak": 0.25, "decay": 0.25},
        "detected_events": [],
        "confidence": 0.0,
        "explanation": "数据不足，无法预测。",
        "llm_available": False,
        "ts_features": {},
    }
