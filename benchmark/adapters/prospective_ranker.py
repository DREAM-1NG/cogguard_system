#!/usr/bin/env python3
"""
Prospective learned ranker for next-user prediction.

This adapter uses FOREST-format cascades. Candidate users are generated from
training-set popularity, training-set transition statistics, and observed-prefix
social neighbors. Future test users are never injected into the candidate set.
"""
import argparse
import json
import math
import os
import random
from collections import Counter, defaultdict
from typing import Dict, Iterable, List, Sequence, Tuple

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler


K_LIST = (10, 50, 100)


def parse_cascade(line: str) -> List[Tuple[int, int]]:
    result: List[Tuple[int, int]] = []
    for raw in line.strip().split():
        parts = raw.split(",")
        if len(parts) != 2:
            continue
        try:
            result.append((int(parts[0]), int(parts[1])))
        except ValueError:
            continue
    return sorted(result, key=lambda item: item[1])


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


def train_statistics(cascades: Sequence[List[Tuple[int, int]]]) -> Tuple[Counter, Dict[int, Counter]]:
    popularity = Counter()
    transitions: Dict[int, Counter] = defaultdict(Counter)
    for cascade in cascades:
        users = [user for user, _ in cascade]
        popularity.update(users)
        for parent, child in zip(users, users[1:]):
            if parent != child:
                transitions[parent][child] += 1
    return popularity, transitions


def unique_preserving_order(values: Iterable[int]) -> List[int]:
    seen = set()
    result = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


def candidate_scores(
    observed_users: Sequence[int],
    global_candidates: Sequence[int],
    popularity: Counter,
    transitions: Dict[int, Counter],
    neighbors: Dict[int, set],
    max_candidates: int,
) -> List[Tuple[int, float, float, float]]:
    observed_set = set(observed_users)
    candidate_set = set(global_candidates)
    neighbor_counts = Counter()
    transition_counts = Counter()

    for recency_rank, user in enumerate(reversed(observed_users)):
        recency_weight = 1.0 / (recency_rank + 1)
        for neighbor in neighbors.get(user, ()):
            if neighbor not in observed_set:
                candidate_set.add(neighbor)
                neighbor_counts[neighbor] += recency_weight
        for nxt, count in transitions.get(user, {}).items():
            if nxt not in observed_set:
                candidate_set.add(nxt)
                transition_counts[nxt] += count * recency_weight

    candidate_set.difference_update(observed_set)
    scored = []
    for candidate in candidate_set:
        popularity_score = math.log1p(popularity.get(candidate, 0))
        neighbor_score = math.log1p(neighbor_counts.get(candidate, 0.0))
        transition_score = math.log1p(transition_counts.get(candidate, 0.0))
        heuristic = popularity_score + 2.0 * neighbor_score + 3.0 * transition_score
        scored.append((heuristic, popularity_score, neighbor_score, transition_score, candidate))
    scored.sort(reverse=True)
    top = scored[:max_candidates]
    return [(candidate, pop, neigh, trans) for _, pop, neigh, trans, candidate in top]


def feature_row(
    candidate: int,
    popularity_score: float,
    neighbor_score: float,
    transition_score: float,
    observed_users: Sequence[int],
    observed_times: Sequence[int],
    popularity: Counter,
    neighbors: Dict[int, set],
) -> List[float]:
    last_user = observed_users[-1]
    duration = max(observed_times[-1] - observed_times[0], 0) if len(observed_times) >= 2 else 0
    return [
        popularity_score,
        neighbor_score,
        transition_score,
        1.0 if candidate in neighbors.get(last_user, ()) else 0.0,
        math.log1p(popularity.get(candidate, 0)),
        math.log1p(len(observed_users)),
        math.log1p(duration),
    ]


