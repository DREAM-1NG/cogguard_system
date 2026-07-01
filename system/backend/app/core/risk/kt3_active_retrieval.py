"""Active evidence retrieval for analyst-triggered KT3 agent reviews.

The default path is intentionally local and reproducible. Optional external
providers are injected explicitly and audited; they are never called from
``/risk/assess``.
"""

from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from typing import Any, Protocol
import re


TOKEN_PATTERN = re.compile(r"[\u4e00-\u9fff]|[A-Za-z0-9_]+")
DEFAULT_TOP_K = 3


class ActiveEvidenceProvider(Protocol):
    """Optional external retrieval provider used only by manual review."""

    async def __call__(
        self,
        *,
        query: str,
        context: dict[str, Any],
        top_k: int,
    ) -> list[dict[str, Any]]:
        ...


async def retrieve_active_evidence(
    *,
    context: dict[str, Any],
    top_k: int = DEFAULT_TOP_K,
    external_provider: ActiveEvidenceProvider | None = None,
    external_enabled: bool = False,
) -> dict[str, Any]:
    """Retrieve local evidence and optionally enrich it with external sources."""
    top_k = max(1, min(int(top_k or DEFAULT_TOP_K), 10))
    base_queries = _build_queries(context)
    query_plan = _refine_queries(base_queries, context)
    queries = query_plan["queries"]
    local_corpus = _build_local_corpus(context)
    local_results = [
        _retrieve_local(query=query, corpus=local_corpus, top_k=top_k)
        for query in queries
    ]
    external_results = []
    failures = []

    if external_enabled and external_provider is not None:
        for query in queries:
            try:
                rows = await external_provider(query=query, context=context, top_k=top_k)
                external_results.append(_normalize_external_result(query, rows))
            except Exception as exc:  # pragma: no cover - exercised through tests
                failures.append(
                    {
                        "query": query,
                        "error_type": type(exc).__name__,
                        "message": str(exc),
                    }
                )

    conflict_queries = _build_conflict_requeries(context, local_results, external_results)
    conflict_requery_results = [
        _retrieve_local(query=query, corpus=local_corpus, top_k=top_k)
        for query in conflict_queries
    ]
    source_quality = _aggregate_source_quality(local_results, external_results, conflict_requery_results)
    return {
        "schema_version": "kt3-active-evidence-v1",
        "created_at": _utc_now(),
        "queries": queries,
        "base_queries": base_queries,
        "query_refinement_trace": query_plan["trace"],
        "local_corpus_size": len(local_corpus),
        "local_results": local_results,
        "external_results": external_results,
        "source_quality": source_quality,
        "conflict_requery_results": conflict_requery_results,
        "audit": {
            "external_enabled": bool(external_enabled),
            "external_provider_configured": external_provider is not None,
            "external_calls": len(external_results) + len(failures),
            "failures": failures,
            "default_local_first": True,
            "query_refinement_enabled": True,
            "conflict_requery_enabled": True,
        },
        "capability_boundary": {
            "runs_only_in_manual_agent_review": True,
            "does_not_fit_dataset_labels": True,
            "external_retrieval_default_enabled": False,
            "claim_to_query": True,
            "source_quality_scoring": True,
            "conflict_requery": True,
        },
    }


