import json
import pickle
import importlib.util
from argparse import Namespace
from pathlib import Path

import networkx as nx
import numpy as np
import pandas as pd
import pytest

from scripts.run_io_reproduction_suite import parse_args
from scripts.run_discover_encoder_comparison import _summary_row, _winner
from scripts import run_discover_stability_batch as stability_batch
from scripts.run_detect_encoder_batch import (
    _load_or_run_discovery as _detect_batch_load_or_run_discovery,
    _row_from_result as _detect_batch_row_from_result,
)

from app.core.coordination_baseline.deep_graph import DeepGraphDiscoverConfig, run_deep_graph_discover
from app.core.coordination_baseline.io_reproduction import (
    DEFAULT_RELATIONS,
    build_coordination_discover_comparison_report,
    build_dynamic_relation_graphs,
    build_iohunter_commands,
    build_iohunter_run_plan,
    run_iohunter_lightweight_batch,
    build_unmasking_similarity_graphs,
    dynamic_graph_summary,
    ensure_iohunter_official_data_layout,
    fuse_directed_graphs,
    fuse_similarity_graphs,
    generate_llm_prompt_records,
    inspect_iohunter_data,
    inspect_iohunter_environment,
    iohunter_workspace_status,
    iohunter_processed_to_event_table,
    load_iohunter_run_plan,
    make_sample_events,
    node_embedding_classifier_baseline,
    patch_iohunter_official_scripts,
    parse_iohunter_log_metrics,
    node_pruning_baseline,
    run_dyna_colm_ablation_suite,
    run_dyna_colm_characterize,
    run_discover_ablation_suite,
    run_discover_stability_analysis,
    run_dyna_colm_detect,
    run_dyna_colm_discover,
    run_dyna_colm_gnn_prototype,
    run_dyna_colm_gnn_ablations,
    run_setting_a_discovery,
    run_setting_b_detection,
    run_setting_ablation_suite,
    run_iohunter_plan,
    run_lightweight_llm_baselines,
    run_zeyan_coexpression_summary,
    run_reproduction_suite,
    run_unmasking_reproduction,
    summarize_iohunter_runs,
    flatten_reproduction_metrics,
    write_iohunter_run_exports,
    write_iohunter_event_table,
    _apply_discover_edge_scores_to_relation_graphs,
    _dynamic_edge_records_from_graph,
    _is_valid_zip,
    normalize_event_table,
)


def test_unmasking_similarity_graph_and_fused_graph_are_constructed():
    events = make_sample_events()
    graphs = build_unmasking_similarity_graphs(events, relations=("url_share", "hashtag_share", "retweet_target"))
    fused = fuse_similarity_graphs(graphs)

    assert set(graphs) == {"url_share", "hashtag_share", "retweet_target", "text_similarity"}
    assert graphs["url_share"].has_edge("u1", "u2")
    assert fused.has_edge("u1", "u2")
    assert "url_share" in fused["u1"]["u2"]["relations"]
    assert graphs["url_share"]["u1"]["u2"]["object_instances"]
    assert graphs["url_share"]["u1"]["u2"]["object_instances"][0]["object_id"] == "https://a.example/story"


def test_node_pruning_and_embedding_classifier_report_metrics():
    events = make_sample_events()
    result = run_unmasking_reproduction(events, relations=("url_share", "hashtag_share", "retweet_target"))
    fused_summary = result["graph_summaries"]["fused"]
    pruning = result["node_pruning"]["fused"]
    embedding_classifier = result["node_embedding_classifier"]

    assert fused_summary["node_count"] == 4
    assert pruning["selected_nodes"]
    assert pruning["metrics"] is not None
    assert embedding_classifier["metrics"] is not None


def test_node_embedding_classifier_handles_labeled_isolates_missing_from_graph():
    graph = nx.Graph()
    graph.add_edge("u1", "u2", weight=1.0)
    result = node_embedding_classifier_baseline(graph, {"u1": 1, "u2": 1, "u3": 0, "u4": 0}, dim=4)

    assert result["metrics"] is not None
    assert set(result["test_nodes"]).issubset({"u1", "u2", "u3", "u4"})


def test_node_embedding_classifier_uses_lightweight_backend_for_large_graphs():
    graph = nx.Graph()
    graph.add_edges_from((f"u{index}", f"u{index + 1}") for index in range(1199))
    labels = {f"u{index}": int(index % 2 == 0) for index in range(1200)}
    result = node_embedding_classifier_baseline(graph, labels, dim=32)

    assert result["embedding_backend"] == "structural_fallback"
    assert result["metrics"] is not None


def test_lightweight_llm_baselines_generate_prompt_records(tmp_path: Path):
    events = make_sample_events()
    graphs = build_unmasking_similarity_graphs(events, relations=("url_share", "hashtag_share", "retweet_target"))
    fused = fuse_similarity_graphs(graphs)

    records = generate_llm_prompt_records(events, fused, mode="centrality", labels={"u1": 1})
    result = run_lightweight_llm_baselines(events, fused, output_dir=tmp_path)

    assert records
    assert "degree centrality" in records[0]["input"]
    assert set(result["modes"]) == {"interaction", "centrality", "metadata", "content", "multi_input"}
    assert (tmp_path / "leveraging_llms" / "centrality_prompts.jsonl").exists()


def test_dyna_colm_gnn_prototype_outputs_scores_and_communities():
    events = make_sample_events()
    result = run_dyna_colm_gnn_prototype(events, relations=("url_share", "hashtag_share", "retweet_target"))

    assert result["method"] == "dyna_colm_gnn_prototype"
    assert result["variant"] == "full"
    assert result["relation_attention"]
    assert result["task"] == "coordination_community_discovery_then_discrimination"
    assert abs(sum(result["relation_attention"].values()) - 1.0) < 1e-5
    assert result["nodes"]
    assert result["edges"]
    assert result["dynamic_edges"]
    assert result["communities"]
    assert "top_objects" in result["communities"][0]
    assert "directed_out_weight" in result["nodes"][0]


def test_dyna_colm_gnn_ablations_are_exportable_variants():
    events = make_sample_events()
    result = run_dyna_colm_gnn_ablations(events, relations=("url_share", "hashtag_share", "retweet_target"))

    assert set(result).issuperset({"full", "without_lm", "without_gnn", "without_direction_time"})
    assert result["without_lm"]["uses_lm_features"] is False
    assert result["without_gnn"]["uses_gnn_message_passing"] is False
    assert result["without_direction_time"]["uses_direction_time_features"] is False
    assert result["full"]["metrics"] is not None


def test_dyna_colm_discover_outputs_unlabeled_community_evidence(tmp_path: Path):
    events = make_sample_events().drop(columns=["label"])
    result = run_dyna_colm_discover(
        events,
        output_dir=tmp_path,
        relations=("url_share", "hashtag_share", "retweet_target"),
        seed=42,
        encoder="lightweight",
        community_algorithm="louvain",
    )

    assert result["setting"] == "discover"
    assert result["task"] == "coordination_community_discovery"
    assert result["metrics"]["cluster_count"] >= 1
    assert result["relation_attention"]
    assert result["nodes"]
    assert result["edges"]
    assert result["dynamic_edges"]
    assert result["communities"]
    assert "community_score" in result["communities"][0]
    assert "evidence_summary" in result
    assert result["structure_filter"]["mode"] == "none"
    assert result["deep_graph_model"]["encoder"] == "lightweight"
    assert result["community_algorithm"] == "louvain"
    assert result["graph_metrics"]["community_algorithm"] == "louvain"
    assert result["graph_metrics"]["community_algorithm_effective"] in {"louvain", "greedy"}
    assert (tmp_path / "discovery_summary.json").exists()


def test_dyna_colm_discover_defaults_to_leiden_with_explicit_effective_backend():
    events = make_sample_events().drop(columns=["label"])
    result = run_dyna_colm_discover(
        events,
        relations=("url_share", "hashtag_share", "retweet_target"),
        seed=42,
        encoder="lightweight",
    )

    assert result["community_algorithm"] == "leiden"
    assert result["graph_metrics"]["community_algorithm"] == "leiden"
    assert result["community_algorithm_effective"] in {"leiden", "louvain", "greedy"}
    assert result["graph_metrics"]["community_algorithm_effective"] == result["community_algorithm_effective"]
    if result["community_algorithm_effective"] != "leiden":
        assert result["community_algorithm_fallback_reason"]


def test_dyna_colm_discover_is_stable_for_fixed_seed():
    events = make_sample_events().drop(columns=["label"])
    first = run_dyna_colm_discover(events, relations=("url_share", "hashtag_share", "retweet_target"), seed=7, encoder="lightweight")
    second = run_dyna_colm_discover(events, relations=("url_share", "hashtag_share", "retweet_target"), seed=7, encoder="lightweight")

    assert first["metrics"]["cluster_count"] == second["metrics"]["cluster_count"]
    assert first["relation_attention"] == second["relation_attention"]
    assert first["communities"][0]["top_objects"] == second["communities"][0]["top_objects"]


