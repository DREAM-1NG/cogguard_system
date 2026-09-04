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

from app.core.coordination_baseline.io_reproduction import (  # noqa: E402
    IOHUNTER_CANONICAL_RELATIONS,
    iohunter_processed_to_event_table,
    load_iohunter_processed_dataset,
    run_dyna_colm_discover,
    run_zeyan_coexpression_summary,
)


DEFAULT_ENCODERS = ("magnn_legacy", "han", "amdn_hage", "zeyan_coexpression")
DISCOVER_METRIC_FIELDS = (
    "dataset",
    "seed",
    "encoder",
    "node_count",
    "edge_count",
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
    "device",
    "community_algorithm",
    "community_algorithm_effective",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compare Discover encoders without detection metrics.")
    parser.add_argument("--dataset-dir", required=True, help="Directory containing IOHunter processed pickle")
    parser.add_argument("--dataset-name", default="", help="Dataset name for outputs")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--max-edges-per-relation", type=int, default=1000)
    parser.add_argument("--epochs", type=int, default=20)
    parser.add_argument("--embedding-dim", type=int, default=32)
    parser.add_argument("--hidden-dim", type=int, default=32)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--encoders", nargs="*", default=list(DEFAULT_ENCODERS))
    parser.add_argument("--relations", nargs="*", default=list(IOHUNTER_CANONICAL_RELATIONS))
    parser.add_argument("--community-algorithm", choices=("leiden", "louvain", "greedy"), default="leiden")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    dataset_dir = Path(args.dataset_dir).resolve()
    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    dataset_name = args.dataset_name or dataset_dir.name
    dataset = load_iohunter_processed_dataset(dataset_dir)
    events = iohunter_processed_to_event_table(
        dataset,
        dataset_name=dataset_name,
        max_edges_per_relation=args.max_edges_per_relation,
    )
    events_path = output_dir / "events.csv"
    events.to_csv(events_path, index=False)

    rows = []
    summaries = {}
    for encoder in args.encoders:
        encoder_output = output_dir / encoder
        started = time.time()
        if encoder == "zeyan_coexpression":
            summary = run_zeyan_coexpression_summary(
                events,
                output_dir=encoder_output,
                relations=tuple(args.relations),
                seed=args.seed,
                community_algorithm=args.community_algorithm,
            )
        else:
            summary = run_dyna_colm_discover(
                events,
                output_dir=encoder_output,
                relations=tuple(args.relations),
                seed=args.seed,
                encoder=encoder,
                epochs=args.epochs,
                embedding_dim=args.embedding_dim,
                hidden_dim=args.hidden_dim,
                device="auto",
                community_algorithm=args.community_algorithm,
            )
        runtime = round(time.time() - started, 3)
        summaries[encoder] = summary
        rows.append(_summary_row(dataset_name, int(args.seed), encoder, summary, runtime))

    csv_path = output_dir / "discover_metrics.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as file_handle:
        writer = csv.DictWriter(file_handle, fieldnames=list(DISCOVER_METRIC_FIELDS))
        writer.writeheader()
        writer.writerows(rows)
    report = {
        "dataset": dataset_name,
        "seed": int(args.seed),
        "events": str(events_path),
        "rows": rows,
        "winner": _winner(rows),
        "summaries": {
            encoder: {
                "summary_path": str(output_dir / encoder / "discovery_summary.json"),
                "deep_graph_model": summary.get("deep_graph_model", {}),
            }
            for encoder, summary in summaries.items()
        },
    }
    report_path = output_dir / "discover_encoder_comparison.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


def _summary_row(dataset: str, seed: int, encoder: str, summary: dict[str, object], runtime: float) -> dict[str, object]:
    metrics = summary.get("metrics") if isinstance(summary.get("metrics"), dict) else {}
    graph_metrics = summary.get("graph_metrics") if isinstance(summary.get("graph_metrics"), dict) else {}
    deep_model = summary.get("deep_graph_model") if isinstance(summary.get("deep_graph_model"), dict) else {}
    return {
        "dataset": dataset,
        "seed": seed,
        "encoder": encoder,
        "node_count": graph_metrics.get("node_count"),
        "edge_count": graph_metrics.get("edge_count"),
        "modularity": metrics.get("modularity"),
        "density": metrics.get("density"),
        "conductance": metrics.get("conductance"),
        "cluster_count": metrics.get("cluster_count"),
        "largest_cluster_size": metrics.get("largest_cluster_size"),
        "mean_object_concentration": metrics.get("mean_object_concentration"),
        "max_object_concentration": metrics.get("max_object_concentration"),
        "relation_entropy": metrics.get("relation_entropy"),
        "reconstruction_auc": metrics.get("reconstruction_auc"),
        "reconstruction_ap": metrics.get("reconstruction_ap"),
        "final_training_loss": metrics.get("final_training_loss"),
        "runtime_seconds": runtime,
        "device": deep_model.get("device", "cpu"),
        "community_algorithm": summary.get("community_algorithm"),
        "community_algorithm_effective": summary.get("community_algorithm_effective"),
    }


def _winner(rows: list[dict[str, object]]) -> dict[str, object]:
    if not rows:
        return {"conclusion": "insufficient_rows"}
    metrics = ("modularity", "mean_object_concentration", "reconstruction_auc")
    scored = []
    for row in rows:
        values = [float(row[metric]) for metric in metrics if row.get(metric) not in {None, ""}]
        score = sum(values) / len(values) if values else float("-inf")
        scored.append((score, str(row["encoder"])))
    score, encoder = max(scored)
    return {"conclusion": "best_discover_score", "encoder": encoder, "score": round(float(score), 6)}


if __name__ == "__main__":
    main()
