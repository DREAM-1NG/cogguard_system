"""KT3 reviewer and RAG task queue scaffold.

The production model path should remain deterministic and testable. This module
therefore does not call a live LLM or retriever. It converts uncertain or
high-risk KT3 outputs into a structured queue that a future RAG / multi-agent
review layer can consume.
"""

from __future__ import annotations

from collections import Counter
from typing import Any


MAX_QUERY_CHARS = 220


def build_kt3_review_queue(
    *,
    post_semantics: dict[str, Any] | None,
    kt3_harmfulness: dict[str, Any] | None,
    max_items: int = 20,
) -> dict[str, Any]:
    """Build a deterministic review queue from KT3 post/user/community outputs."""
    post_semantics = post_semantics or {}
    kt3_harmfulness = kt3_harmfulness or {}

    posts = _semantic_posts(post_semantics)
    accounts = _as_list(_get(kt3_harmfulness, "user_level", "accounts"))
    communities = _as_list(_get(kt3_harmfulness, "community_level", "communities"))

    review_items = _build_review_items(posts, accounts, communities, max_items=max_items)
    retrieval_tasks = _build_retrieval_tasks(posts, kt3_harmfulness, max_items=max_items)
    agent_tasks = _build_agent_tasks(review_items, retrieval_tasks, kt3_harmfulness)
    counter_inputs = _build_counter_narrative_inputs(kt3_harmfulness, max_items=5)

    priority_counts = Counter(item["priority"] for item in review_items)
    item_type_counts = Counter(item["type"] for item in review_items)

    return {
        "capability_boundary": {
            "status": "implemented_review_queue_scaffold",
            "live_llm_or_rag": False,
            "description": (
                "This queue prepares reviewer, retrieval, and counter-narrative "
                "tasks from KT3 evidence. It does not execute external retrieval "
                "or multi-agent LLM review yet."
            ),
        },
        "summary": {
            "review_items": len(review_items),
            "high_priority": priority_counts.get("high", 0) + priority_counts.get("critical", 0),
            "retrieval_tasks": len(retrieval_tasks),
            "agent_tasks": len(agent_tasks),
            "counter_narrative_tasks": len(counter_inputs),
            "item_types": dict(item_type_counts),
            "recommended_next_action": _recommended_next_action(review_items, retrieval_tasks, counter_inputs),
        },
        "review_items": review_items,
        "retrieval_tasks": retrieval_tasks,
        "agent_tasks": agent_tasks,
        "counter_narrative_inputs": counter_inputs,
    }


def _build_review_items(
    posts: list[dict[str, Any]],
    accounts: list[dict[str, Any]],
    communities: list[dict[str, Any]],
    *,
    max_items: int,
) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []

    for post in sorted(posts, key=_post_review_sort_key, reverse=True):
        reasons = _post_review_reasons(post)
        if not reasons:
            continue
        _append_limited(
            items,
            {
                "id": f"post:{_text(post.get('post_id')) or len(items)}",
                "type": "post_semantic_review",
                "priority": _post_priority(post, reasons),
                "execution_status": "planned_only",
                "requires_external_execution": True,
                "reason": "; ".join(reasons),
                "agent_role": "HarmReviewer",
                "evidence": _post_evidence(post),
            },
            max_items=max_items,
        )

    for account in sorted(accounts, key=_account_review_sort_key, reverse=True):
        reasons = _account_review_reasons(account)
        if not reasons:
            continue
        _append_limited(
            items,
            {
                "id": f"account:{_text(account.get('account_id')) or len(items)}",
                "type": "account_harm_review",
                "priority": _account_priority(account, reasons),
                "execution_status": "planned_only",
                "requires_external_execution": True,
                "reason": "; ".join(reasons),
                "agent_role": "AccountBehaviorReviewer",
                "evidence": {
                    "account_id": account.get("account_id"),
                    "author_name": account.get("author_name"),
                    "community_id": account.get("community_id"),
                    "risk_summary": account.get("risk_summary") or {},
                    "risk_profile_flags": account.get("risk_profile_flags") or {},
                    "representative_posts": _as_list(account.get("representative_posts"))[:3],
                },
            },
            max_items=max_items,
        )

    for community in sorted(communities, key=_community_review_sort_key, reverse=True):
        reasons = _community_review_reasons(community)
        if not reasons:
            continue
        _append_limited(
            items,
            {
                "id": f"community:{_text(community.get('community_id')) or len(items)}",
                "type": "community_harm_review",
                "priority": _community_priority(community, reasons),
                "execution_status": "planned_only",
                "requires_external_execution": True,
                "reason": "; ".join(reasons),
                "agent_role": "CommunityJudge",
                "evidence": {
                    "community_id": community.get("community_id"),
                    "member_count": community.get("member_count"),
                    "coord_edge_count": community.get("coord_edge_count"),
                    "risk_summary": community.get("risk_summary") or {},
                    "risk_flags": community.get("risk_flags") or {},
                    "claims_coverage": _as_list(community.get("claims_coverage"))[:5],
                    "key_accounts": _as_list(community.get("key_accounts"))[:5],
                },
            },
            max_items=max_items,
        )

    return sorted(items, key=_item_priority_sort_key, reverse=True)[:max_items]


