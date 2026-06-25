#!/usr/bin/env python3
"""
Adversarial protocol-level proxy for HyperIDP-style multi-scale prediction.

This adapter is intentionally scoped as a reproduction proxy, not the HyperIDP
paper architecture. It adds a trainable shared encoder, macro/micro heads, and a
gradient-reversal task discriminator on top of the same leak-checked candidate
protocol used by HyperIDPProtocolProxy.
"""
import argparse
import json
import math
import os
import random
import sys
from pathlib import Path
from typing import Dict, List, Sequence, Tuple

import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import DataLoader, TensorDataset

sys.path.insert(0, str(Path(__file__).resolve().parent))
from hyperidp_protocol_proxy import (  # noqa: E402
    K_LIST,
    average_precision_at_k,
    candidate_rows,
    load_cascades,
    load_neighbors,
    msle,
    ndcg_at_k,
    prefix_features,
    prefix_split,
    train_statistics,
    unique_preserving_order,
)


def micro_feature_row(
    candidate: int,
    pop_score: float,
    transition_score: float,
    hyper_score: float,
    social_score: float,
    observed_users: Sequence[int],
    observed_times: Sequence[int],
    popularity,
    social_neighbors: Dict[int, set],
) -> List[float]:
    duration = max(observed_times[-1] - observed_times[0], 0) if len(observed_times) >= 2 else 0
    last_user = observed_users[-1]
    return [
        pop_score,
        transition_score,
        hyper_score,
        social_score,
        1.0 if candidate in social_neighbors.get(last_user, ()) else 0.0,
        math.log1p(popularity.get(candidate, 0)),
        math.log1p(len(observed_users)),
        math.log1p(duration),
    ]


class GradientReverse(torch.autograd.Function):
    @staticmethod
    def forward(ctx, x, scale):
        ctx.scale = scale
        return x.view_as(x)

    @staticmethod
    def backward(ctx, grad_output):
        return -ctx.scale * grad_output, None


