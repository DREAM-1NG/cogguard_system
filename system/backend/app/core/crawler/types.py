from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.models.post import StandardComment, StandardPost


@dataclass(slots=True)
class CrawlRequestOptions:
    keywords: list[str] = field(default_factory=list)
    post_ids: list[str] = field(default_factory=list)
    max_posts: int = 50
    crawl_comments: bool = True
    recursive_comments: bool = False
    enrich_author_profiles: bool = False
    comment_sort: str = "none"
    max_comments_per_post: int | None = None


@dataclass(slots=True)
class CrawlBatch:
    posts: list[StandardPost] = field(default_factory=list)
    comments: list[StandardComment] = field(default_factory=list)
    crawl_metadata: dict[str, Any] = field(default_factory=dict)
