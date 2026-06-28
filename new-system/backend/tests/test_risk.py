"""风险研判模块测试。"""

from __future__ import annotations

import pytest

from app.core.risk.harmful_detector import analyze_harmful_content
from app.core.risk.llm_bridge import build_llm_bridge_result
from app.core.risk.stance_detector import derive_stance_target, detect_stance
from app.schemas.risk import RiskAssessRequest
from app.services import risk_service


class _FakeCursor:
    def __init__(self, items):
        self._items = list(items)

    def sort(self, *_args, **_kwargs):
        return self

    def limit(self, limit: int):
        self._items = self._items[:limit]
        return self

    async def to_list(self, length: int | None = None):
        if length is None:
            return list(self._items)
        return list(self._items[:length])


class _FakeCollection:
    def __init__(self, items=None):
        self.items = list(items or [])
        self.inserted = []
        self.inject_object_id = False

    def find(self, mongo_filter=None, _projection=None):
        mongo_filter = mongo_filter or {}
        filtered = []
        for item in self.items:
            if mongo_filter.get("platform") and item.get("platform") != mongo_filter["platform"]:
                continue
            post_id_filter = mongo_filter.get("post_id")
            if post_id_filter and item.get("post_id") not in post_id_filter.get("$in", []):
                continue
            filtered.append(item)
        return _FakeCursor(filtered)

    async def insert_one(self, item):
        if self.inject_object_id:
            item["_id"] = object()
        self.inserted.append(item)

    async def find_one(self, mongo_filter, _projection=None):
        for item in self.inserted:
            if item.get("report_id") == mongo_filter.get("report_id"):
                return item
        return None


class _FakeDB(dict):
    def __getitem__(self, name):
        return super().__getitem__(name)


def test_analyze_harmful_content_flags_violent_text():
    result = analyze_harmful_content("大家一起冲，必须把他打死！")
    assert result["label"] == "harmful"
    assert result["score"] > 0.5


def test_detect_stance_support_and_query():
    support = detect_stance("我支持这个说法，必须重视", "这个说法")
    query = detect_stance("这是真的吗？有证据吗？", "这个说法")
    assert support["label"] == "support"
    assert query["label"] == "query"


def test_derive_stance_target_strips_hashtag_wrappers():
    target = derive_stance_target([{"hashtags": ["#热点话题#", "#其他#"]}])
    assert target == "热点话题"


def test_build_llm_bridge_result_disabled_by_default():
    result = build_llm_bridge_result(
        target="热点话题",
        phase_result={"risk_level": "medium", "phase": "coordination", "phase_label": "协同期", "rationale": ["检测到明显协同行为"]},
        disarm_result={"summary": "Coordinated Amplification"},
        evidence_pack={"propagation": {"claims": [{"object_id": "https://example.com/a"}]}},
        recommendations=[{"action": "内容处置", "description": "优先审核高风险帖子"}],
    )
    assert result["status"] == "disabled"
    assert "suggested_prompt" in result


def test_risk_assess_request_defaults_to_agent_mode():
    req = RiskAssessRequest()
    assert req.analysis_mode == "agent"


@pytest.mark.asyncio
async def test_assess_risk_generates_structured_report(monkeypatch):
    posts = [
        {
            "platform": "weibo",
            "post_id": "p1",
            "content": "这是假的，别信，大家不要被带节奏",
            "author_id": "u1",
            "author_name": "用户1",
            "timestamp": "2026-06-01T10:00:00Z",
            "url": "https://example.com/a",
            "hashtags": ["热点话题"],
            "likes": 1,
            "reposts": 2,
            "comments_count": 3,
        },
        {
            "platform": "weibo",
            "post_id": "p2",
            "content": "支持这个说法，转发扩散，必须重视",
            "author_id": "u2",
            "author_name": "用户2",
            "timestamp": "2026-06-01T10:00:20Z",
            "url": "https://example.com/a",
            "hashtags": ["热点话题"],
            "likes": 5,
            "reposts": 10,
            "comments_count": 1,
        },
    ]
    fake_db = _FakeDB(
        raw_posts=_FakeCollection(posts),
        risk_reports=_FakeCollection(),
    )
    monkeypatch.setattr(risk_service, "get_mongo_db", lambda: fake_db)

    result = await risk_service.assess_risk(
        RiskAssessRequest(platform="weibo", keyword="热点", max_posts=10, stance_target="热点话题")
    )

    assert result["target"] == "热点话题"
    assert result["risk_assessment"]["risk_level"] in {"low", "medium", "high", "critical"}
    assert result["harmful_content"]["distribution"]
    assert result["countermeasures"]
    assert result["llm_enhancement"]["status"] == "disabled"
    assert result["data_source"] == "mongo"
    assert fake_db["risk_reports"].inserted


