"""Review manual-agent report contracts and compact prompt builders."""

from __future__ import annotations

from typing import Any
import json

from app.core.review.propagation_agent import PROPAGATION_AGENT_REPORT_SECTIONS
from app.core.review.propagation_agent import build_propagation_agent_output_contract
from app.core.review.propagation_agent import build_propagation_agent_prompt_note
from app.core.review.agent_policy import adjudicate_policy
from app.core.review.agent_policy import normalize_rule_provenance


MAX_PROMPT_TEXT_CHARS = 2_000
JUDGE_DECISION_BEGIN = "<REVIEW_JUDGE_DECISION>"
JUDGE_DECISION_END = "</REVIEW_JUDGE_DECISION>"
JUDGE_AXIS_LABELS = {"harmful", "non_harmful", "uncertain", "unavailable"}
JUDGE_STANCE_LABELS = {"support", "deny", "query", "neutral", "unlinked", "uncertain"}

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
    "parse_judge_decision_footer",
    "validate_judge_decision_against_policy",
]


def build_agent_system_prompt(agent_name: str) -> str:
    sections = "\n".join(f"- {section}" for section in AGENT_REPORT_SECTIONS[agent_name])
    judge_policy_note = (
        "\nDETERMINISTIC POLICY DECISION FRAME: read policy_decision_frame before writing conclusions. "
        "Cite active policy id, threshold comparisons, accepted rules, weighted expert evidence references, "
        "and historical failure cautions. Do not invent a policy result.\n"
        "For HarmfulnessJudgeAgent: use policy only as advisory provenance until human approval. "
        "After the Chinese report, append exactly one machine-readable decision footer between "
        f"{JUDGE_DECISION_BEGIN} and {JUDGE_DECISION_END}. The footer must be strict JSON with "
        "main_axes.attack_hate_offense, main_axes.misinfo_claim_risk, stance, review_required, "
        "review_reason, and fine_labels. Each axis contains available, label, and confidence. "
        "Use label harmful, non_harmful, uncertain, or unavailable; never infer unavailable axes.\n"
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
    if agent_name == "HarmfulnessJudgeAgent":
        return {
            "main_output": "natural_language_chinese_report",
            "machine_footer": {
                "begin": JUDGE_DECISION_BEGIN,
                "end": JUDGE_DECISION_END,
                "schema": {
                    "main_axes": {
                        "attack_hate_offense": {"available": "bool", "label": "enum", "confidence": "0..1"},
                        "misinfo_claim_risk": {"available": "bool", "label": "enum", "confidence": "0..1"},
                    },
                    "stance": {"available": "bool", "label": "enum", "confidence": "0..1"},
                    "review_required": "bool",
                    "review_reason": "list[str]",
                    "fine_labels": "list[str]",
                },
            },
        }
    return build_propagation_agent_output_contract(agent_name)


def parse_judge_decision_footer(report_text: str) -> tuple[str, dict[str, Any] | None, str | None]:
    """Separate and validate the Judge's distillation-only decision footer."""
    text = str(report_text or "").strip()
    begin = text.rfind(JUDGE_DECISION_BEGIN)
    end = text.rfind(JUDGE_DECISION_END)
    if begin < 0 or end < begin:
        return text, None, "missing_judge_decision_footer"
    footer_text = text[begin + len(JUDGE_DECISION_BEGIN) : end].strip()
    clean_text = (text[:begin] + text[end + len(JUDGE_DECISION_END) :]).strip()
    try:
        raw = json.loads(footer_text)
    except (TypeError, ValueError, json.JSONDecodeError):
        return clean_text, None, "invalid_judge_decision_json"
    if not isinstance(raw, dict):
        return clean_text, None, "invalid_judge_decision_schema"

    axes = raw.get("main_axes")
    if not isinstance(axes, dict):
        return clean_text, None, "invalid_judge_decision_axes"
    normalized_axes: dict[str, dict[str, Any]] = {}
    for axis_name in ("attack_hate_offense", "misinfo_claim_risk"):
        axis = axes.get(axis_name)
        if not isinstance(axis, dict):
            return clean_text, None, f"missing_judge_axis:{axis_name}"
        available = _strict_bool(axis.get("available"))
        if available is None:
            return clean_text, None, f"invalid_judge_axis_available:{axis_name}"
        label = str(axis.get("label") or "unavailable").strip().lower()
        if label not in JUDGE_AXIS_LABELS or (not available and label != "unavailable"):
            return clean_text, None, f"invalid_judge_axis_label:{axis_name}"
        confidence = _bounded_confidence(axis.get("confidence"))
        if confidence is None:
            return clean_text, None, f"invalid_judge_axis_confidence:{axis_name}"
        normalized_axes[axis_name] = {
            "available": available,
            "label": label,
            "confidence": confidence,
        }

    stance = raw.get("stance")
    if not isinstance(stance, dict):
        return clean_text, None, "invalid_judge_stance"
    stance_available = _strict_bool(stance.get("available"))
    if stance_available is None:
        return clean_text, None, "invalid_judge_stance_available"
    stance_label = str(stance.get("label") or "unlinked").strip().lower()
    if stance_label not in JUDGE_STANCE_LABELS:
        return clean_text, None, "invalid_judge_stance_label"
    stance_confidence = _bounded_confidence(stance.get("confidence"))
    if stance_confidence is None:
        return clean_text, None, "invalid_judge_stance_confidence"

    review_required = _strict_bool(raw.get("review_required"))
    if review_required is None:
        return clean_text, None, "invalid_judge_review_required"

    return clean_text, {
        "schema_version": "review-judge-teacher-prediction-v1",
        "main_axes": normalized_axes,
        "stance": {
            "available": stance_available,
            "label": stance_label,
            "confidence": stance_confidence,
        },
        "review_required": review_required,
        "review_reason": _string_list(raw.get("review_reason")),
        "fine_labels": _string_list(raw.get("fine_labels")),
    }, None


def validate_judge_decision_against_policy(
    teacher_prediction: dict[str, Any] | None,
    policy_decision_frame: dict[str, Any] | None,
) -> dict[str, Any]:
    """Audit an LLM Judge footer against deterministic advisory policy gates."""
    prediction = teacher_prediction if isinstance(teacher_prediction, dict) else {}
    frame = policy_decision_frame if isinstance(policy_decision_frame, dict) else {}
    recommendation = frame.get("policy_recommendation") or {}
    recommendation = recommendation if isinstance(recommendation, dict) else {}
    judge_review_required = bool(prediction.get("review_required"))
    policy_review_required = bool(recommendation.get("review_required"))
    policy_abstain = bool(recommendation.get("abstain"))
    conflict_reasons: list[str] = []
    if policy_review_required and not judge_review_required:
        conflict_reasons.append("judge_rejected_required_review")
    if policy_abstain and not judge_review_required:
        conflict_reasons.append("judge_rejected_required_abstention")
    return {
        "schema_version": "review-policy-judge-alignment-v1",
        "advisory_only": bool(frame.get("advisory_only", True)),
        "conflict_detected": bool(conflict_reasons),
        "conflict_reasons": conflict_reasons,
        "judge_review_required": judge_review_required,
        "policy_review_required": policy_review_required,
        "policy_abstain": policy_abstain,
        "effective_review_required": bool(
            judge_review_required or policy_review_required or policy_abstain
        ),
        "detector_outputs_modified": False,
    }


def _bounded_confidence(value: Any) -> float | None:
    try:
        confidence = float(value)
    except (TypeError, ValueError):
        return None
    if not 0.0 <= confidence <= 1.0:
        return None
    return round(confidence, 6)


def _strict_bool(value: Any) -> bool | None:
    return value if type(value) is bool else None


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def build_agent_user_prompt(
    agent_name: str,
    context: dict[str, Any],
    reports_by_agent: dict[str, dict[str, Any]],
    *,
    policy_guidance: dict[str, Any],
) -> str:
    memory_enabled = agent_name in {"QuestionReflectionAgent", "HarmfulnessJudgeAgent", "CountermeasureAgent"}
    selected_context = context if memory_enabled else {
        key: value for key, value in context.items() if key != "error_memory_summary"
    }
    payload = {
        "agent_name": agent_name,
        "task_boundary": "这是分析员触发的复核任务。只生成自然语言分析报告，不发布内容，不覆盖系统判定。",
        "policy_guidance": _compact_prompt_value(policy_guidance),
        "output_contract": build_agent_output_contract(agent_name),
        "selected_context": _compact_prompt_value(selected_context),
        "prior_agent_reports": _compact_prior_reports(reports_by_agent),
    }
    if memory_enabled:
        payload["error_memory_summary"] = _compact_prompt_value(context.get("error_memory_summary") or {})
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
    footer_note = (
        f" Append the strict JSON decision footer between {JUDGE_DECISION_BEGIN} and {JUDGE_DECISION_END}."
        if agent_name == "HarmfulnessJudgeAgent"
        else ""
    )
    return (
        f"Revise the {agent_name} draft in Chinese after critique, preserving evidence/uncertainty separation "
        f"and advisory policy limits.{footer_note}"
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
    envelope = envelope if isinstance(envelope, dict) else {}
    completed_experts = [
        agent_name
        for agent_name, report in reports_by_agent.items()
        if report.get("status") == "completed"
    ]
    adjudication = adjudicate_policy(
        envelope,
        case_score=context.get("case_score"),
        uncertainty=context.get("case_uncertainty"),
        trigger_facts=context.get("policy_trigger_facts") or {},
        completed_experts=completed_experts,
    )
    policy_binding = bool(adjudication.get("policy_binding"))
    accepted_rules = []
    if policy_binding:
        for rule in envelope.get("candidate_rules") or []:
            if not isinstance(rule, dict) or rule.get("status") not in {"accepted_for_round", "activated"}:
                continue
            provenance = normalize_rule_provenance(rule)
            accepted_rules.append(
                {
                    **provenance,
                    "explanation": str(rule.get("description") or rule.get("rationale") or ""),
                    "status": rule.get("status"),
                }
            )
    weights = (adjudication.get("expert_coverage") or {}).get("applicable_weights") or {}
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
    recommendations = adjudication.get("recommendations") or {}
    frame = {
        "schema_version": "review-policy-adjudication-frame-v1",
        "active_policy_id": envelope.get("policy_id"),
        "activation_status": envelope.get("activation_status"),
        "policy_binding": policy_binding,
        "advisory_only": True,
        "observed_case": {
            "score": context.get("case_score"),
            "uncertainty": context.get("case_uncertainty"),
            "trigger_facts": context.get("policy_trigger_facts") or {},
        },
        "threshold_comparisons": adjudication.get("threshold_comparisons") or {},
        "matched_trigger_conditions": adjudication.get("trigger_matches") or {},
        "matched_accepted_rules": accepted_rules,
        "expert_weight_coverage": adjudication.get("expert_coverage") or {},
        "weighted_expert_contribution_refs": contributions,
        "historical_failure_memory_cautions": cautions,
        "matched_failure_memory": memory.get("matched_records") or [],
        "failure_memory_match_reasons": memory.get("match_reasons") or [],
        "ignored_failure_memory_count": int(memory.get("ignored_count") or 0),
        "policy_recommendation": {
            "review_required": bool(recommendations.get("review")),
            "retrieval_required": bool(recommendations.get("retrieval")),
            "abstain": bool(recommendations.get("abstain")),
            "countermeasure_recommended": bool(recommendations.get("countermeasure")),
        },
        "policy_evidence_conflict": adjudication.get("conflict") or {},
        "policy_provenance": adjudication.get("policy_provenance") or {},
        "detector_outputs_modified": False,
    }
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
    suffix = "...[truncated]"
    return f"{text[: MAX_PROMPT_TEXT_CHARS - len(suffix)]}{suffix}"
