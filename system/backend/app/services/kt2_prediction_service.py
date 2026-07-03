"""KT2 macro/micro propagation prediction bridge.

This service connects the main CogGuard system to the KT2 research artifacts
under ``subsystems/cogguard_dev``.  The default path reads the latest cached
KT2SequenceJointModel benchmark result so the dashboard can respond quickly.
An optional live small-run path is kept for development/debugging, but it is
not used by the frontend by default because it trains a model on request.
"""

from __future__ import annotations

import asyncio
import importlib
import json
import sys
from pathlib import Path
from statistics import mean
from typing import Any


SYSTEM_ROOT = Path(__file__).resolve().parents[3]
COGGUARD_ROOT = SYSTEM_ROOT.parent
CISCN_ROOT = COGGUARD_ROOT.parent
COGGUARD_DEV = COGGUARD_ROOT / "subsystems" / "cogguard_dev"
KT2_SAMPLE_ARTIFACT = COGGUARD_DEV / "benchmark" / "kt2_sequence_vs_minds_sample_300c_5ep_3seed.json"
FOREST_DATA_ROOT = CISCN_ROOT / "dataset" / "forest-data"
KT2_TWITTER_CHECKPOINT = COGGUARD_DEV / "benchmark" / "checkpoints" / "kt2_sequence_twitter_system.pt"

KT2_MODEL_NAME = "KT2SequenceJointModel"
MINDS_MODEL_NAME = "MINDS"


async def predict_kt2_macro_micro(
    *,
    dataset: str = "twitter",
    seed: int | None = 42,
    run_live: bool = False,
    max_train_cascades: int = 300,
    max_test_cascades: int = 100,
    epochs: int = 5,
) -> dict[str, Any]:
    """Return KT2 macro/micro prediction evidence for the system dashboard."""

    dataset = _normalize_dataset(dataset)
    if run_live:
        return await asyncio.to_thread(
            _run_live_small_run,
            dataset=dataset,
            seed=seed or 42,
            max_train_cascades=max_train_cascades,
            max_test_cascades=max_test_cascades,
            epochs=epochs,
        )
    return _load_cached_result(dataset=dataset, seed=seed)


async def predict_event_macro_micro(
    *,
    posts: list[dict[str, Any]],
    comments: list[dict[str, Any]] | None = None,
    top_k: int = 10,
) -> dict[str, Any]:
    """Run current-event KT2 macro/micro inference with the local Twitter checkpoint."""

    if len(posts) + len(comments or []) < 3:
        return {
            "status": "data_insufficient",
            "model_status": "unavailable",
        }
    return await asyncio.to_thread(
        _predict_event_macro_micro_sync,
        posts=posts,
        comments=comments or [],
        top_k=top_k,
    )


def _predict_event_macro_micro_sync(
    *,
    posts: list[dict[str, Any]],
    comments: list[dict[str, Any]],
    top_k: int,
) -> dict[str, Any]:
    try:
        if str(COGGUARD_DEV) not in sys.path:
            sys.path.insert(0, str(COGGUARD_DEV))
        module = importlib.import_module("benchmark.adapters.kt2_sequence_joint_model")
        predictor = getattr(module, "predict_event_with_checkpoint")
        result = predictor(
            KT2_TWITTER_CHECKPOINT,
            posts,
            comments,
            top_k=top_k,
            device="cpu",
        )
    except Exception:
        return {
            "status": "model_unavailable",
            "model_status": "unavailable",
        }

    if result.get("status") != "ok":
        return {
            "status": result.get("status", "model_unavailable"),
            "model_status": "unavailable",
        }

    return {
        "status": "ok",
        "model_status": "available",
        "macro": result.get("macro") or {},
        "micro": result.get("micro") or {},
        "model": result.get("model") or {},
    }


