from __future__ import annotations

import importlib.util
import json
import math
import sys
from pathlib import Path

import pytest

from app.config import PROJECT_ROOT


def _load_stage1():
    module_name = "_test_cogguard_coordination_stage1"
    cached = sys.modules.get(module_name)
    if cached is not None:
        return cached
    package_dir = PROJECT_ROOT / "research" / "coordination_discover" / "stage1"
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


def _batch(stage1):
    metrics = stage1.CoordinationMetricSet(
        tsgs_spectral_density=0.73,
        mhcr_hyperedge_coherence=0.81,
        temporal_sync_delta_seconds=12.5,
        overall_coordination_score=0.77,
        evidence_coverage=0.91,
        relation_diversity=0.66,
    )
    cluster = stage1.DiscoveredCluster(
        cluster_id="cluster-2",
        member_account_ids=("account-b", "account-a", "account-b"),
        coordination_metrics=metrics,
        evidence_refs=("evidence:2", "evidence:1", "evidence:2"),
        sparsified_subgraph_ref="artifacts/cluster-2.npz",
        embedding_ref="artifacts/cluster-2.npy",
        artifact_hashes={"cluster-2.npz": "sha256:abc"},
        relation_types=("shared_url", "shared_url"),
        window_ids=("window-1",),
        evidence_kind_counts={"shared_url": 2},
    )
    provenance = stage1.DiscoveryProvenance(
        snapshot_id="snapshot-1",
        data_fingerprint="sha256:data",
        source_dataset="fixture",
        source_event="event-1",
        stage1_model_version="coordination-discovery-v1",
        tsgs_version="tsgs-v1",
        mhcr_version="mhcr-v1",
        created_at="2026-08-07T00:00:00Z",
        seed=42,
        split_policy="label_sealed_full_snapshot",
        input_event_count=5,
        input_account_count=2,
        method_config_hash="sha256:method",
    )
    return stage1.DiscoveredClusterBatch(
        batch_id="disc-batch-1",
        timestamp="2026-08-07T00:01:00Z",
        candidate_clusters=(cluster,),
        provenance=provenance,
        platforms=("weibo", "douyin", "xhs"),
        quality_flags=("sampling_applied",),
        artifact_manifest_ref="artifacts/manifest.json",
    )


def test_discovered_cluster_batch_json_round_trip_is_deterministic(tmp_path: Path):
    stage1 = _load_stage1()
    batch = _batch(stage1)
    first = tmp_path / "first.json"
    second = tmp_path / "second.json"

    batch.to_json(first)
    restored = stage1.DiscoveredClusterBatch.from_json(first)
    restored.to_json(second)

    assert first.read_bytes() == second.read_bytes()
    assert restored == batch
    payload = json.loads(first.read_text(encoding="utf-8"))
    assert payload["schema_version"] == "cogguard.discovered-cluster-batch/v1"
    assert payload["stage"] == "coordination_discovery"
    assert payload["claim_role"] == "unsupervised_candidate_clusters"
    assert payload["candidate_clusters"][0]["size"] == 2
    assert payload["candidate_clusters"][0]["member_account_ids"] == ["account-a", "account-b"]
    assert payload["candidate_clusters"][0]["evidence_refs"] == ["evidence:1", "evidence:2"]
    assert payload["provenance"]["label_policy"] == "stage1_label_free"
    assert payload["batch_fingerprint"].startswith("sha256:")


def test_contract_rejects_duplicate_cluster_ids():
    stage1 = _load_stage1()
    batch = _batch(stage1)

    with pytest.raises(ValueError, match="duplicate cluster_id"):
        stage1.DiscoveredClusterBatch(
            batch_id=batch.batch_id,
            timestamp=batch.timestamp,
            candidate_clusters=(batch.candidate_clusters[0], batch.candidate_clusters[0]),
            provenance=batch.provenance,
        )


