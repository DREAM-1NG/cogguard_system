from __future__ import annotations

import argparse
import json
import math
import statistics
from collections import defaultdict
from itertools import combinations
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


MAINLINE_ENCODER = "magnn"
DEFAULT_ENCODER_ORDER = [
    "magnn",
    "magnn_legacy",
    "han",
    "amdn_hage",
    "zeyan_coexpression",
    "raw_graph_community",
]
ENCODER_LABELS = {
    "magnn": "MAGNN",
    "magnn_legacy": "MAGNN-Legacy",
    "han": "HAN",
    "amdn_hage": "AMDN-HAGE",
    "zeyan_coexpression": "Zeyan",
    "raw_graph_community": "Raw Graph",
    "lightweight": "Raw Graph",
}
METRIC_SPECS = [
    ("modularity", "Modularity", "#8ecae6", True),
    ("conductance", "Conductance", "#ff7b72", False),
    ("seed_nmi", "Seed NMI", "#90ee90", True),
    ("density", "Density", "#ffd60a", True),
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build KT1 Discover report tables and figures.")
    parser.add_argument(
        "--batch-dirs",
        nargs="+",
        required=True,
        help="One or more batch directories containing dataset/seed_x/encoder/discovery_summary.json",
    )
    parser.add_argument("--output-dir", required=True)
    parser.add_argument(
        "--encoder-alias",
        nargs="*",
        default=[],
        help="Optional encoder aliases in the form source=target, e.g. lightweight=raw_graph_community",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    alias_map = _parse_aliases(args.encoder_alias)
    rows, assignments = _load_runs([Path(path).resolve() for path in args.batch_dirs], alias_map=alias_map)
    if not rows:
        raise SystemExit("No discovery_summary.json files were found in the provided batch directories.")

    pairwise_nmi_df = _pairwise_seed_nmi(assignments)
    summary_df = _summarize_runs(rows, pairwise_nmi_df)
    mainline_df = _mainline_metrics(summary_df, encoder=MAINLINE_ENCODER)
    ablation_df = _ablation_metrics(summary_df)

    rows_df = pd.DataFrame(rows).sort_values(["dataset", "encoder", "seed"]).reset_index(drop=True)
    rows_df.to_csv(output_dir / "discover_runs_all.csv", index=False, encoding="utf-8")
    pairwise_nmi_df.to_csv(output_dir / "discover_pairwise_seed_nmi.csv", index=False, encoding="utf-8")
    summary_df.to_csv(output_dir / "discover_ablation_metrics_by_dataset.csv", index=False, encoding="utf-8")
    mainline_df.to_csv(output_dir / "discover_mainline_metrics.csv", index=False, encoding="utf-8")
    ablation_df.to_csv(output_dir / "discover_ablation_metrics_overall.csv", index=False, encoding="utf-8")

    _plot_mainline(mainline_df, output_dir / "discover_mainline_multi_dataset.png")
    _plot_ablation(ablation_df, output_dir / "discover_ablation_multi_dataset.png")
    _write_markdown_report(
        output_dir / "discover_report.md",
        mainline_df=mainline_df,
        ablation_df=ablation_df,
        pairwise_nmi_df=pairwise_nmi_df,
    )


def _parse_aliases(items: list[str]) -> dict[str, str]:
    alias_map: dict[str, str] = {}
    for item in items:
        if "=" not in item:
            continue
        source, target = item.split("=", 1)
        source = source.strip()
        target = target.strip()
        if source and target:
            alias_map[source] = target
    return alias_map


def _load_runs(batch_dirs: list[Path], *, alias_map: dict[str, str]) -> tuple[list[dict[str, object]], dict[tuple[str, str, int], dict[str, int]]]:
    rows: list[dict[str, object]] = []
    assignments: dict[tuple[str, str, int], dict[str, int]] = {}
    seen: set[tuple[str, str, int]] = set()

    for batch_dir in batch_dirs:
        for summary_path in batch_dir.glob("*/*/*/discovery_summary.json"):
            try:
                dataset = summary_path.parents[2].name
                seed_token = summary_path.parents[1].name
                encoder_name = summary_path.parents[0].name
                seed = int(seed_token.replace("seed_", ""))
            except Exception:
                continue
            encoder = alias_map.get(encoder_name, encoder_name)
            key = (dataset, encoder, seed)
            if key in seen:
                continue
            payload = json.loads(summary_path.read_text(encoding="utf-8"))
            metrics = payload.get("metrics", {}) if isinstance(payload.get("metrics"), dict) else {}
            graph_metrics = payload.get("graph_metrics", {}) if isinstance(payload.get("graph_metrics"), dict) else {}
            rows.append(
                {
                    "dataset": dataset,
                    "encoder": encoder,
                    "source_encoder": encoder_name,
                    "seed": seed,
                    "modularity": _to_float(metrics.get("modularity")),
                    "conductance": _to_float(metrics.get("conductance")),
                    "density": _to_float(metrics.get("density")),
                    "cluster_count": _to_float(metrics.get("cluster_count")),
                    "largest_cluster_size": _to_float(metrics.get("largest_cluster_size")),
                    "mean_object_concentration": _to_float(metrics.get("mean_object_concentration")),
                    "reconstruction_auc": _to_float(metrics.get("reconstruction_auc")),
                    "reconstruction_ap": _to_float(metrics.get("reconstruction_ap")),
                    "runtime_seconds": _to_float(graph_metrics.get("runtime_seconds")) or _to_float(metrics.get("runtime_seconds")),
                    "summary_path": str(summary_path),
                }
            )
            assignments[key] = _cluster_assignment(payload)
            seen.add(key)
    return rows, assignments


def _cluster_assignment(payload: dict[str, object]) -> dict[str, int]:
    output: dict[str, int] = {}
    nodes = payload.get("nodes", [])
    if not isinstance(nodes, list):
        return output
    for node in nodes:
        if not isinstance(node, dict):
            continue
        account_id = node.get("account_id")
        cluster_id = node.get("cluster_id")
        if account_id is None or cluster_id is None:
            continue
        try:
            output[str(account_id)] = int(cluster_id)
        except (TypeError, ValueError):
            continue
    return output


def _pairwise_seed_nmi(assignments: dict[tuple[str, str, int], dict[str, int]]) -> pd.DataFrame:
    grouped: dict[tuple[str, str], list[tuple[int, dict[str, int]]]] = defaultdict(list)
    for (dataset, encoder, seed), mapping in assignments.items():
        if mapping:
            grouped[(dataset, encoder)].append((seed, mapping))

    rows: list[dict[str, object]] = []
    for (dataset, encoder), items in sorted(grouped.items()):
        for (left_seed, left_map), (right_seed, right_map) in combinations(sorted(items, key=lambda item: item[0]), 2):
            common_nodes = sorted(set(left_map).intersection(right_map))
            if not common_nodes:
                continue
            left_labels = [left_map[node] for node in common_nodes]
            right_labels = [right_map[node] for node in common_nodes]
            nmi = _normalized_mutual_information(left_labels, right_labels)
            rows.append(
                {
                    "dataset": dataset,
                    "encoder": encoder,
                    "left_seed": left_seed,
                    "right_seed": right_seed,
                    "common_node_count": len(common_nodes),
                    "seed_nmi": round(float(nmi), 6) if nmi is not None else None,
                }
            )
    return pd.DataFrame(rows)


def _summarize_runs(rows: list[dict[str, object]], pairwise_nmi_df: pd.DataFrame) -> pd.DataFrame:
    df = pd.DataFrame(rows)
    grouped = df.groupby(["dataset", "encoder"], dropna=False)
    records: list[dict[str, object]] = []
    for (dataset, encoder), group in grouped:
        record: dict[str, object] = {
            "dataset": dataset,
            "encoder": encoder,
            "seed_count": int(group["seed"].nunique()),
        }
        for metric in [
            "modularity",
            "conductance",
            "density",
            "cluster_count",
            "largest_cluster_size",
            "mean_object_concentration",
            "reconstruction_auc",
            "reconstruction_ap",
        ]:
            values = [value for value in group[metric].tolist() if value is not None and not pd.isna(value)]
            record[f"{metric}_mean"] = round(float(statistics.mean(values)), 6) if values else None
            record[f"{metric}_std"] = round(float(statistics.pstdev(values)), 6) if len(values) > 1 else 0.0 if values else None

        nmi_group = pairwise_nmi_df[
            (pairwise_nmi_df["dataset"] == dataset) & (pairwise_nmi_df["encoder"] == encoder)
        ]
        nmi_values = [float(value) for value in nmi_group["seed_nmi"].dropna().tolist()]
        record["seed_nmi_mean"] = round(float(statistics.mean(nmi_values)), 6) if nmi_values else None
        record["seed_nmi_std"] = round(float(statistics.pstdev(nmi_values)), 6) if len(nmi_values) > 1 else 0.0 if nmi_values else None
        record["seed_nmi_pair_count"] = len(nmi_values)
        records.append(record)

    output = pd.DataFrame(records)
    encoder_rank = {name: index for index, name in enumerate(DEFAULT_ENCODER_ORDER)}
    output["encoder_rank"] = output["encoder"].map(lambda value: encoder_rank.get(str(value), 999))
    output = output.sort_values(["dataset", "encoder_rank", "encoder"]).drop(columns=["encoder_rank"]).reset_index(drop=True)
    return output


def _mainline_metrics(summary_df: pd.DataFrame, *, encoder: str) -> pd.DataFrame:
    mainline = summary_df[summary_df["encoder"] == encoder].copy()
    return mainline.sort_values("dataset").reset_index(drop=True)


def _ablation_metrics(summary_df: pd.DataFrame) -> pd.DataFrame:
    records: list[dict[str, object]] = []
    for encoder, group in summary_df.groupby("encoder", dropna=False):
        record: dict[str, object] = {"encoder": encoder, "dataset_count": int(group["dataset"].nunique())}
        for metric in ["modularity_mean", "conductance_mean", "density_mean", "seed_nmi_mean"]:
            values = [float(value) for value in group[metric].dropna().tolist()]
            record[metric] = round(float(statistics.mean(values)), 6) if values else None
            record[f"{metric}_std"] = round(float(statistics.pstdev(values)), 6) if len(values) > 1 else 0.0 if values else None
        records.append(record)
    output = pd.DataFrame(records)
    encoder_rank = {name: index for index, name in enumerate(DEFAULT_ENCODER_ORDER)}
    output["encoder_rank"] = output["encoder"].map(lambda value: encoder_rank.get(str(value), 999))
    output = output.sort_values(["encoder_rank", "encoder"]).drop(columns=["encoder_rank"]).reset_index(drop=True)
    return output


def _plot_mainline(mainline_df: pd.DataFrame, output_path: Path) -> None:
    fig, axes = plt.subplots(2, 2, figsize=(13.6, 8.8), facecolor="white")
    axes = axes.flatten()
    x_labels = mainline_df["dataset"].tolist()
    x = np.arange(len(x_labels))

    for axis, (metric, title, color, higher_better) in zip(axes, METRIC_SPECS):
        values = mainline_df[f"{metric}_mean"].astype(float).to_numpy()
        bars = axis.bar(x, values, color=color, edgecolor="white", linewidth=0.8)
        axis.set_title(_axis_title(metric, title), fontsize=15, pad=10)
        axis.set_ylabel("Score", fontsize=11)
        axis.set_xticks(x)
        axis.set_xticklabels(x_labels, rotation=0, fontsize=10)
        axis.grid(axis="y", alpha=0.25, linestyle="--")
        _set_metric_axis_limits(axis, values, metric)
        for bar, value in zip(bars, values):
            text_y = _value_label_y(axis, metric, float(bar.get_height()), values)
            axis.text(
                bar.get_x() + bar.get_width() / 2.0,
                text_y,
                _format_metric_value(metric, value),
                ha="center",
                va="bottom",
                fontsize=9,
            )
        if not higher_better:
            axis.text(0.98, 0.96, "Lower is better", transform=axis.transAxes, ha="right", va="top", fontsize=9, color="#555555")

    fig.suptitle("Discover Mainline Metrics Across Datasets", fontsize=18, y=0.98)
    fig.tight_layout(rect=[0, 0, 1, 0.96])
    fig.savefig(output_path, dpi=300)
    plt.close(fig)


def _plot_ablation(ablation_df: pd.DataFrame, output_path: Path) -> None:
    fig, axes = plt.subplots(2, 2, figsize=(13.6, 8.8), facecolor="white")
    axes = axes.flatten()
    encoder_labels = [ENCODER_LABELS.get(str(value), str(value)) for value in ablation_df["encoder"].tolist()]
    x = np.arange(len(encoder_labels))

    for axis, (metric, title, color, higher_better) in zip(axes, METRIC_SPECS):
        values = ablation_df[f"{metric}_mean"].astype(float).to_numpy()
        bars = axis.bar(x, values, color=color, edgecolor="white", linewidth=0.8)
        axis.set_title(_axis_title(metric, title), fontsize=15, pad=10)
        axis.set_ylabel("Score", fontsize=11)
        axis.set_xticks(x)
        axis.set_xticklabels(encoder_labels, rotation=20, ha="right", fontsize=10)
        axis.grid(axis="y", alpha=0.25, linestyle="--")
        _set_metric_axis_limits(axis, values, metric)
        for bar, value in zip(bars, values):
            text_y = _value_label_y(axis, metric, float(bar.get_height()), values)
            axis.text(
                bar.get_x() + bar.get_width() / 2.0,
                text_y,
                _format_metric_value(metric, value),
                ha="center",
                va="bottom",
                fontsize=9,
            )
        if not higher_better:
            axis.text(0.98, 0.96, "Lower is better", transform=axis.transAxes, ha="right", va="top", fontsize=9, color="#555555")

    fig.suptitle("Discover Ablation Metrics Averaged Across Datasets", fontsize=18, y=0.98)
    fig.tight_layout(rect=[0, 0, 1, 0.96])
    fig.savefig(output_path, dpi=300)
    plt.close(fig)


def _set_metric_axis_limits(axis, values: np.ndarray, metric: str) -> None:
    if values.size == 0 or np.all(np.isnan(values)):
        axis.set_ylim(0.0, 1.0)
        return
    numeric = values[~np.isnan(values)]
    lower = float(np.min(numeric))
    upper = float(np.max(numeric))
    if metric in {"modularity", "seed_nmi"}:
        axis.set_ylim(max(0.0, lower - 0.05), upper + 0.03)
    elif metric == "conductance":
        axis.set_ylim(0.0, max(upper * 1.2, upper + 0.001))
    elif metric == "density":
        positive = numeric[numeric > 0.0]
        if positive.size == 0:
            axis.set_ylim(0.0, 1.0)
        else:
            axis.set_yscale("log")
            axis.set_ylim(float(np.min(positive)) / 2.0, float(np.max(positive)) * 2.0)
            axis.yaxis.set_major_formatter(plt.FuncFormatter(lambda value, _: f"{value:.0e}"))
    else:
        axis.set_ylim(max(0.0, lower - 0.05), upper + 0.08)


def _label_offset(values: np.ndarray) -> float:
    numeric = values[~np.isnan(values)]
    if numeric.size == 0:
        return 0.01
    maximum = float(np.max(numeric))
    if maximum <= 0.05:
        return maximum * 0.03 + 0.0002
    return maximum * 0.01 + 0.002


def _format_metric_value(metric: str, value: float) -> str:
    if metric == "density":
        return f"{value:.2e}"
    if metric == "conductance":
        return f"{value:.4f}"
    return f"{value:.3f}"


def _axis_title(metric: str, title: str) -> str:
    if metric == "density":
        return f"{title} (log scale)"
    return title


def _value_label_y(axis, metric: str, bar_height: float, values: np.ndarray) -> float:
    if metric == "density":
        return bar_height * 1.12
    y_min, y_max = axis.get_ylim()
    proposed = bar_height + _label_offset(values)
    max_allowed = y_max - (y_max - y_min) * 0.06
    return min(proposed, max_allowed)


def _write_markdown_report(
    output_path: Path,
    *,
    mainline_df: pd.DataFrame,
    ablation_df: pd.DataFrame,
    pairwise_nmi_df: pd.DataFrame,
) -> None:
    lines: list[str] = []
    lines.append("# KT1 Discover Multi-Dataset Report")
    lines.append("")
    lines.append("## Mainline Metrics (MAGNN + Leiden)")
    lines.append("")
    lines.append(
        mainline_df[
            [
                "dataset",
                "modularity_mean",
                "conductance_mean",
                "seed_nmi_mean",
                "density_mean",
            ]
        ].to_markdown(index=False)
    )
    lines.append("")
    lines.append("## Ablation Metrics (Averaged Across Datasets)")
    lines.append("")
    lines.append(
        ablation_df[
            [
                "encoder",
                "modularity_mean",
                "conductance_mean",
                "seed_nmi_mean",
                "density_mean",
            ]
        ].to_markdown(index=False)
    )
    lines.append("")
    lines.append("## Notes")
    lines.append("")
    lines.append("- `seed_nmi` is pairwise community-assignment NMI across random seeds for the same dataset and encoder.")
    lines.append("- `conductance` is lower-better; `modularity`, `seed_nmi`, and `density` are higher-better.")
    lines.append(f"- Pairwise NMI rows: {len(pairwise_nmi_df)}")
    output_path.write_text("\n".join(lines), encoding="utf-8")


def _normalized_mutual_information(left_labels: list[int], right_labels: list[int]) -> float | None:
    if len(left_labels) != len(right_labels) or not left_labels:
        return None
    total = len(left_labels)
    left_counts: defaultdict[int, int] = defaultdict(int)
    right_counts: defaultdict[int, int] = defaultdict(int)
    joint_counts: defaultdict[tuple[int, int], int] = defaultdict(int)
    for left, right in zip(left_labels, right_labels):
        left_counts[left] += 1
        right_counts[right] += 1
        joint_counts[(left, right)] += 1

    def entropy(counts: defaultdict[int, int]) -> float:
        value = 0.0
        for count in counts.values():
            probability = count / total
            if probability > 0.0:
                value -= probability * math.log(probability)
        return value

    left_entropy = entropy(left_counts)
    right_entropy = entropy(right_counts)
    if left_entropy <= 0.0 and right_entropy <= 0.0:
        return 1.0
    mutual_information = 0.0
    for (left, right), count in joint_counts.items():
        probability = count / total
        left_probability = left_counts[left] / total
        right_probability = right_counts[right] / total
        if probability > 0.0 and left_probability > 0.0 and right_probability > 0.0:
            mutual_information += probability * math.log(probability / (left_probability * right_probability))
    denominator = (left_entropy + right_entropy) / 2.0
    if denominator <= 0.0:
        return None
    return mutual_information / denominator


def _to_float(value: object) -> float | None:
    if value in {None, ""}:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


if __name__ == "__main__":
    main()
