from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence

from propagation.analysis import analyze_events
from propagation.loaders import load_dataset, make_synthetic_events
from propagation.protocol import load_coordination_scope


USER_KEYS = ("user_id", "account_id", "uid", "user", "member_id")
GROUP_KEYS = ("group_id", "cluster_id", "coord_group_id", "community_id")
PREDICTION_KEYS = ("predicted_label", "prediction", "is_coordinated", "coordination_label")
SCORE_KEYS = ("node_score", "score", "probability", "coordination_score")
POSITIVE_LABELS = {"1", "true", "yes", "y", "coordinated", "positive"}


def convert_kt1_predictions(
    kt1_predictions: str | Path,
    output_dir: str | Path,
    *,
    min_score: Optional[float] = None,
) -> Dict[str, Any]:
    """Convert KT1 user-level coordination predictions into a KT2 scope file.

    The adapter is intentionally conservative: it only emits users whose
    prediction label is positive, or whose score passes an explicit threshold
    when no prediction label is present.
    """

    source = Path(kt1_predictions)
    records = _coordination_records(_read_records(source), min_score=min_score)
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    users = sorted({record["user_id"] for record in records})
    grouped: Dict[str, List[str]] = {}
    for record in records:
        group_id = record.get("group_id")
        if group_id:
            grouped.setdefault(str(group_id), []).append(record["user_id"])

    payload = {
        "schema": "cogguard.kt2.kt1_coordination_scope.v1",
        "source": str(source),
        "selection_rule": {
            "positive_labels": sorted(POSITIVE_LABELS),
            "min_score": min_score,
            "note": "Rows are selected from KT1 user-level predictions; event-level metrics are not treated as coordinated users.",
        },
        "users": users,
        "groups": [{"group_id": group_id, "users": sorted(set(group_users))} for group_id, group_users in sorted(grouped.items())],
        "records": records,
    }

    json_path = out / "kt1_coordination_scope.json"
    csv_path = out / "kt1_coordination_scope.csv"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    _write_records_csv(records, csv_path)

    return {
        "schema": "cogguard.kt2.kt1_coordination_adapter.v1",
        "source": str(source),
        "coordination_file": str(json_path),
        "coordination_csv": str(csv_path),
        "selected_user_count": len(users),
        "selected_group_count": len(grouped),
        "records": len(records),
    }


