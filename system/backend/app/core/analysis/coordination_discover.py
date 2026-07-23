from __future__ import annotations

import hashlib
import random
import re
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from statistics import mean, median, pstdev
from typing import Any

import pandas as pd

from app.core.analysis.contracts import EventSnapshot
from app.core.coordination_baseline import account_stats as coordination_account_stats
from app.core.coordination_baseline import detect_groups, generate_coordinated_network, group_stats as coordination_group_stats
from app.core.coordination_baseline.network import graph_to_dict

TOKEN_PATTERN = re.compile(r"[\u4e00-\u9fff]|[A-Za-z0-9_]+")
WINDOW_SCALES_HOURS = (1, 6, 24)
DEFAULT_OVERLAP_RATIO = 0.5
DEFAULT_MAX_SLICES_PER_SCALE = 12


def build_coordination_discover_evidence_edges(
    snapshot: EventSnapshot,
    options: dict[str, Any] | None = None,
) -> dict[str, Any]:
    options = dict(options or {})
    content_index = _build_content_index(snapshot)
    evidence_edges: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()

    for row in [*snapshot.posts, *snapshot.comments]:
        content_ref = _content_ref(row)
        account_id = _text(row.get("author_id"))
        timestamp = _timestamp_seconds(row.get("timestamp"))
        platform = _text(row.get("platform")) or "unknown"
        for edge in _content_evidence_edges(
            row,
            content_ref=content_ref,
            account_id=account_id,
            timestamp=timestamp,
            platform=platform,
            content_index=content_index,
        ):
            key = (edge["source"], edge["target"], edge["evidence_kind"])
            if key in seen:
                continue
            seen.add(key)
            evidence_edges.append(edge)

    for relation in snapshot.relationships:
        source_ref = _text(relation.source_id)
        target_ref = _text(relation.target_id)
        source_row = content_index.get(source_ref)
        if not source_row:
            continue
        evidence_edges.append(
            {
                "source": source_row["account_id"],
                "target": f"native_relation:{relation.relation_type}:{target_ref}",
                "content_id": source_ref,
                "source_content_id": source_ref,
                "target_content_id": target_ref,
                "evidence_kind": "native_relation",
                "relation_type": relation.relation_type,
                "evidence_ref": f"{source_ref}:{relation.relation_type}:{target_ref}",
                "platform": relation.platform,
                "weight": 1.0,
                "observed_at": _timestamp_seconds(relation.observed_at),
            }
        )

    for signature, members in _near_duplicate_groups(content_index).items():
        if len(members) < 2:
            continue
        object_id = f"near_duplicate:{signature}"
        for member in members:
            evidence_edges.append(
                {
                    "source": member["account_id"],
                    "target": object_id,
                    "content_id": member["content_ref"],
                    "source_content_id": member["content_ref"],
                    "target_content_id": object_id,
                    "evidence_kind": "near_duplicate",
                    "relation_type": "near_duplicate",
                    "evidence_ref": f"{member['content_ref']}:{object_id}",
                    "platform": member["platform"],
                    "weight": 0.75,
                    "observed_at": member["timestamp_share"],
                }
            )

    evidence_edges = _dedupe_edges(evidence_edges)
    evidence_rows = _edges_to_rows(evidence_edges)
    coverage = Counter(edge["evidence_kind"] for edge in evidence_edges)
    return {
        "status": "ok" if evidence_edges else "data_insufficient",
        "technology": "coordination_discover",
        "snapshot_id": snapshot.snapshot_id,
        "event_id": snapshot.event_id,
        "evidence_edges": evidence_edges,
        "evidence_rows": evidence_rows,
        "coverage": {
            "kind_counts": dict(coverage),
            "row_count": len(evidence_rows),
            "content_count": len(content_index),
            "coverage_ratio": round(len(evidence_rows) / max(len(content_index), 1), 6) if content_index else 0.0,
        },
        "summary": {
            "evidence_edge_count": len(evidence_edges),
            "content_count": len(content_index),
            "evidence_kind_count": len(coverage),
        },
    }


