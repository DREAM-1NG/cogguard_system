from __future__ import annotations

import hashlib
import json
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse

from .contracts import (
    MODALITY_SPECIFIC_FIELD_MARKERS,
    PLATFORM_GENERIC_EVIDENCE_KINDS,
    TOPOLOGY_AUDIT_FEATURE_NAMES,
    EvidenceEdge,
    EvidenceGraph,
    EvidenceObject,
)

TOKEN_PATTERN = re.compile(r"[\u4e00-\u9fff]|[A-Za-z0-9_]+")
HASHTAG_PATTERN = re.compile(r"#([0-9A-Za-z_\-\u4e00-\u9fff]+)#?")
MENTION_PATTERN = re.compile(r"@([0-9A-Za-z_\-\u4e00-\u9fff]+)")
MEDIA_EXTENSIONS = {
    ".jpg",
    ".jpeg",
    ".png",
    ".gif",
    ".webp",
    ".bmp",
    ".mp4",
    ".mov",
    ".m4v",
    ".avi",
    ".mkv",
    ".mp3",
    ".wav",
    ".aac",
    ".flac",
}


def build_evidence_graph(snapshot: Any) -> EvidenceGraph:
    """Build the platform-generic temporal account-object evidence graph."""

    posts = _snapshot_list(snapshot, "posts")
    comments = _snapshot_list(snapshot, "comments")
    relationships = _snapshot_list(snapshot, "relationships")
    snapshot_id = _snapshot_text(snapshot, "snapshot_id") or _stable_hash({"posts": posts, "comments": comments})[:16]
    event_id = _snapshot_text(snapshot, "event_id")
    data_fingerprint = _snapshot_text(snapshot, "data_fingerprint") or _stable_hash(
        {"snapshot_id": snapshot_id, "posts": posts, "comments": comments, "relationships": relationships}
    )

    content_index = _build_content_index(posts=posts, comments=comments)
    objects: dict[str, EvidenceObject] = {}
    edges: list[EvidenceEdge] = []
    excluded_fields: list[dict[str, str]] = []

    for content in content_index.values():
        excluded_fields.extend(_excluded_modality_fields(content["row"], content_id=content["content_id"]))
        for edge, evidence_object in _content_edges(content, content_index=content_index):
            objects.setdefault(evidence_object.object_id, evidence_object)
            edges.append(edge)

    for signature, members in _near_duplicate_groups(content_index).items():
        if len(members) < 2:
            continue
        object_id = f"near_duplicate:{signature}"
        evidence_object = EvidenceObject(object_id=object_id, object_kind="near_duplicate", value=signature)
        objects.setdefault(object_id, evidence_object)
        for member in members:
            edges.append(
                _edge(
                    account_id=member["account_id"],
                    content_id=member["content_id"],
                    object_id=object_id,
                    evidence_kind="near_duplicate",
                    relation_type="near_duplicate",
                    evidence_ref=f"{member['content_id']}:near_duplicate:{signature}",
                    platform=member["platform"],
                    observed_at=member["observed_at"],
                    weight=0.75,
                )
            )

    for relation in relationships:
        source_id = _object_text(relation, "source_id")
        target_id = _object_text(relation, "target_id")
        relation_type = _normalize_token(_object_text(relation, "relation_type")) or "native_relation"
        platform = _object_text(relation, "platform") or "unknown"
        source_content = _find_content(content_index, source_id, platform=platform)
        if not source_content:
            continue
        object_id = f"native_relation:{relation_type}:{_normalize_token(target_id)}"
        objects.setdefault(
            object_id,
            EvidenceObject(object_id=object_id, object_kind="native_relation", value=f"{relation_type}:{target_id}"),
        )
        edges.append(
            _edge(
                account_id=source_content["account_id"],
                content_id=source_content["content_id"],
                object_id=object_id,
                evidence_kind="native_relation",
                relation_type=relation_type,
                evidence_ref=_object_text(relation, "evidence_ref") or f"{source_id}:{relation_type}:{target_id}",
                platform=platform,
                observed_at=_timestamp_seconds(_object_value(relation, "observed_at")),
            )
        )

    edges = _dedupe_edges(edges)
    accounts = sorted({edge.source_account_id for edge in edges if edge.source_account_id})
    coverage = _coverage(edges=edges, content_count=len(content_index), object_count=len(objects))
    audit_features = _topology_audit_features(accounts=accounts, edges=edges)

    return EvidenceGraph(
        snapshot_id=snapshot_id,
        event_id=event_id,
        data_fingerprint=data_fingerprint,
        accounts=accounts,
        objects=sorted(objects.values(), key=lambda item: item.object_id),
        edges=edges,
        excluded_fields=excluded_fields,
        topology_audit_features=audit_features,
        coverage=coverage,
    )


