"""Offline MARO reference-protocol adapter for local misinformation experiments.

This module mirrors MARO's implemented role order while keeping it out of the
production Review runtime. It is limited to a text post and an optional,
separately scoped comment view. Comments are never converted into fact evidence
and Weibo21 comment timing remains explicitly unknown.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Awaitable, Callable, Mapping, Protocol
import json
import time
import uuid

from app.core.review.agent_contracts import (
    CLAIM_EVIDENCE_BEGIN,
    CLAIM_EVIDENCE_END,
    JUDGE_DECISION_BEGIN,
    JUDGE_DECISION_END,
    parse_claim_evidence_footer,
    parse_judge_decision_footer,
)
from app.core.review.evidence_contracts import EvidenceBundle, RationaleCapsule, apply_claim_assessment


MARO_PROTOCOL_VERSION = "maro-weibo21-reference-adapter-v1"
MARO_PAPER_PROTOCOL_VERSION = "maro-weibo21-paper-adapter-v2"
MARO_CONTENT_AGENT = "MAROContentAnalysisAgent"
MARO_COMMENT_AGENT = "MAROCommentAnalysisAgent"
MARO_QUESTION_AGENT = "MAROFactCheckingQuestionAgent"
MARO_SUMMARIZER_AGENT = "MAROFactCheckingSummarizer"
MARO_FACT_AGENT = "MAROFactCheckingAgent"
MARO_REFLECTION_AGENT = "MAROQuestionReflectionAgent"
MARO_JUDGE_AGENT = "HarmfulnessJudgeAgent"
MARO_ROLE_ORDER = (
    MARO_CONTENT_AGENT,
    MARO_COMMENT_AGENT,
    MARO_QUESTION_AGENT,
    MARO_SUMMARIZER_AGENT,
    MARO_FACT_AGENT,
    MARO_JUDGE_AGENT,
)
MARO_PAPER_ROLE_ORDER = (
    MARO_CONTENT_AGENT,
    MARO_COMMENT_AGENT,
    MARO_QUESTION_AGENT,
    MARO_SUMMARIZER_AGENT,
    MARO_FACT_AGENT,
    MARO_REFLECTION_AGENT,
    MARO_CONTENT_AGENT,
    MARO_COMMENT_AGENT,
    MARO_FACT_AGENT,
    MARO_JUDGE_AGENT,
)
MARO_FACT_PLAN_BEGIN = "<MARO_FACT_CHECKING_PLAN>"
MARO_FACT_PLAN_END = "</MARO_FACT_CHECKING_PLAN>"
MARO_REFLECTION_PLAN_BEGIN = "<MARO_REFLECTION_PLAN>"
MARO_REFLECTION_PLAN_END = "</MARO_REFLECTION_PLAN>"

__all__ = [
    "MARO_PROTOCOL_VERSION",
    "MARO_PAPER_PROTOCOL_VERSION",
    "MARO_CONTENT_AGENT",
    "MARO_COMMENT_AGENT",
    "MARO_QUESTION_AGENT",
    "MARO_SUMMARIZER_AGENT",
    "MARO_FACT_AGENT",
    "MARO_REFLECTION_AGENT",
    "MARO_JUDGE_AGENT",
    "MARO_ROLE_ORDER",
    "MARO_PAPER_ROLE_ORDER",
    "MARO_FACT_PLAN_BEGIN",
    "MARO_FACT_PLAN_END",
    "MARO_REFLECTION_PLAN_BEGIN",
    "MARO_REFLECTION_PLAN_END",
    "build_maro_input_views",
    "parse_fact_checking_plan",
    "parse_reflection_plan",
    "run_maro_paper_reference_review",
    "run_maro_reference_review",
]


class MAROProvider(Protocol):
    async def __call__(
        self,
        *,
        agent_name: str,
        system_prompt: str,
        user_prompt: str,
        input_bundle: dict[str, Any],
        model: str,
    ) -> str: ...


Retriever = Callable[..., Awaitable[list[dict[str, Any]]]]


@dataclass(frozen=True)
class MAROInputViews:
    """The two input views consumed by MARO's content and comment roles."""

    input_profile: str
    original_news: str
    comments: tuple[str, ...]
    original_news_and_comment: str
    comment_temporal_scope: str
    post_time_leakage_risk: bool

    @property
    def comments_available(self) -> bool:
        return self.input_profile == "post_and_comments" and bool(self.comments)


