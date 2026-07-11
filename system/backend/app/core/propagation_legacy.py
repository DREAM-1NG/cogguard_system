"""传播归因分析模块。

基于帖子的时序关系构建传播子图，识别关键角色，提取证据链与关键路径：
- 起爆节点（最早发布者）
- 桥接节点（连接不同群体）
- 扩散节点（高转发量）
- 证据链（claim 级传播路径 + 关键角色 + 支撑帖子）
"""

from __future__ import annotations

from collections import Counter
import hashlib
from itertools import islice

import networkx as nx
import numpy as np
import pandas as pd

from app.core.propagation.builders import build_claims, build_timeline
from app.core.propagation.constants import (
    APPROX_BETWEENNESS_SAMPLE_SIZE,
    DIFFUSION_MAX_DEPTH,
    DIFFUSION_VISIBLE_NODE_LIMIT,
    EXACT_BETWEENNESS_NODE_LIMIT,
)
from app.core.propagation.quality import build_user_quality_portrait
from app.core.propagation.roles import identify_key_roles



# ---------------------------------------------------------------------------
# Public entry
# ---------------------------------------------------------------------------

def build_propagation_graph(
    posts: list[dict],
    comments: list[dict] | None = None,
    diffusion_node_limit: int = DIFFUSION_VISIBLE_NODE_LIMIT,
) -> dict:
    """从帖子列表构建传播图，按共享对象（URL/标签）追踪传播链。

    Parameters
    ----------
    posts : list[dict]
        帖子列表（来自 raw_posts）。
    comments : list[dict] | None
        评论列表（来自 raw_comments），用于提取显式回复边。

    Returns
    -------
    dict 含 graph_data, timeline, key_roles, claims, evidence_chains
    """
    if not posts:
        return _empty_result()

    df = pd.DataFrame(posts)
    df["ts"] = pd.to_datetime(df.get("timestamp"), errors="coerce", utc=True)
    df = df.dropna(subset=["ts"]).sort_values("ts")

    if df.empty:
        return _empty_result()

    # --- 构建 MultiDiGraph（支持同一对节点间多条边）---
    G = nx.MultiDiGraph()

    # 添加节点
    for _, row in df.iterrows():
        node_id = str(row.get("author_id", ""))
        if not node_id:
            continue
        if node_id not in G:
            G.add_node(
                node_id,
                author_name=row.get("author_name", node_id),
                post_count=0,
                first_ts=str(row["ts"]),
            )
        G.nodes[node_id]["post_count"] = G.nodes[node_id].get("post_count", 0) + 1

    # --- 隐式边：共享对象（URL / 标签）时序关联 ---
    shared_objects: dict[str, list] = {}
    for _, row in df.iterrows():
        objs: list[str] = []
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
        # 有界时序前驱规则：每个分享者连接到最近的前驱（而非始终连接到最早分享者）
        for i, follower in enumerate(sorted_shares[1:], start=1):
            if not follower["author_id"]:
                continue
            # 向前搜索最近的不同作者前驱
            predecessor = None
            for j in range(i - 1, -1, -1):
                cand = sorted_shares[j]
                if cand["author_id"] != follower["author_id"]:
                    predecessor = cand
                    break
            if predecessor is None:
                continue
            src, dst = predecessor["author_id"], follower["author_id"]
            time_delta = (follower["ts"] - predecessor["ts"]).total_seconds()
            G.add_edge(
                src, dst,
                type="implicit",
                weight=1,
                object_id=obj_id,
                time_delta=round(time_delta, 1),
            )

    # --- 显式边：评论回复关系 ---
    _add_explicit_edges(G, df, comments or [])

    # --- 分析 ---
    bc = _betweenness(G)
    key_roles = identify_key_roles(G, bc)

    claims = build_claims(shared_objects)
    timeline = build_timeline(df)

    evidence_chains = _extract_evidence_chains(G, shared_objects, key_roles, bc, df)
    path_analysis = _build_path_analysis(G, evidence_chains)
    diffusion_summary = _build_diffusion_summary(
        G,
        evidence_chains,
        shared_objects,
        df,
        comments or [],
        node_limit=diffusion_node_limit,
    )
    user_quality = build_user_quality_portrait(posts, comments or [])

    # --- 序列化 ---
    nodes = []
    for n, attrs in G.nodes(data=True):
        nodes.append({"id": n, **{k: v for k, v in attrs.items()}})

    edges = []
    for u, v, _key, d in G.edges(data=True, keys=True):
        edges.append({
            "source": u,
            "target": v,
            "weight": d.get("weight", 1),
            "type": d.get("type", "implicit"),
        })

    return {
        "graph": {
            "nodes": nodes,
            "edges": edges,
            "node_count": G.number_of_nodes(),
            "edge_count": G.number_of_edges(),
        },
        "key_roles": key_roles,
        "claims": claims,
        "timeline": timeline,
        "evidence_chains": evidence_chains,
        "path_analysis": path_analysis,
        "diffusion_summary": diffusion_summary,
        "user_quality": user_quality,
    }


# ---------------------------------------------------------------------------
# 显式边提取
# ---------------------------------------------------------------------------

def _add_explicit_edges(
    G: nx.MultiDiGraph,
    df: pd.DataFrame,
    comments: list[dict],
) -> None:
    """从评论的 reply_to 字段提取显式回复边并加入图。"""
    if not comments:
        return

    # 构建 post_id → author_id 查找表
    post_author: dict[str, str] = {}
    for _, row in df.iterrows():
        pid = str(row.get("post_id", ""))
        aid = str(row.get("author_id", ""))
        if pid and aid:
            post_author[pid] = aid

    # 也把评论自身加入查找表（支持评论回复评论）
    comment_author: dict[str, str] = {}
    comment_author_name: dict[str, str] = {}
    for c in comments:
        cid = str(c.get("comment_id", ""))
        aid = str(c.get("author_id", ""))
        if cid and aid:
            comment_author[cid] = aid
            comment_author_name[aid] = c.get("author_name", aid)

    for c in comments:
        reply_to = str(c.get("reply_to", "") or "")
        if not reply_to:
            continue
        commenter = str(c.get("author_id", ""))
        if not commenter:
            continue

        # reply_to 可能指向帖子或评论
        parent_author = post_author.get(reply_to) or comment_author.get(reply_to)
        if not parent_author or parent_author == commenter:
            continue

        # 确保节点存在
        if parent_author not in G:
            G.add_node(
                parent_author,
                author_name=comment_author_name.get(parent_author, parent_author),
                post_count=0,
                first_ts="",
            )
        if commenter not in G:
            G.add_node(commenter, author_name=c.get("author_name", commenter), post_count=0, first_ts="")

        # 传播方向是“被回复内容的作者 -> 评论/回复者”，否则评论活跃用户会被误判成源头。
        G.add_edge(
            parent_author, commenter,
            type="explicit",
            weight=1,
            comment_id=str(c.get("comment_id", "")),
        )


