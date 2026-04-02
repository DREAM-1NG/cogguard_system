"""账户行为画像分析模块。

基于已采集的帖子数据，构建账户级行为画像：
- 发文频率与节律分析（作息模式、发文间隔）
- 互动模式（点赞/转发/评论比例）
- 自动化倾向评估（规律性、高频度等异常信号）
"""

from __future__ import annotations

from datetime import datetime
from collections import Counter

import numpy as np
import pandas as pd


def build_account_profiles(posts: list[dict]) -> list[dict]:
    """从帖子列表构建所有账户的行为画像。"""
    if not posts:
        return []

    df = pd.DataFrame(posts)
    if "author_id" not in df.columns:
        return []

    df["ts"] = pd.to_datetime(df.get("timestamp"), errors="coerce", utc=True)
    df = df.dropna(subset=["ts"])

    if df.empty:
        return []

    profiles = []
    for author_id, group in df.groupby("author_id"):
        profile = _analyze_account(str(author_id), group)
        profiles.append(profile)

    profiles.sort(key=lambda p: p["automation_score"], reverse=True)
    return profiles


def _analyze_account(account_id: str, posts: pd.DataFrame) -> dict:
    """分析单个账户的行为特征。"""
    n = len(posts)
    author_name = posts["author_name"].iloc[0] if "author_name" in posts.columns else account_id

    ts_sorted = posts["ts"].sort_values()
    hours = ts_sorted.dt.hour.values

    # 发文时段分布（24小时直方图）
    hour_dist = Counter(hours)
    hour_histogram = [hour_dist.get(h, 0) for h in range(24)]

    # 活跃时段
    if len(hours) > 0:
        peak_hour = int(Counter(hours).most_common(1)[0][0])
        active_hours = len(set(hours))
    else:
        peak_hour = 0
        active_hours = 0

    # 发文间隔分析
    if n >= 2:
        intervals = np.diff(ts_sorted.astype(np.int64) // 10**9)  # 秒
        avg_interval = float(np.mean(intervals))
        std_interval = float(np.std(intervals))
        min_interval = float(np.min(intervals))
        regularity = 1 - (std_interval / avg_interval) if avg_interval > 0 else 0
        regularity = max(0, min(1, regularity))
    else:
        avg_interval = 0
        std_interval = 0
        min_interval = 0
        regularity = 0

    # 互动指标
    likes = posts["likes"].sum() if "likes" in posts.columns else 0
    reposts = posts["reposts"].sum() if "reposts" in posts.columns else 0
    comments = posts["comments_count"].sum() if "comments_count" in posts.columns else 0

    # 内容多样性（unique hashtags / urls）
    all_hashtags = []
    for tags in posts.get("hashtags", pd.Series(dtype=object)).dropna():
        if isinstance(tags, list):
            all_hashtags.extend(tags)
    unique_hashtags = len(set(all_hashtags))

    all_urls = posts["url"].dropna().unique() if "url" in posts.columns else []
    unique_urls = len([u for u in all_urls if u])

    # 自动化倾向评估（0-100 分，越高越可疑）
    automation_score = _calc_automation_score(
        post_count=n,
        regularity=regularity,
        active_hours=active_hours,
        min_interval=min_interval,
        avg_interval=avg_interval,
    )

    time_span_hours = 0
    if n >= 2:
        span = (ts_sorted.iloc[-1] - ts_sorted.iloc[0]).total_seconds() / 3600
        time_span_hours = round(span, 1)

    return {
        "account_id": account_id,
        "author_name": author_name,
        "post_count": n,
        "time_span_hours": time_span_hours,
        "avg_interval_seconds": round(avg_interval, 1),
        "min_interval_seconds": round(min_interval, 1),
        "regularity": round(regularity, 4),
        "peak_hour": peak_hour,
        "active_hours": active_hours,
        "hour_histogram": hour_histogram,
        "total_likes": int(likes),
        "total_reposts": int(reposts),
        "total_comments": int(comments),
        "unique_hashtags": unique_hashtags,
        "unique_urls": unique_urls,
        "automation_score": automation_score,
    }


def _calc_automation_score(
    post_count: int,
    regularity: float,
    active_hours: int,
    min_interval: float,
    avg_interval: float,
) -> int:
    """综合多项指标计算自动化倾向分数（0-100）。"""
    score = 0

    # 发文规律性过高（真人通常不规律）
    if regularity > 0.8:
        score += 25
    elif regularity > 0.5:
        score += 15

    # 活跃时段过少（真人通常分布在多个时段）
    if active_hours <= 2:
        score += 20
    elif active_hours <= 4:
        score += 10

    # 发文间隔过短
    if min_interval < 10:
        score += 25
    elif min_interval < 60:
        score += 15

    # 高频发文
    if post_count > 20 and avg_interval < 300:
        score += 20
    elif post_count > 10 and avg_interval < 600:
        score += 10

    # 批量发文特征
    if post_count >= 5 and avg_interval < 60:
        score += 10

    return min(score, 100)
