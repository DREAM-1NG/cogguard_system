from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.core.analysis.contracts import (
    AnalysisRunStatus,
    AnalysisStageContext,
    EventSnapshot,
    UnknownAnalysisStage,
    normalize_analysis_stage,
)
from app.core.analysis.registry import AnalysisRegistry
from app.core.analysis.stages import (
    AnalysisStagePort,
    DefaultSemanticEngine,
    PropagationAnalysisPropagationEngine,
    SemanticEnrichmentStage,
    SnapshotCoordinationEngine,
    StudentReviewStage,
    TeacherReviewStage,
    UnavailableStudentRuntime,
    UnavailableTeacherJobPort,
    default_analysis_stage_registry,
)


@dataclass(slots=True)
class AnalysisEnginePorts:
    """One-release adapter for callers that still construct role-specific engines."""

    coordination: Any
    propagation: Any
    student: Any
    teacher: Any
    semantic: Any | None = None


class AnalysisExecutor:
    def __init__(
        self,
        *,
        registry: AnalysisRegistry,
        stages: dict[str, AnalysisStagePort] | None = None,
        engines: AnalysisEnginePorts | None = None,
    ) -> None:
        if stages is not None and engines is not None:
            raise ValueError("Configure either Analysis Stage ports or legacy engine ports, not both")
        self.registry = registry
        self.engines = engines
        if stages is not None:
            self.stages = dict(stages)
        elif engines is not None:
            self.stages = _legacy_stage_registry(engines)
        else:
            self.stages = default_analysis_stage_registry()

    async def execute_run(self, run_id: str) -> dict[str, Any]:
        run = await self.registry.get_run(run_id)
        if run is None:
            raise KeyError(f"Analysis run not found: {run_id}")

        stages = [_normalize_stage(stage) for stage in run.get("requested_stages", [])]
        options = dict(run.get("options") or {})
        snapshot = await self.registry.load_event_snapshot(str(run["snapshot_id"]))
        await self.registry.transition_run_status(
            run_id,
            AnalysisRunStatus.RUNNING,
            event_type="run_started",
            payload={"snapshot_id": snapshot.snapshot_id, "requested_stages": stages},
        )

        results: dict[str, Any] = {}
        active_models = await self._active_models()
        artifact_manifest: dict[str, Any] = {
            "schema": "cogguard.analysis.artifact_manifest.v1",
            "snapshot_id": snapshot.snapshot_id,
            "data_fingerprint": snapshot.data_fingerprint,
            "run_id": run_id,
            "prototype": True,
            "stages": {},
        }
        for stage in stages:
            stage_options = _stage_options(options, stage)
            active_model = active_models.get(_stage_technology(stage))
            if active_model:
                stage_options["active_model"] = active_model
            await self.registry.append_run_event(
                run_id,
                event_type="stage_started",
                status=AnalysisRunStatus.RUNNING,
                payload={"stage": stage, "options": stage_options},
            )
            result = await self._execute_stage(
                stage,
                snapshot,
                stage_options,
                results,
                run_id=run_id,
            )
            results[stage] = result
            artifact_ref = await self.registry.save_run_artifact(
                run_id=run_id,
                artifact_key=f"stage:{stage}:result",
                payload=result,
            )
            result_summary = _stage_result_summary(stage, result)
            artifact_manifest["stages"][stage] = {
                **_stage_artifact_record(stage, result),
                "result_artifact": _artifact_event_ref(artifact_ref),
                "result_summary": result_summary,
            }
            await self.registry.update_artifact_manifest(run_id, artifact_manifest)
            await self.registry.append_run_event(
                run_id,
                event_type=_stage_completed_event_type(stage, result),
                status=AnalysisRunStatus.RUNNING,
                payload={
                    "stage": stage,
                    "result_summary": result_summary,
                    "result_artifact": _artifact_event_ref(artifact_ref),
                },
            )

        final_status = _final_status(results)
        result_summary = {
            stage: _stage_result_summary(stage, result)
            for stage, result in results.items()
        }
        event_type = {
            AnalysisRunStatus.AWAITING_REVIEW: "run_awaiting_review",
            AnalysisRunStatus.NEEDS_EVIDENCE: "run_needs_evidence",
            AnalysisRunStatus.COMPLETED: "run_completed",
        }[final_status]
        updated = await self.registry.transition_run_status(
            run_id,
            final_status,
            event_type=event_type,
            payload={
                "snapshot_id": snapshot.snapshot_id,
                "results": result_summary,
                "artifact_manifest": artifact_manifest,
            },
        )
        updated["results"] = results
        updated["result_summary"] = result_summary
        updated["artifact_manifest"] = artifact_manifest
        return updated

    async def _active_models(self) -> dict[str, dict[str, Any]]:
        """Read approved pointers when the persistence store exposes them.

        Missing pointers are intentional: the existing artifact-first/fallback
        policy remains the only source of runtime output in that case.
        """

        getter = getattr(self.registry, "get_active_model", None)
        if getter is None:
            return {}
        models: dict[str, dict[str, Any]] = {}
        for technology in ("coordination_discover", "propagation_analysis", "review_student", "review_teacher"):
            model = await getter(technology)
            if isinstance(model, dict) and model.get("status") == "active":
                models[technology] = model
        return models

    async def _execute_stage(
        self,
        stage: str,
        snapshot: EventSnapshot,
        options: dict[str, Any],
        results: dict[str, Any],
        *,
        run_id: str | None = None,
    ) -> dict[str, Any]:
        port = self.stages.get(stage)
        if port is None:
            raise UnknownAnalysisStage(f"Unknown analysis stage: {stage}")
        return await port.execute(
            AnalysisStageContext(
                stage=stage,
                run_id=run_id or "",
                snapshot=snapshot,
                options=dict(options),
                prior_results=dict(results),
            )
        )


