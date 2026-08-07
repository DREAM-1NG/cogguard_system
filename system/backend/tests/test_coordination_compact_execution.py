from __future__ import annotations

import dataclasses
import importlib
import importlib.util
import inspect
import json
import sys
import types
from pathlib import Path

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


def _edge_array(package, edges, weights=None):
    weights = [1.0] * len(edges) if weights is None else weights
    return package.CompactEdgeArray(
        endpoints=_ro(edges, np.dtype("<u2")),
        weights=_ro(weights, np.dtype("<f4")),
    )


def _discovery_view(package, *, campaign="russia", source_fingerprint=None):
    layers = {}
    for layer, relation in package.IOHUNTER_LAYER_RELATIONS.items():
        edge = [(0, 1)] if layer == "coRT" else []
        layers[layer] = package.CompactRelationEdges(
            endpoints=_ro(edge, np.dtype("<u2")).reshape((len(edge), 2)),
            weights=_ro([1.0] * len(edge), np.dtype("<f4")),
            layer=layer,
            relation=relation,
        )
    return package.CompactIOHunterDiscoveryView(
        campaign=campaign,
        account_count=6,
        relation_edges=layers,
        time_semantics=package.IOHUNTER_STATIC_TIME_SEMANTICS,
        source_layer_fingerprint=source_fingerprint or _sha("a"),
        manifest=package.CompactIOHunterManifest(
            dataset_id=f"iohunter-{campaign}",
            source_size_bytes=1234,
            source_mtime_ns=5678,
        ),
    )


def _fold(package, fold_id="fold-000", *, validation=(0, 1), test=(2, 3)):
    return package.CompactIOHunterFold(
        fold_id=fold_id,
        train_indices=_ro([4, 5], np.dtype("<u2")),
        validation_indices=_ro(validation, np.dtype("<u2")),
        test_indices=_ro(test, np.dtype("<u2")),
    )


def _evaluator(package, *, labels=(0, 1, 1, 0, 0, 1), campaign="russia", fold=None, fused_edges=None, source_path="G:\\fixture\\iohunter.pkl", source_sha=None):
    primary_fold = _fold(package) if fold is None else fold
    folds = [primary_fold]
    for index in range(1, 5):
        folds.append(_fold(package, f"fold-{index:03d}", validation=(0, 1), test=(2, 3)))
    return package.CompactIOHunterEvaluator(
        campaign=campaign,
        account_labels=_ro(labels, np.dtype("u1")),
        official_folds=tuple(folds),
        fused_edges=_edge_array(package, [(0, 1), (2, 3)] if fused_edges is None else fused_edges),
        source_path=source_path,
        source_sha256=source_sha or _sha("b"),
        semantic_content_fingerprint=_sha("c"),
        content_fingerprint=_sha("d"),
    )


def _batch(package, assignments=(0, 0, 1, 1, 2, 2)):
    stage1 = importlib.import_module("research.coordination_discover.stage1.contracts")
    clusters = []
    for cluster_id in sorted(set(assignments)):
        members = tuple(f"account-{index:06d}" for index, value in enumerate(assignments) if value == cluster_id)
        clusters.append(
            stage1.DiscoveredCluster(
                cluster_id=f"cluster-{cluster_id}",
                member_account_ids=members,
                coordination_metrics=stage1.CoordinationMetricSet(
                    tsgs_spectral_density=0.0,
                    mhcr_hyperedge_coherence=0.0,
                    temporal_sync_delta_seconds=0.0,
                    overall_coordination_score=0.0,
                ),
            )
        )
    return stage1.DiscoveredClusterBatch(
        batch_id="compact-batch",
        timestamp="2026-08-07T00:00:00Z",
        candidate_clusters=tuple(clusters),
        provenance=stage1.DiscoveryProvenance(
            snapshot_id="compact-fixture",
            data_fingerprint=_sha("a"),
            source_dataset="iohunter-russia",
            source_event="compact-source-layers",
            stage1_model_version="fixture-compact-v1",
            tsgs_version="not-run",
            mhcr_version="not-run",
            created_at="2026-08-07T00:00:00Z",
            seed=42,
            split_policy="official_static_fold",
            input_event_count=0,
            input_account_count=len(assignments),
            method_config_hash=_sha("e"),
        ),
        runtime_diagnostics=stage1.DiscoveryRuntimeDiagnostics(
            tsgs_seconds=0.0,
            mhcr_seconds=0.0,
            leiden_seconds=0.0,
            total_seconds=0.0,
        ),
    )


