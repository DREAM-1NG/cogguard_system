from __future__ import annotations

import argparse
import json
import math
import pickle
from collections import defaultdict
from pathlib import Path
from statistics import mean, pstdev
from typing import Any, Iterable, Mapping


BENCHMARK_DIR = Path(__file__).resolve().parent
DEFAULT_FAIR_MATRIX = BENCHMARK_DIR / "propagation_fair_learned_matrix_20260810.json"
DEFAULT_PRIMARY_STABLE = BENCHMARK_DIR / "propagation_sota_primary_stable_20260810.json"
DEFAULT_TEMPORAL_STABLE = BENCHMARK_DIR / "propagation_sota_frontier_temporal_stable_20260810.json"
DEFAULT_TGN_RESULTS = Path(r"G:\CISCN\CogGuard\subsystems\kt2_repos\tgn\results")
DEFAULT_DOC_DIR = Path(
    r"G:\CISCN\CogGuard\.worktrees\refactor-system\system\doc\research\propagation_paper_deep_reads"
)

MACRO_FAIR_METRICS = ("msle", "mae", "trend_mae", "trend_rmse", "direction_accuracy")
MICRO_FAIR_METRICS = ("candidate_recall_full", "hits@10", "hits@50", "hits@100", "mrr", "ndcg@100")
CASFT_METRICS = ("msle", "mae", "mape_percent", "smape")


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


