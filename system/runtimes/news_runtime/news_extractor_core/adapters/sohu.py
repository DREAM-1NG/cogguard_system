from __future__ import annotations

import tempfile

from ..models import NewsItem
from ..news_crawler.sohu_news import SohuNewsCrawler, RequestHeaders
from .base import CrawlerAdapter


class SohuAdapter(CrawlerAdapter):
    @property
    def platform_name(self) -> str:
        return "sohu"

    def extract(self, url: str) -> NewsItem:
        crawler = SohuNewsCrawler(url, save_path=tempfile.mkdtemp(), headers=RequestHeaders())
        html = crawler.fetch_content()
        return NewsItem(crawler.parse_content(html).model_dump())
