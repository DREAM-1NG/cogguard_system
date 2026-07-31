import asyncio

import pandas as pd
import pytest
from httpx import AsyncClient

from app.config import settings
from app.core.security import get_current_user_or_local_preview
from app.main import app
from app.services import (
    account_service,
    coordination_service,
    propagation_model_service,
    propagation_observation_service,
    propagation_prediction_service,
    propagation_service,
    risk_service,
)
from app.api.v1 import coordination as coordination_api
from app.api.v1 import propagation as propagation_api
from app.api.v1 import risk as risk_api


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


class FakeMotorStyleDB:
    def __init__(self, collections):
        self.collections = collections

    def __getitem__(self, name):
        return self.collections[name]

    def __getattr__(self, name):
        if name == "get":
            return self.collections.get(name)
        raise AttributeError(name)


def _post(event_id, platform, post_id, author_id, timestamp, *, hashtags=None, media_urls=None, author_name=None):
    return {
        "event_id": event_id,
        "platform": platform,
        "post_id": post_id,
        "author_id": author_id,
        "author_name": author_name or author_id,
        "timestamp": timestamp,
        "content": f"content {post_id}",
        "url": "https://example.com/shared",
        "hashtags": hashtags or [],
        "media_urls": media_urls or [],
        "likes": 1,
        "reposts": 0,
        "comments_count": 0,
    }


def _comment(
    event_id,
    platform,
    comment_id,
    post_id,
    author_id,
    timestamp,
    *,
    hashtags=None,
    media_urls=None,
    shared_urls=None,
    author_name=None,
):
    return {
        "event_id": event_id,
        "platform": platform,
        "comment_id": comment_id,
        "post_id": post_id,
        "author_id": author_id,
        "author_name": author_name or author_id,
        "timestamp": timestamp,
        "content": f"content {comment_id}",
        "hashtags": hashtags or [],
        "shared_urls": shared_urls or [],
        "media_urls": media_urls or [],
        "likes": 1,
        "sub_comment_count": 0,
    }


def _make_pair_result():
    return pd.DataFrame([
        {
            "object_id": "obj-1",
            "account_id": "u1",
            "account_id_y": "u2",
            "content_id": "p1",
            "content_id_y": "p2",
            "time_delta": 5,
        },
        {
            "object_id": "obj-1",
            "account_id": "u2",
            "account_id_y": "u3",
            "content_id": "p2",
            "content_id_y": "p3",
            "time_delta": 6,
        },
        {
            "object_id": "obj-2",
            "account_id": "u10",
            "account_id_y": "u10",
            "content_id": "p10",
            "content_id_y": "p11",
            "time_delta": 3,
        },
    ])


def test_build_event_filter_combines_event_id_and_platform():
    assert coordination_service.build_event_filter("event-1", "weibo") == {
        "event_id": "event-1",
        "platform": "weibo",
    }
    assert coordination_service.build_event_filter(None, "weibo") == {"platform": "weibo"}
    assert coordination_service.build_event_filter("event-1", None) == {"event_id": "event-1"}
    assert coordination_service.build_event_filter(None, None) == {}


def test_load_event_posts_uses_item_access_for_motor_style_db():
    rows = [{"post_id": "p1"}]
    fake_db = FakeMotorStyleDB({"raw_posts": FakeCollection(rows), "get": FakeCollection([])})

    result = asyncio.run(coordination_service.load_event_posts(fake_db))

    assert result == rows


