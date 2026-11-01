from __future__ import annotations

from abc import ABC, abstractmethod

from ..models import NewsItem


class CrawlerAdapter(ABC):
    @property
    @abstractmethod
    def platform_name(self) -> str:
        raise NotImplementedError

    @abstractmethod
    def extract(self, url: str) -> NewsItem:
        raise NotImplementedError
