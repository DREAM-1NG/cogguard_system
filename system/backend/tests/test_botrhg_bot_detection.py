import asyncio
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from httpx import ASGITransport, AsyncClient

from app.api.v1 import accounts as accounts_api
from app.config import settings
from app.core.analysis.query_result_cache import clear_local_query_result_cache
from app.core.account_labeling import account_scope_key
from app.core.security import get_current_user
from app.core.bot_detection import run_botrhg_detection
from app.main import app
from app.services import account_service
from app.services import bot_detection_service
from app.utils.exceptions import AppException


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


async def no_active_account_model():
    return None


async def missing_active_account_model_resolution():
    return SimpleNamespace(
        status="missing",
        model=None,
        model_version="",
        artifact_hash="",
        pointer_revision=0,
        reason="",
        detail="",
    )


def available_active_account_model_resolution(model):
    return SimpleNamespace(
        status="available",
        model=model,
        model_version=model.model_version,
        artifact_hash=model.artifact_hash,
        pointer_revision=model.pointer_revision,
        reason="",
        detail="",
    )


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

    async def active_model():
        model = SimpleNamespace(model_version="governed-model", artifact_hash="a" * 64, pointer_revision=1)
        return available_active_account_model_resolution(model)

    monkeypatch.setattr(bot_detection_service, "get_active_account_model_resolution", active_model)
    monkeypatch.setattr(
        bot_detection_service,
        "run_trained_botrhg_detection",
        lambda _posts, _model, *, allow_legacy_fallback: {
            "method": "BotRHG",
            "accounts": [{"account_id": "u1"}],
            "summary": {"account_count": 1, "bot_count": 0},
        },
    )

    class AuditSession:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

        async def commit(self):
            return None

    async def record_audits(*_args, **_kwargs):
        return 0

    monkeypatch.setattr(bot_detection_service, "async_session_factory", AuditSession)
    monkeypatch.setattr(bot_detection_service, "record_account_prediction_audits", record_audits)

    result = asyncio.run(
        bot_detection_service.detect_social_bots(
            event_id="event-1",
            platform="weibo",
        )
    )

    assert raw_posts.calls[0]["query"] == {"event_id": "event-1", "platform": "weibo"}
    assert result["summary"]["event_id"] == "event-1"
    assert result["summary"]["platform"] == "weibo"
    assert result["summary"]["account_count"] == 1


def test_botrhg_service_partitions_multi_platform_inference(monkeypatch):
    posts = [
        _post("same-id", "2026-05-21T00:00:00+00:00", "weibo text"),
        {
            **_post("same-id", "2026-05-21T00:05:00+00:00", "douyin text"),
            "platform": "douyin",
        },
    ]
    model = SimpleNamespace(model_version="governed-model", artifact_hash="a" * 64, pointer_revision=1)

    async def active_model():
        return available_active_account_model_resolution(model)

    def detect(scoped_posts, _model, *, allow_legacy_fallback):
        platform = scoped_posts[0]["platform"]
        assert {post["platform"] for post in scoped_posts} == {platform}
        return {
            "method": "BotRHG",
            "runtime_mode": "strict_trained_checkpoint",
            "accounts": [
                {
                    "account_id": "same-id",
                    "final_prediction": "bot" if platform == "weibo" else "human",
                    "routed": False,
                }
            ],
            "summary": {"routing_budget": 0.2},
        }

    class AuditSession:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

        async def commit(self):
            return None

    observed = {}

    async def record_audits(_session, **kwargs):
        observed.update(kwargs)
        return len(kwargs["result"]["accounts"])

    monkeypatch.setattr(bot_detection_service, "get_mongo_db", lambda: FakeMongoDB(raw_posts=FakeCollection(posts)))
    monkeypatch.setattr(bot_detection_service, "get_active_account_model_resolution", active_model)
    monkeypatch.setattr(bot_detection_service, "run_trained_botrhg_detection", detect)
    monkeypatch.setattr(bot_detection_service, "async_session_factory", AuditSession)
    monkeypatch.setattr(bot_detection_service, "record_account_prediction_audits", record_audits)

    result = asyncio.run(bot_detection_service.detect_social_bots())

    assert {(row["platform"], row["account_id"]) for row in result["accounts"]} == {
        ("weibo", "same-id"),
        ("douyin", "same-id"),
    }
    assert result["summary"]["account_count"] == 2
    assert result["summary"]["bot_count"] == 1
    assert result["summary"]["platform_count"] == 2
    assert observed["result"] is result