def _build_retrieval_tasks(
    posts: list[dict[str, Any]],
    kt3_harmfulness: dict[str, Any],
    *,
    max_items: int,
) -> list[dict[str, Any]]:
    tasks: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()

    for post in sorted(posts, key=_post_review_sort_key, reverse=True):
        harm = post.get("harmfulness") or {}
        stance = post.get("stance") or {}
        claim = post.get("primary_claim") or {}
        harm_label = _text(harm.get("label"))
        stance_label = _text(stance.get("label"))
        claim_id = _text(claim.get("claim_id"))

        if not claim_id and harm_label in {"harmful", "uncertain"}:
            query = _task_query(
                post.get("excerpt"),
                _get(post, "evidence", "text"),
                _get(post, "evidence", "ocr_text"),
                _get(post, "evidence", "asr_text"),
            )
            _append_retrieval_task(
                tasks,
                seen,
                {
                    "id": f"retrieve:post:{_text(post.get('post_id')) or len(tasks)}",
                    "source_type": "post",
                    "source_id": post.get("post_id"),
                    "priority": "high" if harm_label == "harmful" else "medium",
                    "execution_status": "planned_only",
                    "requires_external_execution": True,
                    "purpose": "claim_linking_and_context",
                    "query": query,
                    "expected_evidence": ["canonical claim", "source context", "hard negatives"],
                },
                max_items=max_items,
            )

        if claim_id and (harm_label == "harmful" or stance_label in {"uncertain", "query"}):
            query = _task_query(claim.get("claim_text"), post.get("excerpt"))
            _append_retrieval_task(
                tasks,
                seen,
                {
                    "id": f"retrieve:claim:{claim_id}",
                    "source_type": "claim",
                    "source_id": claim_id,
                    "priority": "high" if harm_label == "harmful" else "medium",
                    "execution_status": "planned_only",
                    "requires_external_execution": True,
                    "purpose": "external_verification_or_context",
                    "query": query,
                    "expected_evidence": ["supporting sources", "refuting sources", "context timeline"],
                },
                max_items=max_items,
            )

    for claim in _as_list(_get(kt3_harmfulness, "global_summary", "claim_rank")):
        if len(tasks) >= max_items:
            break
        claim_id = _text(claim.get("claim_id"))
        harmful_posts = _safe_int(claim.get("harmful_posts"))
        if not claim_id or harmful_posts <= 0:
            continue
        _append_retrieval_task(
            tasks,
            seen,
            {
                "id": f"retrieve:top_claim:{claim_id}",
                "source_type": "claim",
                "source_id": claim_id,
                "priority": "high",
                "execution_status": "planned_only",
                "requires_external_execution": True,
                "purpose": "campaign_claim_verification",
                "query": _task_query(claim.get("claim_text"), claim_id),
                "expected_evidence": ["claim provenance", "verification evidence", "related narratives"],
            },
            max_items=max_items,
        )

    return tasks[:max_items]


