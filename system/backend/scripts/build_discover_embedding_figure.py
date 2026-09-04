from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import Colormap


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build Discover user embedding figure from discovery_summary.json")
    parser.add_argument("--summary", required=True, help="Path to discovery_summary.json")
    parser.add_argument("--output", required=True, help="Output PNG path")
    parser.add_argument("--title", default="Discover User Embedding Visualization")
    parser.add_argument("--top-communities", type=int, default=8, help="Keep only the largest K communities; others grouped as background")
    parser.add_argument("--min-community-size", type=int, default=3, help="Minimum community size to keep distinct")
    parser.add_argument("--perplexity", type=float, default=30.0, help="t-SNE perplexity")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    summary_path = Path(args.summary).resolve()
    output_path = Path(args.output).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    payload = json.loads(summary_path.read_text(encoding="utf-8"))
    embeddings, cluster_ids, node_scores = _load_embeddings(payload)
    if embeddings.size == 0:
        raise SystemExit("No discover_embedding vectors were found in the summary.")

    labels, focus_mask = _focus_labels(cluster_ids, top_communities=args.top_communities, min_community_size=args.min_community_size)
    embeddings = embeddings[focus_mask]
    node_scores = node_scores[focus_mask]

    scaled = _standardize(embeddings)
    pca_2d = _pca_projection(scaled, components=2)
    svd_2d = _svd_projection(scaled, components=2)
    tsne_2d = _tsne_projection(scaled, perplexity=min(args.perplexity, max(5.0, len(scaled) / 8.0)))
    umap_or_fallback, umap_title = _umap_or_fallback_projection(scaled)

    color_values, cmap, label_lookup = _color_encoding(labels)
    sizes = _point_sizes(node_scores)

    fig, axes = plt.subplots(2, 2, figsize=(13.8, 10.2), facecolor="white")
    panels = [
        (axes[0, 0], pca_2d, "PCA visualization", "PCA component 1", "PCA component 2"),
        (axes[0, 1], tsne_2d, "t-SNE visualization", "t-SNE component 1", "t-SNE component 2"),
        (axes[1, 0], umap_or_fallback, umap_title, f"{umap_title.split()[0]} component 1", f"{umap_title.split()[0]} component 2"),
        (axes[1, 1], svd_2d, "SVD visualization", "SVD component 1", "SVD component 2"),
    ]

    for axis, points, title, x_label, y_label in panels:
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
        axis.set_title(title, fontsize=12, pad=10)
        axis.set_xlabel(x_label, fontsize=10)
        axis.set_ylabel(y_label, fontsize=10)
        axis.grid(alpha=0.18, linestyle="--")
        cbar = fig.colorbar(scatter, ax=axis, fraction=0.045, pad=0.04)
        cbar.ax.tick_params(labelsize=8)
        cbar.set_label("Community group", fontsize=9)

    fig.suptitle(args.title, fontsize=18, y=0.985)
    fig.tight_layout(rect=[0, 0, 1, 0.965])
    fig.savefig(output_path, dpi=300)
    plt.close(fig)


def _load_embeddings(payload: dict[str, object]) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    nodes = payload.get("nodes", [])
    if not isinstance(nodes, list):
        return np.empty((0, 0)), np.empty(0), np.empty(0)

    embeddings: list[list[float]] = []
    clusters: list[int] = []
    node_scores: list[float] = []
    for node in nodes:
        if not isinstance(node, dict):
            continue
        embedding = node.get("discover_embedding")
        cluster_id = node.get("cluster_id")
        if not isinstance(embedding, list) or len(embedding) < 2 or cluster_id is None:
            continue
        try:
            embeddings.append([float(value) for value in embedding])
            clusters.append(int(cluster_id))
            node_scores.append(float(node.get("node_score", 0.0)))
        except (TypeError, ValueError):
            continue

    return (
        np.asarray(embeddings, dtype=float),
        np.asarray(clusters, dtype=int),
        np.asarray(node_scores, dtype=float),
    )


