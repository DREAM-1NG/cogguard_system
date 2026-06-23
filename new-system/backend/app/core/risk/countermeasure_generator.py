"""反制建议生成。"""

from __future__ import annotations


def generate_countermeasures(evidence_pack: dict, phase_result: dict, disarm_result: dict) -> list[dict]:
    """根据证据和阶段生成反制建议。"""
    content = evidence_pack["content_summary"]
    coordination = evidence_pack["coordination"]["summary"]
    accounts = evidence_pack["accounts"]

    recommendations: list[dict] = []

    if content["harmful_ratio"] >= 0.25:
        recommendations.append({
            "priority": "high",
            "action": "内容处置",
            "description": "优先审核并标记高风险帖子，对明显攻击性或煽动性内容进行限流/删除。",
        })

    if coordination["coordinated_accounts"] >= 3:
        recommendations.append({
            "priority": "high",
            "action": "协同账号监测",
            "description": "对高频同步账号建立重点观察名单，复核其共享链接、标签和发文时间窗。",
        })

    if accounts["avg_automation_score"] >= 45:
        recommendations.append({
            "priority": "medium",
            "action": "账号处置",
            "description": "对自动化倾向较高的账户执行二次校验，必要时限制互动能力。",
        })

    if content["query_ratio"] + content["deny_ratio"] >= 0.3:
        recommendations.append({
            "priority": "medium",
            "action": "澄清引导",
            "description": "发布澄清信息并集中回应高频质疑点，降低不确定性传播。",
        })

    if phase_result["phase"] == "breakout":
        recommendations.append({
            "priority": "high",
            "action": "应急响应",
            "description": "进入扩散期，建议启动加密监测频率并同步平台与运营团队快速处置。",
        })

    if not recommendations:
        recommendations.append({
            "priority": "low",
            "action": "持续观察",
            "description": "当前风险较低，维持常规监测并记录话题演化。",
        })

    recommendations.append({
        "priority": "info",
        "action": "预测下一步",
        "description": "潜在下一步动作：" + "；".join(disarm_result["predicted_next_steps"][:2]),
    })
    return recommendations