def build_maro_input_views(case: Mapping[str, Any]) -> MAROInputViews:
    """Build dual MARO views and require a non-empty original-news view."""

    raw = case.get("maro_inputs") if isinstance(case.get("maro_inputs"), Mapping) else {}
    profile = str(raw.get("input_profile") or "post_only").strip()
    if profile not in {"post_only", "post_and_comments"}:
        raise ValueError(f"Unsupported MARO input profile: {profile}")
    original_news = str(raw.get("original_news") or case.get("text") or "").strip()
    if not original_news:
        raise ValueError("MARO reference protocol requires non-empty original_news")
    comments = (
        tuple(str(item).strip() for item in _as_list(raw.get("comments")) if str(item).strip())
        if profile == "post_and_comments"
        else ()
    )
    original_news_and_comment = str(raw.get("original_news_and_comment") or "").strip()
    if not original_news_and_comment:
        original_news_and_comment = _join_post_and_comments(original_news, comments)
    return MAROInputViews(
        input_profile=profile,
        original_news=original_news,
        comments=comments,
        original_news_and_comment=original_news_and_comment,
        comment_temporal_scope="unknown" if profile == "post_and_comments" else "not_used",
        post_time_leakage_risk=bool(profile == "post_and_comments" and comments),
    )


async def run_maro_reference_review(
    *,
    case: Mapping[str, Any],
    provider: MAROProvider,
    model: str,
    active_retriever: Retriever | None,
    external_retrieval_enabled: bool,
    retrieval_top_k: int,
    max_agent_calls_per_case: int,
    include_question_reflection: bool = False,
    include_judge: bool = True,
) -> dict[str, Any]:
    """Run MARO's analysis and fact-checking sequence for one local case.

    The final judge keeps the existing ``HarmfulnessJudgeAgent`` identifier so
    that the experiment evaluator can reuse its typed Teacher-silver parser.
    ``maro_role`` preserves the source-framework role name for audit.
    """

    views = build_maro_input_views(case)
    protocol_version = MARO_PAPER_PROTOCOL_VERSION if include_question_reflection else MARO_PROTOCOL_VERSION
    role_order = MARO_PAPER_ROLE_ORDER if include_question_reflection else MARO_ROLE_ORDER
    if not include_judge:
        role_order = role_order[:-1]
    call_state = _CallState(
        max_calls=max(1, int(max_agent_calls_per_case)) if max_agent_calls_per_case > 0 else len(role_order)
    )
    reports: list[dict[str, Any]] = []

    content = await _call_role(
        provider,
        call_state,
        agent_name=MARO_CONTENT_AGENT,
        maro_role="Writing Style Analysis Agent",
        system_prompt=_content_system_prompt(),
        input_bundle={"original_news": views.original_news},
        model=model,
    )
    reports.append(content)

    comment = await _call_role(
        provider,
        call_state,
        agent_name=MARO_COMMENT_AGENT,
        maro_role="Comment Analysis Agent",
        system_prompt=_comment_system_prompt(),
        input_bundle={
            "original_news_and_comment": views.original_news_and_comment,
            "comments": list(views.comments),
            "comments_available": views.comments_available,
            "comment_temporal_scope": views.comment_temporal_scope,
            "post_time_leakage_risk": views.post_time_leakage_risk,
        },
        model=model,
    )
    reports.append(comment)

    question = await _call_role(
        provider,
        call_state,
        agent_name=MARO_QUESTION_AGENT,
        maro_role="Fact-Checking Questioning Agent",
        system_prompt=_question_system_prompt(),
        input_bundle={
            "original_news": views.original_news,
            "content_analysis_report": content["report_text"],
            "comment_analysis_report": comment["report_text"],
        },
        model=model,
    )
    reports.append(question)
    fact_plan, fact_plan_error = parse_fact_checking_plan(question["report_text"])

    evidence_bundle, retrieval_audit = await _retrieve_fact_evidence(
        fact_plan,
        fact_plan_error=fact_plan_error,
        active_retriever=active_retriever,
        external_retrieval_enabled=external_retrieval_enabled,
        retrieval_top_k=retrieval_top_k,
        original_news=views.original_news,
    )

    summarizer = await _call_role(
        provider,
        call_state,
        agent_name=MARO_SUMMARIZER_AGENT,
        maro_role="Fact-Checking Summarizer",
        system_prompt=_summarizer_system_prompt(),
        input_bundle={
            "original_news": views.original_news,
            "fact_checking_plan": fact_plan,
            "evidence_bundle": evidence_bundle.to_dict(),
        },
        model=model,
    )
    reports.append(summarizer)

    fact = await _call_role(
        provider,
        call_state,
        agent_name=MARO_FACT_AGENT,
        maro_role="Fact-Checking Agent",
        system_prompt=_fact_system_prompt(),
        input_bundle={
            "original_news": views.original_news,
            "fact_checking_plan": fact_plan,
            "evidence_bundle": evidence_bundle.to_dict(),
            "fact_checking_summary": summarizer["report_text"],
        },
        model=model,
    )
    fact_text, fact_assessment, fact_error = parse_claim_evidence_footer(fact["report_text"])
    fact["report_text"] = fact_text
    if fact_assessment is not None:
        evidence_bundle = apply_claim_assessment(evidence_bundle, fact_assessment)
    fact["structured_sidecar"] = {
        "claim_assessment": fact_assessment,
        "claim_assessment_valid": fact_error is None,
        "claim_assessment_error": fact_error,
        "evidence_bundle": evidence_bundle.to_dict(),
    }
    reports.append(fact)

    content_report = content["report_text"]
    comment_report = comment["report_text"]
    fact_report = fact["report_text"]
    reflection_error: str | None = None
    if include_question_reflection:
        reflection = await _call_role(
            provider,
            call_state,
            agent_name=MARO_REFLECTION_AGENT,
            maro_role="Questioning Agent",
            system_prompt=_reflection_system_prompt(),
            input_bundle={
                "original_news": views.original_news,
                "content_analysis_report": content_report,
                "comment_analysis_report": comment_report,
                "fact_checking_report": fact_report,
                "evidence_bundle": evidence_bundle.to_dict(),
            },
            model=model,
        )
        reports.append(reflection)
        reflection_plan, reflection_error = parse_reflection_plan(reflection["report_text"])

        content_refinement = await _call_role(
            provider,
            call_state,
            agent_name=MARO_CONTENT_AGENT,
            maro_role="Writing Style Analysis Agent (reflection response)",
            system_prompt=_content_refinement_system_prompt(),
            input_bundle={
                "original_news": views.original_news,
                "initial_report": content_report,
                "reflection_questions": reflection_plan["content_questions"],
            },
            model=model,
        )
        reports.append(content_refinement)

        comment_refinement = await _call_role(
            provider,
            call_state,
            agent_name=MARO_COMMENT_AGENT,
            maro_role="Comment Analysis Agent (reflection response)",
            system_prompt=_comment_refinement_system_prompt(),
            input_bundle={
                "original_news_and_comment": views.original_news_and_comment,
                "initial_report": comment_report,
                "reflection_questions": reflection_plan["comment_questions"],
                "comments_available": views.comments_available,
                "comment_temporal_scope": views.comment_temporal_scope,
                "post_time_leakage_risk": views.post_time_leakage_risk,
            },
            model=model,
        )
        reports.append(comment_refinement)

        fact_refinement = await _call_role(
            provider,
            call_state,
            agent_name=MARO_FACT_AGENT,
            maro_role="Fact-Checking Agent (reflection response)",
            system_prompt=_fact_refinement_system_prompt(),
            input_bundle={
                "original_news": views.original_news,
                "initial_report": fact_report,
                "reflection_questions": reflection_plan["fact_questions"],
                "fact_checking_plan": fact_plan,
                "evidence_bundle": evidence_bundle.to_dict(),
            },
            model=model,
        )
        refined_fact_text, refined_fact_assessment, refined_fact_error = parse_claim_evidence_footer(
            fact_refinement["report_text"]
        )
        fact_refinement["report_text"] = refined_fact_text
        if refined_fact_assessment is not None:
            evidence_bundle = apply_claim_assessment(evidence_bundle, refined_fact_assessment)
        fact_refinement["structured_sidecar"] = {
            "claim_assessment": refined_fact_assessment,
            "claim_assessment_valid": refined_fact_error is None,
            "claim_assessment_error": refined_fact_error,
            "evidence_bundle": evidence_bundle.to_dict(),
        }
        reports.append(fact_refinement)

        content_report = _merge_analysis_reports(content_report, content_refinement["report_text"])
        comment_report = _merge_analysis_reports(comment_report, comment_refinement["report_text"])
        fact_report = _merge_analysis_reports(fact_report, fact_refinement["report_text"])

    rationale_capsules = _build_rationale_capsules(summarizer["report_text"], evidence_bundle)
    prediction: dict[str, Any] | None = None
    judge_error: str | None = None
    prediction_masked = False
    if include_judge:
        judge = await _call_role(
            provider,
            call_state,
            agent_name=MARO_JUDGE_AGENT,
            maro_role="Judgment Agent",
            system_prompt=_judge_system_prompt(),
            input_bundle={
                "original_news": views.original_news,
                "content_analysis_report": content_report,
                "comment_analysis_report": comment_report,
                "fact_checking_report": fact_report,
                "evidence_bundle": evidence_bundle.to_dict(),
                "rationale_capsules": rationale_capsules,
                "protocol_limitations": {
                    "comment_temporal_scope": views.comment_temporal_scope,
                    "post_time_leakage_risk": views.post_time_leakage_risk,
                },
            },
            model=model,
        )
        judge_text, prediction, judge_error = parse_judge_decision_footer(judge["report_text"])
        prediction, prediction_masked = _mask_unverified_misinfo_prediction(prediction, evidence_bundle)
        judge["report_text"] = judge_text
        judge["report_role"] = "judge_final"
        judge["structured_sidecar"] = {
            "teacher_prediction": prediction or {},
            "teacher_prediction_valid": judge_error is None,
            "teacher_prediction_error": judge_error,
            "misinfo_prediction_masked": prediction_masked,
            "review_required": bool((prediction or {}).get("review_required", True)),
            "evidence_bundle": evidence_bundle.to_dict(),
            "rationale_capsules": rationale_capsules,
            "evidence_refs": list(evidence_bundle.source_refs),
            "uncertainties": _uncertainties(evidence_bundle, fact_plan_error, judge_error),
        }
        reports.append(judge)

    completed = sum(1 for item in reports if item["status"] == "completed")
    return {
        "schema_version": protocol_version,
        "input_bundle": {
            "selected_posts": [{"content": views.original_news, "claim_text": views.original_news}],
            "maro_input_views": asdict(views),
            "evidence_bundle": evidence_bundle.to_dict(),
        },
        "agent_reports": reports,
        "evidence_bundle": evidence_bundle.to_dict(),
        "rationale_capsules": rationale_capsules,
        "active_retrieval": {"audit": retrieval_audit},
        "audit": {
            "protocol": protocol_version,
            "role_order": list(role_order),
            "comment_temporal_scope": views.comment_temporal_scope,
            "post_time_leakage_risk": views.post_time_leakage_risk,
            "fact_plan_error": fact_plan_error,
            "reflection_error": reflection_error,
            "judge_error": judge_error,
            "misinfo_prediction_masked": prediction_masked,
            "llm_call_audit": call_state.audit,
            "failure_mode_tags": _uncertainties(evidence_bundle, fact_plan_error, judge_error),
        },
        "summary": {
            "requested_agents": len(reports),
            "completed": completed,
            "failed": len(reports) - completed,
            "planned_llm_call_count": len(role_order),
            "actual_llm_call_count": call_state.count,
            "llm_call_budget": call_state.max_calls,
            "effective_runtime_mode": "maro_reference",
            "review_task": "claim_deception",
            "analysis_stage_only": not include_judge,
        },
    }