def test_botrhg_service_does_not_fall_back_to_rule_detection(monkeypatch):
    posts = [_post("u1", "2026-05-21T00:00:00+00:00", "hello")]
    raw_posts = FakeCollection(posts)
    fake_db = FakeMongoDB(raw_posts=raw_posts)
    monkeypatch.setattr(bot_detection_service, "get_mongo_db", lambda: fake_db)
    monkeypatch.setattr(
        bot_detection_service,
        "get_active_account_model_resolution",
        missing_active_account_model_resolution,
    )
    monkeypatch.setattr(bot_detection_service, "run_trained_botrhg_detection", lambda _posts: None)

    result = asyncio.run(
        bot_detection_service.detect_social_bots(event_id="event-1", platform="weibo")
    )

    assert result["accounts"] == []
    assert result["summary"]["account_count"] == 0
    assert result["summary"]["post_count"] == 1


def test_botrhg_service_returns_unavailable_without_a_governed_pointer(monkeypatch):
    posts = [_post("u1", "2026-05-21T00:00:00+00:00", "hello")]
    raw_posts = FakeCollection(posts)
    monkeypatch.setattr(bot_detection_service, "get_mongo_db", lambda: FakeMongoDB(raw_posts=raw_posts))
    monkeypatch.setattr(
        bot_detection_service,
        "get_active_account_model_resolution",
        missing_active_account_model_resolution,
    )
    monkeypatch.setattr(
        bot_detection_service,
        "run_trained_botrhg_detection",
        lambda *_args, **_kwargs: pytest.fail("legacy inference must not run without an active pointer"),
    )

    result = asyncio.run(bot_detection_service.detect_social_bots(event_id="event-1", platform="weibo"))

    assert result["accounts"] == []
    assert result["audit_status"] == "unavailable_without_active_pointer"
    assert result["summary"]["account_count"] == 0


def test_botrhg_service_records_runtime_failure_as_a_hard_error(monkeypatch):
    posts = [_post("u1", "2026-05-21T00:00:00+00:00", "hello")]
    model = SimpleNamespace(
        model_version="governed-model",
        artifact_hash="a" * 64,
        pointer_revision=2,
    )

    async def active_model():
        return available_active_account_model_resolution(model)

    class AuditSession:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

        async def commit(self):
            return None

    observed = {}

    async def record_error(_session, **kwargs):
        observed.update(kwargs)
        return 1

    monkeypatch.setattr(bot_detection_service, "get_mongo_db", lambda: FakeMongoDB(raw_posts=FakeCollection(posts)))
    monkeypatch.setattr(bot_detection_service, "get_active_account_model_resolution", active_model)
    monkeypatch.setattr(bot_detection_service, "run_trained_botrhg_detection", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(bot_detection_service, "async_session_factory", AuditSession)
    monkeypatch.setattr(bot_detection_service, "record_account_runtime_error", record_error, raising=False)
    monkeypatch.setattr(
        bot_detection_service,
        "record_account_prediction_audits",
        lambda *_args, **_kwargs: pytest.fail("runtime failures are not successful prediction audits"),
    )

    result = asyncio.run(bot_detection_service.detect_social_bots(event_id="event-1", platform="weibo"))

    assert result["status"] == "unavailable"
    assert result["reason"] == "account_model_runtime_unavailable"
    assert result["audit_status"] == "runtime_hard_error"
    assert result["audit_persisted_count"] == 1
    assert observed["model"] is model
    assert observed["reason"] == "account_model_runtime_load_failure"


def test_botrhg_service_audits_an_invalid_active_pointer(monkeypatch):
    posts = [_post("u1", "2026-05-21T00:00:00+00:00", "hello")]
    resolution = SimpleNamespace(
        status="invalid",
        model=None,
        model_version="model-invalid",
        artifact_hash="b" * 64,
        pointer_revision=5,
        reason="active_model_bundle_invalid",
        detail="bundle manifest SHA-256 mismatch",
    )

    async def invalid_resolution():
        return resolution

    class AuditSession:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

        async def commit(self):
            return None

    observed = {}

    async def record_error(_session, **kwargs):
        observed.update(kwargs)
        return 1

    monkeypatch.setattr(bot_detection_service, "get_mongo_db", lambda: FakeMongoDB(raw_posts=FakeCollection(posts)))
    monkeypatch.setattr(
        bot_detection_service,
        "get_active_account_model_resolution",
        invalid_resolution,
        raising=False,
    )
    monkeypatch.setattr(
        bot_detection_service,
        "run_trained_botrhg_detection",
        lambda *_args, **_kwargs: pytest.fail("invalid pointers must not reach inference"),
    )
    monkeypatch.setattr(bot_detection_service, "async_session_factory", AuditSession)
    monkeypatch.setattr(bot_detection_service, "record_account_runtime_error", record_error)

    result = asyncio.run(bot_detection_service.detect_social_bots(event_id="event-1", platform="weibo"))

    assert result["status"] == "unavailable"
    assert result["reason"] == "account_model_pointer_invalid"
    assert result["pointer_failure_reason"] == "active_model_bundle_invalid"
    assert result["audit_status"] == "runtime_hard_error"
    assert result["audit_persisted_count"] == 1
    assert observed["model"] is resolution
    assert observed["reason"] == "active_model_bundle_invalid"


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
                "/api/v1/accounts/bot-detection?event_id=event-1&platform=weibo"
            )

    response = asyncio.run(_request())

    assert response.status_code == 200
    assert response.json()["code"] == 0
    assert response.json()["data"]["method"] == "BotRHG"
    assert calls == {
        "event_id": "event-1",
        "platform": "weibo",
    }


