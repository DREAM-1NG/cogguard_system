from __future__ import annotations

import argparse
import csv
import json
import statistics
import subprocess
import sys
import time
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ENCODERS = ("magnn_legacy", "han", "amdn_hage", "zeyan_coexpression")
NUMERIC_FIELDS = (
    "modularity",
    "density",
    "conductance",
    "cluster_count",
    "largest_cluster_size",
    "mean_object_concentration",
    "max_object_concentration",
    "relation_entropy",
    "reconstruction_auc",
    "reconstruction_ap",
    "final_training_loss",
    "runtime_seconds",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Discover encoder comparison on multiple IOHunter datasets.")
    parser.add_argument("--processed-root", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--datasets", nargs="*", default=["UAE", "cuba", "russia", "venezuela", "iran", "china"])
    parser.add_argument("--encoders", nargs="*", default=list(DEFAULT_ENCODERS))
    parser.add_argument("--seeds", nargs="*", type=int, default=[42, 43, 44])
    parser.add_argument("--max-edges-per-relation", type=int, default=5000)
    parser.add_argument("--epochs", type=int, default=50)
    parser.add_argument("--embedding-dim", type=int, default=32)
    parser.add_argument("--hidden-dim", type=int, default=32)
    parser.add_argument("--community-algorithm", choices=("leiden", "louvain", "greedy"), default="leiden")
    parser.add_argument("--python", default=sys.executable)
    parser.add_argument("--continue-on-error", action="store_true")
    parser.add_argument("--resume", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    processed_root = Path(args.processed_root).resolve()
    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    records = []
    for dataset in args.datasets:
        for seed in args.seeds:
            dataset_dir = (processed_root / dataset).resolve()
            run_output = output_dir / dataset / f"seed_{seed}"
            metrics_csv = run_output / "discover_metrics.csv"
            if args.resume and metrics_csv.exists():
                records.append({
                    "dataset": dataset,
                    "seed": seed,
                    "status": "skipped_existing",
                    "output_dir": str(run_output),
                })
                continue
            command = [
                args.python,
                str(BACKEND_ROOT / "scripts" / "run_discover_encoder_comparison.py"),
                "--dataset-dir",
                str(dataset_dir),
                "--dataset-name",
                dataset,
                "--output-dir",
                str(run_output.resolve()),
                "--max-edges-per-relation",
                str(args.max_edges_per_relation),
                "--epochs",
                str(args.epochs),
                "--embedding-dim",
                str(args.embedding_dim),
                "--hidden-dim",
                str(args.hidden_dim),
                "--community-algorithm",
                args.community_algorithm,
                "--seed",
                str(seed),
                "--encoders",
                *args.encoders,
            ]
            started = time.time()
            log_path = output_dir / f"{dataset}_seed_{seed}.log"
            with log_path.open("w", encoding="utf-8") as log_handle:
                process = subprocess.run(
                    command,
                    cwd=str(BACKEND_ROOT),
                    text=True,
                    stdout=log_handle,
                    stderr=subprocess.STDOUT,
                )
            elapsed = round(time.time() - started, 3)
            status = "passed" if process.returncode == 0 else "failed"
            record = {
                "dataset": dataset,
                "seed": seed,
                "status": status,
                "returncode": process.returncode,
                "elapsed_seconds": elapsed,
                "output_dir": str(run_output),
                "log": str(log_path),
            }
            records.append(record)
            _write_manifest(output_dir, records, args)
            if process.returncode != 0 and not args.continue_on_error:
                break
        if any(record["status"] == "failed" for record in records) and not args.continue_on_error:
            break
    _write_manifest(output_dir, records, args)
    aggregate = _aggregate_rows(output_dir, records)
    print(json.dumps({"records": records, "aggregate": aggregate}, ensure_ascii=False, indent=2))
    if any(record["status"] == "failed" for record in records):
        raise SystemExit(1)


def _write_manifest(output_dir: Path, records: list[dict[str, object]], args: argparse.Namespace) -> None:
    (output_dir / "batch_manifest.json").write_text(
        json.dumps(
            {
                "records": records,
                "datasets": args.datasets,
                "encoders": args.encoders,
                "seeds": args.seeds,
                "max_edges_per_relation": args.max_edges_per_relation,
                "epochs": args.epochs,
                "embedding_dim": args.embedding_dim,
                "hidden_dim": args.hidden_dim,
                "community_algorithm": args.community_algorithm,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def _aggregate_rows(output_dir: Path, records: list[dict[str, object]]) -> dict[str, object]:
    rows = []
    for record in records:
        if record["status"] not in {"passed", "skipped_existing"}:
            continue
        csv_path = Path(str(record["output_dir"])) / "discover_metrics.csv"
        if not csv_path.exists():
            continue
        with csv_path.open("r", encoding="utf-8", newline="") as file_handle:
            for row in csv.DictReader(file_handle):
                row["batch_elapsed_seconds"] = record.get("elapsed_seconds")
                rows.append(row)
    all_csv = output_dir / "discover_metrics_all.csv"
    if rows:
        fields = list(rows[0].keys())
        with all_csv.open("w", encoding="utf-8", newline="") as file_handle:
            writer = csv.DictWriter(file_handle, fieldnames=fields)
            writer.writeheader()
            writer.writerows(rows)
    (output_dir / "discover_metrics_all.json").write_text(
        json.dumps(rows, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    mean_std = _write_mean_std(output_dir, rows)
    stability = _write_stability(output_dir, rows)
    runtime = _write_runtime(output_dir, rows)
    return {
        "row_count": len(rows),
        "csv": str(all_csv),
        "mean_std_csv": str(mean_std),
        "stability_csv": str(stability),
        "runtime_csv": str(runtime),
    }


def _write_mean_std(output_dir: Path, rows: list[dict[str, object]]) -> Path:
    grouped: dict[tuple[str, str], list[dict[str, object]]] = {}
    for row in rows:
        grouped.setdefault((str(row["dataset"]), str(row["encoder"])), []).append(row)
    output = output_dir / "discover_metrics_mean_std.csv"
    fields = ["dataset", "encoder", "seed_count"]
    for field in NUMERIC_FIELDS:
        fields.extend([f"{field}_mean", f"{field}_std"])
    with output.open("w", encoding="utf-8", newline="") as file_handle:
        writer = csv.DictWriter(file_handle, fieldnames=fields)
        writer.writeheader()
        for (dataset, encoder), group in sorted(grouped.items()):
            item: dict[str, object] = {"dataset": dataset, "encoder": encoder, "seed_count": len(group)}
            for field in NUMERIC_FIELDS:
                values = [_to_float(row.get(field)) for row in group]
                values = [value for value in values if value is not None]
                item[f"{field}_mean"] = round(statistics.mean(values), 6) if values else None
                item[f"{field}_std"] = round(statistics.pstdev(values), 6) if len(values) > 1 else 0.0 if values else None
            writer.writerow(item)
    return output


def _write_stability(output_dir: Path, rows: list[dict[str, object]]) -> Path:
    grouped: dict[tuple[str, str], list[dict[str, object]]] = {}
    for row in rows:
        grouped.setdefault((str(row["dataset"]), str(row["encoder"])), []).append(row)
    output = output_dir / "discover_stability.csv"
    fields = ["dataset", "encoder", "seed_count", "modularity_std", "cluster_count_std", "largest_cluster_size_std"]
    with output.open("w", encoding="utf-8", newline="") as file_handle:
        writer = csv.DictWriter(file_handle, fieldnames=fields)
        writer.writeheader()
        for (dataset, encoder), group in sorted(grouped.items()):
            writer.writerow({
                "dataset": dataset,
                "encoder": encoder,
                "seed_count": len(group),
                "modularity_std": _std_for(group, "modularity"),
                "cluster_count_std": _std_for(group, "cluster_count"),
                "largest_cluster_size_std": _std_for(group, "largest_cluster_size"),
            })
    return output


def _write_runtime(output_dir: Path, rows: list[dict[str, object]]) -> Path:
    output = output_dir / "discover_runtime.csv"
    fields = ["dataset", "seed", "encoder", "runtime_seconds", "device"]
    with output.open("w", encoding="utf-8", newline="") as file_handle:
        writer = csv.DictWriter(file_handle, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field) for field in fields})
    return output


def _std_for(group: list[dict[str, object]], field: str) -> float | None:
    values = [_to_float(row.get(field)) for row in group]
    values = [value for value in values if value is not None]
    if not values:
        return None
    return round(statistics.pstdev(values), 6) if len(values) > 1 else 0.0


def _to_float(value: object) -> float | None:
    if value in {None, ""}:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


if __name__ == "__main__":
    main()
