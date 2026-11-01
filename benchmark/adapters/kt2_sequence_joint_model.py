from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Sequence, Tuple

import numpy as np

from benchmark.adapters.propagation_protocol import (
    UNK_USER_ID,
    TrainingUserVocabulary,
    build_observation_prefix,
    build_training_user_vocabulary,
    encode_prefix,
    fair_protocol_audit,
    gate_fair_protocol,
    load_original_cascade_splits,
)


Cascade = List[Tuple[int, int]]
K_LIST = (10, 50, 100)
DEFAULT_OBS_RATIOS = (0.1, 0.3, 0.5)
DEFAULT_TREND_STEPS = 4
DEFAULT_RELATION_NEIGHBORS = 4
DEFAULT_HYPEREDGE_COUNT = 4
LOSS_WEIGHTS = {
    "final_size": 1.0,
    "trend": 0.5,
    "next_user": 0.5,
    "soft_coupling": 0.05,
    "adversarial": 0.02,
    "diff_orthogonality": 0.01,
}
DEFAULT_MODEL_VARIANT = "ours"
MODEL_VARIANT_SPECS = {
    "ours": {
        "model_name": "Ours",
        "method_family": "MINDS+FOREST+CasFT",
        "implementation": "kt2_sequence_joint_model",
        "loss_weights": LOSS_WEIGHTS,
        "methodology": (
            "MINDS backbone with DynamicCasHGNN/RelationGNN/SharedLSTM, final-size and "
            "continuous trend heads, FOREST-style macro/micro soft coupling, and sampled-softmax "
            "next-user training."
        ),
    },
    "minds_shared_backbone": {
        "model_name": "MINDS",
        "method_family": "MINDS",
        "implementation": "same_protocol_reimplementation",
        "loss_weights": {
            "final_size": 1.0,
            "trend": 0.0,
            "next_user": 0.5,
            "soft_coupling": 0.0,
            "adversarial": 0.02,
            "diff_orthogonality": 0.01,
        },
        "methodology": (
            "Same-protocol MINDS-style trainable baseline: DynamicCasHGNN, RelationGNN, "
            "SharedLSTM, adversarial stage objective, and macro/micro heads. It disables "
            "the KT2-specific FOREST soft coupling and CasFT-style trend supervision so it "
            "can be compared under the same split/window/metric implementation."
        ),
    },
}


def model_variant_spec(variant: str) -> Dict[str, Any]:
    key = str(variant or DEFAULT_MODEL_VARIANT)
    if key not in MODEL_VARIANT_SPECS:
        allowed = ", ".join(sorted(MODEL_VARIANT_SPECS))
        raise ValueError(f"Unknown KT2 sequence model variant: {key}. Allowed variants: {allowed}")
    spec = dict(MODEL_VARIANT_SPECS[key])
    spec["loss_weights"] = dict(spec["loss_weights"])
    return spec


def stable_user_bucket(user_id: int, user_hash_buckets: int) -> int:
    """Legacy compatibility helper; fair training uses the shared vocabulary."""
    if user_hash_buckets <= 3:
        return 2
    return 2 + (abs(int(user_id)) % (int(user_hash_buckets) - 2))


def observation_count(cascade_len: int, obs_ratio: float) -> int:
    if cascade_len <= 1:
        return 0
    return min(max(1, int(math.ceil(cascade_len * float(obs_ratio)))), cascade_len - 1)


def _pad(values: Sequence[float], length: int, pad_value: float = 0.0) -> List[float]:
    row = list(values[:length])
    if len(row) < length:
        row.extend([pad_value] * (length - len(row)))
    return row


def build_relation_neighbors(
    cascades: Sequence[Cascade],
    *,
    user_hash_buckets: int = 4096,
    relation_neighbor_count: int = DEFAULT_RELATION_NEIGHBORS,
    vocabulary: TrainingUserVocabulary | None = None,
) -> Dict[int, List[int]]:
    """Build a train-split transition graph used by the RelationGNN block."""

    transitions: Dict[int, Counter] = defaultdict(Counter)
    for cascade in cascades:
        buckets = [
            vocabulary.encode(user) if vocabulary is not None else stable_user_bucket(user, user_hash_buckets)
            for user, _timestamp in cascade
        ]
        for src, dst in zip(buckets, buckets[1:]):
            if src != dst:
                transitions[src][dst] += 1
    neighbors: Dict[int, List[int]] = {}
    for user, counter in transitions.items():
        ranked = [dst for dst, _count in counter.most_common(relation_neighbor_count)]
        neighbors[user] = [int(value) for value in _pad(ranked, relation_neighbor_count)]
    return neighbors


def _relation_neighbor_matrix(
    observed_buckets: Sequence[int],
    relation_neighbors: Mapping[int, Sequence[int]],
    max_sequence_len: int,
    relation_neighbor_count: int,
) -> List[List[int]]:
    rows: List[List[int]] = []
    for bucket in observed_buckets[:max_sequence_len]:
        rows.append([int(value) for value in _pad(relation_neighbors.get(int(bucket), []), relation_neighbor_count)])
    while len(rows) < max_sequence_len:
        rows.append([0] * relation_neighbor_count)
    return rows


def _hyperedge_matrix(
    observed_buckets: Sequence[int],
    hyperedge_count: int,
    max_sequence_len: int,
) -> List[List[int]]:
    """Represent a prefix as ordered stage hyperedges over observed users."""

    rows: List[List[int]] = []
    if not observed_buckets:
        return [[0] * max_sequence_len for _ in range(hyperedge_count)]
    for stage in range(hyperedge_count):
        start = int(math.floor(stage * len(observed_buckets) / float(hyperedge_count)))
        end = int(math.floor((stage + 1) * len(observed_buckets) / float(hyperedge_count)))
        if stage == hyperedge_count - 1:
            end = len(observed_buckets)
        rows.append([int(value) for value in _pad(observed_buckets[start:end], max_sequence_len)])
    return rows


def _stage_label(obs_ratio: float, hyperedge_count: int) -> int:
    ratio = min(max(float(obs_ratio), 0.0), 1.0)
    return min(max(int(math.ceil(ratio * hyperedge_count)) - 1, 0), hyperedge_count - 1)


def _trend_target(cascade: Cascade, observed_count: int, trend_steps: int) -> List[float]:
    final_count = len(cascade)
    if final_count <= observed_count:
        return [math.log1p(final_count)] * trend_steps
    timestamps = [int(ts) for _user, ts in cascade]
    observed_time = timestamps[observed_count - 1]
    final_time = timestamps[-1]
    values: List[float] = []
    if final_time > observed_time:
        horizon = float(final_time - observed_time)
        for step in range(1, trend_steps + 1):
            checkpoint_time = observed_time + horizon * (step / float(trend_steps))
            count = observed_count
            while count < final_count and timestamps[count] <= checkpoint_time:
                count += 1
            values.append(math.log1p(max(count, observed_count)))
    else:
        future_count = final_count - observed_count
        for step in range(1, trend_steps + 1):
            count = observed_count + int(math.ceil(future_count * step / float(trend_steps)))
            values.append(math.log1p(min(count, final_count)))
    return values


def _relative_time_features(cascade: Cascade, observed_count: int, max_sequence_len: int) -> List[float]:
    observed = cascade[:observed_count]
    if not observed:
        return [0.0] * max_sequence_len
    start = observed[0][1]
    end = observed[-1][1]
    span = max(float(end - start), 1.0)
    return _pad([(ts - start) / span for _user, ts in observed], max_sequence_len)


def _sample_negatives(
    train_user_buckets: Sequence[int],
    excluded: set[int],
    negative_samples: int,
    rng: random.Random,
    user_hash_buckets: int,
) -> List[int]:
    pool = [user for user in train_user_buckets if user not in excluded and user > 1]
    if not pool:
        pool = [1]
    if len(pool) >= negative_samples:
        return rng.sample(pool, negative_samples)
    return [rng.choice(pool) for _ in range(negative_samples)]


