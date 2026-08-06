from __future__ import annotations

import importlib
import inspect
import json
import math
import sys
import types
from dataclasses import FrozenInstanceError, replace
from pathlib import Path

import numpy as np
import pytest

from app.config import PROJECT_ROOT


def _load_stage2():
    package_name = "_test_cogguard_coordination_stage2"
    package_dir = PROJECT_ROOT / "research" / "coordination_detect"
    if package_name not in sys.modules:
        package = types.ModuleType(package_name)
        package.__package__ = package_name
        package.__path__ = [str(package_dir)]
        sys.modules[package_name] = package
    return types.SimpleNamespace(
        contracts=importlib.import_module(f"{package_name}.contracts"),
        features=importlib.import_module(f"{package_name}.features"),
        baseline=importlib.import_module(f"{package_name}.heuristic_baseline"),
        learned=importlib.import_module(f"{package_name}.learned"),
        engine=importlib.import_module(f"{package_name}.engine"),
    )


def _load_stage1():
    package_name = "_test_cogguard_coordination_stage1_for_stage2"
    cached = sys.modules.get(package_name)
    if cached is not None:
        return cached
    package_dir = PROJECT_ROOT / "research" / "coordination_discover" / "stage1"
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


@pytest.fixture(scope="module")
def stage2():
    return _load_stage2()


@pytest.fixture
def schema(stage2):
    return stage2.contracts.DetectionFeatureSchema(
        version="fixture-features/v1",
        names=("signal", "context"),
    )


def _case(stage2, schema, case_id, split, label, values, *, cluster_id=None, names=None):
    return stage2.contracts.DetectionTrainingCase(
        case_id=case_id,
        cluster_id=cluster_id or f"cluster-{case_id}",
        split=split,
        label=label,
        feature_schema_version=schema.version,
        feature_schema_fingerprint=schema.fingerprint,
        feature_names=names or schema.names,
        feature_values=tuple(values),
        provenance={"dataset": "stage2-fixture", "row": case_id},
    )


def _fit_fixture(stage2, schema, *, permute_train_labels=False):
    rows = [
        ("t1", 0, (-3.0, -1.0)),
        ("t2", 0, (-2.0, 0.5)),
        ("t3", 1, (0.5, -2.0)),
        ("t4", 1, (3.5, 1.5)),
        ("t5", 1, (2.0, -0.5)),
        ("t6", 0, (-0.5, 2.5)),
    ]
    if permute_train_labels:
        labels = [1, 0, 1, 0, 0, 1]
        rows = [(case_id, labels[index], values) for index, (case_id, _, values) in enumerate(rows)]
    train = [_case(stage2, schema, case_id, "train", label, values) for case_id, label, values in rows]
    validation = [
        _case(stage2, schema, "v1", "validation", 0, (-2.5, -0.5)),
        _case(stage2, schema, "v2", "validation", 0, (-1.0, 1.5)),
        _case(stage2, schema, "v3", "validation", 1, (1.0, -1.5)),
        _case(stage2, schema, "v4", "validation", 1, (3.0, 1.0)),
    ]
    detector = stage2.learned.LearnedCoordinationDetector(schema=schema)
    return detector, detector.fit(train, validation), train, validation


