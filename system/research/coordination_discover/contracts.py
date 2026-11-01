from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal

COORDINATION_DISCOVER_TECHNOLOGY = "coordination_discover"
COORDINATION_DISCOVER_MODEL_VERSION = "coordination_discover-temporal-magnn-leiden-v0"
DEPRECATED_COORDINATION_DISCOVER_MODEL_VERSIONS = {
    COORDINATION_DISCOVER_MODEL_VERSION: "deprecated_non_claimable_recon_regression",
}
MODALITY_POLICY = "platform_generic_only"
FALLBACK_POLICY = "evidence_runtime_v2"

PLATFORM_GENERIC_EVIDENCE_KINDS = (
    "url",
    "domain",
    "hashtag",
    "keyword",
    "entity",
    "target",
    "native_relation",
    "discussion",
    "near_duplicate",
)

MODALITY_SPECIFIC_FIELD_MARKERS = (
    "media",
    "video",
    "audio",
    "image",
    "picture",
    "pic",
    "thumbnail",
    "cover",
    "ocr",
    "asr",
    "frame",
    "embedding",
)

SEMANTIC_TEXT_EMBEDDING_FIELDS = (
    "lm_text_embedding",
    "semantic_text_embedding",
    "text_embedding",
)

TOPOLOGY_AUDIT_FEATURE_NAMES = (
    "degree",
    "weighted_degree",
    "object_concentration",
    "component_size",
    "pagerank",
    "density",
)


@dataclass(slots=True)
class EvidenceObject:
    object_id: str
    object_kind: str
    value: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class EvidenceEdge:
    source_account_id: str
    evidence_object_id: str
    evidence_kind: str
    relation_type: str
    content_id: str
    platform: str
    observed_at: float
    evidence_ref: str
    weight: float = 1.0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class AccountMultigraphEdge:
    source_account_id: str
    target_account_id: str
    evidence_kind: str
    relation_type: str
    platform: str
    observed_at: float
    weight: float
    time_delta_seconds: float
    source_content_id: str
    target_content_id: str
    evidence_objects: list[str]
    evidence_refs: list[str]
    direction: str
    layer: str = "behavior"
    component_kinds: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class EvidenceGraph:
    snapshot_id: str
    event_id: str
    data_fingerprint: str
    accounts: list[str]
    objects: list[EvidenceObject]
    edges: list[EvidenceEdge]
    account_edges: list[AccountMultigraphEdge] = field(default_factory=list)
    excluded_fields: list[dict[str, str]] = field(default_factory=list)
    topology_audit_features: dict[str, Any] = field(default_factory=dict)
    coverage: dict[str, Any] = field(default_factory=dict)
    representation_inputs: dict[str, Any] = field(default_factory=dict)
    modality_policy: str = MODALITY_POLICY

    def to_dict(self) -> dict[str, Any]:
        return {
            "snapshot_id": self.snapshot_id,
            "event_id": self.event_id,
            "data_fingerprint": self.data_fingerprint,
            "accounts": list(self.accounts),
            "objects": [item.to_dict() for item in self.objects],
            "edges": [item.to_dict() for item in self.edges],
            "account_edges": [item.to_dict() for item in self.account_edges],
            "excluded_fields": list(self.excluded_fields),
            "topology_audit_features": dict(self.topology_audit_features),
            "coverage": dict(self.coverage),
            "representation_inputs": dict(self.representation_inputs),
            "modality_policy": self.modality_policy,
        }


@dataclass(slots=True)
class TemporalMAGNNConfig:
    embedding_dim: int = 16
    epochs: int = 5
    learning_rate: float = 0.01
    negative_ratio: int = 2
    time_bucket_seconds: int = 3600
    min_learned_edge_score: float = 0.05
    seed: int = 1729
    device: str = "cuda"
    export_embedding_dims: int = 8
    require_leiden: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class DynamicDiscoverRequest:
    snapshot: Any
    artifact_dir: str | None = None
    model_config: TemporalMAGNNConfig = field(default_factory=TemporalMAGNNConfig)
    window_hours: tuple[int, ...] = (1, 6, 24)
    overlap_ratio: float = 0.5
    source_dataset: str = ""
    source_event: str = ""
    model_version: str = COORDINATION_DISCOVER_MODEL_VERSION
    fallback_policy: str = FALLBACK_POLICY
    modality_policy: str = MODALITY_POLICY


