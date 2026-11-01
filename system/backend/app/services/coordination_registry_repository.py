"""Focused registry repository module."""

from __future__ import annotations

import asyncio
import json
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence
import numpy as np
import pandas as pd
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from app.config import PROJECT_ROOT
from app.core.coordination_detect import (
    PRETRAINED_CHECKPOINT_PATH,
    ensure_china_pretrained_fusion_checkpoint,
    extract_labels,
    run_china_pretrained_detect,
    run_dyna_colm_detect,
)
from app.core.coordination_discover import (
    DEFAULT_RELATIONS,
    build_unmasking_similarity_graphs,
    fuse_similarity_graphs,
    normalize_event_table,
    read_event_table,
    run_dyna_colm_discover,
)
from app.db.mysql import async_session_factory
from app.models.coordination_registry import CoordinationDataset, CoordinationRun

from app.services.coordination_registry_common import (
    DATASET_STORAGE_ROOT,
    RUN_RELATIONS,
    RUN_STORAGE_ROOT,
    SYSTEM_ARCHIVE_DISCOVER_ENCODER,
    SYSTEM_ARCHIVE_GNN_BACKEND,
    _dataset_record,
    _json_dump,
    _load_archive_result_pair,
    _safe_json_loads,
    _system_archive_run_summary,
    _unique_dataset_slug,
    ensure_system_archive_datasets,
)
from app.services.coordination_result_projection import (
    _build_coordination_community_payload,
    _build_coordination_graph_payload,
    _build_result_snapshot,
    _load_run_result_pair,
)

async def list_coordination_datasets(db: AsyncSession) -> list[dict[str, Any]]:
    await ensure_system_archive_datasets(db)
    result = await db.execute(select(CoordinationDataset).order_by(CoordinationDataset.source_type.asc(), CoordinationDataset.display_name.asc()))
    datasets = result.scalars().all()
    records = []
    for dataset in datasets:
        latest_run = None
        if dataset.latest_run_id:
            latest_run_result = await db.execute(select(CoordinationRun).where(CoordinationRun.id == dataset.latest_run_id))
            latest_run = latest_run_result.scalar_one_or_none()
        archive_summary = None
        if latest_run is None and dataset.source_type == "system_archive":
            archive_summary = _system_archive_run_summary(dataset)
        records.append(_dataset_record(dataset, latest_run=latest_run, archive_summary=archive_summary))
    return records


async def upload_coordination_dataset(
    *,
    db: AsyncSession,
    filename: str,
    content: bytes,
    created_by: int,
    display_name: str | None = None,
) -> dict[str, Any]:
    suffix = Path(filename).suffix.lower()
    if suffix not in {".csv", ".jsonl", ".ndjson"}:
        raise ValueError("Only CSV and JSONL event tables are supported")
    dataset_name = (display_name or Path(filename).stem or "uploaded-dataset").strip()
    slug = await _unique_dataset_slug(db, dataset_name)
    dataset_dir = DATASET_STORAGE_ROOT / slug
    dataset_dir.mkdir(parents=True, exist_ok=True)
    stored_name = "source.csv" if suffix == ".csv" else "source.jsonl"
    source_path = dataset_dir / stored_name
    source_path.write_bytes(content)

    # Parsing plus similarity-graph summarization is CPU-bound (it enumerates
    # account pairs per shared object), so keep it off the event loop.
    events = await asyncio.to_thread(read_event_table, source_path)
    summary = await asyncio.to_thread(_summarize_event_table, events)
    record = CoordinationDataset(
        slug=slug,
        display_name=dataset_name,
        source_type="uploaded",
        source_format="csv" if suffix == ".csv" else "jsonl",
        source_path=str(source_path),
        metadata_json=_json_dump({"uploaded_filename": filename}),
        has_labels=bool(summary["has_labels"]),
        event_rows=int(summary["event_rows"]),
        account_nodes=int(summary["account_nodes"]),
        object_ids=int(summary["object_ids"]),
        user_user_edges=int(summary["user_user_edges"]),
        available_relations=_json_dump(summary["available_relations"]),
        created_by=created_by,
    )
    db.add(record)
    await db.commit()
    await db.refresh(record)
    return _dataset_record(record)