@pytest.mark.parametrize("field", ["tsgs_spectral_density", "mhcr_hyperedge_coherence", "overall_coordination_score", "evidence_coverage", "relation_diversity"])
@pytest.mark.parametrize("value", [-0.01, 1.01, math.nan, math.inf])
def test_contract_rejects_non_finite_or_out_of_range_unit_metrics(field: str, value: float):
    stage1 = _load_stage1()
    values = {
        "tsgs_spectral_density": 0.5,
        "mhcr_hyperedge_coherence": 0.5,
        "temporal_sync_delta_seconds": 1.0,
        "overall_coordination_score": 0.5,
        "evidence_coverage": 0.5,
        "relation_diversity": 0.5,
    }
    values[field] = value

    with pytest.raises(ValueError, match=field):
        stage1.CoordinationMetricSet(**values)


@pytest.mark.parametrize("value", [-1.0, math.nan, math.inf])
def test_contract_rejects_invalid_temporal_delta(value: float):
    stage1 = _load_stage1()

    with pytest.raises(ValueError, match="temporal_sync_delta_seconds"):
        stage1.CoordinationMetricSet(
            tsgs_spectral_density=0.5,
            mhcr_hyperedge_coherence=0.5,
            temporal_sync_delta_seconds=value,
            overall_coordination_score=0.5,
        )


def test_contract_rejects_unknown_schema_version_and_inconsistent_size():
    stage1 = _load_stage1()
    payload = _batch(stage1).to_dict()
    payload["schema_version"] = "cogguard.discovered-cluster-batch/v999"

    with pytest.raises(ValueError, match="unsupported schema_version"):
        stage1.DiscoveredClusterBatch.from_dict(payload)

    payload = _batch(stage1).to_dict()
    payload["candidate_clusters"][0]["size"] = 999
    with pytest.raises(ValueError, match="size does not match"):
        stage1.DiscoveredClusterBatch.from_dict(payload)


def test_provenance_rejects_non_label_free_policy():
    stage1 = _load_stage1()

    with pytest.raises(ValueError, match="label_policy"):
        stage1.DiscoveryProvenance(
            snapshot_id="snapshot-1",
            data_fingerprint="sha256:data",
            source_dataset="fixture",
            source_event="event-1",
            stage1_model_version="coordination-discovery-v1",
            tsgs_version="tsgs-v1",
            mhcr_version="mhcr-v1",
            created_at="2026-08-07T00:00:00Z",
            seed=42,
            split_policy="label_sealed_full_snapshot",
            label_policy="supervised",
        )


@pytest.mark.parametrize(
    ("location", "field", "value"),
    [
        ("candidate_clusters", "metadata", {"label": "coordinated"}),
        ("provenance", "method_metadata", {"verdict": "harmful"}),
        ("batch", "metadata", {"risk": "high"}),
    ],
)
def test_from_dict_rejects_label_bearing_unknown_fields(location: str, field: str, value: object):
    stage1 = _load_stage1()
    payload = _batch(stage1).to_dict()
    target = payload if location == "batch" else payload[location]
    if location == "candidate_clusters":
        target = target[0]
    target[field] = value

    with pytest.raises(ValueError, match="unknown fields"):
        stage1.DiscoveredClusterBatch.from_dict(payload)


def test_metric_set_from_dict_requires_unsupervised_ranking_score_role():
    stage1 = _load_stage1()
    payload = _batch(stage1).candidate_clusters[0].coordination_metrics.to_dict()
    payload["overall_coordination_score_role"] = "probability"

    with pytest.raises(ValueError, match="overall_coordination_score_role"):
        stage1.CoordinationMetricSet.from_dict(payload)


@pytest.mark.parametrize(
    ("parser", "payload"),
    [
        ("CoordinationMetricSet", {"unexpected": 1}),
        ("DiscoveredCluster", {"unexpected": 1}),
        ("DiscoveryProvenance", {"unexpected": 1}),
        ("DiscoveredClusterBatch", {"unexpected": 1}),
    ],
)
def test_from_dict_rejects_unknown_and_missing_schema_fields(parser: str, payload: dict[str, object]):
    stage1 = _load_stage1()
    target = getattr(stage1, parser)

    with pytest.raises(ValueError, match="unknown fields"):
        target.from_dict(payload)

    with pytest.raises(ValueError, match="missing required fields"):
        target.from_dict({})