def test_coordination_detection_filters_by_event_and_includes_metadata(monkeypatch):
    posts = [
        _post(
            "event-1",
            "weibo",
            "p1",
            "u1",
            "2026-05-21T00:00:00+00:00",
            media_urls=["https://img/a.jpg"],
            author_name="账号甲",
        ),
        _post(
            "event-1",
            "weibo",
            "p2",
            "u2",
            "2026-05-21T00:00:20+00:00",
            media_urls=["https://img/a.jpg"],
            author_name="账号乙",
        ),
    ]
    comments = [
        _comment(
            "event-1",
            "weibo",
            "c1",
            "p1",
            "u3",
            "2026-05-21T00:00:15+00:00",
            hashtags=["coord-tag"],
            shared_urls=["https://coord.example/shared"],
            author_name="评论账号丙",
        )
    ]
    raw_posts = FakeCollection(posts)
    raw_comments = FakeCollection(comments)
    fake_db = FakeMongoDB(raw_posts=raw_posts, raw_comments=raw_comments)
    monkeypatch.setattr(coordination_service, "get_mongo_db", lambda: fake_db)

    result = asyncio.run(
        coordination_service.run_coordination_detection(
            event_id="event-1",
            platform="weibo",
            time_window=60,
            min_participation=1,
        )
    )

    assert raw_posts.calls[0]["query"] == {"event_id": "event-1", "platform": "weibo"}
    assert raw_comments.calls[0]["query"] == {"event_id": "event-1", "platform": "weibo"}
    assert result["summary"]["event_id"] == "event-1"
    assert result["summary"]["platform"] == "weibo"
    assert result["summary"]["total_posts"] == 2
    assert result["summary"]["total_comments"] == 1
    assert result["summary"]["total_items"] == 3
    assert result["summary"]["total_pairs"] >= 1
    assert "cluster_count" in result["summary"]
    assert "cluster_stats" in result
    assert all("first_seen_at" in node for node in result["network"]["nodes"])
    assert all("coordinated_object_count" in node for node in result["network"]["nodes"])
    assert any(node.get("account_label") == "账号甲" for node in result["network"]["nodes"])
    assert all("shared_objects_preview" in node for node in result["network"]["nodes"])
    assert any(edge.get("shared_objects_preview") for edge in result["network"]["edges"])
    assert any(edge.get("shared_content_previews") for edge in result["network"]["edges"])
    assert result["account_stats"][0]["account_label"]
    assert "shared_objects_preview" in result["account_stats"][0]
    assert result["group_stats"][0]["object_type"] in {"话题", "链接", "图片"}
    assert "core_nodes" in result["cluster_stats"][0]
    assert "bridge_nodes" in result["cluster_stats"][0]
    assert "early_nodes" in result["cluster_stats"][0]
    assert "shared_objects_preview" in result["cluster_stats"][0]


def test_coordination_detection_supports_comment_only_shared_objects(monkeypatch):
    comments = [
        _comment(
            "event-1",
            "weibo",
            "c1",
            "p1",
            "u1",
            "2026-05-21T00:00:00+00:00",
            hashtags=["coord-tag"],
            shared_urls=["https://coord.example/shared"],
        ),
        _comment(
            "event-1",
            "weibo",
            "c2",
            "p1",
            "u2",
            "2026-05-21T00:00:20+00:00",
            hashtags=["coord-tag"],
            shared_urls=["https://coord.example/shared"],
        ),
    ]
    raw_posts = FakeCollection([])
    raw_comments = FakeCollection(comments)
    fake_db = FakeMongoDB(raw_posts=raw_posts, raw_comments=raw_comments)
    monkeypatch.setattr(coordination_service, "get_mongo_db", lambda: fake_db)

    result = asyncio.run(
        coordination_service.run_coordination_detection(
            event_id="event-1",
            platform="weibo",
            time_window=60,
            min_participation=1,
        )
    )

    assert raw_comments.calls[0]["query"] == {"event_id": "event-1", "platform": "weibo"}
    assert result["summary"]["total_posts"] == 0
    assert result["summary"]["total_comments"] == 2
    assert result["summary"]["total_items"] == 2
    assert result["summary"]["total_pairs"] >= 1
    assert {node["id"] for node in result["network"]["nodes"]} == {"u1", "u2"}
    assert {row["object_id"] for row in result["group_stats"]} == {
        "coord-tag",
        "https://coord.example/shared",
    }