def _load_cached_result(*, dataset: str, seed: int | None) -> dict[str, Any]:
    if not KT2_SAMPLE_ARTIFACT.exists():
        return _missing_result(
            dataset=dataset,
            seed=seed,
            source="cached_artifact",
            note=f"KT2 cached artifact not found: {KT2_SAMPLE_ARTIFACT}",
        )

    payload = json.loads(KT2_SAMPLE_ARTIFACT.read_text(encoding="utf-8"))
    rows = [row for row in payload.get("rows", []) if isinstance(row, dict)]
    kt2_rows = [
        row
        for row in rows
        if row.get("model") == KT2_MODEL_NAME
        and row.get("status") == "ok"
        and _normalize_dataset(str(row.get("dataset", ""))) == dataset
    ]
    if seed is not None:
        selected = [row for row in kt2_rows if int(row.get("seed", -1)) == int(seed)]
        if selected:
            kt2_rows = selected
    if not kt2_rows:
        return _missing_result(
            dataset=dataset,
            seed=seed,
            source="cached_artifact",
            note=f"No KT2SequenceJointModel row for dataset={dataset}, seed={seed}.",
            artifact=str(KT2_SAMPLE_ARTIFACT),
        )

    minds_rows = [
        row
        for row in rows
        if row.get("model") == MINDS_MODEL_NAME
        and row.get("status") == "ok"
        and _normalize_dataset(str(row.get("dataset", ""))) == dataset
    ]
    if seed is not None:
        selected = [row for row in minds_rows if int(row.get("seed", -1)) == int(seed)]
        if selected:
            minds_rows = selected

    return _format_result(
        kt2_rows=kt2_rows,
        minds_rows=minds_rows,
        dataset=dataset,
        seed=seed,
        source="cached_artifact",
        artifact=str(KT2_SAMPLE_ARTIFACT),
        evidence_level=str(payload.get("evidence_level", "sampled_experiment")),
        full_validation_passed=bool(payload.get("full_validation_passed", False)),
        boundary=str(payload.get("boundary", "")),
    )


def _run_live_small_run(
    *,
    dataset: str,
    seed: int,
    max_train_cascades: int,
    max_test_cascades: int,
    epochs: int,
) -> dict[str, Any]:
    data_dir = FOREST_DATA_ROOT / dataset
    if not data_dir.exists():
        return _missing_result(
            dataset=dataset,
            seed=seed,
            source="live_small_run",
            note=f"FOREST dataset directory not found: {data_dir}",
        )

    try:
        if str(COGGUARD_DEV) not in sys.path:
            sys.path.insert(0, str(COGGUARD_DEV))
        module = importlib.import_module("benchmark.adapters.kt2_sequence_joint_model")
        runner = getattr(module, "run_kt2_sequence_joint_model")
        row = runner(
            data_dir,
            dataset=dataset,
            seed=seed,
            epochs=epochs,
            max_train_cascades=max_train_cascades,
            max_test_cascades=max_test_cascades,
            batch_size=128,
            hidden_dim=64,
            device="cpu",
        )
    except Exception as exc:  # pragma: no cover - environment dependent.
        return _missing_result(
            dataset=dataset,
            seed=seed,
            source="live_small_run",
            note=f"KT2 live small-run failed: {type(exc).__name__}: {exc}",
        )

    if row.get("status") != "ok":
        return _missing_result(
            dataset=dataset,
            seed=seed,
            source="live_small_run",
            note=str(row.get("note") or "KT2 live small-run did not produce an ok result."),
            raw_result=row,
        )

    return _format_result(
        kt2_rows=[row],
        minds_rows=[],
        dataset=dataset,
        seed=seed,
        source="live_small_run",
        artifact=None,
        evidence_level="live_small_run",
        full_validation_passed=False,
        boundary=(
            "Live system call runs a resource-bounded KT2SequenceJointModel small-run. "
            "It is experimental prediction evidence, not a full validation result."
        ),
    )


