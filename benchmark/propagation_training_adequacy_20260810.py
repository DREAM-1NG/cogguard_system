from __future__ import annotations

import argparse
import json
import math
import sys
import time
from collections import defaultdict
from pathlib import Path
from statistics import mean, pstdev
from typing import Dict, Iterable, List, Mapping, Sequence, Tuple

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from benchmark.adapters.cascade_io import load_forest_split
from benchmark.adapters.kt2_sequence_joint_model import run_kt2_sequence_joint_model


DEFAULT_FOREST_DATA = Path(r"G:\CISCN\dataset\forest-data")
DEFAULT_DOC_DIR = Path(
    r"G:\CISCN\CogGuard\.worktrees\refactor-system\system\doc\research\propagation_paper_deep_reads"
)
PROTOCOL_ID = "propagation_training_adequacy_forestsplit_v1"
MODEL_VARIANTS = {
    "Ours": "ours",
    "MINDS": "minds_shared_backbone",
}
LOWER_IS_BETTER = {"msle", "mae", "rmse", "trend_mae", "trend_rmse", "final_epoch_loss"}
HIGHER_IS_BETTER = {"hits@100", "mrr", "ndcg@100", "candidate_recall_full", "direction_accuracy"}
SUMMARY_METRICS = (
    "msle",
    "mae",
    "trend_mae",
    "hits@100",
    "mrr",
    "ndcg@100",
    "candidate_recall_full",
    "final_epoch_loss",
)


def parse_csv(value: str) -> List[str]:
    return [item.strip() for item in str(value or "").split(",") if item.strip()]


def parse_int_csv(value: str) -> List[int]:
    return [int(item) for item in parse_csv(value)]


def finite(value) -> float | None:
    if isinstance(value, (int, float)) and math.isfinite(float(value)):
        return float(value)
    return None


def metric_value(row: Mapping, metric: str) -> float | None:
    if metric == "final_epoch_loss":
        curve = row.get("training_loss_curve") or []
        if isinstance(curve, list) and curve:
            value = finite(curve[-1])
            if value is not None:
                return value
    return finite(row.get(metric))


def mean_std(values: Sequence[float]) -> Tuple[float | None, float | None, int]:
    clean = [float(value) for value in values if math.isfinite(float(value))]
    if not clean:
        return None, None, 0
    return mean(clean), pstdev(clean) if len(clean) > 1 else 0.0, len(clean)


def dataset_expected_counts(args: argparse.Namespace, dataset: str) -> Dict[str, int]:
    train, valid, test = load_forest_split(Path(args.forest_data_root) / dataset)
    eval_cascades = test or valid
    train_limit = int(args.train_cascades)
    eval_limit = int(args.eval_cascades)
    return {
        "train_available": len(train),
        "valid_available": len(valid),
        "test_available": len(test),
        "train_used_expected": len(train[:train_limit]) if train_limit > 0 else len(train),
        "eval_used_expected": len(eval_cascades[:eval_limit]) if eval_limit > 0 else len(eval_cascades),
        "eval_split": "test" if test else "valid",
    }


def row_key(row: Mapping) -> tuple:
    return (
        str(row.get("dataset", "")),
        str(row.get("model", "")),
        int(row.get("seed", 0) or 0),
        int(row.get("epochs", 0) or 0),
        int(row.get("hidden_dim", 0) or 0),
        int(row.get("max_sequence_len", 0) or 0),
        int(row.get("train_cascades_used", 0) or 0),
        int(row.get("eval_cascades_used", 0) or 0),
    )


def load_existing(path: Path) -> List[Dict]:
    if not path.is_file():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    rows = payload.get("rows", [])
    if not isinstance(rows, list):
        return []
    dedup: Dict[tuple, Dict] = {}
    for row in rows:
        if isinstance(row, dict):
            dedup[row_key(row)] = row
    return list(dedup.values())