@dataclass(slots=True)
class _LegacyCoordinationStage:
    engines: AnalysisEnginePorts

    async def execute(self, context: AnalysisStageContext) -> dict[str, Any]:
        return await self.engines.coordination.analyze(context.snapshot, context.options)


@dataclass(slots=True)
class _LegacyPropagationStage:
    engines: AnalysisEnginePorts

    async def execute(self, context: AnalysisStageContext) -> dict[str, Any]:
        return await self.engines.propagation.hindcast(context.snapshot, context.options)


@dataclass(slots=True)
class _LegacyStudentStage:
    engines: AnalysisEnginePorts

    async def execute(self, context: AnalysisStageContext) -> dict[str, Any]:
        return await self.engines.student.predict(context.review_case())


@dataclass(slots=True)
class _LegacyTeacherStage:
    engines: AnalysisEnginePorts

    async def execute(self, context: AnalysisStageContext) -> dict[str, Any]:
        return await self.engines.teacher.submit(context.review_case())


@dataclass(slots=True)
class _LegacySemanticStage:
    engines: AnalysisEnginePorts

    async def execute(self, context: AnalysisStageContext) -> dict[str, Any]:
        return await SemanticEnrichmentStage(self.engines.semantic).execute(context)


def _legacy_stage_registry(engines: AnalysisEnginePorts) -> dict[str, AnalysisStagePort]:
    return {
        "coordination_discover": _LegacyCoordinationStage(engines),
        "propagation_analysis": _LegacyPropagationStage(engines),
        "semantic_enrichment": _LegacySemanticStage(engines),
        "student": _LegacyStudentStage(engines),
        "teacher": _LegacyTeacherStage(engines),
    }


def default_analysis_engine_ports() -> AnalysisEnginePorts:
    """Build the one-release role-specific adapter used by legacy callers."""
    from app.core.analysis.runtime import InternalStudentRuntime, InternalTeacherJobPort

    return AnalysisEnginePorts(
        coordination=SnapshotCoordinationEngine(),
        propagation=PropagationAnalysisPropagationEngine(),
        student=InternalStudentRuntime(),
        teacher=InternalTeacherJobPort(),
        semantic=DefaultSemanticEngine(),
    )

def _stage_options(options: dict[str, Any], stage: str) -> dict[str, Any]:
    value = options.get(stage)
    return dict(value) if isinstance(value, dict) else {}


def _stage_technology(stage: str) -> str:
    return {
        "student": "review_student",
        "teacher": "review_teacher",
    }.get(stage, stage)


