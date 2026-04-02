# -*- coding: utf-8 -*-
"""
图片服务 - 下载图片并转换为 Base64 或保存到本地
"""
import base64
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor

logger = logging.getLogger(__name__)

# 平台特定的图片请求头配置
PLATFORM_IMAGE_HEADERS: Dict[str, Dict[str, str]] = {
    "wechat": {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Referer": "https://mp.weixin.qq.com/",
        "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    },
    "default": {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "image/*,*/*;q=0.8",
    },
}


class ImageFetchError(Exception):
    """图片获取错误"""
    pass


@dataclass
class ImageResult:
    """图片处理结果"""
    url: str
    success: bool
    base64_data: Optional[str] = None
    mime_type: Optional[str] = None
    error: Optional[str] = None

    def to_data_url(self) -> Optional[str]:
        """转换为 Data URL 格式"""
        if self.success and self.base64_data and self.mime_type:
            return f"data:{self.mime_type};base64,{self.base64_data}"
        return None


class ImageService:
    """图片服务 - 下载图片并转换为 Base64"""

    MAX_IMAGE_SIZE = 5 * 1024 * 1024  # 5MB
    TIMEOUT = 10  # 秒
    MAX_WORKERS = 5  # 并发下载数

    def __init__(self, platform: str = "default"):
        self.platform = platform
        self.headers = PLATFORM_IMAGE_HEADERS.get(
            platform,
            PLATFORM_IMAGE_HEADERS["default"]
        )

    def _detect_mime_type(self, content: bytes, url: str) -> str:
        """根据文件头检测图片 MIME 类型"""
        if len(content) < 12:
            return "image/jpeg"

        # PNG: 89 50 4E 47 0D 0A 1A 0A
        if content[:8] == b'\x89PNG\r\n\x1a\n':
            return "image/png"
        # JPEG: FF D8 FF
        elif content[:2] == b'\xff\xd8':
            return "image/jpeg"
        # GIF: GIF87a or GIF89a
        elif content[:6] in (b'GIF87a', b'GIF89a'):
            return "image/gif"
        # WebP: RIFF....WEBP
        elif content[:4] == b'RIFF' and content[8:12] == b'WEBP':
            return "image/webp"
        # BMP: BM
        elif content[:2] == b'BM':
            return "image/bmp"
        # 从 URL 推断
        url_lower = url.lower()
        if '.png' in url_lower:
            return "image/png"
        elif '.gif' in url_lower:
            return "image/gif"
        elif '.webp' in url_lower:
            return "image/webp"
        # 默认 JPEG
        return "image/jpeg"

    def _download_single(self, url: str) -> ImageResult:
        """下载单张图片（同步）"""
        try:
            from curl_cffi import requests as curl_requests

            response = curl_requests.get(
                url,
                headers=self.headers,
                timeout=self.TIMEOUT,
                impersonate="chrome",
            )

            if response.status_code != 200:
                return ImageResult(
                    url=url,
                    success=False,
                    error=f"HTTP {response.status_code}"
                )

            content = response.content

            # 检查大小
            if len(content) > self.MAX_IMAGE_SIZE:
                return ImageResult(
                    url=url,
                    success=False,
                    error=f"图片过大: {len(content) / 1024 / 1024:.1f}MB > 5MB"
                )

            # 检测 MIME 类型
            mime_type = self._detect_mime_type(content, url)

            # 转换为 base64
            base64_data = base64.b64encode(content).decode("utf-8")

            return ImageResult(
                url=url,
                success=True,
                base64_data=base64_data,
                mime_type=mime_type,
            )

        except Exception as e:
            logger.warning(f"下载图片失败 {url}: {e}")
            return ImageResult(url=url, success=False, error=str(e))

    def download_images(self, urls: List[str]) -> Dict[str, ImageResult]:
        """
        批量下载图片并转换为 Base64

        Args:
            urls: 图片 URL 列表

        Returns:
            {url: ImageResult} 映射
        """
        if not urls:
            return {}

        results = {}

        with ThreadPoolExecutor(max_workers=self.MAX_WORKERS) as executor:
            future_to_url = {
                executor.submit(self._download_single, url): url
                for url in urls
            }

            for future in future_to_url:
                url = future_to_url[future]
                try:
                    results[url] = future.result()
                except Exception as e:
                    results[url] = ImageResult(
                        url=url,
                        success=False,
                        error=str(e)
                    )

        # 日志统计
        success_count = sum(1 for r in results.values() if r.success)
        logger.info(f"图片下载完成: {success_count}/{len(urls)} 成功")

        return results

    def _get_extension(self, mime_type: str) -> str:
        """根据 MIME 类型获取文件扩展名"""
        mime_to_ext = {
            "image/png": ".png",
            "image/jpeg": ".jpg",
            "image/gif": ".gif",
            "image/webp": ".webp",
            "image/bmp": ".bmp",
        }
        return mime_to_ext.get(mime_type, ".jpg")

    def _download_and_save(self, url: str, save_path: str) -> Tuple[bool, str]:
        """下载单张图片并保存到本地"""
        try:
            from curl_cffi import requests as curl_requests

            response = curl_requests.get(
                url,
                headers=self.headers,
                timeout=self.TIMEOUT,
                impersonate="chrome",
            )

            if response.status_code != 200:
                return False, f"HTTP {response.status_code}"

            content = response.content

            if len(content) > self.MAX_IMAGE_SIZE:
                return False, f"图片过大: {len(content) / 1024 / 1024:.1f}MB"

            # 检测类型并确定扩展名
            mime_type = self._detect_mime_type(content, url)
            ext = self._get_extension(mime_type)

            # 确保路径有正确的扩展名
            if not save_path.endswith(ext):
                save_path = save_path.rsplit(".", 1)[0] + ext if "." in os.path.basename(save_path) else save_path + ext

            # 写入文件
            with open(save_path, "wb") as f:
                f.write(content)

            return True, save_path

        except Exception as e:
            logger.warning(f"下载图片失败 {url}: {e}")
            return False, str(e)

    def download_to_local(
        self,
        urls: List[str],
        save_dir: str
    ) -> Dict[str, Optional[str]]:
        """
        下载图片到本地目录

        Args:
            urls: 图片 URL 列表
            save_dir: 保存目录

        Returns:
            {原始URL: 本地绝对路径} 映射，下载失败的值为 None
        """
        if not urls:
            return {}

        # 创建目录
        save_dir_path = Path(save_dir)
        save_dir_path.mkdir(parents=True, exist_ok=True)

        results: Dict[str, Optional[str]] = {}

        def download_task(args: Tuple[int, str]) -> Tuple[str, Optional[str]]:
            idx, url = args
            save_path = str(save_dir_path / f"{idx + 1}")
            success, result = self._download_and_save(url, save_path)
            if success:
                return url, os.path.abspath(result)
            else:
                logger.warning(f"图片 {idx + 1} 下载失败: {result}")
                return url, None

        with ThreadPoolExecutor(max_workers=self.MAX_WORKERS) as executor:
            tasks = list(enumerate(urls))
            for url, local_path in executor.map(download_task, tasks):
                results[url] = local_path

        # 日志统计
        success_count = sum(1 for v in results.values() if v is not None)
        logger.info(f"图片保存完成: {success_count}/{len(urls)} 成功, 目录: {save_dir}")

        return results
