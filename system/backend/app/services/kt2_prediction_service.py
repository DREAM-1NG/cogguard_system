"""KT2 macro/micro propagation prediction bridge.

The system-facing path reads vetted KT2 research artifacts vendored under
``system/research/kt2``. Live training and event checkpoint inference stay
unavailable until their runners are internalized under the same boundary.
"""

from __future__ import annotations

import json
from pathlib import Path
from statistics import mean
from typing import Any


SYSTEM_ROOT = Path(__file__).resolve().parents[3]
KT2_RESEARCH_ROOT = SYSTEM_ROOT / "research" / "kt2"
KT2_BENCHMARK_ROOT = KT2_RESEARCH_ROOT / "benchmark"
KT2_SAMPLE_ARTIFACT = KT2_BENCHMARK_ROOT / "kt2_sequence_vs_minds_sample_300c_5ep_3seed.json"
FOREST_DATA_ROOT = KT2_RESEARCH_ROOT / "datasets" / "forest-data"
KT2_TWITTER_CHECKPOINT = KT2_BENCHMARK_ROOT / "checkpoints" / "kt2_sequence_twitter_system.pt"

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
        return _missing_result(
            dataset=dataset,
            seed=seed or 42,
            source="live_small_run",
            note=(
                "KT2 live small-run is unavailable until the training runner "
                "is internalized under system/research/kt2."
            ),
            artifact=str(FOREST_DATA_ROOT),
        )
    return _load_cached_result(dataset=dataset, seed=seed)


async def predict_event_macro_micro(
    *,
    posts: list[dict[str, Any]],
    comments: list[dict[str, Any]] | None = None,
    top_k: int = 10,
) -> dict[str, Any]:
    """Run current-event KT2 macro/micro inference when an internal checkpoint exists."""

    if len(posts) + len(comments or []) < 3:
        return {
            "status": "data_insufficient",
            "model_status": "unavailable",
        }
    if not KT2_TWITTER_CHECKPOINT.exists():
        return {
            "status": "model_unavailable",
            "model_status": "unavailable",
            "note": f"KT2 event checkpoint not found inside system boundary: {KT2_TWITTER_CHECKPOINT}",
        }
    return {
        "status": "model_unavailable",
        "model_status": "unavailable",
        "note": "KT2 event checkpoint exists, but the internal checkpoint adapter is not wired yet.",
        "artifact": str(KT2_TWITTER_CHECKPOINT),
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
