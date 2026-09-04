"""Product-safe projections for event review cases."""

from __future__ import annotations

import json
import re
from collections.abc import Iterable
from datetime import datetime, timezone
from typing import Any

from app.schemas.review_case import (
    ActionRequired,
    CaseActivity,
    CaseActivityType,
    ConfirmedDecision,
    CoordinationBusinessSummary,
    DecisionDraft,
    Disposition,
    EvidenceAnnotation,
    EvidenceAssessment,
    EvidenceItem,
    EvidenceSufficiency,
    PreliminaryFinding,
    PropagationBusinessSummary,
    ReviewAdvisory,
    ReviewCaseSummary,
    ReviewConclusion,
    ReviewUrgency,
)


def build_case_summary(row: Any) -> ReviewCaseSummary:
    """Project an internal case record through an explicit business whitelist."""

    preliminary = _json_loads(getattr(row, "preliminary_finding_json", "{}"), {})
    business = _json_loads(getattr(row, "business_summary_json", "{}"), {})
    coordination = _mapping(business.get("coordination"))
    propagation = _mapping(business.get("propagation"))
    return ReviewCaseSummary(
        case_id=str(row.case_id),
        event_id=str(row.event_id),
        title=_product_text(row.title or row.event_id, limit=512),
        preliminary_finding=PreliminaryFinding(
            conclusion=_enum_value(
                ReviewConclusion,
                preliminary.get("conclusion") or row.preliminary_conclusion,
                ReviewConclusion.INSUFFICIENT_EVIDENCE,
            ),
            rationale=_product_text(
                preliminary.get("rationale") or "Available evidence is not yet conclusive.",
                limit=8000,
            ),
            key_evidence_refs=_safe_string_list(preliminary.get("key_evidence_refs")),
        ),
        evidence_sufficiency=_enum_value(
            EvidenceSufficiency,
            row.evidence_sufficiency,
            EvidenceSufficiency.INSUFFICIENT,
        ),
        sufficiency_reasons=_safe_string_list(business.get("sufficiency_reasons")),
        missing_evidence=_safe_string_list(business.get("missing_evidence")),
        urgency=_enum_value(ReviewUrgency, row.urgency, ReviewUrgency.ROUTINE),
        disposition=_enum_value(Disposition, row.disposition, Disposition.GATHER_EVIDENCE),
        action_required=_enum_value(ActionRequired, row.action_required, ActionRequired.ADD_EVIDENCE),
        coordination_summary=CoordinationBusinessSummary(
            narrative=_product_text(
                coordination.get("narrative") or "No coordination summary is available.",
                limit=8000,
            ),
            key_communities=_safe_string_list(coordination.get("key_communities")),
            key_accounts=_safe_string_list(coordination.get("key_accounts")),
        ),
        propagation_summary=PropagationBusinessSummary(
            narrative=_product_text(
                propagation.get("narrative") or "No propagation summary is available.",
                limit=8000,
            ),
            trend=_product_text(propagation.get("trend") or "unknown", limit=256),
            forecast_range=_optional_text(propagation.get("forecast_range"), limit=256),
            likely_next_targets=_safe_string_list(propagation.get("likely_next_targets")),
        ),
        updated_at=getattr(row, "updated_at", None) or _now(),
    )


def build_evidence_item(
    raw: dict[str, Any],
    *,
    evidence_kind: str,
    annotations: list[EvidenceAnnotation] | None = None,
) -> EvidenceItem:
    """Convert immutable snapshot content to the narrow analyst evidence view."""

    evidence_ref = _evidence_ref(raw, evidence_kind)
    content = _source_text(raw.get("content") or raw.get("text") or raw.get("title") or "", limit=8000)
    title = _source_text(raw.get("title") or content[:120] or evidence_ref, limit=512)
    annotation_rows = list(annotations or [])
    assessment = annotation_rows[-1].assessment if annotation_rows else EvidenceAssessment.UNRESOLVED
    return EvidenceItem(
        evidence_ref=evidence_ref,
        evidence_type=evidence_kind,
        assessment=assessment,
        title=title,
        excerpt=content[:8000],
        source_url=_optional_source_text(
            raw.get("url") or raw.get("detail_url") or raw.get("note_url"),
            limit=2048,
        ),
        platform=_optional_source_text(raw.get("platform"), limit=64),
        observed_at=raw.get("timestamp") or raw.get("publish_time") or raw.get("created_at"),
        annotations=annotation_rows,
    )


