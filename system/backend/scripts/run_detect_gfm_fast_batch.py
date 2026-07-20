from __future__ import annotations

import argparse
import csv
import json
import statistics
import sys
import time
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.core.coordination_baseline.io_reproduction import (  # noqa: E402
    IOHUNTER_CANONICAL_RELATIONS,
    _amdn_hage_style_metrics,
    _cpu_light_gfm_lm_gnn_scores,
    _detection_metric_dict,
    _prediction_rows_from_discover_features,
    _split_for_detect,
    iohunter_processed_to_event_table,
    load_iohunter_processed_dataset,
    prepare_dyna_colm_detect_inputs,
)


DEFAULT_DATASETS = ("UAE", "cuba", "russia", "venezuela", "iran", "china")
DEFAULT_SPLITS = ("supervised", "scarce_supervised", "cross_io")
METRIC_FIELDS = (
    "auc",
    "auprc",
    "max_f1",
    "max_f1_threshold",
    "precision_at_k",
    "recall_at_k",
    "accuracy",
    "amdn_hage_ap",
    "amdn_hage_auc",
    "runtime_seconds",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fast KT1 Detect CPU-light LM+GNN batch runner.")
    parser.add_argument("--processed-root", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--precomputed-discovery-root", required=True)
    parser.add_argument("--lm-cache-root", required=True)
    parser.add_argument("--datasets", nargs="*", default=list(DEFAULT_DATASETS))
    parser.add_argument("--seeds", nargs="*", type=int, default=[42, 43, 44, 45, 46])
    parser.add_argument("--split-modes", nargs="*", default=list(DEFAULT_SPLITS))
    parser.add_argument("--max-edges-per-relation", type=int, default=5000)
    parser.add_argument("--discover-encoder", default="magnn")
    parser.add_argument("--discover-epochs", type=int, default=20)
    parser.add_argument("--embedding-dim", type=int, default=32)
    parser.add_argument("--hidden-dim", type=int, default=32)
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--lm-backend", default="sbert")
    parser.add_argument("--relations", nargs="*", default=list(IOHUNTER_CANONICAL_RELATIONS))
    parser.add_argument("--resume", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    processed_root = Path(args.processed_root).resolve()
    output_dir = Path(args.output_dir).resolve()
    discovery_root = Path(args.precomputed_discovery_root).resolve()
    lm_cache_root = Path(args.lm_cache_root).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, object]] = []
    for dataset in args.datasets:
        dataset_started = time.time()
        print(f"[dataset-start] {dataset}", flush=True)
        events = iohunter_processed_to_event_table(
            load_iohunter_processed_dataset(processed_root / dataset),
            dataset_name=dataset,
            max_edges_per_relation=args.max_edges_per_relation,
        )
        events_path = output_dir / dataset / "events.csv"
        events_path.parent.mkdir(parents=True, exist_ok=True)
        if not events_path.exists():
            events.to_csv(events_path, index=False)
        for seed in args.seeds:
            seed_started = time.time()
            summary_base = output_dir / dataset / f"seed_{seed}" / args.discover_encoder
            discovery_path = discovery_root / dataset / f"seed_{seed}" / args.discover_encoder / "discovery_summary.json"
            if not discovery_path.exists():
                raise FileNotFoundError(f"Missing precomputed discovery: {discovery_path}")
            discovery = json.loads(discovery_path.read_text(encoding="utf-8"))
            print(f"[prepare-start] {dataset} seed={seed}", flush=True)
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
                gnn_backend="gfm_lm_gnn_cpu_light",
                precomputed_discovery=discovery,
                lm_cache_dir=lm_cache_root / dataset,
            )
            print(
                f"[prepare-done] {dataset} seed={seed} runtime={round(time.time() - seed_started, 3)}s "
                f"features={prepared.features.shape} lm={prepared.lm_feature_source}",
                flush=True,
            )
            for split_mode in args.split_modes:
                run_output = summary_base / split_mode / "gfm_lm_gnn_cpu_light" / args.lm_backend
                summary_path = run_output / "detection_summary.json"
                run_id = f"{dataset}_seed{seed}_{args.discover_encoder}_{split_mode}_gfm_lm_gnn_cpu_light_{args.lm_backend}"
                if args.resume and summary_path.exists():
                    print(f"[skip] {run_id}", flush=True)
                    summary = json.loads(summary_path.read_text(encoding="utf-8"))
                    rows.append(_row_from_summary(dataset, seed, run_id, summary, 0.0, str(run_output), "skipped_existing"))
                    _write_outputs(output_dir, rows, args)
                    continue
                started = time.time()
                print(f"[run-start] {run_id}", flush=True)
                split, split_detail = _split_for_detect(events, prepared.nodes, prepared.y, split_mode=split_mode, seed=seed)
                scores, classifier_backend, fusion_details = _cpu_light_gfm_lm_gnn_scores(
                    prepared.features,
                    prepared.y,
                    prepared.graphs,
                    prepared.nodes,
                    discover_feature_count=prepared.discover_feature_count,
                    lm_feature_count=prepared.lm_feature_count,
                    seed=seed,
                    split=split,
                )
                predictions = _prediction_rows_from_discover_features(
                    prepared.nodes,
                    scores,
                    prepared.labels,
                    prepared.node_records,
                    split=split,
                )
                test_predictions = [row for row in predictions if row.get("evaluation_split") == "test"]
                y_true = [int(row["label"]) for row in test_predictions]
                y_score = [float(row["node_score"]) for row in test_predictions]
                metrics = _detection_metric_dict(y_true, y_score) if test_predictions else {}
                metrics["amdn_hage_style"] = _amdn_hage_style_metrics(y_true, y_score) if test_predictions else {}
                runtime = round(time.time() - started, 3)
                summary = _compact_summary(
                    dataset=dataset,
                    seed=seed,
                    split_mode=split_mode,
                    split_detail=split_detail,
                    prepared=prepared,
                    classifier_backend=classifier_backend,
                    fusion_details=fusion_details,
                    metrics=metrics,
                    train_count=int(split.train.size),
                    test_count=int(split.test.size),
                    runtime=runtime,
                    args=args,
                )
                _write_run(run_output, summary, predictions)
                rows.append(_row_from_summary(dataset, seed, run_id, summary, runtime, str(run_output), "passed"))
                _write_outputs(output_dir, rows, args)
                print(f"[run-done] {run_id} runtime={runtime}s auc={metrics.get('auc')}", flush=True)
        print(f"[dataset-done] {dataset} runtime={round(time.time() - dataset_started, 3)}s", flush=True)
    result = _write_outputs(output_dir, rows, args)
    print(json.dumps(result, ensure_ascii=False, indent=2), flush=True)


