from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Dict, List, Optional

import networkx as nx
import numpy as np
import pandas as pd

from .models import PropagationEvent, sorted_nodes_by_time


def analyze_events(events: List[PropagationEvent], output_dir: str, focus_event_id: Optional[str] = None) -> Dict:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    summaries = [summarize_event(event) for event in events]
    participants = pd.concat([participant_table(event) for event in events], ignore_index=True) if events else pd.DataFrame()
    ignitions = pd.concat([ignition_points(event) for event in events], ignore_index=True) if events else pd.DataFrame()
    paths = {event.event_id: key_paths(event) for event in events}
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
        "narrative": build_narrative(summaries, ignitions),
    }

    (out / "analysis_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    participants.to_csv(out / "participants.csv", index=False)
    ignitions.to_csv(out / "ignition_points.csv", index=False)
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
        "top_spreaders": [n for n, _ in Counter(out_degrees).most_common(5)],
    }


def participant_table(event: PropagationEvent) -> pd.DataFrame:
    graph = event.to_graph()
    pagerank = _influence_scores(graph)
    undirected = graph.to_undirected()
    betweenness = nx.betweenness_centrality(undirected) if graph.number_of_nodes() < 2000 else {n: 0 for n in graph.nodes}
    rows = []
    by_user = defaultdict(list)
    for node_id, data in graph.nodes(data=True):
        by_user[data.get("user_id", node_id)].append(node_id)
    for user_id, node_ids in by_user.items():
        times = [graph.nodes[n].get("timestamp") for n in node_ids if graph.nodes[n].get("timestamp")]
        participant = event.participants.get(user_id)
        rows.append(
            {
                "event_id": event.event_id,
                "user_id": user_id,
                "screen_name": participant.screen_name if participant else None,
                "followers_count": participant.followers_count if participant else None,
                "verified": participant.verified if participant else None,
                "post_count": len(node_ids),
                "first_seen": min(times) if times else None,
                "out_degree_sum": sum(graph.out_degree(n) for n in node_ids),
                "pagerank_sum": sum(pagerank.get(n, 0.0) for n in node_ids),
                "betweenness_sum": sum(betweenness.get(n, 0.0) for n in node_ids),
                "role": _participant_role(sum(graph.out_degree(n) for n in node_ids), sum(betweenness.get(n, 0.0) for n in node_ids)),
            }
        )
    return pd.DataFrame(rows)


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


def _participant_role(out_degree: int, betweenness: float) -> str:
    if out_degree >= 5:
        return "amplifier/KOL"
    if betweenness > 0.05:
        return "bridge"
    if out_degree > 0:
        return "secondary-spreader"
    return "ordinary-participant"


def _influence_scores(graph: nx.DiGraph, exact_limit: int = 5000) -> Dict[str, float]:
    if not graph.number_of_nodes():
        return {}
    if graph.number_of_nodes() <= exact_limit:
        return nx.pagerank(graph)
    total = sum(deg for _, deg in graph.out_degree()) or 1
    return {node: graph.out_degree(node) / total for node in graph.nodes}


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
