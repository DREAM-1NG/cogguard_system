"""传播归因分析模块。

基于帖子的时序关系构建传播子图，识别关键角色，提取证据链与关键路径：
- 起爆节点（最早发布者）
- 桥接节点（连接不同群体）
- 扩散节点（高转发量）
- 证据链（claim 级传播路径 + 关键角色 + 支撑帖子）
"""

from __future__ import annotations

from itertools import islice

import networkx as nx
import numpy as np
import pandas as pd


# ---------------------------------------------------------------------------
# Public entry
# ---------------------------------------------------------------------------

def build_propagation_graph(
    posts: list[dict],
    comments: list[dict] | None = None,
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
    key_roles = _identify_key_roles(G, bc)

    claims = _build_claims(shared_objects)
    timeline = _build_timeline(df)

    evidence_chains = _extract_evidence_chains(G, shared_objects, key_roles, bc, df)

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
    for c in comments:
        cid = str(c.get("comment_id", ""))
        aid = str(c.get("author_id", ""))
        if cid and aid:
            comment_author[cid] = aid

    for c in comments:
        reply_to = str(c.get("reply_to", "") or "")
        if not reply_to:
            continue
        src = str(c.get("author_id", ""))
        if not src:
            continue

        # reply_to 可能指向帖子或评论
        dst = post_author.get(reply_to) or comment_author.get(reply_to)
        if not dst or src == dst:
            continue

        # 确保节点存在
        if src not in G:
            G.add_node(src, author_name=c.get("author_name", src), post_count=0, first_ts="")
        if dst not in G:
            G.add_node(dst, author_name="", post_count=0, first_ts="")

        G.add_edge(
            src, dst,
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
        return nx.betweenness_centrality(G, weight="weight")
    except Exception:
        return {}


# ---------------------------------------------------------------------------
# Key roles
# ---------------------------------------------------------------------------

def _identify_key_roles(G: nx.MultiDiGraph, bc: dict[str, float]) -> dict:
    """识别传播网络中的关键角色。"""
    if G.number_of_nodes() == 0:
        return {"originators": [], "bridges": [], "amplifiers": []}

    # 起爆节点：出度高、入度低
    originators = []
    for n in G.nodes():
        out_d = G.out_degree(n)
        in_d = G.in_degree(n)
        if out_d > 0 and out_d >= in_d:
            originators.append({
                "account_id": n,
                "out_degree": out_d,
                "in_degree": in_d,
                "author_name": G.nodes[n].get("author_name", n),
            })
    originators.sort(key=lambda x: x["out_degree"], reverse=True)

    # 桥接节点：介数中心性高
    bridges = []
    for n, score in sorted(bc.items(), key=lambda x: x[1], reverse=True)[:10]:
        if score > 0:
            bridges.append({
                "account_id": n,
                "betweenness": round(score, 4),
                "author_name": G.nodes[n].get("author_name", n),
            })

    # 扩散节点：入度最高
    amplifiers = []
    for n in G.nodes():
        in_d = G.in_degree(n)
        if in_d > 0:
            amplifiers.append({
                "account_id": n,
                "in_degree": in_d,
                "author_name": G.nodes[n].get("author_name", n),
            })
    amplifiers.sort(key=lambda x: x["in_degree"], reverse=True)

    return {
        "originators": originators[:10],
        "bridges": bridges[:10],
        "amplifiers": amplifiers[:10],
    }


# ---------------------------------------------------------------------------
# Claims & timeline (unchanged logic, extracted for clarity)
# ---------------------------------------------------------------------------

def _build_claims(shared_objects: dict[str, list]) -> list[dict]:
    claims = []
    for obj_id, shares in sorted(
        shared_objects.items(), key=lambda x: len(x[1]), reverse=True
    )[:20]:
        accounts = list({s["author_id"] for s in shares})
        claims.append({
            "object_id": obj_id,
            "share_count": len(shares),
            "account_count": len(accounts),
            "first_share": str(shares[0]["ts"]) if shares else "",
        })
    return claims


def _build_timeline(df: pd.DataFrame) -> list[dict]:
    timeline = []
    for _, row in df.head(100).iterrows():
        timeline.append({
            "post_id": str(row.get("post_id", "")),
            "author_id": str(row.get("author_id", "")),
            "author_name": row.get("author_name", ""),
            "timestamp": str(row["ts"]),
            "content": str(row.get("content", ""))[:100],
        })
    return timeline


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
    }
