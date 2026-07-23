from __future__ import annotations

import argparse
import csv
import json
import shutil
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Iterable


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

EXPERIMENT_ROOT = BACKEND_ROOT / "experiments" / "coordination_discover_io_reproduction"
DEFAULT_ARCHIVE_NAME = "archive_coordination_discover_final_20260628"

CANONICAL_SOURCE_DIRS = {
    "discover_final": EXPERIMENT_ROOT / "accept_discover_magnn_legacy_vs_core_6d_s5_ep20",
    "discover_stability": EXPERIMENT_ROOT / "discover_leiden_stability_6d_lightweight_final",
    "detect_final": EXPERIMENT_ROOT / "accept_detect_fusion_merged_final",
    "detect_detailed": EXPERIMENT_ROOT / "accept_detect_fusion_lm_gnn_6d_s5_ep20",
}

COPY_PLAN = {
    "discover/discover_metrics_all.csv": CANONICAL_SOURCE_DIRS["discover_final"] / "discover_metrics_all.csv",
    "discover/discover_metrics_mean_std.csv": CANONICAL_SOURCE_DIRS["discover_final"] / "discover_metrics_mean_std.csv",
    "discover/discover_runtime.csv": CANONICAL_SOURCE_DIRS["discover_final"] / "discover_runtime.csv",
    "discover/discover_stability.csv": CANONICAL_SOURCE_DIRS["discover_final"] / "discover_stability.csv",
    "discover/batch_manifest.json": CANONICAL_SOURCE_DIRS["discover_final"] / "batch_manifest.json",
    "discover_stability/discover_stability_summary.csv": CANONICAL_SOURCE_DIRS["discover_stability"] / "discover_stability_summary.csv",
    "discover_stability/discover_stability_pairwise.csv": CANONICAL_SOURCE_DIRS["discover_stability"] / "discover_stability_pairwise.csv",
    "discover_stability/discover_stability_windows.csv": CANONICAL_SOURCE_DIRS["discover_stability"] / "discover_stability_windows.csv",
    "discover_stability/stability_batch_manifest.json": CANONICAL_SOURCE_DIRS["discover_stability"] / "stability_batch_manifest.json",
    "detect/detect_metrics_all.csv": CANONICAL_SOURCE_DIRS["detect_final"] / "detect_metrics_all.csv",
    "detect/detect_metrics_mean_std.csv": CANONICAL_SOURCE_DIRS["detect_final"] / "detect_metrics_mean_std.csv",
    "detect/batch_manifest.json": CANONICAL_SOURCE_DIRS["detect_final"] / "batch_manifest.json",
    "detect/merge_sources.json": CANONICAL_SOURCE_DIRS["detect_final"] / "merge_sources.json",
    "detect/acceptance_report.md": CANONICAL_SOURCE_DIRS["detect_final"] / "acceptance_report.md",
    "notes/README.md": EXPERIMENT_ROOT / "README.md",
    "notes/experiments.md": EXPERIMENT_ROOT / "experiments.md",
    "rerun/run-acceptance-experiments.ps1": EXPERIMENT_ROOT / "run-acceptance-experiments.ps1",
    "rerun/run-detect-fusion-shards.ps1": EXPERIMENT_ROOT / "run-detect-fusion-shards.ps1",
}

DATASETS = ("UAE", "cuba", "russia", "venezuela", "iran", "china")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Archive CoordinationDiscover Discover/Detect experiment outputs into a reusable bundle.")
    parser.add_argument(
        "--archive-dir",
        default=str(EXPERIMENT_ROOT / DEFAULT_ARCHIVE_NAME),
        help="Destination archive directory.",
    )
    parser.add_argument(
        "--dataset-root",
        default="G:\\CISCN\\dataset\\iohunter\\SocGFM\\data\\processed",
        help="Optional IOHunter processed dataset root for event-scale statistics.",
    )
    return parser.parse_args()


def _read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _copy_file(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)


def _to_float(value: object) -> float | None:
    if value in {None, ""}:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _to_int(value: object) -> int | None:
    if value in {None, ""}:
        return None
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _mean(values: Iterable[float]) -> float | None:
    materialized = [float(value) for value in values]
    if not materialized:
        return None
    return round(sum(materialized) / len(materialized), 6)


