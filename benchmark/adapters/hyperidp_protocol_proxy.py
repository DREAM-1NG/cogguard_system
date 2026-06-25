#!/usr/bin/env python3
"""
Protocol-level HyperIDP proxy for unified macro/micro diffusion prediction.

This is not the HyperIDP architecture. It is a lightweight, leak-checked adapter
that mirrors the paper's multi-scale evaluation surface: one early-observation
model predicts final cascade size, and one prospective ranker predicts future
users. Temporal hypergraph structure is approximated with train-set coactivation
statistics over time buckets.
"""
import argparse
import json
import math
import os
import random
from collections import Counter, defaultdict
from itertools import combinations
from typing import Dict, Iterable, List, Sequence, Tuple

import numpy as np
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler


K_LIST = (10, 50, 100)


def parse_cascade(line: str) -> List[Tuple[int, int]]:
    cascade: List[Tuple[int, int]] = []
    for raw in line.strip().split():
        parts = raw.split(",")
        if len(parts) != 2:
            continue
        try:
            cascade.append((int(parts[0]), int(parts[1])))
        except ValueError:
            continue
    return sorted(cascade, key=lambda item: item[1])


def load_cascades(path: str) -> List[List[Tuple[int, int]]]:
    cascades: List[List[Tuple[int, int]]] = []
    with open(path, "r", encoding="utf-8", errors="ignore") as handle:
        for line in handle:
            cascade = parse_cascade(line)
            if len(cascade) >= 4:
                cascades.append(cascade)
    return cascades


def load_neighbors(path: str) -> Dict[int, set]:
    neighbors: Dict[int, set] = defaultdict(set)
    if not os.path.exists(path):
        return neighbors
    with open(path, "r", encoding="utf-8", errors="ignore") as handle:
        for line in handle:
            parts = line.strip().replace(",", " ").split()
            if len(parts) < 2:
                continue
            try:
                src, dst = int(parts[0]), int(parts[1])
            except ValueError:
                continue
            neighbors[src].add(dst)
            neighbors[dst].add(src)
    return neighbors


def unique_preserving_order(values: Iterable[int]) -> List[int]:
    seen = set()
    result = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