def build_sidecar_for_agent(
    *,
    agent_name: str,
    context: dict[str, Any],
    retrieval_bundle: dict[str, Any] | None,
    debate_bundle: dict[str, Any] | None,
) -> dict[str, Any]:
    """Build a machine-readable sidecar while keeping report_text natural."""
    retrieval_bundle = retrieval_bundle or {}
    debate_bundle = debate_bundle or {}
    local_refs = [
        evidence
        for result in retrieval_bundle.get("local_results") or []
        for evidence in result.get("top_evidence") or []
    ]
    external_refs = [
        evidence
        for result in retrieval_bundle.get("external_results") or []
        for evidence in result.get("top_evidence") or []
    ]
    uncertainties = _uncertainties_for_agent(agent_name, context, retrieval_bundle, debate_bundle)
    policy = context.get("active_policy") or context.get("policy") or {}
    active_policy = policy.get("policy") if isinstance(policy, dict) and "policy" in policy else policy
    return {
        "schema_version": "kt3-agent-sidecar-v1",
        "sidecar_role": "system_audit_not_agent_primary_output",
        "not_agent_primary_output": True,
        "primary_agent_output_ref": "analysis_report.text",
        "agent_name": agent_name,
        "evidence_refs": (local_refs + external_refs)[:8],
        "retrieval_queries": retrieval_bundle.get("queries") or [],
        "retrieval_refinement_trace": retrieval_bundle.get("query_refinement_trace") or [],
        "source_quality": retrieval_bundle.get("source_quality") or _source_quality(local_refs, external_refs),
        "uncertainties": uncertainties,
        "debate_trace_refs": debate_bundle.get("trace_refs") or [],
        "debate_mode": debate_bundle.get("debate_mode") or (
            "full_debate" if debate_bundle.get("schema_version") == "kt3-full-debate-v1" else "light_debate"
        ),
        "full_debate_trace_refs": debate_bundle.get("full_debate_trace_refs") or [],
        "suggested_actions": _suggested_actions(agent_name, uncertainties, retrieval_bundle),
        "confidence": _sidecar_confidence(local_refs, external_refs, uncertainties),
        "review_required": bool(uncertainties or debate_bundle.get("triggered")),
        "active_retrieval_used": bool(retrieval_bundle),
        "light_debate_used": bool(debate_bundle.get("triggered")),
        "active_policy_id": policy.get("policy_id") if isinstance(policy, dict) else None,
        "policy_rule_refs": _policy_rule_refs(policy),
        "policy_thresholds": {
            "review_threshold": active_policy.get("review_threshold") if isinstance(active_policy, dict) else None,
            "abstain_threshold": active_policy.get("abstain_threshold") if isinstance(active_policy, dict) else None,
            "retrieval_threshold": active_policy.get("retrieval_threshold") if isinstance(active_policy, dict) else None,
            "countermeasure_threshold": active_policy.get("countermeasure_threshold") if isinstance(active_policy, dict) else None,
        },
    }


def should_trigger_light_debate(
    *,
    context: dict[str, Any],
    retrieval_bundle: dict[str, Any] | None,
) -> tuple[bool, list[str]]:
    reasons = []
    for post in context.get("selected_posts") or []:
        view = post.get("post_view_detection") or {}
        stance = post.get("stance") or {}
        if view.get("conflict"):
            reasons.append(f"post:{post.get('post_id')}:cross_view_conflict")
        if stance.get("abstain") or stance.get("label") in {"uncertain", "query"}:
            reasons.append(f"post:{post.get('post_id')}:claim_stance_uncertain")
        if _as_float(view.get("conflict", {}).get("score")) >= 0.35:
            reasons.append(f"post:{post.get('post_id')}:high_conflict_score")

    retrieval_bundle = retrieval_bundle or {}
    for result in retrieval_bundle.get("local_results") or []:
        if not result.get("top_evidence"):
            reasons.append(f"query:{_hash_text(result.get('query'))}:no_local_evidence")
    for failure in (retrieval_bundle.get("audit") or {}).get("failures") or []:
        reasons.append(f"external_retrieval_failure:{failure.get('error_type')}")
    return bool(reasons), reasons[:8]


def build_light_debate_trace(
    *,
    context: dict[str, Any],
    retrieval_bundle: dict[str, Any] | None,
    reasons: list[str],
) -> dict[str, Any]:
    """Create a lightweight D2D/MAD-Sherlock inspired debate scaffold."""
    retrieval_bundle = retrieval_bundle or {}
    trace_id = f"debate:{_hash_text({'refs': context.get('input_refs'), 'reasons': reasons})[:12]}"
    top_queries = retrieval_bundle.get("queries") or []
    return {
        "schema_version": "kt3-light-debate-v1",
        "triggered": bool(reasons),
        "trace_id": trace_id,
        "trace_refs": [trace_id] if reasons else [],
        "reasons": reasons,
        "turns": [
            {
                "stage": "opening",
                "role": "evidence_affirming_agent",
                "content": (
                    "Existing detector and retrieval evidence may support a harmfulness review; "
                    f"key queries: {top_queries[:3]}."
                ),
            },
            {
                "stage": "rebuttal",
                "role": "evidence_skeptic_agent",
                "content": (
                    "The case contains uncertainty or missing evidence; do not treat this as an "
                    "automatic final harmfulness label."
                ),
            },
            {
                "stage": "judge_synthesis",
                "role": "light_debate_judge",
                "content": (
                    "Use the debate as uncertainty context for QuestionReflection and "
                    "HarmfulnessJudge; require human confirmation before countermeasures."
                ),
            },
        ],
        "capability_boundary": {
            "not_full_d2d_protocol": True,
            "high_conflict_only": True,
            "natural_language_trace_for_judge": True,
        },
    }


