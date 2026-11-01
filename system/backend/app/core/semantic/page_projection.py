"""Compact, read-only projections for Event Review semantic surfaces."""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping
from typing import Any, Literal


SemanticPageView = Literal["evidence", "clusters", "entities", "temporal", "verifiable"]
SEMANTIC_PAGE_VIEWS = frozenset({"evidence", "clusters", "entities", "temporal", "verifiable"})
SEMANTIC_STATIC_PAGE_VIEWS = frozenset({"evidence", "clusters", "entities", "temporal"})
SEMANTIC_PAGE_READ_MODEL_SCHEMA = "cogguard.semantic.page_read_model.v2"
_LEGACY_SEMANTIC_PAGE_READ_MODEL_SCHEMA = "cogguard.semantic.page_read_model.v1"

_KEYWORD_LIMIT = 50
_TOPIC_LIMIT = 50
_COMMUNITY_LIMIT = 12
_ENTITY_GROUP_LIMIT = 16
_RELATION_FACET_LIMIT = 24
_RELATION_DISTRIBUTION_LIMIT = 8
_WORKSPACE_TRACEABLE_PAGE_SIZE = 40
_TRACEABLE_TEXT_LIMIT = 1_500


def build_semantic_page_projection(
    artifact: Mapping[str, Any],
    *,
    view: SemanticPageView,
    page: int = 1,
    page_size: int = 40,
) -> dict[str, Any]:
    """Build one bounded UI projection without exposing the full artifact.

    This is the compatibility path for artifacts written before the page read
    model existed. New analysis runs persist a compact read model during stage
    execution so page requests do not need to call this function.
    """
    if view == "evidence":
        summary, content = _evidence_projection(artifact)
        return {"summary": summary, "content": content}
    if view == "clusters":
        summary, content = _cluster_projection(artifact)
        return {"summary": summary, "content": content}
    if view == "entities":
        summary, content = _entity_projection(artifact)
        return {"summary": summary, "content": content}
    if view == "temporal":
        summary = _artifact_summary(artifact)
        return {"summary": summary, "content": _temporal_content(artifact)}
    summary, content = _verifiable_projection(artifact, page=max(1, page), page_size=max(1, page_size))
    return {
        "summary": summary,
        "content": content,
    }


def build_semantic_page_read_model(
    artifact: Mapping[str, Any],
    *,
    source_artifact_sha256: str,
) -> dict[str, Any]:
    """Compile compact analyst projections while the source artifact is in memory.

    The persisted read model intentionally excludes raw ``layers`` and
    unbounded traceable rows. It is an accelerator for the Semantic Evidence
    Workspace, not a second semantic analysis result or a replacement for the
    immutable source artifact.
    """
    source_hash = _text(source_artifact_sha256)
    if not source_hash:
        raise ValueError("semantic page read model requires source artifact sha256")

    summary, views = _compile_static_page_views(artifact)
    return {
        "schema": SEMANTIC_PAGE_READ_MODEL_SCHEMA,
        "source_artifact_sha256": source_hash,
        "snapshot_fingerprint": _artifact_snapshot_fingerprint(artifact),
        "summary": summary,
        "views": views,
        "workspace": build_semantic_workspace_projection(
            artifact,
            page=1,
            page_size=_WORKSPACE_TRACEABLE_PAGE_SIZE,
        ),
    }


def read_semantic_page_read_model(
    read_model: Mapping[str, Any],
    *,
    view: SemanticPageView,
    expected_source_artifact_sha256: str,
) -> dict[str, Any] | None:
    """Validate and read one aggregate projection from a persisted read model."""
    if view not in SEMANTIC_STATIC_PAGE_VIEWS:
        return None
    if _text(read_model.get("schema")) not in {
        SEMANTIC_PAGE_READ_MODEL_SCHEMA,
        _LEGACY_SEMANTIC_PAGE_READ_MODEL_SCHEMA,
    }:
        return None
    if _text(read_model.get("source_artifact_sha256")) != _text(expected_source_artifact_sha256):
        return None
    if not _text(read_model.get("snapshot_fingerprint")):
        return None
    summary = read_model.get("summary")
    views = read_model.get("views")
    if not isinstance(summary, Mapping) or not isinstance(views, Mapping):
        return None
    content = views.get(view)
    if not isinstance(content, Mapping):
        return None
    return {
        "summary": {
            "record_count": _number(summary.get("record_count")),
            "platform_count": _number(summary.get("platform_count")),
        },
        "content": dict(content),
    }


