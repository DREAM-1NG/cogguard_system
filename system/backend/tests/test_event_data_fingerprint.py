from __future__ import annotations

import asyncio

from app.services.event_data import event_data_fingerprint


class FakeCollection:
    def __init__(self, count: int, job_id: int, object_id: str):
        self.count = count
        self.job_id = job_id
        self.object_id = object_id

    async def count_documents(self, _query):
        return self.count

    async def find_one(self, _query, _projection, sort=None):
        return {
            "_id": self.object_id,
            "crawl_job_id": self.job_id,
            "timestamp": "2026-05-21T00:00:00Z",
        }


def test_event_data_fingerprint_tracks_ingestion_generation():
    async def scenario():
        posts = FakeCollection(2, 10, "post-2")
        comments = FakeCollection(4, 10, "comment-4")
        first = await event_data_fingerprint(
            {"raw_posts": posts, "raw_comments": comments},
            event_id="event-1",
            platform="weibo",
        )

        posts.job_id = 11
        second = await event_data_fingerprint(
            {"raw_posts": posts, "raw_comments": comments},
            event_id="event-1",
            platform="weibo",
        )

        assert first
        assert second
        assert first != second

    asyncio.run(scenario())

def test_event_data_fingerprint_bypasses_collections_without_generation_api():
    class IncompleteCollection:
        pass

    async def scenario():
        result = await event_data_fingerprint(
            {"raw_posts": IncompleteCollection(), "raw_comments": IncompleteCollection()},
            event_id="event-1",
        )
        assert result is None

    asyncio.run(scenario())
