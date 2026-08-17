"""Product-facing V2 Event Review Case API."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError

from app.core.analysis.sse import parse_last_event_id
from app.core.security import get_current_user, require_roles
from app.db.mongodb import get_mongo_db
from app.db.mysql import get_db
from app.models.user import User
from app.schemas.review_case import (
    CaseActivity,
    DecisionConfirmRequest,
    DecisionDraftUpsert,
    EvidenceAnnotationCreate,
    EvidenceAssessment,
    ReviewRequestCreate,
)
from app.services.review_case_service import ReviewCaseConflict, ReviewCaseService
from app.utils.response import success


router = APIRouter()
require_case_reader = get_current_user
require_case_editor = require_roles("admin", "analyst")


def get_review_case_service(
    db: AsyncSession = Depends(get_db),
    mongo_db: Any = Depends(get_mongo_db),
) -> ReviewCaseService:
    return ReviewCaseService(db=db, mongo_db=mongo_db)


@router.get("/latest")
async def latest_case(
    service: ReviewCaseService = Depends(get_review_case_service),
    _current_user: User = Depends(require_case_reader),
):
    return await _read_response(service.latest)


@router.get("")
async def search_cases(
    query: str = Query("", max_length=256),
    limit: int = Query(20, ge=1, le=100),
    service: ReviewCaseService = Depends(get_review_case_service),
    _current_user: User = Depends(require_case_reader),
):
    try:
        result = await service.search(query=query, limit=limit)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return success(data=result.model_dump(mode="json"))


@router.get("/{case_id}")
async def get_case(
    case_id: str,
    service: ReviewCaseService = Depends(get_review_case_service),
    _current_user: User = Depends(require_case_reader),
):
    return await _read_response(lambda: service.detail(case_id))


@router.get("/{case_id}/evidence")
async def get_case_evidence(
    case_id: str,
    assessment: EvidenceAssessment = Query(EvidenceAssessment.UNRESOLVED),
    cursor: int = Query(0, ge=0),
    limit: int = Query(40, ge=1, le=100),
    service: ReviewCaseService = Depends(get_review_case_service),
    _current_user: User = Depends(require_case_reader),
):
    if assessment == EvidenceAssessment.UNRESOLVED and cursor == 0 and limit == 40:
        operation = lambda: service.evidence(case_id)
    else:
        operation = lambda: service.evidence(
            case_id,
            assessment=assessment,
            cursor=cursor,
            limit=limit,
        )
    return await _read_response(operation)


@router.get("/{case_id}/teacher-audit")
async def get_teacher_audit(
    case_id: str,
    service: ReviewCaseService = Depends(get_review_case_service),
    _current_user: User = Depends(require_case_reader),
):
    return await _read_response(lambda: service.teacher_audit(case_id))


@router.post("/{case_id}/review-requests")
async def request_case_review(
    case_id: str,
    body: ReviewRequestCreate,
    service: ReviewCaseService = Depends(get_review_case_service),
    current_user: User = Depends(require_case_editor),
):
    return await _write_response(
        lambda: service.request_review(case_id, body, actor=current_user),
        db=service.db,
    )


@router.post("/{case_id}/evidence-annotations")
async def annotate_case_evidence(
    case_id: str,
    body: EvidenceAnnotationCreate,
    service: ReviewCaseService = Depends(get_review_case_service),
    current_user: User = Depends(require_case_editor),
):
    return await _write_response(
        lambda: service.add_annotation(case_id, body, actor=current_user),
        db=service.db,
    )


@router.put("/{case_id}/decision-draft")
async def save_case_decision_draft(
    case_id: str,
    body: DecisionDraftUpsert,
    service: ReviewCaseService = Depends(get_review_case_service),
    current_user: User = Depends(require_case_editor),
):
    return await _write_response(
        lambda: service.save_draft(case_id, body, actor=current_user),
        db=service.db,
    )


@router.post("/{case_id}/decisions/confirm")
async def confirm_case_decision(
    case_id: str,
    body: DecisionConfirmRequest,
    service: ReviewCaseService = Depends(get_review_case_service),
    current_user: User = Depends(require_case_editor),
):
    return await _write_response(
        lambda: service.confirm_decision(case_id, body, actor=current_user),
        db=service.db,
    )


@router.get("/{case_id}/activities")
async def list_case_activities(
    case_id: str,
    after_id: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    service: ReviewCaseService = Depends(get_review_case_service),
    _current_user: User = Depends(require_case_reader),
):
    return await _read_response(
        lambda: service.activities(case_id, after_id=after_id, limit=limit)
    )


@router.get("/{case_id}/events/stream")
async def stream_case_events(
    case_id: str,
    last_event_id: str | None = Header(default=None, alias="Last-Event-ID"),
    after_id: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    service: ReviewCaseService = Depends(get_review_case_service),
    _current_user: User = Depends(require_case_reader),
):
    cursor = parse_last_event_id(last_event_id, fallback=after_id)
    try:
        activities = await service.activities(case_id, after_id=cursor, limit=limit)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return StreamingResponse(
        iter_case_sse_events(activities.items),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache"},
    )


async def _read_response(operation):
    try:
        result = await operation()
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return success(data=result.model_dump(mode="json"))


async def _write_response(operation, *, db: AsyncSession):
    try:
        result = await operation()
        await db.commit()
    except KeyError as exc:
        await db.rollback()
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ReviewCaseConflict as exc:
        await db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(
            status_code=409,
            detail="The case changed while the decision was being confirmed",
        ) from exc
    except ValueError as exc:
        await db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return success(data=result.model_dump(mode="json"))


def format_case_sse_event(activity: CaseActivity) -> str:
    data = {
        "case_id": activity.case_id,
        "action_required": activity.action_required.value,
        "message": activity.summary,
        "occurred_at": activity.occurred_at.isoformat(),
    }
    return (
        f"id: {activity.cursor}\n"
        f"event: {activity.activity_type.value}\n"
        f"data: {json.dumps(data, ensure_ascii=False, sort_keys=True)}\n\n"
    )


async def iter_case_sse_events(activities: list[CaseActivity]) -> AsyncIterator[str]:
    for activity in activities:
        yield format_case_sse_event(activity)


__all__ = [
    "format_case_sse_event",
    "get_review_case_service",
    "iter_case_sse_events",
    "require_case_editor",
    "require_case_reader",
    "router",
]
