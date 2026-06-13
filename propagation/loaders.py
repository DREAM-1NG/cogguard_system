from __future__ import annotations

import json
import re
import csv
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from dateutil import parser as date_parser

from .models import PropagationEvent, PropagationNode


def load_dataset(
    dataset: str,
    data_dir: Optional[str] = None,
    max_events: Optional[int] = None,
    event_id: Optional[str] = None,
) -> List[PropagationEvent]:
    if not data_dir:
        return make_synthetic_events()
    dataset = _normalize_dataset_name(dataset)
    if dataset == "weibo":
        return load_weibo_auto(data_dir, max_events=max_events, event_id=event_id)
    if dataset == "weibo_rumor":
        return load_weibo_rumor(data_dir, max_events=max_events, event_id=event_id)
    if dataset == "rumor_rvnn_twitter":
        return load_rumor_rvnn_twitter(data_dir)
    if dataset in {"pheme", "pheme_rnr"}:
        return load_pheme(data_dir)
    raise ValueError(f"Unsupported dataset: {dataset}")


def load_weibo_auto(data_dir: str, max_events: Optional[int] = None, event_id: Optional[str] = None) -> List[PropagationEvent]:
    """Load a Weibo-like dataset by detecting the concrete on-disk format."""

    root = Path(data_dir)
    if _find_weibo_event_files(root):
        return load_weibo_rumor(data_dir, max_events=max_events, event_id=event_id)
    if _find_rvnn_processed_files(root):
        return load_rumor_rvnn_twitter(data_dir)
    return load_weibo_tree_records(data_dir)


def load_weibo_rumor(data_dir: str, max_events: Optional[int] = None, event_id: Optional[str] = None) -> List[PropagationEvent]:
    """Load the ScienceDB/Ma-Weibo rumor event dataset.

    Expected public metadata format:
    - an event index where each row is event_id, label, post_ids;
    - a posts/ directory where posts/{event_id}.json contains post objects.

    If post objects do not expose explicit parent/repost fields, the loader uses
    the first post id as the source post and connects the remaining posts to it.
    """

    events: List[PropagationEvent] = []
    for row in iter_weibo_rumor_rows(data_dir, max_events=max_events, event_id=event_id):
        event = build_weibo_rumor_event(Path(data_dir), row)
        if event.nodes:
            events.append(event)

    if not events:
        raise ValueError(f"No Weibo Rumor events parsed under {data_dir}")
    return events


def iter_weibo_rumor_rows(
    data_dir: str,
    max_events: Optional[int] = None,
    event_id: Optional[str] = None,
) -> Iterable[Tuple[str, str, List[str]]]:
    root = Path(data_dir)
    event_files = _find_weibo_event_files(root)
    if not event_files:
        raise ValueError(
            "No Weibo Rumor event index found. Expected rows like "
            "'event_id,label,post_ids' and optional posts/{event_id}.json files."
        )

    parsed_rows: List[Tuple[str, str, List[str]]] = []
    for path in event_files:
        for raw_line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
            parsed = _parse_weibo_event_line(raw_line)
            if not parsed:
                continue
            if event_id and parsed[0] != event_id:
                continue
            parsed_rows.append(parsed)

    if max_events is not None:
        if max_events <= 0:
            raise ValueError("max_events must be positive")
        parsed_rows = sorted(parsed_rows, key=lambda row: len(row[2]), reverse=True)[:max_events]

    yield from parsed_rows


