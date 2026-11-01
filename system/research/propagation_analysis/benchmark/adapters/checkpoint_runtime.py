"""Checkpoint inference runtime for current-event propagation prediction."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np


def _load_sibling_module(name: str):
    module_name = f"cogguard_propagation_analysis_{name}"
    module = sys.modules.get(module_name)
    if module is not None:
        return module
    path = Path(__file__).with_name(f"{name}.py")
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load Propagation Analysis runtime module: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


_event_adapter = _load_sibling_module("event_adapter")
_sequence_model = _load_sibling_module("sequence_model")
_contract = _load_sibling_module("prediction_contract")


def predict_event_with_checkpoint(
    checkpoint_path: Path | str,
    posts: Sequence[Mapping[str, Any]],
    comments: Sequence[Mapping[str, Any]] | None = None,
    *,
    top_k: int = 10,
    observation_ratio: float | None = None,
    prefix_is_preselected: bool = False,
    device: str = "cpu",
) -> dict[str, Any]:
    """Load the internal checkpoint and run a CPU-safe event inference pass."""

    checkpoint_path = Path(checkpoint_path)
    if not checkpoint_path.is_file():
        return _contract.empty_prediction(
            "missing_checkpoint",
            "The deployed Twitter checkpoint is unavailable.",
            checkpoint_path,
        )

    torch, nn, torch_error = _sequence_model.safe_torch()
    if torch_error is not None:
        return _contract.empty_prediction(
            "missing_dependency",
            f"PyTorch is unavailable: {torch_error}",
            checkpoint_path,
        )

    target_device = torch.device("cuda" if device == "cuda" and torch.cuda.is_available() else "cpu")
    try:
        try:
            checkpoint = torch.load(checkpoint_path, map_location=target_device, weights_only=False)
        except TypeError:  # pragma: no cover - old PyTorch.
            checkpoint = torch.load(checkpoint_path, map_location=target_device)
        config = checkpoint.get("config") or {}
        configured_ratios = tuple(
            sorted(
                {
                    round(float(value), 4)
                    for value in (config.get("obs_ratios") or [_event_adapter.DEFAULT_LIVE_OBSERVATION_RATIO])
                    if 0.0 < float(value) <= 1.0
                }
            )
        )
        requested_ratio = (
            _event_adapter.DEFAULT_LIVE_OBSERVATION_RATIO if observation_ratio is None else float(observation_ratio)
        )
        if not configured_ratios or min(
            abs(requested_ratio - supported_ratio) for supported_ratio in configured_ratios
        ) > 1e-4:
            return _contract.empty_prediction(
                "unsupported_observation_ratio",
                "The checkpoint supports only its recorded observation ratios.",
                checkpoint_path,
            )
        bundle = _event_adapter.build_event_inference_bundle(
            posts,
            comments or [],
            max_sequence_len=int(config.get("max_sequence_len", 64)),
            user_hash_buckets=int(config.get("user_hash_buckets", 4096)),
            relation_neighbor_count=int(config.get("relation_neighbor_count", _event_adapter.DEFAULT_RELATION_NEIGHBORS)),
            hyperedge_count=int(config.get("hyperedge_count", _event_adapter.DEFAULT_HYPEREDGE_COUNT)),
            relation_neighbors=checkpoint.get("relation_neighbors") or {},
            train_user_buckets=checkpoint.get("train_user_buckets") or [],
            observation_ratio=requested_ratio,
            prefix_is_preselected=prefix_is_preselected,
        )
        if bundle["status"] != "ok":
            return _contract.empty_prediction("data_insufficient", bundle["note"], checkpoint_path)

        trend_steps = int(config.get("trend_steps", _event_adapter.DEFAULT_TREND_STEPS))
        model = _sequence_model.make_sequence_joint_model(
            torch,
            nn,
            int(config.get("user_hash_buckets", 4096)),
            int(config.get("hidden_dim", 64)),
            trend_steps,
            int(config.get("hyperedge_count", _event_adapter.DEFAULT_HYPEREDGE_COUNT)),
        ).to(target_device)
        model.load_state_dict(checkpoint["state_dict"])
        model.eval()
        with torch.no_grad():
            final_log, trend_log, decoder_state, _shared, _macro, _micro = model(
                torch.from_numpy(bundle["seq_user_ids"]).to(target_device),
                torch.from_numpy(bundle["seq_time_features"]).to(target_device),
                torch.from_numpy(bundle["relation_neighbor_ids"]).to(target_device),
                torch.from_numpy(bundle["hyperedge_user_ids"]).to(target_device),
                torch.from_numpy(bundle["observed_counts"]).to(target_device),
                torch.from_numpy(bundle["obs_ratios"]).to(target_device),
            )
            candidate_buckets = bundle["candidate_buckets"]
            candidate_tensor = torch.tensor(candidate_buckets, dtype=torch.long, device=target_device)
            logits = torch.mv(model.user_embedding(candidate_tensor), decoder_state.squeeze(0))
            probabilities = torch.softmax(logits, dim=0).cpu().numpy().astype(float)
            predicted_size = max(float(torch.expm1(final_log).cpu().item()), float(bundle["observed_counts"][0]))
            trend_values = np.maximum.accumulate(torch.expm1(trend_log).cpu().numpy()[0]).tolist()
    except Exception as exc:
        return _contract.empty_prediction(
            "model_error",
            f"Checkpoint inference failed: {type(exc).__name__}: {exc}",
            checkpoint_path,
        )

    identity_mapping = _contract.map_bucket_probabilities_to_unique_users(
        candidate_buckets,
        probabilities,
        bundle["bucket_to_users"],
    )
    user_scores = identity_mapping["user_scores"]
    mapped_bucket_count = identity_mapping["mapped_bucket_count"]
    mapped_probability_mass = identity_mapping["mapped_probability_mass"]

    top_users = []
    for rank, (author_id, score) in enumerate(
        sorted(user_scores.items(), key=lambda item: item[1], reverse=True)[: max(1, int(top_k))],
        start=1,
    ):
        meta = bundle["candidate_meta"][author_id]
        bucket_collision_size = len(bundle["bucket_to_users"].get(int(meta["bucket"]), []))
        top_users.append(
            {
                "rank": rank,
                "author_id": author_id,
                "author_name": meta["author_name"],
                "score": round(float(score), 8),
                "candidate_source": "observed_user_hash_bucket_proxy",
                "activation_type": "reactivation",
                "identity_resolution": (
                    "unique_current_event_bucket_proxy"
                    if bucket_collision_size == 1
                    else "ambiguous_current_event_bucket_proxy"
                ),
                "score_semantics": "bucket_probability_shared_across_observed_bucket_members",
                "bucket_collision_size": bucket_collision_size,
                "event_count": int(meta["event_count"]),
                "first_seen_at": meta["first_seen_at"],
                "last_seen_at": meta["last_seen_at"],
                "evidence_refs": meta["evidence_refs"],
                "trace_available": True,
            }
        )

    observed_size = int(bundle["observed_counts"][0])
    predicted_direction = "rising" if predicted_size >= observed_size * 1.05 else "stable"
    return {
        "status": "ok",
        "model_status": "available",
        "adapter_boundary": _contract.ADAPTER_BOUNDARY,
        "checkpoint_path": str(checkpoint_path),
        "macro": {
            "observed_size": observed_size,
            "predicted_size": int(round(predicted_size)),
            "trend_points": _contract.trend_points(trend_values),
            "intervals": None,
            "direction": predicted_direction,
            "score_concentration": _contract.score_concentration(list(user_scores.values())),
            "calibration_status": "unavailable",
        },
        "micro": {
            "top_users": top_users,
            "candidate_count": len(bundle["candidate_meta"]),
            "candidate_bucket_count": len(candidate_buckets),
            "candidate_source_counts": bundle["candidate_source_counts"],
            "reactivation_count": len(top_users),
            "new_activation_count": 0,
            "coverage": {
                "mapped_candidate_buckets": mapped_bucket_count,
                "unmapped_candidate_buckets": len(candidate_buckets) - mapped_bucket_count,
                "legal_candidate_buckets": len(candidate_buckets),
                "mapped_probability_mass": round(mapped_probability_mass, 8),
                "new_activation_status": "abstain_no_identity_mapping",
                "identity_mapping_status": "unique_current_event_bucket_proxy_only",
                "ambiguous_mapped_buckets": identity_mapping["ambiguous_mapped_buckets"],
                "excluded_ambiguous_users": identity_mapping["excluded_ambiguous_users"],
                "unique_identity_probability_mass": round(identity_mapping["unique_identity_probability_mass"], 8),
            },
        },
        "model": {
            "name": "PropagationSequenceJointModel",
            "checkpoint": str(checkpoint_path),
            "dataset": str(checkpoint.get("dataset") or "twitter"),
            "methodology": checkpoint.get("methodology") or "Sequence joint macro/micro propagation model.",
            "scope": "current_event",
        },
        "inference_scope": {
            "loaded_event_count": int(bundle["loaded_event_count"]),
            "observed_event_count": int(bundle["observed_event_count"]),
            "observed_until": bundle["latest_timestamp"].isoformat(),
            "observation_ratio": float(bundle["observed_event_count"]) / float(bundle["loaded_event_count"]),
            "actual_observation_ratio": float(bundle["observed_event_count"]) / float(bundle["loaded_event_count"]),
            "checkpoint_conditioning_ratio": float(bundle["obs_ratios"][0]),
            "prefix_is_preselected": bool(bundle["prefix_is_preselected"]),
        },
    }


__all__ = [
    "predict_event_with_checkpoint",
]
