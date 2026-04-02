# -*- coding: utf-8 -*-
"""
Twitter/X 推文内容提取爬虫

使用 X 内部 GraphQL API 获取推文详情。
支持两种模式:
1. Guest Token 模式 (默认): 无需认证，可访问公开推文
2. Cookie 认证模式: 需要登录 Cookie，可访问受保护推文
"""
import logging
import os
import re
from datetime import datetime
from typing import List, Optional

from pydantic import Field

from news_crawler.core import (
    BaseNewsCrawler,
    ContentItem,
    ContentType,
    NewsItem,
    NewsMetaInfo,
    RequestHeaders as BaseRequestHeaders,
)
from news_crawler.core.fetchers import FetchRequest, FetchStrategy

from .twitter_client import (
    TwitterClient,
    TwitterCredentials,
    extract_tweet_id,
)
from .twitter_types import TweetData, TweetMedia

logger = logging.getLogger(__name__)


class TwitterRequestHeaders(BaseRequestHeaders):
    """Twitter 请求头 (实际未使用，因为使用 API 客户端)"""
    user_agent: str = Field(
        default="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        alias="User-Agent",
    )


class TwitterApiFetcher(FetchStrategy):
    """Twitter API 数据获取策略"""

    def __init__(self, credentials: Optional[TwitterCredentials] = None):
        self.credentials = credentials
        self.client = TwitterClient(credentials)

    def fetch(self, request: FetchRequest) -> str:
        """获取推文数据 (返回 JSON 字符串形式)"""
        tweet_id = extract_tweet_id(request.url)
        tweet_data = self.client.get_tweet(tweet_id)
        # 返回序列化的推文数据用于后续解析
        import json
        return json.dumps({
            "tweet_id": tweet_id,
            "tweet_data": tweet_data.__dict__ if tweet_data else None,
        })


