import asyncio
import copy
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

import pytest
from httpx import ASGITransport, AsyncClient

from app.api.v1 import accounts as accounts_api
from app.config import settings
from app.core.security import get_current_user
from app.core.bot_detection import run_botrhg_detection
from app.main import app
from app.services import account_service
from app.services import bot_detection_service


@pytest.fixture
def authenticated_user_override():
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=1, role="analyst", is_active=True)
    yield
    app.dependency_overrides.pop(get_current_user, None)


class FakeCursor:
    def __init__(self, rows):
        self.rows = rows

    async def to_list(self, length):
        return self.rows[:length]


class FakeCollection:
    def __init__(self, rows):
        self.rows = rows
        self.calls = []

    def find(self, query, projection=None):
        self.calls.append({"query": query, "projection": projection})
        return FakeCursor(self.rows)


class FakeMongoDB(dict):
    pass


class FakeRedis:
    def __init__(self):
        self.values = {}
        self.set_calls = []

    async def get(self, key):
        return self.values.get(key)

    async def setex(self, key, ttl, value):
        self.set_calls.append((key, ttl, value))
        self.values[key] = value


class EmptyRedis:
    async def get(self, key):
        return None

    async def setex(self, key, ttl, value):
        return None


def _post(account_id, timestamp, content, *, author_name=None, profile=None, likes=0, reposts=0):
    return {
        "event_id": "event-1",
        "platform": "weibo",
        "post_id": f"{account_id}-{timestamp}",
        "author_id": account_id,
        "author_name": author_name or account_id,
        "timestamp": timestamp,
        "content": content,
        "author_profile": profile or {},
        "likes": likes,
        "reposts": reposts,
        "comments_count": 0,
        "hashtags": ["topic"],
        "url": "https://example.com/shared",
    }


def test_botrhg_detection_routes_low_reliability_accounts_and_preserves_others():
    posts = [
        _post("bot-a", "2026-05-21T00:00:00+00:00", "buy now HTTPURL #topic", profile={"followers_count": 2, "friends_count": 800}),
        _post("bot-a", "2026-05-21T00:00:12+00:00", "buy now HTTPURL #topic", profile={"followers_count": 2, "friends_count": 800}),
        _post("bot-a", "2026-05-21T00:00:24+00:00", "buy now HTTPURL #topic", profile={"followers_count": 2, "friends_count": 800}),
        _post("human-a", "2026-05-21T00:00:00+00:00", "现场信息和长文本观察", profile={"followers_count": 800, "friends_count": 180}, likes=5),
        _post("human-a", "2026-05-21T03:10:00+00:00", "补充观点与来源", profile={"followers_count": 800, "friends_count": 180}, likes=6),
        _post("ambiguous-a", "2026-05-21T00:01:00+00:00", "buy now HTTPURL #topic", profile={"followers_count": 30, "friends_count": 300}),
        _post("ambiguous-a", "2026-05-21T00:01:35+00:00", "普通评论但带链接 HTTPURL", profile={"followers_count": 30, "friends_count": 300}),
    ]

    result = run_botrhg_detection(posts, routing_budget=0.5, support_k=2)

    assert result["method"] == "BotRHG"
    assert result["summary"]["account_count"] == 3
    assert result["summary"]["routed_count"] == 1
    assert result["summary"]["routing_budget"] == 0.5

    account_map = {row["account_id"]: row for row in result["accounts"]}
    assert account_map["ambiguous-a"]["routed"] is True
    assert account_map["ambiguous-a"]["local_reliability"] < account_map["human-a"]["local_reliability"]
    assert account_map["ambiguous-a"]["hyperedge"]["center"] == "ambiguous-a"
    assert len(account_map["ambiguous-a"]["hyperedge"]["support_nodes"]) == 2
    assert account_map["ambiguous-a"]["hyperedge"]["support_k"] == 2
    assert account_map["ambiguous-a"]["final_bot_probability"] != account_map["ambiguous-a"]["base_bot_probability"]
    assert account_map["human-a"]["routed"] is False
    assert account_map["human-a"]["final_prediction"] == account_map["human-a"]["base_prediction"]
    assert result["model_card"]["feature_encoder"] == "profile_description_tweets_plus_properties"
    assert result["model_card"]["selective_rule"] == "preserve_base_unless_routed"

    for support_row in account_map["ambiguous-a"]["support_evidence"]:
        support_account = account_map[support_row["account_id"]]
        assert support_row["final_prediction"] == support_account["final_prediction"]
        assert support_row["final_bot_probability"] == support_account["final_bot_probability"]
        assert support_row["routed"] == support_account["routed"]


