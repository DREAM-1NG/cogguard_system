"""Manual MARO-style KT3 LLM agent review.

This module is intentionally separate from the deterministic KT3 review queue.
It only runs when an analyst explicitly selects posts/trees and agents. The
agent output is a natural-language analysis report with minimal audit metadata;
it is not a classifier output and should not be used to fit benchmark labels.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
from typing import Any, Protocol
from uuid import uuid4
import asyncio
import base64
import json
from pathlib import Path

import httpx

from app.core.risk.kt3_active_retrieval import ActiveEvidenceProvider
from app.core.risk.kt3_active_retrieval import build_full_debate_trace
from app.core.risk.kt3_active_retrieval import build_light_debate_trace
from app.core.risk.kt3_active_retrieval import build_sidecar_for_agent
from app.core.risk.kt3_active_retrieval import retrieve_active_evidence
from app.core.risk.kt3_active_retrieval import should_trigger_light_debate


AGENT_ORDER = (
    "PostHarmAgent",
    "MultimodalConsistencyAgent",
    "ClaimEvidenceAgent",
    "PropagationTreeAgent",
    "QuestionReflectionAgent",
    "HarmfulnessJudgeAgent",
    "CountermeasureAgent",
)

EXPERT_AGENTS = {
    "PostHarmAgent",
    "MultimodalConsistencyAgent",
    "ClaimEvidenceAgent",
    "PropagationTreeAgent",
}

FOLLOWUP_AGENTS = (
    "QuestionReflectionAgent",
    "HarmfulnessJudgeAgent",
    "CountermeasureAgent",
)

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
    "PropagationTreeAgent": [
        "传播树结构概览",
        "关键分支",
        "Stance 演化",
        "异常放大迹象",
        "与 harmfulness 的关系",
        "需人工核验节点",
    ],
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

AGENT_METHOD_TRACE = [
    {
        "paper": "MARO, EMNLP 2025",
        "transfer": (
            "Use role-specific expert analysis reports, question-reflection, "
            "and a judge-style synthesis instead of a single automatic classifier."
        ),
    },
    {
        "paper": "RAMA, 2025",
        "transfer": (
            "Treat claim/evidence work as multimodal query construction and "
            "evidence sufficiency review."
        ),
    },
    {
        "paper": "MAD-Sherlock, 2024/2025",
        "transfer": (
            "Use multimodal context-mismatch review for image/video evidence "
            "instead of relying only on text or metadata."
        ),
    },
    {
        "paper": "D2D, EMNLP 2025",
        "transfer": (
            "Keep debate/reflection outputs as analyst-facing reports and avoid "
            "unsafe automatic publication of debunking content."
        ),
    },
]


class KT3LLMAgentProvider(Protocol):
    """Pluggable provider for tests or alternate LLM backends."""

    async def __call__(
        self,
        *,
        agent_name: str,
        system_prompt: str,
        user_prompt: str,
        input_bundle: dict[str, Any],
        model: str,
    ) -> str:
        ...


@dataclass(frozen=True)
class OpenAICompatibleConfig:
    api_key: str
    base_url: str
    model: str
    wire_api: str = "chat_completions"
    timeout_seconds: float = 60.0
    include_media_base64: bool = False
    require_vision: bool = False


class OpenAICompatibleAgentProvider:
    """Minimal OpenAI-compatible provider with chat and Responses support."""

    def __init__(self, config: OpenAICompatibleConfig):
        self.config = config

    async def __call__(
        self,
        *,
        agent_name: str,
        system_prompt: str,
        user_prompt: str,
        input_bundle: dict[str, Any],
        model: str,
    ) -> str:
        if not self.config.api_key:
            raise RuntimeError("LLM API key is not configured")
        payload_model = model or self.config.model
        wire_api = _normalize_wire_api(self.config.wire_api)
        if wire_api == "responses":
            url = self.config.base_url.rstrip("/") + "/responses"
            payload = _openai_responses_payload(
                system_prompt,
                user_prompt,
                input_bundle,
                model=payload_model,
            )
        else:
            url = self.config.base_url.rstrip("/") + "/chat/completions"
            payload = {
                "model": payload_model,
                "messages": _openai_messages(system_prompt, user_prompt, input_bundle),
                "temperature": 0.2,
            }
        headers = {"Authorization": f"Bearer {self.config.api_key}"}
        async with httpx.AsyncClient(timeout=self.config.timeout_seconds) as client:
            response = await client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()
        if wire_api == "responses":
            return _extract_responses_text(data, agent_name)
        choices = data.get("choices") or []
        if not choices:
            raise RuntimeError(f"{agent_name} returned no choices")
        message = choices[0].get("message") or {}
        content = message.get("content")
        if isinstance(content, list):
            return "\n".join(str(item.get("text") or item) for item in content)
        if not isinstance(content, str) or not content.strip():
            raise RuntimeError(f"{agent_name} returned an empty report")
        return content.strip()


async def run_manual_kt3_agent_review(
    *,
    report: dict[str, Any],
    agent_names: list[str],
    case_id: str | None = None,
    selected_post_ids: list[str] | None = None,
    selected_tree_ids: list[str] | None = None,
    human_triggered_by: int | str = 0,
    provider: KT3LLMAgentProvider | None = None,
    model: str = "",
    provider_name: str = "openai-compatible",
    include_media_base64: bool = False,
    max_keyframes: int = 4,
    enable_active_retrieval: bool = False,
    enable_light_debate: bool = False,
    enable_full_debate: bool = False,
    debate_max_rounds: int = 3,
    retrieval_top_k: int = 3,
    active_retriever: ActiveEvidenceProvider | None = None,
    external_retrieval_enabled: bool = False,
    policy: dict[str, Any] | None = None,
    require_vision: bool = False,
) -> dict[str, Any]:
    """Run analyst-triggered natural-language KT3 agent reports."""
    normalized_agents = _normalize_agent_names(agent_names)
    existing_reviews = _as_list(report.get("agent_reviews"))
    context = _build_agent_context(
        report,
        case_id=case_id,
        selected_post_ids=selected_post_ids or [],
        selected_tree_ids=selected_tree_ids or [],
        include_media_base64=include_media_base64,
        max_keyframes=max_keyframes,
    )
    context["policy"] = policy or {}
    context["active_policy"] = policy or {}
    retrieval_bundle = (
        await retrieve_active_evidence(
            context=context,
            top_k=retrieval_top_k,
            external_provider=active_retriever,
            external_enabled=external_retrieval_enabled,
        )
        if enable_active_retrieval
        else None
    )
    if retrieval_bundle is not None:
        context["active_retrieval"] = retrieval_bundle
    debate_triggered, debate_reasons = should_trigger_light_debate(
        context=context,
        retrieval_bundle=retrieval_bundle,
    )
    if enable_full_debate and debate_triggered:
        debate_bundle = await build_full_debate_trace(
            context=context,
            retrieval_bundle=retrieval_bundle,
            reasons=debate_reasons,
            provider=provider,
            model=model,
            max_rounds=debate_max_rounds,
        )
    else:
        debate_bundle = (
            build_light_debate_trace(
                context=context,
                retrieval_bundle=retrieval_bundle,
                reasons=debate_reasons,
            )
            if enable_light_debate and debate_triggered
            else {"schema_version": "kt3-light-debate-v1", "triggered": False, "reasons": debate_reasons}
        )
    context["debate_trace"] = debate_bundle
    context["full_debate"] = debate_bundle if debate_bundle.get("schema_version") == "kt3-full-debate-v1" else None
    context["light_debate"] = debate_bundle if debate_bundle.get("schema_version") == "kt3-light-debate-v1" else None
    context["debate_mode"] = debate_bundle.get("debate_mode") or (
        "full_debate" if debate_bundle.get("schema_version") == "kt3-full-debate-v1" else "light_debate"
    )
    run_id = str(uuid4())
    created_at = _utc_now()
    input_hash = _hash_payload(
        {
            "report_id": report.get("report_id"),
            "case_id": case_id,
            "agents": normalized_agents,
            "selected_post_ids": selected_post_ids or [],
            "selected_tree_ids": selected_tree_ids or [],
            "enable_active_retrieval": enable_active_retrieval,
            "enable_light_debate": enable_light_debate,
            "enable_full_debate": enable_full_debate,
            "debate_max_rounds": debate_max_rounds,
            "policy_id": (policy or {}).get("policy_id"),
            "context": context,
        }
    )

    state = {
        "run_id": run_id,
        "created_at": created_at,
        "provider_name": provider_name,
        "model": model,
        "human_triggered_by": str(human_triggered_by),
        "input_hash": input_hash,
        "retrieval_bundle": retrieval_bundle,
        "debate_bundle": debate_bundle,
        "require_vision": require_vision,
        "enable_full_debate": enable_full_debate,
    }
    reports_by_agent = {
        str(item.get("agent_name")): item
        for item in existing_reviews
        if isinstance(item, dict) and item.get("status") == "completed"
    }

    results: list[dict[str, Any]] = []
    expert_agents = [agent for agent in normalized_agents if agent in EXPERT_AGENTS]
    followup_agents = [agent for agent in normalized_agents if agent in FOLLOWUP_AGENTS]

    expert_results = await _run_agent_batch(
        expert_agents,
        context=context,
        reports_by_agent=reports_by_agent,
        provider=provider,
        state=state,
    )
    results.extend(expert_results)
    reports_by_agent.update(_completed_by_agent(expert_results))

    if "QuestionReflectionAgent" in followup_agents:
        [reflection_result] = await _run_agent_batch(
            ["QuestionReflectionAgent"],
            context=context,
            reports_by_agent=reports_by_agent,
            provider=provider,
            state=state,
        )
        results.append(reflection_result)
        reports_by_agent.update(_completed_by_agent([reflection_result]))
        reflection_responses = await _run_reflection_response_batch(
            expert_agents,
            context=context,
            reports_by_agent=reports_by_agent,
            provider=provider,
            state=state,
        )
        results.extend(reflection_responses)
        reports_by_agent.update(_completed_by_agent(reflection_responses))

    for agent in ("HarmfulnessJudgeAgent", "CountermeasureAgent"):
        if agent not in followup_agents:
            continue
        [result] = await _run_agent_batch(
            [agent],
            context=context,
            reports_by_agent=reports_by_agent,
            provider=provider,
            state=state,
        )
        results.append(result)
        reports_by_agent.update(_completed_by_agent([result]))

    audit = {
        "run_id": run_id,
        "created_at": created_at,
        "agent_names": normalized_agents,
        "case_id": case_id,
        "human_triggered_by": str(human_triggered_by),
        "input_refs": context["input_refs"],
        "input_hash": input_hash,
        "provider_name": provider_name,
        "model": model,
        "method_trace": AGENT_METHOD_TRACE,
        "active_retrieval": retrieval_bundle,
        "light_debate": debate_bundle,
        "full_debate": debate_bundle if debate_bundle.get("schema_version") == "kt3-full-debate-v1" else None,
        "policy_id": (policy or {}).get("policy_id"),
        "capability_boundary": {
            "manual_human_triggered": True,
            "not_a_classifier": True,
            "fits_benchmark_labels": False,
            "natural_language_reports": True,
            "failure_policy": "record_failure_without_synthetic_report",
            "active_retrieval_default_external": False,
            "policy_does_not_modify_detector_outputs": True,
            "strict_vision_required": require_vision,
            "full_debate_optional": True,
            "full_debate_high_conflict_only": True,
            "maro_question_reflection_loop": "expert_reports_then_reflection_then_expert_response",
        },
    }
    return {
        "schema_version": "kt3-manual-agent-review-v1",
        "audit": audit,
        "input_bundle": context,
        "agent_reports": results,
        "active_retrieval": retrieval_bundle,
        "light_debate": debate_bundle,
        "full_debate": debate_bundle if debate_bundle.get("schema_version") == "kt3-full-debate-v1" else None,
        "summary": {
            "requested_agents": len(normalized_agents),
            "completed": sum(1 for item in results if item.get("status") == "completed"),
            "failed": sum(1 for item in results if item.get("status") == "failed"),
            "active_retrieval_used": retrieval_bundle is not None,
            "light_debate_triggered": bool(debate_bundle.get("triggered")),
            "full_debate_triggered": bool(
                debate_bundle.get("triggered") and debate_bundle.get("schema_version") == "kt3-full-debate-v1"
            ),
            "reflection_response_reports": sum(
                1 for item in results if item.get("report_role") == "reflection_response"
            ),
            "report_ids": [item.get("review_id") for item in results],
        },
    }


def build_llm_provider_from_settings(settings: Any) -> OpenAICompatibleAgentProvider | None:
    api_key = str(getattr(settings, "LLM_API_KEY", "") or "")
    if not api_key:
        return None
    config = OpenAICompatibleConfig(
        api_key=api_key,
        base_url=str(getattr(settings, "LLM_API_BASE", "") or "https://api.deepseek.com/v1"),
        model=str(getattr(settings, "LLM_MODEL", "") or "deepseek-chat"),
        wire_api=str(getattr(settings, "LLM_API_WIRE", "") or "chat_completions"),
        include_media_base64=bool(getattr(settings, "LLM_INCLUDE_MEDIA_BASE64", False)),
        require_vision=bool(getattr(settings, "LLM_REQUIRE_VISION", False)),
    )
    return OpenAICompatibleAgentProvider(config)


def agent_review_suggestions(report: dict[str, Any]) -> dict[str, Any]:
    """Build human-facing agent suggestions without calling an LLM."""
    kt3 = report.get("kt3_harmfulness") or {}
    review_queue = kt3.get("review_queue") or {}
    review_items = _as_list(review_queue.get("review_items"))
    posts = _semantic_posts(report.get("post_semantics") or {})

    suggested: list[dict[str, Any]] = []
    if review_items:
        suggested.append(
            {
                "agent_name": "PostHarmAgent",
                "reason": "post-level review queue has uncertain or high-risk harmfulness items",
                "source": "review_queue",
            }
        )
    if any(_post_has_multimodal_conflict(post) for post in posts):
        suggested.append(
            {
                "agent_name": "MultimodalConsistencyAgent",
                "reason": "selected posts include cross-view conflict or missing decodable media evidence",
                "source": "post_view_detection",
            }
        )
    if review_queue.get("retrieval_tasks"):
        suggested.append(
            {
                "agent_name": "ClaimEvidenceAgent",
                "reason": "claim/evidence review or retrieval tasks are planned",
                "source": "review_queue",
            }
        )
    if _has_propagation_tree_context(report):
        suggested.append(
            {
                "agent_name": "PropagationTreeAgent",
                "reason": "propagation/thread context is available for structural review",
                "source": "propagation",
            }
        )
    if suggested:
        suggested.append(
            {
                "agent_name": "QuestionReflectionAgent",
                "reason": "question-reflection should summarize conflicts and missing evidence after expert reports",
                "source": "MARO-style workflow",
            }
        )
        suggested.append(
            {
                "agent_name": "HarmfulnessJudgeAgent",
                "reason": "judge report should synthesize expert reports into a human-confirmed recommendation",
                "source": "MARO-style workflow",
            }
        )
    if _has_countermeasure_context(report):
        suggested.append(
            {
                "agent_name": "CountermeasureAgent",
                "reason": "high-risk or harmful claim context can support evidence-bound countermeasure planning",
                "source": "countermeasure",
            }
        )
    seen = set()
    deduped = []
    for item in suggested:
        name = item["agent_name"]
        if name in seen:
            continue
        seen.add(name)
        deduped.append(item)
    return {
        "schema_version": "kt3-agent-suggestions-v1",
        "manual_trigger_required": True,
        "suggested_agents": deduped,
        "all_agents": list(AGENT_ORDER),
        "review_required": bool(deduped),
        "review_reason": "; ".join(item["reason"] for item in deduped[:4]),
        "capability_boundary": {
            "llm_called": False,
            "manual_confirmation_required": True,
            "not_a_benchmark_fitting_step": True,
        },
    }


async def _run_agent_batch(
    agents: list[str],
    *,
    context: dict[str, Any],
    reports_by_agent: dict[str, dict[str, Any]],
    provider: KT3LLMAgentProvider | None,
    state: dict[str, Any],
) -> list[dict[str, Any]]:
    if not agents:
        return []
    tasks = [
        _run_single_agent(
            agent,
            context=context,
            reports_by_agent=reports_by_agent,
            provider=provider,
            state=state,
        )
        for agent in agents
    ]
    return await asyncio.gather(*tasks)


async def _run_reflection_response_batch(
    expert_agents: list[str],
    *,
    context: dict[str, Any],
    reports_by_agent: dict[str, dict[str, Any]],
    provider: KT3LLMAgentProvider | None,
    state: dict[str, Any],
) -> list[dict[str, Any]]:
    if provider is None or "QuestionReflectionAgent" not in reports_by_agent:
        return []
    tasks = [
        _run_single_reflection_response(
            agent,
            context=context,
            reports_by_agent=reports_by_agent,
            provider=provider,
            state=state,
        )
        for agent in expert_agents
        if agent in reports_by_agent
    ]
    return await asyncio.gather(*tasks) if tasks else []


async def _run_single_reflection_response(
    agent_name: str,
    *,
    context: dict[str, Any],
    reports_by_agent: dict[str, dict[str, Any]],
    provider: KT3LLMAgentProvider,
    state: dict[str, Any],
) -> dict[str, Any]:
    review_id = str(uuid4())
    response_agent_name = f"{agent_name}ReflectionResponse"
    base = {
        "review_id": review_id,
        "run_id": state["run_id"],
        "agent_name": response_agent_name,
        "parent_agent_name": agent_name,
        "report_role": "reflection_response",
        "model": state["model"],
        "provider_name": state["provider_name"],
        "input_refs": context["input_refs"],
        "input_hash": state["input_hash"],
        "created_at": state["created_at"],
        "human_triggered_by": state["human_triggered_by"],
    }
    system_prompt = (
        "You are the same KT3 expert agent responding to the QuestionReflectionAgent. "
        "Write a concise natural-language supplement in Chinese. Address missing "
        "evidence, conflicts, and what should change in your original analysis. "
        "Do not output JSON and do not claim final classifier authority."
    )
    user_prompt = _reflection_response_prompt(agent_name, context, reports_by_agent)
    try:
        report_text = await provider(
            agent_name=response_agent_name,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            input_bundle=context,
            model=state["model"],
        )
    except Exception as exc:  # pragma: no cover
        sidecar = build_sidecar_for_agent(
            agent_name=agent_name,
            context=context,
            retrieval_bundle=state.get("retrieval_bundle"),
            debate_bundle=state.get("debate_bundle"),
        )
        return {
            **base,
            "status": "failed",
            "error": str(exc),
            "analysis_report": _analysis_report_payload(
                agent_name=response_agent_name,
                report_text=None,
                status="failed",
                error=str(exc),
            ),
            "report_text": None,
            "system_audit_sidecar": sidecar,
            "structured_sidecar": sidecar,
            "safety_flags": ["provider_failure", "no_synthetic_fallback"],
        }
    sidecar = build_sidecar_for_agent(
        agent_name=agent_name,
        context=context,
        retrieval_bundle=state.get("retrieval_bundle"),
        debate_bundle=state.get("debate_bundle"),
    )
    return {
        **base,
        "status": "completed",
        "analysis_report": _analysis_report_payload(
            agent_name=response_agent_name,
            report_text=str(report_text).strip(),
            status="completed",
        ),
        "report_text": str(report_text).strip(),
        "report_format": "maro_style_reflection_response_report",
        "system_audit_sidecar": sidecar,
        "structured_sidecar": sidecar,
        "safety_flags": ["human_confirmation_required", "not_a_classifier_output", "reflection_response"],
    }


async def _run_single_agent(
    agent_name: str,
    *,
    context: dict[str, Any],
    reports_by_agent: dict[str, dict[str, Any]],
    provider: KT3LLMAgentProvider | None,
    state: dict[str, Any],
) -> dict[str, Any]:
    review_id = str(uuid4())
    base = {
        "review_id": review_id,
        "run_id": state["run_id"],
        "agent_name": agent_name,
        "model": state["model"],
        "provider_name": state["provider_name"],
        "input_refs": context["input_refs"],
        "input_hash": state["input_hash"],
        "created_at": state["created_at"],
        "human_triggered_by": state["human_triggered_by"],
    }
    if provider is None:
        sidecar = build_sidecar_for_agent(
            agent_name=agent_name,
            context=context,
            retrieval_bundle=state.get("retrieval_bundle"),
            debate_bundle=state.get("debate_bundle"),
        )
        return {
            **base,
            "status": "failed",
            "error": "LLM provider is not configured; no synthetic report was generated.",
            "analysis_report": _analysis_report_payload(
                agent_name=agent_name,
                report_text=None,
                status="failed",
                error="LLM provider is not configured; no synthetic report was generated.",
            ),
            "report_text": None,
            "system_audit_sidecar": sidecar,
            "structured_sidecar": sidecar,
            "safety_flags": ["no_synthetic_fallback"],
        }
    if _agent_requires_vision(agent_name, context=context, state=state):
        media_status = _vision_input_status(context)
        if not media_status["has_vision_input"]:
            sidecar = build_sidecar_for_agent(
                agent_name=agent_name,
                context=context,
                retrieval_bundle=state.get("retrieval_bundle"),
                debate_bundle=state.get("debate_bundle"),
            )
            return {
                **base,
                "status": "failed",
                "error": "Vision input is required for this agent, but no image/keyframe data URL was available.",
                "analysis_report": _analysis_report_payload(
                    agent_name=agent_name,
                    report_text=None,
                    status="failed",
                    error="Vision input is required for this agent, but no image/keyframe data URL was available.",
                ),
                "report_text": None,
                "system_audit_sidecar": sidecar,
                "structured_sidecar": sidecar,
                "vision_required": True,
                "vision_input_status": media_status,
                "safety_flags": ["vision_required", "missing_vision_input", "no_synthetic_fallback"],
            }

    system_prompt = _agent_system_prompt(agent_name)
    user_prompt = _agent_user_prompt(agent_name, context, reports_by_agent)
    try:
        report_text = await provider(
            agent_name=agent_name,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            input_bundle=context,
            model=state["model"],
        )
    except Exception as exc:  # pragma: no cover - covered through API/core tests
        sidecar = build_sidecar_for_agent(
            agent_name=agent_name,
            context=context,
            retrieval_bundle=state.get("retrieval_bundle"),
            debate_bundle=state.get("debate_bundle"),
        )
        return {
            **base,
            "status": "failed",
            "error": str(exc),
            "analysis_report": _analysis_report_payload(
                agent_name=agent_name,
                report_text=None,
                status="failed",
                error=str(exc),
            ),
            "report_text": None,
            "system_audit_sidecar": sidecar,
            "structured_sidecar": sidecar,
            "vision_required": _agent_requires_vision(agent_name, context=context, state=state),
            "vision_input_status": _vision_input_status(context),
            "safety_flags": ["provider_failure", "no_synthetic_fallback"],
        }
    sidecar = build_sidecar_for_agent(
        agent_name=agent_name,
        context=context,
        retrieval_bundle=state.get("retrieval_bundle"),
        debate_bundle=state.get("debate_bundle"),
    )
    analysis_report = _analysis_report_payload(
        agent_name=agent_name,
        report_text=str(report_text).strip(),
        status="completed",
    )
    return {
        **base,
        "status": "completed",
        "analysis_report": analysis_report,
        "report_text": str(report_text).strip(),
        "report_format": "maro_style_natural_language_analysis_report",
        "system_audit_sidecar": sidecar,
        "structured_sidecar": sidecar,
        "sections_expected": AGENT_REPORT_SECTIONS[agent_name],
        "vision_required": _agent_requires_vision(agent_name, context=context, state=state),
        "vision_input_status": _vision_input_status(context),
        "safety_flags": _agent_safety_flags(agent_name),
    }


def _analysis_report_payload(
    *,
    agent_name: str,
    report_text: str | None,
    status: str,
    error: str | None = None,
) -> dict[str, Any]:
    """Primary MARO-style Agent output: a natural-language analysis report."""
    return {
        "schema_version": "kt3-maro-analysis-report-v1",
        "agent_name": agent_name,
        "status": status,
        "format": "natural_language_or_semi_structured_report",
        "text": report_text,
        "error": error,
        "sections_expected": AGENT_REPORT_SECTIONS.get(agent_name, []),
        "capability_boundary": {
            "primary_agent_output": True,
            "not_json_classifier": True,
            "system_sidecar_is_audit_only": True,
            "human_confirmation_required": True,
        },
    }


def _completed_by_agent(results: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {
        str(item.get("agent_name")): item
        for item in results
        if item.get("status") == "completed"
    }


def _agent_system_prompt(agent_name: str) -> str:
    sections = "\n".join(f"- {section}" for section in AGENT_REPORT_SECTIONS[agent_name])
    judge_policy_note = (
        "\nFor HarmfulnessJudgeAgent: explicitly read selected_context.active_policy "
        "when present. Explain which policy thresholds/rule explanations support "
        "review, abstain, retrieval, or countermeasure recommendations, and state "
        "that the policy is advisory until human approval.\n"
        if agent_name == "HarmfulnessJudgeAgent"
        else ""
    )
    optimizer_note = (
        "\nDecision rule optimization is not a selectable judgement role here. "
        "If policy context is present, cite it as provenance rather than changing it.\n"
    )
    return (
        "You are a KT3 MARO-style expert agent for harmfulness characterization. "
        "Write a role-specific natural-language analysis report in Chinese. "
        "Do not output JSON as the main report. Do not claim to be the final "
        "automatic classifier. Separate evidence from uncertainty and make clear "
        "what requires human confirmation.\n\n"
        f"Agent: {agent_name}\n"
        "Required report sections:\n"
        f"{sections}\n"
        f"{judge_policy_note}"
        f"{optimizer_note}"
    )


def _agent_user_prompt(
    agent_name: str,
    context: dict[str, Any],
    reports_by_agent: dict[str, dict[str, Any]],
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
        "policy_guidance": _policy_guidance_for_prompt(context),
        "selected_context": context,
        "prior_agent_reports": prior_reports,
    }
    return json.dumps(payload, ensure_ascii=False, default=str)


def _reflection_response_prompt(
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
        "expected_response": [
            "which reflection questions affect the original analysis",
            "what evidence remains missing",
            "whether any original conclusion should be softened",
            "what the Judge should treat as uncertain",
        ],
    }
    return json.dumps(payload, ensure_ascii=False, default=str)


def _policy_guidance_for_prompt(context: dict[str, Any]) -> dict[str, Any]:
    policy = context.get("active_policy") or context.get("policy") or {}
    active_policy = policy.get("policy") if isinstance(policy, dict) and "policy" in policy else policy
    if not isinstance(active_policy, dict) or not active_policy:
        return {
            "active_policy_present": False,
            "judge_should_note": "No activated decision policy was supplied; use detector evidence and human confirmation.",
        }
    accepted_rules = []
    for rule in policy.get("candidate_rules") or []:
        if isinstance(rule, dict) and rule.get("status") in {"accepted_for_round", "activated"}:
            accepted_rules.append(
                {
                    "rule_id": rule.get("rule_id"),
                    "description": rule.get("description"),
                    "source": rule.get("source"),
                    "round": rule.get("round"),
                }
            )
    return {
        "active_policy_present": True,
        "policy_id": policy.get("policy_id") if isinstance(policy, dict) else None,
        "activation_status": policy.get("activation_status") if isinstance(policy, dict) else None,
        "thresholds": {
            "review_threshold": active_policy.get("review_threshold"),
            "abstain_threshold": active_policy.get("abstain_threshold"),
            "retrieval_threshold": active_policy.get("retrieval_threshold"),
            "countermeasure_threshold": active_policy.get("countermeasure_threshold"),
        },
        "accepted_rule_refs": accepted_rules[:8],
        "judge_should_note": (
            "Use the active policy as advisory provenance for review/retrieval/"
            "countermeasure recommendations; do not overwrite detector outputs."
        ),
    }


def _openai_messages(
    system_prompt: str,
    user_prompt: str,
    input_bundle: dict[str, Any],
) -> list[dict[str, Any]]:
    media_items = _as_list(input_bundle.get("media_inputs"))
    image_parts = []
    for item in media_items:
        data_url = item.get("data_url") if isinstance(item, dict) else None
        if data_url:
            image_parts.append({"type": "image_url", "image_url": {"url": data_url}})
    if not image_parts:
        return [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
    content = [{"type": "text", "text": user_prompt}, *image_parts]
    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": content},
    ]


def _openai_responses_payload(
    system_prompt: str,
    user_prompt: str,
    input_bundle: dict[str, Any],
    *,
    model: str,
) -> dict[str, Any]:
    content: list[dict[str, Any]] = [{"type": "input_text", "text": user_prompt}]
    for item in _as_list(input_bundle.get("media_inputs")):
        data_url = item.get("data_url") if isinstance(item, dict) else None
        if data_url:
            content.append({"type": "input_image", "image_url": data_url})
    return {
        "model": model,
        "instructions": system_prompt,
        "input": [{"role": "user", "content": content}],
        "temperature": 0.2,
    }


def _extract_responses_text(data: dict[str, Any], agent_name: str) -> str:
    output_text = data.get("output_text")
    if isinstance(output_text, str) and output_text.strip():
        return output_text.strip()
    chunks: list[str] = []
    for item in _as_list(data.get("output")):
        if not isinstance(item, dict):
            continue
        for content in _as_list(item.get("content")):
            if not isinstance(content, dict):
                continue
            text = content.get("text")
            if isinstance(text, str) and text.strip():
                chunks.append(text.strip())
    if chunks:
        return "\n".join(chunks)
    raise RuntimeError(f"{agent_name} returned an empty Responses report")


def _normalize_wire_api(value: str) -> str:
    normalized = str(value or "").strip().lower().replace("-", "_")
    if normalized in {"responses", "response"}:
        return "responses"
    if normalized in {"chat", "chat_completion", "chat_completions", "completions"}:
        return "chat_completions"
    raise RuntimeError(f"Unsupported LLM_API_WIRE: {value}")


def _build_agent_context(
    report: dict[str, Any],
    *,
    case_id: str | None,
    selected_post_ids: list[str],
    selected_tree_ids: list[str],
    include_media_base64: bool,
    max_keyframes: int,
) -> dict[str, Any]:
    posts = _select_posts(report.get("post_semantics") or {}, selected_post_ids)
    propagation_context = _select_propagation_context(report, selected_tree_ids)
    media_inputs = []
    for post in posts:
        media_inputs.extend(
            _media_inputs_for_post(
                post,
                include_media_base64=include_media_base64,
                max_keyframes=max_keyframes,
            )
        )
    input_refs = {
        "report_id": report.get("report_id"),
        "case_id": case_id,
        "event_id": report.get("event_id"),
        "platform": report.get("platform"),
        "post_ids": [_text(post.get("post_id")) for post in posts if _text(post.get("post_id"))],
        "tree_ids": selected_tree_ids,
    }
    return {
        "schema_version": "kt3-agent-input-bundle-v1",
        "input_refs": input_refs,
        "selected_posts": posts,
        "media_inputs": media_inputs,
        "propagation_context": propagation_context,
        "review_queue": _get(report, "kt3_harmfulness", "review_queue") or {},
        "review_execution": _get(report, "kt3_harmfulness", "review_execution") or {},
        "disarm_analysis": report.get("disarm_analysis") or {},
        "capability_boundary": {
            "media_policy": "file_reference_with_optional_base64",
            "video_keyframe_policy": "cover_or_first_frame_plus_uniform_top_k",
            "raw_video_direct_input": False,
            "account_identifiers_should_be_treated_as_pseudonymous": True,
        },
    }


def _select_posts(post_semantics: dict[str, Any], selected_post_ids: list[str]) -> list[dict[str, Any]]:
    posts = _semantic_posts(post_semantics)
    if not selected_post_ids:
        return posts[:5]
    wanted = {str(item) for item in selected_post_ids}
    selected = [post for post in posts if str(post.get("post_id")) in wanted]
    return selected[:20]


def _select_propagation_context(report: dict[str, Any], selected_tree_ids: list[str]) -> dict[str, Any]:
    kt3 = report.get("kt3_harmfulness") or {}
    graph_export = kt3.get("graph_export") or {}
    post_semantics = report.get("post_semantics") or {}
    return {
        "selected_tree_ids": selected_tree_ids,
        "claim_rank": _as_list(_get(kt3, "global_summary", "claim_rank"))[:10],
        "graph_summary": graph_export.get("summary") or {},
        "post_semantics_summary": post_semantics.get("summary") or {},
        "note": (
            "If PHEME structure/reactions are available, pass their parsed tree "
            "overview here. Current runtime may only contain graph summaries."
        ),
    }


def _media_inputs_for_post(
    post: dict[str, Any],
    *,
    include_media_base64: bool,
    max_keyframes: int,
) -> list[dict[str, Any]]:
    evidence = post.get("evidence") or {}
    raw = post.get("raw_data") or {}
    media_urls = _as_list(post.get("media_urls")) or _as_list(evidence.get("media_urls"))
    rows: list[dict[str, Any]] = []
    for index, url in enumerate(media_urls[:max_keyframes]):
        media_type = _infer_media_type(str(url))
        row = {
            "post_id": post.get("post_id"),
            "media_index": index,
            "media_type": media_type,
            "uri": str(url),
            "selection_policy": "image_original_or_video_cover_then_uniform_keyframes",
            "ocr_text": _text(raw.get("ocr_text")) or _text(evidence.get("ocr_text")),
            "asr_text": _text(raw.get("asr_text")) or _text(evidence.get("asr_text")),
            "caption": _text(raw.get("caption")) or _text(evidence.get("caption")),
        }
        if include_media_base64:
            row["data_url"] = _maybe_data_url(str(url))
        rows.append(row)
    if not rows and any(_text(raw.get(key)) or _text(evidence.get(key)) for key in ("ocr_text", "asr_text", "caption")):
        rows.append(
            {
                "post_id": post.get("post_id"),
                "media_index": 0,
                "media_type": "derived_text_only",
                "uri": "",
                "selection_policy": "no_media_file_reference_available",
                "ocr_text": _text(raw.get("ocr_text")) or _text(evidence.get("ocr_text")),
                "asr_text": _text(raw.get("asr_text")) or _text(evidence.get("asr_text")),
                "caption": _text(raw.get("caption")) or _text(evidence.get("caption")),
            }
        )
    return rows


def _maybe_data_url(uri: str) -> str | None:
    path = Path(uri)
    if not path.exists() or not path.is_file():
        return None
    suffix = path.suffix.lower()
    mime = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".webp": "image/webp",
    }.get(suffix)
    if not mime:
        return None
    data = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{data}"


def _infer_media_type(uri: str) -> str:
    suffix = Path(uri).suffix.lower()
    if suffix in {".jpg", ".jpeg", ".png", ".webp", ".gif"}:
        return "image"
    if suffix in {".mp4", ".mov", ".avi", ".mkv", ".webm"}:
        return "video_keyframe_reference"
    return "media_reference"


def _agent_safety_flags(agent_name: str) -> list[str]:
    flags = ["human_confirmation_required", "not_a_classifier_output"]
    if agent_name == "CountermeasureAgent":
        flags.extend(["no_auto_publish", "evidence_bound_countermeasure"])
    if agent_name == "HarmfulnessJudgeAgent":
        flags.append("advisory_judgement_only")
    return flags


def _agent_requires_vision(
    agent_name: str,
    *,
    context: dict[str, Any],
    state: dict[str, Any],
) -> bool:
    if not bool(state.get("require_vision")):
        return False
    # Strict vision is scoped to the multimodal/keyframe review agent. Other
    # MARO-style agents may cite OCR/ASR/caption or detector outputs without
    # becoming raw visual reviewers.
    return agent_name == "MultimodalConsistencyAgent"


def _vision_input_status(context: dict[str, Any]) -> dict[str, Any]:
    media_inputs = [item for item in _as_list(context.get("media_inputs")) if isinstance(item, dict)]
    data_url_count = sum(1 for item in media_inputs if item.get("data_url"))
    media_types = sorted({str(item.get("media_type") or "unknown") for item in media_inputs})
    return {
        "has_vision_input": data_url_count > 0,
        "media_input_count": len(media_inputs),
        "data_url_count": data_url_count,
        "media_types": media_types,
        "requires_base64_or_accessible_image_url": True,
    }


def _normalize_agent_names(agent_names: list[str]) -> list[str]:
    aliases = {
        "PostHarm": "PostHarmAgent",
        "MultimodalConsistency": "MultimodalConsistencyAgent",
        "ClaimEvidence": "ClaimEvidenceAgent",
        "PropagationTree": "PropagationTreeAgent",
        "QuestionReflection": "QuestionReflectionAgent",
        "HarmfulnessJudge": "HarmfulnessJudgeAgent",
        "Countermeasure": "CountermeasureAgent",
    }
    normalized = []
    for item in agent_names:
        name = aliases.get(str(item), str(item))
        if name not in AGENT_ORDER:
            raise ValueError(f"Unsupported KT3 agent: {item}")
        if name not in normalized:
            normalized.append(name)
    if not normalized:
        raise ValueError("At least one KT3 agent must be selected")
    return sorted(normalized, key=lambda name: AGENT_ORDER.index(name))


def _post_has_multimodal_conflict(post: dict[str, Any]) -> bool:
    view = post.get("post_view_detection") or {}
    if view.get("conflict"):
        return True
    review_reasons = _as_list(view.get("review_reason"))
    return any("conflict" in str(reason) or "media" in str(reason) for reason in review_reasons)


def _has_propagation_tree_context(report: dict[str, Any]) -> bool:
    kt3 = report.get("kt3_harmfulness") or {}
    graph_summary = _get(kt3, "graph_export", "summary") or {}
    return bool(graph_summary or _get(report, "post_semantics", "summary", "available_claims"))


def _has_countermeasure_context(report: dict[str, Any]) -> bool:
    risk_level = _text(_get(report, "scores", "risk_level"))
    kt3_level = _text(_get(report, "kt3_harmfulness", "global_summary", "kt3_harm_risk_level"))
    return risk_level in {"high", "critical"} or kt3_level in {"medium", "high"}


def _semantic_posts(post_semantics: dict[str, Any]) -> list[dict[str, Any]]:
    posts = _as_list(post_semantics.get("posts"))
    if posts:
        return posts
    return _as_list(post_semantics.get("aggregation_posts"))


def _hash_payload(payload: Any) -> str:
    return sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")).hexdigest()


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _get(mapping: dict[str, Any], *path: str) -> Any:
    value: Any = mapping
    for part in path:
        if not isinstance(value, dict):
            return None
        value = value.get(part)
    return value


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def _text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()