class TwitterNewsCrawler(BaseNewsCrawler):
    """Twitter/X 推文爬虫实现"""

    headers_model = TwitterRequestHeaders
    fetch_strategy = TwitterApiFetcher
    persist_by_default = True

    def __init__(
        self,
        new_url: str,
        save_path: str = "data/",
        headers: Optional[TwitterRequestHeaders] = None,
        fetcher: Optional[FetchStrategy] = None,
        cookie: Optional[str] = None,
        credentials: Optional[TwitterCredentials] = None,
    ):
        # 处理认证 (可选，用于访问受保护推文)
        if credentials:
            self._credentials = credentials
        elif cookie:
            try:
                self._credentials = TwitterCredentials.from_cookie_string(cookie)
            except ValueError:
                logger.warning("Cookie 解析失败，将使用 Guest Token 模式")
                self._credentials = None
        else:
            # 尝试从环境变量获取 (可选)
            self._credentials = TwitterCredentials.from_env()

        if self._credentials:
            logger.info("使用 Cookie 认证模式")
        else:
            logger.info("使用 Guest Token 模式 (仅可访问公开推文)")

        # 创建自定义 fetcher
        if fetcher is None:
            fetcher = TwitterApiFetcher(self._credentials)

        super().__init__(new_url, save_path, headers=headers, fetcher=fetcher)

        # 缓存推文数据
        self._tweet_data: Optional[TweetData] = None

    def create_fetcher(self) -> FetchStrategy:
        """创建 Twitter API 获取器"""
        return TwitterApiFetcher(self._credentials)

    def get_article_id(self) -> str:
        """获取推文 ID"""
        return extract_tweet_id(self.new_url)

    def fetch_content(self) -> str:
        """获取推文内容"""
        # 直接使用 API 客户端获取数据
        tweet_id = self.get_article_id()
        self.logger.info("Fetching tweet %s", tweet_id)

        client = TwitterClient(self._credentials)
        self._tweet_data = client.get_tweet(tweet_id)

        # 返回空字符串，实际数据已缓存
        return ""

    def parse_content(self, html: str) -> NewsItem:
        """解析推文内容"""
        if self._tweet_data is None:
            raise ValueError("推文数据未获取")

        tweet = self._tweet_data
        contents: List[ContentItem] = []

        # 添加主文本
        text = tweet.full_text or tweet.text
        if text:
            # 清理 t.co 链接
            text = self._clean_text(text)
            for paragraph in text.split("\n"):
                paragraph = paragraph.strip()
                if paragraph:
                    contents.append(ContentItem(type=ContentType.TEXT, content=paragraph))

        # 添加媒体
        for media in tweet.media:
            if media.type == "photo":
                contents.append(
                    ContentItem(
                        type=ContentType.IMAGE,
                        content=media.media_url,
                        desc=media.alt_text,
                    )
                )
            elif media.type in ("video", "animated_gif"):
                if media.video_url:
                    contents.append(
                        ContentItem(
                            type=ContentType.VIDEO,
                            content=media.video_url,
                            desc=f"{media.type}: {media.width}x{media.height}",
                        )
                    )

        # 处理引用推文
        if tweet.quoted_tweet:
            quoted = tweet.quoted_tweet
            quoted_author = f"@{quoted.author.screen_name}" if quoted.author.screen_name else "Unknown"
            contents.append(
                ContentItem(
                    type=ContentType.TEXT,
                    content=f"[引用 {quoted_author}]: {self._clean_text(quoted.full_text or quoted.text)}",
                )
            )

        # 构建元信息
        meta_info = NewsMetaInfo(
            author_name=f"{tweet.author.name} (@{tweet.author.screen_name})",
            author_url=f"https://x.com/{tweet.author.screen_name}" if tweet.author.screen_name else "",
            publish_time=self._parse_publish_time(tweet.created_at),
            extra={
                "retweet_count": tweet.retweet_count,
                "like_count": tweet.like_count,
                "reply_count": tweet.reply_count,
                "view_count": tweet.view_count,
            },
        )

        # 构建标题 (使用前 50 个字符或完整文本)
        title_text = tweet.full_text or tweet.text
        title = self._clean_text(title_text)[:100] if title_text else f"Tweet {tweet.id}"

        return self.compose_news_item(
            title=title,
            meta_info=meta_info,
            contents=contents,
            news_id=tweet.id,
        )

    @staticmethod
    def _clean_text(text: str) -> str:
        """清理推文文本，移除 t.co 链接等"""
        if not text:
            return ""
        # 移除 t.co 短链接 (通常在文末)
        text = re.sub(r"\s*https://t\.co/\w+\s*$", "", text)
        # 保留中间的链接但移除 t.co 域名
        text = re.sub(r"https://t\.co/\w+", "", text)
        return text.strip()

    @staticmethod
    def _parse_publish_time(created_at: str) -> str:
        """解析 Twitter 时间格式"""
        if not created_at:
            return ""
        try:
            # Twitter 格式: "Wed Oct 10 20:19:24 +0000 2018"
            dt = datetime.strptime(created_at, "%a %b %d %H:%M:%S %z %Y")
            return dt.strftime("%Y-%m-%d %H:%M:%S")
        except ValueError:
            return created_at


if __name__ == "__main__":
    # 测试用例
    logging.basicConfig(level=logging.INFO)

    # 公开推文测试 (无需认证)
    # Barack Obama 的著名推文
    test_urls = [
        "https://x.com/BarackObama/status/896523232098078720",
    ]

    # 检查是否设置了环境变量 (可选，用于访问受保护推文)
    has_auth = os.environ.get("TWITTER_COOKIE") or (
        os.environ.get("TWITTER_AUTH_TOKEN") and os.environ.get("TWITTER_CT0")
    )

    if has_auth:
        print("检测到认证信息，将使用 Cookie 认证模式")
    else:
        print("未检测到认证信息，将使用 Guest Token 模式 (仅可访问公开推文)")

    for url in test_urls:
        print(f"\n{'='*60}")
        print(f"Testing: {url}")
        print("=" * 60)

        try:
            crawler = TwitterNewsCrawler(url, save_path="data/")
            result = crawler.run()
            print(f"Title: {result.title}")
            print(f"Author: {result.meta_info.author_name}")
            print(f"Published: {result.meta_info.publish_time}")
            print(f"Texts: {len(result.texts)} paragraphs")
            print(f"Images: {len(result.images)}")
            print(f"Videos: {len(result.videos)}")
            print("\nContent:")
            for text in result.texts[:3]:  # 只显示前3段
                print(f"  - {text[:100]}...")
        except Exception as e:
            import traceback
            print(f"Error: {e}")
            traceback.print_exc()
