"""业务服务层包。

封装各模块的业务逻辑（认证、采集等），由 API 路由层调用。
服务层负责编排 core 逻辑、数据库操作和外部调用。
"""

from .case_research_archive import (
    load_research_archive_manifest,
    load_structured_search_records,
    verify_research_archive,
)

__all__ = [
    "load_research_archive_manifest",
    "load_structured_search_records",
    "verify_research_archive",
]