def requested_jobs(args: argparse.Namespace) -> List[Dict]:
    jobs: List[Dict] = []
    for dataset in parse_csv(args.datasets):
        for seed in parse_int_csv(args.seeds):
            for model in parse_csv(args.models):
                for epochs in parse_int_csv(args.epoch_grid):
                    for hidden_dim in parse_int_csv(args.hidden_dims):
                        for max_sequence_len in parse_int_csv(args.max_sequence_lens):
                            jobs.append(
                                {
                                    "dataset": dataset,
                                    "seed": seed,
                                    "model": model,
                                    "epochs": epochs,
                                    "hidden_dim": hidden_dim,
                                    "max_sequence_len": max_sequence_len,
                                }
                            )
    return jobs


def expected_key(job: Mapping, args: argparse.Namespace) -> tuple:
    counts = dataset_expected_counts(args, str(job["dataset"]))
    return (
        str(job["dataset"]),
        str(job["model"]),
        int(job["seed"]),
        int(job["epochs"]),
        int(job["hidden_dim"]),
        int(job["max_sequence_len"]),
        int(counts["train_used_expected"]),
        int(counts["eval_used_expected"]),
    )


def run_one(args: argparse.Namespace, job: Mapping) -> Dict:
    model = str(job["model"])
    if model not in MODEL_VARIANTS:
        return {
            **job,
            "status": "not_comparable",
            "reason": f"No sequence model variant is registered for {model}.",
        }
    checkpoint_dir = Path(args.training_checkpoint_dir)
    checkpoint_path = checkpoint_dir / (
        f"{job['dataset']}_{model}_seed{job['seed']}_ep{job['epochs']}"
        f"_h{job['hidden_dim']}_seq{job['max_sequence_len']}"
        f"_train{int(args.train_cascades)}_eval{int(args.eval_cascades)}.pt"
    )
    row = run_kt2_sequence_joint_model(
        Path(args.forest_data_root) / str(job["dataset"]),
        dataset=str(job["dataset"]),
        model_name=model,
        model_variant=MODEL_VARIANTS[model],
        obs_ratios=[float(item) for item in parse_csv(args.obs_ratios)],
        epochs=int(job["epochs"]),
        batch_size=int(args.batch_size),
        hidden_dim=int(job["hidden_dim"]),
        max_train_cascades=int(args.train_cascades),
        max_test_cascades=int(args.eval_cascades),
        max_sequence_len=int(job["max_sequence_len"]),
        trend_steps=int(args.trend_steps),
        negative_samples=int(args.negative_samples),
        rollout_steps=int(args.rollout_steps),
        progress_interval=int(args.progress_interval),
        seed=int(job["seed"]),
        device=args.device,
        training_checkpoint_path=str(checkpoint_path),
        training_checkpoint_interval=int(args.training_checkpoint_interval),
    )
    row["adequacy_protocol_id"] = PROTOCOL_ID
    row["training_adequacy_scope"] = "epoch_learning_curve"
    row["training_adequacy_claim_boundary"] = (
        "This row is for training sufficiency diagnosis. It is not an original-paper SOTA claim."
    )
    counts = dataset_expected_counts(args, str(job["dataset"]))
    row["training_adequacy_counts"] = counts
    row["fair_protocol_passed"] = bool(
        row.get("status") == "ok"
        and int(row.get("epochs", -1)) == int(job["epochs"])
        and int(row.get("hidden_dim", -1)) == int(job["hidden_dim"])
        and int(row.get("max_sequence_len", -1)) == int(job["max_sequence_len"])
        and int(row.get("train_cascades_used", -1)) == int(counts["train_used_expected"])
        and int(row.get("eval_cascades_used", -1)) == int(counts["eval_used_expected"])
        and row.get("candidate_protocol_audit", {}).get("leakage_check_passed") is True
    )
    return row