# ---------------------------------------------------------------------------
# Betweenness centrality (cached for reuse)
# ---------------------------------------------------------------------------

def _betweenness(G: nx.MultiDiGraph) -> dict[str, float]:
    """计算介数中心性，供角色识别和路径评分共用。"""
    if G.number_of_edges() == 0:
        return {}
    try:
        if G.number_of_nodes() <= EXACT_BETWEENNESS_NODE_LIMIT:
            return nx.betweenness_centrality(G, weight="weight")

        simple_G = nx.DiGraph()
        simple_G.add_nodes_from(G.nodes())
        for u, v, _key, data in G.edges(data=True, keys=True):
            weight = float(data.get("weight", 1) or 1)
            if simple_G.has_edge(u, v):
                simple_G[u][v]["weight"] += weight
            else:
                simple_G.add_edge(u, v, weight=weight)

        sample_size = min(APPROX_BETWEENNESS_SAMPLE_SIZE, simple_G.number_of_nodes())
        return nx.betweenness_centrality(
            simple_G,
            k=sample_size,
            weight="weight",
            seed=42,
        )
    except Exception:
        return {}


# ---------------------------------------------------------------------------
# Zhiview-style observed propagation summaries
# ---------------------------------------------------------------------------

def _build_path_analysis(G: nx.MultiDiGraph, evidence_chains: list[dict]) -> dict:
    """Summarize observed propagation paths and hierarchy from the graph."""
    edge_type_counts = Counter(
        d.get("type", "implicit") for _u, _v, _k, d in G.edges(data=True, keys=True)
    )
    layer_distribution = _build_layer_distribution(G)
    max_depth = max((row["level"] for row in layer_distribution if row["level"] >= 0), default=0)

    key_paths: list[dict] = []
    for chain in evidence_chains:
        for path in chain.get("key_paths", []) or []:
            key_paths.append({
                "claim_id": chain.get("claim_id"),
                "path_id": path.get("path_id"),
                "nodes": path.get("nodes", []),
                "score": path.get("score", 0),
                "confidence": path.get("confidence", "unknown"),
                "path_length": (path.get("metadata") or {}).get("path_length", len(path.get("nodes", []))),
                "explanation": path.get("explanation", ""),
            })
    key_paths.sort(key=lambda item: item.get("score", 0), reverse=True)

    first_layer = next((row for row in layer_distribution if row["level"] == 1), None)
    return {
        "node_count": G.number_of_nodes(),
        "edge_count": G.number_of_edges(),
        "max_depth": max_depth,
        "edge_type_counts": dict(edge_type_counts),
        "first_layer_ratio": first_layer["ratio"] if first_layer else 0,
        "layer_distribution": layer_distribution,
        "key_paths": key_paths[:8],
    }


def _build_layer_distribution(G: nx.MultiDiGraph) -> list[dict]:
    if G.number_of_nodes() == 0:
        return []

    simple_G = nx.DiGraph()
    simple_G.add_nodes_from(G.nodes())
    for u, v in G.edges():
        simple_G.add_edge(u, v)

    roots = [
        n for n in simple_G.nodes()
        if simple_G.in_degree(n) == 0 and simple_G.out_degree(n) > 0
    ]
    if not roots:
        roots = [
            n for n, _deg in sorted(
                simple_G.out_degree(),
                key=lambda item: item[1],
                reverse=True,
            )[:3]
            if simple_G.out_degree(n) > 0
        ]
    if not roots:
        roots = list(simple_G.nodes())[:1]

    node_layers: dict[str, int] = {}
    for root in roots:
        lengths = nx.single_source_shortest_path_length(simple_G, root)
        for node, layer in lengths.items():
            node_layers[node] = min(layer, node_layers.get(node, layer))

    for node in simple_G.nodes():
        node_layers.setdefault(node, -1)

    total = max(simple_G.number_of_nodes(), 1)
    counts = Counter(node_layers.values())
    rows = []
    for level, count in sorted(counts.items(), key=lambda item: item[0]):
        label = "未连接" if level < 0 else ("源头层" if level == 0 else f"第{level}层")
        rows.append({
            "level": level,
            "label": label,
            "node_count": count,
            "ratio": round(count / total, 4),
        })
    return rows


