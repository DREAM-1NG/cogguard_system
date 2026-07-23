from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any

import pytest

from app.core.analysis import AnalysisRunStatus, InvalidRunTransition, TimeWindow
from app.core.analysis.registry import AnalysisRegistry, SqlAlchemyAnalysisStore
from app.models.analysis import AnalysisRun


class FakeCursor:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self.rows = rows

    async def to_list(self, length: int) -> list[dict[str, Any]]:
        return self.rows[:length]


class FakeCollection:
    def __init__(self, rows: list[dict[str, Any]] | None = None) -> None:
        self.rows = rows or []
        self.documents: dict[str, dict[str, Any]] = {}
        self.find_calls: list[dict[str, Any]] = []
        self.update_calls: list[dict[str, Any]] = []

    def find(self, query: dict[str, Any], projection: dict[str, int] | None = None) -> FakeCursor:
        self.find_calls.append({"query": query, "projection": projection})
        filtered = [
            row
            for row in self.rows
            if all(row.get(key) == value for key, value in query.items())
        ]
        return FakeCursor(filtered)

    async def update_one(
        self,
        query: dict[str, Any],
        update: dict[str, Any],
        *,
        upsert: bool = False,
    ) -> None:
        self.update_calls.append({"query": query, "update": update, "upsert": upsert})
        snapshot_id = str(query["snapshot_id"])
        if snapshot_id not in self.documents and upsert:
            self.documents[snapshot_id] = dict(update["$setOnInsert"])


class FakeAnalysisStore:
    def __init__(self) -> None:
        self.snapshots: dict[str, dict[str, Any]] = {}
        self.runs: dict[str, dict[str, Any]] = {}
        self.events: list[dict[str, Any]] = []
        self.next_event_id = 1

    async def get_snapshot_record(self, snapshot_id: str) -> dict[str, Any] | None:
        return self.snapshots.get(snapshot_id)

    async def save_snapshot_manifest(
        self,
        *,
        snapshot,
        mongo_collection: str,
        mongo_key: str,
        created_by: int,
    ) -> dict[str, Any]:
        existing = self.snapshots.get(snapshot.snapshot_id)
        if existing is not None:
            return existing
        record = {
            "snapshot_id": snapshot.snapshot_id,
            "event_id": snapshot.event_id,
            "data_fingerprint": snapshot.data_fingerprint,
            "mongo_collection": mongo_collection,
            "mongo_key": mongo_key,
            "platforms": list(snapshot.platforms),
            "quality": snapshot.quality_report.model_dump(mode="json"),
            "created_by": created_by,
        }
        self.snapshots[snapshot.snapshot_id] = record
        return record

    async def create_run(
        self,
        *,
        run_id: str,
        event_id: str,
        snapshot_id: str,
        requested_stages: list[str],
        options: dict[str, Any],
        created_by: int,
    ) -> dict[str, Any]:
        run = {
            "run_id": run_id,
            "event_id": event_id,
            "snapshot_id": snapshot_id,
            "status": AnalysisRunStatus.QUEUED.value,
            "requested_stages": requested_stages,
            "options": options,
            "created_by": created_by,
            "finished_at": None,
        }
        self.runs[run_id] = run
        return run

    async def get_run(self, run_id: str) -> dict[str, Any] | None:
        return self.runs.get(run_id)

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
        run["last_payload"] = payload
        if finished:
            run["finished_at"] = "finished"
        return run

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
        return event

    async def list_run_events(self, *, run_id: str, after_id: int = 0, limit: int = 100) -> list[dict[str, Any]]:
        return [
            event
            for event in self.events
            if event["run_id"] == run_id and event["id"] > after_id
        ][:limit]


class FakeSession:
    def __init__(self) -> None:
        self.flush_count = 0

    async def flush(self) -> None:
        self.flush_count += 1


def _dt(day: int, hour: int = 0) -> datetime:
    return datetime(2026, 5, day, hour, tzinfo=timezone.utc)


