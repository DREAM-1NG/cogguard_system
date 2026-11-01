"""Review local multi-agent runtime.

The existing review queue describes what an Agent/RAG layer should review. This
module executes a concrete local multi-agent pass with distinct roles and a
shared blackboard. It stays offline and deterministic by default, while exposing
provider hooks for future LLM/RAG integration.
"""

from __future__ import annotations

from collections import Counter
from typing import Any, Protocol


MULTI_AGENT_METHOD_TRACE = [
    {
        "paper": "MARO, EMNLP 2025",
        "transfer": (
            "separate cross-domain misinformation judgement into role-specific "
            "agents and aggregate decisions with auditable rules"
        ),
    },
    {
        "paper": "ReAct, ICLR 2023",
        "transfer": (
            "make reasoning/action traces explicit through retrieval, review, and "
            "decision steps rather than a single opaque classifier"
        ),
    },
    {
        "paper": "DEFAME, 2025",
        "transfer": (
            "use multimodal expert outputs and evidence retrieval as fact-checking "
            "inputs before final claim judgement"
        ),
    },
    {
        "paper": "Multi-agent debate for fact-checking, 2024",
        "transfer": (
            "treat agents as reviewers/verifiers/explainers with disagreement and "
            "escalation fields"
        ),
    },
]


class ReviewAgentProvider(Protocol):
    """Optional offline/test provider hook for one local Review agent role."""

    def __call__(
        self,
        *,
        agent_name: str,
        blackboard: dict[str, Any],
        local_result: dict[str, Any],
    ) -> dict[str, Any] | None:
        ...


def execute_multi_agent_review(
    *,
    post_semantics: dict[str, Any] | None,
    review_harmfulness: dict[str, Any] | None,
    user_mil: dict[str, Any] | None = None,
    graph_export: dict[str, Any] | None = None,
    review_execution: dict[str, Any] | None = None,
    agent_provider: ReviewAgentProvider | None = None,
) -> dict[str, Any]:
    """Execute a deterministic multi-agent Review pass over in-report evidence."""
    blackboard = _build_blackboard(
        post_semantics=post_semantics or {},
        review_harmfulness=review_harmfulness or {},
        user_mil=user_mil or {},
        graph_export=graph_export or {},
        review_execution=review_execution or {},
    )
    provider_state = {
        "provider_configured": agent_provider is not None,
        "live_external_call": False,
        "results_used": 0,
        "failures": [],
    }

    agent_order = [
        "HarmReviewAgent",
        "StanceClaimAgent",
        "EvidenceRetrievalAgent",
        "UserMILAgent",
        "CommunityJudgeAgent",
        "CounterNarrativeAgent",
    ]
    agent_results = []
    for agent_name in agent_order:
        local_result = _execute_local_agent(agent_name, blackboard)
        result = _apply_provider(agent_name, blackboard, local_result, agent_provider, provider_state)
        blackboard["agent_outputs"][agent_name] = result
        agent_results.append(result)

    final_decision = _final_decision(blackboard, agent_results)

    return {
        "capability_boundary": {
            "status": "implemented_local_multi_agent_runtime",
            "multi_agent_runtime": True,
            "live_llm_or_external_rag": bool(provider_state["live_external_call"]),
            "pluggable_agent_provider": bool(provider_state["provider_configured"]),
            "trained_agent_policy": False,
            "provider_failure_policy": "fallback_to_local_agents",
            "description": (
                "Executes distinct Review agent roles over a shared in-report "
                "blackboard. Default execution is deterministic and offline; "
                "provider hooks can override individual agent outputs in tests "
                "or future deployments."
            ),
        },
        "method_trace": MULTI_AGENT_METHOD_TRACE,
        "summary": {
            "agents_executed": len(agent_results),
            "blackboard_posts": len(blackboard["posts"]),
            "blackboard_accounts": len(blackboard["accounts"]),
            "blackboard_communities": len(blackboard["communities"]),
            "provider_results_used": provider_state["results_used"],
            "provider_failures": len(provider_state["failures"]),
            "external_followup_required": bool(final_decision["external_followup_required"]),
        },
        "blackboard": _public_blackboard(blackboard),
        "agent_results": agent_results,
        "final_decision": final_decision,
        "provider_audit": {
            "provider_configured": provider_state["provider_configured"],
            "results_used": provider_state["results_used"],
            "live_external_call": provider_state["live_external_call"],
            "failures": provider_state["failures"][:10],
        },
    }