def _build_diffusion_summary(
    G: nx.MultiDiGraph,
    evidence_chains: list[dict],
    shared_objects: dict[str, list],
    df: pd.DataFrame,
    comments: list[dict],
    node_limit: int = DIFFUSION_VISIBLE_NODE_LIMIT,
) -> dict:
    """Build a stable radial diffusion-tree summary from the full observed graph.

    The frontend should render this summary instead of inferring roots and
    layers from key paths. Full graph data is used for scoring, but only a
    readable backbone is returned for the first-screen visualization.
    """
    resolved_node_limit = _resolve_diffusion_node_limit(node_limit, G.number_of_nodes())
    if G.number_of_nodes() == 0:
        return _empty_diffusion_summary(resolved_node_limit, requested_node_limit=node_limit)

    simple_G = _to_weighted_digraph(G)
    key_paths = _flatten_key_paths(evidence_chains)
    key_node_set = {node for path in key_paths for node in path.get("nodes", [])}
    key_edge_set = {
        (path["nodes"][index], path["nodes"][index + 1])
        for path in key_paths
        for index in range(max(len(path.get("nodes", [])) - 1, 0))
    }

    root_id = _select_key_path_root(key_paths, simple_G, G) or _select_diffusion_root(simple_G, G)
    parallel_roots = _select_parallel_roots(simple_G, G, root_id)
    subtree_sizes = _estimate_subtree_sizes(simple_G, root_id)
    post_index = _build_post_index(df)
    comment_index = _build_comment_index(comments)
    is_full_view = resolved_node_limit >= G.number_of_nodes()

    visible_nodes: set[str] = set()
    tree_edges: dict[tuple[str, str], dict] = {}
    node_layers: dict[str, int] = {}

    def add_node(node_id: str, layer: int, *, force: bool = False) -> bool:
        if not node_id or not simple_G.has_node(node_id):
            return False
        if len(visible_nodes) >= resolved_node_limit and node_id not in visible_nodes and not force:
            return False
        visible_nodes.add(node_id)
        node_layers[node_id] = min(layer, node_layers.get(node_id, layer))
        return True

    add_node(root_id, 0)
    queue: list[tuple[str, int]] = [(root_id, 0)] if root_id else []
    for parallel_root in parallel_roots:
        if add_node(parallel_root, 1) and root_id:
            tree_edges[(root_id, parallel_root)] = {
                "source": root_id,
                "target": parallel_root,
                "weight": simple_G[root_id][parallel_root]["weight"] if simple_G.has_edge(root_id, parallel_root) else 1,
                "type": "parallel_root",
                "is_parallel_root": True,
            }
            queue.append((parallel_root, 1))

    visited_for_expansion = {root_id} if root_id else set()
    while queue:
        parent, depth = queue.pop(0)
        if depth >= DIFFUSION_MAX_DEPTH:
            continue
        if parent in visited_for_expansion and parent != root_id:
            continue
        visited_for_expansion.add(parent)

        children = [
            child for child in simple_G.successors(parent)
            if child != parent and child not in visible_nodes
        ]
        children.sort(
            key=lambda child: _diffusion_child_score(simple_G, G, child, subtree_sizes, key_node_set, key_edge_set, parent),
            reverse=True,
        )
        budget = _diffusion_child_budget(depth)
        for child in children[:budget]:
            next_depth = depth + 1
            if not add_node(child, next_depth):
                continue
            edge_data = simple_G[parent][child]
            tree_edges[(parent, child)] = {
                "source": parent,
                "target": child,
                "weight": edge_data.get("weight", 1),
                "type": edge_data.get("type", "implicit"),
                "object_id": edge_data.get("object_id"),
                "is_parallel_root": False,
            }
            queue.append((child, next_depth))

    # Force key paths into the readable tree even when they are not among the
    # top influence branches. Their edges are highlighted separately.
    for path in key_paths:
        nodes = [node for node in path.get("nodes", []) if simple_G.has_node(node)]
        starts_at_root = bool(nodes) and nodes[0] == root_id
        for index, node in enumerate(nodes):
            path_layer = min(index, DIFFUSION_MAX_DEPTH) if starts_at_root else (
                0 if node == root_id else min(index + 1, DIFFUSION_MAX_DEPTH)
            )
            if not add_node(node, path_layer, force=len(visible_nodes) < resolved_node_limit):
                continue
            if index > 0:
                source = nodes[index - 1]
                target = node
                if source in visible_nodes and target in visible_nodes:
                    edge_data = simple_G.get_edge_data(source, target, default={})
                    tree_edges.setdefault((source, target), {
                        "source": source,
                        "target": target,
                        "weight": edge_data.get("weight", 1),
                        "type": edge_data.get("type", "key_path"),
                        "object_id": edge_data.get("object_id"),
                        "is_parallel_root": False,
                    })

    if is_full_view:
        full_layers = _diffusion_all_node_layers(simple_G, root_id)
        for node_id, layer in full_layers.items():
            visible_nodes.add(node_id)
            node_layers[node_id] = layer
        for source, target, edge_data in simple_G.edges(data=True):
            if source == target:
                continue
            source_layer = node_layers.get(source)
            target_layer = node_layers.get(target)
            if source_layer == target_layer:
                continue
            tree_edges.setdefault((source, target), {
                "source": source,
                "target": target,
                "weight": edge_data.get("weight", 1),
                "type": edge_data.get("type", "implicit"),
                "object_id": edge_data.get("object_id"),
                "is_parallel_root": False,
            })

    visible_node_rows = [
        _diffusion_node_row(G, simple_G, node_id, node_layers.get(node_id, -1), key_node_set, root_id)
        for node_id in sorted(
            visible_nodes,
            key=lambda item: (node_layers.get(item, 999), -simple_G.out_degree(item), str(item)),
        )
    ]
    visible_node_ids = {row["id"] for row in visible_node_rows}

    tree_edge_rows = [
        edge for edge in tree_edges.values()
        if edge["source"] in visible_node_ids and edge["target"] in visible_node_ids
        and node_layers.get(edge["source"]) != node_layers.get(edge["target"])
    ]
    highlight_edges = [
        _diffusion_highlight_edge(simple_G, source, target)
        for source, target in key_edge_set
        if source in visible_node_ids and target in visible_node_ids
        and node_layers.get(source) != node_layers.get(target)
    ]
    visible_node_rows = _apply_clustered_diffusion_layout(
        visible_node_rows,
        tree_edge_rows,
        shared_objects,
        root_id,
        simple_G,
    )

    layers = _diffusion_layer_rows(visible_node_rows, simple_G.number_of_nodes())
    detail_index = _build_diffusion_detail_index(
        visible_node_ids,
        shared_objects,
        post_index,
        comment_index,
        evidence_chains,
        simple_G,
        G,
    )

    return {
        "root_node": _diffusion_node_row(G, simple_G, root_id, 0, key_node_set, root_id) if root_id else None,
        "parallel_roots": [
            _diffusion_node_row(G, simple_G, node_id, node_layers.get(node_id, 1), key_node_set, root_id)
            for node_id in parallel_roots
            if node_id in visible_node_ids
        ],
        "visible_nodes": visible_node_rows,
        "tree_edges": tree_edge_rows,
        "highlight_edges": highlight_edges,
        "layers": layers,
        "detail_index": detail_index,
        "meta": {
            "mode": "layered_summary",
            "layout": "clustered_similarity",
            "source": "full_observed_graph",
            "total_nodes": G.number_of_nodes(),
            "total_edges": G.number_of_edges(),
            "requested_node_limit": int(node_limit or 0),
            "visible_node_limit": resolved_node_limit,
            "visible_node_count": len(visible_node_rows),
            "is_full_view": is_full_view,
            "tree_edge_count": len(tree_edge_rows),
            "highlight_edge_count": len(highlight_edges),
        },
    }


def _resolve_diffusion_node_limit(node_limit: int | None, total_nodes: int) -> int:
    if total_nodes <= 0:
        return 0
    try:
        requested = int(node_limit if node_limit is not None else DIFFUSION_VISIBLE_NODE_LIMIT)
    except (TypeError, ValueError):
        requested = DIFFUSION_VISIBLE_NODE_LIMIT
    if requested <= 0:
        return total_nodes
    return min(max(requested, 1), total_nodes)


