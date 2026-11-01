"""Pure projection helpers for automatic review case analysis."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from app.core.analysis import EventSnapshot, TimeWindow
from app.schemas.review_case import (
    ActionRequired,
    Disposition,
    EvidenceSufficiency,
    ReviewConclusion,
    ReviewUrgency,
)


@dataclass(frozen=True, slots=True)
class AnalysisProjection:
    conclusion: ReviewConclusion
    evidence_sufficiency: EvidenceSufficiency
    urgency: ReviewUrgency
    disposition: Disposition
    action_required: ActionRequired
    preliminary_finding: dict[str, Any]
    business_summary: dict[str, Any]


def derive_analysis_windows(
    *,
    posts: list[dict[str, Any]],
    comments: list[dict[str, Any]],
    crawl_job_id: int,
) -> tuple[TimeWindow, TimeWindow]:
    rows = [*posts, *comments]
    core_rows = [
        row for row in rows if int(row.get("crawl_job_id") or 0) == int(crawl_job_id)
    ]
    context_times = [
        timestamp for row in rows if (timestamp := _timestamp(row.get("timestamp")))
    ]
    core_times = [
        timestamp
        for row in core_rows
        if (timestamp := _timestamp(row.get("timestamp")))
    ]
    fallback_start = datetime(1970, 1, 1, tzinfo=timezone.utc)
    if not context_times:
        context_times = list(core_times) or [fallback_start]
    if not core_times:
        core_times = list(context_times)
    core_start, core_end = _window_bounds(core_times)
    context_start, context_end = _window_bounds([*context_times, core_start, core_end])
    return (
        TimeWindow(start=core_start, end=core_end),
        TimeWindow(start=context_start, end=context_end),
    )


def project_analysis_results(
    *,
    snapshot: EventSnapshot,
    results: dict[str, Any],
) -> AnalysisProjection:
    student = dict(results.get("student") or {})
    coordination = dict(results.get("coordination_discover") or {})
    propagation = dict(results.get("propagation_analysis") or {})
    conclusion = _review_conclusion(student)
    sufficiency = _evidence_sufficiency(snapshot, student)
    urgency = _review_urgency(student)
    disposition = _disposition(conclusion, urgency)
    action = (
        ActionRequired.ADD_EVIDENCE
        if sufficiency != EvidenceSufficiency.SUFFICIENT or bool(student.get("abstain"))
        else ActionRequired.CONFIRM_DECISION
    )
    evidence_refs = _student_evidence_refs(student)
    preliminary = {
        "conclusion": conclusion.value,
        "rationale": _student_rationale(student, conclusion),
        "key_evidence_refs": evidence_refs,
    }
    missing = _missing_evidence(snapshot, student)
    business = {
        "sufficiency_reasons": _sufficiency_reasons(snapshot, student),
        "missing_evidence": missing,
        "coordination": _coordination_summary(coordination),
        "propagation": _propagation_summary(propagation),
    }
    return AnalysisProjection(
        conclusion=conclusion,
        evidence_sufficiency=sufficiency,
        urgency=urgency,
        disposition=disposition,
        action_required=action,
        preliminary_finding=preliminary,
        business_summary=business,
    )


def teacher_routing_reasons(
    *,
    student: dict[str, Any],
    evidence_sufficiency: str,
    urgency: str,
    manual_request: bool = False,
) -> list[str]:
    reasons: list[str] = []
    if manual_request:
        reasons.append("manual_request")
    if str(student.get("status") or "") not in {"ok", "completed"}:
        reasons.append("student_unavailable")
    if bool(student.get("abstain")):
        reasons.append("student_abstained")
    if bool(student.get("review_required")):
        reasons.append("student_requested_review")
    if evidence_sufficiency in {"limited", "insufficient"}:
        reasons.append("evidence_not_sufficient")
    if bool(
        student.get("ood")
        or student.get("out_of_distribution")
        or student.get("domain_shift")
    ):
        reasons.append("distribution_shift")
    if urgency in {"urgent", "critical"}:
        reasons.append("high_urgency")
    return list(dict.fromkeys(reasons))


def _teacher_business_advisory(
    verdict: dict[str, Any], preliminary: str
) -> dict[str, Any]:
    raw = dict(verdict.get("advisory") or {})
    conclusion = _label_conclusion(
        raw.get("conclusion") or raw.get("decision") or verdict.get("label")
    )
    urgency = _review_urgency(verdict)
    disposition = _disposition(conclusion, urgency)
    differences = []
    if conclusion.value != str(preliminary):
        differences.append("The review advisory differs from the preliminary finding.")
    return {
        "conclusion": conclusion.value,
        "urgency": urgency.value,
        "disposition": disposition.value,
        "rationale": str(
            raw.get("rationale")
            or verdict.get("reason")
            or "Independent review completed."
        )[:8000],
        "differences_from_preliminary": differences,
        "key_evidence_refs": _student_evidence_refs(verdict),
        "received_at": _now().isoformat(),
    }


def _review_conclusion(student: dict[str, Any]) -> ReviewConclusion:
    if bool(student.get("abstain")) and not student.get("label"):
        return ReviewConclusion.INSUFFICIENT_EVIDENCE
    return _label_conclusion(student.get("label") or student.get("conclusion"))


def _label_conclusion(value: Any) -> ReviewConclusion:
    normalized = str(value or "").strip().lower()
    if normalized in {"harmful", "high", "malicious", "true"}:
        return ReviewConclusion.HARMFUL
    if normalized in {"non_harmful", "non-harmful", "harmless", "benign", "false"}:
        return ReviewConclusion.NON_HARMFUL
    return ReviewConclusion.INSUFFICIENT_EVIDENCE


def _evidence_sufficiency(
    snapshot: EventSnapshot,
    student: dict[str, Any],
) -> EvidenceSufficiency:
    if snapshot.quality_report.status == "reject" or str(student.get("status")) not in {
        "ok",
        "completed",
    }:
        return EvidenceSufficiency.INSUFFICIENT
    if snapshot.quality_report.status == "warn" or bool(student.get("abstain")):
        return EvidenceSufficiency.LIMITED
    return EvidenceSufficiency.SUFFICIENT


def _review_urgency(student: dict[str, Any]) -> ReviewUrgency:
    value = str(student.get("urgency") or student.get("risk_level") or "").lower()
    return {
        "critical": ReviewUrgency.CRITICAL,
        "high": ReviewUrgency.URGENT,
        "urgent": ReviewUrgency.URGENT,
        "medium": ReviewUrgency.WATCH,
        "watch": ReviewUrgency.WATCH,
    }.get(value, ReviewUrgency.ROUTINE)


def _disposition(conclusion: ReviewConclusion, urgency: ReviewUrgency) -> Disposition:
    if conclusion == ReviewConclusion.INSUFFICIENT_EVIDENCE:
        return Disposition.GATHER_EVIDENCE
    if conclusion == ReviewConclusion.NON_HARMFUL:
        return (
            Disposition.ARCHIVE
            if urgency == ReviewUrgency.ROUTINE
            else Disposition.MONITOR
        )
    return (
        Disposition.RESPOND
        if urgency == ReviewUrgency.CRITICAL
        else Disposition.ESCALATE
    )


def _student_rationale(student: dict[str, Any], conclusion: ReviewConclusion) -> str:
    reason = student.get("reason")
    if reason:
        return str(reason)[:8000]
    reasons = student.get("review_reason")
    if isinstance(reasons, list) and reasons:
        return "; ".join(str(item) for item in reasons)[:8000]
    return {
        ReviewConclusion.HARMFUL: "Available evidence supports a harmfulness finding.",
        ReviewConclusion.NON_HARMFUL: "Available evidence does not support a harmfulness finding.",
        ReviewConclusion.INSUFFICIENT_EVIDENCE: "Available evidence is not yet conclusive.",
    }[conclusion]


def _student_evidence_refs(result: dict[str, Any]) -> list[str]:
    refs = result.get("key_evidence_refs")
    if not isinstance(refs, list):
        refs = []
    return [str(item)[:512] for item in refs if str(item).strip()][:100]


def _coordination_summary(result: dict[str, Any]) -> dict[str, Any]:
    summary = dict(result.get("summary") or {})
    communities = result.get("community_lineage") or result.get("communities") or []
    accounts = result.get("account_risk_tiers") or []
    community_names = [
        str(row.get("community_id") or row.get("id"))
        for row in communities
        if isinstance(row, dict) and (row.get("community_id") or row.get("id"))
    ][:100]
    account_names = [
        str(row.get("account_label") or row.get("account_id"))
        for row in accounts
        if isinstance(row, dict) and (row.get("account_label") or row.get("account_id"))
    ][:100]
    count = int(summary.get("coordinated_accounts") or len(account_names) or 0)
    return {
        "narrative": f"Observed coordination evidence involves {count} accounts.",
        "key_communities": community_names,
        "key_accounts": account_names,
    }


def _propagation_summary(result: dict[str, Any]) -> dict[str, Any]:
    interval = result.get("scale_interval")
    forecast_range = None
    if isinstance(interval, (list, tuple)) and len(interval) >= 2:
        forecast_range = f"{interval[0]}-{interval[1]} accounts"
    ranking = result.get("next_hop_ranking") or []
    targets = [
        str(row.get("node_id") or row.get("account_id") or row.get("id"))
        for row in ranking
        if isinstance(row, dict)
        and (row.get("node_id") or row.get("account_id") or row.get("id"))
    ][:100]
    trend = str(result.get("trend") or result.get("trend_label") or "unknown")[:256]
    return {
        "narrative": "Propagation analysis summarizes the observed event trajectory.",
        "trend": trend,
        "forecast_range": forecast_range,
        "likely_next_targets": targets,
    }


def _sufficiency_reasons(snapshot: EventSnapshot, student: dict[str, Any]) -> list[str]:
    reasons = [str(item) for item in snapshot.quality_report.issues]
    if bool(student.get("abstain")):
        reasons.append("The preliminary finding deferred because uncertainty remains.")
    return reasons[:100]


def _missing_evidence(snapshot: EventSnapshot, student: dict[str, Any]) -> list[str]:
    missing: list[str] = []
    if snapshot.quality_report.missing_timestamps:
        missing.append("Content timestamps")
    if snapshot.quality_report.missing_authors:
        missing.append("Account attribution")
    if snapshot.quality_report.status != "pass":
        missing.append("Additional independent event evidence")
    if bool(student.get("abstain")):
        missing.append("Evidence resolving the preliminary uncertainty")
    return list(dict.fromkeys(missing))[:100]


def _empty_business_summary() -> dict[str, Any]:
    return {
        "sufficiency_reasons": [],
        "missing_evidence": [],
        "coordination": {
            "narrative": "Coordination analysis is pending.",
            "key_communities": [],
            "key_accounts": [],
        },
        "propagation": {
            "narrative": "Propagation analysis is pending.",
            "trend": "unknown",
            "forecast_range": None,
            "likely_next_targets": [],
        },
    }


def _window_bounds(values: list[datetime]) -> tuple[datetime, datetime]:
    start = min(values)
    end = max(values) + timedelta(microseconds=1)
    if start >= end:
        end = start + timedelta(seconds=1)
    return start, end


def _timestamp(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return (
            value.replace(tzinfo=timezone.utc)
            if value.tzinfo is None
            else value.astimezone(timezone.utc)
        )
    if isinstance(value, (int, float)):
        seconds = float(value) / 1000 if float(value) > 10_000_000_000 else float(value)
        try:
            return datetime.fromtimestamp(seconds, tz=timezone.utc)
        except (OverflowError, OSError, ValueError):
            return None
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    return (
        parsed.replace(tzinfo=timezone.utc)
        if parsed.tzinfo is None
        else parsed.astimezone(timezone.utc)
    )


def _json_dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)


def _json_loads(value: str | None, default: Any) -> Any:
    try:
        return json.loads(value) if value else default
    except (TypeError, json.JSONDecodeError):
        return default


def _now() -> datetime:
    return datetime.now(timezone.utc)


__all__ = [
    "AnalysisProjection",
    "derive_analysis_windows",
    "project_analysis_results",
    "teacher_routing_reasons",
]
