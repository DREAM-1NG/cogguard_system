from __future__ import annotations

import asyncio
import importlib.util
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.config import PROJECT_ROOT
from app.core.analysis import TimeWindow, build_event_snapshot
from app.core.analysis.executor import SnapshotCoordinationEngine


def _load_kt1():
    module_name = "_test_cogguard_research_kt1"
    cached = sys.modules.get(module_name)
    if cached is not None:
        return cached
    package_dir = PROJECT_ROOT / "research" / "kt1"
    spec = importlib.util.spec_from_file_location(
        module_name,
        package_dir / "__init__.py",
        submodule_search_locations=[str(package_dir)],
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _dt(day: int, hour: int = 0, minute: int = 0) -> datetime:
    return datetime(2026, 5, day, hour, minute, tzinfo=timezone.utc)


def _snapshot():
    return build_event_snapshot(
        event_id="trump_visit",
        posts=[
            {
                "event_id": "trump_visit",
                "platform": "weibo",
                "post_id": "p1",
                "author_id": "u1",
                "timestamp": _dt(11, 1, 0),
                "content": "shared claim template alpha beta gamma delta epsilon zeta eta theta iota first",
                "url": "https://example.com/story?a=1",
                "media_urls": ["https://cdn.example.com/clip.mp4"],
                "image_embedding": [0.1, 0.2],
                "hashtags": ["#TrumpVisit", "#SharedNarrative"],
                "keywords": ["visit"],
                "entities": ["White House"],
                "target": "Trump",
                "raw_data": {
                    "link": "https://example.com/story?a=1",
                    "topic": ["TrumpVisit"],
                    "entities": ["White House"],
                    "video": {"url": "https://cdn.example.com/clip.mp4"},
                },
            },
            {
                "event_id": "trump_visit",
                "platform": "douyin",
                "post_id": "p2",
                "author_id": "u2",
                "timestamp": _dt(11, 1, 20),
                "content": "shared claim template alpha beta gamma delta epsilon zeta eta theta iota second",
                "url": "https://example.com/story?a=1",
                "media_urls": ["https://cdn.example.com/clip.mp4"],
                "hashtags": ["#TrumpVisit", "#SharedNarrative"],
                "keywords": ["visit"],
                "entities": ["White House"],
                "target": "Trump",
                "repost_id": "p1",
            },
            {
                "event_id": "trump_visit",
                "platform": "xhs",
                "post_id": "p3",
                "author_id": "u3",
                "timestamp": _dt(11, 2, 10),
                "content": "shared claim template alpha beta gamma delta epsilon zeta eta theta iota third",
                "url": "https://example.com/story?a=1",
                "hashtags": ["#TrumpVisit"],
                "keywords": ["visit"],
                "entities": ["White House"],
                "target": "Trump",
                "quote_post_id": "p2",
            },
        ],
        comments=[
            {
                "comment_id": "c1",
                "post_id": "p1",
                "author_id": "u4",
                "timestamp": _dt(11, 1, 5),
                "reply_to": "p1",
                "content": "shared reply around same discussion target",
                "entities": ["White House"],
            }
        ],
        core_window=TimeWindow(start=_dt(11), end=_dt(21)),
        context_window=TimeWindow(start=_dt(1), end=_dt(31)),
    )


def test_strict_leiden_runtime_dependencies_are_available():
    import igraph
    import leidenalg

    assert igraph.__version__.startswith("0.11.")
    assert leidenalg is not None


def test_research_evidence_graph_uses_platform_generic_signals_only():
    kt1 = _load_kt1()

    graph = kt1.build_evidence_graph(_snapshot())
    kinds = {edge.evidence_kind for edge in graph.edges}
    values = {item.value for item in graph.objects}

    assert {"url", "domain", "hashtag", "keyword", "entity", "target", "native_relation", "discussion", "near_duplicate"}.issubset(kinds)
    assert "media" not in kinds
    assert not any(str(value).endswith(".mp4") for value in values)
    assert graph.modality_policy == "platform_generic_only"
    assert any(item["field"] == "media_urls" for item in graph.excluded_fields)
    assert any(item["field"] == "image_embedding" for item in graph.excluded_fields)
    assert any(item["field"].startswith("raw_data.video") for item in graph.excluded_fields)


def test_research_model_input_excludes_topology_audit_features():
    kt1 = _load_kt1()

    graph = kt1.build_evidence_graph(_snapshot())
    tensors = kt1.build_temporal_magnn_tensors(graph, kt1.TemporalMAGNNConfig(device="cpu"))

    assert graph.topology_audit_features["feature_role"] == "audit_only"
    assert {"degree", "pagerank", "density", "object_concentration"}.issubset(
        set(graph.topology_audit_features["feature_names"])
    )
    assert not {"degree", "pagerank", "density", "object_concentration"} & set(tensors.feature_names)
    assert set(tensors.feature_names) == {
        "source_account_id",
        "evidence_object_id",
        "relation_type",
        "time_bucket",
    }


def test_dynamic_discover_smoke_writes_reproducible_artifact(tmp_path: Path):
    kt1 = _load_kt1()
    config = kt1.TemporalMAGNNConfig(
        embedding_dim=8,
        epochs=2,
        negative_ratio=1,
        device="cpu",
        min_learned_edge_score=0.0,
    )

    result = kt1.run_dynamic_discover(
        kt1.DynamicDiscoverRequest(
            snapshot=_snapshot(),
            artifact_dir=str(tmp_path),
            model_config=config,
            source_dataset="fixture",
            source_event="trump_visit",
        )
    )
    exported = kt1.export_coordination_result(result)

    assert result.status == "ok"
    assert result.learned_edge_graph["edge_count"] >= 1
    assert result.learned_edge_graph["partition_backend"] == "leiden"
    assert result.communities
    assert result.manifest.data_fingerprint == _snapshot().data_fingerprint
    assert result.manifest.partition_backend == "leiden"
    assert result.audit_metrics["model_input"]["feature_names"] == list(kt1.MODEL_INPUT_FEATURE_NAMES)
    assert exported["model_role"] == "dynamic_discover"
    assert exported["detect_role"] == "validation_only"
    assert (tmp_path / "manifest.json").exists()
    assert (tmp_path / "discover_result.json").exists()
    assert (tmp_path / "coordination_result.json").exists()


def test_detect_validation_reports_metrics_only_when_labels_exist():
    kt1 = _load_kt1()

    result = kt1.run_detect_validation(
        kt1.DetectValidationRequest(
            rows=[
                {"score": 0.9, "label": 1},
                {"score": 0.7, "label": 1},
                {"score": 0.3, "label": 0},
                {"score": 0.1, "label": 0},
            ]
        )
    )
    missing = kt1.run_detect_validation(kt1.DetectValidationRequest(rows=[{"score": 0.9}]))

    assert result.status == "ok"
    assert result.metrics["auprc"] == 1.0
    assert result.metrics["max_f1"] == 1.0
    assert missing.status == "missing_labels"


def test_backend_uses_kt1_artifact_when_fingerprint_matches(tmp_path: Path):
    async def scenario():
        kt1 = _load_kt1()
        snapshot = _snapshot()
        kt1.run_dynamic_discover(
            kt1.DynamicDiscoverRequest(
                snapshot=snapshot,
                artifact_dir=str(tmp_path),
                model_config=kt1.TemporalMAGNNConfig(
                    embedding_dim=8,
                    epochs=1,
                    negative_ratio=1,
                    device="cpu",
                    min_learned_edge_score=0.0,
                ),
            )
        )

        result = await SnapshotCoordinationEngine().analyze(snapshot, {"artifact_dir": str(tmp_path)})

        assert result["model_version"] == kt1.KT1_MODEL_VERSION
        assert result["fallback"] is False
        assert result["artifact_manifest"]["partition_backend"] == "leiden"
        assert result["artifact_manifest"]["data_fingerprint"] == snapshot.data_fingerprint
        assert result["summary"]["coordinated_edges"] >= 1

    asyncio.run(scenario())


def test_backend_rejects_non_leiden_kt1_artifact(tmp_path: Path):
    async def scenario():
        kt1 = _load_kt1()
        snapshot = _snapshot()
        kt1.run_dynamic_discover(
            kt1.DynamicDiscoverRequest(
                snapshot=snapshot,
                artifact_dir=str(tmp_path),
                model_config=kt1.TemporalMAGNNConfig(
                    embedding_dim=8,
                    epochs=1,
                    negative_ratio=1,
                    device="cpu",
                    min_learned_edge_score=0.0,
                ),
            )
        )
        manifest_path = tmp_path / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["partition_backend"] = "networkx_modularity_fallback"
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

        result = await SnapshotCoordinationEngine().analyze(
            snapshot,
            {"artifact_dir": str(tmp_path), "time_window": 3600, "min_participation": 1},
        )

        assert result["model_version"] == "coordination-evidence-runtime-v2"
        assert result["fallback"] is True
        assert result["fallback_reason"] == "artifact_partition_backend_not_leiden"

    asyncio.run(scenario())


def test_backend_falls_back_to_evidence_runtime_when_artifact_missing(tmp_path: Path):
    async def scenario():
        result = await SnapshotCoordinationEngine().analyze(
            _snapshot(),
            {"artifact_dir": str(tmp_path / "missing"), "time_window": 3600, "min_participation": 1},
        )

        assert result["model_version"] == "coordination-evidence-runtime-v2"
        assert result["fallback"] is True
        assert result["fallback_reason"] == "kt1_artifact_not_found"

    asyncio.run(scenario())
