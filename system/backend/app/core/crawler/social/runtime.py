"""Runtime adapter for the internal social crawler seam."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from app.core.crawler.base import BaseCrawler
from app.core.crawler.mediacrawler_env import (
    build_mediacrawler_env,
    resolve_mediacrawler_runtime_python,
    resolve_python_bin,
    resolve_social_runtime_root,
    resolve_uv_bin,
)
from app.core.crawler.social.metadata import build_social_crawl_metadata
from app.core.crawler.social.normalizers import (
    COMMENT_SORT_OPTIONS,
    generic_jsonl_to_comment,
    generic_jsonl_to_post,
    read_appended_jsonl_rows,
    sort_comments,
    weibo_comment_line_to_comment,
    weibo_content_line_to_post,
)
from app.core.crawler.types import CrawlBatch, CrawlRequestOptions
from app.models.post import StandardComment, StandardPost

SUPPORTED_SOCIAL_PLATFORMS = {"weibo", "douyin", "xhs"}
COGGUARD_TO_MEDIA: dict[str, tuple[str, str]] = {
    "weibo": ("wb", "weibo"),
    "douyin": ("dy", "douyin"),
    "xhs": ("xhs", "xhs"),
}


class MediaSocialCrawler(BaseCrawler):
    """Collect posts and comments via the vendored social runtime."""

    def __init__(self, platform: str) -> None:
        super().__init__()
        if platform not in SUPPORTED_SOCIAL_PLATFORMS:
            raise ValueError(f"Unsupported social platform: {platform}")
        from app.config import settings

        self.platform = platform
        self._runtime_code, self._data_subdir = COGGUARD_TO_MEDIA[platform]
        self.last_comments: list[StandardComment] = []
        self.crawl_comments = True
        self.recursive_comments = False
        self.enrich_author_profiles = False
        self.comment_sort = "none"
        self.max_comments_per_post = max(1, settings.MEDIACRAWLER_MAX_COMMENTS_PER_POST)
        self.crawl_metadata = build_social_crawl_metadata(
            crawl_comments=True,
            recursive_comments=self.recursive_comments,
            enrich_author_profiles=self.enrich_author_profiles,
            comment_sort=self.comment_sort,
            max_comments_per_post=self.max_comments_per_post,
        )

    def _configure_runtime_options(
        self,
        *,
        crawl_comments: bool = True,
        recursive_comments: bool = False,
        enrich_author_profiles: bool = False,
        comment_sort: str = "none",
        max_comments_per_post: int | None = None,
    ) -> None:
        if comment_sort not in COMMENT_SORT_OPTIONS:
            raise ValueError(f"Unsupported comment_sort: {comment_sort!r}")
        self.crawl_comments = crawl_comments
        self.recursive_comments = recursive_comments
        self.enrich_author_profiles = enrich_author_profiles
        self.comment_sort = comment_sort
        if max_comments_per_post is not None and max_comments_per_post > 0:
            self.max_comments_per_post = max_comments_per_post
        self.crawl_metadata = build_social_crawl_metadata(
            crawl_comments=crawl_comments,
            recursive_comments=self.recursive_comments,
            enrich_author_profiles=self.enrich_author_profiles,
            comment_sort=self.comment_sort,
            max_comments_per_post=self.max_comments_per_post,
        )

    def _build_command(self, runtime_python: str | None, uv_bin: str | None, keywords: list[str]) -> list[str]:
        keyword_arg = ",".join(keyword.strip() for keyword in keywords if keyword.strip())
        if not keyword_arg:
            raise ValueError("At least one non-empty keyword is required for social crawling.")

        if runtime_python:
            cmd: list[str] = [runtime_python, "main.py"]
        else:
            if not uv_bin:
                raise RuntimeError("Social runtime is unavailable: missing both project .venv python and uv.")
            cmd = [uv_bin, "run", "--python", resolve_python_bin(), "main.py"]

        from app.config import settings

        login_type = settings.MEDIACRAWLER_LOGIN_TYPE.strip() or "cookie"
        cookies = settings.MEDIACRAWLER_COOKIES or ""
        cmd.extend(
            [
                "--platform",
                self._runtime_code,
                "--lt",
                login_type,
                "--type",
                "search",
                "--keywords",
                keyword_arg,
                "--get_comment",
                "yes" if self.crawl_comments else "no",
                "--get_sub_comment",
                "yes" if self.crawl_comments and self.recursive_comments else "no",
                "--max_comments_count_singlenotes",
                str(max(1, self.max_comments_per_post)),
                "--save_data_option",
                "jsonl",
            ]
        )
        if cookies and login_type == "cookie":
            cmd.extend(["--cookies", cookies])
        return cmd

    def _jsonl_output_path(self, runtime_root: Path, item_type: str) -> Path:
        from datetime import datetime

        date_part = datetime.now().strftime("%Y-%m-%d")
        return runtime_root / "data" / self._data_subdir / "jsonl" / f"search_{item_type}_{date_part}.jsonl"

    def _snapshot_output_offsets(self, runtime_root: Path) -> dict[str, int]:
        offsets: dict[str, int] = {}
        for item_type in ("contents", "comments"):
            path = self._jsonl_output_path(runtime_root, item_type)
            offsets[item_type] = path.stat().st_size if path.is_file() else 0
        return offsets

    def _read_appended_jsonl_rows(self, path: Path, start_offset: int) -> list[dict[str, Any]]:
        return read_appended_jsonl_rows(path, start_offset)

    def _normalize_post_rows(self, rows: list[dict[str, Any]], max_posts: int) -> list[StandardPost]:
        posts: list[StandardPost] = []
        for raw in rows:
            post = (
                weibo_content_line_to_post(raw, self.platform)
                if self.platform == "weibo"
                else generic_jsonl_to_post(raw, self.platform)
            )
            posts.append(post)
            if len(posts) >= max_posts:
                break
        return posts

    def _normalize_comment_rows(self, rows: list[dict[str, Any]]) -> list[StandardComment]:
        comments: list[StandardComment] = []
        for raw in rows:
            comment = (
                weibo_comment_line_to_comment(raw, self.platform)
                if self.platform == "weibo"
                else generic_jsonl_to_comment(raw, self.platform)
            )
            comments.append(comment)
        return comments

    async def collect(self, request: CrawlRequestOptions) -> CrawlBatch:
        self.last_comments = []
        self._configure_runtime_options(
            crawl_comments=request.crawl_comments,
            recursive_comments=request.recursive_comments,
            enrich_author_profiles=request.enrich_author_profiles,
            comment_sort=request.comment_sort,
            max_comments_per_post=request.max_comments_per_post,
        )

        runtime_root = resolve_social_runtime_root()
        main_py = runtime_root / "main.py"
        if not main_py.is_file():
            raise RuntimeError(f"Internal social runtime entrypoint was not found under {runtime_root}.")

        runtime_python = resolve_mediacrawler_runtime_python(runtime_root)
        uv_bin = resolve_uv_bin()
        cmd = self._build_command(runtime_python, uv_bin, request.keywords)
        output_offsets = self._snapshot_output_offsets(runtime_root)

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            cwd=str(runtime_root),
            env=build_mediacrawler_env(),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        if proc.returncode != 0:
            err = (stderr or b"").decode("utf-8", errors="replace")[-4000:]
            out = (stdout or b"").decode("utf-8", errors="replace")[-2000:]
            raise RuntimeError(f"Social runtime failed (exit={proc.returncode}): {err or out}")

        content_path = self._jsonl_output_path(runtime_root, "contents")
        comment_path = self._jsonl_output_path(runtime_root, "comments")
        raw_post_rows = read_appended_jsonl_rows(content_path, output_offsets["contents"])
        raw_comment_rows = read_appended_jsonl_rows(comment_path, output_offsets["comments"])

        posts = self._normalize_post_rows(raw_post_rows, request.max_posts)
        comments = (
            sort_comments(self._normalize_comment_rows(raw_comment_rows), self.comment_sort)
            if request.crawl_comments
            else []
        )
        self.last_comments = comments
        output_files = {
            "contents": str(content_path),
            "comments": str(comment_path),
        }
        raw_counts = {
            "posts": len(raw_post_rows),
            "comments": len(raw_comment_rows),
        }
        batch = CrawlBatch(
            posts=posts,
            comments=comments,
            crawl_metadata=build_social_crawl_metadata(
                crawl_comments=request.crawl_comments,
                recursive_comments=self.recursive_comments,
                enrich_author_profiles=self.enrich_author_profiles,
                comment_sort=self.comment_sort,
                max_comments_per_post=self.max_comments_per_post,
                output_files=output_files,
                raw_counts=raw_counts,
            ),
        )
        return self._remember_batch(batch)
