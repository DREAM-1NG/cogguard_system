"""Unified event snapshot and analysis-run contracts."""

from app.core.analysis.contracts import (
    AnalysisRunStatus,
    DataQualityReport,
    EventSnapshot,
    EvidenceRelation,
    InvalidRunTransition,
    ProvenanceRecord,
    TimeWindow,
    transition_run_status,
)
from app.core.analysis.registry import AnalysisRegistry, SqlAlchemyAnalysisStore
from app.core.analysis.snapshots import build_event_snapshot
from app.core.analysis.sse import format_sse_event, iter_sse_events, parse_last_event_id

__all__ = [
    "AnalysisRegistry",
    "AnalysisRunStatus",
    "DataQualityReport",
    "EventSnapshot",
    "EvidenceRelation",
    "InvalidRunTransition",
    "ProvenanceRecord",
    "SqlAlchemyAnalysisStore",
    "TimeWindow",
    "build_event_snapshot",
    "format_sse_event",
    "iter_sse_events",
    "parse_last_event_id",
    "transition_run_status",
]
