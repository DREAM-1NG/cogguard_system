from __future__ import annotations

import tempfile

from ..models import NewsItem
from ..news_crawler.wechat_news import RequestHeaders, WeChatNewsCrawler
from .base import CrawlerAdapter


class WeChatAdapter(CrawlerAdapter):
    @property
    def platform_name(self) -> str:
        return "wechat"

    def extract(self, url: str) -> NewsItem:
        crawler = WeChatNewsCrawler(url, save_path=tempfile.mkdtemp(), headers=RequestHeaders())
        html = crawler.fetch_content()
        return NewsItem(crawler.parse_content(html).model_dump())