def build_weibo_rumor_event(root: Path, row: Tuple[str, str, List[str]]) -> PropagationEvent:
    row_event_id, label, post_ids = row
    event = PropagationEvent(
        event_id=row_event_id,
        label=label,
        metadata={
            "source_format": "ScienceDB/Ma-Weibo event index + per-event JSON",
            "real_user_profile_available": False,
            "real_timestamp_available": True,
            "note": "Weibo JSON includes user ids and timestamps but not full user profiles.",
        },
    )
    post_lookup = _load_weibo_posts(root, row_event_id)
    aliases = _weibo_post_aliases(post_lookup)
    source_id = post_ids[0] if post_ids else None
    post_id_set = set(post_ids)
    for idx, post_id in enumerate(post_ids):
        raw = post_lookup.get(post_id) or post_lookup.get(aliases.get(post_id, "")) or {}
        parent_id = _extract_parent_id(raw)
        if parent_id and parent_id not in post_id_set:
            parent_id = aliases.get(str(parent_id), str(parent_id))
        if parent_id and parent_id not in post_id_set:
            parent_id = None
        if not parent_id and idx > 0:
            parent_id = source_id
        if parent_id == post_id:
            parent_id = None
        event.add_node(
            PropagationNode(
                node_id=post_id,
                user_id=_extract_user_id(raw, post_id),
                text=str(raw.get("text") or raw.get("content") or raw.get("message") or ""),
                timestamp=_parse_time(raw.get("created_at") or raw.get("time") or raw.get("t") or raw.get("timestamp")),
                parent_id=str(parent_id) if parent_id else None,
                event_id=row_event_id,
                label=label,
                raw=raw,
            )
        )
    _ensure_temporal_order(event)
    return event


def load_rumor_rvnn_twitter(data_dir: str) -> List[PropagationEvent]:
    """Load the official Rumor_RvNN Twitter15/16 preprocessed tree rows."""

    root = Path(data_dir)
    labels = _load_label_map(root)
    events = _load_rvnn_processed(root, labels)
    if not events:
        raise ValueError(
            "No Rumor_RvNN processed files found. Expected "
            "resource/data.TD_RvNN.vol_*.txt or data.BU_RvNN.vol_*.txt."
        )
    return events


def load_weibo_tree_records(data_dir: str) -> List[PropagationEvent]:
    """Load generic Weibo propagation tree records.

    Public Weibo mirrors appear in slightly different layouts. This parser
    intentionally accepts multiple line formats:
    - parent child
    - parent -> child
    - parent: child1 child2 ...
    - JSON lines containing id/mid, parent/parent_id, user/user_id, t/time.
    """

    root = Path(data_dir)
    labels = _load_label_map(root)
    tree_files = _find_tree_files(root)
    events: List[PropagationEvent] = []

    for path in tree_files:
        event_id = path.stem
        event = PropagationEvent(event_id=event_id, label=labels.get(event_id))
        parsed_any = False
        for raw_line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
            line = raw_line.strip()
            if not line:
                continue
            if line.startswith("{"):
                node = _parse_json_node(line, event_id, labels.get(event_id))
                if node:
                    event.add_node(node)
                    parsed_any = True
                continue
            records = _parse_edge_records(line, default_event_id=event_id)
            for record in records:
                parent = record["parent"]
                child = record["child"]
                child_user = record.get("child_user") or f"user_{child}"
                parent_user = record.get("parent_user") or f"user_{parent}"
                if parent not in event.nodes:
                    event.add_node(PropagationNode(node_id=parent, user_id=parent_user, timestamp=record.get("parent_time")))
                event.add_node(
                    PropagationNode(
                        node_id=child,
                        user_id=child_user,
                        parent_id=parent,
                        timestamp=record.get("child_time"),
                        text=record.get("text") or "",
                    )
                )
                parsed_any = True
        if parsed_any and event.nodes:
            _ensure_temporal_order(event)
            events.append(event)

    if not events:
        raise ValueError(f"No Weibo propagation tree records found under {data_dir}")
    return events


# Backward-compatible name retained for older local scripts.
load_weibo_rvnn = load_weibo_auto