def build_semantic_workspace_projection(
    artifact: Mapping[str, Any],
    *,
    filters: Mapping[str, Any] | None = None,
    page: int = 1,
    page_size: int = _WORKSPACE_TRACEABLE_PAGE_SIZE,
) -> dict[str, Any]:
    """Build one linked, bounded Semantic Evidence Workspace projection.

    The projection keeps the joint semantic fields needed by the analyst
    workspace, but it never transfers the complete artifact ``layers`` to the
    browser. Each request contains aggregate facets, bounded cross-facet
    relations, and one page of traceable records only.
    """
    normalized_filters = _normalize_workspace_filters(filters)
    items = list(_filtered_semantic_items(artifact, normalized_filters))
    summary = _summary_from_items(items)
    keyword_counts: Counter[str] = Counter()
    sentiment_counts: Counter[str] = Counter()
    stance_counts: Counter[str] = Counter()
    topic_counts: Counter[str] = Counter()
    entity_groups: dict[str, Counter[str]] = defaultdict(Counter)
    time_counts: Counter[str] = Counter()
    platform_counts: Counter[str] = Counter()

    for _layer, item in items:
        keyword_counts.update(_nested_texts(item.get("keywords"), key="term"))
        sentiment_counts.update([_nested_label(item.get("sentiment"))])
        stance_counts.update([_nested_label(item.get("stance"))])
        topic_counts.update(_nested_texts(item.get("topics"), key="label"))
        time_counts.update([_record_date(item)])
        platform_counts.update([_text(item.get("platform"), default="unknown")])
        _accumulate_entity_groups(entity_groups, item)

    actual_page, traceable_rows = _paged_traceable_rows(
        items,
        page=max(1, page),
        page_size=max(1, page_size),
    )
    return {
        "summary": summary,
        "content": {
            "evidence": {
                "keywords": _count_rows(keyword_counts, limit=_KEYWORD_LIMIT),
                "sentiment": _count_rows(sentiment_counts),
                "stance": _count_rows(stance_counts),
            },
            "clusters": {
                "topics": _count_rows(topic_counts, limit=_TOPIC_LIMIT),
                "communities": _community_rows(artifact),
            },
            "entities": _entity_content_from_groups(entity_groups),
            "temporal": {
                "time_slices": _count_rows(time_counts),
                "platforms": _count_rows(platform_counts),
            },
            "relations": _relationship_index(items),
            "traceable": {
                "items": traceable_rows,
                "page": actual_page,
                "page_size": max(1, page_size),
                "total": len(items),
            },
        },
    }


def read_semantic_workspace_read_model(
    read_model: Mapping[str, Any],
    *,
    expected_source_artifact_sha256: str,
) -> dict[str, Any] | None:
    """Read the unfiltered workspace projection from a verified v2 read model."""
    if _text(read_model.get("schema")) != SEMANTIC_PAGE_READ_MODEL_SCHEMA:
        return None
    if _text(read_model.get("source_artifact_sha256")) != _text(expected_source_artifact_sha256):
        return None
    if not _text(read_model.get("snapshot_fingerprint")):
        return None
    workspace = read_model.get("workspace")
    if not isinstance(workspace, Mapping):
        return None
    summary = workspace.get("summary")
    content = workspace.get("content")
    if not isinstance(summary, Mapping) or not isinstance(content, Mapping):
        return None
    return {
        "summary": {
            "record_count": _number(summary.get("record_count")),
            "platform_count": _number(summary.get("platform_count")),
        },
        "content": dict(content),
    }


def _semantic_items(artifact: Mapping[str, Any]) -> Iterable[tuple[str, Mapping[str, Any]]]:
    layers = artifact.get("layers")
    if not isinstance(layers, Mapping):
        return
    for layer in ("posts", "comments"):
        records = layers.get(layer)
        if not isinstance(records, list):
            continue
        for item in records:
            if isinstance(item, Mapping):
                yield layer, item


def _filtered_semantic_items(
    artifact: Mapping[str, Any],
    filters: Mapping[str, Any],
) -> Iterable[tuple[str, Mapping[str, Any]]]:
    for layer, item in _semantic_items(artifact):
        if _item_matches_workspace_filters(layer, item, filters):
            yield layer, item