async def build_full_debate_trace(
    *,
    context: dict[str, Any],
    retrieval_bundle: dict[str, Any] | None,
    reasons: list[str],
    provider: Any | None = None,
    model: str = "",
    max_rounds: int = 3,
) -> dict[str, Any]:
    """Run an optional multi-stage D2D/MAD-Sherlock style debate trace.

    The provider is the same OpenAI-compatible callable used by the manual
    agents. If it is unavailable or fails, the debate is recorded as failed
    instead of generating a synthetic final judgement.
    """
    max_rounds = max(1, min(int(max_rounds or 1), 5))
    trace_id = f"full-debate:{_hash_text({'refs': context.get('input_refs'), 'reasons': reasons})[:12]}"
    if not reasons:
        return {
            "schema_version": "kt3-full-debate-v1",
            "debate_mode": "full_debate",
            "triggered": False,
            "trace_id": trace_id,
            "trace_refs": [],
            "full_debate_trace_refs": [],
            "reasons": [],
            "turns": [],
            "capability_boundary": {"high_conflict_only": True},
        }
    if provider is None:
        return {
            "schema_version": "kt3-full-debate-v1",
            "debate_mode": "full_debate",
            "triggered": True,
            "status": "failed",
            "trace_id": trace_id,
            "trace_refs": [trace_id],
            "full_debate_trace_refs": [trace_id],
            "reasons": reasons,
            "turns": [],
            "error": "LLM provider is not configured; full debate was not synthesized.",
            "safety_flags": ["no_synthetic_fallback"],
            "capability_boundary": {"real_multi_round_llm_required": True, "high_conflict_only": True},
        }

    turns: list[dict[str, Any]] = []
    stages = ["opening", "rebuttal", *[f"free_debate_round_{idx}" for idx in range(1, max_rounds + 1)], "closing", "judge_synthesis"]
    prior_text = ""
    for stage in stages:
        role = _debate_role_for_stage(stage)
        system_prompt = (
            "You are a KT3 debate participant for analyst-triggered harmfulness review. "
            "Write concise Chinese natural-language debate notes. Do not output a final "
            "automatic classifier label; keep uncertainty and evidence requests explicit."
        )
        user_prompt = _full_debate_prompt(
            stage=stage,
            role=role,
            context=context,
            retrieval_bundle=retrieval_bundle or {},
            reasons=reasons,
            prior_text=prior_text,
        )
        try:
            content = await provider(
                agent_name=f"FullDebate:{stage}",
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                input_bundle=context,
                model=model,
            )
            status = "completed"
        except Exception as exc:  # pragma: no cover - covered by provider failure tests
            content = f"Provider failure during {stage}: {type(exc).__name__}: {exc}"
            status = "failed"
        turn = {
            "turn_id": f"{trace_id}:{stage}",
            "stage": stage,
            "role": role,
            "status": status,
            "content": str(content).strip(),
        }
        turns.append(turn)
        prior_text = "\n".join(item["content"] for item in turns[-4:])
        if status == "failed":
            break

    return {
        "schema_version": "kt3-full-debate-v1",
        "debate_mode": "full_debate",
        "triggered": True,
        "status": "completed" if all(turn["status"] == "completed" for turn in turns) else "failed",
        "trace_id": trace_id,
        "trace_refs": [trace_id],
        "full_debate_trace_refs": [turn["turn_id"] for turn in turns],
        "reasons": reasons,
        "turns": turns,
        "evidence_requests": _debate_evidence_requests(reasons, retrieval_bundle or {}),
        "capability_boundary": {
            "real_multi_round_llm_calls": True,
            "high_conflict_only": True,
            "natural_language_transcript_for_judge": True,
            "does_not_override_detector_outputs": True,
        },
    }


def _build_queries(context: dict[str, Any]) -> list[str]:
    queries = []
    for task in (context.get("review_queue") or {}).get("retrieval_tasks") or []:
        query = _text(task.get("query"))
        if query:
            queries.append(query)
    for post in context.get("selected_posts") or []:
        parts = [
            post.get("excerpt"),
            _get(post, "primary_claim", "claim_text"),
            _get(post, "evidence", "text"),
            _get(post, "evidence", "ocr_text"),
            _get(post, "evidence", "asr_text"),
        ]
        query = " ".join(_text(part) for part in parts if _text(part))[:220]
        if query:
            queries.append(query)
    if not queries:
        refs = context.get("input_refs") or {}
        queries.append(" ".join(_text(value) for value in refs.values() if _text(value)) or "kt3 harmfulness review")
    return _dedupe(queries)[:8]


