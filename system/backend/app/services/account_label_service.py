"""Service layer for account behavior labels."""

from __future__ import annotations

import json
import hashlib
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.account_labeling import normalize_account_behavior_label
from app.models.account_labeling import (
    AccountBehaviorLabelRecord,
    AccountDetectionCaseRecord,
    AccountLabelBatchItem,
    AccountLabelReviewAssignment,
)
from app.models.user import User
from app.utils.exceptions import AppException

__all__ = [
    "adjudicate_account_label",
    "assign_account_label_review",
    "get_account_label_stats",
    "submit_account_label",
]


async def submit_account_label(
    session: AsyncSession,
    *,
    case_id: str,
    batch_id: str | None,
    behavior_label: str,
    confidence: float,
    evidence_post_ids: list[str],
    reason_tags: list[str],
    notes: str,
    case_fingerprint: str,
    analyst_id: int,
) -> dict[str, Any]:
    """Store an analyst label as submitted evidence, not automatic gold."""

    try:
        normalized = normalize_account_behavior_label(behavior_label)
    except ValueError as exc:
        raise AppException(code=400, msg=str(exc)) from exc
    if not case_fingerprint or not case_fingerprint.strip():
        raise AppException(code=400, msg="Account label case_fingerprint is required.")
    case = await _require_case(session, case_id)
    if case_fingerprint != case.case_fingerprint:
        raise AppException(code=409, msg="Account label case fingerprint does not match the current case.")
    case_post_ids = set(_loads(case.post_ids_json, []))
    case_evidence_ids = set(_loads(case.evidence_post_ids_json, []))
    allowed_evidence_ids = case_post_ids | case_evidence_ids
    unknown_evidence_ids = [post_id for post_id in evidence_post_ids if post_id not in allowed_evidence_ids]
    if unknown_evidence_ids:
        raise AppException(code=400, msg="Account label evidence_post_ids must belong to the case evidence set.")
    batch_item = None
    if batch_id:
        batch_item = await _require_queued_batch_item(session, batch_id=batch_id, case_id=case_id)
    review_required = _requires_independent_review(
        behavior_label=normalized.behavior_label,
        case_fingerprint=case.case_fingerprint,
        reason_tags=reason_tags,
        model_output_json=case.model_output_json,
        batch_item=batch_item,
    )
    label_id = f"account-label-{uuid.uuid4().hex[:16]}"
    record = AccountBehaviorLabelRecord(
        label_id=label_id,
        case_id=case_id,
        batch_id=batch_id,
        behavior_label=normalized.behavior_label,
        training_target=normalized.training_target,
        label_status="submitted" if review_required else "approved",
        analyst_id=analyst_id,
        confidence=confidence,
        evidence_post_ids_json=json.dumps(evidence_post_ids, ensure_ascii=False),
        reason_tags_json=json.dumps(reason_tags, ensure_ascii=False),
        notes=notes,
        case_fingerprint=case.case_fingerprint,
        review_required=review_required,
        second_review_status="pending" if review_required else "not_required",
    )
    session.add(record)
    await session.flush()
    return _label_projection(record)


async def _require_case(session: AsyncSession, case_id: str) -> AccountDetectionCaseRecord:
    record = (
        await session.execute(
            select(AccountDetectionCaseRecord).where(AccountDetectionCaseRecord.case_id == case_id)
        )
    ).scalar_one_or_none()
    if record is None:
        raise AppException(code=404, msg="Account detection case not found.")
    return record


async def _require_queued_batch_item(
    session: AsyncSession,
    *,
    batch_id: str,
    case_id: str,
) -> AccountLabelBatchItem:
    item = (
        await session.execute(
            select(AccountLabelBatchItem).where(
                AccountLabelBatchItem.batch_id == batch_id,
                AccountLabelBatchItem.case_id == case_id,
                AccountLabelBatchItem.status == "queued",
            )
        )
    ).scalar_one_or_none()
    if item is None:
        raise AppException(code=409, msg="Account label must reference a queued case in the selected batch.")
    return item


