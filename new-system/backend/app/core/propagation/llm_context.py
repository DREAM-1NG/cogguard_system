"""LLM 上下文事件提取模块。

通过 LLM API 从事件文本中提取外生事件（KOL 放大、官方回应等），
支持 mock 模式和多次调用多数投票。
"""

from __future__ import annotations

import json
import logging
from collections import Counter
from typing import Any

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

# 允许的事件类型
VALID_EVENT_TYPES = frozenset({
    "kol_amplification",
    "official_response",
    "platform_intervention",
    "narrative_mutation",
    "coordinated_burst",
    "none",
})

_EXTRACTION_PROMPT = """\
你是一个社交媒体传播分析专家。请从以下事件信息中提取外生事件。

## 事件概要
{event_summary}

## 最近小时传播量
{volumes}

## 代表性帖子（最新5条）
{top_posts}

## 协同检测信号
{coordination_signals}

请以 JSON 格式输出检测到的外生事件。每个事件包含类型、证据和置信度。
事件类型只能是以下之一：kol_amplification, official_response, platform_intervention, narrative_mutation, coordinated_burst, none

输出格式：
{{"events": [{{"type": "事件类型", "evidence": "证据文本", "confidence": 0.0到1.0}}]}}

如果没有检测到任何事件，输出：{{"events": [{{"type": "none", "evidence": "", "confidence": 1.0}}]}}
"""


async def extract_events(
    event_summary: str,
    volumes: list[int | float],
    top_posts: list[str],
    coordination_signals: dict[str, Any] | None = None,
    *,
    mock: bool = False,
    num_samples: int = 3,
) -> dict:
    """从事件上下文中提取外生事件。

    Parameters
    ----------
    mock : bool
        为 True 时跳过 API 调用，返回中性结果。
    num_samples : int
        LLM 调用次数，取多数投票。
    """
    if mock or not getattr(settings, "LLM_API_KEY", ""):
        return {"events": [], "llm_available": False}

    prompt = _EXTRACTION_PROMPT.format(
        event_summary=event_summary[:500],
        volumes=str(volumes[-12:]),
        top_posts="\n".join(p[:200] for p in top_posts[:5]),
        coordination_signals=json.dumps(coordination_signals or {}, ensure_ascii=False)[:300],
    )

    # 多次调用取多数投票
    all_events: list[list[dict]] = []
    for _ in range(num_samples):
        try:
            result = await _call_llm(prompt)
            events = _parse_events(result)
            all_events.append(events)
        except Exception:
            logger.warning("LLM call failed, skipping sample")

    if not all_events:
        return {"events": [], "llm_available": False}

    # 多数投票：保留出现在 >= 2/3 样本中的事件类型
    threshold = max(len(all_events) * 2 // 3, 1)
    type_counts: Counter[str] = Counter()
    type_evidence: dict[str, str] = {}
    type_confidence: dict[str, list[float]] = {}

    for sample in all_events:
        for ev in sample:
            t = ev.get("type", "none")
            type_counts[t] += 1
            if t not in type_evidence:
                type_evidence[t] = ev.get("evidence", "")
            type_confidence.setdefault(t, []).append(ev.get("confidence", 0.5))

    voted_events = []
    for t, count in type_counts.items():
        if count >= threshold and t != "none":
            voted_events.append({
                "type": t,
                "evidence": type_evidence.get(t, ""),
                "confidence": round(sum(type_confidence[t]) / len(type_confidence[t]), 2),
            })

    return {"events": voted_events, "llm_available": True}


async def _call_llm(prompt: str) -> str:
    """调用 OpenAI 兼容 API。"""
    api_key = getattr(settings, "LLM_API_KEY", "")
    api_base = getattr(settings, "LLM_API_BASE", "https://api.deepseek.com/v1")
    model = getattr(settings, "LLM_MODEL", "deepseek-chat")

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            f"{api_base}/chat/completions",
            headers={"Authorization": f"Bearer {api_key}"},
            json={
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.3,
                "response_format": {"type": "json_object"},
            },
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]


def _parse_events(raw: str) -> list[dict]:
    """解析 LLM 返回的 JSON，验证事件类型。"""
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return []

    events = data.get("events", [])
    valid = []
    for ev in events:
        if not isinstance(ev, dict):
            continue
        t = ev.get("type", "")
        if t in VALID_EVENT_TYPES:
            valid.append({
                "type": t,
                "evidence": str(ev.get("evidence", ""))[:200],
                "confidence": min(max(float(ev.get("confidence", 0.5)), 0.0), 1.0),
            })
    return valid
