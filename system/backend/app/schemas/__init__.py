"""Pydantic 请求/响应数据模式包。

定义 API 接口的输入输出校验模型，与 models 包中的 ORM 模型分离，
遵循 FastAPI 最佳实践。
"""

from app.schemas.case_research import (
    PlatformGap,
    ResearchArchiveEntry,
    StructuredSearchHit,
    StructuredSearchRecord,
)
from app.schemas.twitter_benchmark import TwitterBenchmarkManifest

__all__ = [
    "PlatformGap",
    "ResearchArchiveEntry",
    "StructuredSearchHit",
    "StructuredSearchRecord",
    "TwitterBenchmarkManifest",
]
