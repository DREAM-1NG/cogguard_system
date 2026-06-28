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
    agent_outputs: dict | None = None,
    report_format: str = "json",
) -> dict:
    """组装结构化研判报告。"""
    created_at = datetime.now(timezone.utc).isoformat()
    content = evidence_pack["content_summary"]
    agent_outputs = agent_outputs or {}
    overview = (
        f"围绕“{target}”共分析 {content['total_posts']} 条帖子，"
        f"其中 harmful 占比 {content['harmful_ratio']:.0%}，"
        f"当前处于{phase_result['phase_label']}，风险等级为 {phase_result['risk_level']}。"
    )

    report = {
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
        "fact_check_results": agent_outputs.get("fact_check_results", []),
        "hate_results": agent_outputs.get("hate_results", []),
        "narrative_results": agent_outputs.get("narrative_results", []),
        "community_harmfulness": agent_outputs.get("community_harmfulness", {}),
        "optimization_trace": agent_outputs.get("optimization_trace", {}),
        "evidence_table": agent_outputs.get("evidence_table", []),
        "agent_trace": agent_outputs.get("agent_trace", []),
        "report_format": report_format,
        "appendix": {
            "top_claims": evidence_pack["propagation"]["claims"],
            "timeline": evidence_pack["propagation"]["timeline"],
        },
    }
    if report_format == "markdown":
        report["markdown_report"] = _build_markdown_report(report)
    elif report_format == "pdf":
        report["pdf_report"] = {
            "status": "renderer_not_configured",
            "reason": "当前环境未配置 PDF 渲染依赖，已返回结构化 JSON 报告。",
        }
    return report


def _build_markdown_report(report: dict) -> str:
    """Build a compact Markdown report for export/preview."""
    assessment = report.get("risk_assessment", {})
    community = report.get("community_harmfulness", {})
    lines = [
        f"# KT3 风险研判报告 {report.get('report_id', '')}",
        "",
        f"- 目标话题：{report.get('target', '')}",
        f"- 风险等级：{assessment.get('risk_level', '')}",
        f"- 风险阶段：{assessment.get('phase_label', '')}",
        f"- 社区 harmfulness：{community.get('level', '未启用')}",
        "",
        "## 执行摘要",
        report.get("executive_summary", ""),
        "",
        "## 事实核查",
    ]
    for item in report.get("fact_check_results", [])[:5]:
        lines.append(f"- `{item.get('verdict')}` {item.get('claim')}: {item.get('explanation')}")
    if not report.get("fact_check_results"):
        lines.append("- 未启用或未发现可核查 claim。")

    lines.extend(["", "## 有害/仇恨语言"])
    for item in report.get("hate_results", [])[:5]:
        lines.append(f"- `{item.get('label')}` {item.get('post_id')}: {', '.join(item.get('categories', []))}")
    if not report.get("hate_results"):
        lines.append("- 未启用或未发现可分析内容。")

    lines.extend(["", "## 反制建议"])
    for item in report.get("countermeasures", [])[:6]:
        lines.append(f"- `{item.get('priority')}` {item.get('action')}: {item.get('description')}")

    return "\n".join(lines)
