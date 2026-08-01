"""BotRHG-style account-level social bot detection.

This module is a lightweight system adapter for the NLPCC BotRHG method:
feature encoding, KNN support hyperedges, reliability-guided routing, and
selective residual correction. It is deterministic so the product system can
serve explainable account-level results without invoking the full research
training CLI.
"""

from __future__ import annotations

import math
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import numpy as np
import pandas as pd


@dataclass(slots=True)
class AccountEvidence:
    account_id: str
    account_label: str
    posts: list[dict[str, Any]]
    feature_vector: np.ndarray
    base_bot_probability: float
    base_prediction: str
    confidence_deficit: float
    activity: dict[str, Any]


def run_botrhg_detection(
    posts: list[dict[str, Any]],
    *,
    routing_budget: float = 0.2,
    support_k: int = 8,
) -> dict[str, Any]:
    """Run deterministic BotRHG-style inference over collected posts."""
    budget = _clamp(float(routing_budget), 0.0, 1.0)
    k = max(1, int(support_k))
    accounts = _build_account_evidence(posts)
    if not accounts:
        return _empty_result(budget, k)

    feature_matrix = np.vstack([account.feature_vector for account in accounts])
    similarity = _cosine_similarity_matrix(feature_matrix)
    support = _support_neighbors(accounts, similarity, k)
    reliabilities = _local_reliability(accounts, similarity)
    routed_ids = _select_routed(accounts, reliabilities, budget)

    support_rows_by_index = []
    support_means_by_index = []
    final_outputs_by_id = {}
    for index, account in enumerate(accounts):
        local_reliability = reliabilities[account.account_id]
        correction_risk = 1.0 - local_reliability
        support_rows = _support_rows(accounts, support[index], similarity[index])
        support_rows_by_index.append(support_rows)
        support_mean = _weighted_support_bot_probability(support_rows)
        support_means_by_index.append(support_mean)
        routed = account.account_id in routed_ids
        final_probability = account.base_bot_probability
        if routed:
            residual_delta = (support_mean - account.base_bot_probability) * correction_risk
            final_probability = _clamp(account.base_bot_probability + 0.65 * residual_delta, 0.0, 1.0)

        final_outputs_by_id[account.account_id] = {
            "final_bot_probability": round(final_probability, 6),
            "final_prediction": _prediction_label(final_probability),
            "routed": routed,
        }

    output_accounts = []
    for index, account in enumerate(accounts):
        local_reliability = reliabilities[account.account_id]
        correction_risk = 1.0 - local_reliability
        support_rows = _enrich_support_rows(support_rows_by_index[index], final_outputs_by_id)
        support_mean = support_means_by_index[index]
        final_output = final_outputs_by_id[account.account_id]

        output_accounts.append(
            {
                "account_id": account.account_id,
                "account_label": account.account_label,
                "post_count": int(account.activity["post_count"]),
                "base_bot_probability": round(account.base_bot_probability, 6),
                "final_bot_probability": final_output["final_bot_probability"],
                "base_prediction": account.base_prediction,
                "final_prediction": final_output["final_prediction"],
                "confidence_deficit": round(account.confidence_deficit, 6),
                "local_reliability": round(local_reliability, 6),
                "correction_risk": round(correction_risk, 6),
                "routed": final_output["routed"],
                "hyperedge": {
                    "center": account.account_id,
                    "support_nodes": [row["account_id"] for row in support_rows],
                    "support_k": len(support_rows),
                    "support_bot_probability_mean": round(support_mean, 6),
                },
                "support_evidence": support_rows,
                "signals": account.activity["signals"],
            }
        )

    output_accounts.sort(
        key=lambda row: (
            -float(row["final_bot_probability"]),
            -float(row["correction_risk"]),
            str(row["account_id"]),
        )
    )
    routed_count = sum(1 for row in output_accounts if row["routed"])
    return {
        "method": "BotRHG",
        "accounts": output_accounts,
        "summary": {
            "account_count": len(output_accounts),
            "routed_count": routed_count,
            "routing_budget": budget,
            "support_k": k,
            "bot_count": sum(1 for row in output_accounts if row["final_prediction"] == "bot"),
        },
        "model_card": {
            "paper_title": "BotRHG: Reliability-Guided Hypergraph Learning for Social Bot Detection",
            "feature_encoder": "profile_description_tweets_plus_properties",
            "hypergraph_construction": "target_centered_knn_support_hyperedges",
            "routing": "local_reference_reliability_top_budget",
            "selective_rule": "preserve_base_unless_routed",
            "research_source": "internal_legacy_proxy",
            "system_adapter": "deterministic_inference_proxy",
        },
    }


