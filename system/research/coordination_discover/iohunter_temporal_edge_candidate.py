from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

import pandas as pd

from .contracts import AccountMultigraphEdge, EvidenceGraph
from .temporal_edge_model import (
    TemporalEdgeModelConfig,
    fit_temporal_edge_model,
    fit_temporal_edge_model_multi_seed,
    run_temporal_edge_ablation_suite,
)

DEFAULT_CANDIDATE_SOURCE = "research_candidate_offline_iohunter"
DEFAULT_CANDIDATE_SETTING = "discover_candidate_eval"
DEFAULT_CANDIDATE_FAMILY = "research"
DEFAULT_CANDIDATE_SCOPE = "account_pair"
DEFAULT_CANDIDATE_METHOD = "temporal_history_edge_mlp_v2"
DEFAULT_CANDIDATE_METRICS_FILENAME = "temporal_edge_candidate_metrics.csv"
DEFAULT_CANDIDATE_SUMMARY_FILENAME = "temporal_edge_candidate_summary.json"
DEFAULT_CANDIDATE_ABLATION_METRICS_FILENAME = "temporal_edge_candidate_ablation_metrics.csv"


def build_iohunter_temporal_edge_graph(
    events: pd.DataFrame,
    *,
    dataset_name: str,
) -> EvidenceGraph:
    frame = events.copy()
    timestamp_policy = str(
        getattr(events, "attrs", {}).get("timestamp_policy")
        or "unspecified_processed_event_time"
    )
    if frame.empty:
        accounts = _sorted_accounts(frame)
        return EvidenceGraph(
            snapshot_id=f"iohunter:{dataset_name}:empty",
            event_id=f"iohunter:{dataset_name}:empty",
            data_fingerprint=f"iohunter:{dataset_name}:empty",
            accounts=accounts,
            objects=[],
            edges=[],
            account_edges=[],
            representation_inputs={
                "source": "iohunter_processed_events",
                "timestamp_policy": timestamp_policy,
                "platform_policy": "iohunter_processed_graph",
            },
        )

    for column, default in (
        ("relation", "profile"),
        ("target_account_id", ""),
        ("source_graph", ""),
        ("edge_weight", 1.0),
        ("object_id", ""),
        ("content_id", ""),
        ("timestamp", 0.0),
    ):
        if column not in frame.columns:
            frame[column] = default

    relation_frame = frame.loc[frame["relation"].astype(str) != "profile"].copy()
    relation_frame["account_id"] = relation_frame["account_id"].map(_canonical_account_id)
    relation_frame["target_account_id"] = relation_frame["target_account_id"].map(_canonical_account_id)
    relation_frame = relation_frame.loc[
        (relation_frame["account_id"] != "")
        & (relation_frame["target_account_id"] != "")
        & (relation_frame["account_id"] != relation_frame["target_account_id"])
    ].copy()

    if relation_frame.empty:
        accounts = _sorted_accounts(frame)
        return EvidenceGraph(
            snapshot_id=f"iohunter:{dataset_name}:no_edges",
            event_id=f"iohunter:{dataset_name}:no_edges",
            data_fingerprint=_fingerprint(frame, dataset_name=dataset_name),
            accounts=accounts,
            objects=[],
            edges=[],
            account_edges=[],
            representation_inputs={
                "source": "iohunter_processed_events",
                "timestamp_policy": timestamp_policy,
                "platform_policy": "iohunter_processed_graph",
            },
        )

    sort_columns = [column for column in ("timestamp", "relation", "account_id", "target_account_id", "object_id", "content_id") if column in relation_frame.columns]
    relation_frame = relation_frame.sort_values(by=sort_columns, kind="mergesort").reset_index(drop=True)
    relation_order = {relation: index for index, relation in enumerate(sorted(relation_frame["relation"].astype(str).unique()))}
    support_counts = relation_frame.groupby("object_id", dropna=False).size().to_dict()

    last_observed_by_pair: dict[tuple[str, str], float] = {}
    account_edges: list[AccountMultigraphEdge] = []
    for row in relation_frame.itertuples(index=False):
        source = _canonical_account_id(getattr(row, "account_id", ""))
        target = _canonical_account_id(getattr(row, "target_account_id", ""))
        if not source or not target or source == target:
            continue
        relation = str(getattr(row, "relation", "") or "unknown")
        source_graph = str(getattr(row, "source_graph", "") or "unknown_graph")
        platform = "iohunter_processed_graph"
        object_id = str(getattr(row, "object_id", "") or f"{dataset_name}:{relation}:{source}:{target}")
        content_id = str(getattr(row, "content_id", "") or object_id)
        observed_at = _float_value(getattr(row, "timestamp", 0.0)) * 3600.0 + relation_order.get(relation, 0) * 60.0
        pair_key = (source, target)
        previous = last_observed_by_pair.get(pair_key)
        time_delta_seconds = observed_at - previous if previous is not None else 3600.0
        if time_delta_seconds <= 0:
            time_delta_seconds = 1.0
        last_observed_by_pair[pair_key] = observed_at
        weight = _float_value(getattr(row, "edge_weight", 1.0))
        support_count = int(support_counts.get(object_id, 1))
        account_edges.append(
            AccountMultigraphEdge(
                source_account_id=source,
                target_account_id=target,
                evidence_kind=relation,
                relation_type=relation,
                platform=platform,
                observed_at=round(observed_at, 6),
                weight=round(weight if weight > 0 else 1.0, 6),
                time_delta_seconds=round(time_delta_seconds, 6),
                source_content_id=content_id,
                target_content_id=content_id,
                evidence_objects=[object_id],
                evidence_refs=[content_id],
                direction="observed",
                layer="iohunter_research",
                component_kinds=[relation, f"source_graph:{source_graph}"],
            )
        )

    accounts = sorted({edge.source_account_id for edge in account_edges} | {edge.target_account_id for edge in account_edges})
    return EvidenceGraph(
        snapshot_id=f"iohunter:{dataset_name}",
        event_id=f"iohunter:{dataset_name}",
        data_fingerprint=_fingerprint(relation_frame, dataset_name=dataset_name),
        accounts=accounts,
        objects=[],
        edges=[],
        account_edges=account_edges,
        representation_inputs={
            "source": "iohunter_processed_events",
            "timestamp_policy": timestamp_policy,
            "platform_policy": "iohunter_processed_graph",
        },
    )


