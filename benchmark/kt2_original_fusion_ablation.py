from __future__ import annotations

import argparse
import json
import math
import time
from pathlib import Path
from statistics import mean, pstdev
from typing import Dict, Iterable, List, Mapping, Optional, Sequence

from benchmark.adapters.kt2_joint_model import run_kt2_joint_model
from benchmark.kt2_original_fusion_experiment import (
    DEFAULT_CASFT_REPO,
    DEFAULT_FOREST_DATA,
    DEFAULT_FOREST_REPO,
    DEFAULT_MINDS_REPO,
    original_alignment_failures,
    original_subpath_failures,
)
from benchmark.schema import validate_benchmark_results


REQUIRED_VARIANTS = (
    "minds_baseline",
    "minds_plus_forest",
    "minds_plus_casft",
    "full_minds_forest_casft",
    "local_kt2_bridge",
)

METRIC_KEYS = (
    "msle",
    "mae",
    "rmse",
    "direction_accuracy",
    "candidate_recall_full",
    "hits@10",
    "hits@50",
    "hits@100",
    "map@100",
    "mrr",
    "macro_micro_consistency",
)

LOWER_IS_BETTER = {"msle", "mae", "rmse"}


def parse_csv(value: str) -> List[str]:
    return [item.strip() for item in str(value).split(",") if item.strip()]


def parse_float_csv(value: str) -> List[float]:
    return [float(item) for item in parse_csv(value)]


def variant_kwargs(variant: str, args: argparse.Namespace) -> Dict:
    """Return method switches for one KT2 original-architecture ablation row."""

    if variant not in REQUIRED_VARIANTS:
        raise ValueError(f"unknown KT2 original-fusion variant: {variant}")

    base = {
        "use_original_minds_components": variant in {
            "minds_baseline",
            "minds_plus_forest",
            "minds_plus_casft",
            "full_minds_forest_casft",
        },
        "use_original_minds_full_module": variant in {
            "minds_baseline",
            "minds_plus_forest",
            "minds_plus_casft",
            "full_minds_forest_casft",
        },
        "lambda_original_minds_module": float(args.lambda_original_minds_module),
        "minds_repo": str(args.minds_repo),
        "use_original_forest_components": variant in {"minds_plus_forest", "full_minds_forest_casft"},
        "forest_repo": str(args.forest_repo),
        "lambda_original_forest_ce": float(args.lambda_original_forest_ce),
        "lambda_original_forest_rl": float(args.lambda_original_forest_rl),
        "original_forest_rollout_samples": int(args.original_forest_rollout_samples),
        "original_forest_start_size": int(args.original_forest_start_size),
        "lambda_consistency": float(args.lambda_consistency),
        "lambda_forest_pg": float(args.lambda_forest_pg),
        "forest_pg_rollout_samples": int(args.forest_pg_rollout_samples),
        "use_original_casft_diffusion": variant in {"minds_plus_casft", "full_minds_forest_casft"},
        "use_original_casft_spatiotemporal": variant in {"minds_plus_casft", "full_minds_forest_casft"},
        "casft_repo": str(args.casft_repo),
        "lambda_original_casft_spatiotemporal": float(args.lambda_original_casft_spatiotemporal),
        "lambda_trend": float(args.lambda_trend),
        "lambda_diffusion": float(args.lambda_diffusion),
        "casft_diffusion_timesteps": int(args.casft_diffusion_timesteps),
        "casft_sampling_timesteps": int(args.casft_sampling_timesteps),
        "casft_spatiotemporal_interval_num": int(args.casft_spatiotemporal_interval_num),
        "casft_spatiotemporal_tpp_hdim": int(args.casft_spatiotemporal_tpp_hdim),
    }

    if variant == "minds_baseline":
        base.update(
            {
                "use_original_forest_components": False,
                "lambda_original_forest_ce": 0.0,
                "lambda_original_forest_rl": 0.0,
                "original_forest_rollout_samples": 0,
                "lambda_consistency": 0.0,
                "lambda_forest_pg": 0.0,
                "forest_pg_rollout_samples": 0,
                "use_original_casft_diffusion": False,
                "use_original_casft_spatiotemporal": False,
                "lambda_original_casft_spatiotemporal": 0.0,
                "lambda_trend": 0.0,
                "lambda_diffusion": 0.0,
            }
        )
    elif variant == "minds_plus_forest":
        base.update(
            {
                "use_original_casft_diffusion": False,
                "use_original_casft_spatiotemporal": False,
                "lambda_original_casft_spatiotemporal": 0.0,
                "lambda_trend": 0.0,
                "lambda_diffusion": 0.0,
            }
        )
    elif variant == "minds_plus_casft":
        base.update(
            {
                "use_original_forest_components": False,
                "lambda_original_forest_ce": 0.0,
                "lambda_original_forest_rl": 0.0,
                "original_forest_rollout_samples": 0,
                "lambda_consistency": 0.0,
                "lambda_forest_pg": 0.0,
                "forest_pg_rollout_samples": 0,
            }
        )
    elif variant == "local_kt2_bridge":
        base.update(
            {
                "use_original_minds_components": False,
                "use_original_minds_full_module": False,
                "lambda_original_minds_module": 0.0,
                "use_original_forest_components": False,
                "lambda_original_forest_ce": 0.0,
                "lambda_original_forest_rl": 0.0,
                "original_forest_rollout_samples": 0,
                "use_original_casft_diffusion": False,
                "use_original_casft_spatiotemporal": False,
                "lambda_original_casft_spatiotemporal": 0.0,
            }
        )
    return base


