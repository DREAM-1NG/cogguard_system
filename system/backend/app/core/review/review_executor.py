"""Local Review execution scaffold.

This module moves Review one step beyond a planned queue: it executes a deterministic
local review over the evidence already present in the risk report. It deliberately
does not call external LLMs, search engines, or vector databases. The output is a
review result that can later be replaced or enriched by a true RAG / multi-agent
runtime without changing the report contract.
"""

from __future__ import annotations

from collections import Counter
from typing import Any, Protocol
import re


TOKEN_PATTERN = re.compile(r"[\u4e00-\u9fff]|[A-Za-z0-9_]+")
MAX_EVIDENCE_PER_TASK = 3


class ReviewEvidenceRetriever(Protocol):
    """Optional offline/test retriever hook for Review execution."""

    def __call__(
        self,
        *,
        task: dict[str, Any],
        corpus: list[dict[str, Any]],
        local_result: dict[str, Any],
        max_evidence: int,
    ) -> dict[str, Any] | None:
        ...


class ReviewProvider(Protocol):
    """Optional offline/test reviewer hook for Review execution."""

    def __call__(
        self,
        *,
        item: dict[str, Any],
        local_result: dict[str, Any],
        retrieval_evidence: list[dict[str, Any]],
    ) -> dict[str, Any] | None:
        ...


def execute_review_queue(
    *,
    post_semantics: dict[str, Any] | None,
    review_harmfulness: dict[str, Any] | None,
    review_queue: dict[str, Any] | None,
    max_evidence: int = MAX_EVIDENCE_PER_TASK,
    evidence_retriever: ReviewEvidenceRetriever | None = None,
    review_provider: ReviewProvider | None = None,
) -> dict[str, Any]:
    """Execute local deterministic Review tasks over in-report evidence."""
    post_semantics = post_semantics or {}
    review_harmfulness = review_harmfulness or {}
    review_queue = review_queue or {}

    corpus = _build_local_corpus(post_semantics, review_harmfulness)
    provider_state = _provider_state(evidence_retriever, review_provider)
    retrieval_results = [
        _execute_retrieval_task(
            task,
            corpus,
            max_evidence=max_evidence,
            evidence_retriever=evidence_retriever,
            provider_state=provider_state,
        )
        for task in _as_list(review_queue.get("retrieval_tasks"))
    ]
    retrieval_by_source = _index_retrieval_results(retrieval_results)

    review_results = [
        _execute_review_item(
            item,
            retrieval_by_source,
            review_provider=review_provider,
            provider_state=provider_state,
        )
        for item in _as_list(review_queue.get("review_items"))
    ]
    agent_results = _execute_agent_tasks(_as_list(review_queue.get("agent_tasks")), review_results, retrieval_results)
    counter_drafts = [
        _draft_counter_narrative(item)
        for item in _as_list(review_queue.get("counter_narrative_inputs"))
    ]

    escalation_count = sum(1 for result in review_results if result.get("external_review_required"))
    confidence_values = [
        float(result["local_confidence"])
        for result in review_results
        if isinstance(result.get("local_confidence"), (int, float))
    ]
    avg_confidence = sum(confidence_values) / len(confidence_values) if confidence_values else 0.0
    outcome_counts = Counter(result.get("local_outcome", "unknown") for result in review_results)

    return {
        "capability_boundary": {
            "status": _execution_status(provider_state),
            "local_rag": True,
            "pluggable_retriever": bool(provider_state["retriever_configured"]),
            "pluggable_review_provider": bool(provider_state["review_provider_configured"]),
            "live_llm_or_external_rag": bool(provider_state["live_external_call"]),
            "provider_failure_policy": "fallback_to_local_result",
            "description": (
                "Executes Review tasks with an in-report lexical evidence corpus by default. "
                "Optional retriever/reviewer hooks can be injected for offline mock or future "
                "provider execution; provider failures fall back to the deterministic local result."
            ),
        },
        "summary": {
            "corpus_documents": len(corpus),
            "retrieval_tasks_executed": len(retrieval_results),
            "review_items_executed": len(review_results),
            "agent_tasks_executed": len(agent_results),
            "counter_narrative_drafts": len(counter_drafts),
            "external_review_required": escalation_count,
            "avg_local_confidence": round(avg_confidence, 4),
            "outcomes": dict(outcome_counts),
            "provider_results_used": provider_state["results_used"],
            "provider_failures": len(provider_state["failures"]),
        },
        "retrieval_results": retrieval_results,
        "review_results": review_results,
        "agent_results": agent_results,
        "counter_narrative_drafts": counter_drafts,
        "provider_audit": {
            "retriever_configured": provider_state["retriever_configured"],
            "review_provider_configured": provider_state["review_provider_configured"],
            "results_used": provider_state["results_used"],
            "live_external_call": provider_state["live_external_call"],
            "failures": provider_state["failures"][:10],
        },
    }