def test_botrhg_detection_normalizes_mixed_timezone_timestamps():
    posts = [
        _post("u1", datetime(2026, 5, 21, 8, 0, 0), "first"),
        _post("u1", "2026-05-21T08:00:20+00:00", "second"),
    ]

    result = run_botrhg_detection(posts)

    assert result["summary"]["account_count"] == 1
    assert result["accounts"][0]["signals"]["burst"] > 0


def test_accounts_page_exposes_botrhg_probability_not_legacy_automation_score():
    source_path = Path(__file__).parents[2] / "frontend" / "src" / "views" / "accounts" / "index.vue"
    source = source_path.read_text(encoding="utf-8")

    assert "自动化评分" not in source
    assert "scoreLabel(" not in source
    assert "scoreColor(" not in source
    assert "BotRHG 最终概率" in source
    assert "final_bot_probability" in source
    assert "base_bot_probability" in source


def test_botrhg_service_filters_posts_by_event_and_platform(monkeypatch):
    posts = [_post("u1", "2026-05-21T00:00:00+00:00", "hello")]
    raw_posts = FakeCollection(posts)
    fake_db = FakeMongoDB(raw_posts=raw_posts)
    fake_redis = FakeRedis()
    monkeypatch.setattr(bot_detection_service, "get_mongo_db", lambda: fake_db)
    monkeypatch.setattr(bot_detection_service, "get_redis", lambda: fake_redis, raising=False)
    bot_detection_service.clear_detection_cache()

    result = asyncio.run(
        bot_detection_service.detect_social_bots(
            event_id="event-1",
            platform="weibo",
            routing_budget=0.3,
            support_k=1,
        )
    )

    assert raw_posts.calls[0]["query"] == {"event_id": "event-1", "platform": "weibo"}
    assert result["summary"]["event_id"] == "event-1"
    assert result["summary"]["platform"] == "weibo"
    assert result["summary"]["account_count"] == 1


def test_botrhg_api_requires_authenticated_user_and_passes_parameters(monkeypatch, authenticated_user_override):
    calls = {}

    async def fake_detect_social_bots(**kwargs):
        calls.update(kwargs)
        return {
            "method": "BotRHG",
            "accounts": [],
            "summary": {"account_count": 0},
            "model_card": {},
        }

    monkeypatch.setattr(accounts_api.bot_detection_service, "detect_social_bots", fake_detect_social_bots)

    async def _request():
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.post(
                "/api/v1/accounts/bot-detection?event_id=event-1&platform=weibo&routing_budget=0.25&support_k=3"
            )

    response = asyncio.run(_request())

    assert response.status_code == 200
    assert response.json()["code"] == 0
    assert response.json()["data"]["method"] == "BotRHG"
    assert calls == {
        "event_id": "event-1",
        "platform": "weibo",
        "routing_budget": 0.25,
        "support_k": 3,
    }


def test_account_profiles_accepts_authenticated_user(monkeypatch, authenticated_user_override):
    calls = {}

    async def fake_get_account_profiles(**kwargs):
        calls.update(kwargs)
        return [{"account_id": "u1"}]

    monkeypatch.setattr(accounts_api.account_service, "get_account_profiles", fake_get_account_profiles)

    async def _request():
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.get("/api/v1/accounts/profiles?event_id=event-1&platform=weibo")

    response = asyncio.run(_request())

    assert response.status_code == 200
    assert response.json()["data"] == [{"account_id": "u1"}]
    assert calls == {"platform": "weibo", "event_id": "event-1"}
