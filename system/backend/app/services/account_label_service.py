"""Service layer for account behavior labels."""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.account_labeling import normalize_account_behavior_label
from app.models.account_labeling import AccountBehaviorLabelRecord, AccountDetectionCaseRecord, AccountLabelBatchItem
from app.utils.exceptions import AppException

__all__ = [
    "adjudicate_account_label",
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
    case = await _require_case(session, case_id)
    if case_fingerprint and case_fingerprint != case.case_fingerprint:
        raise AppException(code=409, msg="Account label case fingerprint does not match the current case.")
    case_post_ids = set(_loads(case.post_ids_json, []))
    case_evidence_ids = set(_loads(case.evidence_post_ids_json, []))
    allowed_evidence_ids = case_post_ids | case_evidence_ids
    unknown_evidence_ids = [post_id for post_id in evidence_post_ids if post_id not in allowed_evidence_ids]
    if unknown_evidence_ids:
        raise AppException(code=400, msg="Account label evidence_post_ids must belong to the case evidence set.")
    if batch_id:
        await _require_queued_batch_item(session, batch_id=batch_id, case_id=case_id)
    label_id = f"account-label-{uuid.uuid4().hex[:16]}"
    record = AccountBehaviorLabelRecord(
        label_id=label_id,
        case_id=case_id,
        batch_id=batch_id,
        behavior_label=normalized.behavior_label,
        training_target=normalized.training_target,
        label_status="submitted",
        analyst_id=analyst_id,
        confidence=confidence,
        evidence_post_ids_json=json.dumps(evidence_post_ids, ensure_ascii=False),
        reason_tags_json=json.dumps(reason_tags, ensure_ascii=False),
        notes=notes,
        case_fingerprint=case.case_fingerprint,
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


async def _require_queued_batch_item(session: AsyncSession, *, batch_id: str, case_id: str) -> None:
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


async def adjudicate_account_label(
    session: AsyncSession,
    *,
    label_id: str,
    approved: bool,
    adjudicator_id: int,
    behavior_label: str | None = None,
    notes: str = "",
) -> dict[str, Any] | None:
    """Approve or reject a submitted label."""

    record = (
        await session.execute(
            select(AccountBehaviorLabelRecord).where(AccountBehaviorLabelRecord.label_id == label_id)
        )
    ).scalar_one_or_none()
    if record is None:
        return None
    if behavior_label:
        try:
            normalized = normalize_account_behavior_label(behavior_label)
        except ValueError as exc:
            raise AppException(code=400, msg=str(exc)) from exc
        record.behavior_label = normalized.behavior_label
        record.training_target = normalized.training_target
    record.label_status = "adjudicated" if approved and behavior_label else ("approved" if approved else "rejected")
    record.adjudicated_by = adjudicator_id
    record.adjudicated_at = datetime.utcnow()
    if notes:
        record.notes = f"{record.notes}\nAdjudication: {notes}".strip()
    await session.flush()
    return _label_projection(record)


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
    }


def _loads(payload: str, fallback: Any) -> Any:
    try:
        return json.loads(payload)
    except json.JSONDecodeError:
        return fallback