def _content_edges(
    content: dict[str, Any],
    *,
    content_index: dict[str, dict[str, Any]],
) -> list[tuple[EvidenceEdge, EvidenceObject]]:
    row = content["row"]
    account_id = content["account_id"]
    if not account_id:
        return []

    edges: list[tuple[EvidenceEdge, EvidenceObject]] = []
    text = content["text"]
    for url in _iter_urls(row):
        normalized = _normalize_url(url)
        if not normalized:
            continue
        edges.append(_edge_pair(content, "url", normalized, "url", normalized))
        domain = _domain(normalized)
        if domain:
            edges.append(_edge_pair(content, "domain", domain, "domain", domain))

    for hashtag in _iter_hashtags(row, text):
        normalized = _normalize_token(hashtag)
        if normalized:
            edges.append(_edge_pair(content, "hashtag", normalized, "hashtag", normalized))

    for keyword in _iter_keywords(row):
        normalized = _normalize_token(keyword)
        if normalized:
            edges.append(_edge_pair(content, "keyword", normalized, "keyword", normalized))

    for entity in _iter_entities(row, text):
        normalized = _normalize_token(entity)
        if normalized:
            edges.append(_edge_pair(content, "entity", normalized, "entity", normalized))

    for target_ref, target_label, relation_type in _iter_targets(row, content_index=content_index):
        normalized = _normalize_token(target_label or target_ref)
        if normalized:
            edges.append(_edge_pair(content, "target", normalized, relation_type, target_ref))

    for discussion in _iter_discussion_targets(row):
        normalized = _normalize_token(discussion)
        if normalized:
            edges.append(_edge_pair(content, "discussion", normalized, "discussion", discussion))

    for relation_type, target_ref in _iter_native_relations(row):
        normalized = _normalize_token(target_ref)
        if normalized:
            edges.append(_edge_pair(content, "native_relation", f"{relation_type}:{normalized}", relation_type, target_ref))

    return edges


def _edge_pair(
    content: dict[str, Any],
    evidence_kind: str,
    object_value: str,
    relation_type: str,
    evidence_value: str,
) -> tuple[EvidenceEdge, EvidenceObject]:
    object_id = f"{evidence_kind}:{object_value}"
    evidence_object = EvidenceObject(object_id=object_id, object_kind=evidence_kind, value=object_value)
    edge = _edge(
        account_id=content["account_id"],
        content_id=content["content_id"],
        object_id=object_id,
        evidence_kind=evidence_kind,
        relation_type=relation_type,
        evidence_ref=f"{content['content_id']}:{relation_type}:{evidence_value}",
        platform=content["platform"],
        observed_at=content["observed_at"],
    )
    return edge, evidence_object


def _edge(
    *,
    account_id: str,
    content_id: str,
    object_id: str,
    evidence_kind: str,
    relation_type: str,
    evidence_ref: str,
    platform: str,
    observed_at: float,
    weight: float = 1.0,
) -> EvidenceEdge:
    return EvidenceEdge(
        source_account_id=account_id,
        evidence_object_id=object_id,
        evidence_kind=evidence_kind,
        relation_type=relation_type,
        content_id=content_id,
        platform=platform,
        observed_at=observed_at,
        evidence_ref=evidence_ref,
        weight=weight,
    )


