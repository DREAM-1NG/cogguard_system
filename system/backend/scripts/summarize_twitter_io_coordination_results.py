from __future__ import annotations

import argparse
import json
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Summarize Twitter IO coordination experiment outputs into a markdown table.",
    )
    parser.add_argument("--results-dir", required=True, help="Experiment output directory")
    parser.add_argument(
        "--output",
        default="",
        help="Optional markdown output path; defaults to <results-dir>/comparison.md",
    )
    return parser.parse_args()


def load_method_summaries(results_dir: Path) -> list[dict[str, object]]:
    summaries: list[dict[str, object]] = []
    for summary_path in sorted(results_dir.glob("*_summary.json")):
        with summary_path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
        summaries.append(payload)
    return summaries


def build_markdown_table(rows: list[dict[str, object]]) -> str:
    header = (
        "| Method | Paper Anchor | Events | Objects | Pairs | Nodes | Edges | "
        "Largest Component | Clusters | Modularity |\n"
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|"
    )
    body_lines = []
    for row in rows:
        body_lines.append(
            "| {method} | {paper_anchor} | {event_count} | {filtered_object_count} | "
            "{pair_count} | {node_count} | {edge_count} | {largest_component_size} | "
            "{cluster_count} | {modularity_score} |".format(
                method=row.get("method", ""),
                paper_anchor=row.get("paper_anchor", ""),
                event_count=row.get("event_count", 0),
                filtered_object_count=row.get("filtered_object_count", 0),
                pair_count=row.get("pair_count", 0),
                node_count=row.get("node_count", 0),
                edge_count=row.get("edge_count", 0),
                largest_component_size=row.get("largest_component_size", 0),
                cluster_count=row.get("cluster_count", 0),
                modularity_score=row.get("modularity_score", "null"),
            )
        )
    return "\n".join([header, *body_lines])


def main() -> None:
    args = parse_args()
    results_dir = Path(args.results_dir).resolve()
    output_path = Path(args.output).resolve() if args.output else results_dir / "comparison.md"
    rows = load_method_summaries(results_dir)
    markdown = build_markdown_table(rows)
    output_path.write_text(markdown + "\n", encoding="utf-8")
    print(markdown)


if __name__ == "__main__":
    main()