def build_sequence_training_examples(
    cascades: Sequence[Cascade],
    *,
    obs_ratios: Sequence[float] = DEFAULT_OBS_RATIOS,
    max_sequence_len: int = 64,
    trend_steps: int = DEFAULT_TREND_STEPS,
    user_hash_buckets: int = 4096,
    relation_neighbor_count: int = DEFAULT_RELATION_NEIGHBORS,
    hyperedge_count: int = DEFAULT_HYPEREDGE_COUNT,
    negative_samples: int = 32,
    relation_neighbors: Mapping[int, Sequence[int]] | None = None,
    user_universe_buckets: Sequence[int] | None = None,
    vocabulary: TrainingUserVocabulary | None = None,
    seed: int = 42,
) -> Dict:
    """Build cascade-window examples for the formal KT2 sequence model.

    Each cascade contributes one training example per observation ratio. Micro
    supervision is the next activated user, not a prefix+candidate feature row.
    """

    rng = random.Random(seed)
    if vocabulary is None and user_universe_buckets is None:
        vocabulary = build_training_user_vocabulary(cascades, max_user_ids=user_hash_buckets)
    if vocabulary is not None:
        train_user_buckets = vocabulary.model_user_ids
    elif user_universe_buckets is None:
        train_user_buckets = sorted(
            {
                stable_user_bucket(user, user_hash_buckets)
                for cascade in cascades
                for user, _timestamp in cascade
            }
        )
    else:
        train_user_buckets = sorted({int(user) for user in user_universe_buckets})
    relation_neighbors = relation_neighbors or build_relation_neighbors(
        cascades,
        user_hash_buckets=user_hash_buckets,
        relation_neighbor_count=relation_neighbor_count,
        vocabulary=vocabulary,
    )
    seq_user_ids: List[List[int]] = []
    seq_time_features: List[List[float]] = []
    relation_neighbor_ids: List[List[List[int]]] = []
    hyperedge_user_ids: List[List[List[int]]] = []
    observed_counts: List[float] = []
    final_counts: List[float] = []
    macro_y: List[float] = []
    trend_y: List[List[float]] = []
    next_user_y: List[int] = []
    negative_user_ids: List[List[int]] = []
    stage_y: List[int] = []
    obs_ratio_rows: List[float] = []
    event_ids: List[int] = []

    for event_idx, cascade in enumerate(cascades):
        if len(cascade) < 3:
            continue
        for obs_ratio in obs_ratios:
            prefix = build_observation_prefix(cascade, obs_ratio)
            obs_count = int(prefix["observed_count"])
            if obs_count <= 0 or obs_count >= len(cascade):
                continue
            observed = prefix["observed"]
            encoded_observed = encode_prefix(observed, vocabulary) if vocabulary is not None else observed
            observed_buckets = [
                int(user) if vocabulary is not None else stable_user_bucket(user, user_hash_buckets)
                for user, _ts in encoded_observed
            ]
            target_raw_user = int(prefix["next_event"][0])
            target_bucket = vocabulary.encode(target_raw_user) if vocabulary is not None else stable_user_bucket(target_raw_user, user_hash_buckets)
            excluded = set(observed_buckets)
            excluded.add(target_bucket)
            seq_user_ids.append(_pad(observed_buckets, max_sequence_len))
            seq_time_features.append(_relative_time_features(cascade, obs_count, max_sequence_len))
            relation_neighbor_ids.append(
                _relation_neighbor_matrix(
                    observed_buckets,
                    relation_neighbors,
                    max_sequence_len,
                    relation_neighbor_count,
                )
            )
            hyperedge_user_ids.append(_hyperedge_matrix(observed_buckets, hyperedge_count, max_sequence_len))
            observed_counts.append(float(obs_count))
            final_counts.append(float(len(cascade)))
            macro_y.append(math.log1p(len(cascade)))
            trend_y.append(_trend_target(cascade, obs_count, trend_steps))
            next_user_y.append(target_bucket)
            negative_user_ids.append(
                _sample_negatives(train_user_buckets, excluded, negative_samples, rng, user_hash_buckets)
            )
            stage_y.append(_stage_label(obs_ratio, hyperedge_count))
            obs_ratio_rows.append(float(obs_ratio))
            event_ids.append(event_idx)

    return {
        "seq_user_ids": np.asarray(seq_user_ids, dtype=np.int64),
        "seq_time_features": np.asarray(seq_time_features, dtype=np.float32),
        "relation_neighbor_ids": np.asarray(relation_neighbor_ids, dtype=np.int64),
        "hyperedge_user_ids": np.asarray(hyperedge_user_ids, dtype=np.int64),
        "observed_counts": np.asarray(observed_counts, dtype=np.float32),
        "final_counts": np.asarray(final_counts, dtype=np.float32),
        "macro_y": np.asarray(macro_y, dtype=np.float32),
        "trend_y": np.asarray(trend_y, dtype=np.float32),
        "next_user_y": np.asarray(next_user_y, dtype=np.int64),
        "negative_user_ids": np.asarray(negative_user_ids, dtype=np.int64),
        "stage_y": np.asarray(stage_y, dtype=np.int64),
        "obs_ratios": np.asarray(obs_ratio_rows, dtype=np.float32),
        "event_ids": np.asarray(event_ids, dtype=np.int64),
        "window_weights": np.asarray(
            [1.0 / float(Counter(event_ids)[event_id]) for event_id in event_ids],
            dtype=np.float32,
        ),
        "train_user_buckets": np.asarray(train_user_buckets, dtype=np.int64),
        "unk_user_id": UNK_USER_ID,
        "training_vocabulary": vocabulary,
        "relation_neighbor_count": int(relation_neighbor_count),
        "hyperedge_count": int(hyperedge_count),
        "window_count": len(macro_y),
        "candidate_features_used_as_model_input": False,
    }


def _safe_torch():
    try:
        import torch
        import torch.nn as nn
        from torch.utils.data import DataLoader, TensorDataset
    except Exception as exc:  # pragma: no cover - environment dependent.
        return None, None, None, None, exc
    return torch, nn, DataLoader, TensorDataset, None


def _average_precision(rank: int | None, k: int) -> float:
    if rank is None or rank > k:
        return 0.0
    return 1.0 / float(rank)


def _ndcg(rank: int | None, k: int) -> float:
    if rank is None or rank > k:
        return 0.0
    return 1.0 / math.log2(float(rank) + 1.0)


def _regression_metrics(y_true: np.ndarray, y_pred: np.ndarray, observed: np.ndarray) -> Dict[str, float]:
    pred = np.maximum(y_pred.astype(float), 1.0)
    true = np.maximum(y_true.astype(float), 1.0)
    return {
        "msle": float(np.mean(np.square(np.log2(pred) - np.log2(true)))),
        "mae": float(np.mean(np.abs(pred - true))),
        "rmse": float(np.sqrt(np.mean(np.square(pred - true)))),
        "mape_percent": float(np.mean(np.abs((true - pred) / np.maximum(true, 1.0))) * 100.0),
        "smape_percent": float(np.mean(2.0 * np.abs(pred - true) / np.maximum(np.abs(true) + np.abs(pred), 1.0)) * 100.0),
        "direction_accuracy": float(np.mean((true >= observed * 1.1) == (pred >= observed * 1.1))),
    }


