"""Coordination Discover research-grade platform-generic pipeline."""

from .artifacts import (
    find_snapshot_artifact,
    load_discover_artifact,
    validate_manifest_for_snapshot,
    write_discover_artifact,
)
from .contracts import (
    FALLBACK_POLICY,
    KT1_MODEL_VERSION,
    MODALITY_POLICY,
    COORDINATION_DISCOVER_MODEL_VERSION,
    COORDINATION_DISCOVER_TECHNOLOGY,
    DetectValidationRequest,
    DetectValidationResult,
    DiscoverResult,
    DynamicDiscoverRequest,
    EvidenceEdge,
    EvidenceGraph,
    EvidenceObject,
    KT1ArtifactManifest,
    TemporalMAGNNConfig,
)
from .evidence import build_evidence_graph
from .models import (
    MODEL_INPUT_FEATURE_NAMES,
    TemporalMAGNNTensors,
    build_account_pair_edges,
    build_temporal_magnn_tensors,
    fit_temporal_magnn,
    partition_learned_graph,
)
from .pipelines import export_coordination_result, run_detect_validation, run_dynamic_discover

__all__ = [
    "FALLBACK_POLICY",
    "COORDINATION_DISCOVER_MODEL_VERSION",
    "COORDINATION_DISCOVER_TECHNOLOGY",
    "KT1ArtifactManifest",
    "KT1_MODEL_VERSION",
    "MODALITY_POLICY",
    "MODEL_INPUT_FEATURE_NAMES",
    "DetectValidationRequest",
    "DetectValidationResult",
    "DiscoverResult",
    "DynamicDiscoverRequest",
    "EvidenceEdge",
    "EvidenceGraph",
    "EvidenceObject",
    "TemporalMAGNNConfig",
    "TemporalMAGNNTensors",
    "build_account_pair_edges",
    "build_evidence_graph",
    "build_temporal_magnn_tensors",
    "export_coordination_result",
    "find_snapshot_artifact",
    "fit_temporal_magnn",
    "load_discover_artifact",
    "partition_learned_graph",
    "run_detect_validation",
    "run_dynamic_discover",
    "validate_manifest_for_snapshot",
    "write_discover_artifact",
]
