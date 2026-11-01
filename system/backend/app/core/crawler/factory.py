from __future__ import annotations

from app.core.crawler.base import BaseCrawler
from app.core.crawler.mock import MockCrawler
from app.core.crawler.news import NEWS_PLATFORM_ID, NewsExtractCrawler
from app.core.crawler.social import MediaSocialCrawler, SUPPORTED_SOCIAL_PLATFORMS


def build_crawler(platform: str) -> BaseCrawler:
    p = (platform or "").strip()
    if p == "mock_weibo":
        return MockCrawler()
    if p == NEWS_PLATFORM_ID:
        return NewsExtractCrawler()
    if p in SUPPORTED_SOCIAL_PLATFORMS:
        return MediaSocialCrawler(p)
    raise ValueError(f"Unsupported platform: {platform!r}")
