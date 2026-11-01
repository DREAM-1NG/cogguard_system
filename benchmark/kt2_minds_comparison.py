from __future__ import annotations

import argparse
import json
import math
import sys
import time
from pathlib import Path
from statistics import mean, pstdev
from typing import Dict, Iterable, List, Mapping, Optional, Sequence

from benchmark.adapters.kt2_joint_model import run_kt2_joint_model
from benchmark.adapters.kt2_sequence_joint_model import run_kt2_sequence_joint_model
from benchmark.same_protocol_full_run_baselines import (
    DEFAULT_FOREST_DATA,
    DEFAULT_MINDS_REPO,
    ADAPTERS_DIR,
    prepare_minds_forest_dataset,
    resolve_minds_work_dir,
    run_adapter,
)
from benchmark.schema import validate_benchmark_results


COMMON_METRICS = (
    "msle",
    "hits@10",
    "hits@50",
    "hits@100",
    "map@10",
    "map@50",
    "map@100",
)
LOWER_IS_BETTER = {"msle"}
MIN_FULL_RUN_DATASETS = 3
MIN_FULL_RUN_SEEDS = 3
MIN_FULL_RUN_EPOCHS = 200
KT2_FORMAL_MODEL = "KT2SequenceJointModel"
TRAINABLE_COMPARISON_MODELS = {"MINDS", KT2_FORMAL_MODEL}
MODEL_ALIASES = {
    "KT2": KT2_FORMAL_MODEL,
    "KT2Sequence": KT2_FORMAL_MODEL,
    "KT2JointModel": "legacy_candidate_level_kt2",
}


def parse_csv(value: str) -> List[str]:
    return [item.strip() for item in str(value or "").split(",") if item.strip()]


def parse_int_csv(value: str) -> List[int]:
    return [int(item) for item in parse_csv(value)]


def parse_float_csv(value: str) -> List[float]:
    return [float(item) for item in parse_csv(value)]


def normalize_selected_models(value: str) -> set[str]:
    """Return the trainable model subset allowed in the KT2-vs-MINDS verdict."""

    selected = set()
    unknown = []
    for raw_model in parse_csv(value):
        model = MODEL_ALIASES.get(raw_model, raw_model)
        if model == "legacy_candidate_level_kt2" or model not in TRAINABLE_COMPARISON_MODELS:
            unknown.append(raw_model)
        else:
            selected.add(model)
    if unknown:
        allowed = ", ".join(sorted(TRAINABLE_COMPARISON_MODELS | {"KT2", "KT2Sequence"}))
        blocked = ", ".join(unknown)
        raise ValueError(
            f"Unsupported model(s) for KT2-vs-MINDS trainable comparison: {blocked}. "
            f"Allowed models are: {allowed}. KT2JointModel is legacy candidate-level ablation only. "
            f"Handcrafted/heuristic baselines must stay outside this verdict."
        )
    return selected or set(TRAINABLE_COMPARISON_MODELS)


def split_comparison_rows(rows: Iterable[Mapping]) -> tuple[List[Dict], List[Dict]]:
    """Keep only trainable comparison rows and summarize ignored sanity/baseline rows."""

    kept: List[Dict] = []
    ignored: List[Dict] = []
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        model = str(row.get("model", ""))
        if model in TRAINABLE_COMPARISON_MODELS:
            kept.append(dict(row))
        else:
            ignored.append(
                {
                    "model": model,
                    "dataset": row.get("dataset", row.get("experiment_dataset")),
                    "seed": row.get("seed", row.get("experiment_seed")),
                    "status": row.get("status"),
                    "reason": "excluded_from_trainable_model_verdict",
                }
            )
    return kept, ignored


def finite_metric(row: Mapping, metric: str) -> Optional[float]:
    value = row.get(metric)
    if isinstance(value, (int, float)) and math.isfinite(float(value)):
        return float(value)
    return None


