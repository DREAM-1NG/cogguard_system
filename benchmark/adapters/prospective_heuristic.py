#!/usr/bin/env python3
"""
Prospective non-learning baseline for next-user prediction.

The adapter reads FOREST-format cascades. It builds candidates from training
cascade popularity and the static social graph, observes only the early prefix
of each test cascade, and ranks candidate future users without injecting any
future activated node.
"""
import argparse
import json
import math
import os
from collections import Counter, defaultdict
from typing import Dict, Iterable, List, Sequence, Tuple


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
    return result


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


def rank_candidates(
    observed_users: Sequence[int],
    global_candidates: Sequence[int],
    popularity: Counter,
    transitions: Dict[int, Counter],
    neighbors: Dict[int, set],
    max_candidates: int,
) -> List[int]:
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
        score = (
            1.0 * math.log1p(popularity.get(candidate, 0))
            + 2.0 * math.log1p(neighbor_counts.get(candidate, 0.0))
            + 3.0 * math.log1p(transition_counts.get(candidate, 0.0))
        )
        scored.append((score, popularity.get(candidate, 0), -candidate, candidate))

    scored.sort(reverse=True)
    return [candidate for _, _, _, candidate in scored[:max_candidates]]


def evaluate(
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
    hit_counts = {k: 0 for k in K_LIST}
    ap_sums = {k: 0.0 for k in K_LIST}
    ndcg_sums = {k: 0.0 for k in K_LIST}
    reciprocal_rank_sum = 0.0
    covered_full = 0
    total_relevant = 0
    total_candidate_size = 0
    evaluated_events = 0

    for cascade in test_cascades:
        users = [user for user, _ in cascade]
        cut = max(2, int(len(users) * obs_ratio))
        if cut >= len(users):
            continue
        observed_users = unique_preserving_order(users[:cut])
        ranked = rank_candidates(
            observed_users,
            global_candidates,
            popularity,
            transitions,
            neighbors,
            max_candidates,
        )
        if not ranked:
            continue

        observed_set = set(observed_users)
        end = min(len(users), cut + max_future_per_cascade)
        future_users = set(users[cut:end]) - observed_set
        if not future_users:
            continue

        evaluated_events += 1
        total_candidate_size += len(ranked)
        labels = [1 if candidate in future_users else 0 for candidate in ranked]
        total_relevant += len(future_users)
        covered_full += sum(labels)
        relevant_positions = [idx for idx, label in enumerate(labels, start=1) if label == 1]
        if relevant_positions:
            reciprocal_rank_sum += 1.0 / relevant_positions[0]
        for k in K_LIST:
            top_k = labels[:k]
            hit_counts[k] += sum(top_k) / len(future_users)
            ap_sums[k] += average_precision_at_k(top_k, len(future_users))
            ndcg_sums[k] += ndcg_at_k(top_k, len(future_users))

    result = {
        "model": "ProspectiveHeuristic",
        "mode": "prospective_next_user",
        "obs_ratio": obs_ratio,
        "relevant_users_test": total_relevant,
        "events_test": evaluated_events,
        "candidate_recall_full": covered_full / max(total_relevant, 1),
        "avg_candidate_size": total_candidate_size / max(evaluated_events, 1),
        "msle": None,
        "mae": None,
        "auc": None,
        "average_precision": None,
        "mrr": reciprocal_rank_sum / max(evaluated_events, 1),
        "note": "Ranks future users from training popularity, observed-prefix social neighbors, and train transitions only; no future true user injection.",
    }
    for k in K_LIST:
        result[f"hits@{k}"] = hit_counts[k] / max(evaluated_events, 1)
        result[f"map@{k}"] = ap_sums[k] / max(evaluated_events, 1)
        result[f"ndcg@{k}"] = ndcg_sums[k] / max(evaluated_events, 1)
    return result


def average_precision_at_k(labels: List[int], relevant_count: int) -> float:
    relevant_seen = 0
    precision_sum = 0.0
    for idx, label in enumerate(labels, start=1):
        if label == 1:
            relevant_seen += 1
            precision_sum += relevant_seen / idx
    return float(precision_sum / max(relevant_count, 1))


def ndcg_at_k(labels: List[int], relevant_count: int) -> float:
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
    args = parser.parse_args()

    train_path = os.path.join(args.data_dir, "cascade.txt")
    test_path = os.path.join(args.data_dir, "cascadetest.txt")
    edge_path = os.path.join(args.data_dir, "edges.txt")

    train_cascades = load_cascades(train_path)
    test_cascades = load_cascades(test_path)
    popularity, transitions = train_statistics(train_cascades)
    neighbors = load_neighbors(edge_path)

    result = evaluate(
        test_cascades,
        popularity,
        transitions,
        neighbors,
        args.obs_ratio,
        args.max_future_per_cascade,
        args.global_top_n,
        args.max_candidates,
    )
    result["dataset"] = os.path.basename(args.data_dir)
    print(
        "[ProspectiveHeuristic] "
        f"Coverage={result['candidate_recall_full']:.4f} "
        f"Hits@100={result['hits@100']:.4f}"
    )
    print(json.dumps(result))


if __name__ == "__main__":
    main()