def _compact_summary(
    *,
    dataset: str,
    seed: int,
    split_mode: str,
    split_detail: str,
    prepared,
    classifier_backend: str,
    fusion_details: dict[str, object],
    metrics: dict[str, object],
    train_count: int,
    test_count: int,
    runtime: float,
    args: argparse.Namespace,
) -> dict[str, object]:
    return {
        "setting": "detect",
        "task": "coordination_discrimination",
        "method": "dyna_colm_detect_fast_batch",
        "dataset": dataset,
        "seed": seed,
        "relations": list(args.relations),
        "detect_model": {
            "uses_discover_outputs": True,
            "discover_encoder": args.discover_encoder,
            "discover_epochs": args.discover_epochs,
            "lm_backend": args.lm_backend,
            "lm_feature_source": prepared.lm_feature_source,
            "gnn_backend": "gfm_lm_gnn_cpu_light",
            "split_mode": split_mode,
            "split_detail": split_detail,
            "train_count": train_count,
            "test_count": test_count,
            "evaluation_protocol": "heldout_test_only",
            "feature_count": int(prepared.features.shape[1]),
            "discover_feature_count": prepared.discover_feature_count,
            "lm_feature_count": prepared.lm_feature_count,
            "discover_embedding_dim": prepared.discover_embedding_dim,
            "classifier_backend": classifier_backend,
            "uses_community_features": True,
            "uses_dynamic_features": True,
            "uses_metapath_instance_features": True,
            "uses_full_discover_embeddings": prepared.discover_embedding_dim > 0,
            "uses_discover_reweighted_edges": prepared.uses_discover_reweighted_edges,
            "reweighted_edge_count": int(prepared.reweighted_edge_count),
            "uses_lm_features": True,
            "uses_precomputed_discovery": True,
            "uses_lm_disk_cache": True,
            "uses_prepared_detect_inputs": True,
            "include_diagnostics": False,
            "include_characterization": False,
            "include_community_scores": False,
            "compact_summary": True,
            "fusion_details": fusion_details,
        },
        "metrics": metrics,
        "runtime_seconds": runtime,
        "prediction_count": len(prepared.nodes),
        "compact_artifacts": {
            "predictions_csv": "predictions.csv",
            "omitted_from_json": ["predictions", "node_scores", "community_scores", "characterization"],
        },
        "characterization": {
            "task": "coordination_characterization",
            "method": "skipped_for_detect_only_batch",
            "communities": [],
            "summary": {"community_count": 0},
        },
    }


