"""Propagation prediction model orchestration service.

This service owns future trend and next-hop prediction for event-scoped
propagation data. Observed path reconstruction belongs in
``propagation_observation_service`` instead.
"""

from __future__ import annotations

from app.db.mongodb import get_mongo_db
from app.services.event_data import analysis_scope_metadata, load_event_comments, load_event_posts
from app.services import propagation_prediction_service


PREDICTION_MODEL_CAPABILITY = {
    "name": "macro_micro_sequence_propagation_prediction",
    "type": "macro_micro_prediction",
    "boundary": "future_trend_and_next_hop_prediction",
    "predicts_future": True,
}


def empty_prediction_result(event_id: str | None, platform: str | None) -> dict:
    return {
        "error": "No analyzable posts found. Run data collection or choose another event/platform.",
        "event_id": event_id,
        "platform": platform,
        "capability": dict(PREDICTION_MODEL_CAPABILITY),
        "data_scope": analysis_scope_metadata(
            event_id=event_id,
            platform=platform,
            posts_count=0,
            comments_count=0,
        ),
    }


def attach_prediction_scope(
    result: dict,
    *,
    event_id: str | None,
    platform: str | None,
    posts_count: int,
    comments_count: int,
) -> dict:
    result["event_id"] = event_id
    result["platform"] = platform
    result["capability"] = dict(PREDICTION_MODEL_CAPABILITY)
    result["data_scope"] = analysis_scope_metadata(
        event_id=event_id,
        platform=platform,
        posts_count=posts_count,
        comments_count=comments_count,
    )
    return result


async def predict_current_event_model(
    platform: str | None = None,
    event_id: str | None = None,
    *,
    top_k: int = 10,
) -> dict:
    """Run the macro/micro prediction model over current event-scoped data."""
    mongo_db = get_mongo_db()

    posts = await load_event_posts(mongo_db, event_id=event_id, platform=platform)
    if not posts:
        return empty_prediction_result(event_id, platform)

    comments = await load_event_comments(mongo_db, event_id=event_id, platform=platform)
    result = await propagation_prediction_service.predict_event_macro_micro(
        posts=posts,
        comments=comments,
        top_k=top_k,
    )
    result.setdefault(
        "methodology",
        propagation_prediction_service.prediction_methodology(
            source="current_event_service",
            protocol={"top_k": top_k},
        ),
    )
    result["prediction_boundary"] = {
        "method": "macro_micro_sequence_model",
        "is_primary_model": True,
        "observed_input_only": True,
        "legacy_speed_acceleration_scaffold": "removed_from_public_prediction_api",
    }

    return attach_prediction_scope(
        result,
        event_id=event_id,
        platform=platform,
        posts_count=len(posts),
        comments_count=len(comments),
    )


async def predict_benchmark_model_evidence(
    *,
    dataset: str = "twitter",
    seed: int | None = 42,
    run_live: bool = False,
) -> dict:
    """Return cached or small-run experiment evidence for the prediction model."""
    result = await propagation_prediction_service.predict_propagation_macro_micro(
        dataset=dataset,
        seed=seed,
        run_live=run_live,
    )
    result.setdefault(
        "methodology",
        propagation_prediction_service.prediction_methodology(
            source="benchmark_model_evidence",
            protocol={"dataset": dataset, "seed": seed, "run_live": run_live},
        ),
    )
    result["capability"] = dict(PREDICTION_MODEL_CAPABILITY)
    result["prediction_boundary"] = {
        "method": "benchmark_macro_micro_evidence",
        "is_primary_model": True,
        "current_event": False,
        "legacy_speed_acceleration_scaffold": "removed_from_public_prediction_api",
    }
    return result


# Backward-compatible service names for existing callers.
predict_propagation_model_event = predict_current_event_model
