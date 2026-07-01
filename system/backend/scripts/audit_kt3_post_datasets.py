"""Audit local KT3 post-level benchmark readiness.

The script is intentionally read-only. It checks whether local benchmark
directories contain the minimum files needed for post-level full validation:
splits, labels, text fields, and media alignment where applicable.
"""

from __future__ import annotations

import argparse
import csv
import json
import zipfile
from collections import Counter
from pathlib import Path
from typing import Any

DEFAULT_REGISTRY = (
    Path(__file__).resolve().parents[1]
    / "app"
    / "core"
    / "risk"
    / "config"
    / "kt3_post_benchmarks.json"
)


POST_BENCHMARKS = {
    "MultiOFF": {
        "task": "meme_offensive_detection",
        "modalities": ["text", "image"],
        "required_for_unified_model": True,
    },
    "PHEME": {
        "task": "rumour_thread_veracity",
        "modalities": ["tweet_text", "thread"],
        "required_for_unified_model": True,
    },
    "Twitter15_16_dataset": {
        "task": "rumour_event_classification",
        "modalities": ["tweet_tree"],
        "required_for_unified_model": False,
    },
    "mcfend": {
        "task": "chinese_fake_news_detection",
        "modalities": ["news_text", "social_context", "user_context"],
        "required_for_unified_model": True,
    },
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dataset-root",
        default=r"G:\CISCN\dataset",
        help="Root directory containing local benchmark datasets.",
    )
    parser.add_argument(
        "--output",
        default=r"G:\CISCN\.tmp\kt3_post_dataset_audit.json",
        help="Path to write the JSON audit report.",
    )
    parser.add_argument(
        "--registry",
        default=str(DEFAULT_REGISTRY),
        help="Machine-readable KT3 post benchmark registry JSON.",
    )
    args = parser.parse_args()

    dataset_root = Path(args.dataset_root)
    registry = load_registry(Path(args.registry))
    report = {
        "schema": "kt3-post-dataset-audit-v2",
        "dataset_root": str(dataset_root),
        "registry_path": str(Path(args.registry)),
        "registry_schema": registry.get("schema"),
        "scope": "post_level_unified_detection",
        "benchmarks": {},
        "summary": {},
    }

    report["benchmarks"]["MultiOFF"] = audit_multioff(dataset_root / "MultiOFF")
    report["benchmarks"]["PHEME"] = audit_pheme(dataset_root / "PHEME")
    report["benchmarks"]["Twitter15_16_dataset"] = audit_twitter1516(
        dataset_root / "Twitter15_16_dataset"
    )
    report["benchmarks"]["mcfend"] = audit_mcfend(dataset_root / "mcfend")
    report["benchmarks"]["HateXplain"] = audit_hatexplain(
        first_existing_path(
            [
                dataset_root / "HateXplain",
                dataset_root / "hatexplain",
                dataset_root / "kt3_public" / "HateXplain",
                dataset_root / "kt3_public" / "hatexplain",
            ]
        )
    )
    report["benchmarks"]["FakeSV"] = audit_fakesv(
        first_existing_path(
            [
                dataset_root / "FakeSV",
                dataset_root / "fakesv",
                dataset_root / "kt3_public" / "FakeSV",
                dataset_root / "kt3_public" / "fakesv",
            ]
        )
    )
    report["benchmarks"].update(audit_registry_benchmarks(dataset_root, registry, report["benchmarks"]))
    enrich_with_registry(report["benchmarks"], registry)
    report["summary"] = summarize(report["benchmarks"])

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report["summary"], ensure_ascii=False, indent=2))
    print(f"wrote {output}")
    return 0


