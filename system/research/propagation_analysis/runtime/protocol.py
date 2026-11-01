"""PropagationAnalysis hindcast protocol helpers.

This module keeps research-grade propagation claims separate from the live
fallback runtime. It can score observed event bundles today, while marking
untrained deep models as unavailable instead of fabricating results.
"""

from __future__ import annotations

import math
from collections import Counter, defaultdict
from datetime import datetime, timezone
from statistics import mean
from typing import Any, Iterable, Mapping


DEFAULT_COVERAGE_LEVELS = (0.8, 0.95)
DEFAULT_HORIZONS = ("1h", "6h", "24h", "48h")
DEEP_BASELINE_NAMES = ("tgn", "dygformer", "casflow", "casft")


def build_hindcast_protocol(
    *,
    bundle: Mapping[str, Any],
    forecast: Mapping[str, Any],
    posts: list[dict[str, Any]],
    comments: list[dict[str, Any]] | None = None,
    top_k: int = 10,
    coverage_levels: Iterable[float] = DEFAULT_COVERAGE_LEVELS,
    horizons: Iterable[str] = DEFAULT_HORIZONS,
) -> dict[str, Any]:
    """Return the app-facing PropagationAnalysis prediction protocol for one event snapshot."""

    rows = _normalize_rows(posts, comments or [])
    candidate_meta = dict(bundle.get("candidate_meta") or {})
    active_accounts = sorted({row["author_id"] for row in rows if row.get("author_id")})
    horizon_names = [str(item) for item in horizons]
    projected_size = _project_independent_active_accounts(
        current_size=len(active_accounts),
        forecast=forecast,
    )
    calibration = _event_residuals(rows)
    conformal_intervals = {
        _coverage_key(level): split_conformal_interval(
            point=projected_size,
            residuals=calibration["absolute_residuals"],
            coverage=float(level),
        )
        for level in coverage_levels
    }
    next_hops = rank_next_hop_candidates(
        candidate_meta=candidate_meta,
        rows=rows,
        relation_edges=list(bundle.get("relation_edges") or []),
        top_k=top_k,
    )
    baselines = build_baseline_suite(
        rows=rows,
        relation_edges=list(bundle.get("relation_edges") or []),
        candidate_meta=candidate_meta,
        checkpoint_available=bool(bundle.get("checkpoint_available")),
        top_k=top_k,
    )

    scale_forecast = {
        "target": "independent_active_accounts",
        "point": projected_size,
        "observed": len(active_accounts),
        "horizons": {
            horizon: _horizon_projection(projected_size, horizon)
            for horizon in horizon_names
        },
        "intervals": conformal_intervals,
        "calibration": calibration,
    }
    return {
        "schema": "cogguard.propagation_analysis.hindcast_protocol.v1",
        "model_version": "propagation_analysis-hindcast-protocol-v1",
        "scale_forecast": scale_forecast,
        "conformal_intervals": conformal_intervals,
        "next_hop_ranking": {
            "target": "next_independent_active_accounts",
            "top_k": max(1, int(top_k)),
            "items": next_hops,
            "candidate_count": len(candidate_meta),
            "coverage": round(len(next_hops) / max(len(candidate_meta), 1), 6) if candidate_meta else 0.0,
            "calibration_status": "blocked_without_next_hop_gold",
        },
        "platform_hindcasts": _platform_hindcasts(rows, projected_size),
        "baselines": baselines,
        "protocol": {
            "macro_target": "independent_active_accounts",
            "micro_targets": ["first_edge", "first_node", "repeat_edge", "overall_next_hop"],
            "prefixes": ["1h", "6h", "24h", "48h"],
            "public_benchmark_prefixes": [0.1, 0.3, 0.5],
            "activation_gate": (
                "Deep PropagationAnalysis models require stronger-than-persistence validation, "
                "nominal conformal coverage, and an approved checkpoint before activation."
            ),
            "claim_status": _claim_status(forecast, checkpoint_available=bool(bundle.get("checkpoint_available"))),
        },
        "abstain": _should_abstain(rows, forecast),
    }


