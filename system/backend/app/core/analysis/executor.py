from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from app.core.analysis.contracts import AnalysisRunStatus, EventSnapshot, UnknownAnalysisStage, normalize_analysis_stage
from app.core.analysis.registry import AnalysisRegistry
from app.core.analysis.runtime import InternalStudentRuntime, InternalTeacherJobPort


class CoordinationEngine(Protocol):
    async def analyze(self, snapshot: EventSnapshot, options: dict[str, Any]) -> dict[str, Any]:
        ...


class PropagationEngine(Protocol):
    async def hindcast(self, snapshot: EventSnapshot, options: dict[str, Any]) -> dict[str, Any]:
        ...


class StudentRuntime(Protocol):
    async def predict(self, case: dict[str, Any]) -> dict[str, Any]:
        ...


class TeacherJobPort(Protocol):
    async def submit(self, case: dict[str, Any]) -> dict[str, Any]:
        ...


@dataclass(slots=True)
class AnalysisEnginePorts:
    coordination: CoordinationEngine
    propagation: PropagationEngine
    student: StudentRuntime
    teacher: TeacherJobPort


class AnalysisExecutor:
    def __init__(self, *, registry: AnalysisRegistry, engines: AnalysisEnginePorts) -> None:
        self.registry = registry
        self.engines = engines

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
            result = await self._execute_stage(stage, snapshot, stage_options)
            results[stage] = result
            artifact_manifest["stages"][stage] = _stage_artifact_record(stage, result)
            await self.registry.update_artifact_manifest(run_id, artifact_manifest)
            await self.registry.append_run_event(
                run_id,
                event_type=_stage_completed_event_type(stage, result),
                status=AnalysisRunStatus.RUNNING,
                payload={"stage": stage, "result": result},
            )

        final_status = _final_status(results)
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
                "results": results,
                "artifact_manifest": artifact_manifest,
            },
        )
        updated["results"] = results
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
    ) -> dict[str, Any]:
        if stage == "coordination_discover":
            return await self.engines.coordination.analyze(snapshot, options)
        if stage == "propagation_analysis":
            return await self.engines.propagation.hindcast(snapshot, options)
        if stage == "student":
            return await self.engines.student.predict(_case_from_snapshot(snapshot, options=options))
        if stage == "teacher":
            return await self.engines.teacher.submit(_case_from_snapshot(snapshot, options=options))
        raise UnknownAnalysisStage(f"Unknown analysis stage: {stage}")


class SnapshotCoordinationEngine:
    async def analyze(self, snapshot: EventSnapshot, options: dict[str, Any]) -> dict[str, Any]:
        from app.core.analysis.coordination_discover import analyze_coordination_discover_snapshot
        from app.core.analysis.coordination_discover_adapter import try_load_coordination_discover_result

        research_options = dict(options)
        active_model = research_options.get("active_model")
        if isinstance(active_model, dict) and active_model.get("artifact_uri"):
            research_options.setdefault("artifact_dir", active_model["artifact_uri"])
        research_result, fallback_reason = try_load_coordination_discover_result(snapshot, research_options)
        if research_result is not None:
            return research_result

        result = analyze_coordination_discover_snapshot(snapshot, options)
        result["fallback"] = True
        result["fallback_reason"] = fallback_reason or "coordination_discover_artifact_unavailable"
        result["fallback_policy"] = "evidence_runtime_v2"
        return result


class PropagationAnalysisPropagationEngine:
    async def hindcast(self, snapshot: EventSnapshot, options: dict[str, Any]) -> dict[str, Any]:
        from app.services.propagation_prediction_service import predict_event_macro_micro

        result = await predict_event_macro_micro(
            posts=snapshot.posts,
            comments=snapshot.comments,
            top_k=int(options.get("top_k", 10) or 10),
            checkpoint_path=(options.get("active_model") or {}).get("artifact_uri"),
        )
        return {"technology": "propagation_analysis", **result}


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


def default_analysis_engine_ports() -> AnalysisEnginePorts:
    return AnalysisEnginePorts(
        coordination=SnapshotCoordinationEngine(),
        propagation=PropagationAnalysisPropagationEngine(),
        student=InternalStudentRuntime(),
        teacher=InternalTeacherJobPort(),
    )


def _case_from_snapshot(snapshot: EventSnapshot, *, options: dict[str, Any]) -> dict[str, Any]:
    return {
        "snapshot_id": snapshot.snapshot_id,
        "event_id": snapshot.event_id,
        "platforms": list(snapshot.platforms),
        "posts": list(snapshot.posts),
        "comments": list(snapshot.comments),
        "relationships": [edge.model_dump(mode="json") for edge in snapshot.relationships],
        "quality_report": snapshot.quality_report.model_dump(mode="json"),
        "provenance": [record.model_dump(mode="json") for record in snapshot.provenance],
        "options": dict(options),
    }


def _single_platform(snapshot: EventSnapshot) -> str | None:
    return snapshot.platforms[0] if len(snapshot.platforms) == 1 else None


def _coordination_community_lineage(network: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "community_id": str(cluster.get("cluster_id", index)),
            "size": int(cluster.get("size", 0) or 0),
            "members": [str(member) for member in cluster.get("members", [])],
            "evidence": {
                "edge_count": int(cluster.get("edge_count", 0) or 0),
                "total_weight": int(cluster.get("total_weight", 0) or 0),
                "shared_objects": list(cluster.get("shared_objects", [])),
            },
        }
        for index, cluster in enumerate(network.get("clusters", []) or [])
        if isinstance(cluster, dict)
    ]


def _coordination_account_risk_tiers(account_rows: Any) -> list[dict[str, Any]]:
    if not isinstance(account_rows, list):
        return []
    tiers: list[dict[str, Any]] = []
    for row in account_rows:
        if not isinstance(row, dict):
            continue
        account_id = str(row.get("account_id") or "").strip()
        if not account_id:
            continue
        tiers.append(
            {
                "account_id": account_id,
                "account_label": row.get("account_label") or account_id,
                "tier": "observed_coordination",
                "evidence": {
                    "degree": int(row.get("degree", 0) or 0),
                    "avg_weight": float(row.get("avg_weight", 0) or 0),
                    "avg_time_delta": float(row.get("avg_time_delta", 0) or 0),
                    "coordinated_shares_count": int(row.get("coordinated_shares_count", 0) or 0),
                    "shared_objects_preview": list(row.get("shared_objects_preview", []) or []),
                },
            }
        )
    return tiers


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
    }
