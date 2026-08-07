"""Build disjoint MARO-aligned Review experiment populations.

The protocol fixes three gold-free manifests while using labels only for
offline stratification:

* 100 test cases per dataset for the paired MultiAgent/Student pilot;
* 200 train cases per dataset for Teacher Silver generation;
* 500 validation tasks per semantic risk axis for policy refinement.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from app.core.review.maro_comparison import DATASET_AXIS_MAPPING  # noqa: E402
from app.core.review.trainable_post import NEGATIVE_LABEL, POSITIVE_LABEL, binary_label  # noqa: E402
from run_review_post_multiview_ablation import build_splits  # noqa: E402


DEFAULT_DATASETS = list(DATASET_AXIS_MAPPING)


def _identity(case: dict[str, Any], *, protocol_split: str) -> dict[str, str]:
    return {
        "case_id": str(case.get("case_id") or ""),
        "dataset": str(case.get("dataset") or ""),
        # Keep the source split for compatibility. Protocol split membership is
        # determined by build_splits and recorded in the audit artifact.
        "split": str(case.get("split") or ""),
        "protocol_split": protocol_split,
    }


def _hard_case_score(case: dict[str, Any]) -> int:
    views = case.get("views") or {}
    claim_context = case.get("claim_context") or {}
    available_media = sum(
        int(bool((views.get(name) or {}).get("available")))
        for name in ("meme", "img", "video")
    )
    missing_media_semantics = sum(
        int(
            bool((views.get(name) or {}).get("available"))
            and not any((views.get(name) or {}).get(field) for field in ("text", "caption", "ocr", "asr"))
        )
        for name in ("img", "video")
    )
    return (
        3 * int(bool(claim_context.get("available")))
        + 2 * missing_media_semantics
        + available_media
        + int(bool(case.get("thread") or case.get("propagation") or case.get("graph")))
    )


def _select_balanced(
    cases: list[dict[str, Any]],
    count: int,
    *,
    rng: np.random.Generator,
    hard_first: bool = False,
) -> list[dict[str, Any]]:
    by_label = {
        POSITIVE_LABEL: [case for case in cases if binary_label(case)],
        NEGATIVE_LABEL: [case for case in cases if not binary_label(case)],
    }
    for rows in by_label.values():
        rng.shuffle(rows)
        if hard_first:
            rows.sort(key=_hard_case_score, reverse=True)
    positive_target = min(len(by_label[POSITIVE_LABEL]), (count + 1) // 2)
    negative_target = min(len(by_label[NEGATIVE_LABEL]), count // 2)
    remaining = count - positive_target - negative_target
    for label in (POSITIVE_LABEL, NEGATIVE_LABEL):
        if remaining <= 0:
            break
        available = len(by_label[label]) - (positive_target if label == POSITIVE_LABEL else negative_target)
        added = min(remaining, available)
        if label == POSITIVE_LABEL:
            positive_target += added
        else:
            negative_target += added
        remaining -= added
    selected = [
        *by_label[POSITIVE_LABEL][:positive_target],
        *by_label[NEGATIVE_LABEL][:negative_target],
    ]
    selected.sort(key=lambda case: (str(case.get("dataset") or ""), str(case.get("case_id") or "")))
    return selected


def _population_audit(
    selected: list[dict[str, Any]],
    *,
    requested_count: int,
    protocol_split: str,
) -> dict[str, Any]:
    return {
        "protocol_split": protocol_split,
        "requested_count": requested_count,
        "selected_count": len(selected),
        "shortfall": max(0, requested_count - len(selected)),
        "dataset_counts": dict(Counter(str(case.get("dataset") or "") for case in selected)),
        "label_distribution": {
            POSITIVE_LABEL: sum(1 for case in selected if binary_label(case)),
            NEGATIVE_LABEL: sum(1 for case in selected if not binary_label(case)),
        },
        "axis_counts": dict(Counter(DATASET_AXIS_MAPPING[str(case.get("dataset"))] for case in selected)),
    }


def build_experiment_protocol(
    cases_by_dataset: dict[str, list[dict[str, Any]]],
    *,
    test_per_dataset: int = 100,
    teacher_per_dataset: int = 200,
    validation_tasks_per_axis: int = 500,
    random_state: int = 42,
) -> tuple[dict[str, list[dict[str, str]]], dict[str, Any]]:
    rng = np.random.default_rng(random_state)
    split_cases: dict[str, dict[str, list[dict[str, Any]]]] = {}
    split_policies: dict[str, str] = {}
    for dataset, cases in cases_by_dataset.items():
        splits, policy = build_splits(dataset, cases, random_state)
        split_cases[dataset] = splits
        split_policies[dataset] = policy

    test_selected: list[dict[str, Any]] = []
    teacher_selected: list[dict[str, Any]] = []
    for dataset in DEFAULT_DATASETS:
        splits = split_cases.get(dataset, {})
        test_selected.extend(_select_balanced(splits.get("test", []), test_per_dataset, rng=rng))
        teacher_selected.extend(
            _select_balanced(splits.get("train", []), teacher_per_dataset, rng=rng, hard_first=True)
        )

    validation_selected: list[dict[str, Any]] = []
    for axis in dict.fromkeys(DATASET_AXIS_MAPPING.values()):
        candidates = [
            case
            for dataset, mapped_axis in DATASET_AXIS_MAPPING.items()
            if mapped_axis == axis
            for case in split_cases.get(dataset, {}).get("validation", [])
        ]
        validation_selected.extend(
            _select_balanced(candidates, validation_tasks_per_axis, rng=rng)
        )

    selected_cases = {
        "test": test_selected,
        "teacher": teacher_selected,
        "rule_validation": validation_selected,
    }
    protocol_splits = {"test": "test", "teacher": "train", "rule_validation": "validation"}
    manifests = {
        name: [_identity(case, protocol_split=protocol_splits[name]) for case in rows]
        for name, rows in selected_cases.items()
    }
    identity_sets = {
        name: {row["case_id"] for row in rows}
        for name, rows in manifests.items()
    }
    overlaps = {
        f"{left}_vs_{right}": sorted(identity_sets[left] & identity_sets[right])
        for index, left in enumerate(identity_sets)
        for right in list(identity_sets)[index + 1 :]
    }
    audit = {
        "random_state": random_state,
        "split_policies": split_policies,
        "populations": {
            "test": _population_audit(
                test_selected,
                requested_count=test_per_dataset * len(DEFAULT_DATASETS),
                protocol_split="test",
            ),
            "teacher": _population_audit(
                teacher_selected,
                requested_count=teacher_per_dataset * len(DEFAULT_DATASETS),
                protocol_split="train",
            ),
            "rule_validation": _population_audit(
                validation_selected,
                requested_count=validation_tasks_per_axis * len(set(DATASET_AXIS_MAPPING.values())),
                protocol_split="validation",
            ),
        },
        "integrity": {
            "pairwise_overlap_count": sum(len(case_ids) for case_ids in overlaps.values()),
            "pairwise_overlaps": overlaps,
            "gold_exported": False,
        },
    }
    return manifests, audit


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"invalid JSONL at {path}:{line_number}: {exc}") from exc
            if isinstance(row, dict):
                rows.append(row)
    return rows


def write_experiment_protocol(
    *,
    case_dir: Path,
    output_dir: Path,
    datasets: list[str],
    test_per_dataset: int,
    teacher_per_dataset: int,
    validation_tasks_per_axis: int,
    random_state: int,
    allow_shortfall: bool = False,
) -> dict[str, Any]:
    cases_by_dataset = {
        dataset: load_jsonl(case_dir / f"{dataset}.jsonl")
        for dataset in datasets
    }
    manifests, audit = build_experiment_protocol(
        cases_by_dataset,
        test_per_dataset=test_per_dataset,
        teacher_per_dataset=teacher_per_dataset,
        validation_tasks_per_axis=validation_tasks_per_axis,
        random_state=random_state,
    )
    audit.update(
        {
            "schema": "review-maro-experiment-protocol-v1",
            "case_dir": str(case_dir),
            "datasets": list(datasets),
            "requested_scale": {
                "test_per_dataset": test_per_dataset,
                "teacher_per_dataset": teacher_per_dataset,
                "validation_tasks_per_axis": validation_tasks_per_axis,
            },
        }
    )
    shortfalls = {
        name: population["shortfall"]
        for name, population in audit["populations"].items()
        if population["shortfall"]
    }
    if audit["integrity"]["pairwise_overlap_count"]:
        raise ValueError("experiment populations overlap")
    if shortfalls and not allow_shortfall:
        raise ValueError(f"experiment population shortfall: {shortfalls}")
    output_dir.mkdir(parents=True, exist_ok=True)
    paths = {
        "test": output_dir / "test_manifest.jsonl",
        "teacher": output_dir / "teacher_silver_manifest.jsonl",
        "rule_validation": output_dir / "rule_validation_manifest.jsonl",
    }
    for name, path in paths.items():
        path.write_text(
            "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in manifests[name]),
            encoding="utf-8",
        )
    audit["artifacts"] = {name: str(path) for name, path in paths.items()}
    (output_dir / "protocol.audit.json").write_text(
        json.dumps(audit, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return audit


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case-dir", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--datasets", nargs="*", default=DEFAULT_DATASETS)
    parser.add_argument("--test-per-dataset", type=int, default=100)
    parser.add_argument("--teacher-per-dataset", type=int, default=200)
    parser.add_argument("--validation-tasks-per-axis", type=int, default=500)
    parser.add_argument("--random-state", type=int, default=42)
    parser.add_argument("--allow-shortfall", action="store_true")
    args = parser.parse_args()
    if list(args.datasets) != DEFAULT_DATASETS:
        raise SystemExit(f"protocol requires exactly: {', '.join(DEFAULT_DATASETS)}")
    try:
        audit = write_experiment_protocol(
            case_dir=Path(args.case_dir),
            output_dir=Path(args.output_dir),
            datasets=list(args.datasets),
            test_per_dataset=int(args.test_per_dataset),
            teacher_per_dataset=int(args.teacher_per_dataset),
            validation_tasks_per_axis=int(args.validation_tasks_per_axis),
            random_state=int(args.random_state),
            allow_shortfall=bool(args.allow_shortfall),
        )
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
    print(json.dumps(audit, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
