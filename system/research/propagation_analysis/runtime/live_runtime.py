"""Internal KT2 live runtime for current-event inference.

The benchmark adapter in ``benchmark/adapters`` prepares the event bundle seam.
This module turns that bundle plus the trend scaffold into a system-facing
multi-scale result when no deployable checkpoint is available yet.
"""

from __future__ import annotations

from math import log
from typing import Any


def build_live_event_macro_micro(
    *,
    bundle: dict[str, Any],
    trend: dict[str, Any],
    top_k: int = 10,
    checkpoint_available: bool = False,
) -> dict[str, Any]:
    bundle_summary = dict(bundle.get("summary") or {})
    total_posts = int(bundle_summary.get("post_count") or 0)
    total_comments = int(bundle_summary.get("comment_count") or 0)
    candidate_meta = _rank_candidates(bundle.get("candidate_meta") or {})
    top_candidates = candidate_meta[: max(1, int(top_k))]
    trend_features = dict(trend.get("ts_features") or {})

    if total_posts < 2 or not trend_features:
        return _missing_result(
            bundle=bundle,
            trend=trend,
            note="KT2 live runtime requires at least two temporally resolved posts.",
            checkpoint_available=checkpoint_available,
        )

    volume_forecast = dict(trend.get("volume_forecast") or {})
    confidence_interval = dict(trend.get("confidence_interval") or {})
    regime_posterior = dict(trend.get("regime_posterior") or {})

    return {
        "schema": "cogguard.kt2.system_macro_micro_prediction.v1",
        "status": "ok",
        "model": "KT2LiveRuntime",
        "task": "multi_scale",
        "dataset": "current_event",
        "seed": None,
        "source": "internal_live_runtime",
        "artifact": None,
        "label": "实时预测",
        "is_experimental": True,
        "evidence_level": "internal_live_runtime",
        "full_validation_passed": False,
        "boundary": (
            "Internal KT2 live runtime derived from the event bundle and "
            "trend scaffold. It is not a fitted benchmark checkpoint."
        ),
        "methodology": {
            "bundle_adapter": bundle.get("adapter_boundary"),
            "trend_runtime": trend.get("explanation"),
            "checkpoint_mode": "fallback_to_live_runtime" if not checkpoint_available else "checkpoint_fallback",
        },
        "macro": {
            "target": "next_24h_volume_and_direction",
            "metrics": {
                "direction_score": _direction_score(str(trend.get("direction") or "stable")),
                "trend_confidence": _as_float(trend.get("confidence")),
                "volume_1h": _as_float(volume_forecast.get("1h")),
                "volume_6h": _as_float(volume_forecast.get("6h")),
                "volume_24h": _as_float(volume_forecast.get("24h")),
                "ci_1h_low": _interval_bound(confidence_interval.get("1h"), 0),
                "ci_1h_high": _interval_bound(confidence_interval.get("1h"), 1),
                "ci_6h_low": _interval_bound(confidence_interval.get("6h"), 0),
                "ci_6h_high": _interval_bound(confidence_interval.get("6h"), 1),
                "ci_24h_low": _interval_bound(confidence_interval.get("24h"), 0),
                "ci_24h_high": _interval_bound(confidence_interval.get("24h"), 1),
                "regime_entropy": round(_entropy(regime_posterior), 6),
                "llm_available": 1.0 if trend.get("llm_available") else 0.0,
            },
            "obs_ratios": _obs_ratios(bundle),
        },
        "micro": {
            "target": "active_candidate_ranking",
            "metrics": {
                "candidate_count": len(candidate_meta),
                "active_sequence_length": int(bundle_summary.get("active_sequence_length") or 0),
                "relation_edge_count": len(bundle.get("relation_edges") or []),
                "bucket_count": len(bundle.get("candidate_buckets") or {}),
                "top_candidate_activity": round(top_candidates[0]["activity_score"], 3) if top_candidates else 0.0,
                "mean_topk_activity": round(
                    sum(candidate["activity_score"] for candidate in top_candidates) / len(top_candidates), 3
                )
                if top_candidates
                else 0.0,
            },
            "rollout_summary": {
                "topk_examples": top_candidates,
                "trend_events": list(trend.get("detected_events") or []),
            },
            "topk_examples": top_candidates,
        },
        "baseline_comparison": {
            "baseline_model": "bundle_activity_ranking",
            "metrics": {
                "activity_score_mean": round(
                    sum(candidate["activity_score"] for candidate in candidate_meta) / len(candidate_meta), 3
                )
                if candidate_meta
                else 0.0,
                "candidate_coverage": round(len(top_candidates) / len(candidate_meta), 6) if candidate_meta else 0.0,
                "trend_confidence": _as_float(trend.get("confidence")),
            },
            "note": (
                "Live runtime uses the internal event bundle and trend scaffold; "
                "benchmark checkpoint metrics are unavailable until a fitted checkpoint is internalized."
            ),
        },
        "training_protocol": {
            "bundle_signature": bundle.get("bundle_signature"),
            "post_count": total_posts,
            "comment_count": total_comments,
            "candidate_count": len(candidate_meta),
            "observed_count": int(bundle_summary.get("observed_count") or 0),
        },
        "candidate_protocol_audit": {
            "bundle_boundary": bundle.get("adapter_boundary"),
            "relation_neighbor_count": int(bundle.get("relation_neighbor_count") or 0),
            "hyperedge_count": int(bundle.get("hyperedge_count") or 0),
            "checkpoint_available": bool(checkpoint_available),
            "checkpoint_path": bundle.get("checkpoint_path"),
        },
        "rows_used": len(candidate_meta),
    }


