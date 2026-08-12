from __future__ import annotations

import csv
import dataclasses
from datetime import datetime, timezone
import importlib
import importlib.util
import json
from pathlib import Path
import sys

import pytest

from app.config import PROJECT_ROOT


def _modules():
    research_dir = PROJECT_ROOT / "research"
    if "research" not in sys.modules:
        spec = importlib.util.spec_from_file_location(
            "research.coordination_experiments",
            research_dir / "coordination_experiments" / "__init__.py",
            submodule_search_locations=[str(research_dir / "coordination_experiments")],
        )
        assert spec is not None and spec.loader is not None
        package = importlib.util.module_from_spec(spec)
        research = importlib.util.module_from_spec(
            importlib.machinery.ModuleSpec("research", loader=None, is_package=True)
        )
        research.__path__ = [str(research_dir)]
        sys.modules["research"] = research
        sys.modules["research.coordination_experiments"] = package
        spec.loader.exec_module(package)
    package = importlib.import_module("research.coordination_experiments")
    return (
        package,
        importlib.import_module("research.coordination_experiments.metrics"),
        importlib.import_module("research.coordination_experiments.baselines"),
        importlib.import_module("research.coordination_experiments.runner"),
    )


def _manifest(package, *, seed=42, claim_markers=("research_only",), time_axis="observed_utc"):
    return package.ResearchDatasetManifest(
        dataset_id="fixture",
        seed=seed,
        source_paths=("/fixtures/cases.json",),
        source_checksums={"/fixtures/cases.json": "sha256:" + "a" * 64},
        source_checksum_scope="canonical_fixture_content",
        label_semantics="sealed_external_binary_labels",
        sample_count=6,
        source_case_ids=("train-0", "train-1", "val-0", "val-1", "test-0", "test-1"),
        campaign_axis=("train", "validation", "test"),
        platform_axis=("fixture",),
        time_axis=time_axis,
        quality_markers=("fixture",),
        claim_markers=claim_markers,
    )


def _split(package, *, seed=42, policy="campaign_holdout"):
    return package.ExperimentSplit(
        policy=policy,
        seed=seed,
        train_ids=("train-0", "train-1"),
        validation_ids=("val-0", "val-1"),
        test_ids=("test-0", "test-1"),
        train_group_ids=("train",),
        validation_group_ids=("validation",),
        test_group_ids=("test",),
        transform_fit_ids=("train-0", "train-1"),
    )


def _row(
    package,
    runner,
    *,
    seed=42,
    method_id="learned_fused_detector",
    method_version="learned-coordination-logistic-v1",
    model_role="primary_learned",
    status="success",
    metrics=None,
    reason=None,
    claim_markers=("research_only",),
    warning=None,
    runtime_seconds=1.25,
    task="detection",
    selection_eligible=None,
    ablation_id=None,
    audit=None,
):
    if selection_eligible is None:
        selection_eligible = method_id == "learned_fused_detector"
    if ablation_id is None and method_id in {
        "no_tsgs", "no_mhcr", "no_relation_specific", "no_temporal_augmentation",
        "coordination_only", "detection_features_only",
    }:
        ablation_id = method_id
    row_fields = {}
    if (
        status == "success"
        and task == "detection"
        and model_role in {"primary_learned", "learned_comparison"}
        and audit is None
    ):
        train, validation, test, artifact = _detection_fixture(package)
        contracts = importlib.import_module("research.coordination_detect.contracts")
        row_fields = {
            "model_artifact": artifact.to_dict(),
            "train_partition_fingerprint": contracts.case_id_fingerprint(
                case.case_id for case in train
            ),
            "validation_partition_fingerprint": contracts.case_id_fingerprint(
                case.case_id for case in validation
            ),
            "test_partition_fingerprint": contracts.case_id_fingerprint(
                case.case_id for case in test
            ),
        }
    return runner.ResultRow(
        dataset_id="fixture",
        dataset_manifest_fingerprint=_manifest(package, seed=seed, claim_markers=claim_markers).fingerprint,
        evaluator_fingerprint="sha256:" + "b" * 64,
        split_policy="campaign_holdout",
        split_fingerprint=_split(package, seed=seed).fingerprint,
        method_id=method_id,
        method_version=method_version,
        model_role=model_role,
        seed=seed,
        runtime_seconds=runtime_seconds,
        peak_memory_bytes=4096,
        status=status,
        metrics={} if metrics is None else metrics,
        reason=reason,
        warning=warning,
        claim_markers=claim_markers,
        task=task,
        selection_eligible=selection_eligible,
        ablation_id=ablation_id,
        audit={"audit_version": "fixture/v2"} if audit is None else audit,
        **row_fields,
    )


def _complete_detection_metrics():
    return {
        "auprc": 0.8,
        "macro_f1": 0.75,
        "roc_auc": 0.85,
        "ece": 0.1,
        "selective_coverage": 0.75,
        "selective_risk": 0.1,
        "abstain_rate": 0.25,
    }


def _complete_discovery_metrics():
    return {
        "candidate_recall": 0.8,
        "spectral_distortion": 0.1,
        "edge_auprc": 0.75,
        "b_cubed_precision": 0.8,
        "b_cubed_recall": 0.7,
        "b_cubed_f1": 0.7466666666666666,
        "nmi": 0.7,
        "ari": 0.6,
        "cross_seed_stability": 0.9,
    }


def _capability(package, *, dataset_id="fixture"):
    return package.DatasetCapability(
        dataset_id=dataset_id,
        supports_coordination_discovery=True,
        supports_external_label_evaluation=True,
        supports_campaign_holdout=True,
        supports_time_holdout=True,
        supports_social_bot_classification=False,
        supports_binary_coordination_detection=True,
        supports_harmful_cib_detection=True,
        supports_campaign_io_evaluation=True,
        blocked_reasons={"social_bot_classification": "not a bot dataset"},
        claim_markers=("research_only",),
    )


def _coordination_event(*, account_id="account-a", object_id="object-a"):
    event_type = importlib.import_module(
        "research.coordination_discover.stage1.events"
    ).CoordinationEvent
    return event_type(
        account_id=account_id,
        relation="shared_url",
        object_id=object_id,
        observed_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        weight=1.0,
        evidence_ref=f"fixture:{account_id}:{object_id}",
    )


def _detection_fixture(package):
    contracts = importlib.import_module("research.coordination_detect.contracts")
    schema = contracts.DetectionFeatureSchema(version="fixture/v1", names=("score",))

    def case(case_id, split, label, value):
        return contracts.DetectionTrainingCase(
            case_id=case_id,
            cluster_id=f"cluster-{case_id}",
            split=split,
            label=label,
            feature_schema_version=schema.version,
            feature_schema_fingerprint=schema.fingerprint,
            feature_names=schema.names,
            feature_values=(value,),
        )

    train = (case("train-0", "train", 0, 0.1), case("train-1", "train", 1, 0.9))
    validation = (case("val-0", "validation", 0, 0.2), case("val-1", "validation", 1, 0.8))
    test = (case("test-0", "test", 0, 0.15), case("test-1", "test", 1, 0.85))
    validation_fingerprint = contracts.case_id_fingerprint(item.case_id for item in validation)
    artifact = contracts.DetectionModelArtifact(
        feature_schema=schema,
        scaler_mean=(0.5,),
        scaler_scale=(0.4,),
        coefficients=(1.0,),
        intercept=0.0,
        calibrator_slope=1.0,
        calibrator_intercept=0.0,
        lower_decision_threshold=0.3,
        upper_decision_threshold=0.7,
        validation_ood_min=(0.2,),
        validation_ood_max=(0.8,),
        optimizer_config={"algorithm": "fixture"},
        calibrator_config={"algorithm": "fixture"},
        threshold_objective="fixture",
        train_fit_case_ids_fingerprint=contracts.case_id_fingerprint(item.case_id for item in train),
        validation_calibration_case_ids_fingerprint=validation_fingerprint,
        validation_threshold_case_ids_fingerprint=validation_fingerprint,
        validation_ood_case_ids_fingerprint=validation_fingerprint,
    )
    return train, validation, test, artifact