def _make_model(
    torch,
    nn,
    user_hash_buckets: int,
    hidden_dim: int,
    trend_steps: int,
    hyperedge_count: int = DEFAULT_HYPEREDGE_COUNT,
):
    class GradientReversal(torch.autograd.Function):
        @staticmethod
        def forward(ctx, value, alpha: float):
            ctx.alpha = alpha
            return value.view_as(value)

        @staticmethod
        def backward(ctx, grad_output):
            return -ctx.alpha * grad_output, None

    class RelationGNN(nn.Module):
        def __init__(self, emb_dim: int) -> None:
            super().__init__()
            self.message = nn.Sequential(nn.Linear(emb_dim * 2, hidden_dim), nn.ReLU())

        def forward(self, user_emb, neighbor_emb, seq_users):
            neighbor_state = neighbor_emb.mean(dim=2)
            relation_tokens = self.message(torch.cat([user_emb, neighbor_state], dim=-1))
            return _masked_mean(torch, relation_tokens, seq_users.ne(0), dim=1)

    class DynamicCasHGNN(nn.Module):
        def __init__(self, emb_dim: int) -> None:
            super().__init__()
            self.hyperedge_update = nn.Sequential(nn.Linear(emb_dim, hidden_dim), nn.ReLU())
            self.stage_attention = nn.Linear(hidden_dim, 1)

        def forward(self, hyperedge_emb, hyperedge_users):
            node_mask = hyperedge_users.ne(0)
            edge_state = _masked_mean(torch, hyperedge_emb, node_mask, dim=2)
            edge_state = self.hyperedge_update(edge_state)
            edge_mask = node_mask.any(dim=2)
            attn = self.stage_attention(edge_state).squeeze(-1)
            attn = attn.masked_fill(~edge_mask, -1e9)
            weights = torch.softmax(attn, dim=1).unsqueeze(-1)
            weights = torch.where(edge_mask.unsqueeze(-1), weights, torch.zeros_like(weights))
            denom = weights.sum(dim=1).clamp_min(1e-6)
            return (edge_state * weights).sum(dim=1) / denom

    class EulerTrendDecoder(nn.Module):
        def __init__(self) -> None:
            super().__init__()
            self.dynamics = nn.Sequential(
                nn.Linear(hidden_dim + 2, hidden_dim),
                nn.Tanh(),
                nn.Linear(hidden_dim, hidden_dim),
            )
            self.increment = nn.Linear(hidden_dim, 1)

        def forward(self, macro_repr, observed_log, obs_ratios):
            latent = macro_repr
            current = observed_log
            checkpoints = []
            dt = 1.0 / float(trend_steps)
            for step in range(1, trend_steps + 1):
                t = torch.full((macro_repr.shape[0], 1), step / float(trend_steps), device=macro_repr.device)
                latent = latent + dt * self.dynamics(torch.cat([latent, t, obs_ratios.unsqueeze(-1)], dim=-1))
                delta = torch.nn.functional.softplus(self.increment(latent).squeeze(-1)) * dt
                current = current + delta
                checkpoints.append(current)
            return torch.stack(checkpoints, dim=1)

    class KT2SequenceJointModel(nn.Module):
        def __init__(self) -> None:
            super().__init__()
            emb_dim = max(8, hidden_dim // 2)
            self.user_embedding = nn.Embedding(user_hash_buckets, emb_dim, padding_idx=0)
            self.relation_gnn = RelationGNN(emb_dim)
            self.dynamic_cascade_hgnn = DynamicCasHGNN(emb_dim)
            self.shared_lstm = nn.LSTM(emb_dim + hidden_dim + 1, hidden_dim, batch_first=True)
            self.shared_projection = nn.Sequential(nn.Linear(hidden_dim * 3 + 2, hidden_dim), nn.ReLU())
            self.macro_private = nn.Sequential(nn.Linear(hidden_dim, hidden_dim), nn.ReLU())
            self.micro_private = nn.Sequential(nn.Linear(hidden_dim, hidden_dim), nn.ReLU())
            self.final_growth_head = nn.Linear(hidden_dim, 1)
            self.trend_decoder = EulerTrendDecoder()
            self.user_decoder = nn.Linear(hidden_dim, emb_dim)
            self.stage_adversary = nn.Linear(hidden_dim, hyperedge_count)

        def forward(self, seq_users, seq_times, relation_neighbors, hyperedge_users, observed_counts, obs_ratios):
            emb = self.user_embedding(seq_users)
            relation_emb = self.user_embedding(relation_neighbors)
            relation_context = self.relation_gnn(emb, relation_emb, seq_users)
            relation_tokens = relation_context.unsqueeze(1).expand(-1, seq_users.shape[1], -1)
            seq_input = torch.cat([emb, relation_tokens, seq_times.unsqueeze(-1)], dim=-1)
            _out, (hidden, _cell) = self.shared_lstm(seq_input)
            hyperedge_emb = self.user_embedding(hyperedge_users)
            hypergraph_context = self.dynamic_cascade_hgnn(hyperedge_emb, hyperedge_users)
            shared = self.shared_projection(
                torch.cat(
                    [
                        hidden[-1],
                        relation_context,
                        hypergraph_context,
                        torch.log1p(observed_counts).unsqueeze(-1),
                        obs_ratios.unsqueeze(-1),
                    ],
                    dim=-1,
                )
            )
            macro_repr = self.macro_private(shared)
            micro_repr = self.micro_private(shared)
            observed_log = torch.log1p(observed_counts)
            final_log = observed_log + torch.nn.functional.softplus(self.final_growth_head(macro_repr).squeeze(-1))
            trend_log = self.trend_decoder(macro_repr, observed_log, obs_ratios)
            final_log = torch.maximum(final_log, trend_log[:, -1])
            decoder_state = self.user_decoder(micro_repr)
            return final_log, trend_log, decoder_state, shared, macro_repr, micro_repr

        def adversarial_logits(self, shared, alpha: float = 1.0):
            return self.stage_adversary(GradientReversal.apply(shared, alpha))

    return KT2SequenceJointModel()


def _masked_mean(torch, values, mask, dim: int):
    mask = mask.unsqueeze(-1).to(values.dtype)
    return (values * mask).sum(dim=dim) / mask.sum(dim=dim).clamp_min(1.0)


def _orthogonality_loss(torch, macro_repr, micro_repr):
    macro_norm = macro_repr / macro_repr.norm(dim=1, keepdim=True).clamp_min(1e-6)
    micro_norm = micro_repr / micro_repr.norm(dim=1, keepdim=True).clamp_min(1e-6)
    return torch.square(torch.sum(macro_norm * micro_norm, dim=1)).mean()


def _train_model(bundle: Mapping, args: argparse.Namespace, device):
    torch, nn, DataLoader, TensorDataset, err = _safe_torch()
    if err is not None:
        raise err
    loss_weights = dict(args.loss_weights)

    model = _make_model(
        torch,
        nn,
        args.user_hash_buckets,
        args.hidden_dim,
        args.trend_steps,
        args.hyperedge_count,
    ).to(device)
    dataset = TensorDataset(
        torch.from_numpy(bundle["seq_user_ids"]),
        torch.from_numpy(bundle["seq_time_features"]),
        torch.from_numpy(bundle["relation_neighbor_ids"]),
        torch.from_numpy(bundle["hyperedge_user_ids"]),
        torch.from_numpy(bundle["observed_counts"]),
        torch.from_numpy(bundle["obs_ratios"]),
        torch.from_numpy(bundle["macro_y"]),
        torch.from_numpy(bundle["trend_y"]),
        torch.from_numpy(bundle["next_user_y"]),
        torch.from_numpy(bundle["negative_user_ids"]),
        torch.from_numpy(bundle["stage_y"]),
        torch.from_numpy(bundle["event_ids"]),
        torch.from_numpy(bundle["window_weights"]),
    )
    loader = DataLoader(dataset, batch_size=args.batch_size, shuffle=True)
    optimizer = torch.optim.AdamW(model.parameters(), lr=args.lr, weight_decay=args.weight_decay)
    mse = nn.MSELoss(reduction="none")
    ce = nn.CrossEntropyLoss(reduction="none")
    adversary = nn.CrossEntropyLoss()

    model.train()
    final_losses: List[float] = []
    epoch_losses: List[float] = []
    progress_interval = int(getattr(args, "progress_interval", 0) or 0)
    checkpoint_path = Path(str(getattr(args, "training_checkpoint_path", "") or ""))
    checkpoint_interval = int(getattr(args, "training_checkpoint_interval", 0) or 0)
    start_epoch = 0
    if checkpoint_path and checkpoint_path.is_file():
        try:
            checkpoint = torch.load(checkpoint_path, map_location=device)
            if int(checkpoint.get("epochs", args.epochs)) == int(args.epochs):
                model.load_state_dict(checkpoint["model_state_dict"])
                optimizer.load_state_dict(checkpoint["optimizer_state_dict"])
                start_epoch = int(checkpoint.get("epoch", 0))
                epoch_losses = [float(value) for value in checkpoint.get("epoch_losses", [])]
                final_losses = [float(value) for value in checkpoint.get("batch_losses", [])]
                print(
                    "[KT2SequenceJointModel] "
                    f"variant={args.model_variant} resumed_epoch={start_epoch}/{args.epochs} "
                    f"checkpoint={checkpoint_path}",
                    flush=True,
                )
        except Exception as exc:
            print(
                "[KT2SequenceJointModel] "
                f"variant={args.model_variant} checkpoint_resume_failed={type(exc).__name__}: {exc}",
                flush=True,
            )
            start_epoch = 0
            epoch_losses = []
            final_losses = []
    for _epoch in range(start_epoch, args.epochs):
        batch_losses: List[float] = []
        for (
            seq_users,
            seq_times,
            relation_neighbors,
            hyperedge_users,
            observed,
            obs_ratios,
            macro_y,
            trend_y,
            next_user,
            negatives,
            stage_y,
            event_ids,
            window_weights,
        ) in loader:
            seq_users = seq_users.to(device)
            seq_times = seq_times.to(device)
            relation_neighbors = relation_neighbors.to(device)
            hyperedge_users = hyperedge_users.to(device)
            observed = observed.to(device)
            obs_ratios = obs_ratios.to(device)
            macro_y = macro_y.to(device)
            trend_y = trend_y.to(device)
            next_user = next_user.to(device)
            negatives = negatives.to(device)
            stage_y = stage_y.to(device)
            event_ids = event_ids.to(device)

            final_log, trend_log, decoder_state, shared, macro_repr, micro_repr = model(
                seq_users, seq_times, relation_neighbors, hyperedge_users, observed, obs_ratios
            )
            candidates = torch.cat([next_user.unsqueeze(1), negatives], dim=1)
            candidate_emb = model.user_embedding(candidates)
            logits = torch.sum(candidate_emb * decoder_state.unsqueeze(1), dim=-1)
            labels = torch.zeros(logits.shape[0], dtype=torch.long, device=device)
            micro_loss = _cascade_normalized_loss(torch, ce(logits, labels), event_ids)
            macro_loss = _cascade_normalized_loss(torch, mse(final_log, macro_y), event_ids)
            trend_loss = _cascade_normalized_loss(torch, mse(trend_log, trend_y).mean(dim=1), event_ids)
            macro_growth = torch.expm1(final_log).clamp_min(observed) - observed
            first_step_probability = torch.softmax(logits, dim=1)[:, 0]
            expected_rollout_growth = first_step_probability * float(args.rollout_steps)
            soft_coupling = _cascade_normalized_loss(
                torch,
                mse(torch.log1p(macro_growth.clamp_min(0.0)), torch.log1p(expected_rollout_growth)),
                event_ids,
            )
            adv_loss = adversary(model.adversarial_logits(shared, args.adversary_alpha), stage_y)
            diff_loss = _orthogonality_loss(torch, macro_repr, micro_repr)
            loss = (
                loss_weights["final_size"] * macro_loss
                + loss_weights["trend"] * trend_loss
                + loss_weights["next_user"] * micro_loss
                + loss_weights["soft_coupling"] * soft_coupling
                + loss_weights["adversarial"] * adv_loss
                + loss_weights["diff_orthogonality"] * diff_loss
            )
            optimizer.zero_grad()
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), args.max_grad_norm)
            optimizer.step()
            loss_value = float(loss.detach().cpu())
            final_losses.append(loss_value)
            batch_losses.append(loss_value)
        epoch_loss = float(np.mean(batch_losses)) if batch_losses else float("nan")
        epoch_losses.append(epoch_loss)
        if progress_interval > 0 and ((_epoch + 1) == 1 or (_epoch + 1) % progress_interval == 0 or (_epoch + 1) == args.epochs):
            print(
                "[KT2SequenceJointModel] "
                f"variant={args.model_variant} epoch={_epoch + 1}/{args.epochs} "
                f"loss={epoch_loss:.6f}",
                flush=True,
            )
        if checkpoint_path and checkpoint_interval > 0 and (
            (_epoch + 1) % checkpoint_interval == 0 or (_epoch + 1) == args.epochs
        ):
            checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
            tmp_path = checkpoint_path.with_suffix(checkpoint_path.suffix + ".tmp")
            torch.save(
                {
                    "epoch": int(_epoch + 1),
                    "epochs": int(args.epochs),
                    "model_variant": args.model_variant,
                    "model_state_dict": model.state_dict(),
                    "optimizer_state_dict": optimizer.state_dict(),
                    "epoch_losses": epoch_losses,
                    "batch_losses": final_losses[-1000:],
                },
                tmp_path,
            )
            tmp_path.replace(checkpoint_path)
            if progress_interval > 0:
                print(
                    "[KT2SequenceJointModel] "
                    f"variant={args.model_variant} checkpoint_epoch={_epoch + 1}/{args.epochs} "
                    f"checkpoint={checkpoint_path}",
                    flush=True,
                )

    model.training_summary = {
        "final_epoch_loss": epoch_losses[-1] if epoch_losses else None,
        "epoch_loss_curve": epoch_losses,
        "window_count": int(bundle["window_count"]),
        "model_variant": args.model_variant,
        "loss_weights": dict(loss_weights),
        "loss_normalization": "per-window losses are grouped by cascade event_id, averaged per cascade, then averaged across cascades",
        "training_checkpoint_path": str(checkpoint_path) if checkpoint_path else "",
        "training_checkpoint_interval": checkpoint_interval,
        "backbone_components": [
            "DynamicCasHGNN",
            "RelationGNN",
            "SharedLSTM",
            "EulerTrendDecoder",
        ],
    }
    return model


