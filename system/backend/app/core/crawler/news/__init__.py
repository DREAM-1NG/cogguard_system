"""News crawler module with internal runtime import seam."""

from app.core.crawler.news.normalizers import NEWS_PLATFORM_ID, news_data_to_post, parse_time
from app.core.crawler.news.runtime import NewsExtractCrawler, resolve_news_runtime_root

__all__ = [
    "NEWS_PLATFORM_ID",
    "NewsExtractCrawler",
    "news_data_to_post",
    "parse_time",
    "resolve_news_runtime_root",
]