def _stage1_batch(*, cluster_count=1):
    stage1 = _load_stage1()
    contracts = sys.modules[f"{stage1.__name__}.contracts"]
    metrics = stage1.CoordinationMetricSet(
        tsgs_spectral_density=0.72,
        mhcr_hyperedge_coherence=0.81,
        temporal_sync_delta_seconds=8.0,
        overall_coordination_score=0.76,
        evidence_coverage=0.9,
        relation_diversity=0.6,
    )
    first_cluster = stage1.DiscoveredCluster(
        cluster_id="candidate-1",
        member_account_ids=("a", "b", "c"),
        coordination_metrics=metrics,
    )
    clusters = (first_cluster,)
    if cluster_count == 2:
        clusters += (
            stage1.DiscoveredCluster(
                cluster_id="candidate-2",
                member_account_ids=("d", "e"),
                coordination_metrics=metrics,
            ),
        )
    return stage1.DiscoveredClusterBatch(
        batch_id="batch-1",
        timestamp="2026-08-07T00:00:00Z",
        candidate_clusters=clusters,
        provenance=stage1.DiscoveryProvenance(
            snapshot_id="snapshot-1",
            data_fingerprint="sha256:data",
            source_dataset="fixture",
            source_event="event-1",
            stage1_model_version="stage1-v1",
            tsgs_version="tsgs-v1",
            mhcr_version="mhcr-v1",
            created_at="2026-08-07T00:00:00Z",
            seed=7,
            split_policy="label_sealed",
        ),
        runtime_diagnostics=contracts.DiscoveryRuntimeDiagnostics(
            tsgs_seconds=0.1,
            mhcr_seconds=0.1,
            leiden_seconds=0.1,
            total_seconds=0.3,
        ),
    )


def _fit_single_feature_fixture(stage2):
    schema = stage2.contracts.DetectionFeatureSchema(
        version="single-feature/v1",
        names=("caller_signal",),
    )
    train = [
        _case(stage2, schema, "single-t1", "train", 0, (-3.0,)),
        _case(stage2, schema, "single-t2", "train", 0, (-1.0,)),
        _case(stage2, schema, "single-t3", "train", 1, (1.0,)),
        _case(stage2, schema, "single-t4", "train", 1, (3.0,)),
    ]
    validation = [
        _case(stage2, schema, "single-v1", "validation", 0, (-2.0,)),
        _case(stage2, schema, "single-v2", "validation", 0, (-0.5,)),
        _case(stage2, schema, "single-v3", "validation", 1, (0.5,)),
        _case(stage2, schema, "single-v4", "validation", 1, (2.0,)),
    ]
    detector = stage2.learned.LearnedCoordinationDetector(schema=schema)
    return detector, detector.fit(train, validation), schema


def test_learned_coefficients_and_predictions_change_when_train_labels_are_permuted(stage2, schema):
    detector, artifact, _, _ = _fit_fixture(stage2, schema)
    permuted_detector, permuted_artifact, _, _ = _fit_fixture(
        stage2, schema, permute_train_labels=True
    )

    assert not np.allclose(artifact.coefficients, permuted_artifact.coefficients)

    probe_schema = stage2.contracts.DetectionFeatureSchema(
        version="fixture-features/v1", names=("signal", "context")
    )
    probe = _case(stage2, probe_schema, "probe", "validation", 0, (2.2, -0.8))
    first = detector.predict_feature_rows((probe,)).verdicts[0]
    second = permuted_detector.predict_feature_rows((probe,)).verdicts[0]
    assert not math.isclose(first.harmful_probability, second.harmful_probability)


def test_train_fit_excludes_validation_and_records_separate_split_provenance(stage2, schema):
    _, artifact, train, validation = _fit_fixture(stage2, schema)
    changed_validation = [
        _case(stage2, schema, "x1", "validation", 0, (-30.0, -20.0)),
        _case(stage2, schema, "x2", "validation", 0, (-20.0, 30.0)),
        _case(stage2, schema, "x3", "validation", 1, (20.0, -30.0)),
        _case(stage2, schema, "x4", "validation", 1, (30.0, 20.0)),
    ]
    changed = stage2.learned.LearnedCoordinationDetector(schema=schema).fit(
        train, changed_validation
    )

    assert changed.scaler_mean == artifact.scaler_mean
    assert changed.scaler_scale == artifact.scaler_scale
    assert changed.coefficients == artifact.coefficients
    assert changed.intercept == artifact.intercept
    assert artifact.validation_ood_min == tuple(
        min(case.feature_values[index] for case in validation)
        for index in range(len(schema.names))
    )
    assert artifact.validation_ood_max == tuple(
        max(case.feature_values[index] for case in validation)
        for index in range(len(schema.names))
    )
    assert artifact.train_fit_case_ids_fingerprint == stage2.contracts.case_id_fingerprint(
        case.case_id for case in train
    )
    validation_fingerprint = stage2.contracts.case_id_fingerprint(
        case.case_id for case in validation
    )
    assert artifact.validation_calibration_case_ids_fingerprint == validation_fingerprint
    assert artifact.validation_threshold_case_ids_fingerprint == validation_fingerprint
    assert artifact.validation_ood_case_ids_fingerprint == validation_fingerprint
    assert "test" not in json.dumps(artifact.to_dict(), sort_keys=True).lower()


