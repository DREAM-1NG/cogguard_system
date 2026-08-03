"""Persistence-backed governance for V2 analysis outputs and model pointers."""

from __future__ import annotations

import json
import hashlib
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.analysis.governance import approve_canonical_verdict
from app.config import settings
from app.models.analysis import (
    AnalysisModelActivation,
    AnalysisModelActivationApproval,
    AnalysisModelGovernanceDecision,
    AnalysisModelVersion,
    AnalysisRun,
    ReviewFeedback,
    ReviewVerdictVersion,
)
from app.models.user import User


async def approve_run_verdict(
    *,
    run_id: str,
    verdict_id: str,
    approved_by: int,
    approval_notes: str,
    db: AsyncSession,
) -> dict[str, Any]:
    run = await _get_run(run_id, db)
    payload = _json_loads(run.result_json, {})
    source = _find_verdict(payload, verdict_id=verdict_id)
    if source is None:
        source_result = await db.execute(
            select(ReviewVerdictVersion)
            .where(
                ReviewVerdictVersion.verdict_id == verdict_id,
                ReviewVerdictVersion.run_id == run_id,
            )
            .order_by(ReviewVerdictVersion.version.desc())
            .limit(1)
        )
        source_row = source_result.scalar_one_or_none()
        if source_row is not None and source_row.verdict_type != "canonical":
            source = _json_loads(source_row.verdict_json, {})
    if not source:
        raise ValueError("Analysis run does not contain a review verdict to approve")
    source_id = str(source.get("verdict_id") or "").strip()
    if not source_id or source_id != verdict_id:
        raise ValueError("Review verdict has no immutable verdict_id")
    existing = await db.execute(
        select(ReviewVerdictVersion)
        .where(ReviewVerdictVersion.canonical_source_id == source_id)
        .order_by(ReviewVerdictVersion.version.desc())
    )
    if existing.scalars().first() is not None:
        raise ValueError("A canonical verdict already exists for this source verdict")

    canonical = approve_canonical_verdict(
        source,
        approved_by=approved_by,
        approval_notes=approval_notes,
    )
    row = ReviewVerdictVersion(
        verdict_id=canonical["verdict_id"],
        run_id=run_id,
        snapshot_id=str(run.snapshot_id),
        version=1,
        verdict_type="canonical",
        status="approved",
        verdict_json=_json_dumps(canonical),
        immutable_source=str(canonical["immutable_source"]),
        canonical_source_id=source_id,
        provenance_json=_json_dumps(canonical.get("provenance") or {}),
        approved_by=approved_by,
        approved_at=datetime.now(timezone.utc),
        approval_notes=approval_notes,
        created_by=approved_by,
    )
    db.add(row)
    await db.flush()
    return _verdict_mapping(row)


async def create_feedback(
    *,
    run_id: str,
    snapshot_id: str,
    verdict_id: str | None,
    feedback: dict[str, Any],
    created_by: int,
    db: AsyncSession,
) -> dict[str, Any]:
    run = await _get_run(run_id, db)
    if str(run.snapshot_id) != str(snapshot_id):
        raise ValueError("Feedback snapshot_id does not match the analysis run")
    if verdict_id:
        verdict_result = await db.execute(
            select(ReviewVerdictVersion.id)
            .where(
                ReviewVerdictVersion.verdict_id == verdict_id,
                ReviewVerdictVersion.run_id == run_id,
            )
            .limit(1)
        )
        if verdict_result.first() is None:
            raise ValueError("Feedback verdict_id does not belong to the analysis run")
    feedback_id = f"feedback_{uuid4().hex}"
    row = ReviewFeedback(
        feedback_id=feedback_id,
        run_id=run_id,
        verdict_id=verdict_id,
        snapshot_id=snapshot_id,
        feedback_json=_json_dumps(feedback),
        immutable_source="analysis.governance.human_feedback.v1",
        provenance_json=_json_dumps({"created_by": created_by}),
        created_by=created_by,
    )
    db.add(row)
    await db.flush()
    return _feedback_mapping(row)