class MultiTaskAdversarialModel(nn.Module):
    def __init__(self, input_dim: int, hidden_dim: int, adv_weight: float, dropout: float) -> None:
        super().__init__()
        self.adv_weight = adv_weight
        self.encoder = nn.Sequential(
            nn.Linear(input_dim, hidden_dim),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(hidden_dim, hidden_dim),
            nn.ReLU(),
        )
        self.micro_head = nn.Linear(hidden_dim, 1)
        self.macro_head = nn.Linear(hidden_dim, 1)
        self.task_head = nn.Sequential(
            nn.Linear(hidden_dim, hidden_dim // 2),
            nn.ReLU(),
            nn.Linear(hidden_dim // 2, 2),
        )

    def forward(self, x):
        shared = self.encoder(x)
        reversed_shared = GradientReverse.apply(shared, self.adv_weight)
        return (
            self.micro_head(shared).squeeze(-1),
            self.macro_head(shared).squeeze(-1),
            self.task_head(reversed_shared),
        )


def combined_macro_examples(
    cascades,
    popularity,
    transitions,
    hyper_neighbors,
    social_neighbors,
    obs_ratio: float,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    X: List[List[float]] = []
    y: List[float] = []
    observed_counts: List[float] = []
    for cascade in cascades:
        observed_users, observed_times, future_users = prefix_split(cascade, obs_ratio)
        if not future_users:
            continue
        prefix = prefix_features(observed_users, observed_times, popularity, transitions, hyper_neighbors, social_neighbors)
        X.append(prefix + [0.0] * 8)
        y.append(math.log1p(len(cascade)))
        observed_counts.append(float(len(observed_users)))
    return (
        np.asarray(X, dtype=np.float32),
        np.asarray(y, dtype=np.float32),
        np.asarray(observed_counts, dtype=np.float32),
    )


def combined_micro_examples(
    cascades,
    popularity,
    transitions,
    hyper_neighbors,
    social_neighbors,
    obs_ratio: float,
    max_future_per_cascade: int,
    global_top_n: int,
    max_candidates: int,
    negatives_per_cascade: int,
    seed: int,
) -> Tuple[np.ndarray, np.ndarray, Dict]:
    rng = random.Random(seed)
    global_candidates = [user for user, _ in popularity.most_common(global_top_n)]
    X: List[List[float]] = []
    y: List[int] = []
    cascades_used = 0
    positives_seen = 0

    for cascade in cascades:
        observed_users_raw, observed_times, future_tail = prefix_split(cascade, obs_ratio)
        if not future_tail:
            continue
        observed_users = unique_preserving_order(observed_users_raw)
        observed_set = set(observed_users)
        future_users = set(future_tail[:max_future_per_cascade]) - observed_set
        if not future_users:
            continue

        prefix = prefix_features(observed_users_raw, observed_times, popularity, transitions, hyper_neighbors, social_neighbors)
        candidates = candidate_rows(
            observed_users,
            popularity,
            transitions,
            hyper_neighbors,
            social_neighbors,
            global_candidates,
            max_candidates,
        )
        positives = [row for row in candidates if row[0] in future_users]
        negatives = [row for row in candidates if row[0] not in future_users]
        if not positives:
            continue
        if len(negatives) > negatives_per_cascade:
            negatives = rng.sample(negatives, negatives_per_cascade)

        for candidate, pop, transition, hyper, social in positives + negatives:
            candidate_features = micro_feature_row(
                candidate,
                pop,
                transition,
                hyper,
                social,
                observed_users,
                observed_times,
                popularity,
                social_neighbors,
            )
            X.append(prefix + candidate_features)
            y.append(1 if candidate in future_users else 0)
        cascades_used += 1
        positives_seen += len(positives)

    return (
        np.asarray(X, dtype=np.float32),
        np.asarray(y, dtype=np.float32),
        {"train_cascades_used": cascades_used, "train_positive_candidates": positives_seen},
    )


def subsample(X: np.ndarray, y: np.ndarray, limit: int, seed: int) -> Tuple[np.ndarray, np.ndarray]:
    if limit <= 0 or len(X) <= limit:
        return X, y
    rng = np.random.default_rng(seed)
    idx = rng.choice(len(X), size=limit, replace=False)
    return X[idx], y[idx]


def train_model(
    macro_X: np.ndarray,
    macro_y: np.ndarray,
    micro_X: np.ndarray,
    micro_y: np.ndarray,
    args,
    device: torch.device,
) -> MultiTaskAdversarialModel:
    torch.manual_seed(args.seed)
    np.random.seed(args.seed)
    random.seed(args.seed)

    model = MultiTaskAdversarialModel(
        input_dim=macro_X.shape[1],
        hidden_dim=args.hidden_dim,
        adv_weight=args.adv_weight,
        dropout=args.dropout,
    ).to(device)
    x_all = np.vstack([macro_X, micro_X])
    x_mean = x_all.mean(axis=0).astype(np.float32)
    x_std = x_all.std(axis=0).astype(np.float32)
    x_std[x_std < 1e-6] = 1.0
    macro_y_mean = np.float32(macro_y.mean())
    macro_y_std = np.float32(max(macro_y.std(), 1e-6))
    macro_X = ((macro_X - x_mean) / x_std).astype(np.float32)
    micro_X = ((micro_X - x_mean) / x_std).astype(np.float32)
    macro_y = ((macro_y - macro_y_mean) / macro_y_std).astype(np.float32)
    model.register_buffer("x_mean", torch.from_numpy(x_mean).to(device))
    model.register_buffer("x_std", torch.from_numpy(x_std).to(device))
    model.register_buffer("macro_y_mean", torch.tensor(macro_y_mean, device=device))
    model.register_buffer("macro_y_std", torch.tensor(macro_y_std, device=device))
    optimizer = torch.optim.AdamW(model.parameters(), lr=args.lr, weight_decay=args.weight_decay)
    macro_loss_fn = nn.MSELoss()
    positive_rate = float(np.mean(micro_y)) if len(micro_y) else 0.5
    pos_weight = torch.tensor([(1.0 - positive_rate) / max(positive_rate, 1e-6)], device=device)
    micro_loss_fn = nn.BCEWithLogitsLoss(pos_weight=pos_weight)
    task_loss_fn = nn.CrossEntropyLoss()

    macro_ds = TensorDataset(
        torch.from_numpy(macro_X),
        torch.from_numpy(macro_y),
        torch.zeros(len(macro_X), dtype=torch.long),
    )
    micro_ds = TensorDataset(
        torch.from_numpy(micro_X),
        torch.from_numpy(micro_y),
        torch.ones(len(micro_X), dtype=torch.long),
    )
    macro_loader = DataLoader(macro_ds, batch_size=args.batch_size, shuffle=True)
    micro_loader = DataLoader(micro_ds, batch_size=args.batch_size, shuffle=True)

    for _ in range(args.epochs):
        model.train()
        macro_iter = iter(macro_loader)
        micro_iter = iter(micro_loader)
        steps = max(len(macro_loader), len(micro_loader))
        for _step in range(steps):
            optimizer.zero_grad()
            loss = torch.tensor(0.0, device=device)

            try:
                mx, my, mt = next(macro_iter)
            except StopIteration:
                macro_iter = iter(macro_loader)
                mx, my, mt = next(macro_iter)
            mx = mx.to(device)
            my = my.to(device)
            mt = mt.to(device)
            _, pred_macro, pred_task = model(mx)
            loss = loss + args.lambda_macro * macro_loss_fn(pred_macro, my)
            loss = loss + args.lambda_task * task_loss_fn(pred_task, mt)

            try:
                ux, uy, ut = next(micro_iter)
            except StopIteration:
                micro_iter = iter(micro_loader)
                ux, uy, ut = next(micro_iter)
            ux = ux.to(device)
            uy = uy.to(device)
            ut = ut.to(device)
            pred_micro, _, pred_task = model(ux)
            loss = loss + args.lambda_micro * micro_loss_fn(pred_micro, uy)
            loss = loss + args.lambda_task * task_loss_fn(pred_task, ut)

            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), args.max_grad_norm)
            optimizer.step()

    return model


def evaluate(
    model: MultiTaskAdversarialModel,
    test_cascades,
    popularity,
    transitions,
    hyper_neighbors,
    social_neighbors,
    obs_ratio: float,
    max_future_per_cascade: int,
    global_top_n: int,
    max_candidates: int,
    direction_threshold: float,
    device: torch.device,
) -> Dict:
    model.eval()
    global_candidates = [user for user, _ in popularity.most_common(global_top_n)]
    y_true_size: List[float] = []
    y_pred_size: List[float] = []
    observed_counts: List[float] = []
    total_relevant = 0
    total_covered = 0
    event_count = 0
    hit_sums = {k: 0.0 for k in K_LIST}
    ap_sums = {k: 0.0 for k in K_LIST}
    ndcg_sums = {k: 0.0 for k in K_LIST}
    reciprocal_rank_sum = 0.0

    with torch.no_grad():
        for cascade in test_cascades:
            observed_users_raw, observed_times, future_tail = prefix_split(cascade, obs_ratio)
            if not future_tail:
                continue
            prefix = prefix_features(observed_users_raw, observed_times, popularity, transitions, hyper_neighbors, social_neighbors)
            macro_input = torch.tensor([prefix + [0.0] * 8], dtype=torch.float32, device=device)
            macro_input = (macro_input - model.x_mean) / model.x_std
            _, pred_log_size, _ = model(macro_input)
            pred_log_size = pred_log_size * model.macro_y_std + model.macro_y_mean
            pred_size = max(float(torch.expm1(pred_log_size).item()), float(len(observed_users_raw)))
            y_true_size.append(float(len(cascade)))
            y_pred_size.append(pred_size)
            observed_counts.append(float(len(observed_users_raw)))

            observed_users = unique_preserving_order(observed_users_raw)
            observed_set = set(observed_users)
            future_users = set(future_tail[:max_future_per_cascade]) - observed_set
            if not future_users:
                continue
            candidates = candidate_rows(
                observed_users,
                popularity,
                transitions,
                hyper_neighbors,
                social_neighbors,
                global_candidates,
                max_candidates,
            )
            if not candidates:
                continue

            rows = []
            for candidate, pop, transition, hyper, social in candidates:
                rows.append(
                    prefix
                    + micro_feature_row(
                        candidate,
                        pop,
                        transition,
                        hyper,
                        social,
                        observed_users,
                        observed_times,
                        popularity,
                        social_neighbors,
                    )
                )
            micro_input = torch.tensor(rows, dtype=torch.float32, device=device)
            micro_input = (micro_input - model.x_mean) / model.x_std
            pred_micro, _, _ = model(micro_input)
            ranked = [candidates[idx][0] for idx in torch.argsort(pred_micro, descending=True).cpu().numpy()]
            labels = np.asarray([1 if candidate in future_users else 0 for candidate in ranked], dtype=int)

            event_count += 1
            total_relevant += len(future_users)
            total_covered += int(labels.sum())
            relevant_positions = np.flatnonzero(labels == 1)
            if len(relevant_positions):
                reciprocal_rank_sum += 1.0 / float(relevant_positions[0] + 1)
            for k in K_LIST:
                top_k = labels[:k]
                hit_sums[k] += float(top_k.sum() / len(future_users))
                ap_sums[k] += average_precision_at_k(top_k, len(future_users))
                ndcg_sums[k] += ndcg_at_k(top_k, len(future_users))

    y_true = np.asarray(y_true_size, dtype=float)
    y_pred = np.asarray(y_pred_size, dtype=float)
    observed = np.asarray(observed_counts, dtype=float)
    true_growth = y_true >= observed * (1.0 + direction_threshold)
    pred_growth = y_pred >= observed * (1.0 + direction_threshold)
    result = {
        "model": "HyperIDPAdversarialProxy",
        "mode": "protocol_level_adversarial_multitask_proxy",
        "obs_ratio": obs_ratio,
        "events_test": event_count,
        "relevant_users_test": total_relevant,
        "candidate_recall_full": total_covered / max(total_relevant, 1),
        "msle": msle(y_true, y_pred),
        "mae": float(np.mean(np.abs(y_pred - y_true))),
        "direction_accuracy": float(np.mean(true_growth == pred_growth)) if len(y_true) else None,
        "auc": None,
        "average_precision": None,
        "mrr": reciprocal_rank_sum / max(event_count, 1),
        "note": "Not HyperIDP architecture; shared encoder with macro/micro heads and gradient-reversal task adversary over temporal hyperedge proxy features.",
    }
    for k in K_LIST:
        result[f"hits@{k}"] = hit_sums[k] / max(event_count, 1)
        result[f"map@{k}"] = ap_sums[k] / max(event_count, 1)
        result[f"ndcg@{k}"] = ndcg_sums[k] / max(event_count, 1)
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data_dir", required=True)
    parser.add_argument("--obs_ratio", type=float, default=0.3)
    parser.add_argument("--max_future_per_cascade", type=int, default=20)
    parser.add_argument("--global_top_n", type=int, default=3000)
    parser.add_argument("--max_candidates", type=int, default=5000)
    parser.add_argument("--negatives_per_cascade", type=int, default=120)
    parser.add_argument("--bucket_seconds", type=int, default=24 * 3600)
    parser.add_argument("--max_bucket_users", type=int, default=80)
    parser.add_argument("--epochs", type=int, default=5)
    parser.add_argument("--batch_size", type=int, default=4096)
    parser.add_argument("--hidden_dim", type=int, default=64)
    parser.add_argument("--dropout", type=float, default=0.1)
    parser.add_argument("--lr", type=float, default=0.001)
    parser.add_argument("--weight_decay", type=float, default=0.0001)
    parser.add_argument("--lambda_macro", type=float, default=1.0)
    parser.add_argument("--lambda_micro", type=float, default=1.0)
    parser.add_argument("--lambda_task", type=float, default=0.2)
    parser.add_argument("--adv_weight", type=float, default=0.2)
    parser.add_argument("--max_grad_norm", type=float, default=5.0)
    parser.add_argument("--max_train_micro_samples", type=int, default=300000)
    parser.add_argument("--direction_threshold", type=float, default=0.1)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--device", default="cpu", choices=["cpu", "cuda"])
    args = parser.parse_args()

    requested_cuda = args.device == "cuda"
    device = torch.device("cuda" if requested_cuda and torch.cuda.is_available() else "cpu")
    train_path = os.path.join(args.data_dir, "cascade.txt")
    test_path = os.path.join(args.data_dir, "cascadetest.txt")
    edge_path = os.path.join(args.data_dir, "edges.txt")
    train_cascades = load_cascades(train_path)
    test_cascades = load_cascades(test_path)
    social_neighbors = load_neighbors(edge_path)
    popularity, transitions, hyper_neighbors = train_statistics(
        train_cascades,
        args.bucket_seconds,
        args.max_bucket_users,
    )
    macro_X, macro_y, _observed = combined_macro_examples(
        train_cascades,
        popularity,
        transitions,
        hyper_neighbors,
        social_neighbors,
        args.obs_ratio,
    )
    micro_X, micro_y, train_meta = combined_micro_examples(
        train_cascades,
        popularity,
        transitions,
        hyper_neighbors,
        social_neighbors,
        args.obs_ratio,
        args.max_future_per_cascade,
        args.global_top_n,
        args.max_candidates,
        args.negatives_per_cascade,
        args.seed,
    )
    micro_X, micro_y = subsample(micro_X, micro_y, args.max_train_micro_samples, args.seed)
    if len(set(micro_y.tolist())) < 2:
        print("[HyperIDPAdversarialProxy] ERROR: not enough positive/negative samples")
        return

    model = train_model(macro_X, macro_y, micro_X, micro_y, args, device)
    result = evaluate(
        model,
        test_cascades,
        popularity,
        transitions,
        hyper_neighbors,
        social_neighbors,
        args.obs_ratio,
        args.max_future_per_cascade,
        args.global_top_n,
        args.max_candidates,
        args.direction_threshold,
        device,
    )
    result.update(train_meta)
    result["dataset"] = os.path.basename(args.data_dir)
    result["train_macro_samples"] = int(len(macro_X))
    result["train_micro_samples"] = int(len(micro_X))
    result["positive_rate"] = float(np.mean(micro_y))
    result["epochs"] = args.epochs
    result["bucket_seconds"] = args.bucket_seconds
    result["adv_weight"] = args.adv_weight
    result["lambda_task"] = args.lambda_task
    print(
        "[HyperIDPAdversarialProxy] "
        f"MSLE={result['msle']:.4f} "
        f"Coverage={result['candidate_recall_full']:.4f} "
        f"Hits@100={result['hits@100']:.4f}"
    )
    print(json.dumps(result))


if __name__ == "__main__":
    main()