def _write_run(output_dir: Path, summary: dict[str, object], predictions: list[dict[str, object]]) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "detection_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    fields = (
        "account_id",
        "label",
        "evaluation_split",
        "predicted_label",
        "node_score",
        "cluster_id",
        "directed_out_weight",
        "directed_in_weight",
    )
    with (output_dir / "predictions.csv").open("w", encoding="utf-8", newline="") as file_handle:
        writer = csv.DictWriter(file_handle, fieldnames=fields)
        writer.writeheader()
        for row in predictions:
            writer.writerow({field: row.get(field) for field in fields})


def _row_from_summary(
    dataset: str,
    seed: int,
    run_id: str,
    summary: dict[str, object],
    runtime: float,
    output_dir: str,
    status: str,
) -> dict[str, object]:
    metrics = summary.get("metrics") if isinstance(summary.get("metrics"), dict) else {}
    model = summary.get("detect_model") if isinstance(summary.get("detect_model"), dict) else {}
    amdn = metrics.get("amdn_hage_style") if isinstance(metrics.get("amdn_hage_style"), dict) else {}
    return {
        "dataset": dataset,
        "seed": seed,
        "run_id": run_id,
        "status": status,
        "discover_encoder": model.get("discover_encoder"),
        "split_mode": model.get("split_mode"),
        "split_detail": model.get("split_detail"),
        "gnn_backend": model.get("gnn_backend"),
        "lm_backend": model.get("lm_backend"),
        "lm_feature_source": model.get("lm_feature_source"),
        "classifier_backend": model.get("classifier_backend"),
        "evaluation_protocol": model.get("evaluation_protocol"),
        "feature_count": model.get("feature_count"),
        "discover_feature_count": model.get("discover_feature_count"),
        "lm_feature_count": model.get("lm_feature_count"),
        "discover_embedding_dim": model.get("discover_embedding_dim"),
        "uses_full_discover_embeddings": model.get("uses_full_discover_embeddings"),
        "uses_discover_reweighted_edges": model.get("uses_discover_reweighted_edges"),
        "reweighted_edge_count": model.get("reweighted_edge_count"),
        "train_count": model.get("train_count"),
        "test_count": model.get("test_count"),
        "auc": metrics.get("auc"),
        "auprc": metrics.get("auprc"),
        "max_f1": metrics.get("max_f1", amdn.get("max_f1")),
        "max_f1_threshold": metrics.get("max_f1_threshold", amdn.get("max_f1_threshold")),
        "precision_at_k": metrics.get("precision_at_k"),
        "recall_at_k": metrics.get("recall_at_k"),
        "accuracy": metrics.get("accuracy"),
        "amdn_hage_ap": amdn.get("ap"),
        "amdn_hage_auc": amdn.get("auc"),
        "diagnostic_f1_at_0_5": amdn.get("f1_at_0_5", metrics.get("f1")),
        "runtime_seconds": runtime,
        "output_dir": output_dir,
        "summary_path": str(Path(output_dir) / "detection_summary.json"),
    }


