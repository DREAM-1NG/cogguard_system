from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Mapping as MappingABC
from dataclasses import dataclass, field
from pathlib import Path
from types import MappingProxyType
from typing import Any, Mapping

from .contracts import (
    ClusterDetectionBatch,
    ClusterDetectionVerdict,
    DetectionFeatureSchema,
    prediction_input_fingerprint,
)


SOCGFM_CROSS_ATTENTION_ARTIFACT_SCHEMA_VERSION = "cogguard.socgfm-cross-attention-detection-artifact/v1"
SOCGFM_CROSS_ATTENTION_MODEL_VERSION = "socgfm_cross_attention/v1"
SOCGFM_CROSS_ATTENTION_MODEL_ROLE = "primary_socgfm_cross_attention"
SOCGFM_PRECOMPUTED_INFERENCE_MODE = "precomputed_member_probability_cluster_aggregation"
SOCGFM_ACCOUNT_MEMBERSHIP_PROXY_CLAIM_SCOPE = "account_level_io_membership_to_cluster_proxy"
SOCGFM_UNSUPPORTED_GROUP_LEVEL_F1_CLAIM = "group_level_harmful_coordination_f1"
SOCGFM_CLUSTER_AGGREGATION_SCHEMA = DetectionFeatureSchema(
    version="socgfm-cross-attention-cluster-aggregation/v1",
    names=(
        "cluster_size",
        "mean_member_probability",
        "max_member_probability",
        "evidence_coverage",
        "relation_diversity",
        "overall_coordination_score",
    ),
)


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


def _unit_probability(value: Any, field_name: str) -> float:
    result = _finite_float(value, field_name)
    if result < 0.0 or result > 1.0:
        raise ValueError(f"{field_name} must be within [0, 1]")
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


def _freeze_json_value(value: Any, field_name: str) -> Any:
    if isinstance(value, MappingABC):
        return _immutable_scalar_mapping(value, field_name)
    if isinstance(value, (tuple, list)):
        return tuple(_freeze_json_value(item, f"{field_name}[]") for item in value)
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float) and math.isfinite(value):
        return value
    raise ValueError(f"{field_name} values must be finite JSON values")


def _immutable_scalar_mapping(value: Any, field_name: str) -> Mapping[str, Any]:
    if not isinstance(value, MappingABC):
        raise ValueError(f"{field_name} must be a mapping")
    normalized: dict[str, Any] = {}
    for key, item in value.items():
        normalized_key = _required_text(key, f"{field_name} key")
        normalized[normalized_key] = _freeze_json_value(item, f"{field_name}.{normalized_key}")
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


def _sigmoid(value: float) -> float:
    if value >= 0.0:
        return 1.0 / (1.0 + math.exp(-value))
    exponent = math.exp(value)
    return exponent / (1.0 + exponent)


