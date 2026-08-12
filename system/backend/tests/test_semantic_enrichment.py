from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any

from app.core.analysis import DEFAULT_ANALYSIS_STAGES, TimeWindow, build_event_snapshot
from app.core.analysis import semantic_enrichment as semantic_enrichment_module
from app.core.analysis.semantic_enrichment import analyze_semantic_enrichment_snapshot
from app.core.analysis.executor import (
    AnalysisEnginePorts,
    AnalysisExecutor,
    UnavailableTeacherJobPort,
)
from app.core.analysis.registry import AnalysisRegistry


class FakeSnapshotCollection:
    def __init__(self, documents: dict[str, dict[str, Any]]) -> None:
        self.documents = documents

    async def find_one(self, query: dict[str, Any], projection: dict[str, int] | None = None):
        return self.documents.get(str(query["snapshot_id"]))


class FakeArtifactCollection:
    def __init__(self) -> None:
        self.documents: dict[str, dict[str, Any]] = {}

    async def update_one(
        self,
        query: dict[str, Any],
        update: dict[str, Any],
        *,
        upsert: bool = False,
    ) -> None:
        artifact_id = str(query["artifact_id"])
        if "$set" in update:
            self.documents[artifact_id] = {**self.documents.get(artifact_id, {}), **dict(update["$set"])}


class FakeAnalysisStore:
    def __init__(self, snapshot_record: dict[str, Any], run: dict[str, Any]) -> None:
        self.snapshot_record = snapshot_record
        self.runs = {run["run_id"]: dict(run)}
        self.events: list[dict[str, Any]] = []
        self.next_event_id = 1

    async def get_snapshot_record(self, snapshot_id: str) -> dict[str, Any] | None:
        if self.snapshot_record["snapshot_id"] == snapshot_id:
            return dict(self.snapshot_record)
        return None

    async def get_run(self, run_id: str) -> dict[str, Any] | None:
        run = self.runs.get(run_id)
        return dict(run) if run else None

    async def update_run_status(self, *, run_id: str, status, payload: dict[str, Any], finished: bool):
        run = self.runs[run_id]
        run["status"] = status.value
        run["result"] = payload
        if finished:
            run["finished_at"] = "finished"
        return dict(run)

    async def update_artifact_manifest(self, *, run_id: str, manifest: dict[str, Any]):
        run = self.runs[run_id]
        run["artifact_manifest"] = manifest
        return dict(run)

    async def append_run_event(self, *, run_id: str, event_type: str, status, payload: dict[str, Any]):
        event = {
            "id": self.next_event_id,
            "run_id": run_id,
            "event_type": event_type,
            "status": status.value,
            "payload": payload,
        }
        self.next_event_id += 1
        self.events.append(event)
        return dict(event)

    async def list_run_events(self, *, run_id: str, after_id: int = 0, limit: int = 100):
        return [event for event in self.events if event["run_id"] == run_id and event["id"] > after_id][:limit]


class StaticCoordinationEngine:
    async def analyze(self, snapshot, options):
        return {"status": "ok", "summary": {"coordinated_edges": 0}}


class StaticPropagationEngine:
    async def hindcast(self, snapshot, options):
        return {"status": "ok", "next_hop_ranking": {"items": []}}


class StaticStudentRuntime:
    async def predict(self, case):
        return {"status": "ok", "verdict_type": "preliminary", "label": "uncertain"}


class QueuedTeacherJobPort:
    async def submit(self, case):
        return {"status": "queued", "job_id": "teacher_case_review_1", "verdict_type": "teacher_advisory"}


def _dt(day: int, hour: int = 0) -> datetime:
    return datetime(2026, 5, day, hour, tzinfo=timezone.utc)


def _snapshot():
    return build_event_snapshot(
        event_id="trump_visit_2026_05_21",
        posts=[
            {
                "event_id": "trump_visit_2026_05_21",
                "platform": "weibo",
                "post_id": "p1",
                "author_id": "u1",
                "author_name": "新华社",
                "timestamp": _dt(14),
                "content": "特朗普访华欢迎仪式引发大量讨论，中美关系稳定前行。",
                "hashtags": ["特朗普访华", "中美关系"],
            },
            {
                "event_id": "trump_visit_2026_05_21",
                "platform": "xhs",
                "post_id": "p2",
                "author_id": "u2",
                "author_name": "观察账号",
                "timestamp": _dt(14, 1),
                "content": "欢迎宴会细节曝光，网友关注访问行程。",
                "hashtags": ["特朗普访华"],
            },
        ],
        comments=[
            {
                "event_id": "trump_visit_2026_05_21",
                "platform": "weibo",
                "comment_id": "c1",
                "post_id": "p1",
                "reply_to": "p1",
                "author_id": "u3",
                "timestamp": _dt(14, 2),
                "content": "希望关系稳定。",
            }
        ],
        core_window=TimeWindow(start=_dt(11), end=_dt(22)),
        context_window=TimeWindow(start=_dt(1), end=_dt(31)),
    )


def test_default_analysis_stage_contract_stays_four_stage():
    assert DEFAULT_ANALYSIS_STAGES == (
        "coordination_discover",
        "propagation_analysis",
        "student",
        "teacher",
    )