def test_coordination_detection_extracts_account_labels_from_nested_profile_fields(monkeypatch):
    first = _post(
        "event-1",
        "weibo",
        "p1",
        "u1",
        "2026-05-21T00:00:00+00:00",
        media_urls=["https://img/a.jpg"],
        author_name="",
    )
    first["author_profile"] = {"screen_name": "账号甲"}

    second = _post(
        "event-1",
        "weibo",
        "p2",
        "u2",
        "2026-05-21T00:00:18+00:00",
        media_urls=["https://img/a.jpg"],
        author_name="",
    )
    second["raw_data"] = {
        "mblog": {
            "user": {
                "screen_name": "账号乙",
            }
        }
    }

    raw_posts = FakeCollection([first, second])
    raw_comments = FakeCollection([])
    fake_db = FakeMongoDB(raw_posts=raw_posts, raw_comments=raw_comments)
    monkeypatch.setattr(coordination_service, "get_mongo_db", lambda: fake_db)

    result = asyncio.run(
        coordination_service.run_coordination_detection(
            event_id="event-1",
            platform="weibo",
            time_window=60,
            min_participation=1,
        )
    )

    node_map = {node["id"]: node for node in result["network"]["nodes"]}
    assert node_map["u1"]["account_label"] == "账号甲"
    assert node_map["u2"]["account_label"] == "账号乙"
    assert {row["account_label"] for row in result["account_stats"]} == {"账号甲", "账号乙"}


def test_coordination_detection_tolerates_missing_comment_collection(monkeypatch):
    posts = [
        _post("event-1", "weibo", "p1", "u1", "2026-05-21T00:00:00+00:00", media_urls=["https://img/a.jpg"]),
        _post("event-1", "weibo", "p2", "u2", "2026-05-21T00:00:20+00:00", media_urls=["https://img/a.jpg"]),
    ]
    raw_posts = FakeCollection(posts)
    fake_db = FakeMongoDB(raw_posts=raw_posts)
    monkeypatch.setattr(coordination_service, "get_mongo_db", lambda: fake_db)

    result = asyncio.run(
        coordination_service.run_coordination_detection(
            event_id="event-1",
            platform="weibo",
            time_window=60,
            min_participation=1,
        )
    )

    assert result["summary"]["total_comments"] == 0
    assert result["summary"]["total_pairs"] >= 1


def test_generate_network_adds_cluster_annotations():
    graph = coordination_service.generate_coordinated_network(_make_pair_result(), edge_weight=0.5)
    network = coordination_service.graph_to_dict(graph)

    assert network["cluster_count"] >= 1
    assert len(network["clusters"]) == network["cluster_count"]
    assert all("cluster_id" in node for node in network["nodes"])
    assert all("cluster_size" in node for node in network["nodes"])
    assert all("cluster_degree" in node for node in network["nodes"])
    assert all("cross_cluster_edge_count" in node for node in network["nodes"])
    assert all("bridge_score" in node for node in network["nodes"])
    assert any(cluster["members"] for cluster in network["clusters"])
    assert all("core_nodes" in cluster for cluster in network["clusters"])
    assert all("bridge_nodes" in cluster for cluster in network["clusters"])
    assert all("early_nodes" in cluster for cluster in network["clusters"])


def test_generate_network_handles_isolates_and_single_edges():
    result = pd.DataFrame([
        {
            "object_id": "obj-a",
            "account_id": "u1",
            "account_id_y": "u2",
            "content_id": "p1",
            "content_id_y": "p2",
            "time_delta": 3,
        },
        {
            "object_id": "obj-b",
            "account_id": "u9",
            "account_id_y": "u9",
            "content_id": "p9",
            "content_id_y": "p10",
            "time_delta": 1,
        },
    ])
    graph = coordination_service.generate_coordinated_network(result, edge_weight=0.5)
    network = coordination_service.graph_to_dict(graph)

    assert "u9" not in {node["id"] for node in network["nodes"]}
    assert network["component_count"] == 1
    assert network["cluster_count"] == 1


