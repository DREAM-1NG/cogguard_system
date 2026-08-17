"""Teacher Silver supervision contract for Review Student distillation."""

from __future__ import annotations

from typing import Any

from app.core.review.review_task_schema import (
    ATTACK_AXIS,
    MISINFO_AXIS,
    TEACHER_SILVER_SCHEMA,
    claim_context_text,
)
from app.core.review.evidence_contracts import EvidenceBundle, PolicyBundle, RationaleCapsule, rationale_quality_gate

__all__ = [
    "build_teacher_silver_record",
    "build_teacher_silver_quality_gate",
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
    judge_reports = [item for item in agent_reports if item.get("agent_name") == "HarmfulnessJudgeAgent"]
    judge_report = next(
        (
            item
            for item in reversed(judge_reports)
            if item.get("status") == "completed" and item.get("report_role") == "judge_final"
        ),
        next((item for item in reversed(judge_reports) if item.get("status") == "completed"), {}),
    )
    judge_sidecar = judge_report.get("structured_sidecar") or {}
    selected_posts = _as_list((review_result.get("input_bundle") or {}).get("selected_posts"))
    teacher_prediction = judge_sidecar.get("teacher_prediction") or {}
    prediction_axes = teacher_prediction.get("main_axes") if isinstance(teacher_prediction, dict) else {}
    main_axes = {}
    for axis_name in (ATTACK_AXIS, MISINFO_AXIS):
        prediction_axis = prediction_axes.get(axis_name) if isinstance(prediction_axes, dict) else None
        available = bool(isinstance(prediction_axis, dict) and prediction_axis.get("available"))
        main_axes[axis_name] = {
            "available": available,
            "label": str(prediction_axis.get("label") or "unavailable") if isinstance(prediction_axis, dict) else "unavailable",
            "confidence": float(prediction_axis.get("confidence") or 0.0) if isinstance(prediction_axis, dict) else 0.0,
            "source": "judge_teacher_prediction" if available else "masked",
        }
    fine_labels = _dedupe_strings(
        [str(item) for item in teacher_prediction.get("fine_labels") or []]
        if isinstance(teacher_prediction, dict)
        else []
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
    available_axis_confidences = [
        float(axis["confidence"])
        for axis in main_axes.values()
        if axis.get("available")
    ]
    confidence = round(
        max(0.0, min(1.0, float(sum(available_axis_confidences) / len(available_axis_confidences))))
        if available_axis_confidences
        else 0.0,
        6,
    )
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
    stance_prediction = teacher_prediction.get("stance") if isinstance(teacher_prediction, dict) else {}
    stance_prediction = stance_prediction if isinstance(stance_prediction, dict) else {}
    legacy_distillation_eligible = bool(
        judge_report.get("status") == "completed"
        and judge_sidecar.get("teacher_prediction_valid") is True
        and any(axis.get("available") and axis.get("label") in {"harmful", "non_harmful"} for axis in main_axes.values())
    )
    evidence_bundle = EvidenceBundle.from_mapping(
        judge_sidecar.get("evidence_bundle")
        or review_result.get("evidence_bundle")
        or (context_bundle := (review_result.get("input_bundle") or {}).get("evidence_bundle"))
    )
    policy_bundles = [
        PolicyBundle.from_mapping(item)
        for item in _as_list(judge_sidecar.get("policy_bundles") or review_result.get("policy_bundles"))
        if isinstance(item, dict)
    ]
    rationale_capsules = [
        RationaleCapsule.from_mapping(item)
        for item in _as_list(judge_sidecar.get("rationale_capsules") or review_result.get("rationale_capsules"))
        if isinstance(item, dict)
    ]
    claim_supervision_requested = bool(main_axes.get(MISINFO_AXIS, {}).get("available"))
    quality_gate = build_teacher_silver_quality_gate(
        judge_report=judge_report,
        judge_sidecar=judge_sidecar,
        evidence_bundle=evidence_bundle,
        policy_bundles=policy_bundles,
        rationale_capsules=rationale_capsules,
        requires_evidence=claim_supervision_requested,
        requires_policy=bool(main_axes.get(ATTACK_AXIS, {}).get("available")),
    )
    claim_supervision_eligible = not claim_supervision_requested or evidence_bundle.relation_valid
    distillation_eligible = bool(legacy_distillation_eligible and claim_supervision_eligible)
    distillation_ready = bool(distillation_eligible and quality_gate["eligible"])
    return {
        "schema_version": TEACHER_SILVER_SCHEMA,
        "case_id": case.get("case_id"),
        "dataset": case.get("dataset"),
        "split": case.get("split"),
        "main_axes": main_axes,
        "stance": {
            "available": bool(stance_prediction.get("available")),
            "label": str(stance_prediction.get("label") or "unlinked"),
            "confidence": float(stance_prediction.get("confidence") or 0.0),
        },
        "fine_labels": fine_labels,
        "confidence": confidence,
        "review_reason": review_reason,
        "evidence_spans": _dedupe_strings(evidence_spans),
        "trace_refs": _dedupe_strings(trace_refs),
        "sample_mode": sample_mode,
        "review_required": bool(teacher_prediction.get("review_required")) if isinstance(teacher_prediction, dict) else False,
        "distillation_eligible": distillation_eligible,
        "distillation_ready": distillation_ready,
        "distillation_blocker": None if distillation_ready else (
            ";".join(quality_gate["blockers"])
            or judge_sidecar.get("teacher_prediction_error")
            or "missing_valid_judge_teacher_prediction"
        ),
        "quality_gate": quality_gate,
        "evidence_bundle": evidence_bundle.to_dict(),
        "policy_bundles": [item.to_dict() for item in policy_bundles],
        "rationale_capsules": [item.to_dict() for item in rationale_capsules],
        "audit": {
            "teacher_confidence": confidence,
            "teacher_confidence_is_training_target": False,
            "source": "judge_footer_and_typed_evidence",
        },
    }


def build_teacher_silver_quality_gate(
    *,
    judge_report: dict[str, Any],
    judge_sidecar: dict[str, Any],
    evidence_bundle: EvidenceBundle,
    policy_bundles: list[PolicyBundle],
    rationale_capsules: list[RationaleCapsule],
    requires_evidence: bool,
    requires_policy: bool,
) -> dict[str, Any]:
    """Gate new Student supervision without trusting Teacher confidence."""

    blockers: list[str] = []
    if judge_report.get("status") != "completed":
        blockers.append("judge_not_completed")
    if judge_sidecar.get("teacher_prediction_valid") is not True:
        blockers.append("invalid_judge_prediction")
    if judge_sidecar.get("provider_failure") is True or judge_sidecar.get("status") == "failed":
        blockers.append("provider_failure")
    if requires_evidence:
        if evidence_bundle.claim_assessment != "checkable":
            blockers.append("claim_not_checkable")
        if evidence_bundle.retrieval_status != "completed":
            blockers.append(f"retrieval_not_completed:{evidence_bundle.retrieval_status}")
        if not evidence_bundle.has_traceable_evidence:
            blockers.append("missing_traceable_evidence")
        if not evidence_bundle.relation_valid:
            blockers.append("invalid_claim_evidence_relation")
    if requires_policy and not any(policy.usable for policy in policy_bundles):
        blockers.append("missing_active_policy_clause")
    if not rationale_capsules:
        blockers.append("missing_rationale_capsule")
    capsule_blockers: list[str] = []
    for capsule in rationale_capsules:
        eligible, reasons = rationale_quality_gate(
            capsule,
            requires_evidence=capsule.task == "claim_deception",
            requires_policy=capsule.task == "interpersonal_harm",
        )
        if not eligible:
            capsule_blockers.extend(reasons)
    blockers.extend(sorted(set(capsule_blockers)))
    return {
        "schema_version": "review-teacher-silver-quality-gate-v1",
        "eligible": not blockers,
        "blockers": blockers,
        "teacher_confidence_is_training_target": False,
        "evidence_required": requires_evidence,
        "policy_required": requires_policy,
    }


def load_teacher_silver_index(
    rows: list[dict[str, Any]],
    *,
    require_quality_gate: bool = False,
) -> dict[str, dict[str, Any]]:
    index: dict[str, dict[str, Any]] = {}
    duplicate_case_ids: set[str] = set()
    for row in rows:
        case_id = str(row.get("case_id") or "").strip()
        if (
            not case_id
            or row.get("schema_version") != TEACHER_SILVER_SCHEMA
            or row.get("distillation_eligible") is not True
            or (require_quality_gate and row.get("distillation_ready") is not True)
            or not str(row.get("dataset") or "").strip()
            or not str(row.get("split") or "").strip()
        ):
            continue
        if case_id in index:
            duplicate_case_ids.add(case_id)
            continue
        index[case_id] = row
    for case_id in duplicate_case_ids:
        index.pop(case_id, None)
    return index

