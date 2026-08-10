"""Approved-label corpus export for Chinese account detection."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

__all__ = [
    "ApprovedAccountLabel",
    "ChineseAccountCorpusManifest",
    "export_approved_account_corpus",
]


@dataclass(frozen=True, slots=True)
class ApprovedAccountLabel:
    """One adjudicated account label eligible for training export."""

    case_id: str
    account_id: str
    source_account_id: str
    platform: str
    event_id: str
    text: str
    behavior_label: str
    training_target: str
    evidence_post_ids: list[str]
    case_fingerprint: str
    label_id: str
    observed_at: str | None = None
    community_id: str | None = None
    provenance: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ChineseAccountCorpusManifest:
    """Manifest for an approved Chinese account detection corpus version."""

    dataset_version_id: str
    record_count: int
    class_counts: dict[str, int]
    data_fingerprint: str
    source_policy: str
    output_path: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def export_approved_account_corpus(
    records: list[ApprovedAccountLabel],
    output_path: str | Path,
    *,
    dataset_version_id: str,
) -> ChineseAccountCorpusManifest:
    """Write approved labels as JSONL and return a reproducible manifest."""

    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    ordered = sorted(records, key=lambda row: (row.platform, row.event_id, row.account_id, row.case_id))
    digest = hashlib.sha256()
    class_counts: dict[str, int] = {}
    with path.open("w", encoding="utf-8") as handle:
        for record in ordered:
            payload = {
                key: value
                for key, value in asdict(record).items()
                if value is not None
            }
            digest.update(json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8"))
            digest.update(b"\n")
            class_counts[record.training_target] = class_counts.get(record.training_target, 0) + 1
            handle.write(json.dumps(payload, ensure_ascii=False, sort_keys=True))
            handle.write("\n")
    return ChineseAccountCorpusManifest(
        dataset_version_id=dataset_version_id,
        record_count=len(ordered),
        class_counts=class_counts,
        data_fingerprint=digest.hexdigest(),
        source_policy="approved_or_adjudicated_observable_behavior_labels_only",
        output_path=str(path),
    )