def run_kt1_role_evidence_validation(
    kt1_predictions: str | Path,
    output_dir: str | Path,
    *,
    dataset: str = "synthetic",
    data_dir: Optional[str] = None,
    max_events: Optional[int] = 4,
    min_score: Optional[float] = None,
) -> Dict[str, Any]:
    """Run a minimal KT1 -> KT2 role-evidence validation."""

    out = Path(output_dir)
    adapter = convert_kt1_predictions(kt1_predictions, out, min_score=min_score)
    coordination = load_coordination_scope(adapter["coordination_file"])
    events = _load_validation_events(dataset, data_dir, max_events)
    analysis_dir = out / "analysis"
    summary = analyze_events(events, str(analysis_dir), coordination=coordination)

    role_evidence_csv = analysis_dir / "role_evidence.csv"
    quality_path = analysis_dir / "role_evidence_quality.json"
    quality = json.loads(quality_path.read_text(encoding="utf-8")) if quality_path.exists() else {}
    role_rows = _count_csv_rows(role_evidence_csv)
    status = "ok" if adapter["selected_user_count"] > 0 and role_rows > 0 else "missing_evidence"
    validation = {
        "schema": "cogguard.kt2.kt1_role_evidence_validation.v1",
        "status": status,
        "source": str(kt1_predictions),
        "dataset": dataset,
        "data_dir": data_dir,
        "event_count": len(events),
        "coordination_file": adapter["coordination_file"],
        "coordination_csv": adapter["coordination_csv"],
        "selected_user_count": adapter["selected_user_count"],
        "role_evidence_csv": str(role_evidence_csv),
        "role_evidence_quality_json": str(quality_path),
        "role_evidence_rows": role_rows,
        "role_evidence_quality": quality,
        "analysis_summary": summary,
        "note": (
            "This validates KT1 user-level coordination output can drive KT2 observed-graph role evidence. "
            "It is not a substitute for PHEME/full cross-event validation."
        ),
    }
    (out / "kt1_role_evidence_validation.json").write_text(json.dumps(validation, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    return validation


def run_pheme_role_evidence_sample(
    pheme_dir: str | Path,
    output_dir: str | Path,
    *,
    max_events: Optional[int] = 5,
    users_per_event: int = 2,
) -> Dict[str, Any]:
    """Validate the role-evidence path on real PHEME timelines.

    This builds a coordination scope from observed PHEME users so the analysis
    pipeline can be exercised on real thread structure. It is not a KT1
    prediction result and must not be reported as one.
    """

    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    events = load_dataset("pheme", str(pheme_dir), max_events=max_events)
    records = _observed_user_records(events, users_per_event=users_per_event)
    scope_payload = {
        "schema": "cogguard.kt2.pheme_observed_coordination_scope.v1",
        "source": "pheme_observed_sample",
        "data_dir": str(pheme_dir),
        "selection_rule": {
            "users_per_event": users_per_event,
            "note": "Observed PHEME users are selected only to validate KT2 role-evidence analysis on real timelines; this is not KT1 model output.",
        },
        "users": sorted({record["user_id"] for record in records}),
        "groups": _groups_from_records(records),
        "records": records,
    }
    coordination_file = out / "pheme_observed_coordination_scope.json"
    coordination_csv = out / "pheme_observed_coordination_scope.csv"
    coordination_file.write_text(json.dumps(scope_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    _write_records_csv(records, coordination_csv)

    analysis_dir = out / "analysis"
    summary = analyze_events(events, str(analysis_dir), coordination=load_coordination_scope(coordination_file))
    role_evidence_csv = analysis_dir / "role_evidence.csv"
    quality_path = analysis_dir / "role_evidence_quality.json"
    quality = json.loads(quality_path.read_text(encoding="utf-8")) if quality_path.exists() else {}
    role_rows = _count_csv_rows(role_evidence_csv)
    validation = {
        "schema": "cogguard.kt2.pheme_role_evidence_sample.v1",
        "status": "ok" if records and role_rows > 0 else "missing_evidence",
        "source": "pheme_observed_sample",
        "data_dir": str(pheme_dir),
        "event_count": len(events),
        "selected_user_count": len(scope_payload["users"]),
        "selected_group_count": len(scope_payload["groups"]),
        "coordination_file": str(coordination_file),
        "coordination_csv": str(coordination_csv),
        "role_evidence_csv": str(role_evidence_csv),
        "role_evidence_quality_json": str(quality_path),
        "role_evidence_rows": role_rows,
        "role_evidence_quality": quality,
        "analysis_summary": summary,
        "note": "PHEME observed-user scope validates real timeline evidence paths; it is not KT1 coordination prediction output.",
    }
    (out / "pheme_role_evidence_sample.json").write_text(json.dumps(validation, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    return validation


def _load_validation_events(dataset: str, data_dir: Optional[str], max_events: Optional[int]):
    if dataset == "synthetic":
        events = make_synthetic_events()
        if max_events is not None:
            return events[:max_events]
        return events
    return load_dataset(dataset, data_dir, max_events=max_events)


def _observed_user_records(events: Sequence[Any], *, users_per_event: int) -> List[Dict[str, Any]]:
    records: List[Dict[str, Any]] = []
    for event in events:
        users = _event_user_scores(event)
        for rank, (user_id, score) in enumerate(users[: max(users_per_event, 0)], start=1):
            records.append(
                {
                    "user_id": str(user_id),
                    "group_id": f"pheme_{event.event_id}",
                    "predicted_label": "observed_sample",
                    "node_score": score,
                    "source": "pheme_observed_sample",
                    "event_id": event.event_id,
                    "rank": rank,
                }
            )
    return records


def _event_user_scores(event: Any) -> List[tuple[str, int]]:
    counts: Dict[str, int] = {}
    first_seen: Dict[str, Any] = {}
    for node in event.nodes.values():
        user_id = str(node.user_id)
        counts[user_id] = counts.get(user_id, 0) + 1
        if user_id not in first_seen or (node.timestamp is not None and (first_seen[user_id] is None or node.timestamp < first_seen[user_id])):
            first_seen[user_id] = node.timestamp
    return sorted(counts.items(), key=lambda item: (-item[1], str(first_seen.get(item[0]) or ""), item[0]))


def _groups_from_records(records: Iterable[Mapping[str, Any]]) -> List[Dict[str, Any]]:
    grouped: Dict[str, List[str]] = {}
    for record in records:
        group_id = record.get("group_id")
        if group_id:
            grouped.setdefault(str(group_id), []).append(str(record["user_id"]))
    return [{"group_id": group_id, "users": sorted(set(users))} for group_id, users in sorted(grouped.items())]


def _coordination_records(rows: Iterable[Mapping[str, Any]], *, min_score: Optional[float]) -> List[Dict[str, Any]]:
    records: List[Dict[str, Any]] = []
    for row in rows:
        user_id = _first_value(row, USER_KEYS)
        if not user_id:
            continue
        prediction = _first_value(row, PREDICTION_KEYS)
        score = _parse_float(_first_value(row, SCORE_KEYS))
        if not _is_positive(prediction, score, min_score):
            continue
        group_id = _first_value(row, GROUP_KEYS)
        records.append(
            {
                "user_id": str(user_id),
                "group_id": str(group_id) if group_id is not None and str(group_id) != "" else None,
                "predicted_label": prediction,
                "node_score": score,
                "source": "kt1_predictions",
            }
        )
    return records


def _is_positive(prediction: Any, score: Optional[float], min_score: Optional[float]) -> bool:
    if prediction is not None and str(prediction).strip() != "":
        positive = str(prediction).strip().lower() in POSITIVE_LABELS
        return positive and (min_score is None or (score is not None and score >= min_score))
    if min_score is not None and score is not None:
        return score >= min_score
    return False


def _read_records(path: Path) -> List[Mapping[str, Any]]:
    if not path.exists():
        raise FileNotFoundError(f"KT1 predictions file not found: {path}")
    if path.suffix.lower() == ".json":
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, Mapping):
            data = data.get("records") or data.get("items") or []
        if not isinstance(data, list):
            raise ValueError(f"Unsupported KT1 JSON shape: {path}")
        return [item for item in data if isinstance(item, Mapping)]
    delimiter = "\t" if path.suffix.lower() in {".tsv", ".tab"} else ","
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle, delimiter=delimiter))


def _write_records_csv(records: List[Mapping[str, Any]], path: Path) -> None:
    fields = ["user_id", "group_id", "predicted_label", "node_score", "source", "event_id", "rank"]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(records)


def _first_value(row: Mapping[str, Any], keys: Iterable[str]) -> Optional[Any]:
    for key in keys:
        value = row.get(key)
        if value is not None and str(value).strip() != "":
            return value
    return None


def _parse_float(value: Any) -> Optional[float]:
    if value is None or str(value).strip() == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _count_csv_rows(path: Path) -> int:
    if not path.exists():
        return 0
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return sum(1 for _ in csv.DictReader(handle))


def main() -> None:
    parser = argparse.ArgumentParser(description="Convert KT1 coordination predictions and validate KT2 role evidence.")
    parser.add_argument("--kt1_predictions")
    parser.add_argument("--output", required=True)
    parser.add_argument("--dataset", default="synthetic")
    parser.add_argument("--data-dir", default=None)
    parser.add_argument("--max-events", type=int, default=4)
    parser.add_argument("--min-score", type=float, default=None)
    parser.add_argument("--pheme-observed-sample", action="store_true")
    parser.add_argument("--users-per-event", type=int, default=2)
    args = parser.parse_args()
    if args.pheme_observed_sample:
        if not args.data_dir:
            raise SystemExit("--data-dir is required with --pheme-observed-sample")
        result = run_pheme_role_evidence_sample(args.data_dir, args.output, max_events=args.max_events, users_per_event=args.users_per_event)
    else:
        if not args.kt1_predictions:
            raise SystemExit("--kt1_predictions is required unless --pheme-observed-sample is set")
        result = run_kt1_role_evidence_validation(
            args.kt1_predictions,
            args.output,
            dataset=args.dataset,
            data_dir=args.data_dir,
            max_events=args.max_events,
            min_score=args.min_score,
        )
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
