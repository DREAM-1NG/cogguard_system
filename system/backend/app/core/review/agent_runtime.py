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

REVIEW_TASKS = {"interpersonal_harm", "claim_deception"}
TASK_EXPERTS = {
    "interpersonal_harm": "PostHarmAgent",
    "claim_deception": "ClaimEvidenceAgent",
}

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
    "REVIEW_TASKS",
    "TASK_EXPERTS",
    "build_candidate_rule_hints",
    "build_execution_plan_for_runtime",
    "build_failure_mode_tags",
    "has_countermeasure_context",
    "has_multimodal_conflict",
    "has_uncertain_stance_or_view",
    "normalize_agent_names",
    "normalize_review_task",
    "recommend_runtime_mode",
    "resolve_runtime_mode",
    "select_reflection_response_agents",
    "should_postpone_countermeasure",
]


def normalize_review_task(value: str | None) -> str | None:
    """Normalize the two text Review task contracts without inventing a flat label."""

    if value is None or not str(value).strip():
        return None
    task = str(value).strip().lower()
    aliases = {
        "harm": "interpersonal_harm",
        "hate": "interpersonal_harm",
        "offense": "interpersonal_harm",
        "misinformation": "claim_deception",
        "misinfo": "claim_deception",
        "claim": "claim_deception",
    }
    task = aliases.get(task, task)
    if task not in REVIEW_TASKS:
        raise ValueError(f"Unsupported Review task: {value}")
    return task


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
    enable_countermeasure: bool = True,
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
    if enable_countermeasure and "CountermeasureAgent" in normalized_agents:
        forced_complex_reasons.append("countermeasure_selected")

    if requested == "auto":
        if forced_complex_reasons:
            effective = "complex"
            upgraded = recommended != "complex"
            reasons = [*reasons, *forced_complex_reasons]
        else:
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
        reasons.append("multimodal_conflict_confirmed")
    if _has_valid_claim_context(report=report, context=context) and review_queue.get("retrieval_tasks"):
        reasons.append("claim_retrieval_tasks_present")
    if has_propagation_tree_context(report):
        reasons.append("propagation_context_present")
    claim_context_valid = _has_valid_claim_context(report=report, context=context)
    if any(
        has_uncertain_stance_or_view(post, claim_context_valid=claim_context_valid)
        for post in selected_posts
    ):
        reasons.append("stance_or_post_view_uncertain")
    return ("complex", reasons) if reasons else ("simple", ["single_post_low_conflict"])