def train_statistics(
    cascades: Sequence[List[Tuple[int, int]]],
    bucket_seconds: int,
    max_bucket_users: int,
) -> Tuple[Counter, Dict[int, Counter], Dict[int, Counter]]:
    popularity = Counter()
    transitions: Dict[int, Counter] = defaultdict(Counter)
    hyper_neighbors: Dict[int, Counter] = defaultdict(Counter)

    for cascade in cascades:
        users = [user for user, _ in cascade]
        times = [ts for _, ts in cascade]
        popularity.update(users)
        for parent, child in zip(users, users[1:]):
            if parent != child:
                transitions[parent][child] += 1

        buckets: Dict[int, List[int]] = defaultdict(list)
        start = times[0]
        for user, ts in cascade:
            bucket = int((ts - start) // max(bucket_seconds, 1))
            buckets[bucket].append(user)

        for bucket_users in buckets.values():
            unique_users = unique_preserving_order(bucket_users)[:max_bucket_users]
            for src, dst in combinations(unique_users, 2):
                if src == dst:
                    continue
                hyper_neighbors[src][dst] += 1
                hyper_neighbors[dst][src] += 1

    return popularity, transitions, hyper_neighbors


def prefix_split(cascade: List[Tuple[int, int]], obs_ratio: float) -> Tuple[List[int], List[int], List[int]]:
    users = [user for user, _ in cascade]
    times = [ts for _, ts in cascade]
    cut = max(2, int(len(users) * obs_ratio))
    cut = min(cut, len(users))
    return users[:cut], times[:cut], users[cut:]


def prefix_features(
    observed_users: Sequence[int],
    observed_times: Sequence[int],
    popularity: Counter,
    transitions: Dict[int, Counter],
    hyper_neighbors: Dict[int, Counter],
    social_neighbors: Dict[int, set],
) -> List[float]:
    unique_users = unique_preserving_order(observed_users)
    duration = max(observed_times[-1] - observed_times[0], 0) if len(observed_times) >= 2 else 0
    gaps = [b - a for a, b in zip(observed_times, observed_times[1:]) if b >= a]
    avg_gap = float(sum(gaps) / len(gaps)) if gaps else 0.0
    log_pop = [math.log1p(popularity.get(user, 0)) for user in unique_users]

    transition_strength = 0.0
    for parent, child in zip(observed_users, observed_users[1:]):
        transition_strength += math.log1p(transitions.get(parent, {}).get(child, 0))

    hyper_internal = 0.0
    social_internal = 0
    for src, dst in combinations(unique_users[:80], 2):
        hyper_internal += math.log1p(hyper_neighbors.get(src, {}).get(dst, 0))
        if dst in social_neighbors.get(src, ()):
            social_internal += 1

    return [
        math.log1p(len(observed_users)),
        math.log1p(len(unique_users)),
        math.log1p(duration),
        math.log1p(avg_gap),
        math.log1p(len(observed_users) / max(duration, 1)),
        float(sum(log_pop)),
        float(max(log_pop) if log_pop else 0.0),
        transition_strength,
        hyper_internal,
        math.log1p(social_internal),
    ]


def fit_macro_model(
    cascades: Sequence[List[Tuple[int, int]]],
    popularity: Counter,
    transitions: Dict[int, Counter],
    hyper_neighbors: Dict[int, Counter],
    social_neighbors: Dict[int, set],
    obs_ratio: float,
    seed: int,
):
    X: List[List[float]] = []
    y: List[int] = []
    for cascade in cascades:
        observed_users, observed_times, future_users = prefix_split(cascade, obs_ratio)
        if not future_users:
            continue
        X.append(prefix_features(observed_users, observed_times, popularity, transitions, hyper_neighbors, social_neighbors))
        y.append(len(cascade))
    model = RandomForestRegressor(
        n_estimators=120,
        max_depth=14,
        min_samples_leaf=2,
        random_state=seed,
        n_jobs=-1,
    )
    model.fit(np.asarray(X, dtype=float), np.asarray(y, dtype=float))
    return model


def candidate_rows(
    observed_users: Sequence[int],
    popularity: Counter,
    transitions: Dict[int, Counter],
    hyper_neighbors: Dict[int, Counter],
    social_neighbors: Dict[int, set],
    global_candidates: Sequence[int],
    max_candidates: int,
) -> List[Tuple[int, float, float, float, float]]:
    observed_set = set(observed_users)
    candidate_set = set(global_candidates)
    transition_counts = Counter()
    hyper_counts = Counter()
    social_counts = Counter()

    for recency_rank, user in enumerate(reversed(observed_users)):
        recency_weight = 1.0 / (recency_rank + 1)
        for nxt, count in transitions.get(user, {}).items():
            if nxt not in observed_set:
                candidate_set.add(nxt)
                transition_counts[nxt] += count * recency_weight
        for nxt, count in hyper_neighbors.get(user, {}).items():
            if nxt not in observed_set:
                candidate_set.add(nxt)
                hyper_counts[nxt] += count * recency_weight
        for nxt in social_neighbors.get(user, ()):
            if nxt not in observed_set:
                candidate_set.add(nxt)
                social_counts[nxt] += recency_weight

    candidate_set.difference_update(observed_set)
    scored = []
    for candidate in candidate_set:
        pop_score = math.log1p(popularity.get(candidate, 0))
        transition_score = math.log1p(transition_counts.get(candidate, 0.0))
        hyper_score = math.log1p(hyper_counts.get(candidate, 0.0))
        social_score = math.log1p(social_counts.get(candidate, 0.0))
        heuristic = pop_score + 3.0 * transition_score + 2.5 * hyper_score + 1.5 * social_score
        scored.append((heuristic, pop_score, transition_score, hyper_score, social_score, candidate))

    scored.sort(reverse=True)
    return [
        (candidate, pop, transition, hyper, social)
        for _, pop, transition, hyper, social, candidate in scored[:max_candidates]
    ]


def micro_feature_row(
    candidate: int,
    pop_score: float,
    transition_score: float,
    hyper_score: float,
    social_score: float,
    observed_users: Sequence[int],
    observed_times: Sequence[int],
    popularity: Counter,
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


def build_micro_training_data(
    cascades: Sequence[List[Tuple[int, int]]],
    popularity: Counter,
    transitions: Dict[int, Counter],
    hyper_neighbors: Dict[int, Counter],
    social_neighbors: Dict[int, set],
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
        observed_users, observed_times, future_tail = prefix_split(cascade, obs_ratio)
        if not future_tail:
            continue
        observed_users = unique_preserving_order(observed_users)
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
        positives = [row for row in candidates if row[0] in future_users]
        negatives = [row for row in candidates if row[0] not in future_users]
        if not positives:
            continue
        if len(negatives) > negatives_per_cascade:
            negatives = rng.sample(negatives, negatives_per_cascade)

        for candidate, pop, transition, hyper, social in positives + negatives:
            X.append(
                micro_feature_row(
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
            y.append(1 if candidate in future_users else 0)
        cascades_used += 1
        positives_seen += len(positives)

    return (
        np.asarray(X, dtype=float),
        np.asarray(y, dtype=int),
        {"train_cascades_used": cascades_used, "train_positive_candidates": positives_seen},
    )


def msle(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    pred = y_pred.copy()
    pred[pred < 1] = 1
    return float(np.mean(np.square(np.log2(pred) - np.log2(y_true))))


def mae(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    return float(np.mean(np.abs(y_pred - y_true)))


def average_precision_at_k(labels: np.ndarray, relevant_count: int) -> float:
    relevant_seen = 0
    precision_sum = 0.0
    for idx, label in enumerate(labels, start=1):
        if label == 1:
            relevant_seen += 1
            precision_sum += relevant_seen / idx
    return float(precision_sum / max(relevant_count, 1))


def ndcg_at_k(labels: np.ndarray, relevant_count: int) -> float:
    dcg = 0.0
    for idx, label in enumerate(labels, start=1):
        if label == 1:
            dcg += 1.0 / math.log2(idx + 1)
    ideal_hits = min(relevant_count, len(labels))
    idcg = sum(1.0 / math.log2(idx + 1) for idx in range(1, ideal_hits + 1))
    return float(dcg / idcg) if idcg else 0.0


def evaluate(
    macro_model,
    micro_model,
    test_cascades: Sequence[List[Tuple[int, int]]],
    popularity: Counter,
    transitions: Dict[int, Counter],
    hyper_neighbors: Dict[int, Counter],
    social_neighbors: Dict[int, set],
    obs_ratio: float,
    max_future_per_cascade: int,
    global_top_n: int,
    max_candidates: int,
) -> Dict:
    global_candidates = [user for user, _ in popularity.most_common(global_top_n)]
    y_true_size: List[float] = []
    y_pred_size: List[float] = []
    total_relevant = 0
    total_covered = 0
    event_count = 0
    hit_sums = {k: 0.0 for k in K_LIST}
    ap_sums = {k: 0.0 for k in K_LIST}
    ndcg_sums = {k: 0.0 for k in K_LIST}
    reciprocal_rank_sum = 0.0

    for cascade in test_cascades:
        observed_users_raw, observed_times, future_tail = prefix_split(cascade, obs_ratio)
        if not future_tail:
            continue
        y_true_size.append(float(len(cascade)))
        macro_features = prefix_features(
            observed_users_raw,
            observed_times,
            popularity,
            transitions,
            hyper_neighbors,
            social_neighbors,
        )
        pred_size = float(macro_model.predict(np.asarray([macro_features], dtype=float))[0])
        y_pred_size.append(max(pred_size, float(len(observed_users_raw))))

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

        X = np.asarray(
            [
                micro_feature_row(
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
                for candidate, pop, transition, hyper, social in candidates
            ],
            dtype=float,
        )
        probabilities = micro_model.predict_proba(X)[:, 1]
        ranked = [candidates[idx][0] for idx in np.argsort(-probabilities)]
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
    result = {
        "model": "HyperIDPProtocolProxy",
        "mode": "protocol_level_temporal_hypergraph_proxy",
        "obs_ratio": obs_ratio,
        "events_test": event_count,
        "relevant_users_test": total_relevant,
        "candidate_recall_full": total_covered / max(total_relevant, 1),
        "msle": msle(y_true, y_pred),
        "mae": mae(y_true, y_pred),
        "auc": None,
        "average_precision": None,
        "mrr": reciprocal_rank_sum / max(event_count, 1),
        "note": "Not HyperIDP architecture; uses train-set temporal coactivation hyperedges to run the same macro/micro protocol without future-user injection.",
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
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

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

    macro_model = fit_macro_model(
        train_cascades,
        popularity,
        transitions,
        hyper_neighbors,
        social_neighbors,
        args.obs_ratio,
        args.seed,
    )
    X_train, y_train, train_meta = build_micro_training_data(
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
    if len(set(y_train.tolist())) < 2:
        print("[HyperIDPProtocolProxy] ERROR: not enough positive/negative samples")
        return

    micro_model = make_pipeline(
        StandardScaler(),
        LogisticRegression(max_iter=1000, class_weight="balanced"),
    )
    micro_model.fit(X_train, y_train)
    result = evaluate(
        macro_model,
        micro_model,
        test_cascades,
        popularity,
        transitions,
        hyper_neighbors,
        social_neighbors,
        args.obs_ratio,
        args.max_future_per_cascade,
        args.global_top_n,
        args.max_candidates,
    )
    result.update(train_meta)
    result["dataset"] = os.path.basename(args.data_dir)
    result["train_samples"] = int(len(X_train))
    result["positive_rate"] = float(np.mean(y_train))
    result["bucket_seconds"] = args.bucket_seconds
    print(
        "[HyperIDPProtocolProxy] "
        f"MSLE={result['msle']:.4f} "
        f"Coverage={result['candidate_recall_full']:.4f} "
        f"Hits@100={result['hits@100']:.4f}"
    )
    print(json.dumps(result))


if __name__ == "__main__":
    main()
