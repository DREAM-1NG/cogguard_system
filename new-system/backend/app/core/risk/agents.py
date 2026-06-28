"""KT3 multi-agent baseline orchestration.

The first implementation is deterministic and dependency-free. Each function
keeps a stable agent-style contract so it can later be backed by LLM/RAG/model
calls without changing the service or report layer.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from statistics import mean
from typing import Any

from app.core.risk.harmful_detector import analyze_harmful_batch
from app.core.risk.stance_detector import analyze_stance_batch


FACT_REFUTE_TERMS = {"假的", "不实", "辟谣", "造谣", "谣言", "别信", "虚假", "伪造"}
FACT_SUPPORT_TERMS = {"属实", "证实", "确认", "官方通报", "已核实", "是真的", "实锤"}
FACT_QUERY_TERMS = {"求证", "有证据吗", "真的吗", "真的假的", "是否属实", "来源", "证据"}

HATE_TARGET_TERMS = {
    "gender": {"仇女", "仇男", "女拳", "田园女权"},
    "ethnicity": {"种族", "低等", "排外", "外地人", "地域黑"},
    "nationality": {"汉奸", "走狗", "卖国", "境外势力"},
    "identity_group": {"群体", "他们都", "这类人", "低端"},
}
DEHUMANIZATION_TERMS = {"畜生", "牲口", "虫子", "垃圾人", "低等"}
THREAT_TERMS = {"打死", "杀", "去死", "灭掉", "清除", "砍", "炸"}
COUNTER_NARRATIVE_TEMPLATES = {
    "hate": "避免攻击群体身份，围绕事实、个体行为和可验证证据进行澄清。",
    "violence": "优先提示平台审核暴力动员表达，并发布去激化说明。",
    "misleading": "补充权威来源和时间线，明确哪些说法尚无证据支持。",
    "mobilization": "降低扩散激励，提示用户在转发前核验来源。",
    "harassment": "引导讨论回到事实争议，避免点名骚扰和人身攻击。",
}


def _normalize_text(text: str) -> str:
    return " ".join(str(text or "").lower().split())


def _post_ref(post: dict) -> dict:
    return {
        "post_id": str(post.get("post_id", "")),
        "author_id": str(post.get("author_id", "")),
        "content": str(post.get("content", ""))[:220],
    }


def _score_from_hits(text: str, terms: set[str]) -> tuple[int, list[str]]:
    hits = sorted(term for term in terms if term in text)
    return len(hits), hits


def _top_labels(items: list[dict], field: str) -> dict:
    return dict(Counter(str(item.get(field, "unknown")) for item in items))


def run_fact_check_agent(posts: list[dict], target: str) -> list[dict]:
    """Run a lightweight claim/evidence/verdict pipeline over shared objects."""
    grouped: dict[str, list[dict]] = defaultdict(list)
    for post in posts:
        objects = [str(tag) for tag in post.get("hashtags", []) or [] if tag]
        url = str(post.get("url", "") or "")
        if url:
            objects.append(url)
        if not objects:
            objects.append(target or "当前话题")
        for obj in objects:
            grouped[obj].append(post)

    results: list[dict] = []
    for claim_id, claim_posts in sorted(grouped.items(), key=lambda item: len(item[1]), reverse=True)[:10]:
        support = refute = query = 0
        evidence: list[dict] = []
        for post in claim_posts[:8]:
            text = _normalize_text(str(post.get("content", "")))
            support_hits_count, support_hits = _score_from_hits(text, FACT_SUPPORT_TERMS)
            refute_hits_count, refute_hits = _score_from_hits(text, FACT_REFUTE_TERMS)
            query_hits_count, query_hits = _score_from_hits(text, FACT_QUERY_TERMS)
            support += support_hits_count
            refute += refute_hits_count
            query += query_hits_count
            hits = support_hits + refute_hits + query_hits
            if hits:
                evidence.append({
                    **_post_ref(post),
                    "matched_terms": hits[:6],
                    "source_type": "platform_post",
                })

        if refute > support and refute >= query:
            verdict = "refuted"
            explanation = "讨论中辟谣/不实信号占优，需优先核验原始来源。"
        elif support > refute and support >= query:
            verdict = "supported"
            explanation = "讨论中证实/属实信号占优，但仍需外部权威证据确认。"
        elif query > 0:
            verdict = "not_enough_evidence"
            explanation = "质疑和求证表达较多，当前证据不足。"
        else:
            verdict = "not_enough_evidence"
            explanation = "未发现足够事实性线索。"

        conflict = support > 0 and refute > 0
        if conflict:
            verdict = "conflicting"
            explanation = "支持与反驳线索同时存在，建议进入人工复核。"

        evidence_quality = min(0.95, 0.25 + len(evidence) * 0.08 + (0.12 if conflict else 0))
        results.append({
            "claim": claim_id,
            "target": target,
            "verdict": verdict,
            "confidence": round(evidence_quality, 4),
            "evidence_quality": round(evidence_quality, 4),
            "question_decomposition": [
                f"{claim_id} 是否有可靠来源支持？",
                f"{claim_id} 是否被辟谣或出现事实冲突？",
            ],
            "evidence": evidence[:5],
            "explanation": explanation,
            "agent": "FactCheck Agent",
        })

    return results


def run_hate_harm_agent(posts: list[dict]) -> list[dict]:
    """Detect hate, harassment, violence, mobilization, and toxicity signals."""
    harmful_results = analyze_harmful_batch(posts)
    by_post = {item["post_id"]: item for item in harmful_results}
    outputs: list[dict] = []
    for post in posts:
        post_id = str(post.get("post_id", ""))
        text = _normalize_text(str(post.get("content", "")))
        base = by_post.get(post_id, {})
        target_groups: list[str] = []
        rationale_terms: list[str] = []
        for group, terms in HATE_TARGET_TERMS.items():
            _, hits = _score_from_hits(text, terms)
            if hits:
                target_groups.append(group)
                rationale_terms.extend(hits)

        _, dehumanization_hits = _score_from_hits(text, DEHUMANIZATION_TERMS)
        _, threat_hits = _score_from_hits(text, THREAT_TERMS)
        rationale_terms.extend(dehumanization_hits + threat_hits)

        categories = list(base.get("categories", []))
        if target_groups and "hate" not in categories:
            categories.append("hate")
        if dehumanization_hits and "dehumanization" not in categories:
            categories.append("dehumanization")
        if threat_hits and "violence" not in categories:
            categories.append("violence")

        score = float(base.get("score", 0))
        if target_groups:
            score += 0.18
        if dehumanization_hits:
            score += 0.16
        if threat_hits:
            score += 0.2
        score = round(min(score, 1.0), 4)

        if score >= 0.65 or threat_hits:
            label = "harmful"
        elif score >= 0.25 or target_groups:
            label = "borderline"
        else:
            label = "safe"

        outputs.append({
            **_post_ref(post),
            "label": label,
            "score": score,
            "categories": categories,
            "target_groups": sorted(set(target_groups)),
            "rationales": sorted(set(rationale_terms + list(base.get("matched_terms", []))))[:8],
            "explanation": base.get("reason", "未发现明显有害表达"),
            "agent": "Hate/Harm Agent",
        })
    return outputs


def run_narrative_agent(posts: list[dict], target: str) -> list[dict]:
    """Classify stance and narrative action for each post."""
    stance_results = analyze_stance_batch(posts, target)
    outputs: list[dict] = []
    for item in stance_results:
        text = _normalize_text(str(item.get("content", "")))
        narrative_actions: list[str] = []
        if any(term in text for term in ("转发扩散", "必须转", "大家去", "一起冲")):
            narrative_actions.append("amplification")
        if any(term in text for term in ("别信", "辟谣", "求证", "有证据吗")):
            narrative_actions.append("correction_or_query")
        if any(term in text for term in ("内幕", "绝密", "曝光", "实锤")):
            narrative_actions.append("sensational_framing")
        if any(term in text for term in ("傻", "垃圾", "去死", "汉奸")):
            narrative_actions.append("attack_framing")
        if not narrative_actions:
            narrative_actions.append("discussion")
        outputs.append({
            "post_id": item["post_id"],
            "author_id": item["author_id"],
            "content": item["content"],
            "target": target,
            "stance": item["label"],
            "score": item["score"],
            "narrative_actions": narrative_actions,
            "explanation": item["reason"],
            "agent": "Stance/Narrative Agent",
        })
    return outputs


def judge_community_harmfulness(
    evidence_pack: dict,
    fact_check_results: list[dict],
    hate_results: list[dict],
    narrative_results: list[dict],
) -> dict:
    """Fuse post/account/community evidence into a KT3 harmfulness verdict."""
    content = evidence_pack["content_summary"]
    coordination = evidence_pack["coordination"]["summary"]
    accounts = evidence_pack["accounts"]
    propagation = evidence_pack["propagation"]["graph"]

    hate_ratio = 0.0
    if hate_results:
        hate_ratio = sum(1 for item in hate_results if item["label"] == "harmful") / len(hate_results)
    fact_conflict_ratio = 0.0
    if fact_check_results:
        fact_conflict_ratio = sum(
            1 for item in fact_check_results if item["verdict"] in {"refuted", "conflicting"}
        ) / len(fact_check_results)
    amplification_ratio = 0.0
    if narrative_results:
        amplification_ratio = sum(
            1 for item in narrative_results if "amplification" in item.get("narrative_actions", [])
        ) / len(narrative_results)

    score = 0.0
    score += content["harmful_ratio"] * 25
    score += hate_ratio * 25
    score += fact_conflict_ratio * 15
    score += min(coordination["coordinated_accounts"] / 8, 1) * 15
    score += min(propagation["edge_count"] / 10, 1) * 8
    score += min(accounts["avg_automation_score"] / 100, 1) * 7
    score += amplification_ratio * 5
    score = round(min(score, 100), 2)

    if score >= 75:
        level = "critical"
    elif score >= 55:
        level = "high"
    elif score >= 30:
        level = "medium"
    else:
        level = "low"

    categories = Counter()
    for item in hate_results:
        categories.update(item.get("categories", []))
    if fact_conflict_ratio > 0:
        categories["misleading_or_unverified"] += round(fact_conflict_ratio, 4)
    if amplification_ratio >= 0.2:
        categories["coordinated_amplification"] += round(amplification_ratio, 4)

    rationale: list[str] = []
    if hate_ratio >= 0.25:
        rationale.append("有害/仇恨内容在社区中占比较高")
    if fact_conflict_ratio >= 0.25:
        rationale.append("事实核查出现冲突或反驳信号")
    if coordination["coordinated_accounts"] >= 3:
        rationale.append("协同账号数量达到风险阈值")
    if accounts["avg_automation_score"] >= 45:
        rationale.append("账户群体存在自动化倾向")
    if amplification_ratio >= 0.2:
        rationale.append("叙事放大行为明显")
    if not rationale:
        rationale.append("当前 harmfulness 信号较弱")

    return {
        "level": level,
        "score": score,
        "verdict": "harmful_community" if level in {"high", "critical"} else "watchlist",
        "confidence": round(min(0.95, 0.35 + len(hate_results) / 120 + len(fact_check_results) * 0.04), 4),
        "harm_types": [item for item, _count in categories.most_common(6)],
        "post_level": {
            "harmful_ratio": content["harmful_ratio"],
            "hate_ratio": round(hate_ratio, 4),
            "fact_conflict_ratio": round(fact_conflict_ratio, 4),
        },
        "account_level": {
            "total_accounts": accounts["total_accounts"],
            "avg_automation_score": accounts["avg_automation_score"],
            "suspicious_accounts": accounts["suspicious_accounts"],
        },
        "community_level": {
            "coordinated_accounts": coordination["coordinated_accounts"],
            "coordinated_edges": coordination["coordinated_edges"],
            "propagation_edges": propagation["edge_count"],
            "amplification_ratio": round(amplification_ratio, 4),
        },
        "rationale": rationale,
        "agent": "Community Harm Judge",
    }


def build_agent_countermeasures(
    evidence_pack: dict,
    phase_result: dict,
    disarm_result: dict,
    fact_check_results: list[dict],
    hate_results: list[dict],
    community_harmfulness: dict,
) -> list[dict]:
    """Generate closed-loop countermeasures grounded in agent outputs."""
    recommendations: list[dict] = []
    fact_risky = [item for item in fact_check_results if item["verdict"] in {"refuted", "conflicting", "not_enough_evidence"}]
    hate_risky = [item for item in hate_results if item["label"] == "harmful"]

    if fact_risky:
        recommendations.append({
            "priority": "high" if any(item["verdict"] in {"refuted", "conflicting"} for item in fact_risky) else "medium",
            "action": "事实纠偏",
            "description": "围绕高传播 claim 补充权威来源、时间线和证据状态，避免将未证实信息包装为事实。",
            "grounding": [item["claim"] for item in fact_risky[:3]],
        })

    if hate_risky:
        common_categories = Counter(cat for item in hate_risky for cat in item.get("categories", []))
        narrative = COUNTER_NARRATIVE_TEMPLATES.get(common_categories.most_common(1)[0][0], COUNTER_NARRATIVE_TEMPLATES["hate"])
        recommendations.append({
            "priority": "high",
            "action": "反制叙事",
            "description": narrative,
            "grounding": [item["post_id"] for item in hate_risky[:5]],
            "safety_constraints": ["非攻击性", "证据支撑", "避免复述仇恨表达", "避免扩大传播"],
        })

    if community_harmfulness["level"] in {"high", "critical"}:
        recommendations.append({
            "priority": "high",
            "action": "社区级处置",
            "description": "对协同放大账户、关键传播节点和高风险帖子建立审核队列，并记录处置反馈用于优化。",
            "grounding": community_harmfulness["rationale"],
        })

    recommendations.append({
        "priority": "info",
        "action": "闭环优化",
        "description": "将人工复核结果、误判样本和处置效果写入优化集，用于更新决策规则、few-shot 示例和 agent 路由。",
        "grounding": disarm_result.get("predicted_next_steps", [])[:3] or [phase_result["phase_label"]],
    })
    return recommendations


def build_optimization_trace(
    *,
    requested_mode: str,
    used_mode: str,
    fact_check_results: list[dict],
    hate_results: list[dict],
    community_harmfulness: dict,
) -> dict:
    """Describe how the next optimization loop should use this run."""
    verdict_distribution = _top_labels(fact_check_results, "verdict")
    hate_distribution = _top_labels(hate_results, "label")
    confidences = [float(item.get("confidence", 0)) for item in fact_check_results]
    avg_fact_confidence = round(mean(confidences), 4) if confidences else 0.0

    failure_modes: list[str] = []
    if verdict_distribution.get("not_enough_evidence", 0):
        failure_modes.append("fact_evidence_gap")
    if verdict_distribution.get("conflicting", 0):
        failure_modes.append("fact_conflict")
    if community_harmfulness["confidence"] < 0.55:
        failure_modes.append("low_community_confidence")
    if hate_distribution.get("borderline", 0):
        failure_modes.append("borderline_hate_cases")
    if not failure_modes:
        failure_modes.append("no_major_failure_detected")

    return {
        "agent": "Optimization Agent",
        "requested_mode": requested_mode,
        "used_mode": used_mode,
        "strategy": "maro_style_rule_and_prompt_optimization",
        "feedback_sources": ["human_review", "false_positive_cases", "false_negative_cases", "countermeasure_outcomes"],
        "metrics_to_track": [
            "fact_check_verdict_f1",
            "evidence_quality",
            "hate_macro_f1",
            "target_group_f1",
            "community_harmfulness_accuracy",
            "countermeasure_helpfulness",
            "report_completeness",
        ],
        "observed_distributions": {
            "fact_verdicts": verdict_distribution,
            "hate_labels": hate_distribution,
            "avg_fact_confidence": avg_fact_confidence,
        },
        "failure_modes": failure_modes,
        "next_actions": [
            "收集人工复核标签并写入优化样本池",
            "为失败模式补充 few-shot 示例",
            "更新 Judge 决策规则并在跨事件验证集上回归",
        ],
    }


def build_evidence_table(
    fact_check_results: list[dict],
    hate_results: list[dict],
    narrative_results: list[dict],
) -> list[dict]:
    """Flatten key agent evidence into a report-friendly table."""
    rows: list[dict] = []
    narrative_by_post = {item["post_id"]: item for item in narrative_results}
    for item in hate_results[:20]:
        narrative = narrative_by_post.get(item["post_id"], {})
        rows.append({
            "scope": "post",
            "id": item["post_id"],
            "agent": item["agent"],
            "label": item["label"],
            "score": item["score"],
            "stance": narrative.get("stance", ""),
            "evidence": "；".join(item.get("rationales", [])[:5]),
            "content": item.get("content", ""),
        })
    for item in fact_check_results[:10]:
        rows.append({
            "scope": "claim",
            "id": item["claim"],
            "agent": item["agent"],
            "label": item["verdict"],
            "score": item["confidence"],
            "stance": "",
            "evidence": item["explanation"],
            "content": item["claim"],
        })
    return rows


def run_kt3_agent_workflow(
    *,
    posts: list[dict],
    target: str,
    evidence_pack: dict,
    phase_result: dict,
    disarm_result: dict,
    requested_mode: str,
    enable_fact_check: bool = True,
    enable_hate_detection: bool = True,
) -> dict[str, Any]:
    """Run the KT3 detection-response-optimization agent workflow."""
    fact_check_results = run_fact_check_agent(posts, target) if enable_fact_check else []
    hate_results = run_hate_harm_agent(posts) if enable_hate_detection else []
    narrative_results = run_narrative_agent(posts, target)
    community_harmfulness = judge_community_harmfulness(
        evidence_pack=evidence_pack,
        fact_check_results=fact_check_results,
        hate_results=hate_results,
        narrative_results=narrative_results,
    )
    evidence_table = build_evidence_table(fact_check_results, hate_results, narrative_results)
    optimization_trace = build_optimization_trace(
        requested_mode=requested_mode,
        used_mode="agent",
        fact_check_results=fact_check_results,
        hate_results=hate_results,
        community_harmfulness=community_harmfulness,
    )
    return {
        "fact_check_results": fact_check_results,
        "hate_results": hate_results,
        "narrative_results": narrative_results,
        "community_harmfulness": community_harmfulness,
        "evidence_table": evidence_table,
        "optimization_trace": optimization_trace,
        "agent_trace": [
            {"agent": "FactCheck Agent", "status": "enabled" if enable_fact_check else "disabled"},
            {"agent": "Hate/Harm Agent", "status": "enabled" if enable_hate_detection else "disabled"},
            {"agent": "Stance/Narrative Agent", "status": "enabled"},
            {"agent": "Community Harm Judge", "status": "enabled"},
            {"agent": "Optimization Agent", "status": "enabled"},
        ],
    }
