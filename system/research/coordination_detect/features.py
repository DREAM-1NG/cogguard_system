from __future__ import annotations

import math
from collections.abc import Mapping
from typing import Any

from .contracts import DetectionFeatureSchema


STAGE1_FEATURE_NAMES = (
    "cluster_size",
    "tsgs_density",
    "mhcr_coherence",
    "temporal_sync_delta_seconds",
    "unsupervised_coordination_ranking",
    "evidence_coverage",
    "relation_diversity",
)


def _finite(value: Any, field_name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"feature {field_name} must be numeric")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"feature {field_name} must be finite")
    return result


def build_detection_feature_rows(
    batch: Any,
    schema: DetectionFeatureSchema,
    detection_features: Mapping[str, Mapping[str, float]],
) -> dict[str, tuple[float, ...]]:
    if not isinstance(schema, DetectionFeatureSchema):
        raise ValueError("schema must be a DetectionFeatureSchema")
    if not isinstance(detection_features, Mapping):
        raise ValueError("detection_features must be a cluster feature mapping")
    batch.validate()
    clusters = {cluster.cluster_id: cluster for cluster in batch.candidate_clusters}
    extra_cluster_ids = set(detection_features) - set(clusters)
    if extra_cluster_ids:
        raise ValueError(f"detection_features contains extra cluster IDs: {sorted(extra_cluster_ids)}")
    caller_names = tuple(name for name in schema.names if name not in STAGE1_FEATURE_NAMES)
    rows: dict[str, tuple[float, ...]] = {}
    for cluster_id, cluster in clusters.items():
        caller_values = detection_features.get(cluster_id, {})
        if not isinstance(caller_values, Mapping):
            raise ValueError(f"detection features for {cluster_id} must be a mapping")
        actual_names = tuple(caller_values.keys())
        missing = set(caller_names) - set(actual_names)
        extra = set(actual_names) - set(caller_names)
        if missing:
            raise ValueError(f"detection features for {cluster_id} are missing: {sorted(missing)}")
        if extra:
            raise ValueError(f"detection features for {cluster_id} contain extra values: {sorted(extra)}")
        if actual_names != caller_names:
            raise ValueError(f"detection features for {cluster_id} do not match stable ordered names")
        metrics = cluster.coordination_metrics
        known = {
            "cluster_size": float(cluster.size),
            "tsgs_density": metrics.tsgs_spectral_density,
            "mhcr_coherence": metrics.mhcr_hyperedge_coherence,
            "temporal_sync_delta_seconds": metrics.temporal_sync_delta_seconds,
            "unsupervised_coordination_ranking": metrics.overall_coordination_score,
            "evidence_coverage": metrics.evidence_coverage,
            "relation_diversity": metrics.relation_diversity,
        }
        merged = {**known, **caller_values}
        unsupported = set(schema.names) - set(merged)
        if unsupported:
            raise ValueError(f"schema contains missing feature providers: {sorted(unsupported)}")
        rows[cluster_id] = tuple(_finite(merged[name], name) for name in schema.names)
    return rows


__all__ = ["STAGE1_FEATURE_NAMES", "build_detection_feature_rows"]
