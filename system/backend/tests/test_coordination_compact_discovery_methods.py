from __future__ import annotations

import dataclasses
import importlib
import importlib.util
import inspect
import sys
import types

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


def _ro(values, dtype):
    array = np.ascontiguousarray(values, dtype=dtype)
    array.setflags(write=False)
    return array


def _sha(char: str) -> str:
    return "sha256:" + char * 64


def _view(package, account_count: int = 6):
    layers = {}
    layer_edges = {
        "coRT": [(0, 1), (1, 2), (0, 1)],
        "coURL": [(0, 1), (2, 3)],
        "hashSeq": [(1, 2), (3, 4)],
        "fastRT": [(0, 2)],
        "tweetSim": [(4, 5)],
    }
    layer_weights = {
        "coRT": [1.0, 0.8, 0.4],
        "coURL": [0.5, 0.9],
        "hashSeq": [0.7, 0.6],
        "fastRT": [0.3],
        "tweetSim": [0.2],
    }
    for layer, relation in package.IOHUNTER_LAYER_RELATIONS.items():
        edges = layer_edges[layer]
        layers[layer] = package.CompactRelationEdges(
            endpoints=_ro(edges, np.dtype("<u2")),
            weights=_ro(layer_weights[layer], np.dtype("<f4")),
            layer=layer,
            relation=relation,
        )
    return package.CompactIOHunterDiscoveryView(
        campaign="russia",
        account_count=account_count,
        relation_edges=layers,
        time_semantics=package.IOHUNTER_STATIC_TIME_SEMANTICS,
        source_layer_fingerprint=_sha("a"),
        manifest=package.CompactIOHunterManifest(
            dataset_id="iohunter-russia",
            source_size_bytes=1234,
            source_mtime_ns=5678,
        ),
    )


def _input(package, *, account_count: int = 6, config=None):
    return package.CompactDiscoveryExecutionInput(
        discovery_view=_view(package, account_count),
        seed=42,
        method_config_version="compact-test-v1",
        method_config=config or {"max_candidate_edges": 8, "batch_size": 4},
    )


def _input_with_seed(package, seed: int):
    return dataclasses.replace(_input(package), seed=seed)


def test_compact_registry_exposes_candidate_fair_baseline_and_explicit_blocks():
    package = _load_experiments()
    registry = package.default_compact_discovery_registry()

    assert {
        "tsgs_mhcr_compact",
        "edgebank",
        "dense_cosine_leiden",
        "frozen_system_evidence_prior",
        "no_tsgs",
        "no_mhcr",
        "no_relation_specific",
        "no_temporal_augmentation",
        "tgn_style_memory_prior",
    } <= set(registry.method_ids())
    assert registry.implementation("tgn_style_memory_prior").unavailable_reason
    assert registry.implementation("no_temporal_augmentation").unavailable_reason
    assert registry.implementation("frozen_system_evidence_prior").unavailable_reason is None


def test_frozen_system_baseline_executes_canonical_static_graph_core_without_seed_variance():
    package = _load_experiments()
    implementation = package.default_compact_discovery_registry().implementation(
        "frozen_system_evidence_prior"
    )

    first = package.execute_compact_discovery_method(
        {"frozen_system_evidence_prior": implementation},
        "frozen_system_evidence_prior",
        _input_with_seed(package, 42),
    )
    second = package.execute_compact_discovery_method(
        {"frozen_system_evidence_prior": implementation},
        "frozen_system_evidence_prior",
        _input_with_seed(package, 46),
    )

    assert first.status == second.status == "success"
    assert first.prediction is not None and second.prediction is not None
    assert np.array_equal(first.prediction.candidate_endpoints, second.prediction.candidate_endpoints)
    assert np.array_equal(first.prediction.edge_scores, second.prediction.edge_scores)
    assert np.array_equal(first.prediction.account_scores, second.prediction.account_scores)
    assert first.prediction.diagnostics["method_role"] == "frozen_production_evidence_baseline"
    assert first.prediction.diagnostics["clustering"]["backend"] == "networkx_greedy_modularity"
    assert first.prediction.diagnostics["account_score_formula"] == (
        "normalized_production_weighted_degree"
    )
    assert first.prediction.diagnostics["projection_cache_hit"] is False
    assert second.prediction.diagnostics["projection_cache_hit"] is True
    assert first.prediction.diagnostics["runtime_budget_occurrence_limit"] == 100_000
    assert "production_graph_core_only_no_event_snapshot_evidence_extraction" in (
        first.prediction.claim_markers
    )
    assert "production_dynamic_windows_not_evaluated" in first.prediction.claim_markers


