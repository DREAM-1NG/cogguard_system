from __future__ import annotations

from fastapi import APIRouter

from app.api.v2 import analysis, authority_sources, cases, review_cases, system_operations

api_router = APIRouter(prefix="/api/v2")
api_router.include_router(
    analysis.router,
    prefix="/governance",
    tags=["internal-governance-v2"],
)
api_router.include_router(
    analysis.execution_router,
    prefix="/analysis",
    tags=["analysis-v2"],
)
api_router.include_router(
    analysis.product_router,
    prefix="/analysis",
    tags=["analysis-product-v2"],
)
api_router.include_router(
    review_cases.router,
    prefix="/review-cases",
    tags=["review-cases-v2"],
)
api_router.include_router(cases.router, prefix="/cases", tags=["cases-v2"])
api_router.include_router(authority_sources.router, prefix="/authority-sources", tags=["authority-sources-v2"])
api_router.include_router(
    system_operations.router,
    prefix="/system",
    tags=["system-operations-v2"],
)


@api_router.get("/health", tags=["system-v2"])
async def health_check_v2():
    return {"status": "ok", "version": "v2"}