@dataclass
class _CallState:
    max_calls: int
    count: int = 0
    audit: list[dict[str, Any]] = field(default_factory=list)


async def _call_role(
    provider: MAROProvider,
    state: _CallState,
    *,
    agent_name: str,
    maro_role: str,
    system_prompt: str,
    input_bundle: dict[str, Any],
    model: str,
) -> dict[str, Any]:
    review_id = f"maro::{uuid.uuid4().hex}"
    if state.count >= state.max_calls:
        return _failed_role_report(review_id, agent_name, maro_role, input_bundle, "llm_call_budget_exhausted")
    state.count += 1
    started = time.perf_counter()
    try:
        report_text = await provider(
            agent_name=agent_name,
            system_prompt=system_prompt,
            user_prompt=json.dumps(input_bundle, ensure_ascii=False),
            input_bundle=input_bundle,
            model=model,
        )
    except Exception as exc:
        duration = round((time.perf_counter() - started) * 1000, 3)
        state.audit.append({"agent_name": agent_name, "status": "failed", "duration_ms": duration, "error_class": type(exc).__name__})
        return _failed_role_report(review_id, agent_name, maro_role, input_bundle, f"{type(exc).__name__}: {str(exc)[:500]}")
    duration = round((time.perf_counter() - started) * 1000, 3)
    state.audit.append({"agent_name": agent_name, "status": "completed", "duration_ms": duration})
    return {
        "review_id": review_id,
        "agent_name": agent_name,
        "maro_role": maro_role,
        "report_role": "maro_stage",
        "status": "completed",
        "report_text": str(report_text or "").strip(),
        "input_scope": input_bundle,
    }


