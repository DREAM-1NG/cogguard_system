"""Decision-feedback identifiers and payloads for review cases."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from app.models.review_case import ReviewDecision as ReviewDecisionRecord


def _decision_feedback_payload(row: ReviewDecisionRecord) -> dict[str, Any]:
    return {
        "source": "confirmed_decision",
        "decision_id": row.decision_id,
        "decision_version": int(row.version),
        "conclusion": row.conclusion,
        "urgency": row.urgency,
        "disposition": row.disposition,
        "rationale": row.rationale,
        "key_evidence_refs": _json_loads(row.key_evidence_refs_json, []),
        "unresolved_items": _json_loads(row.unresolved_items_json, []),
    }


def _canonical_source_id(*, case_id: str, snapshot_revision_id: str, draft_version: int) -> str:
    raw = f"{case_id}\x1f{snapshot_revision_id}\x1f{draft_version}"
    return f"case_decision_source_{hashlib.sha256(raw.encode('utf-8')).hexdigest()[:32]}"


def _feedback_id(decision_id: str) -> str:
    return f"feedback_{hashlib.sha256(decision_id.encode('utf-8')).hexdigest()[:32]}"


def _json_loads(value: str | None, default: Any) -> Any:
    try:
        return json.loads(value) if value else default
    except (TypeError, json.JSONDecodeError):
        return default


__all__ = [
    "_canonical_source_id",
    "_decision_feedback_payload",
    "_feedback_id",
]
