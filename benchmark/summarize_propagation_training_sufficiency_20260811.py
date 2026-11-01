from __future__ import annotations

import argparse
import json
import math
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from statistics import mean, pstdev
from typing import Any, Iterable, Mapping


BENCHMARK_DIR = Path(__file__).resolve().parent
DOC_DIR = Path(
    r"G:\CISCN\CogGuard\.worktrees\refactor-system\system\doc\research\propagation_paper_deep_reads"
)

DEFAULT_STATUS = BENCHMARK_DIR / "propagation_training_sufficiency_200ep_full_20260811_status.json"
DEFAULT_SEQUENCE_SAMPLED = (
    BENCHMARK_DIR / "propagation_training_sufficiency_sequence_200ep_h64_seq200_300c_3seed_20260811.json"
)
DEFAULT_SEQUENCE_FULL = (
    BENCHMARK_DIR / "propagation_training_sufficiency_sequence_200ep_h64_seq200_fullsource_3seed_20260811.json"
)
DEFAULT_PUBLIC_BASELINES = BENCHMARK_DIR / "propagation_training_sufficiency_public_baselines_200ep_20260811.json"
DEFAULT_TEMPORAL = BENCHMARK_DIR / "propagation_training_sufficiency_temporal_graph_200ep_20260811.json"

EXPECTED_SEQUENCE_ROWS = 3 * 3 * 2
EXPECTED_PUBLIC_ROWS = 3 * 3 * 3
EXPECTED_TEMPORAL_ROWS = 3 * 2

MACRO_METRICS = ("msle", "mae", "rmse", "trend_mae", "trend_rmse", "direction_accuracy")
MICRO_METRICS = ("candidate_recall_full", "hits@10", "hits@50", "hits@100", "mrr", "ndcg@100")
TEMPORAL_METRICS = (
    "test_ap",
    "test_auc",
    "val_ap",
    "val_auc",
    "new_node_test_ap",
    "new_node_test_auc",
)


def load_json(path: str | Path) -> Any:
    p = Path(path)
    if not p.is_file():
        return None
    return json.loads(p.read_text(encoding="utf-8-sig"))