async def register_model_version(
    *,
    payload: dict[str, Any],
    created_by: int,
    db: AsyncSession,
) -> dict[str, Any]:
    artifact_uri = str(payload["artifact_uri"]).strip()
    artifact_hash = str(payload["artifact_hash"]).strip().lower()
    if not artifact_uri or not artifact_hash:
        raise ValueError("A model version requires an artifact URI and hash")
    if not _is_sha256_digest(artifact_hash):
        raise ValueError("A model version requires a 64-character SHA-256 artifact hash")
    row = AnalysisModelVersion(
        technology=str(payload["technology"]).strip(),
        model=str(payload["model"]).strip(),
        version=str(payload["version"]).strip(),
        artifact_hash=artifact_hash,
        artifact_uri=artifact_uri,
        config_json=_json_dumps(payload.get("config") or {}),
        metrics_json=_json_dumps(payload.get("metrics") or {}),
        status="candidate",
        created_by=created_by,
    )
    db.add(row)
    await db.flush()
    return _model_mapping(row)


async def activate_model_version(
    *,
    model_version_id: int,
    operator_id: int,
    reason: str,
    db: AsyncSession,
    artifact_root: str | Path | None = None,
) -> dict[str, Any]:
    if int(operator_id) <= 0:
        raise ValueError("Model activation requires an accountable operator")
    row = await _get_model(model_version_id, db)
    verified = verify_registered_artifact(
        artifact_uri=row.artifact_uri,
        expected_hash=row.artifact_hash,
        technology=row.technology,
        artifact_root=artifact_root or settings.MODEL_ARTIFACT_ROOT,
    )
    if not verified.quality_gates["activation_allowed"]:
        failed = ", ".join(verified.quality_gates["failed_gates"])
        raise ValueError(f"Model quality gates failed: {failed}")
    if not settings.model_activation_requires_dual_approval:
        await approve_model_candidate(
            model_version_id=model_version_id,
            approved_by=operator_id,
            approval_notes="Local activation operator approval.",
            db=db,
            artifact_root=artifact_root,
        )
    active_admin_ids = await _active_administrator_ids(db)
    recorded_approvers = await _active_model_approval_ids(
        model_version_id=model_version_id,
        db=db,
    )
    approvers = _resolve_activation_approvers(
        operator_id=operator_id,
        recorded_approvers=recorded_approvers,
        active_admin_ids=active_admin_ids,
    )
    current_result = await db.execute(
        select(AnalysisModelActivation)
        .where(AnalysisModelActivation.technology == row.technology)
        .with_for_update()
    )
    current = current_result.scalar_one_or_none()
    if current is not None and current.model_version_id == row.id:
        raise ValueError("Model version is already active for this technology")
    previous_id = int(current.model_version_id) if current is not None else None
    decision = _governance_decision(
        decision_type="activation",
        technology=row.technology,
        model_version_id=int(row.id),
        previous_model_version_id=previous_id,
        operator_id=operator_id,
        approved_by=approvers,
        reason=reason,
        verified=verified,
    )
    row.status = "active"
    if current is None:
        current = AnalysisModelActivation(
            technology=row.technology,
            model_version_id=row.id,
            provenance_json=_json_dumps(decision),
            activated_by=operator_id,
        )
        db.add(current)
    else:
        previous_model = await _get_model(current.model_version_id, db)
        previous_model.status = "approved"
        current.model_version_id = row.id
        current.provenance_json = _json_dumps(decision)
        current.activated_by = operator_id
        current.activated_at = datetime.now(timezone.utc)
    history = AnalysisModelGovernanceDecision(
        decision_id=str(decision["decision_id"]),
        technology=row.technology,
        model_version_id=row.id,
        previous_model_version_id=previous_id,
        decision_type="activation",
        decision_json=_json_dumps(decision),
        decided_by=operator_id,
    )
    db.add(history)
    await db.flush()
    # `activated_at` is server-generated on the first active pointer. Load it
    # explicitly before building the async response mapping.
    await db.refresh(current)
    return {
        "decision": decision,
        "model_version": _model_mapping(row),
        "activation": _activation_mapping(current),
    }


