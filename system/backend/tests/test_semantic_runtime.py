from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path

import numpy as np
import pytest

from app.core.analysis import TimeWindow, build_event_snapshot
from app.core.semantic.runtime import (
    MODEL_SPECS,
    ModelWeightsBlockedError,
    SemanticEnrichmentRuntime,
)


def _snapshot():
    ts = datetime(2026, 5, 21, 1, tzinfo=timezone.utc)
    return build_event_snapshot(
        event_id="trump_visit_2026_05_21",
        posts=[
            {"platform": "weibo", "post_id": "p1", "author_id": "u1", "timestamp": ts, "content": "特朗普访华 贸易 合作"},
            {"platform": "xhs", "post_id": "p2", "author_id": "u2", "timestamp": ts, "content": "特朗普访华 贸易 合作"},
        ],
        comments=[
            {"platform": "douyin", "comment_id": "c1", "author_id": "u3", "timestamp": ts, "content": "希望和平合作"},
        ],
        core_window=TimeWindow(start=datetime(2026, 5, 21, tzinfo=timezone.utc), end=datetime(2026, 5, 22, tzinfo=timezone.utc)),
        context_window=TimeWindow(start=datetime(2026, 5, 1, tzinfo=timezone.utc), end=datetime(2026, 5, 31, tzinfo=timezone.utc)),
    )


class FakeEmbedding:
    def __init__(self):
        self.calls = 0
        self.batches = []

    def encode(self, texts, **_kwargs):
        self.calls += 1
        self.batches.append(list(texts))
        return [[float(index + 1), 1.0, 0.5] for index, _ in enumerate(texts)]


class FakePipeline:
    def __init__(self, outputs):
        self.outputs = outputs
        self.calls = 0

    def __call__(self, values, **_kwargs):
        self.calls += 1
        if isinstance(values, str):
            values = [values]
        return [self.outputs[index % len(self.outputs)] for index, _ in enumerate(values)]


def _runtime(tmp_path: Path):
    return SemanticEnrichmentRuntime(
        model_root=tmp_path,
        embedding_model=FakeEmbedding(),
        sentiment_pipeline=FakePipeline([[{"label": "positive", "score": 0.9}]]),
        stance_pipeline=FakePipeline([[{"label": "entailment", "score": 0.8}]]),
        ner_pipeline=FakePipeline([[{"entity_group": "PER", "word": "特朗普", "score": 0.9}]]),
    )


def test_missing_local_weights_block_without_rule_fallback(tmp_path: Path):
    with pytest.raises(ModelWeightsBlockedError) as exc_info:
        SemanticEnrichmentRuntime(model_root=tmp_path)
    assert "bge_embedding" in str(exc_info.value)
    assert all(spec["revision"] for spec in MODEL_SPECS.values())


def test_shared_embedding_is_encoded_once_and_reused(tmp_path: Path):
    runtime = _runtime(tmp_path)
    snapshot = _snapshot()
    result = runtime.enrich(
        snapshot,
        coordination={
            "fallback": False,
            "artifact_dir": str(tmp_path / "coordination_artifact"),
            "artifact_manifest": {"data_fingerprint": snapshot.data_fingerprint},
            "network": {"clusters": [{"cluster_id": "c1", "members": ["u1", "u2"]}]},
        },
        claim="特朗普访华应加强贸易合作",
    )

    assert runtime.embedding_model.batches[0] == ["特朗普访华 贸易 合作", "特朗普访华 贸易 合作", "希望和平合作"]
    # One batch is for source texts; one is for the shared unique MMR candidates.
    assert runtime.embedding_model.calls == 2
    assert result["runtime_status"] == "ready"
    assert result["embedding_manifest"]["artifact_format"] == "npy.gz"
    assert result["embedding_manifest"]["artifact_path"].endswith(".npy.gz")
    assert result["embedding_manifest"]["reused_for"] == ["keywords", "topics", "near_duplicates", "community_comparison", "propagation_path_overlay"]
    assert set(result["layers"]) == {"posts", "comments"}
    assert result["layers"]["posts"][0]["sentiment"]["label"] == "positive"
    assert result["layers"]["posts"][0]["entities"][0]["text"] == "特朗普"
    assert result["cross_analysis"]["platform_slices"]
    assert result["cross_analysis"]["community_slices"]


def test_semantic_artifact_converts_model_numpy_scalars_to_json_primitives(tmp_path: Path):
    runtime = SemanticEnrichmentRuntime(
        model_root=tmp_path,
        embedding_model=FakeEmbedding(),
        sentiment_pipeline=FakePipeline([[{"label": "positive", "score": np.float32(0.9)}]]),
        stance_pipeline=FakePipeline([[{"label": "entailment", "score": np.float32(0.8)}]]),
        ner_pipeline=FakePipeline([[{"entity_group": "PER", "word": "特朗普", "score": np.float32(0.7)}]]),
    )

    result = runtime.enrich(_snapshot(), claim="primary claim")

    assert json.loads(json.dumps(result))["runtime_status"] == "ready"