def run_iohunter_temporal_edge_candidate(
    events: pd.DataFrame,
    *,
    dataset_name: str,
    output_dir: Path | None = None,
    config: TemporalEdgeModelConfig | None = None,
    seeds: Sequence[int] | None = None,
    include_ablations: bool = False,
    ablation_seeds: Sequence[int] | None = None,
) -> dict[str, Any]:
    config = config or TemporalEdgeModelConfig()
    graph = build_iohunter_temporal_edge_graph(events, dataset_name=dataset_name)
    seed_values = tuple(int(seed) for seed in seeds) if seeds is not None else ()
    if seed_values:
        result = fit_temporal_edge_model_multi_seed(graph, config, seeds=seed_values)
    else:
        result = fit_temporal_edge_model(graph, config)
    ablations = None
    if include_ablations:
        ablation_seed_values = tuple(int(seed) for seed in (ablation_seeds or seed_values or (config.seed,)))
        ablations = run_temporal_edge_ablation_suite(graph, config, seeds=ablation_seed_values)
    report_row = _report_row(result, dataset_name=dataset_name, graph=graph)
    summary = {
        "dataset": dataset_name,
        "source": DEFAULT_CANDIDATE_SOURCE,
        "evaluation": {
            "type": "self_supervised_proxy",
            "target": "chronological_future_account_pair_edge_prediction",
            "uses_official_iohunter_node_labels": False,
            "time_provenance": graph.representation_inputs.get("timestamp_policy"),
            "platform_provenance": graph.representation_inputs.get("platform_policy"),
            "claimability": "research_only_non_claimable",
            "mode": result.get("evaluation_mode") or "single_seed",
            "seeds": list(seed_values or (int(config.seed),)),
            "include_ablations": bool(include_ablations),
        },
        "graph": {
            "snapshot_id": graph.snapshot_id,
            "event_id": graph.event_id,
            "data_fingerprint": graph.data_fingerprint,
            "account_count": len(graph.accounts),
            "account_edge_count": len(graph.account_edges),
        },
        "candidate": result,
        "ablations": ablations,
        "report_row": report_row,
    }
    exports: dict[str, str] = {}
    if output_dir is not None:
        exports = write_iohunter_temporal_edge_candidate_exports(summary, output_dir)
        summary["exports"] = exports
    return {
        **summary,
        **exports,
    }