def run_minds_baseline(args: argparse.Namespace, dataset: str, seed: int) -> Dict:
    minds_work_dir = resolve_minds_work_dir(Path(args.minds_repo))
    if minds_work_dir is None:
        return failure_row(
            "MINDS",
            dataset,
            seed,
            args.config_id,
            "missing_external_repo",
            f"MINDS source not found under {args.minds_repo}.",
        )

    prepared = prepare_minds_forest_dataset(
        Path(args.forest_data_root) / dataset,
        minds_work_dir,
        dataset,
        int(args.max_minds_cascades),
    )
    if prepared.get("status") != "ok":
        return failure_row(
            "MINDS",
            dataset,
            seed,
            args.config_id,
            "missing_data",
            str(prepared.get("note", f"Could not stage {dataset} for MINDS.")),
        )

    cmd = [
        args.python,
        "-u",
        str(ADAPTERS_DIR / "minds_runner.py"),
        "--dataset_name",
        str(prepared["dataset_name"]),
        "--report_dataset",
        dataset,
        "--protocol_source",
        f"converted from FOREST {dataset} cascade.txt",
        "--epochs",
        str(args.minds_epochs),
        "--batch_size",
        str(args.minds_batch_size),
        "--emb_dim",
        str(args.minds_emb_dim),
        "--step_split",
        str(args.minds_step_split),
        "--max_seq_length",
        str(args.minds_max_seq_length),
        "--device",
        args.device,
        "--reproduction_level",
        args.minds_reproduction_level,
        "--config_id",
        args.config_id,
        "--seed",
        str(seed),
    ]
    log_path = (
        Path("benchmark")
        / "logs"
        / f"MINDS_{dataset}_seed{seed}_{args.config_id}.log"
    )
    row = run_adapter(cmd, minds_work_dir, args.timeout, "MINDS", dataset, args.config_id, seed, log_path)
    row["comparison_role"] = "trainable_original_minds_baseline"
    row["minds_staged_dataset"] = prepared
    return row


def run_kt2_candidate(args: argparse.Namespace, dataset: str, seed: int) -> Dict:
    return run_kt2_sequence_candidate(args, dataset, seed)


def run_kt2_sequence_candidate(args: argparse.Namespace, dataset: str, seed: int) -> Dict:
    data_dir = Path(args.forest_data_root) / dataset
    row = run_kt2_sequence_joint_model(
        data_dir,
        dataset=dataset,
        obs_ratios=parse_float_csv(getattr(args, "kt2_obs_ratios", "0.1,0.3,0.5")),
        epochs=args.kt2_epochs,
        batch_size=args.kt2_batch_size,
        hidden_dim=args.kt2_hidden_dim,
        max_train_cascades=args.kt2_max_train_cascades,
        max_test_cascades=args.kt2_max_test_cascades,
        max_sequence_len=args.kt2_max_sequence_len,
        trend_steps=getattr(args, "kt2_trend_steps", 4),
        negative_samples=getattr(args, "kt2_negative_samples", 32),
        rollout_steps=getattr(args, "kt2_rollout_steps", 5),
        seed=seed,
        device=args.device,
    )
    row["comparison_role"] = "trainable_kt2_sequence_candidate"
    row["config_id"] = args.config_id
    row["experiment_seed"] = seed
    row["experiment_dataset"] = dataset
    row["experiment_scope"] = "kt2_sequence_vs_original_minds_same_source"
    return row


def run_legacy_kt2_candidate(args: argparse.Namespace, dataset: str, seed: int) -> Dict:
    data_dir = Path(args.forest_data_root) / dataset
    row = run_kt2_joint_model(
        data_dir,
        obs_ratio=args.obs_ratio,
        max_future_per_cascade=args.kt2_max_future_per_cascade,
        global_top_n=args.kt2_global_top_n,
        max_candidates=args.kt2_max_candidates,
        negatives_per_cascade=args.kt2_negatives_per_cascade,
        epochs=args.kt2_epochs,
        batch_size=args.kt2_batch_size,
        hidden_dim=args.kt2_hidden_dim,
        max_train_cascades=args.kt2_max_train_cascades,
        max_test_cascades=args.kt2_max_test_cascades,
        max_sequence_len=args.kt2_max_sequence_len,
        max_steps_per_epoch=args.kt2_max_steps_per_epoch,
        max_eval_cascades=args.kt2_max_eval_cascades,
        lambda_consistency=args.kt2_lambda_consistency,
        lambda_forest_pg=args.kt2_lambda_forest_pg,
        forest_pg_rollout_samples=args.kt2_forest_pg_rollout_samples,
        use_original_minds_components=True,
        use_original_minds_full_module=True,
        lambda_original_minds_module=args.kt2_lambda_original_minds_module,
        minds_repo=args.minds_repo,
        seed=seed,
        device=args.device,
    )
    row["comparison_role"] = "legacy_candidate_level_kt2_ablation"
    row["config_id"] = args.config_id
    row["experiment_seed"] = seed
    row["experiment_dataset"] = dataset
    row["experiment_scope"] = "kt2_vs_original_minds_same_source"
    return row