def _failed_role_report(
    review_id: str,
    agent_name: str,
    maro_role: str,
    input_bundle: dict[str, Any],
    error: str,
) -> dict[str, Any]:
    return {
        "review_id": review_id,
        "agent_name": agent_name,
        "maro_role": maro_role,
        "report_role": "maro_stage",
        "status": "failed",
        "report_text": "",
        "error": error,
        "input_scope": input_bundle,
    }


def parse_fact_checking_plan(report_text: str) -> tuple[dict[str, Any], str | None]:
    """Parse MARO's question stage into a bounded, retrieval-safe plan."""

    text = str(report_text or "")
    begin = text.rfind(MARO_FACT_PLAN_BEGIN)
    end = text.rfind(MARO_FACT_PLAN_END)
    if begin < 0 or end < begin:
        return _empty_fact_plan(), "missing_fact_checking_plan"
    try:
        payload = json.loads(text[begin + len(MARO_FACT_PLAN_BEGIN) : end].strip())
    except (TypeError, ValueError, json.JSONDecodeError):
        return _empty_fact_plan(), "invalid_fact_checking_plan_json"
    if not isinstance(payload, dict):
        return _empty_fact_plan(), "invalid_fact_checking_plan_schema"
    assessment = str(payload.get("claim_assessment") or "").strip().lower()
    claim = str(payload.get("claim") or "").strip()
    questions = [str(item).strip() for item in _as_list(payload.get("questions")) if str(item).strip()]
    if assessment not in {"checkable", "no_verifiable_claim", "extraction_failed"}:
        return _empty_fact_plan(), "invalid_claim_assessment"
    if assessment == "checkable" and (not claim or not questions):
        return _empty_fact_plan(), "missing_claim_or_questions"
    if assessment != "checkable" and (claim or questions):
        return _empty_fact_plan(), "noncheckable_plan_contains_queries"
    return {
        "claim_assessment": assessment,
        "claim": claim,
        "assessment_reason": str(payload.get("assessment_reason") or "").strip(),
        "questions": questions[:3],
    }, None