def run_one(args: argparse.Namespace, dataset: str, seed: int, obs_ratio: float, variant: str) -> Dict:
    data_dir = Path(args.forest_data_root) / dataset
    row = run_kt2_joint_model(
        data_dir,
        obs_ratio=obs_ratio,
        max_future_per_cascade=args.max_future_per_cascade,
        global_top_n=args.global_top_n,
        max_candidates=args.max_candidates,
        negatives_per_cascade=args.negatives_per_cascade,
        epochs=args.epochs,
        batch_size=args.batch_size,
        hidden_dim=args.hidden_dim,
        max_train_cascades=args.max_train_cascades,
        max_test_cascades=args.max_test_cascades,
        max_sequence_len=args.max_sequence_len,
        seed=seed,
        device=args.device,
        **variant_kwargs(variant, args),
    )
    row["ablation_variant"] = variant
    row["experiment_dataset"] = dataset
    row["experiment_seed"] = int(seed)
    row["experiment_obs_ratio"] = float(obs_ratio)
    row["experiment_config_id"] = str(args.config_id)
    row["reproduction_scope"] = "same_protocol_original_component_ablation_small_run"
    row["claim_boundary"] = (
        "Ablates MINDS baseline, FOREST macro/micro constraint, and CasFT continuous trend subpaths "
        "inside KT2JointModel. This is not full original-paper reproduction until full-run gates pass."
    )
    row["enabled_research_components"] = enabled_components(row, variant)
    row["disabled_research_components"] = disabled_components(row["enabled_research_components"])
    return row


def enabled_components(row: Mapping, variant: str) -> List[str]:
    enabled = []
    if variant in {"minds_baseline", "minds_plus_forest", "minds_plus_casft", "full_minds_forest_casft"}:
        enabled.append("MINDS original DynamicCasHGNN/Fusion/SharedLSTM/Module.forward auxiliary")
    if variant in {"minds_plus_forest", "full_minds_forest_casft"}:
        enabled.append("FOREST original RNNModel/RRModel auxiliary plus macro/micro constraint")
    if variant in {"minds_plus_casft", "full_minds_forest_casft"}:
        enabled.append("CasFT original diffusion/spatiotemporal auxiliary plus continuous trend")
    if variant == "local_kt2_bridge":
        enabled.append("KT2 local bridge only")
    return enabled


def disabled_components(enabled: Sequence[str]) -> List[str]:
    labels = {
        "MINDS": "MINDS original DynamicCasHGNN/Fusion/SharedLSTM/Module.forward auxiliary",
        "FOREST": "FOREST original RNNModel/RRModel auxiliary plus macro/micro constraint",
        "CasFT": "CasFT original diffusion/spatiotemporal auxiliary plus continuous trend",
    }
    enabled_text = " ".join(enabled)
    return [label for key, label in labels.items() if key not in enabled_text]


def row_key(row: Mapping) -> tuple[str, int, float, str, str]:
    return (
        str(row.get("experiment_dataset") or row.get("dataset") or ""),
        int(row.get("experiment_seed", row.get("seed", 0))),
        float(row.get("experiment_obs_ratio", row.get("obs_ratio", 0.3))),
        str(row.get("experiment_config_id", "default-ablation")),
        str(row.get("ablation_variant", "")),
    )


