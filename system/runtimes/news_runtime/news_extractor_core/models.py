from __future__ import annotations

from enum import Enum
from typing import Any


class ContentType(str, Enum):
    TEXT = "text"
    IMAGE = "image"
    VIDEO = "video"


class ContentItem:
    def __init__(self, type: str, content: str, desc: str = ""):
        self.type = type
        self.content = content
        self.desc = desc

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": self.type,
            "content": self.content,
            "desc": self.desc,
        }


class NewsMetaInfo:
    def __init__(
        self,
        author_name: str = "",
        author_url: str = "",
        publish_time: str = "",
        **kwargs: Any,
    ):
        self.author_name = author_name
        self.author_url = author_url
        self.publish_time = publish_time
        self.extra = kwargs

    def to_dict(self) -> dict[str, Any]:
        data = {
            "author_name": self.author_name,
            "author_url": self.author_url,
            "publish_time": self.publish_time,
        }
        data.update(self.extra)
        return data


class NewsItem:
    def __init__(self, data: dict[str, Any]):
        self.title = data.get("title", "")
        self.news_url = data.get("news_url", "")
        self.news_id = data.get("news_id", "")

        meta_info = data.get("meta_info", {})
        if isinstance(meta_info, dict):
            self.meta_info = meta_info
        elif hasattr(meta_info, "model_dump"):
            self.meta_info = meta_info.model_dump()
        elif hasattr(meta_info, "dict"):
            self.meta_info = meta_info.dict()
        else:
            self.meta_info = {}

        self.contents = data.get("contents", [])
        self.texts = data.get("texts", [])
        self.images = data.get("images", [])
        self.videos = data.get("videos", [])

    def to_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "news_url": self.news_url,
            "news_id": self.news_id,
            "meta_info": self.meta_info,
            "contents": self.contents,
            "texts": self.texts,
            "images": self.images,
            "videos": self.videos,
        }

    @classmethod
    def from_pydantic(cls, pydantic_model: Any) -> "NewsItem":
        if hasattr(pydantic_model, "model_dump"):
            return cls(pydantic_model.model_dump())
        if hasattr(pydantic_model, "dict"):
            return cls(pydantic_model.dict())
        raise ValueError("Invalid pydantic model")

    def __repr__(self) -> str:
        return f"<NewsItem title={self.title[:30]!r} url={self.news_url[:50]!r}>"
