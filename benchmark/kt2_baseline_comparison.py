from __future__ import annotations

import argparse
import json
from pathlib import Path
from statistics import mean, pstdev
from typing import Dict, Iterable, List, Mapping, Optional


METRICS = (
    "msle",
    "mae",
    "rmse",
    "direction_accuracy",
    "candidate_recall_full",
    "hits@100",
    "map@100",
    "mrr",
    "macro_micro_consistency",
)

PRIMARY_MODELS = ("KT2JointModel", "MINDS", "FOREST", "CasFT")


def load_rows(path: Path) -> List[Dict]:
    if not path.is_file():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, dict)]
    if isinstance(payload, dict):
        rows = payload.get("rows", [])
        return [row for row in rows if isinstance(row, dict)]
    return []


def metric_stats(rows: Iterable[Mapping], metric: str) -> Optional[Dict[str, float]]:
    values = [
        float(row[metric])
        for row in rows
        if normalize_status(row, str(row.get("_source", ""))) == "ok"
        and isinstance(row.get(metric), (int, float))
    ]
    if not values:
        return None
    return {
        "mean": mean(values),
        "std": pstdev(values) if len(values) > 1 else 0.0,
        "n": len(values),
    }


def collect_sources(benchmark_dir: Path) -> Dict[str, List[Dict]]:
    sources = {
        "historical_results": load_rows(benchmark_dir / "results.json"),
        "casft_external_attempt": load_rows(benchmark_dir / "casft_external_attempt.json"),
        "forest_rl_smoke": load_rows(benchmark_dir / "forest_rl_smoke.json"),
        "minds_zip_smoke": load_rows(benchmark_dir / "minds_zip_smoke.json"),
        "kt2_original_fusion_small_matrix": load_rows(benchmark_dir / "kt2_original_fusion_experiment_small_matrix.json"),
        "kt2_original_fusion_ablation_smoke": load_rows(benchmark_dir / "kt2_original_fusion_ablation_smoke.json"),
        "kt2_original_fusion_full_run": load_rows(benchmark_dir / "kt2_original_fusion_full_run.json"),
        "same_protocol_full_run_baselines": load_rows(benchmark_dir / "same_protocol_full_run_baselines.json"),
    }
    return sources


def normalize_status(row: Mapping, source: str) -> str:
    status = row.get("status")
    if isinstance(status, str):
        return status
    return "ok" if any(row.get(metric) is not None for metric in METRICS) else "unknown"


def normalize_level(row: Mapping, source: str) -> str:
    level = row.get("reproduction_level")
    if isinstance(level, str):
        return level
    if source == "historical_results":
        return "historical_result_without_schema"
    return "unknown"


def comparison_rows(sources: Mapping[str, List[Dict]]) -> List[Dict]:
    grouped: Dict[tuple[str, str, str, str, str], List[Dict]] = {}
    for source, rows in sources.items():
        for row in rows:
            model = str(row.get("model", "unknown"))
            if model not in PRIMARY_MODELS:
                continue
            dataset = str(row.get("dataset", "unknown"))
            task = str(row.get("task") or infer_task(row))
            level = normalize_level(row, source)
            scope = comparison_scope(row, source)
            grouped.setdefault((model, dataset, task, level, scope), []).append({**row, "_source": source, "_scope": scope})

    result = []
    for (model, dataset, task, level, scope), rows in sorted(grouped.items()):
        metric_summary = {metric: metric_stats(rows, metric) for metric in METRICS}
        metric_summary = {key: value for key, value in metric_summary.items() if value is not None}
        result.append(
            {
                "model": model,
                "dataset": dataset,
                "task": task,
                "reproduction_level": level,
                "scope": scope,
                "sources": sorted({str(row.get("_source")) for row in rows}),
                "runs": len(rows),
                "status_counts": status_counts(rows),
                "metric_summary": metric_summary,
                "comparability": comparability_label(model, level, rows),
            }
        )
    return result


def comparison_scope(row: Mapping, source: str) -> str:
    if source == "kt2_original_fusion_ablation_smoke":
        return f"ablation:{row.get('ablation_variant', 'unknown')}"
    return source


def infer_task(row: Mapping) -> str:
    has_scale = any(row.get(metric) is not None for metric in ("msle", "mae", "rmse"))
    has_next = any(row.get(metric) is not None for metric in ("hits@100", "map@100", "mrr"))
    if has_scale and has_next:
        return "multi_scale"
    if has_scale:
        return "scale"
    if has_next:
        return "next_hop"
    return "unknown"


def status_counts(rows: Iterable[Mapping]) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for row in rows:
        status = normalize_status(row, str(row.get("_source", "")))
        counts[status] = counts.get(status, 0) + 1
    return counts


def comparability_label(model: str, level: str, rows: List[Mapping]) -> str:
    if model == "KT2JointModel":
        if level == "kt2_joint_model_full_run":
            return "kt2_integrated_same_protocol_full_run"
        if any(str(row.get("_source")) == "kt2_original_fusion_ablation_smoke" for row in rows):
            return "component_ablation_small_run_not_full_protocol"
        return "fusion_small_matrix_not_full_protocol"
    if level == "frontier_reproduction_full_run":
        return "same_protocol_full_run"
    if level == "frontier_reproduction_small_run":
        return "frontier_small_run_not_full_protocol"
    if level == "public_code_adapter":
        return "public_adapter_smoke_or_limited_run"
    if level == "historical_result_without_schema":
        return "historical_baseline_result_needs_schema_refresh"
    return "needs_review"