def load_pheme(data_dir: str) -> List[PropagationEvent]:
    """Load PHEME rumour/non-rumour thread JSON files into propagation events."""

    root = Path(data_dir)
    result: List[PropagationEvent] = []

    for thread_dir in _iter_pheme_thread_dirs(root):
        annotation = _load_pheme_annotation(thread_dir)
        label = _pheme_label(thread_dir, annotation)
        event = PropagationEvent(
            event_id=thread_dir.name,
            label=label,
            metadata=_pheme_metadata(thread_dir, annotation),
        )
        structure_parent = _load_pheme_structure_parents(thread_dir)
        source_ids = set()

        for path in _iter_pheme_tweet_jsons(thread_dir):
            obj = _load_json_object(path)
            if not obj:
                continue
            node_id = str(obj.get("id_str") or obj.get("id") or path.stem)
            if not node_id or node_id.startswith("._"):
                continue
            user = obj.get("user") or {}
            user_id = str(user.get("id_str") or user.get("id") or obj.get("user_id") or f"user_{node_id}")
            parent_id = obj.get("in_reply_to_status_id_str") or obj.get("in_reply_to_status_id")
            parent_id = str(parent_id) if parent_id else structure_parent.get(node_id)
            if "source-tweets" in path.parts:
                parent_id = None
                source_ids.add(node_id)
            event.add_node(
                PropagationNode(
                    node_id=node_id,
                    user_id=user_id,
                    text=obj.get("text") or "",
                    timestamp=_parse_time(obj.get("created_at")),
                    parent_id=parent_id,
                    event_id=event.event_id,
                    label=event.label,
                    raw=obj,
                )
            )

        for node in event.nodes.values():
            structured_parent = structure_parent.get(node.node_id)
            if structured_parent and structured_parent in event.nodes and structured_parent != node.node_id:
                if not node.parent_id or node.parent_id not in event.nodes:
                    node.parent_id = structured_parent
            if node.node_id in source_ids:
                node.parent_id = None

        if event.nodes:
            _repair_missing_parents(event)
            _ensure_temporal_order(event)
            result.append(event)

    if not result:
        raise ValueError(f"No PHEME tweet JSON files found under {data_dir}")
    return result


