from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Dict, Optional, Sequence

from .experiment_audit import BENCHMARK_DIR, DEFAULT_PHEME_DIR, build_audit, write_audit
from .role_evidence_review import validate_review_file


DEFAULT_REVIEW_FILE = BENCHMARK_DIR / "kt1_role_evidence_validation" / "analysis" / "role_evidence_manual_review.csv"


def run_completion_gate(
    *,
    benchmark_dir: Path = BENCHMARK_DIR,
    review_file: Path = DEFAULT_REVIEW_FILE,
    pheme_dir: Optional[Path] = DEFAULT_PHEME_DIR,
    output_json: Optional[Path] = None,
    output_md: Optional[Path] = None,
) -> Dict:
    """Run the KT2 full-validation gate without weakening audit criteria."""

    audit = build_audit(benchmark_dir=benchmark_dir, pheme_dir=pheme_dir)
    review_template = review_file.parent / "role_evidence_manual_review_template.csv"
    review = validate_review_file(review_file, template_csv=review_template if review_template.exists() else None)
    open_checks = _open_checks(audit)
    result = {
        "schema": "cogguard.kt2.completion_gate.v1",
        "status": "passed" if audit["summary"]["full_validation_complete"] and review["ok"] else "incomplete",
        "full_validation_complete": bool(audit["summary"]["full_validation_complete"] and review["ok"]),
        "audit_status": audit["status"],
        "critical_open_sections": audit["summary"]["critical_open_sections"],
        "open_checks": open_checks,
        "manual_review_preflight": review,
        "required_next_action": _required_next_action(open_checks, review),
    }
    if output_json:
        output_json.parent.mkdir(parents=True, exist_ok=True)
        output_json.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    if output_md:
        output_md.parent.mkdir(parents=True, exist_ok=True)
        output_md.write_text(_gate_markdown(result), encoding="utf-8")
    return result


def _open_checks(audit: Dict) -> list[Dict]:
    rows = []
    for section in audit.get("sections", []):
        for check in section.get("checks", []):
            if check.get("status") != "passed":
                rows.append(
                    {
                        "section": section.get("id"),
                        "check": check.get("id"),
                        "status": check.get("status"),
                        "detail": check.get("detail"),
                    }
                )
    return rows


def _required_next_action(open_checks: list[Dict], review: Dict) -> str:
    if not open_checks and review.get("ok"):
        return "KT2 full validation gate passed."
    review_open = any(row.get("check") == "manual_review_records" for row in open_checks)
    if review_open or not review.get("ok"):
        detail = str(review.get("detail", ""))
        rows = int(review.get("rows") or 0)
        reviewed_rows = int(review.get("reviewed_rows") or 0)
        blank_rows = int(review.get("blank_rows") or 0)
        if "does not exist" in detail or rows == 0:
            return (
                "Run benchmark.role_evidence_review init to create role_evidence_manual_review.csv, "
                "then fill every sampled review_pass plus reviewer, evidence_match, confidence_1to5, and any required reason_if_fail "
                "from the prepared template/HTML packet. Rerun benchmark.role_evidence_review status, "
                "benchmark.role_evidence_review validate, benchmark.experiment_audit, and benchmark.completion_gate."
            )
        if blank_rows or reviewed_rows < rows:
            return (
                f"Fill all {rows} sampled rows in role_evidence_manual_review.csv "
                f"({reviewed_rows}/{rows} currently reviewed; {blank_rows} blank review_pass values), including reviewer, "
                "evidence_match, confidence_1to5, and any required reason_if_fail. Then run "
                "benchmark.role_evidence_review status, benchmark.role_evidence_review validate, "
                "benchmark.experiment_audit, and benchmark.completion_gate."
            )
        return (
            "Fix role_evidence_manual_review.csv according to the manual review validation detail, then run benchmark.role_evidence_review status, "
            "benchmark.role_evidence_review validate, benchmark.experiment_audit, and benchmark.completion_gate."
        )
    return "Resolve the remaining non-passed audit checks, then rerun benchmark.completion_gate."


def _gate_markdown(result: Dict) -> str:
    review = result["manual_review_preflight"]
    lines = [
        "# KT2 Completion Gate",
        "",
        "> 生成方式：由 `python -m benchmark.completion_gate` 生成；这是 KT2 full validation 的最终闸门。",
        "",
        f"- Status: `{result['status']}`",
        f"- Full validation complete: `{result['full_validation_complete']}`",
        f"- Audit status: `{result['audit_status']}`",
        f"- Critical open sections: `{', '.join(result['critical_open_sections']) or '-'}`",
        f"- Manual review preflight: `{review['ok']}`",
        f"- Manual review file: `{review.get('review_file', '-')}`",
        f"- Manual review rows: `{review.get('reviewed_rows', 0)}/{review.get('rows', 0)}`",
        f"- Manual review pass rate: `{review.get('pass_rate', 0.0)}`",
        "",
        "## Completion Rule",
        "",
        "- KT2 full validation passes only when the experiment audit has no critical open sections and the manual role-evidence review preflight passes.",
        "- `frontier_reproduction_small_run` evidence is necessary research evidence, but it is not equivalent to full validation or product readiness.",
        "",
        "## Open Checks",
        "",
    ]
    if result["open_checks"]:
        for row in result["open_checks"]:
            lines.append(f"- `{row['section']}` / `{row['check']}` / `{row['status']}`: {row['detail']}")
    else:
        lines.append("- none")
    lines.extend(["", "## Required Next Action", "", result["required_next_action"], ""])
    return "\n".join(lines)


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Run the KT2 full-validation completion gate.")
    parser.add_argument("--benchmark-dir", default=str(BENCHMARK_DIR))
    parser.add_argument("--review-file", default=str(DEFAULT_REVIEW_FILE))
    parser.add_argument("--pheme-dir", default=str(DEFAULT_PHEME_DIR))
    parser.add_argument("--output-json", default=str(BENCHMARK_DIR / "KT2_COMPLETION_GATE.json"))
    parser.add_argument("--output-md", default=str(BENCHMARK_DIR / "KT2_COMPLETION_GATE.md"))
    args = parser.parse_args(argv)

    pheme_dir = Path(args.pheme_dir) if args.pheme_dir else None
    result = run_completion_gate(
        benchmark_dir=Path(args.benchmark_dir),
        review_file=Path(args.review_file),
        pheme_dir=pheme_dir,
        output_json=Path(args.output_json) if args.output_json else None,
        output_md=Path(args.output_md) if args.output_md else None,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["full_validation_complete"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
