from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.colors import Normalize


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build KT1 experiment figures.")
    parser.add_argument("--system-report-dir", required=True)
    parser.add_argument("--detect-ablation-csv", required=True)
    parser.add_argument("--detect-baseline-csv", default="")
    parser.add_argument("--output-dir", required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    system_dir = Path(args.system_report_dir).resolve()
    ablation_csv = Path(args.detect_ablation_csv).resolve()
    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    if args.detect_baseline_csv:
        baseline_df = pd.read_csv(Path(args.detect_baseline_csv).resolve())
        detect_mainline = baseline_df[
            (baseline_df["discover_encoder"] == "magnn")
            & (baseline_df["lm_backend"] == "sbert")
            & (baseline_df["gnn_backend"] == "fusion_gnn")
            & (baseline_df["split_mode"] == "supervised")
        ][
            [
                "dataset",
                "auc_mean",
                "auprc_mean",
                "max_f1_mean",
                "precision_at_k_mean",
                "recall_at_k_mean",
                "accuracy_mean",
            ]
        ].copy()
    else:
        detect_mainline = pd.read_csv(system_dir / "kt1_detect_mainline_table.csv")
    detect_ablation = pd.read_csv(ablation_csv)

    _plot_detect_main_metrics_heatmap(
        detect_mainline,
        output_dir / "kt1_detect_main_metrics_heatmap.png",
        title="KT1 Detect Main Experiment Metrics (Supervised)",
    )
    focus = detect_ablation[
        detect_ablation["ablation"].isin(
            ["full", "without_lm", "without_reweighted_edges", "no_community_features", "classifier_struct_only", "relation_gnn"]
        )
    ].copy()
    _plot_ablation_heatmap(
        focus,
        output_dir / "kt1_detect_ablation_macro_f1_heatmap.png",
        metric="macro_f1_mean",
        title="KT1 Detect Ablation Max-F1 Heatmap",
    )
    _plot_ablation_heatmap(
        focus,
        output_dir / "kt1_detect_ablation_auc_heatmap.png",
        metric="auc_mean",
        title="KT1 Detect Ablation AUC Heatmap",
    )
    _plot_ablation_dual_heatmap(
        focus,
        output_dir / "kt1_detect_ablation_auc_maxf1_combined.png",
        left_metric="auc_mean",
        left_title="AUC",
        right_metric="macro_f1_mean",
        right_title="Max-F1",
        title="KT1 Detect Ablation (Supervised)",
    )


def _format_percent_value(value: float) -> str:
    return f"{value * 100:.2f}"


def _text_color_for_value(value: float, *, norm: Normalize, cmap_name: str) -> str:
    r, g, b, _ = plt.get_cmap(cmap_name)(norm(value))
    luminance = 0.2126 * r + 0.7152 * g + 0.0722 * b
    return "white" if luminance < 0.52 else "black"


def _draw_heatmap_annotations(
    ax: plt.Axes,
    values: np.ndarray,
    *,
    norm: Normalize,
    cmap_name: str,
    fontsize: float,
) -> None:
    for i in range(values.shape[0]):
        for j in range(values.shape[1]):
            cell_value = float(values[i, j])
            ax.text(
                j,
                i,
                _format_percent_value(cell_value),
                ha="center",
                va="center",
                color=_text_color_for_value(cell_value, norm=norm, cmap_name=cmap_name),
                fontsize=fontsize,
                fontweight="bold",
            )


def _plot_detect_main_metrics_heatmap(df: pd.DataFrame, output_path: Path, *, title: str) -> None:
    subset = df.copy()
    subset["dataset"] = subset["dataset"].map(_simple_dataset_name)
    subset = subset.rename(
        columns={
            "auc_mean": "AUC",
            "auprc_mean": "AUPRC",
            "max_f1_mean": "Max-F1",
            "precision_at_k_mean": "P@K",
            "recall_at_k_mean": "R@K",
            "accuracy_mean": "Acc",
        }
    )
    pivot = subset.set_index("dataset")[["AUC", "AUPRC", "Max-F1", "P@K", "R@K", "Acc"]].astype(float)
    values = pivot.values.astype(float)
    n_rows, n_cols = values.shape
    fig_width = max(7.6, n_cols * 1.5)
    fig_height = max(6.2, n_rows * 1.2)
    fig, ax = plt.subplots(figsize=(fig_width, fig_height), facecolor="white")
    norm = Normalize(vmin=float(np.nanmin(values)), vmax=float(np.nanmax(values)))
    cmap_name = "viridis"
    im = ax.imshow(
        values,
        aspect="equal",
        cmap=cmap_name,
        interpolation="nearest",
        vmin=norm.vmin,
        vmax=norm.vmax,
    )
    ax.set_box_aspect(n_rows / n_cols)
    ax.set_title(title, fontsize=14, pad=16)
    ax.set_xlabel("Metric", fontsize=11, labelpad=14)
    ax.set_ylabel("Dataset", fontsize=11, labelpad=14)
    ax.set_xticks(range(len(pivot.columns)))
    ax.set_xticklabels(pivot.columns, rotation=0, fontsize=10)
    ax.set_yticks(range(len(pivot.index)))
    ax.set_yticklabels(pivot.index, fontsize=10)
    _draw_heatmap_annotations(ax, values, norm=norm, cmap_name=cmap_name, fontsize=9.5)
    for spine in ax.spines.values():
        spine.set_visible(False)
    cbar = fig.colorbar(im, ax=ax, shrink=0.9, pad=0.04)
    cbar.ax.tick_params(labelsize=9)
    fig.subplots_adjust(left=0.14, right=0.9, bottom=0.16, top=0.88)
    fig.savefig(output_path, dpi=220)
    plt.close(fig)


def _plot_discover_bar(df: pd.DataFrame, output_path: Path, *, metric: str, title: str) -> None:
    subset = df.copy().sort_values(metric, ascending=False)
    fig, ax = plt.subplots(figsize=(7, 4))
    ax.bar(subset["encoder"], subset[metric].astype(float), color=["#2563eb", "#0f766e", "#d97706", "#dc2626", "#7c3aed"])
    ax.set_title(title)
    ax.set_ylabel(metric)
    for index, value in enumerate(subset[metric].astype(float).tolist()):
        ax.text(index, value, f"{value:.3f}", ha="center", va="bottom", fontsize=8)
    fig.tight_layout()
    fig.savefig(output_path, dpi=220)
    plt.close(fig)


def _plot_ablation_heatmap(df: pd.DataFrame, output_path: Path, *, metric: str, title: str) -> None:
    subset = df.copy()
    subset = subset[subset["split_mode"] == "supervised"].copy()
    subset["dataset"] = subset["dataset"].map(_simple_dataset_name)
    component_order = [
        "full",
        "without_lm",
        "without_reweighted_edges",
        "no_community_features",
        "no_discover_embeddings",
        "classifier_struct_only",
    ]
    component_label = {
        "full": "full",
        "without_lm": "w/o LM",
        "without_reweighted_edges": "w/o edge\nreweight",
        "no_community_features": "w/o community\nfeat",
        "no_discover_embeddings": "w/o discover\nemb",
        "classifier_struct_only": "w/o GNN\n& LM",
    }
    pivot = subset.pivot(index="dataset", columns="ablation", values=metric).astype(float)
    pivot = pivot.reindex(columns=[column for column in component_order if column in pivot.columns])
    values = pivot.values.astype(float)
    n_rows, n_cols = values.shape
    fig_width = max(8.6, n_cols * 1.7)
    fig_height = max(6.2, n_rows * 1.2)
    fig, ax = plt.subplots(figsize=(fig_width, fig_height), facecolor="white")
    norm = Normalize(vmin=float(np.nanmin(values)), vmax=float(np.nanmax(values)))
    cmap_name = "viridis"
    im = ax.imshow(
        values,
        aspect="equal",
        cmap=cmap_name,
        interpolation="nearest",
        vmin=norm.vmin,
        vmax=norm.vmax,
    )
    ax.set_box_aspect(n_rows / n_cols)
    ax.set_title(title, fontsize=14, pad=16)
    ax.set_xlabel("Model / Ablation", fontsize=11, labelpad=14)
    ax.set_ylabel("Dataset", fontsize=11, labelpad=14)
    ax.set_xticks(range(len(pivot.columns)))
    ax.set_xticklabels([component_label.get(item, item) for item in pivot.columns], rotation=0, ha="center", fontsize=9.5)
    ax.set_yticks(range(len(pivot.index)))
    ax.set_yticklabels(pivot.index, fontsize=10)
    _draw_heatmap_annotations(ax, values, norm=norm, cmap_name=cmap_name, fontsize=10)
    for spine in ax.spines.values():
        spine.set_visible(False)
    cbar = fig.colorbar(im, ax=ax, shrink=0.92, pad=0.04)
    cbar.ax.tick_params(labelsize=9)
    fig.subplots_adjust(left=0.14, right=0.9, bottom=0.18, top=0.88)
    fig.savefig(output_path, dpi=220)
    plt.close(fig)


def _build_ablation_pivot(df: pd.DataFrame, metric: str) -> pd.DataFrame:
    subset = df.copy()
    subset = subset[subset["split_mode"] == "supervised"].copy()
    subset["dataset"] = subset["dataset"].map(_simple_dataset_name)
    component_order = [
        "full",
        "without_lm",
        "without_reweighted_edges",
        "no_community_features",
        "no_discover_embeddings",
        "classifier_struct_only",
    ]
    pivot = subset.pivot(index="dataset", columns="ablation", values=metric).astype(float)
    return pivot.reindex(columns=[column for column in component_order if column in pivot.columns])


def _ablation_component_labels(columns: list[str]) -> list[str]:
    component_label = {
        "full": "full",
        "without_lm": "w/o LM",
        "without_reweighted_edges": "w/o edge\nreweight",
        "no_community_features": "w/o community\nfeat",
        "no_discover_embeddings": "w/o discover\nemb",
        "classifier_struct_only": "w/o GNN\n& LM",
    }
    return [component_label.get(item, item) for item in columns]


def _plot_ablation_dual_heatmap(
    df: pd.DataFrame,
    output_path: Path,
    *,
    left_metric: str,
    left_title: str,
    right_metric: str,
    right_title: str,
    title: str,
) -> None:
    left_pivot = _build_ablation_pivot(df, left_metric)
    right_pivot = _build_ablation_pivot(df, right_metric)
    left_values = left_pivot.values.astype(float)
    right_values = right_pivot.values.astype(float)
    n_rows, n_cols = left_values.shape
    fig_width = max(13.0, n_cols * 3.0)
    fig_height = max(6.8, n_rows * 1.25)
    fig, axes = plt.subplots(1, 2, figsize=(fig_width, fig_height), facecolor="white")
    fig.suptitle(title, fontsize=16, y=0.98)

    for ax, pivot, values, panel_title in [
        (axes[0], left_pivot, left_values, left_title),
        (axes[1], right_pivot, right_values, right_title),
    ]:
        norm = Normalize(vmin=float(np.nanmin(values)), vmax=float(np.nanmax(values)))
        cmap_name = "viridis"
        im = ax.imshow(
            values,
            aspect="equal",
            cmap=cmap_name,
            interpolation="nearest",
            vmin=norm.vmin,
            vmax=norm.vmax,
        )
        ax.set_box_aspect(n_rows / n_cols)
        ax.set_title(panel_title, fontsize=13, pad=10)
        ax.set_xticks(range(len(pivot.columns)))
        ax.set_xticklabels(_ablation_component_labels(list(pivot.columns)), rotation=0, ha="center", fontsize=9.5)
        ax.set_yticks(range(len(pivot.index)))
        ax.set_yticklabels(pivot.index, fontsize=10)
        ax.set_xlabel("Model / Ablation", fontsize=11, labelpad=12)
        if ax is axes[0]:
            ax.set_ylabel("Dataset", fontsize=11, labelpad=12)
        _draw_heatmap_annotations(ax, values, norm=norm, cmap_name=cmap_name, fontsize=10)
        for spine in ax.spines.values():
            spine.set_visible(False)
        cbar = fig.colorbar(im, ax=ax, shrink=0.88, pad=0.03)
        cbar.ax.tick_params(labelsize=9)

    fig.subplots_adjust(left=0.08, right=0.96, bottom=0.16, top=0.88, wspace=0.18)
    fig.savefig(output_path, dpi=220)
    plt.close(fig)


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
