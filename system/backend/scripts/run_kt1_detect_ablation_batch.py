from __future__ import annotations

import argparse
import csv
import json
import statistics
import sys
import time
from pathlib import Path

import numpy as np


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.core.coordination.io_reproduction import (  # noqa: E402
    IOHUNTER_CANONICAL_RELATIONS,
    _amdn_hage_style_metrics,
    _detection_metric_dict,
    _prediction_rows_from_discover_features,
    _split_for_detect,
    _torch_fusion_gnn_scores,
    _torch_relation_gnn_scores,
    _fit_transductive_scores_with_split,
    extract_labels,
    iohunter_processed_to_event_table,
    load_iohunter_processed_dataset,
    prepare_dyna_colm_detect_inputs,
)


DEFAULT_DATASETS = ("UAE", "cuba", "russia", "venezuela", "iran", "china")
DEFAULT_SPLITS = ("supervised", "scarce_supervised", "cross_io")
ABLATIONS = (
    "full",
    "without_lm",
    "without_reweighted_edges",
    "no_community_features",
    "no_discover_embeddings",
    "classifier_struct_only",
    "relation_gnn",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run KT1 Detect ablations on IOHunter processed datasets.")
    parser.add_argument("--processed-root", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--precomputed-discovery-root", required=True)
    parser.add_argument("--datasets", nargs="*", default=list(DEFAULT_DATASETS))
    parser.add_argument("--seeds", nargs="*", type=int, default=[42, 43, 44, 45, 46])
    parser.add_argument("--split-modes", nargs="*", default=list(DEFAULT_SPLITS))
    parser.add_argument("--max-edges-per-relation", type=int, default=5000)
    parser.add_argument("--discover-encoder", default="magnn")
    parser.add_argument("--discover-epochs", type=int, default=20)
    parser.add_argument("--detect-epochs", type=int, default=20)
    parser.add_argument("--embedding-dim", type=int, default=32)
    parser.add_argument("--hidden-dim", type=int, default=32)
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--lm-backend", default="sbert")
    parser.add_argument("--relations", nargs="*", default=list(IOHUNTER_CANONICAL_RELATIONS))
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--continue-on-error", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    processed_root = Path(args.processed_root).resolve()
    output_dir = Path(args.output_dir).resolve()
    discovery_root = Path(args.precomputed_discovery_root).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, object]] = []
    for dataset in args.datasets:
        events = iohunter_processed_to_event_table(
            load_iohunter_processed_dataset(processed_root / dataset),
            dataset_name=dataset,
            max_edges_per_relation=args.max_edges_per_relation,
        )
        for seed in args.seeds:
            discovery_path = discovery_root / dataset / f"seed_{seed}" / args.discover_encoder / "discovery_summary.json"
            if not discovery_path.exists():
                raise FileNotFoundError(f"Missing precomputed discovery: {discovery_path}")
            discovery = json.loads(discovery_path.read_text(encoding="utf-8"))
            prepared = prepare_dyna_colm_detect_inputs(
                events,
                relations=tuple(args.relations),
                seed=seed,
                discover_encoder=args.discover_encoder,
                discover_epochs=args.discover_epochs,
                embedding_dim=args.embedding_dim,
                hidden_dim=args.hidden_dim,
                device=args.device,
                lm_backend=args.lm_backend,
                gnn_backend="fusion_gnn",
                precomputed_discovery=discovery,
            )
            for split_mode in args.split_modes:
                split, split_detail = _split_for_detect(events, prepared.nodes, prepared.y, split_mode=split_mode, seed=seed)
                for ablation in ABLATIONS:
                    run_output = output_dir / dataset / f"seed_{seed}" / split_mode / ablation
                    summary_path = run_output / "ablation_summary.json"
                    run_id = f"{dataset}_seed{seed}_{split_mode}_{ablation}"
                    if args.resume and summary_path.exists():
                        rows.append(_row_from_summary(dataset, seed, split_mode, ablation, json.loads(summary_path.read_text(encoding='utf-8')), "skipped_existing"))
                        continue
                    started = time.time()
                    try:
                        summary = _run_ablation(
                            prepared=prepared,
                            split=split,
                            split_detail=split_detail,
                            seed=seed,
                            hidden_dim=args.hidden_dim,
                            detect_epochs=args.detect_epochs,
                            device=args.device,
                            ablation=ablation,
                        )
                        runtime = round(time.time() - started, 3)
                        summary["runtime_seconds"] = runtime
                        run_output.mkdir(parents=True, exist_ok=True)
                        summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
                        rows.append(_row_from_summary(dataset, seed, split_mode, ablation, summary, "passed"))
                    except Exception as exc:
                        rows.append(
                            {
                                "dataset": dataset,
                                "seed": seed,
                                "split_mode": split_mode,
                                "ablation": ablation,
                                "status": "failed",
                                "error": str(exc),
                            }
                        )
                        if not args.continue_on_error:
                            _write_outputs(output_dir, rows)
                            raise
                    _write_outputs(output_dir, rows)
    result = _write_outputs(output_dir, rows)
    print(json.dumps(result, ensure_ascii=False, indent=2))