def test_registry_builds_immutable_snapshot_from_mongo_and_manifest_store():
    async def scenario():
        mongo = {
            "raw_posts": FakeCollection(
                [
                    {
                        "event_id": "trump_visit",
                        "platform": "weibo",
                        "post_id": "p1",
                        "author_id": "u1",
                        "timestamp": _dt(12),
                        "content": "event claim",
                    },
                    {
                        "event_id": "other",
                        "platform": "weibo",
                        "post_id": "p2",
                        "author_id": "u2",
                        "timestamp": _dt(12),
                        "content": "other event",
                    },
                ]
            ),
            "raw_comments": FakeCollection(
                [
                    {
                        "event_id": "trump_visit",
                        "platform": "weibo",
                        "comment_id": "c1",
                        "post_id": "p1",
                        "reply_to": "p1",
                        "author_id": "u3",
                        "timestamp": _dt(12, 1),
                        "content": "reply",
                    }
                ]
            ),
            "analysis_event_snapshots": FakeCollection(),
        }
        store = FakeAnalysisStore()
        registry = AnalysisRegistry(mongo_db=mongo, store=store)

        snapshot = await registry.create_event_snapshot(
            event_id="trump_visit",
            core_window=TimeWindow(start=_dt(11), end=_dt(22)),
            context_window=TimeWindow(start=_dt(1), end=_dt(31)),
            created_by=7,
        )
        second = await registry.create_event_snapshot(
            event_id="trump_visit",
            core_window=TimeWindow(start=_dt(11), end=_dt(22)),
            context_window=TimeWindow(start=_dt(1), end=_dt(31)),
            created_by=7,
        )

        snapshot_collection = mongo["analysis_event_snapshots"]
        assert snapshot.snapshot_id == second.snapshot_id
        assert snapshot.quality_report.status == "pass"
        assert snapshot.quality_report.context_posts == 1
        assert len(snapshot_collection.documents) == 1
        assert len(store.snapshots) == 1
        manifest = store.snapshots[snapshot.snapshot_id]
        assert manifest["mongo_collection"] == "analysis_event_snapshots"
        assert manifest["mongo_key"] == snapshot.snapshot_id
        assert manifest["created_by"] == 7
        assert mongo["raw_posts"].find_calls[-1]["query"] == {"event_id": "trump_visit"}

    asyncio.run(scenario())


def test_registry_creates_run_events_and_recovers_after_cursor():
    async def scenario():
        store = FakeAnalysisStore()
        registry = AnalysisRegistry(mongo_db={}, store=store)
        run = await registry.create_run(
            event_id="trump_visit",
            snapshot_id="snapshot_a",
            requested_stages=["coordination_discover", "propagation_analysis", "student"],
            options={"priority": "demo"},
            created_by=9,
            run_id="run_fixed",
        )
        running = await registry.transition_run_status(
            "run_fixed",
            AnalysisRunStatus.RUNNING,
            payload={"worker": "local"},
        )
        completed = await registry.transition_run_status(
            "run_fixed",
            AnalysisRunStatus.COMPLETED,
            payload={"summary": "ok"},
        )
        events_after_first = await registry.list_run_events("run_fixed", after_id=1)

        assert run["status"] == "queued"
        assert running["status"] == "running"
        assert completed["status"] == "completed"
        assert completed["finished_at"] == "finished"
        assert [event["id"] for event in events_after_first] == [2, 3]
        assert [event["status"] for event in events_after_first] == ["running", "completed"]
        with pytest.raises(InvalidRunTransition):
            await registry.transition_run_status("run_fixed", AnalysisRunStatus.RUNNING)

    asyncio.run(scenario())


def test_sqlalchemy_store_persists_results_for_needs_evidence_runs():
    async def scenario():
        run = AnalysisRun(
            run_id="run_needs_evidence",
            event_id="trump_visit",
            snapshot_id="snapshot_a",
            status=AnalysisRunStatus.RUNNING.value,
            requested_stages_json='["coordination_discover"]',
            options_json="{}",
            artifact_manifest_json="{}",
            created_by=1,
        )
        session = FakeSession()
        store = SqlAlchemyAnalysisStore(session)  # type: ignore[arg-type]

        async def fake_get_run(run_id: str):
            assert run_id == "run_needs_evidence"
            return run

        store.get_run = fake_get_run  # type: ignore[method-assign]

        updated = await store.update_run_status(
            run_id="run_needs_evidence",
            status=AnalysisRunStatus.NEEDS_EVIDENCE,
            payload={"results": {"coordination_discover": {"status": "unavailable"}}},
            finished=False,
        )

        assert updated.result_json == '{"results": {"coordination_discover": {"status": "unavailable"}}}'
        assert session.flush_count == 1

    asyncio.run(scenario())