def _prediction(package, assignments=(0, 0, 1, 1, 2, 2), scores=(0.1, 0.8, 0.9, 0.2, 0.3, 0.7), edges=((0, 1), (2, 3))):
    return package.CompactDiscoveryPrediction(
        account_count=6,
        candidate_endpoints=_ro(edges, np.dtype("<u2")).reshape((len(edges), 2)),
        edge_scores=_ro([0.5] * len(edges), np.dtype("<f4")),
        account_scores=_ro(scores, np.dtype("<f4")),
        cluster_assignments=_ro(assignments, np.dtype("<i4")),
        discovered_cluster_batch=_batch(package, assignments),
        method_id="fixture_compact",
        method_version="fixture-compact-v1",
        implementation_id="fixture-implementation-v1",
        diagnostics={"rows": 6},
        claim_markers=("iohunter_no_ground_truth_coordination_edges",),
    )


def _execution_input(package, *, view=None, method_config=None):
    return package.CompactDiscoveryExecutionInput(
        discovery_view=view or _discovery_view(package),
        seed=42,
        method_config_version="fixture-compact-v1",
        method_config=method_config or {"alpha": 0.25, "layers": ["coRT"]},
    )


def test_execution_input_fingerprint_excludes_evaluator_labels_folds_fused_and_raw_source():
    package = _load_experiments()
    first = _execution_input(package)
    second = _execution_input(package)
    first_evaluator = _evaluator(package)
    changed_evaluator = _evaluator(
        package,
        labels=(1, 0, 0, 1, 1, 0),
        fold=_fold(package, validation=(2, 3), test=(0, 1)),
        fused_edges=[(4, 5)],
        source_path="G:\\other\\changed.pkl",
        source_sha=_sha("f"),
    )

    field_names = {field.name for field in dataclasses.fields(first)}
    forbidden = ("evaluator", "label", "fold", "fused", "source_path", "source_sha", "bot", "harmful", "verdict", "account_risk")
    assert not any(token in name.lower() for name in field_names for token in forbidden)
    assert first.fingerprint == second.fingerprint
    assert first.fingerprint == _execution_input(package).fingerprint
    assert first_evaluator.account_labels.tolist() != changed_evaluator.account_labels.tolist()
    assert first_evaluator.source_path != changed_evaluator.source_path
    assert first.fingerprint == second.fingerprint
    assert not hasattr(first, "evaluator")
    assert not hasattr(first, "events")


@pytest.mark.parametrize(
    "method_config",
    (
        {"raw_path": "G:\\data\\iohunter.pkl"},
        {"sha256": _sha("a")},
        {"nested": {"source_checksum": _sha("b")}},
    ),
)
def test_execution_input_rejects_raw_provenance_aliases(method_config):
    package = _load_experiments()
    with pytest.raises(ValueError, match="evaluator-only key"):
        _execution_input(package, method_config=method_config)


def test_execution_input_allows_non_provenance_hyperparameter_names():
    package = _load_experiments()
    execution_input = _execution_input(
        package,
        method_config={"shared_dimension": 32, "relation_weight": 0.25},
    )

    assert execution_input.method_config["shared_dimension"] == 32


def test_execution_resolves_compact_implementation_without_evaluator_or_coordination_events():
    package = _load_experiments()
    compact_module = importlib.import_module("research.coordination_experiments.compact_execution")
    seen = []

    class FixtureCompactImplementation:
        method_id = "fixture_compact"
        method_version = "fixture-compact-v1"
        implementation_id = "fixture-implementation-v1"
        unavailable_reason = None

        def execute(self, execution_input):
            seen.append(execution_input)
            assert type(execution_input) is package.CompactDiscoveryExecutionInput
            assert not hasattr(execution_input, "evaluator")
            assert not hasattr(execution_input, "labels")
            assert not hasattr(execution_input, "events")
            return _prediction(package)

    signature = inspect.signature(package.execute_compact_discovery_method)
    assert "evaluator" not in signature.parameters
    outcome = package.execute_compact_discovery_method(
        {"fixture_compact": FixtureCompactImplementation()},
        "fixture_compact",
        _execution_input(package),
    )

    assert outcome.status == "success"
    assert outcome.prediction is not None
    assert len(seen) == 1
    assert "CoordinationEvent" not in Path(compact_module.__file__).read_text(encoding="utf-8")


def test_execution_rejects_prediction_from_a_different_discovery_campaign():
    package = _load_experiments()

    class RussiaPredictionImplementation:
        method_id = "fixture_compact"
        method_version = "fixture-compact-v1"
        implementation_id = "fixture-implementation-v1"
        unavailable_reason = None

        def execute(self, execution_input):
            return _prediction(package)

    outcome = package.execute_compact_discovery_method(
        {"fixture_compact": RussiaPredictionImplementation()},
        "fixture_compact",
        _execution_input(package, view=_discovery_view(package, campaign="china")),
    )

    assert outcome.status == "failed"
    assert "campaign" in outcome.reason


