from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from app.core.analysis.contracts import AnalysisRunStatus, EventSnapshot
from app.core.analysis.registry import AnalysisRegistry


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
        for stage in stages:
            stage_options = _stage_options(options, stage)
            await self.registry.append_run_event(
                run_id,
                event_type="stage_started",
                status=AnalysisRunStatus.RUNNING,
                payload={"stage": stage, "options": stage_options},
            )
            result = await self._execute_stage(stage, snapshot, stage_options)
            results[stage] = result
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
            payload={"snapshot_id": snapshot.snapshot_id, "results": results},
        )
        updated["results"] = results
        return updated

    async def _execute_stage(
        self,
        stage: str,
        snapshot: EventSnapshot,
        options: dict[str, Any],
    ) -> dict[str, Any]:
        if stage == "kt1":
            return await self.engines.coordination.analyze(snapshot, options)
        if stage == "kt2":
            return await self.engines.propagation.hindcast(snapshot, options)
        if stage == "student":
            return await self.engines.student.predict(_case_from_snapshot(snapshot, options=options))
        if stage == "teacher":
            return await self.engines.teacher.submit(_case_from_snapshot(snapshot, options=options))
        return {"status": "skipped", "reason": f"Unknown analysis stage: {stage}"}


class SnapshotCoordinationEngine:
    async def analyze(self, snapshot: EventSnapshot, options: dict[str, Any]) -> dict[str, Any]:
        from app.services.coordination_service import analyze_coordination_records

        result = analyze_coordination_records(
            list(snapshot.posts),
            list(snapshot.comments),
            time_window=int(options.get("time_window", 60) or 60),
            min_participation=int(options.get("min_participation", 2) or 2),
            edge_weight=float(options.get("edge_weight", 0.5) or 0.5),
            event_id=snapshot.event_id,
            platform=str(options.get("platform") or _single_platform(snapshot) or "") or None,
        )
        status = "data_insufficient" if result.get("error") else "ok"
        return {
            "status": status,
            "technology": "kt1",
            "model_version": "coordination-baseline-v1",
            "snapshot_id": snapshot.snapshot_id,
            "summary": result.get("summary", {}),
            "community_lineage": _coordination_community_lineage(result.get("network", {})),
            "account_risk_tiers": _coordination_account_risk_tiers(result.get("account_stats", [])),
            "evidence_edges": list(result.get("network", {}).get("edges", [])),
            "domain_shift": {
                "status": "not_evaluated",
                "reason": "Baseline coordination runtime does not estimate domain shift.",
            },
            "abstain": status != "ok",
            "network": result.get("network", {}),
            "account_stats": result.get("account_stats", []),
            "group_stats": result.get("group_stats", []),
            "cluster_stats": result.get("cluster_stats", []),
            "error": result.get("error"),
        }


class KT2PropagationEngine:
    async def hindcast(self, snapshot: EventSnapshot, options: dict[str, Any]) -> dict[str, Any]:
        from app.services.kt2_prediction_service import predict_event_macro_micro

        result = await predict_event_macro_micro(
            posts=snapshot.posts,
            comments=snapshot.comments,
            top_k=int(options.get("top_k", 10) or 10),
        )
        return {"technology": "kt2", **result}


class UnavailableStudentRuntime:
    async def predict(self, case: dict[str, Any]) -> dict[str, Any]:
        return {
            "status": "unavailable",
            "verdict_type": "preliminary",
            "reason": "StudentRuntime.predict is not wired to an internal deployed student model yet.",
            "snapshot_id": case.get("snapshot_id"),
        }


class UnavailableTeacherJobPort:
    async def submit(self, case: dict[str, Any]) -> dict[str, Any]:
        return {
            "status": "unavailable",
            "job_id": None,
            "reason": "TeacherJobPort.submit is not wired to an internal Celery teacher DAG yet.",
            "snapshot_id": case.get("snapshot_id"),
        }


def default_analysis_engine_ports() -> AnalysisEnginePorts:
    return AnalysisEnginePorts(
        coordination=SnapshotCoordinationEngine(),
        propagation=KT2PropagationEngine(),
        student=UnavailableStudentRuntime(),
        teacher=UnavailableTeacherJobPort(),
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


def _normalize_stage(stage: Any) -> str:
    value = str(stage or "").strip().lower()
    aliases = {
        "coordination": "kt1",
        "coordination_engine": "kt1",
        "propagation": "kt2",
        "propagation_engine": "kt2",
        "kt3_student": "student",
        "kt3_teacher": "teacher",
    }
    return aliases.get(value, value)


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
        "data_insufficient",
    }
