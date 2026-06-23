"""启发式有害内容检测。

首版目标是优先可运行、可解释，后续可替换为训练/微调模型。
"""

from __future__ import annotations

from collections import defaultdict

CATEGORY_TERMS: dict[str, set[str]] = {
    "violence": {"打死", "杀", "干掉", "灭掉", "冲塔", "砍", "炸", "围攻", "清除"},
    "harassment": {"傻", "蠢", "垃圾", "滚", "去死", "废物", "汉奸", "走狗", "脑残"},
    "hate": {"仇恨", "极端", "种族", "歧视", "排外", "仇女", "仇男", "低等"},
    "misleading": {"内幕", "实锤", "绝密", "曝光", "造谣", "谣言", "洗地", "操控", "带节奏"},
    "mobilization": {"转发扩散", "必须转", "立即行动", "一起冲", "大家去", "封杀", "抵制", "举报他"},
}

CATEGORY_WEIGHTS = {
    "violence": 0.32,
    "harassment": 0.22,
    "hate": 0.22,
    "misleading": 0.16,
    "mobilization": 0.12,
}

SEVERE_TERMS = {"打死", "杀", "炸", "去死", "灭掉", "清除"}


def _normalize_text(text: str) -> str:
    return " ".join((text or "").lower().split())


def analyze_harmful_content(text: str) -> dict:
    """分析单条文本的有害程度。"""
    normalized = _normalize_text(text)
    matched_terms: dict[str, list[str]] = defaultdict(list)
    score = 0.0

    for category, terms in CATEGORY_TERMS.items():
        for term in terms:
            if term in normalized:
                matched_terms[category].append(term)
                score += CATEGORY_WEIGHTS[category]

    punctuation_boost = 0.05 * normalized.count("!") + 0.05 * normalized.count("！")
    score += min(punctuation_boost, 0.1)

    severe_hit = any(term in normalized for term in SEVERE_TERMS)
    if severe_hit:
        score += 0.18
    score = min(score, 1.0)
    unique_terms = sorted({term for values in matched_terms.values() for term in values})

    if severe_hit or score >= 0.6:
        label = "harmful"
    elif score >= 0.22:
        label = "borderline"
    else:
        label = "safe"

    categories = [category for category, values in matched_terms.items() if values]
    reason = "未发现明显有害表达"
    if unique_terms:
        reason = f"命中风险词: {', '.join(unique_terms[:5])}"

    return {
        "label": label,
        "score": round(score, 4),
        "categories": categories,
        "matched_terms": unique_terms,
        "reason": reason,
    }


def analyze_harmful_batch(posts: list[dict]) -> list[dict]:
    """批量分析帖子有害内容。"""
    results: list[dict] = []
    for post in posts:
        analyzed = analyze_harmful_content(str(post.get("content", "")))
        results.append({
            "post_id": str(post.get("post_id", "")),
            "author_id": str(post.get("author_id", "")),
            "content": str(post.get("content", "")),
            **analyzed,
        })
    return results
