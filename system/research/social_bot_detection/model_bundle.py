"""Verified, portable artifact bundles for account-detection models."""

from __future__ import annotations

import hashlib
import io
import json
import pickle
import re
import shutil
from pathlib import Path, PurePosixPath
from typing import Any, Mapping

import torch

from .evaluation_protocol import is_protocol_report_payload, is_verified_protocol_report

__all__ = [
    "ModelBundleError",
    "load_account_model_bundle",
    "verify_account_model_bundle",
    "write_account_model_bundle",
]

_BUNDLE_SCHEMA = "cogguard.account-model-bundle.v1"
_MANIFEST_NAME = "manifest.json"
_MANIFEST_HASH_NAME = "manifest.sha256"
_REQUIRED_ARTIFACTS = (
    "encoder",
    "detector",
    "feature_schema",
    "calibration",
    "metrics",
    "data_fingerprints",
)
_REQUIRED_COMPONENTS = ("encoder", "detector", "feature_schema", "calibration")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_DEPLOYABLE_SOURCE_SCHEMA = "cogguard.botrhg.account.v3"
_LEGACY_SCHEMAS = {
    "cogguard.botrhg.strict.v1": "legacy_non_deployable",
    "cogguard.botrhg.weibo.v1": "bootstrap_compatible",
    "cogguard.botrhg.account.v2": "bootstrap_compatible",
}
_KNOWN_SOURCE_SCHEMAS = frozenset({_DEPLOYABLE_SOURCE_SCHEMA, *_LEGACY_SCHEMAS})


class ModelBundleError(ValueError):
    """Raised when a model bundle cannot be trusted for use."""


def write_account_model_bundle(
    output_dir: str | Path,
    *,
    encoder: str | Path,
    detector: str | Path,
    feature_schema: Mapping[str, Any],
    calibration: Mapping[str, Any],
    metrics: Mapping[str, Any],
    data_fingerprints: Mapping[str, str],
    source_schema: str,
    protocol_report: Mapping[str, Any] | None = None,
) -> Path:
    """Create an immutable-layout account-model bundle and its integrity manifest."""

    source_schema = _validate_source_schema(source_schema)
    bundle_dir = Path(output_dir).resolve()
    bundle_dir.mkdir(parents=True, exist_ok=True)
    if any(bundle_dir.iterdir()):
        raise ModelBundleError("bundle output directory must be empty")
    encoder_path = _require_input_file(encoder, "encoder")
    detector_path = _require_input_file(detector, "detector")
    _require_mapping(feature_schema, "feature_schema")
    _require_mapping(calibration, "calibration")
    _require_mapping(metrics, "metrics")
    _validate_data_fingerprints(data_fingerprints)
    metrics_payload = dict(metrics)
    # Evaluation evidence must come from the explicit protocol argument.
    metrics_payload.pop("evaluation_protocol", None)
    if is_verified_protocol_report(protocol_report):
        metrics_payload["evaluation_protocol"] = dict(protocol_report)

    artifacts = {
        "encoder": _copy_artifact(encoder_path, bundle_dir, "encoder"),
        "detector": _copy_artifact(detector_path, bundle_dir, "detector"),
        "feature_schema": "feature_schema.json",
        "calibration": "calibration.json",
        "metrics": "metrics.json",
        "data_fingerprints": "data_fingerprints.json",
    }
    _write_json(bundle_dir / artifacts["feature_schema"], dict(feature_schema))
    _write_json(bundle_dir / artifacts["calibration"], dict(calibration))
    _write_json(bundle_dir / artifacts["metrics"], metrics_payload)
    _write_json(bundle_dir / artifacts["data_fingerprints"], dict(data_fingerprints))
    files = {relative_path: _file_sha256(bundle_dir / relative_path) for relative_path in artifacts.values()}
    components = _component_manifest(
        artifacts,
        files,
        source_schema=source_schema,
        feature_schema=feature_schema,
        calibration=calibration,
    )
    manifest = {
        "schema": _BUNDLE_SCHEMA,
        "source_schema": source_schema,
        "deployment": _deployment_status(source_schema, protocol_report),
        "artifacts": artifacts,
        "files": dict(sorted(files.items())),
        "components": components,
    }
    manifest_path = bundle_dir / _MANIFEST_NAME
    _write_json(manifest_path, manifest)
    (bundle_dir / _MANIFEST_HASH_NAME).write_text(f"{_file_sha256(manifest_path)}  {_MANIFEST_NAME}\n", encoding="ascii")
    return manifest_path


