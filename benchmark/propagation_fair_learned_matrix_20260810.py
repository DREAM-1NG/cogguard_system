from __future__ import annotations

import argparse
import json
import math
import sys
import time
from collections import defaultdict
from pathlib import Path
from statistics import mean, pstdev
from typing import Dict, Iterable, List, Mapping, Sequence

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from benchmark.adapters.cascade_io import load_forest_split
from benchmark.adapters.kt2_sequence_joint_model import run_kt2_sequence_joint_model


DEFAULT_FOREST_DATA = Path(r"G:\CISCN\dataset\forest-data")
DEFAULT_DOC_DIR = Path(
    r"G:\CISCN\CogGuard\.worktrees\refactor-system\system\doc\research\propagation_paper_deep_reads"
)
PROTOCOL_ID = "propagation_fair_sequence_forestsplit_v1"
MODEL_VARIANTS = {
    "Ours": "ours",
    "MINDS": "minds_shared_backbone",
}
MACRO_METRICS = (
    "msle",
    "mae",
    "rmse",
    "mape_percent",
    "smape_percent",
    "direction_accuracy",
    "trend_mae",
    "trend_rmse",
    "macro_micro_consistency",
)
MICRO_METRICS = (
    "candidate_recall_full",
    "hits@10",
    "hits@50",
    "hits@100",
    "map@10",
    "map@50",
    "map@100",
    "mrr",
    "ndcg@10",
    "ndcg@50",
    "ndcg@100",
)


def parse_csv(value: str) -> List[str]:
    return [item.strip() for item in str(value or "").split(",") if item.strip()]


def parse_int_csv(value: str) -> List[int]:
    return [int(item) for item in parse_csv(value)]


def parse_float_csv(value: str) -> List[float]:
    return [float(item) for item in parse_csv(value)]


def finite(value) -> float | None:
    if isinstance(value, (int, float)) and math.isfinite(float(value)):
        return float(value)
    return None


def dataset_counts(data_dir: Path, train_limit: int, eval_limit: int) -> Dict[str, int]:
    train, valid, test = load_forest_split(data_dir)
    eval_cascades = test or valid
    train_used = len(train[:train_limit]) if train_limit > 0 else len(train)
    eval_used = len(eval_cascades[:eval_limit]) if eval_limit > 0 else len(eval_cascades)
    return {
        "train_available": len(train),
        "valid_available": len(valid),
        "test_available": len(test),
        "train_used_expected": train_used,
        "eval_used_expected": eval_used,
        "eval_split": "test" if test else "valid",
    }


def protocol_config(args: argparse.Namespace, dataset: str) -> Dict:
    counts = dataset_counts(Path(args.forest_data_root) / dataset, args.train_cascades, args.eval_cascades)
    return {
        "protocol_id": PROTOCOL_ID,
        "dataset": dataset,
        "data_root": str(Path(args.forest_data_root)),
        "split_policy": "FOREST native cascade.txt/cascadevalid.txt/cascadetest.txt",
        "train_file": "cascade.txt",
        "valid_file": "cascadevalid.txt",
        "test_file": "cascadetest.txt",
        "eval_split": counts["eval_split"],
        "train_cascades_limit": int(args.train_cascades),
        "eval_cascades_limit": int(args.eval_cascades),
        "train_cascades_used_expected": counts["train_used_expected"],
        "eval_cascades_used_expected": counts["eval_used_expected"],
        "obs_ratios": parse_float_csv(args.obs_ratios),
        "epochs": int(args.epochs),
        "batch_size": int(args.batch_size),
        "hidden_dim": int(args.hidden_dim),
        "max_sequence_len": int(args.max_sequence_len),
        "trend_steps": int(args.trend_steps),
        "negative_samples": int(args.negative_samples),
        "rollout_steps": int(args.rollout_steps),
        "candidate_policy": "train-user bucket universe; no future-tail candidate injection",
        "metric_impl": "benchmark.adapters.kt2_sequence_joint_model._evaluate_model",
        "counts": counts,
    }