def _format_result(
    *,
    kt2_rows: list[dict[str, Any]],
    minds_rows: list[dict[str, Any]],
    dataset: str,
    seed: int | None,
    source: str,
    artifact: str | None,
    evidence_level: str,
    full_validation_passed: bool,
    boundary: str,
) -> dict[str, Any]:
    primary = kt2_rows[0]
    protocol = primary.get("training_protocol") or {}
    rollout = primary.get("rollout_summary") or {}

    return {
        "schema": "cogguard.kt2.system_macro_micro_prediction.v1",
        "status": "ok",
        "model": KT2_MODEL_NAME,
        "task": "multi_scale",
        "dataset": dataset,
        "seed": seed,
        "source": source,
        "artifact": artifact,
        "label": "实验预测",
        "is_experimental": True,
        "evidence_level": evidence_level,
        "full_validation_passed": full_validation_passed,
        "boundary": boundary
        or "KT2 prediction is displayed as experimental evidence and must not be treated as confirmed future fact.",
        "methodology": primary.get("methodology"),
        "macro": {
            "target": protocol.get("macro_target", "final_size_plus_future_cumulative_trend"),
            "metrics": _aggregate_metrics(
                kt2_rows,
                [
                    "msle",
                    "mae",
                    "rmse",
                    "mape_percent",
                    "smape_percent",
                    "direction_accuracy",
                    "trend_mae",
                    "trend_rmse",
                    "macro_micro_soft_consistency",
                    "macro_micro_consistency",
                ],
            ),
            "obs_ratios": protocol.get("obs_ratios") or primary.get("obs_ratios") or [],
        },
        "micro": {
            "target": protocol.get("micro_target", "next_user_autoregressive_sampled_softmax"),
            "metrics": _aggregate_metrics(
                kt2_rows,
                [
                    "candidate_recall_full",
                    "hits@10",
                    "hits@50",
                    "hits@100",
                    "map@10",
                    "map@50",
                    "map@100",
                    "mrr",
                    "ndcg@10",
                    "ndcg@50",
                    "ndcg@100",
                ],
            ),
            "rollout_summary": rollout,
            "topk_examples": rollout.get("topk_examples") or primary.get("rollout_topk_examples") or [],
        },
        "baseline_comparison": {
            "baseline_model": MINDS_MODEL_NAME,
            "metrics": _aggregate_metrics(
                minds_rows,
                ["msle", "hits@10", "hits@50", "hits@100", "map@10", "map@50", "map@100"],
            ),
            "note": "MINDS rows are shown only as experiment baseline context when cached results are available.",
        },
        "training_protocol": protocol,
        "candidate_protocol_audit": primary.get("candidate_protocol_audit") or {},
        "rows_used": len(kt2_rows),
    }


def _aggregate_metrics(rows: list[dict[str, Any]], keys: list[str]) -> dict[str, float | None]:
    result: dict[str, float | None] = {}
    for key in keys:
        values = [_as_float(row.get(key)) for row in rows]
        present = [value for value in values if value is not None]
        result[key] = round(mean(present), 6) if present else None
    return result


def _missing_result(
    *,
    dataset: str,
    seed: int | None,
    source: str,
    note: str,
    artifact: str | None = None,
    raw_result: dict[str, Any] | None = None,
) -> dict[str, Any]:
    result = {
        "schema": "cogguard.kt2.system_macro_micro_prediction.v1",
        "status": "missing_data",
        "model": KT2_MODEL_NAME,
        "task": "multi_scale",
        "dataset": dataset,
        "seed": seed,
        "source": source,
        "artifact": artifact,
        "label": "实验预测",
        "is_experimental": True,
        "note": note,
    }
    if raw_result is not None:
        result["raw_result"] = raw_result
    return result


def _normalize_dataset(dataset: str) -> str:
    value = (dataset or "twitter").strip().lower()
    aliases = {
        "tweet": "twitter",
        "weibo": "twitter",
        "douban": "douban",
        "memetracker": "memetracker",
    }
    return aliases.get(value, value)


def _as_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