def make_synthetic_events() -> List[PropagationEvent]:
    base = datetime(2024, 1, 1, 9, 0, 0)
    events: List[PropagationEvent] = []
    for eidx in range(8):
        event = PropagationEvent(event_id=f"synthetic_{eidx}", label="rumour" if eidx % 2 else "non-rumour")
        total = 35 + eidx * 8
        for i in range(total):
            if i == 0:
                parent = None
            elif i < 8:
                parent = "0"
            elif i < 20 and i % 3 == 0:
                parent = "2"
            else:
                parent = str(max(0, i // 2 - 1))
            event.add_node(
                PropagationNode(
                    node_id=str(i),
                    user_id=f"u{(i * 7 + eidx) % 23}",
                    text=f"Synthetic post {i}",
                    timestamp=base + timedelta(minutes=i * (1 + eidx % 3)),
                    parent_id=parent,
                    event_id=event.event_id,
                    label=event.label,
                )
            )
        events.append(event)
    return events


def _normalize_dataset_name(dataset: str) -> str:
    normalized = dataset.lower().replace("-", "_")
    aliases = {
        "ma_weibo": "weibo_rumor",
        "weibo_ma": "weibo_rumor",
        "science_db_weibo": "weibo_rumor",
        "sciencedb_weibo": "weibo_rumor",
        "rumor_rvnn": "rumor_rvnn_twitter",
        "rvnn": "rumor_rvnn_twitter",
        "twitter_rvnn": "rumor_rvnn_twitter",
        "twitter15": "rumor_rvnn_twitter",
        "twitter16": "rumor_rvnn_twitter",
        "pheme_rnr": "pheme",
    }
    return aliases.get(normalized, normalized)


def _find_rvnn_processed_files(root: Path) -> List[Path]:
    return sorted(root.rglob("data.TD_RvNN.vol_*.txt")) or sorted(root.rglob("data.BU_RvNN.vol_*.txt"))


def _find_weibo_event_files(root: Path) -> List[Path]:
    candidates = []
    seen_inodes = set()
    for path in root.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in {".txt", ".csv", ".tsv"}:
            continue
        low = str(path).lower()
        if "readme" in low or "download_meta" in low or path.name.startswith("data.") or "twitter" in low or "nfold" in low:
            continue
        try:
            stat = path.stat()
            inode_key = (stat.st_dev, stat.st_ino)
            if inode_key in seen_inodes:
                continue
        except OSError:
            inode_key = None
        parsed = 0
        total = 0
        for raw in path.read_text(encoding="utf-8", errors="ignore").splitlines()[:50]:
            if not raw.strip():
                continue
            total += 1
            if _parse_weibo_event_line(raw):
                parsed += 1
        if parsed and parsed / max(total, 1) >= 0.5:
            candidates.append(path)
            if inode_key:
                seen_inodes.add(inode_key)
    return candidates


def _parse_weibo_event_line(line: str) -> Optional[Tuple[str, str, List[str]]]:
    line = line.strip().lstrip("\ufeff")
    if not line or line.startswith("#"):
        return None
    if line.lower().replace(" ", "") in {"event_id,label,post_ids", "eventid,label,postids"}:
        return None

    row = None
    for delimiter in (",", "\t"):
        try:
            parsed = next(csv.reader([line], delimiter=delimiter))
        except Exception:
            parsed = []
        if len(parsed) >= 3:
            row = [part.strip() for part in parsed]
            break
    if row is None:
        row = re.split(r"\s+", line, maxsplit=2)
    if len(row) < 3:
        return None

    event_id = row[0].strip().strip("'\"")
    if ":" in event_id:
        key, value = event_id.split(":", 1)
        if key.lower() in {"eid", "event", "event_id", "id"}:
            event_id = value.strip().strip("'\"")
    label = _normalize_weibo_label(row[1])
    post_ids = _parse_post_ids(" ".join(row[2:]))
    if not event_id or label is None or not post_ids:
        return None
    return event_id, label, post_ids


def _normalize_weibo_label(value: str) -> Optional[str]:
    value = str(value).strip().strip("'\"").lower()
    if ":" in value:
        key, raw = value.split(":", 1)
        if key in {"label", "y", "class"}:
            value = raw.strip().strip("'\"").lower()
    if value in {"1", "rumor", "rumour", "true", "false_rumor", "false-rumor"}:
        return "rumor"
    if value in {"0", "non-rumor", "non_rumor", "non-rumour", "non_rumour", "normal", "real"}:
        return "non-rumor"
    return None


def _parse_post_ids(value: str) -> List[str]:
    value = value.strip().strip("[](){}")
    parts = [p.strip().strip("'\"") for p in re.split(r"[\s,;|]+", value) if p.strip().strip("'\"")]
    return parts


def _load_weibo_posts(root: Path, event_id: str) -> Dict[str, Dict]:
    path = _find_weibo_post_file(root, event_id)
    if path:
        try:
            obj = json.loads(path.read_text(encoding="utf-8", errors="ignore"))
        except Exception:
            return {}
        return _flatten_post_json(obj)
    return {}


def _find_weibo_post_file(root: Path, event_id: str) -> Optional[Path]:
    for path in (
        root / "posts" / f"{event_id}.json",
        root / "post" / f"{event_id}.json",
        root / "Weibo" / f"{event_id}.json",
        root / "weibo" / f"{event_id}.json",
        root / f"{event_id}.json",
    ):
        if path.exists():
            return path
    return None


def _flatten_post_json(obj) -> Dict[str, Dict]:
    posts: Dict[str, Dict] = {}

    def add_post(item):
        if not isinstance(item, dict):
            return
        post_id = _extract_post_id(item)
        if post_id:
            posts[post_id] = item

    if isinstance(obj, list):
        for item in obj:
            add_post(item)
    elif isinstance(obj, dict):
        if any(k in obj for k in ("id", "id_str", "mid", "post_id")):
            add_post(obj)
        for key in ("posts", "data", "items", "reposts", "comments"):
            value = obj.get(key)
            if isinstance(value, list):
                for item in value:
                    add_post(item)
        for key, value in obj.items():
            if isinstance(value, dict):
                post_id = _extract_post_id(value) or str(key)
                posts[post_id] = value
    return posts


def _weibo_post_aliases(posts: Dict[str, Dict]) -> Dict[str, str]:
    aliases: Dict[str, str] = {}
    for canonical_id, obj in posts.items():
        aliases[str(canonical_id)] = str(canonical_id)
        if not isinstance(obj, dict):
            continue
        for key in ("id", "id_str", "mid", "post_id", "weibo_id"):
            value = obj.get(key)
            if value:
                aliases[str(value)] = str(canonical_id)
    return aliases


def _extract_post_id(obj: Dict) -> Optional[str]:
    value = obj.get("id") or obj.get("id_str") or obj.get("mid") or obj.get("post_id") or obj.get("weibo_id")
    return str(value) if value else None


def _extract_user_id(obj: Dict, fallback: str) -> str:
    user = obj.get("user") if isinstance(obj, dict) else None
    if isinstance(user, dict):
        value = user.get("id") or user.get("id_str") or user.get("uid") or user.get("screen_name")
        if value:
            return str(value)
    value = obj.get("user_id") or obj.get("uid") or obj.get("userid")
    return str(value) if value else f"user_{fallback}"


def _extract_parent_id(obj: Dict) -> Optional[str]:
    if not isinstance(obj, dict):
        return None
    for key in ("parent", "parent_id", "parent_mid", "pid", "reply_to", "reply_to_id", "in_reply_to_status_id"):
        value = obj.get(key)
        if value:
            return str(value)
    for key in ("retweeted_status", "repost_status", "parent_status"):
        value = obj.get(key)
        if isinstance(value, dict):
            post_id = _extract_post_id(value)
            if post_id:
                return post_id
    return None


def _load_rvnn_processed(root: Path, labels: Dict[str, str]) -> List[PropagationEvent]:
    files = _find_rvnn_processed_files(root)
    events: Dict[str, PropagationEvent] = {}
    for path in files:
        for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
            parts = line.strip().split("\t")
            if len(parts) < 5:
                continue
            root_id, parent_idx, current_idx, parent_count, text_len = parts[:5]
            label = labels.get(root_id)
            event = events.get(root_id)
            if event is None:
                event = PropagationEvent(
                    event_id=root_id,
                    label=label,
                    metadata={
                        "source_format": "Rumor_RvNN TD_RvNN preprocessed tree rows",
                        "real_user_profile_available": False,
                        "real_timestamp_available": False,
                        "note": "The public processed file contains structure/features only; user_id and timestamps are local placeholders.",
                    },
                )
                events[root_id] = event
            if event.label is None:
                event.label = label
            parent_id = None if parent_idx in {"None", "none", "null", "-1", ""} else parent_idx
            event.add_node(
                PropagationNode(
                    node_id=current_idx,
                    user_id=f"user_{current_idx}",
                    parent_id=parent_id,
                    event_id=root_id,
                    label=event.label,
                    raw={"root_id": root_id, "parent_count": parent_count, "text_len": text_len, "source_file": str(path)},
                )
            )
    result = [event for event in events.values() if event.nodes]
    for event in result:
        _ensure_temporal_order(event)
    return result


def _find_tree_files(root: Path) -> List[Path]:
    candidates = []
    for path in root.rglob("*.txt"):
        low = str(path).lower()
        if "label" in low or path.name.lower() in {"readme.txt"}:
            continue
        if path.name.startswith("data.") and "rvnn" in path.name.lower():
            continue
        if "tree" in low or "propagation" in low or "weibo" in low:
            candidates.append(path)
    return candidates or [p for p in root.rglob("*.txt") if "label" not in p.name.lower() and not p.name.startswith("data.")]


def _load_label_map(root: Path) -> Dict[str, str]:
    labels: Dict[str, str] = {}
    for path in root.rglob("*.txt"):
        if "label" not in path.name.lower() and path.name.lower() not in {"weibo.txt", "twitter.txt"}:
            continue
        for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
            parts = re.split(r"\s+", line.strip())
            if len(parts) < 2:
                continue
            # Twitter15_label_All.txt format:
            # label event_name root_tweet_id ...
            if parts[0] in {"false", "true", "unverified", "non-rumor", "non-rumour", "rumor", "rumour"} and len(parts) >= 3:
                labels[parts[2]] = parts[0]
                labels[parts[1]] = parts[0]
                continue
            labels[parts[0].split(":")[-1]] = parts[-1].split(":")[-1]
    return labels


def _parse_edge_records(line: str, default_event_id: str = "") -> List[Dict]:
    """Parse one Rumor_RvNN/Weibo tree line into normalized edge records.

    Accepted examples include:
    - parent child
    - parent -> child
    - parent: child1 child2
    - parent\tchild\ttime
    - event_id\tparent\tchild\t...
    - JSON object with parent/child fields
    - Rumor_RvNN tuple-like rows containing parent and current node metadata

    The function returns dictionaries to leave room for user/time metadata when it
    exists, while still supporting simple parent-child trees.
    """
    line = line.strip()
    if not line:
        return []
    if line.startswith("{"):
        try:
            obj = json.loads(line)
        except Exception:
            return []
        parent = obj.get("parent") or obj.get("parent_id") or obj.get("parent_mid") or obj.get("in_reply_to_status_id")
        child = obj.get("child") or obj.get("child_id") or obj.get("id") or obj.get("id_str") or obj.get("mid")
        if parent and child and str(parent) != str(child):
            user = obj.get("user") or {}
            return [
                {
                    "parent": str(parent),
                    "child": str(child),
                    "child_user": str(user.get("id") or user.get("id_str") or obj.get("user_id") or f"user_{child}"),
                    "child_time": _parse_time(obj.get("created_at") or obj.get("time") or obj.get("t")),
                    "text": obj.get("text") or obj.get("content") or "",
                }
            ]
        return []

    if ":" in line and "->" not in line and not line.lstrip().startswith("("):
        parent, children = line.split(":", 1)
        return [
            {"parent": parent.strip(), "child": c.strip()}
            for c in re.split(r"[\s,]+", children)
            if c.strip() and c.strip() != parent.strip()
        ]

    tuple_records = _parse_tuple_like_weibo_line(line)
    if tuple_records:
        return tuple_records

    cleaned = line.replace("->", " ").replace(",", " ").replace("\t", " ")
    parts = [p for p in re.split(r"\s+", cleaned) if p]
    if len(parts) < 2:
        return []

    # Some files include event_id parent child ...; prefer columns 1/2 when the
    # first token equals the current file/event id or looks like a label prefix.
    if len(parts) >= 3 and (parts[0] == default_event_id or parts[0].lower() in {"eid", "event", "event_id", "root"}):
        parent, child = parts[1], parts[2]
    else:
        parent, child = parts[0], parts[1]
    if parent == child:
        return []
    return [{"parent": parent, "child": child}]


def _parse_tuple_like_weibo_line(line: str) -> List[Dict]:
    """Best-effort parser for Rumor_RvNN tree rows with tuple-style metadata.

    Known public variants encode parent/current node information using fragments
    like `(parent_id,parent_user,parent_time) -> (child_id,child_user,child_time)`
    or tab-separated tuple blobs. We extract the first two tuple-like groups and
    map them to parent and child IDs.
    """
    groups = re.findall(r"\(([^()]*)\)", line)
    if len(groups) < 2:
        return []

    def split_group(group: str) -> List[str]:
        return [x.strip().strip("'\"") for x in re.split(r"[,\s]+", group) if x.strip()]

    parent_parts = split_group(groups[0])
    child_parts = split_group(groups[1])
    if not parent_parts or not child_parts:
        return []
    parent = parent_parts[0]
    child = child_parts[0]
    if not parent or not child or parent == child or parent.lower() in {"none", "null"}:
        return []
    record = {"parent": parent, "child": child}
    if len(parent_parts) > 1:
        record["parent_user"] = parent_parts[1]
    if len(child_parts) > 1:
        record["child_user"] = child_parts[1]
    if len(parent_parts) > 2:
        record["parent_time"] = _parse_time(parent_parts[2])
    if len(child_parts) > 2:
        record["child_time"] = _parse_time(child_parts[2])
    return [record]


def _parse_json_node(line: str, event_id: str, label: Optional[str]) -> Optional[PropagationNode]:
    try:
        obj = json.loads(line)
    except Exception:
        return None
    node_id = str(obj.get("id") or obj.get("id_str") or obj.get("mid") or obj.get("tweet_id") or "")
    if not node_id:
        return None
    user = obj.get("user") or {}
    user_id = str(user.get("id") or user.get("id_str") or obj.get("user_id") or f"user_{node_id}")
    parent = obj.get("parent") or obj.get("parent_id") or obj.get("parent_mid")
    return PropagationNode(
        node_id=node_id,
        user_id=user_id,
        text=obj.get("text") or obj.get("content") or "",
        timestamp=_parse_time(obj.get("created_at") or obj.get("time") or obj.get("t")),
        parent_id=str(parent) if parent else None,
        event_id=event_id,
        label=label,
        raw=obj,
    )


def _iter_pheme_thread_dirs(root: Path) -> List[Path]:
    dirs = {
        path.parent
        for path in root.rglob("source-tweets")
        if path.is_dir() and (path.parent / "reactions").exists()
    }
    dirs.update({path.parent for path in root.rglob("reactions") if path.is_dir()})
    return sorted(dirs)


def _iter_pheme_tweet_jsons(thread_dir: Path) -> List[Path]:
    files: List[Path] = []
    for subdir in (thread_dir / "source-tweets", thread_dir / "reactions"):
        if not subdir.exists():
            continue
        files.extend(path for path in subdir.glob("*.json") if _is_real_json_file(path))
    return sorted(files)


def _is_real_json_file(path: Path) -> bool:
    return path.is_file() and path.suffix.lower() == ".json" and not path.name.startswith("._")


def _load_json_object(path: Path) -> Optional[Dict[str, Any]]:
    try:
        obj = json.loads(path.read_text(encoding="utf-8", errors="ignore"))
    except Exception:
        return None
    return obj if isinstance(obj, dict) else None


def _load_pheme_annotation(thread_dir: Path) -> Dict[str, Any]:
    path = thread_dir / "annotation.json"
    obj = _load_json_object(path) if path.exists() else None
    return obj or {}


def _pheme_label(thread_dir: Path, annotation: Dict[str, Any]) -> str:
    parts = {p.lower() for p in thread_dir.parts}
    if "non-rumours" in parts or "non-rumors" in parts:
        return "non-rumour"
    truth = str(annotation.get("true", "")).strip().lower()
    misinformation = str(annotation.get("misinformation", "")).strip().lower()
    if truth in {"1", "true", "yes"}:
        return "true-rumour"
    if misinformation in {"1", "true", "yes"}:
        return "false-rumour"
    return "unverified-rumour"


def _pheme_metadata(thread_dir: Path, annotation: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "topic": _pheme_topic(thread_dir),
        "claim": annotation.get("category"),
        "annotation": annotation,
        "source_path": str(thread_dir),
        "rumour_class": _infer_pheme_label(thread_dir),
        "source_format": "PHEME annotated Twitter thread",
        "real_user_profile_available": True,
        "real_timestamp_available": True,
    }


def _pheme_topic(thread_dir: Path) -> Optional[str]:
    for part in reversed(thread_dir.parts):
        if part.endswith("-all-rnr-threads"):
            return part[: -len("-all-rnr-threads")]
    return None


def _load_pheme_structure_parents(thread_dir: Path) -> Dict[str, str]:
    path = thread_dir / "structure.json"
    obj = _load_json_object(path) if path.exists() else None
    if not obj:
        return {}
    parents: Dict[str, str] = {}

    def walk(parent: Optional[str], children: Any) -> None:
        if isinstance(children, dict):
            for child, grand_children in children.items():
                child_id = str(child)
                if parent and child_id != parent:
                    parents[child_id] = parent
                walk(child_id, grand_children)
        elif isinstance(children, list):
            for child in children:
                if isinstance(child, (str, int)):
                    child_id = str(child)
                    if parent and child_id != parent:
                        parents[child_id] = parent
                else:
                    walk(parent, child)

    walk(None, obj)
    return parents


def _parse_time(value) -> Optional[datetime]:
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)):
        try:
            return datetime.fromtimestamp(float(value))
        except Exception:
            return None
    try:
        return date_parser.parse(str(value))
    except Exception:
        return None


