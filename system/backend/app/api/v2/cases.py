"""Case Workbench v2 API routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import HTMLResponse

from app.core.security import get_current_user_or_local_preview
from app.models.user import User
from app.schemas.cases import CaseActionDecisionRequest, CaseCloseoutReviewRequest, CaseFeedbackRequest
from app.services.case_workbench_service import CaseOperationConflict, CaseWorkbenchService
from app.utils.response import success

router = APIRouter()
_case_workbench_service = CaseWorkbenchService()


def get_case_workbench_service() -> CaseWorkbenchService:
    return _case_workbench_service


@router.get("")
async def list_cases(
    event_id: str | None = Query(None),
    service: CaseWorkbenchService = Depends(get_case_workbench_service),
    _current_user: User | None = Depends(get_current_user_or_local_preview),
):
    return success(data=await service.list_cases(event_id=event_id))


@router.get("/{case_id}")
async def get_case(
    case_id: str,
    service: CaseWorkbenchService = Depends(get_case_workbench_service),
    _current_user: User | None = Depends(get_current_user_or_local_preview),
):
    try:
        return success(data=await service.get_case(case_id))
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/{case_id}/reports/{version}.html")
async def get_case_report_html(
    case_id: str,
    version: int,
    service: CaseWorkbenchService = Depends(get_case_workbench_service),
    _current_user: User | None = Depends(get_current_user_or_local_preview),
):
    try:
        return HTMLResponse(content=await service.render_report_html(case_id, version))
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/{case_id}/reports/{version}.pdf")
async def get_case_report_pdf_fallback(
    case_id: str,
    version: int,
    service: CaseWorkbenchService = Depends(get_case_workbench_service),
    _current_user: User | None = Depends(get_current_user_or_local_preview),
):
    try:
        return HTMLResponse(
            content=await service.render_report_html(case_id, version, pdf_fallback=True),
            headers={"Content-Disposition": f'inline; filename="{case_id}-report-{version}.html"'},
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/{case_id}/actions/{action_id}/complete")
async def complete_case_action(
    case_id: str,
    action_id: str,
    request: CaseActionDecisionRequest,
    service: CaseWorkbenchService = Depends(get_case_workbench_service),
    current_user: User | None = Depends(get_current_user_or_local_preview),
):
    try:
        return success(
            data=await service.complete_action(
                case_id,
                action_id,
                actor_id=_actor_id(current_user),
                note=request.note,
            )
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/{case_id}/actions/{action_id}/waive")
async def waive_case_action(
    case_id: str,
    action_id: str,
    request: CaseActionDecisionRequest,
    service: CaseWorkbenchService = Depends(get_case_workbench_service),
    current_user: User | None = Depends(get_current_user_or_local_preview),
):
    try:
        return success(
            data=await service.waive_action(
                case_id,
                action_id,
                actor_id=_actor_id(current_user),
                note=request.note,
            )
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/{case_id}/feedback")
async def submit_case_feedback(
    case_id: str,
    request: CaseFeedbackRequest,
    service: CaseWorkbenchService = Depends(get_case_workbench_service),
    current_user: User | None = Depends(get_current_user_or_local_preview),
):
    try:
        return success(
            data=await service.submit_feedback(case_id, actor_id=_actor_id(current_user), content=request.content)
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/{case_id}/closeout")
async def submit_case_closeout_review(
    case_id: str,
    request: CaseCloseoutReviewRequest,
    service: CaseWorkbenchService = Depends(get_case_workbench_service),
    current_user: User | None = Depends(get_current_user_or_local_preview),
):
    try:
        return success(
            data=await service.submit_closeout_review(
                case_id,
                actor_id=_actor_id(current_user),
                summary=request.summary,
            )
        )
    except CaseOperationConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


def _actor_id(current_user: User | None) -> str:
    return str(getattr(current_user, "username", "") or "local_preview")


__all__ = ["get_case_workbench_service", "router"]