def _provider_state(
    evidence_retriever: ReviewEvidenceRetriever | None,
    review_provider: ReviewProvider | None,
) -> dict[str, Any]:
    return {
        "retriever_configured": evidence_retriever is not None,
        "review_provider_configured": review_provider is not None,
        "live_external_call": False,
        "results_used": 0,
        "failures": [],
    }


def _execution_status(provider_state: dict[str, Any]) -> str:
    if provider_state["retriever_configured"] or provider_state["review_provider_configured"]:
        return "implemented_pluggable_local_review_executor"
    return "implemented_local_deterministic_review_executor"


def _normalize_retrieval_provider_result(
    provider_result: dict[str, Any] | None,
    local_result: dict[str, Any],
    provider_state: dict[str, Any],
) -> dict[str, Any] | None:
    if not isinstance(provider_result, dict):
        return None

    result = {**local_result, **provider_result}
    top_evidence = _as_list(result.get("top_evidence"))
    result["task_id"] = result.get("task_id") or local_result.get("task_id")
    result["source_type"] = result.get("source_type") or local_result.get("source_type")
    result["source_id"] = result.get("source_id") or local_result.get("source_id")
    result["purpose"] = result.get("purpose") or local_result.get("purpose")
    result["query"] = result.get("query") or local_result.get("query")
    result["execution_status"] = _text(result.get("execution_status")) or "executed_provider"
    result["execution_mode"] = _text(result.get("execution_mode")) or "pluggable_retrieval_provider"
    result["top_evidence"] = top_evidence
    result["evidence_found"] = _safe_int(result.get("evidence_found")) or len(top_evidence)
    result["external_retrieval_required"] = bool(result.get("external_retrieval_required", len(top_evidence) == 0))
    result["provider_status"] = "provider_result_used"

    provider_state["results_used"] += 1
    provider_state["live_external_call"] = provider_state["live_external_call"] or bool(
        result.get("live_external_call")
    )
    return result


def _apply_review_provider(
    item: dict[str, Any],
    local_result: dict[str, Any],
    retrieval_evidence: list[dict[str, Any]],
    review_provider: ReviewProvider | None,
    provider_state: dict[str, Any],
) -> dict[str, Any]:
    if review_provider is None:
        return local_result

    try:
        provider_result = review_provider(
            item=item,
            local_result=local_result,
            retrieval_evidence=retrieval_evidence,
        )
    except Exception as exc:  # pragma: no cover - exercised through tests
        _record_provider_failure(provider_state, "review_provider", item.get("id"), exc)
        return {**local_result, "provider_status": "fallback_after_provider_error"}

    normalized = _normalize_review_provider_result(provider_result, local_result, provider_state)
    if normalized is None:
        return {**local_result, "provider_status": "fallback_after_empty_provider_result"}
    return normalized


def _normalize_review_provider_result(
    provider_result: dict[str, Any] | None,
    local_result: dict[str, Any],
    provider_state: dict[str, Any],
) -> dict[str, Any] | None:
    if not isinstance(provider_result, dict):
        return None

    result = {**local_result, **provider_result}
    result["item_id"] = result.get("item_id") or local_result.get("item_id")
    result["item_type"] = result.get("item_type") or local_result.get("item_type")
    result["agent_role"] = result.get("agent_role") or local_result.get("agent_role")
    result["priority"] = result.get("priority") or local_result.get("priority")
    result["execution_status"] = _text(result.get("execution_status")) or "executed_provider"
    result["execution_mode"] = _text(result.get("execution_mode")) or "pluggable_review_provider"
    result["local_outcome"] = _text(result.get("local_outcome")) or _text(local_result.get("local_outcome"))
    result["local_confidence"] = round(
        max(0.0, min(1.0, _safe_float(result.get("local_confidence")))),
        4,
    )
    result["external_review_required"] = bool(
        result.get("external_review_required", result["local_outcome"].startswith("needs_"))
    )
    result["retrieval_refs"] = _as_list(result.get("retrieval_refs")) or _as_list(local_result.get("retrieval_refs"))
    result["provider_status"] = "provider_result_used"

    provider_state["results_used"] += 1
    provider_state["live_external_call"] = provider_state["live_external_call"] or bool(
        result.get("live_external_call")
    )
    return result


