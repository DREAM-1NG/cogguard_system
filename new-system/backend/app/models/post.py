"""MongoDB document schemas for crawled data (used with Motor, not ORM)."""

from datetime import datetime

from pydantic import BaseModel, Field


class StandardPost(BaseModel):
    platform: str
    post_id: str
    content: str
    author_id: str
    author_name: str
    timestamp: datetime
    url: str = ""
    likes: int = 0
    reposts: int = 0
    comments_count: int = 0
    media_urls: list[str] = Field(default_factory=list)
    hashtags: list[str] = Field(default_factory=list)
    crawl_job_id: int | None = None
    raw_data: dict | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class StandardComment(BaseModel):
    platform: str
    comment_id: str
    post_id: str
    content: str
    author_id: str
    author_name: str
    timestamp: datetime
    reply_to: str | None = None
    likes: int = 0
    crawl_job_id: int | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
