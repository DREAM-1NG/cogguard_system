from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Protocol
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.analysis.contracts import (
    AnalysisRunStatus,
    EventSnapshot,
    TimeWindow,
    transition_run_status,
)
from app.core.analysis.snapshots import build_event_snapshot
from app.models.analysis import AnalysisRun, AnalysisRunEvent, EventSnapshotRecord
from app.services.event_data import load_event_comments, load_event_posts

SNAPSHOT_COLLECTION = "analysis_event_snapshots"
TERMINAL_RUN_STATUSES = {
    AnalysisRunStatus.COMPLETED,
    AnalysisRunStatus.FAILED,
    AnalysisRunStatus.CANCELLED,
}


class AnalysisStore(Protocol):
    async def get_snapshot_record(self, snapshot_id: str) -> Any | None:
        ...

    async def save_snapshot_manifest(
        self,
        *,
        snapshot: EventSnapshot,
        mongo_collection: str,
        mongo_key: str,
        created_by: int,
    ) -> Any:
        ...

    async def create_run(
        self,
        *,
        run_id: str,
        event_id: str,
        snapshot_id: str,
        requested_stages: list[str],
        options: dict[str, Any],
        created_by: int,
    ) -> Any:
        ...

    async def get_run(self, run_id: str) -> Any | None:
        ...

    async def update_run_status(
        self,
        *,
        run_id: str,
        status: AnalysisRunStatus,
        payload: dict[str, Any],
        finished: bool,
    ) -> Any:
        ...

    async def append_run_event(
        self,
        *,
        run_id: str,
        event_type: str,
        status: AnalysisRunStatus,
        payload: dict[str, Any],
    ) -> Any:
        ...

    async def list_run_events(
        self,
        *,
        run_id: str,
        after_id: int = 0,
        limit: int = 100,
    ) -> list[Any]:
        ...


