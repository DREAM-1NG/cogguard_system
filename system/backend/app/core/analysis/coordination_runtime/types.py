from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from app.core.analysis.contracts import EventSnapshot


@dataclass(frozen=True, slots=True)
class ResolvedSnapshotView:
    snapshot: EventSnapshot
    resolution_report: Mapping[str, Any]
    account_mapping: Mapping[str, str] = field(default_factory=dict)
    merged_account_groups: tuple[tuple[str, ...], ...] = ()


@dataclass(frozen=True, slots=True)
class CoordinationDiscoveryResult:
    resolved_view: ResolvedSnapshotView
    batch: Any
    network: dict[str, Any]
    result: dict[str, Any]


__all__ = ["CoordinationDiscoveryResult", "ResolvedSnapshotView"]
