from __future__ import annotations

import hashlib
import json

import pytest
import torch

from research.social_bot_detection.evaluation_protocol import (
    create_frozen_holdout_manifest,
    evaluate_account_protocol,
)
from research.social_bot_detection.model_bundle import (
    ModelBundleError,
    load_account_model_bundle,
    verify_account_model_bundle,
    write_account_model_bundle,
)
from research.social_bot_detection.strict_contracts import StrictAccountRecord


def test_model_bundle_records_required_artifacts_and_file_hashes(tmp_path):
    encoder = tmp_path / "encoder.bin"
    detector = tmp_path / "detector.bin"
    encoder.write_bytes(b"encoder payload")
    torch.save(
        {
            "schema": "cogguard.botrhg.account.v3",
            "text_runtime_assets": {
                "config.json": b"{}",
                "tokenizer_config.json": b"{}",
                "vocab.txt": b"[PAD]\\n[UNK]\\n",
            },
        },
        detector,
    )

    manifest_path = write_account_model_bundle(
        tmp_path / "bundle",
        encoder=encoder,
        detector=detector,
        feature_schema={"numeric_fields": ["followers_count"]},
        calibration={"method": "temperature_scaling", "temperature": 1.0},
        metrics={
            "test": {"macro_f1": 0.75},
        },
        data_fingerprints={"cresci_2017": "f" * 64},
        source_schema="cogguard.botrhg.account.v3",
        protocol_report=_valid_protocol_report(),
    )

    manifest = load_account_model_bundle(manifest_path)

    assert manifest["schema"] == "cogguard.account-model-bundle.v1"
    assert set(manifest["artifacts"]) == {
        "encoder",
        "detector",
        "feature_schema",
        "calibration",
        "metrics",
        "data_fingerprints",
    }
    assert set(manifest["files"]) == set(manifest["artifacts"].values())
    assert manifest["deployment"]["eligible"] is True
    assert manifest["components"]["detector"]["encoder_sha256"] == manifest["components"]["encoder"]["sha256"]
    assert manifest["components"]["calibration"]["detector_sha256"] == manifest["components"]["detector"]["sha256"]
    assert manifest["components"]["feature_schema"]["content_sha256"] == manifest["components"]["detector"]["feature_schema_sha256"]


def test_deployable_bundle_rejects_detector_without_embedded_text_runtime_assets(tmp_path):
    encoder = tmp_path / "encoder.bin"
    detector = tmp_path / "detector.bin"
    encoder.write_bytes(b"encoder payload")
    detector.write_bytes(b"detector payload")
    manifest_path = write_account_model_bundle(
        tmp_path / "bundle",
        encoder=encoder,
        detector=detector,
        feature_schema={"numeric_fields": ["followers_count"]},
        calibration={"method": "temperature_scaling", "temperature": 1.0},
        metrics={"test": {"macro_f1": 0.75}},
        data_fingerprints={"fixture": "f" * 64},
        source_schema="cogguard.botrhg.account.v3",
        protocol_report=_valid_protocol_report(),
    )

    with pytest.raises(ModelBundleError, match="text runtime assets"):
        verify_account_model_bundle(manifest_path.parent)


def test_model_bundle_rejects_an_unknown_detector_source_schema(tmp_path):
    encoder = tmp_path / "encoder.bin"
    detector = tmp_path / "detector.bin"
    encoder.write_bytes(b"encoder")
    detector.write_bytes(b"detector")

    with pytest.raises(ModelBundleError, match="source schema"):
        write_account_model_bundle(
            tmp_path / "bundle",
            encoder=encoder,
            detector=detector,
            feature_schema={"numeric_fields": []},
            calibration={"method": "none"},
            metrics={"test": {}},
            data_fingerprints={"fixture": "f" * 64},
            source_schema="cogguard.unknown.v1",
        )


def test_model_bundle_rejects_tampered_content_and_path_escape(tmp_path):
    encoder = tmp_path / "encoder.bin"
    detector = tmp_path / "detector.bin"
    encoder.write_bytes(b"encoder payload")
    detector.write_bytes(b"detector payload")
    manifest_path = write_account_model_bundle(
        tmp_path / "bundle",
        encoder=encoder,
        detector=detector,
        feature_schema={"numeric_fields": []},
        calibration={"method": "none"},
        metrics={"test": {}},
        data_fingerprints={"fixture": "a" * 64},
        source_schema="cogguard.botrhg.account.v3",
    )
    bundle_dir = manifest_path.parent
    (bundle_dir / "detector.bin").write_bytes(b"tampered")

    with pytest.raises(ModelBundleError, match="SHA-256"):
        verify_account_model_bundle(bundle_dir)

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["artifacts"]["detector"] = "../outside.bin"
    manifest["files"]["../outside.bin"] = "0" * 64
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ModelBundleError, match="path"):
        verify_account_model_bundle(bundle_dir)


def test_model_bundle_rejects_component_binding_tampering_after_manifest_rehash(tmp_path):
    encoder = tmp_path / "encoder.bin"
    detector = tmp_path / "detector.bin"
    encoder.write_bytes(b"encoder")
    detector.write_bytes(b"detector")
    manifest_path = write_account_model_bundle(
        tmp_path / "bundle",
        encoder=encoder,
        detector=detector,
        feature_schema={"numeric_fields": ["followers_count"]},
        calibration={"method": "temperature_scaling", "temperature": 1.0},
        metrics={"test": {}},
        data_fingerprints={"fixture": "f" * 64},
        source_schema="cogguard.botrhg.account.v3",
    )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["components"]["detector"]["encoder_sha256"] = "0" * 64
    _rewrite_manifest_hash(manifest_path, manifest)

    with pytest.raises(ModelBundleError, match="detector is not bound"):
        verify_account_model_bundle(manifest_path.parent)


