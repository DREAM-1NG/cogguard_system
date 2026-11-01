from __future__ import annotations

import tempfile
from typing import Optional

from ..models import NewsItem
from ..news_crawler.tencent_news import RequestHeaders, TencentNewsCrawler
from .base import CrawlerAdapter


class TencentAdapter(CrawlerAdapter):
    @property
    def platform_name(self) -> str:
        return "tencent"

    def extract(self, url: str, headers: Optional[RequestHeaders] = None) -> NewsItem:
        crawler = TencentNewsCrawler(
            new_url=url,
            save_path=tempfile.mkdtemp(),
            headers=headers or RequestHeaders(),
        )
        html = crawler.fetch_content()
        return NewsItem(crawler.parse_content(html).model_dump())
