"""Case Workbench v2 API routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from app.core.security import get_current_user_or_local_preview
from app.models.user import User
from app.services.case_workbench_service import CaseWorkbenchService
from app.utils.response import success

router = APIRouter()


def get_case_workbench_service() -> CaseWorkbenchService:
    return CaseWorkbenchService()


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


__all__ = ["get_case_workbench_service", "router"]