def _summarize_event_table(events: pd.DataFrame) -> dict[str, Any]:
    normalized = normalize_event_table(events)
    relation_candidates = sorted({str(value) for value in normalized["relation"].astype(str).unique() if str(value) in RUN_RELATIONS})
    fused = fuse_similarity_graphs(
        build_unmasking_similarity_graphs(
            normalized,
            relations=tuple(relation_candidates or DEFAULT_RELATIONS),
            include_text_similarity=False,
        )
    )
    labels = extract_labels(normalized)
    has_detect_labels = bool(labels) and len(set(labels.values())) >= 2
    return {
        "has_labels": has_detect_labels,
        "event_rows": int(len(normalized)),
        "account_nodes": int(normalized["account_id"].astype(str).nunique()),
        "object_ids": int(normalized["object_id"].astype(str).nunique()),
        "user_user_edges": int(fused.number_of_edges()),
        "available_relations": sorted({str(value) for value in normalized["relation"].astype(str).unique()}),
    }


async def get_coordination_dataset_detail(db: AsyncSession, dataset_id: int) -> dict[str, Any]:
    await ensure_system_archive_datasets(db)
    result = await db.execute(select(CoordinationDataset).where(CoordinationDataset.id == dataset_id))
    dataset = result.scalar_one_or_none()
    if dataset is None:
        raise ValueError(f"Dataset {dataset_id} not found")
    latest_run = None
    if dataset.latest_run_id:
        run_result = await db.execute(select(CoordinationRun).where(CoordinationRun.id == dataset.latest_run_id))
        latest_run = run_result.scalar_one_or_none()
    runs_result = await db.execute(
        select(CoordinationRun)
        .where(CoordinationRun.dataset_id == dataset.id)
        .order_by(CoordinationRun.id.desc())
        .limit(10)
    )
    runs = runs_result.scalars().all()
    return {
        "dataset": _dataset_record(
            dataset,
            latest_run=latest_run,
            archive_summary=_system_archive_run_summary(dataset) if latest_run is None and dataset.source_type == "system_archive" else None,
        ),
        "runs": [_run_record(run) for run in runs],
        "has_archived_result": dataset.source_type == "system_archive",
    }


async def _load_latest_result_context(
    db: AsyncSession,
    dataset_id: int,
    *,
    allow_empty_uploaded: bool = False,
) -> tuple[CoordinationDataset, dict[str, Any], dict[str, Any], str, CoordinationRun | None]:
    await ensure_system_archive_datasets(db)
    result = await db.execute(select(CoordinationDataset).where(CoordinationDataset.id == dataset_id))
    dataset = result.scalar_one_or_none()
    if dataset is None:
        raise ValueError(f"Dataset {dataset_id} not found")

    if dataset.latest_run_id:
        run_result = await db.execute(select(CoordinationRun).where(CoordinationRun.id == dataset.latest_run_id))
        run = run_result.scalar_one_or_none()
        if run is not None and run.status == "completed":
            discovery, detect = _load_run_result_pair(run)
            return dataset, discovery, detect, "rerun", run

    if dataset.source_type == "system_archive":
        discovery, detect = _load_archive_result_pair(dataset)
        return dataset, discovery, detect, "archive", None

    if allow_empty_uploaded:
        return dataset, {}, {}, "none", None

    raise ValueError(f"Dataset {dataset_id} has no completed coordination result")


async def get_coordination_dataset_latest_result(db: AsyncSession, dataset_id: int) -> dict[str, Any]:
    await ensure_system_archive_datasets(db)
    result = await db.execute(select(CoordinationDataset).where(CoordinationDataset.id == dataset_id))
    dataset = result.scalar_one_or_none()
    if dataset is None:
        raise ValueError(f"Dataset {dataset_id} not found")
    if dataset.latest_run_id:
        run_result = await db.execute(select(CoordinationRun).where(CoordinationRun.id == dataset.latest_run_id))
        run = run_result.scalar_one_or_none()
        if run is not None and run.status == "completed":
            discovery, detect = _load_run_result_pair(run)
            return _build_result_snapshot(dataset, discovery, detect, result_source="rerun", run=run)
        if run is not None:
            if dataset.source_type == "system_archive":
                discovery, detect = _load_archive_result_pair(dataset)
                snapshot = _build_result_snapshot(dataset, discovery, detect, result_source="archive", run=None)
                snapshot["current_run"] = _run_record(run)
                snapshot["status"] = "archive_with_active_rerun"
                return snapshot
            return {
                "dataset_summary": _dataset_record(dataset, latest_run=run),
                "run_summary": _run_record(run),
                "status": "pending_result",
            }
    if dataset.source_type == "system_archive":
        discovery, detect = _load_archive_result_pair(dataset)
        return _build_result_snapshot(dataset, discovery, detect, result_source="archive", run=None)
    return {
        "dataset_summary": _dataset_record(dataset),
        "run_summary": None,
        "status": "no_result",
    }


