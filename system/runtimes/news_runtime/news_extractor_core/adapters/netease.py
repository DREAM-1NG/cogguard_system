from __future__ import annotations

import tempfile

from ..models import NewsItem
from ..news_crawler.netease_news import NeteaseNewsCrawler, RequestHeaders
from .base import CrawlerAdapter


class NeteaseAdapter(CrawlerAdapter):
    @property
    def platform_name(self) -> str:
        return "netease"

    def extract(self, url: str) -> NewsItem:
        crawler = NeteaseNewsCrawler(url, save_path=tempfile.mkdtemp(), headers=RequestHeaders())
        html = crawler.fetch_content()
        return NewsItem(crawler.parse_content(html).model_dump())