def failure_row(model: str, dataset: str, seed: int, config_id: str, status: str, note: str) -> Dict:
    return {
        "model": model,
        "dataset": dataset,
        "task": "multi_scale",
        "status": status,
        "reproduction_level": "frontier_reproduction_attempted"
        if model == "MINDS"
        else "kt2_sequence_joint_model_small_run",
        "seed": seed,
        "config_id": config_id,
        "note": note,
    }


def compare_pair(minds_row: Mapping, kt2_row: Mapping) -> Dict:
    metrics = {}
    positive = 0
    negative = 0
    tied = 0
    missing = []
    for metric in COMMON_METRICS:
        baseline_value = finite_metric(minds_row, metric)
        kt2_value = finite_metric(kt2_row, metric)
        if baseline_value is None or kt2_value is None:
            missing.append(metric)
            continue
        raw_delta = kt2_value - baseline_value
        better_delta = -raw_delta if metric in LOWER_IS_BETTER else raw_delta
        if better_delta > 0:
            positive += 1
            interpretation = "supports_kt2"
        elif better_delta < 0:
            negative += 1
            interpretation = "supports_minds"
        else:
            tied += 1
            interpretation = "tie"
        metrics[metric] = {
            "minds": baseline_value,
            "kt2": kt2_value,
            "raw_delta": raw_delta,
            "better_direction_delta": better_delta,
            "interpretation": interpretation,
        }
    if not metrics:
        verdict = "insufficient_common_metrics"
    elif positive > negative:
        verdict = "supports_kt2_improvement"
    elif negative > positive:
        verdict = "does_not_support_kt2_improvement"
    else:
        verdict = "mixed_or_inconclusive"
    return {
        "dataset": kt2_row.get("dataset") or minds_row.get("dataset"),
        "seed": kt2_row.get("seed", kt2_row.get("experiment_seed", minds_row.get("seed"))),
        "minds_status": minds_row.get("status"),
        "kt2_status": kt2_row.get("status"),
        "metrics": metrics,
        "missing_common_metrics": missing,
        "positive_metric_count": positive,
        "negative_metric_count": negative,
        "tie_metric_count": tied,
        "verdict": verdict,
    }


def metric_summary(comparisons: Iterable[Mapping]) -> Dict[str, Dict[str, float]]:
    values_by_metric: Dict[str, List[float]] = {metric: [] for metric in COMMON_METRICS}
    for comparison in comparisons:
        for metric, payload in comparison.get("metrics", {}).items():
            if isinstance(payload, Mapping) and isinstance(payload.get("better_direction_delta"), (int, float)):
                values_by_metric.setdefault(metric, []).append(float(payload["better_direction_delta"]))
    summary = {}
    for metric, values in values_by_metric.items():
        if values:
            summary[metric] = {
                "mean_better_direction_delta": mean(values),
                "std": pstdev(values) if len(values) > 1 else 0.0,
                "n": len(values),
                "positive": sum(1 for value in values if value > 0),
                "negative": sum(1 for value in values if value < 0),
                "tie": sum(1 for value in values if value == 0),
            }
    return summary


