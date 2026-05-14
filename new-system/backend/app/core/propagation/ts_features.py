"""时序特征提取模块。

将帖子列表按时间聚合为小时级时序特征，供趋势预测使用。
"""

from __future__ import annotations

import math
from collections import Counter

import numpy as np
import pandas as pd


def extract_ts_features(posts: list[dict]) -> dict:
    """从帖子列表提取时序特征。

    Parameters
    ----------
    posts : list[dict]
        帖子列表，每条需含 ``timestamp`` 字段。

    Returns
    -------
    dict
        时序特征字典，含 volumes, velocity, acceleration 等。
    """
    if not posts:
        return _empty_features()

    df = pd.DataFrame(posts)
    df["ts"] = pd.to_datetime(df.get("timestamp"), errors="coerce", utc=True)
    df = df.dropna(subset=["ts"]).sort_values("ts")

    if len(df) < 2:
        return _empty_features()

    # 按小时聚合
    df["hour"] = df["ts"].dt.floor("h")
    hourly = df.groupby("hour").size().sort_index()

    volumes = hourly.values.tolist()
    n = len(volumes)

    if n < 2:
        return {
            "volumes": volumes,
            "velocity": 0.0,
            "acceleration": 0.0,
            "burst_zscore": 0.0,
            "trend_direction": 0,
            "hours_since_start": 0.0,
            "current_volume": volumes[-1] if volumes else 0,
            "total_posts": len(df),
        }

    # 速度：最近两小时的差值
    velocity = float(volumes[-1] - volumes[-2])

    # 加速度：速度的变化
    if n >= 3:
        prev_velocity = float(volumes[-2] - volumes[-3])
        acceleration = velocity - prev_velocity
    else:
        acceleration = 0.0

    # 突发检测：最新小时 vs 滚动均值的 z-score
    arr = np.array(volumes, dtype=float)
    rolling_mean = arr[:-1].mean() if n > 1 else arr[0]
    rolling_std = arr[:-1].std() if n > 1 else 1.0
    if rolling_std < 1e-6:
        rolling_std = 1.0
    burst_zscore = float((arr[-1] - rolling_mean) / rolling_std)

    # 趋势方向：简单线性回归斜率的符号
    x = np.arange(n, dtype=float)
    slope = np.polyfit(x, arr, 1)[0] if n >= 2 else 0.0
    trend_direction = int(np.sign(slope))

    # 事件持续时间
    start = df["ts"].iloc[0]
    end = df["ts"].iloc[-1]
    hours_since_start = max((end - start).total_seconds() / 3600, 0.0)

    return {
        "volumes": volumes,
        "velocity": round(velocity, 2),
        "acceleration": round(acceleration, 2),
        "burst_zscore": round(burst_zscore, 2),
        "trend_direction": trend_direction,
        "hours_since_start": round(hours_since_start, 2),
        "current_volume": volumes[-1],
        "total_posts": len(df),
    }


def _empty_features() -> dict:
    return {
        "volumes": [],
        "velocity": 0.0,
        "acceleration": 0.0,
        "burst_zscore": 0.0,
        "trend_direction": 0,
        "hours_since_start": 0.0,
        "current_volume": 0,
        "total_posts": 0,
    }
