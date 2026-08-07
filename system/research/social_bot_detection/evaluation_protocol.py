"""Fail-closed, record-derived evaluation gates for account detectors."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from itertools import combinations
from typing import Any, Mapping, Sequence

from .strict_contracts import StrictAccountRecord

__all__ = [
    "EvaluationProtocolReport",
    "EvaluationProtocolError",
    "create_frozen_holdout_manifest",
    "evaluate_account_protocol",
    "is_protocol_report_payload",
    "is_verified_protocol_report",
    "verify_frozen_holdout_manifest",
]

_FROZEN_HOLDOUT_SCHEMA = "cogguard.account-frozen-holdout.v1"
_PROTOCOL_SCHEMA = "cogguard.account-evaluation-protocol.v1"
_REPORT_SHA256 = "report_sha256"
_SPLIT_NAMES = ("train", "validation", "test")
_REQUIRED_METADATA = ("event_id", "community_id", "observed_at", "platform")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_REQUIRED_GATES = (
    "account_disjoint",
    "event_disjoint",
    "community_disjoint",
    "time_forward",
    "platform_stratified",
    "frozen_holdout",
)


class EvaluationProtocolError(ValueError):
    """Raised when records cannot support a leakage-safe evaluation claim."""


class EvaluationProtocolReport(dict[str, Any]):
    """A report that retains proof it came directly from protocol evaluation."""

    __slots__ = ("_runtime_digest",)

    def __init__(self, payload: Mapping[str, Any]) -> None:
        body = dict(payload)
        body.pop(_REPORT_SHA256, None)
        body[_REPORT_SHA256] = _canonical_sha256(body)
        super().__init__(body)
        self._runtime_digest = _canonical_sha256(self)


def is_protocol_report_payload(value: Any) -> bool:
    """Validate the persisted, self-describing form of a protocol report."""

    if not isinstance(value, Mapping) or not isinstance(value.get(_REPORT_SHA256), str):
        return False
    body = {key: item for key, item in value.items() if key != _REPORT_SHA256}
    return (
        value[_REPORT_SHA256] == _canonical_sha256(body)
        and _is_auditable_protocol_body(body)
    )


def is_verified_protocol_report(value: Any) -> bool:
    """Accept only an unmodified report returned by evaluate_account_protocol."""

    return (
        isinstance(value, EvaluationProtocolReport)
        and value._runtime_digest == _canonical_sha256(value)
        and is_protocol_report_payload(value)
    )


def create_frozen_holdout_manifest(records: Sequence[StrictAccountRecord]) -> dict[str, Any]:
    """Freeze the exact account records reserved for the final holdout."""

    normalized = _require_records(records, split_name="holdout")
    fingerprints = {record.account_id: _record_fingerprint(record) for record in normalized}
    payload = {
        "schema": _FROZEN_HOLDOUT_SCHEMA,
        "account_ids": sorted(fingerprints),
        "record_fingerprints": {account_id: fingerprints[account_id] for account_id in sorted(fingerprints)},
    }
    return {**payload, "manifest_sha256": _canonical_sha256(payload)}


def verify_frozen_holdout_manifest(
    manifest: Mapping[str, Any],
    records: Sequence[StrictAccountRecord],
) -> None:
    """Reject changed, incomplete, or malformed frozen-holdout records."""

    if not isinstance(manifest, Mapping) or manifest.get("schema") != _FROZEN_HOLDOUT_SCHEMA:
        raise EvaluationProtocolError("unsupported frozen holdout manifest")
    payload = {
        "schema": manifest.get("schema"),
        "account_ids": manifest.get("account_ids"),
        "record_fingerprints": manifest.get("record_fingerprints"),
    }
    if not isinstance(payload["account_ids"], list) or not isinstance(payload["record_fingerprints"], Mapping):
        raise EvaluationProtocolError("malformed frozen holdout manifest")
    if manifest.get("manifest_sha256") != _canonical_sha256(payload):
        raise EvaluationProtocolError("frozen holdout manifest fingerprint does not match its contents")
    normalized = _require_records(records, split_name="holdout")
    observed = {record.account_id: _record_fingerprint(record) for record in normalized}
    expected_ids = payload["account_ids"]
    expected_fingerprints = dict(payload["record_fingerprints"])
    if expected_ids != sorted(observed) or expected_fingerprints != {account_id: observed[account_id] for account_id in sorted(observed)}:
        raise EvaluationProtocolError("frozen holdout record fingerprint mismatch")


def evaluate_account_protocol(
    splits: Mapping[str, Sequence[StrictAccountRecord]],
    *,
    frozen_holdout_manifest: Mapping[str, Any],
) -> dict[str, Any]:
    """Compute all leakage gates from records and the frozen holdout manifest."""

    if set(splits) != set(_SPLIT_NAMES):
        raise EvaluationProtocolError("evaluation splits must be exactly train, validation, and test")
    normalized = {name: _require_records(splits[name], split_name=name) for name in _SPLIT_NAMES}
    verify_frozen_holdout_manifest(frozen_holdout_manifest, normalized["test"])

    fields = {
        "account": {name: {record.account_id for record in records} for name, records in normalized.items()},
        "event": {name: _metadata_values(records, "event_id", name) for name, records in normalized.items()},
        "community": {name: _metadata_values(records, "community_id", name) for name, records in normalized.items()},
    }
    overlaps = {field: _pairwise_overlaps(values) for field, values in fields.items()}
    timestamps = {name: _timestamps(records, name) for name, records in normalized.items()}
    platforms = {name: _platform_counts(records, name) for name, records in normalized.items()}
    platform_names = set().union(*(set(counts) for counts in platforms.values()))
    platform_audit = _platform_audit(platforms, platform_names)
    time_audit = _time_forward_audit(timestamps)
    frozen_audit = _frozen_holdout_audit(frozen_holdout_manifest, normalized["test"])
    gates = {
        "account_disjoint": not overlaps["account"],
        "event_disjoint": not overlaps["event"],
        "community_disjoint": not overlaps["community"],
        "time_forward": bool(time_audit["passed"]),
        "platform_stratified": bool(platform_audit["passed"]),
        "frozen_holdout": bool(frozen_audit["verified"]),
    }
    return EvaluationProtocolReport({
        "schema": _PROTOCOL_SCHEMA,
        "activation_allowed": all(gates.values()),
        "gates": gates,
        "overlaps": overlaps,
        "platforms": platforms,
        "time_bounds": time_audit["bounds"],
        "frozen_holdout": frozen_audit,
        "audit": {
            "splits": {name: _split_audit(records) for name, records in normalized.items()},
            "overlaps": _overlap_audit(overlaps),
            "time_forward": time_audit,
            "platform_stratification": platform_audit,
        },
    })


def _require_records(records: Sequence[StrictAccountRecord], *, split_name: str) -> list[StrictAccountRecord]:
    if not records:
        raise EvaluationProtocolError(f"{split_name} split is empty")
    result = list(records)
    ids = [record.account_id for record in result]
    if len(ids) != len(set(ids)):
        raise EvaluationProtocolError(f"{split_name} split has duplicate account ids")
    for record in result:
        if not isinstance(record, StrictAccountRecord):
            raise EvaluationProtocolError(f"{split_name} split contains an unsupported record")
        for key in _REQUIRED_METADATA:
            if not str(record.metadata.get(key) or "").strip():
                raise EvaluationProtocolError(f"{split_name} record {record.account_id!r} is missing {key}")
    return result


def _metadata_values(records: Sequence[StrictAccountRecord], key: str, split_name: str) -> set[str]:
    values = {str(record.metadata[key]).strip() for record in records}
    if "" in values:
        raise EvaluationProtocolError(f"{split_name} has an empty {key}")
    return values


def _timestamps(records: Sequence[StrictAccountRecord], split_name: str) -> list[datetime]:
    values: list[datetime] = []
    for record in records:
        raw_value = str(record.metadata["observed_at"]).strip().replace("Z", "+00:00")
        try:
            parsed = datetime.fromisoformat(raw_value)
        except ValueError as error:
            raise EvaluationProtocolError(f"{split_name} record {record.account_id!r} has an invalid observed_at") from error
        if parsed.tzinfo is None:
            raise EvaluationProtocolError(f"{split_name} record {record.account_id!r} observed_at must include a timezone")
        values.append(parsed)
    return values


def _platform_counts(records: Sequence[StrictAccountRecord], split_name: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for platform in _metadata_values(records, "platform", split_name):
        counts[platform] = sum(1 for record in records if str(record.metadata["platform"]).strip() == platform)
    return dict(sorted(counts.items()))


def _pairwise_overlaps(values: Mapping[str, set[str]]) -> dict[str, list[str]]:
    return {
        f"{left}:{right}": sorted(values[left] & values[right])
        for left, right in combinations(_SPLIT_NAMES, 2)
        if values[left] & values[right]
    }


def _split_audit(records: Sequence[StrictAccountRecord]) -> dict[str, Any]:
    """Summarize a split without turning caller-provided assertions into evidence."""

    accounts = sorted(record.account_id for record in records)
    events = sorted(str(record.metadata["event_id"]).strip() for record in records)
    communities = sorted(str(record.metadata["community_id"]).strip() for record in records)
    platforms = sorted(str(record.metadata["platform"]).strip() for record in records)
    return {
        "record_count": len(records),
        "account_count": len(accounts),
        "account_ids_sha256": _canonical_sha256(accounts),
        "event_count": len(set(events)),
        "event_ids_sha256": _canonical_sha256(events),
        "community_count": len(set(communities)),
        "community_ids_sha256": _canonical_sha256(communities),
        "platform_count": len(set(platforms)),
        "record_fingerprints_sha256": _canonical_sha256(
            {
                record.account_id: _record_fingerprint(record)
                for record in sorted(records, key=lambda item: item.account_id)
            }
        ),
    }


def _overlap_audit(overlaps: Mapping[str, Mapping[str, list[str]]]) -> dict[str, dict[str, Any]]:
    return {
        field: {
            "overlap_count": sum(len(items) for items in pairs.values()),
            "pair_counts": {pair: len(items) for pair, items in sorted(pairs.items())},
            "overlap_ids_sha256": _canonical_sha256(
                {pair: list(items) for pair, items in sorted(pairs.items())}
            ),
        }
        for field, pairs in sorted(overlaps.items())
    }


def _time_forward_audit(timestamps: Mapping[str, Sequence[datetime]]) -> dict[str, Any]:
    bounds = {
        name: {"min": min(values).isoformat(), "max": max(values).isoformat()}
        for name, values in timestamps.items()
    }
    train_to_validation = min(timestamps["validation"]) - max(timestamps["train"])
    validation_to_test = min(timestamps["test"]) - max(timestamps["validation"])
    return {
        "passed": train_to_validation.total_seconds() > 0 and validation_to_test.total_seconds() > 0,
        "bounds": bounds,
        "train_to_validation_gap_seconds": train_to_validation.total_seconds(),
        "validation_to_test_gap_seconds": validation_to_test.total_seconds(),
    }


def _platform_audit(platforms: Mapping[str, Mapping[str, int]], platform_names: set[str]) -> dict[str, Any]:
    required_platforms = sorted(platform_names)
    missing_by_split = {
        split_name: [platform for platform in required_platforms if counts.get(platform, 0) <= 0]
        for split_name, counts in sorted(platforms.items())
    }
    return {
        "passed": bool(required_platforms) and not any(missing_by_split.values()),
        "required_platforms": required_platforms,
        "counts": {split_name: dict(counts) for split_name, counts in sorted(platforms.items())},
        "missing_by_split": missing_by_split,
    }


def _frozen_holdout_audit(
    manifest: Mapping[str, Any],
    records: Sequence[StrictAccountRecord],
) -> dict[str, Any]:
    account_ids = sorted(record.account_id for record in records)
    record_fingerprints = {
        record.account_id: _record_fingerprint(record)
        for record in sorted(records, key=lambda item: item.account_id)
    }
    return {
        "verified": True,
        "schema": str(manifest["schema"]),
        "manifest_sha256": str(manifest["manifest_sha256"]),
        "account_count": len(account_ids),
        "account_ids_sha256": _canonical_sha256(account_ids),
        "record_fingerprints_sha256": _canonical_sha256(record_fingerprints),
    }


def _is_auditable_protocol_body(body: Mapping[str, Any]) -> bool:
    if body.get("schema") != _PROTOCOL_SCHEMA or not isinstance(body.get("activation_allowed"), bool):
        return False
    gates = body.get("gates")
    audit = body.get("audit")
    frozen_holdout = body.get("frozen_holdout")
    if not isinstance(gates, Mapping) or set(gates) != set(_REQUIRED_GATES):
        return False
    if any(not isinstance(gates[name], bool) for name in _REQUIRED_GATES):
        return False
    if body["activation_allowed"] != all(gates.values()):
        return False
    if not isinstance(audit, Mapping) or not isinstance(audit.get("splits"), Mapping):
        return False
    if set(audit["splits"]) != set(_SPLIT_NAMES):
        return False
    if not isinstance(audit.get("time_forward"), Mapping) or not isinstance(audit.get("platform_stratification"), Mapping):
        return False
    if audit["time_forward"].get("passed") is not gates["time_forward"]:
        return False
    if audit["platform_stratification"].get("passed") is not gates["platform_stratified"]:
        return False
    if not isinstance(frozen_holdout, Mapping) or frozen_holdout.get("verified") is not gates["frozen_holdout"]:
        return False
    return all(
        isinstance(split, Mapping)
        and isinstance(split.get("record_count"), int)
        and split["record_count"] > 0
        and isinstance(split.get("record_fingerprints_sha256"), str)
        and bool(_SHA256.fullmatch(str(split["record_fingerprints_sha256"])))
        for split in audit["splits"].values()
    )


def _record_fingerprint(record: StrictAccountRecord) -> str:
    return _canonical_sha256(
        {
            "account_id": record.account_id,
            "label": record.label,
            "source_file_hash": record.source_file_hash,
            "metadata": {key: record.metadata.get(key) for key in _REQUIRED_METADATA},
        }
    )


def _canonical_sha256(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()