def _infer_pheme_label(path: Path) -> Optional[str]:
    parts = {p.lower() for p in path.parts}
    if "rumours" in parts or "rumors" in parts:
        return "rumour"
    if "non-rumours" in parts or "non-rumors" in parts:
        return "non-rumour"
    return None


def _infer_pheme_event_id(path: Path) -> str:
    parts = list(path.parts)
    for marker in ("source-tweets", "reactions"):
        if marker in parts:
            idx = parts.index(marker)
            if idx > 0:
                return parts[idx - 1]
    return path.parent.name


def _repair_missing_parents(event: PropagationEvent) -> None:
    roots = [n for n in event.nodes.values() if not n.parent_id or n.parent_id not in event.nodes]
    source = min(roots, key=lambda n: n.timestamp or datetime.max, default=None)
    if not source:
        return
    for node in event.nodes.values():
        if node.node_id != source.node_id and (not node.parent_id or node.parent_id not in event.nodes):
            node.parent_id = source.node_id


def _ensure_temporal_order(event: PropagationEvent) -> None:
    base = datetime(2024, 1, 1)
    for idx, node in enumerate(sorted(event.nodes.values(), key=lambda n: n.node_id)):
        if node.timestamp is None:
            node.timestamp = base + timedelta(minutes=idx)