@dataclass(slots=True)
class CoordinationDiscoverArtifactManifest:
    data_fingerprint: str
    model_version: str
    config_hash: str
    source_dataset: str
    source_event: str
    checkpoint_path: str
    metrics_path: str
    result_path: str
    generated_at: str
    fallback_policy: str = FALLBACK_POLICY
    modality_policy: str = MODALITY_POLICY
    partition_backend: str = "leiden"
    status: str = "ok"
    claimability: str = "non_claimable"
    artifact_hashes: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "CoordinationDiscoverArtifactManifest":
        return cls(
            data_fingerprint=str(value.get("data_fingerprint") or ""),
            model_version=str(value.get("model_version") or COORDINATION_DISCOVER_MODEL_VERSION),
            config_hash=str(value.get("config_hash") or ""),
            source_dataset=str(value.get("source_dataset") or ""),
            source_event=str(value.get("source_event") or ""),
            checkpoint_path=str(value.get("checkpoint_path") or ""),
            metrics_path=str(value.get("metrics_path") or ""),
            result_path=str(value.get("result_path") or ""),
            generated_at=str(value.get("generated_at") or _utc_now()),
            fallback_policy=str(value.get("fallback_policy") or FALLBACK_POLICY),
            modality_policy=str(value.get("modality_policy") or MODALITY_POLICY),
            partition_backend=str(value.get("partition_backend") or "leiden"),
            status=str(value.get("status") or "ok"),
            claimability=str(value.get("claimability") or "non_claimable"),
            artifact_hashes={
                str(key): str(item)
                for key, item in dict(value.get("artifact_hashes") or {}).items()
            },
        )


@dataclass(slots=True)
class DiscoverResult:
    status: Literal["ok", "data_insufficient", "model_unavailable"]
    snapshot_id: str
    event_id: str
    data_fingerprint: str
    model_version: str
    evidence_graph: dict[str, Any]
    learned_edge_graph: dict[str, Any]
    communities: list[dict[str, Any]]
    lineage: list[dict[str, Any]]
    attention: dict[str, Any]
    audit_metrics: dict[str, Any]
    manifest: CoordinationDiscoverArtifactManifest
    fallback_reason: str | None = None
    dynamic_communities: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "technology": COORDINATION_DISCOVER_TECHNOLOGY,
            "snapshot_id": self.snapshot_id,
            "event_id": self.event_id,
            "data_fingerprint": self.data_fingerprint,
            "model_version": self.model_version,
            "evidence_graph": self.evidence_graph,
            "learned_edge_graph": self.learned_edge_graph,
            "communities": list(self.communities),
            "lineage": list(self.lineage),
            "attention": dict(self.attention),
            "audit_metrics": dict(self.audit_metrics),
            "manifest": self.manifest.to_dict(),
            "fallback_reason": self.fallback_reason,
            "dynamic_communities": dict(self.dynamic_communities),
        }


@dataclass(slots=True)
class DetectValidationRequest:
    rows: list[dict[str, Any]]
    label_field: str = "label"
    score_field: str = "score"
    positive_label: Any = 1


@dataclass(slots=True)
class DetectValidationResult:
    status: Literal["ok", "missing_labels", "data_insufficient"]
    metrics: dict[str, Any]
    ablation_rows: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "metrics": dict(self.metrics),
            "ablation_rows": list(self.ablation_rows),
        }


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


__all__ = [
    "AccountMultigraphEdge",
    "DetectValidationRequest",
    "DetectValidationResult",
    "DiscoverResult",
    "DynamicDiscoverRequest",
    "EvidenceEdge",
    "EvidenceGraph",
    "EvidenceObject",
    "FALLBACK_POLICY",
    "COORDINATION_DISCOVER_MODEL_VERSION",
    "COORDINATION_DISCOVER_TECHNOLOGY",
    "CoordinationDiscoverArtifactManifest",
    "DEPRECATED_COORDINATION_DISCOVER_MODEL_VERSIONS",
    "MODALITY_POLICY",
    "MODALITY_SPECIFIC_FIELD_MARKERS",
    "PLATFORM_GENERIC_EVIDENCE_KINDS",
    "SEMANTIC_TEXT_EMBEDDING_FIELDS",
    "TOPOLOGY_AUDIT_FEATURE_NAMES",
    "TemporalMAGNNConfig",
]
