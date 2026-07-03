from __future__ import annotations

import argparse
import csv
import json
import math
import sys
import time
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from mpl_toolkits.mplot3d import Axes3D  # noqa: F401


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.core.coordination.io_reproduction import (  # noqa: E402
    IOHUNTER_CANONICAL_RELATIONS,
    _split_for_detect,
    _torch_fusion_gnn_scores,
    iohunter_processed_to_event_table,
    load_iohunter_processed_dataset,
    prepare_dyna_colm_detect_inputs,
)


DEFAULT_PROCESSED_ROOT = Path(r"G:\CISCN\dataset\iohunter\data\processed")
DEFAULT_DISCOVERY_PATH = (
    BACKEND_ROOT
    / "experiments"
    / "kt1_io_reproduction"
    / "accept_discover_magnn_full_embeddings_6d_s5_ep20"
    / "china"
    / "seed_42"
    / "magnn"
    / "discovery_summary.json"
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run threshold × reweight-ratio continuous sweep on China KT1 Detect.")
    parser.add_argument("--processed-root", default=str(DEFAULT_PROCESSED_ROOT))
    parser.add_argument("--dataset", default="china")
    parser.add_argument("--discovery-summary", default=str(DEFAULT_DISCOVERY_PATH))
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--split-mode", choices=("supervised", "scarce_supervised"), default="supervised")
    parser.add_argument("--embedding-dim", type=int, default=32)
    parser.add_argument("--hidden-dim", type=int, default=32)
    parser.add_argument("--detect-epochs", type=int, default=20)
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--threshold-min", type=float, default=0.0)
    parser.add_argument("--threshold-max", type=float, default=1.0)
    parser.add_argument("--threshold-step", type=float, default=0.02)
    parser.add_argument("--alpha-min", type=float, default=0.0)
    parser.add_argument("--alpha-max", type=float, default=1.0)
    parser.add_argument("--alpha-step", type=float, default=0.02)
    parser.add_argument("--max-edges-per-relation", type=int, default=5000)
    parser.add_argument("--lm-cache-dir", default="")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    events = iohunter_processed_to_event_table(
        load_iohunter_processed_dataset(Path(args.processed_root).resolve() / args.dataset),
        dataset_name=args.dataset,
        max_edges_per_relation=args.max_edges_per_relation,
    )
    discovery = json.loads(Path(args.discovery_summary).resolve().read_text(encoding="utf-8"))
    prepared = prepare_dyna_colm_detect_inputs(
        events,
        relations=tuple(IOHUNTER_CANONICAL_RELATIONS),
        seed=args.seed,
        discover_encoder="magnn",
        discover_epochs=20,
        embedding_dim=args.embedding_dim,
        hidden_dim=args.hidden_dim,
        device=args.device,
        lm_backend="sbert",
        gnn_backend="fusion_gnn",
        precomputed_discovery=discovery,
        lm_cache_dir=Path(args.lm_cache_dir).resolve() if args.lm_cache_dir else None,
    )
    if not str(prepared.lm_feature_source).startswith("sbert:"):
        raise RuntimeError(
            f"SBERT strict sweep requested, but runtime LM source is {prepared.lm_feature_source!r}"
        )

    split, split_detail = _split_for_detect(events, prepared.nodes, prepared.y, split_mode=args.split_mode, seed=args.seed)
    test_labels = prepared.y[split.test]
    thresholds = _float_grid(args.threshold_min, args.threshold_max, args.threshold_step)
    alphas = _float_grid(args.alpha_min, args.alpha_max, args.alpha_step)

    rows: list[dict[str, object]] = []
    started = time.time()
    for alpha in alphas:
        graphs = _interpolate_reweighted_graphs(prepared.graphs, alpha=alpha)
        scores, backend, fusion_details = _torch_fusion_gnn_scores(
            prepared.features,
            prepared.y,
            graphs,
            prepared.nodes,
            discover_feature_count=prepared.discover_feature_count,
            lm_feature_count=prepared.lm_feature_count,
            seed=args.seed,
            epochs=args.detect_epochs,
            hidden_dim=args.hidden_dim,
            device=args.device,
            split=split,
        )
        test_scores = scores[split.test]
        for threshold in thresholds:
            metric = _threshold_metrics(test_labels, test_scores, threshold=threshold)
            rows.append(
                {
                    "dataset": args.dataset,
                    "split_mode": args.split_mode,
                    "seed": args.seed,
                    "alpha": round(alpha, 6),
                    "threshold": round(threshold, 6),
                    "auc": metric["auc"],
                    "accuracy": metric["accuracy"],
                    "precision": metric["precision"],
                    "recall": metric["recall"],
                    "f1": metric["f1"],
                    "positive_count": metric["positive_count"],
                    "classifier_backend": backend,
                    "relation_attention": json.dumps(fusion_details.get("relation_attention", {}), ensure_ascii=False),
                }
            )

    csv_path = output_dir / "china_threshold_alpha_sweep.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    _plot_3d_surface(rows, metric="accuracy", output_path=output_dir / "china_threshold_alpha_accuracy_3d.png")
    _plot_3d_surface(rows, metric="precision", output_path=output_dir / "china_threshold_alpha_precision_3d.png")
    _plot_3d_surface(rows, metric="recall", output_path=output_dir / "china_threshold_alpha_recall_3d.png")
    _plot_3d_surface(rows, metric="f1", output_path=output_dir / "china_threshold_alpha_f1_3d.png")

    df = pd.DataFrame(rows)
    best_accuracy = df.loc[df["accuracy"].astype(float).idxmax()].to_dict()
    best_f1 = df.loc[df["f1"].astype(float).idxmax()].to_dict()
    summary = {
        "dataset": args.dataset,
        "split_mode": args.split_mode,
        "seed": args.seed,
        "lm_feature_source": prepared.lm_feature_source,
        "threshold_count": len(thresholds),
        "alpha_count": len(alphas),
        "runtime_seconds": round(time.time() - started, 3),
        "best_accuracy": best_accuracy,
        "best_f1": best_f1,
        "artifacts": {
            "csv": str(csv_path),
            "accuracy_figure": str(output_dir / "china_threshold_alpha_accuracy_3d.png"),
            "precision_figure": str(output_dir / "china_threshold_alpha_precision_3d.png"),
            "recall_figure": str(output_dir / "china_threshold_alpha_recall_3d.png"),
            "f1_figure": str(output_dir / "china_threshold_alpha_f1_3d.png"),
        },
    }
    (output_dir / "china_threshold_alpha_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


def _float_grid(start: float, stop: float, step: float) -> list[float]:
    values = []
    current = float(start)
    while current <= float(stop) + 1e-9:
        values.append(round(current, 10))
        current += float(step)
    return values


def _interpolate_reweighted_graphs(graphs, *, alpha: float):
    result = {}
    for relation, graph in graphs.items():
        relation_graph = graph.copy()
        for _, _, attrs in relation_graph.edges(data=True):
            original = float(attrs.get("original_weight", attrs.get("weight", 1.0)))
            score = attrs.get("discover_edge_score")
            if score is None:
                attrs["weight"] = original
                continue
            reweighted = original * float(score)
            attrs["weight"] = (1.0 - float(alpha)) * original + float(alpha) * reweighted
        result[relation] = relation_graph
    return result


def _roc_auc(y_true: np.ndarray, y_score: np.ndarray) -> float | None:
    positives = y_score[y_true == 1]
    negatives = y_score[y_true == 0]
    if positives.size == 0 or negatives.size == 0:
        return None
    greater = 0.0
    for positive_score in positives:
        greater += float(np.sum(positive_score > negatives))
        greater += 0.5 * float(np.sum(positive_score == negatives))
    return greater / float(positives.size * negatives.size)


def _threshold_metrics(y_true: np.ndarray, y_score: np.ndarray, *, threshold: float) -> dict[str, object]:
    predictions = (y_score >= threshold).astype(int)
    tp = int(np.sum((predictions == 1) & (y_true == 1)))
    fp = int(np.sum((predictions == 1) & (y_true == 0)))
    fn = int(np.sum((predictions == 0) & (y_true == 1)))
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = (2.0 * precision * recall / (precision + recall)) if (precision + recall) else 0.0
    accuracy = float(np.mean(predictions == y_true)) if y_true.size else 0.0
    auc = _roc_auc(y_true, y_score)
    return {
        "precision": round(precision, 6),
        "recall": round(recall, 6),
        "f1": round(f1, 6),
        "accuracy": round(accuracy, 6),
        "auc": round(float(auc), 6) if auc is not None else None,
        "positive_count": int(np.sum(y_true == 1)),
    }


def _plot_3d_surface(rows: list[dict[str, object]], *, metric: str, output_path: Path) -> None:
    df = pd.DataFrame(rows)
    pivot = df.pivot(index="alpha", columns="threshold", values=metric).astype(float)
    thresholds = pivot.columns.astype(float).to_numpy()
    alphas = pivot.index.astype(float).to_numpy()
    X, Y = np.meshgrid(thresholds, alphas)
    Z = pivot.values

    fig = plt.figure(figsize=(9.4, 6.9), facecolor="white")
    ax = fig.add_subplot(111, projection="3d")
    ax.plot_surface(
        X,
        Y,
        Z,
        cmap="plasma",
        linewidth=0,
        antialiased=True,
        alpha=0.22,
        shade=False,
    )
    scatter = ax.scatter(
        X.flatten(),
        Y.flatten(),
        Z.flatten(),
        c=Z.flatten(),
        cmap="plasma",
        s=16,
        edgecolors="none",
        alpha=0.82,
        depthshade=True,
    )
    ax.set_title(f"{metric.capitalize()} vs. Threshold and Weight Ratio (China)", pad=18, fontsize=13)
    ax.set_xlabel("Threshold", labelpad=10, fontsize=10)
    ax.set_ylabel("Weight Ratio", labelpad=10, fontsize=10)
    ax.set_zlabel(metric.capitalize(), labelpad=8, fontsize=10)
    ax.view_init(elev=30, azim=-60)
    ax.xaxis.pane.set_facecolor((0.98, 0.98, 0.98, 1.0))
    ax.yaxis.pane.set_facecolor((0.98, 0.98, 0.98, 1.0))
    ax.zaxis.pane.set_facecolor((0.98, 0.98, 0.98, 1.0))
    ax.xaxis._axinfo["grid"]["color"] = (0.75, 0.75, 0.75, 0.8)
    ax.yaxis._axinfo["grid"]["color"] = (0.75, 0.75, 0.75, 0.8)
    ax.zaxis._axinfo["grid"]["color"] = (0.75, 0.75, 0.75, 0.8)
    cbar = fig.colorbar(scatter, ax=ax, shrink=0.74, pad=0.08)
    cbar.ax.tick_params(labelsize=9)
    fig.subplots_adjust(left=0.02, right=0.88, top=0.90, bottom=0.05)
    fig.savefig(output_path, dpi=220)
    plt.close(fig)


if __name__ == "__main__":
    main()