def audit_multioff(path: Path) -> dict[str, Any]:
    split_dir = path / "Split Dataset"
    image_dir = path / "Labelled Images"
    split_files = {
        "train": split_dir / "Training_meme_dataset.csv",
        "validation": split_dir / "Validation_meme_dataset.csv",
        "test": split_dir / "Testing_meme_dataset.csv",
    }
    result = base_result("MultiOFF", path)
    result.update(
        {
            "task": POST_BENCHMARKS["MultiOFF"]["task"],
            "modalities": POST_BENCHMARKS["MultiOFF"]["modalities"],
            "splits": {},
            "media_alignment": {},
        }
    )
    if not path.exists():
        result["status"] = "missing"
        result["missing"].append(str(path))
        return result

    total_rows = 0
    total_missing_images = 0
    missing_image_examples: list[dict[str, str]] = []
    all_labels: Counter[str] = Counter()
    for split, csv_path in split_files.items():
        split_info = read_csv_split(csv_path)
        labels = Counter(row.get("label", "").strip() for row in split_info["sample_rows"])
        missing_images = 0
        for row in iter_csv_rows(csv_path):
            image_name = row.get("image_name", "").strip()
            if image_name and not (image_dir / image_name).exists():
                missing_images += 1
                if len(missing_image_examples) < 20:
                    missing_image_examples.append(
                        {
                            "split": split,
                            "image_name": image_name,
                        }
                    )
            label = row.get("label", "").strip()
            if label:
                all_labels[label] += 1
        split_info["label_preview"] = dict(labels)
        split_info["missing_images"] = missing_images
        result["splits"][split] = split_info
        total_rows += split_info["row_count"]
        total_missing_images += missing_images

    result["row_count"] = total_rows
    result["label_distribution"] = dict(all_labels)
    result["media_alignment"] = {
        "image_dir_exists": image_dir.exists(),
        "image_files": count_files(image_dir, {".png", ".jpg", ".jpeg"}),
        "missing_split_images": total_missing_images,
        "missing_image_examples": missing_image_examples,
    }
    result["status"] = (
        "ready"
        if total_rows > 0 and image_dir.exists() and total_missing_images == 0
        else "partial"
    )
    result["post_level_views"] = ["meme", "img"]
    return result


def audit_pheme(path: Path) -> dict[str, Any]:
    result = base_result("PHEME", path)
    result.update(
        {
            "task": POST_BENCHMARKS["PHEME"]["task"],
            "modalities": POST_BENCHMARKS["PHEME"]["modalities"],
            "events": {},
        }
    )
    root = path / "all-rnr-annotated-threads"
    if not root.exists():
        result["status"] = "missing"
        result["missing"].append(str(root))
        return result

    total_threads = 0
    total_source_tweets = 0
    total_reactions = 0
    total_annotations = 0
    for event_dir in sorted(p for p in root.iterdir() if p.is_dir() and not p.name.startswith("._")):
        event = {"rumours": 0, "non_rumours": 0, "source_tweets": 0, "reactions": 0}
        for class_name, key in (("rumours", "rumours"), ("non-rumours", "non_rumours")):
            class_dir = event_dir / class_name
            if not class_dir.exists():
                continue
            threads = [p for p in class_dir.iterdir() if p.is_dir() and not p.name.startswith("._")]
            event[key] = len(threads)
            for thread in threads:
                event["source_tweets"] += count_files(thread / "source-tweets", {".json"})
                event["reactions"] += count_files(thread / "reactions", {".json"})
                if (thread / "annotation.json").exists():
                    total_annotations += 1
        total_threads += event["rumours"] + event["non_rumours"]
        total_source_tweets += event["source_tweets"]
        total_reactions += event["reactions"]
        result["events"][event_dir.name] = event

    result["row_count"] = total_source_tweets + total_reactions
    result["thread_count"] = total_threads
    result["annotation_count"] = total_annotations
    result["status"] = "ready" if total_threads and total_source_tweets else "partial"
    result["post_level_views"] = ["tweet"]
    return result


def audit_twitter1516(path: Path) -> dict[str, Any]:
    result = base_result("Twitter15_16_dataset", path)
    result.update(
        {
            "task": POST_BENCHMARKS["Twitter15_16_dataset"]["task"],
            "modalities": POST_BENCHMARKS["Twitter15_16_dataset"]["modalities"],
            "splits": {},
        }
    )
    if not path.exists():
        result["status"] = "missing"
        result["missing"].append(str(path))
        return result

    labels = Counter()
    total_trees = 0
    for subset in ("twitter15", "twitter16"):
        subset_dir = path / subset
        label_path = subset_dir / "label.txt"
        tree_dir = subset_dir / "tree"
        subset_labels = parse_colon_labels(label_path)
        labels.update(subset_labels)
        trees = count_files(tree_dir, {".txt"})
        total_trees += trees
        result["splits"][subset] = {
            "label_file_exists": label_path.exists(),
            "tree_dir_exists": tree_dir.exists(),
            "label_count": sum(subset_labels.values()),
            "tree_files": trees,
            "label_distribution": dict(subset_labels),
        }

    result["row_count"] = total_trees
    result["label_distribution"] = dict(labels)
    result["status"] = "ready" if total_trees and labels else "partial"
    result["post_level_views"] = ["tweet"]
    return result