def build_training_data(
    cascades: Sequence[List[Tuple[int, int]]],
    popularity: Counter,
    transitions: Dict[int, Counter],
    neighbors: Dict[int, set],
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
        users = [user for user, _ in cascade]
        times = [ts for _, ts in cascade]
        cut = max(2, int(len(users) * obs_ratio))
        if cut >= len(users):
            continue
        observed_users = unique_preserving_order(users[:cut])
        observed_times = times[:cut]
        observed_set = set(observed_users)
        end = min(len(users), cut + max_future_per_cascade)
        future_users = set(users[cut:end]) - observed_set
        if not future_users:
            continue

        candidates = candidate_scores(
            observed_users,
            global_candidates,
            popularity,
            transitions,
            neighbors,
            max_candidates,
        )
        positives = [row for row in candidates if row[0] in future_users]
        negatives = [row for row in candidates if row[0] not in future_users]
        if not positives:
            continue
        if len(negatives) > negatives_per_cascade:
            negatives = rng.sample(negatives, negatives_per_cascade)

        for candidate, pop, neigh, trans in positives + negatives:
            X.append(feature_row(candidate, pop, neigh, trans, observed_users, observed_times, popularity, neighbors))
            y.append(1 if candidate in future_users else 0)
        cascades_used += 1
        positives_seen += len(positives)

    return (
        np.asarray(X, dtype=float),
        np.asarray(y, dtype=int),
        {"train_cascades_used": cascades_used, "train_positive_candidates": positives_seen},
    )


def evaluate(
    model,
    test_cascades: Sequence[List[Tuple[int, int]]],
    popularity: Counter,
    transitions: Dict[int, Counter],
    neighbors: Dict[int, set],
    obs_ratio: float,
    max_future_per_cascade: int,
    global_top_n: int,
    max_candidates: int,
) -> Dict:
    global_candidates = [user for user, _ in popularity.most_common(global_top_n)]
    total_relevant = 0
    total_covered = 0
    event_count = 0
    hit_sums = {k: 0.0 for k in K_LIST}
    ap_sums = {k: 0.0 for k in K_LIST}
    ndcg_sums = {k: 0.0 for k in K_LIST}
    reciprocal_rank_sum = 0.0

    for cascade in test_cascades:
        users = [user for user, _ in cascade]
        times = [ts for _, ts in cascade]
        cut = max(2, int(len(users) * obs_ratio))
        if cut >= len(users):
            continue
        observed_users = unique_preserving_order(users[:cut])
        observed_times = times[:cut]
        observed_set = set(observed_users)
        end = min(len(users), cut + max_future_per_cascade)
        future_users = set(users[cut:end]) - observed_set
        if not future_users:
            continue

        candidates = candidate_scores(
            observed_users,
            global_candidates,
            popularity,
            transitions,
            neighbors,
            max_candidates,
        )
        if not candidates:
            continue
        X = np.asarray(
            [
                feature_row(candidate, pop, neigh, trans, observed_users, observed_times, popularity, neighbors)
                for candidate, pop, neigh, trans in candidates
            ],
            dtype=float,
        )
        probabilities = model.predict_proba(X)[:, 1]
        ranked_candidates = [candidates[idx][0] for idx in np.argsort(-probabilities)]
        labels = np.asarray([1 if candidate in future_users else 0 for candidate in ranked_candidates], dtype=int)

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

    result = {
        "model": "ProspectiveRanker",
        "mode": "prospective_learned_ranker",
        "obs_ratio": obs_ratio,
        "events_test": event_count,
        "relevant_users_test": total_relevant,
        "candidate_recall_full": total_covered / max(total_relevant, 1),
        "mrr": reciprocal_rank_sum / max(event_count, 1),
        "msle": None,
        "mae": None,
        "auc": None,
        "average_precision": None,
        "note": "Logistic ranker trained on observed-prefix candidates; test candidates do not include future-user injection.",
    }
    for k in K_LIST:
        result[f"hits@{k}"] = hit_sums[k] / max(event_count, 1)
        result[f"map@{k}"] = ap_sums[k] / max(event_count, 1)
        result[f"ndcg@{k}"] = ndcg_sums[k] / max(event_count, 1)
    return result


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


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data_dir", required=True)
    parser.add_argument("--obs_ratio", type=float, default=0.3)
    parser.add_argument("--max_future_per_cascade", type=int, default=50)
    parser.add_argument("--global_top_n", type=int, default=5000)
    parser.add_argument("--max_candidates", type=int, default=10000)
    parser.add_argument("--negatives_per_cascade", type=int, default=200)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    train_path = os.path.join(args.data_dir, "cascade.txt")
    test_path = os.path.join(args.data_dir, "cascadetest.txt")
    edge_path = os.path.join(args.data_dir, "edges.txt")
    train_cascades = load_cascades(train_path)
    test_cascades = load_cascades(test_path)
    popularity, transitions = train_statistics(train_cascades)
    neighbors = load_neighbors(edge_path)

    X_train, y_train, train_meta = build_training_data(
        train_cascades,
        popularity,
        transitions,
        neighbors,
        args.obs_ratio,
        args.max_future_per_cascade,
        args.global_top_n,
        args.max_candidates,
        args.negatives_per_cascade,
        args.seed,
    )
    if len(set(y_train.tolist())) < 2:
        print("[ProspectiveRanker] ERROR: not enough positive/negative samples")
        return

    model = make_pipeline(
        StandardScaler(),
        LogisticRegression(max_iter=1000, class_weight="balanced"),
    )
    model.fit(X_train, y_train)
    result = evaluate(
        model,
        test_cascades,
        popularity,
        transitions,
        neighbors,
        args.obs_ratio,
        args.max_future_per_cascade,
        args.global_top_n,
        args.max_candidates,
    )
    result.update(train_meta)
    result["dataset"] = os.path.basename(args.data_dir)
    result["train_samples"] = int(len(X_train))
    result["positive_rate"] = float(np.mean(y_train))
    print(
        "[ProspectiveRanker] "
        f"Coverage={result['candidate_recall_full']:.4f} "
        f"Hits@100={result['hits@100']:.4f} MRR={result['mrr']:.4f}"
    )
    print(json.dumps(result))


if __name__ == "__main__":
    main()
