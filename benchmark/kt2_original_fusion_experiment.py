from __future__ import annotations

import argparse
import json
import math
import time
from pathlib import Path
from statistics import mean, pstdev
from typing import Dict, Iterable, List, Mapping

from benchmark.adapters.kt2_joint_model import run_kt2_joint_model
from benchmark.schema import validate_benchmark_results


DEFAULT_FOREST_DATA = Path(r"G:\CISCN\dataset\forest-data")
DEFAULT_MINDS_REPO = Path(r"G:\CISCN\CogGuard\subsystems\kt2_repos\MINDS")
DEFAULT_FOREST_REPO = Path(r"G:\CISCN\CogGuard\subsystems\kt2_repos\FOREST")
DEFAULT_CASFT_REPO = Path(r"G:\CISCN\CogGuard\subsystems\kt2_repos\CasFT")
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

EXPECTED_ORIGINAL_STATUSES = {
    "minds_component_status": "original_dynamic_cas_hgnn_fusion_shared_lstm",
    "minds_module_runtime_status": "original_module_forward_auxiliary",
    "forest_runtime_status": "original_rnnmodel_rrmodel_auxiliary",
    "casft_diffusion_status": "original_gaussian_diffusion_st",
    "casft_spatiotemporal_runtime_status": "original_combined_spatiotemporal_model5_auxiliary",
    "casft_spatiotemporal_fusion_status": "original_combined_spatiotemporal_model5_main_fused",
}

EXPECTED_ALIGNMENT_FIELDS = {
    "minds_module_alignment_loss_mean": "MINDS Module.forward macro teacher alignment",
    "forest_size_alignment_loss_mean": "FOREST RRModel sampled EOS-size teacher alignment",
    "casft_spatiotemporal_alignment_loss_mean": "CasFT CombinedSpatiotemporalModel5 size teacher alignment",
}


