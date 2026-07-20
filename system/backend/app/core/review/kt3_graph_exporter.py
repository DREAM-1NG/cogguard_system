"""KT3 heterogeneous graph export.

This module exports the current KT3 runtime evidence into a graph-native schema
that can be consumed by future HGT / Graph Transformer / temporal graph models.
It is a deterministic graph export, not a trained graph encoder.
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any
from urllib.parse import quote
from urllib.parse import urlparse


GRAPH_ARTIFACT_SCHEMA_VERSION = "kt3-graph-export-v1"


def export_kt3_heterogeneous_graph(
    *,
    post_semantics: dict[str, Any] | None,
    kt3_harmfulness: dict[str, Any] | None,
    coordination: dict[str, Any] | None = None,
    propagation: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Export KT3 post/account/community evidence as a heterogeneous graph."""
    post_semantics = post_semantics or {}
    kt3_harmfulness = kt3_harmfulness or {}
    coordination = coordination or {}
    propagation = propagation or {}

    nodes: dict[str, dict[str, Any]] = {}
    edges: dict[str, dict[str, Any]] = {}

    accounts = _as_list(_get(kt3_harmfulness, "user_level", "accounts"))
    communities = _as_list(_get(kt3_harmfulness, "community_level", "communities"))
    posts = _semantic_posts(post_semantics)

    for community in communities:
        community_id = _text(community.get("community_id")) or "community_all"
        _add_node(
            nodes,
            node_id=f"community:{community_id}",
            node_type="community",
            attrs={
                "community_id": community_id,
                "member_count": _safe_int(community.get("member_count")),
                "harmful_posts": _safe_int(_get(community, "risk_summary", "harmful_posts")),
                "harmful_accounts": _safe_int(_get(community, "risk_summary", "harmful_accounts")),
                "amplification_score": _safe_float(_get(community, "risk_summary", "amplification_score")),
                "dominant_harm_types": _get(community, "risk_summary", "dominant_harm_types") or {},
                "subgroup_roles": community.get("subgroup_roles") or {},
                "risk_flags": community.get("risk_flags") or {},
            },
        )

    for account in accounts:
        account_id = _text(account.get("account_id"))
        if not account_id:
            continue
        community_id = _text(account.get("community_id")) or "community_all"
        _add_node(
            nodes,
            node_id=f"account:{account_id}",
            node_type="account",
            attrs={
                "account_id": account_id,
                "author_name": account.get("author_name"),
                "community_id": community_id,
                "harmful_posts": _safe_int(_get(account, "risk_summary", "harmful_posts")),
                "harmful_ratio": _safe_float(_get(account, "risk_summary", "harmful_ratio")),
                "persistence_score": _safe_float(_get(account, "risk_summary", "persistence_score")),
                "trajectory": _get(account, "risk_summary", "trajectory"),
                "harm_types": _get(account, "risk_summary", "harm_types") or {},
                "harmful_roles": _as_list(_get(account, "role_profile", "harmful_roles")),
                "propagation_roles": _as_list(_get(account, "role_profile", "propagation_roles")),
                "risk_flags": account.get("risk_profile_flags") or {},
            },
        )
        _add_edge(
            edges,
            source=f"account:{account_id}",
            target=f"community:{community_id}",
            edge_type="member_of",
            attrs={"source": "kt3_user_level"},
        )

    for post in posts:
        post_id = _text(post.get("post_id"))
        if not post_id:
            continue
        author_id = _text(post.get("author_id"))
        claim = post.get("primary_claim") or {}
        claim_id = _text(claim.get("claim_id"))
        harm = post.get("harmfulness") or {}
        stance = post.get("stance") or {}
        _add_node(
            nodes,
            node_id=f"post:{post_id}",
            node_type="post",
            attrs={
                "post_id": post_id,
                "author_id": author_id,
                "event_id": post.get("event_id"),
                "platform": post.get("platform"),
                "excerpt": _text(post.get("excerpt"))[:240],
                "modalities": _as_list(post.get("modalities")),
                "harm_label": harm.get("label"),
                "harm_score": _safe_float(harm.get("score")),
                "harm_types": _as_list(harm.get("types")),
                "stance_label": stance.get("label"),
                "stance_confidence": _safe_float(stance.get("confidence")),
                "needs_review": bool(harm.get("abstain")) or bool(stance.get("abstain")) or not claim_id,
            },
        )
        if author_id:
            _add_edge(
                edges,
                source=f"account:{author_id}",
                target=f"post:{post_id}",
                edge_type="authored",
                attrs={"source": "post_semantics"},
            )
        if claim_id:
            _add_claim_node(nodes, claim_id, claim.get("claim_text"))
            _add_edge(
                edges,
                source=f"post:{post_id}",
                target=f"claim:{claim_id}",
                edge_type="mentions_claim",
                attrs={
                    "score": _safe_float(claim.get("score")),
                    "stance": stance.get("label"),
                    "source": "post_semantics.primary_claim",
                },
            )
            if author_id:
                _add_edge(
                    edges,
                    source=f"account:{author_id}",
                    target=f"claim:{claim_id}",
                    edge_type="engages_claim",
                    attrs={
                        "stance": stance.get("label"),
                        "harm_label": harm.get("label"),
                    },
                )
        _add_post_object_nodes(nodes, edges, post)

    for claim in _as_list(post_semantics.get("claim_candidates")):
        claim_id = _text(claim.get("claim_id"))
        if claim_id:
            _add_claim_node(nodes, claim_id, claim.get("claim_text"), extra_attrs=claim)

    for community in communities:
        community_id = _text(community.get("community_id")) or "community_all"
        for claim in _as_list(community.get("claims_coverage")):
            claim_id = _text(claim.get("claim_id"))
            if not claim_id:
                continue
            _add_claim_node(nodes, claim_id, claim.get("claim_text"))
            _add_edge(
                edges,
                source=f"community:{community_id}",
                target=f"claim:{claim_id}",
                edge_type="community_focuses_claim",
                attrs={
                    "linked_posts": _safe_int(claim.get("linked_posts")),
                    "harmful_posts": _safe_int(claim.get("harmful_posts")),
                    "linked_accounts": _safe_int(claim.get("linked_accounts")),
                },
            )

    _add_coordination_edges(nodes, edges, coordination)
    _add_propagation_edges(nodes, edges, propagation)
    _add_community_target_edges(nodes, edges)
    dropped_dangling_edges = _drop_dangling_edges(edges, nodes)

    node_list = sorted(nodes.values(), key=lambda item: item["id"])
    edge_list = sorted(edges.values(), key=lambda item: item["id"])
    node_counts = Counter(node["type"] for node in node_list)
    edge_counts = Counter(edge["type"] for edge in edge_list)

    return {
        "capability_boundary": {
            "status": "implemented_graph_export_schema",
            "trained_graph_model": False,
            "description": (
                "Exports KT3 evidence as an account-post-claim-community-target-media "
                "heterogeneous graph. It does not train or run HGT, Graph Transformer, "
                "or temporal graph models."
            ),
        },
        "schema": {
            "node_types": ["account", "post", "claim", "community", "target", "media"],
            "edge_types": [
                "authored",
                "mentions_claim",
                "engages_claim",
                "member_of",
                "community_focuses_claim",
                "post_targets",
                "account_targets",
                "community_targets",
                "post_uses_media",
                "account_shares_object",
                "co_shares_object",
                "coordinated_with",
                "propagates_to",
            ],
        },
        "summary": {
            "node_count": len(node_list),
            "edge_count": len(edge_list),
            "node_types": dict(node_counts),
            "edge_types": dict(edge_counts),
            "graph_native_ready": bool(node_list and edge_list),
            "dropped_dangling_edges": dropped_dangling_edges,
        },
        "nodes": node_list,
        "edges": edge_list,
    }