def rows_from_payload(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [dict(row) for row in payload if isinstance(row, Mapping)]
    if isinstance(payload, Mapping):
        rows = payload.get("rows", [])
        return [dict(row) for row in rows if isinstance(row, Mapping)]
    return []


def finite(value: Any) -> float | None:
    if isinstance(value, (int, float)) and math.isfinite(float(value)):
        return float(value)
    return None


def fmt(value: Any, digits: int = 4) -> str:
    number = finite(value)
    return "-" if number is None else f"{number:.{digits}f}"


def compact_path(path: str | Path) -> str:
    return str(path).replace("\\", "/")


def source_state(path: str | Path, expected_rows: int | None) -> dict[str, Any]:
    p = Path(path)
    payload = load_json(p)
    rows = rows_from_payload(payload)
    status = payload.get("status") if isinstance(payload, Mapping) else None
    if not p.is_file():
        state = "missing"
    elif expected_rows is None and status:
        state = str(status)
    elif status == "ok" and (expected_rows is None or len(rows) >= expected_rows):
        state = "complete"
    elif rows:
        state = "partial"
    else:
        state = "created_no_rows"
    return {
        "path": compact_path(p),
        "state": state,
        "payload_status": status,
        "rows": len(rows),
        "expected_rows": expected_rows,
        "last_write_time": datetime.fromtimestamp(p.stat().st_mtime).isoformat(timespec="seconds")
        if p.is_file()
        else None,
    }


def summarize_rows(rows: Iterable[Mapping[str, Any]], metrics: Iterable[str]) -> list[dict[str, Any]]:
    groups: dict[tuple[str, str], list[Mapping[str, Any]]] = defaultdict(list)
    for row in rows:
        dataset = str(row.get("dataset", ""))
        model = str(row.get("model", ""))
        if not dataset or not model:
            continue
        groups[(dataset, model)].append(row)

    summary: list[dict[str, Any]] = []
    for (dataset, model), items in sorted(groups.items()):
        record: dict[str, Any] = {
            "dataset": dataset,
            "model": model,
            "rows": len(items),
            "ok_rows": sum(1 for item in items if str(item.get("status")) == "ok"),
            "statuses": sorted({str(item.get("status", "")) for item in items}),
            "seeds": sorted(
                {
                    int(item["seed"])
                    for item in items
                    if isinstance(item.get("seed"), int) or str(item.get("seed", "")).isdigit()
                }
            ),
            "epochs": sorted(
                {
                    int(item["epochs"])
                    for item in items
                    if isinstance(item.get("epochs"), int) or str(item.get("epochs", "")).isdigit()
                }
            ),
        }
        for metric in metrics:
            values = [finite(item.get(metric)) for item in items]
            values = [value for value in values if value is not None]
            if values:
                record[f"{metric}_mean"] = mean(values)
                record[f"{metric}_std"] = pstdev(values) if len(values) > 1 else 0.0
                record[f"{metric}_n"] = len(values)
        summary.append(record)
    return summary


def status_counts(rows: Iterable[Mapping[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = defaultdict(int)
    for row in rows:
        counts[str(row.get("status", ""))] += 1
    return dict(sorted(counts.items()))


def metric_cell(row: Mapping[str, Any], metric: str) -> str:
    mean_value = row.get(f"{metric}_mean")
    std_value = row.get(f"{metric}_std")
    if finite(mean_value) is None:
        return "-"
    return f"{fmt(mean_value)} +/- {fmt(std_value)}"


def table(headers: list[str], rows: list[list[Any]]) -> str:
    lines = ["| " + " | ".join(headers) + " |", "| " + " | ".join("---" for _ in headers) + " |"]
    if not rows:
        rows = [["-" for _ in headers]]
    lines.extend("| " + " | ".join(str(cell) for cell in row) + " |" for row in rows)
    return "\n".join(lines)


def summary_table(summary: list[dict[str, Any]], metrics: tuple[str, ...]) -> list[list[Any]]:
    rows = []
    for row in summary:
        rows.append(
            [
                row["dataset"],
                row["model"],
                row["rows"],
                row["ok_rows"],
                ",".join(str(seed) for seed in row.get("seeds", [])) or "-",
                ",".join(str(epoch) for epoch in row.get("epochs", [])) or "-",
                *[metric_cell(row, metric) for metric in metrics],
            ]
        )
    return rows


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    status_payload = load_json(args.status)
    sequence_sampled = load_json(args.sequence_sampled)
    sequence_full = load_json(args.sequence_full)
    public_baselines = load_json(args.public_baselines)
    temporal = load_json(args.temporal)

    sequence_sampled_rows = rows_from_payload(sequence_sampled)
    sequence_full_rows = rows_from_payload(sequence_full)
    public_rows = rows_from_payload(public_baselines)
    temporal_rows = rows_from_payload(temporal)

    sources = {
        "queue": source_state(args.status, None),
        "sequence_sampled": source_state(args.sequence_sampled, EXPECTED_SEQUENCE_ROWS),
        "sequence_full": source_state(args.sequence_full, EXPECTED_SEQUENCE_ROWS),
        "public_baselines": source_state(args.public_baselines, EXPECTED_PUBLIC_ROWS),
        "temporal_native": source_state(args.temporal, EXPECTED_TEMPORAL_ROWS),
    }
    all_complete = all(
        sources[name]["state"] == "complete"
        for name in ("sequence_sampled", "sequence_full", "public_baselines", "temporal_native")
    )
    queue_status = status_payload.get("status") if isinstance(status_payload, Mapping) else None

    return {
        "schema": "cogguard.propagation.training_sufficiency_200ep_summary.v1",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "training_epoch": 200,
        "status": "complete" if all_complete and queue_status == "finished" else "partial",
        "queue_status": queue_status,
        "current_step": status_payload.get("current_step") if isinstance(status_payload, Mapping) else None,
        "sources": sources,
        "tracks": {
            "sequence_sampled": {
                "task": "same-protocol cascade macro/micro prediction on capped training cascades",
                "status_counts": status_counts(sequence_sampled_rows),
                "macro_summary": summarize_rows(sequence_sampled_rows, MACRO_METRICS),
                "micro_summary": summarize_rows(sequence_sampled_rows, MICRO_METRICS),
            },
            "sequence_full": {
                "task": "same-protocol cascade macro/micro prediction on full local splits",
                "status_counts": status_counts(sequence_full_rows),
                "macro_summary": summarize_rows(sequence_full_rows, MACRO_METRICS),
                "micro_summary": summarize_rows(sequence_full_rows, MICRO_METRICS),
            },
            "public_baselines": {
                "task": "public-code MINDS/FOREST/CasFT sufficient-epoch baselines",
                "status_counts": status_counts(public_rows),
                "macro_summary": summarize_rows(public_rows, MACRO_METRICS),
                "micro_summary": summarize_rows(public_rows, MICRO_METRICS),
                "failures": public_baselines.get("failures", []) if isinstance(public_baselines, Mapping) else [],
            },
            "temporal_native": {
                "task": "native temporal graph link prediction; not mixed with cascade next-hop verdict",
                "status_counts": status_counts(temporal_rows),
                "summary": summarize_rows(temporal_rows, TEMPORAL_METRICS + MICRO_METRICS),
            },
        },
    }


def build_markdown(payload: Mapping[str, Any]) -> str:
    source_rows = [
        [
            name,
            source.get("state"),
            source.get("payload_status") or "-",
            source.get("rows"),
            source.get("expected_rows") or "-",
            source.get("last_write_time") or "-",
            source.get("path"),
        ]
        for name, source in payload["sources"].items()
    ]

    sampled_macro = payload["tracks"]["sequence_sampled"]["macro_summary"]
    sampled_micro = payload["tracks"]["sequence_sampled"]["micro_summary"]
    full_macro = payload["tracks"]["sequence_full"]["macro_summary"]
    full_micro = payload["tracks"]["sequence_full"]["micro_summary"]
    public_macro = payload["tracks"]["public_baselines"]["macro_summary"]
    public_micro = payload["tracks"]["public_baselines"]["micro_summary"]
    temporal_summary = payload["tracks"]["temporal_native"]["summary"]

    lines = [
        "# Propagation Training Sufficiency 200-Epoch Summary",
        "",
        f"- generated_at: `{payload['generated_at']}`",
        f"- queue_status: `{payload.get('queue_status')}`",
        f"- current_step: `{payload.get('current_step') or ''}`",
        f"- summary_status: `{payload.get('status')}`",
        "- training_epoch: `200` for all configured trainable tracks.",
        "- boundary: temporal graph AP/AUC is reported separately from cascade next-hop Top-K.",
        "",
        "## Source Completion",
        "",
        table(["Source", "State", "Payload Status", "Rows", "Expected", "Last Write", "Path"], source_rows),
        "",
        "## Same-Protocol Sampled Track: Macro",
        "",
        table(
            ["Dataset", "Method", "Rows", "OK", "Seeds", "Epochs", "MSLE", "MAE", "Trend MAE", "Direction Acc"],
            summary_table(sampled_macro, ("msle", "mae", "trend_mae", "direction_accuracy")),
        ),
        "",
        "## Same-Protocol Sampled Track: Micro",
        "",
        table(
            ["Dataset", "Method", "Rows", "OK", "Seeds", "Epochs", "Candidate Recall", "Hits@100", "MRR", "NDCG@100"],
            summary_table(sampled_micro, ("candidate_recall_full", "hits@100", "mrr", "ndcg@100")),
        ),
        "",
        "## Same-Protocol Full-Split Track: Macro",
        "",
        table(
            ["Dataset", "Method", "Rows", "OK", "Seeds", "Epochs", "MSLE", "MAE", "Trend MAE", "Direction Acc"],
            summary_table(full_macro, ("msle", "mae", "trend_mae", "direction_accuracy")),
        ),
        "",
        "## Same-Protocol Full-Split Track: Micro",
        "",
        table(
            ["Dataset", "Method", "Rows", "OK", "Seeds", "Epochs", "Candidate Recall", "Hits@100", "MRR", "NDCG@100"],
            summary_table(full_micro, ("candidate_recall_full", "hits@100", "mrr", "ndcg@100")),
        ),
        "",
        "## Public-Code Baselines: Macro/Micro Fields",
        "",
        table(
            ["Dataset", "Method", "Rows", "OK", "Seeds", "Epochs", "MSLE", "MAE", "Trend MAE", "Hits@100"],
            summary_table(public_macro, ("msle", "mae", "trend_mae", "hits@100")),
        ),
        "",
        "## Public-Code Baselines: Micro Fields",
        "",
        table(
            ["Dataset", "Method", "Rows", "OK", "Seeds", "Epochs", "Hits@10", "Hits@50", "Hits@100", "MRR"],
            summary_table(public_micro, ("hits@10", "hits@50", "hits@100", "mrr")),
        ),
        "",
        "## Native Temporal Graph Track",
        "",
        table(
            ["Dataset", "Method", "Rows", "OK", "Seeds", "Epochs", "Test AP", "Test AUC", "New-node Test AP"],
            summary_table(temporal_summary, ("test_ap", "test_auc", "new_node_test_ap")),
        ),
        "",
        "## Interpretation Guardrails",
        "",
        "- Do not claim final SOTA comparison until `summary_status` becomes `complete` and every source is `complete`.",
        "- Ours and MINDS are directly comparable in the same-protocol sampled/full tracks.",
        "- FOREST/CasFT public-code rows are baseline evidence, but only metrics actually emitted by those adapters are comparable.",
        "- TGN/DyGFormer native AP/AUC remains a separate temporal-link-prediction track unless a learned event-level scorer is wired.",
    ]
    return "\n".join(lines) + "\n"


def write_payload(payload: Mapping[str, Any], out: Path, report: Path) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    report.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    report.write_text(build_markdown(payload), encoding="utf-8")


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Summarize 200-epoch propagation training sufficiency outputs.")
    parser.add_argument("--status", default=str(DEFAULT_STATUS))
    parser.add_argument("--sequence_sampled", default=str(DEFAULT_SEQUENCE_SAMPLED))
    parser.add_argument("--sequence_full", default=str(DEFAULT_SEQUENCE_FULL))
    parser.add_argument("--public_baselines", default=str(DEFAULT_PUBLIC_BASELINES))
    parser.add_argument("--temporal", default=str(DEFAULT_TEMPORAL))
    parser.add_argument(
        "--out",
        default=str(BENCHMARK_DIR / "propagation_training_sufficiency_200ep_summary_20260811.json"),
    )
    parser.add_argument(
        "--report",
        default=str(DOC_DIR / "propagation_training_sufficiency_200ep_summary_20260811.md"),
    )
    return parser


def main() -> int:
    args = build_arg_parser().parse_args()
    payload = build_payload(args)
    write_payload(payload, Path(args.out), Path(args.report))
    print(
        json.dumps(
            {
                "status": payload["status"],
                "queue_status": payload["queue_status"],
                "current_step": payload["current_step"],
                "out": args.out,
                "report": args.report,
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