def parse_reflection_plan(report_text: str) -> tuple[dict[str, list[str]], str | None]:
    """Parse role-specific reflection questions for MARO's second analysis pass."""

    text = str(report_text or "")
    begin = text.rfind(MARO_REFLECTION_PLAN_BEGIN)
    end = text.rfind(MARO_REFLECTION_PLAN_END)
    if begin < 0 or end < begin:
        return _empty_reflection_plan(), "missing_reflection_plan"
    try:
        payload = json.loads(text[begin + len(MARO_REFLECTION_PLAN_BEGIN) : end].strip())
    except (TypeError, ValueError, json.JSONDecodeError):
        return _empty_reflection_plan(), "invalid_reflection_plan_json"
    if not isinstance(payload, dict):
        return _empty_reflection_plan(), "invalid_reflection_plan_schema"
    plan: dict[str, list[str]] = {}
    for key in ("content_questions", "comment_questions", "fact_questions"):
        value = payload.get(key)
        if not isinstance(value, list) or any(not str(item).strip() for item in value):
            return _empty_reflection_plan(), f"invalid_{key}"
        plan[key] = [str(item).strip() for item in value[:3]]
    return plan, None


async def run_maro_paper_reference_review(
    *,
    case: Mapping[str, Any],
    provider: MAROProvider,
    model: str,
    active_retriever: Retriever | None,
    external_retrieval_enabled: bool,
    retrieval_top_k: int,
    max_agent_calls_per_case: int,
) -> dict[str, Any]:
    """Run the paper-described MARO chain with one reflection response per expert."""

    return await run_maro_reference_review(
        case=case,
        provider=provider,
        model=model,
        active_retriever=active_retriever,
        external_retrieval_enabled=external_retrieval_enabled,
        retrieval_top_k=retrieval_top_k,
        max_agent_calls_per_case=max_agent_calls_per_case,
        include_question_reflection=True,
    )