def test_dyna_colm_discover_ignores_deprecated_structure_filter_and_stays_full_graph():
    events = make_sample_events().drop(columns=["label"])
    result = run_dyna_colm_discover(
        events,
        relations=("url_share", "hashtag_share", "retweet_target"),
        seed=13,
        encoder="magnn" if importlib.util.find_spec("torch") is not None else "lightweight",
        structure_filter="node_pruning",
        structure_filter_metric="eigenvector",
        structure_filter_percentile=75.0,
        device="cpu",
        epochs=1,
        embedding_dim=8,
        hidden_dim=8,
    )

    assert result["structure_filter"]["mode"] == "none"
    assert result["structure_filter"]["deprecated_ignored"] is True
    assert result["structure_filter"]["requested_mode"] == "node_pruning"
    assert result["structure_filter"]["requested_metric"] == "eigenvector"
    assert result["structure_filter"]["selection_semantics"] == "full_graph_mainline"
    assert "selected_node_count" in result["structure_filter"]
    assert result["graph_metrics"]["node_count"] == len(result["nodes"])
    assert all("passed_structure_filter" in node for node in result["nodes"])
    assert all("structure_filter_score" in node for node in result["nodes"])
    assert "structure_filter" in result["evidence_summary"]


def test_dyna_colm_discover_structure_filter_fields_remain_neutral_after_disable():
    events = make_sample_events().drop(columns=["label"])
    result = run_dyna_colm_discover(
        events,
        relations=("url_share", "hashtag_share", "retweet_target"),
        seed=17,
        encoder="lightweight",
        structure_filter="node_pruning",
        structure_filter_metric="pagerank",
        structure_filter_percentile=75.0,
    )

    assigned_nodes = [node for node in result["nodes"] if node.get("cluster_id") is not None]
    assert len(assigned_nodes) == len(result["nodes"])
    assert result["structure_filter"]["graph_node_count_after"] == len(result["nodes"])
    assert result["structure_filter"]["selected_node_count"] == len(result["nodes"])
    assert all(bool(node["passed_structure_filter"]) for node in result["nodes"])
    assert all(float(node["structure_filter_score"]) == 1.0 for node in result["nodes"])


def test_discover_stability_analysis_writes_window_and_multiscale_outputs(tmp_path: Path):
    events = make_sample_events().drop(columns=["label"])
    result = run_discover_stability_analysis(
        events,
        output_dir=tmp_path,
        relations=("url_share", "hashtag_share", "retweet_target", "mention_target"),
        seed=11,
        encoder="lightweight",
        community_algorithm="leiden",
        window_sizes=(4.0, 8.0),
        min_events_per_window=2,
    )

    assert result["setting"] == "discover"
    assert result["task"] == "coordination_community_stability"
    assert result["windows"]
    assert result["pairwise_stability"]
    assert any(row["comparison_type"] == "multiscale_same_index" for row in result["pairwise_stability"])
    assert set(result["summary"]).issuperset({"mean_modularity", "mean_adjacent_jaccard"})
    assert (tmp_path / "discover_stability_windows.csv").exists()
    assert (tmp_path / "discover_stability_pairwise.csv").exists()
    assert (tmp_path / "stability_manifest.json").exists()


def test_han_discover_encoder_trains_when_torch_is_available():
    if importlib.util.find_spec("torch") is None:
        pytest.skip("torch is not installed in this environment")
    events = make_sample_events().drop(columns=["label"])
    graphs = build_unmasking_similarity_graphs(events, relations=("url_share", "hashtag_share", "retweet_target"), include_text_similarity=False)
    fused = fuse_similarity_graphs(graphs)
    nodes = sorted(set(events["account_id"].astype(str)).union(set(map(str, fused.nodes))))
    features = np.ones((len(nodes), 4), dtype=float)
    for graph in graphs.values():
        graph.add_nodes_from(nodes)
    for encoder in ("han_relation", "han", "magnn_legacy", "magnn", "amdn_hage"):
        result = run_deep_graph_discover(
            graphs,
            nodes,
            features,
            DeepGraphDiscoverConfig(encoder=encoder, epochs=2, embedding_dim=8, hidden_dim=8, seed=42),
        )

        assert result.embeddings.shape == (len(nodes), 8)
        assert result.relation_attention
        assert abs(sum(result.relation_attention.values()) - 1.0) < 1e-5
        assert result.training_loss
        assert result.reconstruction_metrics["positive_edge_count"] > 0
        assert result.edge_scores
        assert result.uses_labels is False


def test_dyna_colm_discover_is_label_free_under_lightweight_encoder():
    events = make_sample_events()
    flipped = events.copy()
    flipped["label"] = 1 - flipped["label"]

    first = run_dyna_colm_discover(events, relations=("url_share", "hashtag_share", "retweet_target"), seed=5, encoder="lightweight")
    second = run_dyna_colm_discover(flipped, relations=("url_share", "hashtag_share", "retweet_target"), seed=5, encoder="lightweight")

    assert first["communities"] == second["communities"]
    assert first["relation_attention"] == second["relation_attention"]
    assert first["edges"] == second["edges"]
    assert first["deep_graph_model"]["uses_labels"] is False


def test_dyna_colm_discover_han_outputs_deep_graph_fields_when_torch_is_available(tmp_path: Path):
    if importlib.util.find_spec("torch") is None:
        pytest.skip("torch is not installed in this environment")
    result = run_dyna_colm_discover(
        make_sample_events(),
        output_dir=tmp_path,
        relations=("url_share", "hashtag_share", "retweet_target"),
        seed=42,
        encoder="han",
        epochs=2,
        embedding_dim=8,
        hidden_dim=8,
    )

    assert result["deep_graph_model"]["encoder"] == "han"
    assert result["deep_graph_model"]["uses_labels"] is False
    assert result["deep_graph_model"]["training_loss"]
    assert result["deep_graph_model"]["metapath_attention"]
    assert "reconstruction_auc" in result["metrics"]
    assert "embedding_norm" in result["nodes"][0]
    assert "text_similarity" not in result["relation_attention"]


def test_dyna_colm_discover_defaults_to_stable_magnn_legacy_when_torch_is_available():
    if importlib.util.find_spec("torch") is None:
        pytest.skip("torch is not installed in this environment")
    result = run_dyna_colm_discover(
        make_sample_events().drop(columns=["label"]),
        relations=("url_share", "hashtag_share", "retweet_target"),
        seed=42,
        epochs=1,
        embedding_dim=8,
        hidden_dim=8,
        device="cpu",
    )

    assert result["deep_graph_model"]["encoder"] == "magnn_legacy"
    assert result["deep_graph_model"]["intra_metapath_attention_summary"]["attention_mechanism"] == "sigmoid_gated_legacy"
    assert result["model_governance"]["status"] == "stable_default"


def test_dyna_colm_discover_magnn_and_amdn_hage_are_available_when_torch_is_available():
    if importlib.util.find_spec("torch") is None:
        pytest.skip("torch is not installed in this environment")
    for encoder in ("magnn_legacy", "magnn", "amdn_hage"):
        result = run_dyna_colm_discover(
            make_sample_events().drop(columns=["label"]),
            relations=("url_share", "hashtag_share", "retweet_target"),
            seed=42,
            encoder=encoder,
            epochs=1,
            embedding_dim=8,
            hidden_dim=8,
        )
        assert result["deep_graph_model"]["encoder"] == encoder
        assert result["deep_graph_model"]["uses_labels"] is False
        assert result["deep_graph_model"]["training_loss"]
        if encoder == "magnn_legacy":
            assert result["deep_graph_model"]["object_node_count"] > 0
            assert result["deep_graph_model"]["metapath_instance_counts"]["url_share"] > 0
            assert result["deep_graph_model"]["edge_score_source"] == "magnn_legacy_edge_reconstruction"
            assert result["deep_graph_model"]["intra_metapath_attention_summary"]["attention_mechanism"] == "sigmoid_gated_legacy"
        if encoder == "magnn":
            assert result["deep_graph_model"]["object_node_count"] > 0
            assert result["deep_graph_model"]["metapath_instance_counts"]["url_share"] > 0
            assert result["deep_graph_model"]["edge_score_source"] == "magnn_edge_reconstruction"
            assert result["deep_graph_model"]["intra_metapath_attention_summary"]["attention_mechanism"] == "target_grouped_softmax"
        if encoder == "amdn_hage":
            assert result["deep_graph_model"]["temporal_nll"] is not None


def test_dyna_colm_discover_outputs_full_embeddings_and_edge_scores_label_free():
    if importlib.util.find_spec("torch") is None:
        pytest.skip("torch is not installed in this environment")
    events = make_sample_events()
    flipped = events.copy()
    flipped["label"] = 1 - flipped["label"].astype(int)

    first = run_dyna_colm_discover(
        events,
        relations=("url_share", "hashtag_share", "retweet_target"),
        seed=42,
        encoder="magnn",
        epochs=1,
        embedding_dim=8,
        hidden_dim=8,
        device="cpu",
    )
    second = run_dyna_colm_discover(
        flipped,
        relations=("url_share", "hashtag_share", "retweet_target"),
        seed=42,
        encoder="magnn",
        epochs=1,
        embedding_dim=8,
        hidden_dim=8,
        device="cpu",
    )

    first_embeddings = {node["account_id"]: node["discover_embedding"] for node in first["nodes"]}
    second_embeddings = {node["account_id"]: node["discover_embedding"] for node in second["nodes"]}
    assert all(len(values) == 8 for values in first_embeddings.values())
    assert first_embeddings == second_embeddings
    assert first["deep_graph_model"]["observed_edge_scores"]
    assert first["deep_graph_model"]["observed_edge_scores"] == second["deep_graph_model"]["observed_edge_scores"]


