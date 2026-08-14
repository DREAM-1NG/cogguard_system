from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from app.core.analysis.contracts import AnalysisRunStatus, EventSnapshot, UnknownAnalysisStage, normalize_analysis_stage
from app.core.analysis.registry import AnalysisRegistry
from app.core.analysis.runtime import InternalStudentRuntime, InternalTeacherJobPort
from app.core.semantic.runtime import (
    ModelWeightsBlockedError,
    SemanticEnrichmentRuntime,
    VerifiedPropagationArtifact,
)


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


class SemanticEngine(Protocol):
    async def enrich(
        self,
        snapshot: EventSnapshot,
        *,
        options: dict[str, Any],
        coordination: dict[str, Any] | None,
        propagation: dict[str, Any] | None,
    ) -> dict[str, Any]:
        ...


@dataclass(slots=True)
class AnalysisEnginePorts:
    coordination: CoordinationEngine
    propagation: PropagationEngine
    student: StudentRuntime
    teacher: TeacherJobPort
    semantic: SemanticEngine | None = None


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
        verified_prior: dict[str, VerifiedPropagationArtifact] = {}
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
                run_id=run_id,
                prior_results=results,
                verified_prior=verified_prior,
            )
            results[stage] = result
            artifact_ref = await self.registry.save_run_artifact(
                run_id=run_id,
                artifact_key=f"stage:{stage}:result",
                payload=result,
            )
            if stage == "propagation_analysis":
                verified = await self._load_verified_propagation_artifact(
                    run_id=run_id,
                    snapshot=snapshot,
                    artifact_ref=artifact_ref,
                )
                if verified is not None:
                    verified_prior[stage] = verified
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
        *,
        run_id: str | None = None,
        prior_results: dict[str, Any] | None = None,
        verified_prior: dict[str, VerifiedPropagationArtifact] | None = None,
    ) -> dict[str, Any]:
        if stage == "coordination_discover":
            return await self.engines.coordination.analyze(snapshot, options)
        if stage == "propagation_analysis":
            return await self.engines.propagation.hindcast(snapshot, options)
        if stage == "student":
            return await self.engines.student.predict(
                _case_from_snapshot(snapshot, options=options, run_id=run_id)
            )
        if stage == "teacher":
            return await self.engines.teacher.submit(
                _case_from_snapshot(snapshot, options=options, run_id=run_id)
            )
        if stage == "semantic_enrichment":
            if self.engines.semantic is None:
                return {
                    "technology": "semantic_enrichment",
                    "status": "unavailable",
                    "runtime_status": "blocked",
                    "blocking_reason": "Semantic engine is not configured",
                    "fallback": False,
                }
            try:
                prior = prior_results or {}
                verified = verified_prior or {}
                return await self.engines.semantic.enrich(
                    snapshot,
                    options=options,
                    coordination=prior.get("coordination_discover"),
                    propagation=verified.get("propagation_analysis"),
                )
            except ModelWeightsBlockedError as exc:
                return {
                    "technology": "semantic_enrichment",
                    "status": "model_weights_blocked",
                    "runtime_status": "blocked",
                    "blocking_reason": str(exc),
                    "fallback": False,
                }
        raise UnknownAnalysisStage(f"Unknown analysis stage: {stage}")

    async def _load_verified_propagation_artifact(
        self,
        *,
        run_id: str,
        snapshot: EventSnapshot,
        artifact_ref: dict[str, Any],
    ) -> VerifiedPropagationArtifact | None:
        if not artifact_ref.get("stored"):
            return None
        artifact_key = str(artifact_ref.get("artifact_key") or "")
        if artifact_key != "stage:propagation_analysis:result":
            return None
        try:
            payload = await self.registry.load_run_artifact(run_id, artifact_key)
        except (KeyError, TypeError, ValueError):
            return None
        if not isinstance(payload, dict):
            return None
        return VerifiedPropagationArtifact(
            payload=payload,
            snapshot_id=snapshot.snapshot_id,
            data_fingerprint=snapshot.data_fingerprint,
            artifact_ref=dict(artifact_ref),
        )


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
            checkpoint_path=(options.get("active_model") or {}).get("checkpoint_path"),
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


class LocalSemanticEnrichmentEngine:
    """Lazy adapter for the fixed local-model semantic runtime."""

    def __init__(self, runtime: SemanticEnrichmentRuntime | None = None) -> None:
        self._runtime = runtime

    async def enrich(
        self,
        snapshot: EventSnapshot,
        *,
        options: dict[str, Any],
        coordination: dict[str, Any] | None,
        propagation: dict[str, Any] | None,
    ) -> dict[str, Any]:
        if self._runtime is None:
            self._runtime = SemanticEnrichmentRuntime()
        return self._runtime.enrich(
            snapshot,
            coordination=coordination,
            propagation=propagation,
            claim=str(options.get("claim") or "") or None,
        )


def default_analysis_engine_ports(
    semantic_runtime: SemanticEnrichmentRuntime | None = None,
    semantic_engine: SemanticEngine | None = None,
) -> AnalysisEnginePorts:
    if semantic_runtime is not None and semantic_engine is not None:
        raise ValueError("Provide either semantic_runtime or semantic_engine, not both")
    return AnalysisEnginePorts(
        coordination=SnapshotCoordinationEngine(),
        propagation=PropagationAnalysisPropagationEngine(),
        student=InternalStudentRuntime(),
        teacher=InternalTeacherJobPort(),
        semantic=semantic_engine or LocalSemanticEnrichmentEngine(semantic_runtime),
    )


def _case_from_snapshot(
    snapshot: EventSnapshot,
    *,
    options: dict[str, Any],
    run_id: str | None = None,
) -> dict[str, Any]:
    case = {
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
    if run_id:
        case["run_id"] = run_id
    return case


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