def write_iohunter_temporal_edge_candidate_exports(
    summary: Mapping[str, Any],
    output_dir: Path,
) -> dict[str, str]:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    summary_path = output_dir / DEFAULT_CANDIDATE_SUMMARY_FILENAME
    metrics_path = output_dir / DEFAULT_CANDIDATE_METRICS_FILENAME
    ablation_metrics_path = output_dir / DEFAULT_CANDIDATE_ABLATION_METRICS_FILENAME

    summary_payload = dict(summary)
    summary_path.write_text(json.dumps(summary_payload, ensure_ascii=False, indent=2), encoding="utf-8")

    row = dict(summary_payload.get("report_row") or {})
    fields = (
        "source",
        "setting",
        "family",
        "method",
        "dataset",
        "scope",
        "split",
        "run_count",
        "macro_f1",
        "auc",
        "auprc",
        "precision",
        "recall",
        "accuracy",
        "ece",
        "edge_max_f1",
        "edge_roc_auc",
        "edge_auprc",
        "edge_ece",
        "system_baseline_edge_auprc",
        "observed_edge_upper_bound_auprc",
        "degree_time_prior_edge_auprc",
        "edgebank_repeat_edge_auprc",
        "tgn_style_memory_prior_edge_auprc",
        "strongest_fair_baseline_edge_auprc",
        "strongest_fair_baseline",
        "candidate_beats_system_baseline",
        "candidate_beats_degree_time_prior",
        "candidate_beats_strongest_fair_baseline",
        "candidate_win_rate_vs_system_baseline",
        "candidate_win_rate_vs_strongest_fair_baseline",
        "candidate_win_rate_vs_degree_time_prior",
        "claim_blocked_reason",
        "primary_metric",
        "primary_metric_name",
        "notes",
        "status",
        "candidate_role",
        "objective",
        "model_backend",
        "evaluation_type",
        "evaluation_mode",
        "label_provenance",
        "time_provenance",
        "account_count",
        "account_edge_count",
    )
    with metrics_path.open("w", encoding="utf-8", newline="") as file_handle:
        writer = csv.DictWriter(file_handle, fieldnames=fields)
        writer.writeheader()
        writer.writerow({field: row.get(field) for field in fields})

    exports = {
        "summary_json": str(summary_path),
        "metrics_csv": str(metrics_path),
    }
    ablation_rows = _ablation_report_rows(summary_payload.get("ablations"), dataset_name=str(summary_payload.get("dataset") or ""))
    if ablation_rows:
        ablation_fields = (
            "source",
            "setting",
            "family",
            "method",
            "dataset",
            "variant",
            "seed_count",
            "edge_auprc_mean",
            "edge_auprc_std",
            "edge_roc_auc_mean",
            "edge_max_f1_mean",
            "edge_ece_mean",
            "win_rate_vs_system_future_edge_prior",
            "win_rate_vs_strongest_fair_baseline",
            "win_rate_vs_degree_time_prior",
            "status",
            "candidate_role",
            "objective",
            "evaluation_mode",
            "notes",
        )
        with ablation_metrics_path.open("w", encoding="utf-8", newline="") as file_handle:
            writer = csv.DictWriter(file_handle, fieldnames=ablation_fields)
            writer.writeheader()
            for ablation_row in ablation_rows:
                writer.writerow({field: ablation_row.get(field) for field in ablation_fields})
        exports["ablation_metrics_csv"] = str(ablation_metrics_path)
    return exports