def test_zeyan_coexpression_and_discover_ablation_suite_are_discover_only():
    if importlib.util.find_spec("torch") is None:
        pytest.skip("torch is not installed in this environment")
    events = make_sample_events()
    baseline = run_zeyan_coexpression_summary(
        events,
        relations=("url_share", "hashtag_share", "retweet_target"),
        seed=42,
        community_algorithm="greedy",
    )
    ablations = run_discover_ablation_suite(
        events,
        relations=("url_share", "hashtag_share", "retweet_target"),
        seed=42,
        epochs=1,
        embedding_dim=8,
        hidden_dim=8,
        device="cpu",
    )

    assert baseline["setting"] == "discover"
    assert baseline["method"] == "zeyan_coexpression_discover"
    assert baseline["deep_graph_model"]["edge_score_source"] == "static_coexpression_weight"
    assert set(ablations) == {"raw_graph_community", "zeyan_coexpression", "magnn_legacy", "han", "amdn_hage"}
    for summary in ablations.values():
        assert summary["setting"] == "discover"
        assert "label_auc" not in summary["metrics"]
        assert "label_f1" not in summary["metrics"]


def test_dyna_colm_detect_outputs_predictions_metrics_and_ablations(tmp_path: Path):
    events = make_sample_events()
    result = run_dyna_colm_detect(
        events,
        output_dir=tmp_path,
        relations=("url_share", "hashtag_share", "retweet_target"),
        seed=42,
        discover_encoder="magnn",
        discover_epochs=1,
        embedding_dim=8,
        hidden_dim=8,
        device="cpu",
        lm_backend="tfidf",
        gnn_backend="relation_gnn",
        split_mode="supervised",
    )

    assert result["setting"] == "detect"
    assert result["task"] == "coordination_discrimination"
    assert result["detect_model"]["uses_discover_outputs"] is True
    assert result["detect_model"]["discover_encoder"] == "magnn"
    assert result["detect_model"]["model_governance"]["status"] == "deprecated_non_claimable"
    assert result["detect_model"]["lm_backend"] == "tfidf"
    assert result["detect_model"]["lm_feature_source"] == "tfidf_object_bag_fallback"
    assert result["detect_model"]["gnn_backend"] == "relation_gnn"
    assert result["detect_model"]["split_mode"] == "supervised"
    assert result["detect_model"]["split_detail"] == "supervised"
    assert result["detect_model"]["evaluation_protocol"] == "heldout_test_only"
    assert result["detect_model"]["feature_count"] > 0
    assert result["detect_model"]["uses_full_discover_embeddings"] is True
    assert result["detect_model"]["discover_embedding_dim"] == 8
    assert result["detect_model"]["feature_count"] >= result["detect_model"]["discover_feature_count"] + result["detect_model"]["lm_feature_count"]
    assert result["detect_model"]["uses_discover_reweighted_edges"] is True
    assert result["detect_model"]["reweighted_edge_count"] > 0
    assert result["detect_model"]["edge_score_source"] == "magnn_edge_reconstruction"
    assert result["metrics"] is not None
    assert "max_f1" in result["metrics"]
    assert result["metrics"]["primary_f1_metric"] == "max_f1"
    assert result["metrics"]["fixed_threshold_f1_policy"] == "diagnostic_only"
    assert "auc" in result["metrics"]
    assert {"ap", "max_f1", "macro_f1_at_0_5"}.issubset(result["metrics"]["amdn_hage_style"])
    assert result["all_node_metrics"] is not None
    assert set(row["evaluation_split"] for row in result["predictions"]).issuperset({"train", "test"})
    assert result["predictions"]
    assert {"account_id", "node_score", "predicted_label", "evaluation_split", "cluster_id"}.issubset(result["predictions"][0])
    assert result["community_scores"]
    assert result["characterization"]["task"] == "coordination_characterization"
    assert result["characterization"]["communities"]
    first_characterized = result["characterization"]["communities"][0]
    assert {"authenticity", "harmfulness", "orchestration", "time_variance"}.issubset(first_characterized)
    assert first_characterized["authenticity"]["label"] != ""
    assert first_characterized["harmfulness"]["severity"] in {"low", "medium", "high"}
    assert first_characterized["orchestration"]["orchestration_type"] in {"centralized", "decentralized", "emergent", "uncertain"}
    assert first_characterized["time_variance"]["temporal_archetype"] in {"stable", "bursty", "adaptive", "dormant"}
    assert result["discovery"]["deep_graph_model"]["encoder"] == "magnn"
    assert result["discovery"]["deep_graph_model"]["object_node_count"] > 0
    assert result["legacy_prototype"]["method"] == "dyna_colm_gnn_prototype"
    assert "without_relation_attention" in result["ablations"]
    assert "static_relation_weight" in result["ablations"]
    assert "no_community_features" in result["ablations"]
    assert result["comparison_rows"]
    assert (tmp_path / "detection_summary.json").exists()


def test_dyna_colm_detect_fusion_gnn_outputs_fusion_details_when_torch_is_available(tmp_path: Path):
    if importlib.util.find_spec("torch") is None:
        pytest.skip("torch is not installed in this environment")
    events = make_sample_events()
    result = run_dyna_colm_detect(
        events,
        output_dir=tmp_path,
        relations=("url_share", "hashtag_share", "retweet_target"),
        seed=42,
        discover_encoder="magnn",
        discover_epochs=1,
        embedding_dim=8,
        hidden_dim=8,
        device="cpu",
        lm_backend="tfidf",
        gnn_backend="fusion_gnn",
        split_mode="supervised",
    )

    assert result["detect_model"]["gnn_backend"] == "fusion_gnn"
    assert result["detect_model"]["uses_discover_outputs"] is True
    assert result["detect_model"]["uses_full_discover_embeddings"] is True
    assert result["detect_model"]["uses_discover_reweighted_edges"] is True
    assert result["detect_model"]["reweighted_edge_count"] > 0
    fusion = result["detect_model"]["fusion_details"]
    assert fusion["fusion_architecture"] == "discover_lm_graph_attention"
    assert set(fusion["branch_attention"]) == {"struct", "lm", "graph"}
    assert "relation_attention" in fusion
    assert "cross_attention_mean" in fusion
    assert result["metrics"]
    assert result["detect_model"]["evaluation_protocol"] == "heldout_test_only"


def test_dyna_colm_detect_gfm_lm_gnn_outputs_iohunter_style_details_when_torch_is_available(tmp_path: Path):
    if importlib.util.find_spec("torch") is None:
        pytest.skip("torch is not installed in this environment")
    events = make_sample_events()
    result = run_dyna_colm_detect(
        events,
        output_dir=tmp_path,
        relations=("url_share", "hashtag_share", "retweet_target"),
        seed=42,
        discover_encoder="magnn",
        discover_epochs=1,
        embedding_dim=8,
        hidden_dim=8,
        device="cpu",
        lm_backend="tfidf",
        gnn_backend="gfm_lm_gnn",
        detect_epochs=2,
        split_mode="supervised",
    )

    assert result["detect_model"]["gnn_backend"] == "gfm_lm_gnn"
    assert result["detect_model"]["detect_epochs"] == 2
    assert result["detect_model"]["classifier_backend"].startswith("gfm_lm_gnn_torch:")
    assert result["detect_model"]["uses_discover_outputs"] is True
    assert result["detect_model"]["uses_full_discover_embeddings"] is True
    assert result["detect_model"]["uses_discover_reweighted_edges"] is True
    assert result["detect_model"]["evaluation_protocol"] == "heldout_test_only"
    fusion = result["detect_model"]["fusion_details"]
    assert fusion["fusion_architecture"] == "iohunter_style_graph_foundation_lm_gnn"
    assert set(fusion["branch_attention"]) == {"discover", "lm", "graph"}
    assert fusion["pretraining_objectives"]["supervised_node_classification"] is True
    assert fusion["pretraining_objectives"]["edge_reconstruction_auxiliary"] is True
    assert fusion["pretraining_objectives"]["discover_lm_alignment_auxiliary"] is True
    assert fusion["edge_reconstruction_pair_count"] > 0
    assert "edge_reconstruction_metrics" in fusion
    assert result["metrics"]
    assert result["all_node_metrics"]


def test_dyna_colm_detect_cpu_light_gfm_lm_gnn_runs_full_feature_path(tmp_path: Path):
    events = make_sample_events()
    result = run_dyna_colm_detect(
        events,
        output_dir=tmp_path,
        relations=("url_share", "hashtag_share", "retweet_target"),
        seed=42,
        discover_encoder="magnn",
        discover_epochs=1,
        embedding_dim=8,
        hidden_dim=8,
        device="cpu",
        lm_backend="tfidf",
        gnn_backend="gfm_lm_gnn_cpu_light",
        detect_epochs=1,
        split_mode="supervised",
        lm_cache_dir=tmp_path / "lm_cache",
    )

    assert result["detect_model"]["gnn_backend"] == "gfm_lm_gnn_cpu_light"
    assert result["detect_model"]["uses_full_discover_embeddings"] is True
    assert result["detect_model"]["uses_discover_reweighted_edges"] is True
    assert result["detect_model"]["uses_lm_disk_cache"] is True
    fusion = result["detect_model"]["fusion_details"]
    assert fusion["fusion_architecture"] == "iohunter_style_cpu_light_fixed_graph_lm_gnn"
    assert fusion["pretraining_objectives"]["fixed_relation_graph_propagation"] is True
    assert result["metrics"]