def audit_mcfend(path: Path) -> dict[str, Any]:
    result = base_result("mcfend", path)
    result.update(
        {
            "task": POST_BENCHMARKS["mcfend"]["task"],
            "modalities": POST_BENCHMARKS["mcfend"]["modalities"],
            "files": {},
        }
    )
    if not path.exists():
        result["status"] = "missing"
        result["missing"].append(str(path))
        return result

    for name in ("news.csv", "social_context.csv", "user.csv"):
        csv_path = path / name
        info = read_csv_split(csv_path, sample_limit=2)
        result["files"][name] = info
    news_info = result["files"]["news.csv"]
    result["row_count"] = news_info.get("row_count", 0)
    result["columns"] = news_info.get("columns", [])
    labels = Counter()
    for row in iter_csv_rows(path / "news.csv"):
        label = row.get("label", "").strip()
        if label:
            labels[label] += 1
    result["label_distribution"] = dict(labels)
    result["status"] = "ready" if result["row_count"] and labels else "partial"
    result["post_level_views"] = ["tweet", "img"]
    return result


def audit_hatexplain(path: Path) -> dict[str, Any]:
    result = base_result("HateXplain", path)
    result.update(
        {
            "task": "text_hate_offensive_detection_with_rationales",
            "modalities": ["tweet_text"],
            "files": {},
            "splits": {},
        }
    )
    data_path = path / "Data" / "dataset.json"
    split_path = path / "Data" / "post_id_divisions.json"
    result["files"] = {
        "dataset.json": {"path": str(data_path), "exists": data_path.exists()},
        "post_id_divisions.json": {"path": str(split_path), "exists": split_path.exists()},
    }
    if not data_path.exists() or not split_path.exists():
        result["status"] = "missing"
        if not data_path.exists():
            result["missing"].append(str(data_path))
        if not split_path.exists():
            result["missing"].append(str(split_path))
        return result

    data = read_json(data_path)
    divisions = read_json(split_path)
    id_to_split = {
        post_id: split
        for split, post_ids in divisions.items()
        for post_id in post_ids
    }
    labels: Counter[str] = Counter()
    splits: Counter[str] = Counter()
    target_rows = 0
    rationale_rows = 0
    for post_id, row in data.items():
        split = id_to_split.get(post_id, "unassigned")
        splits[split] += 1
        annotator_labels = [
            str(item.get("label", "")).strip().lower()
            for item in row.get("annotators") or []
            if item.get("label")
        ]
        if annotator_labels:
            labels[majority_vote(annotator_labels, default="normal")] += 1
        if any(
            str(target).strip() and str(target) != "None"
            for item in row.get("annotators") or []
            for target in item.get("target", [])
        ):
            target_rows += 1
        if row.get("rationales"):
            rationale_rows += 1

    result["row_count"] = len(data)
    result["split_counts"] = dict(splits)
    result["label_distribution"] = dict(labels)
    result["target_annotated_rows"] = target_rows
    result["rationale_annotated_rows"] = rationale_rows
    result["status"] = "ready" if data and {"train", "val", "test"}.issubset(splits) else "partial"
    result["post_level_views"] = ["tweet"]
    return result