def test_evaluator_access_occurs_only_after_implementation_returns(monkeypatch):
    package = _load_experiments()
    log = []
    evaluator = _evaluator(package)
    evaluation = package.IOHunterExternalEvaluationInput(
        evaluator=evaluator,
        fold=evaluator.official_folds[0],
        evaluation_config={"threshold_objective": "macro_f1"},
    )
    original_labels = package.CompactIOHunterEvaluator.account_labels

    def observed_labels(instance):
        log.append("labels")
        return original_labels.__get__(instance, type(instance))

    monkeypatch.setattr(
        package.CompactIOHunterEvaluator,
        "account_labels",
        property(observed_labels),
    )
    log.clear()

    class SpyImplementation:
        method_id = "fixture_compact"
        method_version = "fixture-compact-v1"
        implementation_id = "fixture-implementation-v1"
        unavailable_reason = None

        def execute(self, execution_input):
            log.append("implementation")
            return _prediction(package)

    outcome = package.execute_compact_discovery_method(
        {"fixture_compact": SpyImplementation()},
        "fixture_compact",
        _execution_input(package),
    )
    log.append("before-evaluation")
    result = package.evaluate_iohunter_external_account_recovery(outcome.prediction, evaluation)

    assert log == ["implementation", "before-evaluation", "labels"]
    assert result.status == "success"
    assert result.audit["evaluation_after_execution"] is True


def test_prediction_arrays_are_immutable_sorted_finite_bounded_and_cluster_complete():
    package = _load_experiments()
    prediction = _prediction(package)
    assert prediction.candidate_endpoints.flags.writeable is False
    assert prediction.edge_scores.flags.writeable is False
    assert prediction.account_scores.flags.writeable is False
    assert prediction.cluster_assignments.flags.writeable is False
    with pytest.raises(ValueError, match="sorted"):
        _prediction(package, edges=((2, 3), (0, 1)))
    with pytest.raises(ValueError, match="duplicate"):
        _prediction(package, edges=((0, 1), (0, 1)))
    with pytest.raises(ValueError, match="outside"):
        _prediction(package, edges=((0, 7),))
    with pytest.raises(ValueError, match="finite"):
        package.CompactDiscoveryPrediction(
            account_count=6,
            candidate_endpoints=_ro([(0, 1)], np.dtype("<u2")),
            edge_scores=_ro([float("nan")], np.dtype("<f4")),
            account_scores=_ro([0.1] * 6, np.dtype("<f4")),
            cluster_assignments=_ro([0, 0, 1, 1, 2, 2], np.dtype("<i4")),
            discovered_cluster_batch=_batch(package),
            method_id="fixture_compact",
            method_version="fixture-compact-v1",
            implementation_id="fixture-implementation-v1",
        )


def test_prediction_detaches_from_caller_owned_array_storage():
    package = _load_experiments()
    endpoints = _ro([(0, 1)], np.dtype("<u2"))
    prediction = package.CompactDiscoveryPrediction(
        account_count=6,
        candidate_endpoints=endpoints,
        edge_scores=_ro([0.5], np.dtype("<f4")),
        account_scores=_ro([0.1] * 6, np.dtype("<f4")),
        cluster_assignments=_ro([0, 0, 1, 1, 2, 2], np.dtype("<i4")),
        discovered_cluster_batch=_batch(package),
        method_id="fixture_compact",
        method_version="fixture-compact-v1",
        implementation_id="fixture-implementation-v1",
    )
    endpoints.setflags(write=True)
    endpoints[0, 0] = 4
    assert prediction.candidate_endpoints.tolist() == [[0, 1]]
    with pytest.raises(ValueError):
        prediction.candidate_endpoints.setflags(write=True)
    with pytest.raises(ValueError, match="cover every account"):
        _prediction(package, assignments=(0, 0, 1, 1, 2))
    with pytest.raises(ValueError, match="batch member universe"):
        package.CompactDiscoveryPrediction(
            account_count=6,
            candidate_endpoints=_ro([(0, 1)], np.dtype("<u2")),
            edge_scores=_ro([0.5], np.dtype("<f4")),
            account_scores=_ro([0.1] * 6, np.dtype("<f4")),
            cluster_assignments=_ro([0, 0, 1, 1, 2, 2], np.dtype("<i4")),
            discovered_cluster_batch=_batch(package, assignments=(0, 0, 1, 1, 2, 3)),
            method_id="fixture_compact",
            method_version="fixture-compact-v1",
            implementation_id="fixture-implementation-v1",
        )