def test_lm_feature_matrix_writes_and_reuses_disk_cache(tmp_path: Path):
    from app.core.coordination_baseline.io_reproduction import _lm_feature_matrix

    events = make_sample_events()
    nodes = ["u1", "u2", "u3", "u4"]
    first, source_first = _lm_feature_matrix(events, nodes, backend="tfidf", max_dim=4, cache_dir=tmp_path)
    second, source_second = _lm_feature_matrix(events, nodes, backend="tfidf", max_dim=4, cache_dir=tmp_path)

    assert source_first == "tfidf_object_bag_fallback"
    assert source_second == source_first
    assert np.allclose(first, second)
    assert list(tmp_path.glob("lm_features_tfidf_4_*.npz"))


def test_relation_gnn_graphs_use_discover_edge_scores_without_zeroing_missing_edges():
    graph = nx.Graph()
    graph.add_edge("u1", "u2", weight=4.0)
    graph.add_edge("u2", "u3", weight=5.0)
    discovery = {
        "deep_graph_model": {
            "observed_edge_scores": {
                "u1\tu2": 0.25,
            }
        }
    }

    graphs, changed = _apply_discover_edge_scores_to_relation_graphs({"url_share": graph}, discovery)

    assert changed == 1
    assert graphs["url_share"]["u1"]["u2"]["weight"] == pytest.approx(1.0)
    assert graphs["url_share"]["u1"]["u2"]["original_weight"] == pytest.approx(4.0)
    assert graphs["url_share"]["u1"]["u2"]["discover_edge_score"] == pytest.approx(0.25)
    assert graphs["url_share"]["u2"]["u3"]["weight"] == pytest.approx(5.0)
    assert graphs["url_share"]["u2"]["u3"]["discover_edge_score"] is None


def test_detect_batch_row_flattens_required_fields():
    summary = {
        "detect_model": {
            "discover_encoder": "magnn",
            "detect_epochs": 20,
            "split_mode": "supervised",
            "split_detail": "supervised",
            "gnn_backend": "relation_gnn",
            "lm_backend": "tfidf",
            "lm_feature_source": "tfidf_object_bag_fallback",
            "classifier_backend": "relation_gnn_torch:{}",
            "evaluation_protocol": "heldout_test_only",
            "feature_count": 12,
            "discover_feature_count": 20,
            "lm_feature_count": 8,
            "discover_embedding_dim": 8,
            "uses_full_discover_embeddings": True,
            "uses_discover_reweighted_edges": True,
            "reweighted_edge_count": 4,
            "edge_score_source": "magnn_edge_reconstruction",
            "train_count": 3,
            "test_count": 1,
        },
        "metrics": {
            "auc": 0.75,
            "auprc": 0.8,
            "macro_f1": 0.5,
            "precision_at_k": 1.0,
            "recall_at_k": 0.5,
            "accuracy": 0.5,
            "amdn_hage_style": {
                "ap": 0.8,
                "auc": 0.75,
                "f1_at_0_5": 0.5,
                "max_f1": 0.667,
                "macro_f1_at_0_5": 0.5,
            },
        },
    }

    row = _detect_batch_row_from_result("russia", 42, "run1", summary, 1.23, "out")

    assert row["discover_encoder"] == "magnn"
    assert row["lm_feature_source"] == "tfidf_object_bag_fallback"
    assert row["gnn_backend"] == "relation_gnn"
    assert row["evaluation_protocol"] == "heldout_test_only"
    assert row["uses_full_discover_embeddings"] is True
    assert row["uses_discover_reweighted_edges"] is True
    assert row["reweighted_edge_count"] == 4
    assert row["amdn_hage_ap"] == 0.8
    assert row["max_f1"] == 0.667
    assert row["diagnostic_f1_at_0_5"] == 0.5
    assert "diagnostic_macro_f1_at_0_5" not in row
    assert "amdn_hage_macro_f1_at_0_5" not in row
    assert row["runtime_seconds"] == 1.23


def test_detect_batch_row_supports_fusion_gnn_backend():
    summary = {
        "detect_model": {
            "discover_encoder": "magnn",
            "split_mode": "supervised",
            "split_detail": "supervised",
            "gnn_backend": "fusion_gnn",
            "lm_backend": "tfidf",
            "lm_feature_source": "tfidf_object_bag_fallback",
            "classifier_backend": "fusion_gnn_torch:{}",
            "evaluation_protocol": "heldout_test_only",
            "feature_count": 16,
            "discover_feature_count": 12,
            "lm_feature_count": 4,
            "discover_embedding_dim": 8,
            "uses_full_discover_embeddings": True,
            "uses_discover_reweighted_edges": True,
            "reweighted_edge_count": 5,
            "edge_score_source": "magnn_edge_reconstruction",
            "train_count": 3,
            "test_count": 1,
            "fusion_details": {
                "fusion_architecture": "discover_lm_graph_attention",
                "branch_attention": {"struct": 0.3, "lm": 0.2, "graph": 0.5},
            },
        },
        "metrics": {
            "auc": 0.7,
            "auprc": 0.75,
            "macro_f1": 0.55,
            "precision_at_k": 1.0,
            "recall_at_k": 0.5,
            "accuracy": 0.5,
            "amdn_hage_style": {
                "ap": 0.75,
                "auc": 0.7,
                "f1_at_0_5": 0.5,
                "max_f1": 0.67,
                "macro_f1_at_0_5": 0.5,
            },
        },
    }

    row = _detect_batch_row_from_result("iran", 7, "run2", summary, 2.0, "out")

    assert row["gnn_backend"] == "fusion_gnn"
    assert row["classifier_backend"] == "fusion_gnn_torch:{}"
    assert row["reweighted_edge_count"] == 5
    assert row["max_f1"] == 0.67


def test_detect_batch_row_supports_gfm_lm_gnn_backend():
    summary = {
        "detect_model": {
            "discover_encoder": "magnn",
            "split_mode": "supervised",
            "split_detail": "supervised",
            "gnn_backend": "gfm_lm_gnn",
            "lm_backend": "tfidf",
            "lm_feature_source": "tfidf_object_bag_fallback",
            "classifier_backend": "gfm_lm_gnn_torch:{}",
            "evaluation_protocol": "heldout_test_only",
            "feature_count": 20,
            "discover_feature_count": 14,
            "lm_feature_count": 6,
            "discover_embedding_dim": 8,
            "uses_full_discover_embeddings": True,
            "uses_discover_reweighted_edges": True,
            "reweighted_edge_count": 6,
            "edge_score_source": "magnn_edge_reconstruction",
            "train_count": 3,
            "test_count": 1,
            "fusion_details": {
                "fusion_architecture": "iohunter_style_graph_foundation_lm_gnn",
                "branch_attention": {"discover": 0.35, "lm": 0.2, "graph": 0.45},
                "pretraining_objectives": {"edge_reconstruction_auxiliary": True},
            },
        },
        "metrics": {
            "auc": 0.8,
            "auprc": 0.82,
            "macro_f1": 0.6,
            "precision_at_k": 1.0,
            "recall_at_k": 0.5,
            "accuracy": 0.5,
            "amdn_hage_style": {
                "ap": 0.82,
                "auc": 0.8,
                "f1_at_0_5": 0.6,
                "max_f1": 0.7,
                "macro_f1_at_0_5": 0.6,
            },
        },
    }

    row = _detect_batch_row_from_result("china", 9, "run3", summary, 3.0, "out")

    assert row["gnn_backend"] == "gfm_lm_gnn"
    assert row["classifier_backend"] == "gfm_lm_gnn_torch:{}"
    assert row["reweighted_edge_count"] == 6
    assert row["max_f1"] == 0.7


def test_detect_batch_prefers_precomputed_discovery_root(tmp_path: Path):
    events = make_sample_events()
    precomputed_root = tmp_path / "discover"
    summary_path = precomputed_root / "toy" / "seed_42" / "magnn" / "discovery_summary.json"
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary = run_dyna_colm_discover(
        events.drop(columns=["label"]),
        relations=("url_share", "hashtag_share", "retweet_target"),
        seed=42,
        encoder="magnn",
    )
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    args = Namespace(
        precomputed_discovery_root=str(precomputed_root),
        resume=False,
        relations=("url_share", "hashtag_share", "retweet_target"),
        discover_epochs=2,
        detect_epochs=20,
        embedding_dim=16,
        hidden_dim=16,
        device="cpu",
    )

    loaded = _detect_batch_load_or_run_discovery(events, tmp_path / "detect", "toy", 42, "magnn", args)

    assert loaded["deep_graph_model"]["encoder"] == "magnn"
    assert loaded["nodes"]


def test_dyna_colm_detect_cross_io_split_uses_group_column_when_available():
    if importlib.util.find_spec("torch") is None:
        pytest.skip("torch is not installed in this environment")
    first = make_sample_events()
    first["campaign"] = "a"
    second = make_sample_events()
    second["campaign"] = "b"
    second["account_id"] = second["account_id"].map(lambda value: f"{value}_b")
    events = pd.concat([first, second], ignore_index=True)

    result = run_dyna_colm_detect(
        events,
        relations=("url_share", "hashtag_share", "retweet_target"),
        seed=1,
        discover_encoder="magnn",
        discover_epochs=1,
        embedding_dim=8,
        hidden_dim=8,
        device="cpu",
        lm_backend="tfidf",
        gnn_backend="classifier",
        split_mode="cross_io",
    )

    assert result["detect_model"]["split_mode"] == "cross_io"
    assert result["detect_model"]["split_detail"].startswith("cross_io:campaign:")
    assert result["detect_model"]["uses_lm_features"] is True