def _empty_diffusion_summary(
    visible_node_limit: int = DIFFUSION_VISIBLE_NODE_LIMIT,
    *,
    requested_node_limit: int | None = None,
) -> dict:
    return {
        "root_node": None,
        "parallel_roots": [],
        "visible_nodes": [],
        "tree_edges": [],
        "highlight_edges": [],
        "layers": [],
        "detail_index": {"nodes": {}, "objects": {}},
        "meta": {
            "mode": "layered_summary",
            "layout": "radial",
            "source": "full_observed_graph",
            "total_nodes": 0,
            "total_edges": 0,
            "requested_node_limit": int(requested_node_limit or visible_node_limit or 0),
            "visible_node_limit": visible_node_limit,
            "visible_node_count": 0,
            "is_full_view": True,
            "tree_edge_count": 0,
            "highlight_edge_count": 0,
        },
    }


def _to_weighted_digraph(G: nx.MultiDiGraph) -> nx.DiGraph:
    simple_G = nx.DiGraph()
    simple_G.add_nodes_from(G.nodes())
    for u, v, _key, data in G.edges(data=True, keys=True):
        weight = float(data.get("weight", 1) or 1)
        edge_type = data.get("type", "implicit")
        object_id = data.get("object_id")
        if simple_G.has_edge(u, v):
            simple_G[u][v]["weight"] += weight
            if edge_type == "explicit":
                simple_G[u][v]["type"] = "explicit"
            if not simple_G[u][v].get("object_id") and object_id:
                simple_G[u][v]["object_id"] = object_id
        else:
            simple_G.add_edge(u, v, weight=weight, type=edge_type, object_id=object_id)
    return simple_G


def _flatten_key_paths(evidence_chains: list[dict]) -> list[dict]:
    key_paths = []
    for chain in evidence_chains:
        for path in chain.get("key_paths", []) or []:
            nodes = [str(node) for node in path.get("nodes", []) if str(node)]
            if len(nodes) < 2:
                continue
            key_paths.append({
                "claim_id": chain.get("claim_id"),
                "nodes": nodes,
                "score": path.get("score", 0),
                "explanation": path.get("explanation", ""),
            })
    key_paths.sort(key=lambda item: item.get("score", 0), reverse=True)
    return key_paths[:8]


def _node_has_observed_content(G: nx.MultiDiGraph, node: str) -> bool:
    if not node or not G.has_node(node):
        return False
    attrs = G.nodes[node]
    return bool(int(attrs.get("post_count", 0) or 0) > 0 or attrs.get("first_ts"))


def _select_key_path_root(key_paths: list[dict], simple_G: nx.DiGraph, G: nx.MultiDiGraph) -> str:
    """Use the strongest observed key path origin as the visual root when available."""
    for path in key_paths:
        for node in path.get("nodes", []) or []:
            node_id = str(node)
            if node_id and simple_G.has_node(node_id) and _node_has_observed_content(G, node_id):
                return node_id
    return ""


def _select_diffusion_root(simple_G: nx.DiGraph, G: nx.MultiDiGraph) -> str:
    if simple_G.number_of_nodes() == 0:
        return ""

    roots = [
        node for node in simple_G.nodes()
        if simple_G.in_degree(node) == 0 and simple_G.out_degree(node) > 0
    ]
    candidates = roots or [node for node in simple_G.nodes() if simple_G.out_degree(node) > 0] or list(simple_G.nodes())
    observed_candidates = [node for node in candidates if _node_has_observed_content(G, node)]
    if observed_candidates:
        candidates = observed_candidates

    def first_ts(node: str) -> pd.Timestamp:
        ts = G.nodes[node].get("first_ts", "") if G.has_node(node) else ""
        parsed = pd.to_datetime(ts, errors="coerce", utc=True)
        return parsed if not pd.isna(parsed) else pd.Timestamp.max.tz_localize("UTC")

    return sorted(
        candidates,
        key=lambda node: (
            -simple_G.out_degree(node),
            simple_G.in_degree(node),
            first_ts(node),
            str(node),
        ),
    )[0]


def _select_parallel_roots(simple_G: nx.DiGraph, G: nx.MultiDiGraph, root_id: str, limit: int = 8) -> list[str]:
    roots = [
        node for node in simple_G.nodes()
        if node != root_id and simple_G.in_degree(node) == 0 and simple_G.out_degree(node) > 0
    ]

    def first_ts(node: str) -> pd.Timestamp:
        ts = G.nodes[node].get("first_ts", "") if G.has_node(node) else ""
        parsed = pd.to_datetime(ts, errors="coerce", utc=True)
        return parsed if not pd.isna(parsed) else pd.Timestamp.max.tz_localize("UTC")

    roots.sort(key=lambda node: (-simple_G.out_degree(node), first_ts(node), str(node)))
    return roots[:limit]


def _estimate_subtree_sizes(simple_G: nx.DiGraph, root_id: str) -> dict[str, int]:
    subtree_sizes: dict[str, int] = {node: int(simple_G.out_degree(node)) for node in simple_G.nodes()}
    for node in simple_G.nodes():
        children = list(simple_G.successors(node))
        subtree_sizes[node] += sum(int(simple_G.out_degree(child)) for child in children[:64])
    if root_id and root_id in subtree_sizes:
        subtree_sizes[root_id] = max(subtree_sizes[root_id], simple_G.out_degree(root_id))
    return subtree_sizes


def _diffusion_all_node_layers(simple_G: nx.DiGraph, root_id: str) -> dict[str, int]:
    if simple_G.number_of_nodes() == 0:
        return {}

    layers: dict[str, int] = {}
    if root_id and simple_G.has_node(root_id):
        for node, layer in nx.single_source_shortest_path_length(simple_G, root_id).items():
            layers[node] = min(int(layer), DIFFUSION_MAX_DEPTH)

    roots = [
        node for node in simple_G.nodes()
        if node != root_id and simple_G.in_degree(node) == 0 and simple_G.out_degree(node) > 0
    ]
    for root in roots:
        root_layer = 1 if root_id else 0
        layers[root] = min(root_layer, layers.get(root, root_layer))
        for node, layer in nx.single_source_shortest_path_length(simple_G, root).items():
            candidate_layer = min(root_layer + int(layer), DIFFUSION_MAX_DEPTH)
            layers[node] = min(candidate_layer, layers.get(node, candidate_layer))

    for node in simple_G.nodes():
        layers.setdefault(node, DIFFUSION_MAX_DEPTH)
    return layers