def split_conformal_interval(
    *,
    point: int | float,
    residuals: Iterable[int | float],
    coverage: float,
) -> dict[str, Any]:
    """Build a finite-sample split-conformal interval from absolute residuals."""

    point_value = max(0.0, float(point))
    clean_residuals = sorted(abs(float(value)) for value in residuals if _is_number(value))
    if not clean_residuals:
        clean_residuals = [max(1.0, math.sqrt(point_value + 1.0))]
        calibration_status = "fallback_conservative"
    else:
        calibration_status = "event_prefix_residuals"

    n = len(clean_residuals)
    coverage_value = min(max(float(coverage), 0.01), 0.999)
    index = min(n - 1, max(0, math.ceil((n + 1) * coverage_value) - 1))
    radius = clean_residuals[index]
    return {
        "coverage": round(coverage_value, 3),
        "low": int(max(0, math.floor(point_value - radius))),
        "high": int(math.ceil(point_value + radius)),
        "radius": round(radius, 6),
        "calibration_count": n,
        "calibration_status": calibration_status,
    }


def rank_next_hop_candidates(
    *,
    candidate_meta: Mapping[str, Mapping[str, Any]],
    rows: list[dict[str, Any]],
    relation_edges: list[dict[str, Any]],
    top_k: int,
) -> list[dict[str, Any]]:
    recency_scores = _recency_scores(rows)
    relation_scores = Counter()
    for edge in relation_edges:
        target = str(edge.get("target_ref") or "").strip()
        if target:
            relation_scores[target] += 1

    ranked: list[dict[str, Any]] = []
    for author_id, meta in candidate_meta.items():
        post_count = int(meta.get("post_count") or 0)
        comment_count = int(meta.get("comment_count") or 0)
        activity_score = _as_float(meta.get("activity_score"))
        score = activity_score + recency_scores.get(author_id, 0.0) + 0.5 * relation_scores.get(author_id, 0)
        ranked.append(
            {
                "rank": 0,
                "author_id": author_id,
                "author_name": meta.get("author_name") or author_id,
                "score": round(score, 6),
                "evidence": {
                    "post_count": post_count,
                    "comment_count": comment_count,
                    "activity_score": round(activity_score, 6),
                    "recency_score": round(recency_scores.get(author_id, 0.0), 6),
                    "relation_score": int(relation_scores.get(author_id, 0)),
                    "platforms": list(meta.get("platforms") or []),
                },
            }
        )

    ranked.sort(key=lambda row: (row["score"], row["evidence"]["post_count"], row["author_id"]), reverse=True)
    for index, row in enumerate(ranked[: max(1, int(top_k))], start=1):
        row["rank"] = index
    return ranked[: max(1, int(top_k))]


def build_baseline_suite(
    *,
    rows: list[dict[str, Any]],
    relation_edges: list[dict[str, Any]],
    candidate_meta: Mapping[str, Mapping[str, Any]],
    checkpoint_available: bool,
    top_k: int,
) -> dict[str, Any]:
    active_accounts = {row["author_id"] for row in rows if row.get("author_id")}
    counts_by_hour = _counts_by_hour(rows)
    historical_mean = round(mean(counts_by_hour.values()), 6) if counts_by_hour else 0.0
    baselines = {
        "persistence": {
            "status": "ok",
            "target": "independent_active_accounts",
            "point": len(active_accounts),
            "note": "Persistence baseline predicts no unseen additional active accounts.",
        },
        "historical_mean": {
            "status": "ok" if counts_by_hour else "data_insufficient",
            "target": "hourly_observed_activity",
            "point": historical_mean,
            "window_count": len(counts_by_hour),
        },
        "edgebank": _edge_bank_baseline(relation_edges=relation_edges, rows=rows, top_k=top_k),
        "hawkes_recency": _hawkes_recency_baseline(rows=rows, candidate_meta=candidate_meta, top_k=top_k),
    }
    for name in DEEP_BASELINE_NAMES:
        baselines[name] = {
            "status": "missing_checkpoint" if not checkpoint_available else "model_unavailable",
            "activation_allowed": False,
            "note": (
                f"{name} is registered as a PropagationAnalysis research baseline, but no approved "
                "internal checkpoint/runtime is active for this event."
            ),
        }
    return baselines