def build_execution_plan_for_runtime(
    *,
    requested_agents: list[str],
    runtime_mode: str,
    enable_deep_judge: bool,
    enable_countermeasure: bool = True,
    report: dict[str, Any] | None = None,
    context: dict[str, Any] | None = None,
    forced_agent_names: list[str] | None = None,
) -> dict[str, Any]:
    requested = [agent for agent in requested_agents if agent in AGENT_ORDER]
    review_task = normalize_review_task((context or {}).get("review_task"))
    task_expert = TASK_EXPERTS.get(review_task)
    if task_expert and task_expert not in requested:
        requested.append(task_expert)
    capabilities = _derive_review_capabilities(report=report, context=context)
    capability_filtering_enabled = (report is not None or context is not None)
    forced = _ordered_agents(forced_agent_names or [])
    requested_experts = [agent for agent in requested if agent in EXPERT_AGENTS]
    task_filtered_agents = [
        {
            "agent_name": agent,
            "reason": "not_required_for_review_task",
        }
        for agent in requested_experts
        if task_expert and agent != task_expert and agent not in forced
    ]
    if task_expert:
        requested_experts = [
            agent for agent in requested_experts if agent == task_expert or agent in forced
        ]
    eligible_agents = [
        agent
        for agent in requested_experts
        if not capability_filtering_enabled or _agent_missing_capabilities(agent, capabilities) == []
    ]
    skipped_agents = task_filtered_agents + [
        {
            "agent_name": agent,
            "reason": _agent_skip_reason(agent, capabilities),
        }
        for agent in requested_experts
        if capability_filtering_enabled and _agent_missing_capabilities(agent, capabilities)
        and agent not in forced
    ]
    overrides = [
        {
            "agent_name": agent,
            "reason": "analyst_forced_selection",
            "missing_capabilities": _agent_missing_capabilities(agent, capabilities),
        }
        for agent in requested_experts
        if capability_filtering_enabled
        and agent in forced
        and _agent_missing_capabilities(agent, capabilities)
    ]
    expert_agents = _ordered_agents([*eligible_agents, *[item["agent_name"] for item in overrides]])
    if not expert_agents and review_task != "claim_deception":
        expert_agents = ["PostHarmAgent"]
    if runtime_mode == "simple":
        if "HarmfulnessJudgeAgent" not in requested:
            requested = [*requested, "HarmfulnessJudgeAgent"]
        return {
            "expert_agents": expert_agents,
            "followup_agents": ["HarmfulnessJudgeAgent"],
            "requested_agents": requested,
            "eligible_agents": eligible_agents,
            "executed_agents": [*expert_agents, "HarmfulnessJudgeAgent"],
            "skipped_agents": skipped_agents,
            "overrides": overrides,
            "capabilities": capabilities,
            "run_question_reflection": False,
            "run_reflection_responses": False,
            "deep_judge": False,
            "run_countermeasure": False,
            "claim_agent_enabled": "ClaimEvidenceAgent" in expert_agents,
            "multimodal_agent_enabled": "MultimodalConsistencyAgent" in expert_agents,
            "review_task": review_task,
            "task_expert": task_expert,
        }
    run_question_reflection = bool(expert_agents)
    followup_agents: list[str] = []
    if run_question_reflection:
        followup_agents.append("QuestionReflectionAgent")
    followup_agents.append("HarmfulnessJudgeAgent")
    if enable_countermeasure and "CountermeasureAgent" in requested:
        followup_agents.append("CountermeasureAgent")
    followup_agents = _dedupe_strs(followup_agents)
    return {
        "expert_agents": expert_agents,
        "followup_agents": followup_agents,
        "requested_agents": requested,
        "eligible_agents": eligible_agents,
        "executed_agents": [*expert_agents, *followup_agents],
        "skipped_agents": skipped_agents,
        "overrides": overrides,
        "capabilities": capabilities,
        "run_question_reflection": run_question_reflection,
        "run_reflection_responses": run_question_reflection,
        "deep_judge": bool(enable_deep_judge),
        "run_countermeasure": bool(enable_countermeasure and "CountermeasureAgent" in requested),
        "claim_agent_enabled": "ClaimEvidenceAgent" in expert_agents,
        "multimodal_agent_enabled": "MultimodalConsistencyAgent" in expert_agents,
        "review_task": review_task,
        "task_expert": task_expert,
    }


def _derive_review_capabilities(
    *,
    report: dict[str, Any] | None,
    context: dict[str, Any] | None,
) -> dict[str, bool]:
    report = report or {}
    context = context or {}
    selected_posts = [post for post in _as_list(context.get("selected_posts")) if isinstance(post, dict)]
    review = report.get("review_harmfulness") or {}
    review_queue = review.get("review_queue") or context.get("review_queue") or {}
    claim_context = bool(
        review_queue.get("retrieval_tasks")
        or _get(review, "global_summary", "claim_rank")
        or context.get("claim_rank")
        or any(post.get("claims") or _get(post, "post_view_detection", "claims") for post in selected_posts)
    )
    claim_assessment_input = bool(
        claim_context
        or any(
            str(post.get(field) or "").strip()
            for post in selected_posts
            for field in ("content", "text", "excerpt")
        )
    )
    usable_media = bool(
        any(_has_usable_media_input(item) for item in _as_list(context.get("media_inputs")))
        or any(_post_has_usable_media(post) for post in selected_posts)
    )
    cross_view_conflict = any(has_multimodal_conflict(post) for post in selected_posts)
    return {
        "claim_context": claim_context,
        "claim_assessment_input": claim_assessment_input,
        "usable_media": usable_media,
        "cross_view_conflict": cross_view_conflict,
        "propagation_tree_or_post_post_edges": _has_propagation_tree_or_post_post_edges(report, context),
    }


def _agent_missing_capabilities(agent_name: str, capabilities: dict[str, bool]) -> list[str]:
    requirements = {
        "PostHarmAgent": [],
        "ClaimEvidenceAgent": ["claim_assessment_input"],
        "MultimodalConsistencyAgent": ["usable_media_or_cross_view_conflict"],
        "PropagationTreeAgent": ["propagation_tree_or_post_post_edges"],
    }.get(agent_name, [])
    return [
        requirement
        for requirement in requirements
        if not (
            requirement == "usable_media_or_cross_view_conflict"
            and (capabilities["usable_media"] or capabilities["cross_view_conflict"])
        )
        and not capabilities.get(requirement, False)
    ]


