"""Build a gold-free hard-case manifest from Student prediction records.

The command only ranks and samples existing prediction JSONL rows. It never
calls a Teacher provider, reads gold labels, or writes training data.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from typing import Any, Iterable


AXIS_KEYS = {
    "interpersonal_harm": ("interpersonal_aggression", "attack_hate_offense"),
    "claim_deception": ("ideological_deception", "misinfo_claim_risk"),
}


def _as_float(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _prediction_value(student: dict[str, Any], keys: Iterable[str]) -> float | None:
    for key in keys:
        value = student.get(key)
        if isinstance(value, dict):
            value = value.get("probability", value.get("score"))
        number = _as_float(value)
        if number is not None:
            return max(0.0, min(1.0, number))
    return None


def _binary_entropy(probability: float) -> float:
    epsilon = 1e-8
    p = min(1.0 - epsilon, max(epsilon, probability))
    return float(-(p * math.log(p) + (1.0 - p) * math.log(1.0 - p)) / math.log(2.0))


def _conflict_signal(row: dict[str, Any]) -> float:
    for container in (row, row.get("audit"), row.get("evidence_bundle"), row.get("review_queue")):
        if not isinstance(container, dict):
            continue
        if container.get("conflict_detected") is True or container.get("relation") == "conflicting":
            return 1.0
        if container.get("evidence_status") in {"conflicting", "insufficient"}:
            return 1.0
    return 0.0


def score_hard_case(row: dict[str, Any]) -> dict[str, Any]:
    """Return auditable selection signals without consulting gold labels."""

    student = row.get("student") if isinstance(row.get("student"), dict) else row
    axis_scores: dict[str, float] = {}
    entropy_scores: list[float] = []
    for task, keys in AXIS_KEYS.items():
        probability = _prediction_value(student, keys)
        if probability is None:
            continue
        entropy = _binary_entropy(probability)
        axis_scores[task] = round(probability, 6)
        entropy_scores.append(entropy)
    uncertainty = max(entropy_scores, default=0.0)
    explicit_ood = _as_float(row.get("ood_score")) or 0.0
    conflict = _conflict_signal(row)
    score = min(1.0, 0.6 * uncertainty + 0.25 * conflict + 0.15 * max(0.0, min(1.0, explicit_ood)))
    dataset = str(row.get("dataset") or student.get("dataset") or "unknown").strip() or "unknown"
    task = str(row.get("task") or row.get("risk_axis") or "unknown").strip() or "unknown"
    return {
        "case_id": str(row.get("case_id") or row.get("id") or "").strip(),
        "dataset": dataset,
        "task": task,
        "selection_score": round(score, 6),
        "uncertainty": round(uncertainty, 6),
        "evidence_conflict": bool(conflict),
        "ood_score": round(max(0.0, min(1.0, explicit_ood)), 6),
        "axis_probabilities": axis_scores,
    }


def select_hard_cases(rows: list[dict[str, Any]], *, max_cases: int = 0) -> list[dict[str, Any]]:
    candidates = [score_hard_case(row) for row in rows if isinstance(row, dict)]
    candidates = [row for row in candidates if row["case_id"]]
    groups: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for candidate in candidates:
        groups.setdefault((candidate["dataset"], candidate["task"]), []).append(candidate)
    for values in groups.values():
        values.sort(key=lambda item: (-item["selection_score"], item["case_id"]))

    selected: list[dict[str, Any]] = []
    while groups and (max_cases <= 0 or len(selected) < max_cases):
        progressed = False
        for group in sorted(list(groups)):
            values = groups[group]
            if not values:
                groups.pop(group, None)
                continue
            selected.append(values.pop(0))
            progressed = True
            if not values:
                groups.pop(group, None)
            if max_cases > 0 and len(selected) >= max_cases:
                break
        if not progressed:
            break
    return selected


def build_manifest(rows: list[dict[str, Any]], *, source: str, max_cases: int = 0) -> dict[str, Any]:
    cases = select_hard_cases(rows, max_cases=max_cases)
    payload = json.dumps(cases, ensure_ascii=False, sort_keys=True).encode("utf-8")
    return {
        "schema_version": "review-hard-case-pool-v1",
        "source_predictions": source,
        "gold_labels_used": False,
        "teacher_called": False,
        "selection_policy": {
            "signals": ["entropy", "evidence_conflict", "ood_score"],
            "stratification": ["dataset", "task"],
            "max_cases": max_cases,
        },
        "case_count": len(cases),
        "case_manifest_sha256": hashlib.sha256(payload).hexdigest(),
        "cases": cases,
    }


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                value = json.loads(line)
                if isinstance(value, dict):
                    rows.append(value)
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--predictions", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--max-cases", type=int, default=0)
    args = parser.parse_args()
    manifest = build_manifest(
        _read_jsonl(args.predictions),
        source=str(args.predictions),
        max_cases=max(0, int(args.max_cases)),
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
