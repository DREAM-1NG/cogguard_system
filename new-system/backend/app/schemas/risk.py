"""风险研判请求数据模式。"""

from __future__ import annotations

from pydantic import BaseModel, Field


class RiskAssessRequest(BaseModel):
    platform: str | None = Field(default=None, description="平台名称，如 weibo / mock_weibo")
    keyword: str | None = Field(default=None, description="关键词过滤")
    post_ids: list[str] = Field(default_factory=list, description="限定分析的帖子 ID 列表")
    max_posts: int = Field(default=100, ge=1, le=500)
    stance_target: str | None = Field(default=None, description="立场识别目标/话题")
    analysis_mode: str = Field(default="agent", description="分析模式：agent / model / rule，默认使用 KT3 多智能体闭环")
    enable_fact_check: bool = Field(default=True, description="agent 模式下是否启用事实核查 Agent")
    enable_hate_detection: bool = Field(default=True, description="agent 模式下是否启用仇恨/有害语言 Agent")
    enable_countermeasure: bool = Field(default=True, description="agent 模式下是否启用反制建议 Agent")
    report_format: str = Field(default="json", description="报告格式：json / markdown / pdf")
