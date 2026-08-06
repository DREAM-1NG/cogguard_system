from __future__ import annotations

import csv
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
):
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
        runtime_seconds=1.25,
        peak_memory_bytes=4096,
        status=status,
        metrics={} if metrics is None else metrics,
        reason=reason,
        warning=warning,
        claim_markers=claim_markers,
    )


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

    rows = [
        _row(package, runner, seed=42, metrics={"auprc": 0.7}),
        _row(package, runner, seed=43, metrics={"auprc": 0.9}),
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
    row = _row(package, runner, metrics={"ari": -0.25})
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


def test_fit_audit_enforces_train_validation_test_isolation_and_heuristic_no_fit():
    package, _, _, runner = _modules()
    split = _split(package)
    learned = runner.FitAudit(
        transform_fit_ids=split.train_ids,
        model_fit_ids=split.train_ids,
        calibration_fit_ids=split.validation_ids,
        threshold_fit_ids=split.validation_ids,
        ood_fit_ids=split.validation_ids,
        prediction_ids=split.test_ids,
    )
    runner.validate_fit_isolation(split, learned, model_role="primary_learned")

    leaked = runner.FitAudit(
        transform_fit_ids=split.train_ids,
        model_fit_ids=split.train_ids + (split.test_ids[0],),
        calibration_fit_ids=split.validation_ids,
        threshold_fit_ids=split.validation_ids,
        ood_fit_ids=split.validation_ids,
        prediction_ids=split.test_ids,
    )
    with pytest.raises(ValueError, match="model_fit_ids"):
        runner.validate_fit_isolation(split, leaked, model_role="primary_learned")

    no_fit = runner.FitAudit(prediction_ids=split.test_ids)
    runner.validate_fit_isolation(split, no_fit, model_role="heuristic_baseline")
    with pytest.raises(ValueError, match="must not fit"):
        runner.validate_fit_isolation(split, learned, model_role="heuristic_baseline")


def test_heuristic_rows_are_isolated_from_learned_selection():
    package, _, _, runner = _modules()
    warning = "Research-only heuristic baseline; output is not a learned or production decision."
    heuristic = _row(
        package,
        runner,
        method_id="heuristic_baseline_v1",
        method_version="heuristic_baseline_v1",
        model_role="heuristic_baseline",
        metrics={"auprc": 0.99},
        warning=warning,
    )
    learned = _row(package, runner, metrics={"auprc": 0.8})
    assert runner.select_learned_artifact((heuristic, learned)).artifact_identity == learned.artifact_identity
    with pytest.raises(ValueError, match="warning"):
        _row(
            package,
            runner,
            method_id="heuristic_baseline_v1",
            method_version="heuristic_baseline_v1",
            model_role="heuristic_baseline",
            metrics={"auprc": 0.99},
        )


def test_claim_gates_use_observed_rows_metric_direction_and_dataset_markers():
    package, _, _, runner = _modules()
    rows = (
        _row(package, runner, seed=42, metrics={"auprc": 0.80, "ece": 0.08}),
        _row(package, runner, seed=43, metrics={"auprc": 0.84, "ece": 0.12}),
        _row(package, runner, seed=44, status="failed", reason="failure"),
    )
    maximize = runner.evaluate_claim_gate(
        runner.ClaimGate("harmful-auprc", "auprc", "maximize", 0.81, minimum_successful_seeds=2),
        rows,
    )
    minimize = runner.evaluate_claim_gate(
        runner.ClaimGate("calibration", "ece", "minimize", 0.10, minimum_successful_seeds=2),
        rows,
    )
    assert maximize.status == "supported"
    assert minimize.status == "supported"
    assert maximize.observed_artifact_identities == tuple(sorted(row.artifact_identity for row in rows[:2]))
    assert maximize.to_dict()["direction"] == "maximize"

    cresci = _row(
        package,
        runner,
        metrics={"auprc": 1.0},
        claim_markers=("not_harmful_cib_claim",),
    )
    blocked = runner.evaluate_claim_gate(
        runner.ClaimGate(
            "harmful-cib", "auprc", "maximize", 0.5,
            forbidden_claim_markers=("not_harmful_cib_claim",),
        ),
        (cresci,),
    )
    assert blocked.status == "blocked"
    assert "not_harmful_cib_claim" in blocked.reason

    runtime = runner.evaluate_claim_gate(
        runner.ClaimGate("runtime", "runtime_seconds", "minimize", 1.3, minimum_successful_seeds=2),
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
        metrics={"auprc": 1.0},
        claim_markers=("static_placeholder_not_observed_time",),
    )
    result = runner.evaluate_claim_gate(
        runner.ClaimGate(
            "time-holdout", "auprc", "maximize", 0.5,
            required_split_policy="observed_time_holdout",
        ),
        (row,),
    )
    assert result.status == "blocked"


def test_artifact_writer_emits_deterministic_json_csv_aggregates_and_claim_gates(tmp_path):
    package, _, _, runner = _modules()
    rows = (
        _row(package, runner, seed=43, metrics={"auprc": 0.9}),
        _row(package, runner, seed=42, metrics={"auprc": 0.7}),
        _row(package, runner, seed=44, status="blocked", reason="fixture blocked"),
    )
    gates = (runner.ClaimGate("quality", "auprc", "maximize", 0.75, minimum_successful_seeds=2),)
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
        "direction": "maximize",
        "forbidden_claim_markers": [],
        "gate_id": "quality",
        "method_id": None,
        "metric_name": "auprc",
        "minimum_successful_seeds": 2,
        "required_split_policy": None,
        "threshold": 0.75,
    }


def test_runner_converts_unavailable_capability_and_exception_to_observed_rows():
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
    context = runner.RunContext(
        manifest=_manifest(package),
        evaluator_fingerprint="sha256:" + "b" * 64,
        split=_split(package),
        capability=capability,
    )
    registry = baselines.default_baseline_registry()
    blocked = runner.run_registered_method(
        registry, "tgn_style_memory_prior", context, lambda _: {"edge_auprc": 0.5}
    )
    assert blocked.status == "blocked"
    assert blocked.metrics == {}

    failed = runner.run_registered_method(
        registry,
        "learned_fused_detector",
        context,
        lambda _: (_ for _ in ()).throw(RuntimeError("fixture exploded")),
    )
    assert failed.status == "failed"
    assert "fixture exploded" in failed.reason


def test_cli_script_has_no_production_activation_imports():
    script = PROJECT_ROOT / "backend" / "scripts" / "run_coordination_two_stage_reproduction.py"
    source = script.read_text(encoding="utf-8")
    assert "coordination_model_service" not in source
    assert "coordination-evidence-runtime-v2" not in source
    assert "sys.path.insert" not in source