def normalize_row_identity(row: Dict) -> Dict:
    dataset, seed, obs_ratio, config_id, variant = row_key(row)
    row.setdefault("experiment_dataset", dataset)
    row.setdefault("experiment_seed", seed)
    row.setdefault("experiment_obs_ratio", obs_ratio)
    row.setdefault("experiment_config_id", config_id)
    row.setdefault("ablation_variant", variant)
    row.setdefault("obs_ratio", obs_ratio)
    return row


def load_existing_rows(path: Optional[Path]) -> List[Dict]:
    if path is None or not path.is_file():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    rows = payload.get("rows", []) if isinstance(payload, Mapping) else payload
    deduped: Dict[tuple[str, int, float, str, str], Dict] = {}
    for row in rows if isinstance(rows, list) else []:
        if isinstance(row, dict):
            normalize_row_identity(row)
            deduped[row_key(row)] = row
    return list(deduped.values())


def matrix_coverage(
    rows: Iterable[Mapping],
    datasets: Sequence[str],
    seeds: Sequence[int],
    obs_ratios: Sequence[float],
    variants: Sequence[str],
    config_id: str,
) -> Dict:
    expected = [
        (dataset, int(seed), float(obs_ratio), config_id, variant)
        for dataset in datasets
        for seed in seeds
        for obs_ratio in obs_ratios
        for variant in variants
    ]
    completed = {row_key(row) for row in rows if row.get("status") == "ok"}
    pending = [key for key in expected if key not in completed]
    return {
        "expected_runs": len(expected),
        "completed_expected_runs": len(expected) - len(pending),
        "coverage_ratio": ((len(expected) - len(pending)) / len(expected)) if expected else 0.0,
        "pending_keys": [
            {
                "dataset": dataset,
                "seed": seed,
                "obs_ratio": obs_ratio,
                "config_id": config,
                "ablation_variant": variant,
            }
            for dataset, seed, obs_ratio, config, variant in pending
        ],
    }


def metric_summary(rows: Iterable[Mapping]) -> Dict[str, Dict[str, float]]:
    summary: Dict[str, Dict[str, float]] = {}
    for metric in METRIC_KEYS:
        values = [
            float(row[metric])
            for row in rows
            if isinstance(row.get(metric), (int, float)) and math.isfinite(float(row[metric]))
        ]
        if values:
            summary[metric] = {
                "mean": mean(values),
                "std": pstdev(values) if len(values) > 1 else 0.0,
                "n": len(values),
            }
    return summary


def grouped_metric_summary(rows: Iterable[Mapping]) -> Dict[str, Dict[str, Dict[str, float]]]:
    grouped: Dict[str, List[Mapping]] = {}
    for row in rows:
        grouped.setdefault(str(row.get("ablation_variant", "unknown")), []).append(row)
    return {variant: metric_summary(variant_rows) for variant, variant_rows in sorted(grouped.items())}


def ablation_deltas(
    rows: Iterable[Mapping],
    baseline_variant: str = "minds_baseline",
    target_variant: str = "full_minds_forest_casft",
) -> Dict:
    grouped = grouped_metric_summary(rows)
    baseline = grouped.get(baseline_variant, {})
    target = grouped.get(target_variant, {})
    deltas = {}
    for metric in METRIC_KEYS:
        if metric not in baseline or metric not in target:
            continue
        raw_delta = target[metric]["mean"] - baseline[metric]["mean"]
        better_delta = -raw_delta if metric in LOWER_IS_BETTER else raw_delta
        deltas[metric] = {
            "baseline_mean": baseline[metric]["mean"],
            "target_mean": target[metric]["mean"],
            "raw_delta": raw_delta,
            "better_direction_delta": better_delta,
            "interpretation": "positive_supports_full_variant" if better_delta > 0 else "non_positive_or_inconclusive",
        }
    return deltas


def original_subpath_status(rows: Iterable[Mapping]) -> Dict:
    full_rows = [
        row
        for row in rows
        if row.get("ablation_variant") == "full_minds_forest_casft" and row.get("status") == "ok"
    ]
    subpath_missing = []
    alignment_missing = []
    for row in full_rows:
        identity = {
            "dataset": row.get("experiment_dataset") or row.get("dataset"),
            "seed": row.get("experiment_seed") or row.get("seed"),
            "obs_ratio": row.get("experiment_obs_ratio") or row.get("obs_ratio"),
        }
        for failure in original_subpath_failures(row):
            subpath_missing.append({**identity, **failure})
        for failure in original_alignment_failures(row):
            alignment_missing.append({**identity, **failure})
    return {
        "full_variant_rows": len(full_rows),
        "all_full_variant_original_subpaths_passed": bool(full_rows) and not subpath_missing,
        "all_full_variant_alignment_losses_recorded": bool(full_rows) and not alignment_missing,
        "subpath_missing": subpath_missing,
        "alignment_missing": alignment_missing,
    }