def _empty_result(routing_budget: float, support_k: int) -> dict[str, Any]:
    return {
        "method": "BotRHG",
        "accounts": [],
        "summary": {
            "account_count": 0,
            "routed_count": 0,
            "routing_budget": routing_budget,
            "support_k": support_k,
            "bot_count": 0,
        },
        "model_card": {
            "paper_title": "BotRHG: Reliability-Guided Hypergraph Learning for Social Bot Detection",
            "feature_encoder": "profile_description_tweets_plus_properties",
            "hypergraph_construction": "target_centered_knn_support_hyperedges",
            "routing": "local_reference_reliability_top_budget",
            "selective_rule": "preserve_base_unless_routed",
            "research_source": "internal_legacy_proxy",
            "system_adapter": "deterministic_inference_proxy",
        },
    }


def _build_account_evidence(posts: list[dict[str, Any]]) -> list[AccountEvidence]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for post in posts:
        account_id = str(post.get("author_id") or "").strip()
        if account_id:
            grouped[account_id].append(post)

    accounts = []
    for account_id, rows in sorted(grouped.items()):
        activity = _activity_features(rows)
        base_probability = _base_probability(activity)
        accounts.append(
            AccountEvidence(
                account_id=account_id,
                account_label=activity["account_label"],
                posts=rows,
                feature_vector=_feature_vector(activity, base_probability),
                base_bot_probability=base_probability,
                base_prediction=_prediction_label(base_probability),
                confidence_deficit=1.0 - max(base_probability, 1.0 - base_probability),
                activity=activity,
            )
        )
    return accounts


def _activity_features(posts: list[dict[str, Any]]) -> dict[str, Any]:
    timestamps = sorted(_parse_timestamp(post.get("timestamp")) for post in posts)
    timestamps = [ts for ts in timestamps if ts is not None]
    intervals = np.diff([ts.timestamp() for ts in timestamps]) if len(timestamps) >= 2 else np.asarray([])
    post_count = len(posts)
    min_interval = float(np.min(intervals)) if intervals.size else 0.0
    avg_interval = float(np.mean(intervals)) if intervals.size else 0.0
    regularity = 0.0
    if intervals.size >= 2 and avg_interval > 0:
        regularity = _clamp(1.0 - float(np.std(intervals) / avg_interval), 0.0, 1.0)

    active_hours = len({ts.hour for ts in timestamps}) if timestamps else 0
    text_values = [_normalized_text(str(post.get("content") or "")) for post in posts]
    non_empty_texts = [text for text in text_values if text]
    duplicate_ratio = 0.0
    if non_empty_texts:
        duplicate_ratio = Counter(non_empty_texts).most_common(1)[0][1] / max(len(non_empty_texts), 1)
        if len(non_empty_texts) == 1:
            duplicate_ratio = 0.0

    url_marker_rate = _mean_bool(
        "httpurl" in text or "http://" in text or "https://" in text
        for text in text_values
    )
    hashtag_rate = _mean_bool(bool(post.get("hashtags")) for post in posts)
    followers, friends = _profile_counts(posts)
    follower_friend_imbalance = _clamp(friends / max(followers + friends, 1.0), 0.0, 1.0)
    low_follower_signal = 1.0 if followers < 50 and friends >= 100 else 0.0
    total_engagement = sum(
        int(post.get("likes") or 0) + int(post.get("reposts") or 0) + int(post.get("comments_count") or 0)
        for post in posts
    )
    engagement_per_post = total_engagement / max(post_count, 1)
    low_engagement_signal = 1.0 if post_count >= 3 and engagement_per_post < 1.0 else 0.0

    burst_signal = 0.0
    if min_interval > 0 and min_interval < 60:
        burst_signal = 1.0 - min_interval / 60.0
    low_active_window_signal = 1.0 if post_count >= 3 and active_hours <= 2 else 0.0

    signals = {
        "regularity": round(regularity, 6),
        "burst": round(burst_signal, 6),
        "duplicate_content": round(duplicate_ratio, 6),
        "url_marker_rate": round(url_marker_rate, 6),
        "hashtag_rate": round(hashtag_rate, 6),
        "follower_friend_imbalance": round(follower_friend_imbalance, 6),
        "low_follower_signal": low_follower_signal,
        "low_engagement_signal": low_engagement_signal,
        "low_active_window_signal": low_active_window_signal,
    }
    return {
        "account_label": _account_label(posts),
        "post_count": post_count,
        "min_interval_seconds": min_interval,
        "avg_interval_seconds": avg_interval,
        "active_hours": active_hours,
        "followers": followers,
        "friends": friends,
        "signals": signals,
    }


