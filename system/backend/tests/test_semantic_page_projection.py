from __future__ import annotations

from app.core.semantic.page_projection import (
    build_semantic_page_projection,
    build_semantic_page_read_model,
    build_semantic_workspace_projection,
    read_semantic_page_read_model,
    read_semantic_workspace_read_model,
)


def _artifact() -> dict[str, object]:
    return {
        "layers": {
            "posts": [
                {
                    "id": "post-1",
                    "platform": "weibo",
                    "timestamp": "2026-08-17T08:00:00+00:00",
                    "text": "第一条可追溯内容",
                    "source_url": "https://example.test/post-1",
                    "keywords": [{"term": "事件"}, {"term": "核验"}],
                    "topics": [{"label": "事件进展"}],
                    "sentiment": {"label": "negative"},
                    "stance": {"label": "contradiction"},
                    "entities": [{"text": "北京", "label": "LOC"}],
                },
                {
                    "id": "post-2",
                    "platform": "xhs",
                    "timestamp": "2026-08-17T09:00:00+00:00",
                    "text": "第二条可追溯内容",
                    "keywords": [{"term": "事件"}],
                    "topics": [{"label": "事件进展"}],
                    "sentiment": {"label": "neutral"},
                    "stance": {"label": "neutral"},
                    "entities": [{"text": "北京", "label": "LOC"}],
                },
            ],
            "comments": [
                {
                    "id": "comment-1",
                    "platform": "weibo",
                    "timestamp": "2026-08-17T10:00:00+00:00",
                    "text": "第三条可追溯内容",
                    "keywords": [{"term": "核验"}],
                    "topics": [{"label": "回应"}],
                    "sentiment": {"label": "positive"},
                    "stance": {"label": "entailment"},
                    "entities": [{"text": "张三", "label": "PER"}],
                }
            ],
        },
        "cross_analysis": {
            "time_slices": [
                {"date": "2026-08-17", "count": 3},
            ],
            "platform_slices": [
                {"platform": "weibo", "count": 2},
                {"platform": "xhs", "count": 1},
            ],
            "community_slices": [
                {
                    "community_id": "community-1",
                    "member_count": 2,
                    "item_count": 3,
                    "top_topics": [{"label": "事件进展", "count": 2}],
                }
            ],
        },
    }


def test_evidence_projection_returns_aggregates_without_full_layers():
    projection = build_semantic_page_projection(_artifact(), view="evidence")

    assert projection["summary"] == {"record_count": 3, "platform_count": 2}
    assert projection["content"] == {
        "keywords": [
            {"key": "事件", "label": "事件", "count": 2},
            {"key": "核验", "label": "核验", "count": 2},
        ],
        "sentiment": [
            {"key": "negative", "label": "negative", "count": 1},
            {"key": "neutral", "label": "neutral", "count": 1},
            {"key": "positive", "label": "positive", "count": 1},
        ],
        "stance": [
            {"key": "contradiction", "label": "contradiction", "count": 1},
            {"key": "entailment", "label": "entailment", "count": 1},
            {"key": "neutral", "label": "neutral", "count": 1},
        ],
    }
    assert "layers" not in projection["content"]


def test_verifiable_projection_paginates_traceable_records_on_the_server():
    projection = build_semantic_page_projection(_artifact(), view="verifiable", page=2, page_size=2)

    assert projection["content"] == {
        "items": [
            {
                "id": "comment-1",
                "layer": "comments",
                "platform": "weibo",
                "timestamp": "2026-08-17T10:00:00+00:00",
                "text": "第三条可追溯内容",
                "source_url": None,
                "evidence_ref": "weibo:comment:comment-1",
            }
        ],
        "page": 2,
        "page_size": 2,
        "total": 3,
    }


def test_page_read_model_reuses_static_views_without_retaining_layers():
    artifact = _artifact()
    artifact["embedding_manifest"] = {"snapshot_fingerprint": "snapshot-fingerprint"}

    read_model = build_semantic_page_read_model(
        artifact,
        source_artifact_sha256="semantic-artifact-sha256",
    )

    assert "layers" not in read_model
    assert "verifiable" not in read_model["views"]
    for view in ("evidence", "clusters", "entities", "temporal"):
        assert read_semantic_page_read_model(
            read_model,
            view=view,
            expected_source_artifact_sha256="semantic-artifact-sha256",
        ) == build_semantic_page_projection(artifact, view=view)

    assert read_semantic_page_read_model(
        read_model,
        view="evidence",
        expected_source_artifact_sha256="different-source-sha256",
    ) is None
    assert read_semantic_page_read_model(
        read_model,
        view="verifiable",
        expected_source_artifact_sha256="semantic-artifact-sha256",
    ) is None


def test_workspace_projection_preserves_bounded_entity_to_signal_relations():
    projection = build_semantic_workspace_projection(
        _artifact(),
        filters={"entity": "LOC:北京"},
        page=1,
        page_size=40,
    )

    assert projection["summary"] == {"record_count": 2, "platform_count": 2}
    assert projection["content"]["evidence"]["sentiment"] == [
        {"key": "negative", "label": "negative", "count": 1},
        {"key": "neutral", "label": "neutral", "count": 1},
    ]
    assert projection["content"]["clusters"]["topics"] == [
        {"key": "事件进展", "label": "事件进展", "count": 2},
    ]
    entity_relation = projection["content"]["relations"]["entities"][0]
    assert entity_relation["key"] == "LOC:北京"
    assert entity_relation["sentiment"] == projection["content"]["evidence"]["sentiment"]
    assert entity_relation["stance"] == [
        {"key": "contradiction", "label": "contradiction", "count": 1},
        {"key": "neutral", "label": "neutral", "count": 1},
    ]
    record = projection["content"]["traceable"]["items"][0]
    assert record["entities"] == [{"key": "LOC:北京", "text": "北京", "label": "LOC"}]
    assert record["topics"] == ["事件进展"]
    assert "layers" not in projection["content"]


def test_workspace_read_model_keeps_one_initial_page_without_raw_layers():
    artifact = _artifact()
    artifact["embedding_manifest"] = {"snapshot_fingerprint": "snapshot-fingerprint"}
    read_model = build_semantic_page_read_model(
        artifact,
        source_artifact_sha256="semantic-artifact-sha256",
    )

    workspace = read_semantic_workspace_read_model(
        read_model,
        expected_source_artifact_sha256="semantic-artifact-sha256",
    )

    assert workspace is not None
    assert workspace["content"]["traceable"]["total"] == 3
    assert len(workspace["content"]["traceable"]["items"]) == 3
    assert "layers" not in read_model
    assert "layers" not in workspace["content"]