def test_observed_path_overlay_requires_both_evidence_endpoints(tmp_path: Path):
    ts = datetime(2026, 5, 21, 1, tzinfo=timezone.utc)
    snapshot = build_event_snapshot(
        event_id="trump_visit_2026_05_21",
        posts=[{"platform": "weibo", "post_id": "observed-post", "author_id": "u1", "timestamp": ts, "content": "source post"}],
        comments=[{"platform": "weibo", "comment_id": "orphan-comment", "post_id": "not-in-snapshot", "author_id": "u2", "timestamp": ts, "content": "comment without its parent post"}],
        core_window=TimeWindow(start=datetime(2026, 5, 21, tzinfo=timezone.utc), end=datetime(2026, 5, 22, tzinfo=timezone.utc)),
        context_window=TimeWindow(start=datetime(2026, 5, 1, tzinfo=timezone.utc), end=datetime(2026, 5, 31, tzinfo=timezone.utc)),
    )

    result = _runtime(tmp_path).enrich(snapshot, claim="primary claim")

    assert result["cross_analysis"]["propagation_path_overlays"] == []


def test_observed_path_overlay_cites_parent_post_and_comment(tmp_path: Path):
    ts = datetime(2026, 5, 21, 1, tzinfo=timezone.utc)
    snapshot = build_event_snapshot(
        event_id="trump_visit_2026_05_21",
        posts=[{"platform": "weibo", "post_id": "source-post", "author_id": "u1", "timestamp": ts, "content": "source post"}],
        comments=[{"platform": "weibo", "comment_id": "reply-comment", "post_id": "source-post", "author_id": "u2", "timestamp": ts, "content": "reply comment"}],
        core_window=TimeWindow(start=datetime(2026, 5, 21, tzinfo=timezone.utc), end=datetime(2026, 5, 22, tzinfo=timezone.utc)),
        context_window=TimeWindow(start=datetime(2026, 5, 1, tzinfo=timezone.utc), end=datetime(2026, 5, 31, tzinfo=timezone.utc)),
    )

    result = _runtime(tmp_path).enrich(snapshot, claim="primary claim")

    overlay = result["cross_analysis"]["propagation_path_overlays"][0]["semantic_overlay"]
    assert overlay["evidence_refs"] == ["weibo:post:source-post", "weibo:comment:reply-comment"]
    assert overlay["topics"]
    assert overlay["time_range"] == {
        "start": "2026-05-21T01:00:00+00:00",
        "end": "2026-05-21T01:00:00+00:00",
    }
    assert overlay["associated_claim"] == "primary claim"


def test_community_slices_suppress_fallback_coordination_clusters(tmp_path: Path):
    result = _runtime(tmp_path).enrich(
        _snapshot(),
        coordination={
            "fallback": True,
            "network": {
                "clusters": [
                    {"cluster_id": "fallback-cluster", "members": ["u1", "u2"]},
                ]
            },
        },
        claim="primary claim",
    )

    cross_analysis = result["cross_analysis"]

    assert cross_analysis["community_slices"] == []
    assert cross_analysis["community_slices_unavailable_reason"] == "coordination_fallback"


def test_observed_path_overlay_suppresses_comment_to_comment_reply_edges(tmp_path: Path):
    ts = datetime(2026, 5, 21, 1, tzinfo=timezone.utc)
    snapshot = build_event_snapshot(
        event_id="trump_visit_2026_05_21",
        posts=[{"platform": "weibo", "post_id": "source-post", "author_id": "u1", "timestamp": ts, "content": "source post"}],
        comments=[
            {"platform": "weibo", "comment_id": "parent-comment", "post_id": "source-post", "author_id": "u2", "timestamp": ts, "content": "parent comment"},
            {"platform": "weibo", "comment_id": "reply-comment", "post_id": "source-post", "reply_to": "parent-comment", "author_id": "u3", "timestamp": ts, "content": "reply comment"},
        ],
        core_window=TimeWindow(start=datetime(2026, 5, 21, tzinfo=timezone.utc), end=datetime(2026, 5, 22, tzinfo=timezone.utc)),
        context_window=TimeWindow(start=datetime(2026, 5, 1, tzinfo=timezone.utc), end=datetime(2026, 5, 31, tzinfo=timezone.utc)),
    )

    result = _runtime(tmp_path).enrich(snapshot, claim="primary claim")

    overlays = result["cross_analysis"]["propagation_path_overlays"]

    assert len(overlays) == 1
    assert overlays[0]["semantic_overlay"]["evidence_refs"] == [
        "weibo:post:source-post",
        "weibo:comment:parent-comment",
    ]


def test_community_slice_aggregates_only_actual_coordination_members(tmp_path: Path):
    runtime = _runtime(tmp_path)
    snapshot = _snapshot()

    result = runtime.enrich(
        snapshot,
        coordination={
            "fallback": False,
            "artifact_dir": str(tmp_path / "coordination_artifact"),
            "artifact_manifest": {"data_fingerprint": snapshot.data_fingerprint},
            "network": {
                "clusters": [
                    {"cluster_id": "cluster-a", "members": ["u1", "u3"]},
                ]
            }
        },
        claim="primary claim",
    )

    slices = result["cross_analysis"]["community_slices"]

    assert len(slices) == 1
    assert slices[0]["community_id"] == "cluster-a"
    assert slices[0]["members"] == ["u1", "u3"]
    assert slices[0]["member_count"] == 2
    assert slices[0]["item_count"] == 2
    assert slices[0]["sentiment_distribution"] == {"positive": 2}
    assert slices[0]["stance_distribution"] == {"entailment": 2}
    assert slices[0]["top_keywords"]
    assert slices[0]["top_topics"]
    assert slices[0]["top_entities"] == [{"text": "特朗普", "label": "PER", "count": 2}]