def load_account_model_bundle(bundle: str | Path) -> dict[str, Any]:
    """Load a bundle only after every declared file passes integrity checks."""

    return verify_account_model_bundle(bundle)


def verify_account_model_bundle(bundle: str | Path) -> dict[str, Any]:
    """Validate bundle paths, declared contents, and SHA-256 values fail closed."""

    bundle_path = Path(bundle)
    bundle_dir = bundle_path if bundle_path.is_dir() else bundle_path.parent
    bundle_dir = bundle_dir.resolve()
    manifest_path = bundle_dir / _MANIFEST_NAME
    if not manifest_path.is_file():
        raise ModelBundleError("bundle manifest is missing")
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ModelBundleError("bundle manifest is unreadable") from error
    _validate_manifest_structure(manifest, bundle_dir)
    _verify_manifest_hash(bundle_dir, manifest_path)
    _verify_declared_files(manifest, bundle_dir)
    _verify_no_unlisted_files(manifest, bundle_dir)
    _verify_deployment_policy(manifest, bundle_dir)
    return manifest


def _validate_manifest_structure(manifest: Any, bundle_dir: Path) -> None:
    if not isinstance(manifest, dict) or manifest.get("schema") != _BUNDLE_SCHEMA:
        raise ModelBundleError("unsupported account model bundle")
    _validate_source_schema(manifest.get("source_schema"))
    artifacts = manifest.get("artifacts")
    files = manifest.get("files")
    deployment = manifest.get("deployment")
    components = manifest.get("components")
    if not isinstance(artifacts, dict) or set(artifacts) != set(_REQUIRED_ARTIFACTS):
        raise ModelBundleError("bundle manifest has incomplete artifacts")
    if not isinstance(files, dict) or not files:
        raise ModelBundleError("bundle manifest has no file hashes")
    if not isinstance(deployment, dict) or not isinstance(deployment.get("eligible"), bool) or not isinstance(deployment.get("status"), str):
        raise ModelBundleError("bundle manifest has invalid deployment status")
    if not isinstance(components, dict) or set(components) != set(_REQUIRED_COMPONENTS):
        raise ModelBundleError("bundle manifest has incomplete component metadata")
    for name, relative_path in artifacts.items():
        if not isinstance(relative_path, str):
            raise ModelBundleError(f"bundle artifact {name} has an invalid path")
        _resolve_bundle_path(bundle_dir, relative_path)
        if relative_path not in files:
            raise ModelBundleError(f"bundle artifact {name} has no SHA-256 entry")
    for relative_path, digest in files.items():
        _resolve_bundle_path(bundle_dir, relative_path)
        if not isinstance(digest, str) or not _SHA256.fullmatch(digest):
            raise ModelBundleError(f"bundle file {relative_path!r} has an invalid SHA-256")
    if set(artifacts.values()) != set(files):
        raise ModelBundleError("bundle file hash entries do not exactly match artifacts")
    _validate_component_manifest(manifest, bundle_dir)


def _verify_manifest_hash(bundle_dir: Path, manifest_path: Path) -> None:
    hash_path = bundle_dir / _MANIFEST_HASH_NAME
    if not hash_path.is_file():
        raise ModelBundleError("bundle manifest SHA-256 is missing")
    expected = hash_path.read_text(encoding="ascii").strip().split(maxsplit=1)
    if len(expected) != 2 or expected[1] != _MANIFEST_NAME or not _SHA256.fullmatch(expected[0]):
        raise ModelBundleError("bundle manifest SHA-256 is malformed")
    if _file_sha256(manifest_path) != expected[0]:
        raise ModelBundleError("bundle manifest SHA-256 mismatch")


def _verify_declared_files(manifest: Mapping[str, Any], bundle_dir: Path) -> None:
    for relative_path, expected_digest in manifest["files"].items():
        artifact_path = _resolve_bundle_path(bundle_dir, relative_path)
        if not artifact_path.is_file():
            raise ModelBundleError(f"bundle artifact is missing: {relative_path}")
        if _file_sha256(artifact_path) != expected_digest:
            raise ModelBundleError(f"bundle artifact SHA-256 mismatch: {relative_path}")


