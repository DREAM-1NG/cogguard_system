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

    def sort(self, key: str, direction: int):
        reverse = direction < 0
        self.rows = sorted(self.rows, key=lambda row: row.get(key, 0), reverse=reverse)
        return self

    async def to_list(self, length: int | None) -> list[dict[str, Any]]:
        if length is None:
            return list(self.rows)
        return self.rows[:length]


class FakeCollection:
    def __init__(self, rows: list[dict[str, Any]] | None = None) -> None:
        self.rows = rows or []
        self.documents: dict[str, dict[str, Any]] = {}
        self.find_calls: list[dict[str, Any]] = []
        self.update_calls: list[dict[str, Any]] = []

    def find(self, query: dict[str, Any], projection: dict[str, int] | None = None) -> FakeCursor:
        self.find_calls.append({"query": query, "projection": projection})
        source_rows = [*self.rows, *self.documents.values()]
        filtered = [
            row
            for row in source_rows
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
        document_id = str(query.get("snapshot_id") or query.get("artifact_id"))
        if "$set" in update:
            self.documents[document_id] = {**self.documents.get(document_id, {}), **dict(update["$set"])}
        elif "$setOnInsert" in update and document_id not in self.documents and upsert:
            self.documents[document_id] = dict(update["$setOnInsert"])

    async def find_one(self, query: dict[str, Any], projection: dict[str, int] | None = None):
        snapshot_id = query.get("snapshot_id")
        if snapshot_id is None:
            return None
        document = self.documents.get(str(snapshot_id))
        return dict(document) if document is not None else None


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
        self.refresh_count = 0
        self.added: list[Any] = []

    def add(self, value) -> None:
        self.added.append(value)

    async def flush(self) -> None:
        self.flush_count += 1

    async def refresh(self, _value) -> None:
        self.refresh_count += 1


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
        root_documents = [
            document
            for document in snapshot_collection.documents.values()
            if document.get("payload_kind") == "event_snapshot"
        ]
        assert len(root_documents) == 1
        assert len(store.snapshots) == 1
        manifest = store.snapshots[snapshot.snapshot_id]
        assert manifest["mongo_collection"] == "analysis_event_snapshots"
        assert manifest["mongo_key"] == snapshot.snapshot_id
        assert manifest["created_by"] == 7
        assert mongo["raw_posts"].find_calls[-1]["query"] == {"event_id": "trump_visit"}

    asyncio.run(scenario())


def test_registry_persists_large_event_snapshots_as_chunks_and_restores_them():
    async def scenario():
        posts = [
            {
                "event_id": "trump_visit",
                "platform": "weibo",
                "post_id": f"p{index}",
                "author_id": f"u{index}",
                "timestamp": _dt(12),
                "content": "event claim " + ("x" * 80_000),
            }
            for index in range(8)
        ]
        mongo = {
            "raw_posts": FakeCollection(posts),
            "raw_comments": FakeCollection([]),
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
        restored = await registry.load_event_snapshot(snapshot.snapshot_id)
        snapshot_collection = mongo["analysis_event_snapshots"]
        root_document = snapshot_collection.documents[snapshot.snapshot_id]
        chunk_documents = [
            document
            for document in snapshot_collection.documents.values()
            if document.get("root_snapshot_id") == snapshot.snapshot_id
        ]

        assert root_document["schema"] == "cogguard.analysis.event_snapshot.chunked.v1"
        assert root_document["chunk_count"] == len(chunk_documents)
        assert len(chunk_documents) > 1
        assert restored.snapshot_id == snapshot.snapshot_id
        assert restored.data_fingerprint == snapshot.data_fingerprint
        assert restored.posts == snapshot.posts

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


def test_sqlalchemy_store_refreshes_new_runs_and_events_after_flush():
    async def scenario():
        session = FakeSession()
        store = SqlAlchemyAnalysisStore(session)  # type: ignore[arg-type]

        run = await store.create_run(
            run_id="run_refresh",
            event_id="trump_visit",
            snapshot_id="snapshot_a",
            requested_stages=["coordination_discover"],
            options={},
            created_by=1,
        )
        event = await store.append_run_event(
            run_id="run_refresh",
            event_type="run_queued",
            status=AnalysisRunStatus.QUEUED,
            payload={},
        )

        assert run.run_id == "run_refresh"
        assert event.run_id == "run_refresh"
        assert session.flush_count == 2
        assert session.refresh_count == 2

    asyncio.run(scenario())
