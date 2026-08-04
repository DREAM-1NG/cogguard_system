"""Review manual-agent report contracts and compact prompt builders."""

from __future__ import annotations

from typing import Any
import json

from app.core.review.propagation_agent import PROPAGATION_AGENT_REPORT_SECTIONS
from app.core.review.propagation_agent import build_propagation_agent_output_contract
from app.core.review.propagation_agent import build_propagation_agent_prompt_note


MAX_PROMPT_TEXT_CHARS = 2_000

AGENT_REPORT_SECTIONS: dict[str, list[str]] = {
    "PostHarmAgent": ["帖子内容摘要", "检测结论复核", "危害类型与目标对象分析", "证据充分性", "需要人工确认的问题"],
    "MultimodalConsistencyAgent": ["媒体输入状态", "跨模态一致性", "图文或音视频冲突", "语境错配风险", "综合危害语义", "需要补充的证据"],
    "ClaimEvidenceAgent": ["主张摘要", "帖子立场", "已有证据", "证据缺口", "危害性支持", "建议取证方向"],
    "PropagationTreeAgent": PROPAGATION_AGENT_REPORT_SECTIONS,
    "QuestionReflectionAgent": ["已发现的矛盾", "缺失证据", "必须回答的问题", "建议补充的检索或工具核验", "证据不足时继续裁决的风险"],
    "HarmfulnessJudgeAgent": ["专家报告综合", "证据强度", "建议性危害判断", "能力边界", "人工确认项", "治理建议准备度"],
    "CountermeasureAgent": ["可用证据", "事实纠偏方向", "降权或人工复核建议", "反制文本边界", "安全约束"],
}

