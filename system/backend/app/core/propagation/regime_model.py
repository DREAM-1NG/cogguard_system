"""体制切换级联预测模型。

核心机制：LLM 提取的外生事件 + 历史特征 → 体制后验 → 参数化预测 → 混合预测。
"""

from __future__ import annotations

import math

import numpy as np

# 4 种传播体制
REGIMES = ("seeding", "amplification", "peak", "decay")

# 6 种外生事件类型
EVENT_TYPES = (
    "kol_amplification",
    "official_response",
    "platform_intervention",
    "narrative_mutation",
    "coordinated_burst",
    "none",
)

# 事件→体制评分矩阵 W (4×6)，来自 FINAL_PROPOSAL.md
# 行: seeding, amplification, peak, decay
# 列: kol_amp, official_resp, platform_int, narrative_mut, coord_burst, none
W = np.array([
    [-1,  0,  0,  0,  0, +2],  # seeding
    [+2, -1, -1, +1, +2,  0],  # amplification
    [+1, +1,  0,  0, +1,  0],  # peak
    [-1, +2, +2, -1, -1, +1],  # decay
], dtype=float)

TEMPERATURE = 1.0


def _softmax(x: np.ndarray) -> np.ndarray:
    e = np.exp(x - x.max())
    return e / e.sum()


def compute_regime_posterior(
    detected_events: list[dict],
    history_features: dict,
) -> dict[str, float]:
    """计算体制后验概率 p(z|events, history)。

    Parameters
    ----------
    detected_events : list[dict]
        LLM 提取的事件列表，每项含 type 和 confidence。
    history_features : dict
        时序特征，含 velocity, acceleration, hours_since_start。

    Returns
    -------
    dict[str, float]
        4 种体制的后验概率，和为 1。
    """
    # 构建事件评分向量 e ∈ R^6
    e = np.zeros(6, dtype=float)
    for ev in detected_events:
        t = ev.get("type", "none")
        if t in EVENT_TYPES:
            idx = EVENT_TYPES.index(t)
            e[idx] = max(e[idx], ev.get("confidence", 0.5))

    # 如果没有检测到事件，设置 "none" 为 1.0
    if e.sum() < 1e-6:
        e[5] = 1.0  # none

    # 历史先验 b ∈ R^4
    b = _compute_history_prior(history_features)

    # 体制评分 = W @ e + b
    scores = W @ e + b

    # softmax 归一化
    posterior = _softmax(scores / TEMPERATURE)

    return dict(zip(REGIMES, posterior.tolist()))


def _compute_history_prior(features: dict) -> np.ndarray:
    """从历史特征计算体制先验偏置。"""
    velocity = features.get("velocity", 0.0)
    acceleration = features.get("acceleration", 0.0)
    hours = features.get("hours_since_start", 0.0)

    b = np.zeros(4, dtype=float)

    if hours < 2.0:
        b[0] += 1.5  # bias seeding
    if velocity > 0 and acceleration > 0:
        b[1] += 1.5  # bias amplification
    if velocity > 0 and acceleration <= 0:
        b[2] += 1.0  # bias peak
    if velocity < 0:
        b[3] += 1.5  # bias decay

    return b


def forecast_regime(
    regime: str,
    current_volume: float,
    velocity: float,
    acceleration: float,
    horizon_hours: float,
) -> float:
    """单体制参数化预测。

    Parameters
    ----------
    regime : str
        体制名称。
    current_volume : float
        当前小时传播量。
    velocity : float
        当前速度（每小时变化量）。
    horizon_hours : float
        预测时间跨度（小时）。

    Returns
    -------
    float
        预测的传播量（非负）。
    """
    v = max(current_volume, 1.0)
    h = max(horizon_hours, 0.0)

    if regime == "seeding":
        # 线性增长: y = v + β·h
        beta = max(velocity, 0.1)
        return max(v + beta * h, 0.0)

    elif regime == "amplification":
        # 指数增长: y = v · e^(r·h)，上限 10x
        r = max(velocity / max(v, 1.0), 0.01)
        result = v * math.exp(r * h)
        return min(result, v * 10.0)

    elif regime == "peak":
        # Logistic 饱和: y = K / (1 + e^(-k·(h-h0)))
        K = v * 2.0
        k = 1.0
        h0 = max(h / 2, 1.0)
        return K / (1.0 + math.exp(-k * (h - h0)))

    elif regime == "decay":
        # 指数衰减: y = v · e^(-λ·h)
        lam = max(-velocity / max(v, 1.0), 0.05)
        return max(v * math.exp(-lam * h), 0.0)

    return v  # fallback


def mixture_forecast(
    posterior: dict[str, float],
    current_volume: float,
    velocity: float,
    acceleration: float,
    horizons: list[float] | None = None,
) -> dict:
    """混合预测：ŷ = Σ p(z)·f_z(t+h)。

    Returns
    -------
    dict
        含 volume_forecast, confidence_interval, direction, speed。
    """
    if horizons is None:
        horizons = [1.0, 6.0, 24.0]

    volume_forecast = {}
    confidence_intervals = {}

    for h in horizons:
        # 各体制预测
        forecasts = {}
        for regime in REGIMES:
            forecasts[regime] = forecast_regime(
                regime, current_volume, velocity, acceleration, h
            )

        # 混合预测
        y_hat = sum(posterior.get(z, 0.0) * forecasts[z] for z in REGIMES)

        # 方差（体制间不确定性）
        variance = sum(
            posterior.get(z, 0.0) * (forecasts[z] ** 2)
            for z in REGIMES
        ) - y_hat ** 2
        std = math.sqrt(max(variance, 0.0))

        volume_forecast[f"{int(h)}h"] = round(max(y_hat, 0.0))
        confidence_intervals[f"{int(h)}h"] = [
            round(max(y_hat - 1.96 * std, 0.0)),
            round(y_hat + 1.96 * std),
        ]

    # 方向判断（±5% 死区）
    forecast_1h = volume_forecast.get("1h", current_volume)
    delta_ratio = (forecast_1h - current_volume) / max(current_volume, 1.0)
    if delta_ratio > 0.05:
        direction = "rising"
    elif delta_ratio < -0.05:
        direction = "declining"
    else:
        direction = "stable"

    # 速度（加速度）
    speed_phase = max(posterior, key=posterior.get) if posterior else "seeding"

    return {
        "volume_forecast": volume_forecast,
        "confidence_interval": confidence_intervals,
        "direction": direction,
        "speed": {
            "acceleration": round(acceleration, 2),
            "phase": speed_phase,
        },
    }
