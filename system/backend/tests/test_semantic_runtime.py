from __future__ import annotations

import builtins
from datetime import datetime, timezone
import importlib
import json
from pathlib import Path

import numpy as np
import pytest

from app.core.analysis import TimeWindow, build_event_snapshot
from app.core.semantic.runtime import (
    BGE_ENCODING_BATCH_SIZE,
    MODEL_SPECS,
    ModelWeightsBlockedError,
    SemanticEnrichmentRuntime,
)


def _snapshot():
    timestamp = datetime(2026, 5, 21, 1, tzinfo=timezone.utc)
    return build_event_snapshot(
        event_id="trump_visit_2026_05_21",
        posts=[
            {
                "platform": "weibo",
                "post_id": "p1",
                "author_id": "u1",
                "timestamp": timestamp,
                "content": "特朗普访华 贸易 合作",
            },
            {
                "platform": "xhs",
                "post_id": "p2",
                "author_id": "u2",
                "timestamp": timestamp,
                "content": "特朗普访华 贸易 合作",
            },
        ],
        comments=[
            {
                "platform": "douyin",
                "comment_id": "c1",
                "author_id": "u3",
                "timestamp": timestamp,
                "content": "希望和平合作",
            },
        ],
        core_window=TimeWindow(
            start=datetime(2026, 5, 21, tzinfo=timezone.utc),
            end=datetime(2026, 5, 22, tzinfo=timezone.utc),
        ),
        context_window=TimeWindow(
            start=datetime(2026, 5, 1, tzinfo=timezone.utc),
            end=datetime(2026, 5, 31, tzinfo=timezone.utc),
        ),
    )


class FakeEmbedding:
    def __init__(self):
        self.calls = 0
        self.batches: list[list[str]] = []

    def encode(self, texts, **_kwargs):
        self.calls += 1
        self.batches.append(list(texts))
        return [[float(index + 1), 1.0, 0.5] for index, _ in enumerate(texts)]


class RecordingEmbedding:
    def __init__(self):
        self.batches: list[list[str]] = []

    def encode(self, texts, **_kwargs):
        batch = list(texts)
        self.batches.append(batch)
        return [[float(int(text.rsplit("-", 1)[1]))] for text in batch]


class FakePipeline:
    def __init__(self, outputs):
        self.outputs = outputs

    def __call__(self, values, **_kwargs):
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
        embedding_output_root=tmp_path / "embeddings",
    )


def _write_coordination_artifact(artifact_dir: Path, snapshot, *, members: list[str]) -> None:
    from app.core.analysis.coordination_discover_adapter import _load_coordination_discover_module

    discover = _load_coordination_discover_module()
    artifacts = importlib.import_module(f"{discover.__name__}.artifacts")
    manifest = artifacts.create_manifest(
        data_fingerprint=snapshot.data_fingerprint,
        model_version="semantic-runtime-test-v1",
        config={"purpose": "semantic-runtime-test"},
        artifact_dir=artifact_dir,
        source_event=snapshot.event_id,
        partition_backend="leiden",
    )
    result = discover.DiscoverResult(
        status="ok",
        snapshot_id=snapshot.snapshot_id,
        event_id=snapshot.event_id,
        data_fingerprint=snapshot.data_fingerprint,
        model_version="semantic-runtime-test-v1",
        evidence_graph={},
        learned_edge_graph={},
        communities=[],
        lineage=[],
        attention={},
        audit_metrics={},
        manifest=manifest,
    )
    artifacts.write_discover_artifact(
        result,
        artifact_dir=artifact_dir,
        coordination_result={
            "status": "ok",
            "technology": "coordination_discover",
            "fallback": False,
            "network": {"clusters": [{"cluster_id": "persisted-community", "members": members}]},
        },
    )


def test_missing_local_weights_blocks_without_rule_fallback(tmp_path: Path):
    with pytest.raises(ModelWeightsBlockedError) as exc_info:
        SemanticEnrichmentRuntime(model_root=tmp_path)

    assert "bge_embedding" in str(exc_info.value)
    assert all(spec["revision"] for spec in MODEL_SPECS.values())


def test_bge_encoding_batches_each_text_once_in_original_order(tmp_path: Path):
    encoder = RecordingEmbedding()
    runtime = _runtime(tmp_path)
    runtime.embedding_model = encoder
    batch_size = BGE_ENCODING_BATCH_SIZE
    texts = [f"text-{index}" for index in range(batch_size + 2)]

    vectors = runtime._encode_texts(texts)

    assert len(encoder.batches) == 2
    assert all(len(batch) <= batch_size for batch in encoder.batches)
    assert [text for batch in encoder.batches for text in batch] == texts
    assert vectors == [[float(index)] for index in range(batch_size + 2)]