def _write_outputs(output_dir: Path, rows: list[dict[str, object]], args: argparse.Namespace) -> dict[str, object]:
    (output_dir / "detect_metrics_all.json").write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    all_csv = output_dir / "detect_metrics_all.csv"
    if rows:
        fields = list(dict.fromkeys(key for row in rows for key in row.keys()))
        with all_csv.open("w", encoding="utf-8", newline="") as file_handle:
            writer = csv.DictWriter(file_handle, fieldnames=fields)
            writer.writeheader()
            writer.writerows(rows)
    mean_std = _write_mean_std(output_dir, rows)
    manifest = {
        "datasets": args.datasets,
        "seeds": args.seeds,
        "split_modes": args.split_modes,
        "discover_encoder": args.discover_encoder,
        "gnn_backend": "gfm_lm_gnn_cpu_light",
        "lm_backend": args.lm_backend,
        "lm_cache_root": args.lm_cache_root,
        "row_count": len(rows),
    }
    (output_dir / "batch_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    report = _write_report(output_dir, rows)
    return {"row_count": len(rows), "csv": str(all_csv), "mean_std_csv": str(mean_std), "acceptance_report": str(report)}


def _write_mean_std(output_dir: Path, rows: list[dict[str, object]]) -> Path:
    output = output_dir / "detect_metrics_mean_std.csv"
    grouped: dict[tuple[str, str], list[dict[str, object]]] = {}
    for row in rows:
        if row.get("status") not in {"passed", "skipped_existing"}:
            continue
        grouped.setdefault((str(row.get("dataset")), str(row.get("split_mode"))), []).append(row)
    fields = ["dataset", "split_mode", "run_count"]
    for field in METRIC_FIELDS:
        fields.extend([f"{field}_mean", f"{field}_std"])
    with output.open("w", encoding="utf-8", newline="") as file_handle:
        writer = csv.DictWriter(file_handle, fieldnames=fields)
        writer.writeheader()
        for key, group in sorted(grouped.items()):
            item: dict[str, object] = {"dataset": key[0], "split_mode": key[1], "run_count": len(group)}
            for field in METRIC_FIELDS:
                values = [_to_float(row.get(field)) for row in group]
                values = [value for value in values if value is not None]
                item[f"{field}_mean"] = round(statistics.mean(values), 6) if values else None
                item[f"{field}_std"] = round(statistics.pstdev(values), 6) if len(values) > 1 else 0.0 if values else None
            writer.writerow(item)
    return output


def _write_report(output_dir: Path, rows: list[dict[str, object]]) -> Path:
    output = output_dir / "acceptance_report.md"
    passed = [row for row in rows if row.get("status") in {"passed", "skipped_existing"}]
    lines = [
        "# Fast Detect LM+GNN Acceptance Report",
        "",
        f"- Total rows: {len(rows)}",
        f"- Passed/skipped: {len(passed)}",
        "- Backend: `gfm_lm_gnn_cpu_light`",
        "- Evaluation: held-out test only",
        "- Main F1-style metric: `MaxF1`; fixed-threshold F1@0.5 is diagnostic only.",
        "- Summary mode: compact Detect-only; predictions are stored in per-run `predictions.csv`.",
    ]
    output.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return output


def _to_float(value: object) -> float | None:
    if value in {None, ""}:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


if __name__ == "__main__":
    main()
