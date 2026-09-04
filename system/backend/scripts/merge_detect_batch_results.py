from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from types import SimpleNamespace


SCRIPT_DIR = Path(__file__).resolve().parent
BACKEND_ROOT = SCRIPT_DIR.parents[0]
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

import run_detect_encoder_batch as detect_batch  # noqa: E402


KEY_FIELDS = ("dataset", "seed", "discover_encoder", "split_mode", "gnn_backend", "lm_backend")
STATUS_PRIORITY = {
    "passed": 4,
    "reused_equivalent": 3,
    "skipped_existing": 2,
    "failed": 1,
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Merge sharded Detect batch outputs into one aggregate report.")
    parser.add_argument("--inputs", nargs="+", required=True, help="Batch output dirs or detect_metrics_all.{csv,json} files.")
    parser.add_argument("--output-dir", required=True, help="Directory for merged detect_metrics_all/mean_std/report.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    input_paths = [Path(item).resolve() for item in args.inputs]
    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    discovered_sources = _discover_sources(input_paths)
    merged_records: dict[tuple[str, ...], dict[str, object]] = {}
    metadata = {
        "datasets": set(),
        "seeds": set(),
        "discover_encoders": set(),
        "gnn_backends": set(),
        "lm_backends": set(),
        "split_modes": set(),
        "precomputed_discovery_root": set(),
        "max_edges_per_relation": set(),
        "discover_epochs": set(),
        "embedding_dim": set(),
        "hidden_dim": set(),
        "include_diagnostics": set(),
    }

    for source_index, source_dir in enumerate(discovered_sources):
        manifest = _load_manifest(source_dir)
        _update_metadata(metadata, manifest)
        records = _load_records(source_dir)
        for record in records:
            key = tuple(str(record.get(field, "")) for field in KEY_FIELDS)
            existing = merged_records.get(key)
            candidate = dict(record)
            candidate["_source_index"] = source_index
            if existing is None or _should_replace(existing, candidate):
                merged_records[key] = candidate

    ordered_records = []
    for key, record in sorted(
        merged_records.items(),
        key=lambda item: (
            item[0][0],
            int(item[0][1]) if str(item[0][1]).isdigit() else str(item[0][1]),
            item[0][2],
            item[0][3],
            item[0][4],
            item[0][5],
        ),
    ):
        clean_record = {field: value for field, value in record.items() if not str(field).startswith("_")}
        ordered_records.append(clean_record)

    output_args = SimpleNamespace(
        datasets=sorted(metadata["datasets"]),
        seeds=sorted(metadata["seeds"]),
        discover_encoders=sorted(metadata["discover_encoders"]),
        gnn_backends=sorted(metadata["gnn_backends"]),
        lm_backends=sorted(metadata["lm_backends"]),
        split_modes=sorted(metadata["split_modes"]),
        precomputed_discovery_root=_single_or_sorted(metadata["precomputed_discovery_root"]),
        max_edges_per_relation=_single_or_sorted(metadata["max_edges_per_relation"]),
        discover_epochs=_single_or_sorted(metadata["discover_epochs"]),
        embedding_dim=_single_or_sorted(metadata["embedding_dim"]),
        hidden_dim=_single_or_sorted(metadata["hidden_dim"]),
        include_diagnostics=any(bool(value) for value in metadata["include_diagnostics"]),
    )
    result = detect_batch._write_outputs(output_dir, ordered_records, output_args)
    (output_dir / "merge_sources.json").write_text(
        json.dumps(
            {
                "inputs": [str(path) for path in input_paths],
                "sources": [str(path) for path in discovered_sources],
                "row_count": len(ordered_records),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(json.dumps({"output_dir": str(output_dir), "sources": [str(path) for path in discovered_sources], **result}, ensure_ascii=False, indent=2))


def _discover_sources(input_paths: list[Path]) -> list[Path]:
    sources: list[Path] = []
    seen: set[Path] = set()
    for input_path in input_paths:
        if input_path.is_file():
            source_dir = input_path.parent
            if source_dir not in seen:
                sources.append(source_dir)
                seen.add(source_dir)
            continue
        direct_csv = input_path / "detect_metrics_all.csv"
        direct_json = input_path / "detect_metrics_all.json"
        if direct_csv.exists() or direct_json.exists():
            if input_path not in seen:
                sources.append(input_path)
                seen.add(input_path)
            continue
        for csv_path in sorted(input_path.rglob("detect_metrics_all.csv")):
            source_dir = csv_path.parent
            if source_dir not in seen:
                sources.append(source_dir)
                seen.add(source_dir)
    return sources


def _load_manifest(source_dir: Path) -> dict[str, object]:
    manifest_path = source_dir / "batch_manifest.json"
    if not manifest_path.exists():
        return {}
    return json.loads(manifest_path.read_text(encoding="utf-8"))


def _load_records(source_dir: Path) -> list[dict[str, object]]:
    csv_path = source_dir / "detect_metrics_all.csv"
    if csv_path.exists():
        with csv_path.open("r", encoding="utf-8", newline="") as file_handle:
            return list(csv.DictReader(file_handle))
    json_path = source_dir / "detect_metrics_all.json"
    if json_path.exists():
        payload = json.loads(json_path.read_text(encoding="utf-8"))
        return [item for item in payload if isinstance(item, dict)]
    return []


def _update_metadata(metadata: dict[str, set[object]], manifest: dict[str, object]) -> None:
    for key in ("datasets", "seeds", "discover_encoders", "gnn_backends", "lm_backends", "split_modes"):
        values = manifest.get(key)
        if isinstance(values, list):
            metadata[key].update(values)
    for key in ("precomputed_discovery_root", "max_edges_per_relation", "discover_epochs", "embedding_dim", "hidden_dim", "include_diagnostics"):
        value = manifest.get(key)
        if value is not None:
            metadata[key].add(value)


def _should_replace(existing: dict[str, object], candidate: dict[str, object]) -> bool:
    existing_priority = STATUS_PRIORITY.get(str(existing.get("status")), 0)
    candidate_priority = STATUS_PRIORITY.get(str(candidate.get("status")), 0)
    if candidate_priority != existing_priority:
        return candidate_priority > existing_priority
    existing_runtime = detect_batch._to_float(existing.get("runtime_seconds")) or 0.0
    candidate_runtime = detect_batch._to_float(candidate.get("runtime_seconds")) or 0.0
    if candidate_runtime != existing_runtime:
        return candidate_runtime >= existing_runtime
    return int(candidate.get("_source_index", 0)) >= int(existing.get("_source_index", 0))


def _single_or_sorted(values: set[object]) -> object:
    if not values:
        return None
    if len(values) == 1:
        return next(iter(values))
    return sorted(values)


if __name__ == "__main__":
    main()