def test_real_runtime_contract_stratifies_layers_and_reuses_embeddings(tmp_path: Path):
    runtime = _runtime(tmp_path)
    snapshot = _snapshot()
    coordination_artifact = tmp_path / "coordination_artifact"
    _write_coordination_artifact(coordination_artifact, snapshot, members=["u1", "u2"])

    result = runtime.enrich(
        snapshot,
        coordination={
            "fallback": False,
            "artifact_dir": str(coordination_artifact),
            "artifact_manifest": {"data_fingerprint": "fabricated-fingerprint"},
            "network": {"clusters": [{"cluster_id": "fabricated-community", "members": ["u3"]}]},
        },
        claim="特朗普访华应加强贸易合作",
    )

    assert runtime.embedding_model.batches[0] == [
        "特朗普访华 贸易 合作",
        "特朗普访华 贸易 合作",
        "希望和平合作",
    ]
    assert result["runtime_status"] == "ready"
    assert result["runtime_backend"] == "transformers_sentence_transformers"
    assert result["validation_status"] == "candidate_unvalidated"
    assert result["embedding_manifest"]["reused_for"] == [
        "keywords",
        "topics",
        "near_duplicates",
        "community_comparison",
        "propagation_path_overlay",
    ]
    assert set(result["layers"]) == {"posts", "comments"}
    assert result["layers"]["posts"][0]["sentiment"]["label"] == "positive"
    assert result["layers"]["posts"][0]["stance"]["label"] == "entailment"
    assert result["layers"]["posts"][0]["entities"][0]["text"] == "特朗普"
    assert result["layers"]["posts"][0]["keywords"]
    assert result["layers"]["posts"][0]["topics"]
    assert result["cross_analysis"]["platform_slices"]
    community = result["cross_analysis"]["community_slices"]
    assert [item["community_id"] for item in community] == ["persisted-community"]
    assert community[0]["members"] == ["u1", "u2"]
    assert community[0]["member_count"] == 2
    assert community[0]["item_count"] == 2
    json.loads(json.dumps(result))


def test_stance_is_only_blocked_output_when_primary_claim_is_missing(tmp_path: Path):
    result = _runtime(tmp_path).enrich(_snapshot())

    assert result["runtime_status"] == "ready"
    assert {
        item["stance"]["status"]
        for layer in result["layers"].values()
        for item in layer
    } == {"blocked_missing_primary_claim"}


def test_fallback_coordination_does_not_become_a_community_slice(tmp_path: Path):
    result = _runtime(tmp_path).enrich(
        _snapshot(),
        coordination={
            "fallback": True,
            "network": {"clusters": [{"cluster_id": "not-real", "members": ["u1", "u2"]}]},
        },
        claim="primary claim",
    )

    assert result["cross_analysis"]["community_slices"] == []
    assert result["cross_analysis"]["community_slices_unavailable_reason"] == "coordination_fallback"


def test_empty_coordination_directory_does_not_trust_caller_network_or_manifest(tmp_path: Path):
    snapshot = _snapshot()
    artifact_dir = tmp_path / "empty-coordination-artifact"
    artifact_dir.mkdir()

    result = _runtime(tmp_path).enrich(
        snapshot,
        coordination={
            "artifact_dir": str(artifact_dir),
            "artifact_manifest": {"data_fingerprint": snapshot.data_fingerprint},
            "network": {"clusters": [{"cluster_id": "fabricated-community", "members": ["u1", "u2"]}]},
        },
        claim="primary claim",
    )

    assert result["cross_analysis"]["community_slices"] == []
    assert result["cross_analysis"]["community_slices_unavailable_reason"] == "coordination_artifact_unavailable"


def test_coordination_artifact_without_hashes_does_not_become_a_community_slice(tmp_path: Path):
    snapshot = _snapshot()
    artifact_dir = tmp_path / "coordination-artifact-without-hashes"
    _write_coordination_artifact(artifact_dir, snapshot, members=["u1", "u2"])
    manifest_path = artifact_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["artifact_hashes"] = {}
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    result = _runtime(tmp_path).enrich(
        snapshot,
        coordination={"artifact_dir": str(artifact_dir)},
        claim="primary claim",
    )

    assert result["cross_analysis"]["community_slices"] == []
    assert result["cross_analysis"]["community_slices_unavailable_reason"] == "coordination_artifact_unavailable"


def test_tampered_coordination_artifact_does_not_become_a_community_slice(tmp_path: Path):
    snapshot = _snapshot()
    artifact_dir = tmp_path / "tampered-coordination-artifact"
    _write_coordination_artifact(artifact_dir, snapshot, members=["u1", "u2"])
    result_path = artifact_dir / "coordination_result.json"
    result_path.write_text(result_path.read_text(encoding="utf-8") + "\n", encoding="utf-8")

    result = _runtime(tmp_path).enrich(
        snapshot,
        coordination={
            "artifact_dir": str(artifact_dir),
            "artifact_manifest": {"data_fingerprint": snapshot.data_fingerprint},
            "network": {"clusters": [{"cluster_id": "fabricated-community", "members": ["u1", "u2"]}]},
        },
        claim="primary claim",
    )

    assert result["cross_analysis"]["community_slices"] == []
    assert result["cross_analysis"]["community_slices_unavailable_reason"] == "coordination_artifact_unavailable"


