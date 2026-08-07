from __future__ import annotations

from dataclasses import replace
import hashlib
import json

import pytest

from research.social_bot_detection.evaluation_protocol import (
    EvaluationProtocolError,
    create_frozen_holdout_manifest,
    evaluate_account_protocol,
    verify_frozen_holdout_manifest,
)
from research.social_bot_detection.strict_contracts import StrictAccountRecord


def test_evaluation_protocol_computes_leakage_gates_from_records():
    splits = {
        "train": _records("train", "2024-01-01T00:00:00Z"),
        "validation": _records("validation", "2024-02-01T00:00:00Z"),
        "test": _records("test", "2024-03-01T00:00:00Z"),
    }
    frozen = create_frozen_holdout_manifest(splits["test"])

    report = evaluate_account_protocol(splits, frozen_holdout_manifest=frozen)

    assert report["activation_allowed"] is True
    assert report["gates"] == {
        "account_disjoint": True,
        "event_disjoint": True,
        "community_disjoint": True,
        "time_forward": True,
        "platform_stratified": True,
        "frozen_holdout": True,
    }
    assert report["platforms"]["test"] == {"weibo": 2, "x": 2}
    assert report["frozen_holdout"] == {
        "verified": True,
        "schema": "cogguard.account-frozen-holdout.v1",
        "manifest_sha256": frozen["manifest_sha256"],
        "account_count": 4,
        "account_ids_sha256": report["audit"]["splits"]["test"]["account_ids_sha256"],
        "record_fingerprints_sha256": report["audit"]["splits"]["test"]["record_fingerprints_sha256"],
    }
    assert report["audit"]["time_forward"]["train_to_validation_gap_seconds"] > 0
    assert report["audit"]["time_forward"]["validation_to_test_gap_seconds"] > 0
    assert report["audit"]["platform_stratification"]["missing_by_split"] == {
        "test": [],
        "train": [],
        "validation": [],
    }
    assert report["audit"]["overlaps"]["community"]["overlap_count"] == 0
    with pytest.raises(TypeError):
        evaluate_account_protocol(splits, frozen_holdout_manifest=frozen, time_forward_passed=True)


def test_evaluation_protocol_fails_when_communities_overlap():
    splits = {
        "train": _records("train", "2024-01-01T00:00:00Z"),
        "validation": _records("validation", "2024-02-01T00:00:00Z"),
        "test": _records("test", "2024-03-01T00:00:00Z", community_prefix="train-community"),
    }
    frozen = create_frozen_holdout_manifest(splits["test"])

    report = evaluate_account_protocol(splits, frozen_holdout_manifest=frozen)

    assert report["activation_allowed"] is False
    assert report["gates"]["community_disjoint"] is False
    assert report["overlaps"]["community"]
    assert report["audit"]["overlaps"]["community"]["overlap_count"] > 0


def test_evaluation_protocol_rejects_a_persisted_report_without_record_audit():
    splits = {
        "train": _records("train", "2024-01-01T00:00:00Z"),
        "validation": _records("validation", "2024-02-01T00:00:00Z"),
        "test": _records("test", "2024-03-01T00:00:00Z"),
    }
    report = evaluate_account_protocol(
        splits,
        frozen_holdout_manifest=create_frozen_holdout_manifest(splits["test"]),
    )
    forged = dict(report)
    forged["audit"] = {}
    body = {key: value for key, value in forged.items() if key != "report_sha256"}
    forged["report_sha256"] = hashlib.sha256(
        json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    ).hexdigest()

    from research.social_bot_detection.evaluation_protocol import is_protocol_report_payload

    assert is_protocol_report_payload(forged) is False


def test_frozen_holdout_manifest_detects_record_tampering():
    holdout = _records("test", "2024-03-01T00:00:00Z")
    manifest = create_frozen_holdout_manifest(holdout)
    tampered = [replace(holdout[0], source_file_hash="tampered"), *holdout[1:]]

    with pytest.raises(EvaluationProtocolError, match="fingerprint"):
        verify_frozen_holdout_manifest(manifest, tampered)


def _records(prefix: str, timestamp: str, *, community_prefix: str | None = None) -> list[StrictAccountRecord]:
    community_prefix = community_prefix or f"{prefix}-community"
    return [
        StrictAccountRecord(
            account_id=f"{prefix}-{index}",
            label=index % 2,
            text=f"{prefix} text {index}",
            post_count=1,
            source_file_hash=f"{prefix}-hash-{index}",
            source_encoding="utf-8",
            metadata={
                "event_id": f"{prefix}-event-{index // 2}",
                "community_id": f"{community_prefix}-{index // 2}",
                "observed_at": timestamp,
                "platform": "weibo" if index % 2 == 0 else "x",
            },
        )
        for index in range(4)
    ]
