"""Mock crawler that generates realistic-looking test data.

Produces posts with coordinated patterns (shared URLs/hashtags in tight
time windows) so that downstream coordination detection has something
meaningful to work with.
"""

import random
import uuid
from datetime import datetime, timedelta, timezone

from app.core.crawler.base import BaseCrawler
from app.models.post import StandardComment, StandardPost

_MOCK_CONTENT_TEMPLATES = [
    "关于{topic}的最新消息，事态正在持续发展中。{url}",
    "刚刚看到一条关于{topic}的报道，大家怎么看？{url}",
    "转发：{topic}引发广泛讨论。详情请看 {url}",
    "{topic}话题持续发酵，多方关注。{url}",
    "网友热议{topic}，各方观点碰撞。{url}",
    "深度分析：{topic}背后的真相 {url}",
    "紧急关注！{topic}有新进展 {url}",
    "有人注意到{topic}了吗？信息来源 {url}",
]

_MOCK_COMMENT_TEMPLATES = [
    "说得对，我也注意到了",
    "这个消息确实值得关注",
    "转发扩散",
    "有没有更多细节？",
    "信息来源可靠吗？",
    "同意楼上的看法",
    "太震惊了",
    "关注后续发展",
]

_MOCK_TOPICS = ["热点事件A", "舆论焦点B", "社会话题C", "国际动态D", "科技新闻E"]
_MOCK_URLS = [
    "https://example.com/article/001",
    "https://example.com/article/002",
    "https://example.com/article/003",
]


class MockCrawler(BaseCrawler):
    platform = "mock_weibo"

    def __init__(self) -> None:
        super().__init__()

    async def search(self, keywords: list[str], max_posts: int = 50) -> list[StandardPost]:
        posts: list[StandardPost] = []
        base_time = datetime.now(timezone.utc) - timedelta(hours=6)
        topic = keywords[0] if keywords else random.choice(_MOCK_TOPICS)

        # Group 1: normal users (scattered timestamps)
        normal_count = max(1, int(max_posts * 0.6))
        for i in range(normal_count):
            offset_minutes = random.randint(0, 360)
            posts.append(self._make_post(
                idx=i,
                topic=topic,
                url=random.choice(_MOCK_URLS + [""]),
                timestamp=base_time + timedelta(minutes=offset_minutes),
                author_prefix="user",
            ))

        # Group 2: coordinated accounts (tight time window, shared URL)
        coordinated_count = max_posts - normal_count
        shared_url = random.choice(_MOCK_URLS)
        coord_base = base_time + timedelta(hours=2)
        for i in range(coordinated_count):
            offset_seconds = random.randint(0, 30)
            posts.append(self._make_post(
                idx=normal_count + i,
                topic=topic,
                url=shared_url,
                timestamp=coord_base + timedelta(seconds=offset_seconds),
                author_prefix="coord_bot",
            ))

        return posts[:max_posts]

    async def fetch_comments(self, post_id: str, max_comments: int = 100) -> list[StandardComment]:
        comments: list[StandardComment] = []
        base_time = datetime.now(timezone.utc) - timedelta(hours=3)
        count = min(max_comments, random.randint(3, 20))
        for i in range(count):
            comments.append(StandardComment(
                platform=self.platform,
                comment_id=f"cmt_{uuid.uuid4().hex[:8]}",
                post_id=post_id,
                content=random.choice(_MOCK_COMMENT_TEMPLATES),
                author_id=f"commenter_{random.randint(1000, 9999)}",
                author_name=f"评论用户{random.randint(1, 500)}",
                timestamp=base_time + timedelta(minutes=i * 5),
                likes=random.randint(0, 100),
            ))
        return comments

    @staticmethod
    def _make_post(idx: int, topic: str, url: str, timestamp: datetime, author_prefix: str) -> StandardPost:
        template = random.choice(_MOCK_CONTENT_TEMPLATES)
        content = template.format(topic=topic, url=url).strip()
        author_id = f"{author_prefix}_{random.randint(1000, 9999)}"
        hashtags = [f"#{topic}#"]
        if url:
            hashtags.append("#热议#")
        return StandardPost(
            platform="mock_weibo",
            post_id=f"post_{uuid.uuid4().hex[:10]}",
            content=content,
            author_id=author_id,
            author_name=f"模拟用户{idx}",
            timestamp=timestamp,
            url=url,
            likes=random.randint(0, 5000),
            reposts=random.randint(0, 2000),
            comments_count=random.randint(0, 500),
            hashtags=hashtags,
        )