def write_kt3_graph_artifact(graph: dict[str, Any], artifact_path: str | Path) -> dict[str, Any]:
    """Write a KT3 graph JSON artifact and return an auditable manifest."""
    _validate_graph_for_consumer(graph)
    path = Path(artifact_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    payload = {
        "schema_version": GRAPH_ARTIFACT_SCHEMA_VERSION,
        "artifact_type": "kt3_heterogeneous_graph",
        "capability_boundary": {
            "status": "artifact_exported",
            "consumer_readable": True,
            "trained_graph_model": False,
        },
        "graph": graph,
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")

    return {
        "schema_version": GRAPH_ARTIFACT_SCHEMA_VERSION,
        "artifact_type": "kt3_heterogeneous_graph",
        "artifact_path": str(path),
        "artifact_exported": True,
        "consumer_readable": True,
        "export_verified": True,
        "node_count": _safe_int(_get(graph, "summary", "node_count")),
        "edge_count": _safe_int(_get(graph, "summary", "edge_count")),
        "trained_graph_model": False,
    }


def read_kt3_graph_artifact(artifact_path: str | Path) -> dict[str, Any]:
    """Read a KT3 graph JSON artifact and validate it for downstream consumers."""
    path = Path(artifact_path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema_version") != GRAPH_ARTIFACT_SCHEMA_VERSION:
        raise ValueError("Unsupported KT3 graph artifact schema version")
    if payload.get("artifact_type") != "kt3_heterogeneous_graph":
        raise ValueError("Unsupported KT3 graph artifact type")
    graph = payload.get("graph")
    if not isinstance(graph, dict):
        raise ValueError("KT3 graph artifact does not contain a graph object")
    _validate_graph_for_consumer(graph)
    return payload


def _validate_graph_for_consumer(graph: dict[str, Any]) -> None:
    if not isinstance(graph.get("schema"), dict):
        raise ValueError("KT3 graph missing schema")
    if not isinstance(graph.get("summary"), dict):
        raise ValueError("KT3 graph missing summary")
    if not isinstance(graph.get("nodes"), list):
        raise ValueError("KT3 graph nodes must be a list")
    if not isinstance(graph.get("edges"), list):
        raise ValueError("KT3 graph edges must be a list")

    node_ids = set()
    for node in graph["nodes"]:
        if not isinstance(node, dict) or not _text(node.get("id")) or not _text(node.get("type")):
            raise ValueError("KT3 graph contains an invalid node")
        node_ids.add(node["id"])

    for edge in graph["edges"]:
        if not isinstance(edge, dict) or not _text(edge.get("source")) or not _text(edge.get("target")):
            raise ValueError("KT3 graph contains an invalid edge")
        if edge["source"] not in node_ids or edge["target"] not in node_ids:
            raise ValueError("KT3 graph contains a dangling edge")

    if _safe_int(_get(graph, "summary", "node_count")) != len(graph["nodes"]):
        raise ValueError("KT3 graph node_count does not match nodes")
    if _safe_int(_get(graph, "summary", "edge_count")) != len(graph["edges"]):
        raise ValueError("KT3 graph edge_count does not match edges")


def _add_claim_node(
    nodes: dict[str, dict[str, Any]],
    claim_id: str,
    claim_text: Any,
    *,
    extra_attrs: dict[str, Any] | None = None,
) -> None:
    attrs = {
        "claim_id": claim_id,
        "claim_text": _text(claim_text)[:240],
    }
    if extra_attrs:
        attrs.update({
            "share_count": _safe_int(extra_attrs.get("share_count")),
            "account_count": _safe_int(extra_attrs.get("account_count")),
            "source": extra_attrs.get("source"),
        })
    _add_node(nodes, node_id=f"claim:{claim_id}", node_type="claim", attrs=attrs)


def _add_post_object_nodes(
    nodes: dict[str, dict[str, Any]],
    edges: dict[str, dict[str, Any]],
    post: dict[str, Any],
) -> None:
    post_id = _text(post.get("post_id"))
    author_id = _text(post.get("author_id"))
    evidence = post.get("evidence") or {}
    for media in _post_media_objects(post):
        media_id = _object_node_id("media", media["object_id"])
        _add_node(nodes, node_id=media_id, node_type="media", attrs=media)
        _add_edge(
            edges,
            source=f"post:{post_id}",
            target=media_id,
            edge_type="post_uses_media",
            attrs={"source": media.get("source"), "relation": media.get("relation")},
        )
        if author_id:
            _add_edge(
                edges,
                source=f"account:{author_id}",
                target=media_id,
                edge_type="account_shares_object",
                attrs={"source": media.get("source"), "relation": media.get("relation")},
            )

    for target in _post_target_objects(post, evidence):
        target_id = _object_node_id("target", target["target_id"])
        _add_node(nodes, node_id=target_id, node_type="target", attrs=target)
        _add_edge(
            edges,
            source=f"post:{post_id}",
            target=target_id,
            edge_type="post_targets",
            attrs={"source": target.get("source"), "relation": target.get("relation")},
        )
        if author_id:
            _add_edge(
                edges,
                source=f"account:{author_id}",
                target=target_id,
                edge_type="account_targets",
                attrs={"source": target.get("source"), "relation": target.get("relation")},
            )


def _post_media_objects(post: dict[str, Any]) -> list[dict[str, Any]]:
    objects = []
    for url in _as_list(post.get("media_urls")):
        text = _text(url)
        if not text:
            continue
        parsed = urlparse(text)
        objects.append({
            "object_id": text,
            "media_type": _media_type(text),
            "domain": parsed.netloc.lower(),
            "source": "post.media_urls",
            "relation": "post_media",
        })
    for tag in _as_list(post.get("hashtags")):
        text = _text(tag)
        if text:
            objects.append({
                "object_id": text,
                "media_type": "hashtag",
                "domain": "",
                "source": "post.hashtags",
                "relation": "hashtag_share",
            })
    for key in ("media_text", "ocr_text", "asr_text"):
        text = _text((post.get("evidence") or {}).get(key))
        if text:
            objects.append({
                "object_id": f"{key}:{text[:80]}",
                "media_type": key.replace("_text", ""),
                "domain": "",
                "source": f"post.evidence.{key}",
                "relation": "media_context",
            })
    return _dedupe_objects(objects, "object_id")


def _post_target_objects(post: dict[str, Any], evidence: dict[str, Any]) -> list[dict[str, Any]]:
    objects = []
    raw_data = post.get("raw_data") if isinstance(post.get("raw_data"), dict) else {}
    for key in ("target", "target_id", "target_account_id", "mention_target", "reply_target"):
        for value in (post.get(key), evidence.get(key), raw_data.get(key)):
            text = _text(value)
            if text:
                objects.append({
                    "target_id": text,
                    "target_type": key,
                    "source": "post.target_fields",
                    "relation": "target_reference",
                })
    return _dedupe_objects(objects, "target_id")


def _add_coordination_edges(
    nodes: dict[str, dict[str, Any]],
    edges: dict[str, dict[str, Any]],
    coordination: dict[str, Any],
) -> None:
    for edge in _as_list(_get(coordination, "network", "edges")):
        source = _text(edge.get("source") or edge.get("from") or edge.get("account_a"))
        target = _text(edge.get("target") or edge.get("to") or edge.get("account_b"))
        if not source or not target:
            continue
        _add_edge(
            edges,
            source=f"account:{source}",
            target=f"account:{target}",
            edge_type="coordinated_with",
            attrs={
                "weight": _safe_float(edge.get("weight")),
                "avg_time_delta": _safe_float(edge.get("avg_time_delta")),
                "edge_symmetry_score": _safe_float(edge.get("edge_symmetry_score")),
                "relation": edge.get("relation"),
                "object_id": edge.get("object_id"),
                "source": "coordination.network",
            },
        )
        for obj in _coordination_objects(edge):
            object_type = obj["node_type"]
            object_id = _object_node_id(object_type, obj["object_id"])
            _add_node(nodes, node_id=object_id, node_type=object_type, attrs=obj)
            for account_id in (source, target):
                _add_edge(
                    edges,
                    source=f"account:{account_id}",
                    target=object_id,
                    edge_type="account_targets" if object_type == "target" else "account_shares_object",
                    attrs={
                        "relation": obj.get("relation"),
                        "object_id": obj.get("object_id"),
                        "source": "coordination.object",
                    },
                )
            _add_edge(
                edges,
                source=f"account:{source}",
                target=f"account:{target}",
                edge_type="co_shares_object",
                attrs={
                    "relation": obj.get("relation"),
                    "object_id": obj.get("object_id"),
                    "source": "coordination.object",
                },
            )


def _coordination_objects(edge: dict[str, Any]) -> list[dict[str, Any]]:
    objects = []
    for item in _as_list(edge.get("object_instances")):
        relation = _text(item.get("relation") or edge.get("relation"))
        object_id = _text(item.get("object_id"))
        if object_id:
            objects.append(_object_attrs_for_relation(relation, object_id, source="coordination.object_instances"))
    for item in _as_list(edge.get("objects")):
        relation = _text(edge.get("relation"))
        object_id = _text(item)
        if object_id:
            objects.append(_object_attrs_for_relation(relation, object_id, source="coordination.objects"))
    relation = _text(edge.get("relation"))
    object_id = _text(edge.get("object_id"))
    if object_id:
        objects.append(_object_attrs_for_relation(relation, object_id, source="coordination.edge"))
    return _dedupe_objects(objects, "object_id")


def _object_attrs_for_relation(relation: str, object_id: str, *, source: str) -> dict[str, Any]:
    if relation in {"reply_target", "mention_target", "quote_target", "retweet_target"}:
        return {
            "node_type": "target",
            "target_id": object_id,
            "object_id": object_id,
            "target_type": relation or "coordination_target",
            "relation": relation,
            "source": source,
        }
    return {
        "node_type": "media",
        "object_id": object_id,
        "media_type": _media_type(object_id) if relation == "url_share" else relation or "shared_object",
        "domain": urlparse(object_id).netloc.lower() if object_id.startswith(("http://", "https://")) else "",
        "relation": relation or "shared_object",
        "source": source,
    }


def _add_propagation_edges(
    nodes: dict[str, dict[str, Any]],
    edges: dict[str, dict[str, Any]],
    propagation: dict[str, Any],
) -> None:
    for edge in _as_list(_get(propagation, "graph", "edges")):
        source = _text(edge.get("source"))
        target = _text(edge.get("target"))
        if not source or not target:
            continue
        _add_edge(
            edges,
            source=f"account:{source}",
            target=f"account:{target}",
            edge_type="propagates_to",
            attrs={
                "weight": _safe_float(edge.get("weight")),
                "source": "propagation.graph",
            },
        )


def _add_community_target_edges(
    nodes: dict[str, dict[str, Any]],
    edges: dict[str, dict[str, Any]],
) -> None:
    community_targets: dict[tuple[str, str], dict[str, Any]] = {}
    for edge in edges.values():
        if edge["type"] != "account_targets":
            continue
        account_node = nodes.get(edge["source"])
        if not account_node:
            continue
        community_id = _text(account_node.get("attrs", {}).get("community_id")) or "community_all"
        community_node_id = f"community:{community_id}"
        target_node_id = edge["target"]
        if community_node_id not in nodes or target_node_id not in nodes:
            continue
        key = (community_node_id, target_node_id)
        current = community_targets.setdefault(
            key,
            {"accounts": set(), "relations": set()},
        )
        current["accounts"].add(edge["source"].removeprefix("account:"))
        relation = _text(edge.get("attrs", {}).get("relation"))
        if relation:
            current["relations"].add(relation)

    for (community_node_id, target_node_id), attrs in community_targets.items():
        accounts = sorted(attrs["accounts"])
        relations = sorted(attrs["relations"])
        _add_edge(
            edges,
            source=community_node_id,
            target=target_node_id,
            edge_type="community_targets",
            attrs={
                "linked_accounts": len(accounts),
                "account_sample": accounts[:8],
                "relations": relations,
                "source": "kt3_graph_exporter.account_targets",
            },
        )


def _drop_dangling_edges(edges: dict[str, dict[str, Any]], nodes: dict[str, dict[str, Any]]) -> int:
    dangling = [
        edge_id
        for edge_id, edge in edges.items()
        if edge["source"] not in nodes or edge["target"] not in nodes
    ]
    for edge_id in dangling:
        edges.pop(edge_id, None)
    return len(dangling)


def _object_node_id(node_type: str, object_id: Any) -> str:
    normalized = _text(object_id)
    if not normalized:
        return f"{node_type}:"
    return f"{node_type}:{quote(normalized, safe='')}"


def _media_type(object_id: Any) -> str:
    text = _text(object_id).lower()
    path = urlparse(text).path if text.startswith(("http://", "https://")) else text
    if text.startswith("#"):
        return "hashtag"
    if any(path.endswith(ext) for ext in (".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".svg")):
        return "image"
    if any(path.endswith(ext) for ext in (".mp4", ".mov", ".mkv", ".avi", ".webm", ".m3u8")):
        return "video"
    if text.startswith(("http://", "https://")):
        return "url"
    return "shared_object"


def _dedupe_objects(objects: list[dict[str, Any]], key: str) -> list[dict[str, Any]]:
    seen: set[str] = set()
    deduped: list[dict[str, Any]] = []
    for item in objects:
        value = _text(item.get(key))
        if not value or value in seen:
            continue
        seen.add(value)
        deduped.append(item)
    return deduped


def _add_node(
    nodes: dict[str, dict[str, Any]],
    *,
    node_id: str,
    node_type: str,
    attrs: dict[str, Any],
) -> None:
    if not node_id or node_id.endswith(":"):
        return
    current = nodes.setdefault(node_id, {"id": node_id, "type": node_type, "attrs": {}})
    current["attrs"].update({key: value for key, value in attrs.items() if value is not None})


def _add_edge(
    edges: dict[str, dict[str, Any]],
    *,
    source: str,
    target: str,
    edge_type: str,
    attrs: dict[str, Any],
) -> None:
    if not source or not target or source.endswith(":") or target.endswith(":"):
        return
    suffix = ""
    if edge_type == "co_shares_object":
        object_id = _text(attrs.get("object_id"))
        suffix = f"#{quote(object_id, safe='')}" if object_id else ""
    edge_id = f"{edge_type}:{source}->{target}{suffix}"
    current = edges.setdefault(
        edge_id,
        {"id": edge_id, "source": source, "target": target, "type": edge_type, "attrs": {}},
    )
    current["attrs"].update({key: value for key, value in attrs.items() if value is not None})


def _semantic_posts(post_semantics: dict[str, Any]) -> list[dict[str, Any]]:
    posts = post_semantics.get("aggregation_posts")
    if isinstance(posts, list):
        return posts
    posts = post_semantics.get("posts")
    return posts if isinstance(posts, list) else []


def _get(value: dict[str, Any] | None, *path: str) -> Any:
    current: Any = value or {}
    for key in path:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _text(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def _safe_float(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _safe_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0
