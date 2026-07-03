from __future__ import annotations

import argparse
import csv
import json
import statistics
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd


SCRIPT_DIR = Path(__file__).resolve().parent
BACKEND_ROOT = SCRIPT_DIR.parents[0]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


KT1_ROOT = BACKEND_ROOT / "experiments" / "kt1_io_reproduction"
DEFAULT_DETECT_MERGED = KT1_ROOT / "accept_detect_fusion_merged_final" / "detect_metrics_mean_std.csv"
DEFAULT_DISCOVER_MEAN = KT1_ROOT / "accept_discover_magnn_legacy_vs_core_6d_s5_ep20" / "discover_metrics_mean_std.csv"
DEFAULT_ARCHIVE_MANIFEST = KT1_ROOT / "archive_kt1_final_20260628" / "archive_manifest.json"
DEFAULT_REAL_RUN_DIR = BACKEND_ROOT.parent / "output" / "coordination_runs" / "russia"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build KT1 system integration report, comparison tables, and heatmaps.")
    parser.add_argument("--detect-mean", default=str(DEFAULT_DETECT_MERGED))
    parser.add_argument("--discover-mean", default=str(DEFAULT_DISCOVER_MEAN))
    parser.add_argument("--archive-manifest", default=str(DEFAULT_ARCHIVE_MANIFEST))
    parser.add_argument("--real-run-root", default=str(DEFAULT_REAL_RUN_DIR))
    parser.add_argument("--output-dir", required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    detect_df = pd.read_csv(Path(args.detect_mean))
    discover_df = pd.read_csv(Path(args.discover_mean))
    archive_manifest = json.loads(Path(args.archive_manifest).read_text(encoding="utf-8"))
    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    system_summary = _system_summary(archive_manifest, Path(args.real_run_root))
    detect_summary = _detect_summary_tables(detect_df)
    discover_summary = _discover_summary_tables(discover_df)

    (output_dir / "kt1_system_summary.json").write_text(
        json.dumps(system_summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    _write_csv(output_dir / "kt1_detect_mainline_table.csv", detect_summary["mainline_rows"])
    _write_csv(output_dir / "kt1_detect_backend_comparison.csv", detect_summary["backend_rows"])
    _write_csv(output_dir / "kt1_discover_encoder_comparison.csv", discover_summary["encoder_rows"])
    _write_csv(output_dir / "kt1_discover_detect_claim_rows.csv", detect_summary["claim_rows"])

    _plot_detect_heatmap(
        detect_df,
        output_dir / "kt1_detect_auc_heatmap.png",
        metric="auc_mean",
        title="KT1 Detect AUC Heatmap (magnn + sbert)",
    )
    _plot_detect_heatmap(
        detect_df,
        output_dir / "kt1_detect_macro_f1_heatmap.png",
        metric="macro_f1_mean",
        title="KT1 Detect Macro-F1 Heatmap (magnn + sbert)",
    )
    _plot_discover_bar(
        discover_df,
        output_dir / "kt1_discover_modularity_bar.png",
        metric="modularity_mean",
        title="KT1 Discover Modularity Comparison",
    )

    report = _build_markdown_report(system_summary, detect_summary, discover_summary)
    (output_dir / "kt1_system_report.md").write_text(report, encoding="utf-8")
    print(json.dumps({"output_dir": str(output_dir)}, ensure_ascii=False, indent=2))


def _system_summary(manifest: dict[str, object], real_run_root: Path) -> dict[str, object]:
    scale_rows = manifest.get("dataset_scale", []) if isinstance(manifest.get("dataset_scale"), list) else []
    total_events = sum(int(row.get("event_rows", 0) or 0) for row in scale_rows if isinstance(row, dict))
    total_accounts = sum(int(row.get("account_nodes", 0) or 0) for row in scale_rows if isinstance(row, dict))
    total_objects = sum(int(row.get("object_ids", 0) or 0) for row in scale_rows if isinstance(row, dict))
    total_edges = sum(int(row.get("user_user_edges", 0) or 0) for row in scale_rows if isinstance(row, dict))
    real_run_dirs = sorted(path for path in real_run_root.glob("run_*") if path.is_dir())
    latest_real_run = real_run_dirs[-1] if real_run_dirs else None
    return {
        "dataset_count": len(scale_rows),
        "total_events": total_events,
        "total_accounts": total_accounts,
        "total_objects": total_objects,
        "total_user_user_edges": total_edges,
        "datasets": scale_rows,
        "latest_real_run_dir": str(latest_real_run) if latest_real_run else None,
        "latest_real_run_has_detection_summary": bool(latest_real_run and (latest_real_run / "detection_summary.json").exists()),
        "latest_real_run_has_discovery_summary": bool(latest_real_run and (latest_real_run / "discovery_summary.json").exists()),
        "latest_real_run_has_predictions_csv": bool(latest_real_run and (latest_real_run / "predictions.csv").exists()),
    }


def _detect_summary_tables(df: pd.DataFrame) -> dict[str, list[dict[str, object]]]:
    mainline = df[
        (df["discover_encoder"] == "magnn")
        & (df["gnn_backend"] == "fusion_gnn")
        & (df["lm_backend"] == "sbert")
    ].copy()
    mainline_rows = mainline[
        ["dataset", "split_mode", "auc_mean", "auprc_mean", "macro_f1_mean", "accuracy_mean", "run_count"]
    ].to_dict(orient="records")

    backend_rows: list[dict[str, object]] = []
    subset = df[(df["discover_encoder"] == "magnn") & (df["split_mode"] == "supervised") & (df["lm_backend"] == "sbert")]
    for backend in ("classifier", "fusion_gnn", "relation_gnn"):
        rows = subset[subset["gnn_backend"] == backend]
        if rows.empty:
            continue
        backend_rows.append(
            {
                "gnn_backend": backend,
                "avg_auc": round(rows["auc_mean"].astype(float).mean(), 6),
                "avg_auprc": round(rows["auprc_mean"].astype(float).mean(), 6),
                "avg_macro_f1": round(rows["macro_f1_mean"].astype(float).mean(), 6),
                "avg_accuracy": round(rows["accuracy_mean"].astype(float).mean(), 6),
            }
        )

    claim_rows = []
    for split_mode in ("supervised", "scarce_supervised", "cross_io"):
        rows = mainline[mainline["split_mode"] == split_mode]
        if rows.empty:
            continue
        claim_rows.append(
            {
                "split_mode": split_mode,
                "avg_auc": round(rows["auc_mean"].astype(float).mean(), 6),
                "avg_auprc": round(rows["auprc_mean"].astype(float).mean(), 6),
                "avg_macro_f1": round(rows["macro_f1_mean"].astype(float).mean(), 6),
                "avg_precision_at_k": round(rows["precision_at_k_mean"].astype(float).mean(), 6),
                "avg_recall_at_k": round(rows["recall_at_k_mean"].astype(float).mean(), 6),
            }
        )
    return {
        "mainline_rows": mainline_rows,
        "backend_rows": backend_rows,
        "claim_rows": claim_rows,
    }


def _discover_summary_tables(df: pd.DataFrame) -> dict[str, list[dict[str, object]]]:
    rows = []
    for encoder in ("magnn", "magnn_legacy", "han", "amdn_hage", "zeyan_coexpression"):
        subset = df[df["encoder"] == encoder]
        if subset.empty:
            continue
        row = subset.iloc[0].to_dict()
        rows.append(
            {
                "encoder": encoder,
                "modularity_mean": row.get("modularity_mean"),
                "conductance_mean": row.get("conductance_mean"),
                "mean_object_concentration_mean": row.get("mean_object_concentration_mean"),
                "runtime_seconds_mean": row.get("runtime_seconds_mean"),
            }
        )
    return {"encoder_rows": rows}


def _plot_detect_heatmap(df: pd.DataFrame, output_path: Path, *, metric: str, title: str) -> None:
    subset = df[(df["discover_encoder"] == "magnn") & (df["lm_backend"] == "sbert") & (df["gnn_backend"] == "fusion_gnn")]
    pivot = subset.pivot(index="dataset", columns="split_mode", values=metric).astype(float)
    fig, ax = plt.subplots(figsize=(7, 4))
    im = ax.imshow(pivot.values, aspect="auto", cmap="YlGnBu")
    ax.set_xticks(range(len(pivot.columns)), pivot.columns)
    ax.set_yticks(range(len(pivot.index)), pivot.index)
    ax.set_title(title)
    for i in range(pivot.shape[0]):
        for j in range(pivot.shape[1]):
            ax.text(j, i, f"{pivot.values[i, j]:.3f}", ha="center", va="center", color="black", fontsize=8)
    fig.colorbar(im, ax=ax, shrink=0.8)
    fig.tight_layout()
    fig.savefig(output_path, dpi=220)
    plt.close(fig)


def _plot_discover_bar(df: pd.DataFrame, output_path: Path, *, metric: str, title: str) -> None:
    subset = df[df["encoder"].isin(["magnn", "magnn_legacy", "han", "amdn_hage", "zeyan_coexpression"])].copy()
    subset = subset.sort_values(metric, ascending=False)
    fig, ax = plt.subplots(figsize=(7, 4))
    ax.bar(subset["encoder"], subset[metric].astype(float), color=["#2563eb", "#0f766e", "#d97706", "#dc2626", "#7c3aed"])
    ax.set_title(title)
    ax.set_ylabel(metric)
    for index, value in enumerate(subset[metric].astype(float).tolist()):
        ax.text(index, value, f"{value:.3f}", ha="center", va="bottom", fontsize=8)
    fig.tight_layout()
    fig.savefig(output_path, dpi=220)
    plt.close(fig)


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def _build_markdown_report(
    system_summary: dict[str, object],
    detect_summary: dict[str, list[dict[str, object]]],
    discover_summary: dict[str, list[dict[str, object]]],
) -> str:
    lines = [
        "# KT1 System Integration Report",
        "",
        "## System Status",
        f"- Registered datasets: {system_summary['dataset_count']}",
        f"- Total events: {system_summary['total_events']}",
        f"- Total accounts: {system_summary['total_accounts']}",
        f"- Latest real rerun dir: {system_summary['latest_real_run_dir']}",
        f"- Latest rerun has discover summary: {system_summary['latest_real_run_has_discovery_summary']}",
        f"- Latest rerun has detection summary: {system_summary['latest_real_run_has_detection_summary']}",
        f"- Latest rerun has predictions.csv: {system_summary['latest_real_run_has_predictions_csv']}",
        "",
        "## Detect Mainline (magnn + fusion_gnn + sbert)",
        "",
        "| Split | Avg AUC | Avg AUPRC | Avg Macro-F1 | Avg Precision@K | Avg Recall@K |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for row in detect_summary["claim_rows"]:
        lines.append(
            f"| {row['split_mode']} | {row['avg_auc']:.6f} | {row['avg_auprc']:.6f} | {row['avg_macro_f1']:.6f} | {row['avg_precision_at_k']:.6f} | {row['avg_recall_at_k']:.6f} |"
        )
    lines.extend(
        [
            "",
            "## Detect Backend Comparison (supervised, magnn, sbert)",
            "",
            "| Backend | Avg AUC | Avg AUPRC | Avg Macro-F1 | Avg Accuracy |",
            "|---|---:|---:|---:|---:|",
        ]
    )
    for row in detect_summary["backend_rows"]:
        lines.append(
            f"| {row['gnn_backend']} | {row['avg_auc']:.6f} | {row['avg_auprc']:.6f} | {row['avg_macro_f1']:.6f} | {row['avg_accuracy']:.6f} |"
        )
    lines.extend(
        [
            "",
            "## Discover Encoder Comparison",
            "",
            "| Encoder | Modularity | Conductance | Mean Object Concentration | Runtime(s) |",
            "|---|---:|---:|---:|---:|",
        ]
    )
    for row in discover_summary["encoder_rows"]:
        lines.append(
            f"| {row['encoder']} | {float(row['modularity_mean']):.6f} | {float(row['conductance_mean']):.6f} | {float(row['mean_object_concentration_mean']):.6f} | {float(row['runtime_seconds_mean']):.6f} |"
        )
    lines.extend(
        [
            "",
            "## Deliverables",
            "",
            "- `kt1_detect_mainline_table.csv`",
            "- `kt1_detect_backend_comparison.csv`",
            "- `kt1_discover_encoder_comparison.csv`",
            "- `kt1_detect_auc_heatmap.png`",
            "- `kt1_detect_macro_f1_heatmap.png`",
            "- `kt1_discover_modularity_bar.png`",
        ]
    )
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    main()