def test_dyna_colm_ablation_suite_includes_required_variants():
    events = make_sample_events()
    result = run_dyna_colm_ablation_suite(events, relations=("url_share", "hashtag_share", "retweet_target"), seed=42)

    assert set(result) == {
        "full",
        "without_lm",
        "without_gnn",
        "without_direction_time",
        "without_relation_attention",
        "static_relation_weight",
        "no_community_features",
    }
    assert result["without_relation_attention"]["uses_relation_attention"] is False
    assert result["static_relation_weight"]["relation_attention_mode"] == "static"
    assert result["no_community_features"]["uses_community_features"] is False


def test_legacy_setting_function_aliases_forward_to_functional_names():
    events = make_sample_events()
    discovery = run_dyna_colm_discover(events.drop(columns=["label"]), relations=("url_share",), seed=42, encoder="lightweight")
    detection = run_setting_b_detection(events, relations=("url_share", "hashtag_share", "retweet_target"), seed=42)
    ablations = run_setting_ablation_suite(events, relations=("url_share",), seed=42)

    assert discovery["setting"] == "discover"
    assert detection["setting"] == "detect"
    assert detection["detect_model"]["gnn_backend"] == "gfm_lm_gnn"
    assert "full" in ablations


def test_dynamic_relation_graph_preserves_direction_and_time_delta():
    events = make_sample_events()
    graphs = build_dynamic_relation_graphs(events, relations=("url_share", "retweet_target"))
    fused = fuse_directed_graphs(graphs)
    summary = dynamic_graph_summary(fused)

    assert graphs["url_share"].has_edge("u1", "u2")
    assert graphs["url_share"]["u1"]["u2"]["time_deltas"][0] == 1.0
    assert fused.has_edge("u1", "u2")
    assert summary["edge_count"] > 0
    assert summary["top_objects"]


def test_dynamic_edge_records_tolerate_target_only_accounts():
    graph = nx.DiGraph()
    graph.add_edge(
        "u1",
        "target_only",
        weight=2.0,
        count=1,
        relations=["retweet_target"],
        objects=["target_only"],
        time_deltas=[1.0],
    )

    records = _dynamic_edge_records_from_graph(graph, {"u1": 0.8})

    assert records
    assert records[0]["source"] == "u1"
    assert records[0]["target"] == "target_only"
    assert records[0]["edge_score"] > 0


def test_legacy_gnn_prototype_tolerates_target_only_accounts():
    events = make_sample_events()
    events.loc[events["relation"] == "retweet_target", "target_account_id"] = "target_only"

    result = run_dyna_colm_gnn_prototype(
        events,
        relations=("url_share", "hashtag_share", "retweet_target"),
        seed=42,
        variant="target_only_smoke",
    )

    assert result["dynamic_edges"]
    assert any(edge["target"] == "target_only" for edge in result["dynamic_edges"])


def test_run_reproduction_suite_writes_summary(tmp_path: Path):
    events = make_sample_events()
    summary = run_reproduction_suite(
        events,
        output_dir=tmp_path,
        relations=("url_share", "hashtag_share", "retweet_target"),
    )

    assert {"unmasking", "leveraging_llms", "ours", "ours_ablations", "manifest", "exports"}.issubset(summary)
    rows = flatten_reproduction_metrics(summary)
    assert any(row["family"] == "ours" for row in rows)
    assert any(row["method"].endswith(":without_lm") for row in rows)
    assert (tmp_path / "summary.json").exists()
    assert (tmp_path / "manifest.json").exists()
    assert (tmp_path / "metrics.csv").exists()
    assert (tmp_path / "comparison_table.json").exists()


def test_normalize_event_table_canonicalizes_numeric_account_ids():
    events = normalize_event_table(
        pd.DataFrame(
            [
                {"account_id": 1.0, "relation": "mention_target", "object_id": "obj", "target_account_id": 2.0},
                {"account_id": "3.0", "relation": "url_share", "object_id": "https://example.test/a"},
            ]
        )
    )

    assert events.loc[0, "account_id"] == "1"
    assert events.loc[0, "target_account_id"] == "2"
    assert events.loc[1, "account_id"] == "3"
    assert events.loc[1, "object_id"] == "https://example.test/a"


def test_iohunter_processed_dataset_can_be_converted_and_run(tmp_path: Path):
    graph = nx.Graph()
    graph.add_edge(0, 1, weight=0.9)
    graph.add_edge(2, 3, weight=0.4)
    co_url = nx.Graph()
    co_url.add_edge(0, 1, weight=1.0)
    co_rt = nx.Graph()
    co_rt.add_edge(0, 1, weight=0.8)
    hash_seq = nx.Graph()
    hash_seq.add_edge(2, 3, weight=0.7)
    dataset = {
        "graph": graph,
        "coURL": co_url,
        "coRT": co_rt,
        "hashSeq": hash_seq,
        "fastRT": nx.Graph(),
        "tweetSim": nx.Graph(),
        "labels": np.array([1, 1, 0, 0]),
        "splits": {},
    }

    events = iohunter_processed_to_event_table(dataset, dataset_name="toy")
    summary = run_reproduction_suite(events, output_dir=tmp_path / "suite", relations=("url_share", "retweet_target", "hashtag_share"))

    assert set(events["relation"]).issuperset({"profile", "url_share", "retweet_target", "hashtag_share"})
    assert events["account_id"].nunique() == 4
    assert events.groupby("account_id")["label"].max().sum() == 2
    assert summary["manifest"]["account_count"] == 4
    assert summary["ours"]["dynamic_graph_summary"]["edge_count"] > 0


def test_iohunter_lightweight_batch_runs_multiple_processed_datasets(tmp_path: Path):
    processed_root = tmp_path / "processed"
    for dataset_name, positive_labels in {"russia": [1, 1, 0, 0], "cuba": [1, 0, 1, 0]}.items():
        dataset_dir = processed_root / dataset_name
        dataset_dir.mkdir(parents=True)
        co_url = nx.Graph()
        co_url.add_edge(0, 1, weight=1.0)
        co_rt = nx.Graph()
        co_rt.add_edge(2, 3, weight=0.8)
        dataset = {
            "graph": nx.compose(co_url, co_rt),
            "coURL": co_url,
            "coRT": co_rt,
            "hashSeq": nx.Graph(),
            "fastRT": nx.Graph(),
            "tweetSim": nx.Graph(),
            "labels": np.array(positive_labels),
            "splits": {},
        }
        with (dataset_dir / "0.7_datasets.pkl").open("wb") as file_handle:
            pickle.dump(dataset, file_handle)

    result = run_iohunter_lightweight_batch(
        processed_root,
        output_dir=tmp_path / "batch",
        datasets=("russia", "cuba"),
        max_edges_per_relation=5,
        seed=7,
    )

    assert result["dataset_count"] == 2
    assert result["failed"] == 0
    assert set(result["datasets"]) == {"russia", "cuba"}
    assert all(Path(item["metrics_csv"]).exists() for item in result["datasets"].values())
    assert Path(result["report"]["csv"]).exists()
    assert any(row["dataset"] == "russia" for row in result["report"]["rows"])
    russia_summary = json.loads((tmp_path / "batch" / "russia" / "summary.json").read_text(encoding="utf-8"))
    assert russia_summary["manifest"]["include_text_similarity"] is False
    assert "text_similarity" not in russia_summary["unmasking"]["graph_summaries"]


def test_iohunter_lightweight_batch_can_include_temporal_edge_candidate(tmp_path: Path):
    processed_root = tmp_path / "processed"
    dataset_dir = processed_root / "russia"
    dataset_dir.mkdir(parents=True)
    co_url = nx.Graph()
    co_url.add_edge(0, 1, weight=1.0)
    co_rt = nx.Graph()
    co_rt.add_edge(1, 2, weight=0.8)
    dataset = {
        "graph": nx.compose(co_url, co_rt),
        "coURL": co_url,
        "coRT": co_rt,
        "hashSeq": nx.Graph(),
        "fastRT": nx.Graph(),
        "tweetSim": nx.Graph(),
        "labels": np.array([1, 0, 1]),
        "splits": {},
    }
    with (dataset_dir / "0.7_datasets.pkl").open("wb") as file_handle:
        pickle.dump(dataset, file_handle)

    result = run_iohunter_lightweight_batch(
        processed_root,
        output_dir=tmp_path / "batch",
        datasets=("russia",),
        max_edges_per_relation=5,
        seed=7,
        include_temporal_edge_candidate=True,
        candidate_epochs=1,
        candidate_seeds=(7,),
        include_temporal_edge_ablations=True,
        candidate_ablation_seeds=(7,),
    )

    dataset_result = result["datasets"]["russia"]
    candidate_result = dataset_result["research_candidate"]

    assert result["failed"] == 0
    assert Path(candidate_result["summary_json"]).exists()
    assert Path(candidate_result["metrics_csv"]).exists()
    assert candidate_result["evaluation_mode"] == "multi_seed"
    assert candidate_result["ablation_status"] == "ok"
    assert any(
        row["source"] == "research_candidate_offline_iohunter" and row["dataset"] == "russia"
        for row in result["report"]["rows"]
    )