def _requires_independent_review(
    *,
    behavior_label: str,
    case_fingerprint: str,
    reason_tags: list[str],
    model_output_json: str,
    batch_item: AccountLabelBatchItem | None,
) -> bool:
    """Apply the immutable second-review policy before a label enters training.

    Ordinary human/bot observations are approved by the submitting analyst. A
    stable 10 percent hash sample is independently audited, while abstention,
    explicit risk/conflict/drift evidence, and an acquisition batch's audit
    bucket always wait for a second analyst.
    """

    if behavior_label == "insufficient_evidence":
        return True
    if batch_item is not None and batch_item.selection_bucket == "random_audit":
        return True
    if _deterministic_audit_bucket(case_fingerprint) < 10:
        return True
    normalized_tags = {
        str(tag).strip().lower().replace("-", "_").replace(" ", "_")
        for tag in reason_tags
        if str(tag).strip()
    }
    if normalized_tags & {
        "high_risk",
        "conflict",
        "cross_platform_conflict",
        "drift",
        "drift_alert",
        "ood",
        "model_disagreement",
    }:
        return True
    try:
        model_output = json.loads(model_output_json or "{}")
    except json.JSONDecodeError:
        model_output = {}
    if isinstance(model_output, dict) and any(
        bool(model_output.get(field))
        for field in (
            "requires_second_review",
            "high_risk",
            "cross_platform_conflict",
            "drift_alert",
            "ood",
            "model_disagreement",
        )
    ):
        return True
    return False


def _deterministic_audit_bucket(case_fingerprint: str) -> int:
    """Map a case fingerprint to a stable 0-99 random-audit bucket."""

    digest = hashlib.sha256(case_fingerprint.encode("utf-8")).hexdigest()
    return int(digest[:8], 16) % 100


async def adjudicate_account_label(
    session: AsyncSession,
    *,
    label_id: str,
    approved: bool,
    adjudicator_id: int,
    behavior_label: str | None = None,
    notes: str = "",
    assignment_id: str | None = None,
) -> dict[str, Any] | None:
    """Append an independent adjudication revision for a submitted label.

    The submitted label is immutable.  An adjudication is a new revision that
    points to the submitted label through ``supersedes_id`` and is accepted
    only when the adjudicator owns an active review assignment.
    """

    record = (
        await session.execute(
            select(AccountBehaviorLabelRecord).where(AccountBehaviorLabelRecord.label_id == label_id)
        )
    ).scalar_one_or_none()
    if record is None:
        return None
    if record.analyst_id is not None and int(record.analyst_id) == int(adjudicator_id):
        raise AppException(code=403, msg="An analyst cannot adjudicate their own label.")
    if record.supersedes_id is not None or record.label_status != "submitted":
        raise AppException(code=409, msg="Only the current submitted label revision can be adjudicated.")
    successor = (
        await session.execute(
            select(AccountBehaviorLabelRecord.label_id)
            .where(AccountBehaviorLabelRecord.supersedes_id == record.label_id)
            .limit(1)
        )
    ).scalar_one_or_none()
    if successor is not None:
        raise AppException(code=409, msg="This label already has an immutable adjudication revision.")

    assignment_query = select(AccountLabelReviewAssignment).where(
        AccountLabelReviewAssignment.label_id == record.label_id,
        AccountLabelReviewAssignment.reviewer_id == adjudicator_id,
        AccountLabelReviewAssignment.review_status == "assigned",
    )
    if assignment_id:
        assignment_query = assignment_query.where(
            AccountLabelReviewAssignment.assignment_id == assignment_id
        )
    assignment = (await session.execute(assignment_query)).scalar_one_or_none()
    if assignment is None:
        raise AppException(
            code=409,
            msg="An active review assignment for this label is required before adjudication.",
        )

    adjudicated_label = record.behavior_label
    adjudicated_target = record.training_target
    if behavior_label:
        try:
            normalized = normalize_account_behavior_label(behavior_label)
        except ValueError as exc:
            raise AppException(code=400, msg=str(exc)) from exc
        adjudicated_label = normalized.behavior_label
        adjudicated_target = normalized.training_target
    adjudication_status = "adjudicated" if approved and behavior_label else ("approved" if approved else "rejected")
    if notes:
        adjudication_notes = f"{record.notes}\nAdjudication: {notes}".strip()
    else:
        adjudication_notes = record.notes

    adjudication = AccountBehaviorLabelRecord(
        label_id=f"account-label-{uuid.uuid4().hex[:16]}",
        case_id=record.case_id,
        batch_id=record.batch_id,
        behavior_label=adjudicated_label,
        training_target=adjudicated_target,
        label_status=adjudication_status,
        analyst_id=record.analyst_id,
        confidence=record.confidence,
        evidence_post_ids_json=record.evidence_post_ids_json,
        reason_tags_json=record.reason_tags_json,
        notes=adjudication_notes,
        case_fingerprint=record.case_fingerprint,
        supersedes_id=record.label_id,
        review_required=record.review_required,
        second_review_status="completed",
        adjudicated_by=adjudicator_id,
        adjudicated_at=datetime.now(timezone.utc).replace(tzinfo=None),
    )
    session.add(adjudication)
    assignment.review_status = "completed"
    assignment.completed_at = datetime.now(timezone.utc).replace(tzinfo=None)
    await session.flush()
    return _label_projection(adjudication)