def parse_csv(value: str) -> List[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def parse_float_csv(value: str) -> List[float]:
    return [float(item) for item in parse_csv(value)]


def experiment_config_id(args: argparse.Namespace) -> str:
    return str(getattr(args, "config_id", "") or "default-small")


def experiment_reproduction_level(args: argparse.Namespace) -> str:
    level = str(getattr(args, "reproduction_level", "") or "kt2_joint_model_small_run")
    if level == "frontier_reproduction_full_run":
        return "kt2_joint_model_full_run"
    return level


def metric_summary(rows: Iterable[Mapping]) -> Dict[str, Dict[str, float]]:
    rows = [row for row in rows if row.get("model") == "KT2JointModel" and row.get("status") == "ok"]
    summary: Dict[str, Dict[str, float]] = {}
    for key in METRIC_KEYS:
        values = [float(row[key]) for row in rows if isinstance(row.get(key), (int, float)) and math.isfinite(row[key])]
        if values:
            summary[key] = {
                "mean": mean(values),
                "std": pstdev(values) if len(values) > 1 else 0.0,
                "n": len(values),
            }
    return summary


def grouped_metric_summary(rows: Iterable[Mapping], group_key: str) -> Dict[str, Dict[str, Dict[str, float]]]:
    groups: Dict[str, List[Mapping]] = {}
    for row in rows:
        if row.get("model") != "KT2JointModel":
            continue
        groups.setdefault(str(row.get(group_key, "unknown")), []).append(row)
    return {group: metric_summary(group_rows) for group, group_rows in sorted(groups.items())}


def original_subpath_failures(row: Mapping) -> List[Dict[str, str]]:
    """Return missing original-paper subpaths for a KT2 original-fusion row."""

    if row.get("model") != "KT2JointModel" or row.get("status") != "ok":
        return []
    failures: List[Dict[str, str]] = []
    for key, expected in EXPECTED_ORIGINAL_STATUSES.items():
        actual = row.get(key)
        if actual != expected:
            failures.append(
                {
                    "field": key,
                    "expected": expected,
                    "actual": str(actual),
                }
            )
    return failures


def original_alignment_failures(row: Mapping) -> List[Dict[str, str]]:
    """Return missing original-component teacher alignment evidence."""

    if row.get("model") != "KT2JointModel" or row.get("status") != "ok":
        return []
    training = row.get("joint_training", {})
    if not isinstance(training, Mapping):
        return [{"field": "joint_training", "expected": "mapping with original-component alignment losses", "actual": str(type(training).__name__)}]
    failures: List[Dict[str, str]] = []
    for key, expected in EXPECTED_ALIGNMENT_FIELDS.items():
        value = training.get(key)
        if not isinstance(value, (int, float)) or not math.isfinite(float(value)):
            failures.append({"field": key, "expected": expected, "actual": str(value)})
    distillation = str(training.get("original_component_distillation", ""))
    if "teacher signals" not in distillation:
        failures.append(
            {
                "field": "original_component_distillation",
                "expected": "teacher signals boundary statement",
                "actual": distillation,
            }
        )
    return failures


def original_subpath_audit(rows: Iterable[Mapping]) -> Dict:
    """Summarize whether every successful row really ran and aligned original subpaths."""

    rows = [row for row in rows if row.get("model") == "KT2JointModel"]
    ok_rows = [row for row in rows if row.get("status") == "ok"]
    subpath_missing = []
    alignment_missing = []
    for row in ok_rows:
        identity = {"dataset": row.get("dataset"), "seed": row.get("seed")}
        for failure in original_subpath_failures(row):
            subpath_missing.append({**identity, **failure})
        for failure in original_alignment_failures(row):
            alignment_missing.append({**identity, **failure})
    return {
        "required_original_subpaths": EXPECTED_ORIGINAL_STATUSES,
        "required_alignment_fields": EXPECTED_ALIGNMENT_FIELDS,
        "rows_total": len(rows),
        "rows_ok": len(ok_rows),
        "rows_with_all_original_subpaths": len(ok_rows) - len({(item.get("dataset"), item.get("seed")) for item in subpath_missing}),
        "rows_with_all_alignment_losses": len(ok_rows) - len({(item.get("dataset"), item.get("seed")) for item in alignment_missing}),
        "all_original_subpaths_passed": bool(ok_rows) and not subpath_missing,
        "all_alignment_losses_recorded": bool(ok_rows) and not alignment_missing,
        "subpath_missing": subpath_missing,
        "alignment_missing": alignment_missing,
    }


def matrix_coverage(rows: Iterable[Mapping], datasets: List[str], seeds: List[int], obs_ratios: List[float], config_id: str) -> Dict:
    expected = [(dataset, seed, float(obs_ratio), config_id) for dataset in datasets for seed in seeds for obs_ratio in obs_ratios]
    completed = {row_key(row) for row in rows}
    pending = [key for key in expected if key not in completed]
    completed_expected = [key for key in expected if key in completed]
    return {
        "expected_runs": len(expected),
        "completed_expected_runs": len(completed_expected),
        "coverage_ratio": (len(completed_expected) / len(expected)) if expected else 0.0,
        "completed_keys": [
            {"dataset": dataset, "seed": seed, "obs_ratio": obs_ratio, "config_id": config}
            for dataset, seed, obs_ratio, config in completed_expected
        ],
        "pending_keys": [
            {"dataset": dataset, "seed": seed, "obs_ratio": obs_ratio, "config_id": config}
            for dataset, seed, obs_ratio, config in pending
        ],
    }


def build_summary(
    rows: List[Dict],
    failures: List[Dict],
    datasets: List[str],
    seeds: List[int],
    obs_ratios: List[float],
    config_id: str,
    reproduction_level: str,
    started: float,
) -> Dict:
    schema = validate_benchmark_results(rows)
    subpath_audit = original_subpath_audit(rows)
    coverage = matrix_coverage(rows, datasets, seeds, obs_ratios, config_id)
    if reproduction_level == "kt2_joint_model_full_run":
        boundary = (
            "Runs KT2JointModel with upstream MINDS Module.forward, FOREST RNNModel/RRModel, "
            "and CasFT GaussianDiffusion_ST plus CombinedSpatiotemporalModel5 auxiliary and main-fusion subpaths as a "
            "same-protocol KT2 joint-model full-run evidence row. This is KT2's integrated model evidence, "
            "not a frontier-paper full reproduction label; completion still requires same-protocol MINDS, "
            "FOREST, and CasFT baseline full-run comparison."
        )
    else:
        boundary = (
            "Runs KT2JointModel with upstream MINDS Module.forward, FOREST RNNModel/RRModel, "
            "and CasFT GaussianDiffusion_ST plus CombinedSpatiotemporalModel5 auxiliary and main-fusion subpaths. "
            "This is a repeatable original-subpath fusion experiment, not full original-paper data protocol or full-run reproduction."
        )
    return {
        "schema": "cogguard.kt2.original_fusion_experiment.v1",
        "status": "ok" if schema.get("ok") and not failures and not coverage["pending_keys"] else "partial",
        "reproduction_level": reproduction_level,
        "boundary": boundary,
        "required_original_subpaths": EXPECTED_ORIGINAL_STATUSES,
        "original_subpath_audit": subpath_audit,
        "matrix_coverage": coverage,
        "datasets": datasets,
        "seeds": seeds,
        "obs_ratios": obs_ratios,
        "config_id": config_id,
        "runs": len(rows),
        "failures": failures,
        "schema_report": schema,
        "metric_summary": metric_summary(rows),
        "by_dataset": grouped_metric_summary(rows, "dataset"),
        "by_seed": grouped_metric_summary(rows, "seed"),
        "elapsed_s": round(time.time() - started, 3),
        "rows": rows,
    }


def write_outputs(summary: Mapping, out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    write_markdown(summary, out_path.with_suffix(".md"))


def run_one(args: argparse.Namespace, dataset: str, seed: int, obs_ratio: float) -> Dict:
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
                lambda_consistency=args.lambda_consistency,
                lambda_forest_pg=args.lambda_forest_pg,
                forest_pg_rollout_samples=args.forest_pg_rollout_samples,
                use_original_minds_components=True,
                use_original_minds_full_module=True,
                lambda_original_minds_module=args.lambda_original_minds_module,
                minds_repo=args.minds_repo,
                use_original_forest_components=True,
                forest_repo=args.forest_repo,
                lambda_original_forest_ce=args.lambda_original_forest_ce,
                lambda_original_forest_rl=args.lambda_original_forest_rl,
                original_forest_rollout_samples=args.original_forest_rollout_samples,
                original_forest_start_size=args.original_forest_start_size,
                use_original_casft_diffusion=True,
                use_original_casft_spatiotemporal=True,
                casft_repo=args.casft_repo,
                casft_diffusion_timesteps=args.casft_diffusion_timesteps,
                casft_sampling_timesteps=args.casft_sampling_timesteps,
                lambda_original_casft_spatiotemporal=args.lambda_original_casft_spatiotemporal,
                casft_spatiotemporal_interval_num=args.casft_spatiotemporal_interval_num,
                casft_spatiotemporal_tpp_hdim=args.casft_spatiotemporal_tpp_hdim,
                seed=seed,
                device=args.device,
            )
    row["experiment_dataset"] = dataset
    row["experiment_seed"] = seed
    row["experiment_obs_ratio"] = float(obs_ratio)
    row["experiment_config_id"] = experiment_config_id(args)
    row["reproduction_level"] = experiment_reproduction_level(args)
    if row["reproduction_level"] == "kt2_joint_model_full_run":
        row["full_run_protocol"] = {
            "same_protocol": True,
            "original_subpaths_passed": not original_subpath_failures(row),
            "teacher_alignment_recorded": not original_alignment_failures(row),
            "config_id": experiment_config_id(args),
            "datasets": parse_csv(args.datasets),
            "seeds": [int(value) for value in parse_csv(args.seeds)],
            "obs_ratios": parse_float_csv(getattr(args, "obs_ratios", "") or str(getattr(args, "obs_ratio", 0.3))),
        }
    return row


def record_failures_for_row(row: Mapping, dataset: str, seed: int, obs_ratio: float, config_id: str, failures: List[Dict]) -> None:
    identity = {"dataset": dataset, "seed": seed, "obs_ratio": float(obs_ratio), "config_id": config_id}
    if row.get("status") != "ok":
        failures.append(
            {
                **identity,
                "status": row.get("status"),
                "note": row.get("note"),
            }
        )
    else:
        subpath_failures = original_subpath_failures(row)
        if subpath_failures:
            failures.append(
                {
                    **identity,
                    "status": "original_subpath_incomplete",
                    "note": "One or more required upstream MINDS/FOREST/CasFT original subpaths did not run.",
                    "subpath_failures": subpath_failures,
                }
            )
        alignment_failures = original_alignment_failures(row)
        if alignment_failures:
            failures.append(
                {
                    **identity,
                    "status": "original_alignment_incomplete",
                    "note": "One or more upstream MINDS/FOREST/CasFT teacher alignment losses were not recorded.",
                    "alignment_failures": alignment_failures,
                }
            )


def row_key(row: Mapping) -> tuple[str, int, float, str]:
    dataset = str(row.get("experiment_dataset") or row.get("dataset") or "")
    seed_value = row.get("experiment_seed", row.get("seed", 0))
    obs_ratio = float(row.get("experiment_obs_ratio", row.get("obs_ratio", 0.3)))
    config_id = str(row.get("experiment_config_id", "default-small"))
    return dataset, int(seed_value), obs_ratio, config_id


def normalize_row_identity(row: Dict) -> Dict:
    dataset, seed, obs_ratio, config_id = row_key(row)
    row.setdefault("experiment_dataset", dataset)
    row.setdefault("experiment_seed", seed)
    row.setdefault("experiment_obs_ratio", obs_ratio)
    row.setdefault("experiment_config_id", config_id)
    row.setdefault("obs_ratio", obs_ratio)
    return row


def load_existing_rows(out_path: Path) -> List[Dict]:
    if not out_path.is_file():
        return []
    try:
        payload = json.loads(out_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    rows = payload.get("rows", [])
    if not isinstance(rows, list):
        return []
    deduped: Dict[tuple[str, int, float, str], Dict] = {}
    for row in rows:
        if isinstance(row, dict):
            normalize_row_identity(row)
            deduped[row_key(row)] = row
    return list(deduped.values())


def rebuild_failures(rows: Iterable[Mapping]) -> List[Dict]:
    failures: List[Dict] = []
    for row in rows:
        dataset, seed, obs_ratio, config_id = row_key(row)
        record_failures_for_row(row, dataset, seed, obs_ratio, config_id, failures)
    return failures

def run_experiment(args: argparse.Namespace) -> Dict:
    datasets = parse_csv(args.datasets)
    seeds = [int(seed) for seed in parse_csv(args.seeds)]
    obs_ratios = parse_float_csv(getattr(args, "obs_ratios", "") or str(getattr(args, "obs_ratio", 0.3)))
    config_id = experiment_config_id(args)
    reproduction_level = experiment_reproduction_level(args)
    started = time.time()
    out_path = Path(args.out) if getattr(args, "out", None) else None
    rows: List[Dict] = load_existing_rows(out_path) if out_path is not None and getattr(args, "resume", False) else []
    failures: List[Dict] = rebuild_failures(rows)
    completed = {row_key(row) for row in rows}
    max_runs = int(getattr(args, "max_runs", 0) or 0)
    new_runs = 0

    for dataset in datasets:
        for seed in seeds:
            for obs_ratio in obs_ratios:
                key = (dataset, seed, float(obs_ratio), config_id)
                if key in completed:
                    continue
                if max_runs > 0 and new_runs >= max_runs:
                    return build_summary(rows, failures, datasets, seeds, obs_ratios, config_id, reproduction_level, started)
                row = run_one(args, dataset, seed, obs_ratio)
                rows.append(row)
                completed.add(key)
                new_runs += 1
                record_failures_for_row(row, dataset, seed, obs_ratio, config_id, failures)
                if out_path is not None:
                    write_outputs(build_summary(rows, failures, datasets, seeds, obs_ratios, config_id, reproduction_level, started), out_path)

    return build_summary(rows, failures, datasets, seeds, obs_ratios, config_id, reproduction_level, started)


def write_markdown(summary: Mapping, path: Path) -> None:
    audit = summary.get("original_subpath_audit", {})
    coverage = summary.get("matrix_coverage", {})
    lines = [
        "# KT2 Original-Subpath Fusion Experiment",
        "",
        f"- status: `{summary.get('status')}`",
        f"- reproduction_level: `{summary.get('reproduction_level')}`",
        f"- datasets: `{', '.join(summary.get('datasets', []))}`",
        f"- seeds: `{', '.join(str(seed) for seed in summary.get('seeds', []))}`",
        f"- obs_ratios: `{', '.join(str(value) for value in summary.get('obs_ratios', []))}`",
        f"- config_id: `{summary.get('config_id')}`",
        f"- runs: `{summary.get('runs')}`",
        f"- elapsed_s: `{summary.get('elapsed_s')}`",
        "",
        "Boundary: " + str(summary.get("boundary")),
        "",
        "## Original-Subpath Audit",
        "",
        f"- all_original_subpaths_passed: `{audit.get('all_original_subpaths_passed')}`",
        f"- all_alignment_losses_recorded: `{audit.get('all_alignment_losses_recorded')}`",
        f"- rows_ok: `{audit.get('rows_ok')}` / `{audit.get('rows_total')}`",
        f"- matrix_coverage: `{coverage.get('completed_expected_runs')}` / `{coverage.get('expected_runs')}`",
        f"- pending_keys: `{coverage.get('pending_keys')}`",
        "",
        "## Metric Summary",
        "",
        "| metric | mean | std | n |",
        "|---|---:|---:|---:|",
    ]
    for metric, stats in summary.get("metric_summary", {}).items():
        lines.append(f"| {metric} | {stats['mean']:.6f} | {stats['std']:.6f} | {stats['n']} |")
    lines.extend(["", "## Schema", "", f"- ok: `{summary.get('schema_report', {}).get('ok')}`"])
    for error in summary.get("schema_report", {}).get("errors", []):
        lines.append(f"- error: {error}")
    for warning in summary.get("schema_report", {}).get("warnings", []):
        lines.append(f"- warning: {warning}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--datasets", default="douban,twitter,memetracker")
    parser.add_argument("--seeds", default="42,43")
    parser.add_argument("--forest_data_root", default=str(DEFAULT_FOREST_DATA))
    parser.add_argument("--minds_repo", default=str(DEFAULT_MINDS_REPO))
    parser.add_argument("--forest_repo", default=str(DEFAULT_FOREST_REPO))
    parser.add_argument("--casft_repo", default=str(DEFAULT_CASFT_REPO))
    parser.add_argument("--obs_ratio", type=float, default=0.3)
    parser.add_argument("--obs_ratios", default="", help="Comma-separated observation ratios. Defaults to --obs_ratio for backward compatibility.")
    parser.add_argument("--max_future_per_cascade", type=int, default=20)
    parser.add_argument("--global_top_n", type=int, default=80)
    parser.add_argument("--max_candidates", type=int, default=80)
    parser.add_argument("--negatives_per_cascade", type=int, default=8)
    parser.add_argument("--epochs", type=int, default=200)
    parser.add_argument("--batch_size", type=int, default=8)
    parser.add_argument("--hidden_dim", type=int, default=16)
    parser.add_argument("--max_train_cascades", type=int, default=6)
    parser.add_argument("--max_test_cascades", type=int, default=6)
    parser.add_argument("--max_sequence_len", type=int, default=8)
    parser.add_argument("--lambda_consistency", type=float, default=0.2)
    parser.add_argument("--lambda_forest_pg", type=float, default=0.02)
    parser.add_argument("--forest_pg_rollout_samples", type=int, default=2)
    parser.add_argument("--lambda_original_minds_module", type=float, default=0.01)
    parser.add_argument("--lambda_original_forest_ce", type=float, default=0.02)
    parser.add_argument("--lambda_original_forest_rl", type=float, default=0.001)
    parser.add_argument("--original_forest_rollout_samples", type=int, default=1)
    parser.add_argument("--original_forest_start_size", type=int, default=3)
    parser.add_argument("--lambda_original_casft_spatiotemporal", type=float, default=0.01)
    parser.add_argument("--casft_diffusion_timesteps", type=int, default=2)
    parser.add_argument("--casft_sampling_timesteps", type=int, default=1)
    parser.add_argument("--casft_spatiotemporal_interval_num", type=int, default=4)
    parser.add_argument("--casft_spatiotemporal_tpp_hdim", type=int, default=16)
    parser.add_argument("--device", default="cpu", choices=["cpu", "cuda"])
    parser.add_argument("--out", default=str(Path("benchmark") / "kt2_original_fusion_experiment.json"))
    parser.add_argument("--config_id", default="default-small", help="Experiment configuration id included in resume keys.")
    parser.add_argument(
        "--reproduction_level",
        default="kt2_joint_model_small_run",
        choices=["kt2_joint_model_small_run", "kt2_joint_model_full_run", "frontier_reproduction_full_run"],
        help=(
            "Use kt2_joint_model_full_run for an explicit KT2 same-protocol full-run matrix. "
            "The legacy frontier_reproduction_full_run input is normalized for backward compatibility."
        ),
    )
    parser.add_argument("--resume", action="store_true", help="Reuse completed (dataset, seed) rows from --out before running new work.")
    parser.add_argument("--max_runs", type=int, default=0, help="Maximum number of new dataset/seed runs to execute in this invocation; 0 means all pending.")
    args = parser.parse_args()

    summary = run_experiment(args)
    out_path = Path(args.out)
    write_outputs(summary, out_path)
    print(json.dumps({"status": summary["status"], "runs": summary["runs"], "out": str(out_path)}))


if __name__ == "__main__":
    main()
