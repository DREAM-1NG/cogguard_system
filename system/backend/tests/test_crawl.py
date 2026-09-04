"""Tests for crawl APIs and crawl-related helpers."""

import pytest
from httpx import AsyncClient

from app.api.v1 import crawl as crawl_api
from app.core.crawler.mock import MockCrawler
from app.core.crawler.social import generic_jsonl_to_comment, generic_jsonl_to_post
from app.models.task import CrawlJob
from app.services import crawl_service
from tests.conftest import needs_db, test_session_factory


@pytest.mark.asyncio
async def test_mock_crawler_generates_posts():
    crawler = MockCrawler()
    posts = await crawler.search(keywords=["测试话题"], max_posts=10)
    assert len(posts) == 10
    for post in posts:
        assert post.platform == "mock_weibo"
        assert post.content
        assert post.author_id
        assert post.timestamp


@pytest.mark.asyncio
async def test_mock_crawler_generates_comments():
    crawler = MockCrawler()
    comments = await crawler.fetch_comments("post_123")
    assert len(comments) > 0
    for comment in comments:
        assert comment.post_id == "post_123"
        assert comment.content
        assert comment.author_id


@pytest.mark.asyncio
async def test_mock_crawler_coordinated_pattern():
    crawler = MockCrawler()
    posts = await crawler.search(keywords=["协同测试"], max_posts=20)
    timestamps = sorted(post.timestamp for post in posts)
    gaps = []
    for index in range(1, len(timestamps)):
        gaps.append((timestamps[index] - timestamps[index - 1]).total_seconds())
    assert min(gaps) < 60


def test_normalizer_standardizes_weibo_post():
    raw = {
        "note_id": "wb_001",
        "content": "原始微博内容",
        "user_id": "12345",
        "nickname": "测试用户",
        "create_time": "2026-04-01T10:00:00",
        "liked_count": 100,
        "shared_count": 50,
        "comments_count": 30,
    }
    post = generic_jsonl_to_post(raw, "weibo")
    assert post.platform == "weibo"
    assert post.post_id == "wb_001"
    assert post.content == "原始微博内容"
    assert post.author_name == "测试用户"
    assert post.likes == 100


def test_normalizer_standardizes_comment():
    raw = {
        "comment_id": "cmt_001",
        "note_id": "wb_001",
        "content": "评论内容",
        "user_id": "67890",
        "nickname": "评论者",
        "create_time": "2026-04-01T10:05:00",
    }
    comment = generic_jsonl_to_comment(raw, "weibo")
    assert comment.platform == "weibo"
    assert comment.comment_id == "cmt_001"
    assert comment.content == "评论内容"


@pytest.mark.asyncio
async def test_list_platforms(client: AsyncClient):
    response = await client.get("/api/v1/crawl/platforms")
    assert response.status_code == 200
    data = response.json()["data"]
    ids = {platform["id"] for platform in data}
    names = {platform["name"] for platform in data}
    assert "mock_weibo" not in ids
    assert {"微博", "抖音", "小红书"}.issubset(names)
    assert all("MediaCrawler" not in name for name in names)


@pytest.mark.asyncio
async def test_create_crawl_job_requires_auth(client: AsyncClient):
    response = await client.post(
        "/api/v1/crawl/social",
        json={"platform": "mock_weibo", "keywords": ["test"], "max_posts": 5},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
@needs_db
async def test_list_jobs_includes_system_owned_records_for_user(
    setup_database, auth_client: AsyncClient
):
    async with test_session_factory() as session:
        session.add(
            CrawlJob(
                job_type="social",
                platform="weibo",
                params_json="{}",
                status="completed",
                progress=100,
                created_by=0,
            )
        )
        session.add(
            CrawlJob(
                job_type="social",
                platform="xhs",
                params_json="{}",
                status="completed",
                progress=100,
                created_by=1,
            )
        )
        await session.commit()

    response = await auth_client.get("/api/v1/crawl/jobs?page=1&page_size=20")
    assert response.status_code == 200
    items = response.json()["data"]["items"]
    platforms = {item["platform"] for item in items}
    assert {"weibo", "xhs"}.issubset(platforms)


@pytest.mark.asyncio
@needs_db
async def test_authenticated_user_can_read_system_owned_crawl_jobs(setup_database, auth_client: AsyncClient):
    async with test_session_factory() as session:
        session.add(
            CrawlJob(
                job_type="social",
                platform="douyin",
                params_json="{}",
                status="completed",
                progress=100,
                created_by=0,
            )
        )
        await session.commit()

    response = await auth_client.get("/api/v1/crawl/jobs?page=1&page_size=20")
    assert response.status_code == 200
    items = response.json()["data"]["items"]
    assert any(item["platform"] == "douyin" for item in items)


@pytest.mark.asyncio
@needs_db
async def test_create_crawl_job_local_execution_schedules_backend_task(
    setup_database, auth_client: AsyncClient, monkeypatch
):
    calls = []

    def fake_run_crawl_job(job_id: int, params_json: str):
        calls.append((job_id, params_json))

    monkeypatch.setattr(crawl_api, "run_crawl_job", fake_run_crawl_job)

    response = await auth_client.post(
        "/api/v1/crawl/social",
        json={
            "platform": "mock_weibo",
            "keywords": ["前端任务"],
            "event_id": "frontend_smoke",
            "max_posts": 2,
            "crawl_comments": False,
            "execution_mode": "local",
        },
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["status"] == "running"
    assert data["celery_task_id"].startswith("local:")
    assert calls
    assert '"execution_mode": "local"' in calls[0][1]


@pytest.mark.asyncio
@needs_db
async def test_create_media_download_job_schedules_backend_task(
    setup_database, auth_client: AsyncClient, monkeypatch
):
    calls = []

    def fake_run_media_download_job(job_id: int, params_json: str):
        calls.append((job_id, params_json))
        return {}

    monkeypatch.setattr(
        crawl_api.media_download_service,
        "run_media_download_job",
        fake_run_media_download_job,
    )

    response = await auth_client.post(
        "/api/v1/crawl/media-downloads",
        json={
            "platform": "douyin",
            "keyword": "测试",
            "event_id": "event_1",
            "post_ids": ["p1"],
            "media_types": ["video", "image"],
        },
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["job_type"] == "media_download"
    assert data["platform"] == "media_download"
    assert data["status"] == "running"
    assert data["celery_task_id"].startswith("local:")
    assert calls
    payload = calls[0][1]
    assert '"platform": "douyin"' in payload
    assert '"event_id": "event_1"' in payload


@pytest.mark.asyncio
@needs_db
async def test_delete_media_download_job_does_not_delete_raw_crawl_data(
    setup_database, monkeypatch
):
    delete_calls = []

    class FakeCollection:
        async def delete_many(self, query):
            delete_calls.append(query)

    class FakeMongo:
        def __getitem__(self, _name):
            return FakeCollection()

    monkeypatch.setattr(crawl_service, "get_mongo_db", lambda: FakeMongo())

    async with test_session_factory() as session:
        job = CrawlJob(
            job_type="media_download",
            platform="media_download",
            params_json="{}",
            status="completed",
            progress=100,
            created_by=1,
        )
        session.add(job)
        await session.commit()
        await session.refresh(job)
        job_id = job.id

    async with test_session_factory() as session:
        deleted = await crawl_service.delete_job(job_id, 1, session)
        await session.commit()

    assert deleted is True
    assert delete_calls == []
