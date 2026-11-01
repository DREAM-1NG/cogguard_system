from __future__ import annotations

from fastapi import APIRouter

from app.api.v2 import analysis, review_cases, system_operations

api_router = APIRouter(prefix="/api/v2")
api_router.include_router(
    analysis.router,
    prefix="/governance",
    tags=["internal-governance-v2"],
)
api_router.include_router(
    review_cases.router,
    prefix="/review-cases",
    tags=["review-cases-v2"],
)
api_router.include_router(
    system_operations.router,
    prefix="/system",
    tags=["system-operations-v2"],
)


@api_router.get("/health", tags=["system-v2"])
async def health_check_v2():
    return {"status": "ok", "version": "v2"}
