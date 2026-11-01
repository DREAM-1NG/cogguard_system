from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Dict, Iterable, List, Mapping, Optional, Sequence

from benchmark.kt2_original_fusion_ablation import REQUIRED_VARIANTS


ROOT = Path(__file__).resolve().parents[1]
BENCHMARK_DIR = ROOT / "benchmark"
DEFAULT_SMALL_MATRIX = BENCHMARK_DIR / "kt2_original_fusion_experiment_small_matrix.json"
DEFAULT_ABLATION = BENCHMARK_DIR / "kt2_original_fusion_ablation_smoke.json"
DEFAULT_BASELINE_COMPARISON = BENCHMARK_DIR / "kt2_baseline_comparison.json"

REQUIRED_ORIGINAL_SUBPATH_FLAGS = {
    "minds_component_status": "original_dynamic_cas_hgnn_fusion_shared_lstm",
    "minds_module_runtime_status": "original_module_forward_auxiliary",
    "forest_runtime_status": "original_rnnmodel_rrmodel_auxiliary",
    "casft_diffusion_status": "original_gaussian_diffusion_st",
    "casft_spatiotemporal_runtime_status": "original_combined_spatiotemporal_model5_auxiliary",
    "casft_spatiotemporal_fusion_status": "original_combined_spatiotemporal_model5_main_fused",
}

REQUIRED_ALIGNMENT_FIELDS = (
    "minds_module_alignment_loss_mean",
    "forest_size_alignment_loss_mean",
    "casft_spatiotemporal_alignment_loss_mean",
)

