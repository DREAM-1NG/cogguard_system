from __future__ import annotations

import dataclasses
import hashlib
import importlib.util
import json
import pickle
import sys
import types
from pathlib import Path

import networkx as nx
import numpy as np
import pytest

from app.config import PROJECT_ROOT


def _load_experiments():
    research_dir = PROJECT_ROOT / "research"
    if "research" not in sys.modules:
        package = types.ModuleType("research")
        package.__path__ = [str(research_dir)]
        sys.modules["research"] = package
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


def _graph(node_count: int, edges=()):
    graph = nx.Graph()
    graph.add_nodes_from(range(node_count))
    graph.add_edges_from(edges)
    return graph


def _payload(*, labels=(0, 1, 0, 1, 0, 1), fused_edges=None):
    node_count = len(labels)
    split_templates = (
        ((0, 1, 2), (3,), (4, 5)),
        ((1, 2, 3), (4,), (0, 5)),
        ((2, 3, 4), (5,), (0, 1)),
        ((3, 4, 5), (0,), (1, 2)),
        ((0, 4, 5), (1,), (2, 3)),
    )
    splits = {}
    for fold_id, (train, validation, test) in enumerate(split_templates):
        splits[fold_id] = {
            name: np.asarray([index in members for index in range(node_count)], dtype=np.bool_)
            for name, members in (
                ("train", train),
                ("val", validation),
                ("test", test),
            )
        }
    return {
        "graph": _graph(node_count, fused_edges or [(0, 1), (1, 2), (3, 4)]),
        "coRT": _graph(node_count, [(0, 1, {"weight": 2.0}), (2, 2, {"weight": 99.0})]),
        "coURL": _graph(node_count, [(1, 2, {"weight": 3.0})]),
        "hashSeq": _graph(node_count, [(2, 3, {"weight": 4.0})]),
        "fastRT": _graph(node_count, [(0, 4, {"weight": 5.0})]),
        "tweetSim": _graph(node_count, [(4, 5, {"weight": 0.75})]),
        "labels": np.asarray(labels, dtype=np.float64),
        "splits": splits,
    }


def _write_payload(path: Path, payload=None) -> bytes:
    raw = pickle.dumps(_payload() if payload is None else payload, protocol=pickle.HIGHEST_PROTOCOL)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(raw)
    return raw


def _load(path: Path, *, campaign="russia", budget=256 * 1024 * 1024):
    module = _load_experiments()
    return module.load_compact_iohunter(
        path,
        campaign=campaign,
        trusted_local=True,
        memory_budget_bytes=budget,
    )


def test_compact_loader_api_exists_before_contract_tests():
    module = _load_experiments()
    assert hasattr(module, "load_compact_iohunter")
    assert hasattr(module, "CompactIOHunterDiscoveryView")
    assert hasattr(module, "CompactIOHunterEvaluator")


def test_discovery_view_is_label_free_and_evaluator_separated(tmp_path):
    first_path = tmp_path / "first.pkl"
    second_path = tmp_path / "second.pkl"
    _write_payload(first_path)
    _write_payload(second_path, _payload(labels=(1, 0, 1, 0, 1, 0), fused_edges=[(0, 5)]))

    first = _load(first_path)
    second = _load(second_path)

    discovery_fields = {field.name for field in dataclasses.fields(first.discovery_view)}
    forbidden = ("label", "fold", "fused", "evaluator", "bot", "harmful", "event")
    assert not any(token in name.lower() for name in discovery_fields for token in forbidden)
    assert not hasattr(first.discovery_view, "events")
    assert first.discovery_view.source_layer_fingerprint == second.discovery_view.source_layer_fingerprint
    assert first.evaluator.content_fingerprint != second.evaluator.content_fingerprint
    serialized_manifest = json.dumps(first.discovery_view.manifest.to_dict(), sort_keys=True)
    assert not any(token in serialized_manifest.lower() for token in forbidden)


