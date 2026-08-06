from __future__ import annotations

import csv
import dataclasses
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
        audit={"audit_version": "fixture/v1", "verified": True} if audit is None else audit,
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
        supports_harmful_cib_detection=True,
        supports_campaign_io_evaluation=True,
        blocked_reasons={"social_bot_classification": "not a bot dataset"},
        claim_markers=("research_only",),
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
    } <= set(registry.method_ids())
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
        method_id="learned_fused_detector",
        method_version="learned-coordination-logistic-v1",
        model_role="primary_learned",
        seed=42,
        runtime_seconds=1.0,
        peak_memory_bytes=1024,
        status="success",
        metrics={**_complete_detection_metrics(), "auprc": 1.0},
        claim_markers=("static_placeholder_not_observed_time",),
        selection_eligible=True,
        audit={"audit_version": "fixture/v1", "verified": True},
    )
    result = runner.evaluate_claim_gate(
        runner.ClaimGate(
            "time-holdout", "auprc", "maximize", 0.5,
            claim_scope="observed_time",
            required_split_policy="observed_time_holdout",
        ),
        (row,),
    )
    assert result.status == "blocked"


def test_artifact_writer_emits_deterministic_json_csv_aggregates_and_claim_gates(tmp_path):
    package, _, _, runner = _modules()
    rows = (
        _row(package, runner, seed=43, metrics={**_complete_detection_metrics(), "auprc": 0.9}),
        _row(package, runner, seed=42, metrics={**_complete_detection_metrics(), "auprc": 0.7}),
        _row(package, runner, seed=44, status="blocked", reason="fixture blocked"),
    )
    gates = (runner.ClaimGate("quality", "auprc", "maximize", 0.75, claim_scope="general", minimum_successful_seeds=2),)
    first = runner.write_reproduction_artifacts(rows, tmp_path / "first", claim_gates=gates, bootstrap_resamples=200)
    second = runner.write_reproduction_artifacts(rows, tmp_path / "second", claim_gates=gates, bootstrap_resamples=200)

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
        supports_harmful_cib_detection=True,
        supports_campaign_io_evaluation=True,
        blocked_reasons={
            "observed_time_holdout": "timestamps unavailable",
            "social_bot_classification": "not a bot dataset",
        },
        claim_markers=("research_only",),
    )
    registry = baselines.default_baseline_registry()
    execution_input = runner.DiscoveryExecutionInput(
        manifest=_manifest(package), events=("label-free-event",)
    )
    blocked = runner.execute_discovery_method(
        registry, "tgn_style_memory_prior", execution_input, capability
    )
    assert blocked.status == "blocked"
    assert "observed_time_holdout" in blocked.reason

    registry.bind(
        "edgebank",
        baselines.DiscoveryImplementation(
            "edgebank-implementation-v1",
            lambda _: (_ for _ in ()).throw(RuntimeError("fixture exploded")),
        ),
    )
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
        split_policy="observed_time_holdout",
        split_fingerprint=_split(package).fingerprint,
        method_id="learned_fused_detector",
        method_version="learned-coordination-logistic-v1",
        model_role="primary_learned",
        seed=42,
        runtime_seconds=1.0,
        peak_memory_bytes=1024,
        status="success",
        metrics=_complete_detection_metrics(),
        claim_markers=("static_placeholder_not_observed_time",),
        selection_eligible=True,
        audit={"audit_version": "fixture/v1", "verified": True},
    )
    observed_time = runner.evaluate_claim_gate(
        runner.ClaimGate(
            "observed-time", "auprc", "maximize", 0.5,
            claim_scope="observed_time",
            required_split_policy="observed_time_holdout",
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
    registry = baselines.default_baseline_registry()
    seen = []

    def execute(execution_input):
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

    registry.bind(
        "edgebank",
        baselines.DiscoveryImplementation("edgebank-implementation-v1", execute),
    )
    manifest = _manifest(package)
    execution = runner.execute_discovery_method(
        registry,
        "edgebank",
        runner.DiscoveryExecutionInput(manifest=manifest, events=("label-free-event",)),
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
            peer_cluster_assignments=({"a": "one", "b": "one", "c": "two", "d": "two"},),
        ),
    )
    assert row.status == "success"
    assert set(_complete_discovery_metrics()) == set(row.metrics)
    assert row.audit["label_free_execution"] is True
    assert row.audit["evaluation_after_execution"] is True


def test_detection_fit_audit_is_derived_from_stage2_artifact_and_partitions():
    package, _, baselines, runner = _modules()
    train, validation, test, artifact = _detection_fixture(package)
    registry = baselines.default_baseline_registry()

    def execute(partitions):
        assert partitions.train_cases == train
        assert partitions.validation_cases == validation
        assert partitions.test_cases == test
        return runner.DetectionExecutionOutput(
            model_artifact=artifact,
            predictions=(
                runner.DetectionPrediction("test-0", 0.1, "benign_coordination"),
                runner.DetectionPrediction("test-1", 0.9, "harmful_coordination"),
            ),
        )

    registry.bind(
        "learned_fused_detector",
        baselines.LearnedDetectionImplementation("learned-fused-implementation-v1", execute),
    )
    row = runner.run_detection_method(
        registry,
        "learned_fused_detector",
        manifest=_manifest(package),
        capability=_capability(package),
        evaluator_fingerprint="sha256:" + "b" * 64,
        split=_split(package),
        partitions=runner.DetectionPartitions(train, validation, test),
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
    registry.bind(
        "learned_fused_detector",
        baselines.LearnedDetectionImplementation(
            "learned-fused-implementation-v1",
            lambda _: runner.DetectionExecutionOutput(
                model_artifact=leaked,
                predictions=(
                    runner.DetectionPrediction("test-0", 0.1, "benign_coordination"),
                    runner.DetectionPrediction("test-1", 0.9, "harmful_coordination"),
                ),
            ),
        ),
    )
    rejected = runner.run_detection_method(
        registry,
        "learned_fused_detector",
        manifest=_manifest(package),
        capability=_capability(package),
        evaluator_fingerprint="sha256:" + "b" * 64,
        split=_split(package),
        partitions=runner.DetectionPartitions(train, validation, test),
    )
    assert rejected.status == "failed"
    assert "train_fit_case_ids_fingerprint" in rejected.reason


def test_registered_implementation_binding_prevents_method_relabeling():
    _, _, baselines, runner = _modules()
    registry = baselines.default_baseline_registry()
    with pytest.raises(ValueError, match="implementation identity"):
        registry.bind(
            "edgebank",
            baselines.DiscoveryImplementation(
                "dense-cosine-leiden-implementation-v1",
                lambda _: None,
            ),
        )
    assert not hasattr(runner, "run_registered_method")


def test_heuristic_implementation_receives_test_only_and_cannot_persist_fit_audit():
    package, _, baselines, runner = _modules()
    train, validation, test, _ = _detection_fixture(package)
    registry = baselines.default_baseline_registry()
    seen = []

    def execute(test_input):
        seen.append(test_input)
        assert isinstance(test_input, runner.DetectionTestInput)
        assert not hasattr(test_input, "train_cases")
        assert not hasattr(test_input, "validation_cases")
        return runner.DetectionExecutionOutput(
            model_artifact=None,
            predictions=(
                runner.DetectionPrediction("test-0", 0.1, "benign_coordination"),
                runner.DetectionPrediction("test-1", 0.9, "harmful_coordination"),
            ),
        )

    registry.bind(
        "heuristic_baseline_v1",
        baselines.HeuristicDetectionImplementation(
            "heuristic-baseline-implementation-v1", execute
        ),
    )
    row = runner.run_detection_method(
        registry,
        "heuristic_baseline_v1",
        manifest=_manifest(package),
        capability=_capability(package),
        evaluator_fingerprint="sha256:" + "b" * 64,
        split=_split(package),
        partitions=runner.DetectionPartitions(train, validation, test),
    )
    assert row.status == "success"
    assert len(seen) == 1
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