def _agent_skip_reason(agent_name: str, capabilities: dict[str, bool]) -> str:
    missing = _agent_missing_capabilities(agent_name, capabilities)
    return f"missing_{missing[0]}" if missing else "not_applicable"


def _has_usable_media_input(item: Any) -> bool:
    if not isinstance(item, dict):
        return False
    return bool(item.get("data_url") or item.get("uri")) and str(item.get("media_type") or "") != "derived_text_only"


def _post_has_usable_media(post: dict[str, Any]) -> bool:
    evidence = post.get("evidence") or {}
    return bool(post.get("media_urls") or evidence.get("media_urls"))


def _has_propagation_tree_or_post_post_edges(report: dict[str, Any], context: dict[str, Any]) -> bool:
    review = report.get("review_harmfulness") or {}
    propagation_context = context.get("propagation_context") or review.get("propagation_context") or {}
    tree_metrics = propagation_context.get("tree_metrics") if isinstance(propagation_context, dict) else {}
    tree_metrics = tree_metrics if isinstance(tree_metrics, dict) else {}
    if isinstance(propagation_context, dict) and (
        propagation_context.get("has_thread_context")
        or int(tree_metrics.get("edge_count") or 0) > 0
        or int(tree_metrics.get("node_count") or 0) > 1
    ):
        return True
    graph_summary = _get(review, "graph_export", "summary") or _get(context, "propagation_context", "graph_summary") or {}
    edge_types = _as_list(graph_summary.get("edge_types")) if isinstance(graph_summary, dict) else []
    return any(
        str(edge_type).lower().replace("-", "_") in {"post_post", "repost", "quote", "reply"}
        for edge_type in edge_types
    )


def _ordered_agents(agent_names: list[str]) -> list[str]:
    return sorted(_dedupe_strs([agent for agent in agent_names if agent in AGENT_ORDER]), key=AGENT_ORDER.index)


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
    return "反制" in str(judge_report.get("report_text") or "") or "countermeasure" in judge_text


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
    conflict = view.get("conflict")
    if isinstance(conflict, dict):
        if conflict.get("has_conflict") is True or conflict.get("label_conflict") is True:
            return True
        try:
            if float(conflict.get("score") or 0.0) >= 0.7:
                return True
        except (TypeError, ValueError):
            pass
    elif conflict is True:
        return True
    return any(_is_confirmed_conflict_reason(reason) for reason in _as_list(view.get("review_reason")))


def has_uncertain_stance_or_view(
    post: dict[str, Any],
    *,
    claim_context_valid: bool | None = None,
) -> bool:
    stance = post.get("stance") or {}
    post_view = post.get("post_view_detection") or {}
    stance_label = str(stance.get("label") or "").lower()
    if (
        (stance.get("abstain") and claim_context_valid is not False)
        or stance_label in {"uncertain", "query"}
    ):
        return True
    if stance_label == "unlinked" and claim_context_valid is not False:
        return True
    reasons = _as_list(post_view.get("review_reason"))
    if str(post_view.get("final_harmfulness") or "").lower() == "uncertain" and not _media_only_uncertainty(reasons):
        return True
    return any(
        "uncertain" in str(reason).lower() and not _media_only_reason(reason)
        for reason in reasons
    )


def _has_valid_claim_context(*, report: dict[str, Any], context: dict[str, Any]) -> bool:
    review = report.get("review_harmfulness") or {}
    review_queue = review.get("review_queue") or context.get("review_queue") or {}
    if review_queue.get("retrieval_tasks"):
        return True
    if _get(review, "global_summary", "claim_rank") or context.get("claim_rank"):
        return True
    selected_posts = [post for post in _as_list(context.get("selected_posts")) if isinstance(post, dict)]
    return any(
        post.get("claims")
        or post.get("primary_claim")
        or _get(post, "post_view_detection", "claims")
        or _get(post, "stance", "claim_id")
        for post in selected_posts
    )


def _is_confirmed_conflict_reason(reason: Any) -> bool:
    lowered = str(reason or "").lower()
    return "conflict" in lowered and not any(
        marker in lowered for marker in ("unavailable", "missing", "decode", "not available")
    )


def _media_only_reason(reason: Any) -> bool:
    lowered = str(reason or "").lower()
    return any(marker in lowered for marker in ("media", "image", "video", "meme", "vision", "unavailable", "missing", "decode"))


def _media_only_uncertainty(reasons: list[Any]) -> bool:
    meaningful = [reason for reason in reasons if str(reason or "").strip()]
    return bool(meaningful) and all(_media_only_reason(reason) for reason in meaningful)


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