async def run_maro_paper_multi_dimensional_analysis(
    *,
    case: Mapping[str, Any],
    provider: MAROProvider,
    model: str,
    active_retriever: Retriever | None,
    external_retrieval_enabled: bool,
    retrieval_top_k: int,
    max_agent_calls_per_case: int,
) -> dict[str, Any]:
    """Build MARO's analysis report without running the later INS Judge."""

    return await run_maro_reference_review(
        case=case,
        provider=provider,
        model=model,
        active_retriever=active_retriever,
        external_retrieval_enabled=external_retrieval_enabled,
        retrieval_top_k=retrieval_top_k,
        max_agent_calls_per_case=max_agent_calls_per_case,
        include_question_reflection=True,
        include_judge=False,
    )


async def _retrieve_fact_evidence(
    fact_plan: Mapping[str, Any],
    *,
    fact_plan_error: str | None,
    active_retriever: Retriever | None,
    external_retrieval_enabled: bool,
    retrieval_top_k: int,
    original_news: str,
) -> tuple[EvidenceBundle, dict[str, Any]]:
    assessment = str(fact_plan.get("claim_assessment") or "not_assessed")
    initial = EvidenceBundle(
        claim=str(fact_plan.get("claim") or ""),
        claim_assessment=assessment if assessment in {"checkable", "no_verifiable_claim", "extraction_failed"} else "extraction_failed",
        assessment_provenance="maro_fact_questioning",
        assessment_reason=str(fact_plan.get("assessment_reason") or fact_plan_error or ""),
    )
    audit: dict[str, Any] = {"queries": [], "failures": [], "external_retrieval_enabled": external_retrieval_enabled}
    if fact_plan_error:
        return initial, {**audit, "status": "plan_invalid"}
    if initial.claim_assessment != "checkable":
        return EvidenceBundle.from_mapping({**initial.to_dict(), "retrieval_status": "skipped_non_eligible_claim"}), {**audit, "status": "claim_not_eligible"}
    if not external_retrieval_enabled or active_retriever is None:
        return EvidenceBundle.from_mapping({**initial.to_dict(), "retrieval_status": "provider_unavailable"}), {**audit, "status": "provider_unavailable"}

    source_refs: list[dict[str, Any]] = []
    for question in list(fact_plan.get("questions") or [])[:3]:
        try:
            rows = await active_retriever(
                query=str(question),
                context={"original_news": original_news, "claim": initial.claim, "maro_protocol": MARO_PROTOCOL_VERSION},
                top_k=max(1, int(retrieval_top_k)),
            )
        except Exception as exc:
            audit["failures"].append({"query": str(question), "error_class": type(exc).__name__})
            continue
        audit["queries"].append(str(question))
        for index, row in enumerate(rows or []):
            if not isinstance(row, Mapping):
                continue
            text = str(row.get("text") or row.get("snippet") or "").strip()
            url = str(row.get("url") or row.get("source_uri") or "").strip()
            if not text or not url:
                continue
            source_refs.append(
                {
                    "doc_id": str(row.get("doc_id") or f"maro-retrieval-{len(source_refs) + index + 1}"),
                    "source": str(row.get("source") or row.get("title") or "external_retrieval"),
                    "url": url,
                    "text": text[:2000],
                    "score": row.get("score"),
                }
            )
    if not source_refs:
        status = "provider_failed" if audit["failures"] and not audit["queries"] else "completed_no_relevant_evidence"
        return EvidenceBundle.from_mapping({**initial.to_dict(), "retrieval_status": status}), {**audit, "status": status}
    return EvidenceBundle.from_mapping(
        {
            **initial.to_dict(),
            "query": " | ".join(audit["queries"]),
            "source_refs": source_refs,
            "retrieval_status": "completed",
            "source_quality": "provider_declared",
        }
    ), {**audit, "status": "completed", "source_count": len(source_refs)}


