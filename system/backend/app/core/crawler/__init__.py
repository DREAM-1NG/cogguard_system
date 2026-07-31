"""Crawler interfaces and internal runtime adapters."""

from app.core.crawler.base import BaseCrawler
from app.core.crawler.factory import build_crawler
from app.core.crawler.types import CrawlBatch, CrawlRequestOptions

__all__ = [
    "BaseCrawler",
    "CrawlBatch",
    "CrawlRequestOptions",
    "build_crawler",
]
