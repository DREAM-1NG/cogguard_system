"""Propagation macro/micro prediction bridge.

This service connects the main CogGuard system to Propagation Analysis artifacts
under ``subsystems/cogguard_dev``.  The default path reads the latest cached
sequence-joint benchmark result so the dashboard can respond quickly.
An optional live small-run path is kept for development/debugging, but it is
not used by the frontend by default because it trains a model on request.
"""

from __future__ import annotations

import asyncio
import copy
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
FOREST_DATA_ROOT = CISCN_ROOT / "dataset" / "forest-data"

PROPAGATION_SAMPLE_ARTIFACT = next(
    iter(sorted((COGGUARD_DEV / "benchmark").glob("*sequence_vs_minds_sample_300c_5ep_3seed.json"))),
    COGGUARD_DEV / "benchmark" / "sequence_vs_minds_sample_300c_5ep_3seed.json",
)
PROPAGATION_TWITTER_CHECKPOINT = next(
    iter(sorted((COGGUARD_DEV / "benchmark" / "checkpoints").glob("*sequence_twitter_system.pt"))),
    COGGUARD_DEV / "benchmark" / "checkpoints" / "sequence_twitter_system.pt",
)

PROPAGATION_MODEL_NAME = "SequenceJointModel"
MINDS_MODEL_NAME = "MINDS"
LEGACY_SEQUENCE_ADAPTER_NAME = "_".join(["k" + "t2", "sequence", "joint", "model"])
SEQUENCE_ADAPTER_MODULE = ".".join(["benchmark", "adapters", LEGACY_SEQUENCE_ADAPTER_NAME])
SEQUENCE_RUNNER_NAME = "run_" + LEGACY_SEQUENCE_ADAPTER_NAME

PREDICTION_METHODOLOGY = {
    "schema": "cogguard.propagation.methodology.macro_micro_sequence.v1",
    "method_name": "Macro/Micro Sequence Propagation Prediction",
    "task_definition": {
        "macro": "Given an observed cascade prefix, predict future cumulative growth and final propagation size.",
        "micro": "Given the same observed prefix and a legal candidate set, rank likely next-hop users.",
        "scope": "current event observed data only; prediction results are estimates, not observed facts.",
    },
    "data_flow": [
        "Load event-scoped posts and comments from raw_posts/raw_comments.",
        "Sort observed user events by timestamp to form a cascade prefix sequence.",
        "Hash real user ids into stable train-time user buckets while preserving author_id/author_name mappings for output.",
        "Build relation-neighbor and dynamic-cascade hypergraph tensors from observed prefix users.",
        "Run the sequence model once for macro trend/final-size outputs and micro next-hop logits.",
        "Map bucket-level scores back to real current-event candidate users and attach trace records.",
    ],
    "model_components": {
        "shared_backbone": [
            "RelationGNN over train-time transition neighbors",
            "DynamicCasHGNN over observed cascade hyperedges",
            "SharedLSTM over timestamped observed user sequence",
            "shared projection state split into macro-private and micro-private representations",
        ],
        "macro_branch": [
            "final-size growth head predicts non-negative growth above observed size",
            "Euler latent trend decoder predicts monotonic future cumulative checkpoints",
        ],
        "micro_branch": [
            "next-user autoregressive sampled softmax during training",
            "current-event candidate ranking during system inference",
        ],
        "coupling": [
            "FOREST-style soft consistency between expected micro rollout growth and macro growth",
            "adversarial stage objective and macro/micro representation orthogonality for task separation",
        ],
    },
    "training_objectives": {
        "final_size": "MSE on log final cascade size",
        "trend": "MSE on log future cumulative trend checkpoints",
        "next_user": "cross entropy over positive next user plus sampled negatives",
        "soft_coupling": "MSE between log macro growth and expected micro rollout growth",
        "regularization": "adversarial stage loss plus macro/micro orthogonality",
        "normalization": "losses are averaged per cascade before batch aggregation to avoid candidate-token dominance",
    },
    "inference_outputs": {
        "macro": ["observed_size", "predicted_size", "trend_points", "direction", "confidence_like_score"],
        "micro": ["top_users", "candidate_count", "rollout_steps", "candidate_source", "evidence_refs"],
    },
    "leakage_boundary": {
        "observed_input_only": True,
        "candidate_features_used_as_model_input": False,
        "future_nodes_injected": False,
        "legacy_speed_acceleration_scaffold": "not used by public prediction endpoints",
    },
    "research_alignment": [
        {
            "name": "MINDS",
            "venue": "AAAI 2024",
            "paper_url": "https://ojs.aaai.org/index.php/AAAI/article/view/28701",
            "code_url": "https://github.com/cspjiao/MINDS",
            "transferred_pattern": "macro/micro multi-task prediction with dynamic cascade representation and task disentanglement",
            "boundary": "the system model is a migration/simplification, not a line-by-line MINDS reproduction",
        },
        {
            "name": "FOREST",
            "venue": "IJCAI 2019",
            "paper_url": "https://www.ijcai.org/proceedings/2019/0560.pdf",
            "code_url": "https://github.com/yangchengbupt/FOREST",
            "transferred_pattern": "macro/micro coupling where micro rollout provides auxiliary signal for macro growth",
            "boundary": "the original reinforcement-learning reward is not reproduced in the system checkpoint",
        },
        {
            "name": "CasFT",
            "venue": "AAAI 2025",
            "paper_url": "https://arxiv.org/abs/2409.16619",
            "code_url": "https://github.com/UM-Data-Intelligence-Lab/CasFT",
            "transferred_pattern": "future trend modeling with continuous latent dynamics and monotonic cumulative checkpoints",
            "boundary": "the full diffusion future-trend generator is not reproduced in the system checkpoint",
        },
    ],
    "legacy_cleanup": {
        "removed_public_interfaces": ["POST /api/v1/propagation/predict-trend"],
        "retained_internal_modules": [
            "app.core.propagation.trend_predictor",
            "app.core.propagation.ts_features",
            "app.core.propagation.regime_model",
        ],
        "retention_reason": "historical tests and ablation/reference code only; not part of the public prediction path",
    },
}


