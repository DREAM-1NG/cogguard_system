"""Observed Propagation Analysis service.

This service is the product-facing system capability aligned with observed
propagation analysis: it reads collected event data and reconstructs paths,
roles, shared objects, evidence chains, timeline, and visualization summaries.
It must not call future-prediction model code.
"""

from __future__ import annotations

from collections.abc import Mapping
from inspect import Parameter, signature

from app.core.analysis.query_result_cache import (
    build_query_cache_key,
    get_or_build_query_result,
)
from app.core.propagation_analysis import build_propagation_graph
from app.db.mongodb import get_mongo_db
from app.services.event_data import (
    analysis_scope_metadata,
    event_data_fingerprint,
    load_event_comments,
    load_event_posts,
)


OBSERVED_ANALYSIS_CAPABILITY = {
    "name": "observed_propagation_analysis",
    "type": "system_function",
    "boundary": "observed_data_only",
    "product_alignment": "zhiwei_style_propagation_analysis",
    "predicts_future": False,
}


def empty_observed_result(event_id: str | None, platform: str | None) -> dict:
    return {
        "error": "No analyzable posts found. Run data collection or choose another event/platform.",
        "event_id": event_id,
        "platform": platform,
        "capability": dict(OBSERVED_ANALYSIS_CAPABILITY),
        "data_scope": analysis_scope_metadata(
            event_id=event_id,
            platform=platform,
            posts_count=0,
            comments_count=0,
        ),
    }


def attach_observed_scope(
    result: dict,
    *,
    event_id: str | None,
    platform: str | None,
    posts_count: int,
    comments_count: int,
) -> dict:
    result["event_id"] = event_id
    result["platform"] = platform
    result["capability"] = dict(OBSERVED_ANALYSIS_CAPABILITY)
    result["data_scope"] = analysis_scope_metadata(
        event_id=event_id,
        platform=platform,
        posts_count=posts_count,
        comments_count=comments_count,
    )
    return result


def build_observed_propagation_graph(posts: list[dict], comments: list[dict], *, node_limit: int) -> dict:
    """Build the observed propagation graph while preserving legacy signatures."""
    parameters: Mapping[str, Parameter]
    try:
        parameters = signature(build_propagation_graph).parameters
    except (TypeError, ValueError):
        parameters = {}
    supports_limit = "diffusion_node_limit" in parameters or any(
        param.kind == Parameter.VAR_KEYWORD for param in parameters.values()
    )
    if supports_limit:
        return build_propagation_graph(posts, comments, diffusion_node_limit=node_limit)
    return build_propagation_graph(posts, comments)


async def analyze_observed_propagation(
    platform: str | None = None,
    event_id: str | None = None,
    *,
    node_limit: int = 300,
) -> dict:
    """Analyze only observed propagation facts for an optional event/platform scope."""
    mongo_db = get_mongo_db()

    source_fingerprint = await event_data_fingerprint(
        mongo_db,
        event_id=event_id,
        platform=platform,
    )
    if source_fingerprint:
        cache_key = build_query_cache_key(
            "propagation-observed-v6",
            event_id or "*",
            platform or "*",
            source_fingerprint,
            node_limit,
        )
        return await get_or_build_query_result(
            cache_key,
            lambda: _build_observed_propagation_result(
                mongo_db,
                event_id=event_id,
                platform=platform,
                node_limit=node_limit,
            ),
        )

    return await _build_observed_propagation_result(
        mongo_db,
        event_id=event_id,
        platform=platform,
        node_limit=node_limit,
    )


async def _build_observed_propagation_result(
    mongo_db,
    *,
    event_id: str | None,
    platform: str | None,
    node_limit: int,
) -> dict:
    """Build a projection after the versioned cache has been checked."""

    posts = await load_event_posts(mongo_db, event_id=event_id, platform=platform)
    if not posts:
        return empty_observed_result(event_id, platform)

    comments = await load_event_comments(mongo_db, event_id=event_id, platform=platform)
    result = build_observed_propagation_graph(posts, comments, node_limit=node_limit)

    return attach_observed_scope(
        result,
        event_id=event_id,
        platform=platform,
        posts_count=len(posts),
        comments_count=len(comments),
    )


# Backward-compatible service name for existing callers.
analyze_propagation = analyze_observed_propagation