def audit_fakesv(path: Path) -> dict[str, Any]:
    result = base_result("FakeSV", path)
    result.update(
        {
            "task": "short_video_fake_news_detection",
            "modalities": ["video_id", "keywords", "label"],
            "files": {},
            "splits": {},
            "media_alignment": {},
        }
    )
    data_path = path / "dataset" / "data.json"
    c3d_zip = path / "features" / "c3d.zip"
    temporal_dir = path / "dataset" / "data-split" / "temporal"
    split_files = {
        "train": temporal_dir / "vid_time3_train.txt",
        "validation": temporal_dir / "vid_time3_val.txt",
        "test": temporal_dir / "vid_time3_test.txt",
    }
    result["files"]["data.json"] = {"path": str(data_path), "exists": data_path.exists()}
    result["files"]["features/c3d.zip"] = {
        "path": str(c3d_zip),
        "exists": c3d_zip.exists(),
        "bytes": c3d_zip.stat().st_size if c3d_zip.exists() else 0,
    }
    split_ids_by_split: dict[str, set[str]] = {}
    for split, split_path in split_files.items():
        ids = read_id_lines(split_path)
        split_ids_by_split[split] = set(ids)
        result["splits"][split] = {
            "path": str(split_path),
            "exists": split_path.exists(),
            "row_count": len(ids),
        }
    if not data_path.exists():
        result["status"] = "missing"
        result["missing"].append(str(data_path))
        return result

    labels: Counter[str] = Counter()
    row_count = 0
    text_rows = 0
    for row in iter_jsonl(data_path):
        row_count += 1
        labels[str(row.get("annotation", "")).strip()] += 1
        if str(row.get("keywords", "")).strip():
            text_rows += 1

    split_total = sum(item["row_count"] for item in result["splits"].values())
    c3d_feature_ids = fakesv_c3d_feature_ids(c3d_zip) if c3d_zip.exists() else set()
    c3d_split_coverage = {
        split: len(ids & c3d_feature_ids)
        for split, ids in split_ids_by_split.items()
    }
    c3d_missing_by_split = {
        split: len(ids - c3d_feature_ids)
        for split, ids in split_ids_by_split.items()
    }
    c3d_full_split_coverage = bool(split_total) and all(
        c3d_split_coverage.get(split, 0) == len(ids)
        for split, ids in split_ids_by_split.items()
    )
    result["row_count"] = row_count
    result["label_distribution"] = dict(labels)
    result["keyword_text_rows"] = text_rows
    result["post_level_views"] = ["tweet", "video"]
    result["media_alignment"] = {
        "video_binary_available": False,
        "preextracted_features_available": bool(c3d_feature_ids),
        "preextracted_feature_type": "C3D" if c3d_feature_ids else "",
        "preextracted_feature_file_count": len(c3d_feature_ids),
        "preextracted_feature_split_coverage": c3d_split_coverage,
        "preextracted_feature_missing_by_split": c3d_missing_by_split,
        "preextracted_feature_full_split_coverage": c3d_full_split_coverage,
        "public_metadata_only": not bool(c3d_feature_ids),
        "temporal_split_ids": split_total,
        "note": (
            "The public repository includes video IDs, keywords, labels, and split IDs. "
            "Raw videos require the data-use agreement. Local c3d.zip is treated as a "
            "pre-extracted video feature baseline when it covers the temporal split IDs."
        ),
    }
    result["status"] = (
        "ready"
        if row_count and split_total and c3d_full_split_coverage
        else ("partial" if row_count and split_total else "present_unverified")
    )
    return result


