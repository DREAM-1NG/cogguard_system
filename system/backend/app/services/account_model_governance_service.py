"""Governance gates for Chinese account-detection model versions."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.account_labeling import (
    AccountDetectionDatasetVersion,
    AccountDetectionModelActivation,
    AccountDetectionModelApproval,
    AccountDetectionModelVersion,
)
from app.models.user import User
from app.utils.exceptions import AppException

__all__ = [
    "activate_account_detection_model",
    "approve_account_detection_model",
    "evaluate_account_model_activation_gates",
    "list_account_detection_models",
    "register_account_training_candidate",
]


def evaluate_account_model_activation_gates(
    metrics: dict[str, Any],
    *,
    approver_ids: list[int] | tuple[int, ...],
    max_ece: float = 0.08,
) -> dict[str, Any]:
    """Return account-model activation gates and final activation decision."""

    distinct_approvers = {int(approver_id) for approver_id in approver_ids if int(approver_id) > 0}
    gates = {
        "frozen_holdout": bool(metrics.get("frozen_holdout_passed")),
        "time_forward": bool(metrics.get("time_forward_passed")),
        "platform_stratified": bool(metrics.get("platform_stratified_passed")),
        "community_disjoint": bool(metrics.get("community_disjoint_passed")),
        "calibration": float(metrics.get("ece", 1.0)) <= max_ece,
        "false_positive_burden": bool(metrics.get("false_positive_burden_passed")),
        "shadow_run": bool(metrics.get("shadow_run_passed")),
        "dual_approval": len(distinct_approvers) >= 2,
    }
    return {
        "activation_allowed": all(gates.values()),
        "gates": gates,
        "requirements": {
            "label_source": "approved_or_adjudicated_observable_behavior_labels_only",
            "holdout_policy": "frozen_holdout_never_selected_by_active_learning",
            "deployment_policy": "review_aid_only_until_activated",
            "max_ece": max_ece,
        },
    }


async def register_account_training_candidate(
    session: AsyncSession,
    *,
    model_version: str,
    dataset_version_id: str,
    artifact_uri: str,
    artifact_hash: str,
    metrics: dict[str, Any],
    operator_id: int,
) -> dict[str, Any]:
    """Register a shadow candidate trained from approved account labels."""

    dataset = (
        await session.execute(
            select(AccountDetectionDatasetVersion).where(
                AccountDetectionDatasetVersion.dataset_version_id == dataset_version_id
            )
        )
    ).scalar_one_or_none()
    if dataset is None:
        raise AppException(code=404, msg="Account detection dataset version not found.")
    if dataset.source_label_count <= 0:
        raise AppException(code=409, msg="Account detection dataset version has no approved labels.")
    if dataset.status not in {"candidate", "approved", "training_ready"}:
        raise AppException(code=409, msg="Account detection dataset version is not eligible for training.")
    verified_artifact_hash = _verify_artifact_hash(artifact_uri, artifact_hash)
    metrics = {
        **metrics,
        "dataset_fingerprint": dataset.data_fingerprint,
        "source_label_count": dataset.source_label_count,
    }
    gates = evaluate_account_model_activation_gates(metrics, approver_ids=[])
    record = AccountDetectionModelVersion(
        model_version=model_version,
        dataset_version_id=dataset_version_id,
        artifact_uri=artifact_uri,
        artifact_hash=verified_artifact_hash,
        metrics_json=json.dumps(metrics, ensure_ascii=False),
        gates_json=json.dumps(gates, ensure_ascii=False),
        status="shadow",
        created_by=operator_id,
    )
    session.add(record)
    await session.flush()
    return _model_projection(record)


async def list_account_detection_models(session: AsyncSession) -> list[dict[str, Any]]:
    """Return registered account model versions."""

    rows = (
        await session.execute(
            select(AccountDetectionModelVersion).order_by(AccountDetectionModelVersion.created_at.desc())
        )
    ).scalars().all()
    return [_model_projection(row) for row in rows]


async def approve_account_detection_model(
    session: AsyncSession,
    *,
    model_version: str,
    approver_id: int,
    approval_notes: str = "",
) -> dict[str, Any] | None:
    """Record one immutable active-administrator approval for a shadow model."""

    await _require_active_admin(session, approver_id)
    record = (
        await session.execute(
            select(AccountDetectionModelVersion).where(
                AccountDetectionModelVersion.model_version == model_version
            )
        )
    ).scalar_one_or_none()
    if record is None:
        return None
    if record.status not in {"shadow", "approved"}:
        raise AppException(code=409, msg="Only a shadow or approved account model can receive approvals.")
    existing = (
        await session.execute(
            select(AccountDetectionModelApproval).where(
                AccountDetectionModelApproval.model_version == model_version,
                AccountDetectionModelApproval.approver_id == int(approver_id),
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        return {
            "approval": _approval_projection(existing),
            "approval_recorded": False,
            "active_approval_count": await _approval_count(session, model_version=model_version),
        }
    approval = AccountDetectionModelApproval(
        approval_id=f"account-model-approval-{uuid4().hex[:16]}",
        model_version=model_version,
        approver_id=int(approver_id),
        artifact_hash=record.artifact_hash,
        metrics_fingerprint=_metrics_fingerprint(_loads(record.metrics_json)),
        approval_notes=approval_notes,
    )
    session.add(approval)
    await session.flush()
    count = await _approval_count(session, model_version=model_version)
    if count >= 2 and record.status == "shadow":
        record.status = "approved"
    await session.flush()
    return {
        "approval": _approval_projection(approval),
        "approval_recorded": True,
        "active_approval_count": count,
        "ready_for_activation": count >= 2,
    }


async def activate_account_detection_model(
    session: AsyncSession,
    *,
    model_version: str,
    operator_id: int,
    activation_notes: str = "",
) -> dict[str, Any] | None:
    """Activate a candidate model only when persisted gates and admin approvals pass."""

    record = (
        await session.execute(
            select(AccountDetectionModelVersion).where(
                AccountDetectionModelVersion.model_version == model_version
            )
        )
    ).scalar_one_or_none()
    if record is None:
        return None
    persisted_metrics = _loads(record.metrics_json)
    await _require_active_admin(session, operator_id)
    approver_ids = await _active_model_approval_ids(session, model_version=model_version)
    await _require_recorded_approvals(approver_ids=approver_ids, operator_id=operator_id)
    decision = evaluate_account_model_activation_gates(persisted_metrics, approver_ids=approver_ids)
    if decision["activation_allowed"]:
        record.status = "active"
        existing = (
            await session.execute(
                select(AccountDetectionModelActivation).where(
                    AccountDetectionModelActivation.model_family == "chinese_account_detection"
                )
            )
        ).scalar_one_or_none()
        payload = {
            "decision": decision,
            "approver_ids": approver_ids,
            "activation_notes": activation_notes,
        }
        if existing is None:
            session.add(
                AccountDetectionModelActivation(
                    model_family="chinese_account_detection",
                    model_version=model_version,
                    activation_json=json.dumps(payload, ensure_ascii=False),
                    activated_by=operator_id,
                )
            )
        else:
            existing.model_version = model_version
            existing.activation_json = json.dumps(payload, ensure_ascii=False)
            existing.activated_by = operator_id
    record.gates_json = json.dumps(decision, ensure_ascii=False)
    await session.flush()
    return {**_model_projection(record), "activation_decision": decision}


def _verify_artifact_hash(artifact_uri: str, expected_hash: str) -> str:
    if not artifact_uri:
        raise AppException(code=400, msg="Account model artifact_uri is required.")
    if not expected_hash:
        raise AppException(code=400, msg="Account model artifact_hash is required.")
    path = Path(artifact_uri)
    if path.is_dir():
        path = path / "checkpoint.pt"
    if not path.is_file():
        raise AppException(code=404, msg="Account model artifact file not found.")
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    actual = digest.hexdigest()
    expected = expected_hash.strip().split()[0].lower()
    if actual.lower() != expected:
        raise AppException(code=409, msg="Account model artifact_hash does not match artifact bytes.")
    return actual


async def _require_active_admin(session: AsyncSession, user_id: int) -> None:
    row = (
        await session.execute(
            select(User.id).where(
                User.id == int(user_id),
                User.role == "admin",
                User.is_active.is_(True),
            )
        )
    ).scalar_one_or_none()
    if row is None:
        raise AppException(code=403, msg="Account model governance requires an active administrator.")


def _require_recorded_approvals(
    approver_ids: list[int],
    operator_id: int,
) -> None:
    distinct = {int(value) for value in approver_ids if int(value) > 0}
    if int(operator_id) not in distinct:
        raise AppException(code=403, msg="The activating administrator must have recorded approval.")
    if len(distinct) < 2:
        raise AppException(code=403, msg="Account model activation requires two distinct active administrator approval records.")


async def _active_model_approval_ids(session: AsyncSession, *, model_version: str) -> list[int]:
    rows = (
        await session.execute(
            select(AccountDetectionModelApproval.approver_id)
            .join(User, User.id == AccountDetectionModelApproval.approver_id)
            .where(
                AccountDetectionModelApproval.model_version == model_version,
                User.role == "admin",
                User.is_active.is_(True),
            )
        )
    ).scalars().all()
    return sorted({int(value) for value in rows})


async def _approval_count(session: AsyncSession, *, model_version: str) -> int:
    return len(await _active_model_approval_ids(session, model_version=model_version))


def _metrics_fingerprint(metrics: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(metrics, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()


def _approval_projection(record: AccountDetectionModelApproval) -> dict[str, Any]:
    return {
        "approval_id": record.approval_id,
        "model_version": record.model_version,
        "approver_id": record.approver_id,
        "artifact_hash": record.artifact_hash,
        "metrics_fingerprint": record.metrics_fingerprint,
        "approval_notes": record.approval_notes,
    }


def _model_projection(record: AccountDetectionModelVersion) -> dict[str, Any]:
    return {
        "model_version": record.model_version,
        "dataset_version_id": record.dataset_version_id,
        "artifact_uri": record.artifact_uri,
        "artifact_hash": record.artifact_hash,
        "metrics": _loads(record.metrics_json),
        "gates": _loads(record.gates_json),
        "status": record.status,
    }


def _loads(payload: str) -> Any:
    try:
        return json.loads(payload)
    except json.JSONDecodeError:
        return {}