def _record_provider_failure(
    provider_state: dict[str, Any],
    provider_type: str,
    item_id: Any,
    exc: Exception,
) -> None:
    provider_state["failures"].append(
        {
            "provider_type": provider_type,
            "item_id": item_id,
            "error_type": type(exc).__name__,
            "message": _text(exc),
        }
    )


def _build_local_corpus(
    post_semantics: dict[str, Any],
    review_harmfulness: dict[str, Any],
) -> list[dict[str, Any]]:
    corpus: list[dict[str, Any]] = []

    for post in _semantic_posts(post_semantics):
        evidence = post.get("evidence") or {}
        claim = post.get("primary_claim") or {}
        text_parts = [
            post.get("excerpt"),
            evidence.get("text"),
            evidence.get("ocr_text"),
            evidence.get("asr_text"),
            evidence.get("media_text"),
            claim.get("claim_text"),
            " ".join(_as_list((post.get("harmfulness") or {}).get("types"))),
        ]
        corpus.append(
            _doc(
                doc_id=f"post:{_text(post.get('post_id'))}",
                doc_type="post",
                text=" ".join(_text(part) for part in text_parts if _text(part)),
                payload={
                    "post_id": post.get("post_id"),
                    "author_id": post.get("author_id"),
                    "primary_claim": claim,
                    "harmfulness": post.get("harmfulness") or {},
                    "stance": post.get("stance") or {},
                    "modalities": _as_list(post.get("modalities")),
                },
            )
        )

    for claim in _as_list(post_semantics.get("claim_candidates")):
        corpus.append(
            _doc(
                doc_id=f"claim:{_text(claim.get('claim_id'))}",
                doc_type="claim",
                text=f"{_text(claim.get('claim_id'))} {_text(claim.get('claim_text'))}",
                payload=claim,
            )
        )

    for claim in _as_list(_get(review_harmfulness, "global_summary", "claim_rank")):
        corpus.append(
            _doc(
                doc_id=f"global_claim:{_text(claim.get('claim_id'))}",
                doc_type="claim",
                text=f"{_text(claim.get('claim_id'))} {_text(claim.get('claim_text'))}",
                payload=claim,
            )
        )

    for account in _as_list(_get(review_harmfulness, "user_level", "accounts")):
        summary = account.get("risk_summary") or {}
        top_claims = " ".join(_text(claim.get("claim_text")) for claim in _as_list(account.get("top_claims")))
        corpus.append(
            _doc(
                doc_id=f"account:{_text(account.get('account_id'))}",
                doc_type="account",
                text=(
                    f"{_text(account.get('account_id'))} {_text(account.get('author_name'))} "
                    f"{top_claims} {_text(summary.get('trajectory'))} "
                    f"{' '.join((summary.get('harm_types') or {}).keys())}"
                ),
                payload=account,
            )
        )

    for community in _as_list(_get(review_harmfulness, "community_level", "communities")):
        summary = community.get("risk_summary") or {}
        claim_text = " ".join(_text(claim.get("claim_text")) for claim in _as_list(community.get("claims_coverage")))
        role_text = " ".join((community.get("subgroup_roles") or {}).keys())
        corpus.append(
            _doc(
                doc_id=f"community:{_text(community.get('community_id'))}",
                doc_type="community",
                text=f"{_text(community.get('community_id'))} {claim_text} {role_text} {' '.join((summary.get('dominant_harm_types') or {}).keys())}",
                payload=community,
            )
        )

    return [item for item in corpus if item["tokens"]]


