"""协同检测业务逻辑服务。

从 MongoDB 读取已采集数据，运行协同检测算法，返回网络和统计结果。
"""

from __future__ import annotations

import pandas as pd

from app.core.coordination import detect_groups, generate_coordinated_network, account_stats, group_stats
from app.core.coordination.network import graph_to_dict
from app.db.mongodb import get_mongo_db


async def run_coordination_detection(
    time_window: int = 60,
    min_participation: int = 2,
    edge_weight: float = 0.5,
    platform: str | None = None,
) -> dict:
    """对已采集数据执行协同检测，返回完整分析结果。"""
    mongo_db = get_mongo_db()

    mongo_filter: dict = {}
    if platform:
        mongo_filter["platform"] = platform

    cursor = mongo_db["raw_posts"].find(mongo_filter, {"_id": 0})
    posts = await cursor.to_list(length=10000)

    if not posts:
        return {"error": "没有可分析的数据，请先执行数据采集"}

    rows = []
    for p in posts:
        obj_ids = []
        for tag in p.get("hashtags", []):
            obj_ids.append(tag)
        url = p.get("url", "")
        if url:
            obj_ids.append(url)
        if not obj_ids:
            continue

        ts = p.get("timestamp")
        if isinstance(ts, str):
            ts = pd.Timestamp(ts).timestamp()
        elif hasattr(ts, "timestamp"):
            ts = ts.timestamp()

        for obj_id in obj_ids:
            rows.append({
                "object_id": obj_id,
                "account_id": p.get("author_id", ""),
                "content_id": p.get("post_id", ""),
                "timestamp_share": ts,
            })

    if not rows:
        return {"error": "数据中没有可分析的共享对象（URL/标签）"}

    df = pd.DataFrame(rows)

    result = detect_groups(df, time_window=time_window, min_participation=min_participation)

    if result.empty:
        return {
            "network": {"nodes": [], "edges": [], "node_count": 0, "edge_count": 0, "component_count": 0, "components": []},
            "account_stats": [],
            "group_stats": [],
            "summary": {"total_posts": len(posts), "total_pairs": 0, "coordinated_accounts": 0},
        }

    G = generate_coordinated_network(result, edge_weight=edge_weight)
    network_data = graph_to_dict(G)
    a_stats = account_stats(G, result)
    g_stats = group_stats(G, result)

    return {
        "network": network_data,
        "account_stats": a_stats.to_dict(orient="records"),
        "group_stats": g_stats.to_dict(orient="records"),
        "summary": {
            "total_posts": len(posts),
            "total_pairs": len(result),
            "coordinated_accounts": G.number_of_nodes(),
            "coordinated_edges": G.number_of_edges(),
            "components": network_data["component_count"],
        },
    }