def _verify_no_unlisted_files(manifest: Mapping[str, Any], bundle_dir: Path) -> None:
    expected = set(manifest["files"]) | {_MANIFEST_NAME, _MANIFEST_HASH_NAME}
    found = {
        path.relative_to(bundle_dir).as_posix()
        for path in bundle_dir.rglob("*")
        if path.is_file()
    }
    if found != expected:
        raise ModelBundleError("bundle contains unlisted or missing files")


def _verify_deployment_policy(manifest: Mapping[str, Any], bundle_dir: Path) -> None:
    metrics_path = _resolve_bundle_path(bundle_dir, manifest["artifacts"]["metrics"])
    try:
        metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ModelBundleError("bundle metrics are unreadable") from error
    if not isinstance(metrics, dict):
        raise ModelBundleError("bundle metrics must be an object")
    if manifest["deployment"] != _deployment_status(
        str(manifest.get("source_schema") or ""),
        metrics.get("evaluation_protocol"),
        require_origin=False,
    ):
        raise ModelBundleError("bundle deployment status does not match verified evaluation protocol")
    if manifest["deployment"].get("eligible") is True:
        _verify_deployable_detector_text_assets(manifest, bundle_dir)


def _verify_deployable_detector_text_assets(manifest: Mapping[str, Any], bundle_dir: Path) -> None:
    detector_path = _resolve_bundle_path(bundle_dir, manifest["artifacts"]["detector"])
    try:
        detector = torch.load(io.BytesIO(detector_path.read_bytes()), map_location="cpu", weights_only=True)
        assets = detector.get("text_runtime_assets") if isinstance(detector, Mapping) else None
        if detector.get("schema") != manifest.get("source_schema") or not isinstance(assets, Mapping):
            raise ValueError("invalid detector payload")
        total_size = 0
        normalized_names: set[str] = set()
        for relative_value, payload in assets.items():
            relative = str(relative_value)
            path = PurePosixPath(relative)
            if not relative or path.is_absolute() or ".." in path.parts or "\\" in relative:
                raise ValueError("unsafe text runtime asset path")
            if not isinstance(payload, bytes) or not payload:
                raise ValueError("empty text runtime asset")
            if path.name in {"model.safetensors", "pytorch_model.bin"}:
                raise ValueError("duplicated model weights")
            total_size += len(payload)
            normalized_names.add(path.as_posix())
        if total_size > 64 * 1024 * 1024 or "config.json" not in normalized_names:
            raise ValueError("incomplete text runtime assets")
        tokenizer_files = {"tokenizer.json", "vocab.txt", "spiece.model", "sentencepiece.bpe.model", "merges.txt"}
        if not tokenizer_files.intersection(normalized_names):
            raise ValueError("missing tokenizer vocabulary")
    except (EOFError, KeyError, OSError, pickle.UnpicklingError, RuntimeError, TypeError, ValueError) as error:
        raise ModelBundleError("deployable detector has no verified text runtime assets") from error


def _component_manifest(
    artifacts: Mapping[str, str],
    files: Mapping[str, str],
    *,
    source_schema: str,
    feature_schema: Mapping[str, Any],
    calibration: Mapping[str, Any],
) -> dict[str, dict[str, Any]]:
    """Bind runtime components to their exact artifacts and compatible metadata."""

    feature_payload = _normalized_feature_schema(feature_schema)
    calibration_payload = _normalized_calibration(calibration)
    feature_digest = _canonical_sha256(feature_payload)
    detector_digest = files[artifacts["detector"]]
    return {
        "encoder": {
            "artifact": artifacts["encoder"],
            "sha256": files[artifacts["encoder"]],
            "role": "encoder",
            "source_schema": source_schema,
        },
        "detector": {
            "artifact": artifacts["detector"],
            "sha256": detector_digest,
            "role": "detector",
            "source_schema": source_schema,
            "encoder_sha256": files[artifacts["encoder"]],
            "feature_schema_sha256": feature_digest,
        },
        "feature_schema": {
            "artifact": artifacts["feature_schema"],
            "sha256": files[artifacts["feature_schema"]],
            "role": "feature_schema",
            "content_sha256": feature_digest,
            "numeric_field_count": len(feature_payload.get("numeric_fields", [])),
            "categorical_field_count": len(feature_payload.get("categorical_fields", [])),
        },
        "calibration": {
            "artifact": artifacts["calibration"],
            "sha256": files[artifacts["calibration"]],
            "role": "calibration",
            "content_sha256": _canonical_sha256(calibration_payload),
            "method": calibration_payload["method"],
            "detector_sha256": detector_digest,
        },
    }