def analyze_coordination_discover_snapshot(
    snapshot: EventSnapshot,
    options: dict[str, Any] | None = None,
) -> dict[str, Any]:
    options = dict(options or {})
    edge_bundle = build_coordination_discover_evidence_edges(snapshot, options)
    rows = edge_bundle["evidence_rows"]
    time_window_seconds = int(options.get("time_window", 60) or 60)
    min_participation = int(options.get("min_participation", 2) or 2)
    edge_weight = float(options.get("edge_weight", 0.5) or 0.5)
    window_hours = _normalize_window_hours(options.get("window_hours"))
    overlap_ratio = float(options.get("overlap_ratio", DEFAULT_OVERLAP_RATIO) or DEFAULT_OVERLAP_RATIO)
    max_slices_per_scale = int(options.get("max_slices_per_scale", DEFAULT_MAX_SLICES_PER_SCALE) or DEFAULT_MAX_SLICES_PER_SCALE)

    global_result = _analyze_rows(
        rows,
        time_window_seconds=time_window_seconds,
        min_participation=min_participation,
        edge_weight=edge_weight,
    )
    windows = _analyze_overlapping_windows(
        rows,
        window_hours=window_hours,
        overlap_ratio=overlap_ratio,
        min_participation=min_participation,
        edge_weight=edge_weight,
        max_slices_per_scale=max_slices_per_scale,
    )
    community_lineage = _build_community_lineage(windows)
    null_model = _estimate_null_model(
        rows,
        time_window_seconds=time_window_seconds,
        min_participation=min_participation,
        edge_weight=edge_weight,
        samples=int(options.get("null_model_samples", 12) or 12),
        seed=_seed_from_snapshot(snapshot),
        observed_edges=_summary_value(global_result, "coordinated_edges"),
    )
    perturbation = _estimate_robustness(
        rows,
        time_window_seconds=time_window_seconds,
        min_participation=min_participation,
        edge_weight=edge_weight,
        samples=int(options.get("perturbation_samples", 6) or 6),
        seed=_seed_from_snapshot(snapshot) ^ 0x5A17,
        observed_edges=_summary_value(global_result, "coordinated_edges"),
    )
    domain_shift = _estimate_domain_shift(snapshot, edge_bundle["coverage"])

    summary = dict(global_result["summary"])
    summary.update(
        {
            "event_id": snapshot.event_id,
            "platform": snapshot.platforms[0] if len(snapshot.platforms) == 1 else None,
            "status": global_result["status"],
            "evidence_edge_count": edge_bundle["summary"]["evidence_edge_count"],
            "evidence_kind_count": edge_bundle["summary"]["evidence_kind_count"],
            "window_scales": list(window_hours),
            "lineage_count": len(community_lineage),
            "null_model_p_value": null_model["p_value"],
            "perturbation_median_retained_ratio": perturbation["median_retained_ratio"],
        }
    )

    return {
        "status": global_result["status"],
        "technology": "coordination_discover",
        "model_version": "coordination-evidence-runtime-v2",
        "snapshot_id": snapshot.snapshot_id,
        "summary": summary,
        "community_lineage": community_lineage,
        "account_risk_tiers": _coordination_account_risk_tiers(global_result["account_stats"]),
        "evidence_edges": edge_bundle["evidence_edges"],
        "evidence_coverage": edge_bundle["coverage"],
        "null_model": null_model,
        "perturbation_robustness": perturbation,
        "domain_shift": domain_shift,
        "abstain": global_result["status"] != "ok",
        "network": global_result["network"],
        "account_stats": global_result["account_stats"],
        "group_stats": global_result["group_stats"],
        "cluster_stats": global_result["cluster_stats"],
        "windows": windows,
        "error": None if global_result["status"] == "ok" else global_result.get("error"),
    }