def test_account_detail_includes_detection_result_and_recent_posts(monkeypatch, authenticated_user_override):
    posts = [
        _post("u1", "2026-05-21T00:00:00+00:00", "hello"),
        _post("u1", "2026-05-21T00:10:00+00:00", "reply"),
    ]
    raw_posts = FakeCollection(posts)
    fake_db = FakeMongoDB(raw_posts=raw_posts)
    monkeypatch.setattr(account_service, "get_mongo_db", lambda: fake_db)
    monkeypatch.setattr(account_service, "get_active_account_model", no_active_account_model)
    monkeypatch.setattr(settings, "ACCOUNT_MODEL_BOOTSTRAP_MODE", "local_legacy", raising=False)
    monkeypatch.setattr(settings, "ANALYSIS_RESULT_CACHE_REDIS_ENABLED", False)
    clear_local_query_result_cache()
    monkeypatch.setattr(
        account_service,
        "run_trained_botrhg_detection",
        lambda _posts: {
            "accounts": [
                {
                    "account_id": "u1",
                    "final_prediction": "bot",
                    "final_bot_probability": 0.84,
                    "calibrated_bot_probability": 0.81,
                    "calibrated": True,
                    "routed": True,
                    "support_evidence": [
                        {
                            "account_id": "u2",
                            "similarity": 0.92,
                            "final_bot_probability": 0.27,
                            "routed": False,
                        }
                    ],
                },
            ]
        },
    )

    async def _request():
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.get("/api/v1/accounts/detail/u1?event_id=event-1&platform=weibo")

    response = asyncio.run(_request())
    payload = response.json()["data"]

    assert response.status_code == 200
    assert payload["account_id"] == "u1"
    assert payload["assessment"] == {
        "level": "attention",
        "label": "需关注",
        "prediction": "bot",
        "bot_probability": 0.81,
        "calibrated": True,
        "routed": True,
        "model_version": "",
        "pointer_revision": 0,
        "similar_accounts": [
            {
                "account_id": "u2",
                "similarity": 0.92,
                "bot_probability": 0.27,
                "routed": False,
            }
        ],
    }
    assert "automation_score" not in payload
    assert "detection_result" not in payload
    assert len(payload["recent_posts"]) == 2


def test_account_detail_sorts_mixed_mongo_timestamp_types(monkeypatch):
    posts = [
        _post("u1", "2026-05-21T00:00:00+00:00", "older"),
        {
            **_post("u1", "2026-05-21T00:00:00+00:00", "newer"),
            "timestamp": datetime(2026, 5, 22, tzinfo=timezone.utc),
        },
    ]
    monkeypatch.setattr(account_service, "get_mongo_db", lambda: FakeMongoDB(raw_posts=FakeCollection(posts)))
    monkeypatch.setattr(account_service, "_model_assessments", lambda _posts: _async_value({}))

    detail = asyncio.run(account_service.get_account_detail("u1", platform="weibo"))

    assert [row["content"] for row in detail["recent_posts"]] == ["newer", "older"]