def summarize(rows: Iterable[Mapping]) -> List[Dict]:
    grouped: Dict[tuple, Dict[str, List[float]]] = defaultdict(lambda: defaultdict(list))
    for row in rows:
        if row.get("status") != "ok" or not row.get("fair_protocol_passed"):
            continue
        key = (
            str(row.get("dataset")),
            str(row.get("model")),
            int(row.get("epochs", 0) or 0),
            int(row.get("hidden_dim", 0) or 0),
            int(row.get("max_sequence_len", 0) or 0),
        )
        for metric in SUMMARY_METRICS:
            value = metric_value(row, metric)
            if value is not None:
                grouped[key][metric].append(value)
    summary: List[Dict] = []
    for (dataset, model, epochs, hidden_dim, max_sequence_len), values_by_metric in sorted(grouped.items()):
        record = {
            "dataset": dataset,
            "model": model,
            "epochs": epochs,
            "hidden_dim": hidden_dim,
            "max_sequence_len": max_sequence_len,
        }
        for metric in SUMMARY_METRICS:
            metric_mean, metric_std, metric_n = mean_std(values_by_metric.get(metric, []))
            if metric_n:
                record[f"{metric}_mean"] = metric_mean
                record[f"{metric}_std"] = metric_std
                record[f"{metric}_n"] = metric_n
        summary.append(record)
    return summary


def relative_delta(first: float | None, last: float | None, *, lower_is_better: bool) -> float | None:
    if first is None or last is None or abs(first) < 1e-12:
        return None
    if lower_is_better:
        return (first - last) / abs(first)
    return (last - first) / abs(first)


def analyze_learning_curves(summary: Sequence[Mapping]) -> List[Dict]:
    grouped: Dict[tuple, List[Mapping]] = defaultdict(list)
    for row in summary:
        grouped[(row["dataset"], row["model"], row["hidden_dim"], row["max_sequence_len"])].append(row)
    analyses: List[Dict] = []
    for key, rows in sorted(grouped.items()):
        ordered = sorted(rows, key=lambda item: int(item["epochs"]))
        if len(ordered) < 2:
            continue
        first, last = ordered[0], ordered[-1]
        record = {
            "dataset": key[0],
            "model": key[1],
            "hidden_dim": key[2],
            "max_sequence_len": key[3],
            "first_epoch": first["epochs"],
            "last_epoch": last["epochs"],
            "signals": {},
        }
        improvement_signals = 0
        degradation_signals = 0
        for metric in SUMMARY_METRICS:
            first_value = finite(first.get(f"{metric}_mean"))
            last_value = finite(last.get(f"{metric}_mean"))
            lower = metric in LOWER_IS_BETTER
            delta = relative_delta(first_value, last_value, lower_is_better=lower)
            if delta is None:
                continue
            record["signals"][metric] = {
                "first": first_value,
                "last": last_value,
                "relative_improvement": delta,
            }
            if delta > 0.05:
                improvement_signals += 1
            elif delta < -0.05:
                degradation_signals += 1
        if improvement_signals >= 2:
            verdict = "undertraining_likely"
        elif degradation_signals >= 2:
            verdict = "overfit_or_metric_conflict_possible"
        else:
            verdict = "plateau_or_mixed"
        record["verdict"] = verdict
        record["interpretation"] = {
            "undertraining_likely": "Later epochs improve multiple primary signals by more than 5%; the 5-epoch result is probably premature.",
            "overfit_or_metric_conflict_possible": "Training longer worsens multiple held-out metrics; inspect validation selection and loss balance.",
            "plateau_or_mixed": "More epochs do not clearly improve enough signals; remaining weakness may come from protocol, candidates, capacity, or loss design.",
        }[verdict]
        analyses.append(record)
    return analyses


def protocol_audit(rows: Sequence[Mapping], jobs: Sequence[Mapping], args: argparse.Namespace) -> Dict:
    ok_keys = {row_key(row) for row in rows if row.get("status") == "ok" and row.get("fair_protocol_passed")}
    missing = [job for job in jobs if expected_key(job, args) not in ok_keys]
    return {
        "passed": not missing,
        "row_count": len(rows),
        "fair_ok_count": len(ok_keys),
        "requested_count": len(jobs),
        "missing_or_nonfair_count": len(missing),
        "missing_or_nonfair_rows": missing[:20],
    }


def fmt(value) -> str:
    if isinstance(value, (int, float)) and math.isfinite(float(value)):
        return f"{float(value):.4f}"
    return "-"


