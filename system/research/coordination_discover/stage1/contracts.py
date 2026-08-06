from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Mapping as MappingABC
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from types import MappingProxyType
from typing import Any, Mapping


DISCOVERED_CLUSTER_BATCH_SCHEMA_VERSION = "cogguard.discovered-cluster-batch/v1"
DISCOVERY_STAGE = "coordination_discovery"
DISCOVERY_CLAIM_ROLE = "unsupervised_candidate_clusters"
STAGE1_LABEL_POLICY = "stage1_label_free"
_UNSUPERVISED_RANKING_SCORE_ROLE = "unsupervised_ranking_not_probability"


def _required_text(value: Any, field_name: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be a non-empty string")
    text = value.strip()
    if not text:
        raise ValueError(f"{field_name} must be a non-empty string")
    return text


def _optional_text(value: Any, field_name: str) -> str | None:
    return None if value is None else _required_text(value, field_name)


def _finite_float(value: Any, field_name: str, *, minimum: float, maximum: float | None = None) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{field_name} must be numeric")
    number = float(value)
    if not math.isfinite(number) or number < minimum or (maximum is not None and number > maximum):
        bounds = f"within [{minimum:g}, {maximum:g}]" if maximum is not None else "non-negative"
        raise ValueError(f"{field_name} must be finite and {bounds}")
    return number


def _unit_interval(value: Any, field_name: str) -> float:
    return _finite_float(value, field_name, minimum=0.0, maximum=1.0)


def _non_negative(value: Any, field_name: str) -> float:
    return _finite_float(value, field_name, minimum=0.0)


def _integer(value: Any, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{field_name} must be an integer")
    return value


def _non_negative_int(value: Any, field_name: str) -> int:
    number = _integer(value, field_name)
    if number < 0:
        raise ValueError(f"{field_name} must be a non-negative integer")
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
    if not isinstance(values, (tuple, list)):
        raise ValueError(f"{field_name} must be a sequence of strings")
    normalized = tuple(sorted({_required_text(value, field_name) for value in values}))
    if not allow_empty and not normalized:
        raise ValueError(f"{field_name} must contain at least one value")
    return normalized


def _text_mapping(value: Any, field_name: str) -> Mapping[str, str]:
    if not isinstance(value, MappingABC):
        raise ValueError(f"{field_name} must be a mapping of strings")
    normalized = {
        _required_text(key, f"{field_name} key"): _required_text(item, f"{field_name} value")
        for key, item in value.items()
    }
    return MappingProxyType(dict(sorted(normalized.items())))


def _count_mapping(value: Any, field_name: str) -> Mapping[str, int]:
    if not isinstance(value, MappingABC):
        raise ValueError(f"{field_name} must be a mapping of non-negative integers")
    normalized = {
        _required_text(key, f"{field_name} key"): _non_negative_int(item, f"{field_name} value")
        for key, item in value.items()
    }
    return MappingProxyType(dict(sorted(normalized.items())))


def _require_schema(value: Any, field_name: str, required_fields: frozenset[str]) -> Mapping[str, Any]:
    if not isinstance(value, MappingABC):
        raise ValueError(f"{field_name} must be a JSON object")
    actual_fields = set(value)
    unknown = actual_fields - required_fields
    if unknown:
        raise ValueError(f"{field_name} contains unknown fields: {sorted(map(str, unknown))}")
    missing = required_fields - actual_fields
    if missing:
        raise ValueError(f"{field_name} is missing required fields: {sorted(missing)}")
    return value


def _canonical_json(value: Mapping[str, Any]) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


@dataclass(frozen=True, slots=True)
class CoordinationMetricSet:
    tsgs_spectral_density: float
    mhcr_hyperedge_coherence: float
    temporal_sync_delta_seconds: float
    overall_coordination_score: float
    evidence_coverage: float = 0.0
    relation_diversity: float = 0.0

    _SCHEMA_FIELDS = frozenset(
        {
            "tsgs_spectral_density",
            "mhcr_hyperedge_coherence",
            "temporal_sync_delta_seconds",
            "overall_coordination_score",
            "overall_coordination_score_role",
            "evidence_coverage",
            "relation_diversity",
        }
    )

    def __post_init__(self) -> None:
        for field_name in (
            "tsgs_spectral_density",
            "mhcr_hyperedge_coherence",
            "overall_coordination_score",
            "evidence_coverage",
            "relation_diversity",
        ):
            object.__setattr__(self, field_name, _unit_interval(getattr(self, field_name), field_name))
        object.__setattr__(self, "temporal_sync_delta_seconds", _non_negative(self.temporal_sync_delta_seconds, "temporal_sync_delta_seconds"))

    def validate(self) -> None:
        self.__post_init__()

    def to_dict(self) -> dict[str, float | str]:
        return {
            "tsgs_spectral_density": self.tsgs_spectral_density,
            "mhcr_hyperedge_coherence": self.mhcr_hyperedge_coherence,
            "temporal_sync_delta_seconds": self.temporal_sync_delta_seconds,
            "overall_coordination_score": self.overall_coordination_score,
            "overall_coordination_score_role": _UNSUPERVISED_RANKING_SCORE_ROLE,
            "evidence_coverage": self.evidence_coverage,
            "relation_diversity": self.relation_diversity,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "CoordinationMetricSet":
        value = _require_schema(value, "coordination_metrics", cls._SCHEMA_FIELDS)
        if value["overall_coordination_score_role"] != _UNSUPERVISED_RANKING_SCORE_ROLE:
            raise ValueError(f"overall_coordination_score_role must be {_UNSUPERVISED_RANKING_SCORE_ROLE}")
        return cls(
            tsgs_spectral_density=value["tsgs_spectral_density"],
            mhcr_hyperedge_coherence=value["mhcr_hyperedge_coherence"],
            temporal_sync_delta_seconds=value["temporal_sync_delta_seconds"],
            overall_coordination_score=value["overall_coordination_score"],
            evidence_coverage=value["evidence_coverage"],
            relation_diversity=value["relation_diversity"],
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
    relation_types: tuple[str, ...] = ()
    window_ids: tuple[str, ...] = ()
    evidence_kind_counts: Mapping[str, int] = field(default_factory=dict)

    _SCHEMA_FIELDS = frozenset(
        {
            "cluster_id",
            "size",
            "member_account_ids",
            "coordination_metrics",
            "evidence_refs",
            "sparsified_subgraph_ref",
            "embedding_ref",
            "artifact_hashes",
            "relation_types",
            "window_ids",
            "evidence_kind_counts",
        }
    )

    def __post_init__(self) -> None:
        object.__setattr__(self, "cluster_id", _required_text(self.cluster_id, "cluster_id"))
        object.__setattr__(self, "member_account_ids", _sorted_unique_text(self.member_account_ids, "member_account_ids", allow_empty=False))
        if not isinstance(self.coordination_metrics, CoordinationMetricSet):
            raise ValueError("coordination_metrics must be a CoordinationMetricSet")
        self.coordination_metrics.validate()
        object.__setattr__(self, "evidence_refs", _sorted_unique_text(self.evidence_refs, "evidence_refs"))
        object.__setattr__(self, "sparsified_subgraph_ref", _optional_text(self.sparsified_subgraph_ref, "sparsified_subgraph_ref"))
        object.__setattr__(self, "embedding_ref", _optional_text(self.embedding_ref, "embedding_ref"))
        object.__setattr__(self, "artifact_hashes", _text_mapping(self.artifact_hashes, "artifact_hashes"))
        object.__setattr__(self, "relation_types", _sorted_unique_text(self.relation_types, "relation_types"))
        object.__setattr__(self, "window_ids", _sorted_unique_text(self.window_ids, "window_ids"))
        object.__setattr__(self, "evidence_kind_counts", _count_mapping(self.evidence_kind_counts, "evidence_kind_counts"))

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
            "relation_types": list(self.relation_types),
            "window_ids": list(self.window_ids),
            "evidence_kind_counts": dict(self.evidence_kind_counts),
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "DiscoveredCluster":
        value = _require_schema(value, "candidate cluster", cls._SCHEMA_FIELDS)
        member_ids = _sorted_unique_text(value["member_account_ids"], "member_account_ids", allow_empty=False)
        size = value["size"]
        if isinstance(size, bool) or not isinstance(size, int):
            raise ValueError("cluster size must be an integer")
        if size != len(member_ids):
            raise ValueError("cluster size does not match unique member_account_ids")
        return cls(
            cluster_id=value["cluster_id"],
            member_account_ids=member_ids,
            coordination_metrics=CoordinationMetricSet.from_dict(value["coordination_metrics"]),
            evidence_refs=value["evidence_refs"],
            sparsified_subgraph_ref=value["sparsified_subgraph_ref"],
            embedding_ref=value["embedding_ref"],
            artifact_hashes=value["artifact_hashes"],
            relation_types=value["relation_types"],
            window_ids=value["window_ids"],
            evidence_kind_counts=value["evidence_kind_counts"],
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
    input_event_count: int = 0
    input_account_count: int = 0
    method_config_hash: str | None = None

    _SCHEMA_FIELDS = frozenset(
        {
            "snapshot_id",
            "data_fingerprint",
            "source_dataset",
            "source_event",
            "stage1_model_version",
            "tsgs_version",
            "mhcr_version",
            "created_at",
            "seed",
            "split_policy",
            "label_policy",
            "input_event_count",
            "input_account_count",
            "method_config_hash",
        }
    )

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
        object.__setattr__(self, "seed", _integer(self.seed, "seed"))
        if self.label_policy != STAGE1_LABEL_POLICY:
            raise ValueError(f"label_policy must be {STAGE1_LABEL_POLICY}")
        object.__setattr__(self, "input_event_count", _non_negative_int(self.input_event_count, "input_event_count"))
        object.__setattr__(self, "input_account_count", _non_negative_int(self.input_account_count, "input_account_count"))
        object.__setattr__(self, "method_config_hash", _optional_text(self.method_config_hash, "method_config_hash"))

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
            "input_event_count": self.input_event_count,
            "input_account_count": self.input_account_count,
            "method_config_hash": self.method_config_hash,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "DiscoveryProvenance":
        value = _require_schema(value, "provenance", cls._SCHEMA_FIELDS)
        return cls(
            snapshot_id=value["snapshot_id"],
            data_fingerprint=value["data_fingerprint"],
            source_dataset=value["source_dataset"],
            source_event=value["source_event"],
            stage1_model_version=value["stage1_model_version"],
            tsgs_version=value["tsgs_version"],
            mhcr_version=value["mhcr_version"],
            created_at=value["created_at"],
            seed=value["seed"],
            split_policy=value["split_policy"],
            label_policy=value["label_policy"],
            input_event_count=value["input_event_count"],
            input_account_count=value["input_account_count"],
            method_config_hash=value["method_config_hash"],
        )


@dataclass(frozen=True, slots=True)
class DiscoveredClusterBatch:
    batch_id: str
    timestamp: str
    candidate_clusters: tuple[DiscoveredCluster, ...]
    provenance: DiscoveryProvenance
    platforms: tuple[str, ...] = ()
    quality_flags: tuple[str, ...] = ()
    artifact_manifest_ref: str | None = None
    schema_version: str = DISCOVERED_CLUSTER_BATCH_SCHEMA_VERSION
    stage: str = DISCOVERY_STAGE
    claim_role: str = DISCOVERY_CLAIM_ROLE

    _SCHEMA_FIELDS = frozenset(
        {
            "schema_version",
            "stage",
            "claim_role",
            "batch_id",
            "timestamp",
            "candidate_clusters",
            "provenance",
            "platforms",
            "quality_flags",
            "artifact_manifest_ref",
            "batch_fingerprint",
        }
    )

    def __post_init__(self) -> None:
        if self.schema_version != DISCOVERED_CLUSTER_BATCH_SCHEMA_VERSION:
            raise ValueError(f"unsupported schema_version: {self.schema_version}")
        if self.stage != DISCOVERY_STAGE:
            raise ValueError(f"stage must be {DISCOVERY_STAGE}")
        if self.claim_role != DISCOVERY_CLAIM_ROLE:
            raise ValueError(f"claim_role must be {DISCOVERY_CLAIM_ROLE}")
        object.__setattr__(self, "batch_id", _required_text(self.batch_id, "batch_id"))
        object.__setattr__(self, "timestamp", _utc_timestamp(self.timestamp, "timestamp"))
        if not isinstance(self.candidate_clusters, (tuple, list)):
            raise ValueError("candidate_clusters must be a sequence of DiscoveredCluster values")
        if not all(isinstance(cluster, DiscoveredCluster) for cluster in self.candidate_clusters):
            raise ValueError("candidate_clusters must contain DiscoveredCluster values")
        clusters = tuple(sorted(self.candidate_clusters, key=lambda item: item.cluster_id))
        cluster_ids = [cluster.cluster_id for cluster in clusters]
        if len(cluster_ids) != len(set(cluster_ids)):
            raise ValueError("duplicate cluster_id in candidate_clusters")
        for cluster in clusters:
            cluster.validate()
        object.__setattr__(self, "candidate_clusters", clusters)
        if not isinstance(self.provenance, DiscoveryProvenance):
            raise ValueError("provenance must be a DiscoveryProvenance")
        self.provenance.validate()
        object.__setattr__(self, "platforms", _sorted_unique_text(self.platforms, "platforms"))
        object.__setattr__(self, "quality_flags", _sorted_unique_text(self.quality_flags, "quality_flags"))
        object.__setattr__(self, "artifact_manifest_ref", _optional_text(self.artifact_manifest_ref, "artifact_manifest_ref"))

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
            "platforms": list(self.platforms),
            "quality_flags": list(self.quality_flags),
            "artifact_manifest_ref": self.artifact_manifest_ref,
        }

    def to_dict(self) -> dict[str, Any]:
        payload = self._payload_without_fingerprint()
        payload["batch_fingerprint"] = self.batch_fingerprint
        return payload

    def to_json(self, path: str | Path) -> Path:
        output_path = Path(path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(self.to_dict(), ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n", encoding="utf-8")
        return output_path

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "DiscoveredClusterBatch":
        value = _require_schema(value, "DiscoveredClusterBatch", cls._SCHEMA_FIELDS)
        if value["schema_version"] != DISCOVERED_CLUSTER_BATCH_SCHEMA_VERSION:
            raise ValueError(f"unsupported schema_version: {value['schema_version']}")
        if not isinstance(value["candidate_clusters"], (tuple, list)):
            raise ValueError("candidate_clusters must be a sequence of candidate cluster objects")
        batch = cls(
            batch_id=value["batch_id"],
            timestamp=value["timestamp"],
            candidate_clusters=tuple(DiscoveredCluster.from_dict(item) for item in value["candidate_clusters"]),
            provenance=DiscoveryProvenance.from_dict(value["provenance"]),
            platforms=value["platforms"],
            quality_flags=value["quality_flags"],
            artifact_manifest_ref=value["artifact_manifest_ref"],
            schema_version=value["schema_version"],
            stage=value["stage"],
            claim_role=value["claim_role"],
        )
        declared_fingerprint = _required_text(value["batch_fingerprint"], "batch_fingerprint")
        if declared_fingerprint != batch.batch_fingerprint:
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