def _learned_adapter_fixture(package):
    contracts = importlib.import_module("research.coordination_detect.contracts")
    features = importlib.import_module("research.coordination_detect.features")
    schema = contracts.DetectionFeatureSchema(
        version="learned-adapter-fixture/v1",
        names=features.STAGE1_FEATURE_NAMES + ("detection_signal", "detection_context"),
    )

    def case(case_id, split, label, signal):
        values = (float(signal),) * len(schema.names)
        return contracts.DetectionTrainingCase(
            case_id=case_id,
            cluster_id=f"cluster-{case_id}",
            split=split,
            label=label,
            feature_schema_version=schema.version,
            feature_schema_fingerprint=schema.fingerprint,
            feature_names=schema.names,
            feature_values=values,
        )

    train = tuple(case(f"train-{i}", "train", int(i >= 2), -2.0 + i * 1.5) for i in range(4))
    validation = tuple(
        case(f"val-{i}", "validation", int(i >= 2), -1.5 + i * 1.0) for i in range(4)
    )
    test = tuple(case(f"test-{i}", "test", int(i == 1), -0.5 + i) for i in range(2))
    return train, validation, test, schema


def test_learned_stage2_adapters_fit_projected_artifacts_and_cover_only_unlabeled_test_cases():
    package, _, baselines, runner = _modules()
    train, validation, test, schema = _learned_adapter_fixture(package)
    inference = tuple(runner.DetectionInferenceCase.from_training_case(case) for case in test)
    partitions = runner.DetectionPartitions(train, validation, inference)
    registry = baselines.default_baseline_registry()
    expected_names = {
        "coordination_only_logistic": tuple(
            importlib.import_module("research.coordination_detect.features").STAGE1_FEATURE_NAMES
        ),
        "detection_features_only_classifier": ("detection_signal", "detection_context"),
        "learned_fused_detector": schema.names,
    }

    for method_id, feature_names in expected_names.items():
        assert registry.resolve(method_id, capability=_capability(package)).status == "ready"
        output = registry.implementation(method_id).execute(partitions)
        assert output.model_artifact is not None
        assert output.model_artifact.feature_schema.names == feature_names
        assert {prediction.case_id for prediction in output.predictions} == {
            case.case_id for case in inference
        }
        assert all(not hasattr(case, "label") for case in inference)
        assert "test_labels" not in output.model_artifact.to_dict()


def test_learned_stage2_adapter_associates_verdicts_with_cases_by_cluster_id():
    package, _, baselines, runner = _modules()
    train, validation, test, _ = _learned_adapter_fixture(package)
    inference = tuple(runner.DetectionInferenceCase.from_training_case(case) for case in test)
    non_lexical = (
        dataclasses.replace(inference[0], cluster_id="cluster-z"),
        dataclasses.replace(inference[1], cluster_id="cluster-a"),
    )
    registry = baselines.default_baseline_registry()
    implementation = registry.implementation("learned_fused_detector")

    lexical_output = implementation.execute(
        runner.DetectionPartitions(train, validation, (non_lexical[1], non_lexical[0]))
    )
    non_lexical_output = implementation.execute(
        runner.DetectionPartitions(train, validation, non_lexical)
    )

    expected = {
        prediction.case_id: (prediction.harmful_probability, prediction.decision)
        for prediction in lexical_output.predictions
    }
    actual = {
        prediction.case_id: (prediction.harmful_probability, prediction.decision)
        for prediction in non_lexical_output.predictions
    }
    assert actual == expected


def test_learned_stage2_adapter_fails_closed_when_required_feature_group_is_empty():
    package, _, baselines, _ = _modules()
    contracts = importlib.import_module("research.coordination_detect.contracts")
    runner = importlib.import_module("research.coordination_experiments.runner")

    def partitions_for(schema):
        cases = tuple(
            contracts.DetectionTrainingCase(
                case_id=f"{split}-{i}",
                cluster_id=f"cluster-{split}-{i}",
                split=split,
                label=i % 2,
                feature_schema_version=schema.version,
                feature_schema_fingerprint=schema.fingerprint,
                feature_names=schema.names,
                feature_values=(float(i),) * len(schema.names),
            )
            for split in ("train", "validation", "test")
            for i in range(2)
        )
        return runner.DetectionPartitions(
            cases[:2], cases[2:4],
            tuple(runner.DetectionInferenceCase.from_training_case(case) for case in cases[4:]),
        )

    no_coordination = partitions_for(
        contracts.DetectionFeatureSchema(version="detection-only/v1", names=("score",))
    )
    stage1_names = importlib.import_module("research.coordination_detect.features").STAGE1_FEATURE_NAMES
    no_detection = partitions_for(
        contracts.DetectionFeatureSchema(version="stage1-only/v1", names=stage1_names)
    )
    with pytest.raises(ValueError, match="Stage 1 feature group"):
        baselines.default_baseline_registry().implementation("coordination_only_logistic").execute(
            no_coordination
        )
    with pytest.raises(ValueError, match="detection feature group"):
        baselines.default_baseline_registry().implementation("detection_features_only_classifier").execute(
            no_detection
        )


def test_coordination_only_adapter_accepts_an_explicit_partial_stage1_schema():
    package, _, baselines, runner = _modules()
    contracts = importlib.import_module("research.coordination_detect.contracts")
    schema = contracts.DetectionFeatureSchema(
        version="partial-stage1/v1",
        names=("tsgs_density", "mhcr_coherence", "detection_signal"),
    )

    def case(case_id, split, label, value):
        return contracts.DetectionTrainingCase(
            case_id=case_id,
            cluster_id=f"cluster-{case_id}",
            split=split,
            label=label,
            feature_schema_version=schema.version,
            feature_schema_fingerprint=schema.fingerprint,
            feature_names=schema.names,
            feature_values=(value, value / 2.0, value * 2.0),
        )

    train = tuple(case(f"train-{i}", "train", int(i >= 2), float(i - 2)) for i in range(4))
    validation = tuple(
        case(f"validation-{i}", "validation", int(i >= 2), float(i - 2))
        for i in range(4)
    )
    test = tuple(case(f"test-{i}", "test", int(i == 1), float(i - 1)) for i in range(2))
    partitions = runner.DetectionPartitions(
        train,
        validation,
        tuple(runner.DetectionInferenceCase.from_training_case(row) for row in test),
    )

    output = baselines.default_baseline_registry().implementation(
        "coordination_only_logistic"
    ).execute(partitions)

    assert output.model_artifact is not None
    assert output.model_artifact.feature_schema.names == ("tsgs_density", "mhcr_coherence")


def test_metric_suite_covers_discovery_detection_and_cross_seed_stability():
    _, metrics, _, _ = _modules()

    discovery = metrics.discovery_metrics(
        candidate_edges=(("a", "b"), ("b", "c")),
        reference_edges=(("a", "b"), ("b", "c"), ("c", "d")),
        reference_quadratic_forms=(2.0, 4.0),
        approximate_quadratic_forms=(2.2, 3.6),
        edge_labels=(0, 1, 1, 0),
        edge_scores=(0.1, 0.9, 0.8, 0.2),
        true_clusters={"a": "x", "b": "x", "c": "y", "d": "y"},
        predicted_clusters={"a": "x", "b": "x", "c": "y", "d": "y"},
    )
    assert discovery["candidate_recall"] == pytest.approx(2 / 3)
    assert discovery["spectral_distortion"] == pytest.approx(0.1)
    for name in ("edge_auprc", "b_cubed_precision", "b_cubed_recall", "b_cubed_f1", "nmi", "ari"):
        assert discovery[name] == pytest.approx(1.0)

    detection = metrics.detection_metrics(
        labels=(0, 1, 0, 1),
        probabilities=(0.05, 0.95, 0.1, 0.9),
        decisions=("benign_coordination", "harmful_coordination", "abstain", "harmful_coordination"),
    )
    assert detection["auprc"] == pytest.approx(1.0)
    assert detection["macro_f1"] == pytest.approx(1.0)
    assert detection["roc_auc"] == pytest.approx(1.0)
    assert detection["selective_coverage"] == pytest.approx(0.75)
    assert detection["selective_risk"] == pytest.approx(0.0)
    assert detection["abstain_rate"] == pytest.approx(0.25)
    assert metrics.cross_seed_stability((
        {"a": "x", "b": "x", "c": "y"},
        {"a": "one", "b": "one", "c": "two"},
    )) == pytest.approx(1.0)


