from __future__ import annotations

import base64
import logging
import os
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

PLATFORM_IMAGE_HEADERS: dict[str, dict[str, str]] = {
    "wechat": {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Referer": "https://mp.weixin.qq.com/",
        "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    },
    "default": {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "image/*,*/*;q=0.8",
    },
}


class ImageFetchError(Exception):
    pass


@dataclass
class ImageResult:
    url: str
    success: bool
    base64_data: Optional[str] = None
    mime_type: Optional[str] = None
    error: Optional[str] = None

    def to_data_url(self) -> Optional[str]:
        if self.success and self.base64_data and self.mime_type:
            return f"data:{self.mime_type};base64,{self.base64_data}"
        return None


class ImageService:
    MAX_IMAGE_SIZE = 5 * 1024 * 1024
    TIMEOUT = 10
    MAX_WORKERS = 5

    def __init__(self, platform: str = "default"):
        self.platform = platform
        self.headers = PLATFORM_IMAGE_HEADERS.get(platform, PLATFORM_IMAGE_HEADERS["default"])

    def _detect_mime_type(self, content: bytes, url: str) -> str:
        if len(content) < 12:
            return "image/jpeg"
        if content[:8] == b"\x89PNG\r\n\x1a\n":
            return "image/png"
        if content[:2] == b"\xff\xd8":
            return "image/jpeg"
        if content[:6] in (b"GIF87a", b"GIF89a"):
            return "image/gif"
        if content[:4] == b"RIFF" and content[8:12] == b"WEBP":
            return "image/webp"
        if content[:2] == b"BM":
            return "image/bmp"

        url_lower = url.lower()
        if ".png" in url_lower:
            return "image/png"
        if ".gif" in url_lower:
            return "image/gif"
        if ".webp" in url_lower:
            return "image/webp"
        return "image/jpeg"

    def _download_single(self, url: str) -> ImageResult:
        try:
            from curl_cffi import requests as curl_requests

            response = curl_requests.get(
                url,
                headers=self.headers,
                timeout=self.TIMEOUT,
                impersonate="chrome",
            )
            if response.status_code != 200:
                return ImageResult(url=url, success=False, error=f"HTTP {response.status_code}")

            content = response.content
            if len(content) > self.MAX_IMAGE_SIZE:
                return ImageResult(url=url, success=False, error="image exceeds 5MB limit")

            mime_type = self._detect_mime_type(content, url)
            return ImageResult(
                url=url,
                success=True,
                base64_data=base64.b64encode(content).decode("utf-8"),
                mime_type=mime_type,
            )
        except Exception as exc:
            logger.warning("Image download failed for %s: %s", url, exc)
            return ImageResult(url=url, success=False, error=str(exc))

    def download_images(self, urls: list[str]) -> dict[str, ImageResult]:
        if not urls:
            return {}

        results: dict[str, ImageResult] = {}
        with ThreadPoolExecutor(max_workers=self.MAX_WORKERS) as executor:
            future_to_url = {executor.submit(self._download_single, url): url for url in urls}
            for future, url in future_to_url.items():
                try:
                    results[url] = future.result()
                except Exception as exc:
                    results[url] = ImageResult(url=url, success=False, error=str(exc))

        return results

    def _get_extension(self, mime_type: str) -> str:
        return {
            "image/png": ".png",
            "image/jpeg": ".jpg",
            "image/gif": ".gif",
            "image/webp": ".webp",
            "image/bmp": ".bmp",
        }.get(mime_type, ".jpg")

    def _download_and_save(self, url: str, save_path: str) -> tuple[bool, str]:
        result = self._download_single(url)
        if not result.success or not result.base64_data or not result.mime_type:
            return False, result.error or "download failed"

        ext = self._get_extension(result.mime_type)
        if not save_path.endswith(ext):
            save_path = (
                save_path.rsplit(".", 1)[0] + ext
                if "." in os.path.basename(save_path)
                else save_path + ext
            )
        Path(save_path).write_bytes(base64.b64decode(result.base64_data))
        return True, save_path

    def download_to_local(self, urls: list[str], save_dir: str) -> dict[str, Optional[str]]:
        if not urls:
            return {}

        save_dir_path = Path(save_dir)
        save_dir_path.mkdir(parents=True, exist_ok=True)

        def download_task(args: tuple[int, str]) -> tuple[str, Optional[str]]:
            index, url = args
            success, result = self._download_and_save(url, str(save_dir_path / f"{index + 1}"))
            return url, os.path.abspath(result) if success else None

        with ThreadPoolExecutor(max_workers=self.MAX_WORKERS) as executor:
            return dict(executor.map(download_task, enumerate(urls)))