def build_payload(args: argparse.Namespace, rows: Sequence[Mapping], started: float) -> Dict:
    jobs = requested_jobs(args)
    audit = protocol_audit(rows, jobs, args)
    summary = summarize(rows)
    return {
        "schema": "cogguard.propagation.training_adequacy.v1",
        "status": "ok" if audit["passed"] else "partial",
        "protocol_id": PROTOCOL_ID,
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "elapsed_s": round(time.time() - started, 1),
        "datasets": parse_csv(args.datasets),
        "seeds": parse_int_csv(args.seeds),
        "models": parse_csv(args.models),
        "epoch_grid": parse_int_csv(args.epoch_grid),
        "hidden_dims": parse_int_csv(args.hidden_dims),
        "max_sequence_lens": parse_int_csv(args.max_sequence_lens),
        "train_cascades": int(args.train_cascades),
        "eval_cascades": int(args.eval_cascades),
        "batch_size": int(args.batch_size),
        "claim_boundary": (
            "This experiment diagnoses whether 200-epoch sequence-model training is sufficient under the selected "
            "cascade caps and capacity. It must be reported before any SOTA comparison and cannot by itself prove "
            "original-paper-level performance."
        ),
        "adequacy_criteria": {
            "undertraining_likely": "Later epochs improve at least two primary signals by more than 5%.",
            "plateau_or_mixed": "Longer training does not consistently improve held-out macro/micro signals.",
            "overfit_or_metric_conflict_possible": "Longer training degrades multiple held-out metrics despite training progress.",
        },
        "protocol_audit": audit,
        "summary": summary,
        "learning_curve_analysis": analyze_learning_curves(summary),
        "rows": list(rows),
    }


