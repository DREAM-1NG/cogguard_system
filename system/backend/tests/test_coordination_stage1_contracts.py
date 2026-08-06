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
    )
    return stage1.DiscoveredClusterBatch(
        batch_id="disc-batch-1",
        timestamp="2026-08-07T00:01:00Z",
        candidate_clusters=(cluster,),
        provenance=provenance,
        metadata={"platforms": ["weibo", "douyin", "xhs"]},
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