def _execute_retrieval_task(
    task: dict[str, Any],
    corpus: list[dict[str, Any]],
    *,
    max_evidence: int,
    evidence_retriever: ReviewEvidenceRetriever | None,
    provider_state: dict[str, Any],
) -> dict[str, Any]:
    query = _text(task.get("query"))
    scored = [
        {
            "doc_id": doc["doc_id"],
            "doc_type": doc["doc_type"],
            "score": _lexical_score(query, doc["text"], doc["tokens"]),
            "excerpt": doc["text"][:240],
            "payload_ref": _payload_ref(doc),
        }
        for doc in corpus
    ]
    scored = [item for item in scored if item["score"] > 0]
    scored.sort(key=lambda item: item["score"], reverse=True)
    evidence = scored[:max_evidence]
    local_result = {
        "task_id": task.get("id"),
        "source_type": task.get("source_type"),
        "source_id": task.get("source_id"),
        "purpose": task.get("purpose"),
        "execution_status": "executed_local",
        "execution_mode": "local_lexical_retrieval",
        "query": query,
        "evidence_found": len(evidence),
        "top_evidence": evidence,
        "external_retrieval_required": len(evidence) == 0 or max((item["score"] for item in evidence), default=0.0) < 0.2,
    }
    if evidence_retriever is None:
        return local_result

    try:
        provider_result = evidence_retriever(
            task=task,
            corpus=corpus,
            local_result=local_result,
            max_evidence=max_evidence,
        )
    except Exception as exc:  # pragma: no cover - exercised through tests
        _record_provider_failure(provider_state, "retriever", task.get("id"), exc)
        local_result["provider_status"] = "fallback_after_provider_error"
        return local_result

    normalized = _normalize_retrieval_provider_result(provider_result, local_result, provider_state)
    if normalized is None:
        local_result["provider_status"] = "fallback_after_empty_provider_result"
        return local_result
    return normalized


def _execute_review_item(
    item: dict[str, Any],
    retrieval_by_source: dict[tuple[str, str], list[dict[str, Any]]],
    *,
    review_provider: ReviewProvider | None,
    provider_state: dict[str, Any],
) -> dict[str, Any]:
    item_type = _text(item.get("type"))
    evidence = item.get("evidence") or {}
    retrieval_evidence = retrieval_by_source.get((_source_type_for_item(item_type), _source_id_for_item(item)), [])

    if item_type == "post_semantic_review":
        local_result = _review_post_item(item, evidence, retrieval_evidence)
    elif item_type == "account_harm_review":
        local_result = _review_account_item(item, evidence, retrieval_evidence)
    elif item_type == "community_harm_review":
        local_result = _review_community_item(item, evidence, retrieval_evidence)
    else:
        local_result = _base_review_result(item, "needs_external_review", 0.2, retrieval_evidence)
    return _apply_review_provider(item, local_result, retrieval_evidence, review_provider, provider_state)


def _review_post_item(
    item: dict[str, Any],
    evidence: dict[str, Any],
    retrieval_evidence: list[dict[str, Any]],
) -> dict[str, Any]:
    harm_label = _text(evidence.get("harm_label"))
    harm_score = _safe_float(evidence.get("harm_score"))
    stance_label = _text(evidence.get("stance_label"))
    has_claim = bool(evidence.get("primary_claim"))
    retrieval_support = max((row.get("score", 0.0) for result in retrieval_evidence for row in _as_list(result.get("top_evidence"))), default=0.0)

    if harm_label == "harmful" and has_claim and retrieval_support >= 0.2:
        outcome = "locally_supported_high_risk"
        confidence = min(0.95, 0.55 + 0.25 * harm_score + 0.20 * retrieval_support)
    elif harm_label == "harmful" and not has_claim:
        outcome = "needs_claim_grounding"
        confidence = min(0.75, 0.35 + 0.35 * harm_score)
    elif harm_label == "uncertain" or stance_label in {"uncertain", "unlinked"}:
        outcome = "needs_external_review"
        confidence = max(0.2, min(0.6, harm_score))
    else:
        outcome = "locally_low_risk_or_monitor"
        confidence = max(0.3, min(0.8, 1.0 - harm_score))

    result = _base_review_result(item, outcome, confidence, retrieval_evidence)
    result["review_notes"] = [
        f"post harm label={harm_label or 'unknown'} score={harm_score:.2f}",
        f"stance={stance_label or 'unknown'} claim_grounded={has_claim}",
        f"local retrieval support={retrieval_support:.2f}",
    ]
    result["external_review_required"] = outcome in {"needs_claim_grounding", "needs_external_review"}
    return result


