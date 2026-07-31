from __future__ import annotations

import hashlib

import pytest

from app.core.analysis.governance import approve_canonical_verdict, build_model_activation_decision
from app.services.analysis_governance_service import _artifact_matches_hash, _is_sha256_digest


def test_artifact_hash_validation_requires_a_local_sha256_match(tmp_path):
    artifact = tmp_path / "checkpoint.pt"
    artifact.write_bytes(b"checkpoint")
    digest = hashlib.sha256(artifact.read_bytes()).hexdigest()

    assert _is_sha256_digest(digest)
    assert _artifact_matches_hash(str(artifact), digest)
    assert not _artifact_matches_hash(str(artifact), "0" * 64)
    assert not _artifact_matches_hash(str(artifact), "not-a-sha256")


@pytest.mark.parametrize("uri", ["s3://models/checkpoint.pt", "https://models.example/checkpoint.pt"])
def test_remote_artifact_uri_is_not_claimed_verified_without_resolver(uri):
    assert not _artifact_matches_hash(uri, "0" * 64)


def test_canonical_verdict_requires_an_analyst_and_is_derived_from_source():
    source = {
        "verdict_id": "student_1",
        "verdict_type": "preliminary",
        "technology": "review_student",
        "snapshot_id": "snapshot_1",
        "event_id": "event_1",
        "label": "uncertain",
    }

    with pytest.raises(ValueError, match="positive analyst"):
        approve_canonical_verdict(source, approved_by=0)

    canonical = approve_canonical_verdict(source, approved_by=7, approval_notes="checked")

    assert canonical["verdict_type"] == "canonical"
    assert canonical["canonical_source_id"] == "student_1"
    assert canonical["approved_by"] == 7
    assert canonical["source_digest"]


def test_model_activation_requires_two_distinct_approvers_and_all_quality_gates():
    decision = build_model_activation_decision(
        {
            "technology": "coordination_discover",
            "version": "v1",
            "quality_gates": {
                "latency_passed": True,
                "calibration_passed": True,
                "safety_passed": True,
            },
        },
        approved_by=[7, 7],
    )

    assert decision["activation_allowed"] is False
    assert decision["gates"]["dual_approval"] is False

