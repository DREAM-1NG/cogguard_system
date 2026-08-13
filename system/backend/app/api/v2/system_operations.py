"""Authenticated, product-safe system operation endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import require_roles
from app.db.mysql import get_db
from app.models.user import User
from app.schemas.system_operations import (
    ServiceActivationRequest,
    ServiceConfigCreateRequest,
)
from app.services import system_operations_service
from app.utils.response import success


router = APIRouter()


@router.get("/operation-health")
async def get_operation_health(
    _current_user: User = Depends(require_roles("admin", "analyst")),
    db: AsyncSession = Depends(get_db),
):
    return success(data=await system_operations_service.operation_health(db))


@router.get("/services")
async def list_services(
    _current_user: User = Depends(require_roles("admin", "analyst")),
    db: AsyncSession = Depends(get_db),
):
    return success(data=await system_operations_service.list_service_configs(db))


@router.post("/services")
async def create_service(
    body: ServiceConfigCreateRequest,
    current_user: User = Depends(require_roles("admin")),
    db: AsyncSession = Depends(get_db),
):
    try:
        result = await system_operations_service.create_service_config(
            payload=body.model_dump(),
            user_id=int(current_user.id),
            db=db,
        )
        await db.commit()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return success(data=result)


@router.post("/services/{service_id}/activation")
async def activate_service(
    service_id: int,
    body: ServiceActivationRequest,
    _current_user: User = Depends(require_roles("admin")),
    db: AsyncSession = Depends(get_db),
):
    try:
        result = await system_operations_service.activate_service_config(
            service_id=service_id,
            enabled=body.enabled,
            db=db,
        )
        await db.commit()
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return success(data=result)


@router.post("/services/{service_id}/connection-check")
async def check_service_connection(
    service_id: int,
    _current_user: User = Depends(require_roles("admin")),
    db: AsyncSession = Depends(get_db),
):
    try:
        result = await system_operations_service.check_service_config(service_id, db)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return success(data=result)


__all__ = ["router"]
