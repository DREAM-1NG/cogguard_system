"""Runtime integrity boundary tests for account model bundles."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pytest

from app.core.account_model_artifact import load_deployable_bundle_manifest, verify_bundle_files
from app.services.account_model_runtime_service import _checkpoint_path
from app.services.account_model_governance_service import _verify_artifact_hash
from app.utils.exceptions import AppException

SYSTEM_ROOT = Path(__file__).resolve().parents[2]
if str(SYSTEM_ROOT) not in sys.path:
    sys.path.insert(0, str(SYSTEM_ROOT))

from research.social_bot_detection.model_bundle import write_account_model_bundle


def test_runtime_resolves_only_a_verified_account_model_bundle_v1(tmp_path):
    bundle_dir = _write_bundle(tmp_path)

    checkpoint = _checkpoint_path(str(bundle_dir))

    assert checkpoint == bundle_dir / "detector.pt"


def test_runtime_rejects_a_verified_but_non_deployable_bundle(tmp_path):
    bundle_dir = _write_bundle(tmp_path)

    with pytest.raises(AppException, match="not deployment eligible"):
        load_deployable_bundle_manifest(bundle_dir)


def test_activation_hash_verification_requires_a_deployable_bundle(tmp_path):
    bundle_dir = _write_bundle(tmp_path)
    detector_hash = hashlib.sha256((bundle_dir / "detector.pt").read_bytes()).hexdigest()

    with pytest.raises(AppException, match="not deployment eligible"):
        _verify_artifact_hash(
            str(bundle_dir),
            detector_hash,
            require_deployable=True,
        )


def test_activation_rejects_a_bare_checkpoint_even_when_its_hash_matches(tmp_path):
    checkpoint = tmp_path / "detector.pt"
    checkpoint.write_bytes(b"detector")
    detector_hash = hashlib.sha256(checkpoint.read_bytes()).hexdigest()

    with pytest.raises(AppException, match="deployable account model bundle"):
        _verify_artifact_hash(
            str(checkpoint),
            detector_hash,
            require_deployable=True,
        )


@pytest.mark.parametrize(
    "mutation",
    [
        "tampered",
        "unlisted",
        "unsafe",
        "wrong_schema",
        "component_tamper",
        "encoder_binding_tamper",
        "feature_binding_tamper",
        "calibration_binding_tamper",
        "source_schema_tamper",
    ],
)
def test_runtime_rejects_tampered_unlisted_unsafe_or_wrong_schema_bundles(tmp_path, mutation):
    bundle_dir = _write_bundle(tmp_path)
    if mutation == "tampered":
        (bundle_dir / "detector.pt").write_bytes(b"tampered")
    elif mutation == "unlisted":
        (bundle_dir / "extra.bin").write_bytes(b"not declared")
    else:
        manifest_path = bundle_dir / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if mutation == "unsafe":
            manifest["artifacts"]["detector"] = "../outside.pt"
        elif mutation == "component_tamper":
            manifest["components"]["detector"]["artifact"] = manifest["artifacts"]["encoder"]
        elif mutation == "encoder_binding_tamper":
            manifest["components"]["detector"]["encoder_sha256"] = "0" * 64
        elif mutation == "feature_binding_tamper":
            manifest["components"]["detector"]["feature_schema_sha256"] = "0" * 64
        elif mutation == "calibration_binding_tamper":
            manifest["components"]["calibration"]["detector_sha256"] = "0" * 64
        elif mutation == "source_schema_tamper":
            manifest["components"]["detector"]["source_schema"] = "cogguard.botrhg.other.v1"
        else:
            manifest["schema"] = "cogguard.account-model-bundle.v0"
        _rewrite_manifest_hash(manifest_path, manifest)

    with pytest.raises(AppException, match="Account model bundle"):
        verify_bundle_files(bundle_dir)


def _write_bundle(tmp_path):
    encoder = tmp_path / "encoder.bin"
    detector = tmp_path / "detector.pt"
    encoder.write_bytes(b"encoder")
    detector.write_bytes(b"detector")
    manifest_path = write_account_model_bundle(
        tmp_path / "bundle",
        encoder=encoder,
        detector=detector,
        feature_schema={"numeric_fields": ["post_count"], "categorical_fields": [], "categorical_vocab": {}},
        calibration={"method": "identity", "passed": True},
        metrics={"test": {}},
        data_fingerprints={"fixture": "a" * 64},
        source_schema="cogguard.botrhg.account.v3",
    )
    return manifest_path.parent


def _rewrite_manifest_hash(manifest_path, manifest):
    manifest_path.write_text(json.dumps(manifest, sort_keys=True), encoding="utf-8")
    digest = hashlib.sha256(manifest_path.read_bytes()).hexdigest()
    (manifest_path.parent / "manifest.sha256").write_text(f"{digest}  manifest.json\n", encoding="ascii")