@pytest.mark.parametrize(
    "mutation, match",
    [
        ("overlap", "disjoint"),
        ("duplicate_train", "duplicate"),
        ("duplicate_validation", "duplicate"),
        ("duplicate_cluster", "cluster IDs"),
        ("overlap_cluster", "cluster IDs.*disjoint"),
        ("one_class_train", "both classes"),
        ("one_class_validation", "both classes"),
        ("test_split", "split"),
        ("schema_version", "schema"),
        ("schema_reordered", "ordered"),
        ("non_finite", "finite"),
    ],
)
def test_fit_fails_closed_for_split_id_class_and_schema_violations(
    stage2, schema, mutation, match
):
    _, _, train, validation = _fit_fixture(stage2, schema)
    if mutation == "overlap":
        validation[0] = _case(stage2, schema, train[0].case_id, "validation", 0, (-2.0, 0.0))
    elif mutation == "duplicate_train":
        train.append(train[0])
    elif mutation == "duplicate_validation":
        validation.append(validation[0])
    elif mutation == "duplicate_cluster":
        train[1] = _case(
            stage2,
            schema,
            "distinct-case",
            "train",
            train[1].label,
            train[1].feature_values,
            cluster_id=train[0].cluster_id,
        )
    elif mutation == "overlap_cluster":
        validation[0] = _case(
            stage2,
            schema,
            "distinct-validation-case",
            "validation",
            validation[0].label,
            validation[0].feature_values,
            cluster_id=train[0].cluster_id,
        )
    elif mutation == "one_class_train":
        train = [_case(stage2, schema, f"ot{i}", "train", 0, case.feature_values) for i, case in enumerate(train)]
    elif mutation == "one_class_validation":
        validation = [_case(stage2, schema, f"ov{i}", "validation", 1, case.feature_values) for i, case in enumerate(validation)]
    elif mutation == "test_split":
        train[0] = _case(stage2, schema, "test-row", "test", 0, (-2.0, 0.0))
    elif mutation == "schema_version":
        train[0] = stage2.contracts.DetectionTrainingCase(
            case_id="wrong-schema",
            cluster_id="wrong-schema-cluster",
            split="train",
            label=0,
            feature_schema_version="fixture-features/v2",
            feature_schema_fingerprint=schema.fingerprint,
            feature_names=schema.names,
            feature_values=(-2.0, 0.0),
            provenance={"dataset": "fixture"},
        )
    elif mutation == "schema_reordered":
        train[0] = _case(
            stage2,
            schema,
            "reordered",
            "train",
            0,
            (-2.0, 0.0),
            names=tuple(reversed(schema.names)),
        )
    elif mutation == "non_finite":
        train[0] = _case(stage2, schema, "nan-row", "train", 0, (math.nan, 0.0))

    with pytest.raises(ValueError, match=match):
        stage2.learned.LearnedCoordinationDetector(schema=schema).fit(train, validation)