def _evidence_ref(raw: dict[str, Any], evidence_kind: str) -> str:
    platform = str(raw.get("platform") or "unknown")
    identifier = raw.get("post_id") if evidence_kind == "post" else raw.get("comment_id")
    identifier = identifier or raw.get("id") or "missing-id"
    return f"{platform}:{evidence_kind}:{identifier}"


def _annotation_model(row: Any, *, actor_name: str) -> EvidenceAnnotation:
    return EvidenceAnnotation(
        annotation_id=row.annotation_id,
        evidence_ref=row.evidence_ref,
        assessment=_enum_value(
            EvidenceAssessment,
            row.assessment,
            EvidenceAssessment.UNRESOLVED,
        ),
        note=_product_text(row.note, limit=4000),
        source_url=row.source_url,
        created_by_name=actor_name,
        created_at=row.created_at or _now(),
    )


def _draft_model(row: Any) -> DecisionDraft:
    return DecisionDraft(
        case_id=row.case_id,
        draft_version=row.version,
        conclusion=_enum_value(
            ReviewConclusion,
            row.conclusion,
            ReviewConclusion.INSUFFICIENT_EVIDENCE,
        ),
        urgency=_enum_value(ReviewUrgency, row.urgency, ReviewUrgency.ROUTINE),
        disposition=_enum_value(Disposition, row.disposition, Disposition.GATHER_EVIDENCE),
        rationale=_product_text(row.rationale, limit=8000),
        key_evidence_refs=_json_loads(row.key_evidence_refs_json, []),
        unresolved_items=_json_loads(row.unresolved_items_json, []),
        saved_at=row.updated_at or _now(),
    )


def _confirmed_decision(row: Any, *, actor_name: str) -> ConfirmedDecision:
    return ConfirmedDecision(
        decision_id=row.decision_id,
        decision_version=row.version,
        conclusion=_enum_value(
            ReviewConclusion,
            row.conclusion,
            ReviewConclusion.INSUFFICIENT_EVIDENCE,
        ),
        urgency=_enum_value(ReviewUrgency, row.urgency, ReviewUrgency.ROUTINE),
        disposition=_enum_value(Disposition, row.disposition, Disposition.GATHER_EVIDENCE),
        rationale=_product_text(row.rationale, limit=8000),
        key_evidence_refs=_json_loads(row.key_evidence_refs_json, []),
        unresolved_items=_json_loads(row.unresolved_items_json, []),
        confirmed_by_name=actor_name,
        confirmed_at=row.confirmed_at or _now(),
    )


def _activity_model(row: Any) -> CaseActivity:
    return CaseActivity(
        cursor=row.id,
        case_id=row.case_id,
        activity_type=_enum_value(
            CaseActivityType,
            row.activity_type,
            CaseActivityType.CASE_CREATED,
        ),
        action_required=_enum_value(
            ActionRequired,
            row.action_required,
            ActionRequired.NONE,
        ),
        summary=_product_text(row.summary, limit=1000),
        detail_lines=_safe_string_list(_json_loads(row.detail_lines_json, [])),
        evidence_refs=_json_loads(row.evidence_refs_json, []),
        actor_name=_product_text(row.actor_name or "System", limit=128),
        occurred_at=row.created_at or _now(),
    )


