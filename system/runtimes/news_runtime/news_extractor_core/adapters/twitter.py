from __future__ import annotations

import logging
import tempfile
from typing import Optional

from ..models import NewsItem
from .base import CrawlerAdapter

logger = logging.getLogger(__name__)


class TwitterAdapter(CrawlerAdapter):
    @property
    def platform_name(self) -> str:
        return "twitter"

    def extract(self, url: str, cookie: Optional[str] = None) -> NewsItem:
        from ..news_crawler.twitter_news import TwitterCredentials, TwitterNewsCrawler

        credentials = None
        if cookie:
            try:
                credentials = TwitterCredentials.from_cookie_string(cookie)
            except ValueError as exc:
                logger.warning("Twitter cookie parsing failed; using guest mode: %s", exc)
        else:
            credentials = TwitterCredentials.from_env()

        crawler = TwitterNewsCrawler(
            url,
            save_path=tempfile.mkdtemp(),
            credentials=credentials,
        )
        crawler.fetch_content()
        return NewsItem(crawler.parse_content("").model_dump())