def _build_blackboard(
    *,
    post_semantics: dict[str, Any],
    review_harmfulness: dict[str, Any],
    user_mil: dict[str, Any],
    graph_export: dict[str, Any],
    review_execution: dict[str, Any],
) -> dict[str, Any]:
    posts = _semantic_posts(post_semantics)
    accounts = _as_list(_get(review_harmfulness, "user_level", "accounts"))
    communities = _as_list(_get(review_harmfulness, "community_level", "communities"))
    return {
        "posts": posts,
        "accounts": accounts,
        "communities": communities,
        "claims": _as_list(_get(review_harmfulness, "global_summary", "claim_rank")),
        "user_mil_accounts": _as_list(user_mil.get("accounts")),
        "graph_summary": graph_export.get("summary") or {},
        "review_summary": review_execution.get("summary") or {},
        "retrieval_results": _as_list(review_execution.get("retrieval_results")),
        "review_results": _as_list(review_execution.get("review_results")),
        "counter_narrative_drafts": _as_list(review_execution.get("counter_narrative_drafts")),
        "agent_outputs": {},
    }


def _execute_local_agent(agent_name: str, blackboard: dict[str, Any]) -> dict[str, Any]:
    if agent_name == "HarmReviewAgent":
        return _harm_review_agent(blackboard)
    if agent_name == "StanceClaimAgent":
        return _stance_claim_agent(blackboard)
    if agent_name == "EvidenceRetrievalAgent":
        return _evidence_retrieval_agent(blackboard)
    if agent_name == "UserMILAgent":
        return _user_mil_agent(blackboard)
    if agent_name == "CommunityJudgeAgent":
        return _community_judge_agent(blackboard)
    if agent_name == "CounterNarrativeAgent":
        return _counter_narrative_agent(blackboard)
    return _agent_result(agent_name, "unknown_agent", "monitor", 0.0, [], {})


def _harm_review_agent(blackboard: dict[str, Any]) -> dict[str, Any]:
    harmful = [post for post in blackboard["posts"] if _get(post, "harmfulness", "label") == "harmful"]
    uncertain = [
        post
        for post in blackboard["posts"]
        if _get(post, "harmfulness", "label") == "uncertain" or _get(post, "harmfulness", "abstain")
    ]
    harm_types = Counter()
    for post in harmful:
        harm_types.update(_as_list(_get(post, "harmfulness", "types")))
    score = len(harmful) / len(blackboard["posts"]) if blackboard["posts"] else 0.0
    confidence = min(0.9, 0.45 + 0.1 * len(harmful) + 0.05 * len(harm_types))
    decision = "harmful_posts_present" if harmful else "monitor"
    if uncertain and not harmful:
        decision = "needs_post_review"
    return _agent_result(
        "HarmReviewAgent",
        decision,
        "escalate" if harmful or uncertain else "monitor",
        confidence,
        [
            f"harmful_posts={len(harmful)}",
            f"uncertain_posts={len(uncertain)}",
            f"harm_types={dict(harm_types)}",
        ],
        {
            "harmful_posts": [_post_ref(post) for post in harmful[:5]],
            "uncertain_posts": [_post_ref(post) for post in uncertain[:5]],
            "harm_type_distribution": dict(harm_types),
            "harmful_ratio": round(score, 4),
        },
    )


def _stance_claim_agent(blackboard: dict[str, Any]) -> dict[str, Any]:
    stance_distribution = Counter(_text(_get(post, "stance", "label")) or "unknown" for post in blackboard["posts"])
    claim_counter = Counter()
    unlinked = 0
    low_confidence = 0
    for post in blackboard["posts"]:
        claim_id = _text(_get(post, "primary_claim", "claim_id"))
        if claim_id:
            claim_counter[claim_id] += 1
        else:
            unlinked += 1
        if _safe_float(_get(post, "stance", "confidence")) < 0.45:
            low_confidence += 1
    confidence = max(0.25, min(0.85, 0.75 - 0.05 * unlinked - 0.03 * low_confidence))
    decision = "claim_grounding_needs_review" if unlinked or low_confidence else "claim_grounding_supported"
    return _agent_result(
        "StanceClaimAgent",
        decision,
        "retrieve_evidence" if decision == "claim_grounding_needs_review" else "support",
        confidence,
        [
            f"linked_claims={len(claim_counter)}",
            f"unlinked_posts={unlinked}",
            f"low_confidence_stance={low_confidence}",
        ],
        {
            "stance_distribution": dict(stance_distribution),
            "top_claims": claim_counter.most_common(5),
            "unlinked_posts": unlinked,
            "low_confidence_stance": low_confidence,
        },
    )


