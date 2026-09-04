from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from app.core.crawler.types import CrawlBatch
from app.core.propagation_monitoring import PropagationMonitoring, PropagationMonitoringPorts
from app.models.post import StandardComment, StandardPost
from app.services import crawl_service
from app.tasks import crawl_tasks


class _FakeCollection:
    def __init__(self) -> None:
        self.writes: list[tuple[list[object], bool]] = []

    async def bulk_write(self, operations, *, ordered):
        self.writes.append((list(operations), ordered))


class _FakeMongo:
    def __init__(self) -> None:
        self.collections = {
            "raw_posts": _FakeCollection(),
            "raw_comments": _FakeCollection(),
        }

    def __getitem__(self, name: str):
        return self.collections[name]


class _FakeMongoClient:
    def __init__(self, database: _FakeMongo) -> None:
        self.database = database

    def __getitem__(self, _name: str):
        return self.database

    def close(self) -> None:
        return None


def _cache_monitoring(calls: list[tuple[str | None, str | None]]) -> PropagationMonitoring:
    async def observe(**kwargs):
        calls.append((kwargs["platform"], kwargs["event_id"]))
        return {"scope": [kwargs["platform"], kwargs["event_id"]]}

    async def forecast(**_kwargs):
        return {}

    return PropagationMonitoring(
        PropagationMonitoringPorts(
            observe=observe,
            forecast=forecast,
            validate_cutoff=lambda value: value,
            enforce_forecast=lambda result, **_scope: result,
            persistence=object(),
        )
    )


def test_successful_crawl_write_invalidates_only_affected_observed_scope(monkeypatch):
    calls: list[tuple[str | None, str | None]] = []
    monitoring = _cache_monitoring(calls)
    asyncio.run(monitoring.observed(platform="weibo", event_id="event-1", node_limit=80))
    asyncio.run(monitoring.observed(platform="xhs", event_id="event-1", node_limit=80))

    post = StandardPost(
        platform="weibo",
        post_id="post-1",
        content="new post",
        author_id="author-1",
        author_name="Author",
        timestamp=datetime.now(timezone.utc),
    )
    comment = StandardComment(
        platform="weibo",
        comment_id="comment-1",
        post_id="post-1",
        content="new comment",
        author_id="author-2",
        author_name="Commenter",
        timestamp=datetime.now(timezone.utc),
    )
    batch = CrawlBatch(posts=[post], comments=[comment], crawl_metadata={"source": "test"})
    mongo_db = _FakeMongo()

    class FakeCrawler:
        async def collect(self, _request):
            return batch

    async def fake_orchestrate(**_kwargs):
        return {"created_revision": False}

    monkeypatch.setattr(crawl_tasks, "_create_task_mongo_client", lambda: _FakeMongoClient(mongo_db))
    monkeypatch.setattr(crawl_tasks, "build_crawler", lambda _platform: FakeCrawler())
    monkeypatch.setattr(crawl_tasks, "_orchestrate_successful_crawl", fake_orchestrate)
    monkeypatch.setattr(crawl_tasks, "_update_job_in_db", lambda *_args, **_kwargs: None)

    result = crawl_tasks.run_crawl_job(
        7,
        '{"platform": "weibo", "event_id": "event-1", "keywords": ["event"]}',
    )

    assert result["posts_count"] == 1
    assert result["comments_count"] == 1
    asyncio.run(monitoring.observed(platform="weibo", event_id="event-1", node_limit=80))
    asyncio.run(monitoring.observed(platform="xhs", event_id="event-1", node_limit=80))

    assert calls == [
        ("weibo", "event-1"),
        ("xhs", "event-1"),
        ("weibo", "event-1"),
    ]


def test_delete_job_invalidates_the_deleted_event_and_platform_scope(monkeypatch):
    calls: list[tuple[str | None, str | None]] = []
    monitoring = _cache_monitoring(calls)
    asyncio.run(monitoring.observed(platform="weibo", event_id="event-1", node_limit=80))
    asyncio.run(monitoring.observed(platform="xhs", event_id="event-1", node_limit=80))

    class _Result:
        def scalar_one_or_none(self):
            return type(
                "Job",
                (),
                {
                    "id": 7,
                    "job_type": "social",
                    "platform": "weibo",
                    "params_json": '{"event_id": "event-1"}',
                },
            )()

    class _DB:
        async def execute(self, _statement):
            return _Result()

        async def delete(self, _job):
            return None

        async def flush(self):
            return None

    mongo_db = _FakeMongo()
    for collection in mongo_db.collections.values():
        collection.delete_many = lambda _query: asyncio.sleep(0)
    monkeypatch.setattr(crawl_service, "get_mongo_db", lambda: mongo_db)

    assert asyncio.run(crawl_service.delete_job(7, 42, _DB())) is True

    asyncio.run(monitoring.observed(platform="weibo", event_id="event-1", node_limit=80))
    asyncio.run(monitoring.observed(platform="xhs", event_id="event-1", node_limit=80))
    assert calls == [
        ("weibo", "event-1"),
        ("xhs", "event-1"),
        ("weibo", "event-1"),
    ]
