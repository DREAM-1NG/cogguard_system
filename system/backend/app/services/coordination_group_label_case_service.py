"""File-backed collection service for Coordination group Detection labels."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

from app.config import PROJECT_ROOT
from app.core.analysis.coordination_runtime.group_label_cases import (
    ALLOWED_CLUSTER_HARM_LABELS,
    CoordinationGroupLabelCase,
    write_coordination_group_label_cases,
)

GROUP_LABEL_CASE_ROOT = PROJECT_ROOT / "output" / "coordination_group_label_cases"


def persist_coordination_group_label_cases(
    cases: Sequence[Mapping[str, Any]],
    *,
    snapshot_id: str,
    source_batch_id: str,
    root: str | Path | None = None,
) -> dict[str, Any]:
    """Persist pending group-level Coordination Detection label cases as JSONL."""

    normalized_cases = [_validated_case(case).to_dict() for case in cases]
    output_path = _case_batch_path(
        root or GROUP_LABEL_CASE_ROOT,
        snapshot_id=snapshot_id,
        source_batch_id=source_batch_id,
    )
    write_coordination_group_label_cases(normalized_cases, output_path)
    return {
        "schema_version": "cogguard.coordination-group-label-case-collection/v1",
        "case_count": len(normalized_cases),
        "output_path": str(output_path),
        "snapshot_id": str(snapshot_id),
        "source_batch_id": str(source_batch_id),
        "collection_fingerprint": _stable_hash(normalized_cases),
    }


def record_coordination_group_label_review(
    *,
    case: Mapping[str, Any],
    cluster_harm_label: str,
    reviewer_id: int,
    reviewer_notes: str = "",
    root: str | Path | None = None,
) -> dict[str, Any]:
    """Append one human-reviewed group-level Coordination label case."""

    if cluster_harm_label not in ALLOWED_CLUSTER_HARM_LABELS:
        raise ValueError("cluster_harm_label must be harmful_coordination or benign_coordination")
    if int(reviewer_id) <= 0:
        raise ValueError("reviewer_id must be a positive integer")
    pending = _validated_case(case)
    reviewed_payload = pending.to_dict()
    reviewed_payload["review_status"] = "labeled"
    reviewed_payload["cluster_harm_label"] = cluster_harm_label
    reviewed_payload["review"] = {
        "reviewer_id": int(reviewer_id),
        "reviewer_notes": str(reviewer_notes or ""),
        "reviewed_at": datetime.now(timezone.utc).isoformat(),
    }
    reviewed = _validated_case(reviewed_payload, allow_review=True).to_dict()
    reviewed["review"] = reviewed_payload["review"]

    output_path = _review_path(root or GROUP_LABEL_CASE_ROOT)
    _require_g_drive(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(reviewed, ensure_ascii=False, sort_keys=True, allow_nan=False) + "\n")
    return {
        "schema_version": "cogguard.coordination-group-label-review/v1",
        "case_id": reviewed["case_id"],
        "review_status": reviewed["review_status"],
        "cluster_harm_label": reviewed["cluster_harm_label"],
        "output_path": str(output_path),
        "review_fingerprint": _stable_hash(reviewed),
    }


def _validated_case(value: Mapping[str, Any], *, allow_review: bool = False) -> CoordinationGroupLabelCase:
    if not isinstance(value, Mapping):
        raise ValueError("case must be a JSON object")
    extra_allowed = {"review"} if allow_review else set()
    unknown = set(value) - {
        "schema_version",
        "case_id",
        "event_id",
        "snapshot_id",
        "source_batch_id",
        "cluster_id",
        "member_account_ids",
        "evidence_matrix",
        "characterization",
        "model_output",
        "review_status",
        "cluster_harm_label",
        "created_at",
        *extra_allowed,
    }
    if unknown:
        raise ValueError(f"case contains unknown fields: {sorted(unknown)}")
    return CoordinationGroupLabelCase(
        schema_version=str(value.get("schema_version") or "cogguard.coordination-group-label-case/v1"),
        case_id=str(value.get("case_id") or ""),
        event_id=str(value.get("event_id") or ""),
        snapshot_id=str(value.get("snapshot_id") or ""),
        source_batch_id=str(value.get("source_batch_id") or ""),
        cluster_id=str(value.get("cluster_id") or ""),
        member_account_ids=tuple(value.get("member_account_ids") or ()),
        evidence_matrix=dict(value.get("evidence_matrix") or {}),
        characterization=dict(value.get("characterization") or {}),
        model_output=dict(value.get("model_output") or {}),
        review_status=str(value.get("review_status") or "pending"),
        cluster_harm_label=value.get("cluster_harm_label"),
        created_at=str(value.get("created_at") or datetime.now(timezone.utc).isoformat()),
    )


def _case_batch_path(root: str | Path, *, snapshot_id: str, source_batch_id: str) -> Path:
    root_path = Path(root).expanduser().resolve()
    _require_g_drive(root_path)
    digest = hashlib.sha256(
        json.dumps(
            {"snapshot_id": str(snapshot_id), "source_batch_id": str(source_batch_id)},
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()[:16]
    return root_path / "pending" / f"{_safe_name(snapshot_id)}-{digest}.jsonl"


def _review_path(root: str | Path) -> Path:
    root_path = Path(root).expanduser().resolve()
    _require_g_drive(root_path)
    return root_path / "reviews" / "coordination_group_label_reviews.jsonl"


def _require_g_drive(path: Path) -> None:
    if path.drive.upper() != "G:":
        raise ValueError("coordination group label cases must be written under the G: drive")


def _safe_name(value: Any) -> str:
    text = "".join(char if char.isalnum() or char in {"-", "_"} else "-" for char in str(value or "case"))
    return text.strip("-") or "case"


def _stable_hash(value: Any) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(payload).hexdigest()


__all__ = [
    "GROUP_LABEL_CASE_ROOT",
    "persist_coordination_group_label_cases",
    "record_coordination_group_label_review",
]
