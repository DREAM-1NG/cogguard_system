"""传播归因分析模块。

基于帖子的时序关系构建传播子图，识别关键角色：
- 起爆节点（最早发布者）
- 桥接节点（连接不同群体）
- 扩散节点（高转发量）
"""

from __future__ import annotations

import networkx as nx
import pandas as pd
import numpy as np


def build_propagation_graph(posts: list[dict]) -> dict:
    """从帖子列表构建传播图，按共享对象（URL/标签）追踪传播链。

    Returns
    -------
    dict 含 graph_data, timeline, key_roles, claims
    """
    if not posts:
        return _empty_result()

    df = pd.DataFrame(posts)
    df["ts"] = pd.to_datetime(df.get("timestamp"), errors="coerce", utc=True)
    df = df.dropna(subset=["ts"]).sort_values("ts")

    if df.empty:
        return _empty_result()

    G = nx.DiGraph()

    for _, row in df.iterrows():
        node_id = str(row.get("author_id", ""))
        if not node_id:
            continue
        if node_id not in G:
            G.add_node(node_id, author_name=row.get("author_name", node_id), post_count=0, first_ts=str(row["ts"]))
        G.nodes[node_id]["post_count"] = G.nodes[node_id].get("post_count", 0) + 1

    shared_objects: dict[str, list] = {}
    for _, row in df.iterrows():
        objs = []
        for tag in row.get("hashtags", []) or []:
            objs.append(tag)
        url = row.get("url", "")
        if url:
            objs.append(url)
        for obj in objs:
            if obj not in shared_objects:
                shared_objects[obj] = []
            shared_objects[obj].append({
                "author_id": str(row.get("author_id", "")),
                "post_id": str(row.get("post_id", "")),
                "ts": row["ts"],
            })

    for obj_id, shares in shared_objects.items():
        if len(shares) < 2:
            continue
        sorted_shares = sorted(shares, key=lambda s: s["ts"])
        origin = sorted_shares[0]
        for follower in sorted_shares[1:]:
            if origin["author_id"] == follower["author_id"]:
                continue
            src, dst = origin["author_id"], follower["author_id"]
            if G.has_edge(src, dst):
                G[src][dst]["weight"] += 1
            else:
                G.add_edge(src, dst, weight=1, object_id=obj_id)

    key_roles = _identify_key_roles(G)

    claims = []
    for obj_id, shares in sorted(shared_objects.items(), key=lambda x: len(x[1]), reverse=True)[:20]:
        accounts = list({s["author_id"] for s in shares})
        claims.append({
            "object_id": obj_id,
            "share_count": len(shares),
            "account_count": len(accounts),
            "first_share": str(shares[0]["ts"]) if shares else "",
        })

    timeline = []
    for _, row in df.head(100).iterrows():
        timeline.append({
            "post_id": str(row.get("post_id", "")),
            "author_id": str(row.get("author_id", "")),
            "author_name": row.get("author_name", ""),
            "timestamp": str(row["ts"]),
            "content": str(row.get("content", ""))[:100],
        })

    nodes = []
    for n, attrs in G.nodes(data=True):
        nodes.append({"id": n, **{k: v for k, v in attrs.items()}})
    edges = []
    for u, v, d in G.edges(data=True):
        edges.append({"source": u, "target": v, "weight": d.get("weight", 1)})

    return {
        "graph": {"nodes": nodes, "edges": edges, "node_count": G.number_of_nodes(), "edge_count": G.number_of_edges()},
        "key_roles": key_roles,
        "claims": claims,
        "timeline": timeline,
    }


def _identify_key_roles(G: nx.DiGraph) -> dict:
    """识别传播网络中的关键角色。"""
    if G.number_of_nodes() == 0:
        return {"originators": [], "bridges": [], "amplifiers": []}

    # 起爆节点：出度高、入度低
    originators = []
    for n in G.nodes():
        out_d = G.out_degree(n)
        in_d = G.in_degree(n)
        if out_d > 0 and out_d >= in_d:
            originators.append({"account_id": n, "out_degree": out_d, "in_degree": in_d, "author_name": G.nodes[n].get("author_name", n)})
    originators.sort(key=lambda x: x["out_degree"], reverse=True)

    # 桥接节点：介数中心性高
    bridges = []
    if G.number_of_edges() > 0:
        try:
            bc = nx.betweenness_centrality(G, weight="weight")
            for n, score in sorted(bc.items(), key=lambda x: x[1], reverse=True)[:10]:
                if score > 0:
                    bridges.append({"account_id": n, "betweenness": round(score, 4), "author_name": G.nodes[n].get("author_name", n)})
        except Exception:
            pass

    # 扩散节点：入度最高（被最多人"跟随"传播）
    amplifiers = []
    for n in G.nodes():
        in_d = G.in_degree(n)
        if in_d > 0:
            amplifiers.append({"account_id": n, "in_degree": in_d, "author_name": G.nodes[n].get("author_name", n)})
    amplifiers.sort(key=lambda x: x["in_degree"], reverse=True)

    return {
        "originators": originators[:10],
        "bridges": bridges[:10],
        "amplifiers": amplifiers[:10],
    }


def _empty_result():
    return {
        "graph": {"nodes": [], "edges": [], "node_count": 0, "edge_count": 0},
        "key_roles": {"originators": [], "bridges": [], "amplifiers": []},
        "claims": [],
        "timeline": [],
    }
