"""数据采集相关的请求 / 响应数据模式。"""

from datetime import datetime

from pydantic import BaseModel, Field


class CrawlRequest(BaseModel):
    """创建采集任务的请求体。"""
    platform: str = Field(..., description="平台名称: weibo / douyin / xhs / toutiao / wechat / ...")
    keywords: list[str] = Field(default_factory=list, description="搜索关键词列表")
    post_ids: list[str] = Field(default_factory=list, description="指定帖子ID列表")
    max_posts: int = Field(default=50, ge=1, le=1000)
    crawl_comments: bool = Field(default=True)


class CrawlJobResponse(BaseModel):
    """采集任务状态响应体。"""
    id: int
    job_type: str
    platform: str
    status: str
    progress: int
    result_summary: str | None
    created_at: datetime
    finished_at: datetime | None

    model_config = {"from_attributes": True}


class PostResponse(BaseModel):
    """标准化帖子数据响应体。"""
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


class PostListResponse(BaseModel):
    total: int
    items: list[PostResponse]


class CrawlDataQuery(BaseModel):
    """采集数据查询参数。"""
    platform: str | None = None
    keyword: str | None = None
    start_time: datetime | None = None
    end_time: datetime | None = None
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)
