"""Mock crawler that generates deterministic-enough test data."""

from __future__ import annotations

import random
import uuid
from datetime import datetime, timedelta, timezone

from app.core.crawler.base import BaseCrawler
from app.core.crawler.types import CrawlBatch, CrawlRequestOptions
from app.models.post import StandardComment, StandardPost

_MOCK_CONTENT_TEMPLATES = [
    "{topic} incident update {url}",
    "Observers are discussing {topic} in detail {url}",
    "Fresh chatter about {topic} is spreading quickly {url}",
    "{topic} remains active across multiple accounts {url}",
    "Latest summary for {topic} {url}",
]

_MOCK_COMMENT_TEMPLATES = [
    "Interesting angle.",
    "This needs verification.",
    "I saw similar posts earlier.",
    "The timing looks unusual.",
    "More context would help.",
]

_MOCK_TOPICS = [
    "topic_A",
    "topic_B",
    "topic_C",
    "topic_D",
    "topic_E",
]

_MOCK_URLS = [
    "https://example.com/article/001",
    "https://example.com/article/002",
    "https://example.com/article/003",
]


class MockCrawler(BaseCrawler):
    platform = "mock_weibo"

    async def collect(self, request: CrawlRequestOptions) -> CrawlBatch:
        posts = await self._generate_posts(request.keywords, request.max_posts)
        comments = []
        if request.crawl_comments:
            for post in posts[:10]:
                comments.extend(await self.fetch_comments(post.post_id, request.max_comments_per_post or 100))
        return self._remember_batch(
            CrawlBatch(
                posts=posts,
                comments=comments,
                crawl_metadata={
                    "execution_mode": "mock",
                    "comments_requested": request.crawl_comments,
                },
            )
        )

    async def _generate_posts(self, keywords: list[str], max_posts: int = 50) -> list[StandardPost]:
        posts: list[StandardPost] = []
        base_time = datetime.now(timezone.utc) - timedelta(hours=6)
        topic = keywords[0] if keywords else random.choice(_MOCK_TOPICS)

        normal_count = max(1, int(max_posts * 0.6))
        for i in range(normal_count):
            offset_minutes = random.randint(0, 360)
            posts.append(
                self._make_post(
                    idx=i,
                    topic=topic,
                    url=random.choice(_MOCK_URLS + [""]),
                    timestamp=base_time + timedelta(minutes=offset_minutes),
                    author_prefix="user",
                )
            )

        coordinated_count = max_posts - normal_count
        shared_url = random.choice(_MOCK_URLS)
        coord_base = base_time + timedelta(hours=2)
        for i in range(coordinated_count):
            offset_seconds = random.randint(0, 30)
            posts.append(
                self._make_post(
                    idx=normal_count + i,
                    topic=topic,
                    url=shared_url,
                    timestamp=coord_base + timedelta(seconds=offset_seconds),
                    author_prefix="coord_bot",
                )
            )

        return posts[:max_posts]

    async def fetch_comments(self, post_id: str, max_comments: int = 100) -> list[StandardComment]:
        """Compatibility override for tests that still call the legacy wrapper."""
        comments: list[StandardComment] = []
        base_time = datetime.now(timezone.utc) - timedelta(hours=3)
        count = min(max_comments, random.randint(3, 20))
        for i in range(count):
            comments.append(
                StandardComment(
                    platform=self.platform,
                    comment_id=f"cmt_{uuid.uuid4().hex[:8]}",
                    post_id=post_id,
                    content=random.choice(_MOCK_COMMENT_TEMPLATES),
                    author_id=f"commenter_{random.randint(1000, 9999)}",
                    author_name=f"commenter_{random.randint(1, 500)}",
                    timestamp=base_time + timedelta(minutes=i * 5),
                    likes=random.randint(0, 100),
                )
            )
        return comments

    @staticmethod
    def _make_post(idx: int, topic: str, url: str, timestamp: datetime, author_prefix: str) -> StandardPost:
        template = random.choice(_MOCK_CONTENT_TEMPLATES)
        content = template.format(topic=topic, url=url).strip()
        author_id = f"{author_prefix}_{random.randint(1000, 9999)}"
        hashtags = [f"#{topic}#"]
        if url:
            hashtags.append("#linked#")
        return StandardPost(
            platform="mock_weibo",
            post_id=f"post_{uuid.uuid4().hex[:10]}",
            content=content,
            author_id=author_id,
            author_name=f"author_{idx}",
            timestamp=timestamp,
            url=url,
            likes=random.randint(0, 5000),
            reposts=random.randint(0, 2000),
            comments_count=random.randint(0, 500),
            hashtags=hashtags,
        )