def _report_row(result: Mapping[str, Any], *, dataset_name: str, graph: EvidenceGraph) -> dict[str, Any]:
    test_metrics = _result_test_metrics(result)
    model_summary = result.get("model_summary") if isinstance(result.get("model_summary"), Mapping) else {}
    training = result.get("training") if isinstance(result.get("training"), Mapping) else {}
    protocol = result.get("protocol") if isinstance(result.get("protocol"), Mapping) else {}
    claim_gate = _result_claim_gate(result)
    baseline_auprcs = _result_baseline_test_auprcs(result)
    evaluation_mode = str(result.get("evaluation_mode") or "single_seed")
    seed_count = int(result.get("seed_count") or 1)
    notes = [
        "research_candidate_non_claimable",
        f"dataset={dataset_name}",
        f"objective={result.get('objective', 'direct_account_pair_coordination')}",
        f"feature_fit_policy={training.get('feature_fit_policy', 'train_only')}",
        f"split_policy={protocol.get('split_policy', 'chronological_event_time')}",
        "evaluation_type=self_supervised_proxy",
        f"evaluation_mode={evaluation_mode}",
        "label_provenance=observed_edges_plus_matched_negatives",
        f"time_provenance={graph.representation_inputs.get('timestamp_policy', 'unknown')}",
        f"negative_sampling={protocol.get('negative_sampling', {}).get('strategy', 'relation_platform_time_degree_matched') if isinstance(protocol.get('negative_sampling'), Mapping) else 'relation_platform_time_degree_matched'}",
    ]
    if model_summary.get("mode"):
        notes.append(f"mode={model_summary.get('mode')}")
    if model_summary.get("reason"):
        notes.append(f"reason={model_summary.get('reason')}")
    return {
        "source": DEFAULT_CANDIDATE_SOURCE,
        "setting": DEFAULT_CANDIDATE_SETTING,
        "family": DEFAULT_CANDIDATE_FAMILY,
        "method": result.get("model_backend") or DEFAULT_CANDIDATE_METHOD,
        "dataset": dataset_name,
        "scope": DEFAULT_CANDIDATE_SCOPE,
        "split": "TEST",
        "run_count": seed_count,
        "macro_f1": None,
        "auc": None,
        "auprc": None,
        "precision": None,
        "recall": None,
        "accuracy": None,
        "ece": None,
        "edge_max_f1": _maybe_float(test_metrics.get("max_f1")),
        "edge_roc_auc": _maybe_float(test_metrics.get("roc_auc")),
        "edge_auprc": _maybe_float(test_metrics.get("auprc")),
        "edge_ece": _maybe_float(test_metrics.get("ece")),
        "system_baseline_edge_auprc": _maybe_float(claim_gate.get("system_baseline_test_edge_auprc")),
        "observed_edge_upper_bound_auprc": _maybe_float(claim_gate.get("observed_edge_upper_bound_test_edge_auprc")),
        "degree_time_prior_edge_auprc": _maybe_float(claim_gate.get("degree_time_prior_test_edge_auprc")),
        "edgebank_repeat_edge_auprc": _maybe_float(baseline_auprcs.get("edgebank_repeat")),
        "tgn_style_memory_prior_edge_auprc": _maybe_float(baseline_auprcs.get("tgn_style_memory_prior")),
        "strongest_fair_baseline_edge_auprc": _maybe_float(claim_gate.get("strongest_fair_baseline_test_edge_auprc")),
        "strongest_fair_baseline": claim_gate.get("strongest_fair_baseline"),
        "candidate_beats_system_baseline": _truth_from_rate_or_bool(claim_gate.get("candidate_beats_system_baseline"), claim_gate.get("win_rate_vs_system_future_edge_prior")),
        "candidate_beats_degree_time_prior": _truth_from_rate_or_bool(claim_gate.get("candidate_beats_degree_time_prior"), claim_gate.get("win_rate_vs_degree_time_prior")),
        "candidate_beats_strongest_fair_baseline": _truth_from_rate_or_bool(claim_gate.get("candidate_beats_strongest_fair_baseline"), claim_gate.get("win_rate_vs_strongest_fair_baseline")),
        "candidate_win_rate_vs_system_baseline": _maybe_float(claim_gate.get("win_rate_vs_system_future_edge_prior")),
        "candidate_win_rate_vs_strongest_fair_baseline": _maybe_float(claim_gate.get("win_rate_vs_strongest_fair_baseline")),
        "candidate_win_rate_vs_degree_time_prior": _maybe_float(claim_gate.get("win_rate_vs_degree_time_prior")),
        "claim_blocked_reason": claim_gate.get("blocked_reason"),
        "primary_metric": None,
        "primary_metric_name": "edge_auprc",
        "notes": ";".join(notes),
        "status": result.get("status"),
        "candidate_role": result.get("candidate_role"),
        "objective": result.get("objective"),
        "model_backend": result.get("model_backend"),
        "evaluation_type": "self_supervised_proxy",
        "evaluation_mode": evaluation_mode,
        "label_provenance": "observed_edges_plus_matched_negatives",
        "time_provenance": graph.representation_inputs.get("timestamp_policy"),
        "account_count": len(graph.accounts),
        "account_edge_count": len(graph.account_edges),
    }