def test_account_detail_rejects_ambiguous_cross_platform_account_id(monkeypatch):
    posts = [
        _post("same-id", "2026-05-21T00:00:00+00:00", "weibo text"),
        {
            **_post("same-id", "2026-05-21T00:05:00+00:00", "douyin text"),
            "platform": "douyin",
        },
    ]
    monkeypatch.setattr(account_service, "get_mongo_db", lambda: FakeMongoDB(raw_posts=FakeCollection(posts)))

    with pytest.raises(AppException, match="platform is required"):
        asyncio.run(account_service.get_account_detail("same-id"))


def test_account_assessment_fingerprint_changes_when_model_input_changes():
    post = _post("u1", "2026-05-21T00:00:00+00:00", "same text", profile={"followers_count": 10})
    changed_profile = {
        **post,
        "author_profile": {"followers_count": 1000},
    }
    second_post = _post("u1", "2026-05-21T00:01:00+00:00", "second text")

    assert account_service._assessment_fingerprint([post]) != account_service._assessment_fingerprint(
        [changed_profile]
    )
    assert account_service._assessment_fingerprint([post, second_post]) != account_service._assessment_fingerprint(
        [second_post, post]
    )


async def _async_value(value):
    return value


def test_account_profiles_project_trained_detector_conclusions_without_rule_scores(
    monkeypatch,
    authenticated_user_override,
):
    posts = [
        _post("u1", "2026-05-21T00:00:00+00:00", "hello", author_name="甲"),
        _post("u2", "2026-05-21T00:05:00+00:00", "world", author_name="乙"),
    ]
    raw_posts = FakeCollection(posts)
    fake_db = FakeMongoDB(raw_posts=raw_posts)
    monkeypatch.setattr(account_service, "get_mongo_db", lambda: fake_db)
    monkeypatch.setattr(account_service, "get_active_account_model", no_active_account_model)
    monkeypatch.setattr(settings, "ACCOUNT_MODEL_BOOTSTRAP_MODE", "local_legacy", raising=False)
    monkeypatch.setattr(settings, "ANALYSIS_RESULT_CACHE_REDIS_ENABLED", False)
    clear_local_query_result_cache()
    monkeypatch.setattr(
        account_service,
        "run_trained_botrhg_detection",
        lambda _posts: {
            "accounts": [
                {"account_id": "u1", "final_prediction": "human", "final_bot_probability": 0.12},
                {"account_id": "u2", "final_prediction": "bot", "final_bot_probability": 0.87},
            ]
        },
    )

    async def _request():
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.get("/api/v1/accounts/profiles?event_id=event-1&platform=weibo")

    response = asyncio.run(_request())
    rows = response.json()["data"]

    assert response.status_code == 200
    assert [row["author_name"] for row in rows] == ["乙", "甲"]
    assert rows[0]["assessment"]["level"] == "attention"
    assert rows[0]["assessment"]["prediction"] == "bot"
    assert rows[0]["assessment"]["bot_probability"] == 0.87
    assert rows[1]["assessment"]["level"] == "normal"
    assert rows[1]["assessment"]["prediction"] == "human"
    assert rows[1]["assessment"]["bot_probability"] == 0.12
    assert all("automation_score" not in row for row in rows)


def test_account_profiles_reuse_versioned_detector_projection(monkeypatch):
    posts = [_post("u1", "2026-05-21T00:00:00+00:00", "hello")]
    raw_posts = FakeCollection(posts)
    fake_db = FakeMongoDB(raw_posts=raw_posts)
    detector_calls = 0

    def detect_once(_posts):
        nonlocal detector_calls
        detector_calls += 1
        return {"accounts": [{"account_id": "u1", "final_prediction": "human"}]}

    monkeypatch.setattr(settings, "ANALYSIS_RESULT_CACHE_REDIS_ENABLED", False)
    monkeypatch.setattr(account_service, "get_mongo_db", lambda: fake_db)
    monkeypatch.setattr(account_service, "get_active_account_model", no_active_account_model)
    monkeypatch.setattr(settings, "ACCOUNT_MODEL_BOOTSTRAP_MODE", "local_legacy", raising=False)
    monkeypatch.setattr(account_service, "run_trained_botrhg_detection", detect_once)
    clear_local_query_result_cache()

    first = asyncio.run(account_service.get_account_profiles(event_id="event-1", platform="weibo"))
    second = asyncio.run(account_service.get_account_profiles(event_id="event-1", platform="weibo"))

    assert first == second
    assert detector_calls == 1