def _base_probability(activity: dict[str, Any]) -> float:
    signals = activity["signals"]
    post_count = int(activity["post_count"])
    risk_signal = (
        0.22 * float(signals["regularity"])
        + 0.22 * float(signals["burst"])
        + 0.18 * float(signals["duplicate_content"])
        + 0.12 * float(signals["url_marker_rate"])
        + 0.10 * float(signals["follower_friend_imbalance"])
        + 0.07 * float(signals["low_follower_signal"])
        + 0.06 * float(signals["low_active_window_signal"])
        + 0.03 * min(post_count / 8.0, 1.0)
    )
    return _clamp(_sigmoid(4.0 * (risk_signal - 0.38)), 0.01, 0.99)


def _feature_vector(activity: dict[str, Any], base_probability: float) -> np.ndarray:
    signals = activity["signals"]
    return np.asarray(
        [
            base_probability,
            min(float(activity["post_count"]) / 10.0, 1.0),
            float(signals["regularity"]),
            float(signals["burst"]),
            float(signals["duplicate_content"]),
            float(signals["url_marker_rate"]),
            float(signals["follower_friend_imbalance"]),
            float(signals["low_follower_signal"]),
            float(signals["low_active_window_signal"]),
        ],
        dtype=float,
    )


def _cosine_similarity_matrix(matrix: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    norms[norms <= 0.0] = 1.0
    normalized = matrix / norms
    return np.clip(normalized @ normalized.T, -1.0, 1.0)


def _support_neighbors(accounts: list[AccountEvidence], similarity: np.ndarray, k: int) -> list[list[int]]:
    neighbors = []
    for index in range(len(accounts)):
        candidates = [candidate for candidate in range(len(accounts)) if candidate != index]
        candidates.sort(key=lambda candidate: (-float(similarity[index, candidate]), accounts[candidate].account_id))
        neighbors.append(candidates[:k])
    return neighbors


def _local_reliability(accounts: list[AccountEvidence], similarity: np.ndarray) -> dict[str, float]:
    reliabilities = {}
    uncertainties = np.asarray([account.confidence_deficit for account in accounts], dtype=float)
    for index, account in enumerate(accounts):
        numerator = 1.0
        denominator = 1.0
        for ref_index, _ in enumerate(accounts):
            if ref_index == index:
                continue
            cosine = float(similarity[index, ref_index])
            distance = math.sqrt(max(0.0, 2.0 - 2.0 * cosine))
            weight = math.exp(-distance)
            denominator += weight
            if uncertainties[ref_index] >= uncertainties[index]:
                numerator += weight
        reliabilities[account.account_id] = _clamp(numerator / denominator, 0.0, 1.0)
    return reliabilities


def _select_routed(
    accounts: list[AccountEvidence],
    reliabilities: dict[str, float],
    routing_budget: float,
) -> set[str]:
    count = int(math.floor(routing_budget * len(accounts)))
    if routing_budget > 0.0 and accounts:
        count = max(1, count)
    ranked = sorted(
        accounts,
        key=lambda account: (
            -(1.0 - reliabilities[account.account_id]),
            -account.confidence_deficit,
            account.account_id,
        ),
    )
    return {account.account_id for account in ranked[:count]}


def _support_rows(
    accounts: list[AccountEvidence],
    support_indices: list[int],
    similarity_row: np.ndarray,
) -> list[dict[str, Any]]:
    rows = []
    for index in support_indices:
        account = accounts[index]
        rows.append(
            {
                "account_id": account.account_id,
                "similarity": round(float(similarity_row[index]), 6),
                "base_bot_probability": round(account.base_bot_probability, 6),
                "base_prediction": account.base_prediction,
            }
        )
    return rows


def _enrich_support_rows(
    rows: list[dict[str, Any]],
    final_outputs_by_id: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    enriched = []
    for row in rows:
        final_output = final_outputs_by_id.get(str(row["account_id"]), {})
        enriched.append(
            {
                **row,
                "final_bot_probability": final_output.get("final_bot_probability", row["base_bot_probability"]),
                "final_prediction": final_output.get("final_prediction", row["base_prediction"]),
                "routed": bool(final_output.get("routed", False)),
            }
        )
    return enriched


def _weighted_support_bot_probability(rows: list[dict[str, Any]]) -> float:
    if not rows:
        return 0.5
    weights = np.asarray([max(float(row["similarity"]), 0.0) + 1e-6 for row in rows], dtype=float)
    values = np.asarray([float(row["base_bot_probability"]) for row in rows], dtype=float)
    return float(np.average(values, weights=weights))


def _profile_counts(posts: list[dict[str, Any]]) -> tuple[float, float]:
    for post in posts:
        profile = post.get("author_profile")
        if isinstance(profile, dict):
            followers = _first_number(profile, ("followers_count", "followers", "fan_count", "fans_count"))
            friends = _first_number(profile, ("friends_count", "following_count", "follow_count", "follows_count"))
            if followers is not None or friends is not None:
                return float(followers or 0), float(friends or 0)
        raw_data = post.get("raw_data")
        if isinstance(raw_data, dict):
            user = raw_data.get("user")
            if not isinstance(user, dict):
                mblog = raw_data.get("mblog")
                user = mblog.get("user") if isinstance(mblog, dict) else None
            if isinstance(user, dict):
                followers = _first_number(user, ("followers_count", "followers", "fan_count", "fans_count"))
                friends = _first_number(user, ("friends_count", "following_count", "follow_count", "follows_count"))
                if followers is not None or friends is not None:
                    return float(followers or 0), float(friends or 0)
    return 0.0, 0.0


def _first_number(source: dict[str, Any], keys: tuple[str, ...]) -> float | None:
    for key in keys:
        value = source.get(key)
        if value is None:
            continue
        try:
            return float(value)
        except (TypeError, ValueError):
            continue
    return None


def _account_label(posts: list[dict[str, Any]]) -> str:
    for post in posts:
        for key in ("author_name", "nickname", "screen_name"):
            value = str(post.get(key) or "").strip()
            if value:
                return value
        profile = post.get("author_profile")
        if isinstance(profile, dict):
            value = str(profile.get("screen_name") or profile.get("nickname") or "").strip()
            if value:
                return value
    return str(posts[0].get("author_id") or "")


def _parse_timestamp(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    text = str(value).strip()
    if not text:
        return None
    try:
        return pd.to_datetime(text, errors="coerce", utc=True).to_pydatetime()
    except Exception:
        return None


def _normalized_text(value: str) -> str:
    text = value.lower()
    text = re.sub(r"https?://\S+", "httpurl", text)
    text = re.sub(r"@\w+", "@user", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _mean_bool(values: Any) -> float:
    raw = [bool(value) for value in values]
    if not raw:
        return 0.0
    return float(sum(raw) / len(raw))


def _prediction_label(probability: float) -> str:
    return "bot" if probability >= 0.5 else "human"


def _sigmoid(value: float) -> float:
    return 1.0 / (1.0 + math.exp(-value))


def _clamp(value: float, lower: float, upper: float) -> float:
    return max(lower, min(upper, value))
