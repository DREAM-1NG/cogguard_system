"""Bounded Countermeasure report construction for completed Teacher audits."""

from __future__ import annotations

from typing import Any, Mapping


COUNTERMEASURE_REPORT_SCHEMA = "cogguard.review.countermeasure_report.v1"

__all__ = [
    "COUNTERMEASURE_REPORT_SCHEMA",
    "build_countermeasure_gate",
    "build_countermeasure_report",
]


def build_countermeasure_gate(
    *,
    context: Mapping[str, Any],
    reports_by_agent: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    """Require a valid Judge, traceable input, and persisted governance reference."""

    blockers: list[str] = []
    judge = reports_by_agent.get("HarmfulnessJudgeAgent") or {}
    judge_sidecar = _sidecar(judge)
    prediction = judge_sidecar.get("teacher_prediction")
    governance = judge_sidecar.get("governance_report")
    input_refs = context.get("input_refs") if isinstance(context.get("input_refs"), Mapping) else {}

    if judge.get("status") != "completed":
        blockers.append("judge_not_completed")
    if judge_sidecar.get("teacher_prediction_valid") is not True or not isinstance(prediction, Mapping):
        blockers.append("judge_decision_not_parseable")
    if not list(input_refs.get("post_ids") or []):
        blockers.append("input_spans_unavailable")
    if not isinstance(governance, Mapping) or not list(governance.get("platform_reference_refs") or []):
        blockers.append("governance_reference_not_persistable")
    return {
        "schema": "cogguard.review.countermeasure_gate.v1",
        "eligible": not blockers,
        "blockers": blockers,
        "quality_gate": not blockers,
    }


def build_countermeasure_report(
    *,
    case_id: str,
    snapshot_id: str,
    teacher_audit_id: str,
    reports_by_agent: Mapping[str, Mapping[str, Any]],
    gate: Mapping[str, Any],
) -> dict[str, Any]:
    """Project an internal draft from the persisted Countermeasure Agent output."""

    if gate.get("eligible") is not True:
        return {
            "schema": COUNTERMEASURE_REPORT_SCHEMA,
            "status": "not_generated",
            "case_id": case_id,
            "snapshot_id": snapshot_id,
            "teacher_audit_id": teacher_audit_id,
            "reason": _not_generated_reason(gate.get("blockers")),
            "quality_gate": False,
        }
    countermeasure = reports_by_agent.get("CountermeasureAgent") or {}
    if countermeasure.get("status") != "completed":
        return {
            "schema": COUNTERMEASURE_REPORT_SCHEMA,
            "status": "failed",
            "case_id": case_id,
            "snapshot_id": snapshot_id,
            "teacher_audit_id": teacher_audit_id,
            "reason": "Countermeasure Agent did not complete.",
            "quality_gate": False,
        }

    judge = reports_by_agent.get("HarmfulnessJudgeAgent") or {}
    judge_sidecar = _sidecar(judge)
    governance = judge_sidecar.get("governance_report") if isinstance(judge_sidecar.get("governance_report"), Mapping) else {}
    countermeasure_sidecar = _sidecar(countermeasure)
    evidence_refs = _reference_ids(judge_sidecar)
    policy_refs = _policy_refs(governance)
    return {
        "schema": COUNTERMEASURE_REPORT_SCHEMA,
        "status": "available",
        "case_id": case_id,
        "snapshot_id": snapshot_id,
        "teacher_audit_id": teacher_audit_id,
        "risk_summary": _text(judge.get("report_text"), 1200),
        "evidence_refs": evidence_refs,
        "policy_refs": policy_refs,
        "recommended_actions": _texts(
            governance.get("recommended_actions") or countermeasure_sidecar.get("suggested_actions"),
            12,
            512,
        ),
        "response_draft": _text(countermeasure.get("report_text"), 2400),
        "limitations": [
            "该报告为内部建议草案，必须由分析员确认。",
            "系统不会据此自动发布、删除内容或执行账号处置。",
        ],
        "quality_gate": True,
    }


def _sidecar(report: Mapping[str, Any]) -> dict[str, Any]:
    for key in ("system_audit_sidecar", "structured_sidecar", "sidecar"):
        value = report.get(key)
        if isinstance(value, Mapping):
            return dict(value)
    return {}


def _reference_ids(sidecar: Mapping[str, Any]) -> list[str]:
    result: list[str] = []
    for item in sidecar.get("evidence_refs") or []:
        if isinstance(item, Mapping):
            value = item.get("doc_id") or item.get("source_id") or item.get("id")
        else:
            value = item
        text = _text(value, 256)
        if text and text not in result:
            result.append(text)
    return result[:50]


def _policy_refs(governance: Mapping[str, Any]) -> list[str]:
    result: list[str] = []
    for item in governance.get("platform_reference_refs") or []:
        if not isinstance(item, Mapping):
            continue
        value = _text(item.get("ref_id") or item.get("reference_id") or item.get("url"), 256)
        if value and value not in result:
            result.append(value)
    return result[:50]


def _not_generated_reason(blockers: Any) -> str:
    values = _texts(blockers, 8, 128)
    return "Countermeasure report was not generated: " + (", ".join(values) or "quality gate not met")


def _texts(values: Any, maximum: int, limit: int) -> list[str]:
    if isinstance(values, str):
        values = [values]
    result: list[str] = []
    for value in values if isinstance(values, (list, tuple, set)) else []:
        text = _text(value, limit)
        if text and text not in result:
            result.append(text)
        if len(result) == maximum:
            break
    return result


def _text(value: Any, limit: int) -> str:
    return str(value or "").strip()[:limit]
