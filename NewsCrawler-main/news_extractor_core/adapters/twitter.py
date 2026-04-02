# -*- coding: utf-8 -*-
"""
Twitter/X 推文爬虫适配器

支持两种模式:
1. Guest Token 模式 (默认): 无需认证，可访问公开推文
2. Cookie 认证模式: 需要登录 Cookie，可访问受保护推文
"""
import logging
import tempfile
from typing import Optional

from .base import CrawlerAdapter
from ..models import NewsItem

logger = logging.getLogger(__name__)


class TwitterAdapter(CrawlerAdapter):
    """Twitter/X 适配器"""

    @property
    def platform_name(self) -> str:
        return "twitter"

    def extract(self, url: str, cookie: Optional[str] = None) -> NewsItem:
        """
        提取 Twitter/X 推文内容

        Args:
            url: 推文链接
            cookie: 可选的 Cookie 字符串。如果不提供:
                   - 先尝试从环境变量获取 (TWITTER_COOKIE 或 TWITTER_AUTH_TOKEN + TWITTER_CT0)
                   - 如果环境变量也没有，则使用 Guest Token 模式 (仅可访问公开推文)

        Returns:
            NewsItem: 提取的推文数据
        """
        from news_crawler.twitter_news import TwitterNewsCrawler, TwitterCredentials

        # 处理认证 (可选)
        credentials = None
        if cookie:
            try:
                credentials = TwitterCredentials.from_cookie_string(cookie)
                logger.info("使用提供的 Cookie 认证")
            except ValueError as e:
                logger.warning(f"Cookie 解析失败: {e}，将使用 Guest Token 模式")
        else:
            # 尝试从环境变量获取 (可选)
            credentials = TwitterCredentials.from_env()
            if credentials:
                logger.info("使用环境变量中的 Cookie 认证")
            else:
                logger.info("使用 Guest Token 模式 (仅可访问公开推文)")

        # 创建临时目录
        temp_dir = tempfile.mkdtemp()

        # 创建爬虫实例 (credentials 可以为 None)
        crawler = TwitterNewsCrawler(
            url,
            save_path=temp_dir,
            credentials=credentials,
        )

        # 获取数据
        crawler.fetch_content()
        news_item = crawler.parse_content("")

        # 转换为统一格式
        return NewsItem(news_item.model_dump())
