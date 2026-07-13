from __future__ import annotations

from fastapi import APIRouter

from app.api.v2 import analysis

api_router = APIRouter(prefix="/api/v2")
api_router.include_router(analysis.router, prefix="/analysis", tags=["analysis-v2"])


@api_router.get("/health", tags=["system-v2"])
async def health_check_v2():
    return {"status": "ok", "version": "v2"}