def overall_verdict(comparisons: Sequence[Mapping]) -> str:
    usable = [row for row in comparisons if row.get("verdict") != "insufficient_common_metrics"]
    if not usable:
        return "insufficient_evidence"
    positive = sum(1 for row in usable if row.get("verdict") == "supports_kt2_improvement")
    negative = sum(1 for row in usable if row.get("verdict") == "does_not_support_kt2_improvement")
    if positive == len(usable):
        return "supports_kt2_improvement_on_all_completed_pairs"
    if positive > negative:
        return "partially_supports_kt2_improvement"
    if negative > positive:
        return "does_not_support_kt2_improvement"
    return "mixed_or_inconclusive"


def evidence_level(args: argparse.Namespace) -> str:
    """Return whether this comparison is a preflight or full-validation candidate."""

    datasets = parse_csv(args.datasets)
    seeds = parse_int_csv(args.seeds)
    kt2_untruncated = int(args.kt2_max_train_cascades) <= 0 and int(args.kt2_max_test_cascades) <= 0
    minds_untruncated = int(args.max_minds_cascades) <= 0
    kt2_unbudgeted = int(getattr(args, "kt2_max_steps_per_epoch", 0)) <= 0 and int(
        getattr(args, "kt2_max_eval_cascades", 0)
    ) <= 0
    enough_scope = (
        len(datasets) >= MIN_FULL_RUN_DATASETS
        and len(seeds) >= MIN_FULL_RUN_SEEDS
        and int(args.minds_epochs) >= MIN_FULL_RUN_EPOCHS
        and int(args.kt2_epochs) >= MIN_FULL_RUN_EPOCHS
        and kt2_untruncated
        and minds_untruncated
        and kt2_unbudgeted
    )
    if (
        len(datasets) >= MIN_FULL_RUN_DATASETS
        and int(args.minds_epochs) >= MIN_FULL_RUN_EPOCHS
        and int(args.kt2_epochs) >= MIN_FULL_RUN_EPOCHS
        and kt2_untruncated
        and minds_untruncated
        and not kt2_unbudgeted
    ):
        return "resource_bounded_full_source_candidate"
    return "full_run_candidate" if enough_scope else "preflight"


def full_run_requirements(args: argparse.Namespace, comparisons: Sequence[Mapping], missing_pairs: Sequence[Mapping]) -> Dict:
    datasets = parse_csv(args.datasets)
    seeds = parse_int_csv(args.seeds)
    checks = {
        "dataset_count_at_least_3": len(datasets) >= MIN_FULL_RUN_DATASETS,
        "seed_count_at_least_3": len(seeds) >= MIN_FULL_RUN_SEEDS,
        "minds_epochs_at_least_200": int(args.minds_epochs) >= MIN_FULL_RUN_EPOCHS,
        "kt2_epochs_at_least_200": int(args.kt2_epochs) >= MIN_FULL_RUN_EPOCHS,
        "minds_uses_all_available_cascades": int(args.max_minds_cascades) <= 0,
        "kt2_uses_all_train_and_test_cascades": int(args.kt2_max_train_cascades) <= 0
        and int(args.kt2_max_test_cascades) <= 0,
        "kt2_unbudgeted_training_and_eval": int(getattr(args, "kt2_max_steps_per_epoch", 0)) <= 0
        and int(getattr(args, "kt2_max_eval_cascades", 0)) <= 0,
        "no_missing_model_pairs": not missing_pairs,
        "has_completed_comparisons": bool(comparisons),
    }
    return {
        "checks": checks,
        "passed": all(checks.values()),
        "minimums": {
            "datasets": MIN_FULL_RUN_DATASETS,
            "seeds": MIN_FULL_RUN_SEEDS,
            "epochs": MIN_FULL_RUN_EPOCHS,
        },
    }