async def approve_model_candidate(
    *,
    model_version_id: int,
    approved_by: int,
    approval_notes: str,
    db: AsyncSession,
    artifact_root: str | Path | None = None,
) -> dict[str, Any]:
    """Record one authenticated administrator's approval of a candidate model."""

    if int(approved_by) <= 0:
        raise ValueError("Model candidate approval requires an accountable administrator")
    row = await _get_model(model_version_id, db)
    if row.status not in {"candidate", "approved"}:
        raise ValueError("Only a candidate or approved model version can receive approvals")
    verified = verify_registered_artifact(
        artifact_uri=row.artifact_uri,
        expected_hash=row.artifact_hash,
        technology=row.technology,
        artifact_root=artifact_root or settings.MODEL_ARTIFACT_ROOT,
    )
    if not verified.quality_gates["activation_allowed"]:
        failed = ", ".join(verified.quality_gates["failed_gates"])
        raise ValueError(f"Model quality gates failed: {failed}")
    active_admin_ids = await _active_administrator_ids(db)
    if int(approved_by) not in active_admin_ids:
        raise ValueError("Model candidate approval requires an active administrator")
    existing_result = await db.execute(
        select(AnalysisModelActivationApproval).where(
            AnalysisModelActivationApproval.model_version_id == row.id,
            AnalysisModelActivationApproval.approver_id == int(approved_by),
        )
    )
    approval = existing_result.scalar_one_or_none()
    recorded = approval is not None
    if approval is None:
        approval = AnalysisModelActivationApproval(
            approval_id=f"model_approval_{uuid4().hex}",
            model_version_id=row.id,
            approver_id=int(approved_by),
            approval_notes=approval_notes,
        )
        db.add(approval)
        await db.flush()
        # `created_at` is a server default. Refresh it before serializing the
        # record so async SQLAlchemy never attempts an implicit lazy load.
        await db.refresh(approval)
    approvers = await _active_model_approval_ids(model_version_id=row.id, db=db)
    required_approvals = 2 if settings.model_activation_requires_dual_approval else 1
    if len(approvers) >= required_approvals and row.status == "candidate":
        row.status = "approved"
    await db.flush()
    return {
        "approval": _model_approval_mapping(approval),
        "approval_recorded": not recorded,
        "active_approval_count": len(approvers),
        "required_approval_count": required_approvals,
        "ready_for_activation": len(approvers) >= required_approvals,
    }