def test_iohunter_batch_can_run_research_candidate_only(tmp_path: Path):
    processed_root = tmp_path / "processed"
    dataset_dir = processed_root / "russia"
    dataset_dir.mkdir(parents=True)
    graph = nx.Graph()
    graph.add_edges_from([(0, 1), (1, 2), (2, 3), (3, 0)])
    dataset = {
        "graph": graph,
        "coURL": graph,
        "coRT": nx.Graph(),
        "hashSeq": nx.Graph(),
        "fastRT": nx.Graph(),
        "tweetSim": nx.Graph(),
        "labels": np.array([1, 0, 1, 0]),
        "splits": {},
    }
    with (dataset_dir / "0.7_datasets.pkl").open("wb") as file_handle:
        pickle.dump(dataset, file_handle)

    result = run_iohunter_lightweight_batch(
        processed_root,
        output_dir=tmp_path / "batch",
        datasets=("russia",),
        seed=7,
        include_temporal_edge_candidate=True,
        research_candidate_only=True,
    )

    dataset_result = result["datasets"]["russia"]
    assert result["research_candidate_only"] is True
    assert result["failed"] == 0
    assert not (Path(dataset_result["output_dir"]) / "metrics.csv").exists()
    assert Path(dataset_result["research_candidate"]["metrics_csv"]).exists()
    assert all(row["source"] == "research_candidate_offline_iohunter" for row in result["report"]["rows"])


def test_coordination_discover_comparison_report_merges_lightweight_and_official_metrics(tmp_path: Path):
    lightweight_dir = tmp_path / "lightweight"
    lightweight_dir.mkdir()
    (lightweight_dir / "metrics.csv").write_text(
        "setting,family,method,scope,precision,recall,f1,auc,support,positive_count,notes\n"
        "detect,ours,dyna_colm_gnn_prototype:full,user,0.8,0.7,0.746667,0.9,10,4,numpy\n",
        encoding="utf-8",
    )
    (lightweight_dir / "summary.json").write_text(
        '{"iohunter_conversion":{"dataset":"russia","row_count":20,"account_count":10}}',
        encoding="utf-8",
    )
    official_dir = tmp_path / "official"
    official_dir.mkdir()
    (official_dir / "iohunter_metric_summary.csv").write_text(
        "family,method,setting,dataset,gnn,undersampling,split,metric,run_count,mean,std\n"
        "iohunter,MultiModalGNN_CrossAttention,supervised,russia,sage,,TEST,f1_macro,2,0.61,0.02\n"
        "iohunter,MultiModalGNN_CrossAttention,supervised,russia,sage,,TEST,accuracy,2,0.72,0.03\n",
        encoding="utf-8",
    )

    report = build_coordination_discover_comparison_report(
        output_dir=tmp_path / "report",
        lightweight_dirs=(lightweight_dir,),
        iohunter_summary_dirs=(official_dir,),
    )

    assert report["row_count"] == 2
    assert Path(report["csv"]).exists()
    assert Path(report["json"]).exists()
    assert Path(report["markdown"]).exists()
    assert any(row["method"] == "dyna_colm_gnn_prototype:full" and row["primary_metric"] == 0.746667 for row in report["rows"])
    assert any(row["method"] == "MultiModalGNN_CrossAttention" and row["macro_f1"] == 0.61 for row in report["rows"])


def test_coordination_discover_comparison_report_merges_research_candidate_metrics(tmp_path: Path):
    lightweight_dir = tmp_path / "lightweight"
    lightweight_dir.mkdir()
    (lightweight_dir / "metrics.csv").write_text(
        "setting,family,method,scope,precision,recall,f1,auc,support,positive_count,notes\n"
        "detect,ours,dyna_colm_gnn_prototype:full,user,0.8,0.7,0.746667,0.9,10,4,numpy\n",
        encoding="utf-8",
    )
    (lightweight_dir / "summary.json").write_text(
        '{"iohunter_conversion":{"dataset":"russia","row_count":20,"account_count":10}}',
        encoding="utf-8",
    )
    official_dir = tmp_path / "official"
    official_dir.mkdir()
    (official_dir / "iohunter_metric_summary.csv").write_text(
        "family,method,setting,dataset,gnn,undersampling,split,metric,run_count,mean,std\n"
        "iohunter,MultiModalGNN_CrossAttention,supervised,russia,sage,,TEST,f1_macro,2,0.61,0.02\n"
        "iohunter,MultiModalGNN_CrossAttention,supervised,russia,sage,,TEST,accuracy,2,0.72,0.03\n",
        encoding="utf-8",
    )
    candidate_dir = tmp_path / "candidate"
    candidate_dir.mkdir()
    (candidate_dir / "temporal_edge_candidate_metrics.csv").write_text(
        "source,setting,family,method,dataset,scope,split,run_count,edge_max_f1,edge_roc_auc,edge_auprc,edge_ece,system_baseline_edge_auprc,observed_edge_upper_bound_auprc,degree_time_prior_edge_auprc,candidate_beats_system_baseline,claim_blocked_reason,primary_metric_name,evaluation_type,label_provenance,time_provenance,notes\n"
        "research_candidate_offline_iohunter,discover_candidate_eval,research,temporal_history_edge_mlp_v2,russia,account_pair,TEST,1,0.640000,0.730000,0.710000,0.120000,0.330000,1.000000,0.280000,true,,edge_auprc,self_supervised_proxy,observed_edges_plus_matched_negatives,processed_graph_edge_order_proxy,research_candidate_non_claimable;objective=direct_account_pair_coordination\n",
        encoding="utf-8",
    )

    report = build_coordination_discover_comparison_report(
        output_dir=tmp_path / "report",
        lightweight_dirs=(lightweight_dir,),
        iohunter_summary_dirs=(official_dir,),
        research_candidate_dirs=(candidate_dir,),
    )

    assert report["row_count"] == 3
    candidate_row = next(row for row in report["rows"] if row["source"] == "research_candidate_offline_iohunter")
    assert candidate_row["macro_f1"] is None
    assert candidate_row["auc"] is None
    assert candidate_row["edge_max_f1"] == 0.64
    assert candidate_row["edge_roc_auc"] == 0.73
    assert candidate_row["edge_auprc"] == 0.71
    assert candidate_row["edge_ece"] == 0.12
    assert candidate_row["system_baseline_edge_auprc"] == 0.33
    assert candidate_row["observed_edge_upper_bound_auprc"] == 1.0
    assert candidate_row["degree_time_prior_edge_auprc"] == 0.28
    assert candidate_row["candidate_beats_system_baseline"] is True
    assert candidate_row["claim_blocked_reason"] == ""
    assert candidate_row["evaluation_type"] == "self_supervised_proxy"


def test_write_iohunter_event_table_from_pickle(tmp_path: Path):
    dataset_dir = tmp_path / "russia"
    dataset_dir.mkdir()
    graph = nx.Graph()
    graph.add_edge(0, 1, weight=0.5)
    dataset = {
        "graph": graph,
        "coURL": graph,
        "coRT": nx.Graph(),
        "hashSeq": nx.Graph(),
        "fastRT": nx.Graph(),
        "tweetSim": nx.Graph(),
        "labels": np.array([1, 0]),
        "splits": {},
    }
    with (dataset_dir / "0.7_datasets.pkl").open("wb") as file_handle:
        pickle.dump(dataset, file_handle)

    result = write_iohunter_event_table(dataset_dir, tmp_path / "events.csv")

    assert result["row_count"] > 2
    assert (tmp_path / "events.csv").exists()


def test_iohunter_command_generation_and_data_inspection(tmp_path: Path):
    commands = build_iohunter_commands(
        tmp_path,
        datasets=("russia",),
        seeds=(42,),
        gnns=("sage", "gcn"),
        learning_rates=(1e-2,),
    )
    inspection = inspect_iohunter_data(tmp_path)

    assert len(commands) == 2
    assert "--dataset russia" in commands[0]
    assert "run_MultiModalGNN_CrossAttention.py" in commands[0]
    assert "SocGFM\\src" in commands[0] or "SocGFM/src" in commands[0]
    assert inspection["datasets"]["russia"]["exists"] is False


def test_iohunter_run_plan_uses_src_cwd_and_exports_commands(tmp_path: Path):
    workspace = tmp_path / "iohunter"
    script_dir = workspace / "SocGFM" / "src"
    script_dir.mkdir(parents=True)
    (script_dir / "run_MultiModalGNN_CrossAttention.py").write_text("", encoding="utf-8")
    (script_dir / "run_NodePruning.py").write_text("", encoding="utf-8")
    (script_dir / "run_Node2Vec.py").write_text("", encoding="utf-8")

    run_plan = build_iohunter_run_plan(
        workspace,
        datasets=("russia",),
        seeds=(7,),
        gnns=("sage",),
        learning_rates=(1e-2,),
        epochs=2,
        check=1,
        latent=32,
        embed_type="positional_degree",
        undersampling=(None, "0.9"),
        include_official_baselines=True,
    )
    exports = write_iohunter_run_exports(workspace, tmp_path / "exports", run_plan=run_plan)

    assert len(run_plan) == 4
    assert run_plan[0]["cwd"].endswith("SocGFM\\src") or run_plan[0]["cwd"].endswith("SocGFM/src")
    assert "--epochs" in run_plan[0]["args"]
    assert "--check" in run_plan[0]["args"]
    assert "--latent" in run_plan[0]["args"]
    assert "--embed_type" in run_plan[0]["args"]
    assert run_plan[1]["setting"] == "scarce_supervised"
    assert "--under" in run_plan[1]["args"]
    assert any(item["method"] == "NodePruning" for item in run_plan)
    node2vec_item = next(item for item in run_plan if item["method"] == "Node2Vec")
    assert "--epochs" in node2vec_item["args"]
    assert "--check" in node2vec_item["args"]
    assert "--latent" in node2vec_item["args"]
    assert Path(exports["run_plan_json"]).exists()
    assert Path(exports["powershell"]).read_text(encoding="utf-8").count("run_MultiModalGNN_CrossAttention.py") == 2
    assert "cd " in Path(exports["shell"]).read_text(encoding="utf-8")