def build_payload(
    args: argparse.Namespace,
    rows: List[Dict],
    started: float,
    ignored_rows: Optional[Sequence[Mapping]] = None,
) -> Dict:
    rows, build_ignored = split_comparison_rows(rows)
    ignored_rows = list(ignored_rows or []) + build_ignored
    by_key = {}
    for row in rows:
        key = (row.get("model"), row.get("dataset"), int(row.get("seed", row.get("experiment_seed", 0))))
        by_key[key] = row
    comparisons = []
    missing_pairs = []
    for dataset in parse_csv(args.datasets):
        for seed in parse_int_csv(args.seeds):
            minds_row = by_key.get(("MINDS", dataset, seed))
            kt2_row = by_key.get((KT2_FORMAL_MODEL, dataset, seed))
            if minds_row and kt2_row and minds_row.get("status") == "ok" and kt2_row.get("status") == "ok":
                comparisons.append(compare_pair(minds_row, kt2_row))
            else:
                missing_pairs.append(
                    {
                        "dataset": dataset,
                        "seed": seed,
                        "minds_status": None if minds_row is None else minds_row.get("status"),
                        "kt2_status": None if kt2_row is None else kt2_row.get("status"),
                    }
                )
    schema = validate_benchmark_results(rows)
    verdict = overall_verdict(comparisons)
    full_requirements = full_run_requirements(args, comparisons, missing_pairs)
    level = evidence_level(args)
    complete = not missing_pairs and bool(comparisons) and schema.get("ok")
    return {
        "schema": "cogguard.kt2.minds_comparison.v1",
        "status": "ok" if complete else "partial",
        "config_id": args.config_id,
        "evidence_level": level,
        "full_validation_passed": bool(complete and full_requirements["passed"]),
        "full_run_requirements": full_requirements,
        "boundary": (
            "Compares trainable original MINDS public-code baseline against KT2SequenceJointModel on the same FOREST-source datasets. "
            "Handcrafted/heuristic baselines are excluded from the improvement verdict. "
            "preflight evidence proves the pipeline and a directional comparison only; full_validation_passed=true is required before claiming final KT2 improvement over MINDS."
        ),
        "comparison_model_filter": {
            "allowed_models": sorted(TRAINABLE_COMPARISON_MODELS),
            "aliases": MODEL_ALIASES,
            "ignored_non_comparison_rows": ignored_rows,
            "ignored_non_comparison_row_count": len(ignored_rows),
            "rule": "Only trainable MINDS and KT2SequenceJointModel rows can enter pair verdicts and metric deltas.",
        },
        "datasets": parse_csv(args.datasets),
        "seeds": parse_int_csv(args.seeds),
        "common_metrics": list(COMMON_METRICS),
        "overall_verdict": verdict,
        "metric_summary": metric_summary(comparisons),
        "comparisons": comparisons,
        "missing_pairs": missing_pairs,
        "schema_report": schema,
        "rows": rows,
        "elapsed_s": round(time.time() - started, 1),
    }


def write_markdown(payload: Mapping, path: Path) -> None:
    lines = [
        "# KT2 vs MINDS Comparison",
        "",
        f"- status: `{payload.get('status')}`",
        f"- evidence_level: `{payload.get('evidence_level')}`",
        f"- full_validation_passed: `{payload.get('full_validation_passed')}`",
        f"- overall_verdict: `{payload.get('overall_verdict')}`",
        f"- datasets: `{', '.join(payload.get('datasets', []))}`",
        f"- seeds: `{', '.join(str(seed) for seed in payload.get('seeds', []))}`",
        "",
        str(payload.get("boundary")),
        "",
        "## Model Filter",
        "",
        f"- allowed_models: `{', '.join(payload.get('comparison_model_filter', {}).get('allowed_models', []))}`",
        f"- ignored_non_comparison_row_count: `{payload.get('comparison_model_filter', {}).get('ignored_non_comparison_row_count', 0)}`",
        "- rule: `Only trainable MINDS and KT2SequenceJointModel rows can enter pair verdicts and metric deltas.`",
        "",
        "## Full-Run Requirements",
        "",
        "| check | passed |",
        "|---|---:|",
    ]
    for key, value in payload.get("full_run_requirements", {}).get("checks", {}).items():
        lines.append(f"| {key} | `{value}` |")
    lines.extend([
        "",
        "## Pair Verdicts",
        "",
        "| dataset | seed | verdict | positive | negative | tie |",
        "|---|---:|---|---:|---:|---:|",
    ])
    for row in payload.get("comparisons", []):
        lines.append(
            "| {dataset} | {seed} | {verdict} | {positive} | {negative} | {tie} |".format(
                dataset=row.get("dataset"),
                seed=row.get("seed"),
                verdict=row.get("verdict"),
                positive=row.get("positive_metric_count"),
                negative=row.get("negative_metric_count"),
                tie=row.get("tie_metric_count"),
            )
        )
    lines.extend(["", "## Metric Deltas", "", "| dataset | metric | MINDS | KT2 | better-direction delta | interpretation |", "|---|---|---:|---:|---:|---|"])
    for row in payload.get("comparisons", []):
        for metric, stats in row.get("metrics", {}).items():
            lines.append(
                "| {dataset} | {metric} | {minds:.6f} | {kt2:.6f} | {delta:.6f} | {interpretation} |".format(
                    dataset=row.get("dataset"),
                    metric=metric,
                    minds=stats["minds"],
                    kt2=stats["kt2"],
                    delta=stats["better_direction_delta"],
                    interpretation=stats["interpretation"],
                )
            )
    if payload.get("missing_pairs"):
        lines.extend(["", "## Missing / Failed Pairs", ""])
        for row in payload.get("missing_pairs", []):
            lines.append(f"- `{row}`")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_payload(payload: Mapping, out: Path) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    write_markdown(payload, out.with_suffix(".md"))