REQUIRED_METRICS = (
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

STABILITY_THRESHOLDS = {
    "msle": 100.0,
    "mae": 10000.0,
    "rmse": 20000.0,
}


def load_json(path: Path) -> Dict:
    if not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {"rows": payload if isinstance(payload, list) else []}


def rows(payload: Mapping) -> List[Mapping]:
    raw = payload.get("rows", [])
    return [row for row in raw if isinstance(row, Mapping)] if isinstance(raw, list) else []


def check_original_subpaths(small_matrix: Mapping, small_matrix_path: Path = DEFAULT_SMALL_MATRIX) -> Dict:
    audit = small_matrix.get("original_subpath_audit", {})
    row_list = rows(small_matrix)
    row_failures = []
    for row in row_list:
        if row.get("status") != "ok":
            continue
        identity = _identity(row)
        for key, expected in REQUIRED_ORIGINAL_SUBPATH_FLAGS.items():
            if row.get(key) != expected:
                row_failures.append({**identity, "field": key, "expected": expected, "actual": row.get(key)})
        training = row.get("joint_training", {})
        if not isinstance(training, Mapping):
            row_failures.append({**identity, "field": "joint_training", "expected": "mapping", "actual": type(training).__name__})
            continue
        for key in REQUIRED_ALIGNMENT_FIELDS:
            if not _finite(training.get(key)):
                row_failures.append({**identity, "field": key, "expected": "finite teacher-alignment loss", "actual": training.get(key)})
    passed = (
        bool(row_list)
        and audit.get("all_original_subpaths_passed") is True
        and audit.get("all_alignment_losses_recorded") is True
        and not row_failures
    )
    return {
        "id": "original_subpaths_and_teacher_alignment",
        "status": "passed" if passed else "partial",
        "detail": (
            "All small-matrix KT2 rows ran MINDS/FOREST/CasFT original subpaths, recorded teacher alignment, and fused the CasFT continuous-time path into the main KT2 macro/trend outputs."
            if passed
            else "Original subpath or teacher-alignment evidence is missing or incomplete."
        ),
        "rows": len(row_list),
        "failures": row_failures,
        "evidence": [str(small_matrix_path)],
    }


def check_small_matrix_coverage(
    small_matrix: Mapping,
    min_datasets: int,
    min_seeds: int,
    min_obs_ratios: int,
    small_matrix_path: Path = DEFAULT_SMALL_MATRIX,
) -> Dict:
    coverage = small_matrix.get("matrix_coverage", {})
    row_list = [row for row in rows(small_matrix) if row.get("status") == "ok"]
    datasets = {str(row.get("experiment_dataset") or row.get("dataset")) for row in row_list}
    seeds = {str(row.get("experiment_seed") or row.get("seed")) for row in row_list}
    obs_ratios = {str(row.get("experiment_obs_ratio") or row.get("obs_ratio")) for row in row_list}
    passed = (
        coverage.get("coverage_ratio") == 1.0
        and len(datasets) >= min_datasets
        and len(seeds) >= min_seeds
        and len(obs_ratios) >= min_obs_ratios
    )
    return {
        "id": "small_matrix_coverage",
        "status": "passed" if passed else "partial",
        "detail": (
            f"Requires >= {min_datasets} datasets, >= {min_seeds} seeds, >= {min_obs_ratios} observation ratios; "
            f"found {len(datasets)} datasets, {len(seeds)} seeds, {len(obs_ratios)} observation ratios."
        ),
        "coverage": coverage,
        "datasets": sorted(datasets),
        "seeds": sorted(seeds),
        "obs_ratios": sorted(obs_ratios),
        "evidence": [str(small_matrix_path)],
    }


def check_ablation(ablation: Mapping, ablation_path: Path = DEFAULT_ABLATION) -> Dict:
    row_list = [row for row in rows(ablation) if row.get("status") == "ok"]
    variants = {str(row.get("ablation_variant")) for row in row_list}
    missing = [variant for variant in REQUIRED_VARIANTS if variant not in variants]
    deltas = ablation.get("full_vs_minds_baseline_delta", {})
    has_delta = any(isinstance(value, Mapping) and _finite(value.get("better_direction_delta")) for value in deltas.values())
    subpaths = ablation.get("original_subpath_status", {})
    full_subpaths = subpaths.get("all_full_variant_original_subpaths_passed") is True
    full_alignment = subpaths.get("all_full_variant_alignment_losses_recorded") is True
    passed = not missing and has_delta and full_subpaths and full_alignment
    return {
        "id": "same_protocol_component_ablation",
        "status": "passed" if passed else "missing" if not row_list else "partial",
        "detail": (
            "Same-protocol ablation covers MINDS baseline, FOREST, CasFT, full fusion and local bridge variants."
            if passed
            else "Ablation evidence is missing or does not cover every required research component."
        ),
        "variants_found": sorted(variants),
        "variants_missing": missing,
        "has_full_vs_minds_delta": has_delta,
        "full_variant_original_subpaths_passed": full_subpaths,
        "full_variant_alignment_recorded": full_alignment,
        "evidence": [str(ablation_path)],
    }


def check_full_run_claimability(
    small_matrix: Mapping,
    baseline_comparison: Mapping,
    small_matrix_path: Path = DEFAULT_SMALL_MATRIX,
    baseline_comparison_path: Path = DEFAULT_BASELINE_COMPARISON,
) -> Dict:
    row_list = rows(small_matrix)
    small_matrix_full_run_rows = [
        row
        for row in row_list
        if row.get("model") == "KT2JointModel"
        and row.get("status") == "ok"
        and row.get("reproduction_level") == "kt2_joint_model_full_run"
    ]
    comparison_full_run_rows = [
        row
        for row in rows(baseline_comparison)
        if row.get("model") == "KT2JointModel"
        and row.get("reproduction_level") == "kt2_joint_model_full_run"
        and row.get("comparability") == "kt2_integrated_same_protocol_full_run"
        and row.get("status_counts", {}).get("ok", 0) > 0
    ]
    full_run_rows = small_matrix_full_run_rows + comparison_full_run_rows
    comparison_missing = baseline_comparison.get("missing_requirements", [])
    comparison_status = baseline_comparison.get("status")
    passed = bool(full_run_rows) and comparison_status == "ok" and not comparison_missing
    if passed:
        detail = "KT2 integrated full-run row and same-protocol baseline comparison support current integrated-model evidence."
    elif full_run_rows:
        detail = "KT2 full-run row exists, but same-protocol MINDS/FOREST/CasFT baseline comparison is still incomplete."
    else:
        detail = "No same-protocol full-run evidence yet; current KT2 rows must remain small-run/bridge evidence."
    return {
        "id": "same_protocol_full_run_claimability",
        "status": "passed" if passed else "partial",
        "detail": detail,
        "full_run_rows": len(full_run_rows),
        "baseline_comparison_status": comparison_status,
        "baseline_missing_requirements": comparison_missing,
        "evidence": [str(small_matrix_path), str(baseline_comparison_path)],
    }


def check_metric_integrity(small_matrix: Mapping, small_matrix_path: Path = DEFAULT_SMALL_MATRIX) -> Dict:
    failures = []
    row_list = [row for row in rows(small_matrix) if row.get("model") == "KT2JointModel" and row.get("status") == "ok"]
    for row in row_list:
        identity = _identity(row)
        for metric in REQUIRED_METRICS:
            if not _finite(row.get(metric)):
                failures.append({**identity, "metric": metric, "actual": row.get(metric)})
        audit = row.get("candidate_protocol_audit", {})
        if not isinstance(audit, Mapping) or audit.get("leakage_check_passed") is not True:
            failures.append({**identity, "metric": "candidate_protocol_audit", "actual": audit})
    return {
        "id": "metric_and_leakage_integrity",
        "status": "passed" if row_list and not failures else "partial",
        "detail": "KT2 rows expose required macro/micro metrics and leak-check audit." if row_list and not failures else "Metric or leakage evidence is incomplete.",
        "rows": len(row_list),
        "failures": failures,
        "evidence": [str(small_matrix_path)],
    }


def check_metric_stability(small_matrix: Mapping, small_matrix_path: Path = DEFAULT_SMALL_MATRIX) -> Dict:
    row_list = [row for row in rows(small_matrix) if row.get("model") == "KT2JointModel" and row.get("status") == "ok"]
    failures = []
    for row in row_list:
        identity = _identity(row)
        for metric, threshold in STABILITY_THRESHOLDS.items():
            value = row.get(metric)
            if not _finite(value):
                failures.append({**identity, "metric": metric, "threshold": threshold, "actual": value})
            elif abs(float(value)) > threshold:
                failures.append({**identity, "metric": metric, "threshold": threshold, "actual": float(value)})
    return {
        "id": "small_matrix_metric_stability",
        "status": "passed" if row_list and not failures else "partial",
        "detail": (
            "Small-matrix metrics are finite and below conservative explosion thresholds."
            if row_list and not failures
            else "One or more small-matrix rows has metric explosion; stabilize before using as full reproduction evidence."
        ),
        "thresholds": STABILITY_THRESHOLDS,
        "rows": len(row_list),
        "failures": failures,
        "evidence": [str(small_matrix_path)],
    }


def build_gate(
    *,
    small_matrix_path: Path = DEFAULT_SMALL_MATRIX,
    ablation_path: Path = DEFAULT_ABLATION,
    baseline_comparison_path: Path = DEFAULT_BASELINE_COMPARISON,
    min_datasets: int = 3,
    min_seeds: int = 3,
    min_obs_ratios: int = 3,
) -> Dict:
    small_matrix = load_json(small_matrix_path)
    ablation = load_json(ablation_path)
    baseline_comparison = load_json(baseline_comparison_path)
    checks = [
        check_original_subpaths(small_matrix, small_matrix_path),
        check_small_matrix_coverage(small_matrix, min_datasets, min_seeds, min_obs_ratios, small_matrix_path),
        check_metric_integrity(small_matrix, small_matrix_path),
        check_metric_stability(small_matrix, small_matrix_path),
        check_ablation(ablation, ablation_path),
        check_full_run_claimability(small_matrix, baseline_comparison, small_matrix_path, baseline_comparison_path),
    ]
    status = "evidence_passed" if all(check["status"] == "passed" for check in checks) else "incomplete"
    return {
        "schema": "cogguard.kt2.original_fusion_gate.v1",
        "status": status,
        "objective": "Validate KT2 integrated MINDS/FOREST/CasFT-inspired joint-model evidence without overclaiming original-paper reproduction",
        "claim": (
            "KT2 integrated joint-model evidence passes the current gate; this is not a claim that MINDS/FOREST/CasFT original-paper architectures are fully reproduced."
            if status == "evidence_passed"
            else "KT2 has original-subpath fusion evidence, but integrated joint-model evidence is not complete."
        ),
        "completion_rule": (
            "Gate pass requires upstream MINDS/FOREST/CasFT subpaths, CasFT main-output fusion, teacher-alignment evidence, "
            "same-protocol component ablation, multi-dataset/multi-seed/multi-observation coverage, "
            "required macro/micro metrics, leakage audit, a KT2 integrated full-run row, and same-protocol baseline comparison. "
            "It does not certify full original-paper reproduction."
        ),
        "checks": checks,
        "required_next_actions": required_next_actions(checks),
    }


def required_next_actions(checks: Iterable[Mapping]) -> List[str]:
    actions = []
    by_id = {check.get("id"): check for check in checks}
    coverage = by_id.get("small_matrix_coverage", {})
    if coverage.get("status") != "passed":
        actions.append("Expand original-fusion matrix to at least 3 observation ratios, keeping 3 datasets and 3 seeds.")
    ablation = by_id.get("same_protocol_component_ablation", {})
    if ablation.get("status") != "passed":
        actions.append("Run benchmark.kt2_original_fusion_ablation for all required variants and inspect full-vs-MINDS deltas.")
    full_run = by_id.get("same_protocol_full_run_claimability", {})
    if full_run.get("status") != "passed":
        actions.append("Refresh same-protocol MINDS/FOREST/CasFT/KT2 full-run rows before upgrading any reproduction_level.")
    subpaths = by_id.get("original_subpaths_and_teacher_alignment", {})
    if subpaths.get("status") != "passed":
        actions.append("Fix missing original MINDS/FOREST/CasFT subpath or teacher-alignment failures.")
    metrics = by_id.get("metric_and_leakage_integrity", {})
    if metrics.get("status") != "passed":
        actions.append("Fix missing macro/micro metrics or candidate leakage audit failures.")
    stability = by_id.get("small_matrix_metric_stability", {})
    if stability.get("status") != "passed":
        actions.append("Stabilize abnormal small-matrix metric rows before using KT2 fusion results as reproduction evidence.")
    return actions or ["All KT2 integrated-model evidence gates passed; keep reporting it as KT2 evidence, not full original-paper reproduction."]


def write_outputs(gate: Mapping, out_json: Path, out_md: Optional[Path] = None) -> None:
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(gate, ensure_ascii=True, indent=2), encoding="utf-8")
    if out_md:
        out_md.write_text(gate_markdown(gate), encoding="utf-8")