def _advisory_model(raw: Any) -> ReviewAdvisory | None:
    value = _mapping(raw)
    if not value:
        return None
    try:
        return ReviewAdvisory(
            conclusion=_enum_value(
                ReviewConclusion,
                value.get("conclusion"),
                ReviewConclusion.INSUFFICIENT_EVIDENCE,
            ),
            urgency=_enum_value(ReviewUrgency, value.get("urgency"), ReviewUrgency.ROUTINE),
            disposition=_enum_value(
                Disposition,
                value.get("disposition"),
                Disposition.GATHER_EVIDENCE,
            ),
            rationale=_product_text(value.get("rationale") or "Review advisory is available.", limit=8000),
            differences_from_preliminary=_safe_string_list(
                value.get("differences_from_preliminary")
            ),
            key_evidence_refs=_safe_string_list(value.get("key_evidence_refs")),
            received_at=value.get("received_at") or _now(),
        )
    except (TypeError, ValueError):
        return None


def _enum_value(enum_type: Any, value: Any, default: Any) -> Any:
    try:
        return enum_type(str(value))
    except (TypeError, ValueError):
        return default


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _safe_string_list(value: Any) -> list[str]:
    if isinstance(value, str):
        source: Iterable[Any] = [value]
    elif isinstance(value, Iterable) and not isinstance(value, (dict, bytes)):
        source = value
    else:
        return []
    result: list[str] = []
    for item in source:
        text = _product_text(item, limit=1000)
        if text and text not in result:
            result.append(text[:1000])
        if len(result) >= 100:
            break
    return result


def _optional_text(value: Any, *, limit: int) -> str | None:
    text = _product_text(value, limit=limit)
    return text[:limit] if text else None


def _source_text(value: Any, *, limit: int) -> str:
    return str(value or "").strip()[:limit]


def _optional_source_text(value: Any, *, limit: int) -> str | None:
    text = _source_text(value, limit=limit)
    return text if text else None


_FORBIDDEN_PRODUCT_PATTERNS = (
    re.compile(
        r"\b(?:raw[_ -]?confidence|runtime[_ -]?(?:status|state)|artifact(?:[_ -]?(?:uri|hash))?|"
        r"checkpoint(?:[_ -]?(?:uri|path))?|model[_ -]?version|run[_ -]?id|job[_ -]?id|task[_ -]?id|"
        r"(?:student|teacher)[_ -]?agent|agent|student|teacher|model|run|job|task)"
        r"\s*[:=]\s*[^\s,;]+",
        re.IGNORECASE,
    ),
    re.compile(r"\braw[_ -]?confidence\b", re.IGNORECASE),
    re.compile(r"\bruntime[_ -]?(?:status|state)\b", re.IGNORECASE),
    re.compile(r"\bartifact(?:[_ -]?(?:uri|hash))?\b", re.IGNORECASE),
    re.compile(r"\bcheckpoint(?:[_ -]?(?:uri|path))?\b", re.IGNORECASE),
    re.compile(r"\bmodel[_ -]?version\b", re.IGNORECASE),
    re.compile(r"\b(?:run|job|task)[_ -]?id\b", re.IGNORECASE),
    re.compile(r"\b(?:student|teacher)[_ -]?agent\b", re.IGNORECASE),
    re.compile(r"\braw confidence\b", re.IGNORECASE),
    re.compile(r"\bruntime state\b", re.IGNORECASE),
    re.compile(r"\b(agent|student|teacher|model|checkpoint|artifact|run|job|task)\b", re.IGNORECASE),
)


def _product_text(value: Any, *, limit: int) -> str:
    text = str(value or "").strip()
    for pattern in _FORBIDDEN_PRODUCT_PATTERNS:
        text = pattern.sub("internal review", text)
    return text[:limit]


def _json_loads(value: str | None, default: Any) -> Any:
    try:
        return json.loads(value) if value else default
    except (TypeError, json.JSONDecodeError):
        return default


def _now() -> datetime:
    return datetime.now(timezone.utc)


__all__ = [
    "build_case_summary",
    "build_evidence_item",
]
