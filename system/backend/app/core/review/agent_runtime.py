"""Runtime policy for analyst-triggered Review Agent review.

This module owns the rules that decide which Agents run, whether the review
uses simple or complex mode, and which audit hints are emitted. It does not
execute Agents or call providers.
"""

from __future__ import annotations

from typing import Any

from app.core.review.propagation_agent import has_propagation_tree_context


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

__all__ = [
    "AGENT_ORDER",
    "EXPERT_AGENTS",
    "FOLLOWUP_AGENTS",
    "build_candidate_rule_hints",
    "build_execution_plan_for_runtime",
    "build_failure_mode_tags",
    "has_countermeasure_context",
    "has_multimodal_conflict",
    "has_uncertain_stance_or_view",
    "normalize_agent_names",
    "recommend_runtime_mode",
    "resolve_runtime_mode",
    "select_reflection_response_agents",
    "should_postpone_countermeasure",
]


def normalize_agent_names(agent_names: list[str]) -> list[str]:
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


def resolve_runtime_mode(
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
    recommended, reasons = recommend_runtime_mode(report=report, context=context)
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


def recommend_runtime_mode(*, report: dict[str, Any], context: dict[str, Any]) -> tuple[str, list[str]]:
    reasons: list[str] = []
    selected_posts = _as_list(context.get("selected_posts"))
    review_queue = _get(report, "review_harmfulness", "review_queue") or {}
    if len(selected_posts) > 1:
        reasons.append("multiple_selected_posts")
    if any(has_multimodal_conflict(post) for post in selected_posts):
        reasons.append("multimodal_conflict_or_media_gap")
    if review_queue.get("retrieval_tasks"):
        reasons.append("claim_retrieval_tasks_present")
    if has_propagation_tree_context(report):
        reasons.append("propagation_context_present")
    if any(has_uncertain_stance_or_view(post) for post in selected_posts):
        reasons.append("stance_or_post_view_uncertain")
    return ("complex", reasons) if reasons else ("simple", ["single_post_low_conflict"])


def build_execution_plan_for_runtime(
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


def select_reflection_response_agents(
    *,
    expert_agents: list[str],
    reports_by_agent: dict[str, dict[str, Any]],
    explicit_targets: list[str] | None = None,
) -> list[str]:
    """Choose completed experts for the bounded QuestionReflection response pass."""
    completed = [
        agent
        for agent in expert_agents
        if (reports_by_agent.get(agent) or {}).get("status") == "completed"
    ]
    if explicit_targets is not None:
        requested = _dedupe_strs(explicit_targets)
        return [agent for agent in requested if agent in completed]

    reflection_text = " ".join(
        str(value or "")
        for value in (reports_by_agent.get("QuestionReflectionAgent") or {}).values()
        if isinstance(value, (str, int, float))
    ).lower()
    mentioned = [agent for agent in completed if agent.lower() in reflection_text]
    return (mentioned + [agent for agent in completed if agent not in mentioned])[:2]


def should_postpone_countermeasure(*, report: dict[str, Any], reports_by_agent: dict[str, dict[str, Any]]) -> bool:
    if has_countermeasure_context(report):
        return True
    judge_report = reports_by_agent.get("HarmfulnessJudgeAgent") or {}
    judge_text = str(judge_report.get("report_text") or "").lower()
    return "鍙嶅埗" in str(judge_report.get("report_text") or "") or "countermeasure" in judge_text


def build_candidate_rule_hints(
    *,
    report: dict[str, Any],
    context: dict[str, Any],
    retrieval_bundle: dict[str, Any] | None,
    reports_by_agent: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    hints: list[dict[str, Any]] = []
    selected_posts = _as_list(context.get("selected_posts"))
    if any(has_multimodal_conflict(post) for post in selected_posts):
        hints.append(
            {
                "hint_type": "multimodal_conflict",
                "description": "Cross-view conflict or undecodable media may justify stronger multimodal review triggers.",
            }
        )
    if any(has_uncertain_stance_or_view(post) for post in selected_posts):
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
    if has_countermeasure_context(report) or "CountermeasureAgent" in reports_by_agent:
        hints.append(
            {
                "hint_type": "countermeasure_context",
                "description": "High-risk context suggests reviewing post-judge countermeasure trigger conditions.",
            }
        )
    return hints[:8]


def build_failure_mode_tags(
    *,
    report: dict[str, Any],
    context: dict[str, Any],
    retrieval_bundle: dict[str, Any] | None,
) -> list[str]:
    tags: list[str] = []
    selected_posts = _as_list(context.get("selected_posts"))
    if any(has_multimodal_conflict(post) for post in selected_posts):
        tags.append("multimodal_conflict")
    if any(has_uncertain_stance_or_view(post) for post in selected_posts):
        tags.append("uncertain_post_or_stance")
    if retrieval_bundle and (retrieval_bundle.get("audit") or {}).get("failures"):
        tags.append("external_retrieval_failure")
    if has_propagation_tree_context(report):
        tags.append("propagation_context_present")
    return _dedupe_strs(tags)


def has_multimodal_conflict(post: dict[str, Any]) -> bool:
    view = post.get("post_view_detection") or {}
    if view.get("conflict"):
        return True
    return any("conflict" in str(reason) or "media" in str(reason) for reason in _as_list(view.get("review_reason")))


def has_uncertain_stance_or_view(post: dict[str, Any]) -> bool:
    stance = post.get("stance") or {}
    post_view = post.get("post_view_detection") or {}
    if stance.get("abstain") or str(stance.get("label") or "").lower() in {"uncertain", "query", "unlinked"}:
        return True
    if str(post_view.get("final_harmfulness") or "").lower() == "uncertain":
        return True
    return any("uncertain" in str(reason).lower() for reason in _as_list(post_view.get("review_reason")))


def has_countermeasure_context(report: dict[str, Any]) -> bool:
    risk_level = _text(_get(report, "scores", "risk_level"))
    review_level = _text(_get(report, "review_harmfulness", "global_summary", "review_harm_risk_level"))
    return risk_level in {"high", "critical"} or review_level in {"medium", "high"}


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