def audit_registry_benchmarks(
    dataset_root: Path,
    registry: dict[str, Any],
    existing: dict[str, dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    results = {}
    for benchmark in registry.get("benchmarks", []):
        name = benchmark.get("name")
        if not name or name in existing:
            continue
        aliases = benchmark.get("local_aliases") or [name]
        candidates = [
            candidate
            for alias in aliases
            for candidate in (dataset_root / str(alias), dataset_root / "kt3_public" / str(alias))
        ]
        existing_paths = [str(path) for path in candidates if path.exists()]
        required_files = benchmark.get("required_files") or []
        missing_required = []
        for required in required_files:
            if existing_paths:
                if not any((Path(path) / required).exists() for path in existing_paths):
                    missing_required.append(required)
            else:
                missing_required.append(required)
        status = "missing"
        if existing_paths and missing_required:
            status = "present_unverified"
        elif existing_paths:
            status = "present_unverified"
        results[name] = {
            "dataset": name,
            "task": benchmark.get("task", ""),
            "priority": benchmark.get("priority", ""),
            "path": str(candidates[0]) if candidates else str(dataset_root / name),
            "local_candidates": [str(path) for path in candidates],
            "existing_paths": existing_paths,
            "status": status,
            "row_count": 0,
            "post_level_views": benchmark.get("views") or [],
            "missing": [] if existing_paths else [str(candidates[0]) if candidates else str(dataset_root / name)],
            "missing_required_files": missing_required,
        }
    return results


def enrich_with_registry(
    benchmarks: dict[str, dict[str, Any]],
    registry: dict[str, Any],
) -> None:
    by_name = {item.get("name"): item for item in registry.get("benchmarks", [])}
    for name, result in benchmarks.items():
        item = by_name.get(name)
        if not item:
            continue
        result.setdefault("priority", item.get("priority", ""))
        result["registry"] = {
            "priority": item.get("priority", ""),
            "views": item.get("views") or [],
            "paper": item.get("paper") or {},
            "dataset_url": item.get("dataset_url", ""),
            "repository_url": item.get("repository_url", ""),
            "access": item.get("access", ""),
            "license_note": item.get("license_note", ""),
            "requires_media_binary": bool(item.get("requires_media_binary")),
            "validation_role": item.get("validation_role", ""),
            "local_aliases": item.get("local_aliases") or [],
            "required_files": item.get("required_files") or [],
        }
        result["acquisition"] = acquisition_status(result, item)


def base_result(name: str, path: Path) -> dict[str, Any]:
    return {
        "dataset": name,
        "path": str(path),
        "status": "unknown",
        "row_count": 0,
        "missing": [],
        "notes": [],
    }


def load_registry(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"schema": "missing", "benchmarks": []}
    return json.loads(path.read_text(encoding="utf-8"))


def first_existing_path(paths: list[Path]) -> Path:
    for path in paths:
        if path.exists():
            return path
    return paths[0]


def majority_vote(values: list[str], *, default: str) -> str:
    if not values:
        return default
    counts = Counter(values)
    return sorted(counts.items(), key=lambda item: (item[1], item[0]), reverse=True)[0][0]


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8", errors="ignore"))
    except json.JSONDecodeError:
        return {}


def iter_jsonl(path: Path):
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict):
            yield row


def read_id_lines(path: Path) -> list[str]:
    if not path.exists():
        return []
    return [
        line.strip()
        for line in path.read_text(encoding="utf-8", errors="ignore").splitlines()
        if line.strip()
    ]


def acquisition_status(result: dict[str, Any], registry_item: dict[str, Any]) -> dict[str, Any]:
    status = result.get("status", "unknown")
    access = registry_item.get("access", "")
    if status in {"ready", "partial"}:
        action = "local_conversion_or_validation"
    elif status == "present_unverified":
        if "application" in access:
            action = "request_dataset_access_then_download"
        elif "form" in access:
            action = "request_form_access_then_download"
        elif "drive" in access or "codalab" in access:
            action = "download_from_dataset_portal"
        elif "terms" in access or "kaggle" in access:
            action = "accept_terms_then_download"
        elif "manual" in access or "contact" in access:
            action = "manual_contact_required"
        else:
            action = "verify_local_structure_and_add_converter"
    elif "application" in access:
        action = "request_dataset_access_then_download"
    elif "form" in access:
        action = "request_form_access_then_download"
    elif "drive" in access or "codalab" in access:
        action = "download_from_dataset_portal"
    elif "terms" in access or "kaggle" in access:
        action = "accept_terms_then_download"
    elif "manual" in access or "contact" in access:
        action = "manual_contact_required"
    elif "public" in access:
        action = "download_or_clone_public_dataset"
    else:
        action = "manual_acquisition_required"
    return {
        "access": access,
        "action": action,
        "dataset_url": registry_item.get("dataset_url", ""),
        "repository_url": registry_item.get("repository_url", ""),
        "license_note": registry_item.get("license_note", ""),
    }


def read_csv_split(path: Path, sample_limit: int = 3) -> dict[str, Any]:
    info: dict[str, Any] = {
        "path": str(path),
        "exists": path.exists(),
        "row_count": 0,
        "columns": [],
        "sample_rows": [],
    }
    if not path.exists():
        return info
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        info["columns"] = reader.fieldnames or []
        for row in reader:
            info["row_count"] += 1
            if len(info["sample_rows"]) < sample_limit:
                info["sample_rows"].append(row)
    return info


def iter_csv_rows(path: Path):
    if not path.exists():
        return
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            yield row


def parse_colon_labels(path: Path) -> Counter[str]:
    labels: Counter[str] = Counter()
    if not path.exists():
        return labels
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        if ":" not in line:
            continue
        label, _ = line.split(":", 1)
        labels[label.strip()] += 1
    return labels


def count_files(path: Path, suffixes: set[str]) -> int:
    if not path.exists():
        return 0
    return sum(1 for p in path.iterdir() if p.is_file() and p.suffix.lower() in suffixes)


def fakesv_c3d_feature_ids(c3d_zip: Path) -> set[str]:
    try:
        with zipfile.ZipFile(c3d_zip) as archive:
            return {
                Path(name).stem
                for name in archive.namelist()
                if name.startswith("c3d/") and name.endswith(".hdf5")
            }
    except Exception:
        return set()


def summarize(benchmarks: dict[str, dict[str, Any]]) -> dict[str, Any]:
    statuses = Counter(item.get("status", "unknown") for item in benchmarks.values())
    ready = sorted(name for name, item in benchmarks.items() if item.get("status") == "ready")
    partial = sorted(name for name, item in benchmarks.items() if item.get("status") == "partial")
    missing = sorted(name for name, item in benchmarks.items() if item.get("status") == "missing")
    present_unverified = sorted(
        name for name, item in benchmarks.items() if item.get("status") == "present_unverified"
    )
    p0_missing = sorted(
        name
        for name, item in benchmarks.items()
        if item.get("status") == "missing" and (item.get("registry") or {}).get("priority") == "P0"
    )
    p0_ready = sorted(
        name
        for name, item in benchmarks.items()
        if item.get("status") == "ready" and (item.get("registry") or {}).get("priority") == "P0"
    )
    p0_partial = sorted(
        name
        for name, item in benchmarks.items()
        if item.get("status") == "partial" and (item.get("registry") or {}).get("priority") == "P0"
    )
    p0_present_unverified = sorted(
        name
        for name, item in benchmarks.items()
        if item.get("status") == "present_unverified" and (item.get("registry") or {}).get("priority") == "P0"
    )
    p0_ready_or_partial = sorted(p0_ready + p0_partial)
    p0_not_ready_for_full_validation = sorted(
        name
        for name, item in benchmarks.items()
        if (item.get("registry") or {}).get("priority") == "P0"
        and item.get("status") != "ready"
    )
    p0_acquisition_blockers = {
        name: {
            "status": item.get("status", "unknown"),
            "action": (item.get("acquisition") or {}).get("action", ""),
            "dataset_url": (item.get("acquisition") or {}).get("dataset_url", ""),
            "repository_url": (item.get("acquisition") or {}).get("repository_url", ""),
            "missing_required_files": item.get("missing_required_files", []),
        }
        for name, item in sorted(benchmarks.items())
        if (item.get("registry") or {}).get("priority") == "P0"
        and item.get("status") != "ready"
    }
    acquisition_actions: dict[str, list[str]] = {}
    for name, item in benchmarks.items():
        action = (item.get("acquisition") or {}).get("action")
        if not action:
            continue
        acquisition_actions.setdefault(action, []).append(name)
    return {
        "benchmark_count": len(benchmarks),
        "status_counts": dict(statuses),
        "ready": ready,
        "partial": partial,
        "missing": missing,
        "present_unverified": present_unverified,
        "p0_ready": p0_ready,
        "p0_partial": p0_partial,
        "p0_present_unverified": p0_present_unverified,
        "p0_ready_or_partial": p0_ready_or_partial,
        "p0_missing": p0_missing,
        "p0_not_ready_for_full_validation": p0_not_ready_for_full_validation,
        "p0_acquisition_blockers": p0_acquisition_blockers,
        "acquisition_actions": {key: sorted(value) for key, value in acquisition_actions.items()},
        "ready_for_full_post_validation": [
            name
            for name in ready
            if (benchmarks.get(name, {}).get("registry") or {}).get("priority") == "P0"
            or name in {"PHEME", "Twitter15_16_dataset", "mcfend"}
        ],
        "note": (
            "Readiness only means local files are structurally usable. It does "
            "not prove that the unified post-level model has been trained or "
            "fully evaluated on every benchmark."
        ),
    }


if __name__ == "__main__":
    raise SystemExit(main())