def test_mapping_fields_are_typed_and_deeply_immutable():
    stage1 = _load_stage1()
    artifact_hashes = {"cluster-2.npz": "sha256:abc"}
    evidence_kind_counts = {"shared_url": 2}
    cluster = stage1.DiscoveredCluster(
        cluster_id="cluster-typed-mapping",
        member_account_ids=("account-a",),
        coordination_metrics=_batch(stage1).candidate_clusters[0].coordination_metrics,
        artifact_hashes=artifact_hashes,
        evidence_kind_counts=evidence_kind_counts,
    )
    artifact_hashes["injected"] = "sha256:def"
    evidence_kind_counts["injected"] = 7

    assert dict(cluster.artifact_hashes) == {"cluster-2.npz": "sha256:abc"}
    assert dict(cluster.evidence_kind_counts) == {"shared_url": 2}
    with pytest.raises(TypeError):
        cluster.evidence_kind_counts["injected"] = 7
    with pytest.raises(ValueError, match="evidence_kind_counts"):
        stage1.DiscoveredCluster(
            cluster_id="cluster-invalid-mapping",
            member_account_ids=("account-a",),
            coordination_metrics=_batch(stage1).candidate_clusters[0].coordination_metrics,
            evidence_kind_counts={"shared_url": {"label": "coordinated"}},
        )


def test_contract_rejects_non_string_member_identifiers_and_fractional_size_and_seed():
    stage1 = _load_stage1()

    with pytest.raises(ValueError, match="member_account_ids"):
        stage1.DiscoveredCluster(
            cluster_id="cluster-integer-member",
            member_account_ids=(123,),
            coordination_metrics=_batch(stage1).candidate_clusters[0].coordination_metrics,
        )

    payload = _batch(stage1).to_dict()
    payload["candidate_clusters"][0]["size"] = 2.5
    with pytest.raises(ValueError, match="cluster size must be an integer"):
        stage1.DiscoveredClusterBatch.from_dict(payload)

    payload = _batch(stage1).to_dict()
    payload["provenance"]["seed"] = 42.5
    with pytest.raises(ValueError, match="seed must be an integer"):
        stage1.DiscoveredClusterBatch.from_dict(payload)


@pytest.mark.parametrize("quality_flag", ["bot_suspected", "high_risk"])
def test_contract_rejects_label_bearing_quality_flags(quality_flag: str):
    stage1 = _load_stage1()
    batch = _batch(stage1)

    with pytest.raises(ValueError, match="quality_flags"):
        stage1.DiscoveredClusterBatch(
            batch_id=batch.batch_id,
            timestamp=batch.timestamp,
            candidate_clusters=batch.candidate_clusters,
            provenance=batch.provenance,
            platforms=batch.platforms,
            quality_flags=(quality_flag,),
            artifact_manifest_ref=batch.artifact_manifest_ref,
        )

    payload = batch.to_dict()
    payload["quality_flags"] = [quality_flag]
    with pytest.raises(ValueError, match="quality_flags"):
        stage1.DiscoveredClusterBatch.from_dict(payload)


def test_contract_accepts_neutral_quality_flags():
    stage1 = _load_stage1()
    batch = _batch(stage1)
    quality_flags = (
        "partial_provenance",
        "sparse_evidence",
        "timestamp_imputed",
        "platform_missing",
        "sampling_applied",
    )
    accepted = stage1.DiscoveredClusterBatch(
        batch_id=batch.batch_id,
        timestamp=batch.timestamp,
        candidate_clusters=batch.candidate_clusters,
        provenance=batch.provenance,
        platforms=batch.platforms,
        quality_flags=quality_flags,
        artifact_manifest_ref=batch.artifact_manifest_ref,
    )

    restored = stage1.DiscoveredClusterBatch.from_dict(accepted.to_dict())

    assert restored.quality_flags == tuple(sorted(quality_flags))
