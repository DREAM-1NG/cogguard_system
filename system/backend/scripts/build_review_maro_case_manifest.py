"""Build a shared, gold-free, stratified population manifest for MARO comparisons."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.review.maro_comparison import DATASET_AXIS_MAPPING, build_stratified_case_manifest  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case-dir", required=True)
    parser.add_argument("--eligible-predictions", required=True)
    parser.add_argument("--datasets", nargs="*", default=list(DATASET_AXIS_MAPPING))
    parser.add_argument("--max-per-dataset", type=int, default=100)
    parser.add_argument("--random-state", type=int, default=42)
    parser.add_argument("--output", required=True)
    parser.add_argument("--audit-output", required=True)
    args = parser.parse_args()
    case_dir = Path(args.case_dir)
    cases = []
    for dataset in args.datasets:
        cases.extend(load_jsonl(case_dir / f"{dataset}.jsonl"))
    eligible = load_jsonl(Path(args.eligible_predictions))
    non_test_rows = [
        row
        for row in eligible
        if str(row.get("protocol_split") or row.get("split") or "") != "test"
    ]
    if non_test_rows:
        raise SystemExit("MARO horizontal comparison requires a test population manifest.")
    manifest, audit = build_stratified_case_manifest(
        cases,
        eligible,
        max_per_dataset=int(args.max_per_dataset),
        random_state=int(args.random_state),
    )
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output).write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in manifest), encoding="utf-8")
    audit["schema"] = "review-maro-case-manifest-v1"
    audit["datasets_requested"] = list(args.datasets)
    audit["source_case_dir"] = str(case_dir)
    audit["eligible_predictions"] = str(args.eligible_predictions)
    Path(args.audit_output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.audit_output).write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(audit, ensure_ascii=False, indent=2))
    return 0


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    rows = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                row = json.loads(line)
                if isinstance(row, dict):
                    rows.append(row)
    return rows


if __name__ == "__main__":
    raise SystemExit(main())