def test_model_bundle_rejects_label_proxy_in_feature_schema(tmp_path):
    encoder = tmp_path / "encoder.bin"
    detector = tmp_path / "detector.bin"
    encoder.write_bytes(b"encoder")
    detector.write_bytes(b"detector")

    with pytest.raises(ModelBundleError, match="label-derived"):
        write_account_model_bundle(
            tmp_path / "bundle",
            encoder=encoder,
            detector=detector,
            feature_schema={"categorical_fields": ["source_label"]},
            calibration={"method": "none"},
            metrics={"test": {}},
            data_fingerprints={"fixture": "1" * 64},
            source_schema="cogguard.botrhg.account.v3",
        )


def test_model_bundle_without_a_computed_protocol_is_not_deployable(tmp_path):
    encoder = tmp_path / "encoder.bin"
    detector = tmp_path / "detector.bin"
    encoder.write_bytes(b"encoder")
    detector.write_bytes(b"detector")

    manifest = load_account_model_bundle(
        write_account_model_bundle(
            tmp_path / "bundle",
            encoder=encoder,
            detector=detector,
            feature_schema={"numeric_fields": []},
            calibration={"method": "none"},
            metrics={"test": {"macro_f1": 0.8}},
            data_fingerprints={"fixture": "c" * 64},
            source_schema="cogguard.botrhg.account.v3",
        )
    )

    assert manifest["deployment"] == {"eligible": False, "status": "evaluation_unverified"}


def test_model_bundle_does_not_trust_protocol_embedded_only_in_metrics(tmp_path):
    encoder = tmp_path / "encoder.bin"
    detector = tmp_path / "detector.bin"
    encoder.write_bytes(b"encoder")
    detector.write_bytes(b"detector")

    manifest = load_account_model_bundle(
        write_account_model_bundle(
            tmp_path / "bundle",
            encoder=encoder,
            detector=detector,
            feature_schema={"numeric_fields": []},
            calibration={"method": "none"},
            metrics={"evaluation_protocol": dict(_valid_protocol_report())},
            data_fingerprints={"fixture": "d" * 64},
            source_schema="cogguard.botrhg.account.v3",
        )
    )

    assert manifest["deployment"] == {"eligible": False, "status": "evaluation_unverified"}


def test_model_bundle_rejects_a_plain_mapping_as_protocol_report(tmp_path):
    encoder = tmp_path / "encoder.bin"
    detector = tmp_path / "detector.bin"
    encoder.write_bytes(b"encoder")
    detector.write_bytes(b"detector")

    report = dict(_valid_protocol_report())
    manifest = load_account_model_bundle(
        write_account_model_bundle(
            tmp_path / "bundle",
            encoder=encoder,
            detector=detector,
            feature_schema={"numeric_fields": []},
            calibration={"method": "none"},
            metrics={"test": {}},
            data_fingerprints={"fixture": "e" * 64},
            source_schema="cogguard.botrhg.account.v3",
            protocol_report=report,
        )
    )

    assert manifest["deployment"] == {"eligible": False, "status": "evaluation_unverified"}


@pytest.mark.parametrize(
    ("source_schema", "status"),
    [
        ("cogguard.botrhg.strict.v1", "legacy_non_deployable"),
        ("cogguard.botrhg.weibo.v1", "bootstrap_compatible"),
        ("cogguard.botrhg.account.v2", "bootstrap_compatible"),
    ],
)
def test_legacy_source_schemas_are_not_deployable(tmp_path, source_schema, status):
    encoder = tmp_path / "encoder.bin"
    detector = tmp_path / "detector.bin"
    encoder.write_bytes(b"encoder")
    detector.write_bytes(b"detector")

    manifest = load_account_model_bundle(
        write_account_model_bundle(
            tmp_path / "bundle",
            encoder=encoder,
            detector=detector,
            feature_schema={"numeric_fields": []},
            calibration={"method": "none"},
            metrics={"test": {}},
            data_fingerprints={"fixture": "b" * 64},
            source_schema=source_schema,
        )
    )

    assert manifest["deployment"] == {"eligible": False, "status": status}


def _valid_protocol_report():
    splits = {
        "train": _protocol_records("train", "2024-01-01T00:00:00Z"),
        "validation": _protocol_records("validation", "2024-02-01T00:00:00Z"),
        "test": _protocol_records("test", "2024-03-01T00:00:00Z"),
    }
    return evaluate_account_protocol(
        splits,
        frozen_holdout_manifest=create_frozen_holdout_manifest(splits["test"]),
    )


def _protocol_records(prefix, timestamp):
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
                "community_id": f"{prefix}-community-{index // 2}",
                "observed_at": timestamp,
                "platform": "weibo" if index % 2 == 0 else "x",
            },
        )
        for index in range(4)
    ]


def _rewrite_manifest_hash(manifest_path, manifest):
    manifest_path.write_text(json.dumps(manifest, sort_keys=True), encoding="utf-8")
    digest = hashlib.sha256(manifest_path.read_bytes()).hexdigest()
    (manifest_path.parent / "manifest.sha256").write_text(f"{digest}  manifest.json\n", encoding="ascii")
