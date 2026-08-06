from __future__ import annotations

import hashlib
import json
import math
import pickle
from collections.abc import Mapping as MappingABC, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timezone
from numbers import Real
from pathlib import Path
from types import MappingProxyType
from typing import Any, Mapping

import networkx as nx

from research.coordination_discover.stage1.events import CoordinationEvent

from .protocol import DatasetCapability, ResearchDatasetManifest


IOHUNTER_CAMPAIGNS = ("UAE", "china", "cuba", "iran", "russia", "venezuela")
IOHUNTER_LAYER_RELATIONS = MappingProxyType(
    {
        "coRT": "repost_target",
        "coURL": "shared_url",
        "hashSeq": "shared_hashtag",
        "fastRT": "repost_target",
        "tweetSim": "near_duplicate",
    }
)
# IOHunter's processed relation graphs contain no original event time.
IOHUNTER_STATIC_PLACEHOLDER_TIMESTAMP = datetime(1970, 1, 1, tzinfo=timezone.utc)


def _canonical_json(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def _sha256_bytes(value: bytes) -> str:
    return f"sha256:{hashlib.sha256(value).hexdigest()}"


def _campaign(value: Any) -> str:
    if not isinstance(value, str) or value not in IOHUNTER_CAMPAIGNS:
        raise ValueError(f"campaign must be one of {list(IOHUNTER_CAMPAIGNS)}")
    return value


def _node_index(value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError("IOHunter graph account indices must be non-negative integers")
    return value


def _account_id(campaign: str, node: int) -> str:
    return f"iohunter:{campaign}:account:{node:06d}"


def _source_graph(payload: Mapping[str, Any], layer: str) -> nx.Graph:
    graph = payload.get(layer)
    if not isinstance(graph, nx.Graph) or graph.is_directed() or graph.is_multigraph():
        raise ValueError(f"{layer} must be a simple undirected NetworkX graph")
    for node in graph.nodes:
        _node_index(node)
    return graph


def _edge_weight(data: Mapping[str, Any], layer: str) -> float:
    raw = data.get("weight", 1.0)
    if isinstance(raw, bool) or not isinstance(raw, (int, float)):
        raise ValueError(f"{layer} edge weight must be numeric")
    weight = float(raw)
    if not math.isfinite(weight) or weight <= 0.0:
        raise ValueError(f"{layer} edge weight must be finite and positive")
    return weight


def _event_dict(event: CoordinationEvent) -> dict[str, Any]:
    return {
        "account_id": event.account_id,
        "relation": event.relation,
        "object_id": event.object_id,
        "observed_at": event.observed_at.isoformat().replace("+00:00", "Z"),
        "weight": event.weight,
        "evidence_ref": event.evidence_ref,
    }


@dataclass(frozen=True, slots=True)
class IOHunterDiscoveryPayload:
    events: tuple[CoordinationEvent, ...]
    manifest: ResearchDatasetManifest

    def __post_init__(self) -> None:
        if not isinstance(self.events, (tuple, list)) or not all(
            isinstance(event, CoordinationEvent) for event in self.events
        ):
            raise ValueError("events must contain CoordinationEvent values")
        object.__setattr__(self, "events", tuple(self.events))
        if not isinstance(self.manifest, ResearchDatasetManifest):
            raise ValueError("manifest must be a ResearchDatasetManifest")

    @property
    def discovery_fingerprint(self) -> str:
        return _sha256_bytes(_canonical_json([_event_dict(event) for event in self.events]))

    def to_dict(self) -> dict[str, Any]:
        return {
            "events": [_event_dict(event) for event in self.events],
            "manifest": self.manifest.to_dict(),
        }


@dataclass(frozen=True, slots=True)
class IOHunterLabelEvaluator:
    campaign: str
    account_labels: Mapping[str, int]
    official_folds: Mapping[str, tuple[str, ...]]
    label_semantics: str = "1=information-operation account; 0=non-IO account"

    def __post_init__(self) -> None:
        object.__setattr__(self, "campaign", _campaign(self.campaign))
        labels = dict(sorted(self.account_labels.items()))
        if not labels or any(value not in (0, 1) or isinstance(value, bool) for value in labels.values()):
            raise ValueError("account labels must be non-empty and binary")
        if any(not isinstance(key, str) or not key.startswith(f"iohunter:{self.campaign}:account:") for key in labels):
            raise ValueError("account labels must use campaign-prefixed opaque account IDs")
        object.__setattr__(self, "account_labels", MappingProxyType(labels))
        folds: dict[str, tuple[str, ...]] = {}
        for name, ids in self.official_folds.items():
            if not isinstance(name, str) or not name.strip():
                raise ValueError("official fold names must be non-empty strings")
            normalized = tuple(sorted(set(ids)))
            if not normalized or not set(normalized) <= set(labels):
                raise ValueError("official fold masks must be non-empty and aligned with labels")
            folds[name.strip()] = normalized
        if not folds:
            raise ValueError("official fold masks must be non-empty")
        object.__setattr__(self, "official_folds", MappingProxyType(dict(sorted(folds.items()))))
        if self.label_semantics != "1=information-operation account; 0=non-IO account":
            raise ValueError("IOHunter label semantics are fixed")


def iohunter_capability() -> DatasetCapability:
    return DatasetCapability(
        dataset_id="iohunter",
        supports_coordination_discovery=True,
        supports_external_label_evaluation=True,
        supports_campaign_holdout=True,
        supports_time_holdout=False,
        supports_social_bot_classification=False,
        supports_harmful_cib_detection=True,
        supports_campaign_io_evaluation=True,
        blocked_reasons={
            "observed_time_holdout": "processed graphs lack observed event timestamps",
            "social_bot_classification": "IOHunter labels information-operation accounts, not social bots",
        },
        claim_markers=("offline_research_input",),
    )


def adapt_iohunter_payload(
    payload: Mapping[str, Any],
    *,
    campaign: str,
    seed: int,
    source_path: str | Path | None = None,
) -> IOHunterDiscoveryPayload:
    if not isinstance(payload, MappingABC):
        raise ValueError("IOHunter payload must be a mapping")
    campaign = _campaign(campaign)
    events: list[CoordinationEvent] = []
    account_nodes: set[int] = set()
    for layer, relation in IOHUNTER_LAYER_RELATIONS.items():
        graph = _source_graph(payload, layer)
        account_nodes.update(_node_index(node) for node in graph.nodes)
        edges = []
        for left_raw, right_raw, data in graph.edges(data=True):
            left, right = sorted((_node_index(left_raw), _node_index(right_raw)))
            if left == right:
                continue
            edges.append((left, right, _edge_weight(data, layer)))
        for left, right, weight in sorted(edges):
            pair = f"{left:06d}-{right:06d}"
            evidence_ref = f"iohunter:{campaign}:{layer}:pair:{pair}"
            object_id = f"iohunter-object:{campaign}:{layer}:{pair}"
            for node in (left, right):
                events.append(
                    CoordinationEvent(
                        account_id=_account_id(campaign, node),
                        relation=relation,
                        object_id=object_id,
                        observed_at=IOHUNTER_STATIC_PLACEHOLDER_TIMESTAMP,
                        weight=weight,
                        evidence_ref=evidence_ref,
                    )
                )
    events.sort(key=lambda event: (event.evidence_ref, event.account_id))
    event_tuple = tuple(events)
    graph_fingerprint = _sha256_bytes(_canonical_json([_event_dict(event) for event in event_tuple]))
    path = str(source_path) if source_path is not None else f"G:/CISCN/dataset/iohunter/data/processed/{campaign}/0.7_datasets.pkl"
    manifest = ResearchDatasetManifest(
        dataset_id=f"iohunter-{campaign}",
        seed=seed,
        source_paths=(path,),
        source_checksums={path: graph_fingerprint},
        source_checksum_scope="canonical_discovery_graph_layers",
        label_semantics="not_available_to_discovery_stage",
        sample_count=len(account_nodes),
        source_case_ids=tuple(_account_id(campaign, node) for node in sorted(account_nodes)),
        campaign_axis=(campaign,),
        platform_axis=("twitter",),
        time_axis="static_placeholder_not_observed_time",
        quality_markers=("timestamp_imputed",),
        claim_markers=("offline_research_input",),
    )
    return IOHunterDiscoveryPayload(events=event_tuple, manifest=manifest)


def _as_sequence(value: Any, field_name: str) -> list[Any]:
    if hasattr(value, "detach"):
        value = value.detach().cpu()
    if hasattr(value, "tolist"):
        value = value.tolist()
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise ValueError(f"{field_name} must be an aligned sequence")
    return list(value)


def _mask_ids(value: Any, account_ids: tuple[str, ...], field_name: str) -> tuple[str, ...]:
    values = _as_sequence(value, field_name)
    if len(values) == len(account_ids) and all(item in (True, False, 0, 1) for item in values):
        return tuple(account_id for account_id, included in zip(account_ids, values, strict=True) if bool(included))
    indices = []
    for item in values:
        if isinstance(item, bool) or not isinstance(item, int) or not 0 <= item < len(account_ids):
            raise ValueError(f"{field_name} must be a boolean mask or account-index sequence")
        indices.append(item)
    return tuple(account_ids[index] for index in sorted(set(indices)))


def _normalize_folds(value: Any, account_ids: tuple[str, ...]) -> Mapping[str, tuple[str, ...]]:
    folds: dict[str, tuple[str, ...]] = {}
    if isinstance(value, MappingABC):
        if value and all(isinstance(fold, MappingABC) for fold in value.values()):
            items = (
                (f"fold-{fold_index:03d}-{name}", mask)
                for fold_index, (_, fold) in enumerate(sorted(value.items(), key=lambda item: str(item[0])))
                for name, mask in fold.items()
            )
        else:
            items = value.items()
    else:
        values = _as_sequence(value, "splits")
        if len(values) == 3 and not any(isinstance(item, MappingABC) for item in values):
            items = zip(("train", "validation", "test"), values, strict=True)
        elif all(isinstance(item, MappingABC) for item in values):
            items = (
                (f"fold-{fold_index:03d}-{name}", mask)
                for fold_index, fold in enumerate(values)
                for name, mask in fold.items()
            )
        else:
            raise ValueError("splits must be named masks or a sequence of named fold masks")
    for name, mask in items:
        fold_name = str(name).strip()
        if not fold_name:
            raise ValueError("official fold names must be non-empty")
        folds[fold_name] = _mask_ids(mask, account_ids, fold_name)
    return folds


def build_iohunter_label_evaluator(
    payload: Mapping[str, Any], *, campaign: str
) -> IOHunterLabelEvaluator:
    if not isinstance(payload, MappingABC):
        raise ValueError("IOHunter payload must be a mapping")
    campaign = _campaign(campaign)
    graph = payload.get("graph")
    if not isinstance(graph, nx.Graph):
        raise ValueError("graph is required to align evaluator labels")
    nodes = tuple(sorted(_node_index(node) for node in graph.nodes))
    labels = _as_sequence(payload.get("labels"), "labels")
    if nodes != tuple(range(len(labels))):
        raise ValueError("labels must be aligned with contiguous graph account indices")
    normalized_labels: dict[str, int] = {}
    for node, value in zip(nodes, labels, strict=True):
        if isinstance(value, bool) or not isinstance(value, Real) or not math.isfinite(float(value)) or float(value) not in (0.0, 1.0):
            raise ValueError("IOHunter labels must be binary numeric values")
        normalized_labels[_account_id(campaign, node)] = int(value)
    account_ids = tuple(normalized_labels)
    folds = _normalize_folds(payload.get("splits"), account_ids)
    return IOHunterLabelEvaluator(
        campaign=campaign,
        account_labels=normalized_labels,
        official_folds=folds,
    )


def _trusted_pickle(path: str | Path, *, trusted_local: bool) -> tuple[Path, Mapping[str, Any]]:
    if trusted_local is not True:
        raise ValueError("pickle deserialization requires explicit trusted_local=True")
    source = Path(path).resolve()
    with source.open("rb") as handle:
        payload = pickle.load(handle)
    if not isinstance(payload, MappingABC):
        raise ValueError("IOHunter pickle payload must be a mapping")
    return source, payload


def load_iohunter_discovery(
    path: str | Path,
    *,
    campaign: str,
    seed: int,
    trusted_local: bool = False,
) -> IOHunterDiscoveryPayload:
    source, payload = _trusted_pickle(path, trusted_local=trusted_local)
    return adapt_iohunter_payload(
        payload,
        campaign=campaign,
        seed=seed,
        source_path=source,
    )


def load_iohunter_label_evaluator(
    path: str | Path,
    *,
    campaign: str,
    trusted_local: bool = False,
) -> IOHunterLabelEvaluator:
    _, payload = _trusted_pickle(path, trusted_local=trusted_local)
    return build_iohunter_label_evaluator(payload, campaign=campaign)


__all__ = [
    "IOHUNTER_CAMPAIGNS",
    "IOHUNTER_LAYER_RELATIONS",
    "IOHUNTER_STATIC_PLACEHOLDER_TIMESTAMP",
    "IOHunterDiscoveryPayload",
    "IOHunterLabelEvaluator",
    "adapt_iohunter_payload",
    "build_iohunter_label_evaluator",
    "iohunter_capability",
    "load_iohunter_discovery",
    "load_iohunter_label_evaluator",
]