def test_artifact_serialization_hashing_and_contracts_are_stable_and_immutable(
    stage2, schema, tmp_path: Path
):
    _, artifact, _, _ = _fit_fixture(stage2, schema)
    first = tmp_path / "first.json"
    second = tmp_path / "second.json"

    artifact.to_json(first)
    restored = stage2.contracts.DetectionModelArtifact.from_json(first)
    restored.to_json(second)

    assert first.read_bytes() == second.read_bytes()
    assert restored == artifact
    assert restored.artifact_hash == artifact.artifact_hash
    assert restored.artifact_hash.startswith("sha256:")
    assert restored.optimizer_config["algorithm"] == "full_batch_l2_logistic_regression"
    with pytest.raises(FrozenInstanceError):
        restored.intercept = 0.0
    with pytest.raises(TypeError):
        restored.optimizer_config["seed"] = 99


def test_restored_artifact_reproduces_predictions_and_prediction_identity(
    stage2, schema, tmp_path: Path
):
    detector, artifact, _, _ = _fit_fixture(stage2, schema)
    artifact_path = tmp_path / "artifact.json"
    artifact.to_json(artifact_path)
    restored = stage2.contracts.DetectionModelArtifact.from_json(artifact_path)
    fresh_detector = stage2.learned.LearnedCoordinationDetector(
        schema=restored.feature_schema,
        artifact=restored,
    )
    rows = (
        _case(stage2, schema, "reload-1", "validation", 0, (-0.5, 0.5)),
        _case(stage2, schema, "reload-2", "validation", 1, (0.5, -0.5)),
    )

    original_prediction = detector.predict_feature_rows(rows)
    restored_prediction = fresh_detector.predict_feature_rows(rows)

    assert restored_prediction == original_prediction
    assert restored_prediction.prediction_input_fingerprint == original_prediction.prediction_input_fingerprint
    assert restored_prediction.batch_id == original_prediction.batch_id


def test_row_prediction_identity_binds_ordered_ids_schema_and_exact_features(stage2, schema):
    detector, _, _, _ = _fit_fixture(stage2, schema)
    original = _case(stage2, schema, "identity-row", "validation", 0, (0.0, 0.0))
    changed = _case(stage2, schema, "identity-row", "validation", 0, (0.1, 0.0))

    first = detector.predict_feature_rows((original,))
    second = detector.predict_feature_rows((changed,))

    assert first.source_batch_fingerprint == second.source_batch_fingerprint
    assert first.prediction_input_fingerprint != second.prediction_input_fingerprint
    assert first.batch_id != second.batch_id


def test_stage1_prediction_identity_binds_caller_features_and_canonicalizes_mapping_order(stage2):
    detector, _, _ = _fit_single_feature_fixture(stage2)
    batch = _stage1_batch(cluster_count=2)
    ordered = {
        "candidate-1": {"caller_signal": 0.2},
        "candidate-2": {"caller_signal": 0.4},
    }
    reordered = {
        "candidate-2": {"caller_signal": 0.4},
        "candidate-1": {"caller_signal": 0.2},
    }

    first = detector.predict(batch, ordered)
    same_rows = detector.predict(batch, reordered)
    changed_feature = detector.predict(
        batch,
        {
            "candidate-1": {"caller_signal": 0.3},
            "candidate-2": {"caller_signal": 0.4},
        },
    )
    changed_stage1 = detector.predict(replace(batch, batch_id="batch-2"), ordered)

    assert first == same_rows
    assert first.source_batch_fingerprint == changed_feature.source_batch_fingerprint
    assert first.prediction_input_fingerprint != changed_feature.prediction_input_fingerprint
    assert first.batch_id != changed_feature.batch_id
    assert first.prediction_input_fingerprint != changed_stage1.prediction_input_fingerprint
    assert first.batch_id != changed_stage1.batch_id


