"""Summarize Review post-level full-validation readiness.

This script is deliberately strict. It does not run models or download data; it
audits whether the current audit report, conversion manifest, and evaluation
suite are strong enough to support a full-validation claim.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


P0_DATASETS = {
    "MultiOFF",
    "HateXplain",
    "Jigsaw Toxicity",
    "Hateful Memes",
    "MAMI",
    "MMHS150K",
    "PHEME",
    "RumourEval 2019",
    "MOCHEG",
    "FACTIFY3M",
    "FakeSV",
    "mcfend",
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--audit", default=r"G:\CISCN\.tmp\review_post_dataset_audit_v2.json")
    parser.add_argument("--manifest", default=r"G:\CISCN\.tmp\review_post_cases_full\manifest.json")
    parser.add_argument("--suite", default=r"G:\CISCN\.tmp\review_post_multiview_ablation_full_registry\report.json")
    parser.add_argument("--output", default=r"G:\CISCN\.tmp\review_full_validation_gate_report.json")
    args = parser.parse_args()

    audit = read_json(Path(args.audit))
    manifest = read_json(Path(args.manifest))
    suite = read_json(Path(args.suite))
    report = build_gate_report(audit, manifest, suite)

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report["summary"], ensure_ascii=False, indent=2))
    print(f"wrote {output}")
    return 0


def build_gate_report(
    audit: dict[str, Any],
    manifest: dict[str, Any],
    suite: dict[str, Any],
) -> dict[str, Any]:
    audit_summary = audit.get("summary") or {}
    manifest_datasets = manifest.get("datasets") or {}
    suite_datasets = suite.get("datasets") or {}

    dataset_rows = {}
    blockers = []
    for dataset in sorted(P0_DATASETS):
        audit_item = (audit.get("benchmarks") or {}).get(dataset) or {}
        manifest_item = manifest_datasets.get(dataset) or {}
        suite_item = suite_datasets.get(dataset) or {}
        suite_summary = suite_item.get("summary") or {}
        best = suite_summary.get("best_test_macro_f1")
        row = {
            "dataset": dataset,
            "audit_status": audit_item.get("status", "missing"),
            "conversion_status": manifest_item.get("status", "missing"),
            "case_count": int(manifest_item.get("case_count", 0) or 0),
            "suite_status": suite_summary.get("status", "skipped"),
            "best_test_macro_f1": best,
            "validation_coverage": suite_item.get("validation_coverage") or {},
            "missing_required_files": manifest_item.get("missing") or audit_item.get("missing_required_files") or [],
            "skip_reason": suite_summary.get("skip_reason") or (suite.get("summary") or {}).get("skipped_datasets", {}).get(dataset, ""),
            "acquisition": (audit_item.get("acquisition") or {}),
        }
        row["passes_dataset_gate"] = dataset_passes(row)
        dataset_rows[dataset] = row
        if not row["passes_dataset_gate"]:
            blockers.append(dataset_blocker(row))

    p0_passed = sorted(name for name, row in dataset_rows.items() if row["passes_dataset_gate"])
    p0_failed = sorted(name for name, row in dataset_rows.items() if not row["passes_dataset_gate"])
    overall_pass = not p0_failed
    return {
        "schema": "review-full-validation-gate-v1",
        "inputs": {
            "audit_schema": audit.get("schema"),
            "manifest_schema": manifest.get("schema"),
            "suite_schema": suite.get("schema"),
        },
        "summary": {
            "overall_pass": overall_pass,
            "p0_dataset_count": len(P0_DATASETS),
            "p0_passed": p0_passed,
            "p0_failed": p0_failed,
            "evaluated_datasets": (suite.get("summary") or {}).get("evaluated_datasets", []),
            "p0_not_ready_for_full_validation": audit_summary.get("p0_not_ready_for_full_validation", []),
            "claim": (
                "full_validation_complete"
                if overall_pass
                else "full_validation_not_complete"
            ),
            "note": (
                "Pass requires every P0 dataset to be ready/converted/evaluated with a test metric "
                "and full expected view coverage. Partial, present_unverified, missing, skipped, "
                "metadata-proxy-only, text-only-for-multimodal, or claim-proxy-only states fail the gate."
            ),
        },
        "datasets": dataset_rows,
        "blockers": blockers,
    }


def dataset_passes(row: dict[str, Any]) -> bool:
    if row["audit_status"] != "ready":
        return False
    if row["conversion_status"] != "converted":
        return False
    if row["case_count"] <= 0:
        return False
    if row["suite_status"] != "evaluated":
        return False
    best = row.get("best_test_macro_f1")
    if not (isinstance(best, dict) and best.get("macro_f1") is not None):
        return False
    coverage = row.get("validation_coverage") or {}
    return coverage.get("full_expected_view_coverage") is True


def dataset_blocker(row: dict[str, Any]) -> dict[str, Any]:
    reasons = []
    if row["audit_status"] != "ready":
        reasons.append(f"audit_status={row['audit_status']}")
    if row["conversion_status"] != "converted":
        reasons.append(f"conversion_status={row['conversion_status']}")
    if row["case_count"] <= 0:
        reasons.append("case_count=0")
    if row["suite_status"] != "evaluated":
        reasons.append(f"suite_status={row['suite_status']}")
    if not (isinstance(row.get("best_test_macro_f1"), dict) and row["best_test_macro_f1"].get("macro_f1") is not None):
        reasons.append("missing_test_macro_f1")
    coverage = row.get("validation_coverage") or {}
    if coverage.get("full_expected_view_coverage") is not True:
        missing = coverage.get("missing_requirements") or ["missing_validation_coverage_matrix"]
        reasons.extend(missing)
    action = (row.get("acquisition") or {}).get("action", "")
    return {
        "dataset": row["dataset"],
        "reasons": reasons,
        "required_action": action or "inspect_dataset_state",
        "dataset_url": (row.get("acquisition") or {}).get("dataset_url", ""),
        "repository_url": (row.get("acquisition") or {}).get("repository_url", ""),
        "missing_required_files": row.get("missing_required_files") or [],
        "skip_reason": row.get("skip_reason", ""),
    }


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    raise SystemExit(main())