def _diffusion_child_score(
    simple_G: nx.DiGraph,
    G: nx.MultiDiGraph,
    child: str,
    subtree_sizes: dict[str, int],
    key_node_set: set[str],
    key_edge_set: set[tuple[str, str]],
    parent: str,
) -> float:
    edge_weight = float(simple_G[parent][child].get("weight", 1) if simple_G.has_edge(parent, child) else 1)
    post_count = float(G.nodes[child].get("post_count", 1) if G.has_node(child) else 1)
    key_bonus = 250.0 if child in key_node_set or (parent, child) in key_edge_set else 0.0
    return (
        edge_weight * 8
        + simple_G.out_degree(child) * 6
        + subtree_sizes.get(child, 0) * 1.5
        + np.log1p(post_count) * 4
        + key_bonus
    )


def _diffusion_child_budget(depth: int) -> int:
    budgets = [34, 16, 9, 6, 4, 3]
    return budgets[depth] if depth < len(budgets) else 2


def _diffusion_node_row(
    G: nx.MultiDiGraph,
    simple_G: nx.DiGraph,
    node_id: str,
    layer: int,
    key_node_set: set[str],
    root_id: str,
) -> dict:
    attrs = G.nodes[node_id] if node_id and G.has_node(node_id) else {}
    return {
        "id": node_id,
        "author_name": attrs.get("author_name") or node_id,
        "layer": layer,
        "post_count": int(attrs.get("post_count", 0) or 0),
        "first_ts": attrs.get("first_ts", ""),
        "out_degree": int(simple_G.out_degree(node_id)) if node_id and simple_G.has_node(node_id) else 0,
        "in_degree": int(simple_G.in_degree(node_id)) if node_id and simple_G.has_node(node_id) else 0,
        "is_root": node_id == root_id,
        "is_key": node_id in key_node_set,
    }


def _diffusion_highlight_edge(simple_G: nx.DiGraph, source: str, target: str) -> dict:
    edge_data = simple_G.get_edge_data(source, target, default={})
    return {
        "source": source,
        "target": target,
        "weight": edge_data.get("weight", 1),
        "type": edge_data.get("type", "key_path"),
        "object_id": edge_data.get("object_id"),
        "is_key_path": True,
    }


def _apply_clustered_diffusion_layout(
    visible_nodes: list[dict],
    tree_edges: list[dict],
    shared_objects: dict[str, list],
    root_id: str,
    simple_G: nx.DiGraph,
) -> list[dict]:
    if not visible_nodes:
        return visible_nodes

    node_ids = {str(node.get("id", "")) for node in visible_nodes if node.get("id")}
    object_weights = {
        str(object_id): max(float(len(shares)), 1.0)
        for object_id, shares in shared_objects.items()
    }
    node_object_map = _build_node_object_weight_map(shared_objects, tree_edges, node_ids)
    root_objects = node_object_map.get(root_id, {})

    parent_by_child = {
        str(edge.get("target")): str(edge.get("source"))
        for edge in tree_edges
        if edge.get("source") and edge.get("target")
    }
    children_by_parent: dict[str, list[str]] = {}
    for child, parent in parent_by_child.items():
        children_by_parent.setdefault(parent, []).append(child)

    node_by_id = {str(node["id"]): node for node in visible_nodes}
    first_layer_nodes = [
        node for node in visible_nodes
        if int(node.get("layer", 0) or 0) == 1
    ]
    first_layer_nodes.sort(
        key=lambda node: (
            -int(node.get("out_degree", 0) or 0),
            -int(node.get("post_count", 0) or 0),
            str(node.get("id", "")),
        )
    )

    cluster_anchor_ids = [str(node["id"]) for node in first_layer_nodes[:18]]
    if not cluster_anchor_ids and root_id:
        cluster_anchor_ids = [
            str(node["id"]) for node in visible_nodes
            if str(node.get("id")) != root_id
        ][:1]
    cluster_angles = {
        anchor_id: (-np.pi / 2) + (2 * np.pi * index / max(len(cluster_anchor_ids), 1))
        for index, anchor_id in enumerate(cluster_anchor_ids)
    }

    cluster_by_node: dict[str, str] = {}
    for anchor_id in cluster_anchor_ids:
        cluster_by_node[anchor_id] = anchor_id

    for node in sorted(visible_nodes, key=lambda item: int(item.get("layer", 0) or 0)):
        node_id = str(node.get("id", ""))
        if not node_id or node_id == root_id or node_id in cluster_by_node:
            continue
        parent = parent_by_child.get(node_id)
        if parent and parent in cluster_by_node:
            cluster_by_node[node_id] = cluster_by_node[parent]
            continue
        cluster_by_node[node_id] = _nearest_object_cluster(
            node_id,
            cluster_anchor_ids,
            node_object_map,
        )

    nodes_by_cluster: dict[str, list[dict]] = {}
    for node in visible_nodes:
        node_id = str(node.get("id", ""))
        cluster_id = "root" if node_id == root_id else cluster_by_node.get(node_id) or "root"
        nodes_by_cluster.setdefault(cluster_id, []).append(node)

    laid_out: list[dict] = []
    for node in visible_nodes:
        node_id = str(node.get("id", ""))
        layer = max(int(node.get("layer", 0) or 0), 0)
        node_objects = node_object_map.get(node_id, {})
        similarity_to_root = _weighted_jaccard(node_objects, root_objects, object_weights)
        shared_object_ids = sorted(
            node_objects.keys(),
            key=lambda object_id: (-node_objects.get(object_id, 0), object_id),
        )[:8]

        if node_id == root_id:
            layout_x = 0.0
            layout_y = 0.0
            layout_radius = 0.0
            cluster_id = "root"
        else:
            cluster_id = cluster_by_node.get(node_id) or "root"
            cluster_nodes = nodes_by_cluster.get(cluster_id, [])
            cluster_index = max(0, _node_index_in_cluster(cluster_nodes, node_id))
            cluster_size = max(len(cluster_nodes), 1)
            base_angle = cluster_angles.get(cluster_id, _stable_angle(cluster_id))
            angle_spread = 0.92 if layer <= 1 else 0.68 if layer <= 3 else 0.44
            angle = base_angle + _cluster_offset(cluster_index, cluster_size, angle_spread) + _stable_jitter(node_id, 0.035)
            layout_radius = _cluster_layout_radius(layer, similarity_to_root, cluster_index, cluster_size)
            layout_x = float(np.cos(angle) * layout_radius)
            layout_y = float(np.sin(angle) * layout_radius)

        enriched = dict(node)
        enriched.update({
            "layout_x": round(layout_x, 3),
            "layout_y": round(layout_y, 3),
            "layout_cluster": cluster_id,
            "layout_radius": round(layout_radius, 3),
            "similarity_to_root": round(float(similarity_to_root), 4),
            "shared_object_ids": shared_object_ids,
        })
        laid_out.append(enriched)

    return laid_out