async def assign_account_label_review(
    session: AsyncSession,
    *,
    label_id: str,
    reviewer_id: int,
    assigned_by: int,
) -> dict[str, Any] | None:
    """Create one independent, auditable second-review assignment."""

    record = (
        await session.execute(
            select(AccountBehaviorLabelRecord).where(AccountBehaviorLabelRecord.label_id == label_id)
        )
    ).scalar_one_or_none()
    if record is None:
        return None
    if int(record.analyst_id) == int(reviewer_id):
        raise AppException(code=403, msg="An analyst cannot review their own label.")
    if record.label_status != "submitted" or not record.review_required:
        raise AppException(code=409, msg="This label does not require an active second review assignment.")
    reviewer = (
        await session.execute(
            select(User).where(
                User.id == int(reviewer_id),
                User.is_active.is_(True),
                User.role.in_(("analyst", "admin")),
            )
        )
    ).scalar_one_or_none()
    if reviewer is None:
        raise AppException(code=404, msg="Assigned account label reviewer is not active.")
    current = (
        await session.execute(
            select(AccountLabelReviewAssignment).where(
                AccountLabelReviewAssignment.label_id == label_id,
                AccountLabelReviewAssignment.review_status == "assigned",
            )
        )
    ).scalar_one_or_none()
    if current is not None:
        if current.reviewer_id == int(reviewer_id):
            return _assignment_projection(current)
        raise AppException(code=409, msg="This label already has an active review assignment.")
    assignment = AccountLabelReviewAssignment(
        assignment_id=f"account-label-review-{uuid.uuid4().hex[:16]}",
        label_id=label_id,
        reviewer_id=int(reviewer_id),
        review_round=2,
        review_status="assigned",
        assignment_json=json.dumps(
            {"assigned_by": int(assigned_by), "review_policy": "independent_second_review"},
            ensure_ascii=False,
        ),
    )
    session.add(assignment)
    await session.flush()
    return _assignment_projection(assignment)


async def get_account_label_stats(session: AsyncSession) -> dict[str, Any]:
    """Return label counts by status and behavior label."""

    status_rows = (
        await session.execute(
            select(AccountBehaviorLabelRecord.label_status, func.count()).group_by(
                AccountBehaviorLabelRecord.label_status
            )
        )
    ).all()
    label_rows = (
        await session.execute(
            select(AccountBehaviorLabelRecord.behavior_label, func.count()).group_by(
                AccountBehaviorLabelRecord.behavior_label
            )
        )
    ).all()
    return {
        "status_counts": {str(status): int(count) for status, count in status_rows},
        "behavior_label_counts": {str(label): int(count) for label, count in label_rows},
        "training_policy": "only approved labels with bot/non_bot targets are exported",
    }


def _label_projection(record: AccountBehaviorLabelRecord) -> dict[str, Any]:
    return {
        "label_id": record.label_id,
        "case_id": record.case_id,
        "batch_id": record.batch_id,
        "behavior_label": record.behavior_label,
        "training_target": record.training_target,
        "label_status": record.label_status,
        "analyst_id": record.analyst_id,
        "confidence": record.confidence,
        "evidence_post_ids": _loads(record.evidence_post_ids_json, []),
        "reason_tags": _loads(record.reason_tags_json, []),
        "notes": record.notes,
        "case_fingerprint": record.case_fingerprint,
        "supersedes_id": record.supersedes_id,
        "review_required": record.review_required,
        "second_review_status": record.second_review_status,
    }


def _assignment_projection(record: AccountLabelReviewAssignment) -> dict[str, Any]:
    return {
        "assignment_id": record.assignment_id,
        "label_id": record.label_id,
        "reviewer_id": record.reviewer_id,
        "review_round": record.review_round,
        "review_status": record.review_status,
        "assignment": _loads(record.assignment_json, {}),
        "assigned_at": record.assigned_at.isoformat() if record.assigned_at else None,
        "completed_at": record.completed_at.isoformat() if record.completed_at else None,
    }


def _loads(payload: str, fallback: Any) -> Any:
    try:
        return json.loads(payload)
    except json.JSONDecodeError:
        return fallback
