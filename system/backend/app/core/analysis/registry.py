from __future__ import annotations

import json
import hashlib
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
from app.models.analysis import AnalysisModelActivation, AnalysisModelVersion, AnalysisRun, AnalysisRunEvent, EventSnapshotRecord
from app.services.event_data import load_event_comments, load_event_posts

SNAPSHOT_COLLECTION = "analysis_event_snapshots"
RUN_ARTIFACT_COLLECTION = "analysis_run_artifacts"
SNAPSHOT_CHUNK_SCHEMA = "cogguard.analysis.event_snapshot.chunked.v1"
RUN_ARTIFACT_CHUNK_SCHEMA = "cogguard.analysis.run_artifact.chunked.v1"
# Keep chunks far below MongoDB's 16MB document limit; event snapshots can carry
# tens of thousands of comments during real-system runs.
SNAPSHOT_PAYLOAD_CHARS = 512_000
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

    async def update_artifact_manifest(self, *, run_id: str, manifest: dict[str, Any]) -> Any:
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

    async def get_active_model(self, technology: str) -> Any | None:
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
        if document.get("schema") == SNAPSHOT_CHUNK_SCHEMA:
            payload = await _load_snapshot_payload_chunks(
                collection,
                root_snapshot_id=str(document["snapshot_id"]),
                expected_chunks=int(document.get("chunk_count", 0) or 0),
            )
            return EventSnapshot.model_validate(json.loads(payload))
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

    async def update_artifact_manifest(self, run_id: str, manifest: dict[str, Any]) -> dict[str, Any] | None:
        """Persist the reproducibility manifest without changing run state."""
        updater = getattr(self.store, "update_artifact_manifest", None)
        if updater is None:
            return None
        updated = await updater(run_id=run_id, manifest=dict(manifest))
        return _mapping(updated) if updated is not None else None

    async def save_run_artifact(
        self,
        *,
        run_id: str,
        artifact_key: str,
        payload: Any,
    ) -> dict[str, Any]:
        """Persist a large run artifact outside MySQL result/event columns."""
        artifact_id = f"{run_id}:{artifact_key}"
        try:
            collection = _get_collection(self.mongo_db, RUN_ARTIFACT_COLLECTION)
        except (KeyError, TypeError):
            return {
                "stored": False,
                "artifact_id": artifact_id,
                "reason": f"Mongo collection unavailable: {RUN_ARTIFACT_COLLECTION}",
            }
        if not hasattr(collection, "update_one"):
            return {
                "stored": False,
                "artifact_id": artifact_id,
                "reason": "Mongo artifact collection does not support update_one",
            }

        payload_text = _json_dumps(payload)
        chunks = _chunk_text(payload_text, SNAPSHOT_PAYLOAD_CHARS)
        payload_hash = hashlib.sha256(payload_text.encode("utf-8")).hexdigest()
        await collection.update_one(
            {"artifact_id": artifact_id},
            {
                "$set": {
                    "artifact_id": artifact_id,
                    "schema": RUN_ARTIFACT_CHUNK_SCHEMA,
                    "run_id": run_id,
                    "artifact_key": artifact_key,
                    "payload_sha256": payload_hash,
                    "payload_size_chars": len(payload_text),
                    "chunk_count": len(chunks),
                    "chunk_size_chars": SNAPSHOT_PAYLOAD_CHARS,
                    "created_at": datetime.now(timezone.utc).isoformat(),
                }
            },
            upsert=True,
        )
        for index, chunk in enumerate(chunks):
            await collection.update_one(
                {"artifact_id": _artifact_chunk_id(artifact_id, index)},
                {
                    "$set": {
                        "artifact_id": _artifact_chunk_id(artifact_id, index),
                        "root_artifact_id": artifact_id,
                        "chunk_index": index,
                        "payload": chunk,
                    }
                },
                upsert=True,
            )
        return {
            "stored": True,
            "collection": RUN_ARTIFACT_COLLECTION,
            "artifact_id": artifact_id,
            "artifact_key": artifact_key,
            "payload_sha256": payload_hash,
            "payload_size_chars": len(payload_text),
            "chunk_count": len(chunks),
        }

    async def load_run_artifact(self, run_id: str, artifact_key: str) -> Any:
        """Load and validate a chunked Mongo run artifact payload."""
        collection = _get_collection(self.mongo_db, RUN_ARTIFACT_COLLECTION)
        artifact_id = f"{run_id}:{artifact_key}"
        root = await collection.find_one({"artifact_id": artifact_id}, {"_id": 0})
        if root is None:
            raise KeyError(f"Analysis artifact not found: {artifact_id}")
        expected_chunks = int(root.get("chunk_count", 0) or 0)
        cursor = collection.find(
            {"root_artifact_id": artifact_id},
            {"_id": 0, "chunk_index": 1, "payload": 1},
        )
        sorter = getattr(cursor, "sort", None)
        if sorter is not None:
            cursor = sorter("chunk_index", 1)
        rows = await cursor.to_list(length=expected_chunks or None)
        chunks = sorted(rows, key=lambda row: int(row.get("chunk_index", 0) or 0))
        if len(chunks) != expected_chunks:
            raise KeyError(
                f"Analysis artifact chunks incomplete: {artifact_id} "
                f"expected={expected_chunks} actual={len(chunks)}"
            )
        payload_text = "".join(str(row.get("payload") or "") for row in chunks)
        payload_hash = hashlib.sha256(payload_text.encode("utf-8")).hexdigest()
        if payload_hash != str(root.get("payload_sha256") or ""):
            raise ValueError(f"Analysis artifact hash mismatch: {artifact_id}")
        return json.loads(payload_text)

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

    async def get_active_model(self, technology: str) -> dict[str, Any] | None:
        getter = getattr(self.store, "get_active_model", None)
        if getter is None:
            return None
        row = await getter(technology=technology)
        return _mapping(row) if row is not None else None

    async def _persist_snapshot(self, snapshot: EventSnapshot, *, created_by: int) -> Any:
        collection = _get_collection(self.mongo_db, self.snapshot_collection)
        payload = _json_dumps(snapshot.model_dump(mode="json"))
        chunks = _chunk_text(payload, SNAPSHOT_PAYLOAD_CHARS)
        root_document = {
            "snapshot_id": snapshot.snapshot_id,
            "schema": SNAPSHOT_CHUNK_SCHEMA,
            "payload_kind": "event_snapshot",
            "data_fingerprint": snapshot.data_fingerprint,
            "event_id": snapshot.event_id,
            "platforms": list(snapshot.platforms),
            "quality": snapshot.quality_report.model_dump(mode="json"),
            "chunk_count": len(chunks),
            "chunk_size_chars": SNAPSHOT_PAYLOAD_CHARS,
            "created_at": snapshot.created_at.isoformat(),
        }
        await collection.update_one(
            {"snapshot_id": snapshot.snapshot_id},
            {"$set": root_document},
            upsert=True,
        )
        for index, chunk in enumerate(chunks):
            await collection.update_one(
                {"snapshot_id": _chunk_snapshot_id(snapshot.snapshot_id, index)},
                {
                    "$set": {
                        "snapshot_id": _chunk_snapshot_id(snapshot.snapshot_id, index),
                        "root_snapshot_id": snapshot.snapshot_id,
                        "chunk_index": index,
                        "payload": chunk,
                    }
                },
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
        await self.session.refresh(record)
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
        await self.session.refresh(run)
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

    async def update_artifact_manifest(self, *, run_id: str, manifest: dict[str, Any]) -> AnalysisRun:
        run = await self.get_run(run_id)
        if run is None:
            raise KeyError(f"Analysis run not found: {run_id}")
        run.artifact_manifest_json = _json_dumps(manifest)
        run.updated_at = datetime.now(timezone.utc)
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
        await self.session.refresh(event)
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

    async def get_active_model(self, *, technology: str) -> dict[str, Any] | None:
        result = await self.session.execute(
            select(AnalysisModelActivation, AnalysisModelVersion)
            .join(AnalysisModelVersion, AnalysisModelVersion.id == AnalysisModelActivation.model_version_id)
            .where(AnalysisModelActivation.technology == technology)
        )
        row = result.first()
        if row is None:
            return None
        activation, version = row
        provenance = _json_loads(activation.provenance_json, {})
        artifact = provenance.get("artifact") if isinstance(provenance, dict) else None
        return {
            "technology": activation.technology,
            "model_version_id": activation.model_version_id,
            "version": version.version,
            "model": version.model,
            "artifact_uri": version.artifact_uri,
            "artifact_hash": version.artifact_hash,
            "checkpoint_path": artifact.get("checkpoint_path") if isinstance(artifact, dict) else None,
            "status": version.status,
            "provenance": provenance,
        }


def _get_collection(mongo_db: Any, name: str) -> Any:
    if isinstance(mongo_db, dict):
        return mongo_db[name]
    return mongo_db[name]


def _chunk_text(value: str, chunk_size: int) -> list[str]:
    return [value[index : index + chunk_size] for index in range(0, len(value), chunk_size)] or [""]


def _chunk_snapshot_id(snapshot_id: str, index: int) -> str:
    return f"{snapshot_id}:chunk:{index:06d}"


def _artifact_chunk_id(artifact_id: str, index: int) -> str:
    return f"{artifact_id}:chunk:{index:06d}"


async def _load_snapshot_payload_chunks(
    collection: Any,
    *,
    root_snapshot_id: str,
    expected_chunks: int,
) -> str:
    cursor = collection.find({"root_snapshot_id": root_snapshot_id}, {"_id": 0, "chunk_index": 1, "payload": 1})
    sorter = getattr(cursor, "sort", None)
    if sorter is not None:
        cursor = sorter("chunk_index", 1)
    rows = await cursor.to_list(length=expected_chunks or None)
    chunks = sorted(rows, key=lambda row: int(row.get("chunk_index", 0) or 0))
    if expected_chunks and len(chunks) != expected_chunks:
        raise KeyError(
            f"Event snapshot chunks incomplete: {root_snapshot_id} "
            f"expected={expected_chunks} actual={len(chunks)}"
        )
    return "".join(str(row.get("payload") or "") for row in chunks)


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
    if isinstance(value, AnalysisModelActivation):
        return {
            "technology": value.technology,
            "model_version_id": value.model_version_id,
            "provenance": _json_loads(value.provenance_json, {}),
            "activated_by": value.activated_by,
            "activated_at": _iso(value.activated_at),
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