def _discover_dataset_stats(discover_all_rows: list[dict[str, str]]) -> list[dict[str, object]]:
    grouped: dict[str, dict[str, object]] = {}
    for row in discover_all_rows:
        dataset = str(row.get("dataset"))
        if dataset in grouped:
            continue
        grouped[dataset] = {
            "dataset": dataset,
            "node_count": _to_int(row.get("node_count")),
            "edge_count": _to_int(row.get("edge_count")),
        }
    return [grouped[dataset] for dataset in DATASETS if dataset in grouped]


def _discover_encoder_summary(discover_mean_rows: list[dict[str, str]]) -> list[dict[str, object]]:
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in discover_mean_rows:
        grouped[str(row.get("encoder"))].append(row)
    summary = []
    for encoder, rows in sorted(grouped.items()):
        summary.append(
            {
                "encoder": encoder,
                "avg_modularity": _mean(_to_float(row.get("modularity_mean")) for row in rows if _to_float(row.get("modularity_mean")) is not None),
                "avg_conductance": _mean(_to_float(row.get("conductance_mean")) for row in rows if _to_float(row.get("conductance_mean")) is not None),
                "avg_object_concentration": _mean(
                    _to_float(row.get("mean_object_concentration_mean"))
                    for row in rows
                    if _to_float(row.get("mean_object_concentration_mean")) is not None
                ),
                "avg_runtime_seconds": _mean(
                    _to_float(row.get("runtime_seconds_mean"))
                    for row in rows
                    if _to_float(row.get("runtime_seconds_mean")) is not None
                ),
            }
        )
    return summary


def _detect_summary(detect_mean_rows: list[dict[str, str]]) -> list[dict[str, object]]:
    grouped: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    for row in detect_mean_rows:
        if row.get("discover_encoder") != "magnn" or row.get("lm_backend") != "tfidf":
            continue
        key = (str(row.get("split_mode")), str(row.get("gnn_backend")))
        grouped[key].append(row)
    summary = []
    for (split_mode, gnn_backend), rows in sorted(grouped.items()):
        summary.append(
            {
                "split_mode": split_mode,
                "gnn_backend": gnn_backend,
                "avg_auc": _mean(_to_float(row.get("auc_mean")) for row in rows if _to_float(row.get("auc_mean")) is not None),
                "avg_auprc": _mean(_to_float(row.get("auprc_mean")) for row in rows if _to_float(row.get("auprc_mean")) is not None),
                "avg_macro_f1": _mean(_to_float(row.get("macro_f1_mean")) for row in rows if _to_float(row.get("macro_f1_mean")) is not None),
                "avg_precision_at_k": _mean(
                    _to_float(row.get("precision_at_k_mean"))
                    for row in rows
                    if _to_float(row.get("precision_at_k_mean")) is not None
                ),
                "avg_recall_at_k": _mean(
                    _to_float(row.get("recall_at_k_mean"))
                    for row in rows
                    if _to_float(row.get("recall_at_k_mean")) is not None
                ),
            }
        )
    return summary


def _detect_supervised_by_dataset(detect_mean_rows: list[dict[str, str]]) -> list[dict[str, object]]:
    rows = []
    for row in detect_mean_rows:
        if row.get("discover_encoder") != "magnn" or row.get("lm_backend") != "tfidf" or row.get("split_mode") != "supervised":
            continue
        rows.append(
            {
                "dataset": row.get("dataset"),
                "gnn_backend": row.get("gnn_backend"),
                "auc": _to_float(row.get("auc_mean")),
                "auprc": _to_float(row.get("auprc_mean")),
                "macro_f1": _to_float(row.get("macro_f1_mean")),
            }
        )
    return rows


def _dataset_event_scale(dataset_root: Path | None) -> list[dict[str, object]]:
    if dataset_root is None or not dataset_root.exists():
        return []
    try:
