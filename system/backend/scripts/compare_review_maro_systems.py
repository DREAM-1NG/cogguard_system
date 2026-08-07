"""Compare Review MultiAgent and ReviewStudent under one MARO-style label protocol."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.review.maro_comparison import DATASET_AXIS_MAPPING, build_maro_horizontal_comparison  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case-dir", required=True)
    parser.add_argument(
        "--multi-agent-path",
        required=True,
        help="Agent experiment root, combined JSONL, or one agent_predictions.jsonl file.",
    )
    parser.add_argument("--student-predictions", required=True)
    parser.add_argument(
        "--population-manifest",
        default="",
        help="Optional JSONL fixing the exact case_id/dataset/split evaluation population.",
    )
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    case_dir = Path(args.case_dir)
    agent_path = Path(args.multi_agent_path)
    student_path = Path(args.student_predictions)
    manifest_path = Path(args.population_manifest) if str(args.population_manifest).strip() else None
    output_path = Path(args.output)

    student_rows = load_jsonl(student_path)
    agent_rows = load_agent_rows(agent_path)
    population_rows = load_jsonl(manifest_path) if manifest_path else student_rows
    invalid_population_roles = [
        str(row.get("case_id") or "")
        for row in population_rows
        if row.get("protocol_split") is not None and str(row.get("protocol_split") or "") != "test"
    ]
    if invalid_population_roles:
        raise SystemExit(
            "MARO horizontal comparison population must declare protocol_split=test: "
            + ", ".join(invalid_population_roles[:10])
        )
    cases, missing_cases, identity_errors = load_population_cases(case_dir, population_rows)
    report = build_maro_horizontal_comparison(cases, agent_rows, student_rows)
    report["inputs"] = {
        "case_dir": str(case_dir),
        "multi_agent_path": str(agent_path),
        "student_predictions": str(student_path),
        "population_manifest": str(manifest_path or ""),
        "source_case_count": len(cases),
        "multi_agent_row_count": len(agent_rows),
        "student_row_count": len(student_rows),
        "missing_source_case_ids": missing_cases,
        "population_identity_errors": identity_errors,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"population": report["population"], "paired": report["paired"]}, ensure_ascii=False, indent=2))
    print(f"wrote {output_path}")
    return 1 if missing_cases or identity_errors else 0


def load_population_cases(
    case_dir: Path,
    population_rows: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[str], list[str]]:
    dataset_cases: dict[str, dict[str, dict[str, Any]]] = {}
    for dataset in DATASET_AXIS_MAPPING:
        path = resolve_dataset_case_path(case_dir, dataset)
        dataset_cases[dataset.lower()] = {
            str(case.get("case_id") or ""): case
            for case in load_jsonl(path)
            if str(case.get("case_id") or "")
        }
    selected: list[dict[str, Any]] = []
    missing: list[str] = []
    errors: list[str] = []
    seen: set[str] = set()
    for row in population_rows:
        case_id = str(row.get("case_id") or "").strip()
        dataset = str(row.get("dataset") or "").strip()
        split = str(row.get("split") or "").strip()
        if not case_id or dataset.lower() not in dataset_cases or case_id in seen:
            continue
        seen.add(case_id)
        case = dataset_cases[dataset.lower()].get(case_id)
        if case is None:
            missing.append(case_id)
            continue
        if str(case.get("split") or "") != split:
            errors.append(
                f"source_identity_mismatch:{case_id}:manifest={dataset}/{split}:"
                f"source={case.get('dataset')}/{case.get('split')}"
            )
            continue
        selected.append(case)
    return selected, missing, errors


def load_agent_rows(path: Path) -> list[dict[str, Any]]:
    if path.is_file():
        return load_jsonl(path)
    rows: list[dict[str, Any]] = []
    for dataset in DATASET_AXIS_MAPPING:
        dataset_dir = safe_name(dataset)
        candidates = [
            path / dataset_dir / "agent_predictions.jsonl",
            path / dataset / "agent_predictions.jsonl",
        ]
        prediction_path = next((candidate for candidate in candidates if candidate.is_file()), None)
        if prediction_path:
            rows.extend(load_jsonl(prediction_path))
    return rows


def resolve_dataset_case_path(case_dir: Path, dataset: str) -> Path:
    candidates = [case_dir / f"{dataset}.jsonl", case_dir / f"{safe_name(dataset)}.jsonl"]
    return next((path for path in candidates if path.is_file()), candidates[0])


def load_jsonl(path: Path | None) -> list[dict[str, Any]]:
    if path is None or not path.is_file():
        return []
    rows = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise SystemExit(f"Invalid JSONL at {path}:{line_number}: {exc}") from exc
            if isinstance(row, dict):
                rows.append(row)
    return rows


def safe_name(value: str) -> str:
    return "".join(ch.lower() if ch.isalnum() else "_" for ch in value).strip("_")


if __name__ == "__main__":
    raise SystemExit(main())
