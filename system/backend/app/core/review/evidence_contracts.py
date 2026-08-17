"""Typed evidence contracts shared by Review Teacher and Student pipelines.

These contracts keep factual evidence, governance policy, and rationale
supervision separate. They are intentionally serializable so existing Review
sidecars can adopt them without changing the product API.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, replace
from typing import Any, Literal, Mapping


ReviewTask = Literal["interpersonal_harm", "claim_deception"]
ClaimAssessment = Literal[
    "not_assessed",
    "checkable",
    "no_verifiable_claim",
    "extraction_failed",
]
RetrievalStatus = Literal[
    "not_attempted",
    "skipped_non_eligible_claim",
    "provider_unavailable",
    "provider_failed",
    "completed_no_relevant_evidence",
    "completed",
]
EvidenceRelation = Literal[
    "not_applicable",
    "supported",
    "contradicted",
    "insufficient",
    "conflicting",
]

_CLAIM_ASSESSMENTS = {
    "not_assessed",
    "checkable",
    "no_verifiable_claim",
    "extraction_failed",
}
_RETRIEVAL_STATUSES = {
    "not_attempted",
    "skipped_non_eligible_claim",
    "provider_unavailable",
    "provider_failed",
    "completed_no_relevant_evidence",
    "completed",
}
_EVIDENCE_RELATIONS = {
    "not_applicable",
    "supported",
    "contradicted",
    "insufficient",
    "conflicting",
}
_ASSERTABLE_RELATIONS = {"supported", "contradicted", "insufficient", "conflicting"}


def _clean_text(value: Any) -> str:
    return str(value or "").strip()


def _string_tuple(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()
    values = value if isinstance(value, (list, tuple, set)) else [value]
    return tuple(item for item in (_clean_text(item) for item in values) if item)


def _mapping_tuple(value: Any) -> tuple[dict[str, Any], ...]:
    if value is None:
        return ()
    values = value if isinstance(value, (list, tuple)) else [value]
    return tuple(dict(item) for item in values if isinstance(item, Mapping))


@dataclass(frozen=True)
class EvidenceBundle:
    """Traceable external evidence associated with one factual claim."""

    task: ReviewTask = "claim_deception"
    claim: str = ""
    claim_assessment: ClaimAssessment = "not_assessed"
    assessment_provenance: str = ""
    assessment_reason: str = ""
    query: str = ""
    source_refs: tuple[dict[str, Any], ...] = ()
    quoted_spans: tuple[str, ...] = ()
    relation: EvidenceRelation = "not_applicable"
    source_quality: str = "unknown"
    retrieval_status: RetrievalStatus = "not_attempted"
    retrieved_at: str | None = None
    missing_fields: tuple[str, ...] = ()

    @property
    def claim_eligible(self) -> bool:
        """Whether a structured claim may be used to form a factual query."""

        return self.claim_assessment == "checkable" and bool(self.claim)

    @property
    def retrieval_completed(self) -> bool:
        return self.retrieval_status == "completed"

    @property
    def has_traceable_evidence(self) -> bool:
        """Whether sources and quotations can be audited independently of the post."""

        return bool(self.source_refs and self.quoted_spans) and all(
            bool(_clean_text(ref.get("doc_id")) and _clean_text(ref.get("source")))
            and _clean_text(ref.get("source_origin")) != "review_input"
            for ref in self.source_refs
        )

    @property
    def relation_valid(self) -> bool:
        """Whether an evidence relation satisfies its factual-verification preconditions."""

        return bool(
            self.claim_eligible
            and self.retrieval_completed
            and self.has_traceable_evidence
            and self.relation in _ASSERTABLE_RELATIONS
        )

    @property
    def claim_risk_available(self) -> bool:
        """Whether a Judge may emit a factual claim-risk classification."""

        return self.relation_valid

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any] | None) -> "EvidenceBundle":
        raw = dict(value or {})
        assessment = _clean_text(raw.get("claim_assessment")).lower() or "not_assessed"
        if assessment not in _CLAIM_ASSESSMENTS:
            assessment = "extraction_failed"
        status = _clean_text(raw.get("retrieval_status")).lower() or "not_attempted"
        legacy_statuses = {
            "skipped_no_claim": "skipped_non_eligible_claim",
            "failed_no_provider": "provider_unavailable",
            "succeeded": "completed",
            "succeeded_no_match": "completed_no_relevant_evidence",
        }
        status = legacy_statuses.get(status, status)
        if status not in _RETRIEVAL_STATUSES:
            status = "not_attempted"
        relation = _clean_text(raw.get("relation")).lower() or "not_applicable"
        if relation not in _EVIDENCE_RELATIONS:
            relation = "not_applicable"
        bundle = cls(
            task="claim_deception",
            claim=_clean_text(raw.get("claim")),
            claim_assessment=assessment,  # type: ignore[arg-type]
            assessment_provenance=_clean_text(raw.get("assessment_provenance")),
            assessment_reason=_clean_text(raw.get("assessment_reason")),
            query=_clean_text(raw.get("query")),
            source_refs=_mapping_tuple(raw.get("source_refs") or raw.get("evidence")),
            quoted_spans=_string_tuple(raw.get("quoted_spans")),
            relation=relation,  # type: ignore[arg-type]
            source_quality=_clean_text(raw.get("source_quality")) or "unknown",
            retrieval_status=status,  # type: ignore[arg-type]
            retrieved_at=_clean_text(raw.get("retrieved_at")) or None,
            missing_fields=_string_tuple(raw.get("missing_fields")),
        )
        # Old sidecars used insufficient as a default. Preserve only relations
        # whose claim, retrieval, source and quotation preconditions are explicit.
        return bundle if bundle.relation == "not_applicable" or bundle.relation_valid else replace(
            bundle,
            relation="not_applicable",
        )


def initialize_claim_evidence_bundle(context: Mapping[str, Any]) -> EvidenceBundle:
    """Seed an evidence bundle only from an explicitly structured claim.

    A post body is review input, not a factual query. The ClaimEvidenceAgent may
    later assess it, but a missing structured field must remain ``not_assessed``.
    """

    existing = context.get("evidence_bundle")
    if isinstance(existing, Mapping):
        return EvidenceBundle.from_mapping(existing)

    claim, provenance = _first_structured_claim(context)
    if claim:
        return EvidenceBundle(
            claim=claim,
            claim_assessment="checkable",
            assessment_provenance=provenance,
            assessment_reason="explicit_structured_claim",
        )
    return EvidenceBundle(
        claim_assessment="not_assessed",
        assessment_provenance="review_input",
        assessment_reason="no_explicit_structured_claim",
    )


def apply_claim_assessment(
    bundle: EvidenceBundle,
    assessment: Mapping[str, Any] | None,
) -> EvidenceBundle:
    """Apply a validated ClaimEvidenceAgent assessment without inventing a relation."""

    raw = dict(assessment or {})
    status = _clean_text(raw.get("claim_assessment")).lower()
    if status not in _CLAIM_ASSESSMENTS:
        return replace(
            bundle,
            claim_assessment="extraction_failed",
            assessment_provenance="claim_evidence_agent",
            assessment_reason="invalid_claim_assessment_footer",
            relation="not_applicable",
        )

    claim = _clean_text(raw.get("claim"))
    if status == "checkable" and not claim:
        return replace(
            bundle,
            claim_assessment="extraction_failed",
            assessment_provenance="claim_evidence_agent",
            assessment_reason="checkable_claim_missing_text",
            relation="not_applicable",
        )

    updated = replace(
        bundle,
        claim=claim if status == "checkable" else "",
        claim_assessment=status,  # type: ignore[arg-type]
        assessment_provenance="claim_evidence_agent",
        assessment_reason=_clean_text(raw.get("assessment_reason")),
        relation="not_applicable",
    )
    if status != "checkable":
        return replace(updated, retrieval_status="skipped_non_eligible_claim")

    relation = _clean_text(raw.get("relation")).lower()
    source_ref_ids = set(_string_tuple(raw.get("source_ref_ids")))
    quoted_spans = _string_tuple(raw.get("quoted_spans"))
    if relation not in _ASSERTABLE_RELATIONS or not updated.retrieval_completed:
        return updated
    selected_refs = tuple(
        ref for ref in updated.source_refs if _clean_text(ref.get("doc_id")) in source_ref_ids
    )
    candidate = replace(
        updated,
        source_refs=selected_refs,
        quoted_spans=quoted_spans,
        relation=relation,  # type: ignore[arg-type]
    )
    return candidate if candidate.relation_valid else replace(candidate, relation="not_applicable")


def _first_structured_claim(context: Mapping[str, Any]) -> tuple[str, str]:
    for task in _as_mappings((context.get("review_queue") or {}).get("retrieval_tasks")):
        claim = _claim_text(task.get("claim") or task.get("claim_text"))
        if claim:
            return claim, "review_queue"
    for post in _as_mappings(context.get("selected_posts")):
        claim = _claim_text(post.get("primary_claim"))
        if claim:
            return claim, "post.primary_claim"
        for item in _as_sequence(post.get("claims")):
            claim = _claim_text(item)
            if claim:
                return claim, "post.claims"
    return "", ""


def _claim_text(value: Any) -> str:
    if isinstance(value, Mapping):
        return _clean_text(value.get("claim_text") or value.get("text") or value.get("claim"))
    return _clean_text(value)


def _as_mappings(value: Any) -> tuple[Mapping[str, Any], ...]:
    values = value if isinstance(value, (list, tuple)) else [value]
    return tuple(item for item in values if isinstance(item, Mapping))


def _as_sequence(value: Any) -> tuple[Any, ...]:
    if value is None:
        return ()
    return tuple(value) if isinstance(value, (list, tuple)) else (value,)


@dataclass(frozen=True)
class PolicyBundle:
    """A versioned policy clause that is advisory for analyst review."""

    policy_version: str = ""
    clause_id: str = ""
    applicability: str = ""
    allowed_actions: tuple[str, ...] = ()
    prohibited_actions: tuple[str, ...] = ()
    matched_terms: tuple[str, ...] = ()
    effective: bool = False
    source_ref: str = ""

    @property
    def usable(self) -> bool:
        return bool(self.policy_version and self.clause_id and self.effective)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any] | None) -> "PolicyBundle":
        raw = dict(value or {})
        return cls(
            policy_version=_clean_text(raw.get("policy_version") or raw.get("version")),
            clause_id=_clean_text(raw.get("clause_id")),
            applicability=_clean_text(raw.get("applicability")),
            allowed_actions=_string_tuple(raw.get("allowed_actions")),
            prohibited_actions=_string_tuple(raw.get("prohibited_actions")),
            matched_terms=_string_tuple(raw.get("matched_terms")),
            effective=bool(raw.get("effective")),
            source_ref=_clean_text(raw.get("source_ref") or raw.get("source_uri")),
        )


@dataclass(frozen=True)
class RationaleCapsule:
    """Short, source-bound rationale eligible for Student auxiliary training."""

    task: ReviewTask = "interpersonal_harm"
    capsule_text: str = ""
    input_spans: tuple[str, ...] = ()
    evidence_refs: tuple[str, ...] = ()
    policy_refs: tuple[str, ...] = ()
    citation_coverage: float = 0.0
    source_traceability: bool = False
    relation_validity: bool = False
    policy_clause_match: bool = False
    rationale_span_available: bool = False
    capsule_quality_gate: bool = False
    embedding: tuple[float, ...] = field(default_factory=tuple)

    @property
    def eligible(self) -> bool:
        return bool(self.capsule_quality_gate and self.capsule_text)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any] | None) -> "RationaleCapsule":
        raw = dict(value or {})
        try:
            coverage = max(0.0, min(1.0, float(raw.get("citation_coverage") or 0.0)))
        except (TypeError, ValueError):
            coverage = 0.0
        embedding = raw.get("embedding") or raw.get("capsule_embedding") or ()
        try:
            embedding_tuple = tuple(float(item) for item in embedding)
        except (TypeError, ValueError):
            embedding_tuple = ()
        task = _clean_text(raw.get("task")) or "interpersonal_harm"
        if task not in {"interpersonal_harm", "claim_deception"}:
            task = "interpersonal_harm"
        return cls(
            task=task,  # type: ignore[arg-type]
            capsule_text=_clean_text(raw.get("capsule_text") or raw.get("short_rationale")),
            input_spans=_string_tuple(raw.get("input_spans")),
            evidence_refs=_string_tuple(raw.get("evidence_refs")),
            policy_refs=_string_tuple(raw.get("policy_refs")),
            citation_coverage=coverage,
            source_traceability=bool(raw.get("source_traceability")),
            relation_validity=bool(raw.get("relation_validity")),
            policy_clause_match=bool(raw.get("policy_clause_match")),
            rationale_span_available=bool(raw.get("rationale_span_available")),
            capsule_quality_gate=bool(raw.get("capsule_quality_gate")),
            embedding=embedding_tuple,
        )


def rationale_quality_gate(
    capsule: RationaleCapsule,
    *,
    requires_evidence: bool = False,
    requires_policy: bool = False,
) -> tuple[bool, list[str]]:
    """Return eligibility and explicit blockers for Student supervision."""

    blockers: list[str] = []
    if not capsule.capsule_text:
        blockers.append("missing_capsule_text")
    if requires_evidence and not capsule.source_traceability:
        blockers.append("missing_source_traceability")
    if requires_evidence and not capsule.relation_validity:
        blockers.append("invalid_evidence_relation")
    if requires_policy and not capsule.policy_clause_match:
        blockers.append("missing_policy_clause_match")
    if requires_evidence and capsule.citation_coverage <= 0.0:
        blockers.append("missing_citation_coverage")
    return not blockers, blockers


__all__ = [
    "EvidenceBundle",
    "ClaimAssessment",
    "EvidenceRelation",
    "PolicyBundle",
    "RationaleCapsule",
    "RetrievalStatus",
    "ReviewTask",
    "apply_claim_assessment",
    "initialize_claim_evidence_bundle",
    "rationale_quality_gate",
]