def _cascade_normalized_loss(torch, values, event_ids):
    losses = []
    for event_id in torch.unique(event_ids):
        mask = event_ids.eq(event_id)
        losses.append(values[mask].mean())
    return torch.stack(losses).mean() if losses else values.mean()


def _evaluate_model(
    model,
    cascades: Sequence[Cascade],
    train_user_buckets: Sequence[int],
    args,
    device,
    *,
    vocabulary: TrainingUserVocabulary | None = None,
) -> Dict:
    torch, _nn, _DataLoader, _TensorDataset, err = _safe_torch()
    if err is not None:
        raise err
    bundle = build_sequence_training_examples(
        cascades,
        obs_ratios=args.obs_ratios,
        max_sequence_len=args.max_sequence_len,
        trend_steps=args.trend_steps,
        user_hash_buckets=args.user_hash_buckets,
        relation_neighbor_count=args.relation_neighbor_count,
        hyperedge_count=args.hyperedge_count,
        negative_samples=args.negative_samples,
        relation_neighbors=args.relation_neighbors,
        user_universe_buckets=train_user_buckets,
        vocabulary=vocabulary,
        seed=args.seed + 101,
    )
    if bundle["window_count"] == 0:
        return {"status": "missing_data", "note": "No evaluable sequence windows."}

    allowed = sorted({int(user) for user in train_user_buckets if int(user) > UNK_USER_ID})
    if not allowed:
        allowed = list(range(2, min(args.user_hash_buckets, 102)))
    allowed_tensor = torch.tensor(allowed, dtype=torch.long, device=device)

    y_true: List[float] = []
    y_pred: List[float] = []
    observed_values: List[float] = []
    trend_true: List[float] = []
    trend_pred: List[float] = []
    ranks: List[int | None] = []
    macro_growths: List[float] = []
    micro_growths: List[float] = []
    rollout_lengths: List[int] = []
    rollout_unique_users: List[int] = []
    rollout_topk_examples: List[Dict] = []
    covered = 0

    model.eval()
    with torch.no_grad():
        for idx in range(bundle["window_count"]):
            seq_users = torch.from_numpy(bundle["seq_user_ids"][idx : idx + 1]).to(device)
            seq_times = torch.from_numpy(bundle["seq_time_features"][idx : idx + 1]).to(device)
            relation_neighbors = torch.from_numpy(bundle["relation_neighbor_ids"][idx : idx + 1]).to(device)
            hyperedge_users = torch.from_numpy(bundle["hyperedge_user_ids"][idx : idx + 1]).to(device)
            observed = torch.from_numpy(bundle["observed_counts"][idx : idx + 1]).to(device)
            obs_ratio = torch.from_numpy(bundle["obs_ratios"][idx : idx + 1]).to(device)
            final_log, trend_log, decoder_state, _shared, _macro_repr, _micro_repr = model(
                seq_users, seq_times, relation_neighbors, hyperedge_users, observed, obs_ratio
            )
            pred_size = max(float(torch.expm1(final_log).cpu().item()), float(bundle["observed_counts"][idx]))
            true_size = float(bundle["final_counts"][idx])
            y_true.append(true_size)
            y_pred.append(pred_size)
            observed_values.append(float(bundle["observed_counts"][idx]))
            trend_true.extend(np.expm1(bundle["trend_y"][idx]).tolist())
            trend_pred.extend(torch.expm1(trend_log).cpu().numpy()[0].tolist())
            ranked, rollout_scores, rollout_trace = _autoregressive_rollout(
                model,
                allowed,
                allowed_tensor,
                bundle,
                idx,
                args,
                device,
            )
            target = int(bundle["next_user_y"][idx])
            if target != UNK_USER_ID and target in allowed:
                covered += 1
                rank = ranked.index(target) + 1 if target in ranked else None
            else:
                rank = None
            ranks.append(rank)
            macro_growths.append(max(pred_size - float(bundle["observed_counts"][idx]), 0.0))
            micro_growths.append(float(sum(rollout_scores.values())))
            rollout_lengths.append(len(rollout_trace))
            rollout_unique_users.append(len(rollout_scores))
            if len(rollout_topk_examples) < 3:
                rollout_topk_examples.append(
                    {
                        "event_id": int(bundle["event_ids"][idx]),
                        "obs_ratio": float(bundle["obs_ratios"][idx]),
                        "top_users": [
                            {"user_bucket": int(user), "score": float(score)}
                            for user, score in sorted(
                                rollout_scores.items(),
                                key=lambda item: item[1],
                                reverse=True,
                            )[: min(5, len(rollout_scores))]
                        ],
                    }
                )

    y_true_np = np.asarray(y_true, dtype=float)
    y_pred_np = np.asarray(y_pred, dtype=float)
    observed_np = np.asarray(observed_values, dtype=float)
    metrics = _regression_metrics(y_true_np, y_pred_np, observed_np)
    trend_true_np = np.asarray(trend_true, dtype=float)
    trend_pred_np = np.maximum.accumulate(np.asarray(trend_pred, dtype=float))
    metrics.update(
        {
            "trend_mae": float(np.mean(np.abs(trend_pred_np - trend_true_np))),
            "trend_rmse": float(np.sqrt(np.mean(np.square(trend_pred_np - trend_true_np)))),
            "candidate_recall_full": float(covered / max(len(ranks), 1)),
            "mrr": float(np.mean([0.0 if rank is None else 1.0 / float(rank) for rank in ranks])),
            "macro_micro_soft_consistency": _growth_alignment(macro_growths, micro_growths),
            "rollout_step_count_mean": float(np.mean(rollout_lengths)) if rollout_lengths else 0.0,
            "rollout_unique_user_count_mean": float(np.mean(rollout_unique_users)) if rollout_unique_users else 0.0,
            "rollout_topk_examples": rollout_topk_examples,
        }
    )
    for k in K_LIST:
        metrics[f"hits@{k}"] = float(np.mean([1.0 if rank is not None and rank <= k else 0.0 for rank in ranks]))
        metrics[f"map@{k}"] = float(np.mean([_average_precision(rank, k) for rank in ranks]))
        metrics[f"ndcg@{k}"] = float(np.mean([_ndcg(rank, k) for rank in ranks]))
    return metrics


