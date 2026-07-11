# -*- coding: utf-8 -*-
"""
鏍稿績鏈嶅姟妯″潡
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
