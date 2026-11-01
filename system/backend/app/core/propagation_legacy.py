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
from app.core.propagation.roles import identify_key_roles


# ---------------------------------------------------------------------------
# Row-value coercion
#
# Posts come straight from MongoDB, where documents are heterogeneous: a field
# absent from one document becomes NaN once pandas aligns the frame. NaN is
# truthy and ``str(nan) == "nan"``, so naive ``row.get(k, default)`` access
# silently produces "nan" account nodes, a phantom shared object keyed on NaN,
# and TypeErrors when iterating a NaN list field. Always coerce through these.
# ---------------------------------------------------------------------------

def _clean_str(value) -> str:
    """Return a real string, mapping NaN/None/non-scalars to ""."""
    if value is None:
        return ""
    if isinstance(value, float) and np.isnan(value):
        return ""
    if not isinstance(value, str):
        try:
            if pd.isna(value):
                return ""
        except (TypeError, ValueError):
            pass
        value = str(value)
    text = value.strip()
    if text.lower() in {"nan", "none", "nat"}:
        return ""
    return text


def _clean_list(value) -> list:
    """Return a real list; NaN/None/scalars become []."""
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    return []


def _entity_id(entity_type: str, raw_id: str) -> str:
    return f"{entity_type}:{_clean_str(raw_id)}"


def _edge_id(source: str, target: str, key: object) -> str:
    return f"edge:{source}:{target}:{key}"


def _claim_path_prefix(claim_obj_id: str) -> str:
    claim_key = _clean_str(claim_obj_id) or "claim"
    return hashlib.sha1(claim_key.encode("utf-8")).hexdigest()[:10]


def _evidence_ref_from_content_ref(content_ref: str, platform: str = "") -> dict:
    ref_text = _clean_str(content_ref)
    if not ref_text:
        return {}
    ref_kind, _separator, ref_id = ref_text.partition(":")
    if ref_kind not in {"post", "comment"} or not ref_id:
        return {}
    ref = {f"{ref_kind}_id": ref_id}
    ref_platform = _clean_str(platform)
    if ref_platform:
        ref["platform"] = ref_platform
    return ref


def _edge_evidence_refs(edge: dict) -> list[dict]:
    if edge.get("type") == "explicit":
        comment_id = _clean_str(edge.get("comment_id"))
        if not comment_id:
            return []
        ref = {"comment_id": comment_id}
        comment_platform = _clean_str(edge.get("comment_platform"))
        if comment_platform:
            ref["platform"] = comment_platform
        return [ref]

    refs: list[dict] = []
    for ref_key, platform_key in (
        ("source_content_ref", "source_platform"),
        ("target_content_ref", "target_platform"),
    ):
        ref = _evidence_ref_from_content_ref(edge.get(ref_key, ""), edge.get(platform_key, ""))
        if ref:
            refs.append(ref)
    return refs


def _collect_path_evidence_refs(path_edges: list[dict]) -> list[dict]:
    refs: list[dict] = []
    seen: set[tuple] = set()
    for edge in path_edges:
        for ref in _edge_evidence_refs(edge):
            ref_key = tuple(sorted(ref.items()))
            if ref_key in seen:
                continue
            seen.add(ref_key)
            refs.append(ref)
    return refs


def _inferred_edge_confidence(time_delta: float) -> float:
    """Time proximity supports, but never confirms, a reconstructed relation."""
    return max(0.1, min(0.7, 0.7 / (1.0 + max(float(time_delta), 0.0) / 3600.0)))


def _explicit_time_delta(comment: dict, df: pd.DataFrame, reply_to: str) -> float | None:
    comment_ts = pd.to_datetime(comment.get("timestamp"), errors="coerce", utc=True)
    if pd.isna(comment_ts):
        return None
    parent = df[df.get("post_id", pd.Series(dtype=str)).astype(str) == str(reply_to)]
    if parent.empty:
        return None
    parent_ts = parent.iloc[0].get("ts")
    if pd.isna(parent_ts):
        return None
    return round(float((comment_ts - parent_ts).total_seconds()), 1)