def _autoregressive_rollout(model, allowed: Sequence[int], allowed_tensor, bundle: Mapping, idx: int, args, device):
    torch, _nn, _DataLoader, _TensorDataset, err = _safe_torch()
    if err is not None:
        raise err
    prefix = [int(user) for user in bundle["seq_user_ids"][idx].tolist() if int(user) > 0]
    time_prefix = [float(value) for value in bundle["seq_time_features"][idx].tolist()[: len(prefix)]]
    observed_count = float(bundle["observed_counts"][idx])
    obs_ratio = float(bundle["obs_ratios"][idx])
    rollout_scores: Dict[int, float] = defaultdict(float)
    trace: List[int] = []
    for _step in range(max(1, int(args.rollout_steps))):
        seq_row = np.asarray([_pad(prefix, args.max_sequence_len)], dtype=np.int64)
        time_row = np.asarray([_pad(time_prefix, args.max_sequence_len)], dtype=np.float32)
        relation_row = np.asarray(
            [
                _relation_neighbor_matrix(
                    prefix,
                    args.relation_neighbors,
                    args.max_sequence_len,
                    args.relation_neighbor_count,
                )
            ],
            dtype=np.int64,
        )
        hyperedge_row = np.asarray(
            [_hyperedge_matrix(prefix, args.hyperedge_count, args.max_sequence_len)],
            dtype=np.int64,
        )
        final_log, trend_log, decoder_state, _shared, _macro_repr, _micro_repr = model(
            torch.from_numpy(seq_row).to(device),
            torch.from_numpy(time_row).to(device),
            torch.from_numpy(relation_row).to(device),
            torch.from_numpy(hyperedge_row).to(device),
            torch.tensor([observed_count], dtype=torch.float32, device=device),
            torch.tensor([obs_ratio], dtype=torch.float32, device=device),
        )
        candidate_emb = model.user_embedding(allowed_tensor)
        logits = torch.mv(candidate_emb, decoder_state.squeeze(0))
        seen = set(prefix)
        if seen:
            seen_positions = [pos for pos, user in enumerate(allowed) if user in seen]
            if seen_positions:
                logits[torch.tensor(seen_positions, dtype=torch.long, device=device)] = -1e9
        probabilities = torch.softmax(logits, dim=0)
        top_pos = int(torch.argmax(probabilities).cpu().item())
        top_user = int(allowed[top_pos])
        top_score = float(probabilities[top_pos].cpu().item())
        if top_score <= 0.0:
            break
        rollout_scores[top_user] += top_score
        trace.append(top_user)
        prefix.append(top_user)
        next_time = time_prefix[-1] + 1.0 / float(max(args.rollout_steps, 1)) if time_prefix else 0.0
        time_prefix.append(float(min(next_time, 1.0)))
        observed_count += 1.0
    ranked = [
        user for user, _score in sorted(rollout_scores.items(), key=lambda item: item[1], reverse=True)
    ]
    if len(ranked) < len(allowed):
        ranked.extend([user for user in allowed if user not in set(ranked)])
    return ranked, rollout_scores, trace


def external_user_bucket(user_id: str, user_hash_buckets: int) -> int:
    digest = hashlib.sha1(str(user_id).encode("utf-8", errors="ignore")).hexdigest()
    return stable_user_bucket(int(digest[:16], 16), user_hash_buckets)


def save_kt2_sequence_checkpoint(model, args: argparse.Namespace, bundle: Mapping, checkpoint_path: str | Path, *, dataset: str) -> str:
    torch, _nn, _DataLoader, _TensorDataset, err = _safe_torch()
    if err is not None:
        raise err

    path = Path(checkpoint_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema": "cogguard.kt2.sequence_checkpoint.v1",
        "model": "KT2SequenceJointModel",
        "dataset": dataset,
        "state_dict": model.state_dict(),
        "config": {
            "obs_ratios": list(args.obs_ratios),
            "max_sequence_len": int(args.max_sequence_len),
            "trend_steps": int(args.trend_steps),
            "user_hash_buckets": int(args.user_hash_buckets),
            "relation_neighbor_count": int(args.relation_neighbor_count),
            "hyperedge_count": int(args.hyperedge_count),
            "hidden_dim": int(args.hidden_dim),
            "rollout_steps": int(args.rollout_steps),
            "seed": int(args.seed),
        },
        "relation_neighbors": {
            int(key): [int(value) for value in values]
            for key, values in getattr(args, "relation_neighbors", {}).items()
        },
        "train_user_buckets": [int(value) for value in bundle.get("train_user_buckets", [])],
        "training_summary": getattr(model, "training_summary", {}),
        "methodology": (
            "MINDS-style DynamicCasHGNN + RelationGNN + SharedLSTM with macro trend head "
            "and next-user autoregressive micro head."
        ),
    }
    torch.save(payload, path)
    return str(path)