def _refine_queries(base_queries: list[str], context: dict[str, Any]) -> dict[str, Any]:
    """Build RAMA-style claim-to-query refinements from local context."""
    refined = list(base_queries)
    trace = []
    for post in context.get("selected_posts") or []:
        claim_text = _text(_get(post, "primary_claim", "claim_text"))
        stance_label = _text(_get(post, "stance", "label"))
        if claim_text:
            query = " ".join(part for part in [claim_text, stance_label, "evidence verification"] if part)[:240]
            refined.append(query)
            trace.append(
                {
                    "source": "claim_to_query",
                    "post_id": _text(post.get("post_id")),
                    "base_claim": claim_text[:160],
                    "query": query,
                }
            )
        media_text = " ".join(
            _text(value)
            for value in [
                _get(post, "evidence", "ocr_text"),
                _get(post, "evidence", "asr_text"),
                _get(post, "evidence", "caption"),
            ]
            if _text(value)
        )
        if media_text:
            query = f"{media_text[:180]} multimodal context consistency"
            refined.append(query)
            trace.append(
                {
                    "source": "multimodal_to_query",
                    "post_id": _text(post.get("post_id")),
                    "query": query,
                }
            )
    for claim in _get(context, "propagation_context", "claim_rank") or []:
        claim_text = _text(claim.get("claim_text"))
        if claim_text:
            query = f"{claim_text[:200]} propagation stance evidence"
            refined.append(query)
            trace.append(
                {
                    "source": "propagation_claim_to_query",
                    "claim_id": _text(claim.get("claim_id")),
                    "query": query,
                }
            )
    queries = _dedupe(refined)[:10]
    return {
        "queries": queries,
        "trace": trace,
        "capability_boundary": {
            "claim_to_query": True,
            "multimodal_context_to_query": True,
            "local_first": True,
        },
    }


def _build_conflict_requeries(
    context: dict[str, Any],
    local_results: list[dict[str, Any]],
    external_results: list[dict[str, Any]],
) -> list[str]:
    queries = []
    missing_queries = [result.get("query") for result in local_results if not result.get("top_evidence")]
    if missing_queries:
        queries.extend(f"{_text(query)} corroborating source" for query in missing_queries[:3] if _text(query))
    for post in context.get("selected_posts") or []:
        view = post.get("post_view_detection") or {}
        if view.get("conflict") or _as_float(_get(view, "conflict", "score")) >= 0.35:
            query = " ".join(
                _text(value)
                for value in [
                    post.get("excerpt"),
                    _get(post, "primary_claim", "claim_text"),
                    "cross modal conflict evidence",
                ]
                if _text(value)
            )
            if query:
                queries.append(query[:240])
    if external_results and any(not result.get("top_evidence") for result in external_results):
        queries.append("external evidence conflict fallback local report evidence")
    return _dedupe(queries)[:5]


def _aggregate_source_quality(
    local_results: list[dict[str, Any]],
    external_results: list[dict[str, Any]],
    conflict_requery_results: list[dict[str, Any]],
) -> dict[str, Any]:
    local_refs = [item for result in local_results for item in result.get("top_evidence") or []]
    external_refs = [item for result in external_results for item in result.get("top_evidence") or []]
    conflict_refs = [item for result in conflict_requery_results for item in result.get("top_evidence") or []]
    avg_score_values = [_as_float(item.get("score")) for item in [*local_refs, *external_refs, *conflict_refs]]
    avg_score = sum(avg_score_values) / len(avg_score_values) if avg_score_values else 0.0
    return {
        "local_evidence": len(local_refs),
        "external_evidence": len(external_refs),
        "conflict_requery_evidence": len(conflict_refs),
        "external_url_refs": sum(1 for item in external_refs if item.get("url")),
        "avg_retrieval_score": round(avg_score, 6),
        "quality_note": "local_first_claim_query_refinement_with_optional_external",
    }