def build_summary(
    rows: List[Dict],
    datasets: Sequence[str],
    seeds: Sequence[int],
    obs_ratios: Sequence[float],
    variants: Sequence[str],
    config_id: str,
    started: float,
) -> Dict:
    schema = validate_benchmark_results(rows)
    coverage = matrix_coverage(rows, datasets, seeds, obs_ratios, variants, config_id)
    subpaths = original_subpath_status(rows)
    return {
        "schema": "cogguard.kt2.original_fusion_ablation.v1",
        "status": "ok" if schema["ok"] and not coverage["pending_keys"] else "partial",
        "reproduction_level": "kt2_original_fusion_ablation_small_run",
        "boundary": (
            "Same-protocol KT2 ablation for MINDS baseline, FOREST macro/micro constraint, "
            "and CasFT continuous trend migration. It is evidence for method design, not full original-paper reproduction."
        ),
        "datasets": list(datasets),
        "seeds": list(seeds),
        "obs_ratios": list(obs_ratios),
        "variants": list(variants),
        "config_id": config_id,
        "matrix_coverage": coverage,
        "schema_report": schema,
        "original_subpath_status": subpaths,
        "metric_summary_by_variant": grouped_metric_summary(rows),
        "full_vs_minds_baseline_delta": ablation_deltas(rows),
        "elapsed_s": round(time.time() - started, 3),
        "rows": rows,
    }


