"""Runtime adapter for the internal news extraction seam."""

from __future__ import annotations

import asyncio
import importlib
import importlib.util
import sys
from pathlib import Path
from types import ModuleType

from app.config import PROJECT_ROOT
from app.core.crawler.base import BaseCrawler
from app.core.crawler.news.normalizers import NEWS_PLATFORM_ID, news_data_to_post
from app.core.crawler.types import CrawlBatch, CrawlRequestOptions


def resolve_news_runtime_root() -> Path:
    return (PROJECT_ROOT / "runtimes" / "news_runtime").resolve()


def load_news_runtime_package(runtime_root: Path) -> ModuleType:
    package_name = "cogguard_news_runtime_core"
    if package_name in sys.modules:
        return sys.modules[package_name]

    init_path = runtime_root / "news_extractor_core" / "__init__.py"
    spec = importlib.util.spec_from_file_location(
        package_name,
        init_path,
        submodule_search_locations=[str(init_path.parent)],
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load news runtime package from {init_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[package_name] = module
    spec.loader.exec_module(module)
    return module


class NewsExtractCrawler(BaseCrawler):
    platform = NEWS_PLATFORM_ID

    def _urls_from(self, request: CrawlRequestOptions) -> list[str]:
        urls: list[str] = []
        for value in request.post_ids:
            text = str(value).strip()
            if text.startswith(("http://", "https://")):
                urls.append(text)
        if not urls:
            for value in request.keywords:
                text = str(value).strip()
                if text.startswith(("http://", "https://")):
                    urls.append(text)
        return urls

    def _ensure_runtime(self) -> Path:
        runtime_root = resolve_news_runtime_root()
        if not runtime_root.is_dir():
            raise RuntimeError("Internal news runtime is not available.")
        core_root = runtime_root / "news_extractor_core"
        if not core_root.is_dir():
            raise RuntimeError(f"Internal news runtime core was not found under {runtime_root}.")
        return runtime_root

    async def _extract_via_import(self, runtime_root: Path, url: str):
        def _sync():
            package = load_news_runtime_package(runtime_root)
            extractor_module = importlib.import_module(f"{package.__name__}.services.extractor")
            extractor_service = getattr(extractor_module, "ExtractorService")

            news_item, platform = extractor_service.extract_news(url=url, platform=None, cookie=None)
            return news_data_to_post(news_item.to_dict(), platform)

        return await asyncio.to_thread(_sync)

    async def collect(self, request: CrawlRequestOptions) -> CrawlBatch:
        runtime_root = self._ensure_runtime()
        urls = self._urls_from(request)
        if not urls:
            raise ValueError("News crawling requires at least one article URL in post_ids or keywords.")

        posts = []
        for url in urls[: max(1, request.max_posts)]:
            posts.append(await self._extract_via_import(runtime_root, url))

        batch = CrawlBatch(
            posts=posts,
            comments=[],
            crawl_metadata={
                "execution_mode": "internal_news_runtime_import",
                "runtime_root": str(runtime_root),
                "resolved_urls": urls[: max(1, request.max_posts)],
            },
        )
        return self._remember_batch(batch)