def _result_test_metrics(result: Mapping[str, Any]) -> Mapping[str, Any]:
    aggregate = result.get("aggregate") if isinstance(result.get("aggregate"), Mapping) else {}
    aggregate_test = aggregate.get("test") if isinstance(aggregate.get("test"), Mapping) else {}
    if aggregate_test:
        return {
            metric_name: _summary_mean(aggregate_test.get(metric_name))
            for metric_name in ("max_f1", "roc_auc", "auprc", "ece")
        }
    metrics = result.get("metrics") if isinstance(result.get("metrics"), Mapping) else {}
    return metrics.get("test") if isinstance(metrics.get("test"), Mapping) else {}


def _result_claim_gate(result: Mapping[str, Any]) -> dict[str, Any]:
    aggregate = result.get("aggregate") if isinstance(result.get("aggregate"), Mapping) else {}
    aggregate_claim = aggregate.get("claim_gate") if isinstance(aggregate.get("claim_gate"), Mapping) else {}
    if aggregate_claim:
        baseline_auprcs = _result_baseline_test_auprcs(result)
        return {
            "candidate_test_edge_auprc": _summary_mean(aggregate_claim.get("candidate_test_edge_auprc")),
            "system_baseline_test_edge_auprc": baseline_auprcs.get("system_future_edge_prior"),
            "observed_edge_upper_bound_test_edge_auprc": baseline_auprcs.get("observed_edge_upper_bound"),
            "degree_time_prior_test_edge_auprc": baseline_auprcs.get("degree_time_prior"),
            "strongest_fair_baseline_test_edge_auprc": _summary_mean(aggregate_claim.get("strongest_fair_baseline_test_edge_auprc")),
            "strongest_fair_baseline": aggregate_claim.get("strongest_fair_baseline"),
            "win_rate_vs_system_future_edge_prior": aggregate_claim.get("win_rate_vs_system_future_edge_prior"),
            "win_rate_vs_strongest_fair_baseline": aggregate_claim.get("win_rate_vs_strongest_fair_baseline"),
            "win_rate_vs_degree_time_prior": aggregate_claim.get("win_rate_vs_degree_time_prior"),
            "blocked_reason": "candidate_below_fair_system_baseline"
            if int(aggregate_claim.get("blocked_seed_count") or 0)
            else None,
        }
    return dict(result.get("claim_gate") if isinstance(result.get("claim_gate"), Mapping) else {})


def _result_baseline_test_auprcs(result: Mapping[str, Any]) -> dict[str, Any]:
    aggregate = result.get("aggregate") if isinstance(result.get("aggregate"), Mapping) else {}
    aggregate_baselines = aggregate.get("baselines") if isinstance(aggregate.get("baselines"), Mapping) else {}
    if aggregate_baselines:
        output = {}
        for baseline_name, split_metrics in aggregate_baselines.items():
            if isinstance(split_metrics, Mapping):
                test_metrics = split_metrics.get("test") if isinstance(split_metrics.get("test"), Mapping) else {}
                output[str(baseline_name)] = _summary_mean(test_metrics.get("auprc"))
        return output
    claim_gate = result.get("claim_gate") if isinstance(result.get("claim_gate"), Mapping) else {}
    return dict(claim_gate.get("baseline_test_edge_auprcs") if isinstance(claim_gate.get("baseline_test_edge_auprcs"), Mapping) else {})


def _summary_mean(value: Any) -> Any:
    if isinstance(value, Mapping):
        return value.get("mean")
    return value


def _truth_from_rate_or_bool(flag: Any, rate: Any) -> bool:
    if rate is not None:
        try:
            return float(rate) > 0.5
        except (TypeError, ValueError):
            return False
    return bool(flag)


