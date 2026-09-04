from __future__ import annotations

import tempfile

from ..models import NewsItem
from ..news_crawler.toutiao_news import RequestHeaders, ToutiaoNewsCrawler
from .base import CrawlerAdapter


class ToutiaoAdapter(CrawlerAdapter):
    @property
    def platform_name(self) -> str:
        return "toutiao"

    def extract(self, url: str) -> NewsItem:
        crawler = ToutiaoNewsCrawler(url, save_path=tempfile.mkdtemp(), headers=RequestHeaders())
        html = crawler.fetch_content()
        return NewsItem(crawler.parse_content(html).model_dump())
