from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.analysis.executor import AnalysisExecutor, default_analysis_engine_ports
from app.core.analysis.registry import (
    AnalysisRegistry,
    SEMANTIC_ARTIFACT_KEY,
    SEMANTIC_PAGE_READ_MODEL_ARTIFACT_KEY,
    SqlAlchemyAnalysisStore,
)
from app.core.analysis.query_result_cache import build_query_cache_key, get_or_build_query_result
from app.core.analysis.sse import iter_sse_events, parse_last_event_id
from app.core.semantic.page_projection import (
    SEMANTIC_STATIC_PAGE_VIEWS,
    SemanticPageView,
    build_semantic_page_projection,
    build_semantic_page_read_model,
    build_semantic_workspace_projection,
    read_semantic_page_read_model,
    read_semantic_workspace_read_model,
)
from app.core.security import require_roles
from app.config import settings
from app.db.mongodb import get_mongo_db
from app.db.mysql import get_db
from app.models.user import User
from app.schemas.analysis import (
    AnalysisRunCreateRequest,
    AnalysisSnapshotCreateRequest,
    CanonicalVerdictApprovalRequest,
    ModelActivationRequest,
    ModelCandidateApprovalRequest,
    ModelRollbackRequest,
    ModelVersionCreateRequest,
    ReviewFeedbackCreateRequest,
)
from app.services import analysis_governance_service
from app.utils.response import success

router = APIRouter()
execution_router = APIRouter()
product_router = APIRouter()

def get_analysis_registry(
    db: AsyncSession = Depends(get_db),
    mongo_db: Any = Depends(get_mongo_db),
) -> AnalysisRegistry:
    return AnalysisRegistry(mongo_db=mongo_db, store=SqlAlchemyAnalysisStore(db))


def get_analysis_executor(
    registry: AnalysisRegistry = Depends(get_analysis_registry),
) -> AnalysisExecutor:
    return AnalysisExecutor(registry=registry, engines=default_analysis_engine_ports())


