"""KT3 manual-agent report contracts and prompt builders.

This module owns role names, report sections, safety flags, and prompt payloads
for the analyst-triggered KT3 Agent workflow. Runtime orchestration remains in
``kt3_agent_review``; prompt contracts live here.
"""

from __future__ import annotations

from typing import Any
import json

from app.core.risk.kt3_propagation_agent import PROPAGATION_AGENT_REPORT_SECTIONS
from app.core.risk.kt3_propagation_agent import build_propagation_agent_output_contract
from app.core.risk.kt3_propagation_agent import build_propagation_agent_prompt_note


AGENT_REPORT_SECTIONS: dict[str, list[str]] = {
    "PostHarmAgent": [
        "帖子内容概览",
        "Detector 结论回顾",
        "Harm 类型与目标对象分析",
        "证据充分性",
        "需要人工确认的问题",
    ],
    "MultimodalConsistencyAgent": [
        "媒体预处理输入说明",
        "跨模态一致性",
        "图文/音视冲突",
        "语境错配风险",
        "组合语义 harmfulness",
        "需补充证据",
    ],
    "ClaimEvidenceAgent": [
        "Claim 摘要",
        "帖子立场",
        "已有证据",
        "证据缺口",
        "是否足以支撑 harmfulness 研判",
        "建议检索方向",
    ],
    "PropagationTreeAgent": PROPAGATION_AGENT_REPORT_SECTIONS,
    "QuestionReflectionAgent": [
        "已发现冲突",
        "缺失证据",
        "必须回答的问题",
        "建议补充调用/检索",
        "若不补证据的风险",
    ],
    "HarmfulnessJudgeAgent": [
        "专家报告综述",
        "证据强弱",
        "建议性 harmfulness 判断",
        "能力边界",
        "人工确认项",
        "是否建议进入反制",
    ],
    "CountermeasureAgent": [
        "可用证据",
        "事实纠错方向",
        "降扩散/人审建议",
        "反叙事草案",
        "不能说什么/安全注意",
    ],
}

__all__ = [
    "AGENT_REPORT_SECTIONS",
    "build_agent_output_contract",
    "build_agent_system_prompt",
    "build_agent_user_prompt",
    "build_default_report_role",
    "build_reflection_response_prompt",
    "build_report_role_name",
    "build_revision_system_prompt",
    "build_revision_user_prompt",
    "build_safety_flags",
]


def build_agent_system_prompt(agent_name: str) -> str:
    sections = "\n".join(f"- {section}" for section in AGENT_REPORT_SECTIONS[agent_name])
    judge_policy_note = (
        "\nFor HarmfulnessJudgeAgent: explicitly read selected_context.active_policy "
        "when present. Explain which policy thresholds/rule explanations support "
        "review, abstain, retrieval, or countermeasure recommendations, and state "
        "that the policy is advisory until human approval. Produce a unified "
        "Chinese governance review report for platform analysts, covering risk "
        "type, evidence, disputes, recommended action, public platform reference "
        "basis, and human confirmation items.\n"
        if agent_name == "HarmfulnessJudgeAgent"
        else ""
    )
    countermeasure_note = (
        "\nFor CountermeasureAgent: output internal governance recommendations only. "
        "Do not write public-facing propaganda or auto-publication copy. Recommend "
        "actions such as evidence supplementation, human review, labeling, reduced "
        "distribution, debunking recommendation, account review, victim protection, "
        "or quality-content support only when evidence supports them. Read active policy, "
        "accepted rule references, and error memory summary when present.\n"
        if agent_name == "CountermeasureAgent"
        else ""
    )
    reflection_note = (
        "\nFor QuestionReflectionAgent: read active policy, accepted rule refs, and "
        "error memory summary. Ask questions that target repeated failure modes, "
        "missing evidence, and cross-modal or claim conflicts.\n"
        if agent_name == "QuestionReflectionAgent"
        else ""
    )
    optimizer_note = (
        "\nDecision rule optimization is not a selectable judgement role here. "
        "If policy context is present, cite it as provenance rather than changing it.\n"
    )
    return (
        "You are a MARO-style social media governance review expert. "
        "Write a role-specific natural-language analysis report in Chinese for "
        "platform governance analysts. Use public platform community rules, "
        "transparency report structure, and enforcement vocabulary only as "
        "reference templates; never treat them as automatic legal or enforcement "
        "authority. "
        "Do not output JSON as the main report. Do not claim to be the final "
        "automatic classifier. Separate evidence from uncertainty and make clear "
        "what requires human confirmation. Cite the supplied governance_reference "
        "categories or state that no direct platform template matches.\n\n"
        f"Agent: {agent_name}\n"
        "Required report sections:\n"
        f"{sections}\n"
        f"{judge_policy_note}"
        f"{countermeasure_note}"
        f"{reflection_note}"
        f"{build_propagation_agent_prompt_note(agent_name)}"
        f"{optimizer_note}"
    )


def build_agent_output_contract(agent_name: str) -> dict[str, Any]:
    return build_propagation_agent_output_contract(agent_name)