__all__ = [
    "AGENT_REPORT_SECTIONS",
    "build_agent_output_contract",
    "build_agent_system_prompt",
    "build_agent_user_prompt",
    "build_policy_decision_frame",
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
        "\nDETERMINISTIC POLICY DECISION FRAME: read policy_decision_frame before writing conclusions. "
        "Cite active policy id, threshold comparisons, accepted rules, weighted expert evidence references, "
        "and historical failure cautions. Do not invent a policy result.\n"
        "For HarmfulnessJudgeAgent: use policy only as advisory provenance until human approval.\n"
        if agent_name == "HarmfulnessJudgeAgent"
        else ""
    )
    countermeasure_note = (
        "\nFor CountermeasureAgent: make internal, evidence-bound recommendations only; never draft public "
        "propaganda or auto-publication copy.\n"
        if agent_name == "CountermeasureAgent"
        else ""
    )
    reflection_note = (
        "\nFor QuestionReflectionAgent: ask questions about repeated failures, missing evidence, and conflicts. "
        "Name relevant expert agents when a response is needed.\n"
        if agent_name == "QuestionReflectionAgent"
        else ""
    )
    return (
        "You are a MARO-style social media governance review expert. Write a role-specific natural-language "
        "analysis report in Chinese for platform governance analysts. Treat public platform rules as reference "
        "templates, never automatic legal authority. Do not output JSON as the main report or claim final "
        "classifier authority. Separate evidence, uncertainty, and human confirmation.\n\n"
        f"Agent: {agent_name}\nRequired report sections:\n{sections}\n{judge_policy_note}{countermeasure_note}"
        f"{reflection_note}{build_propagation_agent_prompt_note(agent_name)}\n"
        "Policy optimization is not a selectable judgement role; cite policy provenance without changing it.\n"
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
    payload = {
        "agent_name": agent_name,
        "task_boundary": "这是分析员触发的复核任务。只生成自然语言分析报告，不发布内容，不覆盖系统判定。",
        "policy_guidance": _compact_prompt_value(policy_guidance),
        "error_memory_summary": _compact_prompt_value(context.get("error_memory_summary") or {}),
        "output_contract": build_agent_output_contract(agent_name),
        "selected_context": _compact_prompt_value(context),
        "prior_agent_reports": _compact_prior_reports(reports_by_agent),
    }
    if agent_name == "HarmfulnessJudgeAgent":
        payload["policy_decision_frame"] = build_policy_decision_frame(context, reports_by_agent)
    return json.dumps(payload, ensure_ascii=False, default=str)


def build_reflection_response_prompt(
    agent_name: str,
    context: dict[str, Any],
    reports_by_agent: dict[str, dict[str, Any]],
) -> str:
    expert_report = reports_by_agent.get(agent_name) or {}
    reflection_report = reports_by_agent.get("QuestionReflectionAgent") or {}
    return json.dumps(
        {
            "agent_name": agent_name,
            "task_boundary": "这是问题追问后的专家补充步骤。只用自然语言修订或补充原分析。",
            "original_expert_report": _compact_prior_report(expert_report),
            "question_reflection_report": _compact_prior_report(reflection_report),
            "selected_context": _compact_prompt_value(context),
            "error_memory_summary": _compact_prompt_value(context.get("error_memory_summary") or {}),
            "expected_response": ["哪些追问影响原始分析", "仍缺少哪些证据", "哪些结论需要降低确定性", "裁决阶段应视为何种不确定性"],
        },
        ensure_ascii=False,
        default=str,
    )


def build_safety_flags(agent_name: str) -> list[str]:
    flags = ["human_confirmation_required", "not_a_classifier_output"]
    if agent_name == "CountermeasureAgent":
        flags.extend(["no_auto_publish", "evidence_bound_countermeasure"])
    if agent_name == "HarmfulnessJudgeAgent":
        flags.append("advisory_judgement_only")
    return flags


def build_report_role_name(agent_name: str, stage: str) -> str:
    if agent_name == "HarmfulnessJudgeAgent":
        return {"draft": "judge_draft", "critique": "judge_critique", "final": "judge_final"}.get(stage, "judge_final")
    if agent_name == "CountermeasureAgent":
        return {"draft": "countermeasure_draft", "critique": "countermeasure_critique", "final": "countermeasure_final"}.get(stage, "countermeasure_final")
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
        return f"Review the {agent_name} draft in Chinese for missing evidence, unsupported inference, policy misuse, and uncertainty. Do not output JSON."
    return f"Revise the {agent_name} draft in Chinese after critique, preserving evidence/uncertainty separation and advisory policy limits."


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
    return json.dumps(
        {
            "agent_name": agent_name,
            "revision_kind": revision_kind,
            "selected_context": _compact_prompt_value(context),
            "policy_guidance": _compact_prompt_value(policy_guidance),
            "error_memory_summary": _compact_prompt_value(context.get("error_memory_summary") or {}),
            "source_report": _compact_prior_report(source_report),
            "critique_report": _compact_prior_report(critique_report or {}) if critique_report else None,
            "prior_agent_reports": _compact_prior_reports(reports_by_agent),
        },
        ensure_ascii=False,
        default=str,
    )


def build_policy_decision_frame(context: dict[str, Any], reports_by_agent: dict[str, dict[str, Any]]) -> dict[str, Any]:
    envelope = context.get("active_policy") or context.get("policy") or {}
    policy = envelope.get("policy") if isinstance(envelope, dict) and isinstance(envelope.get("policy"), dict) else envelope
    policy = policy if isinstance(policy, dict) else {}
    thresholds = {
        "review": {"threshold": policy.get("review_threshold")},
        "abstain": {"threshold": policy.get("abstain_threshold")},
        "retrieval": {"threshold": policy.get("retrieval_threshold")},
        "countermeasure": {"threshold": policy.get("countermeasure_threshold")},
    }
    accepted_rules = [
        {"rule_id": rule.get("rule_id"), "explanation": rule.get("description")}
        for rule in (envelope.get("candidate_rules") or [])
        if isinstance(rule, dict) and rule.get("status") in {"accepted_for_round", "activated"}
    ]
    weights = policy.get("agent_weights") or {}
    contributions = []
    for agent_name, report in reports_by_agent.items():
        if report.get("status") != "completed" or agent_name not in weights:
            continue
        contributions.append(
            {
                "agent_name": agent_name,
                "weight": weights[agent_name],
                "evidence_refs": (report.get("system_audit_sidecar") or {}).get("evidence_refs") or [],
            }
        )
    memory = context.get("error_memory_summary") or {}
    cautions = memory.get("historical_failure_cautions") or memory.get("cautions") or []
    frame = {
        "active_policy_id": envelope.get("policy_id") if isinstance(envelope, dict) else None,
        "threshold_comparisons": thresholds,
        "matched_accepted_rules": accepted_rules,
        "weighted_expert_contribution_refs": contributions,
        "historical_failure_memory_cautions": cautions,
    }
    case_score = context.get("case_score")
    uncertainty = context.get("case_uncertainty")
    if case_score is not None:
        frame["case_score"] = case_score
    if uncertainty is not None:
        frame["case_uncertainty"] = uncertainty
    return frame


def _compact_prior_reports(reports_by_agent: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {name: _compact_prior_report(item) for name, item in reports_by_agent.items()}


def _compact_prior_report(report: dict[str, Any]) -> dict[str, Any]:
    return {
        "status": report.get("status"),
        "report_text": _truncate_text(report.get("report_text")),
        "evidence_refs": _compact_prompt_value((report.get("system_audit_sidecar") or {}).get("evidence_refs") or []),
    }


def _compact_prompt_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: _compact_prompt_value(item)
            for key, item in value.items()
            if key not in {"data_url", "base64", "image_base64", "payload_base64"}
        }
    if isinstance(value, list):
        return [_compact_prompt_value(item) for item in value]
    if isinstance(value, tuple):
        return [_compact_prompt_value(item) for item in value]
    if isinstance(value, str):
        if value.strip().lower().startswith("data:") or "base64," in value.lower():
            return "[omitted binary payload]"
        return _truncate_text(value)
    return value


def _truncate_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value)
    if len(text) <= MAX_PROMPT_TEXT_CHARS:
        return text
    return f"{text[:MAX_PROMPT_TEXT_CHARS]}...[truncated]"