def test_external_evaluation_validates_campaign_and_uses_validation_threshold_only():
    package = _load_experiments()
    fold = _fold(package, validation=(0, 1), test=(2, 3, 4, 5))
    evaluator = _evaluator(package, labels=(0, 1, 0, 1, 1, 0), fold=fold)
    prediction = _prediction(
        package,
        scores=(0.60, 0.55, 0.99, 0.20, 0.10, 0.90),
    )
    evaluation = package.IOHunterExternalEvaluationInput(
        evaluator=evaluator,
        fold=evaluator.official_folds[0],
        evaluation_config={"threshold_objective": "macro_f1"},
    )

    result = package.evaluate_iohunter_external_account_recovery(prediction, evaluation)

    assert result.status == "success"
    assert result.threshold == pytest.approx(0.55)
    assert result.threshold_source == "validation_only"
    assert result.metrics["external_account_macro_f1"] == pytest.approx(0.0)
    assert result.metrics["external_account_recall_at_k"] == pytest.approx(0.0)
    assert result.metrics["external_account_evaluated_count"] == 4
    assert result.evaluation_scope == "external_account_recovery_not_coordination_ground_truth"
    assert result.label_semantics == "1=information-operation account; 0=non-IO account"
    assert "iohunter_no_ground_truth_coordination_edges" in result.claim_markers
    assert "iohunter_no_ground_truth_communities" in result.claim_markers
    assert "iohunter_no_causal_campaign_labels" in result.claim_markers
    assert all(name.startswith(("external_account_", "topology_proxy_")) for name in result.metrics)
    assert result.execution_artifact_identity == prediction.artifact_identity
    assert result.fold_fingerprint == package.compact_fold_fingerprint(evaluator.official_folds[0])
    assert result.to_dict()["execution_artifact_identity"] == prediction.artifact_identity
    assert result.to_dict()["fold_fingerprint"] == result.fold_fingerprint
    banned = ("edge_auprc", "true_community", "harmful_cib", "causal_coordination")
    assert not any(token in json.dumps(result.to_dict(), sort_keys=True).lower() for token in banned)

    mismatched = package.IOHunterExternalEvaluationInput(
        evaluator=_evaluator(package, campaign="china"),
        fold=_evaluator(package, campaign="china").official_folds[0],
        evaluation_config={},
    )
    with pytest.raises(ValueError, match="campaign"):
        package.evaluate_iohunter_external_account_recovery(prediction, mismatched)


def test_external_evaluation_blocks_one_class_validation_or_test_partitions():
    package = _load_experiments()
    one_class_validation = _evaluator(package, labels=(0, 0, 0, 1, 0, 1))
    validation_prediction = _prediction(package)
    validation_result = package.evaluate_iohunter_external_account_recovery(
        validation_prediction,
        package.IOHunterExternalEvaluationInput(
            evaluator=one_class_validation,
            fold=one_class_validation.official_folds[0],
            evaluation_config={},
        ),
    )
    assert validation_result.status == "blocked"
    assert "validation partition has one class" in validation_result.reason
    assert validation_result.execution_artifact_identity == validation_prediction.artifact_identity
    assert validation_result.fold_fingerprint == package.compact_fold_fingerprint(
        one_class_validation.official_folds[0]
    )

    fold = _fold(package, validation=(0, 1), test=(2, 4))
    one_class_test = _evaluator(package, labels=(0, 1, 1, 0, 1, 0), fold=fold)
    test_prediction = _prediction(package)
    test_result = package.evaluate_iohunter_external_account_recovery(
        test_prediction,
        package.IOHunterExternalEvaluationInput(
            evaluator=one_class_test,
            fold=one_class_test.official_folds[0],
            evaluation_config={},
        ),
    )
    assert test_result.status == "blocked"
    assert "test partition has one class" in test_result.reason
    assert test_result.execution_artifact_identity == test_prediction.artifact_identity
    assert test_result.fold_fingerprint == package.compact_fold_fingerprint(one_class_test.official_folds[0])


def test_external_evaluation_requires_the_exact_owned_fold_partitions():
    package = _load_experiments()
    evaluator = _evaluator(package)
    changed_validation = package.CompactIOHunterFold(
        fold_id="fold-000",
        train_indices=_ro([0, 1], np.dtype("<u2")),
        validation_indices=_ro([4, 5], np.dtype("<u2")),
        test_indices=_ro([2, 3], np.dtype("<u2")),
    )

    with pytest.raises(ValueError, match="does not belong"):
        package.IOHunterExternalEvaluationInput(
            evaluator=evaluator,
            fold=changed_validation,
            evaluation_config={},
        )