def _dynamic_budget(total: int, *, base: int, maximum: int, scale: int) -> int:
    if total <= 0:
        return 0
    return min(total, min(maximum, max(base, int(np.ceil(np.sqrt(total) * scale)))))


def _response_meta(total: int, budget: int) -> dict:
    returned = min(total, budget)
    return {"total": int(total), "returned": int(returned), "truncated": returned < total}


def _extract_coordination_users(posts: list[dict], comments: list[dict]) -> set[str]:
    coordinated: set[str] = set()
    for item in [*posts, *comments]:
        author_id = _clean_str(item.get("author_id") or item.get("user_id"))
        nested = item.get("coordination") if isinstance(item.get("coordination"), dict) else {}
        group_id = _clean_str(
            item.get("coordination_group_id")
            or item.get("group_id")
            or item.get("cluster_id")
            or nested.get("group_id")
            or nested.get("cluster_id")
        )
        flagged = item.get("is_coordinated") is True or nested.get("is_coordinated") is True
        if author_id and (group_id or flagged):
            coordinated.add(author_id)
    return coordinated


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
        node_id = _clean_str(row.get("author_id"))
        if not node_id:
            continue
        if node_id not in G:
            G.add_node(
                node_id,
                author_name=_clean_str(row.get("author_name")) or node_id,
                post_count=0,
                first_ts=str(row["ts"]),
            )
        G.nodes[node_id]["post_count"] = G.nodes[node_id].get("post_count", 0) + 1

    # --- 隐式边：共享对象（URL / 标签）时序关联 ---
    shared_objects: dict[str, list] = {}
    for _, row in df.iterrows():
        objs: list[str] = []
        for tag in _clean_list(row.get("hashtags")):
            tag_text = _clean_str(tag)
            if tag_text:
                objs.append(tag_text)
        url = _clean_str(row.get("url"))
        if url:
            objs.append(url)
        author_id = _clean_str(row.get("author_id"))
        if not author_id:
            continue
        for obj in objs:
            if obj not in shared_objects:
                shared_objects[obj] = []
            shared_objects[obj].append({
                "author_id": author_id,
                "post_id": _clean_str(row.get("post_id")),
                "platform": _clean_str(row.get("platform")),
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
                edge_id=_edge_id(src, dst, f"inferred:{obj_id}:{i}"),
                type="implicit",
                evidence_type="inferred",
                relation_type="shared_object_temporal_proximity",
                weight=1,
                object_id=obj_id,
                source_platform=_clean_str(predecessor.get("platform")),
                target_platform=_clean_str(follower.get("platform")),
                time_delta=round(time_delta, 1),
                source_content_ref=f"post:{predecessor['post_id']}" if predecessor.get("post_id") else "",
                target_content_ref=f"post:{follower['post_id']}" if follower.get("post_id") else "",
                confidence=round(_inferred_edge_confidence(time_delta), 4),
                is_observed=False,
            )

    # --- 显式边：评论回复关系 ---
    _add_explicit_edges(G, df, comments or [])

    # --- 分析 ---
    bc = _betweenness(G)
    coordination_users = _extract_coordination_users(posts, comments or [])
    key_roles = identify_key_roles(G, bc, coordination_users)

    claims_all = build_claims(shared_objects)
    timeline_all = build_timeline(df)

    evidence_all = _extract_evidence_chains(G, shared_objects, key_roles, bc, df)
    evidence_budget = _dynamic_budget(len(evidence_all), base=20, maximum=80, scale=4)
    evidence_chains = evidence_all[:evidence_budget]
    diffusion_summary = _build_diffusion_summary(
        G,
        evidence_chains,
        shared_objects,
        df,
        comments or [],
        node_limit=diffusion_node_limit,
    )
    path_analysis = _build_path_analysis(
        G,
        evidence_chains,
        diffusion_summary.get("all_node_layers", {}),
    )
    _enrich_role_evidence_and_stability(key_roles, G, evidence_chains, diffusion_summary.get("all_node_layers", {}))
    stability = _build_stability_summary(
        G,
        diffusion_summary.get("all_node_layers", {}),
        key_roles,
        (diffusion_summary.get("root_node") or {}).get("id", ""),
    )
    timeline_budget = _dynamic_budget(len(timeline_all), base=100, maximum=300, scale=20)
    claims_budget = _dynamic_budget(len(claims_all), base=20, maximum=100, scale=8)
    provenance_graph = _build_provenance_graph(posts, comments or [], shared_objects, G)

    # --- 序列化 ---
    nodes = []
    for n, attrs in G.nodes(data=True):
        nodes.append({"id": n, **{k: v for k, v in attrs.items()}})

    edges = []
    for u, v, key, d in G.edges(data=True, keys=True):
        edges.append({
            "source": u,
            "target": v,
            "weight": d.get("weight", 1),
            "type": d.get("type", "implicit"),
            "edge_id": d.get("edge_id") or _edge_id(u, v, key),
            "evidence_type": d.get("evidence_type", "inferred"),
            "relation_type": d.get("relation_type", "shared_object_temporal_proximity"),
            "source_content_ref": d.get("source_content_ref", ""),
            "target_content_ref": d.get("target_content_ref", ""),
            "object_id": d.get("object_id", ""),
            "time_delta": d.get("time_delta"),
            "confidence": d.get("confidence", 0.0),
            "is_observed": bool(d.get("is_observed", False)),
        })

    return {
        "graph": {
            "nodes": nodes,
            "edges": edges,
            "node_count": G.number_of_nodes(),
            "edge_count": G.number_of_edges(),
        },
        "key_roles": key_roles,
        "claims": claims_all[:claims_budget],
        "timeline": timeline_all[:timeline_budget],
        "evidence_chains": evidence_chains,
        "path_analysis": path_analysis,
        "diffusion_summary": diffusion_summary,
        "provenance_graph": provenance_graph,
        "stability": stability,
        "response_meta": {
            "claims": _response_meta(len(claims_all), claims_budget),
            "objects": _response_meta(len(claims_all), claims_budget),
            "timeline": _response_meta(len(timeline_all), timeline_budget),
            "evidence_chains": _response_meta(len(evidence_all), evidence_budget),
        },
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
        pid = _clean_str(row.get("post_id"))
        aid = _clean_str(row.get("author_id"))
        if pid and aid:
            post_author[pid] = aid

    # 也把评论自身加入查找表（支持评论回复评论）
    comment_author: dict[str, str] = {}
    comment_author_name: dict[str, str] = {}
    for c in comments:
        cid = _clean_str(c.get("comment_id"))
        aid = _clean_str(c.get("author_id"))
        if cid and aid:
            comment_author[cid] = aid
            comment_author_name[aid] = _clean_str(c.get("author_name")) or aid

    for c in comments:
        explicit_reply_to = _clean_str(c.get("reply_to"))
        reply_to = explicit_reply_to or _clean_str(c.get("parent_id")) or _clean_str(c.get("parent_comment_id"))
        if not reply_to:
            continue
        commenter = _clean_str(c.get("author_id"))
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
            G.add_node(
                commenter,
                author_name=_clean_str(c.get("author_name")) or commenter,
                post_count=0,
                first_ts="",
            )

        # 传播方向是“被回复内容的作者 -> 评论/回复者”，否则评论活跃用户会被误判成源头。
        evidence_type = "explicit" if explicit_reply_to else "reconstructed"
        G.add_edge(
            parent_author, commenter,
            edge_id=_edge_id(parent_author, commenter, f"{evidence_type}:{_clean_str(c.get('comment_id'))}"),
            type=evidence_type,
            evidence_type=evidence_type,
            relation_type="replies_to",
            weight=1,
            comment_id=_clean_str(c.get("comment_id")),
            comment_platform=_clean_str(c.get("platform")),
            source_content_ref=(
                f"post:{reply_to}" if reply_to in post_author else f"comment:{reply_to}"
            ),
            target_content_ref=f"comment:{_clean_str(c.get('comment_id'))}",
            object_id="",
            time_delta=_explicit_time_delta(c, df, reply_to),
            confidence=1.0 if evidence_type == "explicit" else 0.85,
            is_observed=evidence_type == "explicit",
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
        # weight=None on purpose. Collapsing the multigraph sums interaction
        # counts into `weight`, but betweenness_centrality treats `weight` as a
        # *distance*, so passing it would rank the busiest propagation routes as
        # the longest and drive their bridge nodes' centrality toward zero.
        # Hop-count also matches the exact branch above, where every multi-edge
        # has weight 1 and the shortest path is therefore hop-count anyway.
        return nx.betweenness_centrality(
            simple_G,
            k=sample_size,
            weight=None,
            seed=42,
        )
    except Exception:
        return {}


# ---------------------------------------------------------------------------
# Zhiview-style observed propagation summaries
# ---------------------------------------------------------------------------

def _build_path_analysis(
    G: nx.MultiDiGraph,
    evidence_chains: list[dict],
    node_layers: dict[str, int] | None = None,
) -> dict:
    """Summarize observed propagation paths and hierarchy from the graph."""
    edge_type_counts = Counter(
        d.get("type", "implicit") for _u, _v, _k, d in G.edges(data=True, keys=True)
    )
    layer_distribution = _build_layer_distribution(G, node_layers)
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
                "evidence_refs": [dict(ref) for ref in (path.get("evidence_refs") or [])],
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


def _build_layer_distribution(
    G: nx.MultiDiGraph,
    node_layers: dict[str, int] | None = None,
) -> list[dict]:
    if G.number_of_nodes() == 0:
        return []

    if node_layers is not None:
        return _layer_rows_from_mapping(node_layers, G.number_of_nodes())

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
        # Keep independent sources out of the primary tree. They remain
        # provenance metadata rather than implied connections to the root.
        if not starts_at_root:
            continue
        for index, node in enumerate(nodes):
            path_layer = min(index, DIFFUSION_MAX_DEPTH)
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
            if source_layer is None or target_layer is None or target_layer <= source_layer:
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
        and node_layers.get(edge["source"], -1) >= 0
        and node_layers.get(edge["target"], -1) > node_layers.get(edge["source"], -1)
    ]
    highlight_edges = [
        _diffusion_highlight_edge(simple_G, source, target)
        for source, target in key_edge_set
        if source in visible_node_ids and target in visible_node_ids
        and node_layers.get(source, -1) >= 0
        and node_layers.get(target, -1) > node_layers.get(source, -1)
    ]
    visible_node_rows = _apply_clustered_diffusion_layout(
        visible_node_rows,
        tree_edge_rows,
        shared_objects,
        root_id,
        simple_G,
    )

    all_node_layers = _diffusion_all_node_layers(simple_G, root_id)
    if is_full_view:
        visible_node_rows = [
            _diffusion_node_row(G, simple_G, node_id, all_node_layers.get(node_id, -1), key_node_set, root_id)
            for node_id in sorted(visible_nodes, key=lambda item: (all_node_layers.get(item, 999), str(item)))
        ]
        visible_node_rows = _apply_clustered_diffusion_layout(
            visible_node_rows, tree_edge_rows, shared_objects, root_id, simple_G
        )
    layers = _layer_rows_from_mapping(all_node_layers, simple_G.number_of_nodes())
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
            _diffusion_node_row(
                G,
                simple_G,
                node_id,
                all_node_layers.get(node_id, DIFFUSION_MAX_DEPTH),
                key_node_set,
                root_id,
            )
            for node_id in parallel_roots
        ],
        "visible_nodes": visible_node_rows,
        "tree_edges": tree_edge_rows,
        "highlight_edges": highlight_edges,
        "layers": layers,
        "detail_index": detail_index,
        "layout_relations": [
            {"source": root_id, "target": node_id, "relation_type": "parallel_root_layout"}
            for node_id in parallel_roots
            if node_id != root_id
        ],
        "all_node_layers": all_node_layers,
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
        "layout_relations": [],
        "all_node_layers": {},
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
                simple_G[u][v]["evidence_type"] = data.get("evidence_type", "explicit")
                simple_G[u][v]["relation_type"] = data.get("relation_type", "replies_to")
                simple_G[u][v]["confidence"] = data.get("confidence", 1.0)
                simple_G[u][v]["edge_id"] = data.get("edge_id", "")
            if not simple_G[u][v].get("object_id") and object_id:
                simple_G[u][v]["object_id"] = object_id
        else:
            simple_G.add_edge(
                u, v,
                weight=weight,
                type=edge_type,
                object_id=object_id,
                evidence_type=data.get("evidence_type", "inferred"),
                relation_type=data.get("relation_type", "shared_object_temporal_proximity"),
                confidence=data.get("confidence", 0.0),
                edge_id=data.get("edge_id", ""),
            )
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
    return _layer_rows_from_mapping(
        {str(node.get("id", "")): int(node.get("layer", -1) or -1) for node in visible_nodes},
        total_nodes,
    )


def _layer_rows_from_mapping(node_layers: dict[str, int], total_nodes: int) -> list[dict]:
    total = max(total_nodes, 1)
    counts = Counter(node_layers.values())
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


def _build_provenance_graph(
    posts: list[dict],
    comments: list[dict],
    shared_objects: dict[str, list],
    G: nx.MultiDiGraph,
) -> dict:
    """Build an auditable entity graph; the user graph remains a projection."""
    event_value = next(
        (_clean_str(item.get("event_id")) for item in [*posts, *comments] if _clean_str(item.get("event_id"))),
        "current_event",
    )
    event_id = _entity_id("event", event_value)
    nodes: dict[str, dict] = {event_id: {"entity_id": event_id, "entity_type": "event", "raw_id": event_value}}
    relations: list[dict] = []

    def add_node(entity_type: str, raw_id: str, **attrs) -> str:
        if not raw_id:
            return ""
        entity_id = _entity_id(entity_type, raw_id)
        nodes.setdefault(entity_id, {"entity_id": entity_id, "entity_type": entity_type, "raw_id": raw_id, **attrs})
        return entity_id

    def add_relation(source: str, target: str, relation_type: str, **attrs) -> None:
        if not source or not target or source not in nodes or target not in nodes:
            return
        relation_id = f"relation:{len(relations)}:{relation_type}"
        relations.append({"relation_id": relation_id, "source": source, "target": target, "relation_type": relation_type, **attrs})

    for post in posts:
        author_id = _clean_str(post.get("author_id"))
        post_id = _clean_str(post.get("post_id"))
        user_entity = add_node("user", author_id, author_name=_clean_str(post.get("author_name")) or author_id)
        post_entity = add_node("post", post_id)
        add_relation(event_id, post_entity, "contains")
        add_relation(user_entity, post_entity, "authored")
        objects = [_clean_str(post.get("url")), *[_clean_str(tag) for tag in _clean_list(post.get("hashtags"))]]
        for object_id in filter(None, objects):
            object_entity = add_node("object", object_id)
            add_relation(post_entity, object_entity, "references")

    for comment in comments:
        author_id = _clean_str(comment.get("author_id"))
        comment_id = _clean_str(comment.get("comment_id"))
        reply_to = (
            _clean_str(comment.get("reply_to"))
            or _clean_str(comment.get("parent_id"))
            or _clean_str(comment.get("parent_comment_id"))
        )
        user_entity = add_node("user", author_id, author_name=_clean_str(comment.get("author_name")) or author_id)
        comment_entity = add_node("comment", comment_id)
        add_relation(event_id, comment_entity, "contains")
        add_relation(user_entity, comment_entity, "authored")
        if reply_to:
            target_type = "post" if _entity_id("post", reply_to) in nodes else "comment"
            target_entity = add_node(target_type, reply_to, referenced_only=True)
            add_relation(comment_entity, target_entity, "replies_to")

    for source, target, key, data in G.edges(data=True, keys=True):
        source_entity = add_node("user", _clean_str(source), author_name=G.nodes[source].get("author_name", source))
        target_entity = add_node("user", _clean_str(target), author_name=G.nodes[target].get("author_name", target))
        add_relation(
            source_entity,
            target_entity,
            data.get("relation_type", "propagation_relation"),
            edge_id=data.get("edge_id") or _edge_id(source, target, key),
            evidence_type=data.get("evidence_type", "inferred"),
            is_observed=bool(data.get("is_observed", False)),
        )
    return {"nodes": list(nodes.values()), "relations": relations}


def _build_stability_summary(
    G: nx.MultiDiGraph,
    node_layers: dict[str, int],
    key_roles: dict,
    root_id: str,
) -> dict:
    total_edges = max(G.number_of_edges(), 1)
    confident_edges = sum(
        1 for _u, _v, _k, data in G.edges(data=True, keys=True)
        if float(data.get("confidence", 0.0) or 0.0) >= 0.5
    )
    ranked = [
        row["account_id"]
        for rows in key_roles.values()
        for row in rows
    ]
    unique_ranked = sorted(set(ranked))
    max_degree = max((G.degree(node) for node in G.nodes()), default=0)
    baseline_reachable = _reachable_count(G, root_id, min_confidence=0.0)
    retained_reachable = _reachable_count(G, root_id, min_confidence=0.5)
    sensitivity_rows = []
    for node_id in unique_ranked[:10]:
        without_node = G.copy()
        without_node.remove_node(node_id)
        removed_root = node_id == root_id
        evaluation_root = root_id
        if removed_root:
            evaluation_root = _select_diffusion_root(_to_weighted_digraph(without_node), without_node)
        reachable = _reachable_count(without_node, evaluation_root, min_confidence=0.0)
        sensitivity_rows.append({
            "account_id": node_id,
            "reachable_delta": baseline_reachable - reachable,
            "removed_root": removed_root,
            "evaluation_root_id": evaluation_root,
        })
    return {
        "edge_confidence_threshold": {
            "threshold": 0.5,
            "retained_edge_ratio": round(confident_edges / total_edges, 4),
            "retained_edges": confident_edges,
            "reachable_delta": baseline_reachable - retained_reachable,
        },
        "remove_node_sensitivity": {
            "evaluated_nodes": unique_ranked[:10],
            "max_degree": int(max_degree),
            "ranking_scope": "current_role_leaderboards",
            "effects": sensitivity_rows,
        },
        "prefix_window": {
            "window_fractions": [0.5, 0.75, 1.0],
            "final_layer_count": len(set(node_layers.values())),
            "method": "timestamped_node_induced_prefix",
            "root_id": root_id,
            "windows": _prefix_stability_windows(G, root_id, (0.5, 0.75, 1.0)),
        },
    }


def _reachable_count(G: nx.MultiDiGraph, root_id: str, min_confidence: float) -> int:
    if not root_id or not G.has_node(root_id):
        return 0
    graph = nx.DiGraph()
    graph.add_nodes_from(G.nodes())
    for source, target, _key, data in G.edges(data=True, keys=True):
        if float(data.get("confidence", 0.0) or 0.0) >= min_confidence:
            graph.add_edge(source, target)
    return len(nx.descendants(graph, root_id)) + 1


def _prefix_stability_windows(
    G: nx.MultiDiGraph,
    root_id: str,
    fractions: tuple[float, ...],
) -> list[dict]:
    timestamped_nodes = []
    for node_id, attrs in G.nodes(data=True):
        timestamp = pd.to_datetime(attrs.get("first_ts"), errors="coerce", utc=True)
        if not pd.isna(timestamp):
            timestamped_nodes.append((node_id, timestamp))
    timestamped_nodes.sort(key=lambda item: (item[1], str(item[0])))
    if not timestamped_nodes:
        return []

    windows = []
    for fraction in fractions:
        count = min(len(timestamped_nodes), max(1, int(np.ceil(len(timestamped_nodes) * fraction))))
        included = {node_id for node_id, _timestamp in timestamped_nodes[:count]}
        prefix_graph = G.subgraph(included).copy()
        evaluation_root = root_id if root_id in included else ""
        if not evaluation_root:
            evaluation_root = _select_diffusion_root(_to_weighted_digraph(prefix_graph), prefix_graph)
        windows.append({
            "fraction": float(fraction),
            "node_count": prefix_graph.number_of_nodes(),
            "edge_count": prefix_graph.number_of_edges(),
            "root_present": bool(root_id and root_id in included),
            "evaluation_root_id": evaluation_root,
            "reachable_count": _reachable_count(prefix_graph, evaluation_root, min_confidence=0.0),
        })
    return windows


def _enrich_role_evidence_and_stability(
    key_roles: dict,
    G: nx.MultiDiGraph,
    evidence_chains: list[dict],
    node_layers: dict[str, int],
) -> None:
    for role_rows in key_roles.values():
        for row in role_rows:
            account_id = row.get("account_id", "")
            refs = []
            for chain in evidence_chains:
                for post in chain.get("supporting_posts", []):
                    if post.get("author_id") == account_id:
                        refs.append({"post_id": post.get("post_id", ""), "object_id": chain.get("claim_id", "")})
            row["evidence_refs"] = refs[:8]
            row["stability"] = {
                "layer": node_layers.get(account_id, -1),
                "edge_confidence_ratio": round(
                    sum(
                        float(data.get("confidence", 0.0) or 0.0)
                        for _source, _target, _key, data in G.in_edges(account_id, data=True, keys=True)
                    ) / max(G.in_degree(account_id), 1),
                    4,
                ),
            }


def _build_post_index(df: pd.DataFrame) -> dict[str, list[dict]]:
    post_index: dict[str, list[dict]] = {}
    for _, row in df.iterrows():
        author_id = _clean_str(row.get("author_id"))
        if not author_id:
            continue
        post_index.setdefault(author_id, []).append({
            "post_id": _clean_str(row.get("post_id")),
            "author_id": author_id,
            "author_name": _clean_str(row.get("author_name")) or author_id,
            "timestamp": str(row.get("ts", "")),
            "content": _clean_str(row.get("content"))[:180],
            "url": _clean_str(row.get("url")),
        })
    return post_index


def _build_comment_index(comments: list[dict]) -> dict[str, list[dict]]:
    comment_index: dict[str, list[dict]] = {}
    for comment in comments:
        author_id = _clean_str(comment.get("author_id"))
        if not author_id:
            continue
        comment_index.setdefault(author_id, []).append({
            "comment_id": _clean_str(comment.get("comment_id")),
            "post_id": _clean_str(comment.get("post_id")),
            "author_id": author_id,
            "author_name": _clean_str(comment.get("author_name")) or author_id,
            "timestamp": str(comment.get("timestamp", "")),
            "content": _clean_str(comment.get("content"))[:180],
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
    )

    # 构建角色查找集合
    originator_set = {r["account_id"] for r in key_roles.get("originators", [])}
    bridge_set = {r["account_id"] for r in key_roles.get("bridges", [])}
    amplifier_set = {r["account_id"] for r in key_roles.get("amplifiers", [])}

    # post_id → row 查找
    post_lookup: dict[str, dict] = {}
    for _, row in df.iterrows():
        pid = _clean_str(row.get("post_id"))
        if pid:
            post_lookup[pid] = {
                "post_id": pid,
                "author_id": _clean_str(row.get("author_id")),
                "timestamp": str(row["ts"]),
                "content": _clean_str(row.get("content"))[:100],
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
            evidence_refs = _collect_path_evidence_refs(path_edges)

            all_paths.append({
                "nodes": path_nodes,
                "edges": path_edges,
                "score": score,
                "explanation": explanation,
                "confidence": confidence,
                "evidence_refs": evidence_refs,
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
        p["path_id"] = f"claim-{_claim_path_prefix(claim_obj_id)}-{i}"

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
        "provenance_graph": {"nodes": [], "relations": []},
        "stability": {
            "edge_confidence_threshold": {"threshold": 0.5, "retained_edge_ratio": 0.0, "retained_edges": 0},
            "remove_node_sensitivity": {"evaluated_nodes": [], "max_degree": 0, "ranking_scope": "current_role_leaderboards", "effects": []},
            "prefix_window": {"window_fractions": [0.5, 0.75, 1.0], "final_layer_count": 0, "method": "deterministic_observed_prefix_summary", "root_id": ""},
        },
        "response_meta": {
            "claims": _response_meta(0, 0),
            "timeline": _response_meta(0, 0),
            "evidence_chains": _response_meta(0, 0),
        },
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
    }