def _review_account_item(
    item: dict[str, Any],
    evidence: dict[str, Any],
    retrieval_evidence: list[dict[str, Any]],
) -> dict[str, Any]:
    summary = evidence.get("risk_summary") or {}
    flags = evidence.get("risk_profile_flags") or {}
    harmful_posts = _safe_int(summary.get("harmful_posts"))
    persistence = _safe_float(summary.get("persistence_score"))
    coordinated = bool(flags.get("coordinated"))

    if flags.get("high_harmful") and (persistence >= 0.55 or coordinated):
        outcome = "locally_supported_persistent_account_harm"
        confidence = min(0.92, 0.45 + 0.35 * persistence + 0.05 * harmful_posts + (0.08 if coordinated else 0))
    elif flags.get("needs_review"):
        outcome = "needs_post_level_resolution"
        confidence = min(0.65, 0.35 + 0.25 * persistence)
    else:
        outcome = "locally_monitor_account"
        confidence = 0.5

    result = _base_review_result(item, outcome, confidence, retrieval_evidence)
    result["review_notes"] = [
        f"harmful_posts={harmful_posts}",
        f"persistence_score={persistence:.2f}",
        f"coordinated={coordinated}",
    ]
    result["external_review_required"] = outcome == "needs_post_level_resolution"
    return result


def _review_community_item(
    item: dict[str, Any],
    evidence: dict[str, Any],
    retrieval_evidence: list[dict[str, Any]],
) -> dict[str, Any]:
    summary = evidence.get("risk_summary") or {}
    flags = evidence.get("risk_flags") or {}
    harmful_posts = _safe_int(summary.get("harmful_posts"))
    amplification = _safe_float(summary.get("amplification_score"))

    if flags.get("high_collective_harm") and (flags.get("coordinated_harm_amplification") or amplification >= 0.45):
        outcome = "locally_supported_collective_harm"
        confidence = min(0.93, 0.45 + 0.35 * amplification + 0.03 * harmful_posts)
    elif flags.get("needs_review"):
        outcome = "needs_lower_level_resolution"
        confidence = min(0.65, 0.35 + 0.25 * amplification)
    else:
        outcome = "locally_monitor_community"
        confidence = 0.5

    result = _base_review_result(item, outcome, confidence, retrieval_evidence)
    result["review_notes"] = [
        f"harmful_posts={harmful_posts}",
        f"amplification_score={amplification:.2f}",
        f"coordinated_amplification={bool(flags.get('coordinated_harm_amplification'))}",
    ]
    result["external_review_required"] = outcome == "needs_lower_level_resolution"
    return result


def _base_review_result(
    item: dict[str, Any],
    outcome: str,
    confidence: float,
    retrieval_evidence: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "item_id": item.get("id"),
        "item_type": item.get("type"),
        "agent_role": item.get("agent_role"),
        "priority": item.get("priority"),
        "execution_status": "executed_local",
        "execution_mode": "deterministic_local_reviewer",
        "local_outcome": outcome,
        "local_confidence": round(max(0.0, min(1.0, confidence)), 4),
        "external_review_required": outcome.startswith("needs_"),
        "retrieval_refs": [result.get("task_id") for result in retrieval_evidence],
    }


