"""Propagation analysis and trend prediction service."""

from __future__ import annotations

from app.core.propagation import build_propagation_graph
from app.core.propagation.trend_predictor import predict_trend
from app.db.mongodb import get_mongo_db
from app.services.event_data import analysis_scope_metadata, load_event_comments, load_event_posts


def _empty_result(event_id: str | None, platform: str | None) -> dict:
    return {
        "error": "No analyzable posts found. Run data collection or choose another event/platform.",
        "event_id": event_id,
        "platform": platform,
        "data_scope": analysis_scope_metadata(
            event_id=event_id,
            platform=platform,
            posts_count=0,
            comments_count=0,
        ),
    }


def _attach_scope(
    result: dict,
    *,
    event_id: str | None,
    platform: str | None,
    posts_count: int,
    comments_count: int,
) -> dict:
    result["event_id"] = event_id
    result["platform"] = platform
    result["data_scope"] = analysis_scope_metadata(
        event_id=event_id,
        platform=platform,
        posts_count=posts_count,
        comments_count=comments_count,
    )
    return result


async def analyze_propagation(platform: str | None = None, event_id: str | None = None) -> dict:
    """Analyze propagation paths over optionally event-scoped data."""
    mongo_db = get_mongo_db()

    posts = await load_event_posts(mongo_db, event_id=event_id, platform=platform)
    if not posts:
        return _empty_result(event_id, platform)

    comments = await load_event_comments(mongo_db, event_id=event_id, platform=platform)
    result = build_propagation_graph(posts, comments)

    return _attach_scope(
        result,
        event_id=event_id,
        platform=platform,
        posts_count=len(posts),
        comments_count=len(comments),
    )


async def predict_propagation_trend(platform: str | None = None, event_id: str | None = None) -> dict:
    """Predict propagation trend over optionally event-scoped data."""
    mongo_db = get_mongo_db()

    posts = await load_event_posts(mongo_db, event_id=event_id, platform=platform)
    if not posts:
        return _empty_result(event_id, platform)

    comments = await load_event_comments(mongo_db, event_id=event_id, platform=platform)
    result = await predict_trend(posts, comments, mock_llm=True)

    return _attach_scope(
        result,
        event_id=event_id,
        platform=platform,
        posts_count=len(posts),
        comments_count=len(comments),
    )