@pytest.mark.asyncio
async def test_coordination_api_allows_preview_token_without_db_user(client: AsyncClient, monkeypatch):
    calls = {}

    async def fake_run_coordination_detection(**kwargs):
        calls.update(kwargs)
        return {
            "network": {
                "nodes": [{"id": "u1", "cluster_id": 0, "cluster_size": 2, "cluster_degree": 2}],
                "edges": [{"source": "u1", "target": "u2", "weight": 1.5}],
                "node_count": 2,
                "edge_count": 1,
                "component_count": 1,
                "components": [["u1", "u2"]],
                "cluster_count": 1,
                "clusters": [{"cluster_id": 0, "size": 2, "members": ["u1", "u2"]}],
            },
            "account_stats": [],
            "group_stats": [],
            "cluster_stats": [{"cluster_id": 0, "size": 2, "members": ["u1", "u2"]}],
            "summary": {"coordinated_accounts": 2, "cluster_count": 1},
        }

    monkeypatch.setattr(
        coordination_api.coordination_service,
        "run_coordination_detection",
        fake_run_coordination_detection,
    )

    # The preview bypass ships disabled with an empty token, so enable it
    # explicitly for the test that covers it.
    preview_token = "cogguard-preview-token"
    monkeypatch.setattr(settings, "PREVIEW_AUTH_ENABLED", True)
    monkeypatch.setattr(settings, "PREVIEW_AUTH_TOKEN", preview_token)
    monkeypatch.setattr(settings, "BACKEND_DEBUG", True)
    monkeypatch.setattr(settings, "BACKEND_ENV", "local")

    client.headers["Authorization"] = f"Bearer {preview_token}"
    response = await client.post("/api/v1/coordination/detect?time_window=45&min_participation=1&edge_weight=0.4")

    assert response.status_code == 200
    assert calls == {
        "time_window": 45,
        "min_participation": 1,
        "edge_weight": 0.4,
        "platform": None,
        "event_id": None,
    }
    assert response.json()["data"]["summary"]["coordinated_accounts"] == 2


def test_propagation_analysis_filters_posts_and_comments_by_event(monkeypatch):
    posts = [_post("event-1", "douyin", "p1", "u1", "2026-05-21T00:00:00+00:00")]
    comments = [{"event_id": "event-1", "platform": "douyin", "comment_id": "c1", "post_id": "p1"}]
    raw_posts = FakeCollection(posts)
    raw_comments = FakeCollection(comments)
    fake_db = FakeMongoDB(raw_posts=raw_posts, raw_comments=raw_comments)
    monkeypatch.setattr(propagation_observation_service, "get_mongo_db", lambda: fake_db)
    monkeypatch.setattr(
        propagation_observation_service,
        "build_propagation_graph",
        lambda loaded_posts, loaded_comments: {
            "graph": {"node_count": len(loaded_posts), "edge_count": len(loaded_comments)},
            "key_roles": {},
            "claims": [],
            "timeline": [],
        },
    )

    result = asyncio.run(
        propagation_observation_service.analyze_observed_propagation(platform="douyin", event_id="event-1")
    )

    assert raw_posts.calls[0]["query"] == {"event_id": "event-1", "platform": "douyin"}
    assert raw_comments.calls[0]["query"] == {"event_id": "event-1", "platform": "douyin"}
    assert result["event_id"] == "event-1"
    assert result["platform"] == "douyin"
    assert result["data_scope"] == {"posts": 1, "comments": 1}


def test_risk_assessment_passes_event_id_to_upstream_services(monkeypatch):
    calls = {}

    async def fake_coordination(**kwargs):
        calls["coordination"] = kwargs
        return {"summary": {"coordinated_accounts": 0, "coordinated_edges": 0, "total_pairs": 0}}

    async def fake_propagation(**kwargs):
        calls["propagation"] = kwargs
        return {"graph": {"nodes": [], "edges": [], "node_count": 0, "edge_count": 0}, "claims": [], "timeline": []}

    async def fake_accounts(**kwargs):
        calls["accounts"] = kwargs
        return []

    monkeypatch.setattr(risk_service.coordination_service, "run_coordination_detection", fake_coordination)
    monkeypatch.setattr(risk_service.propagation_service, "analyze_propagation", fake_propagation)
    monkeypatch.setattr(risk_service.account_service, "get_account_profiles", fake_accounts)

    report = asyncio.run(risk_service.assess_risk(event_id="event-1", platform="xhs", db=None))

    assert calls["coordination"]["event_id"] == "event-1"
    assert calls["propagation"]["event_id"] == "event-1"
    assert calls["accounts"]["event_id"] == "event-1"
    assert report["event_id"] == "event-1"
    assert report["platform"] == "xhs"