def _normalize_stage(stage: Any) -> str:
    return normalize_analysis_stage(stage)


def _final_status(results: dict[str, Any]) -> AnalysisRunStatus:
    if _teacher_dispatch_failed(results.get("teacher")):
        return AnalysisRunStatus.NEEDS_EVIDENCE
    if _teacher_job_id(results.get("teacher")):
        return AnalysisRunStatus.AWAITING_REVIEW
    if any(_needs_evidence(result) for result in results.values()):
        return AnalysisRunStatus.NEEDS_EVIDENCE
    return AnalysisRunStatus.COMPLETED


def _teacher_job_id(result: Any) -> str:
    if not isinstance(result, dict):
        return ""
    return str(result.get("job_id") or "").strip()


def _stage_completed_event_type(stage: str, result: Any) -> str:
    if stage == "teacher" and _teacher_dispatch_failed(result):
        return "teacher_job_failed"
    if stage == "teacher" and _teacher_job_id(result):
        return "teacher_job_submitted"
    return "stage_completed"


def _needs_evidence(result: Any) -> bool:
    if not isinstance(result, dict):
        return False
    return str(result.get("status") or "").strip() in {
        "unavailable",
        "missing_data",
        "model_unavailable",
        "missing_checkpoint",
        "data_insufficient",
        "failed",
        "dispatch_failed",
        "persistence_failed",
        "blocked",
        "model_weights_blocked",
    }


def _teacher_dispatch_failed(result: Any) -> bool:
    if not isinstance(result, dict):
        return False
    return str(result.get("status") or "").strip() in {
        "failed",
        "dispatch_failed",
        "persistence_failed",
    }


def _stage_artifact_record(stage: str, result: Any) -> dict[str, Any]:
    """Normalize runtime provenance so fallback output cannot look publishable."""
    row = result if isinstance(result, dict) else {}
    status = str(row.get("status") or "unknown")
    fallback = bool(row.get("fallback"))
    missing_checkpoint = status == "missing_checkpoint" or bool(row.get("missing_checkpoint"))
    explicit_claimability = str(row.get("claimability") or "").strip().lower()
    artifact_uri = row.get("artifact_dir") or row.get("artifact_uri")
    checkpoint_uri = row.get("checkpoint_path") or row.get("checkpoint_uri")
    claimable = (
        explicit_claimability == "claimable"
        and bool(artifact_uri or checkpoint_uri)
        and not fallback
        and not missing_checkpoint
        and status in {"ok", "completed"}
    )
    claimability = "claimable" if claimable else "non_claimable"
    execution_mode, prototype_status = _stage_execution_state(row, status=status, fallback=fallback)
    return {
        "stage": stage,
        "technology": row.get("technology") or stage,
        "model_version": row.get("model_version") or row.get("model") or "unversioned_runtime",
        "artifact_uri": artifact_uri,
        "checkpoint_uri": checkpoint_uri,
        "status": status,
        "fallback": fallback,
        "fallback_reason": row.get("fallback_reason"),
        "claimability": claimability,
        "execution_mode": execution_mode,
        "prototype_status": prototype_status,
        "research_claim": claimability == "claimable",
    }


def _stage_result_summary(stage: str, result: Any) -> dict[str, Any]:
    """Build a compact run/event payload while the full result lives as an artifact."""

    if not isinstance(result, dict):
        return {"stage": stage, "result_type": type(result).__name__}

    summary: dict[str, Any] = {"stage": stage}
    for key, value in result.items():
        if key in {
            "status",
            "technology",
            "model",
            "model_version",
            "verdict_type",
            "verdict_id",
            "job_id",
            "task_id",
            "dispatch_backend",
            "label",
            "risk_level",
            "fallback",
            "fallback_reason",
            "fallback_policy",
            "claimability",
            "abstain",
            "review_required",
        }:
            summary[key] = _compact_scalar(value)
        elif key in {"score", "confidence"} and isinstance(value, (int, float)):
            summary[key] = float(value)
        elif key in {"scale_interval", "platforms", "review_reason"}:
            compact_list = _compact_scalar_list(value)
            if compact_list is not None:
                summary[key] = compact_list
        elif key in {"summary", "protocol", "advisory"} and isinstance(value, dict):
            summary[key] = _compact_mapping(value, max_items=24)

    for key in (
        "evidence_edges",
        "account_risk_tiers",
        "community_lineage",
        "windows",
        "next_hop_ranking",
        "posts",
        "comments",
        "evidence",
        "signals",
    ):
        if key in result:
            summary[f"{key}_summary"] = _shape_summary(result[key])

    network = result.get("network")
    if isinstance(network, dict):
        summary["network_summary"] = _network_summary(network)
    return summary


