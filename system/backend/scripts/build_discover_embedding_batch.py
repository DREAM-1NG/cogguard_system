from __future__ import annotations

import argparse
import json
import statistics
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from build_discover_embedding_figure import (
    _color_encoding,
    _focus_labels,
    _load_embeddings,
    _pca_projection,
    _point_sizes,
    _standardize,
    _svd_projection,
    _tsne_projection,
    _umap_or_fallback_projection,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Batch-build Discover embedding figures and evaluate reduction methods.")
    parser.add_argument("--root", required=True, help="Root directory containing dataset/seed_x/encoder/discovery_summary.json")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--datasets", nargs="*", default=["UAE", "china", "cuba", "iran", "russia", "venezuela"])
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--encoder", default="magnn")
    parser.add_argument("--top-communities", type=int, default=8)
    parser.add_argument("--min-community-size", type=int, default=3)
    parser.add_argument("--perplexity", type=float, default=30.0)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    root = Path(args.root).resolve()
    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    rows: list[dict[str, object]] = []
    dataset_best_rows: list[dict[str, object]] = []
    dataset_artifacts: list[dict[str, object]] = []

    for dataset in args.datasets:
        summary_path = root / dataset / f"seed_{args.seed}" / args.encoder / "discovery_summary.json"
        if not summary_path.exists():
            continue
        payload = json.loads(summary_path.read_text(encoding="utf-8"))
        embeddings, cluster_ids, node_scores = _load_embeddings(payload)
        if embeddings.size == 0:
            continue
        labels, focus_mask = _focus_labels(
            cluster_ids,
            top_communities=args.top_communities,
            min_community_size=args.min_community_size,
        )
        embeddings = embeddings[focus_mask]
        node_scores = node_scores[focus_mask]
        scaled = _standardize(embeddings)
        projections = _projections(scaled, perplexity=args.perplexity)
        if not projections:
            continue

        for method, projection in projections.items():
            metrics = _projection_metrics(scaled, projection, labels)
            rows.append(
                {
                    "dataset": dataset,
                    "method": method,
                    "node_count": len(labels),
                    **metrics,
                }
            )

        dataset_metrics = pd.DataFrame([row for row in rows if row["dataset"] == dataset]).copy()
        ranked = _rank_methods(dataset_metrics)
        best_method = str(ranked.sort_values(["rank_score", "method"]).iloc[0]["method"])
        best_row = ranked[ranked["method"] == best_method].iloc[0].to_dict()
        dataset_best_rows.append(best_row)

        color_values, cmap, _ = _color_encoding(labels)
        sizes = _point_sizes(node_scores)
        single_path = output_dir / f"{dataset}_best_{best_method}.png"
        _plot_single_projection(
            projections[best_method],
            color_values=color_values,
            cmap=cmap,
            sizes=sizes,
            title=f"{dataset} user embedding ({best_method.upper()})",
            x_label=f"{best_method.upper()} component 1",
            y_label=f"{best_method.upper()} component 2",
            output_path=single_path,
        )
        dataset_artifacts.append({"dataset": dataset, "best_method": best_method, "figure": str(single_path)})

    metrics_df = pd.DataFrame(rows)
    if metrics_df.empty:
        raise SystemExit("No dataset projections were generated.")
    metrics_df.to_csv(output_dir / "embedding_reduction_metrics.csv", index=False, encoding="utf-8")

    ranked_metrics_df = _ranked_metrics_by_dataset(metrics_df)
    ranked_metrics_df.to_csv(output_dir / "embedding_reduction_ranked.csv", index=False, encoding="utf-8")

    dataset_best_df = pd.DataFrame(dataset_best_rows).sort_values("dataset").reset_index(drop=True)
    dataset_best_df.to_csv(output_dir / "embedding_best_method_by_dataset.csv", index=False, encoding="utf-8")

    overall_df = _overall_method_summary(metrics_df, ranked_metrics_df)
    overall_df.to_csv(output_dir / "embedding_reduction_overall.csv", index=False, encoding="utf-8")

    showcase_method = str(overall_df.sort_values(["mean_rank_score", "method"]).iloc[0]["method"])
    _plot_showcase_grid(
        root=root,
        datasets=args.datasets,
        seed=args.seed,
        encoder=args.encoder,
        top_communities=args.top_communities,
        min_community_size=args.min_community_size,
        perplexity=args.perplexity,
        method=showcase_method,
        output_path=output_dir / f"embedding_showcase_{showcase_method}.png",
    )

    _write_report(
        output_dir / "embedding_reduction_report.md",
        overall_df=overall_df,
        dataset_best_df=dataset_best_df,
        dataset_artifacts=dataset_artifacts,
        showcase_method=showcase_method,
    )


def _projections(scaled: np.ndarray, *, perplexity: float) -> dict[str, np.ndarray]:
    projections: dict[str, np.ndarray] = {
        "pca": _pca_projection(scaled, components=2),
        "tsne": _tsne_projection(scaled, perplexity=min(perplexity, max(5.0, len(scaled) / 8.0))),
        "svd": _svd_projection(scaled, components=2),
    }
    umap_or_fallback, title = _umap_or_fallback_projection(scaled)
    projections["umap" if title.lower().startswith("umap") else "spectral"] = umap_or_fallback
    return projections


def _projection_metrics(original: np.ndarray, reduced: np.ndarray, labels: np.ndarray) -> dict[str, object]:
    from sklearn.manifold import trustworthiness
    from sklearn.metrics import calinski_harabasz_score, davies_bouldin_score, silhouette_score

    unique_labels = np.unique(labels)
    output: dict[str, object] = {
        "silhouette": None,
        "calinski_harabasz": None,
        "davies_bouldin": None,
        "trustworthiness": None,
    }
    if len(labels) >= 3 and len(unique_labels) >= 2:
        try:
            output["silhouette"] = round(float(silhouette_score(reduced, labels)), 6)
        except Exception:
            output["silhouette"] = None
        try:
            output["calinski_harabasz"] = round(float(calinski_harabasz_score(reduced, labels)), 6)
        except Exception:
            output["calinski_harabasz"] = None
        try:
            output["davies_bouldin"] = round(float(davies_bouldin_score(reduced, labels)), 6)
        except Exception:
            output["davies_bouldin"] = None
    try:
        n_neighbors = min(10, max(2, len(original) - 1))
        output["trustworthiness"] = round(float(trustworthiness(original, reduced, n_neighbors=n_neighbors)), 6)
    except Exception:
        output["trustworthiness"] = None
    return output


def _rank_methods(dataset_metrics: pd.DataFrame) -> pd.DataFrame:
    ranked = dataset_metrics.copy()
    ranked["rank_silhouette"] = ranked["silhouette"].rank(ascending=False, method="min")
    ranked["rank_calinski"] = ranked["calinski_harabasz"].rank(ascending=False, method="min")
    ranked["rank_davies"] = ranked["davies_bouldin"].rank(ascending=True, method="min")
    ranked["rank_trust"] = ranked["trustworthiness"].rank(ascending=False, method="min")
    # Use the more stable neighborhood-preservation and cluster-separation ranks
    # for the showcase decision. Calinski-Harabasz is still reported, but it can
    # become numerically pathological for spectral-style reductions on tiny/fine
    # community layouts, so it should not determine the final display choice.
    rank_columns = ["rank_silhouette", "rank_davies", "rank_trust"]
    ranked["rank_score"] = ranked[rank_columns].mean(axis=1)
    return ranked


def _overall_method_summary(metrics_df: pd.DataFrame, ranked_metrics_df: pd.DataFrame) -> pd.DataFrame:
    grouped = metrics_df.groupby("method", dropna=False)
    rows: list[dict[str, object]] = []
    for method, group in grouped:
        ranked = ranked_metrics_df[ranked_metrics_df["method"] == method]
        rows.append(
            {
                "method": method,
                "dataset_count": int(group["dataset"].nunique()),
                "silhouette_mean": _safe_mean(group["silhouette"]),
                "calinski_harabasz_mean": _safe_mean(group["calinski_harabasz"]),
                "davies_bouldin_mean": _safe_mean(group["davies_bouldin"]),
                "trustworthiness_mean": _safe_mean(group["trustworthiness"]),
                "mean_rank_score": _safe_mean(ranked["rank_score"]),
                "mean_rank_silhouette": _safe_mean(ranked["rank_silhouette"]),
                "mean_rank_calinski": _safe_mean(ranked["rank_calinski"]),
                "mean_rank_davies": _safe_mean(ranked["rank_davies"]),
                "mean_rank_trust": _safe_mean(ranked["rank_trust"]),
            }
        )
    return pd.DataFrame(rows).sort_values(["mean_rank_score", "method"]).reset_index(drop=True)


def _ranked_metrics_by_dataset(metrics_df: pd.DataFrame) -> pd.DataFrame:
    ranked_parts: list[pd.DataFrame] = []
    for dataset, group in metrics_df.groupby("dataset", dropna=False):
        ranked = _rank_methods(group.copy())
        ranked_parts.append(ranked)
    return pd.concat(ranked_parts, ignore_index=True) if ranked_parts else pd.DataFrame()


def _plot_single_projection(
    points: np.ndarray,
    *,
    color_values: np.ndarray,
    cmap,
    sizes: np.ndarray,
    title: str,
    x_label: str,
    y_label: str,
    output_path: Path,
) -> None:
    fig, axis = plt.subplots(figsize=(6.4, 5.2), facecolor="white")
    scatter = axis.scatter(
        points[:, 0],
        points[:, 1],
        c=color_values,
        cmap=cmap,
        s=sizes,
        alpha=0.92,
        linewidths=0.2,
        edgecolors="white",
    )
    axis.set_title(title, fontsize=13, pad=10)
    axis.set_xlabel(x_label, fontsize=10)
    axis.set_ylabel(y_label, fontsize=10)
    axis.grid(alpha=0.18, linestyle="--")
    cbar = fig.colorbar(scatter, ax=axis, fraction=0.046, pad=0.04)
    cbar.ax.tick_params(labelsize=8)
    cbar.set_label("Community group", fontsize=9)
    fig.tight_layout()
    fig.savefig(output_path, dpi=300)
    plt.close(fig)


def _plot_showcase_grid(
    *,
    root: Path,
    datasets: list[str],
    seed: int,
    encoder: str,
    top_communities: int,
    min_community_size: int,
    perplexity: float,
    method: str,
    output_path: Path,
) -> None:
    fig, axes = plt.subplots(2, 3, figsize=(15.5, 9.8), facecolor="white")
    axes = axes.flatten()
    used = 0

    for dataset in datasets:
        summary_path = root / dataset / f"seed_{seed}" / encoder / "discovery_summary.json"
        if not summary_path.exists():
            continue
        payload = json.loads(summary_path.read_text(encoding="utf-8"))
        embeddings, cluster_ids, node_scores = _load_embeddings(payload)
        if embeddings.size == 0:
            continue
        labels, focus_mask = _focus_labels(cluster_ids, top_communities=top_communities, min_community_size=min_community_size)
        embeddings = embeddings[focus_mask]
        node_scores = node_scores[focus_mask]
        scaled = _standardize(embeddings)
        projections = _projections(scaled, perplexity=perplexity)
        if method not in projections:
            continue
        color_values, cmap, _ = _color_encoding(labels)
        sizes = _point_sizes(node_scores)

        axis = axes[used]
        scatter = axis.scatter(
            projections[method][:, 0],
            projections[method][:, 1],
            c=color_values,
            cmap=cmap,
            s=sizes,
            alpha=0.92,
            linewidths=0.2,
            edgecolors="white",
        )
        axis.set_title(dataset, fontsize=12, pad=8)
        axis.set_xlabel(f"{method.upper()}-1", fontsize=9)
        axis.set_ylabel(f"{method.upper()}-2", fontsize=9)
        axis.grid(alpha=0.18, linestyle="--")
        cbar = fig.colorbar(scatter, ax=axis, fraction=0.046, pad=0.03)
        cbar.ax.tick_params(labelsize=7)
        used += 1

    for axis in axes[used:]:
        axis.axis("off")

    fig.suptitle(f"KT1 Discover User Embeddings Across Datasets ({method.upper()})", fontsize=18, y=0.985)
    fig.tight_layout(rect=[0, 0, 1, 0.965])
    fig.savefig(output_path, dpi=300)
    plt.close(fig)


def _write_report(
    output_path: Path,
    *,
    overall_df: pd.DataFrame,
    dataset_best_df: pd.DataFrame,
    dataset_artifacts: list[dict[str, object]],
    showcase_method: str,
) -> None:
    lines: list[str] = []
    lines.append("# Discover Embedding Reduction Report")
    lines.append("")
    lines.append("## Embedding Visualization Summary")
    lines.append("")
    report_table = overall_df.copy()
    report_table["recommendation"] = report_table["method"].apply(
        lambda method: "Main showcase" if method == showcase_method else "Auxiliary comparison"
    )
    report_table = report_table[
        [
            "method",
            "trustworthiness_mean",
            "silhouette_mean",
            "davies_bouldin_mean",
            "calinski_harabasz_mean",
            "mean_rank_score",
            "recommendation",
        ]
    ].rename(
        columns={
            "method": "Reduction Method",
            "trustworthiness_mean": "Trustworthiness ↑",
            "silhouette_mean": "Silhouette ↑",
            "davies_bouldin_mean": "Davies-Bouldin ↓",
            "calinski_harabasz_mean": "Calinski-Harabasz ↑",
            "mean_rank_score": "Mean Rank ↓",
            "recommendation": "Reporting Role",
        }
    )
    lines.append(report_table.to_markdown(index=False))
    lines.append("")
    lines.append("## Overall Method Summary")
    lines.append("")
    lines.append(overall_df.to_markdown(index=False))
    lines.append("")
    lines.append("## Best Method by Dataset")
    lines.append("")
    lines.append(dataset_best_df[["dataset", "method", "rank_score", "silhouette", "trustworthiness"]].to_markdown(index=False))
    lines.append("")
    lines.append(f"## Recommended Showcase Method: `{showcase_method}`")
    lines.append("")
    lines.append("- The recommended method is selected by mean rank across trustworthiness, silhouette, and Davies-Bouldin.")
    lines.append("- Calinski-Harabasz is reported as an auxiliary statistic, but it is excluded from the showcase decision because it can become numerically unstable on fragmented community layouts.")
    lines.append("- Figures generated per dataset:")
    for artifact in dataset_artifacts:
        lines.append(f"  - `{artifact['dataset']}`: `{artifact['best_method']}` -> `{artifact['figure']}`")
    output_path.write_text("\n".join(lines), encoding="utf-8")


def _safe_mean(series: pd.Series) -> float | None:
    values = [float(value) for value in series.dropna().tolist()]
    if not values:
        return None
    return round(float(statistics.mean(values)), 6)


if __name__ == "__main__":
    main()