def test_frozen_system_baseline_blocks_instead_of_truncating_over_runtime_budget(monkeypatch):
    package = _load_experiments()
    compact = importlib.import_module("research.coordination_experiments.compact_discovery_methods")
    monkeypatch.setattr(compact, "_PRODUCTION_STATIC_PROXY_MAX_OCCURRENCES", 1)
    implementation = package.default_compact_discovery_registry().implementation(
        "frozen_system_evidence_prior"
    )

    outcome = package.execute_compact_discovery_method(
        {"frozen_system_evidence_prior": implementation},
        "frozen_system_evidence_prior",
        _input_with_seed(package, 42),
    )

    assert outcome.status == "blocked"
    assert "runtime budget" in str(outcome.reason)
    assert "does not truncate" in str(outcome.reason)


def test_frozen_system_baseline_releases_cached_campaign_before_a_blocked_campaign(monkeypatch):
    package = _load_experiments()
    compact = importlib.import_module("research.coordination_experiments.compact_discovery_methods")
    implementation = package.default_compact_discovery_registry().implementation(
        "frozen_system_evidence_prior"
    )
    first = package.execute_compact_discovery_method(
        {"frozen_system_evidence_prior": implementation},
        "frozen_system_evidence_prior",
        _input_with_seed(package, 42),
    )
    assert first.status == "success"
    assert implementation._projection_cache

    monkeypatch.setattr(compact, "_PRODUCTION_STATIC_PROXY_MAX_OCCURRENCES", 1)
    next_view = dataclasses.replace(_view(package), source_layer_fingerprint=_sha("b"))
    blocked_input = dataclasses.replace(_input(package), discovery_view=next_view)
    blocked = package.execute_compact_discovery_method(
        {"frozen_system_evidence_prior": implementation},
        "frozen_system_evidence_prior",
        blocked_input,
    )

    assert blocked.status == "blocked"
    assert implementation._projection_cache == {}


def test_candidate_is_label_free_deterministic_and_graph_native():
    package = _load_experiments()
    compact = importlib.import_module("research.coordination_experiments.compact_discovery_methods")
    implementation = package.default_compact_discovery_registry().implementation("tsgs_mhcr_compact")
    execution_input = _input(package)
    assert "evaluator" not in {field.name for field in dataclasses.fields(execution_input)}
    assert "CoordinationEvent" not in inspect.getsource(compact)
    assert "[tuple(edge) for edge in endpoints]" not in inspect.getsource(compact)
    first = package.execute_compact_discovery_method(
        {"tsgs_mhcr_compact": implementation}, "tsgs_mhcr_compact", execution_input
    )
    second = package.execute_compact_discovery_method(
        {"tsgs_mhcr_compact": implementation}, "tsgs_mhcr_compact", execution_input
    )

    assert first.status == second.status == "success"
    assert first.prediction is not None and second.prediction is not None
    assert first.prediction.artifact_identity == second.prediction.artifact_identity
    assert len(first.prediction.candidate_endpoints) <= 8
    assert first.prediction.candidate_endpoints.flags.writeable is False
    assert first.prediction.edge_scores.flags.writeable is False
    assert first.prediction.discovered_cluster_batch.provenance.label_policy == "stage1_label_free"
    assert first.prediction.diagnostics["mhcr"]["objective"] == "self_supervised_infonce"
    assert first.prediction.diagnostics["tsgs"]["guarantee_scope"] == "explicit_compact_source_union"
    assert first.prediction.diagnostics["edge_score_formula"] == (
        "normalized_tsgs_evidence_weight_times_mhcr_affinity"
    )
    feature_names = first.prediction.diagnostics["mhcr"]["feature_names"]
    assert len(feature_names) == len(set(feature_names)) == 10


def test_edgebank_is_available_on_static_data_and_carries_static_claim_marker():
    package = _load_experiments()
    implementation = package.default_compact_discovery_registry().implementation("edgebank")
    outcome = package.execute_compact_discovery_method(
        {"edgebank": implementation}, "edgebank", _input(package)
    )

    assert outcome.status == "success"
    assert outcome.prediction is not None
    assert "static_placeholder_not_observed_time" in outcome.prediction.claim_markers
    assert outcome.prediction.diagnostics["method_role"] == "static_edge_memory_baseline"
    assert outcome.prediction.diagnostics["edge_score_formula"] == "static_normalized_edge_weight"
    assert outcome.prediction.diagnostics["tsgs"]["resistance_backend"] == "not_run_static_edgebank"


