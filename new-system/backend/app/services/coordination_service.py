"""Coordination detection service."""

from __future__ import annotations

from typing import Any

import pandas as pd

from app.core.coordination import account_stats, detect_groups, generate_coordinated_network, group_stats
from app.core.coordination.network import graph_to_dict
from app.db.mongodb import get_mongo_db
from app.services.event_data import build_event_filter, load_event_posts


def _summary(
    *,
    event_id: str | None,
    platform: str | None,
    total_posts: int,
    total_pairs: int = 0,
    coordinated_accounts: int = 0,
    coordinated_edges: int = 0,
    components: int = 0,
    clusters: int = 0,
) -> dict[str, Any]:
    return {
        "event_id": event_id,
        "platform": platform,
        "total_posts": total_posts,
        "total_pairs": total_pairs,
        "coordinated_accounts": coordinated_accounts,
        "coordinated_edges": coordinated_edges,
        "components": components,
        "cluster_count": clusters,
    }


def _empty_result(event_id: str | None, platform: str | None, total_posts: int, *, error: str | None = None) -> dict:
    result = {
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
        "summary": _summary(event_id=event_id, platform=platform, total_posts=total_posts),
        "cluster_stats": [],
    }
    if error:
        result["error"] = error
    return result


def _iter_values(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value] if value else []
    if isinstance(value, dict):
        return [str(item) for item in value.values() if item]
    if isinstance(value, (list, tuple, set)):
        return [str(item) for item in value if item]
    return [str(value)]


def _shared_objects(post: dict[str, Any]) -> list[str]:
    objects: list[str] = []
    objects.extend(_iter_values(post.get("hashtags")))
    url = post.get("url")
    if url:
        objects.append(str(url))
    objects.extend(_iter_values(post.get("media_urls")))
    return list(dict.fromkeys(objects))


async def run_coordination_detection(
    time_window: int = 60,
    min_participation: int = 2,
    edge_weight: float = 0.5,
    platform: str | None = None,
    event_id: str | None = None,
) -> dict:
    """Run coordination detection over optionally event-scoped MongoDB posts."""
    mongo_db = get_mongo_db()
    posts = await load_event_posts(mongo_db, event_id=event_id, platform=platform)

    if not posts:
        return _empty_result(
            event_id,
            platform,
            0,
            error="No analyzable posts found. Run data collection or choose another event/platform.",
        )

    rows = []
    for post in posts:
        timestamp = post.get("timestamp")
        if isinstance(timestamp, str):
            timestamp = pd.Timestamp(timestamp).timestamp()
        elif hasattr(timestamp, "timestamp"):
            timestamp = timestamp.timestamp()

        for object_id in _shared_objects(post):
            rows.append(
                {
                    "object_id": object_id,
                    "account_id": post.get("author_id", ""),
                    "content_id": post.get("post_id", ""),
                    "timestamp_share": timestamp,
                }
            )

    if not rows:
        return _empty_result(
            event_id,
            platform,
            len(posts),
            error="Posts do not contain analyzable shared objects (hashtags, URLs, or media URLs).",
        )

    pairs = detect_groups(pd.DataFrame(rows), time_window=time_window, min_participation=min_participation)
    if pairs.empty:
        return _empty_result(event_id, platform, len(posts))

    graph = generate_coordinated_network(pairs, edge_weight=edge_weight)
    network_data = graph_to_dict(graph)
    account_data = account_stats(graph, pairs)
    group_data = group_stats(graph, pairs)
    cluster_data = network_data.get("clusters", [])

    return {
        "network": network_data,
        "account_stats": account_data.to_dict(orient="records"),
        "group_stats": group_data.to_dict(orient="records"),
        "cluster_stats": cluster_data,
        "summary": _summary(
            event_id=event_id,
            platform=platform,
            total_posts=len(posts),
            total_pairs=len(pairs),
            coordinated_accounts=graph.number_of_nodes(),
            coordinated_edges=graph.number_of_edges(),
            components=network_data["component_count"],
            clusters=network_data["cluster_count"],
        ),
    }
