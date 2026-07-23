"""Manual MARO-style Review LLM agent review.

This module is intentionally separate from the deterministic Review queue.
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
import random
from pathlib import Path

import httpx

from app.core.review.active_retrieval import ActiveEvidenceProvider
from app.core.review.active_retrieval import build_full_debate_trace
from app.core.review.active_retrieval import build_light_debate_trace
from app.core.review.active_retrieval import build_sidecar_for_agent
from app.core.review.active_retrieval import retrieve_active_evidence
from app.core.review.active_retrieval import should_trigger_light_debate
from app.core.review.governance_reference import build_governance_reference_context
from app.core.review.governance_reference import build_governance_report_sidecar
from app.core.review.agent_contracts import AGENT_REPORT_SECTIONS
from app.core.review.agent_contracts import build_agent_output_contract
from app.core.review.agent_contracts import build_agent_system_prompt
from app.core.review.agent_contracts import build_agent_user_prompt
from app.core.review.agent_contracts import build_default_report_role
from app.core.review.agent_contracts import build_reflection_response_prompt
from app.core.review.agent_contracts import build_report_role_name
from app.core.review.agent_contracts import build_revision_system_prompt
from app.core.review.agent_contracts import build_revision_user_prompt
from app.core.review.agent_contracts import build_safety_flags
from app.core.review.propagation_agent import has_propagation_tree_context as _has_propagation_tree_context_impl
from app.core.review.propagation_agent import select_propagation_context as _select_propagation_context_impl


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
    {
        "paper": "Public platform governance reports and community rules",
        "transfer": (
            "Use public platform policy categories, transparency report structure, "
            "and enforcement-action vocabulary as report-template guidance only."
        ),
    },
]


class ReviewLLMAgentProvider(Protocol):
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
    timeout_seconds: float = 180.0
    include_media_base64: bool = False
    require_vision: bool = False
    max_retries: int = 2
    retry_backoff_seconds: float = 2.0


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
        data = None
        last_error: Exception | None = None
        max_attempts = max(1, int(self.config.max_retries or 0) + 1)
        for attempt in range(1, max_attempts + 1):
            try:
                async with httpx.AsyncClient(timeout=self.config.timeout_seconds) as client:
                    response = await client.post(url, headers=headers, json=payload)
                    response.raise_for_status()
                    data = response.json()
                    break
            except httpx.HTTPStatusError as exc:
                last_error = exc
                status_code = exc.response.status_code if exc.response is not None else None
                if attempt >= max_attempts or not _should_retry_status(status_code):
                    body = exc.response.text[:1000] if exc.response is not None else ""
                    raise RuntimeError(f"{agent_name} provider HTTP {status_code if status_code else 'error'}: {body}") from exc
            except Exception as exc:
                last_error = exc
                if attempt >= max_attempts or not _should_retry_exception(exc):
                    detail = str(exc) or exc.__class__.__name__
                    raise RuntimeError(f"{agent_name} provider request failed: {detail}") from exc
            await asyncio.sleep(_retry_delay_seconds(self.config.retry_backoff_seconds, attempt))
        if data is None:
            detail = str(last_error) if last_error is not None else "unknown provider error"
            raise RuntimeError(f"{agent_name} provider request failed: {detail}")
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


async def run_manual_agent_review(
    *,
    report: dict[str, Any],
    agent_names: list[str],
    case_id: str | None = None,
    selected_post_ids: list[str] | None = None,
    selected_tree_ids: list[str] | None = None,
    human_triggered_by: int | str = 0,
    provider: ReviewLLMAgentProvider | None = None,
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
    error_memory_summary: dict[str, Any] | None = None,
    require_vision: bool = False,
    runtime_mode: str = "auto",
    enable_deep_judge: bool = False,
) -> dict[str, Any]:
    """Run analyst-triggered natural-language Review agent reports."""
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
    context["error_memory_summary"] = error_memory_summary or {}
    runtime_decision = _resolve_runtime_mode(
        report=report,
        context=context,
        normalized_agents=normalized_agents,
        requested_runtime_mode=runtime_mode,
        enable_active_retrieval=enable_active_retrieval,
        enable_light_debate=enable_light_debate,
        enable_full_debate=enable_full_debate,
        enable_deep_judge=enable_deep_judge,
    )
    effective_runtime_mode = runtime_decision["effective_runtime_mode"]
    execution_plan = _execution_plan_for_runtime(
        requested_agents=normalized_agents,
        runtime_mode=effective_runtime_mode,
        enable_deep_judge=enable_deep_judge,
    )
    retrieval_requested = bool(enable_active_retrieval and effective_runtime_mode == "complex")
    retrieval_enabled = bool(
        retrieval_requested
        and execution_plan["claim_agent_enabled"]
        and "ClaimEvidenceAgent" in execution_plan["expert_agents"]
    )
    retrieval_bundle = (
        await retrieve_active_evidence(
            context=context,
            top_k=retrieval_top_k,
            external_provider=active_retriever,
            external_enabled=external_retrieval_enabled,
        )
        if retrieval_enabled
        else None
    )
    if retrieval_bundle is not None:
        context["active_retrieval"] = retrieval_bundle
    debate_requested = bool(
        effective_runtime_mode == "complex"
        and execution_plan["multimodal_agent_enabled"]
        and (enable_light_debate or enable_full_debate)
    )
    debate_triggered, debate_reasons = should_trigger_light_debate(
        context=context,
        retrieval_bundle=retrieval_bundle,
    )
    if enable_full_debate and debate_requested and debate_triggered:
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
            if enable_light_debate and debate_requested and debate_triggered
            else {"schema_version": "review-light-debate-v1", "triggered": False, "reasons": debate_reasons}
        )
    context["debate_trace"] = debate_bundle
    context["full_debate"] = debate_bundle if debate_bundle.get("schema_version") == "review-full-debate-v1" else None
    context["light_debate"] = debate_bundle if debate_bundle.get("schema_version") == "review-light-debate-v1" else None
    context["debate_mode"] = debate_bundle.get("debate_mode") or (
        "full_debate" if debate_bundle.get("schema_version") == "review-full-debate-v1" else "light_debate"
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
            "runtime_mode": runtime_mode,
            "effective_runtime_mode": effective_runtime_mode,
            "enable_deep_judge": enable_deep_judge,
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
        "runtime_mode": effective_runtime_mode,
        "requested_runtime_mode": runtime_mode,
        "enable_deep_judge": enable_deep_judge,
        "runtime_reasons": runtime_decision["runtime_reasons"],
        "recommended_runtime_mode": runtime_decision["recommended_runtime_mode"],
        "runtime_upgraded_by_requested_features": runtime_decision["runtime_upgraded_by_requested_features"],
    }
    reports_by_agent = {
        str(item.get("agent_name")): item
        for item in existing_reviews
        if isinstance(item, dict) and item.get("status") == "completed"
    }

    results: list[dict[str, Any]] = []
    expert_agents = execution_plan["expert_agents"]
    followup_agents = execution_plan["followup_agents"]

    expert_results = await _run_agent_batch(
        expert_agents,
        context=context,
        reports_by_agent=reports_by_agent,
        provider=provider,
        state=state,
    )
    results.extend(expert_results)
    reports_by_agent.update(_completed_by_agent(expert_results))

    if execution_plan["run_question_reflection"] and "QuestionReflectionAgent" in followup_agents:
        [reflection_result] = await _run_agent_batch(
            ["QuestionReflectionAgent"],
            context=context,
            reports_by_agent=reports_by_agent,
            provider=provider,
            state=state,
        )
        results.append(reflection_result)
        reports_by_agent.update(_completed_by_agent([reflection_result]))
        if execution_plan["run_reflection_responses"]:
            reflection_responses = await _run_reflection_response_batch(
                expert_agents,
                context=context,
                reports_by_agent=reports_by_agent,
                provider=provider,
                state=state,
            )
            results.extend(reflection_responses)
            reports_by_agent.update(_completed_by_agent(reflection_responses))

    if "HarmfulnessJudgeAgent" in followup_agents:
        if execution_plan["deep_judge"]:
            judge_results = await _run_self_refined_agent(
                agent_name="HarmfulnessJudgeAgent",
                context=context,
                reports_by_agent=reports_by_agent,
                provider=provider,
                state=state,
            )
        else:
            judge_results = [
                await _run_single_agent(
                    "HarmfulnessJudgeAgent",
                    context=context,
                    reports_by_agent=reports_by_agent,
                    provider=provider,
                    state=state,
                )
            ]
        results.extend(judge_results)
        reports_by_agent.update(_completed_by_agent([judge_results[-1]]))

    countermeasure_requested = "CountermeasureAgent" in normalized_agents
    countermeasure_allowed = execution_plan["run_countermeasure"]
    if countermeasure_allowed and (
        countermeasure_requested or _should_postpone_countermeasure(report=report, reports_by_agent=reports_by_agent)
    ):
        countermeasure_results = [
            await _run_single_agent(
                "CountermeasureAgent",
                context=context,
                reports_by_agent=reports_by_agent,
                provider=provider,
                state=state,
            )
        ]
        results.extend(countermeasure_results)
        reports_by_agent.update(_completed_by_agent([countermeasure_results[-1]]))

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
        "full_debate": debate_bundle if debate_bundle.get("schema_version") == "review-full-debate-v1" else None,
        "policy_id": (policy or {}).get("policy_id"),
        "recommended_runtime_mode": runtime_decision["recommended_runtime_mode"],
        "effective_runtime_mode": effective_runtime_mode,
        "runtime_reasons": runtime_decision["runtime_reasons"],
        "runtime_upgraded_by_requested_features": runtime_decision["runtime_upgraded_by_requested_features"],
        "candidate_rule_hints": _candidate_rule_hints(
            report=report,
            context=context,
            retrieval_bundle=retrieval_bundle,
            reports_by_agent=reports_by_agent,
        ),
        "failure_mode_tags": _failure_mode_tags(
            report=report,
            context=context,
            retrieval_bundle=retrieval_bundle,
        ),
        "capability_boundary": {
            "manual_human_triggered": True,
            "not_a_classifier": True,
            "fits_benchmark_labels": False,
            "natural_language_reports": True,
            "failure_policy": "record_failure_without_synthetic_report",
            "active_retrieval_default_external": True,
            "policy_does_not_modify_detector_outputs": True,
            "strict_vision_required": require_vision,
            "full_debate_optional": True,
            "full_debate_high_conflict_only": True,
            "maro_question_reflection_loop": "expert_reports_then_reflection_then_expert_response",
            "runtime_mode_enabled": True,
            "countermeasure_post_judge_only": True,
        },
    }
    return {
        "schema_version": "review-manual-agent-review-v1",
        "audit": audit,
        "input_bundle": context,
        "agent_reports": results,
        "active_retrieval": retrieval_bundle,
        "light_debate": debate_bundle,
        "full_debate": debate_bundle if debate_bundle.get("schema_version") == "review-full-debate-v1" else None,
        "summary": {
            "requested_agents": len(normalized_agents),
            "completed": sum(1 for item in results if item.get("status") == "completed"),
            "failed": sum(1 for item in results if item.get("status") == "failed"),
            "active_retrieval_used": retrieval_bundle is not None,
            "light_debate_triggered": bool(debate_bundle.get("triggered")),
            "full_debate_triggered": bool(
                debate_bundle.get("triggered") and debate_bundle.get("schema_version") == "review-full-debate-v1"
            ),
            "reflection_response_reports": sum(
                1 for item in results if item.get("report_role") == "reflection_response"
            ),
            "report_ids": [item.get("review_id") for item in results],
            "recommended_runtime_mode": runtime_decision["recommended_runtime_mode"],
            "effective_runtime_mode": effective_runtime_mode,
            "runtime_reasons": runtime_decision["runtime_reasons"],
            "runtime_upgraded_by_requested_features": runtime_decision["runtime_upgraded_by_requested_features"],
            "candidate_rule_hints": audit["candidate_rule_hints"],
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
        timeout_seconds=float(getattr(settings, "LLM_TIMEOUT_SECONDS", 180.0) or 180.0),
        include_media_base64=bool(getattr(settings, "LLM_INCLUDE_MEDIA_BASE64", False)),
        require_vision=bool(getattr(settings, "LLM_REQUIRE_VISION", False)),
    )
    return OpenAICompatibleAgentProvider(config)


def agent_review_suggestions(report: dict[str, Any]) -> dict[str, Any]:
    """Build human-facing agent suggestions without calling an LLM."""
    review = report.get("review_harmfulness") or {}
    review_queue = review.get("review_queue") or {}
    review_items = _as_list(review_queue.get("review_items"))
    posts = _semantic_posts(report.get("post_semantics") or {})
    suggestion_context = {
        "selected_posts": posts[:5],
        "review_queue": review_queue,
    }
    recommended_runtime_mode, runtime_reasons = _recommended_runtime_mode(
        report=report,
        context=suggestion_context,
    )

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
        "schema_version": "review-agent-suggestions-v1",
        "manual_trigger_required": True,
        "suggested_agents": deduped,
        "all_agents": list(AGENT_ORDER),
        "review_required": bool(deduped),
        "review_reason": "; ".join(item["reason"] for item in deduped[:4]),
        "recommended_runtime_mode": recommended_runtime_mode,
        "runtime_reasons": runtime_reasons,
        "capability_boundary": {
            "llm_called": False,
            "manual_confirmation_required": True,
            "not_a_benchmark_fitting_step": True,
        },
    }


def _resolve_runtime_mode(
    *,
    report: dict[str, Any],
    context: dict[str, Any],
    normalized_agents: list[str],
    requested_runtime_mode: str,
    enable_active_retrieval: bool,
    enable_light_debate: bool,
    enable_full_debate: bool,
    enable_deep_judge: bool,
) -> dict[str, Any]:
    recommended, reasons = _recommended_runtime_mode(report=report, context=context)
    requested = str(requested_runtime_mode or "auto").strip().lower()
    if requested not in {"auto", "simple", "complex"}:
        requested = "auto"

    upgraded = False
    forced_complex_reasons: list[str] = []
    if enable_active_retrieval:
        forced_complex_reasons.append("enabled_active_retrieval")
    if enable_light_debate or enable_full_debate:
        forced_complex_reasons.append("enabled_debate")
    if enable_deep_judge:
        forced_complex_reasons.append("enabled_deep_judge")
    if "CountermeasureAgent" in normalized_agents:
        forced_complex_reasons.append("countermeasure_selected")

    if requested == "auto":
        effective = recommended
    elif requested == "simple":
        if forced_complex_reasons:
            effective = "complex"
            upgraded = True
            reasons = [*reasons, *forced_complex_reasons]
        else:
            effective = "simple"
    else:
        effective = "complex"
        if recommended == "simple":
            reasons = [*reasons, "analyst_requested_complex_mode"]

    return {
        "recommended_runtime_mode": recommended,
        "effective_runtime_mode": effective,
        "runtime_reasons": _dedupe_strs(reasons),
        "runtime_upgraded_by_requested_features": upgraded,
    }


def _recommended_runtime_mode(*, report: dict[str, Any], context: dict[str, Any]) -> tuple[str, list[str]]:
    reasons: list[str] = []
    selected_posts = _as_list(context.get("selected_posts"))
    review_queue = _get(report, "review_harmfulness", "review_queue") or {}
    if len(selected_posts) > 1:
        reasons.append("multiple_selected_posts")
    if any(_post_has_multimodal_conflict(post) for post in selected_posts):
        reasons.append("multimodal_conflict_or_media_gap")
    if review_queue.get("retrieval_tasks"):
        reasons.append("claim_retrieval_tasks_present")
    if _has_propagation_tree_context(report):
        reasons.append("propagation_context_present")
    if any(_post_has_uncertain_stance_or_view(post) for post in selected_posts):
        reasons.append("stance_or_post_view_uncertain")
    return ("complex", reasons) if reasons else ("simple", ["single_post_low_conflict"])


def _execution_plan_for_runtime(
    *,
    requested_agents: list[str],
    runtime_mode: str,
    enable_deep_judge: bool,
) -> dict[str, Any]:
    requested = [agent for agent in requested_agents if agent in AGENT_ORDER]
    if runtime_mode == "simple":
        expert_agents = [
            agent
            for agent in requested
            if agent in {"PostHarmAgent", "ClaimEvidenceAgent", "PropagationTreeAgent", "MultimodalConsistencyAgent"}
        ]
        if "HarmfulnessJudgeAgent" not in requested:
            requested = [*requested, "HarmfulnessJudgeAgent"]
        return {
            "expert_agents": expert_agents,
            "followup_agents": ["HarmfulnessJudgeAgent"],
            "run_question_reflection": False,
            "run_reflection_responses": False,
            "deep_judge": False,
            "run_countermeasure": False,
            "claim_agent_enabled": "ClaimEvidenceAgent" in expert_agents,
            "multimodal_agent_enabled": "MultimodalConsistencyAgent" in expert_agents,
        }
    expert_agents = [agent for agent in requested if agent in EXPERT_AGENTS]
    run_question_reflection = bool(expert_agents)
    followup_agents: list[str] = []
    if run_question_reflection:
        followup_agents.append("QuestionReflectionAgent")
    followup_agents.append("HarmfulnessJudgeAgent")
    if "CountermeasureAgent" in requested:
        followup_agents.append("CountermeasureAgent")
    return {
        "expert_agents": expert_agents,
        "followup_agents": _dedupe_strs(followup_agents),
        "run_question_reflection": run_question_reflection,
        "run_reflection_responses": run_question_reflection,
        "deep_judge": bool(enable_deep_judge),
        "run_countermeasure": True,
        "claim_agent_enabled": "ClaimEvidenceAgent" in expert_agents,
        "multimodal_agent_enabled": "MultimodalConsistencyAgent" in expert_agents,
    }


def _should_postpone_countermeasure(*, report: dict[str, Any], reports_by_agent: dict[str, dict[str, Any]]) -> bool:
    if _has_countermeasure_context(report):
        return True
    judge_report = reports_by_agent.get("HarmfulnessJudgeAgent") or {}
    judge_text = str(judge_report.get("report_text") or "").lower()
    return "反制" in str(judge_report.get("report_text") or "") or "countermeasure" in judge_text


def _candidate_rule_hints(
    *,
    report: dict[str, Any],
    context: dict[str, Any],
    retrieval_bundle: dict[str, Any] | None,
    reports_by_agent: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    hints: list[dict[str, Any]] = []
    selected_posts = _as_list(context.get("selected_posts"))
    if any(_post_has_multimodal_conflict(post) for post in selected_posts):
        hints.append(
            {
                "hint_type": "multimodal_conflict",
                "description": "Cross-view conflict or undecodable media may justify stronger multimodal review triggers.",
            }
        )
    if any(_post_has_uncertain_stance_or_view(post) for post in selected_posts):
        hints.append(
            {
                "hint_type": "uncertainty_cluster",
                "description": "Repeated stance/post-view uncertainty may justify earlier review or retrieval thresholds.",
            }
        )
    if retrieval_bundle and not any(result.get("top_evidence") for result in retrieval_bundle.get("local_results") or []):
        hints.append(
            {
                "hint_type": "retrieval_gap",
                "description": "Local evidence coverage was weak; retrieval thresholds or query templates may need refinement.",
            }
        )
    if _has_countermeasure_context(report) or "CountermeasureAgent" in reports_by_agent:
        hints.append(
            {
                "hint_type": "countermeasure_context",
                "description": "High-risk context suggests reviewing post-judge countermeasure trigger conditions.",
            }
        )
    return hints[:8]


def _failure_mode_tags(
    *,
    report: dict[str, Any],
    context: dict[str, Any],
    retrieval_bundle: dict[str, Any] | None,
) -> list[str]:
    tags: list[str] = []
    selected_posts = _as_list(context.get("selected_posts"))
    if any(_post_has_multimodal_conflict(post) for post in selected_posts):
        tags.append("multimodal_conflict")
    if any(_post_has_uncertain_stance_or_view(post) for post in selected_posts):
        tags.append("uncertain_post_or_stance")
    if retrieval_bundle and (retrieval_bundle.get("audit") or {}).get("failures"):
        tags.append("external_retrieval_failure")
    if _has_propagation_tree_context(report):
        tags.append("propagation_context_present")
    return _dedupe_strs(tags)


async def _run_agent_batch(
    agents: list[str],
    *,
    context: dict[str, Any],
    reports_by_agent: dict[str, dict[str, Any]],
    provider: ReviewLLMAgentProvider | None,
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
    provider: ReviewLLMAgentProvider | None,
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


async def _run_self_refined_agent(
    *,
    agent_name: str,
    context: dict[str, Any],
    reports_by_agent: dict[str, dict[str, Any]],
    provider: ReviewLLMAgentProvider | None,
    state: dict[str, Any],
) -> list[dict[str, Any]]:
    draft = await _run_single_agent(
        agent_name,
        context=context,
        reports_by_agent=reports_by_agent,
        provider=provider,
        state=state,
        report_role_override=_report_role_name(agent_name, "draft"),
    )
    if draft.get("status") != "completed" or provider is None:
        if draft.get("status") == "completed":
            draft["report_role"] = _report_role_name(agent_name, "final")
        return [draft]
    critique = await _run_single_revision_step(
        agent_name=agent_name,
        revision_kind="critique",
        source_report=draft,
        context=context,
        reports_by_agent=reports_by_agent,
        provider=provider,
        state=state,
    )
    if critique.get("status") != "completed":
        draft["report_role"] = _report_role_name(agent_name, "final")
        return [draft, critique]
    final_report = await _run_single_revision_step(
        agent_name=agent_name,
        revision_kind="final",
        source_report=draft,
        critique_report=critique,
        context=context,
        reports_by_agent=reports_by_agent,
        provider=provider,
        state=state,
    )
    return [draft, critique, final_report]


async def _run_single_reflection_response(
    agent_name: str,
    *,
    context: dict[str, Any],
    reports_by_agent: dict[str, dict[str, Any]],
    provider: ReviewLLMAgentProvider,
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
        "You are the same Review expert agent responding to the QuestionReflectionAgent. "
        "Write a concise natural-language supplement in Chinese. Address missing "
        "evidence, conflicts, and what should change in your original analysis. "
        "Do not output JSON and do not claim final classifier authority."
    )
    user_prompt = _reflection_response_prompt(agent_name, context, reports_by_agent)
    try:
        provider_input_bundle = _provider_input_bundle_for_agent(
            response_agent_name,
            context=context,
        )
        report_text = await provider(
            agent_name=response_agent_name,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            input_bundle=provider_input_bundle,
            model=state["model"],
        )
    except Exception as exc:  # pragma: no cover
        error_text = str(exc) or exc.__class__.__name__
        sidecar = build_sidecar_for_agent(
            agent_name=agent_name,
            context=context,
            retrieval_bundle=state.get("retrieval_bundle"),
            debate_bundle=state.get("debate_bundle"),
        )
        sidecar = _enrich_agent_sidecar(sidecar, agent_name=agent_name, context=context)
        return {
            **base,
            "status": "failed",
            "error": error_text,
            "analysis_report": _analysis_report_payload(
                agent_name=response_agent_name,
                report_text=None,
                status="failed",
                error=error_text,
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
    sidecar = _enrich_agent_sidecar(
        sidecar,
        agent_name=response_agent_name,
        context=context,
        report_text=str(report_text).strip(),
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


async def _run_single_revision_step(
    *,
    agent_name: str,
    revision_kind: str,
    source_report: dict[str, Any],
    context: dict[str, Any],
    reports_by_agent: dict[str, dict[str, Any]],
    provider: ReviewLLMAgentProvider,
    state: dict[str, Any],
    critique_report: dict[str, Any] | None = None,
) -> dict[str, Any]:
    review_id = str(uuid4())
    report_role = _report_role_name(agent_name, revision_kind)
    base = {
        "review_id": review_id,
        "run_id": state["run_id"],
        "agent_name": agent_name,
        "report_role": report_role,
        "model": state["model"],
        "provider_name": state["provider_name"],
        "input_refs": context["input_refs"],
        "input_hash": state["input_hash"],
        "created_at": state["created_at"],
        "human_triggered_by": state["human_triggered_by"],
    }
    system_prompt = _revision_system_prompt(agent_name, revision_kind)
    user_prompt = _revision_user_prompt(
        agent_name=agent_name,
        revision_kind=revision_kind,
        source_report=source_report,
        critique_report=critique_report,
        context=context,
        reports_by_agent=reports_by_agent,
    )
    try:
        provider_input_bundle = _provider_input_bundle_for_agent(
            f"{agent_name}:{revision_kind}",
            context=context,
        )
        report_text = await provider(
            agent_name=f"{agent_name}:{revision_kind}",
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            input_bundle=provider_input_bundle,
            model=state["model"],
        )
    except Exception as exc:  # pragma: no cover
        error_text = str(exc) or exc.__class__.__name__
        sidecar = build_sidecar_for_agent(
            agent_name=agent_name,
            context=context,
            retrieval_bundle=state.get("retrieval_bundle"),
            debate_bundle=state.get("debate_bundle"),
        )
        sidecar = _enrich_agent_sidecar(sidecar, agent_name=agent_name, context=context)
        return {
            **base,
            "status": "failed",
            "error": error_text,
            "analysis_report": _analysis_report_payload(
                agent_name=agent_name,
                report_text=None,
                status="failed",
                error=error_text,
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
    sidecar = _enrich_agent_sidecar(
        sidecar,
        agent_name=agent_name,
        context=context,
        report_text=str(report_text).strip(),
    )
    return {
        **base,
        "status": "completed",
        "analysis_report": _analysis_report_payload(
            agent_name=agent_name,
            report_text=str(report_text).strip(),
            status="completed",
        ),
        "report_text": str(report_text).strip(),
        "report_format": "maro_style_natural_language_analysis_report",
        "system_audit_sidecar": sidecar,
        "structured_sidecar": sidecar,
        "sections_expected": AGENT_REPORT_SECTIONS[agent_name],
        "vision_required": _agent_requires_vision(agent_name, context=context, state=state),
        "vision_input_status": _vision_input_status(context),
        "safety_flags": _agent_safety_flags(agent_name),
    }


async def _run_single_agent(
    agent_name: str,
    *,
    context: dict[str, Any],
    reports_by_agent: dict[str, dict[str, Any]],
    provider: ReviewLLMAgentProvider | None,
    state: dict[str, Any],
    report_role_override: str | None = None,
) -> dict[str, Any]:
    review_id = str(uuid4())
    default_report_role = report_role_override or _default_report_role(agent_name)
    base = {
        "review_id": review_id,
        "run_id": state["run_id"],
        "agent_name": agent_name,
        "report_role": default_report_role,
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
        sidecar = _enrich_agent_sidecar(sidecar, agent_name=agent_name, context=context)
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
            sidecar = _enrich_agent_sidecar(sidecar, agent_name=agent_name, context=context)
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
        provider_input_bundle = _provider_input_bundle_for_agent(
            agent_name,
            context=context,
        )
        report_text = await provider(
            agent_name=agent_name,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            input_bundle=provider_input_bundle,
            model=state["model"],
        )
    except Exception as exc:  # pragma: no cover - covered through API/core tests
        error_text = str(exc) or exc.__class__.__name__
        sidecar = build_sidecar_for_agent(
            agent_name=agent_name,
            context=context,
            retrieval_bundle=state.get("retrieval_bundle"),
            debate_bundle=state.get("debate_bundle"),
        )
        sidecar = _enrich_agent_sidecar(sidecar, agent_name=agent_name, context=context)
        return {
            **base,
            "status": "failed",
            "error": error_text,
            "analysis_report": _analysis_report_payload(
                agent_name=agent_name,
                report_text=None,
                status="failed",
                error=error_text,
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
    sidecar = _enrich_agent_sidecar(
        sidecar,
        agent_name=agent_name,
        context=context,
        report_text=str(report_text).strip(),
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
        "schema_version": "review-maro-analysis-report-v1",
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


def _enrich_agent_sidecar(
    sidecar: dict[str, Any],
    *,
    agent_name: str,
    context: dict[str, Any],
    report_text: str | None = None,
) -> dict[str, Any]:
    enriched = dict(sidecar)
    governance_reference = context.get("governance_reference") or build_governance_reference_context(context)
    enriched["platform_reference_refs"] = governance_reference.get("platform_reference_refs") or []
    enriched["governance_reference"] = {
        "matched_categories": governance_reference.get("matched_categories") or [],
        "report_template": governance_reference.get("report_template") or {},
        "usage_boundary": governance_reference.get("usage_boundary") or {},
    }
    if agent_name == "HarmfulnessJudgeAgent":
        enriched["governance_report"] = build_governance_report_sidecar(
            context=context,
            report_text=report_text,
        )
    return enriched


def _agent_system_prompt(agent_name: str) -> str:
    return build_agent_system_prompt(agent_name)


def _agent_output_contract(agent_name: str) -> dict[str, Any]:
    return build_agent_output_contract(agent_name)


def _agent_user_prompt(
    agent_name: str,
    context: dict[str, Any],
    reports_by_agent: dict[str, dict[str, Any]],
) -> str:
    return build_agent_user_prompt(
        agent_name,
        context,
        reports_by_agent,
        policy_guidance=_policy_guidance_for_prompt(context),
    )


def _reflection_response_prompt(
    agent_name: str,
    context: dict[str, Any],
    reports_by_agent: dict[str, dict[str, Any]],
) -> str:
    return build_reflection_response_prompt(agent_name, context, reports_by_agent)


def _policy_guidance_for_prompt(context: dict[str, Any]) -> dict[str, Any]:
    policy = context.get("active_policy") or context.get("policy") or {}
    active_policy = policy.get("policy") if isinstance(policy, dict) and "policy" in policy else policy
    if not isinstance(active_policy, dict) or not active_policy:
        return {
            "active_policy_present": False,
            "judge_should_note": "未提供已激活的决策策略；请基于检测证据和人工确认需求进行建议性判断。",
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
        "error_memory_summary": context.get("error_memory_summary") or {},
        "judge_should_note": (
            "将已激活策略作为复核、检索和治理建议的参考依据；不要覆盖检测器原始输出。"
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


def _should_retry_status(status_code: int | None) -> bool:
    return status_code in {408, 409, 429, 500, 502, 503, 504}


def _should_retry_exception(exc: Exception) -> bool:
    return isinstance(exc, (httpx.TimeoutException, httpx.NetworkError, httpx.RemoteProtocolError))


def _retry_delay_seconds(base_delay: float, attempt: int) -> float:
    base = max(0.25, float(base_delay or 0.0))
    jitter = random.uniform(0.0, 0.35)
    return min(8.0, base * attempt) + jitter


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
    context = {
        "schema_version": "review-agent-input-bundle-v1",
        "input_refs": input_refs,
        "selected_posts": posts,
        "media_inputs": media_inputs,
        "propagation_context": propagation_context,
        "review_queue": _get(report, "review_harmfulness", "review_queue") or {},
        "review_execution": _get(report, "review_harmfulness", "review_execution") or {},
        "disarm_analysis": report.get("disarm_analysis") or {},
        "capability_boundary": {
            "media_policy": "file_reference_with_optional_base64",
            "video_keyframe_policy": "cover_or_first_frame_plus_uniform_top_k",
            "raw_video_direct_input": False,
            "account_identifiers_should_be_treated_as_pseudonymous": True,
        },
    }
    context["governance_reference"] = build_governance_reference_context(context)
    return context


def _select_posts(post_semantics: dict[str, Any], selected_post_ids: list[str]) -> list[dict[str, Any]]:
    posts = _semantic_posts(post_semantics)
    if not selected_post_ids:
        return posts[:5]
    wanted = {str(item) for item in selected_post_ids}
    selected = [post for post in _all_semantic_posts(post_semantics) if str(post.get("post_id")) in wanted]
    return selected[:20]


def _select_propagation_context(report: dict[str, Any], selected_tree_ids: list[str]) -> dict[str, Any]:
    return _select_propagation_context_impl(report, selected_tree_ids)


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
    return build_safety_flags(agent_name)


def _report_role_name(agent_name: str, stage: str) -> str:
    return build_report_role_name(agent_name, stage)


def _default_report_role(agent_name: str) -> str:
    return build_default_report_role(agent_name)


def _revision_system_prompt(agent_name: str, revision_kind: str) -> str:
    return build_revision_system_prompt(agent_name, revision_kind)


def _revision_user_prompt(
    *,
    agent_name: str,
    revision_kind: str,
    source_report: dict[str, Any],
    context: dict[str, Any],
    reports_by_agent: dict[str, dict[str, Any]],
    critique_report: dict[str, Any] | None = None,
) -> str:
    return build_revision_user_prompt(
        agent_name=agent_name,
        revision_kind=revision_kind,
        source_report=source_report,
        context=context,
        reports_by_agent=reports_by_agent,
        policy_guidance=_policy_guidance_for_prompt(context),
        critique_report=critique_report,
    )


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


def _provider_input_bundle_for_agent(
    agent_name: str,
    *,
    context: dict[str, Any],
) -> dict[str, Any]:
    """Avoid sending heavy visual payloads to agents that do not review raw media.

    The full agent context still reaches prompts via ``user_prompt``. This helper
    only trims provider-side ``media_inputs`` so that text-only agents do not pay
    repeated image/base64 transfer cost on multimodal datasets.
    """
    if _provider_should_receive_media(agent_name):
        return context
    trimmed = dict(context)
    trimmed["media_inputs"] = []
    return trimmed


def _provider_should_receive_media(agent_name: str) -> bool:
    normalized = str(agent_name or "")
    return (
        normalized == "MultimodalConsistencyAgent"
        or normalized.startswith("MultimodalConsistencyAgent")
        or normalized.startswith("FullDebate:")
    )


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
            raise ValueError(f"Unsupported Review agent: {item}")
        if name not in normalized:
            normalized.append(name)
    if not normalized:
        raise ValueError("At least one Review agent must be selected")
    return sorted(normalized, key=lambda name: AGENT_ORDER.index(name))


def _post_has_multimodal_conflict(post: dict[str, Any]) -> bool:
    view = post.get("post_view_detection") or {}
    if view.get("conflict"):
        return True
    review_reasons = _as_list(view.get("review_reason"))
    return any("conflict" in str(reason) or "media" in str(reason) for reason in review_reasons)


def _post_has_uncertain_stance_or_view(post: dict[str, Any]) -> bool:
    stance = post.get("stance") or {}
    post_view = post.get("post_view_detection") or {}
    if stance.get("abstain") or str(stance.get("label") or "").lower() in {"uncertain", "query", "unlinked"}:
        return True
    if str(post_view.get("final_harmfulness") or "").lower() == "uncertain":
        return True
    review_reasons = _as_list(post_view.get("review_reason"))
    return any("uncertain" in str(reason).lower() for reason in review_reasons)


def _has_propagation_tree_context(report: dict[str, Any]) -> bool:
    return _has_propagation_tree_context_impl(report)


def _has_countermeasure_context(report: dict[str, Any]) -> bool:
    risk_level = _text(_get(report, "scores", "risk_level"))
    review_level = _text(_get(report, "review_harmfulness", "global_summary", "review_harm_risk_level"))
    return risk_level in {"high", "critical"} or review_level in {"medium", "high"}


def _semantic_posts(post_semantics: dict[str, Any]) -> list[dict[str, Any]]:
    posts = _as_list(post_semantics.get("posts"))
    if posts:
        return posts
    return _as_list(post_semantics.get("aggregation_posts"))


def _all_semantic_posts(post_semantics: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for post in _as_list(post_semantics.get("posts")) + _as_list(post_semantics.get("aggregation_posts")):
        if not isinstance(post, dict):
            continue
        post_id = str(post.get("post_id") or "")
        key = post_id or json.dumps(post, ensure_ascii=False, sort_keys=True, default=str)
        if key in seen:
            continue
        seen.add(key)
        rows.append(post)
    return rows


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


def _dedupe_strs(values: list[Any]) -> list[str]:
    seen: set[str] = set()
    deduped: list[str] = []
    for item in values:
        value = str(item or "").strip()
        if not value or value in seen:
            continue
        seen.add(value)
        deduped.append(value)
    return deduped


def _text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()
