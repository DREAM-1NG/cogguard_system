from __future__ import annotations

import importlib.util
import sys

import pytest

from app.config import PROJECT_ROOT


def _load_coordination_discover():
    module_name = "_test_cogguard_temporal_edge_model"
    cached = sys.modules.get(module_name)
    if cached is not None:
        return cached
    package_dir = PROJECT_ROOT / "research" / "coordination_discover"
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


def _graph():
    coordination_discover = _load_coordination_discover()
    edges = []
    pairs = [
        ("a", "b"),
        ("b", "c"),
        ("c", "d"),
        ("d", "a"),
        ("a", "c"),
        ("b", "d"),
        ("c", "a"),
        ("d", "b"),
    ]
    for index, (source, target) in enumerate(pairs):
        edges.append(
            coordination_discover.AccountMultigraphEdge(
                source_account_id=source,
                target_account_id=target,
                evidence_kind="url",
                relation_type="url_share",
                platform="weibo",
                observed_at=float(index * 10),
                weight=1.0,
                time_delta_seconds=5.0 + index,
                source_content_id=f"p{index}",
                target_content_id=f"p{index + 1}",
                evidence_objects=[f"url:{index % 2}"],
                evidence_refs=[f"ref:{index}"],
                direction="forward",
            )
        )
    return coordination_discover.EvidenceGraph(
        snapshot_id="fixture",
        event_id="fixture",
        data_fingerprint="fixture",
        accounts=["a", "b", "c", "d"],
        objects=[],
        edges=[],
        account_edges=edges,
    )


def test_temporal_edge_split_is_chronological_and_reports_leakage_checks():
    coordination_discover = _load_coordination_discover()
    config = coordination_discover.TemporalEdgeModelConfig(
        validation_ratio=0.25,
        test_ratio=0.25,
    )

    split = coordination_discover.split_temporal_account_edges(_graph(), config)

    assert split.split_policy == "chronological_event_time"
    assert split.train and split.validation and split.test
    assert max(row["observed_at"] for row in split.train) <= min(
        row["observed_at"] for row in split.validation
    )
    assert max(row["observed_at"] for row in split.validation) <= min(
        row["observed_at"] for row in split.test
    )
    assert split.leakage_checks["future_edges_in_train"] == 0
    assert split.leakage_checks["overlapping_edge_keys"] == 0


def test_hard_negative_sampler_matches_relation_and_avoids_observed_pairs():
    coordination_discover = _load_coordination_discover()
    config = coordination_discover.TemporalEdgeModelConfig(
        negative_ratio=2,
        seed=7,
    )
    split = coordination_discover.split_temporal_account_edges(_graph(), config)

    negatives = coordination_discover.build_matched_hard_negatives(
        _graph(),
        split.train,
        config,
    )

    assert negatives
    assert all(row["label"] == 0 for row in negatives)
    assert all(row["relation_type"] == "url_share" for row in negatives)
    assert all(row["platform"] == "weibo" for row in negatives)
    assert all(row["source_account_id"] != row["target_account_id"] for row in negatives)
    assert all(row["sampling_strategy"] == "relation_platform_time_degree_matched" for row in negatives)

    observed_pairs = {
        (row["source_account_id"], row["target_account_id"])
        for row in split.train
    }
    assert not any(
        (row["source_account_id"], row["target_account_id"]) in observed_pairs
        for row in negatives
    )


def test_hard_negative_sampler_is_bounded_for_large_account_sets():
    coordination_discover = _load_coordination_discover()
    positive = {
        "source_account_id": "a0",
        "target_account_id": "a1",
        "evidence_kind": "url",
        "relation_type": "url_share",
        "platform": "weibo",
        "observed_at": 10.0,
        "time_delta_seconds": 5.0,
        "evidence_objects": ["url:1"],
    }
    graph = coordination_discover.EvidenceGraph(
        snapshot_id="large",
        event_id="large",
        data_fingerprint="large",
        accounts=[f"a{index}" for index in range(500)],
        objects=[],
        edges=[],
        account_edges=[
            coordination_discover.AccountMultigraphEdge(
                source_account_id="a0",
                target_account_id="a1",
                evidence_kind="url",
                relation_type="url_share",
                platform="weibo",
                observed_at=10.0,
                weight=1.0,
                time_delta_seconds=5.0,
                source_content_id="p1",
                target_content_id="p2",
                evidence_objects=["url:1"],
                evidence_refs=["p1"],
                direction="forward",
            )
        ],
    )

    negatives = coordination_discover.build_matched_hard_negatives(
        graph,
        [positive],
        coordination_discover.TemporalEdgeModelConfig(negative_ratio=3, seed=19),
    )

    assert len(negatives) == 3
    assert all(row["source_account_id"] != row["target_account_id"] for row in negatives)
    assert not any((row["source_account_id"], row["target_account_id"]) == ("a0", "a1") for row in negatives)