def _build_rationale_capsules(summary: str, evidence_bundle: EvidenceBundle) -> list[dict[str, Any]]:
    snippets = tuple(evidence_bundle.quoted_spans) or tuple(
        str(item.get("text") or "")[:240] for item in evidence_bundle.source_refs[:2] if str(item.get("text") or "")
    )
    capsule = RationaleCapsule(
        task="claim_deception",
        capsule_text=str(summary or "").strip()[:500],
        input_spans=snippets,
        evidence_refs=tuple(str(item.get("doc_id") or "") for item in evidence_bundle.source_refs if item.get("doc_id")),
        citation_coverage=1.0 if snippets and evidence_bundle.has_traceable_evidence else 0.0,
        source_traceability=evidence_bundle.has_traceable_evidence,
        relation_validity=evidence_bundle.relation_valid,
        rationale_span_available=bool(snippets),
        capsule_quality_gate=bool(
            summary
            and snippets
            and evidence_bundle.has_traceable_evidence
            and evidence_bundle.relation_valid
        ),
    )
    return [capsule.to_dict()]


def _uncertainties(bundle: EvidenceBundle, fact_plan_error: str | None, judge_error: str | None) -> list[str]:
    values = [
        fact_plan_error,
        judge_error,
        None if bundle.claim_assessment == "checkable" else f"claim_assessment:{bundle.claim_assessment}",
        None if bundle.retrieval_status == "completed" else f"retrieval_status:{bundle.retrieval_status}",
        None if bundle.relation_valid else "unverified_fact_relation",
    ]
    return [item for item in values if item]


def _mask_unverified_misinfo_prediction(
    prediction: dict[str, Any] | None,
    evidence_bundle: EvidenceBundle,
) -> tuple[dict[str, Any] | None, bool]:
    """Prevent an LLM footer from asserting a fact risk without valid evidence."""

    if prediction is None or evidence_bundle.claim_risk_available:
        return prediction, False
    main_axes = prediction.get("main_axes") if isinstance(prediction.get("main_axes"), dict) else {}
    review_reason = [str(item) for item in prediction.get("review_reason") or [] if str(item).strip()]
    if "fact_evidence_not_traceable" not in review_reason:
        review_reason.append("fact_evidence_not_traceable")
    return {
        **prediction,
        "main_axes": {
            **main_axes,
            "misinfo_claim_risk": {
                "available": False,
                "label": "unavailable",
                "confidence": 0.0,
            },
        },
        "review_required": True,
        "review_reason": review_reason,
    }, True


def _empty_fact_plan() -> dict[str, Any]:
    return {"claim_assessment": "extraction_failed", "claim": "", "assessment_reason": "", "questions": []}


def _empty_reflection_plan() -> dict[str, list[str]]:
    return {"content_questions": [], "comment_questions": [], "fact_questions": []}


def _merge_analysis_reports(initial: str, refinement: str) -> str:
    initial_text = str(initial or "").strip()
    refinement_text = str(refinement or "").strip()
    if not refinement_text:
        return initial_text
    if not initial_text:
        return refinement_text
    return f"Initial analysis:\n{initial_text}\n\nReflection response:\n{refinement_text}"


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else ([] if value is None else [value])


def _join_post_and_comments(post: str, comments: tuple[str, ...]) -> str:
    if not comments:
        return post
    return "[POST]\n" + post + "\n[COMMENTS]\n" + "\n".join(
        f"[COMMENT {index}] {item}" for index, item in enumerate(comments, start=1)
    )


def _content_system_prompt() -> str:
    return (
        "You are MARO's Writing Style Analysis Agent. Analyze only original_news. "
        "Describe wording, attribution, factual-claim cues, and uncertainty. Do not infer truth, read comments, or output a final label."
    )


def _comment_system_prompt() -> str:
    return (
        "You are MARO's Comment Analysis Agent. Analyze only the supplied comment view. "
        "If comments_available is false, state that the view is unavailable. Comments are not verified evidence; "
        "their temporal scope can be unknown. Do not read external facts or issue a final label."
    )


def _question_system_prompt() -> str:
    return (
        "You are MARO's Fact-Checking Questioning Agent. From original_news and the two analysis reports, "
        "identify one checkable factual claim and up to three targeted verification questions, or state that no "
        "verifiable claim exists. Append exactly one JSON footer without Markdown: "
        f"{MARO_FACT_PLAN_BEGIN}{{\"claim_assessment\":\"checkable|no_verifiable_claim|extraction_failed\","
        "\"claim\":\"string only when checkable\",\"assessment_reason\":\"string\","
        "\"questions\":[\"up to three questions only when checkable\"]}"
        f"{MARO_FACT_PLAN_END}."
    )


