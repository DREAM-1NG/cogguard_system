"""MARO-compatible interpersonal-harm analysis for offline HateCoT studies.

This adapter transfers only MARO's role-specialization, reflection, and
separate-rule-Judge mechanics. It does not treat hate/offensive language as a
fact-checking problem and therefore never invokes claim retrieval or Exa.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
import json
from typing import Any, Mapping, Protocol

from app.core.review.evidence_contracts import PolicyBundle, RationaleCapsule, rationale_quality_gate
from app.core.review.governance_reference import load_governance_reference_library


MARO_HARM_PROTOCOL_VERSION = "maro-hatecot-harm-adapter-v1"
MARO_HARM_POST_AGENT = "PostHarmAgent"
MARO_HARM_REFLECTION_AGENT = "QuestionReflectionAgent"
MARO_HARM_ROLE_ORDER = (
    MARO_HARM_POST_AGENT,
    MARO_HARM_REFLECTION_AGENT,
    MARO_HARM_POST_AGENT,
)
HARM_ANALYSIS_BEGIN = "<HARM_ANALYSIS>"
HARM_ANALYSIS_END = "</HARM_ANALYSIS>"
HARM_REFLECTION_BEGIN = "<HARM_REFLECTION>"
HARM_REFLECTION_END = "</HARM_REFLECTION>"

__all__ = [
    "HARM_ANALYSIS_BEGIN",
    "HARM_ANALYSIS_END",
    "HARM_REFLECTION_BEGIN",
    "HARM_REFLECTION_END",
    "MARO_HARM_POST_AGENT",
    "MARO_HARM_PROTOCOL_VERSION",
    "MARO_HARM_REFLECTION_AGENT",
    "MARO_HARM_ROLE_ORDER",
    "format_harm_analysis_report",
    "has_complete_harm_analysis",
    "parse_harm_analysis",
    "parse_harm_reflection",
    "run_maro_harm_multiagent_analysis",
    "select_harm_policy_references",
]


class HarmAnalysisProvider(Protocol):
    """Provider shape shared by the offline DeepSeek experiment adapters."""

    async def __call__(
        self,
        *,
        agent_name: str,
        system_prompt: str,
        user_prompt: str,
        input_bundle: dict[str, Any],
        model: str,
    ) -> str: ...


@dataclass(frozen=True)
class HarmPolicySelection:
    """Advisory public-governance references selected for one text input."""

    policy_version: str
    bundles: tuple[PolicyBundle, ...]
    references: tuple[dict[str, Any], ...]


async def run_maro_harm_multiagent_analysis(
    *,
    case: Mapping[str, Any],
    provider: HarmAnalysisProvider,
    model: str,
    include_reflection: bool = True,
    include_policy_context: bool = True,
) -> dict[str, Any]:
    """Run text-only harm analysis before a separate INS-style Judge call.

    Gold labels and HateCoT explanations are intentionally absent from every
    provider input. The policy references constrain analytical vocabulary but
    never supply a class label or an enforcement decision.
    """

    post_text = str(case.get("text") or "").strip()
    if not post_text:
        raise ValueError("MARO harm analysis requires non-empty text")
    selection = select_harm_policy_references(post_text) if include_policy_context else HarmPolicySelection(
        policy_version="disabled",
        bundles=(),
        references=(),
    )
    reports: list[dict[str, Any]] = []

    initial = await _call_role(
        provider,
        agent_name=MARO_HARM_POST_AGENT,
        role="initial_harm_analysis",
        system_prompt=_post_harm_system_prompt(),
        input_bundle={
            "post_text": post_text,
            "policy_bundles": [bundle.to_dict() for bundle in selection.bundles],
            "policy_context_mode": "local_advisory" if include_policy_context else "off",
            "policy_boundary": _policy_boundary(),
        },
        model=model,
    )
    reports.append(initial)
    initial_text, initial_sidecar, initial_parse_error = parse_harm_analysis(
        initial["report_text"],
        post_text=post_text,
    )
    initial["report_text"] = initial_text
    initial["structured_sidecar"] = {
        "harm_analysis": initial_sidecar,
        "parse_error": initial_parse_error,
    }

    final_text = initial_text
    final_sidecar = initial_sidecar
    final_parse_error = initial_parse_error
    if include_reflection:
        reflection = await _call_role(
            provider,
            agent_name=MARO_HARM_REFLECTION_AGENT,
            role="harm_analysis_reflection",
            system_prompt=_reflection_system_prompt(),
            input_bundle={
                "post_text": post_text,
                "initial_harm_analysis": initial_text,
                "policy_bundles": [bundle.to_dict() for bundle in selection.bundles],
                "policy_context_mode": "local_advisory" if include_policy_context else "off",
                "policy_boundary": _policy_boundary(),
            },
            model=model,
        )
        reports.append(reflection)
        reflection_text, reflection_questions, reflection_error = parse_harm_reflection(
            reflection["report_text"]
        )
        reflection["report_text"] = reflection_text
        reflection["structured_sidecar"] = {
            "questions": reflection_questions,
            "parse_error": reflection_error,
        }

        refinement = await _call_role(
            provider,
            agent_name=MARO_HARM_POST_AGENT,
            role="reflection_response",
            system_prompt=_post_harm_refinement_system_prompt(),
            input_bundle={
                "post_text": post_text,
                "initial_harm_analysis": initial_text,
                "reflection_questions": reflection_questions,
                "policy_bundles": [bundle.to_dict() for bundle in selection.bundles],
                "policy_context_mode": "local_advisory" if include_policy_context else "off",
                "policy_boundary": _policy_boundary(),
            },
            model=model,
        )
        reports.append(refinement)
        final_text, final_sidecar, final_parse_error = parse_harm_analysis(
            refinement["report_text"],
            post_text=post_text,
        )
        refinement["report_text"] = final_text
        refinement["structured_sidecar"] = {
            "harm_analysis": final_sidecar,
            "parse_error": final_parse_error,
        }

    capsule, capsule_blockers = _build_rationale_capsule(
        analysis=final_text,
        sidecar=final_sidecar,
        policy_bundles=selection.bundles,
        require_policy=include_policy_context,
    )
    completed = sum(report["status"] == "completed" for report in reports)
    return {
        "schema_version": MARO_HARM_PROTOCOL_VERSION,
        "review_task": "interpersonal_harm",
        "case_id": str(case.get("case_id") or ""),
        "agent_reports": reports,
        "policy_selection": {
            "policy_version": selection.policy_version,
            "bundles": [bundle.to_dict() for bundle in selection.bundles],
            "references": list(selection.references),
            "source": "local_public_governance_reference_library",
            "external_retrieval_used": False,
            "context_mode": "local_advisory" if include_policy_context else "off",
            "usage_boundary": _policy_boundary(),
        },
        "rationale_capsule": capsule.to_dict(),
        "rationale_capsule_blockers": capsule_blockers,
        "analysis": format_harm_analysis_report(
            initial_analysis=initial_text,
            final_analysis=final_text,
            policy_bundles=selection.bundles,
        ),
        "summary": {
            "requested_agents": len(reports),
            "completed": completed,
            "include_reflection": include_reflection,
            "include_policy_context": include_policy_context,
            "analysis_parse_error": final_parse_error,
        },
        "audit": {
            "gold_label_sent_to_agent": False,
            "dataset_explanation_sent_to_agent": False,
            "external_fact_retrieval_used": False,
            "policy_is_advisory_not_label_source": True,
            "policy_context_mode": "local_advisory" if include_policy_context else "off",
        },
    }


def select_harm_policy_references(post_text: str) -> HarmPolicySelection:
    """Select fixed public governance references without pretending to fact-check."""

    library = load_governance_reference_library()
    categories = {
        str(item.get("category_id") or ""): item
        for item in library.get("governance_categories") or []
        if isinstance(item, Mapping)
    }
    references = {
        str(item.get("ref_id") or ""): item
        for item in library.get("platform_references") or []
        if isinstance(item, Mapping)
    }
    text = post_text.lower()
    selected_ids = [
        category_id
        for category_id in ("hate_harassment", "cyberbullying_attack")
        if _category_matches(categories.get(category_id, {}), text)
    ]
    if not selected_ids:
        selected_ids = ["hate_harassment"]

    version = "{}@{}".format(
        str(library.get("schema_version") or "unknown"),
        str(library.get("updated_at") or "unknown"),
    )
    bundles: list[PolicyBundle] = []
    selected_references: list[dict[str, Any]] = []
    seen_reference_ids: set[str] = set()
    for category_id in selected_ids:
        category = categories.get(category_id) or {}
        reference_ids = [str(value) for value in category.get("reference_refs") or []]
        resolved = [references[item] for item in reference_ids if item in references]
        for reference in resolved:
            reference_id = str(reference.get("ref_id") or "")
            if reference_id and reference_id not in seen_reference_ids:
                selected_references.append(_compact_reference(reference))
                seen_reference_ids.add(reference_id)
        bundles.append(
            PolicyBundle(
                policy_version=version,
                clause_id=category_id,
                applicability=str(category.get("name") or category_id),
                allowed_actions=tuple(str(item) for item in category.get("default_actions") or []),
                prohibited_actions=("automatic_enforcement", "policy_as_label_proxy"),
                matched_terms=tuple(_matched_terms(category, text)),
                effective=True,
                source_ref=str((resolved[0] if resolved else {}).get("url") or ""),
            )
        )
    return HarmPolicySelection(
        policy_version=version,
        bundles=tuple(bundle for bundle in bundles if bundle.usable),
        references=tuple(selected_references),
    )


def parse_harm_analysis(
    report_text: str,
    *,
    post_text: str,
) -> tuple[str, dict[str, Any], str | None]:
    """Parse and verify an input-span sidecar from the PostHarmAgent."""

    text, payload, error = _parse_footer(
        report_text,
        begin=HARM_ANALYSIS_BEGIN,
        end=HARM_ANALYSIS_END,
    )
    if error is not None:
        return text, _empty_harm_analysis(), error
    observed_spans = _verified_input_spans(payload.get("observed_spans"), post_text)
    summary = str(payload.get("summary") or "").strip()[:500]
    if not summary:
        return text, _empty_harm_analysis(), "missing_harm_summary"
    return text or summary, {
        "summary": summary,
        "observed_spans": observed_spans,
        "target_scope": str(payload.get("target_scope") or "unspecified").strip()[:120],
        "harm_cues": _string_list(payload.get("harm_cues"), limit=6),
        "counter_context": _string_list(payload.get("counter_context"), limit=4),
    }, None


def parse_harm_reflection(report_text: str) -> tuple[str, list[str], str | None]:
    """Parse at most two targeted questions for the one available expert."""

    text, payload, error = _parse_footer(
        report_text,
        begin=HARM_REFLECTION_BEGIN,
        end=HARM_REFLECTION_END,
    )
    if error is not None:
        return text, [], error
    questions = _string_list(payload.get("questions"), limit=2)
    return text, questions, None


def has_complete_harm_analysis(record: Mapping[str, Any] | None) -> bool:
    """Return whether every requested harm-analysis role completed."""

    if not isinstance(record, Mapping):
        return False
    summary = record.get("analysis_summary") if isinstance(record.get("analysis_summary"), Mapping) else record.get("summary")
    summary = summary if isinstance(summary, Mapping) else {}
    reports = record.get("agent_reports") if isinstance(record.get("agent_reports"), list) else []
    requested = int(summary.get("requested_agents") or 0)
    completed = int(summary.get("completed") or 0)
    if not (requested > 0 and completed == requested and all(
        isinstance(report, Mapping) and report.get("status") == "completed"
        for report in reports
    )):
        return False
    # A free-text response is not a complete research artifact. The PostHarm
    # analysis and its reflection response both need their verified sidecars
    # before they may enter an audit cache or a later Student-silver pipeline.
    for report in reports:
        if not isinstance(report, Mapping):
            return False
        if report.get("agent_name") not in {MARO_HARM_POST_AGENT, MARO_HARM_REFLECTION_AGENT}:
            continue
        sidecar = report.get("structured_sidecar")
        if not isinstance(sidecar, Mapping) or sidecar.get("parse_error") is not None:
            return False
    return True


def format_harm_analysis_report(
    *,
    initial_analysis: str,
    final_analysis: str,
    policy_bundles: tuple[PolicyBundle, ...],
) -> str:
    """Create the compact analysis passed to the independent rule Judge."""

    policy_text = "\n".join(
        "- {} [{}]: {}".format(bundle.clause_id, bundle.policy_version, bundle.applicability)
        for bundle in policy_bundles
    )
    report = (
        "[POST_HARM_INITIAL]\n"
        + initial_analysis[:4000]
        + "\n\n[POST_HARM_REFINEMENT]\n"
        + final_analysis[:4000]
    )
    if policy_text:
        report = (
            report[: report.index("\n\n[POST_HARM_REFINEMENT]")]
            + "\n\n[POLICY_REFERENCES_ADVISORY_ONLY]\n"
            + policy_text
            + report[report.index("\n\n[POST_HARM_REFINEMENT]"):]
        )
    return report


async def _call_role(
    provider: HarmAnalysisProvider,
    *,
    agent_name: str,
    role: str,
    system_prompt: str,
    input_bundle: dict[str, Any],
    model: str,
) -> dict[str, Any]:
    try:
        response = await provider(
            agent_name=agent_name,
            system_prompt=system_prompt,
            user_prompt=json.dumps(input_bundle, ensure_ascii=False),
            input_bundle=input_bundle,
            model=model,
        )
    except Exception as exc:
        return {
            "agent_name": agent_name,
            "report_role": role,
            "status": "failed",
            "report_text": "",
            "error_class": type(exc).__name__,
            "input_scope": sorted(input_bundle),
        }
    text = str(response or "").strip()
    return {
        "agent_name": agent_name,
        "report_role": role,
        "status": "completed" if text else "failed",
        "report_text": text,
        "input_scope": sorted(input_bundle),
    }


def _build_rationale_capsule(
    *,
    analysis: str,
    sidecar: Mapping[str, Any],
    policy_bundles: tuple[PolicyBundle, ...],
    require_policy: bool,
) -> tuple[RationaleCapsule, list[str]]:
    spans = tuple(str(item) for item in sidecar.get("observed_spans") or [] if str(item).strip())
    raw = RationaleCapsule(
        task="interpersonal_harm",
        capsule_text=str(sidecar.get("summary") or analysis or "").strip()[:500],
        input_spans=spans,
        policy_refs=tuple(bundle.clause_id for bundle in policy_bundles),
        citation_coverage=1.0 if spans else 0.0,
        source_traceability=bool(spans),
        policy_clause_match=bool(policy_bundles),
        rationale_span_available=bool(spans),
    )
    eligible, blockers = rationale_quality_gate(raw, requires_policy=require_policy)
    if not raw.rationale_span_available:
        blockers.append("missing_input_span")
        eligible = False
    return replace(raw, capsule_quality_gate=eligible), blockers


def _parse_footer(report_text: str, *, begin: str, end: str) -> tuple[str, dict[str, Any], str | None]:
    raw = str(report_text or "")
    start = raw.rfind(begin)
    stop = raw.rfind(end)
    if start < 0 or stop < start:
        return raw.strip(), {}, "missing_structured_footer"
    text = (raw[:start] + raw[stop + len(end):]).strip()
    try:
        payload = json.loads(raw[start + len(begin):stop].strip())
    except (TypeError, ValueError, json.JSONDecodeError):
        return text, {}, "invalid_structured_footer"
    if not isinstance(payload, dict):
        return text, {}, "invalid_structured_footer_schema"
    return text, payload, None


def _verified_input_spans(value: Any, post_text: str) -> list[str]:
    normalized_post = post_text.casefold()
    spans: list[str] = []
    for item in _string_list(value, limit=6):
        if item.casefold() not in normalized_post:
            continue
        if item not in spans:
            spans.append(item)
    return spans


def _string_list(value: Any, *, limit: int) -> list[str]:
    values = value if isinstance(value, list) else []
    items: list[str] = []
    for value in values:
        text = str(value or "").strip()
        if text and text not in items:
            items.append(text[:500])
        if len(items) >= limit:
            break
    return items


def _empty_harm_analysis() -> dict[str, Any]:
    return {
        "summary": "",
        "observed_spans": [],
        "target_scope": "unspecified",
        "harm_cues": [],
        "counter_context": [],
    }


def _category_matches(category: Mapping[str, Any], text: str) -> bool:
    return any(str(signal).lower() in text for signal in category.get("signals") or [] if str(signal))


def _matched_terms(category: Mapping[str, Any], text: str) -> list[str]:
    return [
        str(signal)
        for signal in category.get("signals") or []
        if str(signal) and str(signal).lower() in text
    ][:6]


def _compact_reference(reference: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "ref_id": reference.get("ref_id"),
        "platform": reference.get("platform"),
        "title": reference.get("title"),
        "url": reference.get("url"),
        "reference_type": reference.get("reference_type"),
    }


def _policy_boundary() -> dict[str, bool]:
    return {
        "advisory_only": True,
        "does_not_supply_dataset_label": True,
        "does_not_make_legal_conclusion": True,
        "does_not_trigger_automatic_enforcement": True,
    }


def _post_harm_system_prompt() -> str:
    return (
        "You are PostHarmAgent in an offline research evaluation. Analyze only the supplied post text for observable "
        "interpersonal harm: direct abuse, harassment, dehumanization, identity-targeting, and counter-context such "
        "as quotation, negation, or reclamation. Do not use external facts, infer author identity, issue an enforcement "
        "action, or output a class label. Policy references are advisory vocabulary only, never label evidence. "
        + _harm_analysis_footer_contract()
    )


def _reflection_system_prompt() -> str:
    return (
        "You are QuestionReflectionAgent for interpersonal-harm analysis. Inspect the supplied initial analysis for "
        "unsupported inference, missing target/context distinctions, or policy misuse. Ask no more than two questions "
        "that PostHarmAgent can answer from the same post. Do not provide a label or introduce external facts. End with "
        f"{HARM_REFLECTION_BEGIN}{{\"questions\":[\"up to two targeted questions\"]}}{HARM_REFLECTION_END}"
    )


def _post_harm_refinement_system_prompt() -> str:
    return (
        "You are PostHarmAgent responding to targeted reflection questions. Re-examine only the supplied post and initial "
        "analysis. Correct unsupported inferences, preserve uncertainty, and do not issue a final class label or enforcement "
        "recommendation. Write a short analysis paragraph before the footer. Do not echo the input JSON, field names, or "
        "reflection questions. "
        + _harm_analysis_footer_contract()
    )


def _harm_analysis_footer_contract() -> str:
    return (
        "End with exactly one JSON footer without Markdown: "
        f"{HARM_ANALYSIS_BEGIN}{{\"summary\":\"short analysis\",\"observed_spans\":[\"verbatim spans from post only\"],"
        "\"target_scope\":\"individual|identity_group|affiliation_group|unspecified\","
        "\"harm_cues\":[\"observable cues\"],\"counter_context\":[\"negation/quotation/reclamation if present\"]}"
        f"{HARM_ANALYSIS_END}"
    )