def _validate_component_manifest(manifest: Mapping[str, Any], bundle_dir: Path) -> None:
    artifacts = manifest["artifacts"]
    files = manifest["files"]
    components = manifest["components"]
    source_schema = str(manifest.get("source_schema") or "")

    for name in _REQUIRED_COMPONENTS:
        component = components[name]
        if not isinstance(component, Mapping):
            raise ModelBundleError(f"bundle component {name} is invalid")
        if component.get("artifact") != artifacts[name] or component.get("sha256") != files[artifacts[name]]:
            raise ModelBundleError(f"bundle component {name} is not bound to its artifact")
        if component.get("role") != name:
            raise ModelBundleError(f"bundle component {name} has an invalid role")

    encoder = components["encoder"]
    detector = components["detector"]
    feature_component = components["feature_schema"]
    calibration_component = components["calibration"]
    if encoder.get("source_schema") != source_schema or detector.get("source_schema") != source_schema:
        raise ModelBundleError("bundle model components have incompatible source schemas")
    if detector.get("encoder_sha256") != encoder["sha256"]:
        raise ModelBundleError("bundle detector is not bound to the declared encoder")

    feature_schema = _read_json_mapping(bundle_dir, artifacts["feature_schema"], "feature schema")
    normalized_feature_schema = _normalized_feature_schema(feature_schema)
    feature_digest = _canonical_sha256(normalized_feature_schema)
    if feature_component.get("content_sha256") != feature_digest:
        raise ModelBundleError("bundle feature schema content fingerprint mismatch")
    if detector.get("feature_schema_sha256") != feature_digest:
        raise ModelBundleError("bundle detector is not bound to the declared feature schema")
    if feature_component.get("numeric_field_count") != len(normalized_feature_schema.get("numeric_fields", [])):
        raise ModelBundleError("bundle feature schema numeric field count mismatch")
    if feature_component.get("categorical_field_count") != len(normalized_feature_schema.get("categorical_fields", [])):
        raise ModelBundleError("bundle feature schema categorical field count mismatch")

    calibration = _read_json_mapping(bundle_dir, artifacts["calibration"], "calibration")
    normalized_calibration = _normalized_calibration(calibration)
    if calibration_component.get("content_sha256") != _canonical_sha256(normalized_calibration):
        raise ModelBundleError("bundle calibration content fingerprint mismatch")
    if calibration_component.get("method") != normalized_calibration["method"]:
        raise ModelBundleError("bundle calibration method mismatch")
    if calibration_component.get("detector_sha256") != detector["sha256"]:
        raise ModelBundleError("bundle calibration is not bound to the declared detector")


