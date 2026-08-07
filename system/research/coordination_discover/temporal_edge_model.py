from __future__ import annotations
import math
import random
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass, field, replace
from typing import Any

from .contracts import EvidenceGraph

_MODEL_BACKEND = "temporal_history_edge_mlp_v2"
_MISSING_HISTORY_SECONDS = 30 * 24 * 3600.0


@dataclass(slots=True)
class TemporalEdgeModelConfig:
    embedding_dim: int = 16
    hidden_dim: int = 32
    epochs: int = 8
    learning_rate: float = 0.01
    weight_decay: float = 0.0
    negative_ratio: int = 2
    validation_ratio: float = 0.2
    test_ratio: float = 0.2
    seed: int = 1729
    device: str = "cpu"
    max_negatives_per_positive: int = 4
    time_bucket_seconds: int = 3600
    early_stop_patience: int = 3
    prediction_export_limit: int = 5000
    history_time_cap_seconds: float = _MISSING_HISTORY_SECONDS
    refit_on_train_validation: bool = False
    ensemble_validation_tolerance: float = 0.02
    disabled_feature_names: tuple[str, ...] = ()
    score_ensemble_mode: str = "adaptive"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class TemporalEdgeSplit:
    split_policy: str
    train: list[dict[str, Any]]
    validation: list[dict[str, Any]]
    test: list[dict[str, Any]]
    leakage_checks: dict[str, int] = field(default_factory=dict)
    cutoffs: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "split_policy": self.split_policy,
            "train": list(self.train),
            "validation": list(self.validation),
            "test": list(self.test),
            "leakage_checks": dict(self.leakage_checks),
            "cutoffs": dict(self.cutoffs),
        }


def split_temporal_account_edges(
    graph: EvidenceGraph,
    config: TemporalEdgeModelConfig | None = None,
) -> TemporalEdgeSplit:
    config = config or TemporalEdgeModelConfig()
    rows = _sorted_account_edge_rows(graph)
    if not rows:
        return TemporalEdgeSplit(
            split_policy="chronological_event_time",
            train=[],
            validation=[],
            test=[],
            leakage_checks={"future_edges_in_train": 0, "overlapping_edge_keys": 0},
            cutoffs={},
        )

    train_count, validation_count, test_count = _split_counts(
        len(rows),
        validation_ratio=float(config.validation_ratio),
        test_ratio=float(config.test_ratio),
    )
    train = rows[:train_count]
    validation = rows[train_count : train_count + validation_count]
    test = rows[train_count + validation_count : train_count + validation_count + test_count]

    leakage_checks = _leakage_checks(train=train, validation=validation, test=test)
    cutoffs = {
        "train_end_at": _safe_min([row["observed_at"] for row in validation]) if validation else None,
        "validation_end_at": _safe_min([row["observed_at"] for row in test]) if test else None,
        "test_start_at": _safe_min([row["observed_at"] for row in test]) if test else None,
    }
    return TemporalEdgeSplit(
        split_policy="chronological_event_time",
        train=train,
        validation=validation,
        test=test,
        leakage_checks=leakage_checks,
        cutoffs=cutoffs,
    )


