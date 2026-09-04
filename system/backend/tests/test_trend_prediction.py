"""CascadeSwitch 趋势预测模块测试。

测试时序特征提取、体制模型、混合预测、LLM mock 模式。
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone, timedelta

import pytest

from app.core.propagation.ts_features import extract_ts_features
from app.core.propagation.regime_model import (
    compute_regime_posterior,
    forecast_regime,
    mixture_forecast,
    REGIMES,
)
from app.core.propagation.trend_predictor import predict_trend


def _ts(hours: int) -> str:
    base = datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    return (base + timedelta(hours=hours)).isoformat()


def _make_growing_posts(n_hours: int = 12) -> list[dict]:
    posts = []
    pid = 0
    for h in range(n_hours):
        count = max(2, int(5 * (1.3 ** h)))
        for i in range(count):
            posts.append({
                "post_id": f"p{pid}", "author_id": f"u{pid % 20}",
                "author_name": f"User{pid % 20}", "timestamp": _ts(h),
                "content": f"帖子内容 {pid}", "url": "https://example.com/topic",
                "hashtags": ["#热点"],
            })
            pid += 1
    return posts


def _make_decaying_posts(n_hours: int = 12) -> list[dict]:
    posts = []
    pid = 0
    for h in range(n_hours):
        count = max(1, int(50 * (0.7 ** h)))
        for i in range(count):
            posts.append({
                "post_id": f"p{pid}", "author_id": f"u{pid % 20}",
                "timestamp": _ts(h), "content": f"帖子 {pid}",
            })
            pid += 1
    return posts


class TestTsFeatures:
    def test_empty(self):
        assert extract_ts_features([])["total_posts"] == 0

    def test_growing_velocity(self):
        r = extract_ts_features(_make_growing_posts(6))
        assert r["velocity"] > 0 and r["trend_direction"] == 1

    def test_decaying_velocity(self):
        r = extract_ts_features(_make_decaying_posts(6))
        assert r["velocity"] < 0 and r["trend_direction"] == -1

    def test_burst_zscore(self):
        assert extract_ts_features(_make_growing_posts(8))["burst_zscore"] > 0


class TestRegimeModel:
    def test_no_events_seeding(self):
        p = compute_regime_posterior([], {"velocity": 0, "acceleration": 0, "hours_since_start": 1})
        assert p["seeding"] > p["amplification"]

    def test_kol_amplification(self):
        p = compute_regime_posterior(
            [{"type": "kol_amplification", "confidence": 0.9}],
            {"velocity": 10, "acceleration": 5, "hours_since_start": 5},
        )
        assert p["amplification"] > p["decay"]

    def test_official_response_decay(self):
        p = compute_regime_posterior(
            [{"type": "official_response", "confidence": 0.9}],
            {"velocity": -5, "acceleration": -2, "hours_since_start": 10},
        )
        assert p["decay"] > p["amplification"]

    def test_sums_to_one(self):
        p = compute_regime_posterior([{"type": "coordinated_burst", "confidence": 0.8}],
                                     {"velocity": 5, "acceleration": 3, "hours_since_start": 3})
        assert abs(sum(p.values()) - 1.0) < 1e-6


class TestForecastRegime:
    def test_seeding_grows(self):
        assert forecast_regime("seeding", 10, 2, 0, 5) > 10

    def test_amplification_capped(self):
        y = forecast_regime("amplification", 10, 5, 2, 3)
        assert 10 < y <= 100

    def test_decay_shrinks(self):
        assert forecast_regime("decay", 50, -10, -2, 5) < 50

    def test_non_negative(self):
        for r in REGIMES:
            assert forecast_regime(r, 10, 1, 0, 5) >= 0


class TestMixtureForecast:
    def test_structure(self):
        r = mixture_forecast({"seeding": .1, "amplification": .6, "peak": .2, "decay": .1}, 20, 5, 2)
        assert "volume_forecast" in r and "1h" in r["volume_forecast"]

    def test_rising(self):
        r = mixture_forecast({"seeding": 0, "amplification": .9, "peak": .1, "decay": 0}, 20, 10, 5)
        assert r["direction"] == "rising"

    def test_declining(self):
        r = mixture_forecast({"seeding": 0, "amplification": 0, "peak": .1, "decay": .9}, 50, -10, -5)
        assert r["direction"] == "declining"

    def test_ci_brackets(self):
        r = mixture_forecast({"seeding": .25, "amplification": .25, "peak": .25, "decay": .25}, 30, 3, 1)
        for h in ["1h", "6h", "24h"]:
            lo, hi = r["confidence_interval"][h]
            assert lo <= r["volume_forecast"][h] <= hi


class TestTrendPredictor:
    def test_mock_llm(self):
        r = asyncio.get_event_loop().run_until_complete(predict_trend(_make_growing_posts(8), mock_llm=True))
        assert r["llm_available"] is False and "volume_forecast" in r

    def test_empty(self):
        r = asyncio.get_event_loop().run_until_complete(predict_trend([], mock_llm=True))
        assert r["confidence"] == 0.0

    def test_output_keys(self):
        r = asyncio.get_event_loop().run_until_complete(predict_trend(_make_growing_posts(6), mock_llm=True))
        for k in ("volume_forecast", "direction", "regime_posterior", "explanation", "confidence", "ts_features"):
            assert k in r

    def test_chinese_explanation(self):
        r = asyncio.get_event_loop().run_until_complete(predict_trend(_make_growing_posts(6), mock_llm=True))
        assert "阶段" in r["explanation"]


class TestRegression:
    def test_propagation_graph_unchanged(self):
        from app.core.propagation import build_propagation_graph
        r = build_propagation_graph(_make_growing_posts(4))
        assert "graph" in r and "key_roles" in r and "evidence_chains" in r
