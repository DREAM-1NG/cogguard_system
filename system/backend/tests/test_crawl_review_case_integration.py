from __future__ import annotations

import asyncio

from app.tasks import crawl_tasks


def test_successful_crawl_only_triggers_case_orchestration_for_explicit_event(monkeypatch):
    calls: list[dict] = []

    async def fake_process(**kwargs):
        calls.append(kwargs)
        return {"case_id": "case_1", "created_revision": True}

    monkeypatch.setattr(crawl_tasks, "process_successful_crawl", fake_process)

    class FakeSession:
        async def commit(self):
            return None

    class FakeSessionContext:
        async def __aenter__(self):
            return FakeSession()

        async def __aexit__(self, exc_type, exc, traceback):
            return False

    session_factory = FakeSessionContext

    explicit = asyncio.run(
        crawl_tasks._orchestrate_successful_crawl(
            job_id=7,
            params={"event_id": "event_1", "source_keyword": "Event one"},
            result={"posts_count": 2, "comments_count": 1},
            mongo_db={"raw_posts": object(), "raw_comments": object()},
            session_factory=session_factory,
        )
    )
    implicit = asyncio.run(
        crawl_tasks._orchestrate_successful_crawl(
            job_id=8,
            params={"keywords": ["event"]},
            result={"posts_count": 1, "comments_count": 0},
            mongo_db={"raw_posts": object(), "raw_comments": object()},
            session_factory=session_factory,
        )
    )

    assert explicit == {"case_id": "case_1", "created_revision": True}
    assert implicit == {"skipped": True, "reason": "event_id_not_provided"}
    assert len(calls) == 1
    assert calls[0]["event_id"] == "event_1"