async def rollback_model_version(
    *,
    technology: str,
    reason: str,
    requested_by: int,
    target_model_version_id: int | None = None,
    db: AsyncSession,
    artifact_root: str | Path | None = None,
) -> dict[str, Any]:
    if int(requested_by) <= 0:
        raise ValueError("Model rollback requires an accountable administrator")
    if int(requested_by) not in await _active_administrator_ids(db):
        raise ValueError("Model rollback requires an active administrator")
    activation_result = await db.execute(
        select(AnalysisModelActivation)
        .where(AnalysisModelActivation.technology == technology)
        .with_for_update()
    )
    current = activation_result.scalar_one_or_none()
    if current is None:
        raise ValueError(f"No active model found for technology: {technology}")
    history_result = await db.execute(
        select(AnalysisModelGovernanceDecision)
        .where(AnalysisModelGovernanceDecision.technology == technology)
        .order_by(AnalysisModelGovernanceDecision.id.desc())
    )
    history = list(history_result.scalars().all())
    approved_ids = [
        int(item.model_version_id)
        for item in history
        if item.decision_type in {"activation", "rollback"}
    ]
    if target_model_version_id is None:
        target_model_version_id = next(
            (value for value in approved_ids if value != int(current.model_version_id)),
            None,
        )
    if target_model_version_id is None or int(target_model_version_id) not in set(approved_ids):
        raise ValueError("Rollback target is not an approved historical model version")
    if int(target_model_version_id) == int(current.model_version_id):
        raise ValueError("Rollback target is already active")
    previous = await _get_model(int(target_model_version_id), db)
    if previous.technology != technology:
        raise ValueError("Rollback target belongs to a different analysis capability")
    verified = verify_registered_artifact(
        artifact_uri=previous.artifact_uri,
        expected_hash=previous.artifact_hash,
        technology=technology,
        artifact_root=artifact_root or settings.MODEL_ARTIFACT_ROOT,
    )
    if not verified.quality_gates["activation_allowed"]:
        raise ValueError("Rollback target no longer satisfies its capability quality gates")
    active_model = await _get_model(current.model_version_id, db)
    decision = _governance_decision(
        decision_type="rollback",
        technology=technology,
        model_version_id=int(previous.id),
        previous_model_version_id=int(active_model.id),
        operator_id=requested_by,
        approved_by=(requested_by,),
        reason=reason,
        verified=verified,
    )
    current.model_version_id = previous.id
    current.provenance_json = _json_dumps(decision)
    current.activated_by = requested_by
    current.activated_at = datetime.now(timezone.utc)
    active_model.status = "approved"
    previous.status = "active"
    db.add(
        AnalysisModelGovernanceDecision(
            decision_id=str(decision["decision_id"]),
            technology=technology,
            model_version_id=previous.id,
            previous_model_version_id=active_model.id,
            decision_type="rollback",
            decision_json=_json_dumps(decision),
            decided_by=requested_by,
        )
    )
    await db.flush()
    return {"decision": decision, "active_model": _model_mapping(previous)}


async def list_model_governance_history(
    *,
    technology: str,
    db: AsyncSession,
    limit: int = 100,
) -> list[dict[str, Any]]:
    result = await db.execute(
        select(AnalysisModelGovernanceDecision)
        .where(AnalysisModelGovernanceDecision.technology == technology)
        .order_by(AnalysisModelGovernanceDecision.id.desc())
        .limit(limit)
    )
    return [
        {
            "decision_id": row.decision_id,
            "technology": row.technology,
            "model_version_id": row.model_version_id,
            "previous_model_version_id": row.previous_model_version_id,
            "decision_type": row.decision_type,
            "decision": _json_loads(row.decision_json, {}),
            "decided_by": row.decided_by,
            "created_at": row.created_at.isoformat() if row.created_at else None,
        }
        for row in result.scalars().all()
    ]


async def _get_run(run_id: str, db: AsyncSession) -> AnalysisRun:
    result = await db.execute(select(AnalysisRun).where(AnalysisRun.run_id == run_id))
    row = result.scalar_one_or_none()
    if row is None:
        raise ValueError(f"Analysis run not found: {run_id}")
    return row


async def _get_model(model_version_id: int, db: AsyncSession) -> AnalysisModelVersion:
    result = await db.execute(select(AnalysisModelVersion).where(AnalysisModelVersion.id == model_version_id))
    row = result.scalar_one_or_none()
    if row is None:
        raise ValueError(f"Model version not found: {model_version_id}")
    return row


async def _active_administrator_ids(db: AsyncSession) -> set[int]:
    result = await db.execute(
        select(User.id).where(
            User.role == "admin",
            User.is_active.is_(True),
        )
    )
    return {int(value) for value in result.scalars().all()}


async def _active_model_approval_ids(*, model_version_id: int, db: AsyncSession) -> set[int]:
    result = await db.execute(
        select(AnalysisModelActivationApproval.approver_id)
        .join(User, User.id == AnalysisModelActivationApproval.approver_id)
        .where(
            AnalysisModelActivationApproval.model_version_id == int(model_version_id),
            User.role == "admin",
            User.is_active.is_(True),
        )
    )
    return {int(value) for value in result.scalars().all()}


