from __future__ import annotations

from importlib import import_module
from typing import Optional

from ..models import NewsItem
from .detector import detect_platform


ADAPTERS = {
    "wechat": "WeChatAdapter",
    "toutiao": "ToutiaoAdapter",
    "netease": "NeteaseAdapter",
    "sohu": "SohuAdapter",
    "tencent": "TencentAdapter",
    "detik": "DetikAdapter",
    "lenny": "LennyAdapter",
    "naver": "NaverAdapter",
    "quora": "QuoraAdapter",
    "bbc": "BBCAdapter",
    "cnn": "CNNAdapter",
    "twitter": "TwitterAdapter",
}

_ADAPTER_MODULES = {
    "wechat": "..adapters.wechat",
    "toutiao": "..adapters.toutiao",
    "netease": "..adapters.netease",
    "sohu": "..adapters.sohu",
    "tencent": "..adapters.tencent",
    "detik": "..adapters.detik",
    "lenny": "..adapters.lenny",
    "naver": "..adapters.naver",
    "quora": "..adapters.quora",
    "bbc": "..adapters.bbc",
    "cnn": "..adapters.cnn",
    "twitter": "..adapters.twitter",
}


def _load_adapter(platform: str):
    module = import_module(_ADAPTER_MODULES[platform], package=__package__)
    adapter_type = getattr(module, ADAPTERS[platform])
    return adapter_type()


class ExtractorService:
    @staticmethod
    def extract_news(
        url: str,
        platform: Optional[str] = None,
        cookie: Optional[str] = None,
    ) -> tuple[NewsItem, str]:
        if platform is None:
            platform = detect_platform(url)

        if platform is None:
            raise ValueError("Unable to detect a supported news platform for the URL.")

        if platform not in ADAPTERS:
            raise ValueError(f"Platform '{platform}' is not supported.")

        try:
            adapter = _load_adapter(platform)
            if platform == "twitter":
                news_item = adapter.extract(url, cookie=cookie)
            else:
                news_item = adapter.extract(url)
            return news_item, platform
        except Exception as exc:
            raise ValueError(f"Extraction failed: {exc}") from exc
