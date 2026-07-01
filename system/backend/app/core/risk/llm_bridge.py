"""LLM 桥接占位：为后续 LLM 集成预留接口。

第一阶段不使用 LLM 进行最终裁决，仅保留接口定义。
后续可接入通义千问 / 智谱 / DeepSeek 等模型进行：
- 风险报告自然语言摘要生成
- 证据链叙事化解释
- 复杂场景的辅助判断
"""

from __future__ import annotations

from typing import Any


async def generate_summary(report: dict) -> str | None:
    """生成风险报告的自然语言摘要（占位）。"""
    # TODO: 接入 LLM API
    return None


async def explain_evidence(evidence: dict) -> str | None:
    """生成证据链的叙事化解释（占位）。"""
    # TODO: 接入 LLM API
    return None


async def assess_complex_scenario(context: dict[str, Any]) -> dict | None:
    """复杂场景辅助判断（占位）。"""
    # TODO: 接入 LLM API
    return None
