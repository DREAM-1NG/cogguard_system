"""Persistence-backed governance for V2 analysis outputs and model pointers."""

from __future__ import annotations

import json
import hashlib
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.analysis.governance import (
    approve_canonical_verdict,
    build_model_activation_decision,
    build_rollback_decision,
)
from app.models.analysis import (
    AnalysisModelActivation,
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
    approved_by: list[int],
    quality_gates: dict[str, bool],
    db: AsyncSession,
) -> dict[str, Any]:
    row = await _get_model(model_version_id, db)
    if not _artifact_matches_hash(row.artifact_uri, row.artifact_hash):
        raise ValueError("Model artifact URI is unreadable or its hash does not match the registered hash")
    current_result = await db.execute(
        select(AnalysisModelActivation).where(AnalysisModelActivation.technology == row.technology)
    )
    current = current_result.scalar_one_or_none()
    if current is not None and current.model_version_id == row.id:
        raise ValueError("Model version is already active for this technology")
    approver_result = await db.execute(
        select(User.id).where(
            User.id.in_(approved_by),
            User.role == "admin",
            User.is_active.is_(True),
        )
    )
    registered_approvers = {int(value) for value in approver_result.scalars().all()}
    if len(registered_approvers) < 2 or not set(approved_by).issubset(registered_approvers):
        raise ValueError("Model activation requires two distinct active administrator approvers")
    previous = _activation_mapping(current) if current else None
    decision = build_model_activation_decision(
        {
            "technology": row.technology,
            "version": row.version,
            "quality_gates": quality_gates,
        },
        approved_by=approved_by,
        previous_activation=previous,
    )
    if not decision["activation_allowed"]:
        raise ValueError("Model activation quality gates or dual approval are incomplete")
    row.status = "active"
    if current is None:
        current = AnalysisModelActivation(
            technology=row.technology,
            model_version_id=row.id,
            provenance_json=_json_dumps(decision),
            activated_by=min(decision["approved_by"]),
        )
        db.add(current)
    else:
        previous_model = await _get_model(current.model_version_id, db)
        previous_model.status = "superseded"
        current.model_version_id = row.id
        current.provenance_json = _json_dumps(decision)
        current.activated_by = min(decision["approved_by"])
        current.activated_at = datetime.now(timezone.utc)
    await db.flush()
    return {"decision": decision, "model_version": _model_mapping(row), "activation": _activation_mapping(current)}


async def rollback_model_version(
    *,
    technology: str,
    reason: str,
    requested_by: int,
    db: AsyncSession,
) -> dict[str, Any]:
    activation_result = await db.execute(
        select(AnalysisModelActivation).where(AnalysisModelActivation.technology == technology)
    )
    current = activation_result.scalar_one_or_none()
    if current is None:
        raise ValueError(f"No active model found for technology: {technology}")
    history = _json_loads(current.provenance_json, {})
    previous_id = history.get("rollback_pointer")
    if not previous_id:
        raise ValueError("No previous approved model pointer is available for rollback")
    previous = await _get_model(int(previous_id), db)
    if not _artifact_matches_hash(previous.artifact_uri, previous.artifact_hash):
        raise ValueError("Rollback target artifact is unreadable or its hash does not match")
    active_model = await _get_model(current.model_version_id, db)
    decision = build_rollback_decision(
        _activation_mapping(current),
        {"technology": technology, "model_version_id": previous.id},
        reason=reason,
        requested_by=requested_by,
    )
    current.model_version_id = previous.id
    current.provenance_json = _json_dumps({**history, "rollback": decision, "rollback_pointer": None})
    current.activated_by = requested_by
    current.activated_at = datetime.now(timezone.utc)
    active_model.status = "rolled_back"
    previous.status = "active"
    await db.flush()
    return {"decision": decision, "active_model": _model_mapping(previous)}


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
    "approve_run_verdict",
    "create_feedback",
    "register_model_version",
    "rollback_model_version",
]