def _build_local_corpus(context: dict[str, Any]) -> list[dict[str, Any]]:
    corpus = []
    for post in context.get("selected_posts") or []:
        text = " ".join(
            _text(value)
            for value in [
                post.get("excerpt"),
                _get(post, "primary_claim", "claim_text"),
                _get(post, "evidence", "text"),
                _get(post, "evidence", "ocr_text"),
                _get(post, "evidence", "asr_text"),
                _get(post, "evidence", "caption"),
            ]
            if _text(value)
        )
        if text:
            corpus.append(
                {
                    "doc_id": f"post:{_text(post.get('post_id'))}",
                    "source": "selected_post",
                    "title": _text(post.get("post_id")) or "post",
                    "text": text,
                }
            )
    for item in (context.get("review_execution") or {}).get("retrieval_results") or []:
        for evidence in item.get("top_evidence") or []:
            text = _text(evidence.get("text")) or _text(evidence.get("snippet"))
            if text:
                corpus.append(
                    {
                        "doc_id": _text(evidence.get("doc_id")) or f"review:{len(corpus)}",
                        "source": _text(evidence.get("source")) or "review_execution",
                        "title": _text(evidence.get("title")) or _text(item.get("query")),
                        "text": text,
                    }
                )
    for claim in _get(context, "propagation_context", "claim_rank") or []:
        text = " ".join(_text(claim.get(key)) for key in ("claim_id", "claim_text") if _text(claim.get(key)))
        if text:
            corpus.append(
                {
                    "doc_id": f"claim:{_text(claim.get('claim_id'))}",
                    "source": "claim_rank",
                    "title": _text(claim.get("claim_id")) or "claim",
                    "text": text,
                }
            )
    return corpus


def _retrieve_local(*, query: str, corpus: list[dict[str, Any]], top_k: int) -> dict[str, Any]:
    query_tokens = set(_tokens(query))
    rows = []
    for doc in corpus:
        doc_tokens = set(_tokens(doc.get("text")))
        if not query_tokens or not doc_tokens:
            continue
        overlap = len(query_tokens & doc_tokens)
        score = overlap / max(len(query_tokens), 1)
        if score <= 0:
            continue
        rows.append(
            {
                "doc_id": doc.get("doc_id"),
                "source": doc.get("source"),
                "title": doc.get("title"),
                "score": round(score, 6),
                "text": _text(doc.get("text"))[:500],
            }
        )
    rows.sort(key=lambda item: item["score"], reverse=True)
    return {
        "query": query,
        "mode": "local_report_corpus",
        "top_evidence": rows[:top_k],
        "evidence_found": len(rows[:top_k]),
        "retrieved_at": _utc_now(),
    }


def _normalize_external_result(query: str, rows: list[dict[str, Any]]) -> dict[str, Any]:
    evidence = []
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        evidence.append(
            {
                "doc_id": _text(row.get("doc_id")) or _hash_text(row),
                "source": _text(row.get("source")) or _text(row.get("url")) or "external_provider",
                "title": _text(row.get("title")),
                "url": _text(row.get("url")),
                "score": round(max(0.0, min(1.0, _as_float(row.get("score"), 0.5))), 6),
                "text": (_text(row.get("text")) or _text(row.get("snippet")))[:500],
                "retrieved_at": _utc_now(),
            }
        )
    return {
        "query": query,
        "mode": "external_provider",
        "top_evidence": evidence,
        "evidence_found": len(evidence),
        "retrieved_at": _utc_now(),
    }


def _uncertainties_for_agent(
    agent_name: str,
    context: dict[str, Any],
    retrieval_bundle: dict[str, Any],
    debate_bundle: dict[str, Any],
) -> list[str]:
    uncertainties = []
    if agent_name in {"ClaimEvidenceAgent", "QuestionReflectionAgent", "HarmfulnessJudgeAgent"}:
        if not retrieval_bundle.get("local_results"):
            uncertainties.append("no_active_retrieval_results")
        elif any(not result.get("top_evidence") for result in retrieval_bundle.get("local_results") or []):
            uncertainties.append("some_queries_have_no_local_evidence")
    if debate_bundle.get("triggered"):
        uncertainties.append("light_debate_triggered_by_conflict")
    for post in context.get("selected_posts") or []:
        view = post.get("post_view_detection") or {}
        if view.get("conflict"):
            uncertainties.append("cross_view_conflict")
        if _get(post, "stance", "abstain"):
            uncertainties.append("stance_abstained")
    return _dedupe(uncertainties)


def _source_quality(local_refs: list[dict[str, Any]], external_refs: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "local_evidence": len(local_refs),
        "external_evidence": len(external_refs),
        "external_url_refs": sum(1 for item in external_refs if item.get("url")),
        "quality_note": "local_first_optional_external",
    }