def _artifact_event_ref(artifact_ref: dict[str, Any]) -> dict[str, Any]:
    """Return only safe artifact locator fields for events and manifests."""

    keys = (
        "stored",
        "collection",
        "artifact_id",
        "artifact_key",
        "payload_sha256",
        "payload_size_chars",
        "chunk_count",
        "reason",
    )
    return {key: artifact_ref[key] for key in keys if key in artifact_ref}


def _compact_mapping(value: dict[str, Any], *, max_items: int) -> dict[str, Any]:
    compact: dict[str, Any] = {}
    for index, (key, item) in enumerate(value.items()):
        if index >= max_items:
            compact["truncated"] = True
            break
        if _is_scalar(item):
            compact[str(key)] = _compact_scalar(item)
            continue
        scalar_list = _compact_scalar_list(item)
        if scalar_list is not None:
            compact[str(key)] = scalar_list
        else:
            compact[str(key)] = _shape_summary(item)
    return compact


def _compact_scalar_list(value: Any, *, max_items: int = 20) -> list[Any] | None:
    if not isinstance(value, list) or len(value) > max_items:
        return None
    if not all(_is_scalar(item) for item in value):
        return None
    return [_compact_scalar(item) for item in value]


def _compact_scalar(value: Any) -> Any:
    if isinstance(value, str):
        return value[:512]
    return value


def _shape_summary(value: Any) -> dict[str, Any]:
    if isinstance(value, list):
        return {"type": "list", "count": len(value)}
    if isinstance(value, dict):
        return {"type": "dict", "keys": sorted(str(key) for key in value.keys())[:20], "key_count": len(value)}
    return {"type": type(value).__name__}


def _network_summary(network: dict[str, Any]) -> dict[str, Any]:
    return {
        "node_count": int(network.get("node_count") or len(network.get("nodes") or [])),
        "edge_count": int(network.get("edge_count") or len(network.get("edges") or [])),
        "cluster_count": int(network.get("cluster_count") or len(network.get("clusters") or [])),
        "component_count": int(network.get("component_count") or 0),
    }


def _is_scalar(value: Any) -> bool:
    return value is None or isinstance(value, (str, int, float, bool))


def _stage_execution_state(
    result: dict[str, Any],
    *,
    status: str,
    fallback: bool,
) -> tuple[str, str]:
    """Classify runtime evidence without upgrading a demo into a claim."""

    if status in {"failed", "dispatch_failed", "persistence_failed"}:
        return "failed", "needs_evidence"
    if status in {"missing_data", "missing_checkpoint", "model_unavailable", "data_insufficient", "unavailable"}:
        return "blocked", "needs_evidence"
    model_name = str(result.get("model_version") or result.get("model") or "").lower()
    protocol = result.get("protocol") if isinstance(result.get("protocol"), dict) else {}
    if (
        fallback
        or model_name.endswith("live-runtime")
        or "live_runtime" in model_name
        or str(protocol.get("claim_status") or "") == "fallback_only_not_research_claim"
    ):
        return "fallback", "prototype_only"
    if str(result.get("model_status") or "") in {"shadow_untrained", "checkpoint_registered_shadow"}:
        return "shadow", "prototype_only"
    if result.get("verdict_type") == "teacher_advisory" or result.get("canonical_allowed") is False:
        return "advisory", "awaiting_analyst_approval"
    if result.get("artifact_manifest") and not result.get("checkpoint_path"):
        return "artifact", "artifact_backed_non_claimable"
    return "runtime", "claimable" if str(result.get("claimability") or "").lower() == "claimable" else "prototype_only"