def predict_event_with_checkpoint(
    checkpoint_path: str | Path,
    posts: Sequence[Mapping[str, Any]],
    comments: Sequence[Mapping[str, Any]] | None = None,
    *,
    top_k: int = 10,
    device: str = "cpu",
) -> Dict[str, Any]:
    path = Path(checkpoint_path)
    if not path.exists():
        return {"status": "missing_checkpoint", "checkpoint": str(path)}

    torch, nn, _DataLoader, _TensorDataset, err = _safe_torch()
    if err is not None:
        return {"status": "missing_dependency", "note": f"PyTorch unavailable: {type(err).__name__}: {err}"}

    target_device = torch.device("cuda" if device == "cuda" and torch.cuda.is_available() else "cpu")
    try:
        checkpoint = torch.load(path, map_location=target_device, weights_only=False)
    except TypeError:  # pragma: no cover - older torch compatibility.
        checkpoint = torch.load(path, map_location=target_device)
    config = checkpoint.get("config") or {}
    args = argparse.Namespace(
        obs_ratios=[float(value) for value in config.get("obs_ratios", DEFAULT_OBS_RATIOS)],
        max_sequence_len=int(config.get("max_sequence_len", 64)),
        trend_steps=int(config.get("trend_steps", DEFAULT_TREND_STEPS)),
        user_hash_buckets=int(config.get("user_hash_buckets", 4096)),
        relation_neighbor_count=int(config.get("relation_neighbor_count", DEFAULT_RELATION_NEIGHBORS)),
        hyperedge_count=int(config.get("hyperedge_count", DEFAULT_HYPEREDGE_COUNT)),
        hidden_dim=int(config.get("hidden_dim", 64)),
        rollout_steps=int(config.get("rollout_steps", 5)),
        seed=int(config.get("seed", 42)),
    )
    args.relation_neighbors = {
        int(key): [int(value) for value in values]
        for key, values in (checkpoint.get("relation_neighbors") or {}).items()
    }

    bundle = build_event_inference_bundle(
        posts,
        comments or [],
        max_sequence_len=args.max_sequence_len,
        user_hash_buckets=args.user_hash_buckets,
        relation_neighbor_count=args.relation_neighbor_count,
        hyperedge_count=args.hyperedge_count,
        relation_neighbors=args.relation_neighbors,
    )
    if bundle["status"] != "ok":
        return bundle

    model = _make_model(
        torch,
        nn,
        args.user_hash_buckets,
        args.hidden_dim,
        args.trend_steps,
        args.hyperedge_count,
    ).to(target_device)
    model.load_state_dict(checkpoint["state_dict"])
    model.eval()

    with torch.no_grad():
        seq_users = torch.from_numpy(bundle["seq_user_ids"]).to(target_device)
        seq_times = torch.from_numpy(bundle["seq_time_features"]).to(target_device)
        relation_neighbors = torch.from_numpy(bundle["relation_neighbor_ids"]).to(target_device)
        hyperedge_users = torch.from_numpy(bundle["hyperedge_user_ids"]).to(target_device)
        observed = torch.from_numpy(bundle["observed_counts"]).to(target_device)
        obs_ratio = torch.from_numpy(bundle["obs_ratios"]).to(target_device)
        final_log, trend_log, decoder_state, _shared, _macro_repr, _micro_repr = model(
            seq_users,
            seq_times,
            relation_neighbors,
            hyperedge_users,
            observed,
            obs_ratio,
        )
        predicted_size = max(float(torch.expm1(final_log).cpu().item()), float(bundle["observed_counts"][0]))
        trend_values = np.maximum.accumulate(torch.expm1(trend_log).cpu().numpy()[0]).tolist()
        candidate_buckets = bundle["candidate_buckets"]
        allowed_tensor = torch.tensor(candidate_buckets, dtype=torch.long, device=target_device)
        candidate_emb = model.user_embedding(allowed_tensor)
        logits = torch.mv(candidate_emb, decoder_state.squeeze(0))
        probabilities = torch.softmax(logits, dim=0).cpu().numpy().astype(float)

    user_scores: dict[str, float] = defaultdict(float)
    for bucket, probability in zip(candidate_buckets, probabilities):
        bucket_users = bundle["bucket_to_users"].get(int(bucket), [])
        if not bucket_users:
            continue
        share = float(probability) / float(len(bucket_users))
        for user in bucket_users:
            user_scores[user["author_id"]] += share

    top_users = []
    candidate_meta = bundle["candidate_meta"]
    for rank, (author_id, score) in enumerate(
        sorted(user_scores.items(), key=lambda item: item[1], reverse=True)[: max(1, int(top_k))],
        start=1,
    ):
        meta = candidate_meta.get(author_id, {"author_id": author_id, "author_name": author_id})
        top_users.append({
            "rank": rank,
            "author_id": author_id,
            "author_name": meta.get("author_name") or author_id,
            "score": float(score),
            "candidate_source": meta.get("candidate_source", "observed_event"),
            "event_count": int(meta.get("event_count", 0) or 0),
            "first_seen_at": meta.get("first_seen_at"),
            "last_seen_at": meta.get("last_seen_at"),
            "source_counts": meta.get("source_counts") or {},
            "evidence_refs": meta.get("evidence_refs") or [],
            "trace_available": True,
        })

    observed_size = float(bundle["observed_counts"][0])
    final_trend = trend_values[-1] if trend_values else predicted_size
    direction = "rising" if final_trend >= observed_size * 1.05 else "declining" if final_trend <= observed_size * 0.95 else "stable"
    confidence_like = _candidate_confidence([row["score"] for row in top_users], len(candidate_meta))
    return {
        "status": "ok",
        "macro": {
            "observed_size": int(observed_size),
            "predicted_size": int(round(predicted_size)),
            "trend_points": [
                {"step": index + 1, "predicted_size": int(round(value))}
                for index, value in enumerate(trend_values)
            ],
            "direction": direction,
            "confidence_like_score": confidence_like,
        },
        "micro": {
            "top_users": top_users,
            "rollout_steps": int(args.rollout_steps),
            "candidate_count": int(len(candidate_meta)),
        },
        "model": {
            "name": "Ours",
            "checkpoint": str(path),
            "dataset": str(checkpoint.get("dataset") or "twitter"),
            "methodology": checkpoint.get("methodology") or "Sequence joint macro/micro propagation model.",
        },
    }


def build_event_inference_bundle(
    posts: Sequence[Mapping[str, Any]],
    comments: Sequence[Mapping[str, Any]],
    *,
    max_sequence_len: int,
    user_hash_buckets: int,
    relation_neighbor_count: int,
    hyperedge_count: int,
    relation_neighbors: Mapping[int, Sequence[int]],
) -> Dict[str, Any]:
    records = _event_records(posts, comments)
    if len(records) < 3:
        return {"status": "data_insufficient", "note": "At least three observed user events are required."}

    cascade = [
        (int(record["user_int"]), int(record["time_value"]))
        for record in records
    ]
    observed_buckets = [
        external_user_bucket(record["author_id"], user_hash_buckets)
        for record in records
    ]
    candidate_meta: dict[str, dict] = {}
    bucket_to_users: dict[int, list[dict]] = defaultdict(list)
    for record in records:
        author_id = str(record["author_id"])
        if not author_id:
            continue
        meta = candidate_meta.setdefault(
            author_id,
            {
                "author_id": author_id,
                "author_name": record.get("author_name") or author_id,
                "candidate_source": record.get("candidate_source", "observed_event"),
                "event_count": 0,
                "first_seen_at": record.get("timestamp"),
                "last_seen_at": record.get("timestamp"),
                "first_time_value": int(record.get("time_value", 0) or 0),
                "last_time_value": int(record.get("time_value", 0) or 0),
                "source_counts": {},
                "evidence_refs": [],
            },
        )
        meta["event_count"] = int(meta.get("event_count", 0)) + 1
        source = str(record.get("candidate_source") or "observed_event")
        source_counts = meta.setdefault("source_counts", {})
        source_counts[source] = int(source_counts.get(source, 0)) + 1
        meta["candidate_source"] = max(source_counts.items(), key=lambda item: item[1])[0]

        time_value = int(record.get("time_value", 0) or 0)
        if time_value < int(meta.get("first_time_value", time_value) or time_value):
            meta["first_time_value"] = time_value
            meta["first_seen_at"] = record.get("timestamp")
        if time_value >= int(meta.get("last_time_value", time_value) or time_value):
            meta["last_time_value"] = time_value
            meta["last_seen_at"] = record.get("timestamp")

        evidence_ref = _candidate_evidence_ref(record)
        if evidence_ref and len(meta["evidence_refs"]) < 5:
            meta["evidence_refs"].append(evidence_ref)
        bucket = external_user_bucket(author_id, user_hash_buckets)
        if not any(item["author_id"] == author_id for item in bucket_to_users[bucket]):
            bucket_to_users[bucket].append(meta)

    if not candidate_meta:
        return {"status": "data_insufficient", "note": "No candidate users can be mapped."}

    observed_count = len(cascade)
    return {
        "status": "ok",
        "seq_user_ids": np.asarray([_pad(observed_buckets, max_sequence_len)], dtype=np.int64),
        "seq_time_features": np.asarray([_relative_time_features(cascade, observed_count, max_sequence_len)], dtype=np.float32),
        "relation_neighbor_ids": np.asarray(
            [_relation_neighbor_matrix(observed_buckets, relation_neighbors, max_sequence_len, relation_neighbor_count)],
            dtype=np.int64,
        ),
        "hyperedge_user_ids": np.asarray([_hyperedge_matrix(observed_buckets, hyperedge_count, max_sequence_len)], dtype=np.int64),
        "observed_counts": np.asarray([float(observed_count)], dtype=np.float32),
        "obs_ratios": np.asarray([1.0], dtype=np.float32),
        "candidate_buckets": sorted(bucket_to_users.keys()),
        "bucket_to_users": dict(bucket_to_users),
        "candidate_meta": candidate_meta,
    }