def _normalize_workspace_filters(filters: Mapping[str, Any] | None) -> dict[str, Any]:
    source = filters if isinstance(filters, Mapping) else {}
    layer = _text(source.get("layer"), default="all")
    platforms_source = source.get("platforms")
    if isinstance(platforms_source, str):
        platforms = [_text(value) for value in platforms_source.split(",")]
    elif isinstance(platforms_source, Iterable) and not isinstance(platforms_source, (str, bytes)):
        platforms = [_text(value) for value in platforms_source]
    else:
        platforms = []
    return {
        "layer": layer if layer in {"all", "posts", "comments"} else "all",
        "platforms": frozenset(platform for platform in platforms if platform),
        "date": _text(source.get("date")) or None,
        "keyword": _text(source.get("keyword")) or None,
        "topic": _text(source.get("topic")) or None,
        "sentiment": _text(source.get("sentiment")) or None,
        "stance": _text(source.get("stance")) or None,
        "entity": _text(source.get("entity")) or None,
    }


def _item_matches_workspace_filters(
    layer: str,
    item: Mapping[str, Any],
    filters: Mapping[str, Any],
) -> bool:
    if filters["layer"] != "all" and layer != filters["layer"]:
        return False
    platforms = filters["platforms"]
    if platforms and _text(item.get("platform"), default="unknown") not in platforms:
        return False
    if filters["date"] and _record_date(item) != filters["date"]:
        return False
    if filters["keyword"] and filters["keyword"] not in _nested_texts(item.get("keywords"), key="term"):
        return False
    if filters["topic"] and filters["topic"] not in _nested_texts(item.get("topics"), key="label"):
        return False
    if filters["sentiment"] and _nested_label(item.get("sentiment")) != filters["sentiment"]:
        return False
    if filters["stance"] and _nested_label(item.get("stance")) != filters["stance"]:
        return False
    if filters["entity"] and filters["entity"] not in _entity_keys(item):
        return False
    return True


def _summary_from_items(items: Iterable[tuple[str, Mapping[str, Any]]]) -> dict[str, int]:
    summary = _empty_summary()
    for _layer, item in items:
        _accumulate_summary(summary, item)
    return _finalize_summary(summary)


def _accumulate_entity_groups(groups: dict[str, Counter[str]], item: Mapping[str, Any]) -> None:
    entities = item.get("entities")
    if not isinstance(entities, list):
        return
    for entity in entities:
        if not isinstance(entity, Mapping):
            continue
        text = _text(entity.get("text"))
        if text:
            groups[_text(entity.get("label"), default="OTHER")][text] += 1


