"""Download crawled social media assets with existing browser profiles.

This is an operator utility for recovering media that normal HTTP downloaders
cannot fetch because the platform requires page context, referer, or login
cookies. It never writes cookies or request headers to disk.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import re
import time
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from playwright.async_api import BrowserContext, Page, Response, async_playwright


DEFAULT_SOURCE_MANIFEST = Path(
    r"G:\CISCN\CogGuard\.worktrees\refactor-system\system\output\media_downloads"
    r"\platform_allowlist_expanded\all\20260812_222420\manifest.json"
)
DEFAULT_PROFILE_ROOT = Path(r"G:\CISCN\CogGuard\MediaCrawler-main\browser_data")
DEFAULT_CHROME = Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe")
DEFAULT_OUTPUT_ROOT = Path(
    r"G:\CISCN\CogGuard\.worktrees\refactor-system\system\output\media_downloads"
    r"\browser_identity_retry"
)

PLATFORM_PROFILES = {
    "xhs": "cdp_xhs_user_data_dir",
    "weibo": "cdp_wb_user_data_dir",
    "douyin": "cdp_dy_user_data_dir",
}

PLATFORM_HOST_HINTS = {
    "xhs": (
        "sns-webpic",
        "sns-img",
        "sns-video",
    ),
    "weibo": (
        "f.video.weibocdn.com",
        "us.sinaimg.cn",
        "weibo.com/tv/api/component",
        "weibo.com/ajax/statuses/show",
        "m.weibo.cn/statuses/show",
        "m.weibo.cn/statuses/extend",
    ),
    "douyin": (
        "douyinvod.com",
        "douyinpic.com",
        "douyinstatic.com",
        "smtcdns.com",
        "bsgslb.cn",
        "bdcgslb.com",
        "amemv.com",
    ),
}

POST_WAIT_SECONDS = {
    "xhs": 8.0,
    "weibo": 7.0,
    "douyin": 9.0,
}


@dataclass(frozen=True)
class DownloadCase:
    platform: str
    post_id: str
    post_url: str
    source_urls: tuple[str, ...]
    requested_media_types: tuple[str, ...]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-manifest", type=Path, default=DEFAULT_SOURCE_MANIFEST)
    parser.add_argument("--profile-root", type=Path, default=DEFAULT_PROFILE_ROOT)
    parser.add_argument("--chrome", type=Path, default=DEFAULT_CHROME)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--platform", choices=["all", "xhs", "weibo", "douyin"], default="all")
    parser.add_argument("--max-cases", type=int, default=20)
    parser.add_argument("--post-timeout-ms", type=int, default=45_000)
    parser.add_argument("--max-images-per-post", type=int, default=6)
    parser.add_argument("--max-videos-per-post", type=int, default=1)
    parser.add_argument("--max-image-mb", type=int, default=30)
    parser.add_argument("--max-video-mb", type=int, default=260)
    parser.add_argument("--min-image-bytes", type=int, default=2_000)
    parser.add_argument("--min-video-bytes", type=int, default=50_000)
    parser.add_argument("--headed", action="store_true")
    parser.add_argument("--skip-page", action="store_true")
    parser.add_argument("--skip-direct-retry", action="store_true")
    return parser.parse_args()


def sanitize(value: Any, fallback: str = "unknown") -> str:
    text = str(value or "").strip() or fallback
    text = re.sub(r"[^\w.-]+", "_", text, flags=re.UNICODE).strip("._")
    return (text or fallback)[:96]


def suffix_for(content_type: str | None, url: str) -> str:
    lowered = (content_type or "").lower()
    if "mp4" in lowered:
        return ".mp4"
    if "mpegurl" in lowered or "m3u8" in lowered:
        return ".m3u8"
    if "jpeg" in lowered or "jpg" in lowered:
        return ".jpg"
    if "png" in lowered:
        return ".png"
    if "webp" in lowered:
        return ".webp"
    if "gif" in lowered:
        return ".gif"
    suffix = Path(urlparse(url).path).suffix.lower()
    if suffix in {".mp4", ".m3u8", ".jpg", ".jpeg", ".png", ".webp", ".gif"}:
        return suffix
    return ".bin"


def media_kind(content_type: str | None, url: str) -> str | None:
    lowered = (content_type or "").lower()
    path = urlparse(url).path.lower()
    if lowered.startswith("video/") or path.endswith(".mp4") or ".mp4?" in url.lower():
        return "video"
    if lowered.startswith("image/") or any(
        path.endswith(suffix) for suffix in (".jpg", ".jpeg", ".png", ".webp", ".gif")
    ):
        return "image"
    if "mime_type=video" in url.lower() or "/aweme/v1/play/" in url.lower():
        return "video"
    return None


def looks_like_platform_media(platform: str, url: str, content_type: str | None) -> bool:
    parsed = urlparse(url)
    host_and_path = f"{parsed.hostname or ''}{parsed.path}".lower()
    if not any(hint in host_and_path for hint in PLATFORM_HOST_HINTS[platform]):
        return False
    kind = media_kind(content_type, url)
    if not kind:
        return False
    if platform == "weibo":
        return kind == "video"
    if platform == "douyin":
        return kind == "video" or "douyinpic.com" in host_and_path
    return True


def find_media_urls(value: Any) -> list[str]:
    urls: list[str] = []
    if isinstance(value, dict):
        for item in value.values():
            urls.extend(find_media_urls(item))
    elif isinstance(value, list):
        for item in value:
            urls.extend(find_media_urls(item))
    elif isinstance(value, str):
        if "http" not in value:
            return urls
        for match in re.findall(r"https?://[^\\\"'<>\\s]+", value):
            cleaned = match.replace("\\/", "/").rstrip(").,;")
            if re.search(r"\.(mp4|m3u8)(\?|$)", cleaned, flags=re.IGNORECASE):
                urls.append(cleaned)
    return list(dict.fromkeys(urls))


def find_weibo_video_urls(payload: Any) -> list[str]:
    """Extract full video URLs from known Weibo detail JSON fields first."""
    root = payload.get("data", payload) if isinstance(payload, dict) else payload
    candidates: list[str] = []
    if isinstance(root, dict):
        page_info = root.get("page_info")
        if isinstance(page_info, dict):
            media_info = page_info.get("media_info")
            if isinstance(media_info, dict):
                for key in ("stream_url_hd", "stream_url", "h5_url"):
                    value = media_info.get(key)
                    if isinstance(value, str):
                        candidates.append(value)
            urls = page_info.get("urls")
            if isinstance(urls, dict):
                for value in urls.values():
                    if isinstance(value, str):
                        candidates.append(value)
        pics = root.get("pics")
        if isinstance(pics, list):
            for pic in pics:
                if isinstance(pic, dict) and isinstance(pic.get("videoSrc"), str):
                    candidates.append(pic["videoSrc"])
    candidates.extend(find_media_urls(payload))
    return [
        url
        for url in dict.fromkeys(candidates)
        if re.search(r"\.(mp4|m3u8)(\?|$)", url, flags=re.IGNORECASE)
    ]


def load_failed_cases(source_manifest: Path, platform: str, max_cases: int) -> list[DownloadCase]:
    data = json.loads(source_manifest.read_text(encoding="utf-8"))
    grouped: dict[tuple[str, str], dict[str, Any]] = {}
    for item in data.get("items", []):
        if item.get("status") != "failed":
            continue
        item_platform = str(item.get("platform") or "")
        if platform != "all" and item_platform != platform:
            continue
        if item_platform not in PLATFORM_PROFILES:
            continue
        post_id = str(item.get("post_id") or "")
        post_url = str(item.get("post_url") or "")
        url = str(item.get("url") or item.get("media_url") or "")
        if not post_id or not post_url:
            continue
        key = (item_platform, post_id)
        bucket = grouped.setdefault(
            key,
            {
                "platform": item_platform,
                "post_id": post_id,
                "post_url": post_url,
                "source_urls": [],
                "requested_media_types": set(),
            },
        )
        if url:
            bucket["source_urls"].append(url)
        media_type = str(item.get("media_type") or item.get("media_kind") or "")
        if media_type:
            bucket["requested_media_types"].add(media_type)

    counts: Counter[str] = Counter()
    cases: list[DownloadCase] = []
    for bucket in grouped.values():
        item_platform = bucket["platform"]
        if counts[item_platform] >= max_cases:
            continue
        counts[item_platform] += 1
        cases.append(
            DownloadCase(
                platform=item_platform,
                post_id=bucket["post_id"],
                post_url=bucket["post_url"],
                source_urls=tuple(dict.fromkeys(bucket["source_urls"])),
                requested_media_types=tuple(sorted(bucket["requested_media_types"])),
            )
        )
    return cases


class ManifestWriter:
    def __init__(self, output_dir: Path) -> None:
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.jsonl_path = output_dir / "manifest.jsonl"
        self.summary_path = output_dir / "summary.json"
        self.counts: Counter[str] = Counter()
        self.bytes_by_kind: Counter[str] = Counter()
        self.items_written = 0

    def append(self, item: dict[str, Any]) -> None:
        self.items_written += 1
        status = str(item.get("status") or "unknown")
        self.counts[status] += 1
        kind = str(item.get("media_kind") or "unknown")
        if status == "downloaded":
            self.bytes_by_kind[kind] += int(item.get("bytes") or 0)
        with self.jsonl_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(item, ensure_ascii=False, sort_keys=True) + "\n")
        self.write_summary()

    def write_summary(self, extra: dict[str, Any] | None = None) -> None:
        summary = {
            "output_dir": str(self.output_dir),
            "manifest_jsonl": str(self.jsonl_path),
            "items_written": self.items_written,
            "counts": dict(self.counts),
            "downloaded_mb": round(sum(self.bytes_by_kind.values()) / 1024 / 1024, 2),
            "downloaded_bytes_by_kind": dict(self.bytes_by_kind),
            "updated_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        }
        if extra:
            summary.update(extra)
        self.summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")


class BrowserMediaDownloader:
    def __init__(
        self,
        output_dir: Path,
        writer: ManifestWriter,
        max_images_per_post: int,
        max_videos_per_post: int,
        max_image_bytes: int,
        max_video_bytes: int,
        min_image_bytes: int,
        min_video_bytes: int,
    ) -> None:
        self.output_dir = output_dir
        self.writer = writer
        self.max_images_per_post = max_images_per_post
        self.max_videos_per_post = max_videos_per_post
        self.max_image_bytes = max_image_bytes
        self.max_video_bytes = max_video_bytes
        self.min_image_bytes = min_image_bytes
        self.min_video_bytes = min_video_bytes
        self.seen_response_urls: set[str] = set()
        self.saved_urls: set[str] = set()
        self.saved_counts: defaultdict[tuple[str, str], Counter[str]] = defaultdict(Counter)

    def _limit_for(self, kind: str) -> int:
        if kind == "video":
            return self.max_video_bytes
        return self.max_image_bytes

    def _quota_reached(self, case: DownloadCase, kind: str) -> bool:
        key = (case.platform, case.post_id)
        if kind == "video":
            return self.saved_counts[key][kind] >= self.max_videos_per_post
        return self.saved_counts[key][kind] >= self.max_images_per_post

    def _target_path(self, case: DownloadCase, kind: str, url: str, content_type: str | None) -> Path:
        key = (case.platform, case.post_id)
        next_index = self.saved_counts[key][kind] + 1
        digest = hashlib.sha256(url.encode("utf-8")).hexdigest()[:12]
        filename = (
            f"{case.platform}_{sanitize(case.post_id)}_{kind}_{next_index:03d}_"
            f"{digest}{suffix_for(content_type, url)}"
        )
        return self.output_dir / case.platform / sanitize(case.post_id) / filename

    async def maybe_save_response(self, case: DownloadCase, response: Response, source: str) -> None:
        url = response.url
        if url in self.seen_response_urls:
            return
        self.seen_response_urls.add(url)
        content_type = response.headers.get("content-type") or ""
        if not looks_like_platform_media(case.platform, url, content_type):
            return
        kind = media_kind(content_type, url)
        if not kind:
            return
        if kind not in case.requested_media_types and case.requested_media_types:
            return
        if self._quota_reached(case, kind):
            return

        declared_length = response.headers.get("content-length")
        if declared_length and declared_length.isdigit() and int(declared_length) > self._limit_for(kind):
            self.writer.append(
                {
                    "platform": case.platform,
                    "post_id": case.post_id,
                    "post_url": case.post_url,
                    "url": url,
                    "status": "skipped",
                    "reason": "content_length_exceeds_limit",
                    "content_length": int(declared_length),
                    "media_kind": kind,
                    "source": source,
                }
            )
            return

        try:
            body = await response.body()
        except Exception as exc:
            self.writer.append(
                {
                    "platform": case.platform,
                    "post_id": case.post_id,
                    "post_url": case.post_url,
                    "url": url,
                    "status": "response_body_failed",
                    "error_class": type(exc).__name__,
                    "error": str(exc),
                    "media_kind": kind,
                    "content_type": content_type,
                    "source": source,
                }
            )
            return
        await self.save_body(case, url, body, kind, content_type, source)

    async def save_body(
        self,
        case: DownloadCase,
        url: str,
        body: bytes,
        kind: str,
        content_type: str | None,
        source: str,
        status_code: int | None = None,
    ) -> None:
        if not body:
            return
        if url in self.saved_urls:
            return
        if kind == "image" and len(body) < self.min_image_bytes:
            self.writer.append(
                {
                    "platform": case.platform,
                    "post_id": case.post_id,
                    "post_url": case.post_url,
                    "url": url,
                    "status": "skipped",
                    "reason": "image_too_small",
                    "bytes": len(body),
                    "media_kind": kind,
                    "content_type": content_type or "",
                    "source": source,
                }
            )
            return
        if kind == "video" and len(body) < self.min_video_bytes:
            self.writer.append(
                {
                    "platform": case.platform,
                    "post_id": case.post_id,
                    "post_url": case.post_url,
                    "url": url,
                    "status": "skipped",
                    "reason": "video_too_small",
                    "bytes": len(body),
                    "media_kind": kind,
                    "content_type": content_type or "",
                    "source": source,
                }
            )
            return
        if len(body) > self._limit_for(kind):
            self.writer.append(
                {
                    "platform": case.platform,
                    "post_id": case.post_id,
                    "post_url": case.post_url,
                    "url": url,
                    "status": "skipped",
                    "reason": "body_exceeds_limit",
                    "bytes": len(body),
                    "media_kind": kind,
                    "content_type": content_type or "",
                    "source": source,
                }
            )
            return
        target = self._target_path(case, kind, url, content_type)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(body)
        self.saved_urls.add(url)
        key = (case.platform, case.post_id)
        self.saved_counts[key][kind] += 1
        self.writer.append(
            {
                "platform": case.platform,
                "post_id": case.post_id,
                "post_url": case.post_url,
                "url": url,
                "status": "downloaded",
                "status_code": status_code,
                "content_type": content_type or "",
                "bytes": len(body),
                "media_kind": kind,
                "source": source,
                "local_path": str(target),
            }
        )

    async def direct_retry(self, context: BrowserContext, case: DownloadCase) -> None:
        source_urls = list(case.source_urls)
        if case.platform == "weibo" and "video" in case.requested_media_types:
            source_urls = await self.weibo_video_url_candidates(context, case) + source_urls
        for source_url in dict.fromkeys(source_urls):
            if source_url in self.saved_urls:
                continue
            kind = media_kind(None, source_url) or ("video" if "video" in case.requested_media_types else "image")
            if kind in {"image", "video"} and self._quota_reached(case, kind):
                continue
            headers = {"referer": case.post_url}
            try:
                response = await context.request.get(
                    source_url,
                    headers=headers,
                    timeout=30_000,
                    max_redirects=5,
                )
            except Exception as exc:
                self.writer.append(
                    {
                        "platform": case.platform,
                        "post_id": case.post_id,
                        "post_url": case.post_url,
                        "url": source_url,
                        "status": "direct_retry_failed",
                        "error_class": type(exc).__name__,
                        "error": str(exc),
                        "media_kind": kind,
                        "source": "browser_context_request",
                    }
                )
                continue
            content_type = response.headers.get("content-type") or ""
            response_kind = media_kind(content_type, source_url) or kind
            if response.status >= 400:
                self.writer.append(
                    {
                        "platform": case.platform,
                        "post_id": case.post_id,
                        "post_url": case.post_url,
                        "url": source_url,
                        "status": "direct_retry_http_error",
                        "status_code": response.status,
                        "content_type": content_type,
                        "media_kind": response_kind,
                        "source": "browser_context_request",
                    }
                )
                continue
            declared_length = response.headers.get("content-length")
            if declared_length and declared_length.isdigit() and int(declared_length) > self._limit_for(response_kind):
                self.writer.append(
                    {
                        "platform": case.platform,
                        "post_id": case.post_id,
                        "post_url": case.post_url,
                        "url": source_url,
                        "status": "skipped",
                        "reason": "direct_content_length_exceeds_limit",
                        "content_length": int(declared_length),
                        "media_kind": response_kind,
                        "content_type": content_type,
                        "source": "browser_context_request",
                    }
                )
                continue
            try:
                body = await response.body()
            except Exception as exc:
                self.writer.append(
                    {
                        "platform": case.platform,
                        "post_id": case.post_id,
                        "post_url": case.post_url,
                        "url": source_url,
                        "status": "direct_retry_body_failed",
                        "error_class": type(exc).__name__,
                        "error": str(exc),
                        "media_kind": response_kind,
                        "content_type": content_type,
                        "source": "browser_context_request",
                    }
                )
                continue
            await self.save_body(
                case,
                source_url,
                body,
                response_kind,
                content_type,
                "browser_context_request",
                status_code=response.status,
            )

    async def weibo_video_url_candidates(self, context: BrowserContext, case: DownloadCase) -> list[str]:
        candidates: list[str] = []
        endpoints = [
            f"https://m.weibo.cn/statuses/show?id={case.post_id}",
            f"https://m.weibo.cn/statuses/extend?id={case.post_id}",
            f"https://weibo.com/ajax/statuses/show?id={case.post_id}",
        ]
        for endpoint in endpoints:
            try:
                response = await context.request.get(
                    endpoint,
                    headers={"referer": case.post_url},
                    timeout=20_000,
                    max_redirects=5,
                )
            except Exception as exc:
                self.writer.append(
                    {
                        "platform": case.platform,
                        "post_id": case.post_id,
                        "post_url": case.post_url,
                        "url": endpoint,
                        "status": "weibo_api_failed",
                        "error_class": type(exc).__name__,
                        "error": str(exc),
                        "source": "weibo_api_probe",
                    }
                )
                continue
            content_type = response.headers.get("content-type") or ""
            if response.status >= 400:
                self.writer.append(
                    {
                        "platform": case.platform,
                        "post_id": case.post_id,
                        "post_url": case.post_url,
                        "url": endpoint,
                        "status": "weibo_api_http_error",
                        "status_code": response.status,
                        "content_type": content_type,
                        "source": "weibo_api_probe",
                    }
                )
                continue
            try:
                text = await response.text()
            except Exception as exc:
                self.writer.append(
                    {
                        "platform": case.platform,
                        "post_id": case.post_id,
                        "post_url": case.post_url,
                        "url": endpoint,
                        "status": "weibo_api_body_failed",
                        "error_class": type(exc).__name__,
                        "error": str(exc),
                        "content_type": content_type,
                        "source": "weibo_api_probe",
                    }
                )
                continue
            try:
                payload = json.loads(text)
            except json.JSONDecodeError:
                payload = text
            found = [
                url
                for url in find_weibo_video_urls(payload)
                if any(host in url.lower() for host in ("weibocdn.com", "sinaimg.cn"))
            ]
            candidates.extend(found)
            self.writer.append(
                {
                    "platform": case.platform,
                    "post_id": case.post_id,
                    "post_url": case.post_url,
                    "url": endpoint,
                    "status": "weibo_api_probe_done",
                    "status_code": response.status,
                    "content_type": content_type,
                    "candidate_count": len(found),
                    "source": "weibo_api_probe",
                }
            )
        return list(dict.fromkeys(candidates))


async def stimulate_page(page: Page, platform: str) -> None:
    await page.wait_for_timeout(int(POST_WAIT_SECONDS.get(platform, 7.0) * 1000))
    for _ in range(3):
        await page.mouse.wheel(0, 900)
        await page.wait_for_timeout(1_500)
    if platform in {"xhs", "douyin", "weibo"}:
        for selector in ("video", "[aria-label*=play]", "[class*=play]", ".play"):
            try:
                locator = page.locator(selector).first
                if await locator.count():
                    await locator.click(timeout=2_000, force=True)
                    await page.wait_for_timeout(4_000)
                    break
            except Exception:
                continue


async def run_platform(
    args: argparse.Namespace,
    platform: str,
    cases: list[DownloadCase],
    output_dir: Path,
    writer: ManifestWriter,
) -> None:
    profile = args.profile_root / PLATFORM_PROFILES[platform]
    if not profile.exists():
        writer.append(
            {
                "platform": platform,
                "status": "profile_missing",
                "profile": str(profile),
            }
        )
        return
    downloader = BrowserMediaDownloader(
        output_dir=output_dir,
        writer=writer,
        max_images_per_post=args.max_images_per_post,
        max_videos_per_post=args.max_videos_per_post,
        max_image_bytes=args.max_image_mb * 1024 * 1024,
        max_video_bytes=args.max_video_mb * 1024 * 1024,
        min_image_bytes=args.min_image_bytes,
        min_video_bytes=args.min_video_bytes,
    )
    async with async_playwright() as pw:
        context = await pw.chromium.launch_persistent_context(
            user_data_dir=str(profile),
            executable_path=str(args.chrome),
            headless=not args.headed,
            viewport={"width": 1365, "height": 900},
            args=["--disable-blink-features=AutomationControlled"],
        )
        page = await context.new_page()
        for index, case in enumerate(cases, 1):
            started = time.perf_counter()

            async def on_response(response: Response, active_case: DownloadCase = case) -> None:
                await downloader.maybe_save_response(active_case, response, source="page_response")

            page.on("response", on_response)
            page_error: dict[str, Any] | None = None
            if not args.skip_page:
                try:
                    await page.goto(case.post_url, wait_until="domcontentloaded", timeout=args.post_timeout_ms)
                    await stimulate_page(page, case.platform)
                except Exception as exc:
                    page_error = {
                        "error_class": type(exc).__name__,
                        "error": str(exc),
                    }
            if not args.skip_direct_retry:
                await downloader.direct_retry(context, case)
            page.remove_listener("response", on_response)
            writer.append(
                {
                    "platform": case.platform,
                    "post_id": case.post_id,
                    "post_url": case.post_url,
                    "status": "case_done" if page_error is None else "case_done_with_page_error",
                    "page_url": page.url,
                    "requested_media_types": list(case.requested_media_types),
                    "source_url_count": len(case.source_urls),
                    "elapsed_seconds": round(time.perf_counter() - started, 2),
                    "case_index": index,
                    **(page_error or {}),
                }
            )
        await context.close()


async def async_main() -> None:
    args = parse_args()
    cases = load_failed_cases(args.source_manifest, args.platform, args.max_cases)
    output_dir = args.output_root / f"{time.strftime('%Y%m%d_%H%M%S')}_{args.platform}_{os.getpid()}"
    writer = ManifestWriter(output_dir)
    writer.write_summary(
        {
            "source_manifest": str(args.source_manifest),
            "platform": args.platform,
            "max_cases": args.max_cases,
            "case_count": len(cases),
            "case_count_by_platform": dict(Counter(case.platform for case in cases)),
        }
    )
    if not cases:
        return
    if not args.chrome.exists():
        writer.append({"status": "chrome_missing", "chrome": str(args.chrome)})
        return
    by_platform: defaultdict[str, list[DownloadCase]] = defaultdict(list)
    for case in cases:
        by_platform[case.platform].append(case)
    for platform in ("xhs", "weibo", "douyin"):
        platform_cases = by_platform.get(platform, [])
        if platform_cases:
            await run_platform(args, platform, platform_cases, output_dir, writer)
    writer.write_summary(
        {
            "source_manifest": str(args.source_manifest),
            "platform": args.platform,
            "max_cases": args.max_cases,
            "case_count": len(cases),
            "case_count_by_platform": dict(Counter(case.platform for case in cases)),
            "completed": True,
        }
    )
    print(writer.summary_path)


def main() -> None:
    asyncio.run(async_main())


if __name__ == "__main__":
    main()
