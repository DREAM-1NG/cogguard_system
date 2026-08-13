import json

from app.core.analysis.semantic_enrichment import (
    SemanticEnrichmentEngine,
    SemanticScope,
    build_semantic_input_hash,
    build_semantic_scope_hash,
    filter_semantic_records,
    merge_semantics_into_case_projection,
    stratify_semantic_records,
)


RECORDS = [
    {
        "id": "post-1",
        "record_type": "post",
        "text": "虚假消息正在扩散，请核验来源。",
        "platform": "weibo",
        "created_at": "2026-08-10T10:00:00+00:00",
        "coordination_community_id": "community-a",
        "propagation_path_id": "path-1",
    },
    {
        "id": "comment-1",
        "record_type": "comment",
        "text": "这条说法不可信，需要更多证据。",
        "platform": "weibo",
        "created_at": "2026-08-10T10:01:00+00:00",
        "coordination_community_id": "community-a",
        "propagation_path_id": "path-1",
    },
    {
        "id": "post-2",
        "record_type": "post",
        "text": "无关平台内容",
        "platform": "douyin",
        "created_at": "2026-08-10T10:02:00+00:00",
        "coordination_community_id": "community-b",
        "propagation_path_id": "path-2",
    },
]


def test_semantic_scope_filters_and_stratifies_records_deterministically():
    scope = SemanticScope(
        start_at="2026-08-10T09:00:00+00:00",
        end_at="2026-08-10T11:00:00+00:00",
        platforms=("weibo",),
        coordination_community_ids=("community-a",),
        propagation_path_ids=("path-1",),
    )

    filtered = filter_semantic_records(RECORDS, scope)
    strata = stratify_semantic_records(filtered)

    assert [record["id"] for record in strata["posts"]] == ["post-1"]
    assert [record["id"] for record in strata["comments"]] == ["comment-1"]
    assert build_semantic_scope_hash(scope) == build_semantic_scope_hash(scope)
    assert build_semantic_input_hash(filtered) == build_semantic_input_hash(list(reversed(filtered)))


def test_engine_returns_five_json_serializable_candidate_outputs_without_models():
    result = SemanticEnrichmentEngine(allow_model_loading=False).enrich(
        RECORDS,
        SemanticScope(platforms=("weibo",), coordination_community_ids=("community-a",)),
        primary_claim="该消息是真实的。",
    )

    assert set(result["outputs"]) == {"sentiment", "keywords", "topics", "entities", "stance"}
    assert result["strata"]["posts"]["count"] == 1
    assert result["strata"]["comments"]["count"] == 1
    assert result["degraded"] is True
    for output in result["outputs"].values():
        assert output["status"] == "candidate_unvalidated"
        assert output["coverage"]["record_count"] == 2
        assert output["confidence"] >= 0
        assert output["model_manifest"]
        assert output["scope_hash"] == result["scope_hash"]
        assert output["input_hash"] == result["input_hash"]
    assert result["outputs"]["stance"]["status"] == "candidate_unvalidated"
    json.dumps(result, ensure_ascii=False)


def test_missing_primary_claim_blocks_only_stance():
    result = SemanticEnrichmentEngine(allow_model_loading=False).enrich(RECORDS, SemanticScope())

    assert result["outputs"]["stance"]["status"] == "blocked_missing_primary_claim"
    assert all(
        result["outputs"][name]["status"] == "candidate_unvalidated"
        for name in ("sentiment", "keywords", "topics", "entities")
    )


def test_merge_preserves_case_values_exactly():
    projection = {
        "coordination": {"community": "unchanged"},
        "propagation": {"risk": 0.4},
        "student_review": {"verdict": "hold"},
        "teacher_review": {"verdict": "advise"},
        "preliminary_finding": "needs review",
        "canonical_verdict": "unconfirmed",
        "risk": {"level": "medium"},
    }
    semantic = {"outputs": {"keywords": {"status": "candidate_unvalidated"}}}

    merged = merge_semantics_into_case_projection(projection, semantic)

    for key, value in projection.items():
        assert merged[key] == value
    assert merged["semantic_enrichment"] == semantic
    assert "semantic_enrichment" not in projection