def build_agent_user_prompt(
    agent_name: str,
    context: dict[str, Any],
    reports_by_agent: dict[str, dict[str, Any]],
    *,
    policy_guidance: dict[str, Any],
) -> str:
    prior_reports = {
        name: {
            "status": item.get("status"),
            "report_text": item.get("report_text"),
        }
        for name, item in reports_by_agent.items()
    }
    payload = {
        "agent_name": agent_name,
        "task_boundary": (
            "This is an analyst-triggered review. Produce a natural-language "
            "analysis report only; do not publish content and do not overwrite "
            "the system verdict."
        ),
        "policy_guidance": policy_guidance,
        "error_memory_summary": context.get("error_memory_summary") or {},
        "output_contract": build_agent_output_contract(agent_name),
        "selected_context": context,
        "prior_agent_reports": prior_reports,
    }
    return json.dumps(payload, ensure_ascii=False, default=str)


def build_reflection_response_prompt(
    agent_name: str,
    context: dict[str, Any],
    reports_by_agent: dict[str, dict[str, Any]],
) -> str:
    expert_report = reports_by_agent.get(agent_name) or {}
    reflection_report = reports_by_agent.get("QuestionReflectionAgent") or {}
    payload = {
        "agent_name": agent_name,
        "task_boundary": (
            "This is the MARO question-reflection response step. Revise or "
            "supplement your original analysis in natural language only."
        ),
        "original_expert_report": {
            "status": expert_report.get("status"),
            "analysis_report": expert_report.get("analysis_report"),
            "report_text": expert_report.get("report_text"),
        },
        "question_reflection_report": {
            "status": reflection_report.get("status"),
            "analysis_report": reflection_report.get("analysis_report"),
            "report_text": reflection_report.get("report_text"),
        },
        "selected_context": context,
        "error_memory_summary": context.get("error_memory_summary") or {},
        "expected_response": [
            "which reflection questions affect the original analysis",
            "what evidence remains missing",
            "whether any original conclusion should be softened",
            "what the Judge should treat as uncertain",
        ],
    }
    return json.dumps(payload, ensure_ascii=False, default=str)


def build_safety_flags(agent_name: str) -> list[str]:
    flags = ["human_confirmation_required", "not_a_classifier_output"]
    if agent_name == "CountermeasureAgent":
        flags.extend(["no_auto_publish", "evidence_bound_countermeasure"])
    if agent_name == "HarmfulnessJudgeAgent":
        flags.append("advisory_judgement_only")
    return flags


def build_report_role_name(agent_name: str, stage: str) -> str:
    if agent_name == "HarmfulnessJudgeAgent":
        return {
            "draft": "judge_draft",
            "critique": "judge_critique",
            "final": "judge_final",
        }.get(stage, "judge_final")
    if agent_name == "CountermeasureAgent":
        return {
            "draft": "countermeasure_draft",
            "critique": "countermeasure_critique",
            "final": "countermeasure_final",
        }.get(stage, "countermeasure_final")
    return "expert_initial"


def build_default_report_role(agent_name: str) -> str:
    if agent_name == "QuestionReflectionAgent":
        return "reflection"
    if agent_name == "HarmfulnessJudgeAgent":
        return "judge_final"
    if agent_name == "CountermeasureAgent":
        return "countermeasure_final"
    return "expert_initial"


def build_revision_system_prompt(agent_name: str, revision_kind: str) -> str:
    if revision_kind == "critique":
        return (
            f"You are reviewing the draft report of {agent_name}. "
            "Write a Chinese critique focused on missing evidence, unsupported inference, "
            "policy misuse, uncertainty handling, and what should be revised. "
            "Do not output JSON."
        )
    return (
        f"You are revising the {agent_name} draft after critique. "
        "Write a stronger Chinese final report that explicitly addresses the critique, "
        "keeps evidence and uncertainty separate, follows active policy as advisory context, "
        "and does not claim automatic classifier authority."
    )


def build_revision_user_prompt(
    *,
    agent_name: str,
    revision_kind: str,
    source_report: dict[str, Any],
    context: dict[str, Any],
    reports_by_agent: dict[str, dict[str, Any]],
    policy_guidance: dict[str, Any],
    critique_report: dict[str, Any] | None = None,
) -> str:
    payload = {
        "agent_name": agent_name,
        "revision_kind": revision_kind,
        "selected_context": context,
        "policy_guidance": policy_guidance,
        "error_memory_summary": context.get("error_memory_summary") or {},
        "source_report": {
            "report_role": source_report.get("report_role"),
            "status": source_report.get("status"),
            "report_text": source_report.get("report_text"),
            "analysis_report": source_report.get("analysis_report"),
        },
        "critique_report": {
            "report_role": (critique_report or {}).get("report_role"),
            "status": (critique_report or {}).get("status"),
            "report_text": (critique_report or {}).get("report_text"),
        }
        if critique_report
        else None,
        "prior_agent_reports": {
            name: {"status": item.get("status"), "report_text": item.get("report_text")}
            for name, item in reports_by_agent.items()
        },
    }
    return json.dumps(payload, ensure_ascii=False, default=str)
