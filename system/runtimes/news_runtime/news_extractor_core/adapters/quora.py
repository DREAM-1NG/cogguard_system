from __future__ import annotations

import tempfile

from ..models import NewsItem
from ..news_crawler.quora import QuoraAnswerCrawler, RequestHeaders
from .base import CrawlerAdapter


class QuoraAdapter(CrawlerAdapter):
    @property
    def platform_name(self) -> str:
        return "quora"

    def extract(self, url: str) -> NewsItem:
        crawler = QuoraAnswerCrawler(url, save_path=tempfile.mkdtemp(), headers=RequestHeaders())
        html = crawler.fetch_content()
        return NewsItem(crawler.parse_content(html).model_dump())
