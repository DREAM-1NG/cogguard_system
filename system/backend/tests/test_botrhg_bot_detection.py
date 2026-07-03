import asyncio

from httpx import ASGITransport, AsyncClient

from app.api.v1 import accounts as accounts_api
from app.core.bot_detection import run_botrhg_detection
from app.main import app
from app.services import bot_detection_service


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


def test_botrhg_service_filters_posts_by_event_and_platform(monkeypatch):
    posts = [_post("u1", "2026-05-21T00:00:00+00:00", "hello")]
    raw_posts = FakeCollection(posts)
    fake_db = FakeMongoDB(raw_posts=raw_posts)
    monkeypatch.setattr(bot_detection_service, "get_mongo_db", lambda: fake_db)

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


def test_botrhg_api_allows_preview_token_and_passes_parameters(monkeypatch):
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
            client.headers["Authorization"] = "Bearer cogguard-preview-token"
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