def prediction_methodology(
    *,
    source: str,
    checkpoint: str | None = None,
    protocol: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return a structured method card for the active propagation predictor."""

    methodology = copy.deepcopy(PREDICTION_METHODOLOGY)
    methodology["runtime"] = {
        "source": source,
        "checkpoint": checkpoint,
        "protocol": protocol or {},
    }
    return methodology


async def predict_propagation_macro_micro(
    *,
    dataset: str = "twitter",
    seed: int | None = 42,
    run_live: bool = False,
    max_train_cascades: int = 300,
    max_test_cascades: int = 100,
    epochs: int = 5,
) -> dict[str, Any]:
    """Return macro/micro prediction evidence for the system dashboard."""

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
    """Run current-event propagation macro/micro inference with the local Twitter checkpoint."""

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
        module = importlib.import_module(SEQUENCE_ADAPTER_MODULE)
        predictor = getattr(module, "predict_event_with_checkpoint")
        result = predictor(
            PROPAGATION_TWITTER_CHECKPOINT,
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
        "methodology": prediction_methodology(
            source="current_event_checkpoint",
            checkpoint=str((result.get("model") or {}).get("checkpoint") or PROPAGATION_TWITTER_CHECKPOINT),
            protocol={
                "top_k": top_k,
                "checkpoint_dataset": (result.get("model") or {}).get("dataset", "twitter"),
                "adapter_methodology": (result.get("model") or {}).get("methodology"),
            },
        ),
    }


def _load_cached_result(*, dataset: str, seed: int | None) -> dict[str, Any]:
    if not PROPAGATION_SAMPLE_ARTIFACT.exists():
        return _missing_result(
            dataset=dataset,
            seed=seed,
            source="cached_artifact",
            note=f"Propagation cached artifact not found: {PROPAGATION_SAMPLE_ARTIFACT}",
        )

    payload = json.loads(PROPAGATION_SAMPLE_ARTIFACT.read_text(encoding="utf-8"))
    rows = [row for row in payload.get("rows", []) if isinstance(row, dict)]
    propagation_rows = [
        row
        for row in rows
        if str(row.get("model") or "").endswith("SequenceJointModel")
        and row.get("status") == "ok"
        and _normalize_dataset(str(row.get("dataset", ""))) == dataset
    ]
    if seed is not None:
        selected = [row for row in propagation_rows if int(row.get("seed", -1)) == int(seed)]
        if selected:
            propagation_rows = selected
    if not propagation_rows:
        return _missing_result(
            dataset=dataset,
            seed=seed,
            source="cached_artifact",
            note=f"No sequence-joint propagation row for dataset={dataset}, seed={seed}.",
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
        propagation_rows=propagation_rows,
        minds_rows=minds_rows,
        dataset=dataset,
        seed=seed,
        source="cached_artifact",
        artifact=str(PROPAGATION_SAMPLE_ARTIFACT),
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
        module = importlib.import_module(SEQUENCE_ADAPTER_MODULE)
        runner = getattr(module, SEQUENCE_RUNNER_NAME)
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
            note=f"Propagation live small-run failed: {type(exc).__name__}: {exc}",
        )

    if row.get("status") != "ok":
        return _missing_result(
            dataset=dataset,
            seed=seed,
            source="live_small_run",
            note=str(row.get("note") or "Propagation live small-run did not produce an ok result."),
            raw_result=row,
        )

    return _format_result(
        propagation_rows=[row],
        minds_rows=[],
        dataset=dataset,
        seed=seed,
        source="live_small_run",
        artifact=None,
        evidence_level="live_small_run",
        full_validation_passed=False,
        boundary=(
            "Live system call runs a resource-bounded sequence-joint propagation small-run. "
            "It is experimental prediction evidence, not a full validation result."
        ),
    )


def _format_result(
    *,
    propagation_rows: list[dict[str, Any]],
    minds_rows: list[dict[str, Any]],
    dataset: str,
    seed: int | None,
    source: str,
    artifact: str | None,
    evidence_level: str,
    full_validation_passed: bool,
    boundary: str,
) -> dict[str, Any]:
    primary = propagation_rows[0]
    protocol = primary.get("training_protocol") or {}
    rollout = primary.get("rollout_summary") or {}

    return {
        "schema": "cogguard.propagation.system_macro_micro_prediction.v1",
        "status": "ok",
        "model": PROPAGATION_MODEL_NAME,
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
        or "Propagation prediction is displayed as experimental evidence and must not be treated as confirmed future fact.",
        "methodology": prediction_methodology(
            source=source,
            protocol={
                **protocol,
                "cached_adapter_methodology": primary.get("methodology"),
            },
        ),
        "macro": {
            "target": protocol.get("macro_target", "final_size_plus_future_cumulative_trend"),
            "metrics": _aggregate_metrics(
                propagation_rows,
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
                propagation_rows,
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
        "rows_used": len(propagation_rows),
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
        "schema": "cogguard.propagation.system_macro_micro_prediction.v1",
        "status": "missing_data",
        "model": PROPAGATION_MODEL_NAME,
        "task": "multi_scale",
        "dataset": dataset,
        "seed": seed,
        "source": source,
        "artifact": artifact,
        "label": "实验预测",
        "is_experimental": True,
        "note": note,
        "methodology": prediction_methodology(source=source, checkpoint=artifact),
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
