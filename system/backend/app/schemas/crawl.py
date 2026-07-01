"""数据采集相关的请求 / 响应数据模式。"""

from datetime import datetime

from pydantic import BaseModel, Field


class CrawlRequest(BaseModel):
    """创建采集任务的请求体。"""
    platform: str = Field(..., description="平台名称: mock_weibo / weibo / news / ...")
    keywords: list[str] = Field(default_factory=list, description="搜索关键词列表（社交）；新闻平台可填 URL")
    event_id: str | None = Field(
        default=None,
        description="事件标识；用于多平台同一事件数据对齐与去重，例如 trump_visit_2026_05_21。",
    )
    source_keyword: str | None = Field(
        default=None,
        description="本次采集的主关键词；未填写时默认使用 keywords[0]。",
    )
    post_ids: list[str] = Field(
        default_factory=list,
        description="指定帖子/文章 URL 列表（新闻平台必填至少一条 http(s) 链接）",
    )
    max_posts: int = Field(default=50, ge=1, le=1000)
    crawl_comments: bool = Field(default=True)
    recursive_comments: bool = Field(
        default=False,
        description="请求递归完整评论树；当前 MediaCrawler 实际最多落到二级评论，并在 crawl_metadata 中标明降级。",
    )
    enrich_author_profiles: bool = Field(
        default=False,
        description="请求作者主页级画像补全；当前先保留请求元数据，搜索链路只使用结果载荷中的用户字段。",
    )
    comment_sort: str = Field(
        default="none",
        pattern="^(none|like_count_desc|reply_count_desc)$",
        description="评论入库排序：none / like_count_desc / reply_count_desc。",
    )
    max_comments_per_post: int = Field(
        default=200,
        ge=0,
        le=5000,
        description="单条帖子最多抓取评论数；0 表示不额外限制并由爬虫默认策略决定。",
    )
    execution_mode: str = Field(
        default="local",
        pattern="^(local|queued)$",
        description="任务执行方式：local=FastAPI 本地后台执行；queued=投递 Celery 队列。",
    )


class CrawlJobResponse(BaseModel):
    """采集任务状态响应体。"""
    id: int
    job_type: str
    platform: str
    status: str
    progress: int
    result_summary: str | None
    celery_task_id: str | None
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
    author_profile: dict | None = None


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