def _build_agent_tasks(
    review_items: list[dict[str, Any]],
    retrieval_tasks: list[dict[str, Any]],
    kt3_harmfulness: dict[str, Any],
) -> list[dict[str, Any]]:
    tasks = []
    if any(item["type"] == "post_semantic_review" for item in review_items):
        tasks.append(
            {
                "agent": "HarmReviewer",
                "priority": _highest_priority(review_items, "post_semantic_review"),
                "execution_status": "planned_only",
                "requires_external_execution": True,
                "objective": "Review uncertain or high-risk post-level harmfulness and stance outputs.",
                "inputs": [item["id"] for item in review_items if item["type"] == "post_semantic_review"][:10],
                "output_contract": ["final_label", "harm_type", "stance", "rationale", "evidence_refs"],
            }
        )
    if retrieval_tasks:
        tasks.append(
            {
                "agent": "RAGEvidenceRetriever",
                "priority": _highest_priority(retrieval_tasks),
                "execution_status": "planned_only",
                "requires_external_execution": True,
                "objective": "Retrieve claim, context, and verification evidence for KT3 review items.",
                "inputs": [task["id"] for task in retrieval_tasks[:10]],
                "output_contract": ["retrieved_evidence", "source_quality", "claim_context", "hard_negatives"],
            }
        )
    if any(item["type"] == "account_harm_review" for item in review_items):
        tasks.append(
            {
                "agent": "AccountBehaviorReviewer",
                "priority": _highest_priority(review_items, "account_harm_review"),
                "execution_status": "planned_only",
                "requires_external_execution": True,
                "objective": "Check whether account-level harmfulness reflects persistent behavior rather than isolated posts.",
                "inputs": [item["id"] for item in review_items if item["type"] == "account_harm_review"][:10],
                "output_contract": ["persistence_judgement", "role_judgement", "trajectory_note", "evidence_refs"],
            }
        )
    if any(item["type"] == "community_harm_review" for item in review_items):
        tasks.append(
            {
                "agent": "CommunityJudge",
                "priority": _highest_priority(review_items, "community_harm_review"),
                "execution_status": "planned_only",
                "requires_external_execution": True,
                "objective": "Judge collective harm, coordinated amplification, and subgroup roles at community level.",
                "inputs": [item["id"] for item in review_items if item["type"] == "community_harm_review"][:10],
                "output_contract": ["collective_harm_label", "amplification_judgement", "subgroup_roles", "evidence_refs"],
            }
        )
    if _as_list(_get(kt3_harmfulness, "global_summary", "claim_rank")):
        tasks.append(
            {
                "agent": "CounterNarrativePlanner",
                "priority": "medium",
                "execution_status": "planned_only",
                "requires_external_execution": True,
                "objective": "Prepare counter-narrative planning inputs from harmful claims and audience/community context.",
                "inputs": ["counter_narrative_inputs"],
                "output_contract": ["target_claim", "harm_type", "audience", "counter_message_strategy"],
            }
        )
    return tasks


def _build_counter_narrative_inputs(
    kt3_harmfulness: dict[str, Any],
    *,
    max_items: int,
) -> list[dict[str, Any]]:
    harm_types = _get(kt3_harmfulness, "global_summary", "harm_types") or {}
    communities = _as_list(_get(kt3_harmfulness, "community_level", "communities"))
    top_claims = _as_list(_get(kt3_harmfulness, "global_summary", "claim_rank"))

    dominant_harm_types = [
        harm_type
        for harm_type, _count in sorted(harm_types.items(), key=lambda item: item[1], reverse=True)
    ][:3]
    if not dominant_harm_types:
        dominant_harm_types = ["unspecified_harm"]

    inputs = []
    for claim in top_claims[:max_items]:
        if _safe_int(claim.get("harmful_posts")) <= 0:
            continue
        community = _best_community_for_claim(communities, _text(claim.get("claim_id")))
        inputs.append(
            {
                "claim_id": claim.get("claim_id"),
                "claim_text": claim.get("claim_text"),
                "harm_types": dominant_harm_types,
                "priority": "high" if _safe_int(claim.get("harmful_posts")) >= 3 else "medium",
                "audience_context": {
                    "community_id": community.get("community_id") if community else None,
                    "key_accounts": _as_list((community or {}).get("key_accounts"))[:5],
                    "subgroup_roles": (community or {}).get("subgroup_roles") or {},
                },
                "generation_constraints": [
                    "avoid amplifying the harmful claim",
                    "cite verified evidence when available",
                    "separate factual correction from de-escalation framing",
                ],
            }
        )
    return inputs[:max_items]


