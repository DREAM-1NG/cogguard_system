"""Strict BotRHG contracts for paper-faithful social-bot adaptation."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from .contracts import DatasetManifest

__all__ = [
    "StrictAccountRecord",
    "StrictCorpus",
    "StrictFeatureSchema",
    "StrictGraph",
    "StrictRelationEdge",
]


@dataclass(frozen=True, slots=True)
class StrictAccountRecord:
    """One labeled account with paper-aligned text, properties, and provenance."""

    account_id: str
    label: int
    text: str
    post_count: int
    source_file_hash: str
    source_encoding: str
    dataset_name: str = "botection"
    source_label: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    split_group: str = ""
    numeric_features: dict[str, float] = field(default_factory=dict)
    categorical_features: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class StrictRelationEdge:
    """One directed relation edge in the account graph."""

    source_account_id: str
    target_account_id: str
    relation_type: str


@dataclass(frozen=True, slots=True)
class StrictGraph:
    """Graph snapshot for one corpus."""

    node_ids: tuple[str, ...]
    edges: tuple[StrictRelationEdge, ...]
    relation_types: tuple[str, ...]
    available: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class StrictFeatureSchema:
    """Feature schema derived from one training split."""

    numeric_fields: tuple[str, ...]
    categorical_fields: tuple[str, ...]
    categorical_vocab: dict[str, tuple[str, ...]]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class StrictCorpus:
    """Loaded dataset, graph, and manifest for strict BotRHG training."""

    records: list[StrictAccountRecord]
    graph: StrictGraph
    manifest: DatasetManifest