def _build_node_object_weight_map(
    shared_objects: dict[str, list],
    tree_edges: list[dict],
    visible_node_ids: set[str],
) -> dict[str, dict[str, float]]:
    node_objects: dict[str, dict[str, float]] = {node_id: {} for node_id in visible_node_ids}

    def add_object(node_id: str, object_id: str, weight: float) -> None:
        if not node_id or node_id not in visible_node_ids or not object_id:
            return
        bucket = node_objects.setdefault(node_id, {})
        bucket[object_id] = bucket.get(object_id, 0.0) + max(float(weight), 1.0)

    for object_id, shares in shared_objects.items():
        share_weight = max(float(len(shares)), 1.0)
        for share in shares:
            add_object(str(share.get("author_id", "")), str(object_id), share_weight)

    for edge in tree_edges:
        object_id = str(edge.get("object_id") or "")
        if not object_id:
            continue
        weight = float(edge.get("weight", 1) or 1)
        add_object(str(edge.get("source", "")), object_id, weight)
        add_object(str(edge.get("target", "")), object_id, weight)

    return node_objects


def _weighted_jaccard(left: dict[str, float], right: dict[str, float], object_weights: dict[str, float]) -> float:
    keys = set(left) | set(right)
    if not keys:
        return 0.0
    numerator = 0.0
    denominator = 0.0
    for key in keys:
        weight = max(float(object_weights.get(key, 1.0)), 1.0)
        left_value = float(left.get(key, 0.0)) * weight
        right_value = float(right.get(key, 0.0)) * weight
        numerator += min(left_value, right_value)
        denominator += max(left_value, right_value)
    return numerator / denominator if denominator else 0.0


def _nearest_object_cluster(
    node_id: str,
    cluster_anchor_ids: list[str],
    node_object_map: dict[str, dict[str, float]],
) -> str:
    if not cluster_anchor_ids:
        return "root"
    node_objects = node_object_map.get(node_id, {})
    return max(
        cluster_anchor_ids,
        key=lambda anchor_id: (
            _weighted_jaccard(node_objects, node_object_map.get(anchor_id, {}), {}),
            anchor_id,
        ),
    )


def _node_index_in_cluster(cluster_nodes: list[dict], node_id: str) -> int:
    ordered = sorted(
        cluster_nodes,
        key=lambda node: (
            int(node.get("layer", 0) or 0),
            -int(node.get("out_degree", 0) or 0),
            str(node.get("id", "")),
        ),
    )
    for index, node in enumerate(ordered):
        if str(node.get("id", "")) == node_id:
            return index
    return 0


def _cluster_layout_radius(layer: int, similarity_to_root: float, cluster_index: int, cluster_size: int) -> float:
    if layer <= 1:
        base = 92.0
        spread = 42.0
    elif layer == 2:
        base = 190.0
        spread = 82.0
    elif layer == 3:
        base = 292.0
        spread = 112.0
    else:
        base = 390.0 + min(layer - 4, 3) * 74.0
        spread = 132.0
    density_offset = (cluster_index / max(cluster_size - 1, 1)) * spread
    similarity_pull = float(similarity_to_root) * 44.0
    return max(36.0, base + density_offset - similarity_pull)


def _cluster_offset(index: int, size: int, spread: float) -> float:
    if size <= 1:
        return 0.0
    normalized = (index / max(size - 1, 1)) - 0.5
    return normalized * spread


def _stable_angle(value: str) -> float:
    fraction = _stable_fraction(value)
    return -np.pi + fraction * 2 * np.pi


def _stable_jitter(value: str, scale: float) -> float:
    return (_stable_fraction(value) - 0.5) * 2 * scale


def _stable_fraction(value: str) -> float:
    digest = hashlib.sha1(str(value).encode("utf-8")).hexdigest()
    return int(digest[:10], 16) / float(16 ** 10 - 1)


def _diffusion_layer_rows(visible_nodes: list[dict], total_nodes: int) -> list[dict]:
    total = max(total_nodes, 1)
    counts = Counter(node.get("layer", -1) for node in visible_nodes)
    rows = []
    for layer, count in sorted(counts.items(), key=lambda item: item[0]):
        if layer < 0:
            label = "未连接"
        elif layer == 0:
            label = "源头层"
        else:
            label = f"第{layer}层"
        rows.append({
            "level": layer,
            "label": label,
            "node_count": count,
            "ratio": round(count / total, 4),
        })
    return rows


def _build_post_index(df: pd.DataFrame) -> dict[str, list[dict]]:
    post_index: dict[str, list[dict]] = {}
    for _, row in df.iterrows():
        author_id = str(row.get("author_id", ""))
        if not author_id:
            continue
        post_index.setdefault(author_id, []).append({
            "post_id": str(row.get("post_id", "")),
            "author_id": author_id,
            "author_name": row.get("author_name", author_id),
            "timestamp": str(row.get("ts", "")),
            "content": str(row.get("content", ""))[:180],
            "url": str(row.get("url", "") or ""),
        })
    return post_index


def _build_comment_index(comments: list[dict]) -> dict[str, list[dict]]:
    comment_index: dict[str, list[dict]] = {}
    for comment in comments:
        author_id = str(comment.get("author_id", ""))
        if not author_id:
            continue
        comment_index.setdefault(author_id, []).append({
            "comment_id": str(comment.get("comment_id", "")),
            "post_id": str(comment.get("post_id", "")),
            "author_id": author_id,
            "author_name": comment.get("author_name", author_id),
            "timestamp": str(comment.get("timestamp", "")),
            "content": str(comment.get("content", ""))[:180],
        })
    return comment_index


