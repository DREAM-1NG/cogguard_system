"""Uniform Analysis Stage ports and the default adapter registry."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Protocol

from app.core.analysis.contracts import AnalysisStageContext, EventSnapshot
from app.core.analysis.runtime import InternalStudentRuntime, InternalTeacherJobPort


class AnalysisStagePort(Protocol):
    async def execute(self, context: AnalysisStageContext) -> dict[str, Any]: ...


class CoordinationDiscoverStage:
    async def execute(self, context: AnalysisStageContext) -> dict[str, Any]:
        return await _run_coordination_discover(context.snapshot, context.options)


class PropagationAnalysisStage:
    async def execute(self, context: AnalysisStageContext) -> dict[str, Any]:
        return await _run_propagation_analysis(context.snapshot, context.options)


@dataclass(slots=True)
class StudentReviewStage:
    runtime: Any

    async def execute(self, context: AnalysisStageContext) -> dict[str, Any]:
        return await self.runtime.predict(context.review_case())


@dataclass(slots=True)
class TeacherReviewStage:
    runtime: Any

    async def execute(self, context: AnalysisStageContext) -> dict[str, Any]:
        return await self.runtime.submit(context.review_case())


@dataclass(slots=True)
class SemanticEnrichmentStage:
    runtime: Any | None = None

    async def execute(self, context: AnalysisStageContext) -> dict[str, Any]:
        runtime = self.runtime or DefaultSemanticEngine()
        try:
            return await runtime.enrich(
                context.snapshot,
                options=context.options,
                coordination=context.prior_results.get("coordination_discover"),
                propagation=context.prior_results.get("propagation_analysis"),
            )
        except Exception as exc:
            from app.core.semantic.runtime import ModelWeightsBlockedError

            if isinstance(exc, ModelWeightsBlockedError):
                return {
                    "technology": "semantic_enrichment",
                    "status": "model_weights_blocked",
                    "runtime_status": "blocked",
                    "blocking_reason": str(exc),
                    "fallback": False,
                }
            raise


class DefaultSemanticEngine:
    async def enrich(self, snapshot, *, options, coordination, propagation):
        from app.core.semantic.runtime import SemanticEnrichmentRuntime

        runtime = SemanticEnrichmentRuntime(model_root=options.get("model_root", r"G:\CISCN\hf_models"))
        return runtime.enrich(
            snapshot,
            coordination=coordination,
            propagation=propagation,
            claim=options.get("claim"),
        )


class SnapshotCoordinationEngine:
    """One-release adapter for callers using the former engine interface."""

    async def analyze(self, snapshot: EventSnapshot, options: dict[str, Any]) -> dict[str, Any]:
        return await _run_coordination_discover(snapshot, options)


class PropagationAnalysisPropagationEngine:
    """One-release adapter for callers using the former engine interface."""

    async def hindcast(self, snapshot: EventSnapshot, options: dict[str, Any]) -> dict[str, Any]:
        return await _run_propagation_analysis(snapshot, options)


class UnavailableStudentRuntime:
    async def predict(self, case: dict[str, Any]) -> dict[str, Any]:
        return {
            "technology": "student",
            "status": "unavailable",
            "verdict_type": "preliminary",
            "snapshot_id": case.get("snapshot_id"),
            "event_id": case.get("event_id"),
            "reason": "Student runtime is not configured for this executor.",
            "abstain": True,
            "review_required": True,
        }


class UnavailableTeacherJobPort:
    async def submit(self, case: dict[str, Any]) -> dict[str, Any]:
        return {
            "technology": "teacher",
            "status": "unavailable",
            "verdict_type": "teacher_advisory",
            "snapshot_id": case.get("snapshot_id"),
            "event_id": case.get("event_id"),
            "reason": "Teacher job port is not configured for this executor.",
            "review_required": True,
        }


def default_analysis_stage_registry() -> dict[str, AnalysisStagePort]:
    return {
        "coordination_discover": CoordinationDiscoverStage(),
        "propagation_analysis": PropagationAnalysisStage(),
        "semantic_enrichment": SemanticEnrichmentStage(),
        "student": StudentReviewStage(InternalStudentRuntime()),
        "teacher": TeacherReviewStage(InternalTeacherJobPort()),
    }


async def _run_coordination_discover(snapshot: EventSnapshot, options: dict[str, Any]) -> dict[str, Any]:
    from app.core.analysis.coordination_discover import analyze_coordination_discover_snapshot
    from app.core.analysis.coordination_discover_adapter import try_load_coordination_discover_result

    research_options = dict(options)
    active_model = research_options.get("active_model")
    if isinstance(active_model, Mapping) and active_model.get("artifact_uri"):
        research_options.setdefault("artifact_dir", active_model["artifact_uri"])
    research_result, fallback_reason = try_load_coordination_discover_result(snapshot, research_options)
    if research_result is not None:
        return research_result
    result = analyze_coordination_discover_snapshot(snapshot, options)
    result["fallback"] = True
    result["fallback_reason"] = fallback_reason or "coordination_discover_artifact_unavailable"
    result["fallback_policy"] = "evidence_runtime_v2"
    return result


async def _run_propagation_analysis(snapshot: EventSnapshot, options: dict[str, Any]) -> dict[str, Any]:
    from app.services.propagation_prediction_service import predict_event_macro_micro

    active_model = options.get("active_model")
    checkpoint_path = active_model.get("checkpoint_path") if isinstance(active_model, Mapping) else None
    result = await predict_event_macro_micro(
        posts=snapshot.posts,
        comments=snapshot.comments,
        top_k=int(options.get("top_k", 10) or 10),
        checkpoint_path=checkpoint_path,
    )
    return {"technology": "propagation_analysis", **result}


__all__ = [
    "AnalysisStagePort",
    "CoordinationDiscoverStage",
    "DefaultSemanticEngine",
    "PropagationAnalysisPropagationEngine",
    "PropagationAnalysisStage",
    "SemanticEnrichmentStage",
    "SnapshotCoordinationEngine",
    "StudentReviewStage",
    "TeacherReviewStage",
    "UnavailableStudentRuntime",
    "UnavailableTeacherJobPort",
    "default_analysis_stage_registry",
]