def test_compact_edges_are_canonical_read_only_numeric_arrays_and_chunked(tmp_path):
    path = tmp_path / "fixture.pkl"
    _write_payload(path)
    result = _load(path)
    view = result.discovery_view

    assert view.account_count == 6
    assert tuple(view.relation_edges) == ("coRT", "coURL", "fastRT", "hashSeq", "tweetSim")
    assert view.relation_edges["coRT"].endpoints.tolist() == [[0, 1]]
    assert view.relation_edges["coRT"].weights.tolist() == [2.0]
    for relation_edges in view.relation_edges.values():
        assert relation_edges.endpoints.dtype == np.dtype("<u2")
        assert relation_edges.weights.dtype == np.dtype("<f4")
        assert relation_edges.endpoints.flags.writeable is False
        assert relation_edges.weights.flags.writeable is False
        with pytest.raises(ValueError):
            relation_edges.endpoints.setflags(write=True)
        chunks = tuple(relation_edges.iter_chunks(1))
        assert sum(chunk[0].shape[0] for chunk in chunks) == relation_edges.edge_count
    assert result.evaluator.account_labels.dtype == np.dtype("u1")
    assert result.evaluator.account_labels.flags.writeable is False
    assert result.evaluator.fused_edges.endpoints.tolist() == [[0, 1], [1, 2], [3, 4]]


def test_compact_fixture_has_semantic_parity_with_task5_without_identity_aliasing(tmp_path):
    module = _load_experiments()
    path = tmp_path / "fixture.pkl"
    payload = _payload()
    _write_payload(path, payload)

    compact = _load(path).discovery_view
    task5 = module.adapt_iohunter_payload(payload, campaign="russia", seed=42)
    task5_pairs = {
        event.evidence_ref: event.weight
        for event in task5.events
    }
    compact_pairs = {
        f"iohunter:russia:{layer}:pair:{left:06d}-{right:06d}": float(weight)
        for layer, edges in compact.relation_edges.items()
        for (left, right), weight in zip(edges.endpoints.tolist(), edges.weights.tolist(), strict=True)
    }
    assert compact_pairs == task5_pairs
    assert compact.manifest.fingerprint_scope == "iohunter-source-layers/compact-v1"
    assert compact.source_layer_fingerprint != task5.discovery_fingerprint


@pytest.mark.parametrize("weight", [0.0, -1.0, float("inf"), float("nan"), 1e100])
def test_compact_loader_rejects_invalid_or_non_compact_weights(tmp_path, weight):
    path = tmp_path / "bad-weight.pkl"
    payload = _payload()
    payload["coRT"] = _graph(6, [(0, 1, {"weight": weight})])
    _write_payload(path, payload)
    with pytest.raises(ValueError, match="weight"):
        _load(path)


def test_compact_loader_rejects_duplicate_normalized_edges(tmp_path):
    path = tmp_path / "duplicates.pkl"
    payload = _payload()
    graph = nx.MultiGraph()
    graph.add_nodes_from(range(6))
    graph.add_edge(0, 1, weight=1.0)
    graph.add_edge(1, 0, weight=2.0)
    payload["coRT"] = graph
    _write_payload(path, payload)
    with pytest.raises(ValueError, match="duplicate normalized edge"):
        _load(path)


def test_compact_loader_validates_fused_source_label_and_fold_universes(tmp_path):
    module = _load_experiments()
    malformed = []
    bad_fused = _payload()
    bad_fused["graph"].remove_node(5)
    malformed.append((bad_fused, "fused graph"))
    bad_source = _payload()
    for layer in module.IOHUNTER_LAYER_RELATIONS:
        bad_source[layer].remove_node(5)
    malformed.append((bad_source, "source-layer"))
    bad_fold = _payload()
    bad_fold["splits"][0]["test"] = np.asarray([False] * 6, dtype=np.bool_)
    malformed.append((bad_fold, "fold-000"))

    for index, (payload, message) in enumerate(malformed):
        path = tmp_path / f"malformed-{index}.pkl"
        _write_payload(path, payload)
        with pytest.raises(ValueError, match=message):
            _load(path)