def summarize_rows(rows: Iterable[Mapping[str, Any]], metrics: Iterable[str]) -> list[dict[str, Any]]:
    groups: dict[tuple[str, str], dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    status_groups: dict[tuple[str, str], set[str]] = defaultdict(set)
    seeds: dict[tuple[str, str], set[int]] = defaultdict(set)
    for row in rows:
        dataset = str(row.get("dataset", ""))
        model = str(row.get("model", ""))
        key = (dataset, model)
        status_groups[key].add(str(row.get("status", "")))
        try:
            seeds[key].add(int(row.get("seed", 0)))
        except (TypeError, ValueError):
            pass
        for metric in metrics:
            value = finite(row.get(metric))
            if value is not None:
                groups[key][metric].append(value)
    summary: list[dict[str, Any]] = []
    for key in sorted(set(groups) | set(status_groups)):
        dataset, model = key
        record: dict[str, Any] = {
            "dataset": dataset,
            "model": model,
            "n": max([len(values) for values in groups.get(key, {}).values()] or [0]),
            "seeds": sorted(seeds.get(key, set())),
            "statuses": sorted(status_groups.get(key, set())),
        }
        for metric in metrics:
            values = groups.get(key, {}).get(metric, [])
            if values:
                record[f"{metric}_mean"] = mean(values)
                record[f"{metric}_std"] = pstdev(values) if len(values) > 1 else 0.0
                record[f"{metric}_n"] = len(values)
        summary.append(record)
    return summary


def fair_rows(fair_payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    return [
        dict(row)
        for row in fair_payload.get("rows", [])
        if isinstance(row, Mapping) and row.get("status") == "ok" and row.get("fair_protocol_passed") is True
    ]


def casft_rows(primary_payload: Any) -> list[dict[str, Any]]:
    return [
        dict(row)
        for row in rows_from_payload(primary_payload)
        if row.get("model") == "CasFT" and row.get("status") == "ok"
    ]


def forest_status_rows(primary_payload: Any) -> list[dict[str, Any]]:
    rows = []
    for row in rows_from_payload(primary_payload):
        if row.get("model") != "FOREST":
            continue
        rows.append(
            {
                "dataset": row.get("dataset"),
                "model": "FOREST",
                "seed": row.get("seed"),
                "status": row.get("status"),
                "hits@100": row.get("hits@100"),
                "msle": row.get("msle"),
                "mae": row.get("mae"),
                "track_status": "pending_fair_adapter",
                "note": "FOREST public-code adapter ran, but macro values are missing/non-finite under the current local capped run.",
            }
        )
    return rows


def temporal_proxy_status_rows(temporal_payload: Any) -> list[dict[str, Any]]:
    rows = []
    for row in rows_from_payload(temporal_payload):
        model = str(row.get("model"))
        score_source = row.get("event_topk_score_source") or "transition_popularity_proxy_not_learned"
        rows.append(
            {
                "dataset": row.get("dataset"),
                "model": model,
                "status": row.get("status"),
                "upstream_training": "completed" if row.get("status") == "ok" else row.get("status"),
                "event_topk_score_source": score_source,
                "learned_event_topk_available": bool(row.get("learned_event_topk_available", False)),
                "proxy_hits@100_removed_from_verdict": row.get("hits@100"),
                "note": row.get("note"),
            }
        )
    return rows


def load_tgn_native_rows(results_dir: Path) -> list[dict[str, Any]]:
    rows = []
    for dataset in ("douban", "twitter", "memetracker"):
        path = results_dir / f"kt2_kt2_{dataset}_tgn.pkl"
        if not path.is_file():
            rows.append(
                {
                    "dataset": dataset,
                    "model": "TGN",
                    "status": "not_reported",
                    "test_ap": None,
                    "new_node_test_ap": None,
                    "source_file": str(path),
                }
            )
            continue
        try:
            payload = pickle.loads(path.read_bytes())
        except Exception as exc:  # pragma: no cover - defensive for local artifacts.
            rows.append(
                {
                    "dataset": dataset,
                    "model": "TGN",
                    "status": "parse_failed",
                    "note": f"{type(exc).__name__}: {exc}",
                    "source_file": str(path),
                }
            )
            continue
        rows.append(
            {
                "dataset": dataset,
                "model": "TGN",
                "status": "ok",
                "test_ap": finite(payload.get("test_ap")),
                "new_node_test_ap": finite(payload.get("new_node_test_ap")),
                "train_loss": mean(payload.get("train_losses", [])) if payload.get("train_losses") else None,
                "source_file": str(path),
                "track_note": "Native temporal link prediction AP from upstream TGN result pickle; not a cascade next-hop Top-K metric.",
            }
        )
    return rows


def dygformer_native_rows(temporal_payload: Any) -> list[dict[str, Any]]:
    datasets = sorted({str(row.get("dataset")) for row in rows_from_payload(temporal_payload) if row.get("model") == "DyGFormer/DyGLib"})
    return [
        {
            "dataset": dataset,
            "model": "DyGFormer/DyGLib",
            "status": "training_completed_metric_not_structured",
            "test_ap": None,
            "new_node_test_ap": None,
            "track_note": "The stable run logs show upstream training completed, but AP/AUC were not captured into a structured artifact.",
        }
        for dataset in datasets
    ]


def relative_delta(ours: float | None, baseline: float | None, lower_is_better: bool) -> float | None:
    if ours is None or baseline in (None, 0):
        return None
    raw = (baseline - ours) / baseline * 100.0 if lower_is_better else (ours - baseline) / baseline * 100.0
    return raw


def fair_pair_deltas(summary: list[dict[str, Any]], metrics: Iterable[str], lower_is_better: set[str]) -> list[dict[str, Any]]:
    by_key = {(row["dataset"], row["model"]): row for row in summary}
    deltas = []
    for dataset in sorted({row["dataset"] for row in summary}):
        ours = by_key.get((dataset, "Ours"))
        minds = by_key.get((dataset, "MINDS"))
        if not ours or not minds:
            continue
        record = {"dataset": dataset, "baseline": "MINDS", "target": "Ours"}
        for metric in metrics:
            record[f"{metric}_ours"] = ours.get(f"{metric}_mean")
            record[f"{metric}_minds"] = minds.get(f"{metric}_mean")
            record[f"{metric}_relative_delta_percent"] = relative_delta(
                finite(ours.get(f"{metric}_mean")),
                finite(minds.get(f"{metric}_mean")),
                metric in lower_is_better,
            )
        deltas.append(record)
    return deltas


def table(headers: list[str], rows: list[list[Any]]) -> str:
    lines = ["| " + " | ".join(headers) + " |", "| " + " | ".join("---" for _ in headers) + " |"]
    lines.extend("| " + " | ".join(str(cell) for cell in row) + " |" for row in rows)
    return "\n".join(lines)


def metric_cell(row: Mapping[str, Any], metric: str) -> str:
    mean_value = row.get(f"{metric}_mean")
    std_value = row.get(f"{metric}_std")
    if finite(mean_value) is None:
        return "-"
    return f"{fmt(mean_value)}+/-{fmt(std_value)}"


def build_markdown(payload: Mapping[str, Any]) -> str:
    macro_rows = [
        [
            row["dataset"],
            row["model"],
            row["n"],
            ",".join(str(seed) for seed in row.get("seeds", [])),
            metric_cell(row, "msle"),
            metric_cell(row, "mae"),
            metric_cell(row, "trend_mae"),
            metric_cell(row, "direction_accuracy"),
        ]
        for row in payload["tracks"]["macro_fair"]["summary"]
    ]
    micro_rows = [
        [
            row["dataset"],
            row["model"],
            row["n"],
            ",".join(str(seed) for seed in row.get("seeds", [])),
            metric_cell(row, "candidate_recall_full"),
            metric_cell(row, "hits@100"),
            metric_cell(row, "mrr"),
            metric_cell(row, "ndcg@100"),
        ]
        for row in payload["tracks"]["micro_fair"]["summary"]
    ]
    casft_rows_md = [
        [
            row["dataset"],
            row["model"],
            row["n"],
            ",".join(str(seed) for seed in row.get("seeds", [])),
            metric_cell(row, "msle"),
            metric_cell(row, "mae"),
            metric_cell(row, "mape_percent"),
            metric_cell(row, "smape"),
        ]
        for row in payload["tracks"]["macro_only_external"]["summary"]
    ]
    temporal_rows = [
        [
            row.get("dataset"),
            row.get("model"),
            row.get("status"),
            fmt(row.get("test_ap")),
            fmt(row.get("new_node_test_ap")),
            fmt(row.get("train_loss")),
            row.get("track_note", ""),
        ]
        for row in payload["tracks"]["temporal_link_prediction"]["rows"]
    ]
    adapted_rows = [
        [
            row.get("dataset"),
            row.get("model"),
            row.get("status"),
            row.get("upstream_training"),
            row.get("event_topk_score_source"),
            row.get("learned_event_topk_available"),
        ]
        for row in payload["tracks"]["adapted_next_hop"]["rows"]
    ]
    forest_rows_md = [
        [
            row.get("dataset"),
            row.get("seed"),
            row.get("status"),
            fmt(row.get("hits@100")),
            row.get("track_status"),
            row.get("note"),
        ]
        for row in payload["tracks"]["pending_methods"]["forest_rows"]
    ]
    return "\n".join(
        [
            "# Propagation Task-Track Key Metrics 2026-08-10",
            "",
            f"- fair_protocol_passed: `{payload['source_audit']['fair_protocol_passed']}`",
            f"- fair_rows: `{payload['source_audit']['fair_rows']}`",
            "- principle: only methods with the same input/output/supervision/metric are placed in the same verdict table.",
            "",
            "## Track 1: Macro Fair Scale/Trend",
            "",
            "Comparable methods: Ours vs MINDS under the same FOREST split, obs-ratios, caps, epochs, candidate universe and metric implementation.",
            "",
            table(["Dataset", "Method", "N", "Seeds", "MSLE", "MAE", "Trend MAE", "Direction Acc"], macro_rows),
            "",
            "## Track 2: Micro Fair Next-Hop",
            "",
            "Comparable methods: Ours vs MINDS under the same prefix-window next-user ranking protocol.",
            "",
            table(["Dataset", "Method", "N", "Seeds", "Candidate Recall", "Hits@100", "MRR", "NDCG@100"], micro_rows),
            "",
            "## Track 3: Macro-Only External Baseline",
            "",
            "CasFT is reported separately because it is a scale/trend model and does not output next-hop users.",
            "",
            table(["Dataset", "Method", "N", "Seeds", "MSLE", "MAE", "MAPE", "sMAPE"], casft_rows_md),
            "",
            "## Track 4: Native Temporal Link Prediction",
            "",
            "TGN/DyGFormer are link-prediction methods. Their native AP is not equivalent to cascade next-hop Top-K.",
            "",
            table(["Dataset", "Method", "Status", "Test AP", "New-node Test AP", "Train Loss", "Note"], temporal_rows),
            "",
            "## Track 5: Adapted Next-Hop From Temporal Models",
            "",
            "This track is intentionally pending until learned edge scores are used to rank event-level candidate users.",
            "",
            table(["Dataset", "Method", "Status", "Upstream Training", "Top-K Score Source", "Learned Top-K Available"], adapted_rows),
            "",
            "## Pending / Not In Verdict",
            "",
            table(["Dataset", "Seed", "Status", "Hits@100", "Track Status", "Note"], forest_rows_md),
            "",
            "## Key Interpretation",
            "",
            "- Macro fair track: Ours improves MSLE and trend MAE against MINDS on all three datasets, but MAE is worse on Twitter and Memetracker.",
            "- Micro fair track: Ours and MINDS have almost identical Hits@100; Ours is slightly lower on MRR/NDCG, so next-hop improvement is not supported yet.",
            "- CasFT is useful for macro-only discussion but should not be mixed with macro/micro joint verdicts until its prefix-window protocol is aligned.",
            "- TGN/DyGFormer need a learned-score adapter before they can enter the next-hop Top-K table.",
            "",
        ]
    )


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    fair_payload = load_json(args.fair_matrix)
    primary_payload = load_json(args.primary_stable)
    temporal_payload = load_json(args.temporal_stable)
    if not isinstance(fair_payload, Mapping):
        raise RuntimeError(f"Fair matrix is missing or invalid: {args.fair_matrix}")
    fair = fair_rows(fair_payload)
    macro_summary = summarize_rows(fair, MACRO_FAIR_METRICS)
    micro_summary = summarize_rows(fair, MICRO_FAIR_METRICS)
    casft_summary = summarize_rows(casft_rows(primary_payload), CASFT_METRICS)
    temporal_rows = load_tgn_native_rows(Path(args.tgn_results_dir)) + dygformer_native_rows(temporal_payload)
    adapted_rows = temporal_proxy_status_rows(temporal_payload)
    return {
        "schema": "cogguard.propagation.task_track_key_metrics.v1",
        "source_audit": {
            "fair_protocol_passed": bool(fair_payload.get("protocol_audit", {}).get("passed")),
            "fair_rows": len(fair),
            "fair_protocol_id": fair_payload.get("protocol_id"),
            "primary_stable_source": str(args.primary_stable),
            "temporal_stable_source": str(args.temporal_stable),
        },
        "tracks": {
            "macro_fair": {
                "task": "cascade final size and future trend prediction",
                "verdict_comparable": True,
                "summary": macro_summary,
                "deltas_vs_minds": fair_pair_deltas(macro_summary, MACRO_FAIR_METRICS, {"msle", "mae", "trend_mae", "trend_rmse"}),
            },
            "micro_fair": {
                "task": "cascade prefix next-hop user ranking",
                "verdict_comparable": True,
                "summary": micro_summary,
                "deltas_vs_minds": fair_pair_deltas(micro_summary, MICRO_FAIR_METRICS, set()),
            },
            "macro_only_external": {
                "task": "macro-only scale/trend prediction",
                "verdict_comparable": False,
                "summary": casft_summary,
                "boundary": "CasFT rows are external macro-only evidence and not part of the same macro/micro verdict.",
            },
            "temporal_link_prediction": {
                "task": "temporal edge/link prediction",
                "verdict_comparable": False,
                "rows": temporal_rows,
                "boundary": "Native AP/AUC are not cascade next-hop Top-K metrics.",
            },
            "adapted_next_hop": {
                "task": "event-level next-hop ranking adapted from temporal edge scores",
                "verdict_comparable": False,
                "rows": adapted_rows,
                "boundary": "Pending learned scorer; proxy Top-K metrics are excluded from verdict.",
            },
            "pending_methods": {
                "forest_rows": forest_status_rows(primary_payload),
            },
        },
    }


def write_payload(payload: Mapping[str, Any], out: Path, report: Path) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    report.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    report.write_text(build_markdown(payload), encoding="utf-8")


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build task-track key metric tables for propagation experiments.")
    parser.add_argument("--fair_matrix", default=str(DEFAULT_FAIR_MATRIX))
    parser.add_argument("--primary_stable", default=str(DEFAULT_PRIMARY_STABLE))
    parser.add_argument("--temporal_stable", default=str(DEFAULT_TEMPORAL_STABLE))
    parser.add_argument("--tgn_results_dir", default=str(DEFAULT_TGN_RESULTS))
    parser.add_argument("--out", default=str(BENCHMARK_DIR / "propagation_task_track_key_metrics_20260810.json"))
    parser.add_argument(
        "--report",
        default=str(DEFAULT_DOC_DIR / "propagation_task_track_key_metrics_20260810.md"),
    )
    return parser


def main() -> int:
    args = build_arg_parser().parse_args()
    payload = build_payload(args)
    write_payload(payload, Path(args.out), Path(args.report))
    print(json.dumps({"status": "ok", "out": args.out, "report": args.report}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
