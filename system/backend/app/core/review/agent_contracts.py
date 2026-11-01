"""Review manual-agent report contracts and prompt builders.

This module owns role names, report sections, safety flags, and prompt payloads
for analyst-triggered Review agents. Runtime orchestration remains in
``agent_review``; prompt contracts live here.
"""

from __future__ import annotations

from typing import Any
import json

from pydantic import BaseModel, Field

from app.core.review.propagation_agent import PROPAGATION_AGENT_REPORT_SECTIONS
from app.core.review.propagation_agent import build_propagation_agent_output_contract
from app.core.review.propagation_agent import build_propagation_agent_prompt_note


class ClaimEvidenceBundle(BaseModel):
    claims: list[str] = Field(default_factory=list, description="帖子中提取的核心主张")
    supporting_evidence: list[str] = Field(default_factory=list, description="支撑该主张的事实证据")
    contradicting_evidence: list[str] = Field(default_factory=list, description="反驳该主张的事实证据")
    evidence_gap: str = Field(default="", description="目前缺失的证据")


class CompliancePolicyBundle(BaseModel):
    active_policies: list[str] = Field(default_factory=list, description="适用的社区安全规则")
    violation_risk: str = Field(default="", description="违反规则的潜在风险说明")


class JudgeRationaleBundle(BaseModel):
    risk_type: str = Field(description="判定的最终风险类型 (如 hate_speech, misinformation)")
    confidence: float = Field(ge=0.0, le=1.0, description="判定置信度 (0.0 到 1.0)")
    rationale_report: str = Field(description="自然语言研判报告 (此字段将用于 SBERT 向量化蒸馏)")
    human_confirmation_required: bool = Field(description="是否必须人工介入")


AGENT_REPORT_SECTIONS: dict[str, list[str]] = {
    "PostHarmAgent": [
        "帖子内容概览",
        "检测结论复核",
        "危害类型与目标对象分析",
        "证据充分性",
        "需要人工确认的问题",
    ],
    "MultimodalConsistencyAgent": [
        "媒体输入状态",
        "跨模态一致性",
        "图文或音视冲突",
        "语境错配风险",
        "综合危害语义",
        "需要补充的证据",
    ],
    "ClaimEvidenceAgent": [
        "主张摘要",
        "帖子态度",
        "已有证据",
        "证据缺口",
        "危害性支撑",
        "建议取证方向",
    ],
    "PropagationTreeAgent": PROPAGATION_AGENT_REPORT_SECTIONS,
    "QuestionReflectionAgent": [
        "已发现的矛盾",
        "缺失证据",
        "必须回答的问题",
        "建议补充的检索或工具核验",
        "证据不足时继续裁决的风险",
    ],
    "HarmfulnessJudgeAgent": [
        "专家报告综合",
        "证据强度",
        "建议性危害判断",
        "能力边界",
        "人工确认项",
        "治理建议准备度",
    ],
    "CountermeasureAgent": [
        "可用证据",
        "事实纠偏方向",
        "降权或人工复核建议",
        "反制文本边界",
        "安全约束",
    ],
}

__all__ = [
    "AGENT_REPORT_SECTIONS",
    "ClaimEvidenceBundle",
    "CompliancePolicyBundle",
    "JudgeRationaleBundle",
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
    if agent_name == "ClaimEvidenceAgent":
        return ClaimEvidenceBundle.model_json_schema()
    if agent_name == "HarmfulnessJudgeAgent":
        return JudgeRationaleBundle.model_json_schema()
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
        "task_boundary": "这是分析员触发的复核任务。只生成自然语言分析报告，不发布内容，不覆盖系统判定。",
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
        "task_boundary": "这是问题追问后的专家补充步骤。只用自然语言修订或补充原分析。",
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
            "哪些追问会影响原始分析",
            "仍然缺少哪些证据",
            "哪些原始结论需要降低确定性",
            "裁决阶段应将哪些内容视为不确定",
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