def test_bootstrap_and_multi_seed_aggregation_are_deterministic_and_exclude_non_success():
    package, metrics, _, runner = _modules()
    first = metrics.bootstrap_confidence_interval((0.7, 0.8, 0.9), seed=17, resamples=500)
    second = metrics.bootstrap_confidence_interval((0.7, 0.8, 0.9), seed=17, resamples=500)
    assert first == second

    first_metrics = {**_complete_detection_metrics(), "auprc": 0.7}
    second_metrics = {**_complete_detection_metrics(), "auprc": 0.9}
    rows = [
        _row(package, runner, seed=42, metrics=first_metrics),
        _row(package, runner, seed=43, metrics=second_metrics),
        _row(package, runner, seed=44, status="failed", reason="fixture failure"),
        _row(package, runner, seed=45, status="blocked", reason="missing timestamps"),
    ]
    aggregates = runner.aggregate_result_rows(rows, bootstrap_seed=17, bootstrap_resamples=500)
    aggregate = next(item for item in aggregates if item.metric_name == "auprc")
    assert aggregate.metric_name == "auprc"
    assert aggregate.successful_seed_count == 2
    assert aggregate.mean == pytest.approx(0.8)
    assert aggregate.std == pytest.approx(0.1)
    assert aggregate.ci_low <= aggregate.mean <= aggregate.ci_high


def test_metric_directions_are_explicit_and_complete():
    _, metrics, _, _ = _modules()
    maximize = {
        "candidate_recall", "edge_auprc", "b_cubed_precision", "b_cubed_recall",
        "b_cubed_f1", "nmi", "ari", "cross_seed_stability", "auprc",
        "macro_f1", "roc_auc", "selective_coverage",
    }
    minimize = {"spectral_distortion", "ece", "selective_risk", "abstain_rate", "runtime_seconds", "peak_memory_bytes"}
    assert {name for name in maximize if metrics.metric_direction(name) != "maximize"} == set()
    assert {name for name in minimize if metrics.metric_direction(name) != "minimize"} == set()
    with pytest.raises(ValueError, match="unknown metric"):
        metrics.metric_direction("invented_score")


def test_tied_score_auprc_is_order_invariant_and_negative_ari_is_serializable():
    package, metrics, _, runner = _modules()
    assert metrics.average_precision((1, 0, 1, 0), (0.5, 0.5, 0.2, 0.1)) == pytest.approx(
        metrics.average_precision((0, 1, 1, 0), (0.5, 0.5, 0.2, 0.1))
    )
    row = _row(
        package,
        runner,
        method_id="edgebank",
        method_version="edgebank-v1",
        model_role="temporal_baseline",
        metrics={**_complete_discovery_metrics(), "ari": -0.25},
        task="discovery",
        selection_eligible=False,
    )
    assert row.metrics["ari"] == -0.25


def test_baseline_registry_exposes_required_methods_ablations_and_blocking():
    package, _, baselines, _ = _modules()
    registry = baselines.default_baseline_registry()
    assert {
        "dense_cosine_leiden", "frozen_system_evidence_prior", "edgebank",
        "tgn_style_memory_prior", "coordination_only_logistic",
        "detection_features_only_classifier", "learned_fused_detector",
        "heuristic_baseline_v1",
        "deep_pyg_graphsage_fused_detector", "deep_pyg_gin_fused_detector",
        "deep_pyg_gcn_fused_detector", "deep_tabular_mlp_detector",
        "deep_tabular_residual_detector", "deep_len_mlp_fused_detector",
        "deep_len_fast_mlp_fused_detector",
    } <= set(registry.method_ids())
    assert package.DEEP_PYG_DETECTION_METHODS == {
        "deep_pyg_graphsage_fused_detector",
        "deep_pyg_gin_fused_detector",
        "deep_pyg_gcn_fused_detector",
    }
    assert package.DEEP_LEN_FUSED_DETECTION_METHODS == {
        "deep_len_mlp_fused_detector",
        "deep_len_fast_mlp_fused_detector",
    }
    assert package.DEEP_TABULAR_DETECTION_METHODS == {
        "deep_tabular_mlp_detector",
        "deep_tabular_residual_detector",
    }
    for method_id in package.DEEP_DETECTION_METHODS:
        spec = registry.get(method_id)
        assert spec.model_role == "learned_comparison"
        assert spec.claimable is False
        assert spec.selection_eligible is False
        assert spec.warning is not None
    assert registry.get("deep_pyg_graphsage_fused_detector").optional_dependencies == (
        "torch",
        "torch_geometric",
    )
    assert registry.get("deep_tabular_mlp_detector").optional_dependencies == ("torch",)
    assert registry.get("deep_len_mlp_fused_detector").optional_dependencies == ("sklearn",)
    assert registry.get("deep_len_fast_mlp_fused_detector").optional_dependencies == ("sklearn",)
    assert set(baselines.REQUIRED_ABLATIONS) == {
        "no_tsgs", "no_mhcr", "no_relation_specific", "no_temporal_augmentation",
        "coordination_only", "detection_features_only",
    }
    assert set(baselines.REQUIRED_ABLATIONS) <= set(registry.method_ids())

    blocked = registry.resolve(
        "tgn_style_memory_prior",
        capability=package.DatasetCapability(
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
                "observed_time_holdout": "timestamps unavailable",
                "social_bot_classification": "not a bot dataset",
            },
            claim_markers=("research_only",),
        ),
    )
    assert blocked.status == "blocked"
    assert "observed_time_holdout" in blocked.reason


def test_result_rows_retain_blocked_failed_runtime_memory_and_artifact_identity():
    package, _, _, runner = _modules()
    failed = _row(package, runner, status="failed", reason="algorithm error")
    blocked = _row(package, runner, status="blocked", reason="dependency unavailable")
    for row in (failed, blocked):
        payload = row.to_dict()
        assert payload["status"] in {"failed", "blocked"}
        assert payload["reason"]
        assert payload["runtime_seconds"] == 1.25
        assert payload["peak_memory_bytes"] == 4096
        assert payload["artifact_identity"].startswith("sha256:")
        assert payload["metrics"] == {}


def test_opaque_fit_audit_self_report_api_is_removed():
    _, _, _, runner = _modules()
    assert not hasattr(runner, "FitAudit")
    assert not hasattr(runner, "validate_fit_isolation")
    assert not hasattr(runner, "RunObservation")


def test_heuristic_rows_are_isolated_from_learned_selection():
    package, _, baselines, runner = _modules()
    registry = baselines.default_baseline_registry()
    warning = "Research-only heuristic baseline; output is not a learned or production decision."
    heuristic = _row(
        package,
        runner,
        method_id="heuristic_baseline_v1",
        method_version="heuristic_baseline_v1",
        model_role="heuristic_baseline",
        metrics={**_complete_detection_metrics(), "auprc": 0.99},
        warning=warning,
    )
    learned = _row(package, runner, metrics=_complete_detection_metrics())
    assert runner.select_learned_artifact((heuristic, learned), registry).artifact_identity == learned.artifact_identity
    with pytest.raises(ValueError, match="warning"):
        _row(
            package,
            runner,
            method_id="heuristic_baseline_v1",
            method_version="heuristic_baseline_v1",
            model_role="heuristic_baseline",
            metrics={**_complete_detection_metrics(), "auprc": 0.99},
        )


