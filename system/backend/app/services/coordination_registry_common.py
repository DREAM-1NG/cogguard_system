"""Coordination Discover / Detect dataset registry and rerun service."""

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

def _resolve_coordination_experiment_root() -> Path:
    """Locate the Coordination Discover reproduction root.

    The canonical layout is preferred, but historical runs live under other
    ``*_io_reproduction`` directories. Those archives are untracked local
    assets, so fall back to any root that carries a finalized archive.
    """

    canonical = PROJECT_ROOT / "backend" / "experiments" / "coordination_discover_io_reproduction"
    if canonical.exists():
        return canonical
    experiments_root = PROJECT_ROOT / "backend" / "experiments"
    for candidate in sorted(experiments_root.glob("*_io_reproduction")):
        if any(candidate.glob("archive_*_final_*")):
            return candidate
    return canonical


def _resolve_archive_root(experiment_root: Path) -> Path:
    """Locate the finalized archive directory inside an experiment root."""

    canonical = experiment_root / "archive_coordination_discover_final_20260628"
    if canonical.exists():
        return canonical
    for candidate in sorted(experiment_root.glob("archive_*_final_*")):
        return candidate
    return canonical


COORDINATION_EXPERIMENT_ROOT = _resolve_coordination_experiment_root()
ARCHIVE_ROOT = _resolve_archive_root(COORDINATION_EXPERIMENT_ROOT)
ARCHIVE_MANIFEST_PATH = ARCHIVE_ROOT / "archive_manifest.json"
ARCHIVE_DETECT_METRICS_PATH = ARCHIVE_ROOT / "detect" / "detect_metrics_mean_std.csv"
ARCHIVE_FUSION_DETAIL_ROOT = COORDINATION_EXPERIMENT_ROOT / "accept_detect_fusion_shards_6d_s5_ep20"
ARCHIVE_DISCOVER_DETAIL_ROOT = COORDINATION_EXPERIMENT_ROOT / "accept_discover_magnn_full_embeddings_6d_s5_ep20"
ARCHIVE_EVENT_ROOT = COORDINATION_EXPERIMENT_ROOT / "accept_detect_lm_gnn_6d_s5_ep20"

DATASET_STORAGE_ROOT = PROJECT_ROOT / "output" / "coordination_datasets"
RUN_STORAGE_ROOT = PROJECT_ROOT / "output" / "coordination_runs"

MODEL_SIGNATURE = {
    "discover": "MAGNN + Leiden",
    "detect": "SBERT + fusion_gnn",
}
RUN_RELATIONS = (
    "url_share",
    "hashtag_share",
    "retweet_target",
    "reply_target",
    "quote_target",
    "mention_target",
    "fast_retweet",
    "tweet_similarity",
)
SYSTEM_DATASET_CREATED_BY = 0
# The shared China pretrained checkpoint is cached on disk and reused by every
# later unlabeled inference, so it is always built at archive quality rather than
# with whatever lightweight budget the triggering rerun happened to request.
# These mirror ensure_china_pretrained_fusion_checkpoint's own defaults.
PRETRAINED_CHECKPOINT_HIDDEN_DIM = 32
PRETRAINED_CHECKPOINT_DETECT_EPOCHS = 20
SYSTEM_ARCHIVE_SEED = 42
SYSTEM_ARCHIVE_SPLIT = "supervised"
SYSTEM_ARCHIVE_DISCOVER_ENCODER = "magnn"
SYSTEM_ARCHIVE_GNN_BACKEND = "fusion_gnn"
SYSTEM_ARCHIVE_LM_BACKEND = "sbert"

RELATION_LABELS = {
    "url_share": "共享 URL",
    "hashtag_share": "共享话题",
    "retweet_target": "同转推目标",
    "reply_target": "同回复目标",
    "quote_target": "同引用目标",
    "mention_target": "同提及目标",
    "fast_retweet": "快速转推",
    "tweet_similarity": "文本相似",
    "courl": "共链 URL",
    "cort": "共转推",
    "fastrt": "快速转推",
    "hashseq": "话题序列",
    "profile": "账号画像",
}

