from __future__ import annotations

import dataclasses
import importlib.util
import json
import sys
import types
from datetime import datetime, timedelta, timezone

import numpy as np
import pytest

from app.config import PROJECT_ROOT


def _load_stage1_modules():
    package_name = "_test_cogguard_coordination_stage1_engine"
    package_dir = PROJECT_ROOT / "research" / "coordination_discover" / "stage1"
    if package_name not in sys.modules:
        package = types.ModuleType(package_name)
        package.__path__ = [str(package_dir)]
        sys.modules[package_name] = package

    loaded = []
    for child_name in ("contracts", "events", "tsgs", "mhcr", "clustering", "engine"):
        module_name = f"{package_name}.{child_name}"
        module = sys.modules.get(module_name)
        if module is None:
            spec = importlib.util.spec_from_file_location(
                module_name, package_dir / f"{child_name}.py"
            )
            assert spec is not None and spec.loader is not None
            module = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = module
            spec.loader.exec_module(module)
        loaded.append(module)
    return tuple(loaded)


def _events(events_module):
    start = datetime(2026, 8, 7, tzinfo=timezone.utc)
    rows = []
    for account_id in ("account-a", "account-b", "account-c"):
        rows.extend(
            (
                (account_id, "shared_url", "url-left", 0),
                (account_id, "shared_hashtag", "topic-left", 10),
            )
        )
    for account_id in ("account-d", "account-e"):
        rows.extend(
            (
                (account_id, "shared_url", "url-right", 120),
                (account_id, "shared_hashtag", "topic-right", 130),
            )
        )
    rows.append(("account-f", "reply_target", "post-singleton", 240))
    return tuple(
        events_module.CoordinationEvent(
            account_id=account_id,
            relation=relation,
            object_id=object_id,
            observed_at=start + timedelta(seconds=offset),
            weight=1.0,
            evidence_ref=f"evidence:{index:02d}",
        )
        for index, (account_id, relation, object_id, offset) in enumerate(rows)
    )


def _provenance(contracts_module):
    return contracts_module.DiscoveryProvenance(
        snapshot_id="snapshot-stage1-fixture",
        data_fingerprint="sha256:fixture-data",
        source_dataset="stage1-fixture",
        source_event="fixture-event",
        stage1_model_version="coordination-discovery-v1",
        tsgs_version="tsgs-v1",
        mhcr_version="mhcr-infonce-v1",
        created_at="2026-08-07T00:10:00Z",
        seed=41,
        split_policy="label_sealed_full_snapshot",
        input_event_count=11,
        input_account_count=6,
        method_config_hash="sha256:fixture-method",
    )


def _config(tsgs_module, mhcr_module, clustering_module, engine_module):
    return engine_module.DiscoveryConfig(
        tsgs=tsgs_module.TSGSConfig(
            seed=41,
            time_bucket_seconds=60,
            hyperplane_count=12,
            band_size=1,
            bucket_cap=32,
            sampling_multiplier=2.0,
        ),
        mhcr=mhcr_module.MHCRConfig(
            seed=41,
            time_bucket_seconds=60,
            hidden_dimension=8,
            epochs=5,
            temporal_jitter_seconds=8,
            hyperedge_drop_rate=0.2,
        ),
        clustering=clustering_module.LeidenConfig(
            seed=41,
            resolution=0.1,
            embedding_affinity_weight=0.5,
        ),
    )


def _forbidden_output_keys(value):
    prohibited = {"label", "labels", "classifier", "logit", "logits", "probability", "harmful", "verdict"}
    found = set()
    if isinstance(value, dict):
        for key, item in value.items():
            if str(key).lower() in prohibited:
                found.add(str(key).lower())
            found.update(_forbidden_output_keys(item))
    elif isinstance(value, list):
        for item in value:
            found.update(_forbidden_output_keys(item))
    return found


