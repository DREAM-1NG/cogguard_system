from __future__ import annotations

import dataclasses
import hashlib
import importlib.util
import json
import pickle
import sys
import types
from datetime import datetime, timezone
from pathlib import Path

import networkx as nx
import numpy as np
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
        supports_binary_coordination_detection=True,
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


def _relabel_iohunter_universe(payload, mapping):
    for key in ("graph", "coRT", "coURL", "hashSeq", "fastRT", "tweetSim"):
        payload[key] = nx.relabel_nodes(payload[key], mapping, copy=True)
    return payload


def _write_cresci_fixture(
    tmp_path,
    *,
    archive_bytes=b"verified cresci fixture",
    label_scope="genuine, traditional spambots, and social spambots",
):
    archive = tmp_path / "cresci-2017.csv.zip"
    archive.write_bytes(archive_bytes)
    digest = hashlib.sha256(archive_bytes).hexdigest()
    metadata = tmp_path / "dataset_manifest.json"
    metadata.write_text(
        json.dumps(
            {
                "schema": "cogguard.social_bot_detection.dataset_manifest.v1",
                "datasets": [
                    {
                        "id": "cresci-2017",
                        "file": archive.name,
                        "bytes": len(archive_bytes),
                        "sha256": digest.upper(),
                        "label_scope": label_scope,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    return archive, metadata, digest


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
    assert len(first.train_ids + first.validation_ids + first.test_ids) == len(samples)


def test_campaign_holdout_rejects_normalized_id_group_and_argument_collisions():
    module = _load_experiments()
    with pytest.raises(ValueError, match="sample ID.*duplicate"):
        module.build_campaign_holdout(
            {"case": "china", " case ": "cuba", "v": "iran", "t": "russia"},
            ("iran",),
            ("russia",),
            seed=3,
        )
    with pytest.raises(ValueError, match="campaign alias"):
        module.build_campaign_holdout(
            {"a": "china", "b": " china ", "v": "iran", "t": "russia"},
            ("iran",),
            ("russia",),
            seed=3,
        )
    with pytest.raises(ValueError, match="validation campaigns.*duplicate"):
        module.build_campaign_holdout(
            {"a": "china", "v": "iran", "t": "russia"},
            ("iran", " iran "),
            ("russia",),
            seed=3,
        )


def test_direct_split_values_reject_normalized_duplicate_ids_and_groups():
    module = _load_experiments()
    values = {
        "policy": "campaign_holdout",
        "seed": 3,
        "train_ids": ("a",),
        "validation_ids": ("b",),
        "test_ids": ("c",),
        "train_group_ids": ("china",),
        "validation_group_ids": ("iran",),
        "test_group_ids": ("russia",),
        "transform_fit_ids": ("a",),
    }
    with pytest.raises(ValueError, match="train_ids.*duplicate"):
        module.ExperimentSplit(**{**values, "train_ids": ("a", " a "), "transform_fit_ids": ("a", " a ")})
    with pytest.raises(ValueError, match="train_group_ids.*duplicate"):
        module.ExperimentSplit(**{**values, "train_group_ids": ("china", " china ")})


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


def test_time_holdout_rejects_normalized_sample_id_collisions():
    module = _load_experiments()
    with pytest.raises(ValueError, match="sample ID.*duplicate"):
        module.build_time_holdout(
            {
                "case": datetime(2026, 1, 1, tzinfo=timezone.utc),
                " case ": datetime(2026, 1, 2, tzinfo=timezone.utc),
                "test": datetime(2026, 1, 3, tzinfo=timezone.utc),
            },
            datetime(2026, 1, 1, tzinfo=timezone.utc),
            datetime(2026, 1, 2, tzinfo=timezone.utc),
            seed=3,
        )


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


def test_iohunter_discovery_never_requires_or_consumes_fused_graph():
    module = _load_experiments()
    source = _iohunter_payload()
    without_fused_graph = _iohunter_payload()
    del without_fused_graph["graph"]
    replaced_fused_graph = _iohunter_payload()
    replaced_fused_graph["graph"] = object()

    first = module.adapt_iohunter_payload(source, campaign="russia", seed=31)
    removed = module.adapt_iohunter_payload(
        without_fused_graph, campaign="russia", seed=31
    )
    replaced = module.adapt_iohunter_payload(
        replaced_fused_graph, campaign="russia", seed=31
    )

    assert removed.events == first.events == replaced.events
    assert removed.manifest == first.manifest == replaced.manifest
    assert removed.discovery_fingerprint == first.discovery_fingerprint == replaced.discovery_fingerprint


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
    assert {event.account_id for event in discovery.events} == set(discovery.manifest.source_case_ids)


def test_iohunter_requires_one_contiguous_account_universe_from_source_layers():
    module = _load_experiments()
    non_contiguous = _relabel_iohunter_universe(
        _iohunter_payload(), {0: 1, 1: 2, 2: 3, 3: 4}
    )
    with pytest.raises(ValueError, match="contiguous"):
        module.adapt_iohunter_payload(non_contiguous, campaign="russia", seed=31)
    with pytest.raises(ValueError, match="contiguous"):
        module.build_iohunter_label_evaluator(non_contiguous, campaign="russia")


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
    assert evaluator.source_path == "memory://iohunter/russia/evaluator"
    assert evaluator.source_sha256.startswith("sha256:")
    assert len(evaluator.official_folds) == 1
    fold = evaluator.official_folds[0]
    assert fold.fold_id == "fold-000"
    assert fold.train_ids == (
        "iohunter:russia:account:000000",
        "iohunter:russia:account:000001",
    )
    assert fold.validation_ids == ("iohunter:russia:account:000002",)
    assert fold.test_ids == ("iohunter:russia:account:000003",)
    restored = module.IOHunterLabelEvaluator.from_dict(evaluator.to_dict())
    assert restored == evaluator
    assert restored.evaluator_fingerprint == evaluator.evaluator_fingerprint
    with pytest.raises(TypeError):
        evaluator.account_labels["injected"] = 1

    bad_labels = _iohunter_payload(labels=(0, 2, 0, 1))
    with pytest.raises(ValueError, match="binary"):
        module.build_iohunter_label_evaluator(bad_labels, campaign="russia")
    short_labels = _iohunter_payload(labels=(0, 1, 0))
    with pytest.raises(ValueError, match="aligned"):
        module.build_iohunter_label_evaluator(short_labels, campaign="russia")


def test_iohunter_evaluator_requires_fused_graph():
    module = _load_experiments()
    payload = _iohunter_payload()
    del payload["graph"]

    with pytest.raises(ValueError, match="fused graph is required"):
        module.build_iohunter_label_evaluator(payload, campaign="russia")


def test_iohunter_evaluator_rejects_mismatched_fused_graph_universe():
    module = _load_experiments()
    payload = _iohunter_payload()
    payload["graph"].add_node(4)

    with pytest.raises(ValueError, match="fused graph account universe"):
        module.build_iohunter_label_evaluator(payload, campaign="russia")


def test_iohunter_evaluator_accepts_binary_float_labels_and_numbered_fold_masks():
    module = _load_experiments()
    payload = _iohunter_payload(labels=(0.0, 1.0, 0.0, 1.0))
    payload["splits"] = {
        0: {
            "train": np.array((True, True, False, False), dtype=bool),
            "val": np.array((False, False, True, False), dtype=bool),
            "test": np.array((False, False, False, True), dtype=bool),
        },
        3: {
            "train": np.array((False, True, True, False), dtype=bool),
            "validation": np.array((True, False, False, False), dtype=bool),
            "test": np.array((False, False, False, True), dtype=bool),
        },
    }

    evaluator = module.build_iohunter_label_evaluator(payload, campaign="russia")

    assert tuple(fold.fold_id for fold in evaluator.official_folds) == ("fold-000", "fold-003")
    assert all(fold.to_dict()["validation_ids"] for fold in evaluator.official_folds)
    assert evaluator.account_labels["iohunter:russia:account:000001"] == 1


def test_iohunter_evaluator_normalizes_equivalent_direct_float_labels_before_fingerprinting():
    module = _load_experiments()
    folds = module.build_iohunter_label_evaluator(
        _iohunter_payload(), campaign="russia"
    ).official_folds
    common = {
        "campaign": "russia",
        "source_path": "memory://iohunter/russia/evaluator",
        "source_sha256": "sha256:" + "a" * 64,
        "official_folds": folds,
    }
    integer = module.IOHunterLabelEvaluator(
        **common,
        account_labels={
            "iohunter:russia:account:000000": 0,
            "iohunter:russia:account:000001": 1,
            "iohunter:russia:account:000002": 0,
            "iohunter:russia:account:000003": 1,
        },
    )
    floating = module.IOHunterLabelEvaluator(
        **common,
        account_labels={
            "iohunter:russia:account:000000": 0.0,
            "iohunter:russia:account:000001": 1.0,
            "iohunter:russia:account:000002": 0.0,
            "iohunter:russia:account:000003": 1.0,
        },
    )

    assert dict(floating.account_labels) == dict(integer.account_labels)
    assert all(type(value) is int for value in floating.account_labels.values())
    assert floating.evaluator_fingerprint == integer.evaluator_fingerprint


@pytest.mark.parametrize(
    ("partitions", "message"),
    [
        (
            {"train": (1, 1, 0, 0), "validation": (0, 0, 1, 0), "test": (0, 0, 0, 1)},
            "boolean",
        ),
        (
            {"train": (True, True, False), "validation": (False, False, True), "test": (False, False, False)},
            "exactly account_count",
        ),
        (
            {"train": (True, True, False, False), "dev": (False, False, True, False), "test": (False, False, False, True)},
            "partition names",
        ),
        (
            {
                "train": (True, True, False, False),
                "val": (False, False, True, False),
                "validation": (False, False, True, False),
                "test": (False, False, False, True),
            },
            "duplicate validation alias",
        ),
        (
            {"train": (True, True, False, False), "validation": (False, True, True, False), "test": (False, False, False, True)},
            "disjoint",
        ),
        (
            {"train": (True, False, False, False), "validation": (False, True, False, False), "test": (False, False, True, False)},
            "coverage",
        ),
        (
            {"train": (False, False, False, False), "validation": (True, True,True, False), "test": (False, False, False, True)},
            "non-empty",
        ),
    ],
)
def test_iohunter_evaluator_rejects_malformed_official_folds(partitions, message):
    module = _load_experiments()
    payload = _iohunter_payload()
    payload["splits"] = {0: partitions}
    with pytest.raises(ValueError, match=message):
        module.build_iohunter_label_evaluator(payload, campaign="russia")


def test_iohunter_evaluator_fingerprint_covers_labels_folds_semantics_and_provenance():
    module = _load_experiments()
    first = module.build_iohunter_label_evaluator(_iohunter_payload(), campaign="russia")
    changed_labels = module.build_iohunter_label_evaluator(
        _iohunter_payload(labels=(1, 0, 0, 1)), campaign="russia"
    )
    changed_folds_payload = _iohunter_payload()
    changed_folds_payload["splits"] = {
        "train": (True, False, True, False),
        "validation": (False, True, False, False),
        "test": (False, False, False, True),
    }
    changed_folds = module.build_iohunter_label_evaluator(
        changed_folds_payload, campaign="russia"
    )

    assert first.evaluator_fingerprint != changed_labels.evaluator_fingerprint
    assert first.evaluator_fingerprint != changed_folds.evaluator_fingerprint
    tampered = first.to_dict()
    tampered["label_semantics"] = "1=harmful; 0=benign"
    with pytest.raises(ValueError, match="label semantics"):
        module.IOHunterLabelEvaluator.from_dict(tampered)
    tampered = first.to_dict()
    tampered["source_path"] = "memory://changed"
    with pytest.raises(ValueError, match="fingerprint"):
        module.IOHunterLabelEvaluator.from_dict(tampered)


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


def test_trusted_evaluator_owns_raw_source_provenance_without_discovery_leakage(tmp_path):
    module = _load_experiments()
    path = tmp_path / "0.7_datasets.pkl"
    raw = pickle.dumps(_iohunter_payload())
    path.write_bytes(raw)

    evaluator = module.load_iohunter_label_evaluator(
        path, campaign="russia", trusted_local=True
    )
    discovery = module.load_iohunter_discovery(
        path, campaign="russia", seed=31, trusted_local=True
    )

    assert evaluator.source_path == str(path.resolve())
    assert evaluator.source_sha256 == "sha256:" + hashlib.sha256(raw).hexdigest()
    serialized_discovery = json.dumps(discovery.to_dict(), sort_keys=True)
    assert evaluator.source_sha256 not in serialized_discovery
    assert evaluator.evaluator_fingerprint not in serialized_discovery


def test_trusted_evaluator_hashes_the_same_bytes_it_unpickles(tmp_path, monkeypatch):
    module = _load_experiments()
    iohunter = sys.modules["research.coordination_experiments.iohunter"]
    path = tmp_path / "0.7_datasets.pkl"
    raw = pickle.dumps(_iohunter_payload())
    path.write_bytes(raw)
    original_loads = iohunter.pickle.loads
    seen = []

    def recording_loads(value, *args, **kwargs):
        seen.append(value)
        return original_loads(value, *args, **kwargs)

    monkeypatch.setattr(iohunter.pickle, "loads", recording_loads)
    evaluator = module.load_iohunter_label_evaluator(
        path, campaign="russia", trusted_local=True
    )

    assert seen == [raw]
    assert evaluator.source_sha256 == "sha256:" + hashlib.sha256(seen[0]).hexdigest()


def test_iohunter_and_cresci_capabilities_block_unsupported_claims():
    module = _load_experiments()
    iohunter = module.iohunter_capability()
    cresci = module.cresci_capability()

    assert iohunter.supports_coordination_discovery is True
    assert iohunter.supports_external_label_evaluation is True
    assert iohunter.supports_campaign_holdout is True
    assert iohunter.supports_time_holdout is False
    assert "observed_time_holdout" in iohunter.blocked_reasons
    assert iohunter.supports_binary_coordination_detection is False
    assert "binary_coordination_detection" in iohunter.blocked_reasons
    assert iohunter.supports_harmful_cib_detection is False
    assert "harmful_cib_detection" in iohunter.blocked_reasons
    assert "not_harmful_cib_claim" in iohunter.claim_markers
    assert cresci.supports_social_bot_classification is True
    assert cresci.supports_binary_coordination_detection is False
    assert cresci.supports_harmful_cib_detection is False
    assert cresci.supports_coordination_discovery is False
    assert cresci.supports_campaign_io_evaluation is False
    assert cresci.supports_time_holdout is False
    assert "not_harmful_cib_claim" in cresci.claim_markers


def test_cresci_manifest_measures_archive_integrity_and_emits_canonical_bot_semantics(tmp_path):
    module = _load_experiments()
    archive, metadata, digest = _write_cresci_fixture(tmp_path)

    manifest = module.build_cresci_manifest(archive, metadata, seed=37)

    assert manifest.seed == 37
    assert manifest.sample_count == 0
    assert manifest.platform_axis == ("twitter",)
    assert manifest.label_semantics == "social_bot_classification_only:genuine|traditional_spambot|social_spambot"
    assert manifest.claim_markers == ("not_harmful_cib_claim",)
    assert manifest.source_checksums[str(archive.resolve())] == "sha256:" + digest
    assert manifest.source_checksum_scope == "authoritative_archive_and_metadata"


def test_cresci_parses_the_same_metadata_bytes_it_fingerprints(tmp_path, monkeypatch):
    module = _load_experiments()
    cresci = sys.modules["research.coordination_experiments.cresci"]
    archive, metadata, _ = _write_cresci_fixture(tmp_path)
    raw_metadata = metadata.read_bytes()
    original_loads = cresci.json.loads
    seen = []

    def recording_loads(value, *args, **kwargs):
        seen.append(value)
        return original_loads(value, *args, **kwargs)

    monkeypatch.setattr(cresci.json, "loads", recording_loads)
    manifest = module.build_cresci_manifest(archive, metadata, seed=37)

    assert seen == [raw_metadata]
    assert manifest.source_checksums[str(metadata.resolve())] == "sha256:" + hashlib.sha256(raw_metadata).hexdigest()


def test_cresci_measurement_fails_closed_when_source_changes_during_measurement(tmp_path):
    module = _load_experiments()
    cresci = sys.modules["research.coordination_experiments.cresci"]
    archive, _, _ = _write_cresci_fixture(tmp_path)

    class ChangingPath:
        def __init__(self, path):
            self.path = path
            self.calls = 0

        def open(self, *args, **kwargs):
            return self.path.open(*args, **kwargs)

        def stat(self):
            self.calls += 1
            return types.SimpleNamespace(
                st_dev=1,
                st_ino=1,
                st_size=self.path.stat().st_size,
                st_mtime_ns=self.calls,
            )

    with pytest.raises(ValueError, match="changed during measurement"):
        cresci._measure_file(ChangingPath(archive))


def test_cresci_manifest_rejects_same_size_tampered_archive(tmp_path):
    module = _load_experiments()
    archive, metadata, _ = _write_cresci_fixture(tmp_path, archive_bytes=b"original")
    archive.write_bytes(b"tampered")

    with pytest.raises(ValueError, match="SHA-256"):
        module.build_cresci_manifest(archive, metadata, seed=37)


@pytest.mark.parametrize(
    "label_scope",
    [None, "", "harmful-CIB accounts", "genuine and automated accounts"],
)
def test_cresci_manifest_rejects_missing_malformed_or_harmful_label_semantics(
    tmp_path, label_scope
):
    module = _load_experiments()
    archive, metadata, _ = _write_cresci_fixture(tmp_path, label_scope=label_scope)

    with pytest.raises(ValueError, match="label scope"):
        module.build_cresci_manifest(archive, metadata, seed=37)


def test_task5_protocol_does_not_encode_heuristic_baseline_v1_constants():
    source_root = PROJECT_ROOT / "research" / "coordination_experiments"
    combined = "\n".join(path.read_text(encoding="utf-8") for path in source_root.glob("*.py"))

    for token in ("0.25", "0.35", "0.15", "0.65", "0.85", "10.0", "heuristic_baseline_v1"):
        assert token not in combined