def _resolve_activation_approvers(
    *,
    operator_id: int,
    recorded_approvers: set[int],
    active_admin_ids: set[int],
) -> tuple[int, ...]:
    """Validate persisted approvals without trusting caller-supplied identities."""

    operator = int(operator_id)
    if operator <= 0:
        raise ValueError("Model activation requires an accountable operator")
    if operator not in active_admin_ids:
        raise ValueError("The activating operator must be an active administrator")
    approved = set(recorded_approvers) & set(active_admin_ids)
    if operator not in approved:
        raise ValueError("The activating operator must approve the candidate before activation")
    if settings.model_activation_requires_dual_approval and len(approved) < 2:
        raise ValueError("Production model activation requires two distinct active administrator approvers")
    required = 2 if settings.model_activation_requires_dual_approval else 1
    return tuple(sorted(approved if required > 1 else {operator}))


def _find_verdict(payload: dict[str, Any], *, verdict_id: str | None = None) -> dict[str, Any] | None:
    results = payload.get("results") if isinstance(payload, dict) else None
    if not isinstance(results, dict):
        return None
    candidates = (results.get("teacher"), results.get("student"))
    for candidate in candidates:
        if not isinstance(candidate, dict):
            continue
        if candidate.get("verdict_type") not in {"teacher_advisory", "preliminary"}:
            continue
        if verdict_id is None or str(candidate.get("verdict_id")) == str(verdict_id):
            return candidate
    return None


@dataclass(frozen=True, slots=True)
class VerifiedArtifact:
    artifact_path: Path
    checkpoint_path: Path
    manifest_path: Path
    manifest: dict[str, Any]
    checkpoint_sha256: str
    quality_gates: dict[str, Any]


def verify_registered_artifact(
    *,
    artifact_uri: str,
    expected_hash: str,
    technology: str,
    artifact_root: str | Path,
) -> VerifiedArtifact:
    root = Path(artifact_root).expanduser().resolve()
    candidate = Path(str(artifact_uri or "").strip()).expanduser()
    if not candidate.is_absolute():
        candidate = root / candidate
    try:
        artifact_path = candidate.resolve(strict=True)
    except OSError as exc:
        raise ValueError("Model artifact path is unreadable") from exc
    _require_within_root(artifact_path, root)

    artifact_is_directory = artifact_path.is_dir()
    if artifact_is_directory:
        manifest_path = artifact_path / "manifest.json"
    elif artifact_path.is_file():
        manifest_path = artifact_path.parent / "manifest.json"
    else:
        raise ValueError("Model artifact path must be a file or directory")
    try:
        manifest_path = manifest_path.resolve(strict=True)
    except OSError as exc:
        raise ValueError("Model artifact manifest.json is required") from exc
    _require_within_root(
        manifest_path,
        artifact_path if artifact_is_directory else root,
        boundary_name="artifact directory" if artifact_is_directory else "artifact root",
    )
    if not manifest_path.is_file():
        raise ValueError("Model artifact manifest.json is required")
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError("Model artifact manifest is unreadable or invalid JSON") from exc
    if not isinstance(manifest, dict):
        raise ValueError("Model artifact manifest must be a JSON object")
    if str(manifest.get("technology") or "") != str(technology):
        raise ValueError("Model artifact manifest capability does not match the registered model")

    if not artifact_is_directory:
        checkpoint_path = artifact_path
    else:
        relative_checkpoint = str(manifest.get("checkpoint_path") or "checkpoint.pt").strip()
        checkpoint_path = (artifact_path / relative_checkpoint).resolve(strict=True)
        _require_within_root(checkpoint_path, artifact_path, boundary_name="artifact directory")
    _require_within_root(checkpoint_path, root)
    if not checkpoint_path.is_file():
        raise ValueError("Model checkpoint path is not a file")
    expected = str(expected_hash or "").strip().lower()
    if not _is_sha256_digest(expected):
        raise ValueError("Registered model hash is not a SHA-256 digest")
    actual = _sha256_file(checkpoint_path)
    if actual != expected:
        raise ValueError("Model checkpoint SHA-256 does not match the registered hash")
    metrics = manifest.get("metrics")
    if not isinstance(metrics, dict):
        raise ValueError("Model artifact manifest metrics are required")
    quality_gates = evaluate_quality_gates(technology, metrics)
    return VerifiedArtifact(
        artifact_path=artifact_path,
        checkpoint_path=checkpoint_path,
        manifest_path=manifest_path.resolve(),
        manifest=manifest,
        checkpoint_sha256=actual,
        quality_gates=quality_gates,
    )