OBJECT_ID_RELATION_HINTS = {
    "courl": "url_share",
    "cort": "retweet_target",
    "fastrt": "fast_retweet",
    "hashseq": "hashtag_share",
    "url": "url_share",
    "rt": "retweet_target",
    "profile": "profile",
}


def _coordination_runtime_config(dataset: CoordinationDataset) -> dict[str, int | str]:
    """Return a UI-friendly rerun profile for the fixed Coordination mainline.

    Historical archived experiments keep their original paper-facing settings.
    Uploaded real-world datasets, especially unlabeled ones, run on CPU in the
    local system page, so we use a lighter epoch budget to keep the interactive
    rerun path practical while preserving the same MAGNN/Leiden/SBERT/fusion_gnn
    architecture.
    """

    if dataset.source_type == "uploaded" and not dataset.has_labels:
        return {
            "discover_epochs": 2,
            "discover_embedding_dim": 16,
            "discover_hidden_dim": 16,
            "detect_embedding_dim": 16,
            "detect_hidden_dim": 16,
            "detect_epochs": 2,
            "device": "cpu",
        }
    return {
        "discover_epochs": 20,
        "discover_embedding_dim": 32,
        "discover_hidden_dim": 32,
        "detect_embedding_dim": 32,
        "detect_hidden_dim": 32,
        "detect_epochs": 20,
        "device": "auto",
    }


def _json_load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _json_dump(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False)


def _safe_json_loads(text: str | None, default: Any) -> Any:
    if not text:
        return default
    try:
        return json.loads(text)
    except Exception:
        return default


def _slugify(value: str) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return base or "dataset"


async def _unique_dataset_slug(db: AsyncSession, display_name: str) -> str:
    base = _slugify(display_name)
    slug = base
    index = 1
    while True:
        existing = await db.execute(select(CoordinationDataset).where(CoordinationDataset.slug == slug))
        if existing.scalar_one_or_none() is None:
            return slug
        index += 1
        slug = f"{base}-{index}"


def _dataset_record(dataset: CoordinationDataset, *, latest_run: CoordinationRun | None = None, archive_summary: Mapping[str, Any] | None = None) -> dict[str, Any]:
    relations = _safe_json_loads(dataset.available_relations, [])
    metadata = _safe_json_loads(dataset.metadata_json, {})
    latest_metrics = None
    latest_status = "idle"
    latest_source = "none"
    if latest_run is not None:
        latest_status = latest_run.status
        latest_source = latest_run.run_mode
        latest_metrics = _safe_json_loads(latest_run.metrics_json, {})
    elif archive_summary is not None:
        latest_status = "archived"
        latest_source = "archive"
        latest_metrics = archive_summary.get("metrics")
    return {
        "dataset_id": dataset.id,
        "slug": dataset.slug,
        "display_name": dataset.display_name,
        "source_type": dataset.source_type,
        "source_format": dataset.source_format,
        "has_labels": bool(dataset.has_labels),
        "event_rows": int(dataset.event_rows),
        "account_nodes": int(dataset.account_nodes),
        "object_ids": int(dataset.object_ids),
        "user_user_edges": int(dataset.user_user_edges),
        "available_relations": relations,
        "latest_run_id": dataset.latest_run_id,
        "latest_status": latest_status,
        "latest_source": latest_source,
        "latest_metrics": latest_metrics,
        "created_by": dataset.created_by,
        "created_at": dataset.created_at.isoformat() if dataset.created_at else None,
        "updated_at": dataset.updated_at.isoformat() if dataset.updated_at else None,
        "metadata": metadata,
    }


