from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Dict, List, Optional, Set

import networkx as nx
import numpy as np
import pandas as pd

from .models import PropagationEvent, sorted_nodes_by_time
from .protocol import CoordinationScope


_ROLE_EVIDENCE_COLUMNS = [
    "event_id",
    "user_id",
    "coord_group_id",
    "is_coordinated",
    "role",
    "evidence_summary",
    "node_ids",
    "evidence_paths",
    "first_evidence_node",
    "first_seen",
    "out_degree_sum",
    "betweenness_sum",
    "pagerank_sum",
    "post_count",
]


def analyze_events(
    events: List[PropagationEvent],
    output_dir: str,
    focus_event_id: Optional[str] = None,
    coordination: Optional[CoordinationScope] = None,
) -> Dict:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    summaries = [summarize_event(event) for event in events]
    participants = pd.concat([participant_table(event, coordination) for event in events], ignore_index=True) if events else pd.DataFrame()
    ignitions = pd.concat([ignition_points(event) for event in events], ignore_index=True) if events else pd.DataFrame()
    paths = {event.event_id: key_paths(event) for event in events}
    role_evidence = pd.concat([role_evidence_table(event, coordination) for event in events], ignore_index=True) if events else pd.DataFrame()
    role_quality = role_evidence_quality(role_evidence, participants, coordination)
    focus_event = _pick_focus_event(events, focus_event_id)

    summary = {
        "dataset_events": len(events),
        "focus_event_id": focus_event.event_id if focus_event else None,
        "totals": {
            "nodes": int(sum(s["node_count"] for s in summaries)),
            "edges": int(sum(s["edge_count"] for s in summaries)),
            "participants": int(participants["user_id"].nunique()) if not participants.empty else 0,
        },
        "event_summaries": summaries,
        "role_evidence_quality": role_quality,
        "narrative": build_narrative(summaries, ignitions),
    }

    (out / "analysis_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    participants.to_csv(out / "participants.csv", index=False)
    ignitions.to_csv(out / "ignition_points.csv", index=False)
    role_evidence.to_csv(out / "role_evidence.csv", index=False)
    (out / "role_evidence_quality.json").write_text(json.dumps(role_quality, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    (out / "paths.json").write_text(json.dumps(paths, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    write_event_report(out / "event_report.md", focus_event, summaries, participants, ignitions, paths)
    return summary


def summarize_event(event: PropagationEvent) -> Dict:
    graph = event.to_graph()
    node_count = graph.number_of_nodes()
    edge_count = graph.number_of_edges()
    depths = _depths(graph)
    width_by_depth = Counter(depths.values())
    timestamps = [d.get("timestamp") for _, d in graph.nodes(data=True) if d.get("timestamp")]
    duration_minutes = 0.0
    if timestamps:
        duration_minutes = (max(timestamps) - min(timestamps)).total_seconds() / 60.0
    out_degrees = dict(graph.out_degree())
    top_spreaders = sorted(out_degrees.items(), key=lambda item: item[1], reverse=True)[:5]
    avg_branching = float(np.mean(list(out_degrees.values()))) if out_degrees else 0.0
    leaf_ratio = sum(1 for _, deg in graph.out_degree() if deg == 0) / max(node_count, 1)
    source = _source_node(event)
    return {
        "event_id": event.event_id,
        "label": event.label,
        "topic": event.metadata.get("topic"),
        "claim": event.metadata.get("claim"),
        "source_node": source.node_id if source else None,
        "source_user": source.user_id if source else None,
        "source_text": _clean_text(source.text, 220) if source else "",
        "node_count": node_count,
        "edge_count": edge_count,
        "participant_count": len({n.user_id for n in event.nodes.values()}),
        "max_depth": max(depths.values(), default=0),
        "max_width": max(width_by_depth.values(), default=node_count),
        "avg_branching": avg_branching,
        "leaf_ratio": leaf_ratio,
        "duration_minutes": duration_minutes,
        "top_spreaders": [{"node_id": node_id, "out_degree": int(degree)} for node_id, degree in top_spreaders],
    }


def participant_table(event: PropagationEvent, coordination: Optional[CoordinationScope] = None) -> pd.DataFrame:
    graph = event.to_graph()
    coord_users = coordination.users if coordination else set()
    coord_groups = coordination.groups if coordination else {}
    pagerank = _influence_scores(graph)
    undirected = graph.to_undirected()
    betweenness = nx.betweenness_centrality(undirected) if graph.number_of_nodes() < 2000 else {n: 0 for n in graph.nodes}
    rows = []
    by_user = defaultdict(list)
    for node_id, data in graph.nodes(data=True):
        by_user[data.get("user_id", node_id)].append(node_id)
    depths = _depths(graph)
    for user_id, node_ids in by_user.items():
        times = [graph.nodes[n].get("timestamp") for n in node_ids if graph.nodes[n].get("timestamp")]
        participant = event.participants.get(user_id)
        out_degree_sum = sum(graph.out_degree(n) for n in node_ids)
        in_degree_sum = sum(graph.in_degree(n) for n in node_ids)
        betweenness_sum = sum(betweenness.get(n, 0.0) for n in node_ids)
        min_depth = min((depths.get(n, 0) for n in node_ids), default=0)
        rows.append(
            {
                "event_id": event.event_id,
                "user_id": user_id,
                "screen_name": participant.screen_name if participant else None,
                "followers_count": participant.followers_count if participant else None,
                "verified": participant.verified if participant else None,
                "is_coordinated": user_id in coord_users or user_id in coord_groups,
                "coord_group_id": coord_groups.get(user_id),
                "post_count": len(node_ids),
                "first_seen": min(times) if times else None,
                "out_degree_sum": out_degree_sum,
                "in_degree_sum": in_degree_sum,
                "min_depth": min_depth,
                "pagerank_sum": sum(pagerank.get(n, 0.0) for n in node_ids),
                "betweenness_sum": betweenness_sum,
                "role": _participant_role(out_degree_sum, betweenness_sum, in_degree_sum, min_depth),
            }
        )
    return pd.DataFrame(rows)


def role_evidence_table(event: PropagationEvent, coordination: Optional[CoordinationScope] = None, limit: int = 50) -> pd.DataFrame:
    """Return role labels with auditable graph evidence for coordinated users.

    If no coordination scope is supplied, the table falls back to the top structural
    participants so existing demos still produce an inspectable artifact.
    """

    participants = participant_table(event, coordination)
    if participants.empty:
        return pd.DataFrame(columns=_ROLE_EVIDENCE_COLUMNS)
    if coordination and (coordination.users or coordination.groups):
        participants = participants[participants["is_coordinated"] == True]  # noqa: E712
    sort_cols = [col for col in ["pagerank_sum", "betweenness_sum", "out_degree_sum", "post_count"] if col in participants.columns]
    if sort_cols:
        participants = participants.sort_values(sort_cols, ascending=False)
    graph = event.to_graph()
    depths = _depths(graph)
    paths = key_paths(event, limit=30)
    rows = []
    for _, row in participants.head(limit).iterrows():
        user_id = str(row["user_id"])
        node_ids = [node for node, data in graph.nodes(data=True) if str(data.get("user_id")) == user_id]
        evidence_paths = _paths_touching_nodes(paths, set(node_ids), max_paths=3)
        first_node = min(node_ids, key=lambda node: (depths.get(node, 0), node), default=None)
        rows.append(
            {
                "event_id": event.event_id,
                "user_id": user_id,
                "coord_group_id": row.get("coord_group_id"),
                "is_coordinated": bool(row.get("is_coordinated", False)),
                "role": row.get("role"),
                "evidence_summary": _role_evidence_summary(row, node_ids, evidence_paths),
                "node_ids": node_ids,
                "evidence_paths": evidence_paths,
                "first_evidence_node": first_node,
                "first_seen": row.get("first_seen"),
                "out_degree_sum": int(row.get("out_degree_sum", 0)),
                "betweenness_sum": float(row.get("betweenness_sum", 0.0)),
                "pagerank_sum": float(row.get("pagerank_sum", 0.0)),
                "post_count": int(row.get("post_count", 0)),
            }
        )
    return pd.DataFrame(rows, columns=_ROLE_EVIDENCE_COLUMNS)


def role_evidence_quality(
    role_evidence: pd.DataFrame,
    participants: pd.DataFrame,
    coordination: Optional[CoordinationScope] = None,
) -> Dict:
    """Summarize coverage and stability of the rule-based role evidence output."""

    coordinated_users = set(coordination.users) | set(coordination.groups) if coordination else set()
    evidence_users = set(role_evidence["user_id"].astype(str)) if not role_evidence.empty and "user_id" in role_evidence else set()
    participant_users = set(participants["user_id"].astype(str)) if not participants.empty and "user_id" in participants else set()
    target_users = coordinated_users or participant_users

    path_rows = 0
    if not role_evidence.empty and "evidence_paths" in role_evidence:
        path_rows = sum(1 for value in role_evidence["evidence_paths"] if _has_evidence_path(value))

    stability = _role_stability(role_evidence)
    return {
        "scope": "coordinated_users" if coordinated_users else "structural_sample",
        "target_user_count": len(target_users),
        "evidence_user_count": len(evidence_users),
        "coordination_user_coverage": len(evidence_users & target_users) / max(len(target_users), 1),
        "path_complete_rate": path_rows / max(len(role_evidence), 1),
        "role_stability": stability,
        "manual_review_required": True,
        "note": (
            "Role evidence is an observed-graph explanation. Coverage/stability metrics "
            "support review, but do not turn rule labels into supervised ground truth."
        ),
    }


def ignition_points(event: PropagationEvent, bins: int = 12) -> pd.DataFrame:
    graph = event.to_graph()
    nodes = sorted_nodes_by_time(event)
    if len(nodes) < 3:
        return pd.DataFrame(columns=["event_id", "node_id", "user_id", "timestamp", "reason", "score"])
    times = [n.timestamp for n in nodes if n.timestamp]
    if not times:
        return pd.DataFrame()
    start, end = min(times), max(times)
    total_seconds = max((end - start).total_seconds(), 1.0)
    bucket_size = max(total_seconds / bins, 1.0)
    bucket_nodes = defaultdict(list)
    for n in nodes:
        idx = int(((n.timestamp - start).total_seconds() if n.timestamp else 0) // bucket_size)
        bucket_nodes[min(idx, bins - 1)].append(n)
    counts = np.array([len(bucket_nodes[i]) for i in range(bins)], dtype=float)
    mean, std = counts.mean(), counts.std() or 1.0
    pagerank = _influence_scores(graph)
    rows = []
    for idx, count in enumerate(counts):
        z = (count - mean) / std
        if z < 1.0 and count < max(counts):
            continue
        candidates = bucket_nodes[idx]
        for node in sorted(candidates, key=lambda n: graph.out_degree(n.node_id) + pagerank.get(n.node_id, 0), reverse=True)[:3]:
            score = float(z + graph.out_degree(node.node_id) + pagerank.get(node.node_id, 0.0))
            rows.append(
                {
                    "event_id": event.event_id,
                    "node_id": node.node_id,
                    "user_id": node.user_id,
                    "timestamp": node.timestamp,
                    "reason": "time-window growth spike + structural influence",
                    "score": score,
                }
            )
    return pd.DataFrame(rows)


def key_paths(event: PropagationEvent, limit: int = 10) -> List[Dict]:
    graph = event.to_graph()
    leaves = [n for n, deg in graph.out_degree() if deg == 0]
    paths = []
    depths = _depths(graph)
    for leaf in sorted(leaves, key=lambda node: depths.get(node, 0), reverse=True)[: max(limit * 20, limit)]:
        path = [leaf]
        current = leaf
        seen = {leaf}
        while True:
            parents = list(graph.predecessors(current))
            if not parents:
                break
            current = max(parents, key=lambda node: depths.get(node, 0))
            if current in seen:
                break
            path.append(current)
            seen.add(current)
        path = list(reversed(path))
        paths.append({"length": len(path) - 1, "nodes": path})
    return sorted(paths, key=lambda p: p["length"], reverse=True)[:limit]


def build_narrative(summaries: List[Dict], ignitions: pd.DataFrame) -> str:
    if not summaries:
        return "未发现可分析事件。"
    largest = max(summaries, key=lambda s: s["node_count"])
    deepest = max(summaries, key=lambda s: s["max_depth"])
    ignition_count = 0 if ignitions is None or ignitions.empty else len(ignitions)
    return (
        f"共分析 {len(summaries)} 个事件，最大事件为 {largest['event_id']}，规模 {largest['node_count']} 个节点；"
        f"最深传播链来自 {deepest['event_id']}，深度 {deepest['max_depth']}。"
        f"系统识别出 {ignition_count} 个潜在引爆点，主要依据为时间窗口增量异常和节点结构影响力。"
    )


def write_event_report(
    path: Path,
    event: Optional[PropagationEvent],
    summaries: List[Dict],
    participants: pd.DataFrame,
    ignitions: pd.DataFrame,
    paths: Dict[str, List[Dict]],
) -> None:
    if not event:
        path.write_text("# 具体事件总结\n\n未发现可分析事件。\n", encoding="utf-8")
        return
    summary = next((s for s in summaries if s["event_id"] == event.event_id), summarize_event(event))
    event_participants = participants[participants["event_id"] == event.event_id] if not participants.empty else pd.DataFrame()
    event_ignitions = ignitions[ignitions["event_id"] == event.event_id] if not ignitions.empty else pd.DataFrame()
    event_paths = paths.get(event.event_id, [])

    lines = [
        "# 具体事件总结",
        "",
        f"- 事件 ID：`{event.event_id}`",
        f"- 标签：{event.label or '未知'}",
    ]
    if summary.get("topic"):
        lines.append(f"- 主题：{summary['topic']}")
    if summary.get("claim"):
        lines.append(f"- 事件说法：{summary['claim']}")
    if summary.get("source_text"):
        lines.append(f"- 源帖摘要：{summary['source_text']}")
    data_notes = _data_quality_notes(event)
    if data_notes:
        lines += ["", "## 数据说明", ""]
        lines.extend(f"- {note}" for note in data_notes)

    lines += [
        "",
        "## 传播分析",
        "",
        f"该事件包含 {summary['node_count']} 个传播节点、{summary['edge_count']} 条可恢复传播边，"
        f"涉及 {summary['participant_count']} 个参与者。传播树最大深度为 {summary['max_depth']}，"
        f"最大宽度为 {summary['max_width']}，叶子节点占比 {summary['leaf_ratio']:.2%}，"
        f"持续时间约 {summary['duration_minutes']:.1f} 分钟。",
        "",
        "## 传播路径",
        "",
    ]
    if event_paths:
        for idx, row in enumerate(event_paths[:10], 1):
            lines.append(f"{idx}. 长度 {row['length']}：" + " -> ".join(map(str, row["nodes"])))
    else:
        lines.append("未恢复出多跳传播路径；该事件可能是星型扩散，或原始数据缺少父子关系。")

    lines += ["", "## 参与者信息", ""]
    if not event_participants.empty:
        top = event_participants.sort_values(["pagerank_sum", "out_degree_sum", "post_count"], ascending=False).head(10)
        for _, row in top.iterrows():
            name = f"（{row['screen_name']}）" if pd.notna(row.get("screen_name")) and row.get("screen_name") else ""
            followers = ""
            if pd.notna(row.get("followers_count")):
                followers = f"，粉丝 {int(row['followers_count'])}"
            lines.append(
                f"- 用户 `{row['user_id']}`{name}：角色 {row['role']}，发帖 {int(row['post_count'])}，"
                f"出度贡献 {int(row['out_degree_sum'])}{followers}。"
            )
    else:
        lines.append("未提取到参与者画像。")

    lines += ["", "## 引爆点", ""]
    if not event_ignitions.empty:
        for _, row in event_ignitions.sort_values("score", ascending=False).head(10).iterrows():
            lines.append(
                f"- 节点 `{row['node_id']}` / 用户 `{row['user_id']}`：分数 {row['score']:.2f}，"
                f"时间 {row['timestamp']}，原因：{row['reason']}。"
            )
    else:
        lines.append("未检测到显著增长突变窗口；该事件可能传播较平缓或缺少可靠时间戳。")

    lines += ["", "## 结论", ""]
    conclusion = (
        f"该事件的传播形态以{'多层链式扩散' if summary['max_depth'] >= 3 else '浅层扩散'}为主，"
        f"{'存在明显关键节点放大效应' if not event_ignitions.empty else '暂未发现明确引爆节点'}。"
        f"从参与者结构看，TOP 用户承担了主要扩散或桥接作用，可作为后续谣言溯源、辟谣触达和传播预测的重点对象。"
    )
    lines.append(conclusion)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _depths(graph: nx.DiGraph) -> Dict[str, int]:
    roots = [n for n, deg in graph.in_degree() if deg == 0]
    depths: Dict[str, int] = {}
    for root in roots:
        for node, depth in nx.single_source_shortest_path_length(graph, root).items():
            depths[node] = min(depths.get(node, depth), depth)
    for node in graph.nodes:
        depths.setdefault(node, 0)
    return depths


def _participant_role(out_degree: int, betweenness: float, in_degree: int = 0, min_depth: int = 0) -> str:
    if out_degree > 0 and (min_depth == 0 or in_degree == 0):
        return "起爆/源头"
    if betweenness > 0.05:
        return "桥接"
    if out_degree >= 5:
        return "放大"
    if out_degree > 0:
        return "二级扩散"
    return "普通参与者"


def _influence_scores(graph: nx.DiGraph, exact_limit: int = 5000) -> Dict[str, float]:
    if not graph.number_of_nodes():
        return {}
    if graph.number_of_nodes() <= exact_limit:
        return nx.pagerank(graph)
    total = sum(deg for _, deg in graph.out_degree()) or 1
    return {node: graph.out_degree(node) / total for node in graph.nodes}


def _paths_touching_nodes(paths: List[Dict], node_ids: Set[str], max_paths: int) -> List[List[str]]:
    if not node_ids:
        return []
    matches: List[List[str]] = []
    for row in paths:
        path_nodes = [str(node) for node in row.get("nodes", [])]
        if node_ids.intersection(path_nodes):
            matches.append(path_nodes)
        if len(matches) >= max_paths:
            break
    return matches


def _has_evidence_path(value) -> bool:
    if isinstance(value, list):
        return bool(value)
    if value is None:
        return False
    if isinstance(value, float) and pd.isna(value):
        return False
    text = str(value).strip()
    return text not in {"", "[]", "nan", "None"}


def _role_stability(role_evidence: pd.DataFrame) -> Dict:
    if role_evidence.empty or not {"user_id", "role"}.issubset(role_evidence.columns):
        return {
            "multi_event_user_count": 0,
            "stable_user_count": 0,
            "stable_user_rate": 0.0,
            "mean_dominant_role_share": 0.0,
        }

    multi_event = 0
    stable = 0
    shares = []
    for _, rows in role_evidence.groupby("user_id"):
        observation_count = rows["event_id"].nunique() if "event_id" in rows else len(rows)
        if observation_count < 2:
            continue
        multi_event += 1
        counts = rows["role"].value_counts()
        dominant_share = float(counts.iloc[0] / max(counts.sum(), 1))
        shares.append(dominant_share)
        if dominant_share >= 0.6:
            stable += 1
    return {
        "multi_event_user_count": multi_event,
        "stable_user_count": stable,
        "stable_user_rate": stable / max(multi_event, 1),
        "mean_dominant_role_share": float(np.mean(shares)) if shares else 0.0,
    }


def _role_evidence_summary(row: pd.Series, node_ids: List[str], evidence_paths: List[List[str]]) -> str:
    role = row.get("role") or "unknown"
    out_degree = int(row.get("out_degree_sum", 0))
    post_count = int(row.get("post_count", 0))
    betweenness = float(row.get("betweenness_sum", 0.0))
    path_count = len(evidence_paths)
    return (
        f"角色 {role} 基于 {post_count} 条观测帖、{out_degree} 条出边贡献、"
        f"介数中心性 {betweenness:.4f} 判定；"
        f"证据覆盖 {len(node_ids)} 个节点、{path_count} 条关键传播路径。"
    )


def _pick_focus_event(events: List[PropagationEvent], event_id: Optional[str]) -> Optional[PropagationEvent]:
    if not events:
        return None
    if event_id:
        for event in events:
            if event.event_id == event_id:
                return event
    return max(events, key=lambda e: len(e.nodes))


def _source_node(event: PropagationEvent):
    graph = event.to_graph()
    roots = [event.nodes[n] for n, deg in graph.in_degree() if deg == 0 and n in event.nodes]
    if roots:
        return min(roots, key=lambda n: (n.timestamp is None, n.timestamp, n.node_id))
    nodes = list(event.nodes.values())
    return min(nodes, key=lambda n: (n.timestamp is None, n.timestamp, n.node_id), default=None)


def _clean_text(value: str, limit: int) -> str:
    text = " ".join(str(value or "").split())
    if len(text) <= limit:
        return text
    return text[: limit - 3] + "..."


def _data_quality_notes(event: PropagationEvent) -> List[str]:
    notes = []
    source_format = event.metadata.get("source_format")
    if source_format:
        notes.append(f"数据格式：{source_format}。")
    if event.metadata.get("real_user_profile_available") is False:
        notes.append("该数据源不包含真实用户画像，参与者 ID 为本地结构占位，适合验证传播结构分析，不适合作真实 KOL 画像结论。")
    if event.metadata.get("real_timestamp_available") is False:
        notes.append("该数据源不包含真实发布时间，时间序列由节点顺序补齐，持续时间和引爆时间只用于算法流程验证。")
    return notes