def _plain_mapping(value: Mapping[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, item in value.items():
        if isinstance(item, MappingABC):
            result[key] = _plain_mapping(item)
        elif isinstance(item, tuple):
            result[key] = [
                _plain_mapping(child) if isinstance(child, MappingABC) else child
                for child in item
            ]
        else:
            result[key] = item
    return result


@dataclass(frozen=True, slots=True)
class SocGFMCrossAttentionArtifact:
    feature_schema: DetectionFeatureSchema = SOCGFM_CLUSTER_AGGREGATION_SCHEMA
    cluster_coefficients: tuple[float, ...] = (0.0, 2.0, 1.0, 0.5, 0.5, 1.0)
    cluster_intercept: float = -1.0
    calibrator_slope: float = 1.0
    calibrator_intercept: float = 0.0
    decision_threshold: float = 0.5
    default_account_probability: float = 0.5
    account_probabilities: Mapping[str, float] = field(default_factory=dict)
    aggregation_policy: str = "account_probability_mean_max_plus_stage1_metrics"
    threshold_source: str = "validation_macro_f1"
    checkpoint_reference: str = "unregistered"
    provenance: Mapping[str, Any] = field(default_factory=dict)
    inference_mode: str = SOCGFM_PRECOMPUTED_INFERENCE_MODE
    claim_scope: str = SOCGFM_ACCOUNT_MEMBERSHIP_PROXY_CLAIM_SCOPE
    online_neural_forward: bool = False
    unsupported_claims: tuple[str, ...] = (SOCGFM_UNSUPPORTED_GROUP_LEVEL_F1_CLAIM,)
    source_run_hashes: Mapping[str, Any] = field(default_factory=dict)
    model_version: str = SOCGFM_CROSS_ATTENTION_MODEL_VERSION
    model_role: str = SOCGFM_CROSS_ATTENTION_MODEL_ROLE
    schema_version: str = SOCGFM_CROSS_ATTENTION_ARTIFACT_SCHEMA_VERSION

    _FIELDS = frozenset(
        {
            "schema_version",
            "model_version",
            "model_role",
            "feature_schema",
            "cluster_coefficients",
            "cluster_intercept",
            "calibrator_slope",
            "calibrator_intercept",
            "decision_threshold",
            "default_account_probability",
            "account_probabilities",
            "aggregation_policy",
            "threshold_source",
            "checkpoint_reference",
            "provenance",
            "inference_mode",
            "claim_scope",
            "online_neural_forward",
            "unsupported_claims",
            "source_run_hashes",
            "artifact_hash",
        }
    )

    def __post_init__(self) -> None:
        if self.schema_version != SOCGFM_CROSS_ATTENTION_ARTIFACT_SCHEMA_VERSION:
            raise ValueError(f"unsupported schema_version: {self.schema_version}")
        object.__setattr__(self, "model_version", _required_text(self.model_version, "model_version"))
        if _required_text(self.model_role, "model_role") != SOCGFM_CROSS_ATTENTION_MODEL_ROLE:
            raise ValueError("SocGFM artifact must identify the primary SocGFM CrossAttention role")
        if not isinstance(self.feature_schema, DetectionFeatureSchema):
            raise ValueError("feature_schema must be a DetectionFeatureSchema")
        coefficients = _finite_tuple(self.cluster_coefficients, "cluster_coefficients")
        if len(coefficients) != len(self.feature_schema.names):
            raise ValueError("cluster_coefficients must match feature_schema length")
        object.__setattr__(self, "cluster_coefficients", coefficients)
        for field_name in ("cluster_intercept", "calibrator_slope", "calibrator_intercept"):
            object.__setattr__(self, field_name, _finite_float(getattr(self, field_name), field_name))
        object.__setattr__(self, "decision_threshold", _unit_probability(self.decision_threshold, "decision_threshold"))
        object.__setattr__(
            self,
            "default_account_probability",
            _unit_probability(self.default_account_probability, "default_account_probability"),
        )
        probabilities: dict[str, float] = {}
        if not isinstance(self.account_probabilities, MappingABC):
            raise ValueError("account_probabilities must be a mapping")
        for key, value in self.account_probabilities.items():
            probabilities[_required_text(key, "account_probability key")] = _unit_probability(
                value,
                "account_probability",
            )
        object.__setattr__(self, "account_probabilities", MappingProxyType(dict(sorted(probabilities.items()))))
        object.__setattr__(self, "aggregation_policy", _required_text(self.aggregation_policy, "aggregation_policy"))
        object.__setattr__(self, "threshold_source", _required_text(self.threshold_source, "threshold_source"))
        object.__setattr__(self, "checkpoint_reference", _required_text(self.checkpoint_reference, "checkpoint_reference"))
        object.__setattr__(self, "provenance", _immutable_scalar_mapping(self.provenance, "provenance"))
        if _required_text(self.inference_mode, "inference_mode") != SOCGFM_PRECOMPUTED_INFERENCE_MODE:
            raise ValueError("SocGFM v1 online inference must use precomputed member probability aggregation")
        object.__setattr__(self, "inference_mode", SOCGFM_PRECOMPUTED_INFERENCE_MODE)
        if _required_text(self.claim_scope, "claim_scope") != SOCGFM_ACCOUNT_MEMBERSHIP_PROXY_CLAIM_SCOPE:
            raise ValueError("SocGFM v1 claim_scope must be account-level IO membership to cluster proxy")
        object.__setattr__(self, "claim_scope", SOCGFM_ACCOUNT_MEMBERSHIP_PROXY_CLAIM_SCOPE)
        if self.online_neural_forward is not False:
            raise ValueError("SocGFM v1 online_neural_forward must be false")
        claims = _text_tuple(self.unsupported_claims, "unsupported_claims", sorted_values=True)
        if SOCGFM_UNSUPPORTED_GROUP_LEVEL_F1_CLAIM not in claims:
            raise ValueError("unsupported_claims must include group_level_harmful_coordination_f1")
        object.__setattr__(self, "unsupported_claims", claims)
        source_hashes = _immutable_scalar_mapping(self.source_run_hashes, "source_run_hashes")
        if not source_hashes:
            raise ValueError("source_run_hashes must not be empty")
        object.__setattr__(self, "source_run_hashes", source_hashes)

    def _identity_payload(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "model_version": self.model_version,
            "model_role": self.model_role,
            "feature_schema": self.feature_schema.serialized_dict(),
            "cluster_coefficients": list(self.cluster_coefficients),
            "cluster_intercept": self.cluster_intercept,
            "calibrator_slope": self.calibrator_slope,
            "calibrator_intercept": self.calibrator_intercept,
            "decision_threshold": self.decision_threshold,
            "default_account_probability": self.default_account_probability,
            "account_probabilities": dict(self.account_probabilities),
            "aggregation_policy": self.aggregation_policy,
            "threshold_source": self.threshold_source,
            "checkpoint_reference": self.checkpoint_reference,
            "provenance": _plain_mapping(self.provenance),
            "inference_mode": self.inference_mode,
            "claim_scope": self.claim_scope,
            "online_neural_forward": self.online_neural_forward,
            "unsupported_claims": list(self.unsupported_claims),
            "source_run_hashes": _plain_mapping(self.source_run_hashes),
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
    def from_dict(cls, value: Mapping[str, Any]) -> "SocGFMCrossAttentionArtifact":
        value = _require_fields(value, "SocGFMCrossAttentionArtifact", cls._FIELDS)
        artifact = cls(
            feature_schema=DetectionFeatureSchema.from_dict(value["feature_schema"]),
            cluster_coefficients=tuple(value["cluster_coefficients"]),
            cluster_intercept=value["cluster_intercept"],
            calibrator_slope=value["calibrator_slope"],
            calibrator_intercept=value["calibrator_intercept"],
            decision_threshold=value["decision_threshold"],
            default_account_probability=value["default_account_probability"],
            account_probabilities=value["account_probabilities"],
            aggregation_policy=value["aggregation_policy"],
            threshold_source=value["threshold_source"],
            checkpoint_reference=value["checkpoint_reference"],
            provenance=value["provenance"],
            inference_mode=value["inference_mode"],
            claim_scope=value["claim_scope"],
            online_neural_forward=value["online_neural_forward"],
            unsupported_claims=tuple(value["unsupported_claims"]),
            source_run_hashes=value["source_run_hashes"],
            model_version=value["model_version"],
            model_role=value["model_role"],
            schema_version=value["schema_version"],
        )
        if value["artifact_hash"] != artifact.artifact_hash:
            raise ValueError("artifact_hash does not match artifact payload")
        return artifact

    @classmethod
    def from_json(cls, path: str | Path) -> "SocGFMCrossAttentionArtifact":
        try:
            value = json.loads(Path(path).read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError("SocGFMCrossAttentionArtifact JSON is invalid") from exc
        return cls.from_dict(value)


class SocGFMCrossAttentionDetector:
    __slots__ = ("artifact",)

    def __init__(self, artifact: SocGFMCrossAttentionArtifact) -> None:
        if not isinstance(artifact, SocGFMCrossAttentionArtifact):
            raise ValueError("artifact must be a SocGFMCrossAttentionArtifact")
        self.artifact = artifact

    def predict(
        self,
        batch: Any,
        detection_features: Mapping[str, Mapping[str, float]],
    ) -> ClusterDetectionBatch:
        batch.validate()
        if not isinstance(detection_features, MappingABC):
            raise ValueError("detection_features must be a cluster feature mapping")
        cluster_ids: list[str] = []
        feature_rows: list[tuple[float, ...]] = []
        verdicts: list[ClusterDetectionVerdict] = []
        warnings: dict[str, str | None] = {}
        for cluster in batch.candidate_clusters:
            cluster_id = str(cluster.cluster_id)
            row, warning, member_probability_coverage = self._feature_row(cluster, detection_features.get(cluster_id, {}))
            probability = self._probability(row)
            verdicts.append(
                ClusterDetectionVerdict(
                    cluster_id=cluster_id,
                    decision="harmful_coordination" if probability >= self.artifact.decision_threshold else "benign_coordination",
                    harmful_probability=probability,
                    model_version=self.artifact.model_version,
                    model_role=self.artifact.model_role,
                    artifact_hash=self.artifact.artifact_hash,
                    warning=warning,
                    inference_mode=self.artifact.inference_mode,
                    member_probability_coverage=member_probability_coverage,
                    online_neural_forward=self.artifact.online_neural_forward,
                    claim_scope=self.artifact.claim_scope,
                )
            )
            cluster_ids.append(cluster_id)
            feature_rows.append(row)
            warnings[cluster_id] = warning
        input_fingerprint = prediction_input_fingerprint(
            feature_schema_fingerprint=self.artifact.feature_schema.fingerprint,
            ordered_cluster_ids=cluster_ids,
            feature_matrix=feature_rows,
            stage1_batch_fingerprint=batch.batch_fingerprint,
        )
        digest = hashlib.sha256(
            json.dumps(
                {
                    "artifact_hash": self.artifact.artifact_hash,
                    "prediction_input_fingerprint": input_fingerprint,
                    "warning_count": sum(1 for value in warnings.values() if value),
                },
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()
        return ClusterDetectionBatch(
            batch_id=f"socgfm-detection-sha256:{digest}",
            source_batch_id=batch.batch_id,
            source_batch_fingerprint=batch.batch_fingerprint,
            prediction_input_fingerprint=input_fingerprint,
            model_artifact_hash=self.artifact.artifact_hash,
            verdicts=tuple(verdicts),
            model_role=self.artifact.model_role,
            inference_mode=self.artifact.inference_mode,
            claim_scope=self.artifact.claim_scope,
            online_neural_forward=self.artifact.online_neural_forward,
            runtime_diagnostics={
                "online_neural_forward_executed": False,
                "member_probability_source": "precomputed_artifact",
                "aggregation_policy": self.artifact.aggregation_policy,
                "claim_scope": self.artifact.claim_scope,
            },
        )

    def _feature_row(self, cluster: Any, caller_values: Any) -> tuple[tuple[float, ...], str | None, float]:
        if not isinstance(caller_values, MappingABC):
            raise ValueError(f"detection features for {cluster.cluster_id} must be a mapping")
        members = tuple(str(member) for member in cluster.member_account_ids)
        probabilities = [
            float(self.artifact.account_probabilities.get(member, self.artifact.default_account_probability))
            for member in members
        ]
        missing = sum(1 for member in members if member not in self.artifact.account_probabilities)
        if not probabilities:
            probabilities = [self.artifact.default_account_probability]
        member_probability_coverage = 0.0 if not members else float((len(members) - missing) / len(members))
        metrics = cluster.coordination_metrics
        known = {
            "cluster_size": float(cluster.size),
            "mean_member_probability": float(sum(probabilities) / len(probabilities)),
            "max_member_probability": float(max(probabilities)),
            "min_member_probability": float(min(probabilities)),
            "evidence_coverage": float(metrics.evidence_coverage),
            "relation_diversity": float(metrics.relation_diversity),
            "overall_coordination_score": float(metrics.overall_coordination_score),
            "temporal_sync_delta_seconds": float(metrics.temporal_sync_delta_seconds),
            "tsgs_density": float(metrics.tsgs_spectral_density),
            "mhcr_coherence": float(metrics.mhcr_hyperedge_coherence),
        }
        extras = {str(key): _finite_float(value, f"detection feature {key}") for key, value in caller_values.items()}
        merged = {**known, **extras}
        missing_features = set(self.artifact.feature_schema.names) - set(merged)
        if missing_features:
            raise ValueError(f"SocGFM aggregation schema contains missing feature providers: {sorted(missing_features)}")
        row = tuple(_finite_float(merged[name], name) for name in self.artifact.feature_schema.names)
        warning = None
        if missing:
            warning = "部分成员缺少账号级深度概率，已使用模型产物内的默认概率。"
        return row, warning, member_probability_coverage

    def _probability(self, row: tuple[float, ...]) -> float:
        logit = self.artifact.cluster_intercept + sum(
            coefficient * value
            for coefficient, value in zip(self.artifact.cluster_coefficients, row, strict=True)
        )
        return _unit_probability(
            _sigmoid(self.artifact.calibrator_slope * logit + self.artifact.calibrator_intercept),
            "harmful_probability",
        )


__all__ = [
    "SOCGFM_CLUSTER_AGGREGATION_SCHEMA",
    "SOCGFM_CROSS_ATTENTION_ARTIFACT_SCHEMA_VERSION",
    "SOCGFM_CROSS_ATTENTION_MODEL_ROLE",
    "SOCGFM_CROSS_ATTENTION_MODEL_VERSION",
    "SOCGFM_ACCOUNT_MEMBERSHIP_PROXY_CLAIM_SCOPE",
    "SOCGFM_PRECOMPUTED_INFERENCE_MODE",
    "SOCGFM_UNSUPPORTED_GROUP_LEVEL_F1_CLAIM",
    "SocGFMCrossAttentionArtifact",
    "SocGFMCrossAttentionDetector",
]
