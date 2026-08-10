"""Service layer for account-detection active learning."""

from __future__ import annotations

import asyncio
import json
import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.account_active_learning import select_account_detection_label_batch
from app.core.account_labeling import (
    AccountDetectionCase,
    account_scope_key,
    build_account_detection_cases,
)
from app.core.trained_bot_detection import run_trained_botrhg_detection
from app.db.mongodb import get_mongo_db
from app.models.account_labeling import AccountDetectionCaseRecord, AccountLabelBatch, AccountLabelBatchItem
from app.services.account_model_runtime_service import get_active_account_model
from app.services.event_data import load_event_posts

__all__ = [
    "create_account_label_batch",
    "get_account_label_batch",
    "list_account_label_queue",
]


async def create_account_label_batch(
    session: AsyncSession,
    *,
    event_id: str | None,
    platform: str | None,
    budget: int,
    cold_start: bool,
    operator_id: int,
) -> dict[str, Any]:
    """Build cases from Mongo posts, select a label batch, and persist it."""

    posts = await load_event_posts(get_mongo_db(), event_id=event_id, platform=platform)
    cases = build_account_detection_cases(posts, event_id=event_id, platform=platform)
    model_outputs = await _model_outputs(posts)
    approved_case_ids = await _approved_case_ids(session)
    selected = select_account_detection_label_batch(
        cases,
        model_outputs=model_outputs,
        approved_case_ids=approved_case_ids,
        budget=budget,
        cold_start=cold_start or not model_outputs,
    )
    batch_id = f"account-label-batch-{uuid.uuid4().hex[:16]}"

    await _upsert_cases(session, cases, model_outputs)
    session.add(
        AccountLabelBatch(
            batch_id=batch_id,
            strategy=str(selected["strategy"]),
            status="open",
            budget=budget,
            scope_json=json.dumps({"event_id": event_id, "platform": platform}, ensure_ascii=False),
            selection_manifest_json=json.dumps(selected["manifest"], ensure_ascii=False),
            created_by=operator_id,
        )
    )
    for item in selected["items"]:
        session.add(
            AccountLabelBatchItem(
                batch_id=batch_id,
                case_id=item["case_id"],
                account_id=item["account_id"],
                platform=item["platform"],
                event_id=item["event_id"],
                priority_rank=item["priority_rank"],
                selection_bucket=item["selection_bucket"],
                acquisition_scores_json=json.dumps(item["scores"], ensure_ascii=False),
                status="queued",
            )
        )
    await session.flush()
    return {
        **selected,
        "batch_id": batch_id,
        "scope": {"event_id": event_id, "platform": platform},
    }


async def get_account_label_batch(session: AsyncSession, batch_id: str) -> dict[str, Any] | None:
    """Return one persisted label batch."""

    batch = (
        await session.execute(select(AccountLabelBatch).where(AccountLabelBatch.batch_id == batch_id))
    ).scalar_one_or_none()
    if batch is None:
        return None
    items = (
        await session.execute(
            select(AccountLabelBatchItem)
            .where(AccountLabelBatchItem.batch_id == batch_id)
            .order_by(AccountLabelBatchItem.priority_rank.asc())
        )
    ).scalars().all()
    return {
        "batch_id": batch.batch_id,
        "strategy": batch.strategy,
        "status": batch.status,
        "budget": batch.budget,
        "scope": _loads(batch.scope_json),
        "manifest": _loads(batch.selection_manifest_json),
        "items": [_batch_item_projection(item) for item in items],
    }


async def list_account_label_queue(
    session: AsyncSession,
    *,
    batch_id: str | None = None,
    limit: int = 100,
) -> list[dict[str, Any]]:
    """Return queued account-labeling cases."""

    statement = select(AccountLabelBatchItem).where(AccountLabelBatchItem.status == "queued")
    if batch_id:
        statement = statement.where(AccountLabelBatchItem.batch_id == batch_id)
    statement = statement.order_by(AccountLabelBatchItem.priority_rank.asc()).limit(limit)
    items = (await session.execute(statement)).scalars().all()
    return [_batch_item_projection(item) for item in items]


async def _model_outputs(posts: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    if not posts:
        return {}
    active_model = await get_active_account_model()
    if active_model is None:
        return {}
    grouped: dict[str, list[dict[str, Any]]] = {}
    for post in posts:
        platform = str(post.get("platform") or "unknown").strip().lower()
        grouped.setdefault(platform, []).append(post)

    outputs: dict[str, dict[str, Any]] = {}
    for platform, scoped_posts in grouped.items():
        result = await asyncio.to_thread(
            run_trained_botrhg_detection,
            scoped_posts,
            active_model,
            allow_legacy_fallback=False,
        )
        if not result:
            continue
        for row in result.get("accounts", []):
            account_id = str(row.get("account_id") or "").strip()
            if account_id:
                outputs[account_scope_key(platform, account_id)] = {
                    **row,
                    "platform": platform,
                }
    return outputs


async def _approved_case_ids(session: AsyncSession) -> set[str]:
    from app.models.account_labeling import AccountBehaviorLabelRecord

    rows = (
        await session.execute(
            select(AccountBehaviorLabelRecord.case_id).where(
                AccountBehaviorLabelRecord.label_status.in_(("approved", "adjudicated"))
            )
        )
    ).scalars().all()
    return {str(row) for row in rows}


async def _upsert_cases(
    session: AsyncSession,
    cases: list[AccountDetectionCase],
    model_outputs: dict[str, dict[str, Any]],
) -> None:
    existing = (
        await session.execute(
            select(AccountDetectionCaseRecord.case_id).where(
                AccountDetectionCaseRecord.case_id.in_([case.case_id for case in cases])
            )
        )
    ).scalars().all()
    existing_ids = {str(case_id) for case_id in existing}
    for case in cases:
        if case.case_id in existing_ids:
            continue
        session.add(
            AccountDetectionCaseRecord(
                case_id=case.case_id,
                account_id=case.account_id,
                platform=case.platform,
                event_id=case.event_id,
                author_name=case.author_name,
                case_fingerprint=case.case_fingerprint,
                post_ids_json=json.dumps(case.post_ids, ensure_ascii=False),
                evidence_post_ids_json=json.dumps(case.evidence_post_ids, ensure_ascii=False),
                payload_json=json.dumps(case.to_dict(), ensure_ascii=False),
                model_output_json=json.dumps(
                    model_outputs.get(account_scope_key(case.platform, case.account_id), {}),
                    ensure_ascii=False,
                ),
            )
        )


def _batch_item_projection(item: AccountLabelBatchItem) -> dict[str, Any]:
    return {
        "batch_id": item.batch_id,
        "case_id": item.case_id,
        "account_id": item.account_id,
        "platform": item.platform,
        "event_id": item.event_id,
        "priority_rank": item.priority_rank,
        "selection_bucket": item.selection_bucket,
        "acquisition_scores": _loads(item.acquisition_scores_json),
        "status": item.status,
    }


def _loads(payload: str) -> Any:
    try:
        return json.loads(payload)
    except json.JSONDecodeError:
        return {}
