from __future__ import annotations

import tempfile

from ..models import NewsItem
from ..news_crawler.naver_news import NaverNewsCrawler, RequestHeaders
from .base import CrawlerAdapter


class NaverAdapter(CrawlerAdapter):
    @property
    def platform_name(self) -> str:
        return "naver"

    def extract(self, url: str) -> NewsItem:
        crawler = NaverNewsCrawler(url, save_path=tempfile.mkdtemp(), headers=RequestHeaders())
        html = crawler.fetch_content()
        return NewsItem(crawler.parse_content(html).model_dump())