def _event_records(posts: Sequence[Mapping[str, Any]], comments: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for index, post in enumerate(posts):
        record = _event_record(post, index=index, candidate_source="observed_post")
        if record:
            records.append(record)
    offset = len(records)
    for index, comment in enumerate(comments):
        record = _event_record(comment, index=offset + index, candidate_source="observed_comment")
        if record:
            records.append(record)
    records.sort(key=lambda item: (item["time_value"], item["index"]))
    for order, record in enumerate(records):
        if record["time_value"] <= 0:
            record["time_value"] = order
    return records


def _event_record(record: Mapping[str, Any], *, index: int, candidate_source: str) -> dict[str, Any] | None:
    author_id = str(
        record.get("author_id")
        or record.get("user_id")
        or record.get("account_id")
        or record.get("uid")
        or ""
    ).strip()
    if not author_id:
        return None
    timestamp_value = (
        record.get("timestamp")
        or record.get("created_at")
        or record.get("publish_time")
        or record.get("published_at")
        or record.get("time")
    )
    return {
        "author_id": author_id,
        "author_name": str(
            record.get("author_name")
            or record.get("nickname")
            or record.get("screen_name")
            or record.get("username")
            or record.get("user_name")
            or record.get("account_label")
            or author_id
        ),
        "user_int": int(hashlib.sha1(author_id.encode("utf-8", errors="ignore")).hexdigest()[:16], 16),
        "time_value": _timestamp_value(timestamp_value, fallback=index),
        "timestamp": _timestamp_text(timestamp_value, fallback=index),
        "post_id": str(record.get("post_id") or record.get("comment_id") or record.get("id") or record.get("mid") or ""),
        "content": str(record.get("content") or record.get("text") or record.get("raw_text") or record.get("body") or ""),
        "url": str(record.get("url") or record.get("source_url") or record.get("link") or ""),
        "index": index,
        "candidate_source": candidate_source,
    }


def _candidate_evidence_ref(record: Mapping[str, Any]) -> dict[str, Any]:
    content = str(record.get("content") or "").strip()
    if len(content) > 180:
        content = f"{content[:180]}..."
    return {
        "post_id": str(record.get("post_id") or ""),
        "timestamp": record.get("timestamp"),
        "content": content,
        "url": str(record.get("url") or ""),
        "candidate_source": record.get("candidate_source", "observed_event"),
    }


def _timestamp_text(value: Any, *, fallback: int) -> str:
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(float(value), tz=timezone.utc).isoformat()
    text = str(value or "").strip()
    if text:
        return text
    return str(fallback)


def _timestamp_value(value: Any, *, fallback: int) -> int:
    if isinstance(value, (int, float)):
        return int(value)
    text = str(value or "").strip()
    if not text:
        return int(fallback)
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return int(parsed.timestamp())
    except ValueError:
        return int(fallback)


def _candidate_confidence(scores: Sequence[float], candidate_count: int) -> float:
    if not scores or candidate_count <= 1:
        return 0.0
    total = max(sum(scores), 1e-12)
    probabilities = [max(score / total, 1e-12) for score in scores]
    entropy = -sum(prob * math.log(prob) for prob in probabilities)
    max_entropy = math.log(max(len(probabilities), 2))
    return round(float(max(0.0, min(1.0, 1.0 - entropy / max_entropy))), 4)


def _growth_alignment(macro_growths: Sequence[float], micro_growths: Sequence[float]) -> float:
    scores = []
    for macro, micro in zip(macro_growths, micro_growths):
        denom = max(abs(math.log1p(macro)), abs(math.log1p(micro)), 1e-9)
        scores.append(max(0.0, 1.0 - abs(math.log1p(macro) - math.log1p(micro)) / denom))
    return float(np.mean(scores)) if scores else 0.0


def _missing_row(note: str, dataset: str, seed: int) -> Dict:
    return {
        "model": "KT2SequenceJointModel",
        "dataset": dataset,
        "task": "multi_scale",
        "status": "missing_data",
        "reproduction_level": "kt2_sequence_joint_model_small_run",
        "seed": seed,
        "note": note,
    }


def run_kt2_sequence_joint_model(data_dir: str | Path, **kwargs) -> Dict:
    torch, _nn, _DataLoader, _TensorDataset, err = _safe_torch()
    dataset_name = kwargs.get("dataset") or Path(data_dir).name
    seed = int(kwargs.get("seed", 42))
    if err is not None:
        return _missing_row(f"PyTorch unavailable: {type(err).__name__}: {err}", dataset_name, seed)
    model_variant = str(kwargs.get("model_variant", DEFAULT_MODEL_VARIANT))
    try:
        variant_spec = model_variant_spec(model_variant)
    except ValueError as exc:
        return _missing_row(str(exc), dataset_name, seed)
    model_name = str(kwargs.get("model_name") or variant_spec["model_name"])

    args = argparse.Namespace(
        model_variant=model_variant,
        model_name=model_name,
        loss_weights=dict(variant_spec["loss_weights"]),
        obs_ratios=[float(x) for x in kwargs.get("obs_ratios", DEFAULT_OBS_RATIOS)],
        max_sequence_len=int(kwargs.get("max_sequence_len", 64)),
        trend_steps=int(kwargs.get("trend_steps", DEFAULT_TREND_STEPS)),
        user_hash_buckets=int(kwargs.get("user_hash_buckets", 4096)),
        relation_neighbor_count=int(kwargs.get("relation_neighbor_count", DEFAULT_RELATION_NEIGHBORS)),
        hyperedge_count=int(kwargs.get("hyperedge_count", DEFAULT_HYPEREDGE_COUNT)),
        negative_samples=int(kwargs.get("negative_samples", 32)),
        batch_size=int(kwargs.get("batch_size", 128)),
        hidden_dim=int(kwargs.get("hidden_dim", 64)),
        epochs=int(kwargs.get("epochs", 200)),
        lr=float(kwargs.get("lr", 1e-3)),
        weight_decay=float(kwargs.get("weight_decay", 1e-4)),
        max_grad_norm=float(kwargs.get("max_grad_norm", 5.0)),
        rollout_steps=int(kwargs.get("rollout_steps", 5)),
        adversary_alpha=float(kwargs.get("adversary_alpha", 1.0)),
        progress_interval=int(kwargs.get("progress_interval", 0)),
        training_checkpoint_path=str(kwargs.get("training_checkpoint_path", "") or ""),
        training_checkpoint_interval=int(kwargs.get("training_checkpoint_interval", 0) or 0),
        seed=seed,
    )
    random.seed(args.seed)
    np.random.seed(args.seed)
    torch.manual_seed(args.seed)
    device = torch.device("cuda" if kwargs.get("device") == "cuda" and torch.cuda.is_available() else "cpu")

    splits = load_original_cascade_splits(data_dir)
    train, valid, test = splits["train"], splits["valid"], splits["test"]
    max_train = int(kwargs.get("max_train_cascades", 0) or 0)
    max_test = int(kwargs.get("max_test_cascades", 0) or 0)
    if max_train > 0:
        train = train[:max_train]
    eval_cascades = test or valid
    if max_test > 0:
        eval_cascades = eval_cascades[:max_test]
    if not train or not eval_cascades:
        return _missing_row("FOREST train/test cascades are not available.", dataset_name, args.seed)

    vocabulary = build_training_user_vocabulary(train, max_user_ids=args.user_hash_buckets)
    protocol_audit = fair_protocol_audit(
        vocabulary=vocabulary,
        train_cascades=train,
        valid_cascades=valid,
        test_cascades=test,
    )
    if not gate_fair_protocol(protocol_audit):
        return _missing_row("The shared fair propagation protocol did not pass its split/vocabulary gate.", dataset_name, args.seed)

    bundle = build_sequence_training_examples(
        train,
        obs_ratios=args.obs_ratios,
        max_sequence_len=args.max_sequence_len,
        trend_steps=args.trend_steps,
        user_hash_buckets=args.user_hash_buckets,
        relation_neighbor_count=args.relation_neighbor_count,
        hyperedge_count=args.hyperedge_count,
        negative_samples=args.negative_samples,
        vocabulary=vocabulary,
        seed=args.seed,
    )
    if bundle["window_count"] == 0:
        return _missing_row("No trainable multi-window sequence examples were produced.", dataset_name, args.seed)
    args.relation_neighbors = build_relation_neighbors(
        train,
        user_hash_buckets=args.user_hash_buckets,
        relation_neighbor_count=args.relation_neighbor_count,
        vocabulary=vocabulary,
    )

    model = _train_model(bundle, args, device)
    checkpoint_path = kwargs.get("checkpoint_path")
    saved_checkpoint = None
    if checkpoint_path:
        saved_checkpoint = save_kt2_sequence_checkpoint(model, args, bundle, checkpoint_path, dataset=dataset_name)
    metrics = _evaluate_model(
        model,
        eval_cascades,
        bundle["train_user_buckets"],
        args,
        device,
        vocabulary=vocabulary,
    )
    if metrics.get("status") == "missing_data":
        return _missing_row(str(metrics.get("note")), dataset_name, args.seed)

    result = {
        "model": "KT2SequenceJointModel",
        "model_label": model_name,
        "base_model": "KT2SequenceJointModel",
        "model_variant": model_variant,
        "method_family": variant_spec.get("method_family"),
        "implementation": variant_spec.get("implementation"),
        "dataset": dataset_name,
        "task": "multi_scale",
        "status": "ok",
        "reproduction_level": "kt2_sequence_joint_model_small_run",
        "seed": args.seed,
        "mode": "sequence_joint_macro_micro_training",
        "checkpoint_path": saved_checkpoint,
        "train_windows": int(bundle["window_count"]),
        "train_cascades_used": len(train),
        "eval_cascades_used": len(eval_cascades),
        "training_loss_curve": getattr(model, "training_summary", {}).get("epoch_loss_curve", []),
        "final_epoch_loss": getattr(model, "training_summary", {}).get("final_epoch_loss"),
        "epochs": int(args.epochs),
        "batch_size": int(args.batch_size),
        "hidden_dim": int(args.hidden_dim),
        "max_sequence_len": int(args.max_sequence_len),
        "trend_steps": int(args.trend_steps),
        "negative_samples": int(args.negative_samples),
        "rollout_steps": int(args.rollout_steps),
        "user_hash_buckets": int(args.user_hash_buckets),
        "obs_ratios": list(args.obs_ratios),
        "macro_micro_consistency": metrics["macro_micro_soft_consistency"],
        "rollout_summary": {
            "rollout_steps": int(args.rollout_steps),
            "rollout_step_count_mean": metrics.get("rollout_step_count_mean", 0.0),
            "rollout_unique_user_count_mean": metrics.get("rollout_unique_user_count_mean", 0.0),
            "topk_examples": metrics.get("rollout_topk_examples", []),
        },
        "candidate_protocol_audit": {
            **protocol_audit,
            "candidate_source": "training-only real-user vocabulary; unseen evaluation users map to UNK",
        },
        "training_protocol": {
            "backbone": "MINDS-style trainable DynamicCasHGNN + RelationGNN + SharedLSTM sequence state",
            "backbone_components": getattr(model, "training_summary", {}).get("backbone_components", []),
            "micro_target": "next_user_autoregressive_sampled_softmax",
            "macro_target": "final_size_plus_future_cumulative_trend",
            "obs_ratios": list(args.obs_ratios),
            "candidate_features_used_as_model_input": False,
            "vocabulary": "real user ids from cascade.txt only; validation/test OOV maps to UNK",
            "loss_weights": dict(args.loss_weights),
            "loss_normalization": getattr(model, "training_summary", {}).get("loss_normalization"),
            "rollout": "autoregressive multi-step rollout aggregated into future-window Top-K",
            "trend_decoder": "CasFT-style Euler latent dynamics with positive cumulative increments",
        },
        "methodology": variant_spec.get("methodology"),
        "legacy_boundary": (
            "This formal model replaces the legacy candidate-row KT2JointModel path; "
            "prefix+candidate feature rows are retained only for ablation."
        ),
        "note": variant_spec.get("methodology"),
        "research_migration": {
            "MINDS": "Primary backbone orientation: dynamic cascade hypergraph, social graph, and shared sequence state.",
            "FOREST": "Soft coupling uses expected micro rollout growth as an auxiliary macro trend signal.",
            "CasFT": "Continuous trend head predicts monotonic future cumulative size checkpoints.",
        },
    }
    result.update(metrics)
    return result


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the formal sequence-based KT2 macro/micro joint model.")
    parser.add_argument("--data_dir", required=True)
    parser.add_argument("--dataset", default="")
    parser.add_argument("--model_name", default="")
    parser.add_argument("--model_variant", default=DEFAULT_MODEL_VARIANT, choices=sorted(MODEL_VARIANT_SPECS))
    parser.add_argument("--epochs", type=int, default=200)
    parser.add_argument("--batch_size", type=int, default=128)
    parser.add_argument("--hidden_dim", type=int, default=64)
    parser.add_argument("--obs_ratios", default="0.1,0.3,0.5")
    parser.add_argument("--max_sequence_len", type=int, default=64)
    parser.add_argument("--trend_steps", type=int, default=4)
    parser.add_argument("--negative_samples", type=int, default=32)
    parser.add_argument("--rollout_steps", type=int, default=5)
    parser.add_argument("--adversary_alpha", type=float, default=1.0)
    parser.add_argument("--progress_interval", type=int, default=20)
    parser.add_argument("--max_train_cascades", type=int, default=0)
    parser.add_argument("--max_test_cascades", type=int, default=0)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--device", default="cpu", choices=["cpu", "cuda"])
    parser.add_argument("--checkpoint_path", default="")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    result = run_kt2_sequence_joint_model(
        args.data_dir,
        dataset=args.dataset or Path(args.data_dir).name,
        model_name=args.model_name,
        model_variant=args.model_variant,
        epochs=args.epochs,
        batch_size=args.batch_size,
        hidden_dim=args.hidden_dim,
        obs_ratios=[float(item.strip()) for item in args.obs_ratios.split(",") if item.strip()],
        max_sequence_len=args.max_sequence_len,
        trend_steps=args.trend_steps,
        negative_samples=args.negative_samples,
        rollout_steps=args.rollout_steps,
        adversary_alpha=args.adversary_alpha,
        progress_interval=args.progress_interval,
        max_train_cascades=args.max_train_cascades,
        max_test_cascades=args.max_test_cascades,
        seed=args.seed,
        device=args.device,
        checkpoint_path=args.checkpoint_path,
    )
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result.get("status") == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