def _read_json_mapping(bundle_dir: Path, relative_path: str, label: str) -> Mapping[str, Any]:
    try:
        value = json.loads(_resolve_bundle_path(bundle_dir, relative_path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ModelBundleError(f"bundle {label} is unreadable") from error
    if not isinstance(value, Mapping):
        raise ModelBundleError(f"bundle {label} must be an object")
    return value


def _normalized_feature_schema(value: Mapping[str, Any]) -> dict[str, Any]:
    """Keep the feature boundary explicit and reject label-derived proxy fields."""

    _require_mapping(value, "feature_schema")
    normalized: dict[str, Any] = {str(key): item for key, item in value.items()}
    for field_name in ("numeric_fields", "categorical_fields"):
        if field_name not in normalized:
            continue
        fields = normalized[field_name]
        if not isinstance(fields, (list, tuple)) or any(not isinstance(item, str) or not item.strip() for item in fields):
            raise ModelBundleError(f"feature_schema.{field_name} must be a list of non-empty field names")
        if len(fields) != len(set(fields)):
            raise ModelBundleError(f"feature_schema.{field_name} contains duplicate fields")
        if any(item.strip().lower() in {"label", "source_label"} for item in fields):
            raise ModelBundleError("feature_schema contains a label-derived proxy field")
        normalized[field_name] = list(fields)
    vocabulary = normalized.get("categorical_vocab")
    if vocabulary is not None:
        if not isinstance(vocabulary, Mapping):
            raise ModelBundleError("feature_schema.categorical_vocab must be an object")
        normalized_vocab: dict[str, list[str]] = {}
        for field_name, values in vocabulary.items():
            if not isinstance(field_name, str) or field_name.strip().lower() in {"label", "source_label"}:
                raise ModelBundleError("feature_schema contains a label-derived proxy field")
            if not isinstance(values, (list, tuple)) or any(not isinstance(item, str) for item in values):
                raise ModelBundleError("feature_schema categorical vocabularies must contain strings")
            normalized_vocab[field_name] = list(values)
        normalized["categorical_vocab"] = normalized_vocab
    return normalized


def _normalized_calibration(value: Mapping[str, Any]) -> dict[str, Any]:
    _require_mapping(value, "calibration")
    method = value.get("method")
    if not isinstance(method, str) or not method.strip():
        raise ModelBundleError("calibration.method must be a non-empty string")
    normalized = {str(key): item for key, item in value.items()}
    normalized["method"] = method.strip()
    return normalized


def _canonical_sha256(value: Any) -> str:
    encoded = json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _resolve_bundle_path(bundle_dir: Path, relative_path: str) -> Path:
    if "\\" in relative_path:
        raise ModelBundleError("bundle artifact path must use relative POSIX form")
    path = PurePosixPath(relative_path)
    if not relative_path or path.is_absolute() or ".." in path.parts or "." in path.parts:
        raise ModelBundleError("bundle artifact path escapes the bundle")
    resolved = (bundle_dir / Path(*path.parts)).resolve()
    try:
        resolved.relative_to(bundle_dir)
    except ValueError as error:
        raise ModelBundleError("bundle artifact path escapes the bundle") from error
    return resolved


def _copy_artifact(source: Path, bundle_dir: Path, role: str) -> str:
    suffix = source.suffix if source.suffix else ".bin"
    relative_path = f"{role}{suffix}"
    shutil.copyfile(source, bundle_dir / relative_path)
    return relative_path


def _require_input_file(path: str | Path, name: str) -> Path:
    source = Path(path).resolve()
    if not source.is_file():
        raise ModelBundleError(f"{name} artifact must be an existing file")
    return source


def _require_mapping(value: Mapping[str, Any], name: str) -> None:
    if not isinstance(value, Mapping):
        raise ModelBundleError(f"{name} must be a mapping")


def _validate_data_fingerprints(value: Mapping[str, str]) -> None:
    _require_mapping(value, "data_fingerprints")
    if not value or any(not str(name).strip() or not str(fingerprint).strip() for name, fingerprint in value.items()):
        raise ModelBundleError("data_fingerprints must contain non-empty dataset fingerprints")


def _validate_source_schema(source_schema: Any) -> str:
    normalized = str(source_schema or "").strip()
    if normalized not in _KNOWN_SOURCE_SCHEMAS:
        raise ModelBundleError(f"unsupported detector source schema: {normalized or '<empty>'}")
    return normalized


def _deployment_status(
    source_schema: str,
    protocol_report: Mapping[str, Any] | None,
    *,
    require_origin: bool = True,
) -> dict[str, Any]:
    status = _LEGACY_SCHEMAS.get(source_schema)
    if status is not None:
        return {"eligible": False, "status": status}
    expected_gates = {
        "account_disjoint",
        "event_disjoint",
        "community_disjoint",
        "time_forward",
        "platform_stratified",
        "frozen_holdout",
    }
    if (
        isinstance(protocol_report, Mapping)
        and (is_verified_protocol_report(protocol_report) if require_origin else is_protocol_report_payload(protocol_report))
        and protocol_report.get("schema") == "cogguard.account-evaluation-protocol.v1"
        and protocol_report.get("activation_allowed") is True
        and isinstance(protocol_report.get("gates"), Mapping)
        and expected_gates.issubset(protocol_report["gates"])
        and all(protocol_report["gates"][gate] is True for gate in expected_gates)
    ):
        return {"eligible": True, "status": "eligible"}
    return {"eligible": False, "status": "evaluation_unverified"}


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=True, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()
