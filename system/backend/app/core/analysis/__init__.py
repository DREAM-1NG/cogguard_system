"""Unified event snapshot and analysis-run contracts."""

from app.core.analysis.contracts import (
    ANALYSIS_STAGE_ALLOWLIST,
    ANALYSIS_STAGE_ALIASES,
    DEFAULT_ANALYSIS_STAGES,
    AnalysisRunStatus,
    AnalysisStageContext,
    DataQualityReport,
    EventSnapshot,
    EvidenceRelation,
    InvalidRunTransition,
    ProvenanceRecord,
    TimeWindow,
    UnknownAnalysisStage,
    normalize_analysis_stage,
    transition_run_status,
)
from app.core.analysis.coordination_discover import (
    analyze_coordination_discover_snapshot,
    build_coordination_discover_evidence_edges,
)
from app.core.analysis.registry import AnalysisRegistry, SqlAlchemyAnalysisStore
from app.core.analysis.snapshots import build_event_snapshot
from app.core.analysis.sse import format_sse_event, iter_sse_events, parse_last_event_id
from app.core.analysis.coordination_discover_adapter import try_load_coordination_discover_result
from app.core.analysis.stages import AnalysisStagePort, default_analysis_stage_registry

__all__ = [
    "AnalysisRegistry",
    "ANALYSIS_STAGE_ALLOWLIST",
    "ANALYSIS_STAGE_ALIASES",
    "AnalysisRunStatus",
    "AnalysisStageContext",
    "AnalysisStagePort",
    "DEFAULT_ANALYSIS_STAGES",
    "DataQualityReport",
    "EventSnapshot",
    "EvidenceRelation",
    "InvalidRunTransition",
    "ProvenanceRecord",
    "SqlAlchemyAnalysisStore",
    "TimeWindow",
    "UnknownAnalysisStage",
    "build_event_snapshot",
    "analyze_coordination_discover_snapshot",
    "build_coordination_discover_evidence_edges",
    "format_sse_event",
    "iter_sse_events",
    "parse_last_event_id",
    "try_load_coordination_discover_result",
    "default_analysis_stage_registry",
    "normalize_analysis_stage",
    "transition_run_status",
]