def test_inverse_frequency_class_weights_are_train_label_derived(stage2):
    schema = stage2.contracts.DetectionFeatureSchema(
        version="imbalanced/v1", names=("signal",)
    )
    labels = (0, 0, 0, 0, 1, 1)
    train = [
        _case(stage2, schema, f"imbalanced-t{index}", "train", label, (float(index),))
        for index, label in enumerate(labels)
    ]
    validation_values = (-1.0, 1.0, 2.0, 4.0)
    first_validation = [
        _case(stage2, schema, f"imbalanced-v{index}", "validation", label, (value,))
        for index, (label, value) in enumerate(zip((0, 1, 0, 1), validation_values, strict=True))
    ]
    second_validation = [
        _case(stage2, schema, f"imbalanced-x{index}", "validation", label, (value,))
        for index, (label, value) in enumerate(zip((1, 0, 1, 0), validation_values, strict=True))
    ]

    first = stage2.learned.LearnedCoordinationDetector(schema=schema).fit(
        train, first_validation
    )
    second = stage2.learned.LearnedCoordinationDetector(schema=schema).fit(
        train, second_validation
    )

    expected_zero = len(labels) / (2 * labels.count(0))
    expected_one = len(labels) / (2 * labels.count(1))
    assert first.optimizer_config["class_weight_0"] == pytest.approx(expected_zero)
    assert first.optimizer_config["class_weight_1"] == pytest.approx(expected_one)
    assert second.optimizer_config["class_weight_0"] == first.optimizer_config["class_weight_0"]
    assert second.optimizer_config["class_weight_1"] == first.optimizer_config["class_weight_1"]


def test_threshold_ties_use_wider_interval_then_lexicographic_order(stage2):
    probabilities = np.asarray((0.1, 0.2, 0.3, 0.4), dtype=np.float64)
    labels = np.asarray((0, 1, 0, 1), dtype=np.int64)

    # Both candidate pairs cover every row with macro-F1 11/15 and width 0.1.
    assert stage2.learned._select_thresholds(probabilities, labels) == (0.1, 0.2)


def test_constant_validation_logits_calibrate_finitely_and_deterministically(stage2, schema):
    _, _, train, _ = _fit_fixture(stage2, schema)
    validation = [
        _case(stage2, schema, f"constant-v{index}", "validation", label, (0.0, 0.0))
        for index, label in enumerate((0, 1, 0, 1))
    ]

    first = stage2.learned.LearnedCoordinationDetector(schema=schema).fit(train, validation)
    second = stage2.learned.LearnedCoordinationDetector(schema=schema).fit(train, validation)

    assert math.isfinite(first.calibrator_slope)
    assert math.isfinite(first.calibrator_intercept)
    assert first == second


def test_zero_width_validation_ood_accepts_exact_value_and_abstains_on_change(stage2, schema):
    _, _, train, _ = _fit_fixture(stage2, schema)
    validation = [
        _case(stage2, schema, f"zero-width-v{index}", "validation", label, (0.0, 0.0))
        for index, label in enumerate((0, 1, 0, 1))
    ]
    detector = stage2.learned.LearnedCoordinationDetector(schema=schema)
    artifact = detector.fit(train, validation)
    exact = _case(stage2, schema, "zero-width-exact", "validation", 0, (0.0, 0.0))
    changed = _case(stage2, schema, "zero-width-changed", "validation", 0, (0.001, 0.0))

    verdicts = {
        verdict.cluster_id: verdict
        for verdict in detector.predict_feature_rows((exact, changed)).verdicts
    }

    assert artifact.validation_ood_min == (0.0, 0.0)
    assert artifact.validation_ood_max == (0.0, 0.0)
    assert verdicts[exact.cluster_id].abstain_reason != "out_of_distribution"
    assert verdicts[changed.cluster_id].decision == "abstain"
    assert verdicts[changed.cluster_id].abstain_reason == "out_of_distribution"
    assert verdicts[changed.cluster_id].ood_features == ("signal",)


