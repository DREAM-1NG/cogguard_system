from __future__ import annotations

from app.core.review.graph_exporter import export_review_heterogeneous_graph


def test_graph_export_includes_post_relation_edges_from_post_fields():
    graph = export_review_heterogeneous_graph(
        post_semantics={
            "posts": [
                {"post_id": "root", "excerpt": "source post"},
                {"post_id": "reply", "in_reply_to_post_id": "root", "excerpt": "reply"},
                {"post_id": "repost", "raw_data": {"retweeted_status_id_str": "root"}},
                {"post_id": "quote", "raw_data": {"quoted_status": {"id_str": "root"}}},
            ]
        },
        review_harmfulness={},
    )

    assert {"replies_to", "reposts", "quotes"}.issubset(set(graph["schema"]["edge_types"]))
    relation_edges = {
        (edge["type"], edge["source"], edge["target"])
        for edge in graph["edges"]
        if edge["type"] in {"replies_to", "reposts", "quotes"}
    }
    assert ("replies_to", "post:reply", "post:root") in relation_edges
    assert ("reposts", "post:repost", "post:root") in relation_edges
    assert ("quotes", "post:quote", "post:root") in relation_edges
    assert graph["summary"]["edge_types"]["replies_to"] == 1
    assert graph["summary"]["edge_types"]["reposts"] == 1
    assert graph["summary"]["edge_types"]["quotes"] == 1


def test_graph_export_adds_thread_context_reply_edges_as_post_relations():
    thread_context = {
        "schema_version": "review-thread-context-v1",
        "tree_id": "tree-1",
        "root_post_id": "root",
        "nodes": [
            {"node_id": "root", "post_id": "root", "depth": 0, "is_root": True, "excerpt": "claim"},
            {"node_id": "reply", "post_id": "reply", "parent_id": "root", "depth": 1, "excerpt": "reply"},
        ],
        "edges": [
            {"source": "root", "target": "reply", "relation": "replies_to"},
        ],
    }

    graph = export_review_heterogeneous_graph(
        post_semantics={},
        review_harmfulness={},
        propagation={"thread_context": thread_context},
    )

    reply_edges = [edge for edge in graph["edges"] if edge["type"] == "replies_to"]
    assert len(reply_edges) == 1
    assert reply_edges[0]["source"] == "post:reply"
    assert reply_edges[0]["target"] == "post:root"
    assert reply_edges[0]["attrs"]["source"] == "propagation.thread_context.edges"
    assert graph["summary"]["node_types"]["post"] == 2
    assert graph["summary"]["edge_types"]["replies_to"] == 1