def test_account_detail_includes_detection_result_and_recent_posts(monkeypatch, authenticated_user_override):
    posts = [
        _post("u1", "2026-05-21T00:00:00+00:00", "hello"),
        _post("u1", "2026-05-21T00:10:00+00:00", "reply"),
    ]
    raw_posts = FakeCollection(posts)
    fake_db = FakeMongoDB(raw_posts=raw_posts)
    monkeypatch.setattr(account_service, "get_mongo_db", lambda: fake_db)

    async def _request():
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.get("/api/v1/accounts/detail/u1?event_id=event-1&platform=weibo")

    response = asyncio.run(_request())
    payload = response.json()["data"]

    assert response.status_code == 200
    assert payload["account_id"] == "u1"
    assert payload["detection_result"]["method"] == "BotRHG"
    assert payload["detection_result"]["similar_users"] == payload["similar_users"]
    assert len(payload["recent_posts"]) == 2


def test_botrhg_detection_reuses_cached_result_for_same_scope(monkeypatch):
    posts = [_post("u1", "2026-05-21T00:00:00+00:00", "hello")]
    raw_posts = FakeCollection(posts)
    fake_db = FakeMongoDB(raw_posts=raw_posts)
    monkeypatch.setattr(bot_detection_service, "get_mongo_db", lambda: fake_db)
    bot_detection_service.clear_detection_cache()

    first = asyncio.run(bot_detection_service.detect_social_bots(event_id="event-1", platform="weibo"))
    second = asyncio.run(bot_detection_service.detect_social_bots(event_id="event-1", platform="weibo"))

    assert second == first
    assert len(raw_posts.calls) == 1


def test_botrhg_detection_recovers_from_redis_cache_after_memory_reset(monkeypatch):
    posts = [_post("u1", "2026-05-21T00:00:00+00:00", "hello")]
    raw_posts = FakeCollection(posts)
    fake_db = FakeMongoDB(raw_posts=raw_posts)
    fake_redis = FakeRedis()
    fake_result = {
        "method": "BotRHG",
        "accounts": [
            {
                "account_id": "u1",
                "final_prediction": "human",
                "base_bot_probability": 0.1,
                "final_bot_probability": 0.1,
            }
        ],
        "summary": {"account_count": 1, "bot_count": 0, "routed_count": 0},
        "model_card": {"method": "BotRHG"},
    }
    monkeypatch.setattr(bot_detection_service, "get_mongo_db", lambda: fake_db)
    monkeypatch.setattr(bot_detection_service, "get_redis", lambda: fake_redis, raising=False)
    monkeypatch.setattr(bot_detection_service, "run_trained_botrhg_detection", lambda posts: None)
    monkeypatch.setattr(bot_detection_service, "run_botrhg_detection", lambda posts, routing_budget=0.2, support_k=8: copy.deepcopy(fake_result))
    bot_detection_service.clear_detection_cache()

    first = asyncio.run(bot_detection_service.detect_social_bots(event_id="event-1", platform="weibo"))
    bot_detection_service.clear_detection_cache()

    cached = asyncio.run(bot_detection_service.get_cached_detection("event-1", "weibo"))

    assert fake_redis.set_calls
    assert len(raw_posts.calls) == 1
    assert cached == first


def test_latest_botrhg_detection_returns_cached_result(monkeypatch, authenticated_user_override):
    result = {"method": "BotRHG", "accounts": [], "summary": {"account_count": 0}}
    asyncio.run(bot_detection_service.set_detection_cache("event-1", "weibo", result))

    async def _request():
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            client.headers["Authorization"] = f"Bearer {authenticated_user_override}"
            return await client.get("/api/v1/accounts/bot-detection/latest?event_id=event-1&platform=weibo")

    response = asyncio.run(_request())
    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["method"] == result["method"]
    assert payload["accounts"] == []
    assert payload["summary"] == result["summary"]
    assert payload["response_compacted"] is True
    bot_detection_service.clear_detection_cache()


