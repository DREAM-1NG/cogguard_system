"""Run the formal fair propagation comparison matrix.

Formal tables are task-scoped:
- Macro: Ours / MINDS / CasFT
- Micro: Ours / MINDS / FOREST

TGN and DyGFormer are excluded from this script because their native output is a
temporal-link score, not a cascade-prefix next-user table under this protocol.
"""

from __future__ import annotations

import argparse
import json
import math
import time
from collections import defaultdict
from pathlib import Path
from statistics import mean, pstdev
from typing import Any, Iterable, Mapping, Sequence

from benchmark.adapters.fair_learned_adapters import run_fair_learned_adapter
from benchmark.adapters.fair_protocol import DEFAULT_K_LIST, PROTOCOL_ID

DEFAULT_DATA_ROOT = Path(r"G:\CISCN\dataset\forest-data")
DEFAULT_OUTPUT = Path("benchmark") / "propagation_fair_full_matrix.json"
DEFAULT_REPORT = Path("benchmark") / "propagation_fair_full_matrix.md"

MACRO_MODELS = ("Ours", "MINDS", "CasFT")
MICRO_MODELS = ("Ours", "MINDS", "FOREST")
ALL_FORMAL_MODELS = tuple(dict.fromkeys(MACRO_MODELS + MICRO_MODELS))

