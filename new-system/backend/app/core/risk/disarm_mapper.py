"""证据到 DISARM 风格战术映射。"""

from __future__ import annotations


def map_to_disarm(evidence_pack: dict, phase_result: dict) -> dict:
    """将证据映射为简化版 DISARM 战术/技术。"""
    content = evidence_pack["content_summary"]
    coordination = evidence_pack["coordination"]["summary"]
    accounts = evidence_pack["accounts"]

    techniques: list[dict] = []
    next_steps: list[str] = []

    if coordination["coordinated_accounts"] >= 3:
        techniques.append({
            "tactic": "TA06 Amplify",
            "technique": "Coordinated Amplification",
            "score": 0.82,
            "reason": "多个账号围绕共享对象同步扩散",
        })
        next_steps.append("继续扩大相同话题或链接的协同扩散")

    if accounts["avg_automation_score"] >= 45:
        techniques.append({
            "tactic": "TA03 Develop",
            "technique": "Inauthentic Persona Usage",
            "score": 0.68,
            "reason": "账户群体存在明显自动化倾向",
        })
        next_steps.append("使用高频账号维持传播热度")

    if content["harmful_ratio"] >= 0.25:
        techniques.append({
            "tactic": "TA08 Harass",
            "technique": "Abusive Messaging",
            "score": 0.74,
            "reason": "文本中出现较多攻击性或煽动性表达",
        })
        next_steps.append("升级为更强烈的攻击性表达或煽动话术")

    if content["support_ratio"] >= 0.35:
        techniques.append({
            "tactic": "TA04 Seed",
            "technique": "Narrative Seeding",
            "score": 0.61,
            "reason": "支持性表态占比较高，叙事正在被持续灌输",
        })

    if not techniques:
        techniques.append({
            "tactic": "TA01 Observe",
            "technique": "Weak Signal Monitoring",
            "score": 0.35,
            "reason": "当前仅检测到弱风险信号",
        })
        next_steps.append("继续试探话题传播与群体响应")

    return {
        "phase": phase_result["phase"],
        "mapped_techniques": techniques,
        "predicted_next_steps": next_steps[:3],
        "summary": "；".join(item["technique"] for item in techniques[:3]),
    }