def _content_evidence_edges(
    row: dict[str, Any],
    *,
    content_ref: str,
    account_id: str,
    timestamp: float,
    platform: str,
    content_index: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    if not account_id or not content_ref:
        return []
    edges: list[dict[str, Any]] = []
    text = _content_text(row)

    for url in _iter_urls(row):
        edges.append(
            _edge(
                account_id=account_id,
                content_ref=content_ref,
                object_id=f"url:{_normalize_url(url)}",
                evidence_kind="url",
                relation_type="url",
                evidence_ref=f"{content_ref}:url:{_normalize_url(url)}",
                platform=platform,
                timestamp=timestamp,
            )
        )

    for media_url in _iter_media_urls(row):
        edges.append(
            _edge(
                account_id=account_id,
                content_ref=content_ref,
                object_id=f"media:{_normalize_url(media_url)}",
                evidence_kind="media",
                relation_type="media",
                evidence_ref=f"{content_ref}:media:{_normalize_url(media_url)}",
                platform=platform,
                timestamp=timestamp,
            )
        )

    for tag in _iter_hashtags(row):
        edges.append(
            _edge(
                account_id=account_id,
                content_ref=content_ref,
                object_id=f"hashtag:{_normalize_token(tag)}",
                evidence_kind="hashtag",
                relation_type="hashtag",
                evidence_ref=f"{content_ref}:hashtag:{_normalize_token(tag)}",
                platform=platform,
                timestamp=timestamp,
            )
        )

    for entity in _iter_entities(row, text):
        edges.append(
            _edge(
                account_id=account_id,
                content_ref=content_ref,
                object_id=f"entity:{_normalize_token(entity)}",
                evidence_kind="entity",
                relation_type="entity",
                evidence_ref=f"{content_ref}:entity:{_normalize_token(entity)}",
                platform=platform,
                timestamp=timestamp,
            )
        )

    for target_ref, target_label, relation_type in _iter_targets(row, content_index):
        object_id = f"target:{_normalize_token(target_label or target_ref)}"
        edges.append(
            _edge(
                account_id=account_id,
                content_ref=content_ref,
                object_id=object_id,
                evidence_kind="target",
                relation_type=relation_type,
                evidence_ref=f"{content_ref}:{relation_type}:{target_ref}",
                platform=platform,
                timestamp=timestamp,
            )
        )

    for relation_type, target_ref in _iter_native_relations(row):
        object_id = f"native_relation:{relation_type}:{target_ref}"
        edges.append(
            _edge(
                account_id=account_id,
                content_ref=content_ref,
                object_id=object_id,
                evidence_kind="native_relation",
                relation_type=relation_type,
                evidence_ref=f"{content_ref}:{relation_type}:{target_ref}",
                platform=platform,
                timestamp=timestamp,
            )
        )

    if text:
        signature = _near_duplicate_signature(text)
        if signature:
            edges.append(
                _edge(
                    account_id=account_id,
                    content_ref=content_ref,
                    object_id=f"near_duplicate:{signature}",
                    evidence_kind="near_duplicate",
                    relation_type="near_duplicate",
                    evidence_ref=f"{content_ref}:near_duplicate:{signature}",
                    platform=platform,
                    timestamp=timestamp,
                    weight=0.75,
                )
            )

    return edges


def _analyze_rows(
    rows: list[dict[str, Any]],
    *,
    time_window_seconds: int,
    min_participation: int,
    edge_weight: float,
) -> dict[str, Any]:
    if not rows:
        return _empty_coordination_result()

    frame = pd.DataFrame(rows)
    if frame.empty:
        return _empty_coordination_result()

    frame["timestamp_share"] = pd.to_numeric(frame["timestamp_share"], errors="coerce")
    frame = frame.dropna(subset=["timestamp_share", "object_id", "account_id", "content_id"])
    if frame.empty:
        return _empty_coordination_result()

    pairs = detect_groups(
        frame[["object_id", "account_id", "content_id", "timestamp_share"]],
        time_window=time_window_seconds,
        min_participation=min_participation,
    )
    if pairs.empty:
        return _empty_coordination_result(total_posts=len(rows))

    graph = generate_coordinated_network(pairs, edge_weight=edge_weight)
    network = graph_to_dict(graph)
    account_rows = coordination_account_stats(graph, pairs).to_dict(orient="records")
    group_rows = coordination_group_stats(graph, pairs).to_dict(orient="records")
    summary = {
        "event_id": None,
        "platform": None,
        "total_posts": len(frame),
        "total_comments": 0,
        "total_items": len(frame),
        "total_pairs": len(pairs),
        "coordinated_accounts": network["node_count"],
        "coordinated_edges": network["edge_count"],
        "components": network["component_count"],
        "cluster_count": network["cluster_count"],
    }
    return {
        "status": "ok",
        "network": network,
        "account_stats": account_rows,
        "group_stats": group_rows,
        "cluster_stats": list(network.get("clusters", [])),
        "summary": summary,
    }


def _analyze_overlapping_windows(
    rows: list[dict[str, Any]],
    *,
    window_hours: list[int],
    overlap_ratio: float,
    min_participation: int,
    edge_weight: float,
    max_slices_per_scale: int,
) -> list[dict[str, Any]]:
    if not rows:
        return [{"window_hours": hours, "slice_count": 0, "slices": []} for hours in window_hours]

    timestamps = [row["timestamp_share"] for row in rows if isinstance(row.get("timestamp_share"), (int, float))]
    if not timestamps:
        return [{"window_hours": hours, "slice_count": 0, "slices": []} for hours in window_hours]

    start = datetime.fromtimestamp(min(timestamps), tz=timezone.utc)
    end = datetime.fromtimestamp(max(timestamps), tz=timezone.utc)
    if start == end:
        end = end + timedelta(hours=1)

    results: list[dict[str, Any]] = []
    for hours in window_hours:
        window_delta = timedelta(hours=hours)
        step_delta = timedelta(hours=max(hours * max(0.05, 1.0 - overlap_ratio), 0.25))
        slices: list[dict[str, Any]] = []
        slice_start = start
        slice_index = 0
        while slice_start <= end and slice_index < max_slices_per_scale:
            slice_end = min(end + timedelta(seconds=1), slice_start + window_delta)
            slice_rows = [
                row
                for row in rows
                if isinstance(row.get("timestamp_share"), (int, float))
                and slice_start.timestamp() <= float(row["timestamp_share"]) < slice_end.timestamp()
            ]
            if slice_rows:
                slice_result = _analyze_rows(
                    slice_rows,
                    time_window_seconds=max(60, hours * 3600),
                    min_participation=min_participation,
                    edge_weight=edge_weight,
                )
                slices.append(
                    {
                        "slice_id": f"{hours}h:{slice_index}",
                        "window_hours": hours,
                        "slice_index": slice_index,
                        "slice_start": slice_start.isoformat(),
                        "slice_end": slice_end.isoformat(),
                        "row_count": len(slice_rows),
                        "coordinated_edges": _summary_value(slice_result, "coordinated_edges"),
                        "community_count": _summary_value(slice_result, "cluster_count"),
                        "summary": slice_result["summary"],
                        "network": slice_result["network"],
                        "account_stats": slice_result["account_stats"],
                        "group_stats": slice_result["group_stats"],
                        "cluster_stats": slice_result["cluster_stats"],
                    }
                )
            slice_start = slice_start + step_delta
            slice_index += 1
        results.append(
            {
                "window_hours": hours,
                "slice_count": len(slices),
                "slice_span_hours": hours,
                "slices": slices,
            }
        )
    return results


def _build_community_lineage(window_results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    lineages: list[dict[str, Any]] = []
    for scale in window_results:
        hours = int(scale.get("window_hours") or 0)
        for slice_result in scale.get("slices") or []:
            slice_index = int(slice_result.get("slice_index") or 0)
            for cluster in slice_result.get("cluster_stats") or []:
                if not isinstance(cluster, dict):
                    continue
                members = tuple(sorted(_as_list(cluster.get("members"))))
                if not members:
                    continue
                best_lineage = None
                best_score = 0.0
                for lineage in lineages:
                    score = _jaccard(members, lineage["representative_members"])
                    if score > best_score:
                        best_score = score
                        best_lineage = lineage
                if best_lineage is None or best_score < 0.45:
                    best_lineage = {
                        "lineage_id": f"lineage_{len(lineages) + 1}",
                        "representative_members": members,
                        "members_history": [],
                        "occurrences": [],
                        "shared_objects": [],
                    }
                    lineages.append(best_lineage)
                occurrence = {
                    "window_hours": hours,
                    "slice_index": slice_index,
                    "community_id": str(cluster.get("cluster_id") or f"{hours}:{slice_index}"),
                    "members": list(members),
                    "shared_objects": list(cluster.get("shared_objects") or []),
                    "edge_count": int(cluster.get("edge_count", 0) or 0),
                }
                best_lineage["occurrences"].append(occurrence)
                best_lineage["members_history"].append(members)
                for item in occurrence["shared_objects"]:
                    if item not in best_lineage["shared_objects"]:
                        best_lineage["shared_objects"].append(item)

    results: list[dict[str, Any]] = []
    for lineage in lineages:
        history = lineage["members_history"]
        stabilities = [_jaccard(left, right) for left, right in zip(history, history[1:])]
        if len(history) > 1:
            stability_score = mean(stabilities) if stabilities else 1.0
        else:
            stability_score = 1.0
        results.append(
            {
                "lineage_id": lineage["lineage_id"],
                "support_count": len(lineage["occurrences"]),
                "stability_score": round(stability_score, 4),
                "members": list(lineage["representative_members"]),
                "shared_objects": lineage["shared_objects"][:10],
                "windows": lineage["occurrences"],
            }
        )
    results.sort(key=lambda item: (item["support_count"], item["stability_score"]), reverse=True)
    return results


def _estimate_null_model(
    rows: list[dict[str, Any]],
    *,
    time_window_seconds: int,
    min_participation: int,
    edge_weight: float,
    samples: int,
    seed: int,
    observed_edges: int,
) -> dict[str, Any]:
    if not rows:
        return {"observed_edges": 0, "simulated_edge_counts": [], "mean": 0.0, "std": 0.0, "p_value": 1.0, "z_score": 0.0}

    rng = random.Random(seed)
    object_ids = [row["object_id"] for row in rows]
    simulated_edge_counts: list[int] = []
    for _ in range(max(1, samples)):
        shuffled = [dict(row) for row in rows]
        permuted = list(object_ids)
        rng.shuffle(permuted)
        for row, object_id in zip(shuffled, permuted):
            row["object_id"] = object_id
        simulated_edge_counts.append(
            _summary_value(
                _analyze_rows(
                    shuffled,
                    time_window_seconds=time_window_seconds,
                    min_participation=min_participation,
                    edge_weight=edge_weight,
                ),
                "coordinated_edges",
            )
        )

    simulated_mean = mean(simulated_edge_counts) if simulated_edge_counts else 0.0
    simulated_std = pstdev(simulated_edge_counts) if len(simulated_edge_counts) > 1 else 0.0
    more_extreme = sum(1 for value in simulated_edge_counts if value >= observed_edges)
    p_value = (more_extreme + 1) / (len(simulated_edge_counts) + 1)
    z_score = (observed_edges - simulated_mean) / simulated_std if simulated_std > 0 else 0.0
    return {
        "observed_edges": int(observed_edges),
        "simulated_edge_counts": simulated_edge_counts,
        "mean": round(simulated_mean, 4),
        "std": round(simulated_std, 4),
        "p_value": round(p_value, 6),
        "z_score": round(z_score, 4),
    }


def _estimate_robustness(
    rows: list[dict[str, Any]],
    *,
    time_window_seconds: int,
    min_participation: int,
    edge_weight: float,
    samples: int,
    seed: int,
    observed_edges: int,
) -> dict[str, Any]:
    if not rows:
        return {"median_retained_ratio": 0.0, "ratios": [], "samples": 0}

    rng = random.Random(seed)
    ratios: list[float] = []
    row_count = len(rows)
    drop_count = max(1, int(round(row_count * 0.1)))
    for _ in range(max(1, samples)):
        sampled = [dict(row) for row in rows]
        drop_indexes = set(rng.sample(range(row_count), min(drop_count, row_count)))
        sampled = [row for index, row in enumerate(sampled) if index not in drop_indexes]
        result = _analyze_rows(
            sampled,
            time_window_seconds=time_window_seconds,
            min_participation=min_participation,
            edge_weight=edge_weight,
        )
        retained = _summary_value(result, "coordinated_edges")
        ratios.append(round(retained / max(observed_edges, 1), 6))

    return {
        "median_retained_ratio": round(median(ratios) if ratios else 0.0, 6),
        "ratios": ratios,
        "samples": len(ratios),
    }


def _estimate_domain_shift(snapshot: EventSnapshot, coverage: dict[str, Any]) -> dict[str, Any]:
    platform_counts = dict(snapshot.quality_report.platform_counts)
    total = sum(platform_counts.values()) or 1
    dominant_share = max(platform_counts.values()) / total if platform_counts else 0.0
    platform_entropy = 0.0
    for count in platform_counts.values():
        share = count / total
        if share > 0:
            platform_entropy -= share * __import__("math").log(share)
    return {
        "status": "measured" if platform_counts else "not_evaluated",
        "platform_counts": platform_counts,
        "platform_entropy": round(platform_entropy, 4),
        "dominant_share": round(dominant_share, 4),
        "coverage_ratio": coverage.get("coverage_ratio", 0.0),
    }


def _coordination_account_risk_tiers(account_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    tiers: list[dict[str, Any]] = []
    for row in account_rows:
        account_id = _text(row.get("account_id"))
        if not account_id:
            continue
        degree = int(row.get("degree", 0) or 0)
        cross_weight = float(row.get("cross_cluster_weight", 0) or 0)
        tier = "observed_coordination"
        if degree >= 4 and cross_weight > 0:
            tier = "high_coordination"
        elif degree <= 1:
            tier = "light_coordination"
        tiers.append(
            {
                "account_id": account_id,
                "account_label": row.get("account_label") or account_id,
                "tier": tier,
                "evidence": {
                    "degree": degree,
                    "avg_weight": float(row.get("avg_weight", 0) or 0),
                    "avg_time_delta": float(row.get("avg_time_delta", 0) or 0),
                    "coordinated_shares_count": int(row.get("coordinated_shares_count", 0) or 0),
                    "shared_objects_preview": list(row.get("shared_objects_preview", []) or []),
                },
            }
        )
    return tiers


def _build_content_index(snapshot: EventSnapshot) -> dict[str, dict[str, Any]]:
    index: dict[str, dict[str, Any]] = {}
    for kind, rows in (("post", snapshot.posts), ("comment", snapshot.comments)):
        for row in rows:
            content_ref = _content_ref(row, kind=kind)
            timestamp_share = _timestamp_seconds(row.get("timestamp"))
            index[content_ref] = {
                "account_id": _text(row.get("author_id")),
                "content_ref": content_ref,
                "timestamp_share": timestamp_share,
                "platform": _text(row.get("platform")) or "unknown",
                "kind": kind,
                "text": _content_text(row),
                "row": row,
            }
    return index


def _near_duplicate_groups(content_index: dict[str, dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in content_index.values():
        text = row["text"]
        signature = _near_duplicate_signature(text)
        if not signature:
            continue
        groups[signature].append(row)
    return dict(groups)


def _near_duplicate_signature(text: str) -> str:
    tokens = _tokens(text)
    if len(tokens) < 6:
        return ""
    compact = " ".join(tokens[:12])
    return hashlib.sha1(compact.encode("utf-8")).hexdigest()[:12]


def _iter_urls(row: dict[str, Any]) -> list[str]:
    values = []
    for key in ("url", "shared_urls"):
        values.extend(_flatten_text_values(row.get(key)))
    raw_data = row.get("raw_data") if isinstance(row.get("raw_data"), dict) else {}
    values.extend(_extract_nested_urls(raw_data))
    return _dedupe_texts(values)


def _iter_media_urls(row: dict[str, Any]) -> list[str]:
    values = []
    values.extend(_flatten_text_values(row.get("media_urls")))
    raw_data = row.get("raw_data") if isinstance(row.get("raw_data"), dict) else {}
    values.extend(_extract_nested_media_urls(raw_data))
    return _dedupe_texts(values)


def _iter_hashtags(row: dict[str, Any]) -> list[str]:
    values = []
    values.extend(_flatten_text_values(row.get("hashtags")))
    raw_data = row.get("raw_data") if isinstance(row.get("raw_data"), dict) else {}
    values.extend(_extract_nested_hashtags(raw_data))
    return _dedupe_texts(values)


def _iter_entities(row: dict[str, Any], text: str) -> list[str]:
    values = []
    values.extend(_flatten_text_values(row.get("entities")))
    values.extend(_flatten_text_values(row.get("entity_names")))
    raw_data = row.get("raw_data") if isinstance(row.get("raw_data"), dict) else {}
    values.extend(_extract_nested_entities(raw_data))
    values.extend(re.findall(r"@([A-Za-z0-9_\-]+)", text))
    return _dedupe_texts(values)


def _iter_targets(row: dict[str, Any], content_index: dict[str, dict[str, Any]]) -> list[tuple[str, str, str]]:
    targets = []
    relation_map = (
        ("reply_to", "reply"),
        ("parent_comment_id", "reply"),
        ("parent_post_id", "parent"),
        ("quote_post_id", "quote"),
        ("repost_id", "repost"),
        ("retweeted_post_id", "repost"),
        ("target", "target"),
        ("target_id", "target"),
        ("target_account_id", "target"),
        ("mention_target", "target"),
        ("reply_target", "target"),
    )
    for field, relation_type in relation_map:
        value = _text(row.get(field))
        if not value:
            continue
        target_ref = _resolve_target_ref(row, value, content_index)
        targets.append((target_ref, value, relation_type))
    return targets


def _iter_native_relations(row: dict[str, Any]) -> list[tuple[str, str]]:
    relations = []
    for field, relation_type in (
        ("reply_to", "reply"),
        ("parent_comment_id", "reply"),
        ("parent_post_id", "parent"),
        ("quote_post_id", "quote"),
        ("repost_id", "repost"),
        ("retweeted_post_id", "repost"),
    ):
        value = _text(row.get(field))
        if value:
            relations.append((relation_type, value))
    return relations


def _resolve_target_ref(row: dict[str, Any], value: str, content_index: dict[str, dict[str, Any]]) -> str:
    if value in content_index:
        return value
    platform = _text(row.get("platform")) or "unknown"
    return f"{platform}:target:{_normalize_token(value)}"


def _edge(
    *,
    account_id: str,
    content_ref: str,
    object_id: str,
    evidence_kind: str,
    relation_type: str,
    evidence_ref: str,
    platform: str,
    timestamp: float,
    weight: float = 1.0,
) -> dict[str, Any]:
    return {
        "source": account_id,
        "target": object_id,
        "content_id": content_ref,
        "source_content_id": content_ref,
        "target_content_id": object_id,
        "evidence_kind": evidence_kind,
        "relation_type": relation_type,
        "evidence_ref": evidence_ref,
        "platform": platform,
        "weight": weight,
        "observed_at": timestamp,
    }


def _edges_to_rows(evidence_edges: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for edge in evidence_edges:
        source = _text(edge.get("source"))
        content_id = _text(edge.get("content_id"))
        object_id = _text(edge.get("target"))
        if not source or not content_id or not object_id:
            continue
        rows.append(
            {
                "object_id": object_id,
                "account_id": source,
                "content_id": content_id,
                "timestamp_share": float(edge.get("observed_at") or 0.0),
                "evidence_kind": edge.get("evidence_kind"),
                "evidence_ref": edge.get("evidence_ref"),
                "platform": edge.get("platform") or "unknown",
            }
        )
    return rows


def _dedupe_edges(edges: list[dict[str, Any]]) -> list[dict[str, Any]]:
    deduped: dict[tuple[str, str, str], dict[str, Any]] = {}
    for edge in edges:
        key = (_text(edge.get("source")), _text(edge.get("content_id")), _text(edge.get("target")))
        existing = deduped.get(key)
        if existing is None:
            deduped[key] = edge
            continue
        existing["weight"] = max(float(existing.get("weight", 1.0)), float(edge.get("weight", 1.0)))
        if _text(existing.get("relation_type")) == "target" and _text(edge.get("relation_type")):
            existing["relation_type"] = edge["relation_type"]
    return sorted(
        deduped.values(),
        key=lambda edge: (
            float(edge.get("observed_at") or 0.0),
            _text(edge.get("source")),
            _text(edge.get("target")),
            _text(edge.get("evidence_kind")),
        ),
    )


def _empty_coordination_result(total_posts: int = 0) -> dict[str, Any]:
    return {
        "status": "data_insufficient",
        "network": {
            "nodes": [],
            "edges": [],
            "node_count": 0,
            "edge_count": 0,
            "component_count": 0,
            "components": [],
            "cluster_count": 0,
            "clusters": [],
        },
        "account_stats": [],
        "group_stats": [],
        "cluster_stats": [],
        "summary": {
            "event_id": None,
            "platform": None,
            "total_posts": total_posts,
            "total_comments": 0,
            "total_items": total_posts,
            "total_pairs": 0,
            "coordinated_accounts": 0,
            "coordinated_edges": 0,
            "components": 0,
            "cluster_count": 0,
        },
    }


def _normalize_window_hours(value: Any) -> list[int]:
    if isinstance(value, int):
        return [value]
    if isinstance(value, float):
        return [max(1, int(round(value)))]
    if isinstance(value, (list, tuple, set)):
        hours = []
        for item in value:
            try:
                hours.append(max(1, int(item)))
            except (TypeError, ValueError):
                continue
        return hours or list(WINDOW_SCALES_HOURS)
    return list(WINDOW_SCALES_HOURS)


def _summary_value(result: dict[str, Any], key: str) -> int:
    summary = result.get("summary") if isinstance(result, dict) else {}
    if isinstance(summary, dict):
        return int(summary.get(key, 0) or 0)
    return 0


def _build_content_index_key(row: dict[str, Any], kind: str) -> str:
    identifier = _text(row.get("post_id") if kind == "post" else row.get("comment_id"))
    return f"{_text(row.get('platform')) or 'unknown'}:{kind}:{identifier}"


def _content_ref(row: dict[str, Any], kind: str | None = None) -> str:
    if kind is None:
        kind = "comment" if _text(row.get("comment_id")) and not _text(row.get("post_id")) else "post"
    return _build_content_index_key(row, kind)


def _content_text(row: dict[str, Any]) -> str:
    parts = [
        row.get("content"),
        row.get("text"),
        row.get("title"),
        row.get("desc"),
        row.get("summary"),
    ]
    return " ".join(_text(part) for part in parts if _text(part)).strip()


def _timestamp_seconds(value: Any) -> float:
    if isinstance(value, datetime):
        ts = value
    elif value in (None, ""):
        return 0.0
    else:
        try:
            ts = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except ValueError:
            try:
                return float(value)
            except (TypeError, ValueError):
                return 0.0
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    return float(ts.astimezone(timezone.utc).timestamp())


def _seed_from_snapshot(snapshot: EventSnapshot) -> int:
    digest = snapshot.data_fingerprint or snapshot.snapshot_id
    return int(hashlib.sha256(digest.encode("utf-8")).hexdigest()[:8], 16)


def _normalize_url(value: str) -> str:
    text = _text(value)
    return re.sub(r"\s+", "", text).lower()


def _normalize_token(value: str) -> str:
    return re.sub(r"[^0-9A-Za-z\u4e00-\u9fff]+", "", _text(value)).lower()


def _flatten_text_values(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        values = []
        for item in value.values():
            values.extend(_flatten_text_values(item))
        return values
    if isinstance(value, (list, tuple, set)):
        values = []
        for item in value:
            values.extend(_flatten_text_values(item))
        return values
    return [str(value)]


def _extract_nested_urls(value: Any) -> list[str]:
    return _extract_nested_strings(value, {"url", "shared_url", "link"})


def _extract_nested_media_urls(value: Any) -> list[str]:
    return _extract_nested_strings(value, {"media", "video", "image", "cover", "thumbnail", "picture", "pic"})


def _extract_nested_hashtags(value: Any) -> list[str]:
    return _extract_nested_strings(value, {"hash", "tag", "topic"})


def _extract_nested_entities(value: Any) -> list[str]:
    return _extract_nested_strings(value, {"entity", "mention", "target", "keyword", "name"})


def _extract_nested_strings(value: Any, markers: set[str], *, parent_key: str = "") -> list[str]:
    values: list[str] = []
    if isinstance(value, str):
        if any(marker in parent_key.lower() for marker in markers):
            values.append(value)
        return values
    if isinstance(value, dict):
        for key, item in value.items():
            values.extend(_extract_nested_strings(item, markers, parent_key=str(key)))
        return values
    if isinstance(value, (list, tuple, set)):
        for item in value:
            values.extend(_extract_nested_strings(item, markers, parent_key=parent_key))
    return values


def _dedupe_texts(values: list[str]) -> list[str]:
    deduped = []
    seen = set()
    for value in values:
        text = _text(value)
        if not text or text in seen:
            continue
        seen.add(text)
        deduped.append(text)
    return deduped


def _tokens(text: str) -> list[str]:
    return [match.group(0).lower() for match in TOKEN_PATTERN.finditer(text or "")]


def _jaccard(left: tuple[str, ...] | list[str], right: tuple[str, ...] | list[str]) -> float:
    left_set = set(left)
    right_set = set(right)
    if not left_set or not right_set:
        return 0.0
    overlap = left_set & right_set
    if not overlap:
        return 0.0
    return len(overlap) / len(left_set | right_set)


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, (tuple, set)):
        return list(value)
    return [value]


def _text(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


__all__ = [
    "analyze_coordination_discover_snapshot",
    "build_coordination_discover_evidence_edges",
]
