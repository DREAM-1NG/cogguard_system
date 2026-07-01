"""按平台名构造爬虫实例。"""

from __future__ import annotations

from app.config import settings
from app.core.crawler.base import BaseCrawler
from app.core.crawler.mock import MockCrawler
from app.core.crawler.news import NEWS_PLATFORM_ID, NewsExtractCrawler
from app.core.crawler.social import COGGUARD_TO_MEDIA, MediaSocialCrawler


def build_crawler(platform: str) -> BaseCrawler:
    """根据 ``platform`` 返回 Mock / MediaCrawler / News 爬虫。"""
    p = (platform or "").strip()
    if p == "mock_weibo":
        return MockCrawler()
    if p == NEWS_PLATFORM_ID:
        return NewsExtractCrawler()
    if p in COGGUARD_TO_MEDIA:
        return MediaSocialCrawler(p)
    raise ValueError(f"不支持的平台: {platform!r}")


def is_social_platform(platform: str) -> bool:
    return platform in COGGUARD_TO_MEDIA or platform == "mock_weibo"