from app.core.coordination_baseline.io_reproduction import iohunter_processed_to_event_table, load_iohunter_processed_dataset
    except Exception:
        return []
    rows: list[dict[str, object]] = []
    for dataset in DATASETS:
        dataset_dir = dataset_root / dataset
        if not dataset_dir.exists():
            continue
        events = iohunter_processed_to_event_table(
            load_iohunter_processed_dataset(dataset_dir),
            dataset_name=dataset,
            max_edges_per_relation=5000,
        )
        relations = sorted(str(value) for value in events["relation"].dropna().unique().tolist()) if "relation" in events.columns else []
        rows.append(
            {
                "dataset": dataset,
                "event_rows": int(len(events)),
                "account_nodes": int(events["account_id"].nunique()) if "account_id" in events.columns else 0,
                "object_ids": int(events["object_id"].nunique()) if "object_id" in events.columns else 0,
                "relations": relations,
            }
        )
    return rows


def _merge_dataset_scale(
    discover_stats: list[dict[str, object]],
    event_scale: list[dict[str, object]],
) -> list[dict[str, object]]:
    event_lookup = {str(row["dataset"]): row for row in event_scale}
    merged = []
    for row in discover_stats:
        dataset = str(row["dataset"])
        event_row = event_lookup.get(dataset, {})
        merged.append(
            {
                "dataset": dataset,
                "event_rows": event_row.get("event_rows"),
                "account_nodes": event_row.get("account_nodes") or row.get("node_count"),
                "object_ids": event_row.get("object_ids"),
                "user_user_edges": row.get("edge_count"),
                "relations": event_row.get("relations", []),
            }
        )
    return merged


