"""Propagation thread context helpers for KT3 agent review.

This module turns source-post/reaction threads into a compact, auditable
context that an LLM agent can read. It does not train or run graph models.
"""

from __future__ import annotations

from collections import Counter, defaultdict, deque
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any


THREAD_CONTEXT_SCHEMA = "kt3-thread-context-v1"
PROPAGATION_CONTEXT_SCHEMA = "kt3-propagation-context-v1"

__all__ = [
    "PROPAGATION_CONTEXT_SCHEMA",
    "THREAD_CONTEXT_SCHEMA",
    "build_propagation_context",
    "build_propagation_context_for_case",
    "build_thread_context_from_pheme",
    "summarize_thread_context",
]


def build_thread_context_from_pheme(
    source_tweet: dict[str, Any],
    reactions: list[dict[str, Any]],
    *,
    dataset: str = "PHEME",
    event_name: str = "",
    tree_id: str = "",
    rumour_label: str = "",
    veracity: str = "",
) -> dict[str, Any]:
    """Build a normalized reply tree from one PHEME source tweet and reactions."""

    root_post_id = _post_id(source_tweet) or str(tree_id or "root")
    nodes_by_id: dict[str, dict[str, Any]] = {
        root_post_id: _node_from_tweet(
            source_tweet,
            node_id=root_post_id,
            parent_id="",
            depth=0,
            is_root=True,
        )
    }
    pending_parent_by_id: dict[str, str] = {}
    for reaction in reactions:
        post_id = _post_id(reaction)
        if not post_id or post_id in nodes_by_id:
            continue
        parent_id = _reply_parent_id(reaction) or root_post_id
        nodes_by_id[post_id] = _node_from_tweet(
            reaction,
            node_id=post_id,
            parent_id=parent_id,
            depth=1,
            is_root=False,
        )
        pending_parent_by_id[post_id] = parent_id

    for post_id, parent_id in list(pending_parent_by_id.items()):
        if parent_id not in nodes_by_id:
            nodes_by_id[post_id]["parent_id"] = root_post_id
            pending_parent_by_id[post_id] = root_post_id

    children_by_parent: dict[str, list[str]] = defaultdict(list)
    for post_id, parent_id in pending_parent_by_id.items():
        children_by_parent[parent_id].append(post_id)

    queue: deque[tuple[str, int]] = deque([(root_post_id, 0)])
    visited: set[str] = set()
    while queue:
        post_id, depth = queue.popleft()
        if post_id in visited:
            continue
        visited.add(post_id)
        nodes_by_id[post_id]["depth"] = depth
        for child_id in sorted(children_by_parent.get(post_id, [])):
            queue.append((child_id, depth + 1))

    edges = [
        {
            "source": parent_id,
            "target": post_id,
            "relation": "replies_to",
            "source_author_id": nodes_by_id.get(parent_id, {}).get("author_id", ""),
            "target_author_id": nodes_by_id.get(post_id, {}).get("author_id", ""),
        }
        for post_id, parent_id in sorted(pending_parent_by_id.items())
        if post_id in nodes_by_id and parent_id in nodes_by_id
    ]
    nodes = sorted(nodes_by_id.values(), key=lambda item: (int(item.get("depth", 0)), str(item.get("node_id", ""))))
    thread_context = {
        "schema_version": THREAD_CONTEXT_SCHEMA,
        "dataset": dataset,
        "event": event_name,
        "tree_id": str(tree_id or root_post_id),
        "root_post_id": root_post_id,
        "rumour_label": rumour_label,
        "veracity": veracity,
        "nodes": nodes,
        "edges": edges,
    }
    thread_context["summary"] = summarize_thread_context(thread_context)
    return thread_context


