from __future__ import annotations

import argparse
import copy
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
    STABLE_DISCOVER_ENCODER,
    iohunter_processed_to_event_table,
    load_iohunter_processed_dataset,
    prepare_dyna_colm_detect_inputs,
    run_dyna_colm_discover,
    run_dyna_colm_detect,
    run_dyna_colm_detect_from_prepared,
)


DEFAULT_DATASETS = ("UAE", "cuba", "russia", "venezuela", "iran", "china")
DEFAULT_DISCOVER_ENCODERS = (STABLE_DISCOVER_ENCODER,)
DEFAULT_GNN_BACKENDS = ("gfm_lm_gnn", "gfm_lm_gnn_cpu_light", "fusion_gnn", "relation_gnn", "classifier")
DEFAULT_LM_BACKENDS = ("tfidf", "sbert")
DEFAULT_SPLIT_MODES = ("supervised", "scarce_supervised", "cross_io")
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
    parser = argparse.ArgumentParser(description="Run DynaCoLM-Detect batch experiments on IOHunter processed data.")
    parser.add_argument("--processed-root", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument(
        "--precomputed-discovery-root",
        default="",
        help="Optional root directory containing precomputed discovery summaries at <root>/<dataset>/seed_<seed>/<encoder>/discovery_summary.json",
    )
    parser.add_argument("--datasets", nargs="*", default=list(DEFAULT_DATASETS))
    parser.add_argument("--seeds", nargs="*", type=int, default=[42, 43, 44, 45, 46])
    parser.add_argument("--discover-encoders", nargs="*", default=list(DEFAULT_DISCOVER_ENCODERS))
    parser.add_argument("--gnn-backends", nargs="*", default=list(DEFAULT_GNN_BACKENDS))
    parser.add_argument("--lm-backends", nargs="*", default=list(DEFAULT_LM_BACKENDS))
    parser.add_argument("--split-modes", nargs="*", default=list(DEFAULT_SPLIT_MODES))
    parser.add_argument("--max-edges-per-relation", type=int, default=5000)
    parser.add_argument("--discover-epochs", type=int, default=20)
    parser.add_argument("--detect-epochs", type=int, default=20)
    parser.add_argument("--embedding-dim", type=int, default=32)
    parser.add_argument("--hidden-dim", type=int, default=32)
    parser.add_argument("--device", default="auto")
    parser.add_argument(
        "--lm-cache-root",
        default="",
        help="Optional shared LM feature cache root. Defaults to <output-dir>/<dataset>/_lm_cache.",
    )
    parser.add_argument("--relations", nargs="*", default=list(IOHUNTER_CANONICAL_RELATIONS))
    parser.add_argument("--include-diagnostics", action="store_true")
    parser.add_argument(
        "--skip-characterization",
        action="store_true",
        help="Skip heavy PropagationAnalysis-style characterization and write Detect-only summaries for batch metrics.",
    )
    parser.add_argument(
        "--compact-summary",
        action="store_true",
        help="Omit full predictions/node/community score arrays from detection_summary.json; predictions.csv is still written.",
    )
    parser.add_argument("--continue-on-error", action="store_true")
    parser.add_argument("--resume", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    processed_root = Path(args.processed_root).resolve()
    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    records: list[dict[str, object]] = []
    for dataset in args.datasets:
        dataset_dir = processed_root / dataset
        events = iohunter_processed_to_event_table(
            load_iohunter_processed_dataset(dataset_dir),
            dataset_name=dataset,
            max_edges_per_relation=args.max_edges_per_relation,
        )
        prepared_cache: dict[tuple[int, str, str, str], object] = {}
        lm_cache_dir = (Path(args.lm_cache_root).resolve() / dataset) if args.lm_cache_root else (output_dir / dataset / "_lm_cache")
        events_path = output_dir / dataset / "events.csv"
        events_path.parent.mkdir(parents=True, exist_ok=True)
        if not events_path.exists():
            events.to_csv(events_path, index=False)
        for seed in args.seeds:
            for discover_encoder in args.discover_encoders:
                discovery = _load_or_run_discovery(events, output_dir, dataset, seed, discover_encoder, args)
                for split_mode in args.split_modes:
                    for gnn_backend in args.gnn_backends:
                        for lm_backend in args.lm_backends:
                            run_id = (
                                f"{dataset}_seed{seed}_{discover_encoder}_"
                                f"{split_mode}_{gnn_backend}_{lm_backend}"
                            )
                            run_output = output_dir / dataset / f"seed_{seed}" / discover_encoder / split_mode / gnn_backend / lm_backend
                            summary_path = run_output / "detection_summary.json"
                            if args.resume and summary_path.exists():
                                print(f"[skip] {run_id}", flush=True)
                                records.append(_row_from_summary(dataset, seed, run_id, summary_path, status="skipped_existing"))
                                _write_outputs(output_dir, records, args)
                                continue
                            reused = _try_reuse_equivalent_lm_result(
                                output_dir=output_dir,
                                dataset=dataset,
                                seed=seed,
                                discover_encoder=discover_encoder,
                                split_mode=split_mode,
                                gnn_backend=gnn_backend,
                                lm_backend=lm_backend,
                                run_output=run_output,
                            )
                            if reused is not None:
                                print(f"[reuse] {run_id}", flush=True)
                                records.append(_row_from_result(dataset, seed, run_id, reused, 0.0, str(run_output), status="reused_equivalent"))
                                _write_outputs(output_dir, records, args)
                                continue
                            started = time.time()
                            print(f"[start] {run_id}", flush=True)
                            try:
                                prepared_key = (seed, discover_encoder, lm_backend, gnn_backend)
                                prepared = prepared_cache.get(prepared_key)
                                if prepared is None:
                                    prepare_started = time.time()
                                    print(f"[prepare-start] {dataset}_seed{seed}_{discover_encoder}_{gnn_backend}_{lm_backend}", flush=True)
                                    prepared = prepare_dyna_colm_detect_inputs(
                                        events,
                                        relations=tuple(args.relations),
                                        seed=seed,
                                        discover_encoder=discover_encoder,
                                        discover_epochs=args.discover_epochs,
                                        embedding_dim=args.embedding_dim,
                                        hidden_dim=args.hidden_dim,
                                        device=args.device,
                                        lm_backend=lm_backend,
                                        gnn_backend=gnn_backend,
                                        precomputed_discovery=discovery,
                                        lm_cache_dir=lm_cache_dir,
                                    )
                                    prepared_cache[prepared_key] = prepared
                                    print(
                                        f"[prepare-done] {dataset}_seed{seed}_{discover_encoder}_{gnn_backend}_{lm_backend} "
                                        f"runtime={round(time.time() - prepare_started, 3)}s",
                                        flush=True,
                                    )
                                else:
                                    print(f"[prepare-reuse] {dataset}_seed{seed}_{discover_encoder}_{gnn_backend}_{lm_backend}", flush=True)
                                summary = run_dyna_colm_detect_from_prepared(
                                    events,
                                    prepared,
                                    output_dir=run_output,
                                    relations=tuple(args.relations),
                                    seed=seed,
                                    discover_encoder=discover_encoder,
                                    discover_epochs=args.discover_epochs,
                                    detect_epochs=args.detect_epochs,
                                    hidden_dim=args.hidden_dim,
                                    device=args.device,
                                    lm_backend=lm_backend,
                                    gnn_backend=gnn_backend,
                                    split_mode=split_mode,
                                    uses_precomputed_discovery=True,
                                    include_diagnostics=args.include_diagnostics,
                                    include_characterization=not args.skip_characterization,
                                    include_community_scores=not args.compact_summary,
                                    compact_summary=args.compact_summary,
                                    uses_lm_disk_cache=True,
                                )
                                runtime = round(time.time() - started, 3)
                                print(f"[done] {run_id} runtime={runtime}s", flush=True)
                                records.append(_row_from_result(dataset, seed, run_id, summary, runtime, str(run_output)))
                            except Exception as exc:
                                runtime = round(time.time() - started, 3)
                                print(f"[failed] {run_id} runtime={runtime}s error={exc}", flush=True)
                                record = {
                                    "dataset": dataset,
                                    "seed": seed,
                                    "run_id": run_id,
                                    "status": "failed",
                                    "runtime_seconds": runtime,
                                    "error": str(exc),
                                    "output_dir": str(run_output),
                                    "discover_encoder": discover_encoder,
                                    "split_mode": split_mode,
                                    "gnn_backend": gnn_backend,
                                    "lm_backend": lm_backend,
                                }
                                records.append(record)
                                _write_outputs(output_dir, records, args)
                                if not args.continue_on_error:
                                    print(json.dumps({"records": records}, ensure_ascii=False, indent=2))
                                    raise
                            _write_outputs(output_dir, records, args)
    result = _write_outputs(output_dir, records, args)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if any(row.get("status") == "failed" for row in records):
        raise SystemExit(1)


def _try_reuse_equivalent_lm_result(
    *,
    output_dir: Path,
    dataset: str,
    seed: int,
    discover_encoder: str,
    split_mode: str,
    gnn_backend: str,
    lm_backend: str,
    run_output: Path,
) -> dict[str, object] | None:
    if lm_backend != "sbert":
        return None
    source_path = (
        output_dir
        / dataset
        / f"seed_{seed}"
        / discover_encoder
        / split_mode
        / gnn_backend
        / "tfidf"
        / "detection_summary.json"
    )
    if not source_path.exists():
        return None
    source = json.loads(source_path.read_text(encoding="utf-8"))
    model = source.get("detect_model") if isinstance(source.get("detect_model"), dict) else {}
    if model.get("lm_feature_source") != "tfidf_object_bag_fallback":
        return None
    reused = copy.deepcopy(source)
    reused_model = reused.get("detect_model") if isinstance(reused.get("detect_model"), dict) else {}
    reused_model["lm_backend"] = "sbert"
    reused_model["lm_feature_source"] = "tfidf_object_bag_fallback"
    reused_model["reused_from_lm_backend"] = "tfidf"
    reused_model["reused_equivalent_reason"] = "sbert_unavailable_or_failed_to_load"
    run_output.mkdir(parents=True, exist_ok=True)
    (run_output / "detection_summary.json").write_text(
        json.dumps(reused, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    source_predictions = source_path.parent / "predictions.csv"
    if source_predictions.exists():
        (run_output / "predictions.csv").write_text(source_predictions.read_text(encoding="utf-8"), encoding="utf-8")
    return reused


def _load_or_run_discovery(
    events,
    output_dir: Path,
    dataset: str,
    seed: int,
    discover_encoder: str,
    args: argparse.Namespace,
) -> dict[str, object]:
    precomputed_root = Path(args.precomputed_discovery_root).resolve() if getattr(args, "precomputed_discovery_root", "") else None
    if precomputed_root:
        precomputed_summary = (
            precomputed_root
            / dataset
            / f"seed_{seed}"
            / discover_encoder
            / "discovery_summary.json"
        )
        if precomputed_summary.exists():
            return json.loads(precomputed_summary.read_text(encoding="utf-8"))
    discovery_dir = output_dir / dataset / f"seed_{seed}" / discover_encoder / "_cached_discovery"
    summary_path = discovery_dir / "discovery_summary.json"
    if args.resume and summary_path.exists():
        return json.loads(summary_path.read_text(encoding="utf-8"))
    return run_dyna_colm_discover(
        events,
        output_dir=discovery_dir,
        relations=tuple(args.relations),
        seed=seed,
        encoder=discover_encoder,
        epochs=args.discover_epochs,
        embedding_dim=args.embedding_dim,
        hidden_dim=args.hidden_dim,
        device=args.device,
    )


def _row_from_summary(dataset: str, seed: int, run_id: str, summary_path: Path, *, status: str) -> dict[str, object]:
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    return _row_from_result(dataset, seed, run_id, summary, _to_float(summary.get("runtime_seconds")) or 0.0, str(summary_path.parent), status=status)


def _row_from_result(
    dataset: str,
    seed: int,
    run_id: str,
    summary: dict[str, object],
    runtime: float,
    output_dir: str,
    *,
    status: str = "passed",
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
        "detect_epochs": model.get("detect_epochs"),
        "uses_full_discover_embeddings": model.get("uses_full_discover_embeddings"),
        "uses_discover_reweighted_edges": model.get("uses_discover_reweighted_edges"),
        "reweighted_edge_count": model.get("reweighted_edge_count"),
        "edge_score_source": model.get("edge_score_source"),
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


def _write_outputs(output_dir: Path, records: list[dict[str, object]], args: argparse.Namespace) -> dict[str, object]:
    manifest = {
        "datasets": args.datasets,
        "seeds": args.seeds,
        "discover_encoders": args.discover_encoders,
        "gnn_backends": args.gnn_backends,
        "lm_backends": args.lm_backends,
        "split_modes": args.split_modes,
        "precomputed_discovery_root": args.precomputed_discovery_root,
        "max_edges_per_relation": args.max_edges_per_relation,
        "discover_epochs": args.discover_epochs,
        "detect_epochs": args.detect_epochs,
        "embedding_dim": args.embedding_dim,
        "hidden_dim": args.hidden_dim,
        "include_diagnostics": args.include_diagnostics,
        "skip_characterization": args.skip_characterization,
        "compact_summary": args.compact_summary,
        "records": records,
    }
    (output_dir / "batch_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    all_csv = output_dir / "detect_metrics_all.csv"
    if records:
        fields = list(dict.fromkeys(key for row in records for key in row.keys()))
        with all_csv.open("w", encoding="utf-8", newline="") as file_handle:
            writer = csv.DictWriter(file_handle, fieldnames=fields)
            writer.writeheader()
            writer.writerows(records)
    (output_dir / "detect_metrics_all.json").write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
    mean_std = _write_mean_std(output_dir, records)
    report = _write_acceptance_report(output_dir, records)
    return {
        "row_count": len(records),
        "csv": str(all_csv),
        "mean_std_csv": str(mean_std),
        "acceptance_report": str(report),
    }


def _write_mean_std(output_dir: Path, records: list[dict[str, object]]) -> Path:
    output = output_dir / "detect_metrics_mean_std.csv"
    grouped: dict[tuple[str, str, str, str, str], list[dict[str, object]]] = {}
    for row in records:
        if row.get("status") not in {"passed", "skipped_existing", "reused_equivalent"}:
            continue
        key = (
            str(row.get("dataset")),
            str(row.get("discover_encoder")),
            str(row.get("split_mode")),
            str(row.get("gnn_backend")),
            str(row.get("lm_backend")),
        )
        grouped.setdefault(key, []).append(row)
    fields = ["dataset", "discover_encoder", "split_mode", "gnn_backend", "lm_backend", "run_count"]
    for field in METRIC_FIELDS:
        fields.extend([f"{field}_mean", f"{field}_std"])
    with output.open("w", encoding="utf-8", newline="") as file_handle:
        writer = csv.DictWriter(file_handle, fieldnames=fields)
        writer.writeheader()
        for key, group in sorted(grouped.items()):
            item: dict[str, object] = {
                "dataset": key[0],
                "discover_encoder": key[1],
                "split_mode": key[2],
                "gnn_backend": key[3],
                "lm_backend": key[4],
                "run_count": len(group),
            }
            for field in METRIC_FIELDS:
                values = [_to_float(row.get(field)) for row in group]
                values = [value for value in values if value is not None]
                item[f"{field}_mean"] = round(statistics.mean(values), 6) if values else None
                item[f"{field}_std"] = round(statistics.pstdev(values), 6) if len(values) > 1 else 0.0 if values else None
            writer.writerow(item)
    return output


def _write_acceptance_report(output_dir: Path, records: list[dict[str, object]]) -> Path:
    output = output_dir / "acceptance_report.md"
    passed = [row for row in records if row.get("status") in {"passed", "skipped_existing", "reused_equivalent"}]
    failed = [row for row in records if row.get("status") == "failed"]
    reused = [row for row in records if row.get("status") == "reused_equivalent"]
    fallback_count = sum(1 for row in passed if "fallback" in str(row.get("split_detail", "")) or "fallback" in str(row.get("lm_feature_source", "")))
    lines = [
        "# Detect LM+GNN Acceptance Report",
        "",
        f"- Total runs: {len(records)}",
        f"- Passed/skipped: {len(passed)}",
        f"- Reused equivalent LM runs: {len(reused)}",
        f"- Failed: {len(failed)}",
        f"- Runs with fallback markers: {fallback_count}",
        "- Main F1-style metric: `MaxF1`; fixed-threshold F1@0.5 is diagnostic only.",
        "",
        "Main tables:",
        "",
        "- `detect_metrics_all.csv`",
        "- `detect_metrics_mean_std.csv`",
    ]
    if failed:
        lines.extend(["", "Failed runs:", ""])
        for row in failed[:20]:
            lines.append(f"- `{row.get('run_id')}`: {row.get('error')}")
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