def test_claim_gates_use_observed_rows_metric_direction_and_dataset_markers():
    package, _, _, runner = _modules()
    rows = (
        _row(package, runner, seed=42, metrics={**_complete_detection_metrics(), "auprc": 0.80, "ece": 0.08}),
        _row(package, runner, seed=43, metrics={**_complete_detection_metrics(), "auprc": 0.84, "ece": 0.12}),
        _row(package, runner, seed=44, status="failed", reason="failure"),
    )
    maximize = runner.evaluate_claim_gate(
        runner.ClaimGate("harmful-auprc", "auprc", "maximize", 0.81, claim_scope="harmful_cib", minimum_successful_seeds=2),
        rows,
    )
    minimize = runner.evaluate_claim_gate(
        runner.ClaimGate("calibration", "ece", "minimize", 0.10, claim_scope="harmful_cib", minimum_successful_seeds=2),
        rows,
    )
    assert maximize.status == "supported"
    assert minimize.status == "supported"
    assert maximize.observed_artifact_identities == tuple(sorted(row.artifact_identity for row in rows[:2]))
    assert maximize.to_dict()["direction"] == "maximize"

    cresci = _row(
        package,
        runner,
        metrics={**_complete_detection_metrics(), "auprc": 1.0},
        claim_markers=("not_harmful_cib_claim",),
    )
    blocked = runner.evaluate_claim_gate(
        runner.ClaimGate(
            "harmful-cib", "auprc", "maximize", 0.5,
            claim_scope="harmful_cib",
            forbidden_claim_markers=("not_harmful_cib_claim",),
        ),
        (cresci,),
    )
    assert blocked.status == "blocked"
    assert "not_harmful_cib_claim" in blocked.reason

    runtime = runner.evaluate_claim_gate(
        runner.ClaimGate("runtime", "runtime_seconds", "minimize", 1.3, claim_scope="general", minimum_successful_seeds=2),
        rows,
    )
    assert runtime.status == "supported"


def test_time_holdout_claim_blocks_static_placeholder_rows():
    package, _, _, runner = _modules()
    row = runner.ResultRow(
        dataset_id="iohunter-russia",
        dataset_manifest_fingerprint=_manifest(package, time_axis="static_placeholder_not_observed_time").fingerprint,
        evaluator_fingerprint="sha256:" + "b" * 64,
        split_policy="official_static_fold",
        split_fingerprint=_split(package).fingerprint,
        method_id="edgebank",
        method_version="edgebank-v1",
        model_role="temporal_baseline",
        seed=42,
        runtime_seconds=1.0,
        peak_memory_bytes=1024,
        status="success",
        metrics={**_complete_discovery_metrics(), "edge_auprc": 1.0},
        claim_markers=("static_placeholder_not_observed_time",),
        task="discovery",
        audit={"audit_version": "fixture/v2", "label_free_execution": True},
    )
    result = runner.evaluate_claim_gate(
        runner.ClaimGate(
            "time-holdout", "edge_auprc", "maximize", 0.5,
            claim_scope="observed_time",
            required_split_policy="observed_time_holdout",
        ),
        (row,),
    )
    assert result.status == "blocked"


def test_artifact_writer_emits_deterministic_json_csv_aggregates_and_claim_gates():
    package, _, _, runner = _modules()
    rows = (
        _row(package, runner, seed=43, metrics={**_complete_detection_metrics(), "auprc": 0.9}),
        _row(package, runner, seed=42, metrics={**_complete_detection_metrics(), "auprc": 0.7}),
        _row(package, runner, seed=44, status="blocked", reason="fixture blocked"),
    )
    gates = (runner.ClaimGate("quality", "auprc", "maximize", 0.75, claim_scope="general", minimum_successful_seeds=2),)
    output_root = runner.CANONICAL_REPRODUCTION_OUTPUT_ROOT / "pytest-artifact-writer"
    first = runner.write_reproduction_artifacts(
        rows, output_root / "first", claim_gates=gates, bootstrap_resamples=200
    )
    second = runner.write_reproduction_artifacts(
        rows, output_root / "second", claim_gates=gates, bootstrap_resamples=200
    )

    assert first.artifact_identity == second.artifact_identity
    assert first.per_seed_json.read_bytes() == second.per_seed_json.read_bytes()
    assert first.per_seed_csv.read_bytes() == second.per_seed_csv.read_bytes()
    payload = json.loads(first.per_seed_json.read_text(encoding="utf-8"))
    assert [row["seed"] for row in payload["rows"]] == [42, 43, 44]
    required = {
        "dataset_manifest_fingerprint", "evaluator_fingerprint", "split_policy",
        "split_fingerprint", "method_id", "method_version", "seed", "runtime_seconds",
        "peak_memory_bytes", "status", "metrics", "artifact_identity",
    }
    assert required <= set(payload["rows"][0])
    aggregates = json.loads(first.aggregates_json.read_text(encoding="utf-8"))["aggregates"]
    auprc = next(item for item in aggregates if item["metric_name"] == "auprc")
    assert len(auprc["dataset_manifest_fingerprints"]) == 2
    assert len(auprc["split_fingerprints"]) == 2
    assert auprc["evaluator_fingerprints"] == ["sha256:" + "b" * 64]
    with first.per_seed_csv.open(encoding="utf-8", newline="") as handle:
        csv_rows = list(csv.DictReader(handle))
    assert len(csv_rows) == 3
    assert json.loads(csv_rows[0]["metrics"])["auprc"] == 0.7
    serialized_gate = json.loads(first.claim_gates_json.read_text(encoding="utf-8"))["claim_gates"][0]
    assert serialized_gate["status"] == "supported"
    assert serialized_gate["gate_definition"] == {
        "dataset_id": None,
        "claim_scope": "general",
        "direction": "maximize",
        "forbidden_claim_markers": [],
        "gate_id": "quality",
        "method_id": None,
        "metric_name": "auprc",
        "minimum_successful_seeds": 2,
        "required_split_policy": None,
        "threshold": 0.75,
    }


def test_typed_discovery_runner_retains_blocked_and_failed_outcomes():
    package, _, baselines, runner = _modules()
    capability = package.DatasetCapability(
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
            "observed_time_holdout": "timestamps unavailable",
            "social_bot_classification": "not a bot dataset",
        },
        claim_markers=("research_only",),
    )
    default = baselines.default_baseline_registry()

    class FailingEdgeBank(baselines.DiscoveryImplementation):
        method_id = "edgebank"
        implementation_id = "edgebank-implementation-v1"

        def execute(self, execution_input):
            raise RuntimeError("fixture exploded")

    registry = baselines.BaselineRegistry(
        (
            (
                default.get("tgn_style_memory_prior"),
                default.implementation("tgn_style_memory_prior"),
            ),
            (default.get("edgebank"), FailingEdgeBank()),
        )
    )
    execution_input = runner.DiscoveryExecutionInput(
        manifest=_manifest(package), events=(_coordination_event(),)
    )
    blocked = runner.execute_discovery_method(
        registry, "tgn_style_memory_prior", execution_input, capability
    )
    assert blocked.status == "blocked"
    assert "observed_time_holdout" in blocked.reason

    failed = runner.execute_discovery_method(
        registry, "edgebank", execution_input, dataclasses.replace(capability, supports_time_holdout=True, blocked_reasons={"social_bot_classification": "not a bot dataset"})
    )
    assert failed.status == "failed"
    assert "fixture exploded" in failed.reason


