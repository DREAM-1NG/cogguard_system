import asyncio

import pandas as pd

from app.services import account_service, coordination_service, propagation_service, risk_service
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


def _post(event_id, platform, post_id, author_id, timestamp, *, hashtags=None, media_urls=None):
    return {
        "event_id": event_id,
        "platform": platform,
        "post_id": post_id,
        "author_id": author_id,
        "author_name": author_id,
        "timestamp": timestamp,
        "content": f"content {post_id}",
        "url": "https://example.com/shared",
        "hashtags": hashtags or [],
        "media_urls": media_urls or [],
        "likes": 1,
        "reposts": 0,
        "comments_count": 0,
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


def test_coordination_detection_filters_by_event_and_includes_metadata(monkeypatch):
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
        )
    )

    assert raw_posts.calls[0]["query"] == {"event_id": "event-1", "platform": "weibo"}
    assert result["summary"]["event_id"] == "event-1"
    assert result["summary"]["platform"] == "weibo"
    assert result["summary"]["total_posts"] == 2
    assert result["summary"]["total_pairs"] >= 1
    assert "cluster_count" in result["summary"]
    assert "cluster_stats" in result


def test_generate_network_adds_cluster_annotations():
    graph = coordination_service.generate_coordinated_network(_make_pair_result(), edge_weight=0.5)
    network = coordination_service.graph_to_dict(graph)

    assert network["cluster_count"] >= 1
    assert len(network["clusters"]) == network["cluster_count"]
    assert all("cluster_id" in node for node in network["nodes"])
    assert all("cluster_size" in node for node in network["nodes"])
    assert all("cluster_degree" in node for node in network["nodes"])
    assert any(cluster["members"] for cluster in network["clusters"])


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


def test_propagation_analysis_filters_posts_and_comments_by_event(monkeypatch):
    posts = [_post("event-1", "douyin", "p1", "u1", "2026-05-21T00:00:00+00:00")]
    comments = [{"event_id": "event-1", "platform": "douyin", "comment_id": "c1", "post_id": "p1"}]
    raw_posts = FakeCollection(posts)
    raw_comments = FakeCollection(comments)
    fake_db = FakeMongoDB(raw_posts=raw_posts, raw_comments=raw_comments)
    monkeypatch.setattr(propagation_service, "get_mongo_db", lambda: fake_db)
    monkeypatch.setattr(
        propagation_service,
        "build_propagation_graph",
        lambda loaded_posts, loaded_comments: {
            "graph": {"node_count": len(loaded_posts), "edge_count": len(loaded_comments)},
            "key_roles": {},
            "claims": [],
            "timeline": [],
        },
    )

    result = asyncio.run(propagation_service.analyze_propagation(platform="douyin", event_id="event-1"))

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


def test_propagation_api_passes_event_id_to_services(monkeypatch):
    calls = {}

    async def fake_analyze_propagation(platform=None, event_id=None):
        calls["analyze"] = {"platform": platform, "event_id": event_id}
        return {}

    async def fake_predict_propagation_trend(platform=None, event_id=None):
        calls["predict"] = {"platform": platform, "event_id": event_id}
        return {}

    monkeypatch.setattr(propagation_api.propagation_service, "analyze_propagation", fake_analyze_propagation)
    monkeypatch.setattr(propagation_api.propagation_service, "predict_propagation_trend", fake_predict_propagation_trend)

    asyncio.run(propagation_api.analyze(platform="douyin", event_id="event-1", _current_user=object()))
    asyncio.run(propagation_api.predict_trend(platform="douyin", event_id="event-1", _current_user=object()))

    assert calls["analyze"] == {"platform": "douyin", "event_id": "event-1"}
    assert calls["predict"] == {"platform": "douyin", "event_id": "event-1"}


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
