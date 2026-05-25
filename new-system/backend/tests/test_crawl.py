"""Tests for crawl APIs and crawl-related helpers."""

import pytest
from httpx import AsyncClient

from app.core.crawler.mock import MockCrawler
from app.core.crawler.normalizer import DataNormalizer
from app.models.task import CrawlJob
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
        "id": "wb_001",
        "text": "原始微博内容",
        "user_id": "12345",
        "nickname": "测试用户",
        "created_at": "2026-04-01T10:00:00",
        "like_count": 100,
        "repost_count": 50,
        "comment_count": 30,
    }
    post = DataNormalizer.normalize_post(raw, "weibo")
    assert post.platform == "weibo"
    assert post.post_id == "wb_001"
    assert post.content == "原始微博内容"
    assert post.author_name == "测试用户"
    assert post.likes == 100


def test_normalizer_standardizes_comment():
    raw = {
        "id": "cmt_001",
        "post_id": "wb_001",
        "text": "评论内容",
        "user_id": "67890",
        "nickname": "评论者",
        "created_at": "2026-04-01T10:05:00",
    }
    comment = DataNormalizer.normalize_comment(raw, "weibo")
    assert comment.platform == "weibo"
    assert comment.comment_id == "cmt_001"
    assert comment.content == "评论内容"


@pytest.mark.asyncio
async def test_list_platforms(client: AsyncClient):
    response = await client.get("/api/v1/crawl/platforms")
    assert response.status_code == 200
    data = response.json()["data"]
    assert any(platform["id"] == "mock_weibo" for platform in data)


@pytest.mark.asyncio
async def test_create_crawl_job_requires_auth(client: AsyncClient):
    response = await client.post(
        "/api/v1/crawl/social",
        json={"platform": "mock_weibo", "keywords": ["test"], "max_posts": 5},
    )
    assert response.status_code == 403


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
async def test_preview_token_can_read_crawl_jobs(setup_database, client: AsyncClient):
    await client.post(
        "/api/v1/auth/register",
        json={
            "username": "previewuser",
            "email": "preview@example.com",
            "password": "testpass123",
        },
    )

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

    client.headers["Authorization"] = "Bearer cogguard-preview-token"
    response = await client.get("/api/v1/crawl/jobs?page=1&page_size=20")
    assert response.status_code == 200
    items = response.json()["data"]["items"]
    assert any(item["platform"] == "douyin" for item in items)
