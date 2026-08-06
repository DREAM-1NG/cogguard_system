from __future__ import annotations

import hashlib
import json
import math
import pickle
from collections.abc import Mapping as MappingABC, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from numbers import Real
from pathlib import Path
from types import MappingProxyType
from typing import Any, Mapping

import networkx as nx
import numpy as np

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
IOHUNTER_LABEL_SEMANTICS = "1=information-operation account; 0=non-IO account"


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


def _account_universe(payload: Mapping[str, Any]) -> tuple[int, ...]:
    source_nodes: set[int] = set()
    for layer in IOHUNTER_LAYER_RELATIONS:
        source_nodes.update(_node_index(node) for node in _source_graph(payload, layer).nodes)
    ordered = tuple(sorted(source_nodes))
    if not ordered or ordered != tuple(range(len(ordered))):
        raise ValueError("IOHunter account universe must use contiguous integer indices 0 through N-1")
    return ordered


def _evaluator_account_universe(
    payload: Mapping[str, Any], labels: Sequence[Any]
) -> tuple[int, ...]:
    source_nodes = _account_universe(payload)
    fused = payload.get("graph")
    if not isinstance(fused, nx.Graph):
        raise ValueError("fused graph is required for IOHunter evaluator alignment")
    fused_nodes = tuple(sorted(_node_index(node) for node in fused.nodes))
    label_nodes = tuple(range(len(labels)))
    if fused_nodes != source_nodes or fused_nodes != label_nodes:
        raise ValueError(
            "fused graph account universe must equal aligned source-layer and label universes"
        )
    return fused_nodes


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
class IOHunterOfficialFold:
    fold_id: str
    train_ids: tuple[str, ...]
    validation_ids: tuple[str, ...]
    test_ids: tuple[str, ...]

    _FIELDS = frozenset({"fold_id", "train_ids", "validation_ids", "test_ids"})

    def __post_init__(self) -> None:
        if not isinstance(self.fold_id, str) or not self.fold_id.startswith("fold-"):
            raise ValueError("fold_id must be a stable fold-NNN identity")
        suffix = self.fold_id[5:]
        if not suffix.isdigit():
            raise ValueError("fold_id must be a stable fold-NNN identity")
        object.__setattr__(self, "fold_id", f"fold-{int(suffix):03d}")
        for field_name in ("train_ids", "validation_ids", "test_ids"):
            values = getattr(self, field_name)
            if isinstance(values, (str, bytes)) or not isinstance(values, Sequence) or not values:
                raise ValueError(f"{field_name} must be a non-empty account ID sequence")
            normalized: list[str] = []
            seen: set[str] = set()
            for value in values:
                if not isinstance(value, str) or not value.strip():
                    raise ValueError(f"{field_name} must contain account IDs")
                account_id = value.strip()
                if account_id in seen:
                    raise ValueError(f"{field_name} contains duplicate account IDs")
                seen.add(account_id)
                normalized.append(account_id)
            object.__setattr__(self, field_name, tuple(sorted(normalized)))
        partitions = [set(self.train_ids), set(self.validation_ids), set(self.test_ids)]
        if any(left & right for index, left in enumerate(partitions) for right in partitions[index + 1 :]):
            raise ValueError("official fold partitions must be pairwise disjoint")

    def to_dict(self) -> dict[str, Any]:
        return {
            "fold_id": self.fold_id,
            "train_ids": list(self.train_ids),
            "validation_ids": list(self.validation_ids),
            "test_ids": list(self.test_ids),
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "IOHunterOfficialFold":
        if not isinstance(value, MappingABC) or set(value) != cls._FIELDS:
            raise ValueError("official fold must contain exactly fold_id, train_ids, validation_ids, and test_ids")
        return cls(
            fold_id=value["fold_id"],
            train_ids=value["train_ids"],
            validation_ids=value["validation_ids"],
            test_ids=value["test_ids"],
        )


@dataclass(frozen=True, slots=True)
class IOHunterLabelEvaluator:
    campaign: str
    source_path: str
    source_sha256: str
    account_labels: Mapping[str, int]
    official_folds: tuple[IOHunterOfficialFold, ...]
    label_semantics: str = IOHUNTER_LABEL_SEMANTICS

    _FIELDS = frozenset(
        {
            "campaign",
            "source_path",
            "source_sha256",
            "account_labels",
            "official_folds",
            "label_semantics",
            "evaluator_fingerprint",
        }
    )

    def __post_init__(self) -> None:
        object.__setattr__(self, "campaign", _campaign(self.campaign))
        if not isinstance(self.source_path, str) or not self.source_path.strip():
            raise ValueError("source_path must be a non-empty string")
        object.__setattr__(self, "source_path", self.source_path.strip())
        if not isinstance(self.source_sha256, str) or len(self.source_sha256) != 71 or not self.source_sha256.startswith("sha256:"):
            raise ValueError("source_sha256 must be sha256:<64 hex>")
        try:
            int(self.source_sha256[7:], 16)
        except ValueError as exc:
            raise ValueError("source_sha256 must be sha256:<64 hex>") from exc
        object.__setattr__(self, "source_sha256", self.source_sha256.lower())
        if not isinstance(self.account_labels, MappingABC):
            raise ValueError("account_labels must be a mapping")
        labels: dict[str, int] = {}
        for account_id, value in sorted(self.account_labels.items()):
            if (
                isinstance(value, bool)
                or not isinstance(value, Real)
                or not math.isfinite(float(value))
                or float(value) not in (0.0, 1.0)
            ):
                raise ValueError("account labels must be non-empty and binary")
            labels[account_id] = int(value)
        if not labels:
            raise ValueError("account labels must be non-empty and binary")
        if any(not isinstance(key, str) or not key.startswith(f"iohunter:{self.campaign}:account:") for key in labels):
            raise ValueError("account labels must use campaign-prefixed opaque account IDs")
        object.__setattr__(self, "account_labels", MappingProxyType(labels))
        if isinstance(self.official_folds, (str, bytes)) or not isinstance(self.official_folds, Sequence):
            raise ValueError("official_folds must be an immutable fold sequence")
        folds = tuple(sorted(self.official_folds, key=lambda fold: fold.fold_id))
        if not folds or not all(isinstance(fold, IOHunterOfficialFold) for fold in folds):
            raise ValueError("official_folds must contain IOHunterOfficialFold values")
        fold_ids = [fold.fold_id for fold in folds]
        if len(fold_ids) != len(set(fold_ids)):
            raise ValueError("official_folds contains duplicate fold identities")
        universe = set(labels)
        for fold in folds:
            fold_universe = set(fold.train_ids) | set(fold.validation_ids) | set(fold.test_ids)
            if fold_universe != universe:
                raise ValueError(f"{fold.fold_id} partitions must provide full account-universe coverage")
        object.__setattr__(self, "official_folds", folds)
        if self.label_semantics != IOHUNTER_LABEL_SEMANTICS:
            raise ValueError("IOHunter label semantics are fixed")

    def _identity_payload(self) -> dict[str, Any]:
        return {
            "campaign": self.campaign,
            "source_path": self.source_path,
            "source_sha256": self.source_sha256,
            "account_labels": dict(self.account_labels),
            "official_folds": [fold.to_dict() for fold in self.official_folds],
            "label_semantics": self.label_semantics,
        }

    @property
    def evaluator_fingerprint(self) -> str:
        return _sha256_bytes(_canonical_json(self._identity_payload()))

    def to_dict(self) -> dict[str, Any]:
        payload = self._identity_payload()
        payload["evaluator_fingerprint"] = self.evaluator_fingerprint
        return payload

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "IOHunterLabelEvaluator":
        if not isinstance(value, MappingABC):
            raise ValueError("IOHunterLabelEvaluator must be a mapping")
        unknown = set(value) - cls._FIELDS
        missing = cls._FIELDS - set(value)
        if unknown or missing:
            raise ValueError(f"IOHunterLabelEvaluator schema mismatch: unknown={sorted(unknown)}, missing={sorted(missing)}")
        result = cls(
            campaign=value["campaign"],
            source_path=value["source_path"],
            source_sha256=value["source_sha256"],
            account_labels=value["account_labels"],
            official_folds=tuple(IOHunterOfficialFold.from_dict(fold) for fold in value["official_folds"]),
            label_semantics=value["label_semantics"],
        )
        if value["evaluator_fingerprint"] != result.evaluator_fingerprint:
            raise ValueError("evaluator fingerprint does not match evaluator payload")
        return result


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
    account_universe = _account_universe(payload)
    events: list[CoordinationEvent] = []
    for layer, relation in IOHUNTER_LAYER_RELATIONS.items():
        graph = _source_graph(payload, layer)
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
    universe_ids = tuple(_account_id(campaign, node) for node in account_universe)
    if not {event.account_id for event in event_tuple} <= set(universe_ids):
        raise ValueError("Discovery events must reference only the canonical account universe")
    graph_fingerprint = _sha256_bytes(_canonical_json([_event_dict(event) for event in event_tuple]))
    path = str(source_path) if source_path is not None else f"G:/CISCN/dataset/iohunter/data/processed/{campaign}/0.7_datasets.pkl"
    manifest = ResearchDatasetManifest(
        dataset_id=f"iohunter-{campaign}",
        seed=seed,
        source_paths=(path,),
        source_checksums={path: graph_fingerprint},
        source_checksum_scope="canonical_discovery_graph_layers",
        label_semantics="not_available_to_discovery_stage",
        sample_count=len(account_universe),
        source_case_ids=universe_ids,
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
    if isinstance(value, np.ndarray):
        if value.ndim != 1 or value.dtype.kind != "b":
            raise ValueError(f"{field_name} must be an actual one-dimensional boolean mask")
        values = value.tolist()
    else:
        values = _as_sequence(value, field_name)
    if len(values) != len(account_ids):
        raise ValueError(f"{field_name} must contain exactly account_count boolean values")
    if not all(isinstance(item, (bool, np.bool_)) for item in values):
        raise ValueError(f"{field_name} must be an actual boolean mask")
    return tuple(account_id for account_id, included in zip(account_ids, values, strict=True) if bool(included))


def _fold_id(value: Any) -> str:
    if isinstance(value, bool):
        raise ValueError("official fold identity must be an integer or fold-NNN string")
    if isinstance(value, int) and value >= 0:
        return f"fold-{value:03d}"
    if isinstance(value, str):
        text = value.strip()
        if text.isdigit():
            return f"fold-{int(text):03d}"
        if text.startswith("fold-") and text[5:].isdigit():
            return f"fold-{int(text[5:]):03d}"
    raise ValueError("official fold identity must be an integer or fold-NNN string")


def _partition_masks(value: Any, fold_id: str) -> Mapping[str, Any]:
    if not isinstance(value, MappingABC):
        raise ValueError(f"{fold_id} must map partition names to boolean masks")
    normalized: dict[str, Any] = {}
    for raw_name, mask in value.items():
        if not isinstance(raw_name, str) or raw_name != raw_name.strip():
            raise ValueError(f"{fold_id} partition names are invalid")
        if raw_name not in {"train", "validation", "val", "test"}:
            raise ValueError(f"{fold_id} partition names must be train, validation, and test")
        name = "validation" if raw_name == "val" else raw_name
        if name in normalized:
            raise ValueError(f"{fold_id} has a duplicate validation alias")
        normalized[name] = mask
    if set(normalized) != {"train", "validation", "test"}:
        raise ValueError(f"{fold_id} must contain exactly train, validation, and test partition names")
    return normalized


def _normalize_folds(value: Any, account_ids: tuple[str, ...]) -> tuple[IOHunterOfficialFold, ...]:
    if isinstance(value, MappingABC):
        direct_names = set(value)
        if direct_names and all(isinstance(name, str) and name in {"train", "validation", "val", "test"} for name in direct_names):
            fold_items = (("fold-000", value),)
        elif value and all(isinstance(fold, MappingABC) for fold in value.values()):
            fold_items = tuple((_fold_id(raw_id), fold) for raw_id, fold in value.items())
        else:
            raise ValueError("splits must contain structured official folds")
    else:
        folds = _as_sequence(value, "splits")
        if not folds or not all(isinstance(fold, MappingABC) for fold in folds):
            raise ValueError("splits must contain structured official folds")
        fold_items = tuple((f"fold-{index:03d}", fold) for index, fold in enumerate(folds))
    fold_ids = [fold_id for fold_id, _ in fold_items]
    if len(fold_ids) != len(set(fold_ids)):
        raise ValueError("official folds contain duplicate fold identities")
    result: list[IOHunterOfficialFold] = []
    universe = set(account_ids)
    for fold_id, raw_partitions in sorted(fold_items):
        partitions = _partition_masks(raw_partitions, fold_id)
        train_ids = _mask_ids(partitions["train"], account_ids, f"{fold_id} train")
        validation_ids = _mask_ids(partitions["validation"], account_ids, f"{fold_id} validation")
        test_ids = _mask_ids(partitions["test"], account_ids, f"{fold_id} test")
        if not train_ids or not validation_ids or not test_ids:
            raise ValueError(f"{fold_id} partitions must be non-empty")
        sets = [set(train_ids), set(validation_ids), set(test_ids)]
        if any(left & right for index, left in enumerate(sets) for right in sets[index + 1 :]):
            raise ValueError(f"{fold_id} partitions must be pairwise disjoint")
        if set().union(*sets) != universe:
            raise ValueError(f"{fold_id} partitions must provide full account-universe coverage")
        result.append(
            IOHunterOfficialFold(
                fold_id=fold_id,
                train_ids=train_ids,
                validation_ids=validation_ids,
                test_ids=test_ids,
            )
        )
    return tuple(result)


def _build_iohunter_label_evaluator(
    payload: Mapping[str, Any],
    *,
    campaign: str,
    source_path: str,
    source_sha256: str | None,
) -> IOHunterLabelEvaluator:
    if not isinstance(payload, MappingABC):
        raise ValueError("IOHunter payload must be a mapping")
    campaign = _campaign(campaign)
    labels = _as_sequence(payload.get("labels"), "labels")
    nodes = _evaluator_account_universe(payload, labels)
    normalized_labels: dict[str, int] = {}
    for node, value in zip(nodes, labels, strict=True):
        if isinstance(value, bool) or not isinstance(value, Real) or not math.isfinite(float(value)) or float(value) not in (0.0, 1.0):
            raise ValueError("IOHunter labels must be binary numeric values")
        normalized_labels[_account_id(campaign, node)] = int(value)
    account_ids = tuple(normalized_labels)
    folds = _normalize_folds(payload.get("splits"), account_ids)
    if source_sha256 is None:
        canonical_evaluator_payload = {
            "campaign": campaign,
            "account_labels": normalized_labels,
            "official_folds": [fold.to_dict() for fold in folds],
            "label_semantics": IOHUNTER_LABEL_SEMANTICS,
        }
        source_sha256 = _sha256_bytes(_canonical_json(canonical_evaluator_payload))
    return IOHunterLabelEvaluator(
        campaign=campaign,
        source_path=source_path,
        source_sha256=source_sha256,
        account_labels=normalized_labels,
        official_folds=folds,
    )


def build_iohunter_label_evaluator(
    payload: Mapping[str, Any], *, campaign: str
) -> IOHunterLabelEvaluator:
    campaign = _campaign(campaign)
    return _build_iohunter_label_evaluator(
        payload,
        campaign=campaign,
        source_path=f"memory://iohunter/{campaign}/evaluator",
        source_sha256=None,
    )


def _trusted_pickle(path: str | Path, *, trusted_local: bool) -> tuple[Path, Mapping[str, Any], str]:
    if trusted_local is not True:
        raise ValueError("pickle deserialization requires explicit trusted_local=True")
    source = Path(path).resolve()
    source_bytes = source.read_bytes()
    source_sha256 = _sha256_bytes(source_bytes)
    payload = pickle.loads(source_bytes)
    if not isinstance(payload, MappingABC):
        raise ValueError("IOHunter pickle payload must be a mapping")
    return source, payload, source_sha256


def load_iohunter_discovery(
    path: str | Path,
    *,
    campaign: str,
    seed: int,
    trusted_local: bool = False,
) -> IOHunterDiscoveryPayload:
    source, payload, _ = _trusted_pickle(path, trusted_local=trusted_local)
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
    source, payload, source_sha256 = _trusted_pickle(path, trusted_local=trusted_local)
    return _build_iohunter_label_evaluator(
        payload,
        campaign=campaign,
        source_path=str(source),
        source_sha256=source_sha256,
    )


__all__ = [
    "IOHUNTER_CAMPAIGNS",
    "IOHUNTER_LAYER_RELATIONS",
    "IOHUNTER_STATIC_PLACEHOLDER_TIMESTAMP",
    "IOHunterDiscoveryPayload",
    "IOHunterLabelEvaluator",
    "IOHunterOfficialFold",
    "adapt_iohunter_payload",
    "build_iohunter_label_evaluator",
    "iohunter_capability",
    "load_iohunter_discovery",
    "load_iohunter_label_evaluator",
]
