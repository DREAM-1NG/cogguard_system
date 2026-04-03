"""NewsCrawler / news_extractor 封装：按文章 URL 拉取新闻并标准化为帖子。"""

from __future__ import annotations

import asyncio
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx

from app.config import settings
from app.core.crawler.base import BaseCrawler
from app.models.post import StandardComment, StandardPost

# 平台 id 固定为 news，与采集任务中 platform 字段一致
NEWS_PLATFORM_ID = "news"


def _parse_time(s: Any) -> datetime:
    if s is None or s == "":
        return datetime.now(timezone.utc)
    if isinstance(s, datetime):
        return s if s.tzinfo else s.replace(tzinfo=timezone.utc)
    text = str(s).strip()
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return datetime.now(timezone.utc)


def news_data_to_post(data: dict[str, Any], detected: str | None) -> StandardPost:
    """将 NewsExtractor 返回的 ``data`` 字典转为 StandardPost。"""
    meta = data.get("meta_info") or {}
    if not isinstance(meta, dict):
        meta = {}
    title = str(data.get("title", ""))
    texts = data.get("texts") or []
    body = "\n".join(texts) if isinstance(texts, list) and texts else ""
    if not body:
        body = title
    author = str(meta.get("author_name", "") or "")
    nid = str(data.get("news_id", "") or "")
    url = str(data.get("news_url", "") or "")
    return StandardPost(
        platform=NEWS_PLATFORM_ID,
        post_id=nid or url or title[:32],
        content=body or title,
        author_id=author or "unknown",
        author_name=author or "unknown",
        timestamp=_parse_time(meta.get("publish_time")),
        url=url,
        likes=0,
        reposts=0,
        comments_count=0,
        media_urls=list(data.get("images", []) or []),
        hashtags=[],
        raw_data={"news_extractor": data, "detected_platform": detected},
    )


class NewsExtractCrawler(BaseCrawler):
    """按 URL 列表提取新闻（关键词搜索需上游支持；当前仅 URL 模式）。"""

    platform = NEWS_PLATFORM_ID

    def __init__(self) -> None:
        super().__init__()

    def _urls_from(self, keywords: list[str]) -> list[str]:
        urls: list[str] = []
        for p in self.post_ids:
            p = str(p).strip()
            if p.startswith("http://") or p.startswith("https://"):
                urls.append(p)
        if not urls and keywords:
            for k in keywords:
                k = str(k).strip()
                if k.startswith("http://") or k.startswith("https://"):
                    urls.append(k)
        return urls

    def _ensure_backend(self) -> None:
        api = (settings.NEWSCRAWLER_API_BASE or "").strip().rstrip("/")
        root = (settings.NEWSCRAWLER_ROOT or "").strip()
        if not api and (not root or not Path(root).is_dir()):
            raise RuntimeError(
                "未配置 NEWSCRAWLER_API_BASE 或有效的 NEWSCRAWLER_ROOT，无法提取新闻。"
                " 请启动 news_extractor_backend 并设置 API 地址，或设置 NewsCrawler 仓库根目录。"
            )

    async def search(self, keywords: list[str], max_posts: int = 50) -> list[StandardPost]:
        self._ensure_backend()
        urls = self._urls_from(keywords)
        if not urls:
            raise ValueError("新闻采集需要至少一条文章 URL：请填写「链接」字段（post_ids），或在关键词中填入完整 http(s) 链接。")

        urls = urls[: max(1, max_posts)]
        posts: list[StandardPost] = []
        for url in urls:
            if settings.NEWSCRAWLER_API_BASE.strip():
                posts.append(await self._extract_via_http(url))
            else:
                posts.append(await self._extract_via_import(url))
        return posts

    async def _extract_via_http(self, url: str) -> StandardPost:
        base = settings.NEWSCRAWLER_API_BASE.strip().rstrip("/")
        endpoint = f"{base}/api/extract"
        async with httpx.AsyncClient(timeout=120.0) as client:
            r = await client.post(endpoint, json={"url": url, "output_format": "json"})
            r.raise_for_status()
            payload = r.json()
        if payload.get("status") != "success" and not payload.get("data"):
            raise RuntimeError(f"新闻提取失败: {payload}")
        data = payload.get("data") or {}
        plat = payload.get("platform")
        return news_data_to_post(data, plat)

    async def _extract_via_import(self, url: str) -> StandardPost:
        root = Path(settings.NEWSCRAWLER_ROOT).resolve()
        rstr = str(root)
        if rstr not in sys.path:
            sys.path.insert(0, rstr)

        def _sync() -> StandardPost:
            from news_extractor_core.services.extractor import ExtractorService  # type: ignore[import-not-found]

            news_item, plat = ExtractorService.extract_news(url=url, platform=None, cookie=None)
            return news_data_to_post(news_item.to_dict(), plat)

        return await asyncio.to_thread(_sync)

    async def fetch_comments(self, post_id: str, max_comments: int = 100) -> list[StandardComment]:
        return []