def test_stage1_features_are_explicit_ordered_and_extra_features_fail_closed(stage2):
    batch = _stage1_batch()
    schema = stage2.contracts.DetectionFeatureSchema(
        version="stage1-plus/v1",
        names=stage2.features.STAGE1_FEATURE_NAMES + ("caller_signal",),
    )

    rows = stage2.features.build_detection_feature_rows(
        batch, schema, {"candidate-1": {"caller_signal": 0.4}}
    )

    assert rows["candidate-1"] == (3.0, 0.72, 0.81, 8.0, 0.76, 0.9, 0.6, 0.4)
    with pytest.raises(ValueError, match="extra"):
        stage2.features.build_detection_feature_rows(
            batch,
            schema,
            {"candidate-1": {"caller_signal": 0.4, "undeclared": 1.0}},
        )
    with pytest.raises(ValueError, match="missing"):
        stage2.features.build_detection_feature_rows(batch, schema, {"candidate-1": {}})


def test_prediction_abstains_for_ood_and_rejects_schema_uncertainty(stage2, schema):
    detector, artifact, _, _ = _fit_fixture(stage2, schema)
    inside = _case(stage2, schema, "inside", "validation", 0, (0.0, 0.0))
    outside = _case(stage2, schema, "outside", "validation", 0, (99.0, 0.0))

    verdicts = detector.predict_feature_rows((inside, outside)).verdicts

    assert verdicts[1].decision == "abstain"
    assert verdicts[1].abstain_reason == "out_of_distribution"
    assert verdicts[1].ood_features == ("signal",)
    wrong_schema = stage2.contracts.DetectionFeatureSchema(
        version="fixture-features/v2", names=schema.names
    )
    with pytest.raises(ValueError, match="schema"):
        stage2.learned.LearnedCoordinationDetector(
            schema=wrong_schema, artifact=artifact
        )


def test_heuristic_baseline_is_isolated_warns_and_has_no_fit_or_activation_path(stage2, schema):
    baseline = stage2.baseline.HeuristicBayesianBaseline()
    with pytest.warns(UserWarning, match="heuristic baseline"):
        first = baseline.predict(
            cluster_id="baseline-cluster",
            tsgs_density=0.8,
            mhcr_coherence=0.7,
            temporal_sync_score=0.9,
            unsupervised_ranking=0.6,
        )
    _fit_fixture(stage2, schema, permute_train_labels=True)
    with pytest.warns(UserWarning, match="heuristic baseline"):
        second = baseline.predict(
            cluster_id="baseline-cluster",
            tsgs_density=0.8,
            mhcr_coherence=0.7,
            temporal_sync_score=0.9,
            unsupervised_ranking=0.6,
        )

    assert first == second
    assert first.model_version == "heuristic_baseline_v1"
    assert first.model_role == "heuristic_baseline"
    expected_score = 0.25 * 0.8 + 0.35 * 0.7 + 0.25 * 0.9 + 0.15 * 0.6
    expected_probability = 1.0 / (1.0 + math.exp(-10.0 * (expected_score - 0.5)))
    assert first.harmful_probability == pytest.approx(expected_probability)
    assert first.decision == "harmful_coordination"
    assert first.warning
    assert not hasattr(baseline, "fit")
    assert not hasattr(baseline, "activate")
    with pytest.raises(ValueError, match="learned"):
        stage2.engine.CoordinationDetectionEngine(detector=baseline)


def test_learned_source_has_no_baseline_import_or_fixed_baseline_constants(stage2):
    source = inspect.getsource(stage2.learned)

    assert "heuristic_baseline" not in source
    for fixed in ("0.25", "0.35", "0.15", "0.65", "0.85", "10.0"):
        assert fixed not in source


def test_engine_requires_explicit_learned_configuration(stage2, schema):
    detector, artifact, _, _ = _fit_fixture(stage2, schema)

    with pytest.raises(ValueError, match="explicit learned"):
        stage2.engine.CoordinationDetectionEngine()
    assert stage2.engine.CoordinationDetectionEngine(artifact=artifact).artifact == artifact
    assert stage2.engine.CoordinationDetectionEngine(detector=detector).artifact == artifact