def test_iohunter_run_plan_can_include_cross_country(tmp_path: Path):
    workspace = tmp_path / "iohunter"
    script_dir = workspace / "SocGFM" / "src"
    script_dir.mkdir(parents=True)
    (script_dir / "run_MultiModalGNN_CrossAttention.py").write_text("", encoding="utf-8")
    (script_dir / "run_MultiModalGNN_CrossAttention_CrossCountryPlusFineTuning.py").write_text("", encoding="utf-8")

    run_plan = build_iohunter_run_plan(
        workspace,
        datasets=("russia",),
        seeds=(42,),
        gnns=("sage",),
        include_primary=False,
        include_official_baselines=False,
        include_cross_country=True,
    )

    assert len(run_plan) == 1
    assert run_plan[0]["setting"] == "cross_io_finetuning"
    assert run_plan[0]["method"] == "MultiModalGNN_CrossAttention_CrossCountryPlusFineTuning"


def test_iohunter_workspace_status_reports_missing_data(tmp_path: Path):
    script_dir = tmp_path / "SocGFM" / "src"
    script_dir.mkdir(parents=True)
    status = iohunter_workspace_status(tmp_path)

    assert status["ready_for_official_run"] is False
    assert status["repository_ready"] is True
    assert status["data_ready"] is False
    assert "environment" in status


def test_iohunter_environment_can_probe_explicit_python():
    status = inspect_iohunter_environment("python")

    assert status["python_executable"] == "python"
    assert "python_packages" in status
    assert "ready_for_official_run" in status


def test_iohunter_official_data_layout_can_be_linked(tmp_path: Path):
    workspace_data = tmp_path / "data" / "processed" / "russia"
    workspace_data.mkdir(parents=True)
    (workspace_data / "0.7_datasets.pkl").write_text("x", encoding="utf-8")
    (workspace_data / "sbert_nodeattributes_mostPop5.pt").write_text("x", encoding="utf-8")
    (tmp_path / "SocGFM" / "src").mkdir(parents=True)

    layout = ensure_iohunter_official_data_layout(tmp_path)
    status = iohunter_workspace_status(tmp_path)

    assert layout["ready"] is True
    assert (tmp_path / "SocGFM" / "data" / "processed" / "russia" / "0.7_datasets.pkl").exists()
    assert status["data"]["official_data_layout_ready"] is True


def test_iohunter_official_script_patch_is_idempotent(tmp_path: Path):
    script_dir = tmp_path / "SocGFM" / "src"
    script_dir.mkdir(parents=True)
    (script_dir / "run_NodePruning.py").write_text(
        "def main():\n"
        "    save_metrics(val_logger, interim_data_dir, 'VAL')\n"
        "    save_metrics(test_logger, interim_data_dir, 'TEST')\n",
        encoding="utf-8",
    )
    (script_dir / "run_Node2Vec.py").write_text(
        "import os\nimport torch\n"
        "def main():\n"
        "        num_workers = 4\n"
        "        loader = model.loader(batch_size=128, shuffle=True, num_workers=num_workers)\n"
        "    save_metrics(val_logger, interim_data_dir, 'VAL')\n"
        "    save_metrics(test_logger, interim_data_dir, 'TEST')\n",
        encoding="utf-8",
    )

    first = patch_iohunter_official_scripts(tmp_path)
    second = patch_iohunter_official_scripts(tmp_path)
    node2vec_text = (script_dir / "run_Node2Vec.py").read_text(encoding="utf-8")

    assert first["ready"] is True
    assert second["ready"] is True
    assert "return interim_data_dir" in (script_dir / "run_NodePruning.py").read_text(encoding="utf-8")
    assert 'sys.platform.startswith("win")' in node2vec_text
    assert node2vec_text.count("import sys") == 1


def test_zip_validation_rejects_non_zip(tmp_path: Path):
    fake_zip = tmp_path / "data.zip"
    fake_zip.write_text("not a zip", encoding="utf-8")

    assert _is_valid_zip(fake_zip) is False


def test_iohunter_dry_run_and_log_summary(tmp_path: Path):
    workspace = tmp_path / "iohunter"
    script_dir = workspace / "SocGFM" / "src"
    script_dir.mkdir(parents=True)
    (script_dir / "run_MultiModalGNN_CrossAttention.py").write_text("", encoding="utf-8")
    run_plan = build_iohunter_run_plan(workspace, datasets=("russia",), seeds=(42,), gnns=("sage",))
    export_paths = write_iohunter_run_exports(workspace, tmp_path / "plan", run_plan=run_plan)
    loaded_plan = load_iohunter_run_plan(Path(export_paths["run_plan_json"]))
    manifest = run_iohunter_plan(loaded_plan, output_dir=tmp_path / "runs", dry_run=True, limit=1)
    record = manifest["records"][0]
    stdout_log = Path(record["stdout_log"])
    stdout_log.parent.mkdir(parents=True, exist_ok=True)
    stdout_log.write_text("[TEST] f1_macro: 0.73+-0.02\n[TEST] precision: 0.8+-0.1\n", encoding="utf-8")
    summary = summarize_iohunter_runs(tmp_path / "runs")

    assert manifest["dry_run"] is True
    assert manifest["records"][0]["status"] == "dry_run"
    assert stdout_log.exists()
    assert Path(record["stderr_log"]).exists()
    assert summary["metric_count"] == 2
    assert Path(summary["metrics_csv"]).exists()
    assert Path(summary["summary_csv"]).exists()
    assert any(row["metric"] == "f1_macro" and row["mean"] == 0.73 for row in summary["rows"])
    assert any(row["metric"] == "f1_macro" and row["run_count"] == 1 for row in summary["summary_rows"])


def test_iohunter_runner_resumes_successful_runs(tmp_path: Path):
    workspace = tmp_path / "iohunter"
    script_dir = workspace / "SocGFM" / "src"
    script_dir.mkdir(parents=True)
    script = script_dir / "run_MultiModalGNN_CrossAttention.py"
    script.write_text("print('[TEST] f1_macro: 0.9+-0.0')\n", encoding="utf-8")
    run_plan = build_iohunter_run_plan(workspace, datasets=("russia",), seeds=(42,), gnns=("sage",))

    first = run_iohunter_plan(run_plan, output_dir=tmp_path / "runs", python_executable="python", limit=1)
    second = run_iohunter_plan(run_plan, output_dir=tmp_path / "runs", python_executable="python", limit=1)

    assert first["records"][0]["status"] == "passed"
    assert second["records"][0]["status"] == "skipped_existing_success"


def test_iohunter_runner_accepts_official_cleanup_failure_after_metrics(tmp_path: Path):
    workspace = tmp_path / "iohunter"
    script_dir = workspace / "SocGFM" / "src"
    script_dir.mkdir(parents=True)
    script = script_dir / "run_NodePruning.py"
    script.write_text(
        "import sys\n"
        "print('[TEST] f1_macro: 0.88+-0.0')\n"
        "print('shutil.rmtree(exp_dir, ignore_errors=True)', file=sys.stderr)\n"
        "print('TypeError: lstat: path should be string, bytes or os.PathLike, not NoneType', file=sys.stderr)\n"
        "sys.exit(1)\n",
        encoding="utf-8",
    )
    run_plan = [
        {
            "family": "iohunter_official_baseline",
            "method": "NodePruning",
            "setting": "supervised",
            "dataset": "russia",
            "seed": 42,
            "cwd": str(script_dir),
            "script": str(script),
            "args": [],
        }
    ]

    manifest = run_iohunter_plan(run_plan, output_dir=tmp_path / "runs", python_executable="python", stop_on_error=True)

    assert manifest["failed"] == 0
    assert manifest["records"][0]["status"] == "passed_with_cleanup_warning"


def test_iohunter_log_metric_parser():
    rows = parse_iohunter_log_metrics("\ufeff[VAL] f1_macro: 0.5+-0.1\n[TEST] roc_auc: nan+-None\n")

    assert rows[0] == {"split": "VAL", "metric": "f1_macro", "mean": 0.5, "std": 0.1}
    assert rows[1]["mean"] is None
    assert rows[1]["std"] is None


def test_cli_parse_run_command(monkeypatch):
    monkeypatch.setattr(
        "sys.argv",
        [
            "run_io_reproduction_suite.py",
            "run",
            "--events",
            "events.csv",
            "--output-dir",
            "out",
            "--relations",
            *DEFAULT_RELATIONS,
            "--seed",
            "7",
        ],
    )

    args = parse_args()
    assert args.command == "run"
    assert args.seed == 7
    assert tuple(args.relations) == DEFAULT_RELATIONS


