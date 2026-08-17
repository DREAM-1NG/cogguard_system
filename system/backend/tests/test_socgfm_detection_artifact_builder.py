from __future__ import annotations

import csv
import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

from app.config import PROJECT_ROOT
from app.core.analysis.coordination_runtime.socgfm_artifact_builder import (
    build_socgfm_detection_artifact,
)
from app.services.analysis_governance_service import verify_registered_artifact


def _write_source_run(root: Path) -> Path:
    run_dir = root / "runs" / "socgfm_cross_attention" / "tfidf"
    run_dir.mkdir(parents=True)
    prediction_path = run_dir / "predictions.csv"
    with prediction_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["account_id", "platform", "label", "evaluation_split", "node_score"],
        )
        writer.writeheader()
        writer.writerow(
            {
                "account_id": "a1",
                "platform": "twitter",
                "label": "1",
                "evaluation_split": "validation",
                "node_score": "0.91",
            }
        )
        writer.writerow(
            {
                "account_id": "a2",
                "platform": "",
                "label": "0",
                "evaluation_split": "validation",
                "node_score": "0.01",
            }
        )
    (run_dir / "detection_summary.json").write_text(
        json.dumps(
            {
                "detect_model": {
                    "gnn_backend": "socgfm_cross_attention",
                    "classifier_backend": "socgfm_cross_attention_torch:{}",
                },
                "metrics": {
                    "macro_f1": 0.93,
                    "auprc": 0.94,
                    "auc": 0.95,
                    "max_f1_threshold": 0.6,
                },
            },
            ensure_ascii=False,
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    return root / "runs"


def _write_mixed_split_source_run(root: Path) -> Path:
    run_dir = root / "runs" / "socgfm_cross_attention" / "tfidf"
    run_dir.mkdir(parents=True)
    prediction_path = run_dir / "predictions.csv"
    with prediction_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["account_id", "label", "evaluation_split", "node_score"],
        )
        writer.writeheader()
        writer.writerow({"account_id": "train-positive", "label": "1", "evaluation_split": "train", "node_score": "0.01"})
        writer.writerow({"account_id": "train-negative", "label": "0", "evaluation_split": "train", "node_score": "0.99"})
        writer.writerow({"account_id": "val-positive", "label": "1", "evaluation_split": "unassigned", "node_score": "0.80"})
        writer.writerow({"account_id": "val-negative", "label": "0", "evaluation_split": "unassigned", "node_score": "0.20"})
        writer.writerow({"account_id": "test-positive", "label": "1", "evaluation_split": "test", "node_score": "0.70"})
        writer.writerow({"account_id": "test-negative", "label": "0", "evaluation_split": "test", "node_score": "0.30"})
    return root / "runs"


def test_build_socgfm_detection_artifact_is_deterministic_and_claim_scoped(tmp_path: Path):
    source_run_dir = _write_source_run(tmp_path)
    output_dir = (
        PROJECT_ROOT
        / "artifacts"
        / "pytest-socgfm-artifact-builder"
        / hashlib.sha256(str(tmp_path).encode("utf-8")).hexdigest()[:16]
    )

    first = build_socgfm_detection_artifact(
        source_run_dir=source_run_dir,
        output_dir=output_dir,
        version="socgfm-test-v1",
    )
    first_checkpoint_hash = hashlib.sha256((output_dir / "checkpoint.json").read_bytes()).hexdigest()
    second = build_socgfm_detection_artifact(
        source_run_dir=source_run_dir,
        output_dir=output_dir,
        version="socgfm-test-v1",
    )
    second_checkpoint_hash = hashlib.sha256((output_dir / "checkpoint.json").read_bytes()).hexdigest()

    assert first["checkpoint_sha256"] == first_checkpoint_hash
    assert second["checkpoint_sha256"] == second_checkpoint_hash
    assert first_checkpoint_hash == second_checkpoint_hash
    checkpoint = json.loads((output_dir / "checkpoint.json").read_text(encoding="utf-8"))
    manifest = json.loads((output_dir / "manifest.json").read_text(encoding="utf-8"))
    rows = list(csv.DictReader((output_dir / "account_probabilities.csv").open(encoding="utf-8")))

    assert checkpoint["inference_mode"] == "precomputed_member_probability_cluster_aggregation"
    assert checkpoint["claim_scope"] == "account_level_io_membership_to_cluster_proxy"
    assert checkpoint["online_neural_forward"] is False
    assert "group_level_harmful_coordination_f1" in checkpoint["unsupported_claims"]
    assert checkpoint["account_probabilities"] == {"iohunter:a2": 0.01, "twitter:a1": 0.91}
    assert rows[0]["account_key"] == "iohunter:a2"
    assert rows[1]["account_key"] == "twitter:a1"
    assert manifest["technology"] == "coordination_detection"
    assert manifest["backend"] == "socgfm_cross_attention"
    assert manifest["metrics"]["system_primary_model"] == "socgfm_cross_attention"
    assert manifest["metrics"]["claim_scope"] == "account_level_io_membership_to_cluster_proxy"
    assert manifest["metrics"]["online_neural_forward"] is False
    assert "group-level harmful coordination F1" not in json.dumps(manifest, ensure_ascii=False)
    verified = verify_registered_artifact(
        artifact_uri=str(output_dir),
        expected_hash=first_checkpoint_hash,
        technology="coordination_detection",
        artifact_root=PROJECT_ROOT / "artifacts",
    )
    assert verified.quality_gates["activation_allowed"] is True


def test_build_socgfm_detection_artifact_uses_unassigned_as_validation_and_test_metrics(tmp_path: Path):
    source_run_dir = _write_mixed_split_source_run(tmp_path)
    output_dir = (
        PROJECT_ROOT
        / "artifacts"
        / "pytest-socgfm-artifact-builder-mixed-splits"
        / hashlib.sha256(str(tmp_path).encode("utf-8")).hexdigest()[:16]
    )

    summary = build_socgfm_detection_artifact(
        source_run_dir=source_run_dir,
        output_dir=output_dir,
        version="socgfm-mixed-splits-test-v1",
    )
    manifest = json.loads((output_dir / "manifest.json").read_text(encoding="utf-8"))
    provenance = json.loads((output_dir / "provenance.json").read_text(encoding="utf-8"))

    assert summary["account_probability_count"] == 6
    assert provenance["threshold_source"] == "validation_macro_f1"
    assert provenance["metric_source"] == "macro_average_heldout_test_rows_with_per_run_validation_threshold"
    assert manifest["metrics"]["macro_f1"] == 1.0
    assert manifest["metrics"]["auprc"] == 1.0
    assert manifest["metrics"]["roc_auc"] == 1.0
    assert manifest["metrics"]["metric_source"] == "macro_average_heldout_test_rows_with_per_run_validation_threshold"
    assert manifest["metrics"]["threshold_source"] == "validation_macro_f1"


def test_build_socgfm_detection_artifact_cli_writes_registration_payload(tmp_path: Path):
    source_run_dir = _write_source_run(tmp_path)
    output_dir = (
        PROJECT_ROOT
        / "artifacts"
        / "pytest-socgfm-artifact-builder-cli"
        / hashlib.sha256(str(tmp_path).encode("utf-8")).hexdigest()[:16]
    )
    registration_path = output_dir / "registration_payload.json"

    completed = subprocess.run(
        [
            sys.executable,
            str(PROJECT_ROOT / "backend" / "scripts" / "build_socgfm_detection_artifact.py"),
            "--source-run-dir",
            str(source_run_dir),
            "--output-dir",
            str(output_dir),
            "--version",
            "socgfm-cli-test-v1",
            "--registration-json",
            str(registration_path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    summary = json.loads(completed.stdout)
    registration = json.loads(registration_path.read_text(encoding="utf-8"))

    assert summary["artifact_dir"] == str(output_dir.resolve())
    assert registration["technology"] == "coordination_detection"
    assert registration["model"] == "socgfm_cross_attention"
    assert registration["artifact_uri"] == str(output_dir.resolve())
    assert registration["artifact_hash"] == summary["checkpoint_sha256"]
    assert registration["metrics"]["system_primary_model"] == "socgfm_cross_attention"
    assert registration["config"]["online_neural_forward"] is False


def test_verify_socgfm_detection_manifest_rejects_missing_claim_boundaries(tmp_path: Path):
    source_run_dir = _write_source_run(tmp_path)
    output_dir = (
        PROJECT_ROOT
        / "artifacts"
        / "pytest-socgfm-artifact-builder-invalid"
        / hashlib.sha256(str(tmp_path).encode("utf-8")).hexdigest()[:16]
    )
    summary = build_socgfm_detection_artifact(
        source_run_dir=source_run_dir,
        output_dir=output_dir,
        version="socgfm-invalid-test-v1",
    )
    manifest_path = output_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest.pop("claim_scope")
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, sort_keys=True), encoding="utf-8")

    with pytest.raises(ValueError, match="claim_scope"):
        verify_registered_artifact(
            artifact_uri=str(output_dir),
            expected_hash=summary["checkpoint_sha256"],
            technology="coordination_detection",
            artifact_root=PROJECT_ROOT / "artifacts",
        )


def test_verify_socgfm_detection_manifest_rejects_group_level_f1_claim(tmp_path: Path):
    source_run_dir = _write_source_run(tmp_path)
    output_dir = (
        PROJECT_ROOT
        / "artifacts"
        / "pytest-socgfm-artifact-builder-forbidden-claim"
        / hashlib.sha256(str(tmp_path).encode("utf-8")).hexdigest()[:16]
    )
    summary = build_socgfm_detection_artifact(
        source_run_dir=source_run_dir,
        output_dir=output_dir,
        version="socgfm-forbidden-claim-test-v1",
    )
    manifest_path = output_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["metrics"]["group_level_harmful_coordination_f1"] = 0.91
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, sort_keys=True), encoding="utf-8")

    with pytest.raises(ValueError, match="group-level"):
        verify_registered_artifact(
            artifact_uri=str(output_dir),
            expected_hash=summary["checkpoint_sha256"],
            technology="coordination_detection",
            artifact_root=PROJECT_ROOT / "artifacts",
        )


def test_build_socgfm_detection_artifact_rejects_c_drive_output(tmp_path: Path):
    source_run_dir = _write_source_run(tmp_path)

    with pytest.raises(ValueError, match="G: drive"):
        build_socgfm_detection_artifact(
            source_run_dir=source_run_dir,
            output_dir=Path("C:/coordination_detection/socgfm_cross_attention/v1"),
            version="socgfm-test-v1",
        )
