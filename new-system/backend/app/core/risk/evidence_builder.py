"""风险研判证据包构建。"""

from __future__ import annotations

from collections import Counter

import pandas as pd

from app.core.account_profiler import build_account_profiles
from app.core.coordination import account_stats, detect_groups, generate_coordinated_network, group_stats
from app.core.coordination.network import graph_to_dict
from app.core.propagation import build_propagation_graph


def _build_coordination_summary(posts: list[dict]) -> dict:
    rows: list[dict] = []
    for post in posts:
        obj_ids: list[str] = []
        for tag in post.get("hashtags", []) or []:
            if tag:
                obj_ids.append(str(tag))
        url = str(post.get("url", "") or "")
        if url:
            obj_ids.append(url)
        if not obj_ids:
            continue

        ts = post.get("timestamp")
        parsed = pd.to_datetime(ts, errors="coerce", utc=True)
        if pd.isna(parsed):
            continue
        parsed_ts = parsed.timestamp()

        for obj_id in obj_ids:
            rows.append({
                "object_id": obj_id,
                "account_id": str(post.get("author_id", "")),
                "content_id": str(post.get("post_id", "")),
                "timestamp_share": parsed_ts,
            })

    if not rows:
        return {
            "network": {"nodes": [], "edges": [], "node_count": 0, "edge_count": 0, "component_count": 0, "components": []},
            "summary": {"total_pairs": 0, "coordinated_accounts": 0, "coordinated_edges": 0, "components": 0},
            "top_accounts": [],
            "top_groups": [],
        }

    df = pd.DataFrame(rows)
    result = detect_groups(df, time_window=60, min_participation=2)
    if result.empty:
        return {
            "network": {"nodes": [], "edges": [], "node_count": 0, "edge_count": 0, "component_count": 0, "components": []},
            "summary": {"total_pairs": 0, "coordinated_accounts": 0, "coordinated_edges": 0, "components": 0},
            "top_accounts": [],
            "top_groups": [],
        }

    graph = generate_coordinated_network(result, edge_weight=0.5)
    network = graph_to_dict(graph)
    a_stats = account_stats(graph, result).to_dict(orient="records")
    g_stats = group_stats(graph, result).to_dict(orient="records")
    return {
        "network": network,
        "summary": {
            "total_pairs": len(result),
            "coordinated_accounts": graph.number_of_nodes(),
            "coordinated_edges": graph.number_of_edges(),
            "components": network["component_count"],
        },
        "top_accounts": a_stats[:5],
        "top_groups": g_stats[:5],
    }


def _build_content_summary(posts: list[dict], harmful_results: list[dict], stance_results: list[dict]) -> dict:
    harmful_counter = Counter(item["label"] for item in harmful_results)
    stance_counter = Counter(item["label"] for item in stance_results)
    total = len(posts) or 1
    return {
        "total_posts": len(posts),
        "harmful_distribution": dict(harmful_counter),
        "stance_distribution": dict(stance_counter),
        "harmful_ratio": round(harmful_counter.get("harmful", 0) / total, 4),
        "borderline_ratio": round(harmful_counter.get("borderline", 0) / total, 4),
        "support_ratio": round(stance_counter.get("support", 0) / total, 4),
        "deny_ratio": round(stance_counter.get("deny", 0) / total, 4),
        "query_ratio": round(stance_counter.get("query", 0) / total, 4),
    }


def _build_top_posts(harmful_results: list[dict], stance_results: list[dict]) -> list[dict]:
    stance_by_post = {item["post_id"]: item for item in stance_results}
    ordered = sorted(harmful_results, key=lambda item: item["score"], reverse=True)
    top_posts: list[dict] = []
    for item in ordered[:5]:
        stance = stance_by_post.get(item["post_id"], {})
        top_posts.append({
            "post_id": item["post_id"],
            "author_id": item["author_id"],
            "content": item["content"][:160],
            "harmful_label": item["label"],
            "harmful_score": item["score"],
            "stance_label": stance.get("label", "comment"),
            "stance_score": stance.get("score", 0),
            "harmful_reason": item.get("reason", ""),
        })
    return top_posts


def build_evidence_pack(posts: list[dict], harmful_results: list[dict], stance_results: list[dict], target: str) -> dict:
    """构建结构化证据包。"""
    propagation = build_propagation_graph(posts)
    coordination = _build_coordination_summary(posts)
    account_profiles = build_account_profiles(posts)
    avg_automation = round(
        sum(profile["automation_score"] for profile in account_profiles) / len(account_profiles), 2
    ) if account_profiles else 0.0

    suspicious_accounts = [
        {
            "account_id": profile["account_id"],
            "author_name": profile["author_name"],
            "automation_score": profile["automation_score"],
            "post_count": profile["post_count"],
        }
        for profile in account_profiles
        if profile["automation_score"] >= 45
    ][:5]

    content_summary = _build_content_summary(posts, harmful_results, stance_results)
    top_posts = _build_top_posts(harmful_results, stance_results)

    return {
        "target": target,
        "content_summary": content_summary,
        "coordination": coordination,
        "propagation": {
            "graph": propagation["graph"],
            "claims": propagation["claims"][:10],
            "timeline": propagation["timeline"][:20],
            "key_roles": propagation["key_roles"],
        },
        "accounts": {
            "total_accounts": len({str(post.get("author_id", "")) for post in posts if post.get("author_id")}),
            "avg_automation_score": avg_automation,
            "suspicious_accounts": suspicious_accounts,
        },
        "top_posts": top_posts,
        "raw_counts": {
            "posts": len(posts),
            "harmful_posts": content_summary["harmful_distribution"].get("harmful", 0),
            "borderline_posts": content_summary["harmful_distribution"].get("borderline", 0),
            "support_posts": content_summary["stance_distribution"].get("support", 0),
            "deny_posts": content_summary["stance_distribution"].get("deny", 0),
            "query_posts": content_summary["stance_distribution"].get("query", 0),
        },
    }
