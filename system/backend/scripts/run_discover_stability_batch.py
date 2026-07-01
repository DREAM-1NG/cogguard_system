from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.core.coordination.io_reproduction import (  # noqa: E402
    IOHUNTER_CANONICAL_RELATIONS,
    iohunter_processed_to_event_table,
    load_iohunter_processed_dataset,
    run_discover_stability_analysis,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run label-free Discover time-window and multiscale stability analysis.")
    parser.add_argument("--processed-root", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--datasets", nargs="*", default=["UAE", "cuba", "russia", "venezuela", "iran", "china"])
    parser.add_argument("--relations", nargs="*", default=list(IOHUNTER_CANONICAL_RELATIONS))
    parser.add_argument("--encoder", default="magnn", choices=("lightweight", "han_relation", "han", "magnn_legacy", "magnn", "amdn_hage"))
    parser.add_argument("--community-algorithm", choices=("leiden", "louvain", "greedy"), default="leiden")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--max-edges-per-relation", type=int, default=5000)
    parser.add_argument("--epochs", type=int, default=20)
    parser.add_argument("--embedding-dim", type=int, default=32)
    parser.add_argument("--hidden-dim", type=int, default=32)
    parser.add_argument("--device", default="auto")
    parser.add_argument("--window-sizes", nargs="*", type=float, default=[1.0, 3.0, 6.0], help="Window sizes in timestamp units used by the event table.")
    parser.add_argument("--min-events-per-window", type=int, default=2)
    parser.add_argument("--continue-on-error", action="store_true")
    parser.add_argument("--resume", action="store_true", help="Skip datasets with an existing per-dataset stability manifest.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    processed_root = Path(args.processed_root).resolve()
    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    records = []
    all_windows: list[dict[str, object]] = []
    all_pairwise: list[dict[str, object]] = []
    all_summary: list[dict[str, object]] = []
    for dataset_name in args.datasets:
        started = time.time()
        dataset_output = output_dir / dataset_name
        dataset_manifest = dataset_output / "stability_manifest.json"
        if args.resume and dataset_manifest.exists():
            result = json.loads(dataset_manifest.read_text(encoding="utf-8"))
            elapsed = 0.0
            for row in result.get("windows", []):
                all_windows.append({"dataset": dataset_name, **row})
            for row in result.get("pairwise_stability", []):
                all_pairwise.append({"dataset": dataset_name, **row})
            all_summary.append({"dataset": dataset_name, "runtime_seconds": elapsed, **result.get("summary", {})})
            records.append(
                {
                    "dataset": dataset_name,
                    "status": "skipped_existing",
                    "runtime_seconds": elapsed,
                    "output_dir": str(dataset_output),
                }
            )
            _write_outputs(output_dir, args, records, all_windows, all_pairwise, all_summary)
            continue
        try:
            dataset = load_iohunter_processed_dataset(processed_root / dataset_name)
            events = iohunter_processed_to_event_table(
                dataset,
                dataset_name=dataset_name,
                max_edges_per_relation=args.max_edges_per_relation,
            )
            events_path = dataset_output / "events.csv"
            events_path.parent.mkdir(parents=True, exist_ok=True)
            events.to_csv(events_path, index=False)
            result = run_discover_stability_analysis(
                events,
                output_dir=dataset_output,
                relations=tuple(args.relations),
                seed=args.seed,
                encoder=args.encoder,
                community_algorithm=args.community_algorithm,
                epochs=args.epochs,
                embedding_dim=args.embedding_dim,
                hidden_dim=args.hidden_dim,
                device=args.device,
                window_sizes=tuple(args.window_sizes),
                min_events_per_window=args.min_events_per_window,
            )
            elapsed = round(time.time() - started, 3)
            for row in result["windows"]:
                all_windows.append({"dataset": dataset_name, **row})
            for row in result["pairwise_stability"]:
                all_pairwise.append({"dataset": dataset_name, **row})
            all_summary.append({"dataset": dataset_name, "runtime_seconds": elapsed, **result["summary"]})
            records.append(
                {
                    "dataset": dataset_name,
                    "status": "passed",
                    "runtime_seconds": elapsed,
                    "event_count": len(events),
                    "output_dir": str(dataset_output),
                }
            )
            _write_outputs(output_dir, args, records, all_windows, all_pairwise, all_summary)
        except Exception as exc:
            records.append({"dataset": dataset_name, "status": "failed", "error": str(exc)})
            _write_outputs(output_dir, args, records, all_windows, all_pairwise, all_summary)
            if not args.continue_on_error:
                raise
    _write_outputs(output_dir, args, records, all_windows, all_pairwise, all_summary)
    print(json.dumps({"records": records, "output_dir": str(output_dir)}, ensure_ascii=False, indent=2))
    if any(record["status"] == "failed" for record in records):
        raise SystemExit(1)


def _write_outputs(
    output_dir: Path,
    args: argparse.Namespace,
    records: list[dict[str, object]],
    windows: list[dict[str, object]],
    pairwise: list[dict[str, object]],
    summary: list[dict[str, object]],
) -> None:
    _write_csv(output_dir / "discover_stability_windows.csv", windows)
    _write_csv(output_dir / "discover_stability_pairwise.csv", pairwise)
    _write_csv(output_dir / "discover_stability_summary.csv", summary)
    (output_dir / "stability_batch_manifest.json").write_text(
        json.dumps(
            {
                "records": records,
                "datasets": args.datasets,
                "encoder": args.encoder,
                "community_algorithm": args.community_algorithm,
                "window_sizes": args.window_sizes,
                "max_edges_per_relation": args.max_edges_per_relation,
                "epochs": args.epochs,
                "embedding_dim": args.embedding_dim,
                "hidden_dim": args.hidden_dim,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    fields = sorted({key for row in rows for key in row.keys()})
    with path.open("w", encoding="utf-8", newline="") as file_handle:
        if not fields:
            return
        writer = csv.DictWriter(file_handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


if __name__ == "__main__":
    main()