def write_outputs(summary: Mapping, out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    write_markdown(summary, out_path.with_suffix(".md"))


def write_markdown(summary: Mapping, path: Path) -> None:
    coverage = summary.get("matrix_coverage", {})
    subpaths = summary.get("original_subpath_status", {})
    lines = [
        "# KT2 Original-Fusion Ablation",
        "",
        f"- status: `{summary.get('status')}`",
        f"- reproduction_level: `{summary.get('reproduction_level')}`",
        f"- datasets: `{', '.join(summary.get('datasets', []))}`",
        f"- seeds: `{', '.join(str(seed) for seed in summary.get('seeds', []))}`",
        f"- obs_ratios: `{', '.join(str(value) for value in summary.get('obs_ratios', []))}`",
        f"- variants: `{', '.join(summary.get('variants', []))}`",
        f"- matrix_coverage: `{coverage.get('completed_expected_runs')}` / `{coverage.get('expected_runs')}`",
        "",
        "Boundary: " + str(summary.get("boundary")),
        "",
        "## Original Subpaths",
        "",
        f"- full_variant_rows: `{subpaths.get('full_variant_rows')}`",
        f"- all_full_variant_original_subpaths_passed: `{subpaths.get('all_full_variant_original_subpaths_passed')}`",
        f"- all_full_variant_alignment_losses_recorded: `{subpaths.get('all_full_variant_alignment_losses_recorded')}`",
        "",
        "## Variant Metrics",
        "",
        "| variant | metric | mean | std | n |",
        "|---|---|---:|---:|---:|",
    ]
    for variant, metrics in summary.get("metric_summary_by_variant", {}).items():
        for metric, stats in metrics.items():
            lines.append(f"| {variant} | {metric} | {stats['mean']:.6f} | {stats['std']:.6f} | {stats['n']} |")
    lines.extend(["", "## Full vs MINDS Baseline", "", "| metric | baseline | full | better-direction delta | interpretation |", "|---|---:|---:|---:|---|"])
    for metric, delta in summary.get("full_vs_minds_baseline_delta", {}).items():
        lines.append(
            "| {metric} | {baseline:.6f} | {target:.6f} | {delta:.6f} | {interp} |".format(
                metric=metric,
                baseline=delta["baseline_mean"],
                target=delta["target_mean"],
                delta=delta["better_direction_delta"],
                interp=delta["interpretation"],
            )
        )
    if coverage.get("pending_keys"):
        lines.extend(["", "## Pending", ""])
        for row in coverage["pending_keys"]:
            lines.append(f"- `{row}`")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_ablation(args: argparse.Namespace) -> Dict:
    datasets = parse_csv(args.datasets)
    seeds = [int(seed) for seed in parse_csv(args.seeds)]
    obs_ratios = parse_float_csv(args.obs_ratios or str(args.obs_ratio))
    variants = parse_csv(args.variants)
    unknown = [variant for variant in variants if variant not in REQUIRED_VARIANTS]
    if unknown:
        raise ValueError(f"unknown variants: {', '.join(unknown)}")
    started = time.time()
    out_path = Path(args.out) if args.out else None
    rows = load_existing_rows(out_path) if args.resume else []
    completed = {row_key(row) for row in rows}
    max_runs = int(args.max_runs or 0)
    new_runs = 0

    for dataset in datasets:
        for seed in seeds:
            for obs_ratio in obs_ratios:
                for variant in variants:
                    key = (dataset, seed, float(obs_ratio), str(args.config_id), variant)
                    if key in completed:
                        continue
                    if max_runs > 0 and new_runs >= max_runs:
                        return build_summary(rows, datasets, seeds, obs_ratios, variants, str(args.config_id), started)
                    row = run_one(args, dataset, seed, obs_ratio, variant)
                    rows.append(row)
                    completed.add(key)
                    new_runs += 1
                    if out_path:
                        write_outputs(build_summary(rows, datasets, seeds, obs_ratios, variants, str(args.config_id), started), out_path)

    return build_summary(rows, datasets, seeds, obs_ratios, variants, str(args.config_id), started)


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run KT2 MINDS/FOREST/CasFT original-fusion ablations.")
    parser.add_argument("--datasets", default="douban")
    parser.add_argument("--seeds", default="42")
    parser.add_argument("--forest_data_root", default=str(DEFAULT_FOREST_DATA))
    parser.add_argument("--minds_repo", default=str(DEFAULT_MINDS_REPO))
    parser.add_argument("--forest_repo", default=str(DEFAULT_FOREST_REPO))
    parser.add_argument("--casft_repo", default=str(DEFAULT_CASFT_REPO))
    parser.add_argument("--obs_ratio", type=float, default=0.3)
    parser.add_argument("--obs_ratios", default="")
    parser.add_argument("--variants", default=",".join(REQUIRED_VARIANTS))
    parser.add_argument("--max_future_per_cascade", type=int, default=20)
    parser.add_argument("--global_top_n", type=int, default=50)
    parser.add_argument("--max_candidates", type=int, default=50)
    parser.add_argument("--negatives_per_cascade", type=int, default=8)
    parser.add_argument("--epochs", type=int, default=200)
    parser.add_argument("--batch_size", type=int, default=8)
    parser.add_argument("--hidden_dim", type=int, default=16)
    parser.add_argument("--max_train_cascades", type=int, default=4)
    parser.add_argument("--max_test_cascades", type=int, default=4)
    parser.add_argument("--max_sequence_len", type=int, default=8)
    parser.add_argument("--lambda_original_minds_module", type=float, default=0.01)
    parser.add_argument("--lambda_consistency", type=float, default=0.2)
    parser.add_argument("--lambda_forest_pg", type=float, default=0.02)
    parser.add_argument("--forest_pg_rollout_samples", type=int, default=2)
    parser.add_argument("--lambda_original_forest_ce", type=float, default=0.02)
    parser.add_argument("--lambda_original_forest_rl", type=float, default=0.001)
    parser.add_argument("--original_forest_rollout_samples", type=int, default=1)
    parser.add_argument("--original_forest_start_size", type=int, default=3)
    parser.add_argument("--lambda_trend", type=float, default=0.4)
    parser.add_argument("--lambda_diffusion", type=float, default=0.05)
    parser.add_argument("--lambda_original_casft_spatiotemporal", type=float, default=0.01)
    parser.add_argument("--casft_diffusion_timesteps", type=int, default=2)
    parser.add_argument("--casft_sampling_timesteps", type=int, default=1)
    parser.add_argument("--casft_spatiotemporal_interval_num", type=int, default=4)
    parser.add_argument("--casft_spatiotemporal_tpp_hdim", type=int, default=16)
    parser.add_argument("--device", default="cpu", choices=["cpu", "cuda"])
    parser.add_argument("--out", default=str(Path("benchmark") / "kt2_original_fusion_ablation.json"))
    parser.add_argument("--config_id", default="ablation-small")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--max_runs", type=int, default=0)
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_arg_parser().parse_args(argv)
    summary = run_ablation(args)
    out_path = Path(args.out)
    write_outputs(summary, out_path)
    print(json.dumps({"status": summary["status"], "runs": len(summary["rows"]), "out": str(out_path)}))
    return 0 if summary["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
