"""结构化风险报告生成。"""

from __future__ import annotations

from datetime import datetime, timezone


def build_risk_report(
    *,
    report_id: str,
    platform: str | None,
    keyword: str | None,
    target: str,
    evidence_pack: dict,
    phase_result: dict,
    disarm_result: dict,
    recommendations: list[dict],
    llm_result: dict,
) -> dict:
    """组装结构化研判报告。"""
    created_at = datetime.now(timezone.utc).isoformat()
    content = evidence_pack["content_summary"]
    overview = (
        f"围绕“{target}”共分析 {content['total_posts']} 条帖子，"
        f"其中 harmful 占比 {content['harmful_ratio']:.0%}，"
        f"当前处于{phase_result['phase_label']}，风险等级为 {phase_result['risk_level']}。"
    )

    return {
        "report_id": report_id,
        "created_at": created_at,
        "platform": platform or "all",
        "keyword": keyword or "",
        "target": target,
        "status": "completed",
        "executive_summary": overview,
        "input_overview": {
            "platform": platform or "all",
            "keyword": keyword or "",
            "total_posts": content["total_posts"],
            "total_accounts": evidence_pack["accounts"]["total_accounts"],
        },
        "harmful_content": {
            "distribution": content["harmful_distribution"],
            "top_posts": evidence_pack["top_posts"],
        },
        "stance_analysis": {
            "target": target,
            "distribution": content["stance_distribution"],
        },
        "risk_assessment": phase_result,
        "disarm_assessment": disarm_result,
        "evidence": {
            "coordination": evidence_pack["coordination"],
            "propagation": evidence_pack["propagation"],
            "accounts": evidence_pack["accounts"],
        },
        "countermeasures": recommendations,
        "llm_enhancement": llm_result,
        "appendix": {
            "top_claims": evidence_pack["propagation"]["claims"],
            "timeline": evidence_pack["propagation"]["timeline"],
        },
    }
