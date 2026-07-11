from __future__ import annotations

from abc import ABC, abstractmethod

from app.core.crawler.types import CrawlBatch, CrawlRequestOptions


class BaseCrawler(ABC):
    """Small interface for crawler adapters."""

    platform: str = ""

    def __init__(self) -> None:
        self.post_ids: list[str] = []
        self.crawl_metadata: dict[str, object] = {}
        self._last_batch = CrawlBatch()

    @abstractmethod
    async def collect(self, request: CrawlRequestOptions) -> CrawlBatch:
        """Collect posts and optional comments through one seam."""

    async def search(self, keywords: list[str], max_posts: int = 50):
        batch = await self.collect(
            CrawlRequestOptions(
                keywords=list(keywords),
                post_ids=list(self.post_ids),
                max_posts=max_posts,
                crawl_comments=True,
            )
        )
        return batch.posts

    async def fetch_comments(self, post_id: str, max_comments: int = 100):
        return [comment for comment in self._last_batch.comments if comment.post_id == post_id][:max_comments]

    def _remember_batch(self, batch: CrawlBatch) -> CrawlBatch:
        self._last_batch = batch
        self.crawl_metadata = dict(batch.crawl_metadata)
        return batch
