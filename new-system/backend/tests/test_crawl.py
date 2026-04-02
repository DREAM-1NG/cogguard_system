"""数据采集模块测试。

包含两类测试：
1. 纯单元测试（无需外部服务）：MockCrawler 数据生成、DataNormalizer 字段映射
2. API 测试（需要 MySQL）：采集任务创建、平台列表查询、鉴权校验
"""

import pytest
from httpx import AsyncClient

from app.core.crawler.mock import MockCrawler
from app.core.crawler.normalizer import DataNormalizer


@pytest.mark.asyncio
async def test_mock_crawler_generates_posts():
    crawler = MockCrawler()
    posts = await crawler.search(keywords=["测试话题"], max_posts=10)
    assert len(posts) == 10
    for p in posts:
        assert p.platform == "mock_weibo"
        assert p.content
        assert p.author_id
        assert p.timestamp


@pytest.mark.asyncio
async def test_mock_crawler_generates_comments():
    crawler = MockCrawler()
    comments = await crawler.fetch_comments("post_123")
    assert len(comments) > 0
    for c in comments:
        assert c.post_id == "post_123"
        assert c.content
        assert c.author_id


@pytest.mark.asyncio
async def test_mock_crawler_coordinated_pattern():
    """Verify that mock data includes coordinated-looking posts (tight time window)."""
    crawler = MockCrawler()
    posts = await crawler.search(keywords=["协同测试"], max_posts=20)
    timestamps = sorted(p.timestamp for p in posts)
    min_gaps = []
    for i in range(1, len(timestamps)):
        gap = (timestamps[i] - timestamps[i - 1]).total_seconds()
        min_gaps.append(gap)
    assert min(min_gaps) < 60, "Expected some posts within 60 seconds of each other"


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
    resp = await client.get("/api/v1/crawl/platforms")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert any(p["id"] == "mock_weibo" for p in data)


@pytest.mark.asyncio
async def test_create_crawl_job_requires_auth(client: AsyncClient):
    resp = await client.post(
        "/api/v1/crawl/social",
        json={"platform": "mock_weibo", "keywords": ["test"], "max_posts": 5},
    )
    assert resp.status_code == 403