def load_existing_rows(path: Path) -> List[Dict]:
    if not path.is_file():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    rows = payload.get("rows", []) if isinstance(payload, Mapping) else payload
    if not isinstance(rows, list):
        return []
    deduped: Dict[tuple[str, str, int], Dict] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        model = str(row.get("model", ""))
        dataset = str(row.get("dataset", row.get("experiment_dataset", "")))
        try:
            seed = int(row.get("seed", row.get("experiment_seed", 0)))
        except (TypeError, ValueError):
            seed = 0
        if model and dataset:
            deduped[(model, dataset, seed)] = row
    return list(deduped.values())


def completed_pair_keys(rows: Iterable[Mapping]) -> set[tuple[str, int]]:
    status_by_key: Dict[tuple[str, int], set[str]] = {}
    for row in rows:
        if row.get("status") != "ok":
            continue
        dataset = str(row.get("dataset", row.get("experiment_dataset", "")))
        try:
            seed = int(row.get("seed", row.get("experiment_seed", 0)))
        except (TypeError, ValueError):
            continue
        status_by_key.setdefault((dataset, seed), set()).add(str(row.get("model")))
    return {key for key, models in status_by_key.items() if {"MINDS", KT2_FORMAL_MODEL}.issubset(models)}


def existing_model_keys(rows: Iterable[Mapping]) -> set[tuple[str, str, int]]:
    keys = set()
    for row in rows:
        model = str(row.get("model", ""))
        dataset = str(row.get("dataset", row.get("experiment_dataset", "")))
        try:
            seed = int(row.get("seed", row.get("experiment_seed", 0)))
        except (TypeError, ValueError):
            continue
        if model and dataset:
            keys.add((model, dataset, seed))
    return keys