def test_embedding_affinity_reweights_only_explicit_tsgs_candidate_edges():
    _, events_module, tsgs_module, mhcr_module, clustering_module, _ = _load_stage1_modules()
    events = _events(events_module)
    tsgs_result = tsgs_module.TemporalSketchGraphSparsifier(
        tsgs_module.TSGSConfig(
            seed=41,
            time_bucket_seconds=60,
            hyperplane_count=12,
            band_size=1,
            bucket_cap=32,
        )
    ).fit_transform(events)
    representation = mhcr_module.MHCREncoder(
        mhcr_module.MHCRConfig(seed=41, time_bucket_seconds=60, epochs=2)
    ).fit_transform(events, tsgs_result)

    fused = clustering_module.fuse_candidate_edges(
        tsgs_result,
        representation,
        clustering_module.LeidenConfig(seed=41, embedding_affinity_weight=0.5),
    )

    expected_pairs = {
        (edge.source_account_id, edge.target_account_id)
        for edge in tsgs_result.candidate_graph_edges
    }
    actual_pairs = {(edge.source_account_id, edge.target_account_id) for edge in fused.edges}
    assert actual_pairs == expected_pairs
    assert fused.evaluated_embedding_pair_count == len(expected_pairs)
    assert fused.source_graph == "explicit_tsgs_candidate_graph"
    assert all(edge.weight > 0.0 for edge in fused.edges)


def test_leiden_returns_deterministic_partition_and_explicit_singletons():
    _, events_module, tsgs_module, mhcr_module, clustering_module, _ = _load_stage1_modules()
    events = _events(events_module)
    tsgs_result = tsgs_module.TemporalSketchGraphSparsifier(
        tsgs_module.TSGSConfig(
            seed=43,
            time_bucket_seconds=60,
            hyperplane_count=12,
            band_size=1,
            bucket_cap=32,
            sampling_multiplier=2.0,
        )
    ).fit_transform(events)
    representation = mhcr_module.MHCREncoder(
        mhcr_module.MHCRConfig(seed=43, time_bucket_seconds=60, epochs=3)
    ).fit_transform(events, tsgs_result)
    config = clustering_module.LeidenConfig(seed=43, resolution=0.1)

    first = clustering_module.LeidenPartitioner(config).partition(tsgs_result, representation)
    second = clustering_module.LeidenPartitioner(config).partition(tsgs_result, representation)

    assert first == second
    assert first.method == "leiden"
    assert first.role == "interpretation_partition_not_activation"
    assert first.communities == (
        ("account-a", "account-b", "account-c"),
        ("account-d", "account-e"),
        ("account-f",),
    )
    assert first.singleton_account_ids == ("account-f",)
    assert first.no_edge is False


def test_leiden_empty_and_no_edge_inputs_are_explicit():
    _, _, tsgs_module, mhcr_module, clustering_module, _ = _load_stage1_modules()

    empty_tsgs = tsgs_module.TemporalSketchGraphSparsifier().fit_transform([])
    empty_representation = mhcr_module.MHCREncoder(
        mhcr_module.MHCRConfig(epochs=1)
    ).fit_transform([], empty_tsgs)
    empty = clustering_module.LeidenPartitioner().partition(
        empty_tsgs, empty_representation
    )

    assert empty.communities == ()
    assert empty.singleton_account_ids == ()
    assert empty.no_edge is True
    assert empty.status == "empty_graph"

    account_ids = ("account-a", "account-b")
    no_edge_tsgs = dataclasses.replace(empty_tsgs, account_ids=account_ids, full_pair_count=1)
    no_edge_representation = dataclasses.replace(
        empty_representation,
        account_ids=account_ids,
        embeddings=((1.0, 0.0), (0.0, 1.0)),
    )
    no_edge = clustering_module.LeidenPartitioner().partition(
        no_edge_tsgs, no_edge_representation
    )

    assert no_edge.communities == (("account-a",), ("account-b",))
    assert no_edge.singleton_account_ids == account_ids
    assert no_edge.no_edge is True
    assert no_edge.status == "singleton_partition_no_edges"


