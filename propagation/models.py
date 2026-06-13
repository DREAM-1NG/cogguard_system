from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional, Tuple

import networkx as nx


@dataclass
class Participant:
    """A user/account participating in an information cascade."""

    user_id: str
    screen_name: Optional[str] = None
    followers_count: Optional[int] = None
    friends_count: Optional[int] = None
    statuses_count: Optional[int] = None
    verified: Optional[bool] = None
    raw: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PropagationNode:
    """A post/repost/reply node in a propagation tree."""

    node_id: str
    user_id: str
    text: str = ""
    timestamp: Optional[datetime] = None
    parent_id: Optional[str] = None
    event_id: Optional[str] = None
    label: Optional[str] = None
    raw: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PropagationEvent:
    """A single event/cascade represented as a directed graph from parent to child."""

    event_id: str
    nodes: Dict[str, PropagationNode] = field(default_factory=dict)
    participants: Dict[str, Participant] = field(default_factory=dict)
    label: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def add_node(self, node: PropagationNode) -> None:
        if node.event_id is None:
            node.event_id = self.event_id
        if node.label is None:
            node.label = self.label
        self.nodes[node.node_id] = node
        participant = self.participants.setdefault(node.user_id, Participant(user_id=node.user_id))
        user = node.raw.get("user") if isinstance(node.raw, dict) else None
        if isinstance(user, dict):
            participant.screen_name = participant.screen_name or _string_or_none(user.get("screen_name") or user.get("name"))
            participant.followers_count = _prefer_int(participant.followers_count, user.get("followers_count"))
            participant.friends_count = _prefer_int(participant.friends_count, user.get("friends_count"))
            participant.statuses_count = _prefer_int(participant.statuses_count, user.get("statuses_count"))
            if participant.verified is None and user.get("verified") is not None:
                participant.verified = bool(user.get("verified"))
            participant.raw.update(user)

    def to_graph(self) -> nx.DiGraph:
        graph = nx.DiGraph(event_id=self.event_id, label=self.label, metadata=self.metadata)
        for node_id, node in self.nodes.items():
            graph.add_node(
                node_id,
                user_id=node.user_id,
                text=node.text,
                timestamp=node.timestamp,
                label=node.label,
                raw=node.raw,
            )
        for node_id, node in self.nodes.items():
            if node.parent_id and node.parent_id in self.nodes and node.parent_id != node_id:
                graph.add_edge(node.parent_id, node_id)
        return graph

    @classmethod
    def from_edges(
        cls,
        event_id: str,
        edges: Iterable[Tuple[str, str]],
        label: Optional[str] = None,
    ) -> "PropagationEvent":
        event = cls(event_id=event_id, label=label)
        seen = set()
        for parent, child in edges:
            if parent not in seen:
                event.add_node(PropagationNode(node_id=parent, user_id=f"user_{parent}"))
                seen.add(parent)
            if child not in seen:
                event.add_node(PropagationNode(node_id=child, user_id=f"user_{child}", parent_id=parent))
                seen.add(child)
            else:
                event.nodes[child].parent_id = parent
        return event


def sorted_nodes_by_time(event: PropagationEvent) -> List[PropagationNode]:
    return sorted(
        event.nodes.values(),
        key=lambda n: (n.timestamp is None, n.timestamp or datetime.max, n.node_id),
    )


def _prefer_int(existing: Optional[int], value: Any) -> Optional[int]:
    if existing is not None:
        return existing
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _string_or_none(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