def run_comparison(args: argparse.Namespace) -> Dict:
    started = time.time()
    out = Path(args.out)
    loaded_rows = load_existing_rows(out) if getattr(args, "resume", False) else []
    rows, ignored_rows = split_comparison_rows(loaded_rows)
    completed = completed_pair_keys(rows)
    existing = existing_model_keys(rows)
    max_pairs = int(getattr(args, "max_pairs", 0) or 0)
    new_pairs = 0
    selected_models = normalize_selected_models(getattr(args, "models", f"MINDS,{KT2_FORMAL_MODEL}"))
    for dataset in parse_csv(args.datasets):
        for seed in parse_int_csv(args.seeds):
            pair_key = (dataset, seed)
            if pair_key in completed:
                continue
            if max_pairs > 0 and new_pairs >= max_pairs:
                return build_payload(args, rows, started, ignored_rows)
            ran_any = False
            if "MINDS" in selected_models and ("MINDS", dataset, seed) not in existing:
                rows.append(run_minds_baseline(args, dataset, seed))
                existing = existing_model_keys(rows)
                ran_any = True
                write_payload(build_payload(args, rows, started, ignored_rows), out)
            if (
                KT2_FORMAL_MODEL in selected_models
                and (KT2_FORMAL_MODEL, dataset, seed) not in existing
            ):
                rows.append(run_kt2_candidate(args, dataset, seed))
                existing = existing_model_keys(rows)
                ran_any = True
                write_payload(build_payload(args, rows, started, ignored_rows), out)
            if not ran_any:
                continue
            completed = completed_pair_keys(rows)
            new_pairs += 1
            payload = build_payload(args, rows, started, ignored_rows)
            write_payload(payload, out)
    return build_payload(args, rows, started, ignored_rows)


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Compare trainable original MINDS baseline against KT2SequenceJointModel.")
    parser.add_argument("--datasets", default="douban,twitter,memetracker")
    parser.add_argument("--seeds", default="42")
    parser.add_argument("--forest_data_root", default=str(DEFAULT_FOREST_DATA))
    parser.add_argument("--minds_repo", default=str(DEFAULT_MINDS_REPO))
    parser.add_argument("--out", default=str(Path("benchmark") / "kt2_vs_minds_comparison.json"))
    parser.add_argument("--config_id", default="kt2-vs-minds-preflight")
    parser.add_argument(
        "--models",
        default=f"MINDS,{KT2_FORMAL_MODEL}",
        help="Comma-separated subset: MINDS,KT2SequenceJointModel. KT2JointModel is legacy ablation only.",
    )
    parser.add_argument("--python", default=sys.executable)
    parser.add_argument("--device", default="cpu", choices=["cpu", "cuda"])
    parser.add_argument("--timeout", type=int, default=1800)
    parser.add_argument("--obs_ratio", type=float, default=0.3)
    parser.add_argument("--max_minds_cascades", type=int, default=300)
    parser.add_argument("--minds_epochs", type=int, default=200)
    parser.add_argument("--minds_batch_size", type=int, default=32)
    parser.add_argument("--minds_emb_dim", type=int, default=32)
    parser.add_argument("--minds_step_split", type=int, default=4)
    parser.add_argument("--minds_max_seq_length", type=int, default=200)
    parser.add_argument("--minds_reproduction_level", default="frontier_reproduction_full_run")
    parser.add_argument("--kt2_epochs", type=int, default=200)
    parser.add_argument("--kt2_batch_size", type=int, default=8)
    parser.add_argument("--kt2_hidden_dim", type=int, default=16)
    parser.add_argument("--kt2_max_train_cascades", type=int, default=6)
    parser.add_argument("--kt2_max_test_cascades", type=int, default=6)
    parser.add_argument("--kt2_max_sequence_len", type=int, default=8)
    parser.add_argument("--kt2_obs_ratios", default="0.1,0.3,0.5")
    parser.add_argument("--kt2_trend_steps", type=int, default=4)
    parser.add_argument("--kt2_negative_samples", type=int, default=32)
    parser.add_argument("--kt2_rollout_steps", type=int, default=5)
    parser.add_argument("--kt2_max_future_per_cascade", type=int, default=5)
    parser.add_argument("--kt2_global_top_n", type=int, default=50)
    parser.add_argument("--kt2_max_candidates", type=int, default=50)
    parser.add_argument("--kt2_negatives_per_cascade", type=int, default=8)
    parser.add_argument("--kt2_max_steps_per_epoch", type=int, default=0)
    parser.add_argument("--kt2_max_eval_cascades", type=int, default=0)
    parser.add_argument("--kt2_lambda_consistency", type=float, default=0.2)
    parser.add_argument("--kt2_lambda_forest_pg", type=float, default=0.05)
    parser.add_argument("--kt2_forest_pg_rollout_samples", type=int, default=2)
    parser.add_argument("--kt2_lambda_original_minds_module", type=float, default=0.01)
    parser.add_argument("--resume", action="store_true", help="Resume from existing output rows and skip completed dataset/seed pairs.")
    parser.add_argument("--max_pairs", type=int, default=0, help="Run at most this many new dataset/seed pairs in this invocation.")
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_arg_parser().parse_args(argv)
    payload = run_comparison(args)
    write_payload(payload, Path(args.out))
    print(json.dumps({"status": payload["status"], "overall_verdict": payload["overall_verdict"], "out": args.out}))
    return 0 if payload["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