def _normalize_rows(posts: list[dict[str, Any]], comments: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for kind, records in (("post", posts), ("comment", comments)):
        for record in records:
            if not isinstance(record, Mapping):
                continue
            author_id = _first_text(record, ("author_id", "user_id", "account_id", "uid", "creator_id"))
            timestamp = _parse_timestamp(_first_value(record, ("timestamp", "created_at", "publish_time", "published_at", "time")))
            rows.append(
                {
                    "kind": kind,
                    "author_id": author_id,
                    "platform": _first_text(record, ("platform",)) or "unknown",
                    "timestamp": timestamp,
                    "content_id": _first_text(record, ("post_id", "comment_id", "note_id", "item_id", "id")),
                    "reply_to": _first_text(record, ("reply_to", "parent_comment_id", "parent_post_id")),
                }
            )
    rows.sort(key=lambda row: (row["timestamp"] or datetime.min.replace(tzinfo=timezone.utc), row["author_id"]))
    return rows


def _project_independent_active_accounts(*, current_size: int, forecast: Mapping[str, Any]) -> int:
    metrics = dict(dict(forecast.get("macro") or {}).get("metrics") or {})
    volume_24h = _as_float(metrics.get("volume_24h"))
    top_activity = _as_float(dict(dict(forecast.get("micro") or {}).get("metrics") or {}).get("top_candidate_activity"))
    uplift = max(0, int(round(volume_24h * 0.1 + top_activity * 0.05)))
    return max(int(current_size), int(current_size) + uplift)


def _event_residuals(rows: list[dict[str, Any]]) -> dict[str, Any]:
    counts = list(_counts_by_hour(rows).values())
    if len(counts) < 3:
        return {
            "status": "low_evidence",
            "absolute_residuals": [max(1, int(math.sqrt(max(len(rows), 1))))],
            "source": "fallback_conservative",
            "window_count": len(counts),
        }
    residuals = []
    for index in range(1, len(counts)):
        residuals.append(abs(counts[index] - counts[index - 1]))
    return {
        "status": "ok",
        "absolute_residuals": residuals,
        "source": "event_prefix_residuals",
        "window_count": len(counts),
    }


def _counts_by_hour(rows: list[dict[str, Any]]) -> dict[str, int]:
    buckets: Counter[str] = Counter()
    for row in rows:
        timestamp = row.get("timestamp")
        if not isinstance(timestamp, datetime):
            continue
        bucket = timestamp.astimezone(timezone.utc).replace(minute=0, second=0, microsecond=0).isoformat()
        buckets[bucket] += 1
    return dict(sorted(buckets.items()))


def _recency_scores(rows: list[dict[str, Any]]) -> dict[str, float]:
    timestamps = [row["timestamp"] for row in rows if isinstance(row.get("timestamp"), datetime)]
    if not timestamps:
        return {}
    latest = max(timestamps)
    scores: defaultdict[str, float] = defaultdict(float)
    for row in rows:
        author_id = row.get("author_id")
        timestamp = row.get("timestamp")
        if not author_id or not isinstance(timestamp, datetime):
            continue
        age_hours = max((latest - timestamp).total_seconds() / 3600.0, 0.0)
        scores[author_id] += math.exp(-age_hours / 6.0)
    return dict(scores)


def _edge_bank_baseline(*, relation_edges: list[dict[str, Any]], rows: list[dict[str, Any]], top_k: int) -> dict[str, Any]:
    if not relation_edges:
        return {
            "status": "data_insufficient",
            "target": "repeat_edge",
            "topk": [],
            "note": "No observed relation edges are available for EdgeBank-style replay.",
        }
    content_to_author = {row["content_id"]: row["author_id"] for row in rows if row.get("content_id") and row.get("author_id")}
    scores = Counter()
    for edge in relation_edges:
        for key in ("source_ref", "target_ref"):
            author = content_to_author.get(str(edge.get(key) or ""))
            if author:
                scores[author] += 1
    return {
        "status": "ok" if scores else "data_insufficient",
        "target": "repeat_edge",
        "topk": [
            {"author_id": author_id, "score": score}
            for author_id, score in scores.most_common(max(1, int(top_k)))
        ],
    }


def _hawkes_recency_baseline(
    *,
    rows: list[dict[str, Any]],
    candidate_meta: Mapping[str, Mapping[str, Any]],
    top_k: int,
) -> dict[str, Any]:
    scores = _recency_scores(rows)
    if not scores:
        return {
            "status": "data_insufficient",
            "target": "first_node",
            "topk": [],
            "note": "No timestamps are available for recency-intensity scoring.",
        }
    ranked = sorted(scores.items(), key=lambda item: (item[1], item[0]), reverse=True)
    return {
        "status": "ok",
        "target": "first_node",
        "kernel": "exponential_recency",
        "topk": [
            {
                "author_id": author_id,
                "author_name": (candidate_meta.get(author_id) or {}).get("author_name") or author_id,
                "score": round(score, 6),
            }
            for author_id, score in ranked[: max(1, int(top_k))]
        ],
    }


def _platform_hindcasts(rows: list[dict[str, Any]], projected_size: int) -> list[dict[str, Any]]:
    by_platform: defaultdict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_platform[str(row.get("platform") or "unknown")].append(row)
    total_accounts = len({row["author_id"] for row in rows if row.get("author_id")}) or 1
    results = []
    for platform, platform_rows in sorted(by_platform.items()):
        accounts = {row["author_id"] for row in platform_rows if row.get("author_id")}
        share = len(accounts) / total_accounts
        point = max(len(accounts), int(round(projected_size * share)))
        results.append(
            {
                "platform": platform,
                "observed_active_accounts": len(accounts),
                "point": point,
                "post_count": sum(1 for row in platform_rows if row.get("kind") == "post"),
                "comment_count": sum(1 for row in platform_rows if row.get("kind") == "comment"),
            }
        )
    return results


def _horizon_projection(projected_size: int, horizon: str) -> int:
    multipliers = {"1h": 0.25, "6h": 0.5, "24h": 1.0, "48h": 1.2}
    return max(0, int(round(projected_size * multipliers.get(horizon, 1.0))))


def _claim_status(forecast: Mapping[str, Any], *, checkpoint_available: bool) -> str:
    if forecast.get("status") != "ok":
        return "abstain"
    if checkpoint_available and forecast.get("model") != "PropagationAnalysisLiveRuntime":
        return "checkpoint_candidate"
    return "fallback_only_not_research_claim"


def _should_abstain(rows: list[dict[str, Any]], forecast: Mapping[str, Any]) -> bool:
    if forecast.get("status") != "ok":
        return True
    return len({row["author_id"] for row in rows if row.get("author_id")}) < 2


def _coverage_key(value: float) -> str:
    return f"{int(round(float(value) * 100))}"


def _parse_timestamp(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        timestamp = value
    elif value in (None, ""):
        return None
    else:
        try:
            timestamp = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except ValueError:
            return None
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=timezone.utc)
    return timestamp.astimezone(timezone.utc)


def _first_text(row: Mapping[str, Any], keys: tuple[str, ...]) -> str:
    value = _first_value(row, keys)
    return " ".join(str(value or "").split()).strip()


def _first_value(row: Mapping[str, Any], keys: tuple[str, ...]) -> Any:
    for key in keys:
        value = row.get(key)
        if value not in (None, ""):
            return value
    return None


def _as_float(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _is_number(value: Any) -> bool:
    try:
        float(value)
    except (TypeError, ValueError):
        return False
    return True
