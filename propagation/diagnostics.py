from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List

from .loaders import (
    _find_rvnn_processed_files,
    _find_tree_files,
    _find_weibo_event_files,
    _find_weibo_post_file,
    _infer_pheme_label,
    _iter_pheme_thread_dirs,
    _iter_pheme_tweet_jsons,
    _load_json_object,
    _load_pheme_annotation,
    _pheme_label,
    _load_label_map,
    _normalize_dataset_name,
    _parse_edge_records,
    _parse_weibo_event_line,
    load_dataset,
    load_rumor_rvnn_twitter,
)


def inspect_dataset(dataset: str, data_dir: str, output_dir: str | None = None) -> Dict:
    dataset = _normalize_dataset_name(dataset)
    if dataset == "weibo":
        root = Path(data_dir)
        if _find_weibo_event_files(root):
            report = inspect_weibo_rumor(data_dir)
        elif _find_rvnn_processed_files(root):
            report = inspect_rumor_rvnn_twitter(data_dir)
        else:
            report = inspect_weibo_tree_records(data_dir)
    elif dataset == "weibo_rumor":
        report = inspect_weibo_rumor(data_dir)
    elif dataset == "rumor_rvnn_twitter":
        report = inspect_rumor_rvnn_twitter(data_dir)
    elif dataset == "pheme":
        report = inspect_pheme(data_dir)
    else:
        events = load_dataset(dataset, data_dir)
        report = {
            "dataset": dataset,
            "data_dir": data_dir,
            "parsed_events": len(events),
            "parsed_nodes": sum(len(e.nodes) for e in events),
            "status": "ok",
            "note": "Generic inspection only. Detailed line-level audit is implemented for Weibo Rumor and Rumor_RvNN Twitter.",
        }
    if output_dir:
        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)
        (out / "dataset_inspection.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def inspect_pheme(data_dir: str) -> Dict:
    root = Path(data_dir)
    thread_dirs = _iter_pheme_thread_dirs(root)
    topic_counts: Dict[str, int] = {}
    label_counts: Dict[str, int] = {}
    source_count = 0
    reaction_count = 0
    annotation_count = 0
    structure_count = 0
    source_parse_errors = []

    for thread_dir in thread_dirs:
        topic = next((part for part in thread_dir.parts if part.endswith("-all-rnr-threads")), "unknown")
        topic_counts[topic] = topic_counts.get(topic, 0) + 1
        annotation = _load_pheme_annotation(thread_dir)
        if annotation:
            annotation_count += 1
        label = _pheme_label(thread_dir, annotation)
        label_counts[label] = label_counts.get(label, 0) + 1
        if (thread_dir / "structure.json").exists():
            structure_count += 1
        for path in _iter_pheme_tweet_jsons(thread_dir):
            if "source-tweets" in path.parts:
                source_count += 1
                if len(source_parse_errors) < 10:
                    obj = _load_json_object(path)
                    if not obj or not (obj.get("id_str") or obj.get("id")):
                        source_parse_errors.append(str(path))
            elif "reactions" in path.parts:
                reaction_count += 1

    warnings = []
    status = "ok"
    if not thread_dirs:
        status = "error"
        warnings.append("No PHEME thread directories found. Expected */rumours|non-rumours/<thread>/source-tweets and reactions.")
    if source_parse_errors:
        status = "warning"
        warnings.append("Some source tweet JSON files could not be parsed or lacked id/id_str.")
    if thread_dirs and annotation_count < len(thread_dirs):
        warnings.append(f"{len(thread_dirs) - annotation_count} threads have no annotation.json.")

    return {
        "dataset": "pheme",
        "data_dir": str(root),
        "status": status,
        "warnings": warnings,
        "discovered": {
            "thread_dirs": len(thread_dirs),
            "source_tweets": source_count,
            "reactions": reaction_count,
            "annotations": annotation_count,
            "structures": structure_count,
            "topics": topic_counts,
            "labels": label_counts,
        },
        "parsed_estimate": {
            "events": len(thread_dirs),
            "nodes": source_count + reaction_count,
        },
        "source_parse_error_examples": source_parse_errors,
    }


def inspect_rumor_rvnn_twitter(data_dir: str) -> Dict:
    root = Path(data_dir)
    files = _find_rvnn_processed_files(root)
    labels = _load_label_map(root)
    events = load_rumor_rvnn_twitter(data_dir) if files else []
    row_count = 0
    file_reports = []
    for path in files:
        non_empty = sum(1 for line in path.read_text(encoding="utf-8", errors="ignore").splitlines() if line.strip())
        row_count += non_empty
        file_reports.append({"file": str(path), "non_empty_rows": non_empty, "format": "Rumor_RvNN tab-separated processed rows"})

    labeled_events = sum(1 for event in events if event.label)
    warnings = []
    status = "ok"
    if not files:
        status = "error"
        warnings.append("No Rumor_RvNN processed files found. Expected resource/data.TD_RvNN.vol_*.txt or data.BU_RvNN.vol_*.txt.")
    elif labeled_events < len(events):
        status = "warning"
        warnings.append(f"{len(events) - labeled_events} parsed events have no matching Twitter15/16 label entry.")

    return {
        "dataset": "rumor_rvnn_twitter",
        "data_dir": str(root),
        "status": status,
        "warnings": warnings,
        "discovered": {
            "txt_files": len(list(root.rglob("*.txt"))),
            "processed_files": len(files),
            "labels": len(labels),
        },
        "parsed": {
            "events": len(events),
            "nodes": sum(len(event.nodes) for event in events),
            "rows": row_count,
            "events_with_label": labeled_events,
        },
        "file_reports": file_reports,
    }


def inspect_weibo_rumor(data_dir: str) -> Dict:
    root = Path(data_dir)
    event_files = _find_weibo_event_files(root)
    all_json = list(root.rglob("*.json"))
    file_reports: List[Dict] = []
    total_lines = 0
    parsed_lines = 0
    parsed_posts = 0
    examples_unparsed = []

    for path in event_files:
        file_total = 0
        file_parsed = 0
        file_posts = 0
        file_examples = []
        for line_no, raw in enumerate(path.read_text(encoding="utf-8", errors="ignore").splitlines(), 1):
            if not raw.strip():
                continue
            file_total += 1
            parsed = _parse_weibo_event_line(raw)
            if parsed:
                file_parsed += 1
                file_posts += len(parsed[2])
            elif len(file_examples) < 5:
                item = {"line": line_no, "text": raw[:220]}
                file_examples.append(item)
                if len(examples_unparsed) < 10:
                    examples_unparsed.append({**item, "file": str(path)})
        total_lines += file_total
        parsed_lines += file_parsed
        parsed_posts += file_posts
        file_reports.append(
            {
                "file": str(path),
                "non_empty_lines": file_total,
                "parsed_event_lines": file_parsed,
                "referenced_post_ids": file_posts,
                "parse_line_rate": round(file_parsed / file_total, 4) if file_total else 1.0,
                "unparsed_examples": file_examples,
            }
        )

    parsed_event_ids = []
    for report in file_reports:
        path = Path(report["file"])
        for raw in path.read_text(encoding="utf-8", errors="ignore").splitlines():
            parsed = _parse_weibo_event_line(raw)
            if parsed:
                parsed_event_ids.append(parsed[0])
    events_with_posts_json = sum(1 for event_id in parsed_event_ids if _find_weibo_post_file(root, event_id))
    status = "ok"
    warnings = []
    if not event_files:
        status = "error"
        warnings.append("No Weibo Rumor event index found. Expected rows like event_id,label,post_ids.")
    elif parsed_lines < total_lines:
        status = "warning"
        warnings.append("Some event index lines were not parsed; inspect unparsed_examples.")
    if parsed_lines and events_with_posts_json == 0:
        status = "warning"
        warnings.append("Event index parsed, but no posts/{event_id}.json files were found. Graphs will use source-star fallback edges.")

    return {
        "dataset": "weibo_rumor",
        "data_dir": str(root),
        "status": status,
        "warnings": warnings,
        "discovered": {
            "event_index_files": len(event_files),
            "json_files": len(all_json),
            "posts_dir_exists": (root / "posts").exists(),
            "weibo_dir_exists": (root / "Weibo").exists() or (root / "weibo").exists(),
        },
        "parsed": {
            "events": parsed_lines,
            "nodes": parsed_posts,
            "event_index_lines": total_lines,
            "parsed_event_lines": parsed_lines,
            "referenced_post_ids": parsed_posts,
            "events_with_posts_json": events_with_posts_json,
            "overall_parse_line_rate": round(parsed_lines / total_lines, 4) if total_lines else 0.0,
        },
        "unparsed_examples": examples_unparsed,
        "file_reports": file_reports,
    }


def inspect_weibo_tree_records(data_dir: str) -> Dict:
    root = Path(data_dir)
    labels = _load_label_map(root)
    tree_files = _find_tree_files(root)
    all_txt = list(root.rglob("*.txt"))
    all_json = list(root.rglob("*.json"))
    file_reports: List[Dict] = []
    total_lines = 0
    parsed_lines = 0
    parsed_edges = 0
    parsed_nodes = 0
    parsed_events = 0
    suspect_files = []

    for path in tree_files:
        lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
        file_total = 0
        file_parsed_lines = 0
        file_edges = 0
        file_nodes = set()
        examples_unparsed = []
        for line_no, raw in enumerate(lines, 1):
            line = raw.strip()
            if not line:
                continue
            file_total += 1
            records = _parse_edge_records(line, default_event_id=path.stem)
            if records:
                file_parsed_lines += 1
                for record in records:
                    file_edges += 1
                    file_nodes.add(record["parent"])
                    file_nodes.add(record["child"])
            elif len(examples_unparsed) < 5:
                examples_unparsed.append({"line": line_no, "text": line[:220]})
        total_lines += file_total
        parsed_lines += file_parsed_lines
        parsed_edges += file_edges
        parsed_nodes += len(file_nodes)
        if file_edges > 0:
            parsed_events += 1
        if file_total and file_parsed_lines / file_total < 0.8:
            suspect_files.append(str(path))
        file_reports.append(
            {
                "file": str(path),
                "non_empty_lines": file_total,
                "parsed_lines": file_parsed_lines,
                "parsed_edges": file_edges,
                "approx_nodes": len(file_nodes),
                "parse_line_rate": round(file_parsed_lines / file_total, 4) if file_total else 1.0,
                "unparsed_examples": examples_unparsed,
            }
        )

    label_ids = set(labels)
    parsed_event_ids = {Path(r["file"]).stem for r in file_reports if r["parsed_edges"] > 0}
    missing_label = sorted(parsed_event_ids - label_ids)[:50]
    label_without_tree = sorted(label_ids - parsed_event_ids)[:50]

    status = "ok"
    warnings = []
    if not tree_files:
        status = "error"
        warnings.append("No candidate generic tree files found. Use --dataset weibo_rumor for ScienceDB/Ma-Weibo or --dataset rumor_rvnn_twitter for Rumor_RvNN.")
    if suspect_files:
        status = "warning"
        warnings.append(f"{len(suspect_files)} tree files have parse_line_rate < 0.8; inspect dataset_inspection.json examples.")
    if label_without_tree:
        warnings.append(f"Some labels do not have matched tree files. Showing first {len(label_without_tree)} only.")
    if missing_label:
        warnings.append(f"Some parsed tree files do not have labels. Showing first {len(missing_label)} only.")

    return {
        "dataset": "weibo_tree_records",
        "data_dir": str(root),
        "status": status,
        "warnings": warnings,
        "discovered": {
            "txt_files": len(all_txt),
            "json_files": len(all_json),
            "candidate_tree_files": len(tree_files),
            "labels": len(labels),
        },
        "parsed": {
            "events_with_edges": parsed_events,
            "non_empty_tree_lines": total_lines,
            "parsed_tree_lines": parsed_lines,
            "parsed_edges": parsed_edges,
            "approx_nodes_sum_by_file": parsed_nodes,
            "overall_parse_line_rate": round(parsed_lines / total_lines, 4) if total_lines else 0.0,
        },
        "label_coverage": {
            "parsed_events_with_label": len(parsed_event_ids & label_ids),
            "parsed_events_missing_label_first_50": missing_label,
            "labels_without_tree_first_50": label_without_tree,
        },
        "file_reports": file_reports,
    }
