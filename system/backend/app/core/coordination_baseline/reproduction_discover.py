"""Compatibility facade for focused Coordination Discover modules."""

from __future__ import annotations

from app.core.coordination_baseline.reproduction_features import (
    _account_display_name_map,
    _bag_feature_matrix,
    _base_discover_feature_matrix,
    _centrality_feature_matrix,
    _community_evidence,
    _community_records_from_graph,
    _directed_feature_matrix,
    _edge_key_text,
    _embedding_row,
    _graph_with_deep_edge_scores,
    _interaction_text,
    _label_free_events,
    _lm_feature_matrix,
    _message_pass,
    _metadata_text,
    _reduce_feature_dim,
    _relation_attention,
    _relation_degree_features,
    _serialize_observed_edge_scores,
    _user_content,
    _write_jsonl,
    generate_llm_prompt_records,
    run_lightweight_llm_baselines,
    run_unmasking_reproduction,
)

from app.core.coordination_baseline.reproduction_deep_discover import (
    _community_avg_time_delta,
    _counter_entropy,
    _deep_discover_summary,
    _deep_graph_model_summary,
    _discover_attention_mode,
    _discover_edge_score_lookup,
    _discover_embedding_dim,
    _discover_encoder_governance,
    _discover_node_feature_table,
    _discovery_metrics,
    _dynamic_edge_records_from_graph,
    _edge_records_from_graph,
    _evidence_summary,
    _final_training_loss,
    _prediction_rows,
    run_dyna_colm_gnn_ablations,
    run_dyna_colm_gnn_prototype,
)

from app.core.coordination_baseline.reproduction_discover_runtime import (
    _adjacent_window_stability,
    _adjusted_rand_index,
    _adjusted_rand_index_fallback,
    _assignment_pair_jaccard,
    _cluster_assignment,
    _co_cluster_pairs,
    _community_assignment_stability,
    _mean_optional,
    _multiscale_stability,
    _normalized_mutual_info,
    _normalized_mutual_info_fallback,
    _safe_window_name,
    _stability_summary,
    _stability_window_row,
    _write_dict_rows,
    run_discover_ablation_suite,
    run_discover_stability_analysis,
    run_dyna_colm_discover,
    run_zeyan_coexpression_discover,
    run_zeyan_coexpression_summary,
)

from app.core.coordination_baseline.reproduction_detect_models import (
    _build_relation_adjacency_tensors,
    _community_scores,
    _comparison_rows_for_detect,
    _cpu_light_gfm_lm_gnn_scores,
    _detect_discovery_snapshot,
    _fit_transductive_scores,
    _fit_transductive_scores_with_split,
    _prediction_rows_from_discover_features,
    _sample_relation_edge_pairs,
    _split_detect_feature_groups,
    _torch_fusion_gnn_scores,
    _torch_gfm_lm_gnn_scores,
    _torch_relation_gnn_scores,
)

from app.core.coordination_baseline.reproduction_detect_adapter import (
    _apply_discover_edge_scores_to_relation_graphs,
    prepare_dyna_colm_detect_inputs,
)

__all__ = [
    "generate_llm_prompt_records",
    "prepare_dyna_colm_detect_inputs",
    "run_discover_ablation_suite",
    "run_discover_stability_analysis",
    "run_dyna_colm_discover",
    "run_dyna_colm_gnn_ablations",
    "run_dyna_colm_gnn_prototype",
    "run_lightweight_llm_baselines",
    "run_unmasking_reproduction",
    "run_zeyan_coexpression_discover",
    "run_zeyan_coexpression_summary",
]