def _semantic_posts(post_semantics: dict[str, Any]) -> list[dict[str, Any]]:
    posts = post_semantics.get("aggregation_posts")
    if isinstance(posts, list):
        return posts
    posts = post_semantics.get("posts")
    return posts if isinstance(posts, list) else []


def _post_review_reasons(post: dict[str, Any]) -> list[str]:
    harm = post.get("harmfulness") or {}
    stance = post.get("stance") or {}
    primary_claim = post.get("primary_claim")
    reasons = []
    if harm.get("abstain") or _text(harm.get("label")) == "uncertain":
        reasons.append("harmfulness is uncertain or abstained")
    if stance.get("abstain") or _text(stance.get("label")) == "uncertain":
        reasons.append("stance is uncertain or abstained")
    if not primary_claim:
        reasons.append("no linked claim")
    if _text(harm.get("label")) == "harmful" and not primary_claim:
        reasons.append("harmful content lacks claim grounding")
    if "misinformation" in _as_list(harm.get("types")) and _text(stance.get("label")) not in {"support", "deny", "query", "neutral"}:
        reasons.append("misinformation label needs claim-conditioned stance check")
    return _dedupe(reasons)


def _account_review_reasons(account: dict[str, Any]) -> list[str]:
    flags = account.get("risk_profile_flags") or {}
    summary = account.get("risk_summary") or {}
    reasons = []
    if flags.get("high_harmful"):
        reasons.append("account is flagged as high harmful")
    if flags.get("needs_review"):
        reasons.append("account contains abstained post-level judgements")
    if flags.get("coordinated") and _safe_float(summary.get("harmful_ratio")) > 0:
        reasons.append("coordinated account has harmful semantic evidence")
    if _safe_float(summary.get("persistence_score")) >= 0.55:
        reasons.append("persistent harmfulness requires behavior-level review")
    return _dedupe(reasons)


def _community_review_reasons(community: dict[str, Any]) -> list[str]:
    flags = community.get("risk_flags") or {}
    summary = community.get("risk_summary") or {}
    reasons = []
    if flags.get("high_collective_harm"):
        reasons.append("community is flagged as high collective harm")
    if flags.get("coordinated_harm_amplification"):
        reasons.append("coordinated amplification may be increasing harm")
    if flags.get("needs_review"):
        reasons.append("community aggregates uncertain lower-level judgements")
    if _safe_float(summary.get("amplification_score")) >= 0.45:
        reasons.append("amplification score requires community-level review")
    return _dedupe(reasons)


def _post_priority(post: dict[str, Any], reasons: list[str]) -> str:
    harm = post.get("harmfulness") or {}
    harm_label = _text(harm.get("label"))
    harm_score = _safe_float(harm.get("score"))
    if harm_label == "harmful" and ("no linked claim" in reasons or harm_score >= 0.65):
        return "high"
    if harm_label == "harmful":
        return "medium"
    if harm_label == "uncertain" or harm.get("abstain"):
        return "medium"
    return "low"


def _account_priority(account: dict[str, Any], reasons: list[str]) -> str:
    flags = account.get("risk_profile_flags") or {}
    summary = account.get("risk_summary") or {}
    if flags.get("high_harmful") and (flags.get("coordinated") or _safe_float(summary.get("persistence_score")) >= 0.55):
        return "high"
    if flags.get("high_harmful") or flags.get("needs_review"):
        return "medium"
    return "low"


def _community_priority(community: dict[str, Any], reasons: list[str]) -> str:
    flags = community.get("risk_flags") or {}
    summary = community.get("risk_summary") or {}
    if flags.get("high_collective_harm") and (
        flags.get("coordinated_harm_amplification") or _safe_float(summary.get("amplification_score")) >= 0.45
    ):
        return "high"
    if flags.get("high_collective_harm") or flags.get("needs_review"):
        return "medium"
    return "low"


