from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any

from app.core.analysis import AnalysisRunStatus, TimeWindow, build_event_snapshot
from app.core.analysis.executor import (
    AnalysisEnginePorts,
    AnalysisExecutor,
    UnavailableTeacherJobPort,
    default_analysis_engine_ports,
)
from app.core.analysis.registry import AnalysisRegistry
from app.core.analysis import UnknownAnalysisStage


class FakeSnapshotCollection:
    def __init__(self, documents: dict[str, dict[str, Any]]) -> None:
        self.documents = documents

    async def find_one(self, query: dict[str, Any], projection: dict[str, int] | None = None):
        return self.documents.get(str(query["snapshot_id"]))


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

    async def update_run_status(
        self,
        *,
        run_id: str,
        status: AnalysisRunStatus,
        payload: dict[str, Any],
        finished: bool,
    ) -> dict[str, Any]:
        run = self.runs[run_id]
        run["status"] = status.value
        run["result"] = payload
        if finished:
            run["finished_at"] = "finished"
        return dict(run)

    async def append_run_event(
        self,
        *,
        run_id: str,
        event_type: str,
        status: AnalysisRunStatus,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
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
        return [
            event
            for event in self.events
            if event["run_id"] == run_id and event["id"] > after_id
        ][:limit]


class RecordingCoordinationEngine:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []

    async def analyze(self, snapshot, options):
        self.calls.append((snapshot.snapshot_id, dict(options)))
        return {"status": "ok", "community_count": 2}


class RecordingPropagationEngine:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []

    async def hindcast(self, snapshot, options):
        self.calls.append((snapshot.snapshot_id, dict(options)))
        return {"status": "ok", "scale_interval": [1, 3]}


class MissingCheckpointPropagationEngine:
    async def hindcast(self, snapshot, options):
        return {"status": "missing_checkpoint"}


class RecordingStudentRuntime:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    async def predict(self, case):
        self.calls.append(case)
        return {"verdict_type": "preliminary", "label": "uncertain"}


class RecordingTeacherJobPort:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    async def submit(self, case):
        self.calls.append(case)
        return {"job_id": "teacher_job_1", "status": "queued"}


def _dt(day: int, hour: int = 0) -> datetime:
    return datetime(2026, 5, day, hour, tzinfo=timezone.utc)


def _snapshot():
    return build_event_snapshot(
        event_id="trump_visit",
        posts=[
            {
                "event_id": "trump_visit",
                "platform": "weibo",
                "post_id": "p1",
                "author_id": "u1",
                "timestamp": _dt(12),
                "content": "event claim",
            }
        ],
        comments=[],
        core_window=TimeWindow(start=_dt(11), end=_dt(22)),
        context_window=TimeWindow(start=_dt(1), end=_dt(31)),
    )


def _coordination_snapshot():
    return build_event_snapshot(
        event_id="trump_visit",
        posts=[
            {
                "event_id": "trump_visit",
                "platform": "weibo",
                "post_id": "p1",
                "author_id": "u1",
                "timestamp": _dt(12),
                "content": "shared claim 1",
                "hashtags": ["#trump_visit"],
            },
            {
                "event_id": "trump_visit",
                "platform": "weibo",
                "post_id": "p2",
                "author_id": "u2",
                "timestamp": _dt(12, 0),
                "content": "shared claim 2",
                "hashtags": ["#trump_visit"],
            },
        ],
        comments=[],
        core_window=TimeWindow(start=_dt(11), end=_dt(22)),
        context_window=TimeWindow(start=_dt(1), end=_dt(31)),
    )


def test_executor_loads_snapshot_and_runs_requested_stage_ports():
    async def scenario():
        snapshot = _snapshot()
        store = FakeAnalysisStore(
            snapshot_record={
                "snapshot_id": snapshot.snapshot_id,
                "mongo_collection": "analysis_event_snapshots",
                "mongo_key": snapshot.snapshot_id,
            },
            run={
                "run_id": "run_a",
                "event_id": snapshot.event_id,
                "snapshot_id": snapshot.snapshot_id,
                "status": "queued",
                "requested_stages": ["coordination_discover", "propagation_analysis", "student", "teacher"],
                "options": {"coordination_discover": {"window_hours": 6}, "teacher": {"priority": "low"}},
                "finished_at": None,
            },
        )
        registry = AnalysisRegistry(
            mongo_db={
                "analysis_event_snapshots": FakeSnapshotCollection(
                    {snapshot.snapshot_id: snapshot.model_dump(mode="json")}
                )
            },
            store=store,
        )
        coordination = RecordingCoordinationEngine()
        propagation = RecordingPropagationEngine()
        student = RecordingStudentRuntime()
        teacher = RecordingTeacherJobPort()
        executor = AnalysisExecutor(
            registry=registry,
            engines=AnalysisEnginePorts(
                coordination=coordination,
                propagation=propagation,
                student=student,
                teacher=teacher,
            ),
        )

        result = await executor.execute_run("run_a")
        events = await registry.list_run_events("run_a")

        assert result["status"] == "awaiting_review"
        assert result["results"]["coordination_discover"]["community_count"] == 2
        assert result["results"]["propagation_analysis"]["scale_interval"] == [1, 3]
        assert result["results"]["student"]["verdict_type"] == "preliminary"
        assert result["results"]["teacher"]["job_id"] == "teacher_job_1"
        assert coordination.calls == [(snapshot.snapshot_id, {"window_hours": 6})]
        assert propagation.calls == [(snapshot.snapshot_id, {})]
        assert student.calls[0]["snapshot_id"] == snapshot.snapshot_id
        assert teacher.calls[0]["snapshot_id"] == snapshot.snapshot_id
        assert [event["event_type"] for event in events] == [
            "run_started",
            "stage_started",
            "stage_completed",
            "stage_started",
            "stage_completed",
            "stage_started",
            "stage_completed",
            "stage_started",
            "teacher_job_submitted",
            "run_awaiting_review",
        ]

    asyncio.run(scenario())


def test_default_ports_run_evidence_coordination_runtime_for_coordination_discover_snapshot():
    async def scenario():
        snapshot = _coordination_snapshot()
        store = FakeAnalysisStore(
            snapshot_record={
                "snapshot_id": snapshot.snapshot_id,
                "mongo_collection": "analysis_event_snapshots",
                "mongo_key": snapshot.snapshot_id,
            },
            run={
                "run_id": "run_coordination_discover",
                "event_id": snapshot.event_id,
                "snapshot_id": snapshot.snapshot_id,
                "status": "queued",
                "requested_stages": ["coordination_discover"],
                "options": {"coordination_discover": {"time_window": 60, "min_participation": 1}},
                "finished_at": None,
            },
        )
        registry = AnalysisRegistry(
            mongo_db={
                "analysis_event_snapshots": FakeSnapshotCollection(
                    {snapshot.snapshot_id: snapshot.model_dump(mode="json")}
                )
            },
            store=store,
        )
        executor = AnalysisExecutor(registry=registry, engines=default_analysis_engine_ports())

        result = await executor.execute_run("run_coordination_discover")
        coordination_discover = result["results"]["coordination_discover"]

        assert result["status"] == "completed"
        assert coordination_discover["status"] == "ok"
        assert coordination_discover["technology"] == "coordination_discover"
        assert coordination_discover["model_version"] == "coordination-evidence-runtime-v2"
        assert coordination_discover["summary"]["coordinated_edges"] == 1
        assert coordination_discover["evidence_edges"][0]["source"] in {"u1", "u2"}
        assert coordination_discover["account_risk_tiers"][0]["tier"] == "light_coordination"

    asyncio.run(scenario())


def test_executor_marks_missing_checkpoint_as_needs_evidence():
    async def scenario():
        snapshot = _snapshot()
        store = FakeAnalysisStore(
            snapshot_record={
                "snapshot_id": snapshot.snapshot_id,
                "mongo_collection": "analysis_event_snapshots",
                "mongo_key": snapshot.snapshot_id,
            },
            run={
                "run_id": "run_checkpoint",
                "event_id": snapshot.event_id,
                "snapshot_id": snapshot.snapshot_id,
                "status": "queued",
                "requested_stages": ["propagation_analysis"],
                "options": {},
                "finished_at": None,
            },
        )
        registry = AnalysisRegistry(
            mongo_db={
                "analysis_event_snapshots": FakeSnapshotCollection(
                    {snapshot.snapshot_id: snapshot.model_dump(mode="json")}
                )
            },
            store=store,
        )
        executor = AnalysisExecutor(
            registry=registry,
            engines=AnalysisEnginePorts(
                coordination=RecordingCoordinationEngine(),
                propagation=MissingCheckpointPropagationEngine(),
                student=RecordingStudentRuntime(),
                teacher=UnavailableTeacherJobPort(),
            ),
        )

        result = await executor.execute_run("run_checkpoint")

        assert result["status"] == "needs_evidence"
        assert result["results"]["propagation_analysis"]["status"] == "missing_checkpoint"

    asyncio.run(scenario())


def test_executor_rejects_unknown_requested_stage_before_running():
    async def scenario():
        snapshot = _snapshot()
        store = FakeAnalysisStore(
            snapshot_record={
                "snapshot_id": snapshot.snapshot_id,
                "mongo_collection": "analysis_event_snapshots",
                "mongo_key": snapshot.snapshot_id,
            },
            run={
                "run_id": "run_unknown_stage",
                "event_id": snapshot.event_id,
                "snapshot_id": snapshot.snapshot_id,
                "status": "queued",
                "requested_stages": ["coordination_discover", "bogus"],
                "options": {},
                "finished_at": None,
            },
        )
        registry = AnalysisRegistry(
            mongo_db={
                "analysis_event_snapshots": FakeSnapshotCollection(
                    {snapshot.snapshot_id: snapshot.model_dump(mode="json")}
                )
            },
            store=store,
        )
        executor = AnalysisExecutor(
            registry=registry,
            engines=AnalysisEnginePorts(
                coordination=RecordingCoordinationEngine(),
                propagation=RecordingPropagationEngine(),
                student=RecordingStudentRuntime(),
                teacher=UnavailableTeacherJobPort(),
            ),
        )

        try:
            await executor.execute_run("run_unknown_stage")
        except UnknownAnalysisStage:
            pass
        else:
            raise AssertionError("Executor accepted an unknown stage")

        events = await registry.list_run_events("run_unknown_stage")
        assert events == []

    asyncio.run(scenario())


def test_executor_does_not_emit_teacher_submitted_event_without_job_id():
    async def scenario():
        snapshot = _snapshot()
        store = FakeAnalysisStore(
            snapshot_record={
                "snapshot_id": snapshot.snapshot_id,
                "mongo_collection": "analysis_event_snapshots",
                "mongo_key": snapshot.snapshot_id,
            },
            run={
                "run_id": "run_b",
                "event_id": snapshot.event_id,
                "snapshot_id": snapshot.snapshot_id,
                "status": "queued",
                "requested_stages": ["teacher"],
                "options": {},
                "finished_at": None,
            },
        )
        registry = AnalysisRegistry(
            mongo_db={
                "analysis_event_snapshots": FakeSnapshotCollection(
                    {snapshot.snapshot_id: snapshot.model_dump(mode="json")}
                )
            },
            store=store,
        )
        executor = AnalysisExecutor(
            registry=registry,
            engines=AnalysisEnginePorts(
                coordination=RecordingCoordinationEngine(),
                propagation=RecordingPropagationEngine(),
                student=RecordingStudentRuntime(),
                teacher=UnavailableTeacherJobPort(),
            ),
        )

        result = await executor.execute_run("run_b")
        events = await registry.list_run_events("run_b")

        assert result["status"] == "needs_evidence"
        assert result["results"]["teacher"]["status"] == "unavailable"
        assert [event["event_type"] for event in events] == [
            "run_started",
            "stage_started",
            "stage_completed",
            "run_needs_evidence",
        ]

    asyncio.run(scenario())