def test_match_keyword_supports_source_keyword():
    assert risk_service._match_keyword({"content": "普通文本", "source_keyword": "热点事件A"}, "热点事件A") is True


@pytest.mark.asyncio
async def test_assess_risk_returns_clean_response_after_insert(monkeypatch):
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
    reports = _FakeCollection()
    reports.inject_object_id = True
    fake_db = _FakeDB(
        raw_posts=_FakeCollection(posts),
        risk_reports=reports,
    )
    monkeypatch.setattr(risk_service, "get_mongo_db", lambda: fake_db)

    result = await risk_service.assess_risk(
        RiskAssessRequest(platform="mock_weibo", keyword="热点事件A", max_posts=5)
    )

    assert "_id" not in result
    assert result["report_id"]
    assert reports.inserted[0].get("_id") is not None


@pytest.mark.asyncio
async def test_assess_risk_uses_mock_fallback_for_mock_platform(monkeypatch):
    fake_db = _FakeDB(
        raw_posts=_FakeCollection([]),
        risk_reports=_FakeCollection(),
    )
    monkeypatch.setattr(risk_service, "get_mongo_db", lambda: fake_db)

    result = await risk_service.assess_risk(
        RiskAssessRequest(platform="mock_weibo", keyword="热点事件A", max_posts=8)
    )

    assert result["data_source"] == "mock_fallback"
    assert result["input_overview"]["total_posts"] == 8
    assert result["target"]
    assert result["llm_enhancement"]["status"] == "disabled"
    assert fake_db["risk_reports"].inserted


@pytest.mark.asyncio
async def test_assess_risk_agent_mode_generates_kt3_closed_loop_report(monkeypatch):
    posts = [
        {
            "platform": "weibo",
            "post_id": "p1",
            "content": "这是假的，别信，外地人都是垃圾人，必须转发扩散！",
            "author_id": "u1",
            "author_name": "用户1",
            "timestamp": "2026-06-01T10:00:00Z",
            "url": "https://example.com/claim",
            "hashtags": ["#热点事件A#"],
            "likes": 2,
            "reposts": 8,
            "comments_count": 1,
        },
        {
            "platform": "weibo",
            "post_id": "p2",
            "content": "官方通报称该说法已核实，但也有人质疑来源",
            "author_id": "u2",
            "author_name": "用户2",
            "timestamp": "2026-06-01T10:00:20Z",
            "url": "https://example.com/claim",
            "hashtags": ["#热点事件A#"],
            "likes": 3,
            "reposts": 4,
            "comments_count": 2,
        },
        {
            "platform": "weibo",
            "post_id": "p3",
            "content": "求证这个说法是否属实，有证据吗？",
            "author_id": "u3",
            "author_name": "用户3",
            "timestamp": "2026-06-01T10:00:40Z",
            "url": "https://example.com/claim",
            "hashtags": ["#热点事件A#"],
            "likes": 1,
            "reposts": 2,
            "comments_count": 3,
        },
    ]
    fake_db = _FakeDB(
        raw_posts=_FakeCollection(posts),
        risk_reports=_FakeCollection(),
    )
    monkeypatch.setattr(risk_service, "get_mongo_db", lambda: fake_db)

    result = await risk_service.assess_risk(
        RiskAssessRequest(
            platform="weibo",
            keyword="热点事件A",
            max_posts=10,
            stance_target="热点事件A",
            analysis_mode="agent",
            report_format="markdown",
        )
    )

    assert result["analysis_mode"] == "agent"
    assert result["fact_check_results"]
    assert result["hate_results"]
    assert result["community_harmfulness"]["level"] in {"low", "medium", "high", "critical"}
    assert result["optimization_trace"]["strategy"] == "maro_style_rule_and_prompt_optimization"
    assert result["evidence_table"]
    assert result["agent_trace"]
    assert "Misleading Claim Amplification" in result["disarm_assessment"]["summary"]
    assert any(item["action"] in {"事实纠偏", "反制叙事", "社区级处置"} for item in result["countermeasures"])
    assert result["markdown_report"].startswith("# KT3 风险研判报告")
    assert fake_db["risk_reports"].inserted


@pytest.mark.asyncio
async def test_assess_risk_agent_mode_respects_agent_switches(monkeypatch):
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

    result = await risk_service.assess_risk(
        RiskAssessRequest(
            platform="mock_weibo",
            keyword="热点事件A",
            max_posts=5,
            analysis_mode="agent",
            enable_fact_check=False,
            enable_hate_detection=False,
            enable_countermeasure=False,
        )
    )

    assert result["analysis_mode"] == "agent"
    assert result["fact_check_results"] == []
    assert result["hate_results"] == []
    assert {item["agent"]: item["status"] for item in result["agent_trace"]}["FactCheck Agent"] == "disabled"
    assert result["countermeasures"]