def test_account_profiles_filters_by_event_and_platform(monkeypatch):
    posts = [_post("event-1", "weibo", "p1", "u1", "2026-05-21T00:00:00+00:00")]
    raw_posts = FakeCollection(posts)
    fake_db = FakeMongoDB(raw_posts=raw_posts)
    monkeypatch.setattr(account_service, "get_mongo_db", lambda: fake_db)

    profiles = asyncio.run(account_service.get_account_profiles(event_id="event-1", platform="weibo"))

    assert raw_posts.calls[0]["query"] == {"event_id": "event-1", "platform": "weibo"}
    assert profiles[0]["account_id"] == "u1"


def test_coordination_api_passes_event_id_to_service(monkeypatch):
    calls = {}

    async def fake_run_coordination_detection(**kwargs):
        calls.update(kwargs)
        return {"summary": {}}

    monkeypatch.setattr(coordination_api.coordination_service, "run_coordination_detection", fake_run_coordination_detection)

    asyncio.run(coordination_api.run_detection(event_id="event-1", platform="weibo", _current_user=object()))

    assert calls["event_id"] == "event-1"
    assert calls["platform"] == "weibo"


def test_coordination_api_accepts_cluster_enriched_payload(monkeypatch):
    async def fake_run_coordination_detection(**kwargs):
        return {
            "network": {
                "nodes": [{"id": "u1", "cluster_id": 0, "cluster_size": 2, "cluster_degree": 3}],
                "edges": [],
                "node_count": 1,
                "edge_count": 0,
                "component_count": 1,
                "components": [{"size": 1, "members": ["u1"]}],
                "cluster_count": 1,
                "clusters": [{"cluster_id": 0, "size": 1, "members": ["u1"]}],
            },
            "account_stats": [],
            "group_stats": [],
            "cluster_stats": [{"cluster_id": 0, "size": 1, "members": ["u1"]}],
            "summary": {"coordinated_accounts": 1, "coordinated_edges": 0, "total_pairs": 0, "cluster_count": 1},
        }

    monkeypatch.setattr(coordination_api.coordination_service, "run_coordination_detection", fake_run_coordination_detection)

    payload = asyncio.run(coordination_api.run_detection(event_id="event-1", platform="weibo", _current_user=object()))

    assert payload["data"]["summary"]["cluster_count"] == 1
    assert payload["data"]["network"]["clusters"][0]["cluster_id"] == 0


def test_propagation_api_passes_event_id_to_observed_analysis(monkeypatch):
    calls = {}

    async def fake_analyze_propagation(platform=None, event_id=None):
        calls["analyze"] = {"platform": platform, "event_id": event_id}
        return {}

    monkeypatch.setattr(
        propagation_api.propagation_observation_service,
        "analyze_observed_propagation",
        fake_analyze_propagation,
    )

    asyncio.run(propagation_api.analyze(platform="douyin", event_id="event-1", _current_user=object()))

    assert calls["analyze"] == {"platform": "douyin", "event_id": "event-1"}