def _post_evidence(post: dict[str, Any]) -> dict[str, Any]:
    harm = post.get("harmfulness") or {}
    stance = post.get("stance") or {}
    primary_claim = post.get("primary_claim") or {}
    return {
        "post_id": post.get("post_id"),
        "author_id": post.get("author_id"),
        "excerpt": post.get("excerpt"),
        "modalities": _as_list(post.get("modalities")),
        "primary_claim": primary_claim,
        "harm_label": harm.get("label"),
        "harm_score": _safe_float(harm.get("score")),
        "harm_types": _as_list(harm.get("types")),
        "stance_label": stance.get("label"),
        "stance_confidence": _safe_float(stance.get("confidence")),
        "semantic_evidence": post.get("evidence") or {},
    }


def _post_review_sort_key(post: dict[str, Any]) -> tuple[float, int, int]:
    harm = post.get("harmfulness") or {}
    stance = post.get("stance") or {}
    return (
        _safe_float(harm.get("score")),
        1 if _text(harm.get("label")) == "harmful" else 0,
        1 if stance.get("abstain") or not post.get("primary_claim") else 0,
    )


def _account_review_sort_key(account: dict[str, Any]) -> tuple[float, int, int]:
    summary = account.get("risk_summary") or {}
    flags = account.get("risk_profile_flags") or {}
    return (
        _safe_float(summary.get("persistence_score")),
        _safe_int(summary.get("harmful_posts")),
        1 if flags.get("coordinated") else 0,
    )


def _community_review_sort_key(community: dict[str, Any]) -> tuple[float, int, int]:
    summary = community.get("risk_summary") or {}
    flags = community.get("risk_flags") or {}
    return (
        _safe_float(summary.get("amplification_score")),
        _safe_int(summary.get("harmful_posts")),
        1 if flags.get("coordinated_harm_amplification") else 0,
    )


def _item_priority_sort_key(item: dict[str, Any]) -> tuple[int, str]:
    return (_priority_rank(item.get("priority")), _text(item.get("id")))


def _highest_priority(items: list[dict[str, Any]], item_type: str | None = None) -> str:
    candidates = [item for item in items if item_type is None or item.get("type") == item_type]
    if not candidates:
        return "low"
    return max((_text(item.get("priority")) for item in candidates), key=_priority_rank)


def _priority_rank(priority: Any) -> int:
    return {"critical": 4, "high": 3, "medium": 2, "low": 1}.get(_text(priority), 0)


def _append_limited(items: list[dict[str, Any]], item: dict[str, Any], *, max_items: int) -> None:
    if len(items) < max_items:
        items.append(item)


def _append_retrieval_task(
    tasks: list[dict[str, Any]],
    seen: set[tuple[str, str]],
    task: dict[str, Any],
    *,
    max_items: int,
) -> None:
    query = _text(task.get("query"))[:MAX_QUERY_CHARS]
    if not query or len(tasks) >= max_items:
        return
    key = (_text(task.get("purpose")), query.lower())
    if key in seen:
        return
    task["query"] = query
    seen.add(key)
    tasks.append(task)


def _task_query(*parts: Any) -> str:
    return " ".join(_text(part) for part in parts if _text(part))[:MAX_QUERY_CHARS]


def _recommended_next_action(
    review_items: list[dict[str, Any]],
    retrieval_tasks: list[dict[str, Any]],
    counter_inputs: list[dict[str, Any]],
) -> str:
    if any(item.get("priority") in {"critical", "high"} for item in review_items):
        return "run_high_priority_human_or_agent_review"
    if retrieval_tasks:
        return "run_rag_evidence_retrieval"
    if counter_inputs:
        return "prepare_counter_narrative_draft"
    return "no_review_required"


def _best_community_for_claim(communities: list[dict[str, Any]], claim_id: str) -> dict[str, Any] | None:
    if not claim_id:
        return communities[0] if communities else None
    for community in communities:
        for claim in _as_list(community.get("claims_coverage")):
            if _text(claim.get("claim_id")) == claim_id:
                return community
    return communities[0] if communities else None


def _get(value: dict[str, Any] | None, *path: str) -> Any:
    current: Any = value or {}
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


def _dedupe(values: list[str]) -> list[str]:
    seen = set()
    result = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result