def evaluate_quality_gates(technology: str, metrics: dict[str, Any]) -> dict[str, Any]:
    capability = str(technology or "").strip()
    checks: dict[str, bool]
    if capability == "coordination_discover":
        checks = {
            "strict_leiden": metrics.get("strict_leiden") is True,
            "stability_passed": metrics.get("stability_passed") is True,
            "evidence_coverage_passed": metrics.get("evidence_coverage_passed") is True,
        }
    elif capability == "propagation_analysis":
        checks = {
            "coverage_80": _metric_at_least(metrics, "coverage_80", 0.78),
            "coverage_95": _metric_at_least(metrics, "coverage_95", 0.93),
            "beats_strong_baseline": metrics.get("beats_strong_baseline") is True,
        }
    elif capability == "review_student":
        checks = {
            "teacher_macro_f1_gap": _metric_at_most(metrics, "teacher_macro_f1_gap", 0.03),
            "ece": _metric_at_most(metrics, "ece", 0.08),
            "p95_latency_seconds": _metric_at_most(metrics, "p95_latency_seconds", 2.0),
        }
    elif capability == "review_teacher":
        checks = {
            "beats_best_single_agent": metrics.get("beats_best_single_agent") is True,
            "beats_majority_vote": metrics.get("beats_majority_vote") is True,
        }
    else:
        checks = {"registered_capability_policy": False}
    failed = [name for name, passed in checks.items() if not passed]
    return {
        "technology": capability,
        "activation_allowed": not failed,
        "checks": checks,
        "failed_gates": failed,
    }


def _governance_decision(
    *,
    decision_type: str,
    technology: str,
    model_version_id: int,
    previous_model_version_id: int | None,
    operator_id: int,
    approved_by: tuple[int, ...] = (),
    reason: str,
    verified: VerifiedArtifact,
) -> dict[str, Any]:
    decided_at = datetime.now(timezone.utc).isoformat()
    identity = {
        "decision_type": decision_type,
        "technology": technology,
        "model_version_id": model_version_id,
        "previous_model_version_id": previous_model_version_id,
        "operator_id": operator_id,
        "approved_by": list(approved_by),
        "approval_mode": "dual_operator" if len(approved_by) >= 2 else "single_operator",
        "decided_at": decided_at,
    }
    return {
        "schema": "cogguard.analysis.model_governance_decision.v2",
        "decision_id": f"model_decision_{hashlib.sha256(_json_dumps(identity).encode('utf-8')).hexdigest()[:32]}",
        **identity,
        "reason": reason,
        "artifact": {
            "checkpoint_sha256": verified.checkpoint_sha256,
            "checkpoint_path": str(verified.checkpoint_path),
            "manifest_path": str(verified.manifest_path),
        },
        "quality_gates": verified.quality_gates,
        "activation_allowed": verified.quality_gates["activation_allowed"],
        "immutable_source": "analysis.governance.model_decision.v2",
    }