def test_account_profiles_prefer_persisted_prediction_audits_over_synchronous_inference(monkeypatch):
    posts = [
        _post("u1", "2026-05-21T00:00:00+00:00", "hello", author_name="甲"),
        _post("u2", "2026-05-21T00:05:00+00:00", "world", author_name="乙"),
    ]
    model = SimpleNamespace(model_version="governed-model", artifact_hash="a" * 64, pointer_revision=3)

    async def active_model():
        return model

    async def stored_assessments(_posts, _model):
        return {
            account_scope_key("weibo", "u1"): {
                "level": "normal",
                "label": "未见异常",
                "prediction": "human",
                "bot_probability": 0.11,
                "calibrated": False,
                "routed": False,
                "model_version": "governed-model",
                "pointer_revision": 3,
                "similar_accounts": [],
            },
            account_scope_key("weibo", "u2"): {
                "level": "attention",
                "label": "需关注",
                "prediction": "bot",
                "bot_probability": 0.91,
                "calibrated": False,
                "routed": False,
                "model_version": "governed-model",
                "pointer_revision": 3,
                "similar_accounts": [],
            },
        }

    monkeypatch.setattr(account_service, "get_mongo_db", lambda: FakeMongoDB(raw_posts=FakeCollection(posts)))
    monkeypatch.setattr(account_service, "get_active_account_model", active_model)
    monkeypatch.setattr(account_service, "_stored_model_assessments", stored_assessments)
    monkeypatch.setattr(
        account_service,
        "run_trained_botrhg_detection",
        lambda *_args, **_kwargs: pytest.fail("profile list must not run slow synchronous inference when audits exist"),
    )

    profiles = asyncio.run(account_service.get_account_profiles(event_id="event-1", platform="weibo"))

    assert [row["author_name"] for row in profiles] == ["乙", "甲"]
    assert profiles[0]["assessment"]["prediction"] == "bot"
    assert profiles[0]["assessment"]["bot_probability"] == 0.91
    assert profiles[1]["assessment"]["prediction"] == "human"


def test_account_profiles_keep_detection_results_platform_scoped(monkeypatch):
    posts = [
        _post("same-id", "2026-05-21T00:00:00+00:00", "weibo text"),
        {
            **_post("same-id", "2026-05-21T00:05:00+00:00", "douyin text"),
            "platform": "douyin",
        },
    ]
    model = SimpleNamespace(model_version="governed-model", artifact_hash="a" * 64, pointer_revision=3)
    observed_platforms = []

    async def active_model():
        return model

    def detect(scoped_posts, _model, *, allow_legacy_fallback):
        platform = scoped_posts[0]["platform"]
        observed_platforms.append(platform)
        assert {post["platform"] for post in scoped_posts} == {platform}
        return {
            "accounts": [
                {
                    "account_id": "same-id",
                    "final_prediction": "bot" if platform == "weibo" else "human",
                    "calibrated_bot_probability": 0.9 if platform == "weibo" else 0.1,
                }
            ]
        }

    monkeypatch.setattr(account_service, "get_mongo_db", lambda: FakeMongoDB(raw_posts=FakeCollection(posts)))
    monkeypatch.setattr(account_service, "get_active_account_model", active_model)
    monkeypatch.setattr(account_service, "run_trained_botrhg_detection", detect)
    monkeypatch.setattr(settings, "ANALYSIS_RESULT_CACHE_REDIS_ENABLED", False)
    clear_local_query_result_cache()

    profiles = asyncio.run(account_service.get_account_profiles())
    by_platform = {profile["platform"]: profile for profile in profiles}

    assert set(observed_platforms) == {"weibo", "douyin"}
    assert by_platform["weibo"]["assessment"]["prediction"] == "bot"
    assert by_platform["douyin"]["assessment"]["prediction"] == "human"


def test_account_profiles_do_not_use_legacy_checkpoint_when_bootstrap_is_disabled(monkeypatch):
    async def no_active_model():
        return None

    monkeypatch.setattr(account_service, "get_active_account_model", no_active_model)
    monkeypatch.setattr(settings, "ACCOUNT_MODEL_BOOTSTRAP_MODE", "disabled", raising=False)
    monkeypatch.setattr(
        account_service,
        "run_trained_botrhg_detection",
        lambda *_args, **_kwargs: pytest.fail("disabled bootstrap must not run legacy inference"),
    )

    assert asyncio.run(account_service._build_model_assessments([_post("u1", "2026", "text")], None)) == {}