def gate_markdown(gate: Mapping) -> str:
    lines = [
        "# KT2 Original-Fusion Gate",
        "",
        f"- status: `{gate.get('status')}`",
        f"- objective: `{gate.get('objective')}`",
        "",
        str(gate.get("claim")),
        "",
        "Completion rule: " + str(gate.get("completion_rule")),
        "",
        "## Checks",
        "",
    ]
    for check in gate.get("checks", []):
        lines.append(f"- `{check.get('id')}` / `{check.get('status')}`: {check.get('detail')}")
    lines.extend(["", "## Required Next Actions", ""])
    for action in gate.get("required_next_actions", []):
        lines.append(f"- {action}")
    return "\n".join(lines) + "\n"


def _identity(row: Mapping) -> Dict:
    return {
        "dataset": row.get("experiment_dataset") or row.get("dataset"),
        "seed": row.get("experiment_seed") or row.get("seed"),
        "obs_ratio": row.get("experiment_obs_ratio") or row.get("obs_ratio"),
        "variant": row.get("ablation_variant"),
    }


def _finite(value) -> bool:
    return isinstance(value, (int, float)) and math.isfinite(float(value))


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Gate KT2 MINDS/FOREST/CasFT-inspired integrated-model evidence claims.")
    parser.add_argument("--small-matrix", default=str(DEFAULT_SMALL_MATRIX))
    parser.add_argument("--ablation", default=str(DEFAULT_ABLATION))
    parser.add_argument("--baseline-comparison", default=str(DEFAULT_BASELINE_COMPARISON))
    parser.add_argument("--min-datasets", type=int, default=3)
    parser.add_argument("--min-seeds", type=int, default=3)
    parser.add_argument("--min-obs-ratios", type=int, default=3)
    parser.add_argument("--out", default=str(BENCHMARK_DIR / "KT2_ORIGINAL_FUSION_GATE.json"))
    parser.add_argument("--out-md", default=str(BENCHMARK_DIR / "KT2_ORIGINAL_FUSION_GATE.md"))
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_arg_parser().parse_args(argv)
    gate = build_gate(
        small_matrix_path=Path(args.small_matrix),
        ablation_path=Path(args.ablation),
        baseline_comparison_path=Path(args.baseline_comparison),
        min_datasets=args.min_datasets,
        min_seeds=args.min_seeds,
        min_obs_ratios=args.min_obs_ratios,
    )
    write_outputs(gate, Path(args.out), Path(args.out_md) if args.out_md else None)
    print(json.dumps({"status": gate["status"], "out": args.out}, ensure_ascii=False))
    return 0 if gate["status"] == "evidence_passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
