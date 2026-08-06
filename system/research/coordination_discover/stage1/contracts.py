from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from types import MappingProxyType
from typing import Any, Mapping


DISCOVERED_CLUSTER_BATCH_SCHEMA_VERSION = "cogguard.discovered-cluster-batch/v1"
DISCOVERY_STAGE = "coordination_discovery"
DISCOVERY_CLAIM_ROLE = "unsupervised_candidate_clusters"
STAGE1_LABEL_POLICY = "stage1_label_free"


def _required_text(value: Any, field_name: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{field_name} must be a non-empty string")
    return text


def _unit_interval(value: Any, field_name: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field_name} must be numeric") from exc
    if not math.isfinite(number) or not 0.0 <= number <= 1.0:
        raise ValueError(f"{field_name} must be finite and within [0, 1]")
    return number


def _non_negative(value: Any, field_name: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field_name} must be numeric") from exc
    if not math.isfinite(number) or number < 0.0:
        raise ValueError(f"{field_name} must be finite and non-negative")
    return number


def _utc_timestamp(value: Any, field_name: str) -> str:
    text = _required_text(value, field_name)
    normalized = f"{text[:-1]}+00:00" if text.endswith("Z") else text
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise ValueError(f"{field_name} must be an ISO-8601 timestamp") from exc
    if parsed.tzinfo is None:
        raise ValueError(f"{field_name} must include a timezone")
    return text


def _sorted_unique_text(values: Any, field_name: str, *, allow_empty: bool = True) -> tuple[str, ...]:
    if values is None:
        values = ()
    if isinstance(values, (str, bytes)):
        raise ValueError(f"{field_name} must be a sequence of strings")
    normalized = tuple(sorted({_required_text(value, field_name) for value in values}))
    if not allow_empty and not normalized:
        raise ValueError(f"{field_name} must contain at least one value")
    return normalized


def _json_mapping(value: Any, field_name: str) -> Mapping[str, Any]:
    if value is None:
        return MappingProxyType({})
    if not isinstance(value, Mapping):
        raise ValueError(f"{field_name} must be a JSON object")
    try:
        normalized = json.loads(json.dumps(dict(value), ensure_ascii=False, sort_keys=True, allow_nan=False))
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field_name} must contain JSON-serializable finite values") from exc
    return MappingProxyType(normalized)


def _canonical_json(value: Mapping[str, Any]) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