def _build_content_index(*, posts: list[dict[str, Any]], comments: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    index: dict[str, dict[str, Any]] = {}
    post_platforms: dict[str, str] = {}
    for row in posts:
        platform = _text(row.get("platform")) or "unknown"
        post_id = _text(row.get("post_id") or row.get("id"))
        if post_id:
            post_platforms[post_id] = platform
        content = _content_record(row, kind="post", platform=platform)
        index[content["content_id"]] = content
        if post_id:
            index.setdefault(post_id, content)

    for row in comments:
        platform = _text(row.get("platform")) or post_platforms.get(_text(row.get("post_id")), "unknown")
        content = _content_record(row, kind="comment", platform=platform)
        index[content["content_id"]] = content
        comment_id = _text(row.get("comment_id") or row.get("id"))
        if comment_id:
            index.setdefault(comment_id, content)

    return {key: value for key, value in index.items() if key == value["content_id"]}


def _content_record(row: dict[str, Any], *, kind: str, platform: str) -> dict[str, Any]:
    identifier = _text(row.get("post_id") if kind == "post" else row.get("comment_id"))
    identifier = identifier or _text(row.get("id")) or _stable_hash(row)[:12]
    return {
        "content_id": f"{platform}:{kind}:{identifier}",
        "account_id": _text(row.get("author_id") or row.get("user_id") or row.get("account_id")),
        "platform": platform,
        "observed_at": _timestamp_seconds(row.get("timestamp") or row.get("created_at") or row.get("publish_time")),
        "text": _content_text(row),
        "row": row,
    }


def _iter_urls(row: dict[str, Any]) -> list[str]:
    values: list[str] = []
    for key in ("url", "urls", "shared_url", "shared_urls", "link", "links", "source_url"):
        values.extend(_flatten_text_values(row.get(key)))
    raw_data = row.get("raw_data") if isinstance(row.get("raw_data"), dict) else {}
    values.extend(_extract_nested_generic_urls(raw_data))
    return [url for url in _dedupe_texts(values) if not _is_media_url(url)]


def _iter_hashtags(row: dict[str, Any], text: str) -> list[str]:
    values: list[str] = []
    for key in ("hashtag", "hashtags", "topic", "topics", "tags"):
        values.extend(_flatten_text_values(row.get(key)))
    raw_data = row.get("raw_data") if isinstance(row.get("raw_data"), dict) else {}
    values.extend(_extract_nested_strings(raw_data, {"hash", "tag", "topic"}, exclude_modality=True))
    values.extend(HASHTAG_PATTERN.findall(text or ""))
    return _dedupe_texts(values)


def _iter_keywords(row: dict[str, Any]) -> list[str]:
    values: list[str] = []
    for key in ("keyword", "keywords", "key_terms", "topic_keywords"):
        values.extend(_flatten_text_values(row.get(key)))
    raw_data = row.get("raw_data") if isinstance(row.get("raw_data"), dict) else {}
    values.extend(_extract_nested_strings(raw_data, {"keyword", "key_term"}, exclude_modality=True))
    return _dedupe_texts(values)


def _iter_entities(row: dict[str, Any], text: str) -> list[str]:
    values: list[str] = []
    for key in ("entity", "entities", "entity_names", "mentions", "target_entities"):
        values.extend(_flatten_text_values(row.get(key)))
    raw_data = row.get("raw_data") if isinstance(row.get("raw_data"), dict) else {}
    values.extend(_extract_nested_strings(raw_data, {"entity", "mention", "target", "name"}, exclude_modality=True))
    values.extend(MENTION_PATTERN.findall(text or ""))
    return _dedupe_texts(values)


def _iter_targets(row: dict[str, Any], *, content_index: dict[str, dict[str, Any]]) -> list[tuple[str, str, str]]:
    targets: list[tuple[str, str, str]] = []
    for field, relation_type in (
        ("target", "target"),
        ("target_id", "target"),
        ("target_account_id", "target"),
        ("mention_target", "target"),
        ("reply_target", "reply"),
        ("reply_to", "reply"),
        ("parent_comment_id", "reply"),
        ("parent_post_id", "parent"),
        ("quote_post_id", "quote"),
        ("repost_id", "repost"),
        ("retweeted_post_id", "repost"),
    ):
        value = _text(row.get(field))
        if not value:
            continue
        targets.append((_resolve_target_ref(row, value, content_index), value, relation_type))
    return targets


def _iter_discussion_targets(row: dict[str, Any]) -> list[str]:
    values: list[str] = []
    for key in ("discussion_id", "conversation_id", "thread_id", "root_post_id"):
        values.extend(_flatten_text_values(row.get(key)))
    if _text(row.get("comment_id")) and _text(row.get("post_id")):
        values.append(_text(row.get("post_id")))
    return _dedupe_texts(values)


def _iter_native_relations(row: dict[str, Any]) -> list[tuple[str, str]]:
    values: list[tuple[str, str]] = []
    for field, relation_type in (
        ("reply_to", "reply"),
        ("parent_comment_id", "reply"),
        ("parent_post_id", "parent"),
        ("quote_post_id", "quote"),
        ("repost_id", "repost"),
        ("retweeted_post_id", "repost"),
    ):
        value = _text(row.get(field))
        if value:
            values.append((relation_type, value))
    return values


def _near_duplicate_groups(content_index: dict[str, dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for content in content_index.values():
        signature = _near_duplicate_signature(content["text"])
        if signature:
            groups[signature].append(content)
    return dict(groups)


def _near_duplicate_signature(text: str) -> str:
    tokens = _tokens(text)
    if len(tokens) < 6:
        return ""
    compact = " ".join(tokens[:12])
    return hashlib.sha1(compact.encode("utf-8")).hexdigest()[:12]


def _topology_audit_features(*, accounts: list[str], edges: list[EvidenceEdge]) -> dict[str, Any]:
    by_account: dict[str, list[EvidenceEdge]] = defaultdict(list)
    for edge in edges:
        by_account[edge.source_account_id].append(edge)
    rows = []
    for account in accounts:
        account_edges = by_account.get(account, [])
        object_counts = Counter(edge.evidence_object_id for edge in account_edges)
        total = sum(object_counts.values()) or 1
        rows.append(
            {
                "account_id": account,
                "degree": len(object_counts),
                "weighted_degree": round(sum(edge.weight for edge in account_edges), 6),
                "object_concentration": round(max(object_counts.values(), default=0) / total, 6),
                "component_size": 0,
                "pagerank": None,
                "density": None,
            }
        )
    return {
        "feature_role": "audit_only",
        "feature_names": list(TOPOLOGY_AUDIT_FEATURE_NAMES),
        "rows": rows,
    }


def _coverage(*, edges: list[EvidenceEdge], content_count: int, object_count: int) -> dict[str, Any]:
    kind_counts = Counter(edge.evidence_kind for edge in edges)
    return {
        "kind_counts": {kind: int(kind_counts.get(kind, 0)) for kind in PLATFORM_GENERIC_EVIDENCE_KINDS},
        "edge_count": len(edges),
        "object_count": object_count,
        "content_count": content_count,
        "coverage_ratio": round(len(edges) / max(content_count, 1), 6) if content_count else 0.0,
    }


def _dedupe_edges(edges: list[EvidenceEdge]) -> list[EvidenceEdge]:
    deduped: dict[tuple[str, str, str, str], EvidenceEdge] = {}
    for edge in edges:
        if not edge.source_account_id or not edge.evidence_object_id:
            continue
        key = (edge.source_account_id, edge.content_id, edge.evidence_object_id, edge.relation_type)
        existing = deduped.get(key)
        if existing is None or edge.weight > existing.weight:
            deduped[key] = edge
    return sorted(
        deduped.values(),
        key=lambda item: (item.observed_at, item.source_account_id, item.evidence_object_id, item.relation_type),
    )


def _excluded_modality_fields(row: dict[str, Any], *, content_id: str) -> list[dict[str, str]]:
    excluded: list[dict[str, str]] = []
    for key in row:
        if _is_modality_key(key):
            excluded.append({"content_id": content_id, "field": str(key), "reason": "modality_specific"})
    raw_data = row.get("raw_data")
    if isinstance(raw_data, dict):
        for path in _nested_modality_paths(raw_data):
            excluded.append({"content_id": content_id, "field": f"raw_data.{path}", "reason": "modality_specific"})
    return excluded


def _nested_modality_paths(value: Any, *, prefix: str = "") -> list[str]:
    paths: list[str] = []
    if isinstance(value, dict):
        for key, item in value.items():
            next_prefix = f"{prefix}.{key}" if prefix else str(key)
            if _is_modality_key(str(key)):
                paths.append(next_prefix)
                continue
            paths.extend(_nested_modality_paths(item, prefix=next_prefix))
    elif isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            paths.extend(_nested_modality_paths(item, prefix=f"{prefix}[{index}]"))
    return paths


def _extract_nested_generic_urls(value: Any, *, parent_key: str = "") -> list[str]:
    values: list[str] = []
    if _is_modality_key(parent_key):
        return values
    if isinstance(value, str):
        if any(marker in parent_key.lower() for marker in ("url", "link")) and not _is_media_url(value):
            values.append(value)
        return values
    if isinstance(value, dict):
        for key, item in value.items():
            values.extend(_extract_nested_generic_urls(item, parent_key=str(key)))
        return values
    if isinstance(value, (list, tuple, set)):
        for item in value:
            values.extend(_extract_nested_generic_urls(item, parent_key=parent_key))
    return values


def _extract_nested_strings(value: Any, markers: set[str], *, parent_key: str = "", exclude_modality: bool) -> list[str]:
    values: list[str] = []
    if exclude_modality and _is_modality_key(parent_key):
        return values
    if isinstance(value, str):
        if any(marker in parent_key.lower() for marker in markers):
            values.append(value)
        return values
    if isinstance(value, dict):
        for key, item in value.items():
            values.extend(_extract_nested_strings(item, markers, parent_key=str(key), exclude_modality=exclude_modality))
        return values
    if isinstance(value, (list, tuple, set)):
        for item in value:
            values.extend(_extract_nested_strings(item, markers, parent_key=parent_key, exclude_modality=exclude_modality))
    return values


def _resolve_target_ref(row: dict[str, Any], value: str, content_index: dict[str, dict[str, Any]]) -> str:
    platform = _text(row.get("platform")) or "unknown"
    content = _find_content(content_index, value, platform=platform)
    if content:
        return str(content["content_id"])
    return f"{platform}:target:{_normalize_token(value)}"


def _find_content(content_index: dict[str, dict[str, Any]], value: str, *, platform: str) -> dict[str, Any] | None:
    if value in content_index:
        return content_index[value]
    for candidate in (f"{platform}:post:{value}", f"{platform}:comment:{value}"):
        if candidate in content_index:
            return content_index[candidate]
    suffixes = (f":post:{value}", f":comment:{value}")
    for content_id, content in content_index.items():
        if content_id.endswith(suffixes):
            return content
    return None


def _snapshot_list(snapshot: Any, field: str) -> list[Any]:
    value = _object_value(snapshot, field)
    return list(value or []) if isinstance(value, (list, tuple)) else []


def _snapshot_text(snapshot: Any, field: str) -> str:
    return _text(_object_value(snapshot, field))


def _object_value(value: Any, field: str) -> Any:
    if isinstance(value, dict):
        return value.get(field)
    return getattr(value, field, None)


def _object_text(value: Any, field: str) -> str:
    return _text(_object_value(value, field))


def _content_text(row: dict[str, Any]) -> str:
    return " ".join(
        _text(row.get(key))
        for key in ("content", "text", "title", "desc", "summary")
        if _text(row.get(key))
    ).strip()


def _flatten_text_values(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        values: list[str] = []
        for item in value.values():
            values.extend(_flatten_text_values(item))
        return values
    if isinstance(value, (list, tuple, set)):
        items: list[str] = []
        for item in value:
            items.extend(_flatten_text_values(item))
        return items
    return [str(value)]


def _dedupe_texts(values: list[str]) -> list[str]:
    deduped: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = _text(value)
        if not text:
            continue
        key = text.lower()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(text)
    return deduped


def _normalize_url(value: str) -> str:
    text = re.sub(r"\s+", "", _text(value)).lower()
    if not text:
        return ""
    parsed = urlparse(text if "://" in text else f"https://{text}")
    if not parsed.netloc:
        return text
    path = parsed.path.rstrip("/")
    query = f"?{parsed.query}" if parsed.query else ""
    return f"{parsed.scheme}://{parsed.netloc}{path}{query}"


def _domain(value: str) -> str:
    parsed = urlparse(value if "://" in value else f"https://{value}")
    return parsed.netloc.lower()


def _is_media_url(value: str) -> bool:
    path = urlparse(_text(value)).path.lower()
    return any(path.endswith(extension) for extension in MEDIA_EXTENSIONS)


def _normalize_token(value: str) -> str:
    return re.sub(r"[^0-9A-Za-z\u4e00-\u9fff]+", "", _text(value)).lower()


def _tokens(text: str) -> list[str]:
    return [match.group(0).lower() for match in TOKEN_PATTERN.finditer(text or "")]


def _timestamp_seconds(value: Any) -> float:
    if isinstance(value, datetime):
        ts = value
    elif value in (None, ""):
        return 0.0
    else:
        try:
            ts = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except ValueError:
            try:
                return float(value)
            except (TypeError, ValueError):
                return 0.0
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    return float(ts.astimezone(timezone.utc).timestamp())


def _is_modality_key(key: str) -> bool:
    lowered = str(key or "").lower()
    return any(marker in lowered for marker in MODALITY_SPECIFIC_FIELD_MARKERS)


def _stable_hash(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _text(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


__all__ = ["build_evidence_graph"]