def test_temporal_edge_candidate_reports_direct_pair_objective_and_protocol():
    pytest.importorskip("torch")
    coordination_discover = _load_coordination_discover()
    config = coordination_discover.TemporalEdgeModelConfig(
        embedding_dim=8,
        epochs=2,
        negative_ratio=1,
        validation_ratio=0.25,
        test_ratio=0.25,
        device="cpu",
        seed=11,
    )

    result = coordination_discover.fit_temporal_edge_model(_graph(), config)

    assert result["status"] == "ok"
    assert result["model_backend"] == "temporal_history_edge_mlp_v2"
    assert result["candidate_role"] == "research_candidate_non_claimable"
    assert result["objective"] == "direct_account_pair_coordination"
    assert result["protocol"]["split_policy"] == "chronological_event_time"
    assert result["protocol"]["target"] == "chronological_future_account_pair_edge_prediction"
    assert result["protocol"]["negative_sampling"]["strategy"] == "relation_platform_time_degree_matched"
    assert (
        result["protocol"]["negative_sampling"]["future_positive_exclusion_policy"]
        == "base_history_plus_current_and_past_positive_prefix_no_future_split_hindsight"
    )
    assert result["metrics"]["test"]["sample_count"] > 0
    assert {"roc_auc", "auprc", "max_f1", "ece"}.issubset(result["metrics"]["test"])
    assert result["training"]["feature_fit_policy"] == "train_examples_only"
    assert result["baselines"]["observed_edge_upper_bound"]["test"]["auprc"] == 1.0
    assert result["baselines"]["system_future_edge_prior"]["test"]["auprc"] <= 1.0
    assert result["baselines"]["edgebank_repeat"]["test"]["auprc"] <= 1.0
    assert result["baselines"]["tgn_style_memory_prior"]["test"]["auprc"] <= 1.0
    assert result["baselines"]["degree_time_prior"]["test"]["auprc"] <= 1.0
    assert result["claim_gate"]["comparison_baseline"] == "system_future_edge_prior"
    assert result["claim_gate"]["baseline_test_edge_auprcs"]["edgebank_repeat"] <= 1.0
    assert result["claim_gate"]["baseline_test_edge_auprcs"]["tgn_style_memory_prior"] <= 1.0
    assert result["claim_gate"]["observed_edge_upper_bound_test_edge_auprc"] == 1.0
    assert result["claim_gate"]["blocked_reason"] in {None, "candidate_below_fair_system_baseline"}
    assert result["diagnostics"]["train_account_oov_rate"] == 0.0
    assert "log_weight" not in result["model_summary"]["input_feature_names"]
    assert "observed_rank" not in result["model_summary"]["input_feature_names"]
    assert "system_future_edge_prior_score" in result["model_summary"]["input_feature_names"]
    assert "test_account_oov_rate" in result["diagnostics"]
    assert "leiden" not in result["model_backend"]


def test_temporal_edge_candidate_runs_multi_seed_and_reports_aggregate():
    pytest.importorskip("torch")
    coordination_discover = _load_coordination_discover()
    config = coordination_discover.TemporalEdgeModelConfig(
        embedding_dim=8,
        hidden_dim=8,
        epochs=1,
        negative_ratio=1,
        validation_ratio=0.25,
        test_ratio=0.25,
        device="cpu",
        seed=11,
    )

    result = coordination_discover.fit_temporal_edge_model_multi_seed(
        _graph(),
        config,
        seeds=(11, 12),
    )

    assert result["status"] == "ok"
    assert result["evaluation_mode"] == "multi_seed"
    assert result["seed_count"] == 2
    assert set(result["aggregate"]["test"]["auprc"]).issuperset({"mean", "std", "values"})
    assert len(result["aggregate"]["test"]["auprc"]["values"]) == 2
    assert "win_rate_vs_system_future_edge_prior" in result["aggregate"]["claim_gate"]
    assert "strongest_fair_baseline" in result["aggregate"]["claim_gate"]


def test_temporal_edge_ablation_suite_is_research_only_and_disables_components():
    pytest.importorskip("torch")
    coordination_discover = _load_coordination_discover()
    config = coordination_discover.TemporalEdgeModelConfig(
        embedding_dim=8,
        hidden_dim=8,
        epochs=1,
        negative_ratio=1,
        validation_ratio=0.25,
        test_ratio=0.25,
        device="cpu",
        seed=11,
    )

    result = coordination_discover.run_temporal_edge_ablation_suite(
        _graph(),
        config,
        seeds=(11,),
    )

    assert result["status"] == "ok"
    assert result["evaluation_mode"] == "ablation_suite"
    assert result["candidate_role"] == "research_candidate_non_claimable"
    variants = {row["variant"]: row for row in result["variants"]}
    assert {"full", "learned_only", "no_system_prior_feature", "no_exact_pair_history", "no_relation_memory"}.issubset(variants)
    assert variants["no_system_prior_feature"]["config"]["score_ensemble_mode"] == "learned_only"
    assert "system_future_edge_prior_score" in variants["no_system_prior_feature"]["config"]["disabled_feature_names"]
    assert variants["no_exact_pair_history"]["config"]["score_ensemble_mode"] == "learned_only"


def test_temporal_edge_candidate_caps_exported_prediction_rows():
    pytest.importorskip("torch")
    coordination_discover = _load_coordination_discover()
    config = coordination_discover.TemporalEdgeModelConfig(
        embedding_dim=8,
        epochs=1,
        negative_ratio=1,
        validation_ratio=0.25,
        test_ratio=0.25,
        prediction_export_limit=2,
        device="cpu",
        seed=13,
    )

    result = coordination_discover.fit_temporal_edge_model(_graph(), config)

    assert result["status"] == "ok"
    assert len(result["prediction_rows"]["train"]) <= 2
    assert len(result["prediction_rows"]["validation"]) <= 2
    assert len(result["prediction_rows"]["test"]) <= 2
    assert result["prediction_row_counts"]["train"] >= len(result["prediction_rows"]["train"])