def row_fair_protocol_passed(row: Mapping, protocol: Mapping) -> bool:
    if row.get("status") != "ok":
        return False
    expected = {
        "train_cascades_used": protocol["train_cascades_used_expected"],
        "eval_cascades_used": protocol["eval_cascades_used_expected"],
        "epochs": protocol["epochs"],
        "batch_size": protocol["batch_size"],
        "hidden_dim": protocol["hidden_dim"],
        "max_sequence_len": protocol["max_sequence_len"],
        "trend_steps": protocol["trend_steps"],
        "negative_samples": protocol["negative_samples"],
        "rollout_steps": protocol["rollout_steps"],
    }
    for key, value in expected.items():
        if int(row.get(key, -1)) != int(value):
            return False
    if [float(x) for x in row.get("obs_ratios", [])] != [float(x) for x in protocol["obs_ratios"]]:
        return False
    audit = row.get("candidate_protocol_audit", {})
    return bool(audit.get("leakage_check_passed") and not audit.get("future_nodes_injected"))


def run_one(args: argparse.Namespace, dataset: str, seed: int, model: str) -> Dict:
    if model not in MODEL_VARIANTS:
        return {
            "model": model,
            "dataset": dataset,
            "seed": seed,
            "status": "not_comparable",
            "reason": "No same-protocol learned adapter is registered for this model.",
        }
    protocol = protocol_config(args, dataset)
    row = run_kt2_sequence_joint_model(
        Path(args.forest_data_root) / dataset,
        dataset=dataset,
        model_name=model,
        model_variant=MODEL_VARIANTS[model],
        obs_ratios=protocol["obs_ratios"],
        epochs=protocol["epochs"],
        batch_size=protocol["batch_size"],
        hidden_dim=protocol["hidden_dim"],
        max_train_cascades=protocol["train_cascades_limit"],
        max_test_cascades=protocol["eval_cascades_limit"],
        max_sequence_len=protocol["max_sequence_len"],
        trend_steps=protocol["trend_steps"],
        negative_samples=protocol["negative_samples"],
        rollout_steps=protocol["rollout_steps"],
        seed=seed,
        device=args.device,
    )
    row["seed"] = seed
    row["dataset"] = dataset
    row["protocol_id"] = PROTOCOL_ID
    row["fair_protocol"] = protocol
    row["fair_protocol_passed"] = row_fair_protocol_passed(row, protocol)
    row["comparison_scope"] = (
        "resource_bounded_same_protocol"
        if protocol["train_cascades_limit"] > 0 or protocol["eval_cascades_limit"] > 0
        else "full_source_same_protocol"
    )
    row["result_claim_boundary"] = (
        "Comparable with rows that share protocol_id and fair_protocol_passed=true. "
        "This is a same-protocol learned reimplementation matrix, not a mixed original-code SOTA table."
    )
    return row


