from __future__ import annotations

import argparse
import json
import numbers
from pathlib import Path

import pandas as pd
BACKEND_ROOT = Path(__file__).resolve().parents[1]
CoordinationDiscover_ROOT = BACKEND_ROOT / "experiments" / "coordination_discover_io_reproduction"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the final CoordinationDiscover experiment report from full result artifacts.")
    parser.add_argument("--system-report-dir", default=str(CoordinationDiscover_ROOT / "coordination_discover_system_report"))
    parser.add_argument("--detect-ablation-dir", default=str(CoordinationDiscover_ROOT / "coordination_discover_detect_ablation"))
    parser.add_argument("--detect-baseline-csv", default="")
    parser.add_argument("--output-dir", required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    system_dir = Path(args.system_report_dir).resolve()
    ablation_dir = Path(args.detect_ablation_dir).resolve()
    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    system_summary = json.loads((system_dir / "coordination_discover_system_summary.json").read_text(encoding="utf-8"))
    if args.detect_baseline_csv:
        baseline_df = pd.read_csv(Path(args.detect_baseline_csv).resolve())
        detect_mainline = _derive_detect_table_from_baseline(baseline_df)
    else:
        detect_mainline = pd.read_csv(system_dir / "coordination_discover_detect_mainline_table.csv")
    detect_mainline_report = _build_detect_mainline_report_table(detect_mainline)
    detect_mainline_report.to_csv(output_dir / "coordination_discover_detect_mainline_table.csv", index=False)
    detect_ablation = pd.read_csv(ablation_dir / "coordination_discover_detect_ablation_mean_std.csv") if (ablation_dir / "coordination_discover_detect_ablation_mean_std.csv").exists() else pd.DataFrame()

    report_lines = [
        "# CoordinationDiscover Full Experiment Report",
        "",
        "## Dataset Scale",
        f"- Datasets: {system_summary['dataset_count']}",
        f"- Total events: {system_summary['total_events']}",
        f"- Total accounts: {system_summary['total_accounts']}",
        f"- Total objects: {system_summary['total_objects']}",
        f"- Total user-user edges: {system_summary['total_user_user_edges']}",
        "",
        "## Detect Results",
        "",
        "### Detect Main Experiment Table (Supervised)",
        "",
        _df_to_markdown(detect_mainline_report),
    ]

    if not detect_ablation.empty:
        detect_ablation_focus = detect_ablation[
            detect_ablation["ablation"].isin(
                ["full", "without_lm", "without_reweighted_edges", "no_community_features", "no_discover_embeddings", "classifier_struct_only"]
            )
        ].copy()
        detect_ablation_focus = detect_ablation_focus[detect_ablation_focus["split_mode"] == "supervised"].copy()
        detect_ablation_focus["dataset"] = detect_ablation_focus["dataset"].map(_simple_dataset_name)
        ablation_overall = _build_detect_ablation_summary_table(detect_ablation_focus)
        ablation_detail = _build_detect_ablation_detail_table(detect_ablation_focus)
        ablation_overall.to_csv(output_dir / "coordination_discover_detect_ablation_overall.csv", index=False)
        ablation_overall.to_csv(output_dir / "coordination_discover_detect_ablation_auc_maxf1.csv", index=False)
        report_lines.extend(
            [
                "",
                "## Detect Ablation Summary (AUC + Max-F1, Supervised)",
                "",
                _df_to_markdown(ablation_overall),
                "",
                "## Detect Ablation Detail by Dataset (AUC + Max-F1, Supervised)",
                "",
                _df_to_markdown(ablation_detail),
                "",
                "## Detect Ablation Notes",
                "",
                "- All ablation labels are reported in `full model / w/o component` style.",
                "- `without_reweighted_edges` measures the contribution of Discover edge reweighting.",
                "- `without_lm` measures the contribution of SBERT semantic features.",
                "- `no_community_features` measures the contribution of community-level signals.",
            ]
        )

    report_lines.extend(
        [
            "",
            "## Figures",
            "",
            "- `coordination_discover_detect_main_metrics_heatmap.png`",
            "- `coordination_discover_detect_ablation_auc_maxf1_combined.png`",
        ]
    )

    (output_dir / "coordination_discover_full_experiment_report.md").write_text("\n".join(report_lines) + "\n", encoding="utf-8")
    print(json.dumps({"output_dir": str(output_dir)}, ensure_ascii=False, indent=2))


def _df_to_markdown(df: pd.DataFrame) -> str:
    if df.empty:
        return "_No rows_"
    columns = [str(column) for column in df.columns]
    lines = [
        "| " + " | ".join(columns) + " |",
        "| " + " | ".join("---" for _ in columns) + " |",
    ]
    for _, row in df.iterrows():
        values = []
        for column in columns:
            value = row[column]
            if pd.isna(value):
                values.append("")
            elif isinstance(value, numbers.Integral):
                values.append(str(int(value)))
            elif isinstance(value, numbers.Real):
                values.append(f"{float(value):.2f}")
            else:
                values.append(str(value))
        lines.append("| " + " | ".join(values) + " |")
    return "\n".join(lines)


def _build_detect_mainline_report_table(df: pd.DataFrame) -> pd.DataFrame:
    report = df.copy()
    report = report.rename(
        columns={
            "dataset": "Dataset",
            "auc_mean": "AUC",
            "auprc_mean": "AUPRC",
            "macro_f1_mean": "Max-F1",
            "precision_at_k_mean": "P@K",
            "recall_at_k_mean": "R@K",
            "accuracy_mean": "Acc",
            "run_count": "Runs",
        }
    )
    return _apply_percentage_scale(report, ["AUC", "AUPRC", "Max-F1", "P@K", "R@K", "Acc"])


def _build_detect_ablation_summary_table(df: pd.DataFrame) -> pd.DataFrame:
    summary = (
        df.groupby(["ablation"], as_index=False)[["auc_mean", "macro_f1_mean"]]
        .mean()
        .sort_values(["macro_f1_mean", "auc_mean"], ascending=[False, False])
    )
    summary["ablation"] = summary["ablation"].map(_ablation_label)
    summary = summary.rename(columns={"ablation": "Ablation", "auc_mean": "AUC", "macro_f1_mean": "Max-F1"})
    return _apply_percentage_scale(summary, ["AUC", "Max-F1"])


def _build_detect_ablation_detail_table(df: pd.DataFrame) -> pd.DataFrame:
    detail = df[["dataset", "ablation", "run_count", "auc_mean", "macro_f1_mean"]].copy()
    detail["ablation"] = detail["ablation"].map(_ablation_label)
    detail = detail.rename(
        columns={
            "dataset": "Dataset",
            "ablation": "Ablation",
            "run_count": "Runs",
            "auc_mean": "AUC",
            "macro_f1_mean": "Max-F1",
        }
    )
    return _apply_percentage_scale(detail, ["AUC", "Max-F1"])


def _apply_percentage_scale(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    scaled = df.copy()
    for column in columns:
        if column in scaled.columns:
            scaled[column] = scaled[column].astype(float).mul(100.0).round(2)
    return scaled


def _derive_detect_table_from_baseline(df: pd.DataFrame) -> pd.DataFrame:
    subset = df[
        (df["discover_encoder"] == "magnn_legacy")
        & (df["lm_backend"] == "sbert")
        & (df["gnn_backend"] == "fusion_gnn")
        & (df["split_mode"] == "supervised")
    ].copy()
    mainline = subset[
        [
            "dataset",
            "auc_mean",
            "auprc_mean",
            "max_f1_mean",
            "precision_at_k_mean",
            "recall_at_k_mean",
            "accuracy_mean",
            "run_count",
        ]
    ].copy()
    mainline = mainline.rename(columns={"max_f1_mean": "macro_f1_mean"})
    mainline["dataset"] = mainline["dataset"].map(_simple_dataset_name)
    mainline = mainline.sort_values(["dataset"])
    return mainline


def _ablation_label(name: object) -> str:
    mapping = {
        "full": "full",
        "without_lm": "w/o LM",
        "without_reweighted_edges": "w/o edge reweight",
        "no_community_features": "w/o community feat",
        "no_discover_embeddings": "w/o discover emb",
        "classifier_struct_only": "w/o GNN & LM",
    }
    text = str(name)
    return mapping.get(text, text)


def _simple_dataset_name(name: object) -> str:
    mapping = {
        "uae": "UAE",
        "cuba": "Cuba",
        "russia": "Russia",
        "venezuela": "Venezuela",
        "iran": "Iran",
        "china": "China",
    }
    text = str(name)
    return mapping.get(text.lower(), text)
if __name__ == "__main__":
    main()
