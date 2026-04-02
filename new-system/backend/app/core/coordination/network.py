"""协同网络构建（对应 CooRTweet generate_coordinated_network）。

从 detect_groups 的配对结果构建加权无向图，按边权分位数标记异常协调对。
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import networkx as nx


def generate_coordinated_network(
    result: pd.DataFrame,
    edge_weight: float = 0.5,
    fast_net: bool = False,
    subgraph: int = 0,
) -> nx.Graph:
    """从协调配对结果构建加权无向图。

    Parameters
    ----------
    result : DataFrame
        detect_groups 的输出
    edge_weight : float
        边权百分位阈值 (0-1)，超过此百分位的边标记为协调
    fast_net : bool
        是否区分全窗 / 快窗权重（需先调用 flag_speed_share）
    subgraph : int
        0=完整图, 1=仅保留超阈值边, 2=快窗超阈值边, 3=快窗+邻居上下文

    Returns
    -------
    nx.Graph
        节点=账户, 边属性含 weight, avg_time_delta, edge_symmetry_score 等
    """
    if not 0 <= edge_weight <= 1:
        raise ValueError("edge_weight 必须在 0-1 之间")

    if result.empty:
        return nx.Graph()

    data = result.copy()

    # 统一无序对方向
    a1 = data["account_id"].values
    a2 = data["account_id_y"].values
    data["account_id"] = np.minimum(a1, a2)
    data["account_id_y"] = np.maximum(a1, a2)

    G = _build_graph(data)
    _apply_weight_threshold(G, edge_weight, "weight", "weight_threshold")

    if fast_net:
        fast_col = [c for c in data.columns if c.startswith("time_window_")]
        if not fast_col:
            raise ValueError("fast_net=True 但数据中没有 time_window_* 列，请先调用 flag_speed_share")
        fast_data = data[data[fast_col[0]] == 1]
        if not fast_data.empty:
            G_fast = _build_graph(fast_data)
            for u, v, attrs in G_fast.edges(data=True):
                if G.has_edge(u, v):
                    for k, val in attrs.items():
                        G[u][v][f"{k}_fast"] = val
                else:
                    G.add_edge(u, v, **{f"{k}_fast": val for k, val in attrs.items()})
            _apply_weight_threshold(G, edge_weight, "weight_fast", "weight_threshold_fast")

    if subgraph == 1:
        G = _extract_subgraph(G, "weight_threshold")
    elif subgraph == 2:
        G = _extract_subgraph(G, "weight_threshold_fast")
    elif subgraph == 3:
        fast_nodes = set()
        for u, v, d in G.edges(data=True):
            if d.get("weight_threshold_fast", 0) == 1:
                fast_nodes.update([u, v])
        if fast_nodes:
            neighbors = set()
            for n in fast_nodes:
                neighbors.update(G.neighbors(n))
            all_nodes = fast_nodes | neighbors
            G = G.subgraph(all_nodes).copy()
            for n in G.nodes():
                G.nodes[n]["is_coordinated"] = 1 if n in fast_nodes else 0

    return G


def graph_to_dict(G: nx.Graph) -> dict:
    """将 networkx 图转为可序列化的字典（供 API 返回）。"""
    nodes = []
    for n, attrs in G.nodes(data=True):
        nodes.append({"id": str(n), **attrs})

    edges = []
    for u, v, attrs in G.edges(data=True):
        edge = {"source": str(u), "target": str(v)}
        for k, val in attrs.items():
            edge[k] = float(val) if isinstance(val, (int, float, np.integer, np.floating)) else val
        edges.append(edge)

    components = list(nx.connected_components(G))
    return {
        "nodes": nodes,
        "edges": edges,
        "node_count": G.number_of_nodes(),
        "edge_count": G.number_of_edges(),
        "component_count": len(components),
        "components": [
            {"size": len(c), "members": [str(m) for m in c]}
            for c in sorted(components, key=len, reverse=True)
        ],
    }


# ---------------------------------------------------------------------------
# 内部函数
# ---------------------------------------------------------------------------

def _build_graph(data: pd.DataFrame) -> nx.Graph:
    """聚合配对并构建加权无向图。"""
    agg = data.groupby(["account_id", "account_id_y"]).agg(
        weight=("time_delta", "count"),
        avg_time_delta=("time_delta", "mean"),
        n_content_id=("content_id", "nunique"),
        n_content_id_y=("content_id_y", "nunique"),
    ).reset_index()

    agg["edge_symmetry_score"] = agg.apply(
        lambda r: min(r["n_content_id"], r["n_content_id_y"])
        / max(r["n_content_id"], r["n_content_id_y"])
        if max(r["n_content_id"], r["n_content_id_y"]) > 0 else 0,
        axis=1,
    )

    G = nx.Graph()
    for _, row in agg.iterrows():
        G.add_edge(
            str(row["account_id"]),
            str(row["account_id_y"]),
            weight=int(row["weight"]),
            avg_time_delta=round(float(row["avg_time_delta"]), 2),
            n_content_id=int(row["n_content_id"]),
            n_content_id_y=int(row["n_content_id_y"]),
            edge_symmetry_score=round(float(row["edge_symmetry_score"]), 4),
        )
    return G


def _apply_weight_threshold(G: nx.Graph, percentile: float, weight_attr: str, threshold_attr: str):
    """按分位数为边打上阈值标记。"""
    weights = [d.get(weight_attr, 0) for _, _, d in G.edges(data=True)]
    if not weights:
        return
    threshold = float(np.percentile([w for w in weights if w], percentile * 100))
    for u, v, d in G.edges(data=True):
        d[threshold_attr] = 1 if d.get(weight_attr, 0) > threshold else 0


def _extract_subgraph(G: nx.Graph, threshold_attr: str) -> nx.Graph:
    """提取超阈值边构成的子图。"""
    edges = [(u, v) for u, v, d in G.edges(data=True) if d.get(threshold_attr, 0) == 1]
    sub = G.edge_subgraph(edges).copy()
    sub.remove_nodes_from([n for n in sub.nodes() if sub.degree(n) == 0])
    return sub