def _evidence_retrieval_agent(blackboard: dict[str, Any]) -> dict[str, Any]:
    retrieval_results = blackboard["retrieval_results"]
    found = sum(_safe_int(result.get("evidence_found")) for result in retrieval_results)
    external_required = sum(1 for result in retrieval_results if result.get("external_retrieval_required"))
    confidence = min(0.88, 0.35 + 0.08 * found)
    decision = "local_evidence_available" if found else "needs_external_retrieval"
    if external_required:
        decision = "partial_evidence_needs_external_retrieval"
    return _agent_result(
        "EvidenceRetrievalAgent",
        decision,
        "retrieve_external" if external_required or not found else "support",
        confidence,
        [
            f"retrieval_tasks={len(retrieval_results)}",
            f"evidence_found={found}",
            f"external_required={external_required}",
        ],
        {
            "retrieval_tasks": len(retrieval_results),
            "evidence_found": found,
            "external_retrieval_required": external_required,
            "top_evidence": [
                evidence
                for result in retrieval_results[:5]
                for evidence in _as_list(result.get("top_evidence"))[:2]
            ][:6],
        },
    )


def _user_mil_agent(blackboard: dict[str, Any]) -> dict[str, Any]:
    mil_accounts = blackboard["user_mil_accounts"]
    harmful_accounts = [account for account in mil_accounts if account.get("label") == "harmful"]
    uncertain_accounts = [account for account in mil_accounts if account.get("label") == "uncertain"]
    top_accounts = sorted(mil_accounts, key=lambda item: _safe_float(item.get("mil_harm_score")), reverse=True)[:5]
    confidence = min(0.9, 0.4 + 0.08 * len(top_accounts) + 0.05 * len(harmful_accounts))
    if harmful_accounts:
        decision = "persistent_user_harm_supported_by_mil"
    elif uncertain_accounts:
        decision = "user_harm_uncertain"
    else:
        decision = "user_harm_monitor"
    return _agent_result(
        "UserMILAgent",
        decision,
        "escalate" if harmful_accounts or uncertain_accounts else "monitor",
        confidence,
        [
            f"mil_account_bags={len(mil_accounts)}",
            f"harmful_accounts={len(harmful_accounts)}",
            f"uncertain_accounts={len(uncertain_accounts)}",
        ],
        {
            "harmful_accounts": [_account_ref(account) for account in harmful_accounts[:5]],
            "uncertain_accounts": [_account_ref(account) for account in uncertain_accounts[:5]],
            "top_attention_accounts": [_account_ref(account) for account in top_accounts],
        },
    )


def _community_judge_agent(blackboard: dict[str, Any]) -> dict[str, Any]:
    communities = blackboard["communities"]
    high_harm = [community for community in communities if _get(community, "risk_flags", "high_collective_harm")]
    amplified = [
        community for community in communities if _get(community, "risk_flags", "coordinated_harm_amplification")
    ]
    confidence = min(0.9, 0.42 + 0.12 * len(high_harm) + 0.1 * len(amplified))
    decision = "collective_harm_supported" if high_harm else "community_monitor"
    action = "escalate" if high_harm or amplified else "monitor"
    return _agent_result(
        "CommunityJudgeAgent",
        decision,
        action,
        confidence,
        [
            f"communities={len(communities)}",
            f"high_collective_harm={len(high_harm)}",
            f"coordinated_amplification={len(amplified)}",
        ],
        {
            "high_harm_communities": [_community_ref(community) for community in high_harm[:5]],
            "amplified_communities": [_community_ref(community) for community in amplified[:5]],
            "graph_summary": blackboard["graph_summary"],
        },
    )


def _counter_narrative_agent(blackboard: dict[str, Any]) -> dict[str, Any]:
    drafts = blackboard["counter_narrative_drafts"]
    harmful_claims = [claim for claim in blackboard["claims"] if _safe_int(claim.get("harmful_posts")) > 0]
    confidence = min(0.86, 0.35 + 0.1 * len(drafts) + 0.05 * len(harmful_claims))
    decision = "counter_narrative_ready_for_human_review" if drafts else "counter_narrative_not_required_yet"
    return _agent_result(
        "CounterNarrativeAgent",
        decision,
        "human_review" if drafts else "monitor",
        confidence,
        [
            f"drafts={len(drafts)}",
            f"harmful_claims={len(harmful_claims)}",
            "human approval required before publication",
        ],
        {
            "drafts": drafts[:5],
            "harmful_claims": harmful_claims[:5],
            "requires_human_approval": bool(drafts),
        },
    )


def _agent_result(
    agent_name: str,
    decision: str,
    recommended_action: str,
    confidence: float,
    rationale: list[str],
    evidence: dict[str, Any],
) -> dict[str, Any]:
    return {
        "agent": agent_name,
        "execution_status": "executed_local_agent",
        "execution_mode": "deterministic_shared_blackboard_agent",
        "decision": decision,
        "recommended_action": recommended_action,
        "confidence": round(max(0.0, min(1.0, confidence)), 4),
        "rationale": rationale,
        "evidence": evidence,
    }