def _require_within_root(path: Path, root: Path, *, boundary_name: str = "artifact root") -> None:
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise ValueError(f"Model artifact path resolves outside the configured {boundary_name}") from exc


def _metric_at_least(metrics: dict[str, Any], name: str, threshold: float) -> bool:
    try:
        return float(metrics[name]) >= threshold
    except (KeyError, TypeError, ValueError):
        return False


def _metric_at_most(metrics: dict[str, Any], name: str, threshold: float) -> bool:
    try:
        return float(metrics[name]) <= threshold
    except (KeyError, TypeError, ValueError):
        return False


def _artifact_matches_hash(uri: str, expected_hash: str) -> bool:
    value = str(uri or "").strip()
    if not _is_sha256_digest(str(expected_hash).strip().lower()):
        return False
    if value.startswith(("s3://", "gs://", "http://", "https://")):
        # Remote stores need a deployment-specific artifact resolver. Treating
        # an un-fetched URI as verified would make model activation unauditable.
        return False
    path = Path(value)
    if path.is_file():
        return _sha256_file(path) == str(expected_hash).lower()
    if path.is_dir():
        manifest = path / "manifest.json"
        checkpoint = path / "checkpoint.pt"
        source = manifest if manifest.is_file() else checkpoint
        return source.is_file() and _sha256_file(source) == str(expected_hash).lower()
    return False


def _is_sha256_digest(value: str) -> bool:
    return bool(re.fullmatch(r"[0-9a-f]{64}", value))


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _json_dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)


def _json_loads(value: str | None, default: Any) -> Any:
    try:
        return json.loads(value) if value else default
    except (TypeError, json.JSONDecodeError):
        return default


def _verdict_mapping(row: ReviewVerdictVersion) -> dict[str, Any]:
    return {
        "verdict_id": row.verdict_id,
        "run_id": row.run_id,
        "snapshot_id": row.snapshot_id,
        "version": row.version,
        "verdict_type": row.verdict_type,
        "status": row.status,
        "verdict": _json_loads(row.verdict_json, {}),
        "canonical_source_id": row.canonical_source_id,
        "approved_by": row.approved_by,
        "approved_at": row.approved_at.isoformat() if row.approved_at else None,
    }


def _feedback_mapping(row: ReviewFeedback) -> dict[str, Any]:
    return {
        "feedback_id": row.feedback_id,
        "run_id": row.run_id,
        "snapshot_id": row.snapshot_id,
        "verdict_id": row.verdict_id,
        "feedback": _json_loads(row.feedback_json, {}),
        "created_by": row.created_by,
    }


def _model_mapping(row: AnalysisModelVersion) -> dict[str, Any]:
    return {
        "id": row.id,
        "technology": row.technology,
        "model": row.model,
        "version": row.version,
        "artifact_hash": row.artifact_hash,
        "artifact_uri": row.artifact_uri,
        "status": row.status,
        "config": _json_loads(row.config_json, {}),
        "metrics": _json_loads(row.metrics_json, {}),
    }


def _model_approval_mapping(row: AnalysisModelActivationApproval) -> dict[str, Any]:
    return {
        "approval_id": row.approval_id,
        "model_version_id": row.model_version_id,
        "approver_id": row.approver_id,
        "approval_notes": row.approval_notes,
        "immutable_source": row.immutable_source,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


def _activation_mapping(row: AnalysisModelActivation) -> dict[str, Any]:
    return {
        "technology": row.technology,
        "model_version_id": row.model_version_id,
        "provenance": _json_loads(row.provenance_json, {}),
        "activated_by": row.activated_by,
        "activated_at": row.activated_at.isoformat() if row.activated_at else None,
    }


__all__ = [
    "activate_model_version",
    "approve_model_candidate",
    "approve_run_verdict",
    "create_feedback",
    "evaluate_quality_gates",
    "list_model_governance_history",
    "register_model_version",
    "rollback_model_version",
    "verify_registered_artifact",
]
