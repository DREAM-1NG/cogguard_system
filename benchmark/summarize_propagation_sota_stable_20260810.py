from __future__ import annotations

import argparse
import json
import math
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from statistics import mean, pstdev
from typing import Any, Iterable, Mapping


MODEL_ALIASES = {
    "KT2SequenceJointModel": "Ours",
    "PropagationAnalysisSequenceJointModel": "Ours",
    "DyGFormer/DyGLib": "DyGFormer/DyGLib",
    "dyglib": "DyGFormer/DyGLib",
    "tgn": "TGN",
}

METRICS = (
    "msle",
    "mae",
    "rmse",
    "mape_percent",
    "direction_accuracy",
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


def load_json(path: str | Path) -> Any:
    p = Path(path)
    if not p.is_file():
        return None
    return json.loads(p.read_text(encoding="utf-8-sig"))


def rows_from_payload(payload: Any) -> list[dict[str, Any]]:
    if payload is None:
        return []
    if isinstance(payload, list):
        return [dict(row) for row in payload if isinstance(row, Mapping)]
    if isinstance(payload, Mapping):
        rows = payload.get("rows", [])
        return [dict(row) for row in rows if isinstance(row, Mapping)]
    return []


def normalize_model(value: Any) -> str:
    raw = str(value or "")
    return MODEL_ALIASES.get(raw, raw)


def finite(value: Any) -> float | None:
    if isinstance(value, (int, float)) and math.isfinite(float(value)):
        return float(value)
    return None


def selected_rows(primary: list[dict[str, Any]], sequence: list[dict[str, Any]], frontier: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in sequence:
        model = normalize_model(row.get("model"))
        if model not in {"Ours", "MINDS"}:
            continue
        copied = dict(row)
        copied["model"] = model
        copied["source_file"] = "sequence_vs_minds"
        rows.append(copied)
    for row in primary:
        model = normalize_model(row.get("model"))
        if model not in {"FOREST", "CasFT"}:
            continue
        copied = dict(row)
        copied["model"] = model
        copied["source_file"] = "primary_forest_casft"
        if model == "FOREST":
            copied["quality_warning"] = "FOREST adapter completed with non-finite training loss under this Windows/local protocol; use as runnable baseline evidence only."
        rows.append(copied)
    for row in frontier:
        model = normalize_model(row.get("model"))
        if model not in {"DyGFormer/DyGLib", "TGN"}:
            continue
        copied = dict(row)
        copied["model"] = model
        copied["source_file"] = "frontier_temporal"
        rows.append(copied)
    return rows


def group_stats(rows: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[tuple[str, str], list[Mapping[str, Any]]] = defaultdict(list)
    for row in rows:
        groups[(str(row.get("model")), str(row.get("dataset")))].append(row)
    summary = []
    for (model, dataset), items in sorted(groups.items()):
        record: dict[str, Any] = {
            "model": model,
            "dataset": dataset,
            "n_rows": len(items),
            "ok_rows": sum(1 for item in items if str(item.get("status")) == "ok"),
            "statuses": sorted({str(item.get("status")) for item in items}),
            "reproduction_levels": sorted({str(item.get("reproduction_level")) for item in items if item.get("reproduction_level")}),
        }
        for metric in METRICS:
            values = [finite(item.get(metric)) for item in items]
            values = [value for value in values if value is not None]
            if values:
                record[f"{metric}_mean"] = mean(values)
                record[f"{metric}_std"] = pstdev(values) if len(values) > 1 else 0.0
                record[f"{metric}_n"] = len(values)
        summary.append(record)
    return summary


def format_number(value: Any) -> str:
    if not isinstance(value, (int, float)) or not math.isfinite(float(value)):
        return "-"
    return f"{float(value):.4f}"


def table(headers: list[str], rows: list[list[Any]]) -> str:
    lines = ["| " + " | ".join(headers) + " |", "| " + " | ".join("---" for _ in headers) + " |"]
    for row in rows:
        lines.append("| " + " | ".join(str(cell) for cell in row) + " |")
    return "\n".join(lines)


def build_markdown(args: argparse.Namespace, strict_payload: Any, selected: list[dict[str, Any]], summary: list[dict[str, Any]]) -> str:
    strict_rows = rows_from_payload(strict_payload)
    strict_failures = strict_payload.get("failures", []) if isinstance(strict_payload, Mapping) else []
    strict_failure_rows = []
    for failure in strict_failures:
        strict_failure_rows.append(
            [
                failure.get("model", "-"),
                failure.get("dataset", "-"),
                failure.get("seed", "-"),
                failure.get("status", "-"),
                failure.get("note", "-"),
            ]
        )

    macro_rows = []
    for row in summary:
        if any(key in row for key in ("msle_mean", "mae_mean", "rmse_mean")):
            macro_rows.append(
                [
                    row["dataset"],
                    row["model"],
                    row["n_rows"],
                    ",".join(row["statuses"]),
                    format_number(row.get("msle_mean")),
                    format_number(row.get("mae_mean")),
                    format_number(row.get("rmse_mean")),
                    format_number(row.get("direction_accuracy_mean")),
                ]
            )

    micro_rows = []
    for row in summary:
        if any(key in row for key in ("hits@10_mean", "map@10_mean", "mrr_mean")):
            micro_rows.append(
                [
                    row["dataset"],
                    row["model"],
                    row["n_rows"],
                    ",".join(row["statuses"]),
                    format_number(row.get("candidate_recall_full_mean")),
                    format_number(row.get("hits@10_mean")),
                    format_number(row.get("hits@50_mean")),
                    format_number(row.get("hits@100_mean")),
                    format_number(row.get("map@10_mean")),
                    format_number(row.get("map@50_mean")),
                    format_number(row.get("map@100_mean")),
                    format_number(row.get("mrr_mean")),
                    format_number(row.get("ndcg@100_mean")),
                ]
            )

    method_rows = []
    for row in selected:
        method_rows.append(
            [
                row.get("dataset", "-"),
                row.get("model", "-"),
                row.get("seed", row.get("experiment_seed", "-")),
                row.get("status", "-"),
                row.get("reproduction_level", "-"),
                row.get("source_file", "-"),
                row.get("quality_warning", row.get("note", "")) or "",
            ]
        )

    lines = [
        "# Propagation SOTA Stable Matrix Report 2026-08-10",
        "",
        f"- generated_at: `{datetime.now().isoformat(timespec='seconds')}`",
        "- evidence_level: `resource_bounded_stable_matrix`",
        "- strict_full_validation_passed: `false`",
        "- datasets: `douban, twitter, memetracker`",
        "- seeds: `42, 43, 44` for Ours/MINDS/FOREST/CasFT; DyGFormer/TGN use upstream `num_runs=1` plus the shared candidate protocol.",
        "- boundary: this report completes a local stable comparison matrix under explicit caps. It is not an uncapped strict full validation.",
        "",
        "## Stable Run Configuration",
        "",
        table(
            ["Component", "Configuration", "Interpretation"],
            [
                ["Ours vs MINDS", "300 cascades, 5 epochs, 3 seeds, 3 datasets", "Completed earlier and reused as trainable paired evidence."],
                ["FOREST", "1 epoch, 2 train batches, 2 eval batches, RL disabled", "Runnable public-code adapter evidence; non-finite loss is flagged."],
                ["CasFT", "200 events, 1 epoch, timesteps=2, 3 seeds, 3 datasets", "Upstream CasFT training executes under local resource cap."],
                ["DyGFormer/TGN", "50 cascades, 1 epoch, CPU, upstream smoke training", "Upstream scripts complete; reported Top-K metrics remain shared candidate-protocol metrics."],
            ],
        ),
        "",
        "## Strict Full Attempt Failures Kept For Provenance",
        "",
        table(["Model", "Dataset", "Seed", "Status", "Note"], strict_failure_rows or [["-", "-", "-", "-", "No strict failure payload found."]]),
        "",
        "## Macro / Scale Metrics",
        "",
        table(
            ["Dataset", "Method", "Rows", "Status", "MSLE", "MAE", "RMSE", "Direction Acc"],
            macro_rows,
        ),
        "",
        "## Micro / Next-Hop Metrics",
        "",
        table(
            ["Dataset", "Method", "Rows", "Status", "Candidate Recall", "Hits@10", "Hits@50", "Hits@100", "MAP@10", "MAP@50", "MAP@100", "MRR", "NDCG@100"],
            micro_rows,
        ),
        "",
        "## Raw Method Rows",
        "",
        table(["Dataset", "Method", "Seed", "Status", "Reproduction Level", "Source", "Warning/Note"], method_rows),
        "",
        "## Interpretation",
        "",
        "- The matrix is now stable and multi-dataset, but resource-bounded. It should be used for engineering comparison and pipeline evidence, not final paper-level SOTA claims.",
        "- The strongest paired trainable comparison remains Ours vs MINDS on the 300-cascade, 5-epoch, 3-seed protocol.",
        "- FOREST needs a separate numerical-stability pass before it can be treated as a reliable competitive baseline under this Windows adapter.",
        "- DyGFormer/TGN upstream training now launches successfully after the runtime shim path fix, but event-level Top-K values are still produced by the common candidate protocol for comparability.",
    ]
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--primary", required=True)
    parser.add_argument("--sequence", required=True)
    parser.add_argument("--frontier", required=True)
    parser.add_argument("--strict-primary", required=True)
    parser.add_argument("--out-md", required=True)
    parser.add_argument("--out-json", required=True)
    args = parser.parse_args()

    primary_payload = load_json(args.primary)
    sequence_payload = load_json(args.sequence)
    frontier_payload = load_json(args.frontier)
    strict_payload = load_json(args.strict_primary)

    primary = rows_from_payload(primary_payload)
    sequence = rows_from_payload(sequence_payload)
    frontier = rows_from_payload(frontier_payload)
    selected = selected_rows(primary, sequence, frontier)
    summary = group_stats(selected)

    out_json = Path(args.out_json)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(
        json.dumps(
            {
                "schema": "cogguard.propagation_sota_stable_matrix_summary.v1",
                "status": "ok",
                "evidence_level": "resource_bounded_stable_matrix",
                "strict_full_validation_passed": False,
                "selected_rows": selected,
                "summary": summary,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    out_md = Path(args.out_md)
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_md.write_text(build_markdown(args, strict_payload, selected, summary), encoding="utf-8")
    print(json.dumps({"status": "ok", "out_md": str(out_md), "out_json": str(out_json), "rows": len(selected)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
