# -*- coding: utf-8 -*-
"""
骞冲彴妫€娴嬫湇鍔?"""
import re
from typing import Optional


PLATFORM_PATTERNS = {
    "toutiao": r"https?://www\.toutiao\.com/article/",
    "wechat": r"https?://mp\.weixin\.qq\.com/s/",
    "netease": r"https?://www\.163\.com/(news|dy)/article/",  # 鏀寔news鍜宒y涓ょ璺緞
    "sohu": r"https?://www\.sohu\.com/a/",
    "tencent": r"https?://news\.qq\.com/rain/a/",
    "detik": r"https?://news\.detik\.com/",
    "naver": r"https?://.*\.naver\.com/",
    "lenny": r"https?://www\.lennysnewsletter\.com/",
    "quora": r"https?://.*\.quora\.com/",
    "bbc": r"https?://www\.bbc\.com/news/articles/",
    "cnn": r"https?://(edition\.|www\.)?cnn\.com/\d{4}/\d{2}/\d{2}/",
    "twitter": r"https?://(?:www\.)?(?:twitter|x)\.com/\w+/status/\d+",
}


def detect_platform(url: str) -> Optional[str]:
    """
    鏍规嵁 URL 妫€娴嬪钩鍙扮被鍨?
    Args:
        url: 鏂伴椈閾炬帴

    Returns:
        骞冲彴鍚嶇О锛屽鏋滄棤娉曡瘑鍒垯杩斿洖 None
    """
    for platform, pattern in PLATFORM_PATTERNS.items():
        if re.match(pattern, url):
            return platform
    return None


def get_supported_platforms() -> list[dict]:
    """Return supported platform metadata."""
    return [
        {"id": "toutiao", "name": "Toutiao", "icon": "news"},
        {"id": "wechat", "name": "WeChat", "icon": "chat"},
        {"id": "netease", "name": "NetEase News", "icon": "news"},
        {"id": "sohu", "name": "Sohu News", "icon": "news"},
        {"id": "tencent", "name": "Tencent News", "icon": "news"},
        {"id": "detik", "name": "Detik News", "icon": "news"},
        {"id": "naver", "name": "Naver News", "icon": "news"},
        {"id": "lenny", "name": "Lenny's Newsletter", "icon": "newsletter"},
        {"id": "quora", "name": "Quora", "icon": "qa"},
        {"id": "bbc", "name": "BBC News", "icon": "news"},
        {"id": "cnn", "name": "CNN News", "icon": "news"},
        {"id": "twitter", "name": "Twitter/X", "icon": "social"},
    ]