def test_missing_jieba_is_reported_as_a_model_weights_blocker(monkeypatch, tmp_path: Path):
    runtime = _runtime(tmp_path)
    original_import = builtins.__import__

    def missing_jieba(name, *args, **kwargs):
        if name == "jieba":
            raise ModuleNotFoundError("No module named 'jieba'")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", missing_jieba)

    with pytest.raises(ModelWeightsBlockedError, match="jieba"):
        runtime.enrich(_snapshot(), claim="primary claim")


def test_dependency_import_failure_is_reported_as_a_model_weights_blocker(monkeypatch):
    original_import = importlib.import_module

    def broken_transformers(name, *args, **kwargs):
        if name == "transformers":
            raise OSError("torch CUDA DLL unavailable")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(importlib, "import_module", broken_transformers)

    with pytest.raises(ModelWeightsBlockedError, match="transformers runtime dependency unavailable"):
        SemanticEnrichmentRuntime.ensure_runtime_dependencies()


def test_path_overlay_requires_a_matching_propagation_artifact(tmp_path: Path):
    timestamp = datetime(2026, 5, 21, 1, tzinfo=timezone.utc)
    snapshot = build_event_snapshot(
        event_id="trump_visit_2026_05_21",
        posts=[
            {
                "platform": "weibo",
                "post_id": "source-post",
                "author_id": "u1",
                "timestamp": timestamp,
                "content": "source post",
            }
        ],
        comments=[
            {
                "platform": "weibo",
                "comment_id": "parent-comment",
                "post_id": "source-post",
                "author_id": "u2",
                "timestamp": timestamp,
                "content": "parent comment",
            },
            {
                "platform": "weibo",
                "comment_id": "reply-comment",
                "post_id": "source-post",
                "reply_to": "parent-comment",
                "author_id": "u3",
                "timestamp": timestamp,
                "content": "reply comment",
            },
        ],
        core_window=TimeWindow(
            start=datetime(2026, 5, 21, tzinfo=timezone.utc),
            end=datetime(2026, 5, 22, tzinfo=timezone.utc),
        ),
        context_window=TimeWindow(
            start=datetime(2026, 5, 1, tzinfo=timezone.utc),
            end=datetime(2026, 5, 31, tzinfo=timezone.utc),
        ),
    )

    cross_analysis = _runtime(tmp_path).enrich(snapshot, claim="primary claim")["cross_analysis"]

    assert cross_analysis["propagation_path_overlays"] == []
    assert cross_analysis["propagation_path_overlays_unavailable_reason"] == "propagation_result_unavailable"


def test_fabricated_propagation_dictionary_does_not_produce_path_overlays(tmp_path: Path):
    timestamp = datetime(2026, 5, 21, 1, tzinfo=timezone.utc)
    snapshot = build_event_snapshot(
        event_id="trump_visit_2026_05_21",
        posts=[
            {
                "platform": "weibo",
                "post_id": "source-post",
                "author_id": "u1",
                "timestamp": timestamp,
                "content": "source post",
            }
        ],
        comments=[
            {
                "platform": "weibo",
                "comment_id": "reply-comment",
                "post_id": "source-post",
                "reply_to": "source-post",
                "author_id": "u2",
                "timestamp": timestamp,
                "content": "reply comment",
            }
        ],
        core_window=TimeWindow(
            start=datetime(2026, 5, 21, tzinfo=timezone.utc),
            end=datetime(2026, 5, 22, tzinfo=timezone.utc),
        ),
        context_window=TimeWindow(
            start=datetime(2026, 5, 1, tzinfo=timezone.utc),
            end=datetime(2026, 5, 31, tzinfo=timezone.utc),
        ),
    )
    artifact_dir = tmp_path / "fabricated-propagation-artifact"
    artifact_dir.mkdir()
    result = _runtime(tmp_path).enrich(
        snapshot,
        propagation={
            "artifact_dir": str(artifact_dir),
            "artifact_manifest": {"data_fingerprint": snapshot.data_fingerprint},
            "key_paths": [
                {
                    "path_id": "fabricated-path",
                    "nodes": ["weibo:post:source-post", "weibo:comment:reply-comment"],
                }
            ],
        },
        claim="primary claim",
    )

    assert result["cross_analysis"]["propagation_path_overlays"] == []
    assert result["cross_analysis"]["propagation_path_overlays_unavailable_reason"] == "propagation_result_unavailable"