def _missing_result(
    *,
    bundle: dict[str, Any],
    trend: dict[str, Any],
    note: str,
    checkpoint_available: bool,
) -> dict[str, Any]:
    bundle_summary = dict(bundle.get("summary") or {})
    return {
        "schema": "cogguard.kt2.system_macro_micro_prediction.v1",
        "status": "data_insufficient",
        "model": "KT2LiveRuntime",
        "task": "multi_scale",
        "dataset": "current_event",
        "seed": None,
        "source": "internal_live_runtime",
        "artifact": None,
        "label": "实时预测",
        "is_experimental": True,
        "evidence_level": "internal_live_runtime",
        "note": note,
        "boundary": (
            "Internal KT2 live runtime stays conservative when the event bundle "
            "does not contain enough temporally resolved posts."
        ),
        "macro": {
            "target": "next_24h_volume_and_direction",
            "metrics": {},
            "obs_ratios": _obs_ratios(bundle),
        },
        "micro": {
            "target": "active_candidate_ranking",
            "metrics": {},
            "rollout_summary": {
                "topk_examples": [],
                "trend_events": list(trend.get("detected_events") or []),
            },
            "topk_examples": [],
        },
        "baseline_comparison": {
            "baseline_model": "bundle_activity_ranking",
            "metrics": {},
            "note": (
                "Insufficient live evidence for a meaningful macro/micro estimate; "
                f"checkpoint_available={checkpoint_available}."
            ),
        },
        "training_protocol": {
            "bundle_signature": bundle.get("bundle_signature"),
            "post_count": int(bundle_summary.get("post_count") or 0),
            "comment_count": int(bundle_summary.get("comment_count") or 0),
            "candidate_count": int(bundle_summary.get("candidate_count") or 0),
            "observed_count": int(bundle_summary.get("observed_count") or 0),
        },
        "candidate_protocol_audit": {
            "bundle_boundary": bundle.get("adapter_boundary"),
            "relation_neighbor_count": int(bundle.get("relation_neighbor_count") or 0),
            "hyperedge_count": int(bundle.get("hyperedge_count") or 0),
            "checkpoint_available": bool(checkpoint_available),
            "checkpoint_path": bundle.get("checkpoint_path"),
        },
        "rows_used": 0,
    }


def _rank_candidates(candidate_meta: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    ranked = []
    for candidate in candidate_meta.values():
        ranked.append(
            {
                "author_id": candidate.get("author_id"),
                "author_name": candidate.get("author_name"),
                "platforms": list(candidate.get("platforms") or []),
                "post_count": int(candidate.get("post_count") or 0),
                "comment_count": int(candidate.get("comment_count") or 0),
                "activity_score": _as_float(candidate.get("activity_score")),
                "first_seen_at": candidate.get("first_seen_at"),
                "last_seen_at": candidate.get("last_seen_at"),
                "content_ids": list(candidate.get("content_ids") or []),
                "evidence_refs": list(candidate.get("evidence_refs") or []),
                "bucket": int(candidate.get("bucket") or 0),
            }
        )
    ranked.sort(
        key=lambda item: (
            item["activity_score"],
            item["post_count"],
            item["comment_count"],
            str(item["first_seen_at"] or ""),
            str(item["author_id"] or ""),
        ),
        reverse=True,
    )
    return ranked


def _obs_ratios(bundle: dict[str, Any]) -> list[dict[str, Any]]:
    summary = dict(bundle.get("summary") or {})
    observed = int(summary.get("observed_count") or 0)
    posts = int(summary.get("post_count") or 0)
    comments = int(summary.get("comment_count") or 0)
    total = max(observed, posts + comments, 1)
    return [
        {"name": "posts", "ratio": round(posts / total, 6)},
        {"name": "comments", "ratio": round(comments / total, 6)},
        {"name": "observed", "ratio": round(observed / total, 6)},
    ]


def _direction_score(direction: str) -> float:
    return {"rising": 1.0, "stable": 0.0, "declining": -1.0}.get(direction, 0.0)


def _interval_bound(interval: Any, index: int) -> float:
    if isinstance(interval, (list, tuple)) and len(interval) > index:
        return _as_float(interval[index])
    return 0.0


def _entropy(posterior: dict[str, Any]) -> float:
    values = [_as_float(value) for value in posterior.values() if _as_float(value) > 0]
    if not values:
        return 0.0
    return -sum(value * log(value) for value in values)


def _as_float(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0