def test_execution_method_config_overrides_are_applied_without_evaluator_fields():
    package = _load_experiments()
    implementation = package.default_compact_discovery_registry().implementation("edgebank")
    outcome = package.execute_compact_discovery_method(
        {"edgebank": implementation},
        "edgebank",
        _input(package, config={"max_candidate_edges": 1}),
    )

    assert outcome.status == "success"
    assert outcome.prediction is not None
    assert len(outcome.prediction.candidate_endpoints) <= 1


def test_tsgs_reports_exact_and_approximate_backend_without_overclaiming():
    package = _load_experiments()
    registry = package.default_compact_discovery_registry()
    exact = registry.implementation("tsgs_mhcr_compact")
    exact_outcome = package.execute_compact_discovery_method(
        {"tsgs_mhcr_compact": exact}, "tsgs_mhcr_compact", _input(package)
    )
    assert exact_outcome.prediction is not None
    assert exact_outcome.prediction.diagnostics["tsgs"]["resistance_backend"] == "exact_laplacian_pseudoinverse"
    approximate = package.GraphNativeDiscoveryImplementation(
        method_id="tsgs_mhcr_compact",
        method_version="tsgs-mhcr-compact-v1",
        implementation_id="fixture-approximate-v1",
        config=package.CompactDiscoveryMethodConfig(
            method_variant="tsgs_mhcr_compact",
            exact_pseudoinverse_node_limit=2,
        ),
    )
    approximate_outcome = package.execute_compact_discovery_method(
        {"tsgs_mhcr_compact": approximate}, "tsgs_mhcr_compact", _input(package)
    )
    assert approximate_outcome.prediction is not None
    assert approximate_outcome.prediction.diagnostics["tsgs"]["resistance_backend"] == "degree_leverage_approximation"
    assert approximate_outcome.prediction.diagnostics["tsgs"]["spectral_guarantee"] == "approximate_no_exact_guarantee"


def test_dense_baseline_blocks_when_account_limit_is_exceeded():
    package = _load_experiments()
    implementation = package.GraphNativeDiscoveryImplementation(
        method_id="dense_cosine_leiden",
        method_version="dense-cosine-leiden-v1",
        implementation_id="fixture-dense-v1",
        config=package.CompactDiscoveryMethodConfig(
            method_variant="dense_cosine_leiden",
            dense_feasible_account_limit=4,
        ),
    )
    outcome = package.execute_compact_discovery_method(
        {"dense_cosine_leiden": implementation}, "dense_cosine_leiden", _input(package)
    )

    assert outcome.status == "blocked"
    assert "feasibility limit" in outcome.reason


def test_dense_baseline_executes_within_its_declared_limit_and_sorts_endpoints():
    package = _load_experiments()
    implementation = package.default_compact_discovery_registry().implementation("dense_cosine_leiden")
    outcome = package.execute_compact_discovery_method(
        {"dense_cosine_leiden": implementation}, "dense_cosine_leiden", _input(package)
    )

    assert outcome.status == "success"
    assert outcome.prediction is not None
    endpoints = outcome.prediction.candidate_endpoints
    assert np.all(endpoints[:-1, 0] < endpoints[1:, 0]) or np.all(
        (endpoints[:-1, 0] < endpoints[1:, 0])
        | ((endpoints[:-1, 0] == endpoints[1:, 0]) & (endpoints[:-1, 1] < endpoints[1:, 1]))
    )


@pytest.mark.parametrize(
    ("method_id", "diagnostic_path", "expected"),
    (
        ("no_tsgs", ("tsgs", "resistance_backend"), "not_run_input_union"),
        ("no_mhcr", ("mhcr", "objective"), "not_run_normalized_input_representation"),
        ("no_relation_specific", ("mhcr", "relation_transform_count"), 1),
    ),
)
def test_static_ablation_implementations_change_their_declared_component(method_id, diagnostic_path, expected):
    package = _load_experiments()
    implementation = package.default_compact_discovery_registry().implementation(method_id)
    outcome = package.execute_compact_discovery_method(
        {method_id: implementation}, method_id, _input(package)
    )

    assert outcome.status == "success"
    assert outcome.prediction is not None
    diagnostics = outcome.prediction.diagnostics
    assert diagnostics[diagnostic_path[0]][diagnostic_path[1]] == expected


def test_static_iohunter_temporal_methods_are_blocked_not_faked():
    package = _load_experiments()
    registry = package.default_compact_discovery_registry()
    for method_id in ("tgn_style_memory_prior", "no_temporal_augmentation"):
        outcome = package.execute_compact_discovery_method(
            {method_id: registry.implementation(method_id)}, method_id, _input(package)
        )
        assert outcome.status == "blocked"
        assert "observed timestamps" in outcome.reason