def _write_markdown(
    path: Path,
    *,
    archive_name: str,
    dataset_scale: list[dict[str, object]],
    discover_summary: list[dict[str, object]],
    detect_summary: list[dict[str, object]],
    detect_by_dataset: list[dict[str, object]],
) -> None:
    lines = [
        f"# {archive_name}",
        "",
        "This archive bundles the stable CoordinationDiscover Discover/Detect experiment outputs for later reuse.",
        "",
        "## Canonical Source Directories",
        "",
        f"- Discover final: `{CANONICAL_SOURCE_DIRS['discover_final']}`",
        f"- Discover stability: `{CANONICAL_SOURCE_DIRS['discover_stability']}`",
        f"- Detect final merged summary: `{CANONICAL_SOURCE_DIRS['detect_final']}`",
        f"- Detect detailed per-run outputs: `{CANONICAL_SOURCE_DIRS['detect_detailed']}`",
        "",
        "## What To Use",
        "",
        "- Use `discover/discover_metrics_mean_std.csv` for Discover main tables.",
        "- Use `discover_stability/discover_stability_summary.csv` for Discover stability tables.",
        "- Use `detect/detect_metrics_mean_std.csv` for Detect main tables.",
        "- Use `detect/acceptance_report.md` for the final Detect completion note.",
        "- Use `notes/experiments.md` for the chronological experiment log.",
        "",
        "## Dataset Scale",
        "",
        "| Dataset | Event Rows | Account Nodes | Object IDs | User-User Edges | Relations |",
        "|---|---:|---:|---:|---:|---|",
    ]
    for row in dataset_scale:
        relation_text = ", ".join(row.get("relations", []))
        lines.append(
            f"| `{row['dataset']}` | {row.get('event_rows', '')} | {row.get('account_nodes', '')} | {row.get('object_ids', '')} | {row.get('user_user_edges', '')} | {relation_text} |"
        )
    total_events = sum(int(row["event_rows"]) for row in dataset_scale if row.get("event_rows") is not None)
    total_accounts = sum(int(row["account_nodes"]) for row in dataset_scale if row.get("account_nodes") is not None)
    total_objects = sum(int(row["object_ids"]) for row in dataset_scale if row.get("object_ids") is not None)
    total_edges = sum(int(row["user_user_edges"]) for row in dataset_scale if row.get("user_user_edges") is not None)
    lines.extend(
        [
            "",
            f"- Total event rows: `{total_events}`",
            f"- Total account nodes: `{total_accounts}`",
            f"- Total object IDs: `{total_objects}`",
            f"- Total user-user edges: `{total_edges}`",
            "",
            "## Discover Summary",
            "",
            "| Encoder | Avg Modularity | Avg Conductance | Avg Mean Object Concentration | Avg Runtime (s) |",
            "|---|---:|---:|---:|---:|",
        ]
    )
    for row in discover_summary:
        lines.append(
            f"| `{row['encoder']}` | {row.get('avg_modularity', '')} | {row.get('avg_conductance', '')} | {row.get('avg_object_concentration', '')} | {row.get('avg_runtime_seconds', '')} |"
        )
    lines.extend(
        [
            "",
            "## Detect Summary",
            "",
            "| Split | Backend | Avg AUC | Avg AUPRC | Avg Macro-F1 | Avg Precision@K | Avg Recall@K |",
            "|---|---|---:|---:|---:|---:|---:|",
        ]
    )
    for row in detect_summary:
        lines.append(
            f"| `{row['split_mode']}` | `{row['gnn_backend']}` | {row.get('avg_auc', '')} | {row.get('avg_auprc', '')} | {row.get('avg_macro_f1', '')} | {row.get('avg_precision_at_k', '')} | {row.get('avg_recall_at_k', '')} |"
        )
    lines.extend(
        [
            "",
            "## Detect Supervised Per-Dataset Snapshot",
            "",
            "| Dataset | Backend | AUC | AUPRC | Macro-F1 |",
            "|---|---|---:|---:|---:|",
        ]
    )
    for row in detect_by_dataset:
        lines.append(
            f"| `{row['dataset']}` | `{row['gnn_backend']}` | {row.get('auc', '')} | {row.get('auprc', '')} | {row.get('macro_f1', '')} |"
        )
    lines.extend(
        [
            "",
            "## Claim Boundary",
            "",
            "- Discover and Detect are both fully archived and reproducible from the copied summary files plus the canonical source directories above.",
            "- `fusion_gnn` is clearly stronger than `relation_gnn`.",
            "- `fusion_gnn` does not yet beat the stronger `classifier` baseline on average Macro-F1.",
            "- `cross_io` rows on processed IOHunter data should still be treated as protocol fallbacks unless campaign/group metadata is explicitly validated.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    args = parse_args()
    archive_dir = Path(args.archive_dir).resolve()
    dataset_root = Path(args.dataset_root).resolve() if args.dataset_root else None

    missing = [str(path) for path in COPY_PLAN.values() if not path.exists()]
    if missing:
        raise FileNotFoundError(f"Missing source files for archive: {missing}")

    archive_dir.mkdir(parents=True, exist_ok=True)
    for relative_target, source in COPY_PLAN.items():
        _copy_file(source, archive_dir / relative_target)

    discover_all_rows = _read_csv_rows(CANONICAL_SOURCE_DIRS["discover_final"] / "discover_metrics_all.csv")
    discover_mean_rows = _read_csv_rows(CANONICAL_SOURCE_DIRS["discover_final"] / "discover_metrics_mean_std.csv")
    detect_mean_rows = _read_csv_rows(CANONICAL_SOURCE_DIRS["detect_final"] / "detect_metrics_mean_std.csv")

    discover_stats = _discover_dataset_stats(discover_all_rows)
    event_scale = _dataset_event_scale(dataset_root)
    dataset_scale = _merge_dataset_scale(discover_stats, event_scale)
    discover_summary = _discover_encoder_summary(discover_mean_rows)
    detect_summary = _detect_summary(detect_mean_rows)
    detect_by_dataset = _detect_supervised_by_dataset(detect_mean_rows)

    manifest = {
        "archive_name": archive_dir.name,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "archive_dir": str(archive_dir),
        "canonical_source_dirs": {key: str(value) for key, value in CANONICAL_SOURCE_DIRS.items()},
        "copied_files": sorted(COPY_PLAN.keys()),
        "dataset_scale": dataset_scale,
        "discover_summary": discover_summary,
        "detect_summary": detect_summary,
        "detect_supervised_by_dataset": detect_by_dataset,
    }
    (archive_dir / "archive_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    _write_markdown(
        archive_dir / "ARCHIVE_INDEX.md",
        archive_name=archive_dir.name,
        dataset_scale=dataset_scale,
        discover_summary=discover_summary,
        detect_summary=detect_summary,
        detect_by_dataset=detect_by_dataset,
    )
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
