from __future__ import annotations

import tempfile

from ..models import NewsItem
from ..news_crawler.bbc_news import BBCNewsCrawler, RequestHeaders
from .base import CrawlerAdapter


class BBCAdapter(CrawlerAdapter):
    @property
    def platform_name(self) -> str:
        return "bbc"

    def extract(self, url: str) -> NewsItem:
        crawler = BBCNewsCrawler(url, save_path=tempfile.mkdtemp(), headers=RequestHeaders())
        html = crawler.fetch_content()
        return NewsItem(crawler.parse_content(html).model_dump())
