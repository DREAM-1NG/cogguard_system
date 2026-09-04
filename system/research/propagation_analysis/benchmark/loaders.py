"""Public benchmark fixture loaders for PropagationAnalysis.

The loaders normalize small local fixtures and benchmark exports into a common
cascade shape. They do not download datasets or fabricate labels.
"""

from __future__ import annotations

import csv
import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping


SUPPORTED_DATASETS = frozenset({"twitter", "tgb", "douban", "memetracker", "casflow", "casft"})


def load_public_cascade_fixture(
    path: str | Path,
    *,
    dataset: str,
    limit: int | None = None,
) -> dict[str, Any]:
    """Load a local public-dataset fixture into normalized cascades."""

    dataset_name = _normalize_dataset(dataset)
    if dataset_name not in SUPPORTED_DATASETS:
        return {
            "status": "unsupported_dataset",
            "dataset": dataset_name,
            "supported_datasets": sorted(SUPPORTED_DATASETS),
            "cascades": [],
        }

    source = Path(path)
    if not source.exists():
        return {
            "status": "missing_data",
            "dataset": dataset_name,
            "source": str(source),
            "cascades": [],
            "note": f"PropagationAnalysis public dataset fixture not found: {source}",
        }

    records = _load_records(source)
    if limit is not None:
        records = records[: max(0, int(limit))]
    cascades = _records_to_cascades(records, dataset=dataset_name)
    return {
        "status": "ok" if cascades else "data_insufficient",
        "dataset": dataset_name,
        "source": str(source),
        "record_count": len(records),
        "cascade_count": len(cascades),
        "cascades": cascades,
        "schema": "cogguard.propagation_analysis.public_cascade_fixture.v1",
    }


def _load_records(path: Path) -> list[dict[str, Any]]:
    suffix = path.suffix.lower()
    if suffix == ".jsonl":
        records = []
        for line in path.read_text(encoding="utf-8").splitlines():
            text = line.strip()
            if text:
                records.append(json.loads(text))
        return [record for record in records if isinstance(record, dict)]
    if suffix == ".json":
        payload = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(payload, list):
            return [record for record in payload if isinstance(record, dict)]
        if isinstance(payload, dict):
            rows = payload.get("rows") or payload.get("records") or payload.get("events") or []
            return [record for record in rows if isinstance(record, dict)]
        return []
    if suffix == ".csv":
        with path.open("r", encoding="utf-8", newline="") as handle:
            return [dict(row) for row in csv.DictReader(handle)]
    raise ValueError(f"Unsupported PropagationAnalysis fixture format: {path.suffix}")


def _records_to_cascades(records: Iterable[Mapping[str, Any]], *, dataset: str) -> list[dict[str, Any]]:
    grouped: defaultdict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        cascade_id = _first_text(record, ("cascade_id", "thread_id", "event_id", "root_id", "conversation_id")) or "default"
        grouped[cascade_id].append(_normalize_record(record, dataset=dataset, cascade_id=cascade_id))

    cascades = []
    for cascade_id, rows in sorted(grouped.items()):
        rows.sort(key=lambda row: (row.get("timestamp") or "", row.get("user_id") or "", row.get("item_id") or ""))
        users = sorted({row["user_id"] for row in rows if row.get("user_id")})
        cascades.append(
            {
                "cascade_id": cascade_id,
                "dataset": dataset,
                "rows": rows,
                "row_count": len(rows),
                "user_count": len(users),
                "users": users,
                "targets": {
                    "final_size": len(users),
                    "independent_active_accounts": len(users),
                    "next_hop_candidates": users,
                },
            }
        )
    return cascades


def _normalize_record(record: Mapping[str, Any], *, dataset: str, cascade_id: str) -> dict[str, Any]:
    return {
        "dataset": dataset,
        "cascade_id": cascade_id,
        "item_id": _first_text(record, ("item_id", "post_id", "tweet_id", "mid", "id")),
        "user_id": _first_text(record, ("user_id", "author_id", "uid", "account_id", "sender")),
        "parent_id": _first_text(record, ("parent_id", "reply_to", "repost_id", "source_id")),
        "timestamp": _serialize_timestamp(_first_value(record, ("timestamp", "time", "created_at", "publish_time"))),
        "text": _first_text(record, ("text", "content", "body")),
        "raw": dict(record),
    }


def _serialize_timestamp(value: Any) -> str | None:
    if isinstance(value, datetime):
        timestamp = value
    elif value in (None, ""):
        return None
    else:
        text = str(value).strip()
        if not text:
            return None
        try:
            timestamp = datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError:
            return text
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=timezone.utc)
    return timestamp.astimezone(timezone.utc).isoformat()


def _normalize_dataset(dataset: str) -> str:
    value = (dataset or "twitter").strip().lower()
    aliases = {
        "tweet": "twitter",
        "tweets": "twitter",
        "tgb-seq": "tgb",
        "memes": "memetracker",
    }
    return aliases.get(value, value)


def _first_text(row: Mapping[str, Any], keys: tuple[str, ...]) -> str:
    value = _first_value(row, keys)
    return " ".join(str(value or "").split()).strip()


def _first_value(row: Mapping[str, Any], keys: tuple[str, ...]) -> Any:
    for key in keys:
        value = row.get(key)
        if value not in (None, ""):
            return value
    return None