def test_propagation_model_event_reads_current_event_data(monkeypatch):
    posts = [
        _post("event-1", "weibo", "p1", "u1", "2024-01-01T00:00:00Z"),
        _post("event-1", "weibo", "p2", "u2", "2024-01-01T00:01:00Z"),
        _post("event-1", "weibo", "p3", "u3", "2024-01-01T00:02:00Z"),
    ]
    comments = [
        _comment("event-1", "weibo", "c1", "p1", "u2", "2024-01-01T00:03:00Z"),
    ]
    raw_posts = FakeCollection(posts)
    raw_comments = FakeCollection(comments)
    fake_db = FakeMongoDB(raw_posts=raw_posts, raw_comments=raw_comments)
    monkeypatch.setattr(propagation_model_service, "get_mongo_db", lambda: fake_db)

    async def fake_predict_event_macro_micro(*, posts, comments=None, top_k=10):
        return {
            "status": "ok",
            "model_status": "available",
            "macro": {"predicted_size": 5},
            "micro": {"top_users": [{"author_id": "u2", "author_name": "u2", "score": 0.5}]},
            "model": {"name": "Ours"},
        }

    monkeypatch.setattr(
        propagation_model_service.propagation_prediction_service,
        "predict_event_macro_micro",
        fake_predict_event_macro_micro,
    )

    result = asyncio.run(
        propagation_model_service.predict_current_event_model(
            event_id="event-1",
            platform="weibo",
            top_k=5,
        )
    )

    assert raw_posts.calls[0]["query"] == {"event_id": "event-1", "platform": "weibo"}
    assert raw_comments.calls[0]["query"] == {"event_id": "event-1", "platform": "weibo"}
    assert result["status"] == "ok"
    assert result["data_scope"] == {"posts": 3, "comments": 1}
    assert result["micro"]["top_users"][0]["author_id"] == "u2"
    assert result["methodology"]["schema"] == "cogguard.propagation.methodology.macro_micro_sequence.v1"


def test_propagation_api_passes_event_model_prediction_params(monkeypatch):
    calls = {}

    async def fake_predict_propagation_model_event(platform=None, event_id=None, top_k=10):
        calls.update({"platform": platform, "event_id": event_id, "top_k": top_k})
        return {
            "status": "ok",
            "model_status": "available",
            "methodology": {"method_name": "Macro/Micro Sequence Propagation Prediction"},
        }

    monkeypatch.setattr(
        propagation_api.propagation_model_service,
        "predict_current_event_model",
        fake_predict_propagation_model_event,
    )

    payload = asyncio.run(
        propagation_api.predict_model_event(
            platform="weibo",
            event_id="event-1",
            top_k=7,
            _current_user=object(),
        )
    )

    assert calls == {"platform": "weibo", "event_id": "event-1", "top_k": 7}
    assert payload["data"]["model_status"] == "available"
    assert payload["data"].get("methodology", {}).get("method_name") == "Macro/Micro Sequence Propagation Prediction"


def test_propagation_api_accepts_local_preview_dependency(monkeypatch):
    calls = {}

    async def fake_preview_user():
        return None

    async def fake_analyze_propagation(platform=None, event_id=None):
        calls["analyze"] = {"platform": platform, "event_id": event_id}
        return {"event_id": event_id, "platform": platform}

    async def fake_predict_current_event_model(platform=None, event_id=None, top_k=10):
        calls["predict"] = {"platform": platform, "event_id": event_id, "top_k": top_k}
        return {"event_id": event_id, "platform": platform}

    monkeypatch.setattr(
        propagation_api.propagation_observation_service,
        "analyze_observed_propagation",
        fake_analyze_propagation,
    )
    monkeypatch.setattr(
        propagation_api.propagation_model_service,
        "predict_current_event_model",
        fake_predict_current_event_model,
    )
    app.dependency_overrides[get_current_user_or_local_preview] = fake_preview_user

    async def run_requests():
        from httpx import ASGITransport

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            analyze_resp = await client.get("/api/v1/propagation/analyze?event_id=event-1&platform=weibo")
            prediction_resp = await client.post("/api/v1/propagation/model-event-predict?event_id=event-1&platform=weibo")
        return analyze_resp, prediction_resp

    try:
        analyze_resp, prediction_resp = asyncio.run(run_requests())
    finally:
        app.dependency_overrides.pop(get_current_user_or_local_preview, None)

    assert analyze_resp.status_code == 200
    assert prediction_resp.status_code == 200
    assert analyze_resp.json()["data"] == {"event_id": "event-1", "platform": "weibo"}
    assert prediction_resp.json()["data"] == {"event_id": "event-1", "platform": "weibo"}
    assert calls["analyze"] == {"platform": "weibo", "event_id": "event-1"}
    assert calls["predict"] == {"platform": "weibo", "event_id": "event-1", "top_k": 10}