def test_compact_loader_requires_exactly_five_official_folds(tmp_path):
    path = tmp_path / "four-folds.pkl"
    payload = _payload()
    del payload["splits"][4]
    _write_payload(path, payload)
    with pytest.raises(ValueError, match="exactly five official folds"):
        _load(path)


def test_compact_loader_hashes_exact_mapped_source_and_requires_trust(tmp_path):
    module = _load_experiments()
    path = tmp_path / "fixture.pkl"
    raw = _write_payload(path)
    with pytest.raises(ValueError, match="trusted_local=True"):
        module.load_compact_iohunter(path, campaign="russia")

    result = _load(path)
    assert result.evaluator.source_path == str(path.resolve())
    assert result.evaluator.source_sha256 == "sha256:" + hashlib.sha256(raw).hexdigest()
    assert result.memory_profile.source_bytes == len(raw)


def test_compact_loader_fails_closed_when_mapped_source_identity_changes(tmp_path, monkeypatch):
    _load_experiments()
    compact_module = sys.modules["research.coordination_experiments.iohunter_compact"]
    path = tmp_path / "fixture.pkl"
    _write_payload(path)
    original = compact_module._unpickle_mapped

    def mutate_after_load(mapped):
        payload = original(mapped)
        path.write_bytes(path.read_bytes() + b"changed")
        return payload

    monkeypatch.setattr(compact_module, "_unpickle_mapped", mutate_after_load)
    with pytest.raises(RuntimeError, match="source identity changed"):
        _load(path)


def test_compact_loader_records_and_enforces_pre_model_memory_budget(tmp_path):
    module = _load_experiments()
    path = tmp_path / "fixture.pkl"
    _write_payload(path)
    with pytest.raises(module.CompactIOHunterMemoryBudgetExceeded) as error:
        _load(path, budget=1)
    profile = error.value.memory_profile
    assert profile.memory_budget_bytes == 1
    assert profile.estimated_peak_bytes > profile.memory_budget_bytes
    assert profile.model_execution_started is False

    loaded = _load(path)
    assert loaded.memory_profile.measured_peak_bytes > 0
    assert loaded.memory_profile.estimated_peak_bytes >= loaded.memory_profile.measured_peak_bytes
    assert loaded.memory_profile.within_budget is True
    assert loaded.memory_profile.model_execution_started is False


def test_compact_fingerprints_are_deterministic_across_graph_insertion_order(tmp_path):
    first = _payload()
    second = _payload()
    for layer in ("graph", "coRT", "coURL", "hashSeq", "fastRT", "tweetSim"):
        graph = second[layer]
        reversed_graph = nx.Graph()
        reversed_graph.add_nodes_from(reversed(tuple(graph.nodes)))
        reversed_graph.add_edges_from(reversed(tuple(graph.edges(data=True))))
        second[layer] = reversed_graph
    first_path = tmp_path / "first.pkl"
    second_path = tmp_path / "second.pkl"
    _write_payload(first_path, first)
    _write_payload(second_path, second)

    first_result = _load(first_path)
    second_result = _load(second_path)
    assert first_result.discovery_view.source_layer_fingerprint == second_result.discovery_view.source_layer_fingerprint
    assert first_result.evaluator.content_fingerprint != second_result.evaluator.content_fingerprint
    assert first_result.evaluator.semantic_content_fingerprint == second_result.evaluator.semantic_content_fingerprint


def test_compact_value_objects_are_frozen(tmp_path):
    path = tmp_path / "fixture.pkl"
    _write_payload(path)
    result = _load(path)
    with pytest.raises(dataclasses.FrozenInstanceError):
        result.discovery_view.account_count = 7
    with pytest.raises(TypeError):
        result.discovery_view.relation_edges["coRT"] = object()
    with pytest.raises(dataclasses.FrozenInstanceError):
        result.evaluator.campaign = "china"