def _apply_provider(
    agent_name: str,
    blackboard: dict[str, Any],
    local_result: dict[str, Any],
    agent_provider: ReviewAgentProvider | None,
    provider_state: dict[str, Any],
) -> dict[str, Any]:
    if agent_provider is None:
        return local_result
    try:
        provider_result = agent_provider(
            agent_name=agent_name,
            blackboard=blackboard,
            local_result=local_result,
        )
    except Exception as exc:  # pragma: no cover - tested through provider failure hooks
        provider_state["failures"].append(
            {
                "agent": agent_name,
                "error_type": type(exc).__name__,
                "message": _text(exc),
            }
        )
        return {**local_result, "provider_status": "fallback_after_provider_error"}

    if not isinstance(provider_result, dict):
        return {**local_result, "provider_status": "fallback_after_empty_provider_result"}
    result = {**local_result, **provider_result}
    result["agent"] = result.get("agent") or agent_name
    result["execution_status"] = result.get("execution_status") or "executed_provider_agent"
    result["execution_mode"] = result.get("execution_mode") or "pluggable_agent_provider"
    result["provider_status"] = "provider_result_used"
    provider_state["results_used"] += 1
    provider_state["live_external_call"] = provider_state["live_external_call"] or bool(
        result.get("live_external_call")
    )
    return result


def _final_decision(blackboard: dict[str, Any], agent_results: list[dict[str, Any]]) -> dict[str, Any]:
    actions = Counter(_text(result.get("recommended_action")) for result in agent_results)
    confidence_values = [_safe_float(result.get("confidence")) for result in agent_results]
    avg_confidence = sum(confidence_values) / len(confidence_values) if confidence_values else 0.0
    external_followup = any(
        action in {"retrieve_external", "human_review", "escalate"}
        for action in actions
    )
    if actions.get("escalate", 0) >= 2:
        decision = "high_priority_harmfulness_review"
    elif actions.get("escalate") or actions.get("retrieve_external") or actions.get("human_review"):
        decision = "targeted_followup_required"
    else:
        decision = "monitor"
    return {
        "decision": decision,
        "avg_agent_confidence": round(avg_confidence, 4),
        "recommended_actions": dict(actions),
        "external_followup_required": external_followup,
        "top_claims": blackboard["claims"][:5],
        "publish_counter_narrative_without_human_approval": False,
    }


def _public_blackboard(blackboard: dict[str, Any]) -> dict[str, Any]:
    return {
        "post_count": len(blackboard["posts"]),
        "account_count": len(blackboard["accounts"]),
        "community_count": len(blackboard["communities"]),
        "claim_count": len(blackboard["claims"]),
        "user_mil_account_count": len(blackboard["user_mil_accounts"]),
        "graph_summary": blackboard["graph_summary"],
        "review_summary": blackboard["review_summary"],
    }


def _semantic_posts(post_semantics: dict[str, Any]) -> list[dict[str, Any]]:
    posts = post_semantics.get("aggregation_posts")
    if isinstance(posts, list):
        return posts
    posts = post_semantics.get("posts")
    return posts if isinstance(posts, list) else []


def _post_ref(post: dict[str, Any]) -> dict[str, Any]:
    return {
        "post_id": post.get("post_id"),
        "author_id": post.get("author_id"),
        "harm_score": _safe_float(_get(post, "harmfulness", "score")),
        "harm_types": _as_list(_get(post, "harmfulness", "types")),
        "primary_claim": post.get("primary_claim"),
    }


def _account_ref(account: dict[str, Any]) -> dict[str, Any]:
    return {
        "account_id": account.get("account_id"),
        "label": account.get("label") or _get(account, "risk_profile_flags", "high_harmful"),
        "mil_harm_score": _safe_float(account.get("mil_harm_score")),
        "bag_size": _safe_int(account.get("bag_size")),
        "attention_posts": _as_list(account.get("attention_posts"))[:2],
    }


def _community_ref(community: dict[str, Any]) -> dict[str, Any]:
    return {
        "community_id": community.get("community_id"),
        "harmful_posts": _safe_int(_get(community, "risk_summary", "harmful_posts")),
        "amplification_score": _safe_float(_get(community, "risk_summary", "amplification_score")),
        "risk_flags": community.get("risk_flags") or {},
    }


def _get(value: Any, *path: str) -> Any:
    current = value or {}
    for key in path:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _text(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def _safe_float(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _safe_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0