def _execute_agent_tasks(
    agent_tasks: list[dict[str, Any]],
    review_results: list[dict[str, Any]],
    retrieval_results: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    review_by_id = {result.get("item_id"): result for result in review_results}
    retrieval_by_id = {result.get("task_id"): result for result in retrieval_results}
    results = []
    for task in agent_tasks:
        input_ids = _as_list(task.get("inputs"))
        linked_reviews = [review_by_id[item_id] for item_id in input_ids if item_id in review_by_id]
        linked_retrieval = [retrieval_by_id[item_id] for item_id in input_ids if item_id in retrieval_by_id]
        unresolved = sum(1 for result in linked_reviews if result.get("external_review_required"))
        results.append(
            {
                "agent": task.get("agent"),
                "priority": task.get("priority"),
                "execution_status": "executed_local",
                "execution_mode": "deterministic_agent_summary",
                "planned_task_status": task.get("execution_status"),
                "inputs_seen": len(input_ids),
                "linked_review_results": len(linked_reviews),
                "linked_retrieval_results": len(linked_retrieval),
                "external_followup_required": unresolved > 0,
                "summary": _agent_summary(task.get("agent"), linked_reviews, linked_retrieval, unresolved),
            }
        )
    return results


def _draft_counter_narrative(item: dict[str, Any]) -> dict[str, Any]:
    harm_types = _as_list(item.get("harm_types")) or ["unspecified_harm"]
    priority = _text(item.get("priority")) or "medium"
    claim_text = _text(item.get("claim_text")) or _text(item.get("claim_id"))
    return {
        "claim_id": item.get("claim_id"),
        "priority": priority,
        "execution_status": "drafted_local",
        "execution_mode": "deterministic_counter_narrative_planner",
        "target_harm_types": harm_types,
        "strategy": [
            "start from verified context rather than repeating the harmful framing",
            "separate factual correction from de-escalation and safety guidance",
            "adapt wording to the most affected community before publication",
        ],
        "draft_brief": (
            f"Prepare a {priority}-priority counter-narrative for claim '{claim_text[:120]}' "
            f"with focus on {', '.join(harm_types[:3])}."
        ),
        "requires_human_approval": True,
    }


def _agent_summary(
    agent: Any,
    reviews: list[dict[str, Any]],
    retrieval: list[dict[str, Any]],
    unresolved: int,
) -> str:
    agent_name = _text(agent) or "Agent"
    if retrieval and not reviews:
        found = sum(result.get("evidence_found", 0) for result in retrieval)
        return f"{agent_name} executed local retrieval over {len(retrieval)} tasks and found {found} evidence snippets."
    if not reviews:
        return f"{agent_name} has no concrete local review inputs yet."
    outcomes = Counter(result.get("local_outcome", "unknown") for result in reviews)
    return f"{agent_name} summarized {len(reviews)} local review results; unresolved external follow-up={unresolved}; outcomes={dict(outcomes)}."


def _index_retrieval_results(results: list[dict[str, Any]]) -> dict[tuple[str, str], list[dict[str, Any]]]:
    index: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for result in results:
        source_type = _text(result.get("source_type"))
        source_id = _text(result.get("source_id"))
        if source_type and source_id:
            index.setdefault((source_type, source_id), []).append(result)
    return index


def _source_type_for_item(item_type: str) -> str:
    if item_type == "post_semantic_review":
        return "post"
    if item_type == "account_harm_review":
        return "account"
    if item_type == "community_harm_review":
        return "community"
    return ""


def _source_id_for_item(item: dict[str, Any]) -> str:
    item_id = _text(item.get("id"))
    return item_id.split(":", 1)[1] if ":" in item_id else item_id


def _semantic_posts(post_semantics: dict[str, Any]) -> list[dict[str, Any]]:
    posts = post_semantics.get("aggregation_posts")
    if isinstance(posts, list):
        return posts
    posts = post_semantics.get("posts")
    return posts if isinstance(posts, list) else []


def _doc(doc_id: str, doc_type: str, text: str, payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "doc_id": doc_id,
        "doc_type": doc_type,
        "text": _text(text),
        "tokens": _tokenize(text),
        "payload": payload,
    }


def _payload_ref(doc: dict[str, Any]) -> dict[str, Any]:
    payload = doc.get("payload") or {}
    ref = {"doc_id": doc.get("doc_id"), "doc_type": doc.get("doc_type")}
    for key in ("post_id", "claim_id", "account_id", "community_id", "author_id"):
        if payload.get(key):
            ref[key] = payload.get(key)
    return ref


def _lexical_score(query: str, text: str, text_tokens: set[str] | None = None) -> float:
    query_tokens = _tokenize(query)
    doc_tokens = text_tokens or _tokenize(text)
    if not query_tokens or not doc_tokens:
        return 0.0
    overlap = query_tokens & doc_tokens
    if not overlap:
        return 0.0
    containment = len(overlap) / min(len(query_tokens), len(doc_tokens))
    jaccard = len(overlap) / len(query_tokens | doc_tokens)
    return round(min(1.0, 0.65 * containment + 0.35 * jaccard), 4)


def _tokenize(text: Any) -> set[str]:
    return {token.lower() for token in TOKEN_PATTERN.findall(_text(text))}


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
