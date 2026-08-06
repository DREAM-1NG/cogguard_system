from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Iterable, Mapping as MappingABC
from dataclasses import dataclass, field
from pathlib import Path
from types import MappingProxyType
from typing import Any, Mapping


DETECTION_ARTIFACT_SCHEMA_VERSION = "cogguard.coordination-detection-artifact/v1"
DETECTION_BATCH_SCHEMA_VERSION = "cogguard.cluster-detection-batch/v1"
LEARNED_MODEL_VERSION = "learned_coordination_logistic_platt/v1"


def _required_text(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string")
    return value.strip()


def _finite_float(value: Any, field_name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{field_name} must be numeric")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"{field_name} must be finite")
    return result


def _finite_tuple(values: Any, field_name: str) -> tuple[float, ...]:
    if not isinstance(values, (tuple, list)):
        raise ValueError(f"{field_name} must be a sequence")
    return tuple(_finite_float(value, field_name) for value in values)


def _text_tuple(values: Any, field_name: str, *, sorted_values: bool = False) -> tuple[str, ...]:
    if not isinstance(values, (tuple, list)):
        raise ValueError(f"{field_name} must be a sequence of strings")
    result = tuple(_required_text(value, field_name) for value in values)
    if len(result) != len(set(result)):
        raise ValueError(f"{field_name} contains duplicate values")
    return tuple(sorted(result)) if sorted_values else result


def _immutable_mapping(value: Any, field_name: str) -> Mapping[str, Any]:
    if not isinstance(value, MappingABC):
        raise ValueError(f"{field_name} must be a mapping")
    normalized: dict[str, Any] = {}
    for key, item in value.items():
        normalized_key = _required_text(key, f"{field_name} key")
        if item is None or isinstance(item, (str, bool, int)):
            normalized_item = item
        elif isinstance(item, float) and math.isfinite(item):
            normalized_item = item
        else:
            raise ValueError(f"{field_name} values must be finite JSON scalars")
        normalized[normalized_key] = normalized_item
    return MappingProxyType(dict(sorted(normalized.items())))


def _require_fields(value: Any, field_name: str, fields: frozenset[str]) -> Mapping[str, Any]:
    if not isinstance(value, MappingABC):
        raise ValueError(f"{field_name} must be a JSON object")
    actual = set(value)
    unknown = actual - fields
    missing = fields - actual
    if unknown:
        raise ValueError(f"{field_name} contains unknown fields: {sorted(unknown)}")
    if missing:
        raise ValueError(f"{field_name} is missing required fields: {sorted(missing)}")
    return value


def _canonical_json(value: Mapping[str, Any]) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _sha256(value: Mapping[str, Any]) -> str:
    return f"sha256:{hashlib.sha256(_canonical_json(value)).hexdigest()}"


def case_id_fingerprint(case_ids: Iterable[str]) -> str:
    normalized = tuple(sorted(_required_text(case_id, "case_id") for case_id in case_ids))
    if not normalized:
        raise ValueError("case IDs must not be empty")
    if len(normalized) != len(set(normalized)):
        raise ValueError("case IDs must be unique")
    return _sha256({"case_ids": list(normalized)})


@dataclass(frozen=True, slots=True)
class DetectionFeatureSchema:
    version: str
    names: tuple[str, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "version", _required_text(self.version, "version"))
        names = _text_tuple(self.names, "names")
        if not names:
            raise ValueError("names must not be empty")
        object.__setattr__(self, "names", names)

    @property
    def fingerprint(self) -> str:
        return _sha256(self.to_dict())

    def to_dict(self) -> dict[str, Any]:
        return {"version": self.version, "names": list(self.names)}

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "DetectionFeatureSchema":
        value = _require_fields(value, "DetectionFeatureSchema", frozenset({"version", "names", "fingerprint"}))
        schema = cls(version=value["version"], names=tuple(value["names"]))
        if value["fingerprint"] != schema.fingerprint:
            raise ValueError("feature schema fingerprint does not match payload")
        return schema

    def serialized_dict(self) -> dict[str, Any]:
        payload = self.to_dict()
        payload["fingerprint"] = self.fingerprint
        return payload

    def validate_case(self, case: "DetectionTrainingCase") -> None:
        if case.feature_schema_version != self.version or case.feature_schema_fingerprint != self.fingerprint:
            raise ValueError("case feature schema does not match detector schema")
        if case.feature_names != self.names:
            raise ValueError("case features do not match the schema's stable ordered names")
        if len(case.feature_values) != len(self.names):
            raise ValueError("case feature values do not match schema length")
        for name, value in zip(self.names, case.feature_values, strict=True):
            _finite_float(value, f"feature {name}")


@dataclass(frozen=True, slots=True)
class DetectionTrainingCase:
    case_id: str
    cluster_id: str
    split: str
    label: int
    feature_schema_version: str
    feature_schema_fingerprint: str
    feature_names: tuple[str, ...]
    feature_values: tuple[float, ...]
    provenance: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "case_id", _required_text(self.case_id, "case_id"))
        object.__setattr__(self, "cluster_id", _required_text(self.cluster_id, "cluster_id"))
        object.__setattr__(self, "split", _required_text(self.split, "split"))
        if isinstance(self.label, bool) or self.label not in (0, 1):
            raise ValueError("label must be 0 or 1")
        object.__setattr__(self, "feature_schema_version", _required_text(self.feature_schema_version, "feature_schema_version"))
        object.__setattr__(self, "feature_schema_fingerprint", _required_text(self.feature_schema_fingerprint, "feature_schema_fingerprint"))
        object.__setattr__(self, "feature_names", _text_tuple(self.feature_names, "feature_names"))
        if not isinstance(self.feature_values, (tuple, list)):
            raise ValueError("feature_values must be a sequence")
        object.__setattr__(self, "feature_values", tuple(self.feature_values))
        object.__setattr__(self, "provenance", _immutable_mapping(self.provenance, "provenance"))


@dataclass(frozen=True, slots=True)
class DetectionModelArtifact:
    feature_schema: DetectionFeatureSchema
    scaler_mean: tuple[float, ...]
    scaler_scale: tuple[float, ...]
    coefficients: tuple[float, ...]
    intercept: float
    calibrator_slope: float
    calibrator_intercept: float
    lower_decision_threshold: float
    upper_decision_threshold: float
    validation_ood_min: tuple[float, ...]
    validation_ood_max: tuple[float, ...]
    optimizer_config: Mapping[str, Any]
    calibrator_config: Mapping[str, Any]
    threshold_objective: str
    train_fit_case_ids_fingerprint: str
    validation_calibration_case_ids_fingerprint: str
    validation_threshold_case_ids_fingerprint: str
    validation_ood_case_ids_fingerprint: str
    model_version: str = LEARNED_MODEL_VERSION
    model_role: str = "primary_learned"
    schema_version: str = DETECTION_ARTIFACT_SCHEMA_VERSION

    _FIELDS = frozenset(
        {
            "schema_version", "model_version", "model_role", "feature_schema",
            "scaler_mean", "scaler_scale", "coefficients", "intercept",
            "calibrator_slope", "calibrator_intercept", "lower_decision_threshold",
            "upper_decision_threshold", "validation_ood_min", "validation_ood_max",
            "optimizer_config", "calibrator_config", "threshold_objective",
            "train_fit_case_ids_fingerprint", "validation_calibration_case_ids_fingerprint",
            "validation_threshold_case_ids_fingerprint", "validation_ood_case_ids_fingerprint",
            "artifact_hash",
        }
    )

    def __post_init__(self) -> None:
        if not isinstance(self.feature_schema, DetectionFeatureSchema):
            raise ValueError("feature_schema must be a DetectionFeatureSchema")
        if self.schema_version != DETECTION_ARTIFACT_SCHEMA_VERSION:
            raise ValueError(f"unsupported schema_version: {self.schema_version}")
        if self.model_version != LEARNED_MODEL_VERSION or self.model_role != "primary_learned":
            raise ValueError("artifact must identify the primary learned model")
        size = len(self.feature_schema.names)
        for field_name in (
            "scaler_mean", "scaler_scale", "coefficients", "validation_ood_min", "validation_ood_max"
        ):
            values = _finite_tuple(getattr(self, field_name), field_name)
            if len(values) != size:
                raise ValueError(f"{field_name} does not match feature schema length")
            object.__setattr__(self, field_name, values)
        if any(value <= 0.0 for value in self.scaler_scale):
            raise ValueError("scaler_scale must be positive")
        if any(low > high for low, high in zip(self.validation_ood_min, self.validation_ood_max, strict=True)):
            raise ValueError("validation OOD minima must not exceed maxima")
        for field_name in ("intercept", "calibrator_slope", "calibrator_intercept"):
            object.__setattr__(self, field_name, _finite_float(getattr(self, field_name), field_name))
        lower = _finite_float(self.lower_decision_threshold, "lower_decision_threshold")
        upper = _finite_float(self.upper_decision_threshold, "upper_decision_threshold")
        if not 0.0 <= lower < upper <= 1.0:
            raise ValueError("decision thresholds must satisfy 0 <= lower < upper <= 1")
        object.__setattr__(self, "lower_decision_threshold", lower)
        object.__setattr__(self, "upper_decision_threshold", upper)
        object.__setattr__(self, "optimizer_config", _immutable_mapping(self.optimizer_config, "optimizer_config"))
        object.__setattr__(self, "calibrator_config", _immutable_mapping(self.calibrator_config, "calibrator_config"))
        object.__setattr__(self, "threshold_objective", _required_text(self.threshold_objective, "threshold_objective"))
        for field_name in (
            "train_fit_case_ids_fingerprint", "validation_calibration_case_ids_fingerprint",
            "validation_threshold_case_ids_fingerprint", "validation_ood_case_ids_fingerprint",
        ):
            object.__setattr__(self, field_name, _required_text(getattr(self, field_name), field_name))

    def _identity_payload(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "model_version": self.model_version,
            "model_role": self.model_role,
            "feature_schema": self.feature_schema.serialized_dict(),
            "scaler_mean": list(self.scaler_mean),
            "scaler_scale": list(self.scaler_scale),
            "coefficients": list(self.coefficients),
            "intercept": self.intercept,
            "calibrator_slope": self.calibrator_slope,
            "calibrator_intercept": self.calibrator_intercept,
            "lower_decision_threshold": self.lower_decision_threshold,
            "upper_decision_threshold": self.upper_decision_threshold,
            "validation_ood_min": list(self.validation_ood_min),
            "validation_ood_max": list(self.validation_ood_max),
            "optimizer_config": dict(self.optimizer_config),
            "calibrator_config": dict(self.calibrator_config),
            "threshold_objective": self.threshold_objective,
            "train_fit_case_ids_fingerprint": self.train_fit_case_ids_fingerprint,
            "validation_calibration_case_ids_fingerprint": self.validation_calibration_case_ids_fingerprint,
            "validation_threshold_case_ids_fingerprint": self.validation_threshold_case_ids_fingerprint,
            "validation_ood_case_ids_fingerprint": self.validation_ood_case_ids_fingerprint,
        }

    @property
    def artifact_hash(self) -> str:
        return _sha256(self._identity_payload())

    def to_dict(self) -> dict[str, Any]:
        payload = self._identity_payload()
        payload["artifact_hash"] = self.artifact_hash
        return payload

    def to_json(self, path: str | Path) -> Path:
        output_path = Path(path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(self.to_dict(), ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n",
            encoding="utf-8",
        )
        return output_path

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "DetectionModelArtifact":
        value = _require_fields(value, "DetectionModelArtifact", cls._FIELDS)
        artifact = cls(
            feature_schema=DetectionFeatureSchema.from_dict(value["feature_schema"]),
            scaler_mean=tuple(value["scaler_mean"]), scaler_scale=tuple(value["scaler_scale"]),
            coefficients=tuple(value["coefficients"]), intercept=value["intercept"],
            calibrator_slope=value["calibrator_slope"], calibrator_intercept=value["calibrator_intercept"],
            lower_decision_threshold=value["lower_decision_threshold"],
            upper_decision_threshold=value["upper_decision_threshold"],
            validation_ood_min=tuple(value["validation_ood_min"]),
            validation_ood_max=tuple(value["validation_ood_max"]),
            optimizer_config=value["optimizer_config"], calibrator_config=value["calibrator_config"],
            threshold_objective=value["threshold_objective"],
            train_fit_case_ids_fingerprint=value["train_fit_case_ids_fingerprint"],
            validation_calibration_case_ids_fingerprint=value["validation_calibration_case_ids_fingerprint"],
            validation_threshold_case_ids_fingerprint=value["validation_threshold_case_ids_fingerprint"],
            validation_ood_case_ids_fingerprint=value["validation_ood_case_ids_fingerprint"],
            model_version=value["model_version"], model_role=value["model_role"],
            schema_version=value["schema_version"],
        )
        if value["artifact_hash"] != artifact.artifact_hash:
            raise ValueError("artifact_hash does not match artifact payload")
        return artifact

    @classmethod
    def from_json(cls, path: str | Path) -> "DetectionModelArtifact":
        try:
            value = json.loads(Path(path).read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError("DetectionModelArtifact JSON is invalid") from exc
        return cls.from_dict(value)


@dataclass(frozen=True, slots=True)
class ClusterDetectionVerdict:
    cluster_id: str
    decision: str
    harmful_probability: float
    model_version: str
    model_role: str
    artifact_hash: str | None = None
    abstain_reason: str | None = None
    ood_features: tuple[str, ...] = ()
    warning: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "cluster_id", _required_text(self.cluster_id, "cluster_id"))
        if self.decision not in {"benign_coordination", "harmful_coordination", "abstain"}:
            raise ValueError("decision is invalid")
        probability = _finite_float(self.harmful_probability, "harmful_probability")
        if not 0.0 <= probability <= 1.0:
            raise ValueError("harmful_probability must be within [0, 1]")
        object.__setattr__(self, "harmful_probability", probability)
        object.__setattr__(self, "model_version", _required_text(self.model_version, "model_version"))
        object.__setattr__(self, "model_role", _required_text(self.model_role, "model_role"))
        object.__setattr__(self, "ood_features", _text_tuple(self.ood_features, "ood_features", sorted_values=True))
        if self.artifact_hash is not None:
            object.__setattr__(self, "artifact_hash", _required_text(self.artifact_hash, "artifact_hash"))
        if self.abstain_reason is not None:
            object.__setattr__(self, "abstain_reason", _required_text(self.abstain_reason, "abstain_reason"))
        if self.warning is not None:
            object.__setattr__(self, "warning", _required_text(self.warning, "warning"))


@dataclass(frozen=True, slots=True)
class ClusterDetectionBatch:
    batch_id: str
    source_batch_id: str
    source_batch_fingerprint: str
    model_artifact_hash: str
    verdicts: tuple[ClusterDetectionVerdict, ...]
    schema_version: str = DETECTION_BATCH_SCHEMA_VERSION
    model_role: str = "primary_learned"

    def __post_init__(self) -> None:
        if self.schema_version != DETECTION_BATCH_SCHEMA_VERSION:
            raise ValueError(f"unsupported schema_version: {self.schema_version}")
        if self.model_role != "primary_learned":
            raise ValueError("ClusterDetectionBatch is reserved for the primary learned model")
        for field_name in ("batch_id", "source_batch_id", "source_batch_fingerprint", "model_artifact_hash"):
            object.__setattr__(self, field_name, _required_text(getattr(self, field_name), field_name))
        if not isinstance(self.verdicts, (tuple, list)) or not all(
            isinstance(verdict, ClusterDetectionVerdict) for verdict in self.verdicts
        ):
            raise ValueError("verdicts must contain ClusterDetectionVerdict values")
        verdicts = tuple(sorted(self.verdicts, key=lambda item: item.cluster_id))
        ids = [verdict.cluster_id for verdict in verdicts]
        if len(ids) != len(set(ids)):
            raise ValueError("verdicts contain duplicate cluster IDs")
        object.__setattr__(self, "verdicts", verdicts)


__all__ = [
    "ClusterDetectionBatch", "ClusterDetectionVerdict", "DETECTION_ARTIFACT_SCHEMA_VERSION",
    "DETECTION_BATCH_SCHEMA_VERSION", "DetectionFeatureSchema", "DetectionModelArtifact",
    "DetectionTrainingCase", "LEARNED_MODEL_VERSION", "case_id_fingerprint",
]
