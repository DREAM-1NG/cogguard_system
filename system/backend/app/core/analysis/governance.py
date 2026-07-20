"""Governance helpers for analysis verdicts and model activation."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Mapping


CANONICAL_SOURCE = "analysis.governance.canonical_approval.v1"
MODEL_GOVERNANCE_SOURCE = "analysis.governance.model_activation.v1"


def approve_canonical_verdict(
    source_verdict: Mapping[str, Any],
    *,
    approved_by: int,
    approval_notes: str = "",
) -> dict[str, Any]:
    """Create an immutable canonical verdict from an analyst-approved source."""

    verdict_type = str(source_verdict.get("verdict_type") or "")
    if verdict_type == "canonical":
        raise ValueError("Source verdict is already canonical.")
    if int(approved_by) <= 0:
        raise ValueError("Canonical verdict approval requires a positive analyst id.")
    approved_at = datetime.now(timezone.utc).isoformat()
    canonical = {
        "technology": source_verdict.get("technology") or "kt3",
        "schema": "cogguard.analysis.canonical_verdict.v1",
        "status": "approved",
        "verdict_type": "canonical",
        "verdict_id": _canonical_id(source_verdict, approved_by=approved_by),
        "canonical_source_id": source_verdict.get("verdict_id"),
        "snapshot_id": source_verdict.get("snapshot_id"),
        "event_id": source_verdict.get("event_id"),
        "label": source_verdict.get("label") or _decision_label(source_verdict),
        "score": source_verdict.get("score") or _decision_score(source_verdict),
        "approved_by": int(approved_by),
        "approved_at": approved_at,
        "approval_notes": approval_notes,
        "immutable_source": CANONICAL_SOURCE,
        "source_digest": _digest(source_verdict),
        "provenance": {
            "source_verdict_type": verdict_type,
            "source_model_version": source_verdict.get("model_version"),
            "teacher_advisory_only": verdict_type == "teacher_advisory",
            "student_preliminary_only": verdict_type == "preliminary",
        },
    }
    return canonical


def build_model_activation_decision(
    candidate: Mapping[str, Any],
    *,
    approved_by: list[int],
    previous_activation: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Return an auditable active-pointer decision."""

    approvers = [int(value) for value in approved_by if int(value) > 0]
    quality = dict(candidate.get("quality_gates") or {})
    passed = bool(quality.get("latency_passed")) and bool(quality.get("calibration_passed")) and bool(
        quality.get("safety_passed")
    )
    dual_approved = len(set(approvers)) >= 2
    status = "approved_for_activation" if passed and dual_approved else "blocked"
    return {
        "schema": "cogguard.analysis.model_activation_decision.v1",
        "technology": candidate.get("technology"),
        "model_version": candidate.get("version") or candidate.get("model_version"),
        "status": status,
        "activation_allowed": status == "approved_for_activation",
        "approved_by": sorted(set(approvers)),
        "previous_activation": dict(previous_activation or {}),
        "immutable_source": MODEL_GOVERNANCE_SOURCE,
        "gates": {
            "dual_approval": dual_approved,
            "latency_passed": bool(quality.get("latency_passed")),
            "calibration_passed": bool(quality.get("calibration_passed")),
            "safety_passed": bool(quality.get("safety_passed")),
        },
        "rollback_pointer": (previous_activation or {}).get("model_version_id"),
    }


def build_rollback_decision(
    active_activation: Mapping[str, Any],
    previous_activation: Mapping[str, Any],
    *,
    reason: str,
    requested_by: int,
) -> dict[str, Any]:
    if int(requested_by) <= 0:
        raise ValueError("Rollback requires an accountable requester.")
    return {
        "schema": "cogguard.analysis.model_rollback_decision.v1",
        "status": "rollback_requested",
        "technology": active_activation.get("technology") or previous_activation.get("technology"),
        "from_model_version_id": active_activation.get("model_version_id"),
        "to_model_version_id": previous_activation.get("model_version_id"),
        "reason": reason,
        "requested_by": int(requested_by),
        "requested_at": datetime.now(timezone.utc).isoformat(),
        "immutable_source": MODEL_GOVERNANCE_SOURCE,
        "rule_authority_preserved": True,
    }


def select_active_learning_cases(
    cases: list[Mapping[str, Any]],
    *,
    budget: int,
) -> dict[str, Any]:
    ranked = []
    for case in cases:
        signal = dict(case.get("active_learning") or dict(dict(case.get("signals") or {}).get("active_learning") or {}))
        priority = float(signal.get("priority") or 0.0)
        reasons = list(signal.get("reasons") or [])
        if not reasons and priority > 0:
            reasons = ["priority_score"]
        ranked.append(
            {
                "case_id": str(case.get("verdict_id") or case.get("snapshot_id") or _digest(case)[:16]),
                "priority": round(priority, 6),
                "reasons": reasons,
                "diversity_key": _diversity_key(case),
            }
        )
    ranked.sort(key=lambda row: (row["priority"], row["diversity_key"], row["case_id"]), reverse=True)
    selected = ranked[: max(0, int(budget))]
    return {
        "schema": "cogguard.analysis.active_learning_batch.v1",
        "selected": selected,
        "selected_count": len(selected),
        "candidate_count": len(ranked),
        "policy": {
            "drivers": ["uncertainty", "disagreement", "ood", "drift", "diversity", "random_audit"],
            "feedback_trigger": "200_approved_feedback_or_drift_alert",
            "minimum_retrain_interval_days": 7,
        },
    }


def _canonical_id(source_verdict: Mapping[str, Any], *, approved_by: int) -> str:
    payload = {"source": source_verdict, "approved_by": approved_by}
    return f"canonical_{_digest(payload)[:24]}"


def _decision_label(verdict: Mapping[str, Any]) -> str:
    advisory = dict(verdict.get("advisory") or {})
    decision = str(advisory.get("decision") or "")
    if "harmful" in decision and "non_harmful" not in decision:
        return "harmful"
    if "non_harmful" in decision:
        return "non_harmful"
    return "uncertain"


def _decision_score(verdict: Mapping[str, Any]) -> float:
    advisory = dict(verdict.get("advisory") or {})
    try:
        return float(advisory.get("score") or verdict.get("score") or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _diversity_key(case: Mapping[str, Any]) -> str:
    platforms = case.get("platforms")
    if isinstance(platforms, list) and platforms:
        return ",".join(sorted(str(platform) for platform in platforms))
    return str(case.get("event_id") or case.get("snapshot_id") or "")


def _digest(value: Any) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()