def row_key(row: Mapping) -> tuple[str, str, int, str]:
    return (
        str(row.get("model", "")),
        str(row.get("dataset", "")),
        int(row.get("seed", 0) or 0),
        str(row.get("protocol_id", "")),
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
    dedup: Dict[tuple[str, str, int, str], Dict] = {}
    for row in rows:
        if isinstance(row, dict):
            dedup[row_key(row)] = row
    return list(dedup.values())


def summarize(rows: Iterable[Mapping], metrics: Sequence[str]) -> List[Dict]:
    grouped: Dict[tuple[str, str], Dict[str, List[float]]] = defaultdict(lambda: defaultdict(list))
    for row in rows:
        if row.get("status") != "ok" or not row.get("fair_protocol_passed"):
            continue
        key = (str(row.get("dataset")), str(row.get("model")))
        for metric in metrics:
            value = finite(row.get(metric))
            if value is not None:
                grouped[key][metric].append(value)
    summary = []
    for (dataset, model), values_by_metric in sorted(grouped.items()):
        record = {"dataset": dataset, "model": model}
        for metric in metrics:
            values = values_by_metric.get(metric, [])
            if values:
                record[f"{metric}_mean"] = mean(values)
                record[f"{metric}_std"] = pstdev(values) if len(values) > 1 else 0.0
                record[f"{metric}_n"] = len(values)
        summary.append(record)
    return summary


def protocol_audit(rows: Sequence[Mapping], args: argparse.Namespace) -> Dict:
    requested = [(d, s, m) for d in parse_csv(args.datasets) for s in parse_int_csv(args.seeds) for m in parse_csv(args.models)]
    ok_keys = {
        (str(row.get("dataset")), int(row.get("seed", 0) or 0), str(row.get("model")))
        for row in rows
        if row.get("status") == "ok" and row.get("fair_protocol_passed")
    }
    missing = [
        {"dataset": dataset, "seed": seed, "model": model}
        for dataset, seed, model in requested
        if (dataset, seed, model) not in ok_keys
    ]
    protocol_ids = sorted({str(row.get("protocol_id")) for row in rows if row.get("status") == "ok"})
    return {
        "passed": not missing and protocol_ids == [PROTOCOL_ID],
        "protocol_ids": protocol_ids,
        "missing_or_nonfair_rows": missing,
        "row_count": len(rows),
        "fair_ok_count": len(ok_keys),
        "requested_count": len(requested),
    }


def excluded_methods() -> List[Dict]:
    return [
        {
            "model": "Original MINDS public code",
            "status": "excluded_from_fair_verdict",
            "reason": (
                "The current adapter calls SplitData(..., train_rate=0.8, valid_rate=0.1), so its split and "
                "all-position sequence metrics do not match the FOREST split + obs-ratio window protocol."
            ),
            "path_to_fix": "Add a native MINDS fair adapter that consumes explicit train/valid/test cascades and evaluates prefix windows.",
        },
        {
            "model": "DyGFormer/DyGLib",
            "status": "excluded_from_fair_verdict",
            "reason": (
                "The current temporal-graph adapter can run upstream training, but event-level Top-K metrics are still "
                "computed by protocol_next_hop_baseline(), a shared transition/popularity proxy rather than learned scores."
            ),
            "path_to_fix": "Extract learned temporal-node scores at each prefix window and rank the same train-user candidate universe.",
        },
        {
            "model": "TGN",
            "status": "excluded_from_fair_verdict",
            "reason": (
                "The current TGN adapter exports temporal edges and launches self-supervised training, but does not feed "
                "learned TGN scores into the macro/micro event-window evaluator."
            ),
            "path_to_fix": "Add a TGN prefix-state scorer and use the shared Top-K metric implementation.",
        },
        {
            "model": "CasFT",
            "status": "macro_only_pending",
            "reason": "CasFT is a macro future-trend/size model and has no next-user Top-K head in the current protocol.",
            "path_to_fix": "Evaluate CasFT in a separate macro-only table using the same FOREST split and observed prefix windows.",
        },
        {
            "model": "FOREST",
            "status": "pending_fair_adapter",
            "reason": (
                "The current adapter targets public-code smoke/full-run behavior, not the shared prefix-window sampled-softmax "
                "metric implementation used here."
            ),
            "path_to_fix": "Wrap FOREST logits/rollouts into the shared prefix-window evaluator before including it in this verdict.",
        },
    ]


def build_payload(args: argparse.Namespace, rows: Sequence[Mapping], started: float) -> Dict:
    audit = protocol_audit(rows, args)
    return {
        "schema": "cogguard.propagation.fair_learned_matrix.v1",
        "status": "ok" if audit["passed"] else "partial",
        "protocol_id": PROTOCOL_ID,
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "elapsed_s": round(time.time() - started, 1),
        "datasets": parse_csv(args.datasets),
        "seeds": parse_int_csv(args.seeds),
        "models": parse_csv(args.models),
        "macro_metrics": list(MACRO_METRICS),
        "micro_metrics": list(MICRO_METRICS),
        "fairness_definition": (
            "Rows are comparable only when they use the same FOREST train/valid/test files, the same observation ratios, "
            "the same train/eval cascade caps, the same epochs/batch/hidden/sequence configuration, the same candidate "
            "policy, and the same metric implementation."
        ),
        "claim_boundary": (
            "This file is the fair learned matrix. The earlier stable SOTA matrix remains an engineering run record and "
            "must not be used as a direct learned-model improvement verdict."
        ),
        "protocol_audit": audit,
        "macro_summary": summarize(rows, MACRO_METRICS),
        "micro_summary": summarize(rows, MICRO_METRICS),
        "excluded_methods": excluded_methods(),
        "rows": list(rows),
    }


def fmt(value) -> str:
    if isinstance(value, (int, float)) and math.isfinite(float(value)):
        return f"{float(value):.6f}"
    return ""


def write_metric_table(lines: List[str], title: str, summary: Sequence[Mapping], metrics: Sequence[str]) -> None:
    lines.extend(["", f"## {title}", ""])
    header = ["dataset", "model"] + [f"{metric} mean+/-std" for metric in metrics]
    lines.append("| " + " | ".join(header) + " |")
    lines.append("|" + "|".join(["---"] * len(header)) + "|")
    for row in summary:
        cells = [str(row.get("dataset")), str(row.get("model"))]
        for metric in metrics:
            mean_value = row.get(f"{metric}_mean")
            std_value = row.get(f"{metric}_std")
            cells.append(f"{fmt(mean_value)}+/-{fmt(std_value)}" if mean_value is not None else "")
        lines.append("| " + " | ".join(cells) + " |")


def write_markdown(payload: Mapping, path: Path) -> None:
    lines = [
        "# Propagation Fair Learned Matrix",
        "",
        f"- status: `{payload.get('status')}`",
        f"- protocol_id: `{payload.get('protocol_id')}`",
        f"- datasets: `{', '.join(payload.get('datasets', []))}`",
        f"- seeds: `{', '.join(str(seed) for seed in payload.get('seeds', []))}`",
        f"- models: `{', '.join(payload.get('models', []))}`",
        "",
        str(payload.get("fairness_definition")),
        "",
        str(payload.get("claim_boundary")),
        "",
        "## Protocol Audit",
        "",
        "| item | value |",
        "|---|---:|",
    ]
    audit = payload.get("protocol_audit", {})
    for key in ("passed", "row_count", "fair_ok_count", "requested_count"):
        lines.append(f"| {key} | `{audit.get(key)}` |")
    if audit.get("missing_or_nonfair_rows"):
        lines.extend(["", "Missing or non-fair rows:", ""])
        for row in audit.get("missing_or_nonfair_rows", []):
            lines.append(f"- `{row}`")

    write_metric_table(lines, "Macro Metrics", payload.get("macro_summary", []), MACRO_METRICS)
    write_metric_table(lines, "Micro Metrics", payload.get("micro_summary", []), MICRO_METRICS)

    lines.extend(["", "## Excluded / Separate-Track Methods", "", "| model | status | reason | next step |", "|---|---|---|---|"])
    for row in payload.get("excluded_methods", []):
        lines.append(
            "| {model} | {status} | {reason} | {path_to_fix} |".format(
                model=row.get("model"),
                status=row.get("status"),
                reason=str(row.get("reason", "")).replace("|", "/"),
                path_to_fix=str(row.get("path_to_fix", "")).replace("|", "/"),
            )
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_payload(payload: Mapping, out: Path, report: Path | None = None) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    write_markdown(payload, report or out.with_suffix(".md"))


def run_matrix(args: argparse.Namespace) -> Dict:
    started = time.time()
    out = Path(args.out)
    rows = load_existing(out) if args.resume else []
    existing = {row_key(row) for row in rows}
    max_new_runs = int(args.max_new_runs or 0)
    new_runs = 0
    for dataset in parse_csv(args.datasets):
        for seed in parse_int_csv(args.seeds):
            for model in parse_csv(args.models):
                key = (model, dataset, seed, PROTOCOL_ID)
                if key in existing:
                    continue
                if max_new_runs > 0 and new_runs >= max_new_runs:
                    return build_payload(args, rows, started)
                row = run_one(args, dataset, seed, model)
                rows.append(row)
                existing.add(row_key(row))
                new_runs += 1
                payload = build_payload(args, rows, started)
                write_payload(payload, out, Path(args.report))
    return build_payload(args, rows, started)


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run a fair learned propagation matrix under one split/config/metric protocol.")
    parser.add_argument("--datasets", default="douban,twitter,memetracker")
    parser.add_argument("--seeds", default="42,43,44")
    parser.add_argument("--models", default="Ours,MINDS")
    parser.add_argument("--forest_data_root", default=str(DEFAULT_FOREST_DATA))
    parser.add_argument("--out", default=str(Path("benchmark") / "propagation_fair_learned_matrix_20260810.json"))
    parser.add_argument(
        "--report",
        default=str(DEFAULT_DOC_DIR / "propagation_fair_learned_matrix_20260810.md"),
    )
    parser.add_argument("--device", default="cuda", choices=["cpu", "cuda"])
    parser.add_argument("--train_cascades", type=int, default=300)
    parser.add_argument("--eval_cascades", type=int, default=100)
    parser.add_argument("--epochs", type=int, default=200)
    parser.add_argument("--batch_size", type=int, default=32)
    parser.add_argument("--hidden_dim", type=int, default=32)
    parser.add_argument("--max_sequence_len", type=int, default=64)
    parser.add_argument("--obs_ratios", default="0.1,0.3,0.5")
    parser.add_argument("--trend_steps", type=int, default=4)
    parser.add_argument("--negative_samples", type=int, default=32)
    parser.add_argument("--rollout_steps", type=int, default=5)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--max_new_runs", type=int, default=0)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    payload = run_matrix(args)
    write_payload(payload, Path(args.out), Path(args.report))
    print(json.dumps({"status": payload["status"], "out": args.out, "report": args.report}, ensure_ascii=False))
    return 0 if payload["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