def _system_dataset_paths(dataset_name: str) -> dict[str, str]:
    return {
        "events_path": str(ARCHIVE_EVENT_ROOT / dataset_name / "events.csv"),
        "discover_path": str(
            ARCHIVE_DISCOVER_DETAIL_ROOT
            / dataset_name
            / f"seed_{SYSTEM_ARCHIVE_SEED}"
            / SYSTEM_ARCHIVE_DISCOVER_ENCODER
            / "discovery_summary.json"
        ),
        "detect_path": str(
            ARCHIVE_FUSION_DETAIL_ROOT
            / f"{dataset_name}_batch"
            / dataset_name
            / f"seed_{SYSTEM_ARCHIVE_SEED}"
            / SYSTEM_ARCHIVE_DISCOVER_ENCODER
            / SYSTEM_ARCHIVE_SPLIT
            / SYSTEM_ARCHIVE_GNN_BACKEND
            / SYSTEM_ARCHIVE_LM_BACKEND
            / "detection_summary.json"
        ),
    }


def _archive_detect_summary_map() -> dict[str, dict[str, Any]]:
    if not ARCHIVE_DETECT_METRICS_PATH.exists():
        return {}
    import csv

    summaries: dict[str, dict[str, Any]] = {}
    with ARCHIVE_DETECT_METRICS_PATH.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            if (
                row.get("discover_encoder") == SYSTEM_ARCHIVE_DISCOVER_ENCODER
                and row.get("split_mode") == SYSTEM_ARCHIVE_SPLIT
                and row.get("gnn_backend") == SYSTEM_ARCHIVE_GNN_BACKEND
                and row.get("lm_backend") == SYSTEM_ARCHIVE_LM_BACKEND
            ):
                dataset = str(row.get("dataset") or "")
                summaries[dataset] = {
                    "metrics": {
                        "auc_mean": _as_float(row.get("auc_mean")),
                        "auprc_mean": _as_float(row.get("auprc_mean")),
                        "macro_f1_mean": _as_float(row.get("macro_f1_mean")),
                        "precision_at_k_mean": _as_float(row.get("precision_at_k_mean")),
                        "recall_at_k_mean": _as_float(row.get("recall_at_k_mean")),
                        "accuracy_mean": _as_float(row.get("accuracy_mean")),
                    },
                    "summary_row": row,
                }
    return summaries


def _as_float(value: Any) -> float | None:
    try:
        if value is None or value == "":
            return None
        return float(value)
    except Exception:
        return None


def _str_column(frame: pd.DataFrame, name: str) -> pd.Series:
    """Return ``frame[name]`` as a NaN-free string Series, even if absent.

    ``frame.get(name, "")`` returns the plain ``str`` default when the column is
    missing, so chaining ``.fillna()`` / ``.astype(str)`` onto it raises
    AttributeError. Datasets uploaded with only the minimum columns
    (account_id/relation/object_id/timestamp) legitimately have no content
    column, so every access must go through this helper.
    """
    if name in frame.columns:
        return frame[name].fillna("").astype(str)
    return pd.Series("", index=frame.index, dtype="object")


async def ensure_system_archive_datasets(db: AsyncSession) -> None:
    if not ARCHIVE_MANIFEST_PATH.exists():
        return
    manifest = _json_load(ARCHIVE_MANIFEST_PATH)
    archive_summaries = _archive_detect_summary_map()
    for row in manifest.get("dataset_scale", []):
        dataset_name = str(row.get("dataset") or "").strip()
        if not dataset_name:
            continue
        existing = await db.execute(select(CoordinationDataset).where(CoordinationDataset.slug == dataset_name.lower()))
        dataset = existing.scalar_one_or_none()
        metadata = {
            "archive_name": manifest.get("archive_name"),
            "archive_paths": _system_dataset_paths(dataset_name),
            "archive_latest_summary": archive_summaries.get(dataset_name, {}),
        }
        values = {
            "slug": dataset_name.lower(),
            "display_name": dataset_name,
            "source_type": "system_archive",
            "source_format": "csv",
            "source_path": _system_dataset_paths(dataset_name)["events_path"],
            "metadata_json": _json_dump(metadata),
            "has_labels": True,
            "event_rows": int(row.get("event_rows", 0) or 0),
            "account_nodes": int(row.get("account_nodes", 0) or 0),
            "object_ids": int(row.get("object_ids", 0) or 0),
            "user_user_edges": int(row.get("user_user_edges", 0) or 0),
            "available_relations": _json_dump(row.get("relations", [])),
            "created_by": SYSTEM_DATASET_CREATED_BY,
        }
        if dataset is None:
            db.add(CoordinationDataset(**values))
        else:
            for key, value in values.items():
                setattr(dataset, key, value)
    try:
        await db.commit()
    except IntegrityError:
        # Two concurrent first-requests both see "no row" for an archive slug and
        # both insert; the loser trips the unique slug index. The archive values
        # are identical either way, so treat this as already-synced rather than
        # surfacing a 500 from what is a read-path side effect.
        await db.rollback()


