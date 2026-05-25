import asyncio

from app.api.v1 import dashboard as dashboard_api
from app.services import dashboard_service


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


def _post(event_id, platform, post_id, author_name, timestamp, ip_location=None):
    return {
        "event_id": event_id,
        "platform": platform,
        "post_id": post_id,
        "author_id": f"{author_name}-id",
        "author_name": author_name,
        "timestamp": timestamp,
        "content": f"{author_name} content",
        "author_profile": {"ip_location": ip_location} if ip_location else {},
    }


def test_resolve_location_maps_beijing_and_keeps_unknown_structured():
    beijing = dashboard_service.resolve_location("IP属地：北京")
    unknown = dashboard_service.resolve_location("月球基地")

    assert beijing["resolved"] is True
    assert beijing["coordinates"] == [116.4074, 39.9042]
    assert unknown["resolved"] is False
    assert unknown["coordinates"] is None
    assert dashboard_service.resolve_location("United States of America")["resolved"] is True


def test_extract_ip_location_from_raw_mblog_region_name():
    post = {"raw_data": {"post_details_raw": {"mblog": {"region_name": "发布于 北京"}}}}

    assert dashboard_service.extract_ip_location(post) == "发布于 北京"


def test_dashboard_overview_filters_event_and_uses_first_poster_location(monkeypatch):
    posts = [
        _post("event-1", "weibo", "p2", "第二发帖者", "2026-05-21T01:00:00+00:00", "上海"),
        _post("event-1", "weibo", "p1", "新华日报", "2026-05-21T00:00:00+00:00", "北京"),
        _post("event-1", "xhs", "p3", "后续账号", "2026-05-21T02:00:00+00:00", "广东"),
    ]
    comments = [
        {"event_id": "event-1", "platform": "weibo", "comment_id": "c1"},
        {"event_id": "event-1", "platform": "xhs", "comment_id": "c2"},
    ]
    raw_posts = FakeCollection(posts)
    raw_comments = FakeCollection(comments)
    fake_db = FakeMongoDB(raw_posts=raw_posts, raw_comments=raw_comments)
    monkeypatch.setattr(dashboard_service, "get_mongo_db", lambda: fake_db)

    result = asyncio.run(dashboard_service.get_dashboard_overview(event_id="event-1", db=None))

    assert raw_posts.calls[0]["query"] == {"event_id": "event-1"}
    assert raw_comments.calls[0]["query"] == {"event_id": "event-1"}
    assert result["summary"]["posts"] == 3
    assert result["summary"]["comments"] == 2
    assert result["summary"]["platform_count"] == 2
    event_point = result["event_locations"][0]
    assert event_point["origin_author"] == "新华日报"
    assert event_point["origin_post_id"] == "p1"
    assert event_point["ip_location"] == "北京"
    assert event_point["coordinates"] == [116.4074, 39.9042]


def test_dashboard_overview_falls_back_to_first_geolocated_post(monkeypatch):
    posts = [
        _post("event-1", "weibo", "p1", "首帖账号", "2026-05-21T00:00:00+00:00", None),
        _post("event-1", "xhs", "p2", "次帖账号", "2026-05-21T01:00:00+00:00", "广东"),
    ]
    fake_db = FakeMongoDB(
        raw_posts=FakeCollection(posts),
        raw_comments=FakeCollection([]),
    )
    monkeypatch.setattr(dashboard_service, "get_mongo_db", lambda: fake_db)

    result = asyncio.run(dashboard_service.get_dashboard_overview(event_id="event-1", db=None))

    event_point = result["event_locations"][0]
    assert event_point["origin_author"] == "首帖账号"
    assert event_point["origin_ip_location"] is None
    assert event_point["location_source_author"] == "次帖账号"
    assert event_point["ip_location"] == "广东"
    assert event_point["resolved"] is True


def test_dashboard_api_passes_event_id_to_service(monkeypatch):
    calls = {}

    async def fake_overview(**kwargs):
        calls.update(kwargs)
        return {"summary": {}, "event_locations": []}

    monkeypatch.setattr(dashboard_api.dashboard_service, "get_dashboard_overview", fake_overview)

    response = asyncio.run(
        dashboard_api.overview(
            event_id="event-1",
            _current_user=object(),
            db=object(),
        )
    )

    assert calls["event_id"] == "event-1"
    assert response["code"] == 0
    assert "summary" in response["data"]