def _build_diffusion_detail_index(
    visible_node_ids: set[str],
    shared_objects: dict[str, list],
    post_index: dict[str, list[dict]],
    comment_index: dict[str, list[dict]],
    evidence_chains: list[dict],
    simple_G: nx.DiGraph,
    G: nx.MultiDiGraph,
) -> dict:
    node_details = {}
    for node_id in visible_node_ids:
        attrs = G.nodes[node_id] if G.has_node(node_id) else {}
        upstream = [
            _diffusion_neighbor_row(G, parent)
            for parent in list(simple_G.predecessors(node_id))[:12]
        ] if simple_G.has_node(node_id) else []
        downstream = [
            _diffusion_neighbor_row(G, child)
            for child in list(simple_G.successors(node_id))[:12]
        ] if simple_G.has_node(node_id) else []
        node_details[node_id] = {
            "id": node_id,
            "author_name": attrs.get("author_name") or node_id,
            "post_count": int(attrs.get("post_count", 0) or 0),
            "first_ts": attrs.get("first_ts", ""),
            "out_degree": int(simple_G.out_degree(node_id)) if simple_G.has_node(node_id) else 0,
            "in_degree": int(simple_G.in_degree(node_id)) if simple_G.has_node(node_id) else 0,
            "upstream": upstream,
            "downstream": downstream,
            "posts": post_index.get(node_id, [])[:20],
            "comments": comment_index.get(node_id, [])[:20],
            "key_paths": _node_key_path_details(node_id, evidence_chains),
        }

    object_details = {}
    evidence_by_claim = {chain.get("claim_id"): chain for chain in evidence_chains}
    for object_id, shares in shared_objects.items():
        sorted_shares = sorted(shares, key=lambda item: item.get("ts"))
        object_details[object_id] = {
            "object_id": object_id,
            "share_count": len(sorted_shares),
            "account_count": len({share.get("author_id") for share in sorted_shares if share.get("author_id")}),
            "first_share": str(sorted_shares[0]["ts"]) if sorted_shares else "",
            "participants": [
                _diffusion_neighbor_row(G, str(share.get("author_id", "")))
                for share in sorted_shares[:20]
                if share.get("author_id")
            ],
            "timeline": [
                {
                    "post_id": str(share.get("post_id", "")),
                    "author_id": str(share.get("author_id", "")),
                    "author_name": G.nodes[str(share.get("author_id", ""))].get("author_name", str(share.get("author_id", "")))
                    if G.has_node(str(share.get("author_id", ""))) else str(share.get("author_id", "")),
                    "timestamp": str(share.get("ts", "")),
                }
                for share in sorted_shares[:30]
            ],
            "evidence": evidence_by_claim.get(object_id, {}),
        }
    return {"nodes": node_details, "objects": object_details}


def _diffusion_neighbor_row(G: nx.MultiDiGraph, node_id: str) -> dict:
    attrs = G.nodes[node_id] if node_id and G.has_node(node_id) else {}
    return {
        "id": node_id,
        "author_name": attrs.get("author_name") or node_id,
    }


def _node_key_path_details(node_id: str, evidence_chains: list[dict]) -> list[dict]:
    details = []
    for chain in evidence_chains:
        for path in chain.get("key_paths", []) or []:
            nodes = path.get("nodes", []) or []
            if node_id not in nodes:
                continue
            details.append({
                "claim_id": chain.get("claim_id"),
                "nodes": nodes,
                "score": path.get("score", 0),
                "explanation": path.get("explanation", ""),
            })
    details.sort(key=lambda item: item.get("score", 0), reverse=True)
    return details[:8]


# ---------------------------------------------------------------------------
# Evidence chain extraction
# ---------------------------------------------------------------------------

def _extract_evidence_chains(
    G: nx.MultiDiGraph,
    shared_objects: dict[str, list],
    key_roles: dict,
    bc: dict[str, float],
    df: pd.DataFrame,
) -> list[dict]:
    """为 Top 10 claims 生成证据链。"""
    top_claims = sorted(
        shared_objects.items(), key=lambda x: len(x[1]), reverse=True
    )[:10]

    # 构建角色查找集合
    originator_set = {r["account_id"] for r in key_roles.get("originators", [])}
    bridge_set = {r["account_id"] for r in key_roles.get("bridges", [])}
    amplifier_set = {r["account_id"] for r in key_roles.get("amplifiers", [])}

    # post_id → row 查找
    post_lookup: dict[str, dict] = {}
    for _, row in df.iterrows():
        pid = str(row.get("post_id", ""))
        if pid:
            post_lookup[pid] = {
                "post_id": pid,
                "author_id": str(row.get("author_id", "")),
                "timestamp": str(row["ts"]),
                "content": str(row.get("content", ""))[:100],
            }

    chains: list[dict] = []
    for obj_id, shares in top_claims:
        if len(shares) < 2:
            continue
        sorted_shares = sorted(shares, key=lambda s: s["ts"])
        originator = sorted_shares[0]

        # 收集该 claim 涉及的节点
        claim_authors = list({s["author_id"] for s in sorted_shares})

        # 找该 claim 的 amplifiers（入度最高的参与者）
        claim_amplifiers = sorted(
            [a for a in claim_authors if a != originator["author_id"] and G.has_node(a)],
            key=lambda a: G.in_degree(a),
            reverse=True,
        )[:3]

        key_paths = _extract_key_paths_for_claim(
            G, obj_id, originator["author_id"], claim_amplifiers, bc,
            originator_set, bridge_set, amplifier_set,
        )

        # 支撑帖子
        supporting = []
        for s in sorted_shares[:20]:
            p = post_lookup.get(s["post_id"])
            if p:
                supporting.append(p)

        chains.append({
            "claim_id": obj_id,
            "share_count": len(shares),
            "originator": {
                "account_id": originator["author_id"],
                "author_name": G.nodes[originator["author_id"]].get("author_name", "")
                if G.has_node(originator["author_id"]) else "",
                "first_ts": str(originator["ts"]),
            },
            "key_paths": key_paths,
            "supporting_posts": supporting,
        })

    return chains


# ---------------------------------------------------------------------------
# Key path extraction with hybrid scoring
# ---------------------------------------------------------------------------