def _entity_rows(item: Mapping[str, Any]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    entities = item.get("entities")
    if not isinstance(entities, list):
        return rows
    for entity in entities:
        if not isinstance(entity, Mapping):
            continue
        text = _text(entity.get("text"))
        if not text:
            continue
        label = _text(entity.get("label"), default="OTHER")
        rows.append({"key": f"{label}:{text}", "text": text, "label": label})
    return rows


def _entity_keys(item: Mapping[str, Any]) -> list[str]:
    return [row["key"] for row in _entity_rows(item)]


def _record_date(item: Mapping[str, Any]) -> str:
    timestamp = _text(item.get("timestamp"))
    return timestamp[:10] if len(timestamp) >= 10 else "unknown"


def _paged_traceable_rows(
    items: list[tuple[str, Mapping[str, Any]]],
    *,
    page: int,
    page_size: int,
) -> tuple[int, list[dict[str, Any]]]:
    total = len(items)
    max_page = max(1, (total + page_size - 1) // page_size)
    actual_page = page if page <= max_page else 1
    start = (actual_page - 1) * page_size
    stop = start + page_size
    return actual_page, [
        _workspace_traceable_row(layer, item, index)
        for index, (layer, item) in enumerate(items[start:stop], start=start)
    ]


def _workspace_traceable_row(layer: str, item: Mapping[str, Any], index: int) -> dict[str, Any]:
    row = _traceable_row(layer, item, index)
    text = row["text"]
    row.update(
        {
            "date": _record_date(item),
            "text": text[:_TRACEABLE_TEXT_LIMIT],
            "text_truncated": len(text) > _TRACEABLE_TEXT_LIMIT,
            "keywords": _nested_texts(item.get("keywords"), key="term"),
            "topics": _nested_texts(item.get("topics"), key="label"),
            "sentiment": _nested_label(item.get("sentiment")),
            "stance": _nested_label(item.get("stance")),
            "entities": _entity_rows(item),
        }
    )
    return row


def _relationship_index(items: Iterable[tuple[str, Mapping[str, Any]]]) -> dict[str, list[dict[str, Any]]]:
    dimensions: dict[str, dict[str, dict[str, Any]]] = {
        "keywords": {},
        "topics": {},
        "entities": {},
        "platforms": {},
        "time_slices": {},
    }
    for _layer, item in items:
        values = {
            "keywords": [(value, value, "") for value in _nested_texts(item.get("keywords"), key="term")],
            "topics": [(value, value, "") for value in _nested_texts(item.get("topics"), key="label")],
            "entities": [
                (entity["key"], entity["text"], entity["label"])
                for entity in _entity_rows(item)
            ],
            "platforms": [(_text(item.get("platform"), default="unknown"), _text(item.get("platform"), default="unknown"), "")],
            "time_slices": [(_record_date(item), _record_date(item), "")],
        }
        for dimension, entries in values.items():
            for key, label, entity_type in entries:
                _accumulate_relation(dimensions[dimension], key, label, entity_type, item)
    return {
        dimension: _relationship_rows(rows)
        for dimension, rows in dimensions.items()
    }


def _accumulate_relation(
    rows: dict[str, dict[str, Any]],
    key: str,
    label: str,
    entity_type: str,
    item: Mapping[str, Any],
) -> None:
    row = rows.setdefault(
        key,
        {
            "key": key,
            "label": label,
            "type": entity_type or None,
            "count": 0,
            "sentiment": Counter(),
            "stance": Counter(),
            "topics": Counter(),
            "keywords": Counter(),
            "entities": Counter(),
            "platforms": Counter(),
            "time_slices": Counter(),
        },
    )
    row["count"] += 1
    row["sentiment"].update([_nested_label(item.get("sentiment"))])
    row["stance"].update([_nested_label(item.get("stance"))])
    row["topics"].update(_nested_texts(item.get("topics"), key="label"))
    row["keywords"].update(_nested_texts(item.get("keywords"), key="term"))
    row["entities"].update(_entity_keys(item))
    row["platforms"].update([_text(item.get("platform"), default="unknown")])
    row["time_slices"].update([_record_date(item)])


def _relationship_rows(rows: Mapping[str, Mapping[str, Any]]) -> list[dict[str, Any]]:
    ordered = sorted(rows.values(), key=lambda row: (-_number(row.get("count")), _text(row.get("label"))))
    result = []
    for row in ordered[:_RELATION_FACET_LIMIT]:
        result.append(
            {
                "key": _text(row.get("key")),
                "label": _text(row.get("label")),
                "type": _text(row.get("type")) or None,
                "count": _number(row.get("count")),
                "sentiment": _count_rows(row["sentiment"], limit=_RELATION_DISTRIBUTION_LIMIT),
                "stance": _count_rows(row["stance"], limit=_RELATION_DISTRIBUTION_LIMIT),
                "topics": _count_rows(row["topics"], limit=_RELATION_DISTRIBUTION_LIMIT),
                "keywords": _count_rows(row["keywords"], limit=_RELATION_DISTRIBUTION_LIMIT),
                "entities": _count_rows(row["entities"], limit=_RELATION_DISTRIBUTION_LIMIT),
                "platforms": _count_rows(row["platforms"], limit=_RELATION_DISTRIBUTION_LIMIT),
                "time_slices": _count_rows(row["time_slices"], limit=_RELATION_DISTRIBUTION_LIMIT),
            }
        )
    return result


def _evidence_projection(artifact: Mapping[str, Any]) -> tuple[dict[str, int], dict[str, list[dict[str, Any]]]]:
    keyword_counts: Counter[str] = Counter()
    sentiment_counts: Counter[str] = Counter()
    stance_counts: Counter[str] = Counter()
    summary = _empty_summary()
    for _layer, item in _semantic_items(artifact):
        _accumulate_summary(summary, item)
        keyword_counts.update(_nested_texts(item.get("keywords"), key="term"))
        sentiment_counts.update([_nested_label(item.get("sentiment"))])
        stance_counts.update([_nested_label(item.get("stance"))])
    return _finalize_summary(summary), {
        "keywords": _count_rows(keyword_counts, limit=_KEYWORD_LIMIT),
        "sentiment": _count_rows(sentiment_counts),
        "stance": _count_rows(stance_counts),
    }


def _cluster_projection(artifact: Mapping[str, Any]) -> tuple[dict[str, int], dict[str, list[dict[str, Any]]]]:
    topic_counts: Counter[str] = Counter()
    summary = _empty_summary()
    for _layer, item in _semantic_items(artifact):
        _accumulate_summary(summary, item)
        topic_counts.update(_nested_texts(item.get("topics"), key="label"))
    return _finalize_summary(summary), {
        "topics": _count_rows(topic_counts, limit=_TOPIC_LIMIT),
        "communities": _community_rows(artifact),
    }


def _entity_projection(artifact: Mapping[str, Any]) -> tuple[dict[str, int], dict[str, list[dict[str, Any]]]]:
    groups: dict[str, Counter[str]] = defaultdict(Counter)
    summary = _empty_summary()
    for _layer, item in _semantic_items(artifact):
        _accumulate_summary(summary, item)
        entities = item.get("entities")
        if not isinstance(entities, list):
            continue
        for entity in entities:
            if not isinstance(entity, Mapping):
                continue
            text = _text(entity.get("text"))
            if text:
                groups[_text(entity.get("label"), default="OTHER")][text] += 1
    return _finalize_summary(summary), _entity_content_from_groups(groups)


def _compile_static_page_views(artifact: Mapping[str, Any]) -> tuple[dict[str, int], dict[str, dict[str, Any]]]:
    """Compile all aggregate views in one pass while an analysis stage finishes."""
    keyword_counts: Counter[str] = Counter()
    sentiment_counts: Counter[str] = Counter()
    stance_counts: Counter[str] = Counter()
    topic_counts: Counter[str] = Counter()
    entity_groups: dict[str, Counter[str]] = defaultdict(Counter)
    summary = _empty_summary()

    for _layer, item in _semantic_items(artifact):
        _accumulate_summary(summary, item)
        keyword_counts.update(_nested_texts(item.get("keywords"), key="term"))
        sentiment_counts.update([_nested_label(item.get("sentiment"))])
        stance_counts.update([_nested_label(item.get("stance"))])
        topic_counts.update(_nested_texts(item.get("topics"), key="label"))
        entities = item.get("entities")
        if isinstance(entities, list):
            for entity in entities:
                if not isinstance(entity, Mapping):
                    continue
                text = _text(entity.get("text"))
                if text:
                    entity_groups[_text(entity.get("label"), default="OTHER")][text] += 1

    return _finalize_summary(summary), {
        "evidence": {
            "keywords": _count_rows(keyword_counts, limit=_KEYWORD_LIMIT),
            "sentiment": _count_rows(sentiment_counts),
            "stance": _count_rows(stance_counts),
        },
        "clusters": {
            "topics": _count_rows(topic_counts, limit=_TOPIC_LIMIT),
            "communities": _community_rows(artifact),
        },
        "entities": _entity_content_from_groups(entity_groups),
        "temporal": _temporal_content(artifact),
    }


def _entity_content_from_groups(groups: Mapping[str, Counter[str]]) -> dict[str, list[dict[str, Any]]]:
    rows = []
    for entity_type, counts in groups.items():
        rows.append(
            {
                "type": entity_type,
                "total": len(counts),
                "items": _count_rows(counts, limit=_ENTITY_GROUP_LIMIT),
            }
        )
    return {
        "groups": sorted(
            rows,
            key=lambda item: (
                -sum(int(entry["count"]) for entry in item["items"]),
                str(item["type"]),
            ),
        )
    }


def _temporal_content(artifact: Mapping[str, Any]) -> dict[str, list[dict[str, Any]]]:
    cross_analysis = artifact.get("cross_analysis")
    cross = cross_analysis if isinstance(cross_analysis, Mapping) else {}
    return {
        "time_slices": _slice_rows(cross.get("time_slices"), key="date"),
        "platforms": _slice_rows(cross.get("platform_slices"), key="platform"),
    }


def _verifiable_projection(
    artifact: Mapping[str, Any], *, page: int, page_size: int
) -> tuple[dict[str, int], dict[str, Any]]:
    summary = _empty_summary()
    total = 0
    for _layer, item in _semantic_items(artifact):
        total += 1
        _accumulate_summary(summary, item)
    max_page = max(1, (total + page_size - 1) // page_size)
    actual_page = page if page <= max_page else 1
    start = (actual_page - 1) * page_size
    stop = start + page_size
    rows = []
    for index, (layer, item) in enumerate(_semantic_items(artifact)):
        if index < start:
            continue
        if index >= stop:
            break
        rows.append(_traceable_row(layer, item, index))
    return _finalize_summary(summary), {
        "items": rows,
        "page": actual_page,
        "page_size": page_size,
        "total": total,
    }


def _artifact_summary(artifact: Mapping[str, Any]) -> dict[str, int]:
    summary = _empty_summary()
    for _layer, item in _semantic_items(artifact):
        _accumulate_summary(summary, item)
    return _finalize_summary(summary)


def _empty_summary() -> dict[str, Any]:
    return {"record_count": 0, "platforms": set()}


def _accumulate_summary(summary: dict[str, Any], item: Mapping[str, Any]) -> None:
    summary["record_count"] += 1
    platforms = summary["platforms"]
    if isinstance(platforms, set):
        platforms.add(_text(item.get("platform"), default="unknown"))


def _finalize_summary(summary: Mapping[str, Any]) -> dict[str, int]:
    platforms = summary.get("platforms")
    return {
        "record_count": _number(summary.get("record_count")),
        "platform_count": len(platforms) if isinstance(platforms, set) else 0,
    }


def _community_rows(artifact: Mapping[str, Any]) -> list[dict[str, Any]]:
    cross_analysis = artifact.get("cross_analysis")
    cross = cross_analysis if isinstance(cross_analysis, Mapping) else {}
    source = cross.get("community_slices")
    if not isinstance(source, list):
        return []
    rows = []
    for item in source:
        if not isinstance(item, Mapping):
            continue
        community_id = _text(item.get("community_id"))
        if not community_id:
            continue
        rows.append(
            {
                "community_id": community_id,
                "member_count": _number(item.get("member_count")),
                "item_count": _number(item.get("item_count")),
                "topics": _nested_count_rows(item.get("top_topics"), key="label", limit=3),
            }
        )
    return sorted(rows, key=lambda item: (-int(item["item_count"]), str(item["community_id"])))[:_COMMUNITY_LIMIT]


def _slice_rows(value: Any, *, key: str) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    rows = []
    for item in value:
        if not isinstance(item, Mapping):
            continue
        label = _text(item.get(key))
        count = _number(item.get("count"))
        if label:
            rows.append({"key": label, "label": label, "count": count})
    return sorted(rows, key=lambda item: str(item["label"]))


def _traceable_row(layer: str, item: Mapping[str, Any], index: int) -> dict[str, Any]:
    item_id = _text(item.get("id"), default=str(index))
    platform = _text(item.get("platform"), default="unknown")
    item_type = "post" if layer == "posts" else "comment"
    return {
        "id": item_id,
        "layer": layer,
        "platform": platform,
        "timestamp": _text(item.get("timestamp"), default="unknown"),
        "text": _text(item.get("text")),
        "source_url": _text(item.get("source_url") or item.get("sourceUrl") or item.get("url")) or None,
        "evidence_ref": f"{platform}:{item_type}:{item_id}",
    }


def _count_rows(counts: Counter[str], *, limit: int | None = None) -> list[dict[str, Any]]:
    ordered = sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    if limit is not None:
        ordered = ordered[:limit]
    return [{"key": label, "label": label, "count": count} for label, count in ordered if label]


def _nested_count_rows(value: Any, *, key: str, limit: int) -> list[dict[str, Any]]:
    counts: Counter[str] = Counter()
    if isinstance(value, list):
        for item in value:
            if isinstance(item, Mapping):
                label = _text(item.get(key))
                if label:
                    counts[label] += _number(item.get("count")) or 1
    return _count_rows(counts, limit=limit)


def _nested_texts(value: Any, *, key: str) -> list[str]:
    if not isinstance(value, list):
        return []
    return [_text(item.get(key)) for item in value if isinstance(item, Mapping) and _text(item.get(key))]


def _nested_label(value: Any) -> str:
    return _text(value.get("label"), default="unknown") if isinstance(value, Mapping) else "unknown"


def _artifact_snapshot_fingerprint(artifact: Mapping[str, Any]) -> str:
    manifest = artifact.get("embedding_manifest")
    return _text(manifest.get("snapshot_fingerprint")) if isinstance(manifest, Mapping) else ""


def _text(value: Any, *, default: str = "") -> str:
    text = str(value or "").strip()
    return text or default


def _number(value: Any) -> int:
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return 0


__all__ = [
    "SEMANTIC_PAGE_READ_MODEL_SCHEMA",
    "SEMANTIC_PAGE_VIEWS",
    "SEMANTIC_STATIC_PAGE_VIEWS",
    "SemanticPageView",
    "build_semantic_page_projection",
    "build_semantic_page_read_model",
    "build_semantic_workspace_projection",
    "read_semantic_page_read_model",
    "read_semantic_workspace_read_model",
]