def test_cli_parse_discover_detect_ablation_commands(monkeypatch):
    monkeypatch.setattr(
        "sys.argv",
        [
            "run_io_reproduction_suite.py",
            "detect",
            "--events",
            "events.csv",
            "--output-dir",
            "out",
            "--relations",
            "url_share",
            "retweet_target",
            "--seed",
            "9",
            "--discover-encoder",
            "magnn_legacy",
            "--discover-epochs",
            "2",
            "--detect-epochs",
            "3",
            "--embedding-dim",
            "8",
            "--hidden-dim",
            "8",
            "--device",
            "cpu",
            "--lm-backend",
            "tfidf",
            "--gnn-backend",
            "fusion_gnn",
            "--split-mode",
            "scarce_supervised",
        ],
    )

    args = parse_args()

    assert args.command == "detect"
    assert args.seed == 9
    assert tuple(args.relations) == ("url_share", "retweet_target")
    assert args.discover_encoder == "magnn_legacy"
    assert args.discover_epochs == 2
    assert args.detect_epochs == 3
    assert args.embedding_dim == 8
    assert args.hidden_dim == 8
    assert args.device == "cpu"
    assert args.lm_backend == "tfidf"
    assert args.gnn_backend == "fusion_gnn"
    assert args.split_mode == "scarce_supervised"

    monkeypatch.setattr(
        "sys.argv",
        [
            "run_io_reproduction_suite.py",
            "detect",
            "--events",
            "events.csv",
            "--output-dir",
            "out",
        ],
    )
    args = parse_args()
    assert args.command == "detect"
    assert args.discover_encoder == "magnn_legacy"
    assert args.gnn_backend == "gfm_lm_gnn"
    assert args.detect_epochs == 0

    monkeypatch.setattr(
        "sys.argv",
        [
            "run_io_reproduction_suite.py",
            "discover",
            "--events",
            "events.csv",
            "--output-dir",
            "out",
            "--encoder",
            "magnn_legacy",
            "--epochs",
            "2",
            "--embedding-dim",
            "8",
            "--hidden-dim",
            "8",
            "--lr",
            "0.01",
            "--negative-ratio",
            "2.0",
            "--device",
            "cpu",
            "--community-algorithm",
            "louvain",
        ],
    )

    args = parse_args()
    assert args.command == "discover"
    assert args.encoder == "magnn_legacy"
    assert args.epochs == 2
    assert args.embedding_dim == 8
    assert args.hidden_dim == 8
    assert args.lr == 0.01
    assert args.negative_ratio == 2.0
    assert args.device == "cpu"
    assert args.community_algorithm == "louvain"
    assert args.structure_filter == "none"
    assert args.structure_filter_metric == "eigenvector"
    assert args.structure_filter_percentile == 90.0
    assert args.structure_filter_use_weights is False
    assert tuple(args.relations) == DEFAULT_RELATIONS

    monkeypatch.setattr(
        "sys.argv",
        [
            "run_io_reproduction_suite.py",
            "discover",
            "--events",
            "events.csv",
            "--output-dir",
            "out",
            "--structure-filter",
            "node_pruning",
            "--structure-filter-metric",
            "pagerank",
            "--structure-filter-percentile",
            "85",
            "--structure-filter-use-weights",
        ],
    )

    args = parse_args()
    assert args.command == "discover"
    assert args.encoder == "magnn_legacy"
    assert args.community_algorithm == "leiden"
    assert args.structure_filter == "node_pruning"
    assert args.structure_filter_metric == "pagerank"
    assert args.structure_filter_percentile == 85.0
    assert args.structure_filter_use_weights is True
    # The parser keeps deprecated flags for backward compatibility, but the
    # Discover implementation ignores them and stays on the stable full-graph path.

    monkeypatch.setattr(
        "sys.argv",
        [
            "run_io_reproduction_suite.py",
            "iohunter-lightweight-batch",
            "--processed-root",
            "processed",
            "--output-dir",
            "out",
            "--include-temporal-edge-candidate",
            "--candidate-epochs",
            "40",
            "--candidate-embedding-dim",
            "32",
            "--candidate-hidden-dim",
            "64",
            "--candidate-lr",
            "0.005",
            "--candidate-negative-ratio",
            "2",
            "--candidate-seeds",
            "42",
            "43",
            "--include-temporal-edge-ablations",
            "--candidate-ablation-seeds",
            "42",
        ],
    )

    args = parse_args()
    assert args.command == "iohunter-lightweight-batch"
    assert args.include_temporal_edge_candidate is True
    assert args.candidate_epochs == 40
    assert args.candidate_embedding_dim == 32
    assert args.candidate_hidden_dim == 64
    assert args.candidate_lr == 0.005
    assert args.candidate_negative_ratio == 2
    assert tuple(args.candidate_seeds) == (42, 43)
    assert args.include_temporal_edge_ablations is True
    assert tuple(args.candidate_ablation_seeds) == (42,)

    monkeypatch.setattr(
        "sys.argv",
        [
            "run_io_reproduction_suite.py",
            "ablation",
            "--events",
            "events.csv",
            "--output-dir",
            "out",
        ],
    )

    args = parse_args()
    assert args.command == "ablation"
    assert tuple(args.relations) == DEFAULT_RELATIONS

    monkeypatch.setattr(
        "sys.argv",
        [
            "run_io_reproduction_suite.py",
            "characterize",
            "--events",
            "events.csv",
            "--output-dir",
            "out",
            "--seed",
            "11",
        ],
    )
    args = parse_args()
    assert args.command == "characterize"
    assert args.seed == 11
    assert tuple(args.relations) == DEFAULT_RELATIONS


def test_run_dyna_colm_characterize_outputs_four_dimension_profiles(tmp_path: Path):
    events = make_sample_events()
    characterization = run_dyna_colm_characterize(
        events,
        output_dir=tmp_path,
        relations=("url_share", "hashtag_share", "retweet_target"),
        seed=42,
    )

    assert characterization["task"] == "coordination_characterization"
    assert characterization["summary"]["community_count"] >= 1
    assert characterization["summary"]["dimension_support"]["orchestration"] is True
    assert characterization["summary"]["dimension_support"]["time_variance"] is True
    community = characterization["communities"][0]
    assert community["authenticity"]["inauthenticity_type"]
    assert "evidence_channels" in community["authenticity"]["evidence"]
    assert community["harmfulness"]["harm_type"] in {"misinformation", "influence_operation", "harassment", "propaganda", "general_harm"}
    assert "target_group" in community["harmfulness"]["evidence"]
    assert "control_concentration" in community["orchestration"]["evidence"]
    assert "phase_transitions" in community["time_variance"]["evidence"]
    assert (tmp_path / "characterization_summary.json").exists()


def test_discover_encoder_comparison_winner_uses_discover_metrics_only():
    rows = [
        {"encoder": "lightweight", "modularity": 0.9, "mean_object_concentration": 0.5, "reconstruction_auc": None},
        {"encoder": "han", "modularity": 0.91, "mean_object_concentration": 0.6, "reconstruction_auc": 0.8},
    ]

    result = _winner(rows)

    assert result["conclusion"] == "best_discover_score"
    assert result["encoder"] == "han"


def test_discover_stability_batch_writes_aggregate_files(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(
        stability_batch,
        "load_iohunter_processed_dataset",
        lambda path: {"dataset": str(path)},
    )
    monkeypatch.setattr(
        stability_batch,
        "iohunter_processed_to_event_table",
        lambda dataset, dataset_name, max_edges_per_relation: make_sample_events(),
    )

    def fake_stability(events, output_dir, **kwargs):
        output_dir.mkdir(parents=True, exist_ok=True)
        return {
            "windows": [
                {
                    "window_size_seconds": 4.0,
                    "window_index": 0,
                    "event_count": 4,
                    "modularity": 0.5,
                    "conductance": 0.1,
                    "mean_object_concentration": 0.8,
                    "community_algorithm_effective": "leiden",
                }
            ],
            "pairwise_stability": [
                {
                    "comparison_type": "multiscale_same_index",
                    "left_window_size_seconds": 4.0,
                    "right_window_size_seconds": 8.0,
                    "nmi": 1.0,
                    "ari": 1.0,
                    "jaccard": 1.0,
                    "common_node_count": 4,
                }
            ],
            "summary": {
                "window_count": 1,
                "pairwise_count": 1,
                "mean_modularity": 0.5,
                "mean_adjacent_jaccard": None,
            },
        }

    monkeypatch.setattr(stability_batch, "run_discover_stability_analysis", fake_stability)
    monkeypatch.setattr(
        "sys.argv",
        [
            "run_discover_stability_batch.py",
            "--processed-root",
            str(tmp_path / "processed"),
            "--output-dir",
            str(tmp_path / "out"),
            "--datasets",
            "russia",
            "--encoder",
            "lightweight",
            "--window-sizes",
            "4",
            "8",
        ],
    )

    stability_batch.main()

    assert (tmp_path / "out" / "discover_stability_windows.csv").exists()
    assert (tmp_path / "out" / "discover_stability_pairwise.csv").exists()
    assert (tmp_path / "out" / "discover_stability_summary.csv").exists()
    manifest = json.loads((tmp_path / "out" / "stability_batch_manifest.json").read_text(encoding="utf-8"))
    assert manifest["encoder"] == "lightweight"
    assert manifest["community_algorithm"] == "leiden"


def test_discover_encoder_comparison_row_excludes_detection_metrics():
    summary = run_dyna_colm_discover(
        make_sample_events(),
        relations=("url_share", "hashtag_share", "retweet_target"),
        seed=42,
        encoder="lightweight",
    )

    row = _summary_row("toy", 42, "lightweight", summary, 0.1)

    assert "label_auc" not in row
    assert "label_auprc" not in row
    assert "label_f1" not in row
    assert "cluster_purity" not in row
    assert {"modularity", "conductance", "relation_entropy", "runtime_seconds"}.issubset(row)