def _extract_key_paths_for_claim(
    G: nx.MultiDiGraph,
    claim_obj_id: str,
    originator_id: str,
    amplifier_ids: list[str],
    bc: dict[str, float],
    originator_set: set[str],
    bridge_set: set[str],
    amplifier_set: set[str],
) -> list[dict]:
    """为单个 claim 提取 Top 3-5 关键路径。

    使用混合评分：edge_weight × edge_type_bonus × (1 + betweenness_factor)
    """
    if not amplifier_ids or not G.has_node(originator_id):
        return []

    # 将 MultiDiGraph 转为简单 DiGraph 用于路径搜索（取最大权重边）
    simple_G = nx.DiGraph()
    for u, v, _k, d in G.edges(data=True, keys=True):
        w = d.get("weight", 1)
        etype = d.get("type", "implicit")
        if simple_G.has_edge(u, v):
            existing = simple_G[u][v]
            existing["weight"] = existing["weight"] + w
            if etype == "explicit":
                existing["has_explicit"] = True
        else:
            simple_G.add_edge(u, v, weight=w, has_explicit=(etype == "explicit"))

    all_paths: list[dict] = []

    for amp_id in amplifier_ids:
        if not simple_G.has_node(amp_id):
            continue
        try:
            raw_paths = list(islice(
                nx.shortest_simple_paths(simple_G, originator_id, amp_id),
                6,
            ))
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            continue

        for path_nodes in raw_paths:
            if len(path_nodes) < 2 or len(path_nodes) > 8:
                continue

            # 构建边列表并计算分数
            path_edges = []
            edge_score = 0.0
            explicit_count = 0
            implicit_count = 0
            max_time_gap = 0.0
            for i in range(len(path_nodes) - 1):
                u, v = path_nodes[i], path_nodes[i + 1]
                ed = simple_G[u][v]
                w = ed.get("weight", 1)
                has_explicit = ed.get("has_explicit", False)
                bonus = 2.0 if has_explicit else 1.0
                edge_score += w * bonus

                if has_explicit:
                    explicit_count += 1
                else:
                    implicit_count += 1

                # 从 MultiDiGraph 取详细边信息
                edge_info = _best_edge_info(G, u, v)
                path_edges.append(edge_info)
                td = abs(edge_info.get("time_delta", 0) or 0)
                if td > max_time_gap:
                    max_time_gap = td

            # betweenness factor（中间节点）
            bc_factor = 1.0 + sum(bc.get(n, 0) for n in path_nodes[1:-1])

            score = round(edge_score * bc_factor, 2)

            explanation = _generate_path_explanation(
                path_nodes, G, bc, originator_set, bridge_set, amplifier_set,
            )

            # 路径置信度元数据
            total_edges = explicit_count + implicit_count
            explicit_ratio = round(explicit_count / total_edges, 2) if total_edges else 0
            confidence = "high" if explicit_ratio >= 0.5 else ("medium" if explicit_ratio > 0 else "low")

            all_paths.append({
                "nodes": path_nodes,
                "edges": path_edges,
                "score": score,
                "explanation": explanation,
                "confidence": confidence,
                "metadata": {
                    "explicit_edges": explicit_count,
                    "implicit_edges": implicit_count,
                    "explicit_ratio": explicit_ratio,
                    "max_time_gap_sec": round(max_time_gap, 1),
                    "path_length": len(path_nodes),
                },
            })

    # 去重（>50% 节点重叠的路径只保留分数最高的）
    all_paths.sort(key=lambda p: p["score"], reverse=True)
    selected: list[dict] = []
    for p in all_paths:
        if _is_duplicate(p, selected):
            continue
        selected.append(p)
        if len(selected) >= 5:
            break

    # 添加 path_id
    for i, p in enumerate(selected):
        p["path_id"] = i

    return selected


def _best_edge_info(G: nx.MultiDiGraph, u: str, v: str) -> dict:
    """从 MultiDiGraph 中取 u→v 的最佳边信息（优先显式边）。"""
    edges = G.get_edge_data(u, v)
    if not edges:
        return {"source": u, "target": v, "type": "implicit", "weight": 1}

    # 优先返回显式边
    best = None
    for _k, d in edges.items():
        if d.get("type") == "explicit":
            best = d
            break
        if best is None:
            best = d

    return {
        "source": u,
        "target": v,
        "type": best.get("type", "implicit"),
        "weight": best.get("weight", 1),
        **({k: v for k, v in best.items() if k not in ("type", "weight")}),
    }


def _is_duplicate(candidate: dict, selected: list[dict], threshold: float = 0.5) -> bool:
    """检查候选路径是否与已选路径重叠超过阈值。"""
    cand_set = set(candidate["nodes"])
    for s in selected:
        sel_set = set(s["nodes"])
        overlap = len(cand_set & sel_set) / max(len(cand_set), 1)
        if overlap > threshold:
            return True
    return False


# ---------------------------------------------------------------------------
# Path explanation generation
# ---------------------------------------------------------------------------

def _generate_path_explanation(
    path: list[str],
    G: nx.MultiDiGraph,
    bc: dict[str, float],
    originator_set: set[str],
    bridge_set: set[str],
    amplifier_set: set[str],
) -> str:
    """生成人类可读的中文路径解释。"""
    parts: list[str] = []
    for i, node in enumerate(path):
        name = G.nodes[node].get("author_name", node) if G.has_node(node) else node
        if i == 0:
            parts.append(f"{name} 发起传播")
        elif node in bridge_set:
            b = round(bc.get(node, 0), 3)
            parts.append(f"{name} 桥接扩散(介数{b})")
        elif node in amplifier_set:
            in_d = G.in_degree(node)
            parts.append(f"{name} 放大传播(入度{in_d})")
        elif i == len(path) - 1:
            in_d = G.in_degree(node)
            parts.append(f"{name} 接收传播(入度{in_d})")
        else:
            parts.append(f"{name} 中继传播")
    return " → ".join(parts)


# ---------------------------------------------------------------------------
# Empty result
# ---------------------------------------------------------------------------

def _empty_result():
    return {
        "graph": {"nodes": [], "edges": [], "node_count": 0, "edge_count": 0},
        "key_roles": {"originators": [], "bridges": [], "amplifiers": []},
        "claims": [],
        "timeline": [],
        "evidence_chains": [],
        "path_analysis": {
            "node_count": 0,
            "edge_count": 0,
            "max_depth": 0,
            "edge_type_counts": {},
            "first_layer_ratio": 0,
            "layer_distribution": [],
            "key_paths": [],
        },
        "diffusion_summary": _empty_diffusion_summary(),
        "user_quality": {
            "total_users": 0,
            "metrics_available": 0,
            "verified_count": 0,
            "verified_rate": 0,
            "avg_followers": None,
            "buckets": [],
            "top_accounts": [],
        },
    }