def missing_requirements(rows: List[Dict]) -> List[str]:
    present = {(row["model"], row["dataset"]) for row in rows}
    missing = []
    for model in PRIMARY_MODELS:
        if not any(item[0] == model for item in present):
            missing.append(f"{model}: no local evidence row found")
    full_run_models = {
        row["model"]
        for row in rows
        if (
            (
                row["model"] == "KT2JointModel"
                and row["reproduction_level"] == "kt2_joint_model_full_run"
                and row["comparability"] == "kt2_integrated_same_protocol_full_run"
            )
            or (
                row["model"] != "KT2JointModel"
                and row["reproduction_level"] == "frontier_reproduction_full_run"
                and row["comparability"] == "same_protocol_full_run"
            )
        )
        and row.get("status_counts", {}).get("ok", 0) > 0
    }
    full_run_complete = len(full_run_models) == len(PRIMARY_MODELS)
    if not full_run_complete:
        if not any(row["model"] == "KT2JointModel" and row["comparability"] == "fusion_small_matrix_not_full_protocol" for row in rows):
            missing.append("KT2JointModel: original-subpath fusion small matrix missing")
        if not any(row["model"] == "KT2JointModel" and row["comparability"] == "component_ablation_small_run_not_full_protocol" for row in rows):
            missing.append("KT2JointModel: same-protocol component ablation evidence missing")
        if not any(row["model"] == "CasFT" and row["reproduction_level"] == "frontier_reproduction_small_run" for row in rows):
            missing.append("CasFT: frontier small-run evidence missing")
    for model in PRIMARY_MODELS:
        if model not in full_run_models:
            missing.append(f"{model}: same-protocol full-run evidence missing")
    if len(full_run_models) == len(PRIMARY_MODELS):
        datasets_by_model = {
            model: {
                row["dataset"]
                for row in rows
                if row["model"] == model
                and (
                    (
                        model == "KT2JointModel"
                        and row["reproduction_level"] == "kt2_joint_model_full_run"
                        and row["comparability"] == "kt2_integrated_same_protocol_full_run"
                    )
                    or (
                        model != "KT2JointModel"
                        and row["reproduction_level"] == "frontier_reproduction_full_run"
                        and row["comparability"] == "same_protocol_full_run"
                    )
                )
                and row.get("status_counts", {}).get("ok", 0) > 0
            }
            for model in PRIMARY_MODELS
        }
        shared_datasets = set.intersection(*(datasets for datasets in datasets_by_model.values()))
        if not shared_datasets:
            missing.append("All models: same-protocol full-run comparison has no shared dataset")
    return missing


def build_report(benchmark_dir: Path) -> Dict:
    sources = collect_sources(benchmark_dir)
    rows = comparison_rows(sources)
    return {
        "schema": "cogguard.kt2.baseline_comparison.v1",
        "status": "partial" if missing_requirements(rows) else "ok",
        "boundary": "Compares available KT2 fusion, MINDS, FOREST, and CasFT evidence; does not imply full original-paper reproduction.",
        "source_files": {name: len(source_rows) for name, source_rows in sources.items()},
        "rows": rows,
        "missing_requirements": missing_requirements(rows),
    }


def write_markdown_legacy(report: Mapping, path: Path) -> None:
    lines = [
        "# KT2 Baseline Comparison",
        "",
        f"- status: `{report.get('status')}`",
        "",
        str(report.get("boundary")),
        "",
        "## Rows",
        "",
        "| model | dataset | task | level | runs | comparability | key metrics |",
        "|---|---|---|---|---:|---|---|",
    ]
    for row in report.get("rows", []):
        metrics = []
        for metric, stats in row.get("metric_summary", {}).items():
            metrics.append(f"{metric}={stats['mean']:.4f}±{stats['std']:.4f} (n={stats['n']})")
        lines.append(
            "| {model} | {dataset} | {task} | {level} | {runs} | {comparability} | {metrics} |".format(
                model=row.get("model"),
                dataset=row.get("dataset"),
                task=row.get("task"),
                level=row.get("reproduction_level"),
                runs=row.get("runs"),
                comparability=row.get("comparability"),
                metrics="<br>".join(metrics) if metrics else "-",
            )
        )
    lines.extend(["", "## Missing / Not Yet Claimable", ""])
    for item in report.get("missing_requirements", []):
        lines.append(f"- {item}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_markdown(report: Mapping, path: Path) -> None:
    lines = [
        "# KT2 Baseline Comparison",
        "",
        f"- status: `{report.get('status')}`",
        "",
        str(report.get("boundary")),
        "",
        "## Rows",
        "",
        "| model | dataset | task | level | scope | runs | comparability | key metrics |",
        "|---|---|---|---|---|---:|---|---|",
    ]
    for row in report.get("rows", []):
        metrics = []
        for metric, stats in row.get("metric_summary", {}).items():
            metrics.append(f"{metric}={stats['mean']:.4f}+/-{stats['std']:.4f} (n={stats['n']})")
        lines.append(
            "| {model} | {dataset} | {task} | {level} | {scope} | {runs} | {comparability} | {metrics} |".format(
                model=row.get("model"),
                dataset=row.get("dataset"),
                task=row.get("task"),
                level=row.get("reproduction_level"),
                scope=row.get("scope", "-"),
                runs=row.get("runs"),
                comparability=row.get("comparability"),
                metrics="<br>".join(metrics) if metrics else "-",
            )
        )
    lines.extend(["", "## Missing / Not Yet Claimable", ""])
    for item in report.get("missing_requirements", []):
        lines.append(f"- {item}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--benchmark_dir", default=str(Path("benchmark")))
    parser.add_argument("--out", default=str(Path("benchmark") / "kt2_baseline_comparison.json"))
    args = parser.parse_args()
    report = build_report(Path(args.benchmark_dir))
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    write_markdown(report, out.with_suffix(".md"))
    print(json.dumps({"status": report["status"], "rows": len(report["rows"]), "out": str(out)}))


if __name__ == "__main__":
    main()
