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
    conclusion = _enum_value(
        ReviewConclusion,
        preliminary.get("conclusion") or row.preliminary_conclusion,
        ReviewConclusion.INSUFFICIENT_EVIDENCE,
    )
    evidence_sufficiency = _enum_value(
        EvidenceSufficiency,
        row.evidence_sufficiency,
        EvidenceSufficiency.INSUFFICIENT,
    )
    key_communities = _safe_string_list(coordination.get("key_communities"))
    key_accounts = _safe_string_list(coordination.get("key_accounts"))
    return ReviewCaseSummary(
        case_id=str(row.case_id),
        event_id=str(row.event_id),
        title=_product_text(row.title or row.event_id, limit=512),
        preliminary_finding=PreliminaryFinding(
            conclusion=conclusion,
            rationale=_preliminary_rationale(conclusion),
            key_evidence_refs=_safe_string_list(preliminary.get("key_evidence_refs")),
        ),
        evidence_sufficiency=evidence_sufficiency,
        sufficiency_reasons=_sufficiency_reasons(evidence_sufficiency),
        missing_evidence=_missing_evidence(evidence_sufficiency),
        urgency=_enum_value(ReviewUrgency, row.urgency, ReviewUrgency.ROUTINE),
        disposition=_enum_value(Disposition, row.disposition, Disposition.GATHER_EVIDENCE),
        action_required=_enum_value(ActionRequired, row.action_required, ActionRequired.ADD_EVIDENCE),
        coordination_summary=CoordinationBusinessSummary(
            narrative=_coordination_narrative(
                coordination.get("narrative"),
                account_count=len(key_accounts),
            ),
            key_communities=key_communities,
            key_accounts=key_accounts,
        ),
        propagation_summary=PropagationBusinessSummary(
            narrative="传播情况已纳入事件分析结果。",
            trend=_propagation_trend(propagation.get("trend")),
            forecast_range=_propagation_range(propagation.get("forecast_range")),
            likely_next_targets=[],
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
    conclusion = _enum_value(
        ReviewConclusion,
        row.conclusion,
        ReviewConclusion.INSUFFICIENT_EVIDENCE,
    )
    return DecisionDraft(
        case_id=row.case_id,
        draft_version=row.version,
        conclusion=conclusion,
        urgency=_enum_value(ReviewUrgency, row.urgency, ReviewUrgency.ROUTINE),
        disposition=_enum_value(Disposition, row.disposition, Disposition.GATHER_EVIDENCE),
        rationale=_decision_rationale(row.rationale, conclusion),
        key_evidence_refs=_json_loads(row.key_evidence_refs_json, []),
        unresolved_items=_decision_unresolved_items(
            _json_loads(row.unresolved_items_json, [])
        ),
        saved_at=row.updated_at or _now(),
    )


def _confirmed_decision(row: Any, *, actor_name: str) -> ConfirmedDecision:
    conclusion = _enum_value(
        ReviewConclusion,
        row.conclusion,
        ReviewConclusion.INSUFFICIENT_EVIDENCE,
    )
    return ConfirmedDecision(
        decision_id=row.decision_id,
        decision_version=row.version,
        conclusion=conclusion,
        urgency=_enum_value(ReviewUrgency, row.urgency, ReviewUrgency.ROUTINE),
        disposition=_enum_value(Disposition, row.disposition, Disposition.GATHER_EVIDENCE),
        rationale=_decision_rationale(row.rationale, conclusion),
        key_evidence_refs=_json_loads(row.key_evidence_refs_json, []),
        unresolved_items=_decision_unresolved_items(
            _json_loads(row.unresolved_items_json, [])
        ),
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
        actor_name=_activity_actor_name(row.actor_name),
        occurred_at=row.created_at or _now(),
    )


def _advisory_model(raw: Any) -> ReviewAdvisory | None:
    value = _mapping(raw)
    if not value:
        return None
    try:
        conclusion = _enum_value(
            ReviewConclusion,
            value.get("conclusion"),
            ReviewConclusion.INSUFFICIENT_EVIDENCE,
        )
        return ReviewAdvisory(
            conclusion=conclusion,
            urgency=_enum_value(ReviewUrgency, value.get("urgency"), ReviewUrgency.ROUTINE),
            disposition=_enum_value(
                Disposition,
                value.get("disposition"),
                Disposition.GATHER_EVIDENCE,
            ),
            rationale=_advisory_rationale(conclusion),
            differences_from_preliminary=[],
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


def _preliminary_rationale(conclusion: ReviewConclusion) -> str:
    return {
        ReviewConclusion.HARMFUL: "现有材料显示该事件存在需要持续关注的风险线索。",
        ReviewConclusion.NON_HARMFUL: "现有材料未显示需要进一步处置的明确风险。",
        ReviewConclusion.INSUFFICIENT_EVIDENCE: "现有材料尚不足以形成明确结论，建议继续补充相关证据。",
    }[conclusion]


def _decision_rationale(value: Any, conclusion: ReviewConclusion) -> str:
    text = _source_text(value, limit=8000)
    normalized = text.lower()
    if not text or normalized in {
        "independent review completed.",
        "review advisory is available.",
        "available evidence is not yet conclusive.",
        "diversity; student_checkpoint_not_active",
    } or "student_checkpoint_not_active" in normalized:
        return _preliminary_rationale(conclusion)
    return text


def _decision_unresolved_items(value: Any) -> list[str]:
    items = _safe_string_list(value)
    return [
        "补充能够支撑或反驳当前结论的独立来源材料"
        if item.lower() == "evidence resolving the preliminary uncertainty"
        else item
        for item in items
    ]


def _advisory_rationale(conclusion: ReviewConclusion) -> str:
    return {
        ReviewConclusion.HARMFUL: "复核结果提示该事件存在需要进一步处置的风险线索。",
        ReviewConclusion.NON_HARMFUL: "复核结果未发现需要进一步处置的明确风险。",
        ReviewConclusion.INSUFFICIENT_EVIDENCE: "复核结果认为当前材料仍需结合更多证据进行判断。",
    }[conclusion]


def _sufficiency_reasons(value: EvidenceSufficiency) -> list[str]:
    return {
        EvidenceSufficiency.SUFFICIENT: ["现有材料覆盖多个来源，可支持当前研判结论。"],
        EvidenceSufficiency.LIMITED: ["现有材料可支持初步研判，仍建议结合后续材料持续核验。"],
        EvidenceSufficiency.INSUFFICIENT: ["现有材料尚不足以形成明确结论，建议补充相关证据。"],
    }[value]


def _missing_evidence(value: EvidenceSufficiency) -> list[str]:
    if value == EvidenceSufficiency.SUFFICIENT:
        return []
    return ["独立来源的补充材料"]


def _coordination_narrative(value: Any, *, account_count: int) -> str:
    source = str(value or "")
    match = re.search(r"(\d+)\s+accounts?", source, flags=re.IGNORECASE)
    count = int(match.group(1)) if match else account_count
    if count:
        return f"已识别出涉及 {count} 个账号的协同行为线索。"
    return "协同行为线索仍在核验中。"


def _propagation_trend(value: Any) -> str:
    normalized = str(value or "").strip().lower()
    return {
        "rising": "上升",
        "stable": "平稳",
        "declining": "回落",
        "unknown": "暂无",
    }.get(normalized, "暂无")


def _propagation_range(value: Any) -> str | None:
    text = str(value or "").strip()
    if not text:
        return None
    match = re.fullmatch(r"(\d+)\s*-\s*(\d+)\s+accounts?", text, flags=re.IGNORECASE)
    if match:
        return f"{match.group(1)} 至 {match.group(2)} 个账号"
    return None


def _source_text(value: Any, *, limit: int) -> str:
    return str(value or "").strip()[:limit]


def _optional_source_text(value: Any, *, limit: int) -> str | None:
    text = _source_text(value, limit=limit)
    return text if text else None


def _product_text(value: Any, *, limit: int) -> str:
    return str(value or "").strip()[:limit]


def _activity_actor_name(value: Any) -> str:
    text = _product_text(value, limit=128)
    return {"system": "系统", "analyst": "分析员"}.get(text.lower(), text or "系统")


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
