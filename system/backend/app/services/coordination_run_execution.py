"""Focused run execution module."""

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
    MODEL_SIGNATURE,
    PRETRAINED_CHECKPOINT_DETECT_EPOCHS,
    PRETRAINED_CHECKPOINT_HIDDEN_DIM,
    _coordination_runtime_config,
    _json_dump,
    _runnable_relations,
    _safe_json_loads,
)

async def run_coordination_model_job(run_id: int) -> None:
    async with async_session_factory() as session:
        result = await session.execute(select(CoordinationRun).where(CoordinationRun.id == run_id))
        run = result.scalar_one_or_none()
        if run is None:
            return
        dataset_result = await session.execute(select(CoordinationDataset).where(CoordinationDataset.id == run.dataset_id))
        dataset = dataset_result.scalar_one_or_none()
        if dataset is None:
            run.status = "failed"
            run.progress = 100
            run.error = "Dataset not found"
            run.finished_at = datetime.now(timezone.utc)
            await session.commit()
            return
        run.status = "running"
        run.progress = 5
        run.error = None
        await session.commit()

    try:
        await _execute_coordination_run(run_id)
    except Exception as exc:
        async with async_session_factory() as session:
            result = await session.execute(select(CoordinationRun).where(CoordinationRun.id == run_id))
            run = result.scalar_one_or_none()
            if run is not None:
                run.status = "failed"
                run.progress = 100
                run.error = str(exc)
                run.finished_at = datetime.now(timezone.utc)
                await session.commit()
        raise


async def _execute_coordination_run(run_id: int) -> None:
    async with async_session_factory() as session:
        run_result = await session.execute(select(CoordinationRun).where(CoordinationRun.id == run_id))
        run = run_result.scalar_one_or_none()
        if run is None:
            raise RuntimeError("Coordination run context is missing")
        dataset_result = await session.execute(select(CoordinationDataset).where(CoordinationDataset.id == run.dataset_id))
        dataset = dataset_result.scalar_one_or_none()
        if dataset is None:
            raise RuntimeError("Coordination run context is missing")
        source_path = Path(dataset.source_path)
        artifact_dir = Path(run.artifact_dir)
        relations = _runnable_relations(_safe_json_loads(dataset.available_relations, []))
        event_table = read_event_table(source_path)
        runtime_config = _coordination_runtime_config(dataset)
        run.progress = 15
        await session.commit()

    discovery = await asyncio.to_thread(
        run_dyna_colm_discover,
        event_table,
        output_dir=artifact_dir,
        relations=relations,
        seed=42,
        encoder="magnn",
        community_algorithm="leiden",
        epochs=int(runtime_config["discover_epochs"]),
        embedding_dim=int(runtime_config["discover_embedding_dim"]),
        hidden_dim=int(runtime_config["discover_hidden_dim"]),
        device=str(runtime_config["device"]),
    )
    async with async_session_factory() as session:
        run_result = await session.execute(select(CoordinationRun).where(CoordinationRun.id == run_id))
        run = run_result.scalar_one()
        run.progress = 55
        await session.commit()

    if dataset.has_labels:
        detect = await asyncio.to_thread(
            run_dyna_colm_detect,
            event_table,
            output_dir=artifact_dir,
            relations=relations,
            seed=42,
            discover_encoder="magnn",
            discover_epochs=int(runtime_config["discover_epochs"]),
            embedding_dim=int(runtime_config["detect_embedding_dim"]),
            hidden_dim=int(runtime_config["detect_hidden_dim"]),
            device=str(runtime_config["device"]),
            lm_backend="sbert",
            gnn_backend="fusion_gnn",
            detect_epochs=int(runtime_config["detect_epochs"]),
            split_mode="supervised",
            precomputed_discovery=discovery,
            include_diagnostics=False,
        )
        lm_feature_source = (
            detect.get("detect_model", {}).get("lm_feature_source")
            if isinstance(detect.get("detect_model"), Mapping)
            else None
        )
        if not str(lm_feature_source or "").startswith("sbert:"):
            raise RuntimeError(
                "SBERT is required for Coordination reruns, but the runtime fell back to a non-SBERT LM feature source."
            )
        metrics_payload = detect.get("metrics", {})
        summary_payload = {
            "result_source": "rerun",
            "label_mode": "labeled_mainline",
            "model_signature": MODEL_SIGNATURE,
            "actual_lm_feature_source": lm_feature_source,
            "metrics": metrics_payload,
        }
    else:
        # The China checkpoint is a process-wide shared artifact cached on disk,
        # so it must NOT be built with this rerun's interactive budget (which is
        # deliberately tiny, e.g. 2 epochs / hidden 16) — that would permanently
        # cache a near-untrained model for every later unlabeled inference.
        # Build it at archive quality, off the event loop (SBERT encoding plus a
        # torch training loop would otherwise block every concurrent request).
        metadata = await asyncio.to_thread(
            ensure_china_pretrained_fusion_checkpoint,
            device=str(runtime_config["device"]),
            hidden_dim=PRETRAINED_CHECKPOINT_HIDDEN_DIM,
            embedding_dim=int(runtime_config["detect_embedding_dim"]),
            detect_epochs=PRETRAINED_CHECKPOINT_DETECT_EPOCHS,
        )
        detect = await asyncio.to_thread(
            run_china_pretrained_detect,
            event_table,
            discovery,
            output_dir=artifact_dir,
            relations=relations,
            seed=42,
            embedding_dim=int(runtime_config["detect_embedding_dim"]),
            device=str(runtime_config["device"]),
        )
        metrics_payload = detect.get("unlabeled_inference_summary", {})
        summary_payload = {
            "result_source": "rerun",
            "label_mode": "unlabeled_china_pretrained",
            "model_signature": MODEL_SIGNATURE,
            "actual_lm_feature_source": detect.get("detect_model", {}).get("lm_feature_source")
            if isinstance(detect.get("detect_model"), Mapping)
            else None,
            "pretrained_metadata": metadata,
            "detect_inference": metrics_payload,
        }

    async with async_session_factory() as session:
        run_result = await session.execute(select(CoordinationRun).where(CoordinationRun.id == run_id))
        run = run_result.scalar_one()
        dataset_result = await session.execute(select(CoordinationDataset).where(CoordinationDataset.id == run.dataset_id))
        dataset = dataset_result.scalar_one()
        run.status = "completed"
        run.progress = 100
        run.metrics_json = _json_dump(metrics_payload)
        run.result_summary_json = _json_dump(summary_payload)
        run.finished_at = datetime.now(timezone.utc)
        dataset.latest_run_id = run.id
        await session.commit()

__all__ = [
    "run_coordination_model_job",
]