def test_discovery_engine_returns_stable_evidence_backed_batch_without_verdict_fields(
    tmp_path,
):
    contracts_module, events_module, tsgs_module, mhcr_module, clustering_module, engine_module = (
        _load_stage1_modules()
    )
    events = _events(events_module)
    config = _config(tsgs_module, mhcr_module, clustering_module, engine_module)
    engine = engine_module.CoordinationDiscoveryEngine(config)

    first = engine.discover(events, _provenance(contracts_module))
    second = engine.discover(reversed(events), _provenance(contracts_module))

    assert isinstance(first, contracts_module.DiscoveredClusterBatch)
    assert first.to_dict() == second.to_dict()
    assert first.batch_id.startswith("discovery-")
    assert first.timestamp == "2026-08-07T00:10:00Z"
    assert first.provenance.label_policy == "stage1_label_free"
    assert first.candidate_clusters
    assert all(cluster.cluster_id.startswith("cluster-") for cluster in first.candidate_clusters)
    assert all(cluster.evidence_refs for cluster in first.candidate_clusters)
    assert all(cluster.artifact_hashes for cluster in first.candidate_clusters)
    assert all(cluster.embedding_ref for cluster in first.candidate_clusters)
    assert all(cluster.sparsified_subgraph_ref for cluster in first.candidate_clusters)
    for cluster in first.candidate_clusters:
        metrics = cluster.coordination_metrics
        assert 0.0 <= metrics.tsgs_spectral_density <= 1.0
        assert 0.0 <= metrics.mhcr_hyperedge_coherence <= 1.0
        assert 0.0 <= metrics.overall_coordination_score <= 1.0
        assert metrics.temporal_sync_delta_seconds >= 0.0

    payload = first.to_dict()
    assert not _forbidden_output_keys(payload)
    output = tmp_path / "stage1.json"
    first.to_json(output)
    restored = contracts_module.DiscoveredClusterBatch.from_json(output)
    assert restored.to_dict() == payload
    assert json.loads(output.read_text(encoding="utf-8")) == payload


def test_external_label_maps_with_opposite_values_cannot_change_discovery(
    monkeypatch: pytest.MonkeyPatch,
):
    contracts_module, events_module, tsgs_module, mhcr_module, clustering_module, engine_module = (
        _load_stage1_modules()
    )
    events = _events(events_module)
    config = _config(tsgs_module, mhcr_module, clustering_module, engine_module)
    labels = {f"account-{letter}": index % 2 for index, letter in enumerate("abcdef")}

    monkeypatch.setattr(engine_module, "EXTERNAL_LABEL_MAP", labels, raising=False)
    first = engine_module.CoordinationDiscoveryEngine(config).discover(
        events, _provenance(contracts_module)
    )
    monkeypatch.setattr(
        engine_module,
        "EXTERNAL_LABEL_MAP",
        {account_id: 1 - value for account_id, value in labels.items()},
        raising=False,
    )
    second = engine_module.CoordinationDiscoveryEngine(config).discover(
        events, _provenance(contracts_module)
    )

    assert first.to_dict() == second.to_dict()
    assert list(inspect_parameter for inspect_parameter in __import__("inspect").signature(
        engine_module.CoordinationDiscoveryEngine.discover
    ).parameters) == ["self", "events", "provenance"]


def test_engine_empty_snapshot_returns_stable_empty_batch():
    contracts_module, _, tsgs_module, mhcr_module, clustering_module, engine_module = (
        _load_stage1_modules()
    )
    provenance = dataclasses.replace(
        _provenance(contracts_module), input_event_count=0, input_account_count=0
    )
    engine = engine_module.CoordinationDiscoveryEngine(
        _config(tsgs_module, mhcr_module, clustering_module, engine_module)
    )

    batch = engine.discover([], provenance)

    assert batch.candidate_clusters == ()
    assert batch.batch_id.startswith("discovery-")
    assert batch.quality_flags == ("platform_missing", "sparse_evidence")