class AnalysisRegistry:
    def __init__(
        self,
        *,
        mongo_db: Any,
        store: AnalysisStore,
        snapshot_collection: str = SNAPSHOT_COLLECTION,
    ) -> None:
        self.mongo_db = mongo_db
        self.store = store
        self.snapshot_collection = snapshot_collection

    async def create_event_snapshot(
        self,
        *,
        event_id: str,
        core_window: TimeWindow,
        context_window: TimeWindow,
        platform: str | None = None,
        created_by: int = 0,
    ) -> EventSnapshot:
        posts = await load_event_posts(self.mongo_db, event_id=event_id, platform=platform)
        comments = await load_event_comments(self.mongo_db, event_id=event_id, platform=platform)
        snapshot = build_event_snapshot(
            event_id=event_id,
            posts=posts,
            comments=comments,
            core_window=core_window,
            context_window=context_window,
        )
        await self._persist_snapshot(snapshot, created_by=created_by)
        return snapshot

    async def create_run(
        self,
        *,
        event_id: str,
        snapshot_id: str,
        requested_stages: list[str],
        options: dict[str, Any] | None = None,
        created_by: int = 0,
        run_id: str | None = None,
    ) -> dict[str, Any]:
        resolved_run_id = run_id or f"run_{uuid4().hex}"
        run = await self.store.create_run(
            run_id=resolved_run_id,
            event_id=event_id,
            snapshot_id=snapshot_id,
            requested_stages=list(requested_stages),
            options=dict(options or {}),
            created_by=created_by,
        )
        await self.store.append_run_event(
            run_id=resolved_run_id,
            event_type="run_queued",
            status=AnalysisRunStatus.QUEUED,
            payload={
                "event_id": event_id,
                "snapshot_id": snapshot_id,
                "requested_stages": list(requested_stages),
                "options": dict(options or {}),
            },
        )
        return _mapping(run)

    async def get_run(self, run_id: str) -> dict[str, Any] | None:
        run = await self.store.get_run(run_id)
        return _mapping(run) if run is not None else None

    async def load_event_snapshot(self, snapshot_id: str) -> EventSnapshot:
        record = await self.store.get_snapshot_record(snapshot_id)
        if record is None:
            raise KeyError(f"Event snapshot manifest not found: {snapshot_id}")
        manifest = _mapping(record)
        collection = _get_collection(self.mongo_db, str(manifest["mongo_collection"]))
        document = await collection.find_one({"snapshot_id": str(manifest["mongo_key"])}, {"_id": 0})
        if document is None:
            raise KeyError(f"Event snapshot document not found: {snapshot_id}")
        return EventSnapshot.model_validate(document)

    async def transition_run_status(
        self,
        run_id: str,
        target: AnalysisRunStatus | str,
        *,
        payload: dict[str, Any] | None = None,
        event_type: str = "run_status_changed",
    ) -> dict[str, Any]:
        run = await self.store.get_run(run_id)
        if run is None:
            raise KeyError(f"Analysis run not found: {run_id}")
        next_status = transition_run_status(_mapping(run)["status"], target)
        updated = await self.store.update_run_status(
            run_id=run_id,
            status=next_status,
            payload=dict(payload or {}),
            finished=next_status in TERMINAL_RUN_STATUSES,
        )
        await self.store.append_run_event(
            run_id=run_id,
            event_type=event_type,
            status=next_status,
            payload=dict(payload or {}),
        )
        return _mapping(updated)

    async def append_run_event(
        self,
        run_id: str,
        *,
        event_type: str,
        status: AnalysisRunStatus | str,
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        event = await self.store.append_run_event(
            run_id=run_id,
            event_type=event_type,
            status=AnalysisRunStatus(status),
            payload=dict(payload or {}),
        )
        return _mapping(event)

    async def list_run_events(
        self,
        run_id: str,
        *,
        after_id: int = 0,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        events = await self.store.list_run_events(run_id=run_id, after_id=after_id, limit=limit)
        return [_mapping(event) for event in events]

    async def _persist_snapshot(self, snapshot: EventSnapshot, *, created_by: int) -> Any:
        collection = _get_collection(self.mongo_db, self.snapshot_collection)
        await collection.update_one(
            {"snapshot_id": snapshot.snapshot_id},
            {"$setOnInsert": snapshot.model_dump(mode="json")},
            upsert=True,
        )
        return await self.store.save_snapshot_manifest(
            snapshot=snapshot,
            mongo_collection=self.snapshot_collection,
            mongo_key=snapshot.snapshot_id,
            created_by=created_by,
        )


class SqlAlchemyAnalysisStore:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_snapshot_record(self, snapshot_id: str) -> EventSnapshotRecord | None:
        result = await self.session.execute(
            select(EventSnapshotRecord).where(EventSnapshotRecord.snapshot_id == snapshot_id)
        )
        return result.scalar_one_or_none()

    async def save_snapshot_manifest(
        self,
        *,
        snapshot: EventSnapshot,
        mongo_collection: str,
        mongo_key: str,
        created_by: int,
    ) -> EventSnapshotRecord:
        existing = await self.get_snapshot_record(snapshot.snapshot_id)
        if existing is not None:
            return existing
        record = EventSnapshotRecord(
            snapshot_id=snapshot.snapshot_id,
            event_id=snapshot.event_id,
            data_fingerprint=snapshot.data_fingerprint,
            mongo_collection=mongo_collection,
            mongo_key=mongo_key,
            platforms_json=_json_dumps(snapshot.platforms),
            windows_json=_json_dumps(
                {
                    "core_window": snapshot.core_window.model_dump(mode="json"),
                    "context_window": snapshot.context_window.model_dump(mode="json"),
                }
            ),
            quality_json=_json_dumps(snapshot.quality_report.model_dump(mode="json")),
            provenance_json=_json_dumps([record.model_dump(mode="json") for record in snapshot.provenance]),
            created_by=created_by,
        )
        self.session.add(record)
        await self.session.flush()
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
    ) -> AnalysisRun:
        run = AnalysisRun(
            run_id=run_id,
            event_id=event_id,
            snapshot_id=snapshot_id,
            status=AnalysisRunStatus.QUEUED.value,
            requested_stages_json=_json_dumps(requested_stages),
            options_json=_json_dumps(options),
            artifact_manifest_json="{}",
            created_by=created_by,
        )
        self.session.add(run)
        await self.session.flush()
        return run

    async def get_run(self, run_id: str) -> AnalysisRun | None:
        result = await self.session.execute(select(AnalysisRun).where(AnalysisRun.run_id == run_id))
        return result.scalar_one_or_none()

    async def update_run_status(
        self,
        *,
        run_id: str,
        status: AnalysisRunStatus,
        payload: dict[str, Any],
        finished: bool,
    ) -> AnalysisRun:
        run = await self.get_run(run_id)
        if run is None:
            raise KeyError(f"Analysis run not found: {run_id}")
        run.status = status.value
        run.updated_at = datetime.now(timezone.utc)
        if status in {
            AnalysisRunStatus.NEEDS_EVIDENCE,
            AnalysisRunStatus.AWAITING_REVIEW,
            AnalysisRunStatus.COMPLETED,
        }:
            run.result_json = _json_dumps(payload)
        elif status == AnalysisRunStatus.FAILED:
            run.error = str(payload.get("error") or payload.get("message") or "")
        if finished:
            run.finished_at = datetime.now(timezone.utc)
        await self.session.flush()
        return run

    async def append_run_event(
        self,
        *,
        run_id: str,
        event_type: str,
        status: AnalysisRunStatus,
        payload: dict[str, Any],
    ) -> AnalysisRunEvent:
        event = AnalysisRunEvent(
            run_id=run_id,
            event_type=event_type,
            status=status.value,
            payload_json=_json_dumps(payload),
        )
        self.session.add(event)
        await self.session.flush()
        return event

    async def list_run_events(
        self,
        *,
        run_id: str,
        after_id: int = 0,
        limit: int = 100,
    ) -> list[AnalysisRunEvent]:
        result = await self.session.execute(
            select(AnalysisRunEvent)
            .where(AnalysisRunEvent.run_id == run_id, AnalysisRunEvent.id > after_id)
            .order_by(AnalysisRunEvent.id.asc())
            .limit(limit)
        )
        return list(result.scalars().all())


def _get_collection(mongo_db: Any, name: str) -> Any:
    if isinstance(mongo_db, dict):
        return mongo_db[name]
    return mongo_db[name]


def _mapping(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return dict(value)
    if isinstance(value, EventSnapshotRecord):
        return {
            "snapshot_id": value.snapshot_id,
            "event_id": value.event_id,
            "data_fingerprint": value.data_fingerprint,
            "mongo_collection": value.mongo_collection,
            "mongo_key": value.mongo_key,
            "platforms": _json_loads(value.platforms_json, []),
            "quality": _json_loads(value.quality_json, {}),
            "provenance": _json_loads(value.provenance_json, []),
            "created_by": value.created_by,
            "created_at": _iso(value.created_at),
        }
    if isinstance(value, AnalysisRun):
        return {
            "run_id": value.run_id,
            "event_id": value.event_id,
            "snapshot_id": value.snapshot_id,
            "status": value.status,
            "requested_stages": _json_loads(value.requested_stages_json, []),
            "options": _json_loads(value.options_json, {}),
            "result": _json_loads(value.result_json, None),
            "artifact_manifest": _json_loads(value.artifact_manifest_json, {}),
            "error": value.error,
            "celery_task_id": value.celery_task_id,
            "created_by": value.created_by,
            "created_at": _iso(value.created_at),
            "updated_at": _iso(value.updated_at),
            "finished_at": _iso(value.finished_at),
        }
    if isinstance(value, AnalysisRunEvent):
        return {
            "id": value.id,
            "run_id": value.run_id,
            "event_type": value.event_type,
            "status": value.status,
            "payload": _json_loads(value.payload_json, {}),
            "created_at": _iso(value.created_at),
        }
    raise TypeError(f"Unsupported analysis registry value: {type(value).__name__}")


def _json_dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def _json_loads(value: str | None, default: Any) -> Any:
    if not value:
        return default
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return default


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None
