"""阶段 4：研究复现模型接入系统测试。"""

from __future__ import annotations

import pytest

from app.schemas.risk import RiskAssessRequest
from app.services import risk_service
from tests.test_risk import _FakeCollection, _FakeDB


@pytest.mark.asyncio
async def test_assess_risk_falls_back_to_rule_mode_without_models(monkeypatch):
    posts = [{
        "platform": "mock_weibo",
        "post_id": "p1",
        "content": "热点事件A 持续传播",
        "author_id": "u1",
        "author_name": "用户1",
        "timestamp": "2026-06-01T10:00:00Z",
        "url": "https://example.com/a",
        "hashtags": ["#热点事件A#"],
        "likes": 1,
        "reposts": 2,
        "comments_count": 3,
    }]
    fake_db = _FakeDB(raw_posts=_FakeCollection(posts), risk_reports=_FakeCollection())
    monkeypatch.setattr(risk_service, "get_mongo_db", lambda: fake_db)
    monkeypatch.setattr(risk_service, "harmful_model_available", lambda: False)
    monkeypatch.setattr(risk_service, "stance_model_available", lambda: False)

    result = await risk_service.assess_risk(
        RiskAssessRequest(platform="mock_weibo", keyword="热点事件A", max_posts=5, analysis_mode="model")
    )

    assert result["analysis_mode"] == "rule"


@pytest.mark.asyncio
async def test_assess_risk_uses_model_mode_when_models_available(monkeypatch):
    posts = [{
        "platform": "mock_weibo",
        "post_id": "p1",
        "content": "热点事件A 持续传播",
        "author_id": "u1",
        "author_name": "用户1",
        "timestamp": "2026-06-01T10:00:00Z",
        "url": "https://example.com/a",
        "hashtags": ["#热点事件A#"],
        "likes": 1,
        "reposts": 2,
        "comments_count": 3,
    }]
    fake_db = _FakeDB(raw_posts=_FakeCollection(posts), risk_reports=_FakeCollection())
    monkeypatch.setattr(risk_service, "get_mongo_db", lambda: fake_db)
    monkeypatch.setattr(risk_service, "harmful_model_available", lambda: True)
    monkeypatch.setattr(risk_service, "stance_model_available", lambda: True)
    monkeypatch.setattr(risk_service, "predict_harmful_labels", lambda _samples: ["harmful"])
    monkeypatch.setattr(risk_service, "predict_stance_labels", lambda _samples: ["support"])

    result = await risk_service.assess_risk(
        RiskAssessRequest(platform="mock_weibo", keyword="热点事件A", max_posts=5, analysis_mode="model")
    )

    assert result["analysis_mode"] == "model"
    assert result["harmful_content"]["top_posts"][0]["harmful_label"] == "harmful"
    assert result["harmful_content"]["top_posts"][0]["stance_label"] == "support"
