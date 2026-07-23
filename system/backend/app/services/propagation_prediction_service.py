"""Propagation Analysis macro/micro prediction bridge.

The system-facing path reads vetted artifacts under
``system/research/propagation_analysis``. Live training and event checkpoint
inference stay unavailable until their runners are internalized under the same
boundary.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from functools import lru_cache
from pathlib import Path
from statistics import mean
from typing import Any

from app.core.propagation.trend_predictor import predict_trend


SYSTEM_ROOT = Path(__file__).resolve().parents[3]
PROPAGATION_ANALYSIS_ROOT = SYSTEM_ROOT / "research" / "propagation_analysis"
PROPAGATION_BENCHMARK_ROOT = PROPAGATION_ANALYSIS_ROOT / "benchmark"
PROPAGATION_EVENT_ADAPTER_PATH = PROPAGATION_BENCHMARK_ROOT / "adapters" / "event_adapter.py"
PROPAGATION_LIVE_RUNTIME_PATH = PROPAGATION_ANALYSIS_ROOT / "runtime" / "live_runtime.py"
PROPAGATION_PROTOCOL_PATH = PROPAGATION_ANALYSIS_ROOT / "runtime" / "protocol.py"
PROPAGATION_PUBLIC_LOADER_PATH = PROPAGATION_BENCHMARK_ROOT / "loaders.py"
PROPAGATION_SAMPLE_ARTIFACT = PROPAGATION_BENCHMARK_ROOT / "sequence_vs_minds_sample_300c_5ep_3seed.json"
FOREST_DATA_ROOT = PROPAGATION_ANALYSIS_ROOT / "datasets" / "forest-data"
PROPAGATION_TWITTER_CHECKPOINT = PROPAGATION_BENCHMARK_ROOT / "checkpoints" / "propagation_analysis_sequence_twitter_system.pt"

PropagationAnalysis_MODEL_NAME = "PropagationAnalysisSequenceJointModel"
MINDS_MODEL_NAME = "MINDS"


@lru_cache(maxsize=1)
def _load_propagation_analysis_event_adapter():
    return _load_internal_module(
        path=PROPAGATION_EVENT_ADAPTER_PATH,
        module_name="cogguard_propagation_analysis_event_adapter",
        label="PropagationAnalysis event adapter",
    )


@lru_cache(maxsize=1)
def _load_propagation_analysis_live_runtime():
    return _load_internal_module(
        path=PROPAGATION_LIVE_RUNTIME_PATH,
        module_name="cogguard_propagation_analysis_live_runtime",
        label="PropagationAnalysis live runtime",
    )


@lru_cache(maxsize=1)
def _load_propagation_analysis_protocol():
    return _load_internal_module(
        path=PROPAGATION_PROTOCOL_PATH,
        module_name="cogguard_propagation_analysis_protocol",
        label="PropagationAnalysis hindcast protocol",
    )


@lru_cache(maxsize=1)
def _load_propagation_analysis_public_loader():
    return _load_internal_module(
        path=PROPAGATION_PUBLIC_LOADER_PATH,
        module_name="cogguard_propagation_analysis_public_loader",
        label="PropagationAnalysis public dataset loader",
    )


def _load_internal_module(*, path: Path, module_name: str, label: str):
    if not path.is_file():
        raise RuntimeError(f"{label} not found: {path}")
    module = sys.modules.get(module_name)
    if module is not None:
        return module
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load {label} from {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def build_event_inference_bundle(
    posts: list[dict[str, Any]],
    comments: list[dict[str, Any]] | None = None,
    *,
    max_sequence_len: int = 64,
    user_hash_buckets: int = 4096,
    relation_neighbor_count: int = 4,
    hyperedge_count: int = 4,
    relation_neighbors: dict[int, list[int]] | None = None,
) -> dict[str, Any]:
    adapter = _load_propagation_analysis_event_adapter()
    return adapter.build_event_inference_bundle(
        posts,
        comments,
        max_sequence_len=max_sequence_len,
        user_hash_buckets=user_hash_buckets,
        relation_neighbor_count=relation_neighbor_count,
        hyperedge_count=hyperedge_count,
        relation_neighbors=relation_neighbors,
    )


def predict_event_with_checkpoint(
    checkpoint_path: Path | str,
    posts: list[dict[str, Any]],
    comments: list[dict[str, Any]] | None = None,
    *,
    top_k: int = 10,
    max_sequence_len: int = 64,
    user_hash_buckets: int = 4096,
    relation_neighbor_count: int = 4,
    hyperedge_count: int = 4,
    relation_neighbors: dict[int, list[int]] | None = None,
) -> dict[str, Any]:
    adapter = _load_propagation_analysis_event_adapter()
    return adapter.predict_event_with_checkpoint(
        checkpoint_path,
        posts,
        comments,
        top_k=top_k,
        max_sequence_len=max_sequence_len,
        user_hash_buckets=user_hash_buckets,
        relation_neighbor_count=relation_neighbor_count,
        hyperedge_count=hyperedge_count,
        relation_neighbors=relation_neighbors,
    )


def load_public_cascade_fixture(
    path: Path | str,
    *,
    dataset: str,
    limit: int | None = None,
) -> dict[str, Any]:
    loader = _load_propagation_analysis_public_loader()
    return loader.load_public_cascade_fixture(path, dataset=dataset, limit=limit)


async def predict_propagation_analysis_macro_micro(
    *,
    dataset: str = "twitter",
    seed: int | None = 42,
    run_live: bool = False,
    max_train_cascades: int = 300,
    max_test_cascades: int = 100,
    epochs: int = 5,
) -> dict[str, Any]:
    """Return PropagationAnalysis macro/micro prediction evidence for the system dashboard."""

    dataset = _normalize_dataset(dataset)
    if run_live:
        return _missing_result(
            dataset=dataset,
            seed=seed or 42,
            source="live_small_run",
            note=(
                "PropagationAnalysis live small-run is unavailable until the training runner "
                "is internalized under system/research/propagation_analysis."
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
    """Run current-event PropagationAnalysis macro/micro inference using internal runtime seams."""

    comments = comments or []
    trend_forecast = await predict_trend(posts, comments, mock_llm=True)
    bundle = build_event_inference_bundle(posts, comments)
    checkpoint_available = PROPAGATION_TWITTER_CHECKPOINT.exists()
    bundle["checkpoint_path"] = str(PROPAGATION_TWITTER_CHECKPOINT)
    bundle["checkpoint_available"] = checkpoint_available
    if checkpoint_available:
        checkpoint_result = predict_event_with_checkpoint(
            PROPAGATION_TWITTER_CHECKPOINT,
            posts,
            comments,
            top_k=top_k,
        )
        if checkpoint_result.get("status") == "ok":
            return _with_hindcast_protocol(
                {"technology": "propagation_analysis", **checkpoint_result},
                bundle=bundle,
                posts=posts,
                comments=comments,
                top_k=top_k,
            )

    live_runtime = _load_propagation_analysis_live_runtime()
    result = live_runtime.build_live_event_macro_micro(
        bundle=bundle,
        trend=trend_forecast,
        top_k=top_k,
        checkpoint_available=checkpoint_available,
    )
    return _with_hindcast_protocol(
        {"technology": "propagation_analysis", **result},
        bundle=bundle,
        posts=posts,
        comments=comments,
        top_k=top_k,
    )


def _with_hindcast_protocol(
    result: dict[str, Any],
    *,
    bundle: dict[str, Any],
    posts: list[dict[str, Any]],
    comments: list[dict[str, Any]],
    top_k: int,
) -> dict[str, Any]:
    protocol = _load_propagation_analysis_protocol().build_hindcast_protocol(
        bundle=bundle,
        forecast=result,
        posts=posts,
        comments=comments,
        top_k=top_k,
    )
    merged = dict(result)
    merged.update(protocol)
    return merged


def _load_cached_result(*, dataset: str, seed: int | None) -> dict[str, Any]:
    if not PROPAGATION_SAMPLE_ARTIFACT.exists():
        return _missing_result(
            dataset=dataset,
            seed=seed,
            source="cached_artifact",
            note=f"PropagationAnalysis cached artifact not found: {PROPAGATION_SAMPLE_ARTIFACT}",
        )

    payload = json.loads(PROPAGATION_SAMPLE_ARTIFACT.read_text(encoding="utf-8"))
    rows = [row for row in payload.get("rows", []) if isinstance(row, dict)]
    propagation_analysis_rows = [
        row
        for row in rows
        if row.get("model") == PropagationAnalysis_MODEL_NAME
        and row.get("status") == "ok"
        and _normalize_dataset(str(row.get("dataset", ""))) == dataset
    ]
    if seed is not None:
        selected = [row for row in propagation_analysis_rows if int(row.get("seed", -1)) == int(seed)]
        if selected:
            propagation_analysis_rows = selected
    if not propagation_analysis_rows:
        return _missing_result(
            dataset=dataset,
            seed=seed,
            source="cached_artifact",
            note=f"No PropagationAnalysisSequenceJointModel row for dataset={dataset}, seed={seed}.",
            artifact=str(PROPAGATION_SAMPLE_ARTIFACT),
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
        propagation_analysis_rows=propagation_analysis_rows,
        minds_rows=minds_rows,
        dataset=dataset,
        seed=seed,
        source="cached_artifact",
        artifact=str(PROPAGATION_SAMPLE_ARTIFACT),
        evidence_level=str(payload.get("evidence_level", "sampled_experiment")),
        full_validation_passed=bool(payload.get("full_validation_passed", False)),
        boundary=str(payload.get("boundary", "")),
    )


def _format_result(
    *,
    propagation_analysis_rows: list[dict[str, Any]],
    minds_rows: list[dict[str, Any]],
    dataset: str,
    seed: int | None,
    source: str,
    artifact: str | None,
    evidence_level: str,
    full_validation_passed: bool,
    boundary: str,
) -> dict[str, Any]:
    primary = propagation_analysis_rows[0]
    protocol = primary.get("training_protocol") or {}
    rollout = primary.get("rollout_summary") or {}

    return {
        "schema": "cogguard.propagation_analysis.system_macro_micro_prediction.v1",
        "status": "ok",
        "model": PropagationAnalysis_MODEL_NAME,
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
        or "PropagationAnalysis prediction is displayed as experimental evidence and must not be treated as confirmed future fact.",
        "methodology": primary.get("methodology"),
        "macro": {
            "target": protocol.get("macro_target", "final_size_plus_future_cumulative_trend"),
            "metrics": _aggregate_metrics(
                propagation_analysis_rows,
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
                propagation_analysis_rows,
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
        "rows_used": len(propagation_analysis_rows),
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
        "schema": "cogguard.propagation_analysis.system_macro_micro_prediction.v1",
        "status": "missing_data",
        "model": PropagationAnalysis_MODEL_NAME,
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