def test_cli_script_has_no_production_activation_imports():
    script = PROJECT_ROOT / "backend" / "scripts" / "run_coordination_two_stage_reproduction.py"
    source = script.read_text(encoding="utf-8")
    assert "coordination_model_service" not in source
    assert "coordination-evidence-runtime-v2" not in source
    assert "sys.path.insert" not in source


def test_cli_default_output_stays_under_g_drive_repository_root():
    _modules()
    script = PROJECT_ROOT / "backend" / "scripts" / "run_coordination_two_stage_reproduction.py"
    spec = importlib.util.spec_from_file_location(
        "task6_coordination_reproduction_cli", script
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    expected = PROJECT_ROOT / "output" / "coordination_two_stage_reproduction"
    assert module.DEFAULT_OUTPUT == expected
    assert module._parser().parse_args(["--smoke-fixture"]).output == expected
    public_args = module._parser().parse_args(
        [
            "--public-detection",
            "--seeds",
            "11,23",
            "--methods",
            "learned_fused_detector,deep_tabular_mlp_detector",
            "--max-cases",
            "6",
            "--bootstrap-resamples",
            "10",
        ]
    )
    assert public_args.output == expected
    assert public_args.seeds == "11,23"
    assert public_args.methods == "learned_fused_detector,deep_tabular_mlp_detector"
    assert public_args.max_cases == 6
    assert public_args.bootstrap_resamples == 10
    assert module.DEFAULT_OUTPUT.drive.upper() == "G:"


def test_final_review_inference_cases_discard_or_reject_training_provenance():
    package, _, _, runner = _modules()
    _, _, labeled_test, _ = _detection_fixture(package)
    training_case = dataclasses.replace(labeled_test[0], provenance={"label": 1})
    inference_case = runner.DetectionInferenceCase.from_training_case(training_case)
    assert dict(inference_case.provenance) == {}

    provenance_cases = (
        {"label": 1},
        {"metadata": {"label": 1}},
        {"aliases": {"target": 1}},
    )
    for provenance in provenance_cases:
        with pytest.raises(ValueError, match="provenance must be empty"):
            runner.DetectionInferenceCase(
                case_id=training_case.case_id,
                cluster_id=training_case.cluster_id,
                feature_schema_version=training_case.feature_schema_version,
                feature_schema_fingerprint=training_case.feature_schema_fingerprint,
                feature_names=training_case.feature_names,
                feature_values=training_case.feature_values,
                provenance=provenance,
            )


@pytest.mark.parametrize("dispatch_attribute", ("baseline_type", "_baseline_type"))
def test_final_review_heuristic_adapter_ignores_class_level_rebinding(
    monkeypatch, dispatch_attribute
):
    _, _, baselines, runner = _modules()
    implementation = baselines.default_baseline_registry().implementation("heuristic_baseline_v1")
    inference = runner.DetectionInferenceCase(
        case_id="test-heuristic-rebinding",
        cluster_id="cluster-test-heuristic-rebinding",
        feature_schema_version="fixture/v1",
        feature_schema_fingerprint="sha256:" + "c" * 64,
        feature_names=(
            "tsgs_density",
            "mhcr_coherence",
            "temporal_sync_score",
            "unsupervised_ranking",
        ),
        feature_values=(0.8, 0.7, 0.9, 0.6),
    )
    with pytest.warns(UserWarning, match="heuristic baseline"):
        expected = implementation.execute(runner.DetectionTestInput((inference,)))

    class LookalikeBaseline:
        def predict(self, **_kwargs):
            raise AssertionError("class-level heuristic rebinding must not dispatch")

    monkeypatch.setattr(
        baselines.HeuristicDetectionImplementation,
        dispatch_attribute,
        LookalikeBaseline,
        raising=False,
    )
    with pytest.warns(UserWarning, match="heuristic baseline"):
        actual = implementation.execute(runner.DetectionTestInput((inference,)))
    assert actual == expected


def test_final_review_artifact_output_is_confined_to_canonical_root():
    package, _, _, runner = _modules()
    root = runner.CANONICAL_REPRODUCTION_OUTPUT_ROOT
    accepted = root / "pytest-output-root" / "accepted"
    assert runner.validate_reproduction_output_dir(accepted) == accepted.resolve()

    rows = (_row(package, runner, metrics=_complete_detection_metrics()),)
    artifacts = runner.write_reproduction_artifacts(rows, accepted, bootstrap_resamples=10)
    assert artifacts.per_seed_json.parent == accepted.resolve()

    rejected = (
        Path("C:/tmp/cogguard-task6-output"),
        Path("D:/cogguard-task6-output"),
        root / ".." / "coordination_two_stage_reproduction_sibling",
        root.parent / "coordination_two_stage_reproduction_sibling",
    )
    for path in rejected:
        with pytest.raises(ValueError, match="canonical reproduction output root"):
            runner.validate_reproduction_output_dir(path)
        with pytest.raises(ValueError, match="canonical reproduction output root"):
            runner.write_reproduction_artifacts(rows, path, bootstrap_resamples=10)

    script = PROJECT_ROOT / "backend" / "scripts" / "run_coordination_two_stage_reproduction.py"
    spec = importlib.util.spec_from_file_location("task6_output_validation_cli", script)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module._parser().parse_args(
        ["--smoke-fixture", "--output", str(accepted)]
    ).output == accepted.resolve()
    with pytest.raises(SystemExit):
        module._parser().parse_args(
            ["--smoke-fixture", "--output", "C:/tmp/cogguard-task6-output"]
        )


def test_iohunter_family_identity_accepts_only_canonical_campaign_manifests():
    package, _, _, runner = _modules()
    capability = package.iohunter_capability()
    for campaign in package.IOHUNTER_CAMPAIGNS:
        manifest = dataclasses.replace(
            _manifest(package),
            dataset_id=f"iohunter-{campaign}",
            campaign_axis=(campaign,),
        )
        runner.validate_dataset_identity(manifest, capability)

    for dataset_id, campaign_axis in (
        ("iohunter-russia-copy", ("russia",)),
        ("iohunter-Russia", ("Russia",)),
        ("iohunter", ("russia",)),
        ("iohunter-russia", ("russia", "iran")),
    ):
        manifest = dataclasses.replace(
            _manifest(package), dataset_id=dataset_id, campaign_axis=campaign_axis
        )
        with pytest.raises(ValueError, match="canonical IOHunter"):
            runner.validate_dataset_identity(manifest, capability)

    alias_capability = dataclasses.replace(capability, dataset_id="iohunter-russia")
    with pytest.raises(ValueError, match="canonical IOHunter capability"):
        runner.validate_dataset_identity(
            dataclasses.replace(
                _manifest(package), dataset_id="iohunter-russia", campaign_axis=("russia",)
            ),
            alias_capability,
        )


def test_claim_restrictions_are_intrinsic_and_cannot_be_bypassed_by_gate_options():
    package, _, _, runner = _modules()
    cresci = _row(
        package,
        runner,
        metrics=_complete_detection_metrics(),
        claim_markers=("not_harmful_cib_claim",),
    )
    harmful = runner.evaluate_claim_gate(
        runner.ClaimGate(
            "harmful-cib", "auprc", "maximize", 0.5,
            claim_scope="harmful_cib",
        ),
        (cresci,),
    )
    assert harmful.status == "blocked"
    assert "intrinsic" in harmful.reason
    assert "not_harmful_cib_claim" in harmful.to_dict()["reason"]

    static = runner.ResultRow(
        dataset_id="iohunter-russia",
        dataset_manifest_fingerprint=_manifest(package).fingerprint,
        evaluator_fingerprint="sha256:" + "b" * 64,
        split_policy="official_static_fold",
        split_fingerprint=_split(package).fingerprint,
        method_id="edgebank",
        method_version="edgebank-v1",
        model_role="temporal_baseline",
        seed=42,
        runtime_seconds=1.0,
        peak_memory_bytes=1024,
        status="success",
        metrics=_complete_discovery_metrics(),
        claim_markers=("static_placeholder_not_observed_time",),
        task="discovery",
        audit={"audit_version": "fixture/v2", "label_free_execution": True},
    )
    observed_time = runner.evaluate_claim_gate(
        runner.ClaimGate(
            "observed-time", "edge_auprc", "maximize", 0.5,
            claim_scope="observed_time",
            required_split_policy="official_static_fold",
        ),
        (static,),
    )
    assert observed_time.status == "blocked"
    assert "static_placeholder_not_observed_time" in observed_time.reason


def test_duplicate_successful_seed_retries_fail_closed_for_aggregation_and_gates():
    package, _, _, runner = _modules()
    first = _row(package, runner, seed=42, metrics=_complete_detection_metrics())
    retry = _row(
        package, runner, seed=42, metrics=_complete_detection_metrics(), runtime_seconds=1.5
    )
    with pytest.raises(ValueError, match="duplicate successful seed"):
        runner.aggregate_result_rows((first, retry))
    gate = runner.evaluate_claim_gate(
        runner.ClaimGate(
            "two-seed", "auprc", "maximize", 0.5,
            claim_scope="harmful_cib", minimum_successful_seeds=2,
        ),
        (first, retry),
    )
    assert gate.status == "blocked"
    assert gate.observed_seed_count == 1
    assert "duplicate successful seed" in gate.reason


def test_discovery_execution_is_label_free_and_evaluated_only_after_prediction():
    package, _, baselines, runner = _modules()
    default = baselines.default_baseline_registry()
    seen = []

    class FixtureEdgeBank(baselines.DiscoveryImplementation):
        method_id = "edgebank"
        implementation_id = "edgebank-implementation-v1"

        def execute(self, execution_input):
            seen.append(execution_input)
            assert not hasattr(execution_input, "labels")
            assert not hasattr(execution_input, "evaluator")
            return runner.DiscoveryPrediction(
                candidate_edges=(("a", "b"), ("b", "c")),
                approximate_quadratic_forms=(2.0, 4.0),
                edge_score_edges=(("a", "b"), ("b", "c"), ("c", "d"), ("a", "d")),
                edge_scores=(0.9, 0.8, 0.2, 0.1),
                predicted_clusters={"a": "x", "b": "x", "c": "y", "d": "y"},
                artifact_identity="sha256:" + "d" * 64,
            )

    registry = baselines.BaselineRegistry(
        ((default.get("edgebank"), FixtureEdgeBank()),)
    )
    manifest = _manifest(package)
    execution = runner.execute_discovery_method(
        registry,
        "edgebank",
        runner.DiscoveryExecutionInput(manifest=manifest, events=(_coordination_event(),)),
        _capability(package),
    )
    assert execution.status == "success"
    assert len(seen) == 1
    assert not hasattr(execution.prediction, "metrics")

    row = runner.evaluate_discovery_execution(
        execution,
        runner.DiscoveryEvaluationInput(
            evaluator_fingerprint="sha256:" + "b" * 64,
            split=_split(package),
            reference_edges=(("a", "b"), ("b", "c"), ("c", "d")),
            reference_quadratic_forms=(2.0, 4.0),
            edge_score_edges=(("a", "b"), ("b", "c"), ("c", "d"), ("a", "d")),
            edge_labels=(1, 1, 0, 0),
            true_clusters={"a": "x", "b": "x", "c": "y", "d": "y"},
            stability_peers=(
                runner.DiscoveryStabilityPeer(
                    seed=43,
                    current_seed=42,
                    prediction_artifact_identity="sha256:" + "e" * 64,
                    predicted_clusters={"a": "one", "b": "one", "c": "two", "d": "two"},
                ),
            ),
        ),
    )
    assert row.status == "success"
    assert set(_complete_discovery_metrics()) == set(row.metrics)
    assert row.audit["label_free_execution"] is True
    assert row.audit["evaluation_after_execution"] is True


def test_detection_fit_audit_is_derived_from_stage2_artifact_and_partitions():
    package, _, baselines, runner = _modules()
    train, validation, test, artifact = _detection_fixture(package)
    default = baselines.default_baseline_registry()
    inference = tuple(runner.DetectionInferenceCase.from_training_case(case) for case in test)

    class FixtureLearned(baselines.LearnedDetectionImplementation):
        method_id = "learned_fused_detector"
        implementation_id = "learned-fused-implementation-v1"

        def execute(self, partitions):
            assert partitions.train_cases == train
            assert partitions.validation_cases == validation
            assert partitions.test_cases == inference
            return runner.DetectionExecutionOutput(
                model_artifact=artifact,
                predictions=(
                    runner.DetectionPrediction("test-0", 0.1, "benign_coordination"),
                    runner.DetectionPrediction("test-1", 0.9, "harmful_coordination"),
                ),
            )

    registry = baselines.BaselineRegistry(
        ((default.get("learned_fused_detector"), FixtureLearned()),)
    )
    row = runner.run_detection_method(
        registry,
        "learned_fused_detector",
        manifest=_manifest(package),
        capability=_capability(package),
        split=_split(package),
        partitions=runner.DetectionPartitions(train, validation, inference),
        evaluation=runner.DetectionEvaluationInput(
            evaluator_fingerprint="sha256:" + "b" * 64,
            test_labels={case.case_id: case.label for case in test},
        ),
    )
    assert row.status == "success"
    assert row.audit["fit_provenance_source"] == "stage2_model_artifact"
    assert row.audit["model_artifact_hash"] == artifact.artifact_hash
    assert row.audit["test_evaluation_only"] is True

    leaked = dataclasses.replace(
        artifact,
        train_fit_case_ids_fingerprint=importlib.import_module(
            "research.coordination_detect.contracts"
        ).case_id_fingerprint(item.case_id for item in test),
    )
    class LeakedLearned(baselines.LearnedDetectionImplementation):
        method_id = "learned_fused_detector"
        implementation_id = "learned-fused-implementation-v1"

        def execute(self, partitions):
            return runner.DetectionExecutionOutput(
                model_artifact=leaked,
                predictions=(
                    runner.DetectionPrediction("test-0", 0.1, "benign_coordination"),
                    runner.DetectionPrediction("test-1", 0.9, "harmful_coordination"),
                ),
            )

    registry = baselines.BaselineRegistry(
        ((default.get("learned_fused_detector"), LeakedLearned()),)
    )
    rejected = runner.run_detection_method(
        registry,
        "learned_fused_detector",
        manifest=_manifest(package),
        capability=_capability(package),
        split=_split(package),
        partitions=runner.DetectionPartitions(train, validation, inference),
        evaluation=runner.DetectionEvaluationInput(
            evaluator_fingerprint="sha256:" + "b" * 64,
            test_labels={case.case_id: case.label for case in test},
        ),
    )
    assert rejected.status == "failed"
    assert "train_fit_case_ids_fingerprint" in rejected.reason


def test_registered_implementation_binding_prevents_method_relabeling():
    _, _, baselines, runner = _modules()
    registry = baselines.default_baseline_registry()

    class RelabeledEdgeBank(baselines.DiscoveryImplementation):
        method_id = "dense_cosine_leiden"
        implementation_id = "dense-cosine-leiden-implementation-v1"

    with pytest.raises(ValueError, match="implementation method identity"):
        baselines.BaselineRegistry(((registry.get("edgebank"), RelabeledEdgeBank()),))
    assert not hasattr(runner, "run_registered_method")


def test_heuristic_implementation_receives_test_only_and_cannot_persist_fit_audit():
    package, _, baselines, runner = _modules()
    train, validation, test, _ = _detection_fixture(package)
    registry = baselines.default_baseline_registry()
    inference = tuple(
        runner.DetectionInferenceCase(
            case_id=case.case_id,
            cluster_id=case.cluster_id,
            feature_schema_version="fixture-heuristic/v1",
            feature_schema_fingerprint="sha256:" + "c" * 64,
            feature_names=(
                "tsgs_density",
                "mhcr_coherence",
                "temporal_sync_score",
                "unsupervised_ranking",
            ),
            feature_values=(0.8, 0.7, 0.9, 0.6),
            provenance={},
        )
        for case in test
    )
    with pytest.warns(UserWarning, match="heuristic baseline"):
        row = runner.run_detection_method(
            registry,
            "heuristic_baseline_v1",
            manifest=_manifest(package),
            capability=_capability(package),
            split=_split(package),
            partitions=runner.DetectionPartitions(train, validation, inference),
            evaluation=runner.DetectionEvaluationInput(
                evaluator_fingerprint="sha256:" + "b" * 64,
                test_labels={case.case_id: case.label for case in test},
            ),
        )
    assert row.status == "success"
    assert all(not hasattr(case, "label") for case in inference)
    assert row.audit["fit_provenance_source"] == "none_heuristic_test_only"
    assert "train_partition_fingerprint" not in row.audit
    assert "validation_partition_fingerprint" not in row.audit
    assert "model_artifact_hash" not in row.audit
    assert "model_artifact_version" not in row.audit

    invalid_fit_audits = (
        {
            "audit_version": "fixture/v1",
            "fit_provenance_source": "stage2_model_artifact",
        },
        {
            "audit_version": "fixture/v1",
            "fit_provenance_source": "none_heuristic_test_only",
            "train_partition_fingerprint": "sha256:" + "f" * 64,
        },
        {
            "audit_version": "fixture/v1",
            "fit_provenance_source": "none_heuristic_test_only",
            "model_artifact_hash": "sha256:" + "f" * 64,
        },
    )
    for audit in invalid_fit_audits:
        with pytest.raises(ValueError, match="heuristic baseline.*fit audit"):
            _row(
                package,
                runner,
                method_id="heuristic_baseline_v1",
                method_version="heuristic_baseline_v1",
                model_role="heuristic_baseline",
                warning="Research-only heuristic baseline; output is not a learned or production decision.",
                metrics=_complete_detection_metrics(),
                audit=audit,
            )


def test_claim_gate_requires_explicit_claim_scope():
    _, _, _, runner = _modules()
    with pytest.raises(TypeError, match="claim_scope"):
        runner.ClaimGate("quality", "auprc", "maximize", 0.5)


def test_comparison_roles_and_selection_eligibility_are_registry_enforced():
    package, _, baselines, runner = _modules()
    registry = baselines.default_baseline_registry()
    coordination = registry.get("coordination_only")
    detection_only = registry.get("detection_features_only")
    fused = registry.get("learned_fused_detector")
    assert coordination.model_role == detection_only.model_role == "learned_comparison"
    assert not coordination.selection_eligible
    assert not detection_only.selection_eligible
    assert fused.model_role == "primary_learned"
    assert fused.selection_eligible

    comparison_rows = (
        _row(
            package, runner, method_id="coordination_only",
            method_version=coordination.method_version,
            model_role=coordination.model_role,
            metrics=_complete_detection_metrics(),
        ),
        _row(
            package, runner, method_id="detection_features_only",
            method_version=detection_only.method_version,
            model_role=detection_only.model_role,
            metrics=_complete_detection_metrics(),
        ),
        _row(package, runner, metrics=_complete_detection_metrics()),
    )
    selected = runner.select_learned_artifact(comparison_rows, registry)
    assert selected.method_id == "learned_fused_detector"


def test_successful_rows_require_complete_task_metric_suites():
    package, _, _, runner = _modules()
    with pytest.raises(ValueError, match="complete detection metric suite"):
        _row(package, runner, metrics={"auprc": 0.8})
    with pytest.raises(ValueError, match="complete discovery metric suite"):
        runner.ResultRow(
            dataset_id="fixture",
            dataset_manifest_fingerprint=_manifest(package).fingerprint,
            evaluator_fingerprint="sha256:" + "b" * 64,
            split_policy="campaign_holdout",
            split_fingerprint=_split(package).fingerprint,
            method_id="edgebank",
            method_version="edgebank-v1",
            model_role="temporal_baseline",
            seed=42,
            runtime_seconds=1.0,
            peak_memory_bytes=1024,
            status="success",
            metrics={"edge_auprc": 0.8},
            task="discovery",
            audit={"audit_version": "fixture/v1", "verified": True},
        )


@pytest.mark.parametrize(
    ("method_id", "method_version", "model_role", "warning"),
    (
        ("heuristic_baseline_v1", "heuristic_baseline_v1", "primary_learned", None),
        ("learned_fused_detector", "heuristic_baseline_v1", "primary_learned", None),
        ("learned_fused_detector", "learned-coordination-logistic-v1", "heuristic_baseline", None),
        ("heuristic_baseline_v1", "heuristic_baseline_v1", "heuristic_baseline", None),
    ),
)
def test_heuristic_identity_invariants_are_bidirectional(
    method_id, method_version, model_role, warning
):
    package, _, _, runner = _modules()
    with pytest.raises(ValueError, match="heuristic baseline identity"):
        _row(
            package,
            runner,
            method_id=method_id,
            method_version=method_version,
            model_role=model_role,
            warning=warning,
            metrics=_complete_detection_metrics(),
        )


def test_second_review_detection_executors_never_receive_test_labels():
    package, _, baselines, runner = _modules()
    train, validation, labeled_test, artifact = _detection_fixture(package)
    seen = []

    class FixtureLearnedImplementation(baselines.LearnedDetectionImplementation):
        method_id = "learned_fused_detector"
        implementation_id = "fixture-learned-fused-implementation-v1"

        def execute(self, partitions):
            seen.append(partitions)
            assert all(hasattr(case, "label") for case in partitions.train_cases)
            assert all(hasattr(case, "label") for case in partitions.validation_cases)
            assert all(not hasattr(case, "label") for case in partitions.test_cases)
            return runner.DetectionExecutionOutput(
                model_artifact=artifact,
                predictions=(
                    runner.DetectionPrediction("test-0", 0.1, "benign_coordination"),
                    runner.DetectionPrediction("test-1", 0.9, "harmful_coordination"),
                ),
            )

    default = baselines.default_baseline_registry()
    registry = baselines.BaselineRegistry(
        ((default.get("learned_fused_detector"), FixtureLearnedImplementation()),)
    )
    inference_cases = tuple(
        runner.DetectionInferenceCase.from_training_case(case) for case in labeled_test
    )
    evaluation = runner.DetectionEvaluationInput(
        evaluator_fingerprint="sha256:" + "b" * 64,
        test_labels={case.case_id: case.label for case in labeled_test},
    )
    row = runner.run_detection_method(
        registry,
        "learned_fused_detector",
        manifest=_manifest(package),
        capability=_capability(package),
        split=_split(package),
        partitions=runner.DetectionPartitions(train, validation, inference_cases),
        evaluation=evaluation,
    )
    assert row.status == "success"
    assert len(seen) == 1
    assert row.evaluator_fingerprint == evaluation.fingerprint


def test_second_review_registry_is_immutable_and_heuristic_is_concrete_stage2_adapter():
    _, _, baselines, runner = _modules()
    registry = baselines.default_baseline_registry()
    assert not hasattr(registry, "bind")
    implementation = registry.implementation("heuristic_baseline_v1")
    heuristic_type = importlib.import_module(
        "research.coordination_detect.heuristic_baseline"
    ).HeuristicBayesianBaseline
    assert type(implementation) is baselines.HeuristicDetectionImplementation
    assert implementation.implementation_id == registry.get(
        "heuristic_baseline_v1"
    ).implementation_id
    assert not hasattr(implementation, "__dict__")

    inference = runner.DetectionInferenceCase(
        case_id="test-heuristic",
        cluster_id="cluster-test-heuristic",
        feature_schema_version="fixture/v1",
        feature_schema_fingerprint="sha256:" + "c" * 64,
        feature_names=(
            "tsgs_density",
            "mhcr_coherence",
            "temporal_sync_score",
            "unsupervised_ranking",
        ),
        feature_values=(0.8, 0.7, 0.9, 0.6),
        provenance={},
    )
    with pytest.warns(UserWarning, match="heuristic baseline"):
        output = implementation.execute(runner.DetectionTestInput((inference,)))
    with pytest.warns(UserWarning, match="heuristic baseline"):
        expected = heuristic_type().predict(
            cluster_id=inference.cluster_id,
            tsgs_density=0.8,
            mhcr_coherence=0.7,
            temporal_sync_score=0.9,
            unsupervised_ranking=0.6,
        )
    assert output.predictions[0].harmful_probability == expected.harmful_probability
    assert output.predictions[0].decision == expected.decision

    class RelabeledImplementation(baselines.DiscoveryImplementation):
        method_id = "dense_cosine_leiden"
        implementation_id = "relabeled-implementation-v1"

        def execute(self, execution_input):
            raise AssertionError("must not execute")

    edgebank = registry.get("edgebank")
    with pytest.raises(ValueError, match="implementation method identity"):
        baselines.BaselineRegistry(((edgebank, RelabeledImplementation()),))
    with pytest.raises(ValueError, match="duplicate registered method"):
        baselines.BaselineRegistry(
            (
                (edgebank, registry.implementation("edgebank")),
                (edgebank, registry.implementation("edgebank")),
            )
        )


def test_second_review_discovery_requires_exact_copied_coordination_events():
    package, _, _, runner = _modules()
    event_type = importlib.import_module(
        "research.coordination_discover.stage1.events"
    ).CoordinationEvent
    event = event_type(
        account_id="account-a",
        relation="shared_url",
        object_id="https://example.test/a",
        observed_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        weight=1.0,
        evidence_ref="fixture:event:a",
    )

    class DuckEvent:
        account_id = event.account_id
        relation = event.relation
        object_id = event.object_id
        observed_at = event.observed_at
        weight = event.weight
        evidence_ref = event.evidence_ref

    with pytest.raises(ValueError, match="exact canonical CoordinationEvent"):
        runner.DiscoveryExecutionInput(_manifest(package), (DuckEvent(),))
    with pytest.raises(ValueError, match="exact canonical CoordinationEvent"):
        runner.DiscoveryExecutionInput(_manifest(package), ("label-free-event",))

    sealed = runner.DiscoveryExecutionInput(_manifest(package), (event,))
    assert type(sealed.events[0]) is event_type
    assert sealed.events[0] == event
    assert sealed.events[0] is not event


def test_second_review_iohunter_observed_time_is_intrinsic_without_markers():
    package, _, _, runner = _modules()
    manifest = dataclasses.replace(
        _manifest(package, claim_markers=(), time_axis="static_placeholder_not_observed_time"),
        dataset_id="iohunter-russia",
        campaign_axis=("russia",),
    )
    with pytest.raises(ValueError, match="IOHunter.*observed_time_holdout"):
        runner.ResultRow(
            dataset_id=manifest.dataset_id,
            dataset_manifest_fingerprint=manifest.fingerprint,
            evaluator_fingerprint="sha256:" + "b" * 64,
            split_policy="observed_time_holdout",
            split_fingerprint=_split(package, policy="observed_time_holdout").fingerprint,
            method_id="edgebank",
            method_version="edgebank-v1",
            model_role="temporal_baseline",
            seed=42,
            runtime_seconds=1.0,
            peak_memory_bytes=1024,
            status="success",
            metrics=_complete_discovery_metrics(),
            claim_markers=(),
            task="discovery",
            audit={"audit_version": "fixture/v1", "label_free_execution": True},
        )

    static_row = runner.ResultRow(
        dataset_id=manifest.dataset_id,
        dataset_manifest_fingerprint=manifest.fingerprint,
        evaluator_fingerprint="sha256:" + "b" * 64,
        split_policy="official_static_fold",
        split_fingerprint=_split(package).fingerprint,
        method_id="edgebank",
        method_version="edgebank-v1",
        model_role="temporal_baseline",
        seed=42,
        runtime_seconds=1.0,
        peak_memory_bytes=1024,
        status="success",
        metrics=_complete_discovery_metrics(),
        claim_markers=(),
        task="discovery",
        audit={"audit_version": "fixture/v1", "label_free_execution": True},
    )
    blocked = runner.evaluate_claim_gate(
        runner.ClaimGate(
            "observed-time", "edge_auprc", "maximize", 0.5,
            claim_scope="observed_time",
        ),
        (static_row,),
    )
    assert blocked.status == "blocked"
    assert "static_placeholder_not_observed_time" in blocked.reason


def test_second_review_learned_rows_reject_arbitrary_audits_and_rehydrate_artifacts():
    package, _, _, runner = _modules()
    with pytest.raises(ValueError, match="serialized Stage 2 model artifact"):
        _row(
            package,
            runner,
            metrics=_complete_detection_metrics(),
            audit={"audit_version": "fixture/v1", "verified": True},
        )

    assert hasattr(runner.ResultRow, "from_dict")


def test_second_review_stability_peers_require_seed_and_artifact_provenance():
    package, _, _, runner = _modules()
    assert hasattr(runner, "DiscoveryStabilityPeer")
    prediction = runner.DiscoveryPrediction(
        candidate_edges=(("a", "b"),),
        approximate_quadratic_forms=(1.0,),
        edge_score_edges=(("a", "b"), ("a", "c")),
        edge_scores=(0.9, 0.1),
        predicted_clusters={"a": "x", "b": "x", "c": "y"},
        artifact_identity="sha256:" + "d" * 64,
    )
    execution = runner.DiscoveryExecutionOutcome(
        manifest=_manifest(package),
        method_id="edgebank",
        method_version="edgebank-v1",
        model_role="temporal_baseline",
        implementation_id="fixture-edgebank-implementation-v1",
        selection_eligible=False,
        ablation_id=None,
        claim_markers=("research_only",),
        runtime_seconds=0.1,
        peak_memory_bytes=1024,
        status="success",
        prediction=prediction,
        reason=None,
        execution_input_fingerprint="sha256:" + "a" * 64,
    )
    with pytest.raises(ValueError, match="peer seed must differ"):
        runner.DiscoveryStabilityPeer(
            seed=42,
            prediction_artifact_identity="sha256:" + "e" * 64,
            predicted_clusters={"a": "one", "b": "one", "c": "two"},
            current_seed=42,
        )

    peer = runner.DiscoveryStabilityPeer(
        seed=43,
        prediction_artifact_identity="sha256:" + "e" * 64,
        predicted_clusters={"a": "one", "b": "one", "c": "two"},
        current_seed=42,
    )
    evaluation = runner.DiscoveryEvaluationInput(
        evaluator_fingerprint="sha256:" + "b" * 64,
        split=_split(package),
        reference_edges=(("a", "b"),),
        reference_quadratic_forms=(1.0,),
        edge_score_edges=(("a", "b"), ("a", "c")),
        edge_labels=(1, 0),
        true_clusters={"a": "x", "b": "x", "c": "y"},
        stability_peers=(peer,),
    )
    row = runner.evaluate_discovery_execution(execution, evaluation)
    assert row.status == "success"
    assert row.audit["stability_peer_provenance"] == (
        {
            "seed": 43,
            "prediction_artifact_identity": "sha256:" + "e" * 64,
        },
    )

    duplicate_current = dataclasses.replace(
        peer,
        prediction_artifact_identity="sha256:" + "f" * 64,
        predicted_clusters=prediction.predicted_clusters,
    )
    with pytest.raises(ValueError, match="duplicate current assignments"):
        runner.evaluate_discovery_execution(
            execution, dataclasses.replace(evaluation, stability_peers=(duplicate_current,))
        )