MACRO_METRICS = (
    "msle",
    "mae",
    "rmse",
    "mape_percent",
    "smape_percent",
    "direction_accuracy",
    "trend_mae",
    "trend_rmse",
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


def parse_csv(value: str) -> list[str]:
    return [item.strip() for item in str(value or "").split(",") if item.strip()]


def parse_int_csv(value: str) -> list[int]:
    return [int(item) for item in parse_csv(value)]


def parse_float_csv(value: str) -> list[float]:
    return [float(item) for item in parse_csv(value)]


def row_key(row: Mapping[str, Any]) -> tuple[str, str, int, str]:
    return (
        str(row.get("model", "")),
        str(row.get("dataset", "")),
        int(row.get("seed", 0) or 0),
        str(row.get("protocol_id", "")),
    )


def load_existing(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    rows = payload.get("rows", [])
    if not isinstance(rows, list):
        return []
    dedup: dict[tuple[str, str, int, str], dict[str, Any]] = {}
    for row in rows:
        if isinstance(row, dict):
            dedup[row_key(row)] = row
    return list(dedup.values())


def finite(value: Any) -> float | None:
    if isinstance(value, (int, float)) and math.isfinite(float(value)):
        return float(value)
    return None


def summarize(rows: Iterable[Mapping[str, Any]], *, models: Sequence[str], metrics: Sequence[str]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str], dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    for row in rows:
        if row.get("status") != "ok" or not row.get("fair_protocol_passed"):
            continue
        model = str(row.get("model"))
        if model not in models:
            continue
        key = (str(row.get("dataset")), model)
        for metric in metrics:
            value = finite(row.get(metric))
            if value is not None:
                grouped[key][metric].append(value)
    records: list[dict[str, Any]] = []
    for (dataset, model), values_by_metric in sorted(grouped.items()):
        record: dict[str, Any] = {"dataset": dataset, "model": model}
        for metric in metrics:
            values = values_by_metric.get(metric, [])
            if values:
                record[f"{metric}_mean"] = mean(values)
                record[f"{metric}_std"] = pstdev(values) if len(values) > 1 else 0.0
                record[f"{metric}_n"] = len(values)
        records.append(record)
    return records


def required_rows(args: argparse.Namespace) -> list[tuple[str, str, int]]:
    return [
        (dataset, model, seed)
        for dataset in parse_csv(args.datasets)
        for model in parse_csv(args.models)
        for seed in parse_int_csv(args.seeds)
    ]


def protocol_audit(rows: Sequence[Mapping[str, Any]], args: argparse.Namespace) -> dict[str, Any]:
    ok_keys = {
        (str(row.get("dataset")), str(row.get("model")), int(row.get("seed", 0) or 0))
        for row in rows
        if row.get("status") == "ok" and row.get("fair_protocol_passed") and row.get("protocol_id") == PROTOCOL_ID
    }
    missing = [
        {"dataset": dataset, "model": model, "seed": seed}
        for dataset, model, seed in required_rows(args)
        if (dataset, model, seed) not in ok_keys
    ]
    nonfair = [
        {
            "dataset": row.get("dataset"),
            "model": row.get("model"),
            "seed": row.get("seed"),
            "status": row.get("status"),
            "fair_protocol_passed": row.get("fair_protocol_passed"),
            "reason": row.get("reason"),
        }
        for row in rows
        if row.get("status") != "ok" or not row.get("fair_protocol_passed")
    ]
    return {
        "passed": not missing,
        "protocol_id": PROTOCOL_ID,
        "requested_count": len(required_rows(args)),
        "row_count": len(rows),
        "fair_ok_count": len(ok_keys),
        "missing_rows": missing,
        "nonfair_rows": nonfair,
    }


def excluded_methods() -> list[dict[str, str]]:
    return [
        {
            "model": "TGN",
            "status": "excluded_this_round",
            "reason": "Native task is temporal link prediction; current code does not export learned cascade-prefix user rankings.",
            "next_step": "Run in a separate Temporal Link table or add a prefix-state scorer before Micro comparison.",
        },
        {
            "model": "DyGFormer",
            "status": "excluded_this_round",
            "reason": "Native task is temporal link prediction; previous event-level Top-K used proxy candidate ordering.",
            "next_step": "Export learned temporal scores over the shared train-user candidate universe before comparison.",
        },
        {
            "model": "Original MINDS public runner",
            "status": "not_formal_table_source",
            "reason": "The current public runner re-splits data and builds graph structures outside the shared protocol.",
            "next_step": "Keep only as reproduction evidence until a native explicit-split adapter is completed.",
        },
        {
            "model": "Original CasFT public runner",
            "status": "not_formal_table_source",
            "reason": "The staged exporter/preprocessor can merge or re-split cascades, so it is not yet split-preserving.",
            "next_step": "Use the same-protocol macro adapter now; build split-preserving CasFT preprocessing later.",
        },
    ]


def build_payload(args: argparse.Namespace, rows: Sequence[Mapping[str, Any]], started: float) -> dict[str, Any]:
    audit = protocol_audit(rows, args)
    return {
        "schema": "cogguard.propagation.fair_full_matrix.v1",
        "status": "ok" if audit["passed"] else "partial",
        "protocol_id": PROTOCOL_ID,
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "elapsed_s": round(time.time() - started, 1),
        "datasets": parse_csv(args.datasets),
        "seeds": parse_int_csv(args.seeds),
        "models": parse_csv(args.models),
        "epochs": int(args.epochs),
        "obs_ratios": parse_float_csv(args.obs_ratios),
        "comparison_boundary": (
            "Formal comparison uses one native split loader, one train-only real-user vocabulary, "
            "one candidate universe, one prefix-window evaluator, and one metric implementation."
        ),
        "macro_table_scope": list(MACRO_MODELS),
        "micro_table_scope": list(MICRO_MODELS),
        "macro_metrics": list(MACRO_METRICS),
        "micro_metrics": list(MICRO_METRICS),
        "protocol_audit": audit,
        "macro_summary": summarize(rows, models=MACRO_MODELS, metrics=MACRO_METRICS),
        "micro_summary": summarize(rows, models=MICRO_MODELS, metrics=MICRO_METRICS),
        "excluded_methods": excluded_methods(),
        "rows": list(rows),
    }


def fmt(value: Any) -> str:
    number = finite(value)
    return f"{number:.6f}" if number is not None else ""


def write_metric_table(lines: list[str], title: str, rows: Sequence[Mapping[str, Any]], metrics: Sequence[str]) -> None:
    lines.extend(["", f"## {title}", ""])
    header = ["dataset", "method"] + [f"{metric} mean+/-std" for metric in metrics]
    lines.append("| " + " | ".join(header) + " |")
    lines.append("|" + "|".join(["---"] * len(header)) + "|")
    for row in rows:
        cells = [str(row.get("dataset", "")), str(row.get("model", ""))]
        for metric in metrics:
            mean_value = row.get(f"{metric}_mean")
            std_value = row.get(f"{metric}_std")
            cells.append(f"{fmt(mean_value)}+/-{fmt(std_value)}" if mean_value is not None else "")
        lines.append("| " + " | ".join(cells) + " |")


def write_report(payload: Mapping[str, Any], path: Path) -> None:
    lines = [
        "# Propagation Fair Full Matrix",
        "",
        f"- status: `{payload.get('status')}`",
        f"- protocol_id: `{payload.get('protocol_id')}`",
        f"- epochs: `{payload.get('epochs')}`",
        f"- datasets: `{', '.join(payload.get('datasets', []))}`",
        f"- seeds: `{', '.join(str(seed) for seed in payload.get('seeds', []))}`",
        f"- obs_ratios: `{', '.join(str(value) for value in payload.get('obs_ratios', []))}`",
        "",
        str(payload.get("comparison_boundary")),
        "",
        "## Protocol Audit",
        "",
        "| item | value |",
        "|---|---:|",
    ]
    audit = payload.get("protocol_audit", {})
    for key in ("passed", "requested_count", "row_count", "fair_ok_count"):
        lines.append(f"| {key} | `{audit.get(key)}` |")
    if audit.get("missing_rows"):
        lines.extend(["", "Missing or non-fair requested rows:", ""])
        for row in audit["missing_rows"]:
            lines.append(f"- `{row}`")

    write_metric_table(lines, "Macro Size / Trend", payload.get("macro_summary", []), MACRO_METRICS)
    write_metric_table(lines, "Micro Next-Hop", payload.get("micro_summary", []), MICRO_METRICS)

    lines.extend(["", "## Excluded / Separate Track", "", "| model | status | reason | next step |", "|---|---|---|---|"])
    for row in payload.get("excluded_methods", []):
        lines.append(
            "| {model} | {status} | {reason} | {next_step} |".format(
                model=row.get("model", ""),
                status=row.get("status", ""),
                reason=str(row.get("reason", "")).replace("|", "/"),
                next_step=str(row.get("next_step", "")).replace("|", "/"),
            )
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_payload(payload: Mapping[str, Any], out_path: Path, report_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    write_report(payload, report_path)


def run_matrix(args: argparse.Namespace) -> dict[str, Any]:
    started = time.time()
    out_path = Path(args.output)
    rows = load_existing(out_path) if args.resume else []
    existing = {row_key(row) for row in rows}
    max_new_runs = max(0, int(args.max_new_runs))
    new_runs = 0
    for dataset in parse_csv(args.datasets):
        data_dir = Path(args.data_root) / dataset
        for seed in parse_int_csv(args.seeds):
            for model in parse_csv(args.models):
                key = (model, dataset, seed, PROTOCOL_ID)
                if key in existing:
                    continue
                if max_new_runs and new_runs >= max_new_runs:
                    return build_payload(args, rows, started)
                row = run_fair_learned_adapter(
                    data_dir,
                    model_name=model,
                    dataset=dataset,
                    obs_ratios=parse_float_csv(args.obs_ratios),
                    epochs=args.epochs,
                    batch_size=args.batch_size,
                    hidden_dim=args.hidden_dim,
                    max_sequence_len=args.max_sequence_len,
                    trend_steps=args.trend_steps,
                    relation_neighbor_count=args.relation_neighbor_count,
                    max_train_cascades=args.train_limit,
                    max_eval_cascades=args.eval_limit,
                    max_train_users=args.max_train_users,
                    seed=seed,
                    device=args.device,
                    lr=args.lr,
                    weight_decay=args.weight_decay,
                    k_list=DEFAULT_K_LIST,
                )
                rows.append(row)
                existing.add(row_key(row))
                new_runs += 1
                write_payload(build_payload(args, rows, started), out_path, Path(args.report))
    return build_payload(args, rows, started)


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run formal same-protocol propagation comparison matrix.")
    parser.add_argument("--datasets", default="douban,twitter,memetracker")
    parser.add_argument("--seeds", default="42,43,44")
    parser.add_argument("--models", default=",".join(ALL_FORMAL_MODELS))
    parser.add_argument("--data_root", default=str(DEFAULT_DATA_ROOT))
    parser.add_argument("--epochs", type=int, default=200)
    parser.add_argument("--batch_size", type=int, default=64)
    parser.add_argument("--hidden_dim", type=int, default=64)
    parser.add_argument("--max_sequence_len", type=int, default=128)
    parser.add_argument("--trend_steps", type=int, default=4)
    parser.add_argument("--relation_neighbor_count", type=int, default=4)
    parser.add_argument("--obs_ratios", default="0.1,0.3,0.5")
    parser.add_argument("--train_limit", type=int, default=0, help="0 means full training split.")
    parser.add_argument("--eval_limit", type=int, default=0, help="0 means full eval split.")
    parser.add_argument("--max_train_users", type=int, default=0, help="0 means full train vocabulary.")
    parser.add_argument("--device", default="cpu", choices=["cpu", "cuda"])
    parser.add_argument("--lr", type=float, default=1e-3)
    parser.add_argument("--weight_decay", type=float, default=1e-4)
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--report", default=str(DEFAULT_REPORT))
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--max_new_runs", type=int, default=0)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    payload = run_matrix(args)
    write_payload(payload, Path(args.output), Path(args.report))
    print(json.dumps({"status": payload["status"], "output": args.output, "report": args.report}, ensure_ascii=False))
    return 0 if payload["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
