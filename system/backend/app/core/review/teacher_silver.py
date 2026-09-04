"""Teacher Silver supervision contract for Review Student distillation."""

from __future__ import annotations

from typing import Any

from app.core.review.trainable_post import (
    ATTACK_AXIS,
    MISINFO_AXIS,
    TEACHER_SILVER_SCHEMA,
    axis_supports_case,
    claim_context_text,
    stance_proxy_of,
    teacher_axis_confidence,
    teacher_axis_label,
)

__all__ = [
    "build_teacher_silver_record",
    "load_teacher_silver_index",
]


def _dedupe_strings(values: list[str]) -> list[str]:
    seen: set[str] = set()
    deduped: list[str] = []
    for value in values:
        if value is None:
            continue
        item = str(value).strip()
        if not item or item in seen:
            continue
        seen.add(item)
        deduped.append(item)
    return deduped


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def build_teacher_silver_record(
    case: dict[str, Any],
    review_result: dict[str, Any] | None = None,
) -> dict[str, Any]:
    review_result = review_result or {}
    summary = review_result.get("summary") or {}
    audit = review_result.get("audit") or {}
    agent_reports = [item for item in review_result.get("agent_reports") or [] if isinstance(item, dict)]
    judge_report = next(
        (item for item in agent_reports if item.get("agent_name") == "HarmfulnessJudgeAgent"),
        {},
    )
    judge_sidecar = judge_report.get("structured_sidecar") or {}
    selected_posts = _as_list((review_result.get("input_bundle") or {}).get("selected_posts"))
    teacher_confidence = judge_sidecar.get("confidence")
    axis_confidence = teacher_axis_confidence(case, ATTACK_AXIS, teacher_confidence=teacher_confidence)
    misinfo_confidence = teacher_axis_confidence(case, MISINFO_AXIS, teacher_confidence=teacher_confidence)
    main_axes = {
        ATTACK_AXIS: {
            "available": axis_supports_case(case, ATTACK_AXIS),
            "label": "harmful"
            if teacher_axis_label(case, ATTACK_AXIS) == 1
            else "non_harmful"
            if axis_supports_case(case, ATTACK_AXIS)
            else "unavailable",
            "confidence": axis_confidence,
            "source": "teacher_silver" if axis_supports_case(case, ATTACK_AXIS) else "masked",
        },
        MISINFO_AXIS: {
            "available": axis_supports_case(case, MISINFO_AXIS),
            "label": "harmful"
            if teacher_axis_label(case, MISINFO_AXIS) == 1
            else "non_harmful"
            if axis_supports_case(case, MISINFO_AXIS)
            else "unavailable",
            "confidence": misinfo_confidence,
            "source": "teacher_silver" if axis_supports_case(case, MISINFO_AXIS) else "masked",
        },
    }
    fine_labels = _dedupe_strings(
        [
            *(str(item) for item in (case.get("labels") or {}).get("harm_type") or []),
            str((case.get("labels") or {}).get("raw_label") or ""),
            str((case.get("labels") or {}).get("veracity") or ""),
            str((case.get("labels") or {}).get("rumour_label") or ""),
            *(str(item) for item in (case.get("labels") or {}).get("target_groups") or []),
        ]
    )
    evidence_spans: list[str] = []
    for post in selected_posts[:3]:
        if isinstance(post, dict):
            for field in ("excerpt", "content", "claim_text", "evidence_text"):
                value = str(post.get(field) or "").strip()
                if value:
                    evidence_spans.append(value[:240])
    for ref in judge_sidecar.get("evidence_refs") or []:
        if isinstance(ref, dict):
            snippet = str(ref.get("text") or ref.get("snippet") or ref.get("title") or "").strip()
            if snippet:
                evidence_spans.append(snippet[:240])
    trace_refs: list[str] = []
    for item in agent_reports:
        review_id = str(item.get("review_id") or "").strip()
        if review_id:
            trace_refs.append(review_id)
        report_role = str(item.get("report_role") or "").strip()
        if report_role and review_id:
            trace_refs.append(f"{report_role}:{review_id}")
    for ref in judge_sidecar.get("debate_trace_refs") or []:
        if ref:
            trace_refs.append(str(ref))
    runtime_mode = str(summary.get("effective_runtime_mode") or audit.get("effective_runtime_mode") or "simple")
    review_required = bool(judge_sidecar.get("review_required")) or bool(audit.get("failure_mode_tags"))
    sample_mode = "hard_case" if (
        runtime_mode == "complex"
        or review_required
        or summary.get("completed", 0) < summary.get("requested_agents", 0)
        or summary.get("reflection_response_reports", 0)
    ) else "summary_only"
    confidence_sources = [
        float(judge_sidecar.get("confidence")) if judge_sidecar.get("confidence") is not None else None,
        float(summary.get("completed", 0)) / float(summary.get("requested_agents", 1) or 1),
        0.9 if sample_mode == "hard_case" else 0.65,
    ]
    confidence_values = [value for value in confidence_sources if value is not None]
    confidence = round(float(sum(confidence_values) / len(confidence_values)) if confidence_values else 0.5, 6)
    review_reason = _dedupe_strings(
        [
            *(str(item) for item in summary.get("runtime_reasons") or []),
            *(str(item) for item in summary.get("candidate_rule_hints") or []),
            *(str(item) for item in audit.get("failure_mode_tags") or []),
            *(str(item) for item in judge_sidecar.get("uncertainties") or []),
            "claim_linked" if bool(claim_context_text(case)) else "no_claim_context",
            "hard_case" if sample_mode == "hard_case" else "summary_only",
        ]
    )
    stance_label = stance_proxy_of(case)
    return {
        "schema_version": TEACHER_SILVER_SCHEMA,
        "case_id": case.get("case_id"),
        "dataset": case.get("dataset"),
        "split": case.get("split"),
        "main_axes": main_axes,
        "stance": {
            "available": bool(claim_context_text(case)),
            "label": stance_label,
            "confidence": 0.8 if claim_context_text(case) and stance_label != "unlinked" else 0.0,
        },
        "fine_labels": fine_labels,
        "confidence": confidence,
        "review_reason": review_reason,
        "evidence_spans": _dedupe_strings(evidence_spans),
        "trace_refs": _dedupe_strings(trace_refs),
        "sample_mode": sample_mode,
    }


def load_teacher_silver_index(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    index: dict[str, dict[str, Any]] = {}
    for row in rows:
        case_id = str(row.get("case_id") or "").strip()
        if case_id and case_id not in index:
            index[case_id] = row
    return index