def test_propagation_api_passes_prediction_params(monkeypatch):
    calls = {}

    async def fake_predict_benchmark_model_evidence(**kwargs):
        calls.update(kwargs)
        return {"status": "ok", "model": "SequenceJointModel"}

    monkeypatch.setattr(
        propagation_api.propagation_model_service,
        "predict_benchmark_model_evidence",
        fake_predict_benchmark_model_evidence,
    )

    payload = asyncio.run(
        propagation_api.predict_macro_micro_model(
            dataset="douban",
            seed=43,
            run_live=False,
            _current_user=object(),
        )
    )

    assert calls == {"dataset": "douban", "seed": 43, "run_live": False}
    assert payload["data"]["model_display_name"] == "Ours"


def test_propagation_api_exposes_model_prediction_without_frontend_method_label(monkeypatch):
    calls = {}

    async def fake_predict_benchmark_model_evidence(**kwargs):
        calls.update(kwargs)
        return {
            "status": "ok",
            "dataset": kwargs["dataset"],
            "seed": kwargs["seed"],
            "methodology": {"method_name": "Macro/Micro Sequence Propagation Prediction"},
        }

    monkeypatch.setattr(
        propagation_api.propagation_model_service,
        "predict_benchmark_model_evidence",
        fake_predict_benchmark_model_evidence,
    )

    payload = asyncio.run(
        propagation_api.predict_macro_micro_model(
            dataset="twitter",
            seed=42,
            run_live=False,
            _current_user=object(),
        )
    )

    assert calls == {"dataset": "twitter", "seed": 42, "run_live": False}
    assert payload["data"]["model_display_name"] == "Ours"
    assert payload["data"]["dataset"] == "twitter"
    assert "model" not in payload["data"]


def test_propagation_prediction_service_loads_cached_macro_micro_result():
    result = asyncio.run(
        propagation_prediction_service.predict_propagation_macro_micro(
            dataset="twitter",
            seed=42,
            run_live=False,
        )
    )

    assert result["status"] == "ok"
    assert result["model"] == propagation_prediction_service.PROPAGATION_MODEL_NAME
    assert result["label"] == "实验预测"
    assert result["is_experimental"] is True
    assert result["macro"]["metrics"]["msle"] is not None
    assert result["micro"]["metrics"]["hits@10"] is not None
    assert result["candidate_protocol_audit"]["leakage_check_passed"] is True
    assert result["methodology"]["method_name"] == "Macro/Micro Sequence Propagation Prediction"
    assert result["methodology"]["leakage_boundary"]["legacy_speed_acceleration_scaffold"] == "not used by public prediction endpoints"


def test_risk_api_passes_event_id_to_assess_and_report_filters(monkeypatch):
    calls = {}

    class CurrentUser:
        id = 7

    async def fake_assess_risk(**kwargs):
        calls["assess"] = kwargs
        return {}

    async def fake_list_reports(**kwargs):
        calls["list"] = kwargs
        return [], 0

    monkeypatch.setattr(risk_api.risk_service, "assess_risk", fake_assess_risk)
    monkeypatch.setattr(risk_api.risk_service, "list_reports", fake_list_reports)

    asyncio.run(
        risk_api.assess_risk(
            event_id="event-1",
            platform="xhs",
            current_user=CurrentUser(),
            db=object(),
        )
    )
    asyncio.run(risk_api.list_reports(event_id="event-1", _current_user=object(), db=object()))

    assert calls["assess"]["event_id"] == "event-1"
    assert calls["assess"]["platform"] == "xhs"
    assert calls["list"]["event_id"] == "event-1"