def build_matched_hard_negatives(
    graph: EvidenceGraph,
    positive_rows: list[dict[str, Any]],
    config: TemporalEdgeModelConfig | None = None,
    *,
    degree_map: dict[str, int] | None = None,
    observed_rows: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    config = config or TemporalEdgeModelConfig()
    if not positive_rows:
        return []

    observed_source = observed_rows if observed_rows is not None else [
        _edge_to_row(edge) for edge in graph.account_edges
    ]
    observed_pairs = {
        (
            str(row.get("source_account_id") or ""),
            str(row.get("target_account_id") or ""),
        )
        for row in observed_source
        if row.get("source_account_id") and row.get("target_account_id")
    }
    accounts = sorted(
        {
            str(account)
            for account in [
                *graph.accounts,
                *[row.get("source_account_id") for row in positive_rows],
                *[row.get("target_account_id") for row in positive_rows],
            ]
            if account not in (None, "")
        }
    )
    if len(accounts) < 2:
        return []

    degree_map = dict(degree_map or _degree_map(positive_rows))
    negatives: list[dict[str, Any]] = []
    used_candidates: set[tuple[str, str]] = set()
    max_per_positive = max(1, int(config.negative_ratio))
    degree_buckets = _degree_buckets(accounts, degree_map)
    degree_cache: dict[tuple[int, int, int], list[str]] = {}

    for index, positive in enumerate(positive_rows):
        relation_type = str(positive.get("relation_type") or positive.get("evidence_kind") or "unknown")
        platform = str(positive.get("platform") or "unknown")
        positive_pair = (
            str(positive.get("source_account_id") or ""),
            str(positive.get("target_account_id") or ""),
        )
        source_degree = int(positive.get("source_degree") or degree_map.get(str(positive.get("source_account_id") or ""), 0))
        target_degree = int(positive.get("target_degree") or degree_map.get(str(positive.get("target_account_id") or ""), 0))
        observed_at = float(positive.get("observed_at") or 0.0)
        time_delta_seconds = float(positive.get("time_delta_seconds") or config.time_bucket_seconds)
        support_count = int(positive.get("support_count") or max(1, len(positive.get("evidence_objects") or [])))
        observed_pairs_for_row = set(observed_pairs)
        observed_pairs_for_row.update(
            (
                str(row.get("source_account_id") or ""),
                str(row.get("target_account_id") or ""),
            )
            for row in positive_rows[: index + 1]
            if row.get("source_account_id") and row.get("target_account_id")
        )
        observed_pairs_for_row.add(positive_pair)

        ranked_candidates = _rank_candidate_pairs(
            accounts=accounts,
            observed_pairs=observed_pairs_for_row,
            degree_buckets=degree_buckets,
            degree_cache=degree_cache,
            source_degree=source_degree,
            target_degree=target_degree,
            degree_map=degree_map,
            seed=int(config.seed),
            positive_index=index,
            limit=max_per_positive * 8 + 16,
        )
        if not ranked_candidates:
            continue

        emitted = 0
        for candidate_source, candidate_target in ranked_candidates:
            if emitted >= max_per_positive:
                break
            candidate_key = (candidate_source, candidate_target)
            if candidate_key in used_candidates:
                continue
            used_candidates.add(candidate_key)
            negatives.append(
                {
                    "source_account_id": candidate_source,
                    "target_account_id": candidate_target,
                    "evidence_kind": positive.get("evidence_kind") or "coordination_negative",
                    "relation_type": relation_type,
                    "platform": platform,
                    "observed_at": observed_at,
                    "time_delta_seconds": time_delta_seconds,
                    "support_count": support_count,
                    "source_degree": degree_map.get(candidate_source, 0),
                    "target_degree": degree_map.get(candidate_target, 0),
                    "degree_gap": abs(degree_map.get(candidate_source, 0) - degree_map.get(candidate_target, 0)),
                    "observed_rank": float(positive.get("observed_rank") or 0.0),
                    "weight": 0.0,
                    "label": 0,
                    "score": 0.0,
                    "sampling_strategy": "relation_platform_time_degree_matched",
                    "matched_positive_index": index,
                }
            )
            emitted += 1
        if emitted < max_per_positive:
            for candidate_source, candidate_target in ranked_candidates:
                if emitted >= max_per_positive:
                    break
                negatives.append(
                    {
                        "source_account_id": candidate_source,
                        "target_account_id": candidate_target,
                        "evidence_kind": positive.get("evidence_kind") or "coordination_negative",
                        "relation_type": relation_type,
                        "platform": platform,
                        "observed_at": observed_at,
                        "time_delta_seconds": time_delta_seconds,
                        "support_count": support_count,
                        "source_degree": degree_map.get(candidate_source, 0),
                        "target_degree": degree_map.get(candidate_target, 0),
                        "degree_gap": abs(degree_map.get(candidate_source, 0) - degree_map.get(candidate_target, 0)),
                        "observed_rank": float(positive.get("observed_rank") or 0.0),
                        "weight": 0.0,
                        "label": 0,
                        "score": 0.0,
                        "sampling_strategy": "relation_platform_time_degree_matched",
                        "matched_positive_index": index,
                    }
                )
                emitted += 1
        observed_pairs = set(observed_pairs_for_row)

    return negatives


def fit_temporal_edge_model(
    graph: EvidenceGraph,
    config: TemporalEdgeModelConfig | None = None,
) -> dict[str, Any]:
    config = config or TemporalEdgeModelConfig()
    feature_names = _active_numeric_feature_names(config)
    if len(graph.accounts) < 2 or len(graph.account_edges) < 3:
        return _empty_result(status="data_insufficient", config=config, split=None)

    split = split_temporal_account_edges(graph, config)
    if not split.train or not split.validation or not split.test:
        return _empty_result(status="data_insufficient", config=config, split=split)

    degree_map = _degree_map(split.train)
    train_pos = _augment_rows(split.train, label=1, degree_map=degree_map)
    validation_pos = _augment_rows(split.validation, label=1, degree_map=degree_map)
    test_pos = _augment_rows(split.test, label=1, degree_map=degree_map)
    train_neg = build_matched_hard_negatives(
        graph,
        split.train,
        config,
        degree_map=degree_map,
        observed_rows=split.train,
    )
    validation_neg = build_matched_hard_negatives(
        graph,
        split.validation,
        config,
        degree_map=degree_map,
        observed_rows=split.train,
    )
    test_neg = build_matched_hard_negatives(
        graph,
        split.test,
        config,
        degree_map=degree_map,
        observed_rows=split.train,
    )

    train_examples = _attach_temporal_history_features(
        _combine_examples(train_pos, train_neg),
        initial_positive_rows=[],
        update_within_split=True,
        missing_time_since_seconds=float(config.history_time_cap_seconds),
    )
    validation_examples = _attach_temporal_history_features(
        _combine_examples(validation_pos, validation_neg),
        initial_positive_rows=split.train,
        update_within_split=False,
        missing_time_since_seconds=float(config.history_time_cap_seconds),
    )
    test_examples = _attach_temporal_history_features(
        _combine_examples(test_pos, test_neg),
        initial_positive_rows=split.train,
        update_within_split=False,
        missing_time_since_seconds=float(config.history_time_cap_seconds),
    )
    examples_by_split = {
        "train": train_examples,
        "validation": validation_examples,
        "test": test_examples,
    }
    baselines = _baseline_metrics_by_split(examples_by_split)

    account_vocab = _fit_vocab(train_examples, ("source_account_id", "target_account_id"))
    relation_vocab = _fit_vocab(train_examples, ("relation_type",))
    platform_vocab = _fit_vocab(train_examples, ("platform",))
    numeric_stats = _fit_numeric_stats(train_examples, feature_names=feature_names)
    diagnostics = _fit_diagnostics(
        examples_by_split,
        account_vocab=account_vocab,
        relation_vocab=relation_vocab,
        platform_vocab=platform_vocab,
    )

    torch = _torch_optional()
    if torch is None:
        train_scores = _heuristic_scores(train_examples, numeric_stats=numeric_stats, relation_vocab=relation_vocab, feature_names=feature_names)
        validation_scores = _heuristic_scores(validation_examples, numeric_stats=numeric_stats, relation_vocab=relation_vocab, feature_names=feature_names)
        test_scores = _heuristic_scores(test_examples, numeric_stats=numeric_stats, relation_vocab=relation_vocab, feature_names=feature_names)
        metrics = {
            "train": _classification_metrics(train_examples, train_scores),
            "validation": _classification_metrics(validation_examples, validation_scores),
            "test": _classification_metrics(test_examples, test_scores),
        }
        return {
            "status": "ok",
            "model_backend": _MODEL_BACKEND,
            "candidate_role": "research_candidate_non_claimable",
            "objective": "direct_account_pair_coordination",
            "protocol": _protocol(
                split,
                config,
                time_provenance=graph.representation_inputs.get("timestamp_policy"),
            ),
            "metrics": metrics,
            "baselines": baselines,
            "claim_gate": _claim_gate(metrics, baselines),
            "diagnostics": diagnostics,
            "training": {
                "epochs_requested": int(config.epochs),
                "epochs_run": 0,
                "best_epoch": 0,
                "feature_fit_policy": "train_examples_only",
            },
            "model_summary": {
                "mode": "heuristic_fallback",
                "reason": "torch_unavailable",
                "input_feature_names": list(feature_names),
            },
        }

    try:
        return _fit_with_torch(
            torch=torch,
            graph=graph,
            config=config,
            split=split,
            train_examples=train_examples,
            validation_examples=validation_examples,
            test_examples=test_examples,
            account_vocab=account_vocab,
            relation_vocab=relation_vocab,
            platform_vocab=platform_vocab,
            numeric_stats=numeric_stats,
            feature_names=feature_names,
            baselines=baselines,
            diagnostics=diagnostics,
        )
    except RuntimeError as exc:
        return _empty_result(status="model_unavailable", config=config, split=split, error=str(exc))


def fit_temporal_edge_model_multi_seed(
    graph: EvidenceGraph,
    config: TemporalEdgeModelConfig | None = None,
    *,
    seeds: tuple[int, ...] | list[int] = (42, 43, 44, 45, 46),
) -> dict[str, Any]:
    config = config or TemporalEdgeModelConfig()
    seed_values = tuple(int(seed) for seed in seeds) or (int(config.seed),)
    seed_results: list[dict[str, Any]] = []
    for seed in seed_values:
        run_config = replace(config, seed=seed)
        result = fit_temporal_edge_model(graph, run_config)
        seed_results.append(_compact_seed_result(result, seed=seed))

    ok_results = [result for result in seed_results if result.get("status") == "ok"]
    aggregate = _aggregate_seed_results(ok_results)
    return {
        "status": "ok" if ok_results else "all_failed",
        "model_backend": _MODEL_BACKEND,
        "candidate_role": "research_candidate_non_claimable",
        "objective": "direct_account_pair_coordination",
        "evaluation_mode": "multi_seed",
        "seed_count": len(seed_values),
        "seeds": list(seed_values),
        "config": config.to_dict(),
        "aggregate": aggregate,
        "seed_results": seed_results,
    }


def run_temporal_edge_ablation_suite(
    graph: EvidenceGraph,
    config: TemporalEdgeModelConfig | None = None,
    *,
    seeds: tuple[int, ...] | list[int] = (42, 43, 44, 45, 46),
) -> dict[str, Any]:
    config = config or TemporalEdgeModelConfig()
    variants = []
    for variant in _temporal_edge_ablation_configs(config):
        result = fit_temporal_edge_model_multi_seed(
            graph,
            variant["config"],
            seeds=tuple(int(seed) for seed in seeds),
        )
        variants.append(
            {
                "variant": variant["variant"],
                "what_it_tests": variant["what_it_tests"],
                "expected_if_component_matters": variant["expected_if_component_matters"],
                "priority": variant["priority"],
                "config": variant["config"].to_dict(),
                "status": result["status"],
                "seed_count": result["seed_count"],
                "aggregate": result["aggregate"],
                "seed_results": result["seed_results"],
            }
        )
    return {
        "status": "ok" if any(row["status"] == "ok" for row in variants) else "all_failed",
        "model_backend": _MODEL_BACKEND,
        "candidate_role": "research_candidate_non_claimable",
        "objective": "direct_account_pair_coordination",
        "evaluation_mode": "ablation_suite",
        "seeds": [int(seed) for seed in seeds],
        "variants": variants,
    }


def _compact_seed_result(result: dict[str, Any], *, seed: int) -> dict[str, Any]:
    return {
        "seed": int(seed),
        "status": result.get("status"),
        "metrics": result.get("metrics", {}),
        "raw_model_metrics": result.get("raw_model_metrics", {}),
        "baselines": result.get("baselines", {}),
        "claim_gate": result.get("claim_gate", {}),
        "training": result.get("training", {}),
        "model_summary": {
            key: value
            for key, value in dict(result.get("model_summary") or {}).items()
            if key
            not in {
                "account_vocab",
                "relation_vocab",
                "platform_vocab",
            }
        },
        "diagnostics": result.get("diagnostics", {}),
        "error": result.get("error"),
    }


def _aggregate_seed_results(seed_results: list[dict[str, Any]]) -> dict[str, Any]:
    metric_names = ("roc_auc", "auprc", "max_f1", "ece")
    aggregate: dict[str, Any] = {
        split_name: {
            metric_name: _metric_summary(
                [
                    float(result.get("metrics", {}).get(split_name, {}).get(metric_name))
                    for result in seed_results
                    if _is_number(result.get("metrics", {}).get(split_name, {}).get(metric_name))
                ]
            )
            for metric_name in metric_names
        }
        for split_name in ("train", "validation", "test")
    }
    aggregate["baselines"] = _aggregate_baselines(seed_results, metric_names=metric_names)
    aggregate["claim_gate"] = _aggregate_claim_gate(seed_results)
    return aggregate


def _aggregate_baselines(
    seed_results: list[dict[str, Any]],
    *,
    metric_names: tuple[str, ...],
) -> dict[str, Any]:
    baseline_names = sorted(
        {
            str(name)
            for result in seed_results
            for name in dict(result.get("baselines") or {}).keys()
        }
    )
    return {
        baseline_name: {
            split_name: {
                metric_name: _metric_summary(
                    [
                        float(
                            result.get("baselines", {})
                            .get(baseline_name, {})
                            .get(split_name, {})
                            .get(metric_name)
                        )
                        for result in seed_results
                        if _is_number(
                            result.get("baselines", {})
                            .get(baseline_name, {})
                            .get(split_name, {})
                            .get(metric_name)
                        )
                    ]
                )
                for metric_name in metric_names
            }
            for split_name in ("train", "validation", "test")
        }
        for baseline_name in baseline_names
    }


def _aggregate_claim_gate(seed_results: list[dict[str, Any]]) -> dict[str, Any]:
    win_fields = {
        "win_rate_vs_system_future_edge_prior": "candidate_beats_system_baseline",
        "win_rate_vs_strongest_fair_baseline": "candidate_beats_strongest_fair_baseline",
        "win_rate_vs_degree_time_prior": "candidate_beats_degree_time_prior",
    }
    output: dict[str, Any] = {
        key: _rate(
            bool(result.get("claim_gate", {}).get(source_field))
            for result in seed_results
            if source_field in dict(result.get("claim_gate") or {})
        )
        for key, source_field in win_fields.items()
    }
    output["candidate_test_edge_auprc"] = _metric_summary(
        [
            float(result.get("claim_gate", {}).get("candidate_test_edge_auprc"))
            for result in seed_results
            if _is_number(result.get("claim_gate", {}).get("candidate_test_edge_auprc"))
        ]
    )
    output["strongest_fair_baseline_test_edge_auprc"] = _metric_summary(
        [
            float(result.get("claim_gate", {}).get("strongest_fair_baseline_test_edge_auprc"))
            for result in seed_results
            if _is_number(result.get("claim_gate", {}).get("strongest_fair_baseline_test_edge_auprc"))
        ]
    )
    strongest_names = [
        str(result.get("claim_gate", {}).get("strongest_fair_baseline"))
        for result in seed_results
        if result.get("claim_gate", {}).get("strongest_fair_baseline")
    ]
    output["strongest_fair_baseline"] = (
        Counter(strongest_names).most_common(1)[0][0] if strongest_names else None
    )
    output["blocked_seed_count"] = sum(
        1
        for result in seed_results
        if result.get("claim_gate", {}).get("blocked_reason")
    )
    return output


def _metric_summary(values: list[float]) -> dict[str, Any]:
    clean_values = [round(float(value), 6) for value in values if _is_number(value)]
    if not clean_values:
        return {"mean": None, "std": None, "values": []}
    mean = sum(clean_values) / len(clean_values)
    variance = sum((value - mean) ** 2 for value in clean_values) / len(clean_values)
    return {
        "mean": round(mean, 6),
        "std": round(math.sqrt(variance), 6),
        "values": clean_values,
    }


def _rate(values: Any) -> float | None:
    value_list = [bool(value) for value in values]
    if not value_list:
        return None
    return round(sum(1 for value in value_list if value) / len(value_list), 6)


def _is_number(value: Any) -> bool:
    try:
        return value is not None and math.isfinite(float(value))
    except (TypeError, ValueError):
        return False


def _temporal_edge_ablation_configs(config: TemporalEdgeModelConfig) -> list[dict[str, Any]]:
    return [
        {
            "variant": "full",
            "what_it_tests": "complete learned residual plus validation-selected system prior ensemble",
            "expected_if_component_matters": "best or near-best edge AUPRC across seeds",
            "priority": 1,
            "config": replace(config),
        },
        {
            "variant": "learned_only",
            "what_it_tests": "whether the learned temporal edge model is useful without external score ensembling",
            "expected_if_component_matters": "lower than full but competitive with fair priors",
            "priority": 1,
            "config": replace(config, score_ensemble_mode="learned_only"),
        },
        {
            "variant": "no_system_prior_feature",
            "what_it_tests": "whether the model is only learning the engineered system prior shortcut",
            "expected_if_component_matters": "performance should not collapse if embeddings and temporal history add signal",
            "priority": 1,
            "config": replace(
                config,
                disabled_feature_names=_merge_disabled_features(config, ("system_future_edge_prior_score",)),
                score_ensemble_mode="learned_only",
            ),
        },
        {
            "variant": "no_exact_pair_history",
            "what_it_tests": "contribution of exact pair recurrence versus general temporal/degree memory",
            "expected_if_component_matters": "repeat-heavy datasets should drop most",
            "priority": 1,
            "config": replace(
                config,
                disabled_feature_names=_merge_disabled_features(
                    config,
                    (
                        "log_history_pair_count",
                        "log_history_reverse_pair_count",
                        "log_history_pair_weight_sum",
                        "log_time_since_pair_seconds",
                    ),
                ),
                score_ensemble_mode="learned_only",
            ),
        },
        {
            "variant": "no_relation_memory",
            "what_it_tests": "contribution of relation-conditioned temporal memory",
            "expected_if_component_matters": "multi-relation campaigns should show a measurable drop",
            "priority": 1,
            "config": replace(
                config,
                disabled_feature_names=_merge_disabled_features(
                    config,
                    (
                        "log_history_source_relation_degree",
                        "log_history_target_relation_degree",
                        "log_history_relation_count",
                        "log_time_since_source_relation_seconds",
                        "log_time_since_target_relation_seconds",
                    ),
                ),
                score_ensemble_mode="learned_only",
            ),
        },
    ]


def _merge_disabled_features(config: TemporalEdgeModelConfig, names: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(dict.fromkeys([*config.disabled_feature_names, *names]))


def _fit_with_torch(
    *,
    torch: Any,
    graph: EvidenceGraph,
    config: TemporalEdgeModelConfig,
    split: TemporalEdgeSplit,
    train_examples: list[dict[str, Any]],
    validation_examples: list[dict[str, Any]],
    test_examples: list[dict[str, Any]],
    account_vocab: dict[str, int],
    relation_vocab: dict[str, int],
    platform_vocab: dict[str, int],
    numeric_stats: dict[str, tuple[float, float]],
    feature_names: tuple[str, ...],
    baselines: dict[str, dict[str, dict[str, Any]]],
    diagnostics: dict[str, Any],
) -> dict[str, Any]:
    random.seed(int(config.seed))
    torch.manual_seed(int(config.seed))
    device = _resolve_device(torch, config.device)

    model = _TemporalEdgeScorer(
        torch=torch,
        account_count=max(1, len(account_vocab)),
        relation_count=max(1, len(relation_vocab)),
        platform_count=max(1, len(platform_vocab)),
        embedding_dim=max(4, int(config.embedding_dim)),
        hidden_dim=max(8, int(config.hidden_dim)),
        numeric_dim=len(feature_names),
    ).to(device)

    optimizer = torch.optim.AdamW(
        model.parameters(),
        lr=float(config.learning_rate),
        weight_decay=float(config.weight_decay),
    )

    train_tensors = _tensorize_examples(
        torch=torch,
        examples=train_examples,
        account_vocab=account_vocab,
        relation_vocab=relation_vocab,
        platform_vocab=platform_vocab,
        numeric_stats=numeric_stats,
        feature_names=feature_names,
        device=device,
    )
    validation_tensors = _tensorize_examples(
        torch=torch,
        examples=validation_examples,
        account_vocab=account_vocab,
        relation_vocab=relation_vocab,
        platform_vocab=platform_vocab,
        numeric_stats=numeric_stats,
        feature_names=feature_names,
        device=device,
    )
    test_tensors = _tensorize_examples(
        torch=torch,
        examples=test_examples,
        account_vocab=account_vocab,
        relation_vocab=relation_vocab,
        platform_vocab=platform_vocab,
        numeric_stats=numeric_stats,
        feature_names=feature_names,
        device=device,
    )

    best_state = None
    best_validation_score = float("-inf")
    best_epoch = 0
    epochs_since_improvement = 0
    train_history: list[float] = []

    for epoch in range(max(1, int(config.epochs))):
        model.train()
        optimizer.zero_grad()
        logits = model(**train_tensors.inputs)
        loss = _weighted_bce_loss(torch, logits, train_tensors.labels, device=device)
        loss.backward()
        optimizer.step()
        train_history.append(round(float(loss.detach().cpu().item()), 6))

        model.eval()
        with torch.no_grad():
            validation_probs = torch.sigmoid(model(**validation_tensors.inputs)).detach().cpu().tolist()
        validation_metrics = _classification_metrics(validation_examples, validation_probs)
        validation_score = float(validation_metrics.get("auprc", 0.0))
        if validation_score > best_validation_score:
            best_validation_score = validation_score
            best_epoch = epoch + 1
            best_state = {key: value.detach().cpu().clone() for key, value in model.state_dict().items()}
            epochs_since_improvement = 0
        else:
            epochs_since_improvement += 1
            if config.early_stop_patience and epochs_since_improvement >= int(config.early_stop_patience):
                break

    if best_state is not None:
        model.load_state_dict(best_state)

    test_model = model
    refit_history: list[float] = []
    if bool(config.refit_on_train_validation):
        test_model = _TemporalEdgeScorer(
            torch=torch,
            account_count=max(1, len(account_vocab)),
            relation_count=max(1, len(relation_vocab)),
            platform_count=max(1, len(platform_vocab)),
            embedding_dim=max(4, int(config.embedding_dim)),
            hidden_dim=max(8, int(config.hidden_dim)),
            numeric_dim=len(feature_names),
        ).to(device)
        refit_optimizer = torch.optim.AdamW(
            test_model.parameters(),
            lr=float(config.learning_rate),
            weight_decay=float(config.weight_decay),
        )
        refit_tensors = _tensorize_examples(
            torch=torch,
            examples=train_examples + validation_examples,
            account_vocab=account_vocab,
            relation_vocab=relation_vocab,
            platform_vocab=platform_vocab,
            numeric_stats=numeric_stats,
            feature_names=feature_names,
            device=device,
        )
        for _ in range(max(1, int(best_epoch or len(train_history) or config.epochs))):
            test_model.train()
            refit_optimizer.zero_grad()
            refit_logits = test_model(**refit_tensors.inputs)
            refit_loss = _weighted_bce_loss(torch, refit_logits, refit_tensors.labels, device=device)
            refit_loss.backward()
            refit_optimizer.step()
            refit_history.append(round(float(refit_loss.detach().cpu().item()), 6))

    model.eval()
    test_model.eval()
    with torch.no_grad():
        train_probs = torch.sigmoid(model(**train_tensors.inputs)).detach().cpu().tolist()
        validation_probs = torch.sigmoid(model(**validation_tensors.inputs)).detach().cpu().tolist()
        test_probs = torch.sigmoid(test_model(**test_tensors.inputs)).detach().cpu().tolist()

    prior_scores = {
        "train": _system_future_edge_prior_scores(train_examples),
        "validation": _system_future_edge_prior_scores(validation_examples),
        "test": _system_future_edge_prior_scores(test_examples),
    }
    model_scores = {
        "train": train_probs,
        "validation": validation_probs,
        "test": test_probs,
    }
    ensemble = _select_score_ensemble(
        validation_examples=validation_examples,
        validation_model_scores=validation_probs,
        validation_prior_scores=prior_scores["validation"],
        validation_tolerance=float(config.ensemble_validation_tolerance),
        mode=str(config.score_ensemble_mode),
    )
    final_scores = {
        split_name: _apply_score_ensemble(
            model_scores=scores,
            prior_scores=prior_scores[split_name],
            ensemble=ensemble,
        )
        for split_name, scores in model_scores.items()
    }
    raw_model_metrics = {
        "train": _classification_metrics(train_examples, train_probs),
        "validation": _classification_metrics(validation_examples, validation_probs),
        "test": _classification_metrics(test_examples, test_probs),
    }
    metrics = {
        "train": _classification_metrics(train_examples, final_scores["train"]),
        "validation": _classification_metrics(validation_examples, final_scores["validation"]),
        "test": _classification_metrics(test_examples, final_scores["test"]),
    }

    return {
        "status": "ok",
            "model_backend": _MODEL_BACKEND,
        "candidate_role": "research_candidate_non_claimable",
        "objective": "direct_account_pair_coordination",
        "protocol": _protocol(
            split,
            config,
            time_provenance=graph.representation_inputs.get("timestamp_policy"),
        ),
        "metrics": metrics,
        "raw_model_metrics": raw_model_metrics,
        "baselines": baselines,
        "claim_gate": _claim_gate(metrics, baselines),
        "diagnostics": diagnostics,
        "training": {
            "epochs_requested": int(config.epochs),
            "epochs_run": len(train_history),
            "best_epoch": best_epoch,
            "feature_fit_policy": "train_examples_only",
            "split_policy": split.split_policy,
            "test_refit_policy": "train_plus_validation_examples_no_test" if bool(config.refit_on_train_validation) else "disabled_train_only_holdout",
        },
        "model_summary": {
            "device": device,
            "embedding_dim": int(config.embedding_dim),
            "hidden_dim": int(config.hidden_dim),
            "account_vocab_size": len(account_vocab),
            "relation_vocab_size": len(relation_vocab),
            "platform_vocab_size": len(platform_vocab),
            "input_feature_names": list(feature_names),
            "disabled_feature_names": list(config.disabled_feature_names),
            "score_strategy": "validation_selected_system_prior_residual_ensemble",
            "ensemble": ensemble,
            "test_refit_epochs": len(refit_history),
            "use_leiden": False,
            "prediction_export_limit": int(config.prediction_export_limit),
        },
        "training_history": train_history,
        "test_refit_history": refit_history,
        "split_summary": split.to_dict(),
        "prediction_rows": {
            "train": _prediction_rows(
                train_examples,
                final_scores["train"],
                raw_model_scores=model_scores["train"],
                system_prior_scores=prior_scores["train"],
                limit=int(config.prediction_export_limit),
            ),
            "validation": _prediction_rows(
                validation_examples,
                final_scores["validation"],
                raw_model_scores=model_scores["validation"],
                system_prior_scores=prior_scores["validation"],
                limit=int(config.prediction_export_limit),
            ),
            "test": _prediction_rows(
                test_examples,
                final_scores["test"],
                raw_model_scores=model_scores["test"],
                system_prior_scores=prior_scores["test"],
                limit=int(config.prediction_export_limit),
            ),
        },
        "prediction_row_counts": {
            "train": len(train_examples),
            "validation": len(validation_examples),
            "test": len(test_examples),
        },
    }


def _weighted_bce_loss(torch: Any, logits: Any, labels: Any, *, device: str) -> Any:
    positive_count = float(labels.sum().detach().cpu().item())
    negative_count = float(labels.numel() - positive_count)
    pos_weight = None
    if positive_count > 0 and negative_count > 0:
        pos_weight = torch.tensor(negative_count / positive_count, dtype=torch.float32, device=device)
    return torch.nn.functional.binary_cross_entropy_with_logits(
        logits,
        labels,
        pos_weight=pos_weight,
    )


def _select_score_ensemble(
    *,
    validation_examples: list[dict[str, Any]],
    validation_model_scores: list[float],
    validation_prior_scores: list[float],
    validation_tolerance: float,
    mode: str = "adaptive",
) -> dict[str, Any]:
    prior_mean, prior_std = _score_stats(validation_prior_scores)
    model_mean, model_std = _score_stats(validation_model_scores)
    mode = str(mode or "adaptive").strip().lower()
    candidates: list[dict[str, Any]] = []
    if mode in {"adaptive", "system_prior_only", "prior_only"}:
        candidates.append({"strategy": "system_prior_only", "alpha": 0.0, "sign": 1.0})
    if mode in {"adaptive", "learned_only", "learned_residual_only"}:
        candidates.append({"strategy": "learned_residual_only", "alpha": 1.0, "sign": 1.0})
    for alpha in (0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0):
        if mode in {"adaptive", "system_prior_plus_residual", "prior_plus_residual"}:
            candidates.append({"strategy": "system_prior_plus_residual", "alpha": alpha, "sign": 1.0})
        if mode in {"adaptive", "system_prior_minus_residual", "prior_minus_residual"}:
            candidates.append({"strategy": "system_prior_minus_residual", "alpha": alpha, "sign": -1.0})
    if not candidates:
        raise ValueError(f"unsupported score_ensemble_mode: {mode}")

    records: list[dict[str, Any]] = []
    for candidate in candidates:
        scores = _apply_score_ensemble(
            model_scores=validation_model_scores,
            prior_scores=validation_prior_scores,
            ensemble={
                **candidate,
                "prior_mean": prior_mean,
                "prior_std": prior_std,
                "model_mean": model_mean,
                "model_std": model_std,
            },
        )
        metrics = _classification_metrics(validation_examples, scores)
        record = {
            **candidate,
            "validation_auprc": float(metrics.get("auprc") or 0.0),
            "validation_roc_auc": float(metrics.get("roc_auc") or 0.0),
            "validation_max_f1": float(metrics.get("max_f1") or 0.0),
            "prior_mean": prior_mean,
            "prior_std": prior_std,
            "model_mean": model_mean,
            "model_std": model_std,
        }
        record["complexity_rank"] = _ensemble_complexity_rank(record)
        records.append(record)
    if not records:
        return dict(candidates[0])
    best = max(
        records,
        key=lambda record: (
            record["validation_auprc"],
            record["validation_roc_auc"],
            record["validation_max_f1"],
        ),
    )
    prior_record = next((record for record in records if record["strategy"] == "system_prior_only"), None)
    validation_tolerance = max(0.0, float(validation_tolerance))
    residual_beats_prior = bool(
        prior_record is not None
        and best["strategy"] != "system_prior_only"
        and best["validation_auprc"] > prior_record["validation_auprc"] + 1e-9
    )
    prior_gap = (
        best["validation_auprc"] - prior_record["validation_auprc"]
        if prior_record is not None
        else best["validation_auprc"]
    )
    if residual_beats_prior and prior_gap <= validation_tolerance:
        selected = best
        selection_rule = "validation_winner_for_marginal_residual_gain"
    else:
        threshold = best["validation_auprc"] - validation_tolerance
        eligible = [
            record
            for record in records
            if record["validation_auprc"] >= threshold
            and (not residual_beats_prior or record["strategy"] != "system_prior_only")
        ]
        selected = min(
            eligible or [best],
            key=lambda record: (
                record["complexity_rank"],
                -record["validation_auprc"],
                -record["validation_roc_auc"],
            ),
        )
        selection_rule = "validation_tolerance_min_complexity"
    selected["selection_rule"] = selection_rule
    selected["mode"] = mode
    selected["validation_tolerance"] = round(float(validation_tolerance), 6)
    selected["validation_best_auprc"] = round(float(best["validation_auprc"]), 6)
    selected["residual_beats_prior_on_validation"] = residual_beats_prior
    selected["validation_prior_gap"] = round(float(prior_gap), 6)
    return dict(selected)


def _ensemble_complexity_rank(record: dict[str, Any]) -> float:
    strategy = str(record.get("strategy") or "")
    alpha = abs(float(record.get("alpha") or 0.0))
    if strategy == "system_prior_only":
        return 0.0
    if strategy in {"system_prior_plus_residual", "system_prior_minus_residual"}:
        return 1.0 + alpha
    return 10.0


def _apply_score_ensemble(
    *,
    model_scores: list[float],
    prior_scores: list[float],
    ensemble: dict[str, Any],
) -> list[float]:
    strategy = str(ensemble.get("strategy") or "system_prior_only")
    prior_mean = float(ensemble.get("prior_mean") or 0.0)
    prior_std = float(ensemble.get("prior_std") or 1.0)
    model_mean = float(ensemble.get("model_mean") or 0.0)
    model_std = float(ensemble.get("model_std") or 1.0)
    alpha = float(ensemble.get("alpha") or 0.0)
    sign = float(ensemble.get("sign") or 1.0)
    prior_z = [_standardize(score, prior_mean, prior_std) for score in prior_scores]
    model_z = [_standardize(score, model_mean, model_std) for score in model_scores]
    if strategy == "learned_residual_only":
        return model_z
    if strategy == "system_prior_plus_residual":
        return [prior + alpha * model for prior, model in zip(prior_z, model_z)]
    if strategy == "system_prior_minus_residual":
        return [prior + sign * alpha * model for prior, model in zip(prior_z, model_z)]
    return prior_z


def _score_stats(scores: list[float]) -> tuple[float, float]:
    if not scores:
        return 0.0, 1.0
    mean = sum(float(score) for score in scores) / len(scores)
    variance = sum((float(score) - mean) ** 2 for score in scores) / len(scores)
    return mean, math.sqrt(variance) or 1.0


class _TemporalEdgeScorer:
    def __new__(
        cls,
        *,
        torch: Any,
        account_count: int,
        relation_count: int,
        platform_count: int,
        embedding_dim: int,
        hidden_dim: int,
        numeric_dim: int,
    ):
        class Module(torch.nn.Module):  # type: ignore[name-defined]
            def __init__(self) -> None:
                super().__init__()
                self.account_embedding = torch.nn.Embedding(account_count, embedding_dim)
                self.relation_embedding = torch.nn.Embedding(relation_count, embedding_dim)
                self.platform_embedding = torch.nn.Embedding(platform_count, embedding_dim)
                self.numeric_projection = torch.nn.Sequential(
                    torch.nn.Linear(numeric_dim, hidden_dim),
                    torch.nn.ReLU(),
                    torch.nn.Linear(hidden_dim, embedding_dim),
                )
                self.score_head = torch.nn.Sequential(
                    torch.nn.Linear(embedding_dim * 7, hidden_dim),
                    torch.nn.ReLU(),
                    torch.nn.Linear(hidden_dim, max(8, hidden_dim // 2)),
                    torch.nn.ReLU(),
                    torch.nn.Linear(max(8, hidden_dim // 2), 1),
                )
                self.numeric_residual_head = torch.nn.Linear(numeric_dim, 1)

            def forward(
                self,
                source_index: Any,
                target_index: Any,
                relation_index: Any,
                platform_index: Any,
                numeric_features: Any,
            ) -> Any:
                source = self.account_embedding(source_index)
                target = self.account_embedding(target_index)
                relation = self.relation_embedding(relation_index)
                platform = self.platform_embedding(platform_index)
                numeric = self.numeric_projection(numeric_features)
                pair = torch.cat(
                    [
                        source,
                        target,
                        torch.abs(source - target),
                        source * target,
                        relation,
                        platform,
                        numeric,
                    ],
                    dim=-1,
                )
                return self.score_head(pair).squeeze(-1) + self.numeric_residual_head(numeric_features).squeeze(-1)

        return Module()


@dataclass(slots=True)
class _TensorPack:
    inputs: dict[str, Any]
    labels: Any


def _tensorize_examples(
    *,
    torch: Any,
    examples: list[dict[str, Any]],
    account_vocab: dict[str, int],
    relation_vocab: dict[str, int],
    platform_vocab: dict[str, int],
    numeric_stats: dict[str, tuple[float, float]],
    feature_names: tuple[str, ...],
    device: str,
) -> _TensorPack:
    source_index = []
    target_index = []
    relation_index = []
    platform_index = []
    numeric_rows = []
    labels = []

    for row in examples:
        source_index.append(account_vocab.get(str(row.get("source_account_id") or ""), 0))
        target_index.append(account_vocab.get(str(row.get("target_account_id") or ""), 0))
        relation_index.append(relation_vocab.get(str(row.get("relation_type") or ""), 0))
        platform_index.append(platform_vocab.get(str(row.get("platform") or ""), 0))
        numeric_rows.append(_numeric_feature_vector(row, numeric_stats, feature_names=feature_names))
        labels.append(float(row.get("label", 0)))

    return _TensorPack(
        inputs={
            "source_index": torch.tensor(source_index, dtype=torch.long, device=device),
            "target_index": torch.tensor(target_index, dtype=torch.long, device=device),
            "relation_index": torch.tensor(relation_index, dtype=torch.long, device=device),
            "platform_index": torch.tensor(platform_index, dtype=torch.long, device=device),
            "numeric_features": torch.tensor(numeric_rows, dtype=torch.float32, device=device),
        },
        labels=torch.tensor(labels, dtype=torch.float32, device=device),
    )


def _prediction_rows(
    examples: list[dict[str, Any]],
    probabilities: list[float],
    *,
    raw_model_scores: list[float] | None = None,
    system_prior_scores: list[float] | None = None,
    limit: int,
) -> list[dict[str, Any]]:
    rows = []
    for index, (row, probability) in enumerate(zip(examples, probabilities)):
        if index >= max(0, int(limit)):
            break
        payload = dict(row)
        payload["predicted_score"] = round(float(probability), 6)
        if raw_model_scores is not None and index < len(raw_model_scores):
            payload["raw_model_score"] = round(float(raw_model_scores[index]), 6)
        if system_prior_scores is not None and index < len(system_prior_scores):
            payload["system_prior_score"] = round(float(system_prior_scores[index]), 6)
        rows.append(payload)
    return rows


def _numeric_feature_vector(
    row: dict[str, Any],
    numeric_stats: dict[str, tuple[float, float]],
    *,
    feature_names: tuple[str, ...],
) -> list[float]:
    raw_values = _raw_numeric_values(row)
    return [
        _standardize(value, *numeric_stats.get(name, (0.0, 1.0)))
        for name, value in raw_values.items()
        if name in feature_names
    ]


def _fit_numeric_stats(
    rows: list[dict[str, Any]],
    *,
    feature_names: tuple[str, ...],
) -> dict[str, tuple[float, float]]:
    stats: dict[str, tuple[float, float]] = {}
    features: dict[str, list[float]] = {name: [] for name in feature_names}
    for row in rows:
        for name, value in _raw_numeric_values(row).items():
            if name in features:
                features[name].append(value)
    for name, values in features.items():
        mean = sum(values) / max(len(values), 1)
        variance = sum((value - mean) ** 2 for value in values) / max(len(values), 1)
        stats[name] = (mean, math.sqrt(variance) or 1.0)
    return stats


def _raw_numeric_values(row: dict[str, Any]) -> dict[str, float]:
    values = {
        "log_time_delta_seconds": math.log1p(max(0.0, float(row.get("time_delta_seconds") or 0.0))),
        "log_support_count": math.log1p(max(0.0, float(row.get("support_count") or 0.0))),
        "log_history_pair_count": math.log1p(max(0.0, float(row.get("history_pair_count") or 0.0))),
        "log_history_reverse_pair_count": math.log1p(max(0.0, float(row.get("history_reverse_pair_count") or 0.0))),
        "log_history_pair_weight_sum": math.log1p(max(0.0, float(row.get("history_pair_weight_sum") or 0.0))),
        "log_history_source_degree": math.log1p(max(0.0, float(row.get("history_source_degree") or 0.0))),
        "log_history_target_degree": math.log1p(max(0.0, float(row.get("history_target_degree") or 0.0))),
        "log_history_source_relation_degree": math.log1p(max(0.0, float(row.get("history_source_relation_degree") or 0.0))),
        "log_history_target_relation_degree": math.log1p(max(0.0, float(row.get("history_target_relation_degree") or 0.0))),
        "log_history_relation_count": math.log1p(max(0.0, float(row.get("history_relation_count") or 0.0))),
        "log_time_since_pair_seconds": math.log1p(max(1.0, float(row.get("time_since_pair_seconds") or 1.0))),
        "log_time_since_source_relation_seconds": math.log1p(max(1.0, float(row.get("time_since_source_relation_seconds") or 1.0))),
        "log_time_since_target_relation_seconds": math.log1p(max(1.0, float(row.get("time_since_target_relation_seconds") or 1.0))),
        "system_future_edge_prior_score": _system_future_edge_prior_score(row),
        "source_degree": float(row.get("source_degree") or 0.0),
        "target_degree": float(row.get("target_degree") or 0.0),
        "degree_gap": float(row.get("degree_gap") or 0.0),
    }
    return {name: values[name] for name in _NUMERIC_FEATURE_NAMES}


def _fit_vocab(rows: list[dict[str, Any]], fields: tuple[str, ...]) -> dict[str, int]:
    values = {"<unk>"}
    for row in rows:
        for field in fields:
            value = str(row.get(field) or "")
            if value:
                values.add(value)
    return {value: index for index, value in enumerate(sorted(values))}


def _combine_examples(
    positives: list[dict[str, Any]],
    negatives: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    examples = [dict(row) for row in positives]
    examples.extend(dict(row) for row in negatives)
    examples.sort(
        key=lambda row: (
            float(row.get("observed_at") or 0.0),
            int(row.get("label") or 0),
            str(row.get("source_account_id") or ""),
            str(row.get("target_account_id") or ""),
        )
    )
    return examples


def _attach_temporal_history_features(
    examples: list[dict[str, Any]],
    *,
    initial_positive_rows: list[dict[str, Any]],
    update_within_split: bool,
    missing_time_since_seconds: float,
) -> list[dict[str, Any]]:
    state = _empty_history_state()
    for row in sorted(initial_positive_rows, key=lambda item: float(item.get("observed_at") or 0.0)):
        _update_history_state(state, row)

    output: list[dict[str, Any]] = []
    by_time: dict[float, list[dict[str, Any]]] = defaultdict(list)
    for row in examples:
        by_time[float(row.get("observed_at") or 0.0)].append(row)

    for observed_at in sorted(by_time):
        current_rows = sorted(
            by_time[observed_at],
            key=lambda row: (
                int(row.get("label") or 0),
                str(row.get("source_account_id") or ""),
                str(row.get("target_account_id") or ""),
                str(row.get("relation_type") or ""),
            ),
        )
        for row in current_rows:
            enriched = dict(row)
            enriched.update(
                _history_features(
                    state,
                    row,
                    missing_time_since_seconds=missing_time_since_seconds,
                )
            )
            output.append(enriched)
        if update_within_split:
            for row in current_rows:
                if int(row.get("label") or 0) == 1:
                    _update_history_state(state, row)
    output.sort(
        key=lambda row: (
            float(row.get("observed_at") or 0.0),
            int(row.get("label") or 0),
            str(row.get("source_account_id") or ""),
            str(row.get("target_account_id") or ""),
        )
    )
    return output


def _empty_history_state() -> dict[str, Any]:
    return {
        "pair_count": Counter(),
        "pair_weight_sum": defaultdict(float),
        "account_degree": Counter(),
        "source_relation_degree": Counter(),
        "target_relation_degree": Counter(),
        "relation_count": Counter(),
        "last_pair_at": {},
        "last_source_relation_at": {},
        "last_target_relation_at": {},
    }


def _history_features(
    state: dict[str, Any],
    row: dict[str, Any],
    *,
    missing_time_since_seconds: float,
) -> dict[str, float]:
    source = str(row.get("source_account_id") or "")
    target = str(row.get("target_account_id") or "")
    relation = str(row.get("relation_type") or row.get("evidence_kind") or "unknown")
    platform = str(row.get("platform") or "unknown")
    observed_at = float(row.get("observed_at") or 0.0)

    pair_key = (source, target, relation, platform)
    reverse_pair_key = (target, source, relation, platform)
    source_relation_key = (source, relation, platform)
    target_relation_key = (target, relation, platform)
    relation_key = (relation, platform)
    return {
        "history_pair_count": float(state["pair_count"].get(pair_key, 0)),
        "history_reverse_pair_count": float(state["pair_count"].get(reverse_pair_key, 0)),
        "history_pair_weight_sum": float(state["pair_weight_sum"].get(pair_key, 0.0)),
        "history_source_degree": float(state["account_degree"].get(source, 0)),
        "history_target_degree": float(state["account_degree"].get(target, 0)),
        "history_source_relation_degree": float(state["source_relation_degree"].get(source_relation_key, 0)),
        "history_target_relation_degree": float(state["target_relation_degree"].get(target_relation_key, 0)),
        "history_relation_count": float(state["relation_count"].get(relation_key, 0)),
        "time_since_pair_seconds": _time_since(
            observed_at,
            state["last_pair_at"].get(pair_key),
            missing_time_since_seconds=missing_time_since_seconds,
        ),
        "time_since_source_relation_seconds": _time_since(
            observed_at,
            state["last_source_relation_at"].get(source_relation_key),
            missing_time_since_seconds=missing_time_since_seconds,
        ),
        "time_since_target_relation_seconds": _time_since(
            observed_at,
            state["last_target_relation_at"].get(target_relation_key),
            missing_time_since_seconds=missing_time_since_seconds,
        ),
    }


def _update_history_state(state: dict[str, Any], row: dict[str, Any]) -> None:
    source = str(row.get("source_account_id") or "")
    target = str(row.get("target_account_id") or "")
    if not source or not target:
        return
    relation = str(row.get("relation_type") or row.get("evidence_kind") or "unknown")
    platform = str(row.get("platform") or "unknown")
    observed_at = float(row.get("observed_at") or 0.0)
    weight = max(0.0, float(row.get("weight") or 1.0))

    pair_key = (source, target, relation, platform)
    source_relation_key = (source, relation, platform)
    target_relation_key = (target, relation, platform)
    relation_key = (relation, platform)
    state["pair_count"][pair_key] += 1
    state["pair_weight_sum"][pair_key] += weight
    state["account_degree"][source] += 1
    state["account_degree"][target] += 1
    state["source_relation_degree"][source_relation_key] += 1
    state["target_relation_degree"][target_relation_key] += 1
    state["relation_count"][relation_key] += 1
    state["last_pair_at"][pair_key] = observed_at
    state["last_source_relation_at"][source_relation_key] = observed_at
    state["last_target_relation_at"][target_relation_key] = observed_at


def _time_since(
    observed_at: float,
    previous_at: Any,
    *,
    missing_time_since_seconds: float,
) -> float:
    if previous_at is None:
        return max(1.0, float(missing_time_since_seconds))
    return max(1.0, float(observed_at) - float(previous_at))


def _augment_rows(
    rows: list[dict[str, Any]],
    *,
    label: int,
    degree_map: dict[str, int],
) -> list[dict[str, Any]]:
    total = max(len(rows) - 1, 1)
    output = []
    for index, row in enumerate(rows):
        source = str(row.get("source_account_id") or "")
        target = str(row.get("target_account_id") or "")
        source_degree = int(row.get("source_degree") or degree_map.get(source, 0))
        target_degree = int(row.get("target_degree") or degree_map.get(target, 0))
        degree_gap = abs(source_degree - target_degree)
        output.append(
            {
                **row,
                "label": int(label),
                "score": float(label),
                "source_degree": source_degree,
                "target_degree": target_degree,
                "degree_gap": degree_gap,
                "observed_rank": index / total,
                "support_count": int(row.get("support_count") or max(1, len(row.get("evidence_objects") or []))),
            }
        )
    return output


def _classification_metrics(rows: list[dict[str, Any]], scores: list[float]) -> dict[str, Any]:
    labels = [int(row.get("label") or 0) for row in rows]
    if not labels:
        return {
            "sample_count": 0,
            "positive_count": 0,
            "negative_count": 0,
            "roc_auc": 0.0,
            "auprc": 0.0,
            "max_f1": 0.0,
            "ece": 0.0,
        }

    ranked = sorted(zip(scores, labels), key=lambda item: item[0], reverse=True)
    return {
        "sample_count": len(labels),
        "positive_count": sum(labels),
        "negative_count": len(labels) - sum(labels),
        "roc_auc": round(_roc_auc(ranked), 6),
        "auprc": round(_average_precision(ranked), 6),
        "max_f1": round(_max_f1(ranked), 6),
        "ece": round(_expected_calibration_error(labels=labels, scores=[_clip_probability(score) for score in scores]), 6),
        "mean_score": round(sum(_clip_probability(score) for score in scores) / len(scores), 6) if scores else 0.0,
    }


def _baseline_metrics_by_split(
    examples_by_split: dict[str, list[dict[str, Any]]],
) -> dict[str, dict[str, dict[str, Any]]]:
    baselines: dict[str, dict[str, dict[str, Any]]] = {
        "observed_edge_upper_bound": {},
        "system_future_edge_prior": {},
        "edgebank_repeat": {},
        "tgn_style_memory_prior": {},
        "degree_time_prior": {},
    }
    for split_name, examples in examples_by_split.items():
        baselines["observed_edge_upper_bound"][split_name] = _classification_metrics(
            examples,
            _system_evidence_upper_bound_scores(examples),
        )
        baselines["system_future_edge_prior"][split_name] = _classification_metrics(
            examples,
            _system_future_edge_prior_scores(examples),
        )
        baselines["edgebank_repeat"][split_name] = _classification_metrics(
            examples,
            _edgebank_repeat_scores(examples),
        )
        baselines["tgn_style_memory_prior"][split_name] = _classification_metrics(
            examples,
            _tgn_style_memory_prior_scores(examples),
        )
        baselines["degree_time_prior"][split_name] = _classification_metrics(
            examples,
            _degree_time_prior_scores(examples),
        )
    return baselines


def _system_evidence_upper_bound_scores(examples: list[dict[str, Any]]) -> list[float]:
    return [
        1.0
        if float(row.get("weight") or 0.0) > 0.0
        else 0.0
        for row in examples
    ]


def _system_future_edge_prior_scores(examples: list[dict[str, Any]]) -> list[float]:
    return [_system_future_edge_prior_score(row) for row in examples]


def _edgebank_repeat_scores(examples: list[dict[str, Any]]) -> list[float]:
    scores = []
    for row in examples:
        pair_count = float(row.get("history_pair_count") or 0.0)
        pair_weight = float(row.get("history_pair_weight_sum") or 0.0)
        time_since_pair = max(1.0, float(row.get("time_since_pair_seconds") or _MISSING_HISTORY_SECONDS))
        scores.append(
            2.5 * math.log1p(pair_count)
            + 0.75 * math.log1p(pair_weight)
            - 0.25 * math.log1p(time_since_pair / 3600.0)
        )
    return scores


def _tgn_style_memory_prior_scores(examples: list[dict[str, Any]]) -> list[float]:
    scores = []
    for row in examples:
        source_degree = float(row.get("history_source_degree") or 0.0)
        target_degree = float(row.get("history_target_degree") or 0.0)
        source_relation = float(row.get("history_source_relation_degree") or 0.0)
        target_relation = float(row.get("history_target_relation_degree") or 0.0)
        reverse_pair = float(row.get("history_reverse_pair_count") or 0.0)
        relation_count = float(row.get("history_relation_count") or 0.0)
        time_since_source = max(1.0, float(row.get("time_since_source_relation_seconds") or _MISSING_HISTORY_SECONDS))
        time_since_target = max(1.0, float(row.get("time_since_target_relation_seconds") or _MISSING_HISTORY_SECONDS))
        scores.append(
            0.45 * math.log1p(source_degree + target_degree)
            + 0.60 * math.log1p(min(source_relation, target_relation))
            + 0.25 * math.log1p(source_relation + target_relation)
            + 0.30 * math.log1p(reverse_pair)
            + 0.10 * math.log1p(relation_count)
            - 0.10 * math.log1p((time_since_source + time_since_target) / 7200.0)
        )
    return scores


def _system_future_edge_prior_score(row: dict[str, Any]) -> float:
    pair_count = float(row.get("history_pair_count") or 0.0)
    reverse_pair_count = float(row.get("history_reverse_pair_count") or 0.0)
    pair_weight = float(row.get("history_pair_weight_sum") or 0.0)
    source_relation = float(row.get("history_source_relation_degree") or 0.0)
    target_relation = float(row.get("history_target_relation_degree") or 0.0)
    relation_count = float(row.get("history_relation_count") or 0.0)
    source_degree = float(row.get("history_source_degree") or row.get("source_degree") or 0.0)
    target_degree = float(row.get("history_target_degree") or row.get("target_degree") or 0.0)
    time_since_pair = max(1.0, float(row.get("time_since_pair_seconds") or _MISSING_HISTORY_SECONDS))
    return (
        2.0 * math.log1p(pair_count)
        + 0.8 * math.log1p(reverse_pair_count)
        + 0.6 * math.log1p(pair_weight)
        + 0.45 * math.log1p(min(source_relation, target_relation))
        + 0.25 * math.log1p(source_relation + target_relation)
        + 0.15 * math.log1p(source_degree + target_degree)
        + 0.05 * math.log1p(relation_count)
        - 0.20 * math.log1p(time_since_pair / 3600.0)
    )

def _degree_time_prior_scores(examples: list[dict[str, Any]]) -> list[float]:
    scores = []
    for row in examples:
        source_degree = float(row.get("source_degree") or 0.0)
        target_degree = float(row.get("target_degree") or 0.0)
        degree_gap = abs(source_degree - target_degree)
        support_count = float(row.get("support_count") or 0.0)
        time_delta = max(0.0, float(row.get("time_delta_seconds") or 0.0))
        score = (
            math.log1p(source_degree + target_degree)
            - 0.25 * math.log1p(degree_gap)
            + 0.10 * math.log1p(support_count)
            - 0.03 * math.log1p(time_delta)
        )
        scores.append(score)
    return scores


def _claim_gate(
    metrics: dict[str, dict[str, Any]],
    baselines: dict[str, dict[str, dict[str, Any]]],
) -> dict[str, Any]:
    candidate = float(metrics.get("test", {}).get("auprc") or 0.0)
    system = float(
        baselines.get("system_future_edge_prior", {})
        .get("test", {})
        .get("auprc")
        or 0.0
    )
    observed_upper_bound = float(
        baselines.get("observed_edge_upper_bound", {})
        .get("test", {})
        .get("auprc")
        or 0.0
    )
    degree_time = float(
        baselines.get("degree_time_prior", {})
        .get("test", {})
        .get("auprc")
        or 0.0
    )
    baseline_test_edge_auprcs = _baseline_test_metric_map(baselines, "auprc")
    fair_baseline_names = [
        "system_future_edge_prior",
        "edgebank_repeat",
        "tgn_style_memory_prior",
        "degree_time_prior",
    ]
    strongest_fair_baseline = max(
        ((name, baseline_test_edge_auprcs.get(name, 0.0)) for name in fair_baseline_names),
        key=lambda item: item[1],
    )
    beats_system = candidate > system + 1e-9
    blocked_reason = None if beats_system else "candidate_below_fair_system_baseline"
    return {
        "primary_metric": "edge_auprc",
        "comparison_baseline": "system_future_edge_prior",
        "candidate_test_edge_auprc": round(candidate, 6),
        "system_baseline_test_edge_auprc": round(system, 6),
        "observed_edge_upper_bound_test_edge_auprc": round(observed_upper_bound, 6),
        "degree_time_prior_test_edge_auprc": round(degree_time, 6),
        "baseline_test_edge_auprcs": {
            name: round(value, 6)
            for name, value in sorted(baseline_test_edge_auprcs.items())
        },
        "strongest_fair_baseline": strongest_fair_baseline[0],
        "strongest_fair_baseline_test_edge_auprc": round(float(strongest_fair_baseline[1]), 6),
        "candidate_beats_system_baseline": bool(beats_system),
        "candidate_beats_strongest_fair_baseline": bool(candidate > float(strongest_fair_baseline[1]) + 1e-9),
        "candidate_beats_degree_time_prior": bool(candidate > degree_time + 1e-9),
        "blocked_reason": blocked_reason,
    }


def _baseline_test_metric_map(
    baselines: dict[str, dict[str, dict[str, Any]]],
    metric_name: str,
) -> dict[str, float]:
    values = {}
    for baseline_name, split_metrics in baselines.items():
        values[baseline_name] = float(split_metrics.get("test", {}).get(metric_name) or 0.0)
    return values


def _fit_diagnostics(
    examples_by_split: dict[str, list[dict[str, Any]]],
    *,
    account_vocab: dict[str, int],
    relation_vocab: dict[str, int],
    platform_vocab: dict[str, int],
) -> dict[str, Any]:
    diagnostics: dict[str, Any] = {
        "account_vocab_size": len(account_vocab),
        "relation_vocab_size": len(relation_vocab),
        "platform_vocab_size": len(platform_vocab),
        "feature_fit_policy": "train_examples_only",
    }
    for split_name, examples in examples_by_split.items():
        diagnostics[f"{split_name}_account_oov_rate"] = _field_oov_rate(
            examples,
            ("source_account_id", "target_account_id"),
            account_vocab,
        )
        diagnostics[f"{split_name}_relation_oov_rate"] = _field_oov_rate(
            examples,
            ("relation_type",),
            relation_vocab,
        )
        diagnostics[f"{split_name}_platform_oov_rate"] = _field_oov_rate(
            examples,
            ("platform",),
            platform_vocab,
        )
    return diagnostics


def _field_oov_rate(
    rows: list[dict[str, Any]],
    fields: tuple[str, ...],
    vocab: dict[str, int],
) -> float:
    total = 0
    missing = 0
    for row in rows:
        for field in fields:
            value = str(row.get(field) or "")
            if not value:
                continue
            total += 1
            if value not in vocab:
                missing += 1
    return round(missing / total, 6) if total else 0.0


def _heuristic_scores(
    examples: list[dict[str, Any]],
    *,
    numeric_stats: dict[str, tuple[float, float]],
    relation_vocab: dict[str, int],
    feature_names: tuple[str, ...],
) -> list[float]:
    relation_bias = {relation: index / max(len(relation_vocab), 1) for relation, index in relation_vocab.items()}
    scores = []
    for row in examples:
        features = _numeric_feature_vector(row, numeric_stats, feature_names=feature_names)
        weights = (0.35, 0.15, 0.1, 0.15, 0.15, -0.1)
        base = sum(weight * features[index] for index, weight in enumerate(weights) if index < len(features))
        base += 0.05 * relation_bias.get(str(row.get("relation_type") or ""), 0.0)
        scores.append(_sigmoid(base))
    return scores


def _protocol(
    split: TemporalEdgeSplit,
    config: TemporalEdgeModelConfig,
    *,
    time_provenance: Any = None,
) -> dict[str, Any]:
    return {
        "split_policy": split.split_policy,
        "target": "chronological_future_account_pair_edge_prediction",
        "holdout_axes": ["campaign", "platform", "time"],
        "feature_fit_policy": "train_examples_only",
        "history_feature_policy": "train_prefix_for_train_train_for_validation_train_for_test",
        "test_refit_policy": "train_plus_validation_examples_no_test" if bool(config.refit_on_train_validation) else "disabled_train_only_holdout",
        "leakage_control": "observed edge weight is excluded from model inputs",
        "time_provenance": str(time_provenance or "unspecified"),
        "negative_sampling": {
            "strategy": "relation_platform_time_degree_matched",
            "negative_ratio": int(config.negative_ratio),
            "max_negatives_per_positive": int(config.max_negatives_per_positive),
            "future_positive_exclusion_policy": "base_history_plus_current_and_past_positive_prefix_no_future_split_hindsight",
        },
        "leakage_checks": dict(split.leakage_checks),
        "validation_metrics": ["roc_auc", "auprc", "max_f1", "ece"],
    }


def _empty_result(
    *,
    status: str,
    config: TemporalEdgeModelConfig,
    split: TemporalEdgeSplit | None,
    error: str | None = None,
) -> dict[str, Any]:
    feature_names = _active_numeric_feature_names(config)
    empty_split = split or TemporalEdgeSplit(
        split_policy="chronological_event_time",
        train=[],
        validation=[],
        test=[],
        leakage_checks={"future_edges_in_train": 0, "overlapping_edge_keys": 0},
        cutoffs={},
    )
    return {
        "status": status,
        "model_backend": _MODEL_BACKEND,
        "candidate_role": "research_candidate_non_claimable",
        "objective": "direct_account_pair_coordination",
        "protocol": _protocol(empty_split, config),
        "metrics": {
            "train": _classification_metrics([], []),
            "validation": _classification_metrics([], []),
            "test": _classification_metrics([], []),
        },
        "training": {
            "epochs_requested": int(config.epochs),
            "epochs_run": 0,
            "best_epoch": 0,
            "feature_fit_policy": "train_examples_only",
        },
        "model_summary": {
            "mode": "unavailable",
            "reason": error or status,
            "input_feature_names": list(feature_names),
            "use_leiden": False,
        },
        "split_summary": empty_split.to_dict(),
        "error": error,
    }


def _sorted_account_edge_rows(graph: EvidenceGraph) -> list[dict[str, Any]]:
    rows = [_edge_to_row(edge) for edge in graph.account_edges]
    return sorted(
        rows,
        key=lambda row: (
            float(row.get("observed_at") or 0.0),
            str(row.get("source_account_id") or ""),
            str(row.get("target_account_id") or ""),
            str(row.get("relation_type") or ""),
            str(row.get("platform") or ""),
        ),
    )


def _edge_to_row(edge: Any) -> dict[str, Any]:
    if hasattr(edge, "to_dict"):
        return dict(edge.to_dict())
    return dict(edge)


def _split_counts(total: int, *, validation_ratio: float, test_ratio: float) -> tuple[int, int, int]:
    validation_ratio = max(0.0, min(0.9, float(validation_ratio)))
    test_ratio = max(0.0, min(0.9, float(test_ratio)))
    validation_count = max(1, int(round(total * validation_ratio)))
    test_count = max(1, int(round(total * test_ratio)))
    train_count = total - validation_count - test_count
    if train_count < 1:
        deficit = 1 - train_count
        while deficit > 0 and (validation_count > 1 or test_count > 1):
            if validation_count >= test_count and validation_count > 1:
                validation_count -= 1
            elif test_count > 1:
                test_count -= 1
            deficit = 1 - (total - validation_count - test_count)
        train_count = max(1, total - validation_count - test_count)
    if train_count + validation_count + test_count > total:
        overflow = train_count + validation_count + test_count - total
        while overflow > 0 and (validation_count > 1 or test_count > 1):
            if validation_count >= test_count and validation_count > 1:
                validation_count -= 1
            elif test_count > 1:
                test_count -= 1
            overflow = train_count + validation_count + test_count - total
    train_count = max(1, total - validation_count - test_count)
    validation_count = max(1, min(validation_count, total - train_count - 1))
    test_count = max(1, total - train_count - validation_count)
    return train_count, validation_count, test_count


def _leakage_checks(
    *,
    train: list[dict[str, Any]],
    validation: list[dict[str, Any]],
    test: list[dict[str, Any]],
) -> dict[str, int]:
    future_edges_in_train = 0
    if validation:
        validation_cutoff = min(float(row.get("observed_at") or 0.0) for row in validation)
        future_edges_in_train = sum(1 for row in train if float(row.get("observed_at") or 0.0) > validation_cutoff)

    split_key_sets = [_edge_keys(rows) for rows in (train, validation, test) if rows]
    overlapping_edge_keys = 0
    if split_key_sets:
        pairwise = set()
        for left_index, left in enumerate(split_key_sets):
            for right in split_key_sets[left_index + 1 :]:
                pairwise |= left & right
        overlapping_edge_keys = len(pairwise)

    return {
        "future_edges_in_train": int(future_edges_in_train),
        "overlapping_edge_keys": int(overlapping_edge_keys),
    }


def _edge_keys(rows: list[dict[str, Any]]) -> set[tuple[str, str, str, str, float]]:
    return {
        (
            str(row.get("source_account_id") or ""),
            str(row.get("target_account_id") or ""),
            str(row.get("relation_type") or ""),
            str(row.get("platform") or ""),
            float(row.get("observed_at") or 0.0),
        )
        for row in rows
    }


def _degree_map(rows: list[dict[str, Any]]) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for row in rows:
        source = str(row.get("source_account_id") or "")
        target = str(row.get("target_account_id") or "")
        if source:
            counts[source] += 1
        if target:
            counts[target] += 1
    return dict(counts)


def _rank_candidate_pairs(
    *,
    accounts: list[str],
    observed_pairs: set[tuple[str, str]],
    degree_buckets: dict[int, list[str]],
    degree_cache: dict[tuple[int, int, int], list[str]],
    source_degree: int,
    target_degree: int,
    degree_map: dict[str, int],
    seed: int,
    positive_index: int,
    limit: int,
) -> list[tuple[str, str]]:
    source_candidates = _nearby_degree_accounts(
        source_degree,
        degree_buckets=degree_buckets,
        cache=degree_cache,
        limit=limit,
        salt=seed + positive_index * 17,
    )
    target_candidates = _nearby_degree_accounts(
        target_degree,
        degree_buckets=degree_buckets,
        cache=degree_cache,
        limit=limit,
        salt=seed + positive_index * 31,
    )
    ranked: list[tuple[int, str, str]] = []
    for source in source_candidates:
        for target in target_candidates:
            if source == target or (source, target) in observed_pairs:
                continue
            ranked.append(
                (
                    abs(degree_map.get(source, 0) - source_degree)
                    + abs(degree_map.get(target, 0) - target_degree),
                    source,
                    target,
                )
            )
            if len(ranked) >= max(limit * 4, limit):
                break
        if len(ranked) >= max(limit * 4, limit):
            break

    if len(ranked) < limit:
        offset = (seed + positive_index * 9973) % max(len(accounts), 1)
        for source_offset in range(min(len(accounts), limit * 4 + 16)):
            source = accounts[(offset + source_offset) % len(accounts)]
            for target_offset in range(1, min(len(accounts), limit * 2 + 8)):
                target = accounts[(offset + source_offset + target_offset) % len(accounts)]
                if source == target or (source, target) in observed_pairs:
                    continue
                ranked.append(
                    (
                        abs(degree_map.get(source, 0) - source_degree)
                        + abs(degree_map.get(target, 0) - target_degree),
                        source,
                        target,
                    )
                )
                if len(ranked) >= limit:
                    break
            if len(ranked) >= limit:
                break

    return [(source, target) for _, source, target in sorted(ranked)[:limit]]


def _degree_buckets(accounts: list[str], degree_map: dict[str, int]) -> dict[int, list[str]]:
    buckets: dict[int, list[str]] = defaultdict(list)
    for account in accounts:
        buckets[int(degree_map.get(account, 0))].append(account)
    for values in buckets.values():
        values.sort()
    return dict(buckets)


def _nearby_degree_accounts(
    degree: int,
    *,
    degree_buckets: dict[int, list[str]],
    cache: dict[tuple[int, int, int], list[str]],
    limit: int,
    salt: int,
) -> list[str]:
    limit = max(1, int(limit))
    key = (int(degree), limit, int(salt) % 997)
    cached = cache.get(key)
    if cached is not None:
        return cached

    output: list[str] = []
    for bucket_degree in sorted(degree_buckets, key=lambda item: (abs(item - degree), item)):
        values = degree_buckets[bucket_degree]
        if not values:
            continue
        offset = int(salt) % len(values)
        rotated = values[offset:] + values[:offset]
        output.extend(rotated[: max(0, limit - len(output))])
        if len(output) >= limit:
            break
    cache[key] = output
    return output


def _safe_min(values: list[float]) -> float | None:
    return min(values) if values else None


def _standardize(value: float, mean: float, std: float) -> float:
    if std == 0:
        return 0.0
    return (float(value) - float(mean)) / float(std)


def _sigmoid(value: float) -> float:
    return 1.0 / (1.0 + math.exp(-float(value)))


def _clip_probability(value: float) -> float:
    return min(1.0, max(0.0, float(value)))


def _torch_optional() -> Any | None:
    try:
        import torch
    except Exception:
        return None
    return torch


def _resolve_device(torch: Any, requested: str) -> str:
    requested = str(requested or "cpu").lower()
    if requested == "cuda" and getattr(torch, "cuda", None) is not None and torch.cuda.is_available():
        return "cuda"
    return "cpu"


def _roc_auc(ranked: list[tuple[float, int]]) -> float:
    positives = sum(label for _, label in ranked)
    negatives = len(ranked) - positives
    if positives == 0 or negatives == 0:
        return 0.0
    rank_sum = 0.0
    for index, (_, label) in enumerate(sorted(ranked, key=lambda item: item[0]), start=1):
        if label:
            rank_sum += index
    return (rank_sum - positives * (positives + 1) / 2.0) / (positives * negatives)


def _average_precision(ranked: list[tuple[float, int]]) -> float:
    positives = sum(label for _, label in ranked)
    if positives == 0:
        return 0.0
    hits = 0
    precision_sum = 0.0
    for index, (_, label) in enumerate(ranked, start=1):
        if label:
            hits += 1
            precision_sum += hits / index
    return precision_sum / positives


def _max_f1(ranked: list[tuple[float, int]]) -> float:
    positives = sum(label for _, label in ranked)
    if positives == 0:
        return 0.0
    true_positive = 0
    best = 0.0
    for index, (_, label) in enumerate(ranked, start=1):
        if label:
            true_positive += 1
        precision = true_positive / index
        recall = true_positive / positives
        if precision + recall:
            best = max(best, 2 * precision * recall / (precision + recall))
    return best


def _expected_calibration_error(*, labels: list[int], scores: list[float], bins: int = 10) -> float:
    if not labels:
        return 0.0
    total = len(labels)
    error = 0.0
    for bucket in range(bins):
        lower = bucket / bins
        upper = (bucket + 1) / bins
        indexes = [
            index
            for index, score in enumerate(scores)
            if lower <= score < upper or (bucket == bins - 1 and score == 1.0)
        ]
        if not indexes:
            continue
        confidence = sum(scores[index] for index in indexes) / len(indexes)
        accuracy = sum(labels[index] for index in indexes) / len(indexes)
        error += (len(indexes) / total) * abs(accuracy - confidence)
    return error


_NUMERIC_FEATURE_NAMES = (
    "log_time_delta_seconds",
    "log_support_count",
    "log_history_pair_count",
    "log_history_reverse_pair_count",
    "log_history_pair_weight_sum",
    "log_history_source_degree",
    "log_history_target_degree",
    "log_history_source_relation_degree",
    "log_history_target_relation_degree",
    "log_history_relation_count",
    "log_time_since_pair_seconds",
    "log_time_since_source_relation_seconds",
    "log_time_since_target_relation_seconds",
    "system_future_edge_prior_score",
    "source_degree",
    "target_degree",
    "degree_gap",
)


def _active_numeric_feature_names(config: TemporalEdgeModelConfig) -> tuple[str, ...]:
    disabled = {str(name) for name in config.disabled_feature_names}
    return tuple(name for name in _NUMERIC_FEATURE_NAMES if name not in disabled)


__all__ = [
    "TemporalEdgeModelConfig",
    "TemporalEdgeSplit",
    "build_matched_hard_negatives",
    "fit_temporal_edge_model",
    "fit_temporal_edge_model_multi_seed",
    "run_temporal_edge_ablation_suite",
    "split_temporal_account_edges",
]
