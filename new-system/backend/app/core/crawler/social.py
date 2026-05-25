"""Direct MediaCrawler execution and JSONL ingestion for social platforms."""

from __future__ import annotations

import asyncio
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.config import settings
from app.core.crawler.base import BaseCrawler
from app.core.crawler.mediacrawler_env import (
    build_mediacrawler_env,
    resolve_mediacrawler_runtime_python,
    resolve_python_bin,
    resolve_uv_bin,
)
from app.models.post import StandardComment, StandardPost

# CogGuard platform id -> (MediaCrawler --platform code, data/ subdirectory)
COGGUARD_TO_MEDIA: dict[str, tuple[str, str]] = {
    "weibo": ("wb", "weibo"),
    "douyin": ("dy", "douyin"),
    "xhs": ("xhs", "xhs"),
    "kuaishou": ("ks", "kuaishou"),
    "bilibili": ("bili", "bili"),
    "tieba": ("tieba", "tieba"),
    "zhihu": ("zhihu", "zhihu"),
}

COMMENT_SORT_OPTIONS = {"none", "like_count_desc", "reply_count_desc"}


@dataclass
class MediaCrawlBatch:
    posts: list[StandardPost]
    comments: list[StandardComment]
    output_files: dict[str, str]
    raw_counts: dict[str, int]


def _parse_ts(value: Any) -> datetime:
    if value is None or value == "":
        return datetime.now(timezone.utc)
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    try:
        if isinstance(value, (int, float)):
            timestamp = float(value)
            if timestamp > 10_000_000_000:
                timestamp = timestamp / 1000
            return datetime.fromtimestamp(timestamp, tz=timezone.utc)
        text = str(value).strip()
        if text.isdigit():
            timestamp = float(text)
            if timestamp > 10_000_000_000:
                timestamp = timestamp / 1000
            return datetime.fromtimestamp(timestamp, tz=timezone.utc)
    except (ValueError, OSError):
        pass
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return datetime.now(timezone.utc)


def _first_non_empty(*values: Any) -> Any:
    for value in values:
        if value is None:
            continue
        if isinstance(value, str) and not value.strip():
            continue
        return value
    return None


def _to_int(*values: Any) -> int:
    unit_multiplier = {
        "万": 10_000,
        "w": 10_000,
        "W": 10_000,
        "亿": 100_000_000,
    }
    for value in values:
        if value is None:
            continue
        if isinstance(value, str):
            value = value.strip()
            if not value or value.lower() == "none":
                continue
            value = value.replace(",", "").replace(" ", "")
            multiplier = 1
            if value[-1:] in unit_multiplier:
                multiplier = unit_multiplier[value[-1]]
                value = value[:-1]
            try:
                return int(float(value) * multiplier)
            except (TypeError, ValueError):
                continue
        try:
            return int(float(value))
        except (TypeError, ValueError):
            continue
    return 0


def _normalize_url(value: str) -> str | None:
    text = value.strip()
    if not text:
        return None
    if text.startswith("//"):
        return f"https:{text}"
    if text.startswith(("http://", "https://")):
        return text
    return None


def _split_string_values(value: str) -> list[str]:
    text = value.strip()
    if not text:
        return []
    if text.startswith("[") and text.endswith("]"):
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            parsed = None
        if isinstance(parsed, list):
            return [str(item).strip() for item in parsed if str(item).strip()]
    parts = re.split(r"[\n,;|]+", text)
    return [part.strip() for part in parts if part.strip()]


def _collect_media_urls(target: list[str], value: Any) -> None:
    if value is None:
        return
    if isinstance(value, str):
        for item in _split_string_values(value):
            normalized = _normalize_url(item)
            if normalized:
                target.append(normalized)
        return
    if isinstance(value, dict):
        for key in (
            "url",
            "urls",
            "src",
            "image_url",
            "video_url",
            "cover_url",
            "download_url",
            "origin_url",
            "play_url",
            "url_default",
        ):
            if key in value:
                _collect_media_urls(target, value.get(key))
        return
    if isinstance(value, (list, tuple, set)):
        for item in value:
            _collect_media_urls(target, item)