async def get_coordination_dataset_graph(
    db: AsyncSession,
    dataset_id: int,
    *,
    node_limit: int = 200,
    min_node_score: float = 0.0,
) -> dict[str, Any]:
    dataset, discovery, detect, result_source, run = await _load_latest_result_context(
        db,
        dataset_id,
        allow_empty_uploaded=True,
    )
    payload = _build_coordination_graph_payload(
        dataset,
        discovery,
        detect,
        node_limit=node_limit,
        min_node_score=min_node_score,
    )
    payload["run_summary"] = {
        "result_source": result_source,
        "run_id": run.id if run is not None else None,
        "status": run.status if run is not None else ("no_result" if result_source == "none" else "archived"),
    }
    return payload


async def get_coordination_community_detail(
    db: AsyncSession,
    dataset_id: int,
    cluster_id: str,
    *,
    member_limit: int = 500,
) -> dict[str, Any]:
    dataset, discovery, detect, result_source, run = await _load_latest_result_context(db, dataset_id)
    payload = _build_coordination_community_payload(
        dataset,
        discovery,
        detect,
        cluster_id=cluster_id,
        member_limit=member_limit,
    )
    payload["run_summary"] = {
        "result_source": result_source,
        "run_id": run.id if run is not None else None,
        "status": run.status if run is not None else "archived",
    }
    return payload


def _run_record(run: CoordinationRun) -> dict[str, Any]:
    return {
        "run_id": run.id,
        "dataset_id": run.dataset_id,
        "status": run.status,
        "progress": run.progress,
        "run_mode": run.run_mode,
        "discover_encoder": run.discover_encoder,
        "community_algorithm": run.community_algorithm,
        "lm_backend": run.lm_backend,
        "gnn_backend": run.gnn_backend,
        "label_mode": run.label_mode,
        "artifact_dir": run.artifact_dir,
        "metrics": _safe_json_loads(run.metrics_json, {}),
        "result_summary": _safe_json_loads(run.result_summary_json, {}),
        "pretrained_weight_path": run.pretrained_weight_path,
        "error": run.error,
        "created_at": run.created_at.isoformat() if run.created_at else None,
        "finished_at": run.finished_at.isoformat() if run.finished_at else None,
    }


async def create_coordination_run(*, db: AsyncSession, dataset_id: int, created_by: int) -> dict[str, Any]:
    await ensure_system_archive_datasets(db)
    result = await db.execute(select(CoordinationDataset).where(CoordinationDataset.id == dataset_id))
    dataset = result.scalar_one_or_none()
    if dataset is None:
        raise ValueError(f"Dataset {dataset_id} not found")
    artifact_dir = RUN_STORAGE_ROOT / dataset.slug / f"run_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S_%f')}"
    run = CoordinationRun(
        dataset_id=dataset.id,
        status="pending",
        progress=0,
        run_mode="rerun",
        discover_encoder=SYSTEM_ARCHIVE_DISCOVER_ENCODER,
        community_algorithm="leiden",
        lm_backend="sbert",
        gnn_backend=SYSTEM_ARCHIVE_GNN_BACKEND,
        label_mode="labeled_mainline" if dataset.has_labels else "unlabeled_china_pretrained",
        artifact_dir=str(artifact_dir),
        created_by=created_by,
        pretrained_weight_path=str(PRETRAINED_CHECKPOINT_PATH) if not dataset.has_labels else None,
    )
    db.add(run)
    await db.flush()
    dataset.latest_run_id = run.id
    await db.commit()
    await db.refresh(run)
    return _run_record(run)


async def get_coordination_run(db: AsyncSession, run_id: int) -> dict[str, Any]:
    result = await db.execute(select(CoordinationRun).where(CoordinationRun.id == run_id))
    run = result.scalar_one_or_none()
    if run is None:
        raise ValueError(f"Run {run_id} not found")
    return _run_record(run)

__all__ = [
    "create_coordination_run",
    "get_coordination_community_detail",
    "get_coordination_dataset_detail",
    "get_coordination_dataset_graph",
    "get_coordination_dataset_latest_result",
    "get_coordination_run",
    "list_coordination_datasets",
    "upload_coordination_dataset",
]