def _runnable_relations(raw_relations: Sequence[str]) -> tuple[str, ...]:
    seen = []
    for relation in raw_relations:
        relation = str(relation)
        if relation in RUN_RELATIONS and relation not in seen:
            seen.append(relation)
    return tuple(seen or DEFAULT_RELATIONS)


def _dataset_paths_from_record(dataset: CoordinationDataset) -> dict[str, Any]:
    metadata = _safe_json_loads(dataset.metadata_json, {})
    archive_paths = metadata.get("archive_paths", {}) if isinstance(metadata, dict) else {}
    return {
        "source_path": dataset.source_path,
        "archive_paths": archive_paths if isinstance(archive_paths, dict) else {},
    }


def _system_archive_run_summary(dataset: CoordinationDataset) -> dict[str, Any]:
    metadata = _safe_json_loads(dataset.metadata_json, {})
    archive_summary = metadata.get("archive_latest_summary", {}) if isinstance(metadata, dict) else {}
    return {
        "source": "archive",
        "status": "archived",
        "run_mode": "archive",
        "label_mode": "labeled_mainline",
        "model_signature": MODEL_SIGNATURE,
        "metrics": archive_summary.get("metrics") if isinstance(archive_summary, dict) else None,
    }


def _load_archive_result_pair(dataset: CoordinationDataset) -> tuple[dict[str, Any], dict[str, Any]]:
    paths = _dataset_paths_from_record(dataset).get("archive_paths", {})
    discover_path = Path(str(paths.get("discover_path", "")))
    detect_path = Path(str(paths.get("detect_path", "")))
    if not discover_path.exists():
        raise FileNotFoundError(f"Missing archived discover summary: {discover_path}")
    if not detect_path.exists():
        raise FileNotFoundError(f"Missing archived detect summary: {detect_path}")
    return _json_load(discover_path), _json_load(detect_path)

__all__ = [
    "ARCHIVE_DETECT_METRICS_PATH",
    "ARCHIVE_DISCOVER_DETAIL_ROOT",
    "ARCHIVE_EVENT_ROOT",
    "ARCHIVE_FUSION_DETAIL_ROOT",
    "ARCHIVE_MANIFEST_PATH",
    "ARCHIVE_ROOT",
    "COORDINATION_EXPERIMENT_ROOT",
    "DATASET_STORAGE_ROOT",
    "MODEL_SIGNATURE",
    "OBJECT_ID_RELATION_HINTS",
    "PRETRAINED_CHECKPOINT_DETECT_EPOCHS",
    "PRETRAINED_CHECKPOINT_HIDDEN_DIM",
    "RELATION_LABELS",
    "RUN_RELATIONS",
    "RUN_STORAGE_ROOT",
    "SYSTEM_ARCHIVE_DISCOVER_ENCODER",
    "SYSTEM_ARCHIVE_GNN_BACKEND",
    "SYSTEM_ARCHIVE_LM_BACKEND",
    "SYSTEM_ARCHIVE_SEED",
    "SYSTEM_ARCHIVE_SPLIT",
    "SYSTEM_DATASET_CREATED_BY",
    "ensure_system_archive_datasets",
]
