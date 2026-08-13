"""Stream-download failed Douyin videos from the media manifest.

This utility is intentionally narrow: it retries only Douyin failed media URLs
from an existing manifest and writes response bodies incrementally so large
videos do not hang Playwright response capture.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import time
from collections import Counter
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import requests


DEFAULT_SOURCE_MANIFEST = Path(
    r"G:\CISCN\CogGuard\.worktrees\refactor-system\system\output\media_downloads"
    r"\platform_allowlist_expanded\all\20260812_222420\manifest.json"
)
DEFAULT_OUTPUT_ROOT = Path(
    r"G:\CISCN\CogGuard\.worktrees\refactor-system\system\output\media_downloads"
    r"\douyin_stream_retry"
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-manifest", type=Path, default=DEFAULT_SOURCE_MANIFEST)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--max-items", type=int, default=20)
    parser.add_argument("--max-mb", type=int, default=500)
    parser.add_argument("--timeout", type=int, default=120)
    parser.add_argument("--chunk-size", type=int, default=1024 * 1024)
    return parser.parse_args()


def load_failed_douyin_items(path: Path, max_items: int) -> list[dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    items: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in data.get("items", []):
        if item.get("status") != "failed" or item.get("platform") != "douyin":
            continue
        url = str(item.get("url") or item.get("media_url") or "")
        if not url or url in seen:
            continue
        seen.add(url)
        items.append(item)
        if len(items) >= max_items:
            break
    return items


def safe_id(value: Any) -> str:
    text = str(value or "unknown")
    keep = "".join(ch if ch.isalnum() or ch in "-_." else "_" for ch in text)
    return (keep.strip("._") or "unknown")[:96]


def write_jsonl(path: Path, item: dict[str, Any]) -> None:
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(item, ensure_ascii=False, sort_keys=True) + "\n")


def download_one(item: dict[str, Any], output_dir: Path, args: argparse.Namespace) -> dict[str, Any]:
    url = str(item.get("url") or item.get("media_url") or "")
    post_id = str(item.get("post_id") or "unknown")
    target_dir = output_dir / "douyin" / safe_id(post_id)
    target_dir.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256(url.encode("utf-8")).hexdigest()[:12]
    target = target_dir / f"douyin_{safe_id(post_id)}_video_{digest}.mp4"
    partial = target.with_suffix(".mp4.part")
    headers = {
        "accept": "video/webm,video/ogg,video/*;q=0.9,*/*;q=0.8",
        "accept-language": "zh-CN,zh;q=0.9,en;q=0.8",
        "referer": str(item.get("post_url") or "https://www.douyin.com/"),
        "user-agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/151.0.0.0 Safari/537.36"
        ),
    }
    started = time.perf_counter()
    max_bytes = args.max_mb * 1024 * 1024
    bytes_written = 0
    try:
        with requests.get(
            url,
            headers=headers,
            stream=True,
            timeout=(15, args.timeout),
            allow_redirects=True,
        ) as response:
            content_type = response.headers.get("content-type") or ""
            content_length = response.headers.get("content-length")
            if content_length and content_length.isdigit() and int(content_length) > max_bytes:
                return {
                    "platform": "douyin",
                    "post_id": post_id,
                    "post_url": item.get("post_url"),
                    "url": url,
                    "final_url": response.url,
                    "status": "skipped",
                    "reason": "content_length_exceeds_limit",
                    "status_code": response.status_code,
                    "content_type": content_type,
                    "content_length": int(content_length),
                    "elapsed_seconds": round(time.perf_counter() - started, 2),
                }
            if response.status_code >= 400:
                return {
                    "platform": "douyin",
                    "post_id": post_id,
                    "post_url": item.get("post_url"),
                    "url": url,
                    "final_url": response.url,
                    "status": "http_error",
                    "status_code": response.status_code,
                    "content_type": content_type,
                    "elapsed_seconds": round(time.perf_counter() - started, 2),
                }
            with partial.open("wb") as fh:
                for chunk in response.iter_content(chunk_size=args.chunk_size):
                    if not chunk:
                        continue
                    bytes_written += len(chunk)
                    if bytes_written > max_bytes:
                        fh.close()
                        partial.unlink(missing_ok=True)
                        return {
                            "platform": "douyin",
                            "post_id": post_id,
                            "post_url": item.get("post_url"),
                            "url": url,
                            "final_url": response.url,
                            "status": "skipped",
                            "reason": "body_exceeds_limit",
                            "bytes": bytes_written,
                            "status_code": response.status_code,
                            "content_type": content_type,
                            "elapsed_seconds": round(time.perf_counter() - started, 2),
                        }
                    fh.write(chunk)
        if bytes_written < 50_000:
            partial.unlink(missing_ok=True)
            return {
                "platform": "douyin",
                "post_id": post_id,
                "post_url": item.get("post_url"),
                "url": url,
                "status": "skipped",
                "reason": "video_too_small",
                "bytes": bytes_written,
                "elapsed_seconds": round(time.perf_counter() - started, 2),
            }
        partial.replace(target)
        return {
            "platform": "douyin",
            "post_id": post_id,
            "post_url": item.get("post_url"),
            "url": url,
            "final_url": response.url,
            "status": "downloaded",
            "status_code": response.status_code,
            "content_type": content_type,
            "bytes": bytes_written,
            "media_kind": "video",
            "final_host": urlparse(response.url).hostname,
            "local_path": str(target),
            "elapsed_seconds": round(time.perf_counter() - started, 2),
        }
    except Exception as exc:
        partial.unlink(missing_ok=True)
        return {
            "platform": "douyin",
            "post_id": post_id,
            "post_url": item.get("post_url"),
            "url": url,
            "status": "failed",
            "error_class": type(exc).__name__,
            "error": str(exc),
            "bytes": bytes_written,
            "elapsed_seconds": round(time.perf_counter() - started, 2),
        }


def main() -> None:
    args = parse_args()
    output_dir = args.output_root / f"{time.strftime('%Y%m%d_%H%M%S')}_{os.getpid()}"
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest_jsonl = output_dir / "manifest.jsonl"
    items = load_failed_douyin_items(args.source_manifest, args.max_items)
    results: list[dict[str, Any]] = []
    for item in items:
        result = download_one(item, output_dir, args)
        results.append(result)
        write_jsonl(manifest_jsonl, result)
        summary = summarize(results, output_dir, manifest_jsonl, args.source_manifest, len(items))
        (output_dir / "summary.json").write_text(
            json.dumps(summary, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    print(output_dir / "summary.json")


def summarize(
    results: list[dict[str, Any]],
    output_dir: Path,
    manifest_jsonl: Path,
    source_manifest: Path,
    total: int,
) -> dict[str, Any]:
    return {
        "output_dir": str(output_dir),
        "source_manifest": str(source_manifest),
        "manifest_jsonl": str(manifest_jsonl),
        "total": total,
        "completed": len(results),
        "status": dict(Counter(str(item.get("status")) for item in results)),
        "downloaded": sum(1 for item in results if item.get("status") == "downloaded"),
        "downloaded_mb": round(
            sum(int(item.get("bytes") or 0) for item in results if item.get("status") == "downloaded")
            / 1024
            / 1024,
            2,
        ),
    }


if __name__ == "__main__":
    main()
