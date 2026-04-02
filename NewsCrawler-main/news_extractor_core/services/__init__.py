# -*- coding: utf-8 -*-
"""
核心服务模块
"""
from .detector import detect_platform, get_supported_platforms
from .extractor import ExtractorService
from .formatter import to_markdown
from .image_service import ImageService, ImageResult, ImageFetchError

__all__ = [
    "detect_platform",
    "get_supported_platforms",
    "ExtractorService",
    "to_markdown",
    "ImageService",
    "ImageResult",
    "ImageFetchError",
]