def test_executor_runs_explicit_semantic_enrichment_without_primary_claim():
    async def scenario():
        snapshot = _snapshot()
        store = FakeAnalysisStore(
            snapshot_record={
                "snapshot_id": snapshot.snapshot_id,
                "mongo_collection": "analysis_event_snapshots",
                "mongo_key": snapshot.snapshot_id,
            },
            run={
                "run_id": "run_semantic",
                "event_id": snapshot.event_id,
                "snapshot_id": snapshot.snapshot_id,
                "status": "queued",
                "requested_stages": ["semantic_enrichment"],
                "options": {},
                "finished_at": None,
            },
        )
        registry = AnalysisRegistry(
            mongo_db={
                "analysis_event_snapshots": FakeSnapshotCollection(
                    {snapshot.snapshot_id: snapshot.model_dump(mode="json")}
                ),
                "analysis_run_artifacts": FakeArtifactCollection(),
            },
            store=store,
        )
        executor = AnalysisExecutor(
            registry=registry,
            engines=AnalysisEnginePorts(
                coordination=StaticCoordinationEngine(),
                propagation=StaticPropagationEngine(),
                semantic=None,
                student=StaticStudentRuntime(),
                teacher=UnavailableTeacherJobPort(),
            ),
        )

        result = await executor.execute_run("run_semantic")
        semantic = result["results"]["semantic_enrichment"]

        assert result["status"] == "needs_evidence"
        assert semantic["status"] == "partial"
        assert semantic["technology"] == "semantic_enrichment"
        assert semantic["model_status"] == "candidate_unvalidated"
        assert semantic["stance"]["status"] == "blocked"
        assert semantic["stance"]["code"] == "blocked_missing_primary_claim"
        assert semantic["sentiment"]["summary"]["total_texts"] == 3
        assert semantic["keywords"]["main_posts"][0]["term"]
        assert semantic["topics"]["main_posts"]["topic_count"] >= 1
        assert semantic["entities"]["main_posts"]
        assert result["artifact_manifest"]["stages"]["semantic_enrichment"]["claimability"] == "non_claimable"

    asyncio.run(scenario())


def test_missing_primary_claim_status_is_not_hidden_by_queued_teacher_job():
    async def scenario():
        snapshot = _snapshot()
        store = FakeAnalysisStore(
            snapshot_record={
                "snapshot_id": snapshot.snapshot_id,
                "mongo_collection": "analysis_event_snapshots",
                "mongo_key": snapshot.snapshot_id,
            },
            run={
                "run_id": "run_semantic_teacher",
                "event_id": snapshot.event_id,
                "snapshot_id": snapshot.snapshot_id,
                "status": "queued",
                "requested_stages": ["semantic_enrichment", "teacher"],
                "options": {},
                "finished_at": None,
            },
        )
        registry = AnalysisRegistry(
            mongo_db={
                "analysis_event_snapshots": FakeSnapshotCollection(
                    {snapshot.snapshot_id: snapshot.model_dump(mode="json")}
                ),
                "analysis_run_artifacts": FakeArtifactCollection(),
            },
            store=store,
        )
        executor = AnalysisExecutor(
            registry=registry,
            engines=AnalysisEnginePorts(
                coordination=StaticCoordinationEngine(),
                propagation=StaticPropagationEngine(),
                semantic=None,
                student=StaticStudentRuntime(),
                teacher=QueuedTeacherJobPort(),
            ),
        )

        result = await executor.execute_run("run_semantic_teacher")

        assert result["status"] == "needs_evidence"
        assert result["results"]["teacher"]["job_id"] == "teacher_case_review_1"
        assert result["results"]["semantic_enrichment"]["stance"]["code"] == "blocked_missing_primary_claim"

    asyncio.run(scenario())


def test_semantic_artifact_hash_is_stable_for_identical_inputs(monkeypatch):
    snapshot = _snapshot()

    class SequenceDatetime(datetime):
        call_count = 0

        @classmethod
        def now(cls, tz=None):
            cls.call_count += 1
            return datetime(2026, 5, 14, 12, 0, cls.call_count, tzinfo=tz or timezone.utc)

    monkeypatch.setattr(semantic_enrichment_module, "datetime", SequenceDatetime)

    first = semantic_enrichment_module.analyze_semantic_enrichment_snapshot(
        snapshot,
        {"primary_claim_text": "中美关系稳定前行"},
    )
    second = semantic_enrichment_module.analyze_semantic_enrichment_snapshot(
        snapshot,
        {"primary_claim_text": "中美关系稳定前行"},
    )

    assert first["generated_at"] != second["generated_at"]
    assert first["artifact_sha256"] == second["artifact_sha256"]


def test_semantic_decision_support_recommends_action_refs_without_changing_score_policy():
    snapshot = _snapshot()

    semantic = analyze_semantic_enrichment_snapshot(
        snapshot,
        {"primary_claim_text": "涓編鍏崇郴绋冲畾鍓嶈"},
    )
    recommendations = semantic["decision_support"]["action_recommendations"]

    assert recommendations
    assert recommendations[0]["recommendation_id"] == "semantic_action_review_public_response"
    assert recommendations[0]["action_id"] == "action_review_public_response"
    assert recommendations[0]["status"] == "candidate_unvalidated"
    assert recommendations[0]["score_policy"] == "evidence_overlay_only"
    assert recommendations[0]["evidence_refs"] == [
        "semantic_case_workbench_demo",
        "claim_cctv_primary",
    ]
    assert recommendations[0]["does_not_modify"] == [
        "coordination_discover",
        "propagation_analysis",
        "student",
        "teacher",
    ]
    assert semantic["provenance"]["score_policy"] == "semantic_artifacts_are_evidence_overlay_only"
