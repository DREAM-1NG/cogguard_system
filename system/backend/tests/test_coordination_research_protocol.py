from __future__ import annotations

import dataclasses
import importlib.util
import json
import pickle
import sys
import types
from datetime import datetime, timezone
from pathlib import Path

import networkx as nx
import pytest

from app.config import PROJECT_ROOT


def _load_experiments():
    research_name = "research"
    research_dir = PROJECT_ROOT / "research"
    if research_name not in sys.modules:
        research_package = types.ModuleType(research_name)
        research_package.__path__ = [str(research_dir)]
        sys.modules[research_name] = research_package

    package_name = "research.coordination_experiments"
    cached = sys.modules.get(package_name)
    if cached is not None:
        return cached
    package_dir = research_dir / "coordination_experiments"
    spec = importlib.util.spec_from_file_location(
        package_name,
        package_dir / "__init__.py",
        submodule_search_locations=[str(package_dir)],
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[package_name] = module
    spec.loader.exec_module(module)
    return module


def _capability(module):
    return module.DatasetCapability(
        dataset_id="fixture",
        supports_coordination_discovery=True,
        supports_external_label_evaluation=True,
        supports_campaign_holdout=True,
        supports_time_holdout=False,
        supports_social_bot_classification=False,
        supports_harmful_cib_detection=True,
        supports_campaign_io_evaluation=True,
        blocked_reasons={
            "observed_time_holdout": "fixture has no observed timestamps",
            "social_bot_classification": "fixture is not a bot dataset",
        },
        claim_markers=("research_only",),
    )


def _manifest(module):
    return module.ResearchDatasetManifest(
        dataset_id="fixture",
        seed=42,
        source_paths=("/datasets/fixture.json",),
        source_checksums={"/datasets/fixture.json": "sha256:" + "a" * 64},
        source_checksum_scope="canonical_fixture_content",
        label_semantics="sealed_external_binary_labels",
        sample_count=4,
        source_case_ids=("case-b", "case-a"),
        campaign_axis=("campaign-b", "campaign-a"),
        platform_axis=("twitter",),
        time_axis="observed_utc",
        quality_markers=("research_only",),
        claim_markers=("not_production_evidence",),
    )


def _graph(edges=()):
    graph = nx.Graph()
    graph.add_nodes_from(range(4))
    graph.add_edges_from(edges)
    return graph


def _iohunter_payload(*, labels=(0, 1, 0, 1), reverse_splits=False):
    split_values = {
        "train": (True, True, False, False),
        "validation": (False, False, True, False),
        "test": (False, False, False, True),
    }
    if reverse_splits:
        split_values = {key: tuple(reversed(value)) for key, value in split_values.items()}
    return {
        "graph": _graph([(0, 1), (1, 2), (2, 3)]),
        "coRT": _graph([(0, 1, {"weight": 2.0}), (2, 2, {"weight": 99.0})]),
        "coURL": _graph([(1, 2, {"weight": 3.0})]),
        "hashSeq": _graph([(2, 3, {"weight": 4.0})]),
        "fastRT": _graph([(0, 1, {"weight": 5.0})]),
        "tweetSim": _graph([(0, 3, {"weight": 0.75})]),
        "labels": tuple(labels),
        "splits": split_values,
    }


def _forbidden_discovery_keys(value):
    prohibited = {
        "labels",
        "class_counts",
        "splits",
        "official_folds",
        "harmful",
        "bot",
        "evaluator",
        "evaluator_ref",
    }
    found = set()
    if isinstance(value, dict):
        for key, item in value.items():
            if str(key).lower() in prohibited:
                found.add(str(key).lower())
            found.update(_forbidden_discovery_keys(item))
    elif isinstance(value, list):
        for item in value:
            found.update(_forbidden_discovery_keys(item))
    return found


def test_manifest_and_capability_are_immutable_canonical_round_trip_values():
    module = _load_experiments()
    manifest = _manifest(module)
    capability = _capability(module)

    assert module.ResearchDatasetManifest.from_dict(manifest.to_dict()) == manifest
    assert module.DatasetCapability.from_dict(capability.to_dict()) == capability
    assert manifest.to_dict()["source_case_ids"] == ["case-a", "case-b"]
    assert manifest.fingerprint.startswith("sha256:")
    assert capability.fingerprint.startswith("sha256:")
    assert module.ResearchDatasetManifest.from_dict(manifest.to_dict()).fingerprint == manifest.fingerprint
    with pytest.raises(dataclasses.FrozenInstanceError):
        manifest.seed = 7
    with pytest.raises(TypeError):
        capability.blocked_reasons["injected"] = "not immutable"


def test_manifest_and_capability_reject_unknown_fields_and_bad_checksums():
    module = _load_experiments()
    payload = _manifest(module).to_dict()
    payload["unexpected"] = True
    with pytest.raises(ValueError, match="unknown fields"):
        module.ResearchDatasetManifest.from_dict(payload)

    payload = _manifest(module).to_dict()
    payload["source_checksums"]["/datasets/fixture.json"] = "md5:bad"
    with pytest.raises(ValueError, match="source_checksums"):
        module.ResearchDatasetManifest.from_dict(payload)

    capability = _capability(module).to_dict()
    capability["blocked_reasons"] = {}
    with pytest.raises(ValueError, match="blocked reason"):
        module.DatasetCapability.from_dict(capability)


def test_experiment_split_round_trip_fingerprint_and_train_only_transform_ids():
    module = _load_experiments()
    split = module.build_campaign_holdout(
        {"a": "china", "b": "cuba", "c": "iran", "d": "russia"},
        validation_campaigns=("iran",),
        test_campaigns=("russia",),
        seed=19,
    )

    assert split.train_ids == ("a", "b")
    assert split.validation_ids == ("c",)
    assert split.test_ids == ("d",)
    assert split.train_group_ids == ("china", "cuba")
    assert split.validation_group_ids == ("iran",)
    assert split.test_group_ids == ("russia",)
    assert split.transform_fit_ids == split.train_ids
    assert module.ExperimentSplit.from_dict(split.to_dict()) == split
    assert module.ExperimentSplit.from_dict(split.to_dict()).fingerprint == split.fingerprint
    with pytest.raises(dataclasses.FrozenInstanceError):
        split.seed = 2


def test_campaign_holdout_is_group_disjoint_deterministic_and_seed_recorded():
    module = _load_experiments()
    samples = {
        "cn-2": "china",
        "cu-1": "cuba",
        "cn-1": "china",
        "ir-1": "iran",
        "ru-1": "russia",
    }
    first = module.build_campaign_holdout(samples, ("iran",), ("russia",), seed=11)
    reordered = module.build_campaign_holdout(dict(reversed(tuple(samples.items()))), ("iran",), ("russia",), seed=11)
    different_seed = module.build_campaign_holdout(samples, ("iran",), ("russia",), seed=12)

    assert first == reordered
    assert first.train_ids == ("cn-1", "cn-2", "cu-1")
    assert first.fingerprint != different_seed.fingerprint
    assert not (set(first.train_group_ids) & set(first.validation_group_ids))
    assert not (set(first.train_group_ids) & set(first.test_group_ids))


@pytest.mark.parametrize(
    ("samples", "validation", "test", "message"),
    [
        ({"a": "china", "b": "iran", "c": "russia"}, ("missing",), ("russia",), "missing"),
        ({"a": "china", "b": "iran", "c": "russia"}, ("iran",), ("iran",), "overlap"),
        ({"a": "china", "b": "iran"}, ("china",), ("iran",), "train"),
        ({"a": "china", "b": "iran", "c": "russia"}, (), ("russia",), "validation"),
    ],
)
def test_campaign_holdout_fails_closed(samples, validation, test, message):
    module = _load_experiments()
    with pytest.raises(ValueError, match=message):
        module.build_campaign_holdout(samples, validation, test, seed=3)


def test_time_holdout_uses_strict_timezone_aware_chronological_boundaries():
    module = _load_experiments()
    utc = timezone.utc
    times = {
        "train-before": datetime(2026, 1, 1, tzinfo=utc),
        "train-boundary": datetime(2026, 1, 2, tzinfo=utc),
        "validation": datetime(2026, 1, 3, tzinfo=utc),
        "validation-boundary": datetime(2026, 1, 4, tzinfo=utc),
        "test": datetime(2026, 1, 5, tzinfo=utc),
    }
    split = module.build_time_holdout(
        times,
        train_end=datetime(2026, 1, 2, tzinfo=utc),
        validation_end=datetime(2026, 1, 4, tzinfo=utc),
        seed=23,
    )

    assert split.train_ids == ("train-before", "train-boundary")
    assert split.validation_ids == ("validation", "validation-boundary")
    assert split.test_ids == ("test",)
    assert split.transform_fit_ids == split.train_ids
    assert split.policy == "observed_time_holdout"


@pytest.mark.parametrize(
    ("times", "train_end", "validation_end", "message"),
    [
        ({"a": None, "b": datetime(2026, 1, 2, tzinfo=timezone.utc)}, datetime(2026, 1, 1, tzinfo=timezone.utc), datetime(2026, 1, 2, tzinfo=timezone.utc), "timestamp"),
        ({"a": datetime(2026, 1, 1), "b": datetime(2026, 1, 2, tzinfo=timezone.utc)}, datetime(2026, 1, 1, tzinfo=timezone.utc), datetime(2026, 1, 2, tzinfo=timezone.utc), "timezone"),
        ({"a": datetime(2026, 1, 1, tzinfo=timezone.utc), "b": datetime(2026, 1, 2, tzinfo=timezone.utc), "c": datetime(2026, 1, 3, tzinfo=timezone.utc)}, datetime(2026, 1, 2, tzinfo=timezone.utc), datetime(2026, 1, 2, tzinfo=timezone.utc), "boundary"),
        ({"a": datetime(2026, 1, 1, tzinfo=timezone.utc), "b": datetime(2026, 1, 2, tzinfo=timezone.utc)}, datetime(2026, 1, 1, tzinfo=timezone.utc), datetime(2026, 1, 2, tzinfo=timezone.utc), "test"),
    ],
)
def test_time_holdout_fails_closed(times, train_end, validation_end, message):
    module = _load_experiments()
    with pytest.raises(ValueError, match=message):
        module.build_time_holdout(times, train_end, validation_end, seed=3)


def test_iohunter_discovery_is_label_and_official_split_invariant():
    module = _load_experiments()
    source = _iohunter_payload()
    inverted = _iohunter_payload(labels=(1, 0, 1, 0), reverse_splits=True)
    inverted["graph"] = _graph([(0, 3)])

    first = module.adapt_iohunter_payload(source, campaign="russia", seed=31)
    second = module.adapt_iohunter_payload(inverted, campaign="russia", seed=31)

    assert first.events == second.events
    assert first.discovery_fingerprint == second.discovery_fingerprint
    assert first.manifest == second.manifest
    assert not _forbidden_discovery_keys(first.to_dict())
    assert set(first.to_dict()) == {"events", "manifest"}


def test_iohunter_emits_only_source_relations_bidirectionally_without_self_loops():
    module = _load_experiments()
    discovery = module.adapt_iohunter_payload(_iohunter_payload(), campaign="russia", seed=31)

    assert len(discovery.events) == 10
    assert {event.relation for event in discovery.events} == {
        "repost_target",
        "shared_url",
        "shared_hashtag",
        "near_duplicate",
    }
    assert all(event.weight > 0.0 for event in discovery.events)
    assert all(event.observed_at == module.IOHUNTER_STATIC_PLACEHOLDER_TIMESTAMP for event in discovery.events)
    assert all(event.account_id.startswith("iohunter:russia:account:") for event in discovery.events)
    assert all("label" not in event.account_id and "class" not in event.account_id for event in discovery.events)
    assert all("graph" not in event.evidence_ref for event in discovery.events)
    assert {event.evidence_ref.split(":")[2] for event in discovery.events} == {
        "coRT",
        "coURL",
        "hashSeq",
        "fastRT",
        "tweetSim",
    }
    pair_refs = {}
    for event in discovery.events:
        pair_refs.setdefault(event.evidence_ref, []).append(event)
    assert all(len(events) == 2 for events in pair_refs.values())
    assert all(len({event.object_id for event in events}) == 1 for events in pair_refs.values())
    assert discovery.manifest.time_axis == "static_placeholder_not_observed_time"
    assert discovery.manifest.source_checksum_scope == "canonical_discovery_graph_layers"
    assert discovery.manifest.quality_markers == ("timestamp_imputed",)


@pytest.mark.parametrize("weight", [0.0, -1.0, float("inf"), float("nan")])
def test_iohunter_rejects_non_positive_or_non_finite_edge_weights(weight):
    module = _load_experiments()
    payload = _iohunter_payload()
    payload["coRT"] = _graph([(0, 1, {"weight": weight})])
    with pytest.raises(ValueError, match="weight"):
        module.adapt_iohunter_payload(payload, campaign="russia", seed=31)


def test_iohunter_evaluator_is_sealed_immutable_and_aligned():
    module = _load_experiments()
    evaluator = module.build_iohunter_label_evaluator(_iohunter_payload(), campaign="russia")

    assert dict(evaluator.account_labels) == {
        "iohunter:russia:account:000000": 0,
        "iohunter:russia:account:000001": 1,
        "iohunter:russia:account:000002": 0,
        "iohunter:russia:account:000003": 1,
    }
    assert evaluator.label_semantics == "1=information-operation account; 0=non-IO account"
    assert set(evaluator.official_folds) == {"test", "train", "validation"}
    with pytest.raises(TypeError):
        evaluator.account_labels["injected"] = 1

    bad_labels = _iohunter_payload(labels=(0, 2, 0, 1))
    with pytest.raises(ValueError, match="binary"):
        module.build_iohunter_label_evaluator(bad_labels, campaign="russia")
    short_labels = _iohunter_payload(labels=(0, 1, 0))
    with pytest.raises(ValueError, match="aligned"):
        module.build_iohunter_label_evaluator(short_labels, campaign="russia")


def test_iohunter_evaluator_accepts_binary_float_labels_and_numbered_fold_masks():
    module = _load_experiments()
    payload = _iohunter_payload(labels=(0.0, 1.0, 0.0, 1.0))
    payload["splits"] = {
        0: {
            "train": (True, True, False, False),
            "validation": (False, False, True, False),
            "test": (False, False, False, True),
        },
        1: {
            "train": (False, True, True, False),
            "validation": (True, False, False, False),
            "test": (False, False, False, True),
        },
    }

    evaluator = module.build_iohunter_label_evaluator(payload, campaign="russia")

    assert tuple(evaluator.official_folds) == (
        "fold-000-test",
        "fold-000-train",
        "fold-000-validation",
        "fold-001-test",
        "fold-001-train",
        "fold-001-validation",
    )
    assert evaluator.account_labels["iohunter:russia:account:000001"] == 1


def test_iohunter_pickle_loading_requires_explicit_trusted_local_gate(tmp_path):
    module = _load_experiments()
    path = tmp_path / "fixture.pkl"
    path.write_bytes(b"not loaded without trust")

    with pytest.raises(ValueError, match="trusted_local=True"):
        module.load_iohunter_discovery(path, campaign="russia", seed=31)
    with pytest.raises(ValueError, match="trusted_local=True"):
        module.load_iohunter_label_evaluator(path, campaign="russia")


def test_loaded_discovery_manifest_cannot_fingerprint_sealed_pickle_fields(tmp_path):
    module = _load_experiments()
    path = tmp_path / "0.7_datasets.pkl"
    with path.open("wb") as handle:
        pickle.dump(_iohunter_payload(), handle)
    first = module.load_iohunter_discovery(
        path, campaign="russia", seed=31, trusted_local=True
    )

    with path.open("wb") as handle:
        pickle.dump(
            _iohunter_payload(labels=(1, 0, 1, 0), reverse_splits=True), handle
        )
    second = module.load_iohunter_discovery(
        path, campaign="russia", seed=31, trusted_local=True
    )

    assert first.events == second.events
    assert first.discovery_fingerprint == second.discovery_fingerprint
    assert first.manifest == second.manifest


def test_iohunter_and_cresci_capabilities_block_unsupported_claims():
    module = _load_experiments()
    iohunter = module.iohunter_capability()
    cresci = module.cresci_capability()

    assert iohunter.supports_coordination_discovery is True
    assert iohunter.supports_external_label_evaluation is True
    assert iohunter.supports_campaign_holdout is True
    assert iohunter.supports_time_holdout is False
    assert "observed_time_holdout" in iohunter.blocked_reasons
    assert cresci.supports_social_bot_classification is True
    assert cresci.supports_harmful_cib_detection is False
    assert cresci.supports_coordination_discovery is False
    assert cresci.supports_campaign_io_evaluation is False
    assert cresci.supports_time_holdout is False
    assert "not_harmful_cib_claim" in cresci.claim_markers


def test_cresci_manifest_uses_authoritative_metadata_without_opening_archive(tmp_path):
    module = _load_experiments()
    archive = tmp_path / "cresci-2017.csv.zip"
    archive.write_bytes(b"fixture archive is not opened")
    metadata = tmp_path / "dataset_manifest.json"
    metadata.write_text(
        json.dumps(
            {
                "schema": "cogguard.social_bot_detection.dataset_manifest.v1",
                "datasets": [
                    {
                        "id": "cresci-2017",
                        "file": archive.name,
                        "bytes": archive.stat().st_size,
                        "sha256": "B" * 64,
                        "label_scope": "genuine, traditional spambots, and social spambots",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    manifest = module.build_cresci_manifest(archive, metadata, seed=37)

    assert manifest.seed == 37
    assert manifest.sample_count == 0
    assert manifest.platform_axis == ("twitter",)
    assert manifest.label_semantics == "genuine, traditional spambots, and social spambots"
    assert manifest.claim_markers == ("not_harmful_cib_claim",)
    assert manifest.source_checksums[str(archive.resolve())] == "sha256:" + "b" * 64
    assert manifest.source_checksum_scope == "authoritative_archive_and_metadata"
