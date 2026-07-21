from __future__ import annotations

import math
from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Any, Mapping, Sequence

import numpy as np
import pandas as pd

from app.core.account_profiler import build_account_profiles
from app.core.propagation_analysis import build_propagation_graph
from app.core.risk.disarm_scorer import map_evidence_to_techniques, score_attack_path_full
from app.core.risk.ds_fusion import fuse_evidence
from app.core.risk.evidence_builder import build_evidence_pack
from app.core.risk.phase_detector import detect_phase
from app.core.risk.report_builder import build_report


def _safe_divide(numerator: float, denominator: float) -> float:
    return float(numerator / denominator) if denominator else 0.0


def _clamp(value: float, lower: float = 0.0, upper: float = 1.0) -> float:
    return max(lower, min(upper, float(value)))


def _object_kind(object_id: str) -> str:
    text = str(object_id or "").strip().lower()
    if not text:
        return "content"
    if text.startswith("http://") or text.startswith("https://"):
        if any(text.endswith(ext) for ext in (".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".svg")):
            return "image"
        if any(text.endswith(ext) for ext in (".mp4", ".mov", ".avi", ".mkv", ".webm", ".m3u8")):
            return "video"
        return "url"
    if text.startswith("#") or text.startswith("topic"):
        return "hashtag"
    if text.startswith("tweet:") or text.startswith("post:") or text.startswith("comment:"):
        return "content"
    return "content"


def _dominant_label(counter: Counter[str], default: str) -> str:
    if not counter:
        return default
    return counter.most_common(1)[0][0]


def _account_id_from_profile(profile: Mapping[str, Any]) -> str:
    return str(profile.get("account_id") or "").strip()


def _convert_events_to_posts(events: pd.DataFrame) -> list[dict[str, Any]]:
    posts: list[dict[str, Any]] = []
    for row in events.to_dict(orient="records"):
        relation = str(row.get("relation") or "")
        object_id = str(row.get("object_id") or "")
        record = {
            "author_id": str(row.get("account_id") or ""),
            "author_name": str(row.get("author_name") or row.get("account_label") or row.get("account_id") or ""),
            "post_id": str(row.get("content_id") or ""),
            "timestamp": row.get("timestamp"),
            "content": str(row.get("content") or ""),
            "url": object_id if _object_kind(object_id) == "url" else "",
            "shared_urls": [object_id] if relation == "url_share" and _object_kind(object_id) == "url" else [],
            "media_urls": [object_id] if relation in {"media_share", "image_share", "video_share"} or _object_kind(object_id) in {"image", "video"} else [],
            "hashtags": [object_id] if relation == "hashtag_share" or _object_kind(object_id) == "hashtag" else [],
            "likes": 0,
            "reposts": int(relation == "retweet_target"),
            "comments_count": int(relation == "reply_target"),
        }
        posts.append(record)
    return posts


def _relation_counter(events: pd.DataFrame) -> Counter[str]:
    counter: Counter[str] = Counter()
    if "relation" not in events.columns:
        return counter
    for relation, count in events["relation"].astype(str).value_counts().items():
        counter[str(relation)] = int(count)
    return counter


def _target_group_from_community(community: Mapping[str, Any], events: pd.DataFrame) -> str:
    relation_breakdown = community.get("relation_breakdown", {})
    if isinstance(relation_breakdown, Mapping):
        if any(str(key).endswith("reply_target") for key in relation_breakdown):
            return "targeted_accounts"
        if any(str(key).endswith("mention_target") for key in relation_breakdown):
            return "mentioned_accounts"
    object_ids = [str(entry.get("object_id") or "") for entry in community.get("top_objects", []) if isinstance(entry, Mapping)]
    if any(_object_kind(object_id) == "url" for object_id in object_ids):
        return "narrative_consumers"
    if any(_object_kind(object_id) == "hashtag" for object_id in object_ids):
        return "topic_audience"
    if not events.empty and "target_account_id" in events.columns:
        cluster_accounts = set(map(str, community.get("accounts", []) or community.get("top_nodes", []) or []))
        targeted = events[
            events["account_id"].astype(str).isin(cluster_accounts)
            & events["target_account_id"].fillna("").astype(str).ne("")
        ]
        if not targeted.empty:
            return "targeted_accounts"
    return "general_audience"


def _claim_status_from_community(community: Mapping[str, Any]) -> str:
    top_objects = community.get("top_objects", [])
    if not isinstance(top_objects, Sequence):
        return "unknown"
    url_like = 0
    content_like = 0
    for entry in top_objects:
        if not isinstance(entry, Mapping):
            continue
        object_kind = _object_kind(str(entry.get("object_id") or ""))
        if object_kind == "url":
            url_like += 1
        elif object_kind == "content":
            content_like += 1
    if url_like and content_like:
        return "mixed_claims"
    if url_like:
        return "linked_claims"
    if content_like:
        return "content_claims"
    return "unknown"


def _frame_from_community(community: Mapping[str, Any], events: pd.DataFrame) -> str:
    relation_breakdown = community.get("relation_breakdown", {})
    if isinstance(relation_breakdown, Mapping):
        counts = {str(key): int(value) for key, value in relation_breakdown.items()}
        if counts.get("reply_target", 0) >= max(counts.get("retweet_target", 0), counts.get("url_share", 0), 1):
            return "targeted_engagement"
        if counts.get("retweet_target", 0) >= max(counts.get("reply_target", 0), counts.get("url_share", 0), 1):
            return "amplification"
        if counts.get("url_share", 0) >= max(counts.get("retweet_target", 0), counts.get("hashtag_share", 0), 1):
            return "narrative_link_sharing"
        if counts.get("hashtag_share", 0) > 0:
            return "topic_framing"
    content = " ".join(events.get("content", pd.Series(dtype=str)).fillna("").astype(str).tolist()).lower()
    if any(token in content for token in ("hate", "attack", "abuse", "harass")):
        return "aggressive_frame"
    if any(token in content for token in ("story", "report", "claim", "fact")):
        return "claim_repetition"
    return "general_coordination"


def _appeal_from_community(community: Mapping[str, Any], events: pd.DataFrame) -> str:
    relation_breakdown = community.get("relation_breakdown", {})
    if isinstance(relation_breakdown, Mapping):
        if int(relation_breakdown.get("mention_target", 0)) > 0 or int(relation_breakdown.get("reply_target", 0)) > 0:
            return "social_pressure"
        if int(relation_breakdown.get("retweet_target", 0)) > 0:
            return "bandwagon"
    content = " ".join(events.get("content", pd.Series(dtype=str)).fillna("").astype(str).tolist()).lower()
    if any(token in content for token in ("urgent", "now", "must", "immediately")):
        return "urgency"
    return "attention"


def _orchestration_type(community: Mapping[str, Any], events: pd.DataFrame) -> tuple[str, float, dict[str, float]]:
    size = max(int(community.get("size") or 0), 1)
    density = float(community.get("density", 0.0) or 0.0)
    community_score = float(community.get("community_score", 0.0) or 0.0)
    object_concentration = float(community.get("object_concentration", 0.0) or 0.0)
    avg_time_delta = community.get("avg_time_delta")
    avg_time_delta_value = float(avg_time_delta) if avg_time_delta not in {None, ""} else 0.0

    if events.empty:
        cluster_events = events
    else:
        accounts = set(map(str, community.get("accounts", []) or community.get("top_nodes", []) or []))
        cluster_events = events[events["account_id"].astype(str).isin(accounts)] if accounts else events.iloc[0:0]

    account_counts = cluster_events["account_id"].astype(str).value_counts() if not cluster_events.empty else pd.Series(dtype=int)
    control_concentration = float(account_counts.max() / max(account_counts.sum(), 1)) if not account_counts.empty else 0.0
    role_asymmetry = _clamp(control_concentration * 0.7 + object_concentration * 0.3)
    community_coupling = _clamp(density * 0.5 + community_score * 0.5)
    organic_baseline_gap = _clamp(object_concentration - min(0.5, 1.0 / size) + (0.15 if avg_time_delta_value and avg_time_delta_value <= 2 else 0.0))

    if role_asymmetry >= 0.55 and community_coupling >= 0.45:
        label = "centralized"
        confidence = _clamp(0.45 + role_asymmetry * 0.3 + community_coupling * 0.25)
    elif community_coupling >= 0.35 and organic_baseline_gap >= 0.15:
        label = "decentralized"
        confidence = _clamp(0.4 + community_coupling * 0.3 + organic_baseline_gap * 0.3)
    elif organic_baseline_gap <= 0.12 and density <= 0.45:
        label = "emergent"
        confidence = _clamp(0.35 + (1.0 - organic_baseline_gap) * 0.2 + (1.0 - min(density, 1.0)) * 0.15)
    else:
        label = "uncertain"
        confidence = 0.35

    evidence = {
        "control_concentration": round(control_concentration, 6),
        "role_asymmetry": round(role_asymmetry, 6),
        "community_coupling": round(community_coupling, 6),
        "organic_baseline_gap": round(organic_baseline_gap, 6),
    }
    return label, round(confidence, 6), evidence


def _temporal_archetype(community: Mapping[str, Any], cluster_events: pd.DataFrame, phase: Mapping[str, Any] | None = None) -> tuple[str, float, dict[str, Any]]:
    timestamps = cluster_events["timestamp"].tolist() if "timestamp" in cluster_events.columns else []
    numeric_ts = sorted([float(value) for value in timestamps if value not in ("", None)])
    if len(numeric_ts) >= 2:
        lifetime_span = float(numeric_ts[-1] - numeric_ts[0])
        intervals = [numeric_ts[idx + 1] - numeric_ts[idx] for idx in range(len(numeric_ts) - 1)]
        if intervals and float(np.mean(intervals)) > 0:
            burstiness = float(np.std(intervals) / max(np.mean(intervals), 1e-9))
        else:
            burstiness = 0.0
    else:
        lifetime_span = 0.0
        burstiness = 0.0

    distinct_objects = cluster_events["object_id"].astype(str).nunique() if "object_id" in cluster_events.columns and not cluster_events.empty else 0
    distinct_relations = cluster_events["relation"].astype(str).nunique() if "relation" in cluster_events.columns and not cluster_events.empty else 0
    unique_accounts = cluster_events["account_id"].astype(str).nunique() if "account_id" in cluster_events.columns and not cluster_events.empty else 0
    adaptation_rate = _clamp(_safe_divide(distinct_objects + distinct_relations, max(unique_accounts, 1) * 2.0))
    membership_shift = _clamp(_safe_divide(unique_accounts, max(int(community.get("size") or 0), 1)))
    phase_name = str((phase or {}).get("current_phase") or "").strip().lower()
    phase_transitions = [phase_name] if phase_name else []

    if burstiness >= 1.5 and lifetime_span <= 10:
        label = "bursty"
        confidence = _clamp(0.45 + min(burstiness / 4.0, 0.45))
    elif adaptation_rate >= 0.45 or phase_name == "regeneration":
        label = "adaptive"
        confidence = _clamp(0.4 + adaptation_rate * 0.4)
    elif lifetime_span >= 20 and burstiness <= 0.8:
        label = "stable"
        confidence = _clamp(0.4 + min(lifetime_span / 100.0, 0.4))
    elif lifetime_span > 0 and burstiness < 0.3 and len(numeric_ts) <= 3:
        label = "dormant"
        confidence = 0.45
    else:
        label = "adaptive" if distinct_objects > 2 else "stable"
        confidence = 0.35

    timeline = []
    if not cluster_events.empty:
        for row in cluster_events.sort_values("timestamp").head(10).to_dict(orient="records"):
            timeline.append(
                {
                    "timestamp": row.get("timestamp"),
                    "account_id": str(row.get("account_id") or ""),
                    "relation": str(row.get("relation") or ""),
                    "object_id": str(row.get("object_id") or ""),
                    "content": str(row.get("content") or "")[:120],
                }
            )

    evidence = {
        "lifetime_span": round(lifetime_span, 6),
        "phase_transitions": phase_transitions,
        "adaptation_rate": round(adaptation_rate, 6),
        "membership_shift": round(membership_shift, 6),
        "burstiness": round(burstiness, 6),
        "evidence_timeline": timeline,
    }
    return label, round(confidence, 6), evidence


def _harm_type_from_report(report: Mapping[str, Any], community: Mapping[str, Any], cluster_events: pd.DataFrame) -> str:
    disarm = report.get("disarm_analysis", {}) if isinstance(report.get("disarm_analysis"), Mapping) else {}
    observed = disarm.get("observed_techniques", [])
    names = " ".join(str(item.get("name") or "").lower() for item in observed if isinstance(item, Mapping))
    if "amplify existing narrative" in names or "post content" in names:
        return "misinformation"
    if "flood information space" in names or "coordinate activity" in names:
        return "influence_operation"
    frame = _frame_from_community(community, cluster_events)
    if "aggressive" in frame:
        return "harassment"
    if "claim" in frame or "narrative" in frame:
        return "propaganda"
    return "general_harm"


def _severity_from_report(report: Mapping[str, Any], community: Mapping[str, Any], temporal_confidence: float) -> tuple[str, float]:
    scores = report.get("scores", {}) if isinstance(report.get("scores"), Mapping) else {}
    overall = float(scores.get("overall_risk_score", 0.0) or 0.0)
    object_concentration = float(community.get("object_concentration", 0.0) or 0.0)
    severity_score = _clamp(overall / 100.0 * 0.6 + object_concentration * 0.2 + temporal_confidence * 0.2)
    if severity_score >= 0.75:
        return "high", round(severity_score, 6)
    if severity_score >= 0.45:
        return "medium", round(severity_score, 6)
    return "low", round(severity_score, 6)


def _community_account_profiles(profile_rows: Sequence[Mapping[str, Any]], community_accounts: set[str]) -> list[Mapping[str, Any]]:
    return [row for row in profile_rows if _account_id_from_profile(row) in community_accounts]


def _build_profile_rows(events: pd.DataFrame) -> list[dict[str, Any]]:
    if events.empty:
        return []
    posts = _convert_events_to_posts(events)
    return build_account_profiles(posts)


def _build_report_inputs(events: pd.DataFrame, community: Mapping[str, Any], profile_rows: Sequence[Mapping[str, Any]]) -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
    accounts = set(map(str, community.get("accounts", []) or community.get("top_nodes", []) or []))
    cluster_events = events[events["account_id"].astype(str).isin(accounts)].copy() if accounts else events.iloc[0:0].copy()
    coord_data = {
        "network": {
            "nodes": [{"id": account_id} for account_id in sorted(accounts)],
            "edges": [],
            "node_count": len(accounts),
            "edge_count": max(int(community.get("size", 0)) - 1, 0),
            "component_count": 1 if accounts else 0,
            "components": [{"size": len(accounts), "accounts": sorted(accounts)}] if accounts else [],
        },
        "summary": {
            "total_pairs": max(int(community.get("size", 0)) - 1, 0),
            "coordinated_accounts": len(accounts),
            "coordinated_edges": max(int(community.get("size", 0)) - 1, 0),
        },
        "account_stats": [
            {"account_id": account_id, "degree": 1, "avg_weight": float(community.get("community_score", 0.0) or 0.0), "coordinated_shares_count": len(cluster_events)}
            for account_id in sorted(accounts)
        ],
    }
    propagation = build_propagation_graph(_convert_events_to_posts(cluster_events), comments=[])
    acct_data = [dict(row) for row in _community_account_profiles(profile_rows, accounts)]
    return coord_data, propagation, acct_data


@dataclass
class CharacterizationConfig:
    include_risk_report: bool = True
    include_observer_lens: bool = True
    observer_lens: str = "network_security"


def characterize_detect_output(
    *,
    events: pd.DataFrame,
    discovery: Mapping[str, Any],
    predictions: Sequence[Mapping[str, Any]] | None = None,
    config: CharacterizationConfig | None = None,
) -> dict[str, Any]:
    cfg = config or CharacterizationConfig()
    normalized = events.copy()
    if not normalized.empty:
        normalized["account_id"] = normalized["account_id"].astype(str)
        if "relation" in normalized.columns:
            normalized["relation"] = normalized["relation"].astype(str)
        if "object_id" in normalized.columns:
            normalized["object_id"] = normalized["object_id"].astype(str)
    communities = [community for community in discovery.get("communities", []) if isinstance(community, Mapping)]
    prediction_rows = [row for row in (predictions or []) if isinstance(row, Mapping)]
    predictions_by_cluster: dict[object, list[Mapping[str, Any]]] = defaultdict(list)
    for row in prediction_rows:
        predictions_by_cluster[row.get("cluster_id")].append(row)

    profile_rows = _build_profile_rows(normalized)
    profile_by_account = {_account_id_from_profile(row): row for row in profile_rows}
    relation_counts = _relation_counter(normalized)

    characterization_records: list[dict[str, Any]] = []
    aggregate_authenticity_scores: list[float] = []
    aggregate_harm_scores: list[float] = []
    orchestration_counter: Counter[str] = Counter()
    temporal_counter: Counter[str] = Counter()

    for community in communities:
        accounts = set(map(str, community.get("accounts", []) or community.get("top_nodes", []) or []))
        if not accounts:
            top_nodes = community.get("top_nodes", [])
            accounts = set(map(str, top_nodes if isinstance(top_nodes, Sequence) else []))
        cluster_events = normalized[normalized["account_id"].isin(accounts)].copy() if accounts else normalized.iloc[0:0].copy()
        community_predictions = predictions_by_cluster.get(community.get("cluster_id"), [])
        community_profiles = _community_account_profiles(profile_rows, accounts)
        automation_scores = [float(row.get("automation_score", 0.0) or 0.0) for row in community_profiles]
        high_automation_ratio = _safe_divide(sum(1 for score in automation_scores if score >= 60.0), len(automation_scores))
        avg_automation = _safe_divide(sum(automation_scores), len(automation_scores))
        profile_label_counter = Counter()
        if high_automation_ratio >= 0.6:
            profile_label_counter["bot_network"] += 2
        elif high_automation_ratio >= 0.3:
            profile_label_counter["cyborg_mixture"] += 2
        elif community_profiles:
            profile_label_counter["likely_authentic"] += 1
        if avg_automation >= 75:
            profile_label_counter["bot_network"] += 1
        if avg_automation >= 45 and avg_automation < 75:
            profile_label_counter["cyborg_mixture"] += 1
        authenticity_label = _dominant_label(profile_label_counter, "unknown")
        authenticity_score = round(_clamp(1.0 - avg_automation / 100.0), 6) if automation_scores else 0.5
        authenticity_confidence = round(_clamp(0.35 + high_automation_ratio * 0.45 + (0.15 if community_profiles else 0.0)), 6)
        authenticity_evidence = {
            "community_size": int(community.get("size") or len(accounts)),
            "high_automation_ratio": round(high_automation_ratio, 6),
            "avg_automation_score": round(avg_automation, 6),
            "regularity_mean": round(_safe_divide(sum(float(row.get("regularity", 0.0) or 0.0) for row in community_profiles), len(community_profiles)), 6) if community_profiles else 0.0,
            "evidence_channels": ["account_behavior", "discover_structure"] + (["content_metadata"] if not cluster_events.empty else []),
        }

        orchestration_label, orchestration_confidence, orchestration_evidence = _orchestration_type(community, cluster_events)

        coord_data, propagation, acct_data = _build_report_inputs(normalized, community, profile_rows)
        evidence_pack = build_evidence_pack(coord_data, propagation, acct_data)
        phase = detect_phase(evidence_pack)
        fusion = fuse_evidence(evidence_pack, phase)
        disarm = score_attack_path_full(evidence_pack, phase, fusion)
        report = build_report(
            event_id=str(community.get("cluster_id")),
            platform="characterization",
            evidence_pack=evidence_pack,
            phase_result=phase,
            fusion_result=fusion,
            disarm_result=disarm,
        )
        temporal_label, temporal_confidence, temporal_evidence = _temporal_archetype(
            community,
            cluster_events,
            phase=report.get("phase") if isinstance(report.get("phase"), Mapping) else None,
        )
        harm_type = _harm_type_from_report(report, community, cluster_events)
        severity_label, severity_score = _severity_from_report(report, community, temporal_confidence)
        harmfulness_confidence = round(_clamp(0.35 + severity_score * 0.4 + orchestration_confidence * 0.2), 6)
        harmfulness_evidence = {
            "target_group": _target_group_from_community(community, cluster_events),
            "claim_status": _claim_status_from_community(community),
            "frame": _frame_from_community(community, cluster_events),
            "appeal": _appeal_from_community(community, cluster_events),
            "evidence_snippets": [
                str(entry.get("content_preview") or entry.get("object_id") or "")
                for entry in propagation.get("claims", [])[:3]
                if isinstance(entry, Mapping)
            ] or [str(item.get("object_id") or "") for item in community.get("top_objects", [])[:3] if isinstance(item, Mapping)],
            "observer_lens": cfg.observer_lens if cfg.include_observer_lens else None,
        }

        if community_predictions:
            detect_node_scores = [float(row.get("node_score", 0.0) or 0.0) for row in community_predictions]
            detect_risk = round(float(np.mean(detect_node_scores)), 6)
        else:
            detect_risk = round(float(community.get("community_score", 0.0) or 0.0), 6)

        community_record = {
            "cluster_id": community.get("cluster_id"),
            "accounts": sorted(accounts),
            "authenticity": {
                "label": authenticity_label,
                "authenticity_score": authenticity_score,
                "inauthenticity_type": authenticity_label,
                "confidence": authenticity_confidence,
                "evidence": authenticity_evidence,
            },
            "harmfulness": {
                "label": severity_label,
                "harm_type": harm_type,
                "severity": severity_label,
                "severity_score": severity_score,
                "confidence": harmfulness_confidence,
                "evidence": harmfulness_evidence,
            },
            "orchestration": {
                "label": orchestration_label,
                "orchestration_type": orchestration_label,
                "confidence": orchestration_confidence,
                "evidence": orchestration_evidence,
            },
            "time_variance": {
                "label": temporal_label,
                "temporal_archetype": temporal_label,
                "confidence": temporal_confidence,
                "evidence": temporal_evidence,
            },
            "detect_bridge": {
                "community_score": float(community.get("community_score", 0.0) or 0.0),
                "detect_node_score_mean": detect_risk,
                "top_objects": community.get("top_objects", []),
                "relation_breakdown": community.get("relation_breakdown", {}),
            },
        }
        if cfg.include_risk_report:
            community_record["risk_report"] = report

        aggregate_authenticity_scores.append(authenticity_score)
        aggregate_harm_scores.append(severity_score)
        orchestration_counter[orchestration_label] += 1
        temporal_counter[temporal_label] += 1
        characterization_records.append(community_record)

    summary = {
        "community_count": len(characterization_records),
        "dimension_support": {
            "authenticity": bool(profile_rows),
            "harmfulness": bool(characterization_records),
            "orchestration": bool(communities),
            "time_variance": bool(communities),
        },
        "aggregate": {
            "mean_authenticity_score": round(float(np.mean(aggregate_authenticity_scores)), 6) if aggregate_authenticity_scores else 0.0,
            "mean_harm_severity_score": round(float(np.mean(aggregate_harm_scores)), 6) if aggregate_harm_scores else 0.0,
            "orchestration_distribution": dict(orchestration_counter),
            "temporal_archetype_distribution": dict(temporal_counter),
            "global_relation_breakdown": dict(relation_counts),
        },
    }
    return {
        "task": "coordination_characterization",
        "method": "detect_then_characterize",
        "observer_lens": cfg.observer_lens if cfg.include_observer_lens else None,
        "communities": characterization_records,
        "summary": summary,
    }