def test_latest_botrhg_detection_computes_when_cache_is_empty(monkeypatch, authenticated_user_override):
    posts = [_post("u1", "2026-05-21T00:00:00+00:00", "hello")]
    raw_posts = FakeCollection(posts)
    fake_db = FakeMongoDB(raw_posts=raw_posts)
    fake_result = {
        "method": "BotRHG",
        "accounts": [
            {
                "account_id": "u1",
                "final_prediction": "human",
                "base_bot_probability": 0.1,
                "final_bot_probability": 0.1,
            }
        ],
        "summary": {"account_count": 1, "bot_count": 0, "routed_count": 0},
        "model_card": {"method": "BotRHG"},
    }
    monkeypatch.setattr(bot_detection_service, "get_mongo_db", lambda: fake_db)
    monkeypatch.setattr(bot_detection_service, "get_redis", lambda: FakeRedis(), raising=False)
    monkeypatch.setattr(bot_detection_service, "run_trained_botrhg_detection", lambda posts: None)
    monkeypatch.setattr(
        bot_detection_service,
        "run_botrhg_detection",
        lambda posts, routing_budget=0.2, support_k=8: copy.deepcopy(fake_result),
    )
    bot_detection_service.clear_detection_cache()

    async def _request():
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            client.headers["Authorization"] = f"Bearer {authenticated_user_override}"
            return await client.get("/api/v1/accounts/bot-detection/latest?event_id=event-1&platform=weibo")

    response = asyncio.run(_request())

    assert response.status_code == 200
    assert response.json()["data"]["accounts"][0]["final_bot_probability"] == 0.1
    assert len(raw_posts.calls) == 1
    bot_detection_service.clear_detection_cache()


def test_latest_botrhg_detection_returns_compact_account_payload(monkeypatch, authenticated_user_override):
    result = {
        "method": "BotRHG",
        "accounts": [
            {
                "account_id": "u1",
                "final_prediction": "human",
                "base_prediction": "human",
                "base_bot_probability": 0.1,
                "final_bot_probability": 0.2,
                "local_reliability": 0.9,
                "routed": True,
                "support_evidence": [{"account_id": "neighbor", "similarity": 0.99}],
                "signals": {"burst": 0.1},
                "hyperedge": {"center": "u1", "support_nodes": ["neighbor"]},
            }
        ],
        "summary": {"account_count": 1, "bot_count": 0, "routed_count": 1},
        "method_card": {"method": "BotRHG"},
    }
    asyncio.run(bot_detection_service.set_detection_cache("event-1", "weibo", result))

    async def _request():
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            client.headers["Authorization"] = f"Bearer {authenticated_user_override}"
            return await client.get("/api/v1/accounts/bot-detection/latest?event_id=event-1&platform=weibo")

    response = asyncio.run(_request())
    account = response.json()["data"]["accounts"][0]

    assert response.status_code == 200
    assert account["final_bot_probability"] == 0.2
    assert account["base_bot_probability"] == 0.1
    assert account["local_reliability"] == 0.9
    assert account["routed"] is True
    assert "support_evidence" not in account
    assert "signals" not in account
    assert "hyperedge" not in account
    bot_detection_service.clear_detection_cache()


def test_botrhg_detection_cache_expires(monkeypatch):
    result = {"method": "BotRHG", "accounts": [], "summary": {"account_count": 0}}
    monkeypatch.setattr(settings, "BOTRHG_CACHE_TTL_SECONDS", 1)
    monkeypatch.setattr(bot_detection_service, "get_redis", lambda: EmptyRedis(), raising=False)
    asyncio.run(bot_detection_service.set_detection_cache("event-1", "weibo", result))
    monkeypatch.setattr(bot_detection_service.time, "monotonic", lambda: 2.0)
    monkeypatch.setattr(bot_detection_service, "_DETECTION_CACHE", {
        ("event-1", "weibo", 0.2, 8): (0.0, result),
    })

    assert asyncio.run(bot_detection_service.get_cached_detection("event-1", "weibo")) is None
    bot_detection_service.clear_detection_cache()