def write_markdown(payload: Mapping, path: Path) -> None:
    lines = [
        "# Propagation Training Adequacy 2026-08-10",
        "",
        f"- status: `{payload.get('status')}`",
        f"- protocol_id: `{payload.get('protocol_id')}`",
        f"- datasets: `{', '.join(payload.get('datasets', []))}`",
        f"- seeds: `{', '.join(str(seed) for seed in payload.get('seeds', []))}`",
        f"- models: `{', '.join(payload.get('models', []))}`",
        f"- epoch_grid: `{', '.join(str(epoch) for epoch in payload.get('epoch_grid', []))}`",
        f"- train/eval cascades: `{payload.get('train_cascades')}/{payload.get('eval_cascades')}`",
        "",
        str(payload.get("claim_boundary")),
        "",
        "## Protocol Audit",
        "",
        "| item | value |",
        "|---|---:|",
    ]
    audit = payload.get("protocol_audit", {})
    for key in ("passed", "row_count", "fair_ok_count", "requested_count", "missing_or_nonfair_count"):
        lines.append(f"| {key} | `{audit.get(key)}` |")

    lines.extend(
        [
            "",
            "## Learning Curve Summary",
            "",
            "| Dataset | Model | Epochs | Hidden | MSLE | MAE | Trend MAE | Hits@100 | MRR | NDCG@100 | Final Loss |",
            "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for row in payload.get("summary", []):
        lines.append(
            "| {dataset} | {model} | {epochs} | {hidden_dim} | {msle} | {mae} | {trend_mae} | {hits} | {mrr} | {ndcg} | {loss} |".format(
                dataset=row.get("dataset"),
                model=row.get("model"),
                epochs=row.get("epochs"),
                hidden_dim=row.get("hidden_dim"),
                msle=fmt(row.get("msle_mean")),
                mae=fmt(row.get("mae_mean")),
                trend_mae=fmt(row.get("trend_mae_mean")),
                hits=fmt(row.get("hits@100_mean")),
                mrr=fmt(row.get("mrr_mean")),
                ndcg=fmt(row.get("ndcg@100_mean")),
                loss=fmt(row.get("final_epoch_loss_mean")),
            )
        )

    lines.extend(
        [
            "",
            "## Adequacy Verdicts",
            "",
            "| Dataset | Model | Epoch Range | Verdict | Interpretation |",
            "|---|---|---|---|---|",
        ]
    )
    for item in payload.get("learning_curve_analysis", []):
        lines.append(
            "| {dataset} | {model} | {first}-{last} | {verdict} | {interpretation} |".format(
                dataset=item.get("dataset"),
                model=item.get("model"),
                first=item.get("first_epoch"),
                last=item.get("last_epoch"),
                verdict=item.get("verdict"),
                interpretation=str(item.get("interpretation", "")).replace("|", "/"),
            )
        )

    lines.extend(
        [
            "",
            "## Reporting Rule",
            "",
            "- If `undertraining_likely` appears, the corresponding shorter-run result must be treated as premature.",
            "- If `plateau_or_mixed` appears, inspect candidate coverage, loss conflict, model capacity, and protocol mismatch before increasing epochs further.",
            "- SOTA comparison should only resume after this report has at least one stable multi-seed epoch setting.",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_payload(payload: Mapping, out: Path, report: Path) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    write_markdown(payload, report)


def run_matrix(args: argparse.Namespace) -> Dict:
    started = time.time()
    out = Path(args.out)
    rows = load_existing(out) if args.resume else []
    existing = {row_key(row) for row in rows}
    jobs = requested_jobs(args)
    max_new_runs = int(args.max_new_runs or 0)
    new_runs = 0
    for index, job in enumerate(jobs, start=1):
        key = expected_key(job, args)
        if key in existing:
            print(
                "[training-adequacy] skip existing "
                f"{index}/{len(jobs)} dataset={job['dataset']} model={job['model']} "
                f"seed={job['seed']} epochs={job['epochs']}",
                flush=True,
            )
            continue
        if max_new_runs > 0 and new_runs >= max_new_runs:
            return build_payload(args, rows, started)
        print(
            "[training-adequacy] start "
            f"{index}/{len(jobs)} dataset={job['dataset']} model={job['model']} "
            f"seed={job['seed']} epochs={job['epochs']} hidden={job['hidden_dim']} "
            f"max_seq={job['max_sequence_len']}",
            flush=True,
        )
        row = run_one(args, job)
        rows.append(row)
        existing.add(row_key(row))
        new_runs += 1
        payload = build_payload(args, rows, started)
        write_payload(payload, Path(args.out), Path(args.report))
        print(
            "[training-adequacy] finish "
            f"{index}/{len(jobs)} dataset={row.get('dataset')} model={row.get('model')} "
            f"seed={row.get('seed')} epochs={row.get('epochs')} status={row.get('status')}",
            flush=True,
        )
    return build_payload(args, rows, started)


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run propagation model training adequacy learning-curve experiments.")
    parser.add_argument("--datasets", default="douban,twitter,memetracker")
    parser.add_argument("--seeds", default="42,43,44")
    parser.add_argument("--models", default="Ours,MINDS")
    parser.add_argument("--epoch_grid", default="200")
    parser.add_argument("--hidden_dims", default="32")
    parser.add_argument("--max_sequence_lens", default="64")
    parser.add_argument("--forest_data_root", default=str(DEFAULT_FOREST_DATA))
    parser.add_argument("--out", default=str(Path("benchmark") / "propagation_training_adequacy_20260810.json"))
    parser.add_argument(
        "--report",
        default=str(DEFAULT_DOC_DIR / "propagation_training_adequacy_20260810.md"),
    )
    parser.add_argument("--device", default="cuda", choices=["cpu", "cuda"])
    parser.add_argument("--train_cascades", type=int, default=300)
    parser.add_argument("--eval_cascades", type=int, default=100)
    parser.add_argument("--batch_size", type=int, default=32)
    parser.add_argument("--obs_ratios", default="0.1,0.3,0.5")
    parser.add_argument("--trend_steps", type=int, default=4)
    parser.add_argument("--negative_samples", type=int, default=32)
    parser.add_argument("--rollout_steps", type=int, default=5)
    parser.add_argument("--progress_interval", type=int, default=20)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--max_new_runs", type=int, default=0)
    parser.add_argument(
        "--training_checkpoint_dir",
        default=str(Path("benchmark") / "checkpoints" / "propagation_training_adequacy_20260810"),
    )
    parser.add_argument("--training_checkpoint_interval", type=int, default=5)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    payload = run_matrix(args)
    write_payload(payload, Path(args.out), Path(args.report))
    print(json.dumps({"status": payload["status"], "out": args.out, "report": args.report}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
