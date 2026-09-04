"""Crawler acquisition and normalization package.

This package owns crawler interfaces, social and news adapters, mock fixtures,
factory wiring, runtime environment helpers, and normalized record conversion.
"""

from app.core.crawler.base import BaseCrawler
from app.core.crawler.factory import build_crawler
from app.core.crawler.types import CrawlBatch, CrawlRequestOptions

__all__ = [
    "BaseCrawler",
    "CrawlBatch",
    "CrawlRequestOptions",
    "base",
    "build_crawler",
    "factory",
    "mediacrawler_env",
    "mock",
    "news",
    "social",
    "types",
]