def _summarizer_system_prompt() -> str:
    return (
        "You are MARO's Fact-Checking Summarizer. Summarize only the supplied traceable evidence bundle. "
        "Cite doc_id values beside each factual statement. Do not turn missing retrieval into evidence or issue a final label."
    )


def _fact_system_prompt() -> str:
    return (
        "You are MARO's Fact-Checking Agent. Assess only the supplied claim and traceable retrieval results. "
        "A supported, contradicted, or conflicting relation requires completed retrieval, cited source_ref_ids, and quoted_spans. "
        "Provider failure, no claim, or no relevant results must use relation=not_applicable. Append exactly one JSON footer: "
        f"{CLAIM_EVIDENCE_BEGIN}{{\"claim_assessment\":\"checkable|no_verifiable_claim|extraction_failed\","
        "\"claim\":\"string only when checkable\",\"assessment_reason\":\"string\","
        "\"relation\":\"not_applicable|supported|contradicted|conflicting\","
        "\"source_ref_ids\":[\"doc_id\"],\"quoted_spans\":[\"verbatim source span\"]}"
        f"{CLAIM_EVIDENCE_END}."
    )


def _reflection_system_prompt() -> str:
    return (
        "You are MARO's Questioning Agent. Inspect the initial writing-style, comment, and fact-checking reports "
        "for missing reasoning, unsupported conclusions, or overlooked uncertainty. Ask up to three targeted questions "
        "for each named expert. Do not issue a final label or introduce new facts. Append exactly one JSON footer: "
        f"{MARO_REFLECTION_PLAN_BEGIN}{{\"content_questions\":[\"questions for writing-style analysis\"],"
        "\"comment_questions\":[\"questions for comment analysis\"],"
        "\"fact_questions\":[\"questions for fact checking\"]}"
        f"{MARO_REFLECTION_PLAN_END}."
    )


def _content_refinement_system_prompt() -> str:
    return (
        "You are MARO's Writing Style Analysis Agent responding to reflection questions. "
        "Re-examine only original_news and the initial report. Answer each question with observable wording, attribution, "
        "or uncertainty; do not determine truthfulness or issue a final label."
    )


def _comment_refinement_system_prompt() -> str:
    return (
        "You are MARO's Comment Analysis Agent responding to reflection questions. "
        "Re-examine only the supplied comment view and initial report. Distinguish commenter opinion from verified fact, "
        "preserve unknown comment timing, and do not issue a final label."
    )


def _fact_refinement_system_prompt() -> str:
    return (
        "You are MARO's Fact-Checking Agent responding to reflection questions. Re-examine only the supplied claim, "
        "traceable evidence, and initial report. Do not invent evidence. Append exactly one JSON footer using the same "
        "claim_assessment, relation, source_ref_ids, and quoted_spans contract as the initial fact-checking stage: "
        f"{CLAIM_EVIDENCE_BEGIN}{{\"claim_assessment\":\"checkable|no_verifiable_claim|extraction_failed\","
        "\"claim\":\"string only when checkable\",\"assessment_reason\":\"string\","
        "\"relation\":\"not_applicable|supported|contradicted|conflicting\","
        "\"source_ref_ids\":[\"doc_id\"],\"quoted_spans\":[\"verbatim source span\"]}"
        f"{CLAIM_EVIDENCE_END}."
    )


def _judge_system_prompt() -> str:
    return (
        "You are MARO's Judgment Agent. Synthesize the role reports without inventing evidence. "
        "For misinfo_claim_risk, mark the axis unavailable when the claim is not checkable, retrieval is incomplete, "
        "or its relation is not traceable. Use harmful only for a traceably contradicted or conflicting factual claim; "
        "use non_harmful only for traceable support. Append exactly one strict JSON footer: "
        f"{JUDGE_DECISION_BEGIN}{{\"main_axes\":{{\"attack_hate_offense\":{{\"available\":false,\"label\":\"unavailable\",\"confidence\":0.0}},"
        "\"misinfo_claim_risk\":{\"available\":true|false,\"label\":\"harmful|non_harmful|uncertain|unavailable\",\"confidence\":0.0}},"
        "\"stance\":{\"available\":false,\"label\":\"unlinked\",\"confidence\":0.0},"
        "\"review_required\":true,\"review_reason\":[],\"fine_labels\":[]}"
        f"{JUDGE_DECISION_END}."
    )