def _ablation_report_rows(ablations: Any, *, dataset_name: str) -> list[dict[str, Any]]:
    if not isinstance(ablations, Mapping):
        return []
    rows = []
    for variant in ablations.get("variants", []):
        if not isinstance(variant, Mapping):
            continue
        aggregate = variant.get("aggregate") if isinstance(variant.get("aggregate"), Mapping) else {}
        test_metrics = aggregate.get("test") if isinstance(aggregate.get("test"), Mapping) else {}
        claim_gate = aggregate.get("claim_gate") if isinstance(aggregate.get("claim_gate"), Mapping) else {}
        rows.append(
            {
                "source": DEFAULT_CANDIDATE_SOURCE,
                "setting": DEFAULT_CANDIDATE_SETTING,
                "family": DEFAULT_CANDIDATE_FAMILY,
                "method": DEFAULT_CANDIDATE_METHOD,
                "dataset": dataset_name,
                "variant": variant.get("variant"),
                "seed_count": variant.get("seed_count"),
                "edge_auprc_mean": _summary_mean(test_metrics.get("auprc")),
                "edge_auprc_std": (test_metrics.get("auprc") or {}).get("std") if isinstance(test_metrics.get("auprc"), Mapping) else None,
                "edge_roc_auc_mean": _summary_mean(test_metrics.get("roc_auc")),
                "edge_max_f1_mean": _summary_mean(test_metrics.get("max_f1")),
                "edge_ece_mean": _summary_mean(test_metrics.get("ece")),
                "win_rate_vs_system_future_edge_prior": claim_gate.get("win_rate_vs_system_future_edge_prior"),
                "win_rate_vs_strongest_fair_baseline": claim_gate.get("win_rate_vs_strongest_fair_baseline"),
                "win_rate_vs_degree_time_prior": claim_gate.get("win_rate_vs_degree_time_prior"),
                "status": variant.get("status"),
                "candidate_role": ablations.get("candidate_role"),
                "objective": ablations.get("objective"),
                "evaluation_mode": ablations.get("evaluation_mode"),
                "notes": f"what_it_tests={variant.get('what_it_tests', '')}",
            }
        )
    return rows


def _sorted_accounts(frame: pd.DataFrame) -> list[str]:
    if "account_id" not in frame.columns:
        return []
    accounts = {_canonical_account_id(value) for value in frame["account_id"].tolist()}
    if "target_account_id" in frame.columns:
        accounts.update(_canonical_account_id(value) for value in frame["target_account_id"].tolist())
    return sorted(account for account in accounts if account)


def _canonical_account_id(value: object) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    if not text or text.lower() in {"nan", "none", "null"}:
        return ""
    try:
        number = float(text)
    except ValueError:
        return text
    if number.is_integer() and text.replace(".", "", 1).lstrip("+-").isdigit():
        return str(int(number))
    return text


def _float_value(value: object) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _maybe_float(value: object) -> float | None:
    try:
        if value is None:
            return None
        return round(float(value), 6)
    except (TypeError, ValueError):
        return None


def _fingerprint(frame: pd.DataFrame, *, dataset_name: str) -> str:
    columns = [
        column
        for column in ("account_id", "relation", "object_id", "timestamp", "target_account_id", "source_graph", "edge_weight")
        if column in frame.columns
    ]
    payload = frame.loc[:, columns].fillna("").astype(str).to_json(orient="records", force_ascii=False)
    return hashlib.sha256(f"{dataset_name}|{payload}".encode("utf-8")).hexdigest()[:24]


__all__ = [
    "DEFAULT_CANDIDATE_ABLATION_METRICS_FILENAME",
    "DEFAULT_CANDIDATE_FAMILY",
    "DEFAULT_CANDIDATE_METHOD",
    "DEFAULT_CANDIDATE_METRICS_FILENAME",
    "DEFAULT_CANDIDATE_SCOPE",
    "DEFAULT_CANDIDATE_SETTING",
    "DEFAULT_CANDIDATE_SOURCE",
    "DEFAULT_CANDIDATE_SUMMARY_FILENAME",
    "build_iohunter_temporal_edge_graph",
    "run_iohunter_temporal_edge_candidate",
    "write_iohunter_temporal_edge_candidate_exports",
]