def _policy_rule_refs(policy: dict[str, Any]) -> list[dict[str, Any]]:
    if not isinstance(policy, dict):
        return []
    refs = []
    for rule in policy.get("candidate_rules") or []:
        if not isinstance(rule, dict) or rule.get("status") not in {"accepted_for_round", "activated"}:
            continue
        refs.append(
            {
                "rule_id": rule.get("rule_id"),
                "round": rule.get("round"),
                "description": rule.get("description"),
                "source": rule.get("source"),
            }
        )
    return refs[:8]


def _suggested_actions(
    agent_name: str,
    uncertainties: list[str],
    retrieval_bundle: dict[str, Any],
) -> list[str]:
    actions = []
    if uncertainties:
        actions.append("human_review_required")
    if any(not result.get("top_evidence") for result in retrieval_bundle.get("local_results") or []):
        actions.append("consider_external_retrieval")
    if agent_name == "CountermeasureAgent":
        actions.append("do_not_publish_without_human_approval")
    if agent_name == "HarmfulnessJudgeAgent":
        actions.append("keep_detector_outputs_unchanged")
    return _dedupe(actions)


def _sidecar_confidence(
    local_refs: list[dict[str, Any]],
    external_refs: list[dict[str, Any]],
    uncertainties: list[str],
) -> float:
    base = 0.45 + min(0.25, 0.03 * len(local_refs)) + min(0.2, 0.05 * len(external_refs))
    penalty = min(0.35, 0.06 * len(uncertainties))
    return round(max(0.05, min(0.95, base - penalty)), 4)


def _debate_role_for_stage(stage: str) -> str:
    if stage == "opening":
        return "evidence_affirming_agent"
    if stage == "rebuttal":
        return "evidence_skeptic_agent"
    if stage == "closing":
        return "countermeasure_safety_agent"
    if stage == "judge_synthesis":
        return "debate_judge"
    return "free_debate_cross_examiner"


def _full_debate_prompt(
    *,
    stage: str,
    role: str,
    context: dict[str, Any],
    retrieval_bundle: dict[str, Any],
    reasons: list[str],
    prior_text: str,
) -> str:
    payload = {
        "stage": stage,
        "role": role,
        "trigger_reasons": reasons,
        "selected_posts": context.get("selected_posts") or [],
        "active_policy": context.get("active_policy") or context.get("policy") or {},
        "retrieval_summary": {
            "queries": retrieval_bundle.get("queries") or [],
            "source_quality": retrieval_bundle.get("source_quality") or {},
            "local_results": retrieval_bundle.get("local_results") or [],
            "external_results": retrieval_bundle.get("external_results") or [],
            "conflict_requery_results": retrieval_bundle.get("conflict_requery_results") or [],
        },
        "prior_debate_excerpt": prior_text[-3000:],
        "instruction": (
            "Use this stage to debate evidence sufficiency, multimodal conflict, "
            "claim linkage, and whether additional evidence is required before "
            "a human harmfulness decision."
        ),
    }
    return str(payload)


def _debate_evidence_requests(reasons: list[str], retrieval_bundle: dict[str, Any]) -> list[str]:
    requests = []
    if any("cross_view_conflict" in reason or "high_conflict" in reason for reason in reasons):
        requests.append("request_visual_ooc_or_source_context_check")
    if any("claim_stance_uncertain" in reason for reason in reasons):
        requests.append("request_claim_conditioned_stance_recheck")
    if any("no_local_evidence" in reason for reason in reasons):
        requests.append("request_external_or_curated_evidence_search")
    if (retrieval_bundle.get("source_quality") or {}).get("external_evidence", 0) == 0:
        requests.append("external_evidence_not_available_in_current_run")
    return _dedupe(requests)


def _tokens(value: Any) -> list[str]:
    return [match.group(0).lower() for match in TOKEN_PATTERN.finditer(_text(value))]


def _hash_text(value: Any) -> str:
    return sha256(str(value).encode("utf-8")).hexdigest()


def _dedupe(values: list[str]) -> list[str]:
    seen = set()
    rows = []
    for value in values:
        text = _text(value)
        if not text or text in seen:
            continue
        seen.add(text)
        rows.append(text)
    return rows


def _get(mapping: dict[str, Any], *path: str) -> Any:
    value: Any = mapping
    for part in path:
        if not isinstance(value, dict):
            return None
        value = value.get(part)
    return value


def _as_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()
