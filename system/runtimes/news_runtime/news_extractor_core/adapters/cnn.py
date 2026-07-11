from __future__ import annotations

import tempfile

from ..models import NewsItem
from ..news_crawler.cnn_news import CNNNewsCrawler, RequestHeaders
from .base import CrawlerAdapter


class CNNAdapter(CrawlerAdapter):
    @property
    def platform_name(self) -> str:
        return "cnn"

    def extract(self, url: str) -> NewsItem:
        crawler = CNNNewsCrawler(url, save_path=tempfile.mkdtemp(), headers=RequestHeaders())
        html = crawler.fetch_content()
        return NewsItem(crawler.parse_content(html).model_dump())
