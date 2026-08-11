"""Pydantic 请求/响应数据模式包。

定义 API 接口的输入输出校验模型，与 models 包中的 ORM 模型分离，
遵循 FastAPI 最佳实践。
"""

from .case_research import (
    PlatformGap,
    ResearchArchiveEntry,
    StructuredSearchHit,
    StructuredSearchRecord,
)

__all__ = [
    "PlatformGap",
    "ResearchArchiveEntry",
    "StructuredSearchHit",
    "StructuredSearchRecord",
]