def _focus_labels(cluster_ids: np.ndarray, *, top_communities: int, min_community_size: int) -> tuple[np.ndarray, np.ndarray]:
    unique, counts = np.unique(cluster_ids, return_counts=True)
    ranked = sorted(
        [(int(label), int(count)) for label, count in zip(unique.tolist(), counts.tolist()) if int(count) >= min_community_size],
        key=lambda item: (-item[1], item[0]),
    )
    keep = {label for label, _ in ranked[:top_communities]}
    mask = np.asarray([label in keep for label in cluster_ids], dtype=bool)
    if not np.any(mask):
        mask = np.ones_like(cluster_ids, dtype=bool)
        keep = {int(label) for label in unique[: min(len(unique), top_communities)]}
    remap = {label: index for index, label in enumerate(sorted(keep))}
    labels = np.asarray([remap.get(int(label), len(remap)) for label in cluster_ids[mask]], dtype=int)
    return labels, mask


def _standardize(matrix: np.ndarray) -> np.ndarray:
    mean = np.mean(matrix, axis=0, keepdims=True)
    std = np.std(matrix, axis=0, keepdims=True)
    std[std <= 1e-8] = 1.0
    return (matrix - mean) / std


def _pca_projection(matrix: np.ndarray, *, components: int) -> np.ndarray:
    from sklearn.decomposition import PCA

    return PCA(n_components=components, random_state=42).fit_transform(matrix)


def _svd_projection(matrix: np.ndarray, *, components: int) -> np.ndarray:
    from sklearn.decomposition import TruncatedSVD

    return TruncatedSVD(n_components=components, random_state=42).fit_transform(matrix)


def _tsne_projection(matrix: np.ndarray, *, perplexity: float) -> np.ndarray:
    from sklearn.manifold import TSNE

    safe_perplexity = max(5.0, min(float(perplexity), max(5.0, len(matrix) - 1.0)))
    return TSNE(
        n_components=2,
        random_state=42,
        perplexity=safe_perplexity,
        init="pca",
        learning_rate="auto",
        max_iter=1000,
    ).fit_transform(matrix)


def _umap_or_fallback_projection(matrix: np.ndarray) -> tuple[np.ndarray, str]:
    try:
        import umap  # type: ignore

        reducer = umap.UMAP(
            n_components=2,
            random_state=42,
            n_neighbors=min(15, max(5, len(matrix) - 1)),
            min_dist=0.1,
        )
        return reducer.fit_transform(matrix), "UMAP visualization"
    except Exception:
        from sklearn.manifold import SpectralEmbedding

        n_neighbors = min(15, max(2, len(matrix) - 1))
        return (
            SpectralEmbedding(n_components=2, random_state=42, n_neighbors=n_neighbors).fit_transform(matrix),
            "Spectral visualization",
        )


def _color_encoding(labels: np.ndarray) -> tuple[np.ndarray, Colormap, dict[int, int]]:
    label_values = sorted(set(int(value) for value in labels.tolist()))
    label_lookup = {label: index for index, label in enumerate(label_values)}
    color_values = np.asarray([label_lookup[int(label)] for label in labels.tolist()], dtype=float)
    # Keep a continuous academic-style colorbar instead of a stepped categorical bar.
    # The points still encode discrete community ids, but the scalar mappable uses
    # the full viridis ramp so the colorbar remains smooth for report figures.
    cmap = plt.get_cmap("viridis")
    return color_values, cmap, label_lookup


def _point_sizes(node_scores: np.ndarray) -> np.ndarray:
    if node_scores.size == 0:
        return np.asarray([], dtype=float)
    normalized = node_scores - np.min(node_scores)
    max_value = float(np.max(normalized))
    if max_value <= 1e-9:
        return np.full_like(node_scores, 18.0, dtype=float)
    normalized = normalized / max_value
    return 14.0 + normalized * 62.0

if __name__ == "__main__":
    main()