def _collect_direct_media_url(target: list[str], value: Any) -> None:
    if not isinstance(value, str):
        return
    normalized = _normalize_url(value)
    if normalized:
        target.append(normalized)


def _collect_dict_url(target: list[str], value: Any, key: str = "url") -> None:
    if isinstance(value, dict):
        _collect_direct_media_url(target, value.get(key))


def _collect_weibo_page_info_media_urls(target: list[str], page_info: Any) -> None:
    if not isinstance(page_info, dict):
        return

    _collect_dict_url(target, page_info.get("page_pic"))

    media_info = page_info.get("media_info")
    if isinstance(media_info, dict):
        for key in (
            "stream_url",
            "stream_url_hd",
            "mp4_sd_url",
            "mp4_hd_url",
            "mp4_720p_mp4",
            "mp4_1080p_mp4",
        ):
            _collect_direct_media_url(target, media_info.get(key))

    urls = page_info.get("urls")
    if isinstance(urls, dict):
        for key, value in urls.items():
            key_text = str(key).lower()
            value_text = str(value).lower()
            if "mp4" in key_text or ".mp4" in value_text:
                _collect_direct_media_url(target, value)


def _collect_weibo_pic_media_urls(target: list[str], pics: Any) -> None:
    if not isinstance(pics, list):
        return
    for pic in pics:
        if isinstance(pic, str):
            _collect_direct_media_url(target, pic)
            continue
        if not isinstance(pic, dict):
            continue
        _collect_direct_media_url(target, pic.get("url"))
        _collect_dict_url(target, pic.get("large"))


def _collect_weibo_pic_infos_media_urls(target: list[str], pic_infos: Any) -> None:
    if not isinstance(pic_infos, dict):
        return
    for pic_info in pic_infos.values():
        if not isinstance(pic_info, dict):
            continue
        for key in ("thumbnail", "bmiddle", "large", "original"):
            _collect_dict_url(target, pic_info.get(key))


def _collect_weibo_mix_media_urls(target: list[str], mix_media_info: Any) -> None:
    if isinstance(mix_media_info, dict):
        items = mix_media_info.get("items") or []
    elif isinstance(mix_media_info, list):
        items = mix_media_info
    else:
        return

    for item in items:
        if not isinstance(item, dict):
            continue
        data = item.get("data") if isinstance(item.get("data"), dict) else item
        _collect_weibo_pic_media_urls(target, data.get("pics"))
        _collect_weibo_page_info_media_urls(target, data.get("page_info"))
        for key in ("thumbnail_pic", "bmiddle_pic", "original_pic"):
            _collect_direct_media_url(target, data.get(key))


def _collect_weibo_mblog_media_urls(target: list[str], mblog: Any) -> None:
    if not isinstance(mblog, dict):
        return

    _collect_media_urls(target, mblog.get("media_urls"))
    _collect_weibo_pic_media_urls(target, mblog.get("pics"))
    _collect_weibo_pic_infos_media_urls(target, mblog.get("pic_infos"))
    for key in ("thumbnail_pic", "bmiddle_pic", "original_pic"):
        _collect_direct_media_url(target, mblog.get(key))
    _collect_weibo_page_info_media_urls(target, mblog.get("page_info"))
    _collect_weibo_mix_media_urls(target, mblog.get("mix_media_info"))


def _iter_weibo_mblog_payloads(raw: dict[str, Any]) -> list[dict[str, Any]]:
    payloads: list[dict[str, Any]] = [raw]
    for key in ("mblog", "status"):
        value = raw.get(key)
        if isinstance(value, dict):
            payloads.append(value)

    detail_raw = raw.get("post_details_raw")
    if isinstance(detail_raw, dict):
        for key in ("raw", "mblog", "status"):
            value = detail_raw.get(key)
            if isinstance(value, dict):
                payloads.append(value)
                for nested_key in ("mblog", "status"):
                    nested_value = value.get(nested_key)
                    if isinstance(nested_value, dict):
                        payloads.append(nested_value)

    return payloads


