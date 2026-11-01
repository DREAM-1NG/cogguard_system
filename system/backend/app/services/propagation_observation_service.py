"""Observed Propagation Analysis service.

This service is the product-facing system capability aligned with observed
propagation analysis: it reads collected event data and reconstructs paths,
roles, shared objects, evidence chains, timeline, and visualization summaries.
It must not call future-prediction model code.
"""

from __future__ import annotations

import asyncio
import logging
from inspect import Parameter, signature

from app.core.propagation_analysis import build_propagation_graph
from app.db.mongodb import get_mongo_db
from app.services.event_data import analysis_scope_metadata, load_event_comments, load_event_posts


logger = logging.getLogger(__name__)

OBSERVED_ANALYSIS_CAPABILITY = {
    "name": "observed_propagation_analysis",
    "type": "system_function",
    "boundary": "observed_data_only",
    "product_alignment": "zhiwei_style_propagation_analysis",
    "predicts_future": False,
}


def empty_observed_result(event_id: str | None, platform: str | None) -> dict:
    return {
        "status": "data_insufficient",
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
    try:
        mongo_db = get_mongo_db()
        posts = await load_event_posts(mongo_db, event_id=event_id, platform=platform)
        comments = await load_event_comments(mongo_db, event_id=event_id, platform=platform)
    except Exception:
        logger.exception(
            "Observed propagation data is unavailable for event_id=%r platform=%r",
            event_id,
            platform,
        )
        result = empty_observed_result(event_id, platform)
        result["status"] = "data_unavailable"
        result["error"] = "Current event data source is unavailable."
        return result

    if not posts:
        return empty_observed_result(event_id, platform)

    result = await asyncio.to_thread(build_observed_propagation_graph, posts, comments, node_limit=node_limit)

    return attach_observed_scope(
        result,
        event_id=event_id,
        platform=platform,
        posts_count=len(posts),
        comments_count=len(comments),
    )


# Backward-compatible service name for existing callers.
analyze_propagation = analyze_observed_propagation