@dataclass(frozen=True, slots=True)
class CoordinationMetricSet:
    tsgs_spectral_density: float
    mhcr_hyperedge_coherence: float
    temporal_sync_delta_seconds: float
    overall_coordination_score: float
    evidence_coverage: float = 0.0
    relation_diversity: float = 0.0

    def __post_init__(self) -> None:
        for field_name in (
            "tsgs_spectral_density",
            "mhcr_hyperedge_coherence",
            "overall_coordination_score",
            "evidence_coverage",
            "relation_diversity",
        ):
            object.__setattr__(self, field_name, _unit_interval(getattr(self, field_name), field_name))
        object.__setattr__(
            self,
            "temporal_sync_delta_seconds",
            _non_negative(self.temporal_sync_delta_seconds, "temporal_sync_delta_seconds"),
        )

    def validate(self) -> None:
        self.__post_init__()

    def to_dict(self) -> dict[str, float | str]:
        return {
            "tsgs_spectral_density": self.tsgs_spectral_density,
            "mhcr_hyperedge_coherence": self.mhcr_hyperedge_coherence,
            "temporal_sync_delta_seconds": self.temporal_sync_delta_seconds,
            "overall_coordination_score": self.overall_coordination_score,
            "overall_coordination_score_role": "unsupervised_ranking_not_probability",
            "evidence_coverage": self.evidence_coverage,
            "relation_diversity": self.relation_diversity,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "CoordinationMetricSet":
        if not isinstance(value, Mapping):
            raise ValueError("coordination_metrics must be a JSON object")
        return cls(
            tsgs_spectral_density=value.get("tsgs_spectral_density"),
            mhcr_hyperedge_coherence=value.get("mhcr_hyperedge_coherence"),
            temporal_sync_delta_seconds=value.get("temporal_sync_delta_seconds"),
            overall_coordination_score=value.get("overall_coordination_score"),
            evidence_coverage=value.get("evidence_coverage", 0.0),
            relation_diversity=value.get("relation_diversity", 0.0),
        )


@dataclass(frozen=True, slots=True)
class DiscoveredCluster:
    cluster_id: str
    member_account_ids: tuple[str, ...]
    coordination_metrics: CoordinationMetricSet
    evidence_refs: tuple[str, ...] = ()
    sparsified_subgraph_ref: str | None = None
    embedding_ref: str | None = None
    artifact_hashes: Mapping[str, str] = field(default_factory=dict)
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "cluster_id", _required_text(self.cluster_id, "cluster_id"))
        object.__setattr__(
            self,
            "member_account_ids",
            _sorted_unique_text(self.member_account_ids, "member_account_ids", allow_empty=False),
        )
        if not isinstance(self.coordination_metrics, CoordinationMetricSet):
            raise ValueError("coordination_metrics must be a CoordinationMetricSet")
        self.coordination_metrics.validate()
        object.__setattr__(self, "evidence_refs", _sorted_unique_text(self.evidence_refs, "evidence_refs"))
        for field_name in ("sparsified_subgraph_ref", "embedding_ref"):
            value = getattr(self, field_name)
            if value is not None:
                object.__setattr__(self, field_name, _required_text(value, field_name))
        hashes = {
            _required_text(key, "artifact_hashes key"): _required_text(item, "artifact_hashes value")
            for key, item in dict(self.artifact_hashes).items()
        }
        object.__setattr__(self, "artifact_hashes", MappingProxyType(dict(sorted(hashes.items()))))
        object.__setattr__(self, "metadata", _json_mapping(self.metadata, "metadata"))

    @property
    def size(self) -> int:
        return len(self.member_account_ids)

    def validate(self) -> None:
        self.__post_init__()

    def to_dict(self) -> dict[str, Any]:
        return {
            "cluster_id": self.cluster_id,
            "size": self.size,
            "member_account_ids": list(self.member_account_ids),
            "coordination_metrics": self.coordination_metrics.to_dict(),
            "evidence_refs": list(self.evidence_refs),
            "sparsified_subgraph_ref": self.sparsified_subgraph_ref,
            "embedding_ref": self.embedding_ref,
            "artifact_hashes": dict(self.artifact_hashes),
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "DiscoveredCluster":
        if not isinstance(value, Mapping):
            raise ValueError("candidate cluster must be a JSON object")
        member_ids = _sorted_unique_text(value.get("member_account_ids"), "member_account_ids", allow_empty=False)
        declared_size = value.get("size")
        if declared_size is not None:
            try:
                size = int(declared_size)
            except (TypeError, ValueError) as exc:
                raise ValueError("cluster size must be an integer") from exc
            if size != len(member_ids):
                raise ValueError("cluster size does not match unique member_account_ids")
        return cls(
            cluster_id=value.get("cluster_id"),
            member_account_ids=member_ids,
            coordination_metrics=CoordinationMetricSet.from_dict(value.get("coordination_metrics", {})),
            evidence_refs=tuple(value.get("evidence_refs") or ()),
            sparsified_subgraph_ref=value.get("sparsified_subgraph_ref"),
            embedding_ref=value.get("embedding_ref"),
            artifact_hashes=value.get("artifact_hashes") or {},
            metadata=value.get("metadata") or {},
        )


@dataclass(frozen=True, slots=True)
class DiscoveryProvenance:
    snapshot_id: str
    data_fingerprint: str
    source_dataset: str
    source_event: str
    stage1_model_version: str
    tsgs_version: str
    mhcr_version: str
    created_at: str
    seed: int
    split_policy: str
    label_policy: str = STAGE1_LABEL_POLICY
    method_metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for field_name in (
            "snapshot_id",
            "data_fingerprint",
            "source_dataset",
            "source_event",
            "stage1_model_version",
            "tsgs_version",
            "mhcr_version",
            "split_policy",
        ):
            object.__setattr__(self, field_name, _required_text(getattr(self, field_name), field_name))
        object.__setattr__(self, "created_at", _utc_timestamp(self.created_at, "created_at"))
        try:
            object.__setattr__(self, "seed", int(self.seed))
        except (TypeError, ValueError) as exc:
            raise ValueError("seed must be an integer") from exc
        if self.label_policy != STAGE1_LABEL_POLICY:
            raise ValueError(f"label_policy must be {STAGE1_LABEL_POLICY}")
        object.__setattr__(self, "method_metadata", _json_mapping(self.method_metadata, "method_metadata"))

    def validate(self) -> None:
        self.__post_init__()

    def to_dict(self) -> dict[str, Any]:
        return {
            "snapshot_id": self.snapshot_id,
            "data_fingerprint": self.data_fingerprint,
            "source_dataset": self.source_dataset,
            "source_event": self.source_event,
            "stage1_model_version": self.stage1_model_version,
            "tsgs_version": self.tsgs_version,
            "mhcr_version": self.mhcr_version,
            "created_at": self.created_at,
            "seed": self.seed,
            "split_policy": self.split_policy,
            "label_policy": self.label_policy,
            "method_metadata": dict(self.method_metadata),
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "DiscoveryProvenance":
        if not isinstance(value, Mapping):
            raise ValueError("provenance must be a JSON object")
        return cls(
            snapshot_id=value.get("snapshot_id"),
            data_fingerprint=value.get("data_fingerprint"),
            source_dataset=value.get("source_dataset"),
            source_event=value.get("source_event"),
            stage1_model_version=value.get("stage1_model_version"),
            tsgs_version=value.get("tsgs_version"),
            mhcr_version=value.get("mhcr_version"),
            created_at=value.get("created_at"),
            seed=value.get("seed"),
            split_policy=value.get("split_policy"),
            label_policy=value.get("label_policy", STAGE1_LABEL_POLICY),
            method_metadata=value.get("method_metadata") or {},
        )


@dataclass(frozen=True, slots=True)
class DiscoveredClusterBatch:
    batch_id: str
    timestamp: str
    candidate_clusters: tuple[DiscoveredCluster, ...]
    provenance: DiscoveryProvenance
    metadata: Mapping[str, Any] = field(default_factory=dict)
    schema_version: str = DISCOVERED_CLUSTER_BATCH_SCHEMA_VERSION
    stage: str = DISCOVERY_STAGE
    claim_role: str = DISCOVERY_CLAIM_ROLE

    def __post_init__(self) -> None:
        if self.schema_version != DISCOVERED_CLUSTER_BATCH_SCHEMA_VERSION:
            raise ValueError(f"unsupported schema_version: {self.schema_version}")
        if self.stage != DISCOVERY_STAGE:
            raise ValueError(f"stage must be {DISCOVERY_STAGE}")
        if self.claim_role != DISCOVERY_CLAIM_ROLE:
            raise ValueError(f"claim_role must be {DISCOVERY_CLAIM_ROLE}")
        object.__setattr__(self, "batch_id", _required_text(self.batch_id, "batch_id"))
        object.__setattr__(self, "timestamp", _utc_timestamp(self.timestamp, "timestamp"))
        clusters = tuple(sorted(tuple(self.candidate_clusters), key=lambda item: item.cluster_id))
        if not all(isinstance(cluster, DiscoveredCluster) for cluster in clusters):
            raise ValueError("candidate_clusters must contain DiscoveredCluster values")
        cluster_ids = [cluster.cluster_id for cluster in clusters]
        if len(cluster_ids) != len(set(cluster_ids)):
            raise ValueError("duplicate cluster_id in candidate_clusters")
        for cluster in clusters:
            cluster.validate()
        object.__setattr__(self, "candidate_clusters", clusters)
        if not isinstance(self.provenance, DiscoveryProvenance):
            raise ValueError("provenance must be a DiscoveryProvenance")
        self.provenance.validate()
        object.__setattr__(self, "metadata", _json_mapping(self.metadata, "metadata"))

    @property
    def batch_fingerprint(self) -> str:
        return f"sha256:{hashlib.sha256(_canonical_json(self._payload_without_fingerprint())).hexdigest()}"

    def validate(self) -> None:
        self.__post_init__()

    def _payload_without_fingerprint(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "stage": self.stage,
            "claim_role": self.claim_role,
            "batch_id": self.batch_id,
            "timestamp": self.timestamp,
            "candidate_clusters": [cluster.to_dict() for cluster in self.candidate_clusters],
            "provenance": self.provenance.to_dict(),
            "metadata": dict(self.metadata),
        }

    def to_dict(self) -> dict[str, Any]:
        payload = self._payload_without_fingerprint()
        payload["batch_fingerprint"] = self.batch_fingerprint
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
    def from_dict(cls, value: Mapping[str, Any]) -> "DiscoveredClusterBatch":
        if not isinstance(value, Mapping):
            raise ValueError("DiscoveredClusterBatch must be a JSON object")
        schema_version = value.get("schema_version")
        if schema_version != DISCOVERED_CLUSTER_BATCH_SCHEMA_VERSION:
            raise ValueError(f"unsupported schema_version: {schema_version}")
        batch = cls(
            batch_id=value.get("batch_id"),
            timestamp=value.get("timestamp"),
            candidate_clusters=tuple(
                DiscoveredCluster.from_dict(item) for item in value.get("candidate_clusters") or ()
            ),
            provenance=DiscoveryProvenance.from_dict(value.get("provenance") or {}),
            metadata=value.get("metadata") or {},
            schema_version=schema_version,
            stage=value.get("stage"),
            claim_role=value.get("claim_role"),
        )
        declared_fingerprint = value.get("batch_fingerprint")
        if declared_fingerprint is not None and declared_fingerprint != batch.batch_fingerprint:
            raise ValueError("batch_fingerprint does not match batch payload")
        return batch

    @classmethod
    def from_json(cls, path: str | Path) -> "DiscoveredClusterBatch":
        try:
            value = json.loads(Path(path).read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError("DiscoveredClusterBatch JSON is invalid") from exc
        return cls.from_dict(value)


__all__ = [
    "CoordinationMetricSet",
    "DISCOVERED_CLUSTER_BATCH_SCHEMA_VERSION",
    "DISCOVERY_CLAIM_ROLE",
    "DISCOVERY_STAGE",
    "DiscoveredCluster",
    "DiscoveredClusterBatch",
    "DiscoveryProvenance",
    "STAGE1_LABEL_POLICY",
]