def _run_ablation(*, prepared, split, split_detail: str, seed: int, hidden_dim: int, detect_epochs: int, device: str, ablation: str) -> dict[str, object]:
    features = np.asarray(prepared.features, dtype=float)
    graphs = {key: value.copy() for key, value in prepared.graphs.items()}
    discover_feature_count = prepared.discover_feature_count
    lm_feature_count = prepared.lm_feature_count

    if ablation == "without_lm":
        start = discover_feature_count
        stop = discover_feature_count + lm_feature_count
        if stop > start:
            features[:, start:stop] = 0.0
    elif ablation == "without_reweighted_edges":
        for graph in graphs.values():
            for _, _, attrs in graph.edges(data=True):
                attrs["weight"] = float(attrs.get("original_weight", attrs.get("weight", 1.0)))
                attrs["discover_edge_score"] = None
    elif ablation == "no_community_features":
        features[:, 7:12] = 0.0
    elif ablation == "no_discover_embeddings":
        if prepared.discover_embedding_dim > 0:
            features[:, -prepared.discover_embedding_dim :] = 0.0
    elif ablation == "classifier_struct_only":
        if lm_feature_count > 0:
            features[:, discover_feature_count : discover_feature_count + lm_feature_count] = 0.0

    if ablation == "relation_gnn":
        scores, backend, details = _torch_relation_gnn_scores(
            features,
            prepared.y,
            graphs,
            prepared.nodes,
            seed=seed,
            epochs=detect_epochs,
            hidden_dim=hidden_dim,
            device=device,
            split=split,
        )
    elif ablation == "classifier_struct_only":
        scores, backend = _fit_transductive_scores_with_split(features, prepared.y, seed=seed, split=split)
        details = {"fusion_architecture": "classifier_struct_only"}
    else:
        scores, backend, details = _torch_fusion_gnn_scores(
            features,
            prepared.y,
            graphs,
            prepared.nodes,
            discover_feature_count=discover_feature_count,
            lm_feature_count=lm_feature_count,
            seed=seed,
            epochs=detect_epochs,
            hidden_dim=hidden_dim,
            device=device,
            split=split,
        )

    predictions = _prediction_rows_from_discover_features(prepared.nodes, scores, prepared.labels, prepared.node_records, split=split)
    test_predictions = [row for row in predictions if row.get("evaluation_split") == "test"]
    y_true = [int(row["label"]) for row in test_predictions]
    y_score = [float(row["node_score"]) for row in test_predictions]
    metrics = _detection_metric_dict(y_true, y_score) if test_predictions else {}
    metrics["amdn_hage_style"] = _amdn_hage_style_metrics(y_true, y_score) if test_predictions else {}
    return {
        "ablation": ablation,
        "split_detail": split_detail,
        "classifier_backend": backend,
        "fusion_details": details,
        "metrics": metrics,
    }


def _row_from_summary(dataset: str, seed: int, split_mode: str, ablation: str, summary: dict[str, object], status: str) -> dict[str, object]:
    metrics = summary.get("metrics", {}) if isinstance(summary.get("metrics"), dict) else {}
    amdn = metrics.get("amdn_hage_style", {}) if isinstance(metrics.get("amdn_hage_style"), dict) else {}
    return {
        "dataset": dataset,
        "seed": seed,
        "split_mode": split_mode,
        "ablation": ablation,
        "status": status,
        "auc": metrics.get("auc"),
        "auprc": metrics.get("auprc"),
        "macro_f1": metrics.get("macro_f1"),
        "accuracy": metrics.get("accuracy"),
        "precision_at_k": metrics.get("precision_at_k"),
        "recall_at_k": metrics.get("recall_at_k"),
        "amdn_hage_ap": amdn.get("ap"),
        "amdn_hage_auc": amdn.get("auc"),
        "runtime_seconds": summary.get("runtime_seconds"),
        "classifier_backend": summary.get("classifier_backend"),
    }


def _write_outputs(output_dir: Path, rows: list[dict[str, object]]) -> dict[str, object]:
    output_dir.mkdir(parents=True, exist_ok=True)
    csv_path = output_dir / "kt1_detect_ablation_all.csv"
    if rows:
        fields = sorted({key for row in rows for key in row.keys()})
        with csv_path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            writer.writerows(rows)
    mean_std_path = output_dir / "kt1_detect_ablation_mean_std.csv"
    grouped: dict[tuple[str, str, str], list[dict[str, object]]] = {}
    for row in rows:
        if row.get("status") != "passed":
            continue
        grouped.setdefault((str(row["dataset"]), str(row["split_mode"]), str(row["ablation"])), []).append(row)
    mean_rows = []
    for (dataset, split_mode, ablation), group in sorted(grouped.items()):
        mean_rows.append(
            {
                "dataset": dataset,
                "split_mode": split_mode,
                "ablation": ablation,
                "run_count": len(group),
                "auc_mean": _mean(group, "auc"),
                "auprc_mean": _mean(group, "auprc"),
                "macro_f1_mean": _mean(group, "macro_f1"),
                "accuracy_mean": _mean(group, "accuracy"),
                "precision_at_k_mean": _mean(group, "precision_at_k"),
                "recall_at_k_mean": _mean(group, "recall_at_k"),
                "runtime_seconds_mean": _mean(group, "runtime_seconds"),
            }
        )
    if mean_rows:
        with mean_std_path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(mean_rows[0].keys()))
            writer.writeheader()
            writer.writerows(mean_rows)
    return {"output_dir": str(output_dir), "row_count": len(rows)}


def _mean(rows: list[dict[str, object]], key: str) -> float | None:
    values = []
    for row in rows:
        value = row.get(key)
        if value in {None, ""}:
            continue
        values.append(float(value))
    return round(statistics.mean(values), 6) if values else None


if __name__ == "__main__":
    main()
