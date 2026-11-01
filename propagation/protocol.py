from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Set

from .models import PropagationEvent, sorted_nodes_by_time


@dataclass(frozen=True)
class CoordinationScope:
    """KT1 coordination output normalized for KT2 role/evidence filtering."""

    users: Set[str]
    groups: Dict[str, str]


def load_coordination_scope(path: Optional[str]) -> CoordinationScope:
    if not path:
        return CoordinationScope(users=set(), groups={})
    source = Path(path)
    if not source.exists():
        raise FileNotFoundError(f"coordination file not found: {source}")
    if source.suffix.lower() == ".json":
        return _load_coordination_json(source)
    return _load_coordination_table(source)


def export_standard_cascades(
    events: Iterable[PropagationEvent],
    output_dir: str,
    coordination: Optional[CoordinationScope] = None,
    *,
    t_obs: Optional[float] = None,
    t_pred: Optional[float] = None,
    split: str = "unspecified",
    leakage_check: str = "observed graph only; prediction labels excluded from protocol export",
) -> Path:
    """Write a compact protocol file shared by KT2 analysis, prediction, and benchmark stages."""

    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    coord = coordination or CoordinationScope(users=set(), groups={})
    payload = {
        "schema": "cogguard.kt2.standard_cascade.v1",
        "protocol": {
            "t_obs": t_obs,
            "t_pred": t_pred,
            "split": split,
            "leakage_check": leakage_check,
        },
        "events": [_event_payload(event, coord) for event in events],
    }
    path = out / "standard_cascades.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    return path


def _event_payload(event: PropagationEvent, coordination: CoordinationScope) -> Dict[str, Any]:
    graph = event.to_graph()
    ordered = sorted_nodes_by_time(event)
    nodes = []
    for idx, node in enumerate(ordered):
        nodes.append(
            {
                "node_id": node.node_id,
                "user_id": node.user_id,
                "parent_id": node.parent_id,
                "timestamp": node.timestamp,
                "text": node.text,
                "coord_group_id": coordination.groups.get(node.user_id),
                "is_coordinated": node.user_id in coordination.users or node.user_id in coordination.groups,
                "activation_index": idx,
            }
        )
    return {
        "event_id": event.event_id,
        "label": event.label,
        "metadata": event.metadata,
        "nodes": nodes,
        "edges": [{"source": src, "target": dst} for src, dst in graph.edges()],
    }


def _load_coordination_json(path: Path) -> CoordinationScope:
    data = json.loads(path.read_text(encoding="utf-8"))
    users: Set[str] = set()
    groups: Dict[str, str] = {}

    if isinstance(data, Mapping):
        for key in ("users", "coordinated_users", "user_ids"):
            users.update(str(value) for value in _as_list(data.get(key)))
        for item in _as_list(data.get("groups") or data.get("coordination_groups")):
            if isinstance(item, Mapping):
                group_id = str(item.get("group_id") or item.get("id") or item.get("cluster_id") or "coord")
                for user_id in _as_list(item.get("users") or item.get("user_ids") or item.get("members")):
                    user = str(user_id)
                    users.add(user)
                    groups[user] = group_id
        for item in _as_list(data.get("records") or data.get("items")):
            if isinstance(item, Mapping):
                user = _record_user_id(item)
                if user:
                    users.add(user)
                    if item.get("group_id") or item.get("cluster_id"):
                        groups[user] = str(item.get("group_id") or item.get("cluster_id"))
    elif isinstance(data, list):
        for item in data:
            if isinstance(item, Mapping):
                user = _record_user_id(item)
                if user:
                    users.add(user)
                    if item.get("group_id") or item.get("cluster_id"):
                        groups[user] = str(item.get("group_id") or item.get("cluster_id"))
            else:
                users.add(str(item))
    return CoordinationScope(users=users, groups=groups)


def _load_coordination_table(path: Path) -> CoordinationScope:
    delimiter = "\t" if path.suffix.lower() in {".tsv", ".tab"} else ","
    users: Set[str] = set()
    groups: Dict[str, str] = {}
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle, delimiter=delimiter)
        if not reader.fieldnames:
            return CoordinationScope(users=set(), groups={})
        for row in reader:
            user = _record_user_id(row)
            if not user:
                continue
            users.add(user)
            group = row.get("group_id") or row.get("cluster_id") or row.get("coord_group_id")
            if group:
                groups[user] = str(group)
    return CoordinationScope(users=users, groups=groups)


def _record_user_id(record: Mapping[str, Any]) -> Optional[str]:
    for key in ("user_id", "uid", "user", "account_id", "member_id"):
        value = record.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return None


def _as_list(value: Any) -> List[Any]:
    if value is None:
        return []
    if isinstance(value, (list, tuple, set)):
        return list(value)
    return [value]
