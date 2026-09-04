from __future__ import annotations

import hashlib
import json

import pytest

from app.core.analysis.governance import approve_canonical_verdict, build_model_activation_decision
from app.config import settings
from app.services.analysis_governance_service import (
    _resolve_activation_approvers,
    _artifact_matches_hash,
    _is_sha256_digest,
    evaluate_quality_gates,
    verify_registered_artifact,
)


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


def test_production_activation_requires_two_distinct_active_administrators(monkeypatch):
    monkeypatch.setattr(settings, "BACKEND_ENV", "production")
    monkeypatch.setattr(settings, "ANALYSIS_MODEL_ACTIVATION_APPROVAL_MODE", "auto")

    with pytest.raises(ValueError, match="two distinct active administrator"):
        _resolve_activation_approvers(
            operator_id=7,
            recorded_approvers={7},
            active_admin_ids={7, 9},
        )

    assert _resolve_activation_approvers(
        operator_id=7,
        recorded_approvers={7, 9},
        active_admin_ids={7, 9},
    ) == (7, 9)


def test_local_activation_records_one_accountable_administrator(monkeypatch):
    monkeypatch.setattr(settings, "BACKEND_ENV", "local")
    monkeypatch.setattr(settings, "ANALYSIS_MODEL_ACTIVATION_APPROVAL_MODE", "auto")

    assert _resolve_activation_approvers(
        operator_id=7,
        recorded_approvers={7},
        active_admin_ids={7},
    ) == (7,)


def test_registered_artifact_must_resolve_inside_root_and_match_manifest(tmp_path):
    root = tmp_path / "artifacts"
    artifact_dir = root / "review_student" / "v1"
    artifact_dir.mkdir(parents=True)
    checkpoint = artifact_dir / "checkpoint.pt"
    checkpoint.write_bytes(b"student-checkpoint")
    digest = hashlib.sha256(checkpoint.read_bytes()).hexdigest()
    manifest = {
                "technology": "review_student",
                "checkpoint_path": "checkpoint.pt",
                "checkpoint_sha256": digest,
                "metrics": {
                    "teacher_macro_f1_gap": 0.02,
                    "ece": 0.07,
                    "p95_latency_seconds": 1.8,
                },
            }
    manifest["manifest_sha256"] = hashlib.sha256(
        json.dumps(manifest, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    (artifact_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

    verified = verify_registered_artifact(
        artifact_uri=str(artifact_dir),
        expected_hash=digest,
        technology="review_student",
        artifact_root=root,
    )

    assert verified.checkpoint_path == checkpoint.resolve()
    assert verified.manifest["technology"] == "review_student"
    assert verified.quality_gates["activation_allowed"] is True

    outside = tmp_path / "outside.pt"
    outside.write_bytes(b"outside")
    with pytest.raises(ValueError, match="artifact root"):
        verify_registered_artifact(
            artifact_uri=str(outside),
            expected_hash=hashlib.sha256(outside.read_bytes()).hexdigest(),
            technology="review_student",
            artifact_root=root,
        )


def test_registered_artifact_rejects_post_registration_manifest_mutation(tmp_path):
    root = tmp_path / "artifacts"
    artifact_dir = root / "review_student" / "v1"
    artifact_dir.mkdir(parents=True)
    checkpoint = artifact_dir / "checkpoint.pt"
    checkpoint.write_bytes(b"student-checkpoint")
    checkpoint_digest = hashlib.sha256(checkpoint.read_bytes()).hexdigest()
    manifest = {
        "schema": "cogguard.review_student.artifact.v1",
        "technology": "review_student",
        "version": "v1",
        "checkpoint_path": checkpoint.name,
        "checkpoint_sha256": checkpoint_digest,
        "backbone": "xlm-roberta-base",
        "rationale_dim": 768,
        "metrics": {
            "teacher_macro_f1_gap": 0.02,
            "ece": 0.07,
            "p95_latency_seconds": 1.8,
        },
    }
    manifest["manifest_sha256"] = hashlib.sha256(
        json.dumps(
            manifest,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    manifest_path = artifact_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    verify_registered_artifact(
        artifact_uri=str(artifact_dir),
        expected_hash=checkpoint_digest,
        technology="review_student",
        artifact_root=root,
    )

    manifest["metrics"]["ece"] = 0.01
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(ValueError, match="manifest"):
        verify_registered_artifact(
            artifact_uri=str(artifact_dir),
            expected_hash=checkpoint_digest,
            technology="review_student",
            artifact_root=root,
        )


def test_directory_manifest_checkpoint_cannot_escape_its_artifact_directory(tmp_path):
    root = tmp_path / "artifacts"
    artifact_dir = root / "review_student" / "v1"
    sibling_dir = root / "review_student" / "v2"
    artifact_dir.mkdir(parents=True)
    sibling_dir.mkdir(parents=True)
    sibling_checkpoint = sibling_dir / "checkpoint.pt"
    sibling_checkpoint.write_bytes(b"sibling-checkpoint")
    (artifact_dir / "manifest.json").write_text(
        json.dumps(
            {
                "technology": "review_student",
                "checkpoint_path": "../v2/checkpoint.pt",
                "metrics": {
                    "teacher_macro_f1_gap": 0.02,
                    "ece": 0.07,
                    "p95_latency_seconds": 1.8,
                },
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="artifact directory"):
        verify_registered_artifact(
            artifact_uri=str(artifact_dir),
            expected_hash=hashlib.sha256(sibling_checkpoint.read_bytes()).hexdigest(),
            technology="review_student",
            artifact_root=root,
        )


@pytest.mark.parametrize(
    ("technology", "metrics", "allowed"),
    [
        (
            "coordination_discover",
            {"strict_leiden": True, "stability_passed": True, "evidence_coverage_passed": True},
            True,
        ),
        (
            "propagation_analysis",
            {"coverage_80": 0.79, "coverage_95": 0.94, "beats_strong_baseline": True},
            True,
        ),
        (
            "review_student",
            {"teacher_macro_f1_gap": 0.04, "ece": 0.07, "p95_latency_seconds": 1.0},
            False,
        ),
        (
            "review_teacher",
            {"beats_best_single_agent": True, "beats_majority_vote": False},
            False,
        ),
    ],
)
def test_quality_gates_are_computed_by_capability(technology, metrics, allowed):
    assert evaluate_quality_gates(technology, metrics)["activation_allowed"] is allowed


def test_review_student_quality_gates_reject_negative_activation_metrics():
    result = evaluate_quality_gates(
        "review_student",
        {
            "teacher_macro_f1_gap": -1,
            "ece": -1,
            "p95_latency_seconds": -1,
        },
    )

    assert result["activation_allowed"] is False
    assert set(result["failed_gates"]) == {
        "teacher_macro_f1_gap",
        "ece",
        "p95_latency_seconds",
    }