@execution_router.post("/snapshots")
async def create_snapshot(
    body: AnalysisSnapshotCreateRequest,
    registry: AnalysisRegistry = Depends(get_analysis_registry),
    current_user: User = Depends(require_roles("admin", "analyst")),
):
    try:
        snapshot = await registry.create_event_snapshot(
            event_id=body.event_id,
            core_window=body.core_window,
            context_window=body.context_window,
            platform=body.platform,
            created_by=int(current_user.id),
        )
    except (KeyError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return success(data=snapshot.model_dump(mode="json"))


@execution_router.post("/runs")
async def create_run(
    body: AnalysisRunCreateRequest,
    registry: AnalysisRegistry = Depends(get_analysis_registry),
    current_user: User = Depends(require_roles("admin", "analyst")),
):
    return success(
        data=await registry.create_run(
            event_id=body.event_id,
            snapshot_id=body.snapshot_id,
            requested_stages=body.requested_stages,
            options=body.options,
            created_by=int(current_user.id),
        )
    )


@execution_router.post("/runs/{run_id}/execute")
async def execute_run(
    run_id: str,
    executor: AnalysisExecutor = Depends(get_analysis_executor),
    _current_user: User = Depends(require_roles("admin", "analyst")),
):
    try:
        return success(data=await executor.execute_run(run_id))
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/runs/{run_id}")
async def get_run(
    run_id: str,
    registry: AnalysisRegistry = Depends(get_analysis_registry),
    _current_user: User = Depends(require_roles("admin")),
):
    run = await registry.get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Analysis run not found")
    return success(data=run)


@router.get("/runs/{run_id}/artifacts/{artifact_key:path}")
@product_router.get("/runs/{run_id}/artifacts/{artifact_key:path}")
async def get_run_artifact(
    run_id: str,
    artifact_key: str,
    registry: AnalysisRegistry = Depends(get_analysis_registry),
    _current_user: User = Depends(require_roles("admin", "analyst")),
):
    try:
        payload = await registry.load_run_artifact(run_id, artifact_key)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return success(data=payload)


@product_router.get("/events/{event_id}/semantic")
async def get_event_semantic_projection(
    event_id: str,
    registry: AnalysisRegistry = Depends(get_analysis_registry),
    _current_user: User = Depends(require_roles("admin", "analyst")),
):
    return success(data=await _event_semantic_projection(event_id, registry))


@product_router.get("/events/{event_id}/semantic/views/{view}")
async def get_semantic_page_projection(
    event_id: str,
    view: SemanticPageView,
    page: int = Query(1, ge=1),
    page_size: int = Query(40, ge=1, le=100),
    registry: AnalysisRegistry = Depends(get_analysis_registry),
    _current_user: User = Depends(require_roles("admin", "analyst")),
):
    """Return one bounded semantic readout for the Event Review subpages."""
    return success(
        data=await _event_semantic_page_projection(
            event_id,
            registry,
            view=view,
            page=page,
            page_size=page_size,
        )
    )


@product_router.get("/events/{event_id}/semantic/workspace")
async def get_semantic_workspace_projection(
    event_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(40, ge=1, le=40),
    layer: str = Query("all"),
    platforms: str | None = Query(None),
    date: str | None = Query(None),
    keyword: str | None = Query(None),
    topic: str | None = Query(None),
    sentiment: str | None = Query(None),
    stance: str | None = Query(None),
    entity: str | None = Query(None),
    registry: AnalysisRegistry = Depends(get_analysis_registry),
    _current_user: User = Depends(require_roles("admin", "analyst")),
):
    """Return one linked, bounded Semantic Evidence Workspace projection."""
    filters = _semantic_workspace_filters(
        layer=layer,
        platforms=platforms,
        date=date,
        keyword=keyword,
        topic=topic,
        sentiment=sentiment,
        stance=stance,
        entity=entity,
    )
    return success(
        data=await _event_semantic_workspace_projection(
            event_id,
            registry,
            filters=filters,
            page=page,
            page_size=page_size,
        )
    )


async def _event_semantic_projection(event_id: str, registry: AnalysisRegistry) -> dict[str, Any]:
    try:
        candidates = await registry.list_semantic_artifact_candidates(event_id)
    except Exception:
        return _semantic_projection(
            event_id=event_id,
            status="blocked",
            blocking_reason="semantic_artifact_lookup_failed",
        )
    if not candidates:
        return _semantic_projection(
            event_id=event_id,
            status="not_found",
            blocking_reason="semantic_artifact_not_found",
        )

    blocked: dict[str, Any] | None = None
    current_snapshot_cache: dict[tuple[str, str, str, str, str], Any] = {}
    for run in candidates:
        run_id = str(run.get("run_id") or "")
        snapshot_id = _optional_text(run.get("snapshot_id"))
        try:
            artifact = await registry.load_run_artifact(run_id, SEMANTIC_ARTIFACT_KEY)
        except ValueError as exc:
            reason = (
                "semantic_artifact_integrity_failed"
                if "hash mismatch" in str(exc).lower()
                else "semantic_artifact_load_failed"
            )
        except KeyError:
            reason = "semantic_artifact_not_found"
        except Exception:
            reason = "semantic_artifact_load_failed"
        else:
            if _is_ready_semantic_artifact(artifact):
                freshness_reason = await _semantic_artifact_freshness(
                    event_id=event_id,
                    run=run,
                    snapshot_fingerprint=_semantic_artifact_snapshot_fingerprint(artifact),
                    registry=registry,
                    current_snapshot_cache=current_snapshot_cache,
                )
                if freshness_reason is None:
                    return _semantic_projection(
                        event_id=event_id,
                        run_id=run_id,
                        snapshot_id=snapshot_id,
                        status="ready",
                        blocking_reason=None,
                        artifact=artifact,
                    )
                reason = freshness_reason
            else:
                payload = artifact if isinstance(artifact, dict) else {}
                reason = _optional_text(payload.get("blocking_reason")) or "semantic_artifact_not_ready"

        if blocked is None:
            blocked = _semantic_projection(
                event_id=event_id,
                run_id=run_id,
                snapshot_id=snapshot_id,
                status="blocked",
                blocking_reason=reason,
            )

    return blocked or _semantic_projection(
        event_id=event_id,
        status="not_found",
        blocking_reason="semantic_artifact_not_found",
    )


async def _event_semantic_page_projection(
    event_id: str,
    registry: AnalysisRegistry,
    *,
    view: SemanticPageView,
    page: int,
    page_size: int,
) -> dict[str, Any]:
    """Read aggregate pages from the compact artifact, with legacy fallback.

    The persisted read model is written in the same run as the complete
    semantic artifact and pins its source hash. Existing runs keep using the
    original verified artifact path until they are recomputed.
    """
    if view not in SEMANTIC_STATIC_PAGE_VIEWS:
        projection = await _event_semantic_projection(event_id, registry)
        return await _semantic_page_projection(projection, view=view, page=page, page_size=page_size)

    try:
        candidates = await registry.list_semantic_artifact_candidates(event_id)
    except Exception:
        return _semantic_page_response(
            event_id=event_id,
            view=view,
            status="blocked",
            blocking_reason="semantic_artifact_lookup_failed",
        )

    current_snapshot_cache: dict[tuple[str, str, str, str, str], Any] = {}
    for run in candidates:
        run_id = str(run.get("run_id") or "")
        snapshot_id = _optional_text(run.get("snapshot_id"))
        source_artifact_sha256 = _semantic_result_artifact_sha256(run)
        if not run_id or not source_artifact_sha256:
            continue
        try:
            read_model = await registry.load_run_artifact(run_id, SEMANTIC_PAGE_READ_MODEL_ARTIFACT_KEY)
        except (KeyError, ValueError, TypeError):
            continue
        except Exception:
            continue
        if not isinstance(read_model, dict):
            continue
        compact = read_semantic_page_read_model(
            read_model,
            view=view,
            expected_source_artifact_sha256=source_artifact_sha256,
        )
        if compact is None:
            continue
        freshness_reason = await _semantic_artifact_freshness(
            event_id=event_id,
            run=run,
            snapshot_fingerprint=_optional_text(read_model.get("snapshot_fingerprint")),
            registry=registry,
            current_snapshot_cache=current_snapshot_cache,
        )
        if freshness_reason is None:
            return _semantic_page_response(
                event_id=event_id,
                run_id=run_id,
                snapshot_id=snapshot_id,
                view=view,
                status="ready",
                blocking_reason=None,
                **compact,
            )

    # Older artifacts do not contain a read model. Preserve their page contract
    # and integrity checks while keeping new artifacts on the small-payload path.
    projection = await _event_semantic_projection(event_id, registry)
    legacy_read_model = await _backfill_semantic_page_read_model(
        projection,
        candidates=candidates,
        registry=registry,
    )
    if isinstance(legacy_read_model, dict):
        compact = read_semantic_page_read_model(
            legacy_read_model,
            view=view,
            expected_source_artifact_sha256=_optional_text(legacy_read_model.get("source_artifact_sha256")),
        )
        if compact is not None:
            return _semantic_page_response(
                event_id=projection.get("event_id"),
                run_id=projection.get("run_id"),
                snapshot_id=projection.get("snapshot_id"),
                view=view,
                status=str(projection.get("status") or "not_found"),
                blocking_reason=_optional_text(projection.get("blocking_reason")) or None,
                **compact,
            )
    return await _semantic_page_projection(projection, view=view, page=page, page_size=page_size)


async def _event_semantic_workspace_projection(
    event_id: str,
    registry: AnalysisRegistry,
    *,
    filters: dict[str, Any],
    page: int,
    page_size: int,
) -> dict[str, Any]:
    """Read the compact workspace first, then recompute selected linked facets.

    An unfiltered workspace is fully available from the persisted read model.
    When an analyst selects a facet, the immutable source artifact is read on
    the server to preserve exact joint filtering without moving raw layers to
    the browser.
    """
    selection = await _select_current_semantic_workspace_read_model(event_id, registry)
    if selection is not None:
        run, compact = selection
        if not _has_semantic_workspace_filters(filters):
            return _semantic_workspace_response(
                event_id=event_id,
                run_id=run.get("run_id"),
                snapshot_id=run.get("snapshot_id"),
                status="ready",
                blocking_reason=None,
                **compact,
            )
        return await _semantic_workspace_response_from_read_model(
            event_id=event_id,
            run=run,
            compact=compact,
            filters=filters,
            page=page,
            page_size=page_size,
            registry=registry,
        )

    projection = await _event_semantic_projection(event_id, registry)
    if not _has_semantic_workspace_filters(filters):
        try:
            candidates = await registry.list_semantic_artifact_candidates(event_id)
        except Exception:
            candidates = []
        legacy_read_model = await _backfill_semantic_page_read_model(
            projection,
            candidates=candidates,
            registry=registry,
        )
        if isinstance(legacy_read_model, dict):
            compact = read_semantic_workspace_read_model(
                legacy_read_model,
                expected_source_artifact_sha256=_optional_text(legacy_read_model.get("source_artifact_sha256")),
            )
            if compact is not None:
                return _semantic_workspace_response(
                    event_id=projection.get("event_id"),
                    run_id=projection.get("run_id"),
                    snapshot_id=projection.get("snapshot_id"),
                    status=str(projection.get("status") or "not_found"),
                    blocking_reason=_optional_text(projection.get("blocking_reason")) or None,
                    **compact,
                )
    return await _semantic_workspace_response_from_artifact(
        projection,
        filters=filters,
        page=page,
        page_size=page_size,
    )


async def _select_current_semantic_workspace_read_model(
    event_id: str,
    registry: AnalysisRegistry,
) -> tuple[dict[str, Any], dict[str, Any]] | None:
    """Return the first fresh, hash-pinned workspace read model for one event."""
    try:
        candidates = await registry.list_semantic_artifact_candidates(event_id)
    except Exception:
        return None

    current_snapshot_cache: dict[tuple[str, str, str, str, str], Any] = {}
    for run in candidates:
        run_id = str(run.get("run_id") or "")
        source_artifact_sha256 = _semantic_result_artifact_sha256(run)
        if not run_id or not source_artifact_sha256:
            continue
        try:
            read_model = await registry.load_run_artifact(run_id, SEMANTIC_PAGE_READ_MODEL_ARTIFACT_KEY)
        except (KeyError, ValueError, TypeError):
            continue
        except Exception:
            continue
        if not isinstance(read_model, dict):
            continue
        compact = read_semantic_workspace_read_model(
            read_model,
            expected_source_artifact_sha256=source_artifact_sha256,
        )
        if compact is None:
            continue
        freshness_reason = await _semantic_artifact_freshness(
            event_id=event_id,
            run=run,
            snapshot_fingerprint=_optional_text(read_model.get("snapshot_fingerprint")),
            registry=registry,
            current_snapshot_cache=current_snapshot_cache,
        )
        if freshness_reason is None:
            return run, compact
    return None


async def _semantic_page_projection(
    projection: dict[str, Any],
    *,
    view: SemanticPageView,
    page: int,
    page_size: int,
) -> dict[str, Any]:
    """Remove full-artifact payloads from page routes while retaining freshness checks."""
    base = _semantic_page_response(
        event_id=projection.get("event_id"),
        run_id=projection.get("run_id"),
        snapshot_id=projection.get("snapshot_id"),
        status=str(projection.get("status") or "not_found"),
        blocking_reason=_optional_text(projection.get("blocking_reason")) or None,
        view=view,
    )
    artifact = projection.get("artifact")
    if projection.get("status") != "ready" or not isinstance(artifact, dict):
        return base

    embedding_manifest = artifact.get("embedding_manifest")
    fingerprint = (
        _optional_text(embedding_manifest.get("snapshot_fingerprint"))
        if isinstance(embedding_manifest, dict)
        else None
    )
    key = build_query_cache_key(
        "semantic-page-projection-v1",
        projection.get("event_id"),
        projection.get("run_id"),
        projection.get("snapshot_id"),
        fingerprint or "missing-fingerprint",
        view,
        page,
        page_size,
    )

    async def build() -> dict[str, Any]:
        return build_semantic_page_projection(
            artifact,
            view=view,
            page=page,
            page_size=page_size,
        )

    compact = await get_or_build_query_result(key, build)
    return {**base, **compact}


async def _semantic_workspace_response_from_artifact(
    projection: dict[str, Any],
    *,
    filters: dict[str, Any],
    page: int,
    page_size: int,
) -> dict[str, Any]:
    """Build a selected workspace response without returning the source artifact."""
    base = _semantic_workspace_response(
        event_id=projection.get("event_id"),
        run_id=projection.get("run_id"),
        snapshot_id=projection.get("snapshot_id"),
        status=str(projection.get("status") or "not_found"),
        blocking_reason=_optional_text(projection.get("blocking_reason")) or None,
    )
    artifact = projection.get("artifact")
    if projection.get("status") != "ready" or not isinstance(artifact, dict):
        return base

    embedding_manifest = artifact.get("embedding_manifest")
    fingerprint = (
        _optional_text(embedding_manifest.get("snapshot_fingerprint"))
        if isinstance(embedding_manifest, dict)
        else None
    )
    key = build_query_cache_key(
        "semantic-workspace-projection-v1",
        projection.get("event_id"),
        projection.get("run_id"),
        projection.get("snapshot_id"),
        fingerprint or "missing-fingerprint",
        filters,
        page,
        page_size,
    )

    async def build() -> dict[str, Any]:
        return build_semantic_workspace_projection(
            artifact,
            filters=filters,
            page=page,
            page_size=page_size,
        )

    compact = await get_or_build_query_result(key, build)
    return {**base, **compact}


async def _semantic_workspace_response_from_read_model(
    *,
    event_id: str,
    run: dict[str, Any],
    compact: dict[str, Any],
    filters: dict[str, Any],
    page: int,
    page_size: int,
    registry: AnalysisRegistry,
) -> dict[str, Any]:
    """Serve a filtered projection without loading its source artifact on a cache hit."""
    run_id = _optional_text(run.get("run_id"))
    snapshot_id = _optional_text(run.get("snapshot_id"))
    source_artifact_sha256 = _semantic_result_artifact_sha256(run)
    base = _semantic_workspace_response(
        event_id=event_id,
        run_id=run_id,
        snapshot_id=snapshot_id,
        status="ready",
        blocking_reason=None,
    )
    if not run_id or not source_artifact_sha256:
        return {**base, **compact}

    key = build_query_cache_key(
        "semantic-workspace-projection-v2",
        event_id,
        run_id,
        snapshot_id or "missing-snapshot",
        source_artifact_sha256,
        filters,
        page,
        page_size,
    )

    async def build() -> dict[str, Any]:
        artifact = await registry.load_run_artifact(run_id, SEMANTIC_ARTIFACT_KEY)
        if not _is_ready_semantic_artifact(artifact):
            raise ValueError("semantic artifact is not ready")
        return build_semantic_workspace_projection(
            artifact,
            filters=filters,
            page=page,
            page_size=page_size,
        )

    try:
        filtered = await get_or_build_query_result(key, build)
    except KeyError:
        return _semantic_workspace_response(
            event_id=event_id,
            run_id=run_id,
            snapshot_id=snapshot_id,
            status="blocked",
            blocking_reason="semantic_artifact_not_found",
        )
    except ValueError as exc:
        reason = "semantic_artifact_integrity_failed" if "hash mismatch" in str(exc).lower() else "semantic_artifact_load_failed"
        return _semantic_workspace_response(
            event_id=event_id,
            run_id=run_id,
            snapshot_id=snapshot_id,
            status="blocked",
            blocking_reason=reason,
        )
    except Exception:
        return _semantic_workspace_response(
            event_id=event_id,
            run_id=run_id,
            snapshot_id=snapshot_id,
            status="blocked",
            blocking_reason="semantic_artifact_load_failed",
        )
    return {**base, **filtered}


async def _backfill_semantic_page_read_model(
    projection: dict[str, Any],
    *,
    candidates: list[dict[str, Any]],
    registry: AnalysisRegistry,
) -> dict[str, Any] | None:
    """Materialize the derived read model after a verified legacy read.

    This keeps old immutable analysis runs usable without making a first legacy
    page request appear fresh when it is not. A persistence failure only leaves
    that run on the compatibility path; it never changes the response.
    """
    artifact = projection.get("artifact")
    run_id = _optional_text(projection.get("run_id"))
    if projection.get("status") != "ready" or not isinstance(artifact, dict) or not run_id:
        return None
    run = next((candidate for candidate in candidates if _optional_text(candidate.get("run_id")) == run_id), None)
    source_artifact_sha256 = _semantic_result_artifact_sha256(run) if isinstance(run, dict) else ""
    if not source_artifact_sha256:
        return None
    try:
        read_model = build_semantic_page_read_model(
            artifact,
            source_artifact_sha256=source_artifact_sha256,
        )
        if not _optional_text(read_model.get("snapshot_fingerprint")):
            return None
        try:
            await registry.save_run_artifact(
                run_id=run_id,
                artifact_key=SEMANTIC_PAGE_READ_MODEL_ARTIFACT_KEY,
                payload=read_model,
            )
        except Exception:
            # The current response may still use the read model that was
            # derived from the verified artifact. A later request simply falls
            # back to compatibility materialization again.
            pass
        return read_model
    except Exception:
        # This is an optional materialization for legacy artifacts. The already
        # validated full-artifact response remains the source of truth.
        return None


async def _semantic_artifact_freshness(
    *,
    event_id: str,
    run: dict[str, Any],
    snapshot_fingerprint: str | None,
    registry: AnalysisRegistry,
    current_snapshot_cache: dict[tuple[str, str, str, str, str], Any],
) -> str | None:
    """Return a blocking reason unless artifact, snapshot, and source content agree."""
    ttl_seconds = max(0, int(settings.SEMANTIC_ARTIFACT_FRESHNESS_CACHE_TTL_SECONDS))
    if ttl_seconds == 0:
        return await _verify_semantic_artifact_freshness(
            event_id=event_id,
            run=run,
            snapshot_fingerprint=snapshot_fingerprint,
            registry=registry,
            current_snapshot_cache=current_snapshot_cache,
        )
    run_id = _optional_text(run.get("run_id"))
    snapshot_id = _optional_text(run.get("snapshot_id"))
    artifact_manifest = run.get("artifact_manifest")
    run_fingerprint = (
        _optional_text(artifact_manifest.get("data_fingerprint"))
        if isinstance(artifact_manifest, dict)
        else None
    )
    cache_key = build_query_cache_key(
        "semantic-artifact-freshness-v1",
        event_id,
        run_id or "missing-run",
        snapshot_id or "missing-snapshot",
        snapshot_fingerprint or "missing-embedding-fingerprint",
        run_fingerprint or "missing-run-fingerprint",
    )

    async def build() -> dict[str, Any]:
        return {
            "reason": await _verify_semantic_artifact_freshness(
                event_id=event_id,
                run=run,
                snapshot_fingerprint=snapshot_fingerprint,
                registry=registry,
                current_snapshot_cache=current_snapshot_cache,
            )
        }

    cached = await get_or_build_query_result(
        cache_key,
        build,
        should_cache=lambda value: value.get("reason") is None,
        ttl_seconds=float(ttl_seconds),
    )
    reason = cached.get("reason")
    return reason if isinstance(reason, str) and reason else None


async def _verify_semantic_artifact_freshness(
    *,
    event_id: str,
    run: dict[str, Any],
    snapshot_fingerprint: str | None,
    registry: AnalysisRegistry,
    current_snapshot_cache: dict[tuple[str, str, str, str, str], Any],
) -> str | None:
    """Perform one uncached, fail-closed source freshness verification."""
    snapshot_id = _optional_text(run.get("snapshot_id"))
    embedding_fingerprint = _optional_text(snapshot_fingerprint)
    artifact_manifest = run.get("artifact_manifest")
    run_fingerprint = (
        _optional_text(artifact_manifest.get("data_fingerprint"))
        if isinstance(artifact_manifest, dict)
        else None
    )
    if not snapshot_id or not embedding_fingerprint or not run_fingerprint:
        return "semantic_artifact_snapshot_mismatch"

    try:
        snapshot = await registry.load_event_snapshot(snapshot_id)
    except Exception:
        return "semantic_snapshot_lookup_failed"

    snapshot_fingerprint = _optional_text(getattr(snapshot, "data_fingerprint", None))
    if (
        _optional_text(getattr(snapshot, "snapshot_id", None)) != snapshot_id
        or _optional_text(getattr(snapshot, "event_id", None)) != event_id
        or not snapshot_fingerprint
        or snapshot_fingerprint != embedding_fingerprint
        or snapshot_fingerprint != run_fingerprint
    ):
        return "semantic_artifact_snapshot_mismatch"

    core_window = getattr(snapshot, "core_window", None)
    context_window = getattr(snapshot, "context_window", None)
    cache_key = (
        event_id,
        _window_identity(core_window, "start"),
        _window_identity(core_window, "end"),
        _window_identity(context_window, "start"),
        _window_identity(context_window, "end"),
    )
    try:
        current_snapshot = current_snapshot_cache.get(cache_key)
        if current_snapshot is None:
            current_snapshot = await registry.build_current_event_snapshot(
                event_id=event_id,
                core_window=core_window,
                context_window=context_window,
            )
            current_snapshot_cache[cache_key] = current_snapshot
    except Exception:
        return "semantic_current_source_lookup_failed"

    if (
        _optional_text(getattr(current_snapshot, "event_id", None)) != event_id
        or _optional_text(getattr(current_snapshot, "data_fingerprint", None)) != snapshot_fingerprint
    ):
        return "semantic_artifact_snapshot_mismatch"
    return None


def _semantic_artifact_snapshot_fingerprint(artifact: dict[str, Any]) -> str | None:
    embedding_manifest = artifact.get("embedding_manifest")
    if not isinstance(embedding_manifest, dict):
        return None
    return _optional_text(embedding_manifest.get("snapshot_fingerprint")) or None


def _semantic_result_artifact_sha256(run: dict[str, Any]) -> str:
    artifact_manifest = run.get("artifact_manifest")
    if not isinstance(artifact_manifest, dict):
        return ""
    stages = artifact_manifest.get("stages")
    if not isinstance(stages, dict):
        return ""
    semantic_stage = stages.get("semantic_enrichment")
    if not isinstance(semantic_stage, dict):
        return ""
    result_artifact = semantic_stage.get("result_artifact")
    return _optional_text(result_artifact.get("payload_sha256")) if isinstance(result_artifact, dict) else ""


def _semantic_page_response(
    *,
    event_id: Any,
    view: SemanticPageView,
    status: str,
    blocking_reason: str | None,
    run_id: Any = None,
    snapshot_id: Any = None,
    summary: dict[str, Any] | None = None,
    content: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "event_id": event_id,
        "run_id": run_id,
        "snapshot_id": snapshot_id,
        "status": status,
        "blocking_reason": blocking_reason,
        "view": view,
        "summary": summary,
        "content": content,
    }


def _semantic_workspace_response(
    *,
    event_id: Any,
    status: str,
    blocking_reason: str | None,
    run_id: Any = None,
    snapshot_id: Any = None,
    summary: dict[str, Any] | None = None,
    content: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "event_id": event_id,
        "run_id": run_id,
        "snapshot_id": snapshot_id,
        "status": status,
        "blocking_reason": blocking_reason,
        "summary": summary,
        "content": content,
    }


def _semantic_workspace_filters(
    *,
    layer: str,
    platforms: str | None,
    date: str | None,
    keyword: str | None,
    topic: str | None,
    sentiment: str | None,
    stance: str | None,
    entity: str | None,
) -> dict[str, Any]:
    return {
        "layer": _optional_text(layer) or "all",
        "platforms": [
            platform.strip()
            for platform in (platforms or "").split(",")
            if platform.strip()
        ],
        "date": _optional_text(date),
        "keyword": _optional_text(keyword),
        "topic": _optional_text(topic),
        "sentiment": _optional_text(sentiment),
        "stance": _optional_text(stance),
        "entity": _optional_text(entity),
    }


def _has_semantic_workspace_filters(filters: dict[str, Any]) -> bool:
    return any(
        [
            _optional_text(filters.get("layer")) not in {"", "all"},
            bool(filters.get("platforms")),
            bool(_optional_text(filters.get("date"))),
            bool(_optional_text(filters.get("keyword"))),
            bool(_optional_text(filters.get("topic"))),
            bool(_optional_text(filters.get("sentiment"))),
            bool(_optional_text(filters.get("stance"))),
            bool(_optional_text(filters.get("entity"))),
        ]
    )


def _window_identity(window: Any, field: str) -> str:
    return _optional_text(getattr(window, field, None)) or ""


def _semantic_projection(
    *,
    event_id: str,
    status: str,
    blocking_reason: str | None,
    run_id: str | None = None,
    snapshot_id: str | None = None,
    artifact: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "event_id": event_id,
        "run_id": run_id,
        "snapshot_id": snapshot_id,
        "status": status,
        "blocking_reason": blocking_reason,
        "artifact": artifact,
    }


def _is_ready_semantic_artifact(artifact: Any) -> bool:
    return (
        isinstance(artifact, dict)
        and artifact.get("technology") == "semantic_enrichment"
        and artifact.get("status") == "ok"
        and artifact.get("runtime_status") == "ready"
        and not artifact.get("fallback")
    )


def _optional_text(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None


@router.get("/runs/{run_id}/events")
async def list_run_events(
    run_id: str,
    after_id: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    registry: AnalysisRegistry = Depends(get_analysis_registry),
    _current_user: User = Depends(require_roles("admin")),
):
    events = await registry.list_run_events(run_id, after_id=after_id, limit=limit)
    return success(data={"run_id": run_id, "after_id": after_id, "events": events})


@router.get("/runs/{run_id}/events/stream")
async def stream_run_events(
    run_id: str,
    last_event_id: str | None = Header(default=None, alias="Last-Event-ID"),
    after_id: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    registry: AnalysisRegistry = Depends(get_analysis_registry),
    _current_user: User = Depends(require_roles("admin")),
):
    cursor = parse_last_event_id(last_event_id, fallback=after_id)
    events = await registry.list_run_events(run_id, after_id=cursor, limit=limit)
    return StreamingResponse(
        iter_sse_events(events),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache"},
    )


@router.post("/runs/{run_id}/verdicts/{verdict_id}/approve")
async def approve_verdict(
    run_id: str,
    verdict_id: str,
    body: CanonicalVerdictApprovalRequest,
    current_user: User = Depends(require_roles("admin", "analyst")),
    db: AsyncSession = Depends(get_db),
):
    try:
        result = await analysis_governance_service.approve_run_verdict(
            run_id=run_id,
            verdict_id=verdict_id,
            approved_by=int(current_user.id),
            approval_notes=body.approval_notes,
            db=db,
        )
        await db.commit()
    except ValueError as exc:
        detail = str(exc)
        raise HTTPException(status_code=404 if "not found" in detail else 400, detail=detail) from exc
    return success(data=result)


@router.post("/runs/{run_id}/feedback")
async def record_feedback(
    run_id: str,
    body: ReviewFeedbackCreateRequest,
    current_user: User = Depends(require_roles("admin", "analyst")),
    db: AsyncSession = Depends(get_db),
):
    if body.run_id != run_id:
        raise HTTPException(status_code=400, detail="Feedback run_id does not match the URL")
    try:
        result = await analysis_governance_service.create_feedback(
            run_id=run_id,
            snapshot_id=body.snapshot_id,
            verdict_id=body.verdict_id,
            feedback=body.feedback,
            created_by=int(current_user.id),
            db=db,
        )
        await db.commit()
    except ValueError as exc:
        detail = str(exc)
        raise HTTPException(status_code=404 if "not found" in detail else 400, detail=detail) from exc
    return success(data=result)


@router.post("/models")
async def register_model(
    body: ModelVersionCreateRequest,
    current_user: User = Depends(require_roles("admin")),
    db: AsyncSession = Depends(get_db),
):
    try:
        result = await analysis_governance_service.register_model_version(
            payload=body.model_dump(),
            created_by=int(current_user.id),
            db=db,
        )
        await db.commit()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return success(data=result)


@router.post("/models/{model_version_id}/activate")
async def activate_model(
    model_version_id: int,
    body: ModelActivationRequest,
    current_user: User = Depends(require_roles("admin")),
    db: AsyncSession = Depends(get_db),
):
    try:
        result = await analysis_governance_service.activate_model_version(
            model_version_id=model_version_id,
            operator_id=int(current_user.id),
            reason=body.reason,
            db=db,
        )
        await db.commit()
    except ValueError as exc:
        detail = str(exc)
        raise HTTPException(status_code=404 if "not found" in detail else 400, detail=detail) from exc
    return success(data=result)


@router.post("/models/{model_version_id}/approvals")
async def approve_model_candidate(
    model_version_id: int,
    body: ModelCandidateApprovalRequest,
    current_user: User = Depends(require_roles("admin")),
    db: AsyncSession = Depends(get_db),
):
    try:
        result = await analysis_governance_service.approve_model_candidate(
            model_version_id=model_version_id,
            approved_by=int(current_user.id),
            approval_notes=body.approval_notes,
            db=db,
        )
        await db.commit()
    except ValueError as exc:
        detail = str(exc)
        raise HTTPException(status_code=404 if "not found" in detail else 400, detail=detail) from exc
    return success(data=result)


@router.post("/models/{technology}/rollback")
async def rollback_model(
    technology: str,
    body: ModelRollbackRequest,
    current_user: User = Depends(require_roles("admin")),
    db: AsyncSession = Depends(get_db),
):
    try:
        result = await analysis_governance_service.rollback_model_version(
            technology=technology,
            reason=body.reason,
            requested_by=int(current_user.id),
            target_model_version_id=body.target_model_version_id,
            db=db,
        )
        await db.commit()
    except ValueError as exc:
        detail = str(exc)
        raise HTTPException(status_code=404 if "not found" in detail else 400, detail=detail) from exc
    return success(data=result)


@router.get("/models/{technology}/history")
async def model_governance_history(
    technology: str,
    limit: int = Query(100, ge=1, le=1000),
    _current_user: User = Depends(require_roles("admin")),
    db: AsyncSession = Depends(get_db),
):
    result = await analysis_governance_service.list_model_governance_history(
        technology=technology,
        db=db,
        limit=limit,
    )
    return success(data={"items": result, "total": len(result)})