def _unique_preserve_order(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        result.append(item)
    return result


def _extract_media_urls(raw: dict[str, Any]) -> list[str]:
    collected: list[str] = []
    for key in (
        "media_urls",
        "image_list",
        "images",
        "pictures",
        "video_url",
        "video_download_url",
        "note_download_url",
        "music_download_url",
        "cover_url",
        "video_cover_url",
        "play_url",
    ):
        _collect_media_urls(collected, raw.get(key))
    for payload in _iter_weibo_mblog_payloads(raw):
        _collect_weibo_mblog_media_urls(collected, payload)
    return _unique_preserve_order(collected)


def _extract_hashtags(raw: dict[str, Any]) -> list[str]:
    values = _first_non_empty(raw.get("hashtags"), raw.get("tag_list"), raw.get("tags"))
    if values is None:
        return []
    if isinstance(values, (list, tuple, set)):
        return _unique_preserve_order([str(item).strip() for item in values if str(item).strip()])
    if isinstance(values, dict):
        return _unique_preserve_order([str(item).strip() for item in values.values() if str(item).strip()])
    if isinstance(values, str):
        return _unique_preserve_order(_split_string_values(values))
    return []


def _extract_author_profile(raw: dict[str, Any]) -> dict[str, Any] | None:
    profile: dict[str, Any] = {}
    for key in (
        "user_id",
        "nickname",
        "avatar",
        "gender",
        "profile_url",
        "ip_location",
        "sec_uid",
        "short_user_id",
        "user_unique_id",
        "user_signature",
        "desc",
        "follows",
        "fans",
        "interaction",
        "videos_count",
        "tag_list",
        "xsec_token",
    ):
        value = raw.get(key)
        if value is None:
            continue
        if isinstance(value, str):
            value = value.strip()
            if not value:
                continue
        profile[key] = value
    return profile or None


def _normalize_reply_to(value: Any, comment_id: str | None = None) -> str | None:
    if value in (None, "", 0, "0"):
        return None
    text = str(value).strip()
    if not text or text.lower() == "none":
        return None
    if comment_id and text == str(comment_id).strip():
        return None
    return text or None


def _combine_title_desc(raw: dict[str, Any], cogguard_platform: str) -> str:
    if cogguard_platform == "xhs":
        parts: list[str] = []
        for value in (raw.get("title"), raw.get("desc")):
            if value is None:
                continue
            text = str(value).strip()
            if text and text not in parts:
                parts.append(text)
        return "\n".join(parts)
    return str(_first_non_empty(raw.get("content"), raw.get("desc"), raw.get("title")) or "")


def _build_standard_post(
    raw: dict[str, Any],
    cogguard_platform: str,
    *,
    post_id: str,
    content: str,
    url: str,
) -> StandardPost:
    return StandardPost(
        platform=cogguard_platform,
        post_id=post_id or str(hash(json.dumps(raw, sort_keys=True, default=str)))[:16],
        content=content,
        author_id=str(_first_non_empty(raw.get("user_id"), raw.get("uid"), raw.get("author_id")) or ""),
        author_name=str(
            _first_non_empty(
                raw.get("nickname"),
                raw.get("author_name"),
                raw.get("user_name"),
                raw.get("user_nickname"),
                "unknown",
            )
        ),
        timestamp=_parse_ts(
            _first_non_empty(
                raw.get("create_time"),
                raw.get("create_ts"),
                raw.get("time"),
                raw.get("publish_time"),
                raw.get("pub_ts"),
            )
        ),
        url=url,
        likes=_to_int(raw.get("liked_count"), raw.get("digg_count"), raw.get("like_count")),
        reposts=_to_int(raw.get("shared_count"), raw.get("share_count"), raw.get("repost_count")),
        comments_count=_to_int(raw.get("comments_count"), raw.get("comment_count"), raw.get("video_comment")),
        media_urls=_extract_media_urls(raw),
        hashtags=_extract_hashtags(raw),
        author_profile=_extract_author_profile(raw),
        raw_data=raw,
    )


def _build_standard_comment(
    raw: dict[str, Any],
    cogguard_platform: str,
    *,
    comment_id: str,
    post_id: str,
    content: str,
) -> StandardComment:
    return StandardComment(
        platform=cogguard_platform,
        comment_id=comment_id,
        post_id=post_id,
        content=content,
        author_id=str(_first_non_empty(raw.get("user_id"), raw.get("uid"), raw.get("author_id")) or ""),
        author_name=str(
            _first_non_empty(
                raw.get("nickname"),
                raw.get("author_name"),
                raw.get("user_name"),
                raw.get("user_nickname"),
                "unknown",
            )
        ),
        timestamp=_parse_ts(
            _first_non_empty(
                raw.get("create_time"),
                raw.get("time"),
                raw.get("publish_time"),
                raw.get("created_at"),
            )
        ),
        reply_to=_normalize_reply_to(
            _first_non_empty(raw.get("parent_comment_id"), raw.get("reply_to")),
            comment_id,
        ),
        likes=_to_int(raw.get("comment_like_count"), raw.get("like_count"), raw.get("liked_count")),
        media_urls=_extract_media_urls(raw),
        sub_comment_count=_to_int(raw.get("sub_comment_count")),
        author_profile=_extract_author_profile(raw),
        raw_data=raw,
    )


def weibo_content_line_to_post(raw: dict[str, Any], cogguard_platform: str) -> StandardPost:
    """Convert a Weibo ``search_contents_*.jsonl`` row."""
    return _build_standard_post(
        raw,
        cogguard_platform,
        post_id=str(raw.get("note_id", "")),
        content=str(raw.get("content", "")),
        url=str(raw.get("note_url", "")),
    )


def weibo_comment_line_to_comment(raw: dict[str, Any], cogguard_platform: str) -> StandardComment:
    return _build_standard_comment(
        raw,
        cogguard_platform,
        comment_id=str(raw.get("comment_id", "")),
        post_id=str(raw.get("note_id", "")),
        content=str(raw.get("content", "")),
    )


def generic_jsonl_to_post(raw: dict[str, Any], cogguard_platform: str) -> StandardPost:
    """Convert a generic MediaCrawler content row."""
    return _build_standard_post(
        raw,
        cogguard_platform,
        post_id=str(
            _first_non_empty(
                raw.get("note_id"),
                raw.get("aweme_id"),
                raw.get("id"),
                raw.get("video_id"),
                raw.get("content_id"),
            )
            or ""
        ),
        content=_combine_title_desc(raw, cogguard_platform),
        url=str(_first_non_empty(raw.get("note_url"), raw.get("aweme_url"), raw.get("url"), raw.get("share_url")) or ""),
    )


def generic_jsonl_to_comment(raw: dict[str, Any], cogguard_platform: str) -> StandardComment:
    return _build_standard_comment(
        raw,
        cogguard_platform,
        comment_id=str(_first_non_empty(raw.get("comment_id"), raw.get("cid"), raw.get("id")) or ""),
        post_id=str(
            _first_non_empty(
                raw.get("note_id"),
                raw.get("aweme_id"),
                raw.get("video_id"),
                raw.get("post_id"),
                raw.get("content_id"),
            )
            or ""
        ),
        content=str(_first_non_empty(raw.get("content"), raw.get("text")) or ""),
    )


def sort_comments(comments: list[StandardComment], sort_mode: str = "none") -> list[StandardComment]:
    """Return comments sorted for downstream storage/query convenience."""
    if sort_mode == "like_count_desc":
        return sorted(comments, key=lambda comment: (comment.likes, comment.sub_comment_count), reverse=True)
    if sort_mode == "reply_count_desc":
        return sorted(comments, key=lambda comment: (comment.sub_comment_count, comment.likes), reverse=True)
    return comments


class MediaSocialCrawler(BaseCrawler):
    """Run MediaCrawler via CLI and ingest only the current batch delta."""

    def __init__(self, cogguard_platform: str) -> None:
        super().__init__()
        if cogguard_platform not in COGGUARD_TO_MEDIA:
            raise ValueError(f"Unsupported social platform: {cogguard_platform}")
        self.cogguard_platform = cogguard_platform
        self._mc_code, self._data_subdir = COGGUARD_TO_MEDIA[cogguard_platform]
        self.platform = cogguard_platform
        self.last_comments: list[StandardComment] = []
        self.recursive_comments = False
        self.enrich_author_profiles = False
        self.comment_sort = "none"
        self.crawl_metadata: dict[str, Any] = self._build_crawl_metadata()

    def _build_crawl_metadata(
        self,
        *,
        output_files: dict[str, str] | None = None,
        raw_counts: dict[str, int] | None = None,
    ) -> dict[str, Any]:
        metadata: dict[str, Any] = {
            "recursive_comments_requested": self.recursive_comments,
            "recursive_comments_supported": False,
            "effective_comment_depth": 2 if settings.MEDIACRAWLER_GET_SUB_COMMENTS else 1,
            "author_profile_enrichment_requested": self.enrich_author_profiles,
            "author_profile_enrichment_supported": False,
            "author_profile_source": "search_result_payload",
            "comment_sort": self.comment_sort,
            "execution_mode": "direct_mediacrawler_cli",
            "ingestion_mode": "jsonl_delta",
        }
        if output_files:
            metadata["output_files"] = output_files
        if raw_counts:
            metadata["raw_counts"] = raw_counts
        return metadata

    def configure_runtime_options(
        self,
        *,
        recursive_comments: bool = False,
        enrich_author_profiles: bool = False,
        comment_sort: str = "none",
    ) -> None:
        if comment_sort not in COMMENT_SORT_OPTIONS:
            raise ValueError(f"Unsupported comment_sort: {comment_sort!r}")
        self.recursive_comments = recursive_comments
        self.enrich_author_profiles = enrich_author_profiles
        self.comment_sort = comment_sort
        self.crawl_metadata = self._build_crawl_metadata()

    def _build_command(self, runtime_python: str | None, uv_bin: str | None, keywords: list[str]) -> list[str]:
        keyword_arg = ",".join(keyword.strip() for keyword in keywords if keyword.strip())
        if not keyword_arg:
            raise ValueError("At least one non-empty keyword is required for social crawling.")

        login_type = settings.MEDIACRAWLER_LOGIN_TYPE.strip() or "cookie"
        cookies = settings.MEDIACRAWLER_COOKIES or ""

        if runtime_python:
            cmd: list[str] = [runtime_python, "main.py"]
        else:
            if not uv_bin:
                raise RuntimeError(
                    "MediaCrawler runtime is unavailable: missing both project .venv python and uv executable."
                )
            cmd = [uv_bin, "run", "--python", resolve_python_bin(), "main.py"]

        cmd.extend(
            [
                "--platform",
                self._mc_code,
                "--lt",
                login_type,
                "--type",
                "search",
                "--keywords",
                keyword_arg,
                "--get_comment",
                "yes",
                "--get_sub_comment",
                "yes" if settings.MEDIACRAWLER_GET_SUB_COMMENTS else "no",
                "--max_comments_count_singlenotes",
                str(max(1, settings.MEDIACRAWLER_MAX_COMMENTS_PER_POST)),
                "--save_data_option",
                "jsonl",
            ]
        )
        if cookies and login_type == "cookie":
            cmd.extend(["--cookies", cookies])
        return cmd

    def _jsonl_output_path(self, mc_root: Path, item_type: str) -> Path:
        date_part = datetime.now().strftime("%Y-%m-%d")
        return mc_root / "data" / self._data_subdir / "jsonl" / f"search_{item_type}_{date_part}.jsonl"

    def _snapshot_output_offsets(self, mc_root: Path) -> dict[str, int]:
        offsets: dict[str, int] = {}
        for item_type in ("contents", "comments"):
            path = self._jsonl_output_path(mc_root, item_type)
            offsets[item_type] = path.stat().st_size if path.is_file() else 0
        return offsets

    def _read_appended_jsonl_rows(self, path: Path, start_offset: int) -> list[dict[str, Any]]:
        if not path.is_file():
            return []

        file_size = path.stat().st_size
        seek_offset = start_offset if 0 <= start_offset <= file_size else 0
        rows: list[dict[str, Any]] = []
        with path.open("rb") as handle:
            if seek_offset:
                handle.seek(seek_offset)
            for raw_line in handle:
                line = raw_line.decode("utf-8", errors="replace").strip()
                if not line:
                    continue
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
        return rows

    def _normalize_post_rows(self, rows: list[dict[str, Any]], max_posts: int) -> list[StandardPost]:
        posts: list[StandardPost] = []
        for raw in rows:
            post = (
                weibo_content_line_to_post(raw, self.cogguard_platform)
                if self.cogguard_platform == "weibo"
                else generic_jsonl_to_post(raw, self.cogguard_platform)
            )
            posts.append(post)
            if len(posts) >= max_posts:
                break
        return posts

    def _normalize_comment_rows(self, rows: list[dict[str, Any]]) -> list[StandardComment]:
        comments: list[StandardComment] = []
        for raw in rows:
            comment = (
                weibo_comment_line_to_comment(raw, self.cogguard_platform)
                if self.cogguard_platform == "weibo"
                else generic_jsonl_to_comment(raw, self.cogguard_platform)
            )
            comments.append(comment)
        return comments

    async def execute_search_batch(self, keywords: list[str], max_posts: int = 50) -> MediaCrawlBatch:
        self.last_comments = []
        root = (settings.MEDIACRAWLER_ROOT or "").strip()
        if not root or not Path(root).is_dir():
            raise RuntimeError("MEDIACRAWLER_ROOT is not configured or does not point to a valid directory.")

        mc_root = Path(root).resolve()
        main_py = mc_root / "main.py"
        if not main_py.is_file():
            raise RuntimeError(f"MediaCrawler main.py was not found under {mc_root}.")

        runtime_python = resolve_mediacrawler_runtime_python(root)
        uv_bin = resolve_uv_bin()
        cmd = self._build_command(runtime_python, uv_bin, keywords)
        output_offsets = self._snapshot_output_offsets(mc_root)

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            cwd=str(mc_root),
            env=build_mediacrawler_env(),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        if proc.returncode != 0:
            err = (stderr or b"").decode("utf-8", errors="replace")[-4000:]
            out = (stdout or b"").decode("utf-8", errors="replace")[-2000:]
            raise RuntimeError(f"MediaCrawler failed (exit={proc.returncode}): {err or out}")

        content_path = self._jsonl_output_path(mc_root, "contents")
        comment_path = self._jsonl_output_path(mc_root, "comments")
        raw_post_rows = self._read_appended_jsonl_rows(content_path, output_offsets["contents"])
        raw_comment_rows = self._read_appended_jsonl_rows(comment_path, output_offsets["comments"])

        posts = self._normalize_post_rows(raw_post_rows, max_posts)
        self.last_comments = sort_comments(self._normalize_comment_rows(raw_comment_rows), self.comment_sort)
        output_files = {
            "contents": str(content_path),
            "comments": str(comment_path),
        }
        raw_counts = {
            "posts": len(raw_post_rows),
            "comments": len(raw_comment_rows),
        }
        self.crawl_metadata = self._build_crawl_metadata(output_files=output_files, raw_counts=raw_counts)
        return MediaCrawlBatch(
            posts=posts,
            comments=self.last_comments,
            output_files=output_files,
            raw_counts=raw_counts,
        )

    async def search(self, keywords: list[str], max_posts: int = 50) -> list[StandardPost]:
        batch = await self.execute_search_batch(keywords=keywords, max_posts=max_posts)
        return batch.posts

    async def fetch_comments(self, post_id: str, max_comments: int = 100) -> list[StandardComment]:
        """Comments are loaded in bulk during ``search`` and filtered here."""
        return [comment for comment in self.last_comments if comment.post_id == post_id][:max_comments]
