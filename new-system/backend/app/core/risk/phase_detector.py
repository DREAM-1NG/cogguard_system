"""风险阶段与等级评估。"""

from __future__ import annotations


PHASE_LABELS = {
    "seed": "播种期",
    "coordination": "协同期",
    "breakout": "扩散期",
    "response": "对抗期",
    "decay": "衰减期",
}


def _risk_level(score: float) -> str:
    if score >= 75:
        return "critical"
    if score >= 55:
        return "high"
    if score >= 30:
        return "medium"
    return "low"


def assess_risk_phase(evidence_pack: dict) -> dict:
    """根据证据包评估风险阶段。"""
    content = evidence_pack["content_summary"]
    coordination = evidence_pack["coordination"]["summary"]
    propagation = evidence_pack["propagation"]["graph"]
    accounts = evidence_pack["accounts"]

    harmful_ratio = content["harmful_ratio"]
    support_ratio = content["support_ratio"]
    deny_ratio = content["deny_ratio"]
    query_ratio = content["query_ratio"]
    coordinated_accounts = coordination["coordinated_accounts"]
    coordinated_edges = coordination["coordinated_edges"]
    propagation_edges = propagation["edge_count"]
    avg_automation = accounts["avg_automation_score"]
    total_posts = content["total_posts"]

    risk_score = 0.0
    risk_score += harmful_ratio * 40
    risk_score += min(coordinated_accounts / 10, 1) * 20
    risk_score += min(coordinated_edges / 10, 1) * 10
    risk_score += min(propagation_edges / 10, 1) * 12
    risk_score += min(avg_automation / 100, 1) * 12
    risk_score += support_ratio * 10
    risk_score -= min(deny_ratio * 6 + query_ratio * 4, 8)
    risk_score = max(0.0, min(risk_score, 100.0))

    if total_posts <= 5 and harmful_ratio < 0.2:
        phase = "seed"
    elif coordinated_accounts >= 4 or coordinated_edges >= 3:
        phase = "coordination"
    elif propagation_edges >= 5 or harmful_ratio >= 0.35 or risk_score >= 65:
        phase = "breakout"
    elif deny_ratio + query_ratio >= support_ratio and total_posts >= 8:
        phase = "response"
    else:
        phase = "decay"

    breakout_likelihood = round(min(0.95, 0.2 + harmful_ratio * 0.6 + coordinated_edges * 0.04), 4)
    confidence = round(min(0.95, 0.3 + total_posts / 50 + coordinated_accounts / 20), 4)

    rationale = []
    if harmful_ratio >= 0.3:
        rationale.append("有害内容占比较高")
    if coordinated_accounts >= 4:
        rationale.append("检测到明显协同行为")
    if propagation_edges >= 5:
        rationale.append("传播链条已形成")
    if avg_automation >= 45:
        rationale.append("存在较高自动化倾向")
    if deny_ratio + query_ratio >= support_ratio and total_posts >= 8:
        rationale.append("讨论进入质疑/回应阶段")
    if not rationale:
        rationale.append("当前风险信号较弱，仍需持续监测")

    return {
        "phase": phase,
        "phase_label": PHASE_LABELS[phase],
        "risk_score": round(risk_score, 2),
        "risk_level": _risk_level(risk_score),
        "confidence": confidence,
        "breakout_likelihood": breakout_likelihood,
        "rationale": rationale,
    }
