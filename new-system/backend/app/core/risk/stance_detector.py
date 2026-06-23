"""启发式立场检测。

首版采用 claim/target-aware 的轻量规则方案，输出 support / deny / query / comment。
"""

from __future__ import annotations

from collections import Counter

SUPPORT_TERMS = {"支持", "属实", "是真的", "确实", "转发扩散", "必须重视", "同意", "赞成"}
DENY_TERMS = {"假的", "不实", "辟谣", "别信", "不是这样", "造谣", "谣言", "假的吧"}
QUERY_TERMS = {"真的吗", "真的假的", "求证", "是否属实", "有证据吗", "?", "？", "为什么", "怎么回事"}
COMMENT_TERMS = {"围观", "路过", "看法", "有点意思", "吃瓜", "关注"}


def _normalize_text(text: str) -> str:
    return " ".join((text or "").lower().split())


def _clean_target_text(text: str) -> str:
    cleaned = str(text or "").strip()
    if cleaned.startswith("#") and cleaned.endswith("#") and len(cleaned) > 2:
        cleaned = cleaned[1:-1]
    return cleaned.strip("# ")


def derive_stance_target(posts: list[dict], explicit_target: str | None = None, fallback_keyword: str | None = None) -> str:
    """推导立场目标。"""
    if explicit_target:
        cleaned = _clean_target_text(explicit_target)
        if cleaned:
            return cleaned
    if fallback_keyword:
        cleaned = _clean_target_text(fallback_keyword)
        if cleaned:
            return cleaned

    hashtags: list[str] = []
    for post in posts:
        for tag in post.get("hashtags", []) or []:
            cleaned = _clean_target_text(str(tag))
            if cleaned:
                hashtags.append(cleaned)

    if hashtags:
        return Counter(hashtags).most_common(1)[0][0]
    return "当前话题"


def detect_stance(text: str, target: str) -> dict:
    """识别文本对指定目标的立场。"""
    normalized = _normalize_text(text)
    scores = {
        "support": 0.0,
        "deny": 0.0,
        "query": 0.0,
        "comment": 0.05,
    }

    for term in SUPPORT_TERMS:
        if term in normalized:
            scores["support"] += 0.3
    for term in DENY_TERMS:
        if term in normalized:
            scores["deny"] += 0.35
    for term in QUERY_TERMS:
        if term in normalized:
            scores["query"] += 0.28
    for term in COMMENT_TERMS:
        if term in normalized:
            scores["comment"] += 0.15

    if target and target != "当前话题" and target in normalized:
        for key in ("support", "deny", "query"):
            scores[key] += 0.08

    label = max(scores.items(), key=lambda item: item[1])[0]
    confidence = min(round(max(scores.values()), 4), 0.95)
    if confidence < 0.2:
        label = "comment"
        confidence = 0.2

    reason_terms: list[str] = []
    for group in (SUPPORT_TERMS, DENY_TERMS, QUERY_TERMS, COMMENT_TERMS):
        for term in group:
            if term in normalized:
                reason_terms.append(term)
    reason = "未发现明确立场词，默认归为 comment"
    if reason_terms:
        reason = f"命中立场词: {', '.join(reason_terms[:5])}"

    return {
        "target": target,
        "label": label,
        "score": confidence,
        "reason": reason,
    }


def analyze_stance_batch(posts: list[dict], target: str) -> list[dict]:
    """批量分析帖子立场。"""
    results: list[dict] = []
    for post in posts:
        analyzed = detect_stance(str(post.get("content", "")), target)
        results.append({
            "post_id": str(post.get("post_id", "")),
            "author_id": str(post.get("author_id", "")),
            "content": str(post.get("content", "")),
            **analyzed,
        })
    return results