def build_propagation_context_for_case(
    case: dict[str, Any],
    *,
    claim_rank: list[dict[str, Any]] | None = None,
    graph_summary: dict[str, Any] | None = None,
    post_semantics_summary: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build an agent-readable propagation context from a normalized case."""

    thread_context = case.get("thread_context") or {}
    return build_propagation_context(
        thread_context if isinstance(thread_context, dict) else {},
        claim_rank=claim_rank,
        graph_summary=graph_summary,
        post_semantics_summary=post_semantics_summary,
    )


def build_propagation_context(
    thread_context: dict[str, Any] | None,
    *,
    claim_rank: list[dict[str, Any]] | None = None,
    graph_summary: dict[str, Any] | None = None,
    post_semantics_summary: dict[str, Any] | None = None,
    max_nodes: int = 12,
    max_branches: int = 5,
    max_snapshots: int = 4,
) -> dict[str, Any]:
    """Summarize a thread tree for PropagationTreeAgent."""

    thread_context = thread_context or {}
    nodes = _as_list(thread_context.get("nodes"))
    edges = _as_list(thread_context.get("edges"))
    summary = thread_context.get("summary") if isinstance(thread_context.get("summary"), dict) else {}
    has_thread_context = bool(nodes and thread_context.get("tree_id"))
    missing_fields = []
    if not has_thread_context:
        missing_fields.append("thread_context.nodes")
    if not edges and len(nodes) > 1:
        missing_fields.append("thread_context.edges")
    if not any(_parse_timestamp(node.get("created_at")) for node in nodes):
        missing_fields.append("node.created_at")
    if not any(_text(node.get("stance_label")) for node in nodes):
        missing_fields.append("node.stance_label")

    return {
        "schema_version": PROPAGATION_CONTEXT_SCHEMA,
        "tree_id": thread_context.get("tree_id", ""),
        "root_post_id": thread_context.get("root_post_id", ""),
        "has_thread_context": has_thread_context,
        "tree_metrics": summary or summarize_thread_context(thread_context),
        "central_nodes": _central_nodes(nodes, edges, limit=max_nodes),
        "key_branches": _key_branches(thread_context, limit=max_branches),
        "stance_by_depth": _stance_by_depth(nodes),
        "temporal_snapshots": _temporal_snapshots(nodes, max_snapshots=max_snapshots),
        "evidence_nodes": _evidence_nodes(nodes, limit=max_nodes),
        "claim_rank": _as_list(claim_rank)[:10],
        "graph_summary": graph_summary or {},
        "post_semantics_summary": post_semantics_summary or {},
        "missing_fields": missing_fields,
        "method_notes": [
            "Conversation/thread linkages are treated as first-class evidence.",
            "Key branches are compacted before LLM review to avoid context overflow.",
            "If thread nodes or edges are missing, the propagation review must be evidence-limited.",
        ],
    }


def summarize_thread_context(thread_context: dict[str, Any] | None) -> dict[str, Any]:
    thread_context = thread_context or {}
    nodes = _as_list(thread_context.get("nodes"))
    edges = _as_list(thread_context.get("edges"))
    depths = [_safe_int(node.get("depth")) for node in nodes]
    children_by_parent: dict[str, int] = defaultdict(int)
    for edge in edges:
        source = _text(edge.get("source"))
        if source:
            children_by_parent[source] += 1
    stance_counts = Counter(_text(node.get("stance_label")) or "unknown" for node in nodes)
    timestamps = [_parse_timestamp(node.get("created_at")) for node in nodes]
    valid_timestamps = [item for item in timestamps if item is not None]
    return {
        "node_count": len(nodes),
        "edge_count": len(edges),
        "reply_count": max(0, len(nodes) - 1),
        "max_depth": max(depths) if depths else 0,
        "max_width": max(children_by_parent.values()) if children_by_parent else 0,
        "stance_counts": dict(stance_counts),
        "has_timestamps": bool(valid_timestamps),
        "first_seen_at": min(valid_timestamps).isoformat() if valid_timestamps else "",
        "last_seen_at": max(valid_timestamps).isoformat() if valid_timestamps else "",
    }


def _node_from_tweet(
    tweet: dict[str, Any],
    *,
    node_id: str,
    parent_id: str,
    depth: int,
    is_root: bool,
) -> dict[str, Any]:
    user = tweet.get("user") if isinstance(tweet.get("user"), dict) else {}
    text = _text(tweet.get("text") or tweet.get("full_text"))
    return {
        "node_id": node_id,
        "post_id": node_id,
        "parent_id": parent_id,
        "author_id": _text(user.get("id_str") or user.get("id") or tweet.get("user_id")),
        "created_at": _text(tweet.get("created_at")),
        "text": text,
        "excerpt": text[:240],
        "depth": depth,
        "is_root": is_root,
        "stance_label": "source" if is_root else _stance_proxy(text),
    }


def _post_id(tweet: dict[str, Any]) -> str:
    return _text(tweet.get("id_str") or tweet.get("id"))


def _reply_parent_id(tweet: dict[str, Any]) -> str:
    return _text(tweet.get("in_reply_to_status_id_str") or tweet.get("in_reply_to_status_id"))


def _stance_proxy(text: str) -> str:
    lowered = text.lower()
    deny_markers = ("fake", "false", "hoax", "lie", "wrong", "not true", "假的", "谣言", "不实", "辟谣")
    support_markers = ("true", "confirmed", "agree", "yes", "support", "证实", "同意", "属实")
    if "?" in text or "？" in text:
        return "query"
    if any(marker in lowered for marker in deny_markers):
        return "deny"
    if any(marker in lowered for marker in support_markers):
        return "support"
    return "neutral"


def _central_nodes(nodes: list[Any], edges: list[Any], *, limit: int) -> list[dict[str, Any]]:
    degree = Counter()
    for edge in edges:
        source = _text(edge.get("source")) if isinstance(edge, dict) else ""
        target = _text(edge.get("target")) if isinstance(edge, dict) else ""
        if source:
            degree[source] += 1
        if target:
            degree[target] += 1
    rows = []
    for node in nodes:
        if not isinstance(node, dict):
            continue
        node_id = _text(node.get("node_id") or node.get("post_id"))
        rows.append(
            {
                "node_id": node_id,
                "depth": _safe_int(node.get("depth")),
                "degree": int(degree.get(node_id, 0)),
                "stance_label": _text(node.get("stance_label")) or "unknown",
                "excerpt": _text(node.get("excerpt") or node.get("text"))[:200],
            }
        )
    return sorted(rows, key=lambda item: (-item["degree"], item["depth"], item["node_id"]))[:limit]


def _key_branches(thread_context: dict[str, Any], *, limit: int) -> list[dict[str, Any]]:
    nodes = {str(node.get("node_id") or node.get("post_id")): node for node in _as_list(thread_context.get("nodes")) if isinstance(node, dict)}
    if not nodes:
        return []
    children_by_parent: dict[str, list[str]] = defaultdict(list)
    for edge in _as_list(thread_context.get("edges")):
        if not isinstance(edge, dict):
            continue
        source = _text(edge.get("source"))
        target = _text(edge.get("target"))
        if source and target:
            children_by_parent[source].append(target)
    root_id = _text(thread_context.get("root_post_id")) or next(iter(nodes))
    paths: list[list[str]] = []

    def visit(node_id: str, path: list[str]) -> None:
        children = sorted(children_by_parent.get(node_id, []))
        if not children:
            paths.append(path)
            return
        for child_id in children:
            if child_id in path:
                continue
            visit(child_id, [*path, child_id])

    visit(root_id, [root_id])
    if not paths:
        paths = [[root_id]]
    ranked = sorted(paths, key=lambda path: (-len(path), path[-1]))[:limit]
    branches = []
    for index, path in enumerate(ranked, start=1):
        path_nodes = [nodes[node_id] for node_id in path if node_id in nodes]
        branches.append(
            {
                "branch_id": f"branch-{index}",
                "path_node_ids": path,
                "depth": max(0, len(path) - 1),
                "stance_sequence": [_text(node.get("stance_label")) or "unknown" for node in path_nodes],
                "excerpts": [_text(node.get("excerpt") or node.get("text"))[:160] for node in path_nodes],
            }
        )
    return branches


def _stance_by_depth(nodes: list[Any]) -> dict[str, dict[str, int]]:
    rows: dict[str, Counter] = defaultdict(Counter)
    for node in nodes:
        if not isinstance(node, dict):
            continue
        depth = str(_safe_int(node.get("depth")))
        stance = _text(node.get("stance_label")) or "unknown"
        rows[depth][stance] += 1
    return {depth: dict(counter) for depth, counter in sorted(rows.items(), key=lambda item: int(item[0]))}


def _temporal_snapshots(nodes: list[Any], *, max_snapshots: int) -> list[dict[str, Any]]:
    stamped = []
    for node in nodes:
        if not isinstance(node, dict):
            continue
        timestamp = _parse_timestamp(node.get("created_at"))
        if timestamp is None:
            continue
        stamped.append((timestamp, node))
    stamped.sort(key=lambda item: item[0])
    if not stamped:
        return []
    bucket_count = min(max(1, max_snapshots), len(stamped))
    buckets: list[list[tuple[datetime, dict[str, Any]]]] = [[] for _ in range(bucket_count)]
    for index, item in enumerate(stamped):
        bucket_index = min(bucket_count - 1, int(index * bucket_count / len(stamped)))
        buckets[bucket_index].append(item)
    snapshots = []
    cumulative = 0
    for index, bucket in enumerate(buckets, start=1):
        if not bucket:
            continue
        cumulative += len(bucket)
        stance_counts = Counter(_text(node.get("stance_label")) or "unknown" for _, node in bucket)
        snapshots.append(
            {
                "snapshot_id": f"t{index}",
                "start_at": bucket[0][0].isoformat(),
                "end_at": bucket[-1][0].isoformat(),
                "new_nodes": len(bucket),
                "cumulative_nodes": cumulative,
                "stance_counts": dict(stance_counts),
            }
        )
    return snapshots


def _evidence_nodes(nodes: list[Any], *, limit: int) -> list[dict[str, Any]]:
    rows = []
    for node in nodes:
        if not isinstance(node, dict):
            continue
        text = _text(node.get("text") or node.get("excerpt"))
        if not text:
            continue
        rows.append(
            {
                "node_id": _text(node.get("node_id") or node.get("post_id")),
                "depth": _safe_int(node.get("depth")),
                "stance_label": _text(node.get("stance_label")) or "unknown",
                "text": text[:240],
            }
        )
    return sorted(rows, key=lambda item: (item["depth"], item["node_id"]))[:limit]


def _parse_timestamp(value: Any) -> datetime | None:
    raw = _text(value)
    if not raw:
        return None
    try:
        parsed = parsedate_to_datetime(raw)
    except (TypeError, ValueError):
        try:
            parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except ValueError:
            return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def _safe_int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _text(value: Any) -> str:
    return str(value or "").strip()
