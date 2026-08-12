"""Fair protocol primitives for propagation comparison experiments.

This module is intentionally model-agnostic: it owns dataset splits, train-only
vocabulary, observation prefixes, metric computation, and audit fields. Model
adapters may only enter the formal tables when they consume this protocol.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Sequence

import numpy as np

Cascade = list[tuple[int, int]]

PAD_USER_ID = 0
EOS_USER_ID = 1
UNK_USER_ID = 2
FIRST_REAL_USER_ID = 3

PROTOCOL_ID = "cogguard.propagation.fair_split_vocab_prefix.v2"
SPLIT_FILENAMES = {
    "train": "cascade.txt",
    "valid": "cascadevalid.txt",
    "test": "cascadetest.txt",
}
DEFAULT_K_LIST = (10, 50, 100)


@dataclass(frozen=True)
class TrainingUserVocabulary:
    """User vocabulary built only from the training cascade split."""

    user_to_id: Mapping[int, int]
    id_to_user: Mapping[int, int]
    overflow_user_count: int = 0

    @property
    def size(self) -> int:
        return max(self.id_to_user.keys(), default=UNK_USER_ID) + 1

    @property
    def train_user_count(self) -> int:
        return len(self.user_to_id)

    @property
    def candidate_ids(self) -> list[int]:
        return sorted(self.id_to_user)

    def encode(self, user_id: int) -> int:
        return int(self.user_to_id.get(int(user_id), UNK_USER_ID))

    def decode(self, vocab_id: int) -> int | None:
        return self.id_to_user.get(int(vocab_id))


@dataclass(frozen=True)
class PrefixWindow:
    """A single cascade prefix used for macro and micro evaluation."""

    split: str
    cascade_index: int
    obs_ratio: float
    observed: Cascade
    observed_user_ids: tuple[int, ...]
    observed_vocab_ids: tuple[int, ...]
    observed_times: tuple[int, ...]
    target_user_id: int | None
    target_vocab_id: int
    target_is_oov: bool
    observed_size: int
    final_size: int
    trend_counts: tuple[float, ...]

    @property
    def future_count(self) -> int:
        return max(0, self.final_size - self.observed_size)


def parse_forest_cascade(line: str) -> Cascade:
    """Parse one FOREST cascade row as ``[(user_id, timestamp_ms), ...]``."""

    cascade: Cascade = []
    for raw_item in line.strip().split():
        parts = raw_item.split(",")
        if len(parts) != 2:
            continue
        try:
            user_id = int(parts[0])
            timestamp_ms = int(float(parts[1]) * 1000)
        except ValueError:
            continue
        cascade.append((user_id, timestamp_ms))
    return sorted(cascade, key=lambda item: item[1])


def load_forest_cascades(path: str | Path, *, min_length: int = 2, limit: int = 0) -> list[Cascade]:
    cascades: list[Cascade] = []
    with Path(path).open("r", encoding="utf-8", errors="ignore") as handle:
        for line in handle:
            cascade = parse_forest_cascade(line)
            if len(cascade) >= min_length:
                cascades.append(cascade)
                if limit and len(cascades) >= limit:
                    break
    return cascades


def load_original_cascade_splits(
    data_dir: str | Path,
    *,
    min_length: int = 2,
    train_limit: int = 0,
    valid_limit: int = 0,
    test_limit: int = 0,
) -> dict[str, list[Cascade]]:
    """Load the dataset's explicit train/validation/test files without re-splitting."""

    root = Path(data_dir)
    limits = {"train": train_limit, "valid": valid_limit, "test": test_limit}
    splits: dict[str, list[Cascade]] = {}
    for split, filename in SPLIT_FILENAMES.items():
        path = root / filename
        splits[split] = (
            load_forest_cascades(path, min_length=min_length, limit=max(0, int(limits[split])))
            if path.exists()
            else []
        )
    return splits


def build_training_user_vocabulary(
    train_cascades: Sequence[Cascade],
    *,
    max_train_users: int = 0,
) -> TrainingUserVocabulary:
    """Build deterministic real-user ids from training data only.

    ``max_train_users=0`` means keep the full training vocabulary. If a cap is
    provided, users are retained by descending training frequency, then raw id.
    Capping is recorded as overflow and is never a hash bucket.
    """

    counts: dict[int, int] = {}
    for cascade in train_cascades:
        for user_id, _timestamp in cascade:
            counts[int(user_id)] = counts.get(int(user_id), 0) + 1
    ordered_users = [user for user, _count in sorted(counts.items(), key=lambda item: (-item[1], item[0]))]
    if max_train_users and max_train_users > 0:
        retained = ordered_users[: int(max_train_users)]
    else:
        retained = ordered_users
    user_to_id = {raw_user: index + FIRST_REAL_USER_ID for index, raw_user in enumerate(retained)}
    id_to_user = {vocab_id: raw_user for raw_user, vocab_id in user_to_id.items()}
    return TrainingUserVocabulary(
        user_to_id=user_to_id,
        id_to_user=id_to_user,
        overflow_user_count=max(0, len(ordered_users) - len(retained)),
    )


def observation_count(cascade_len: int, obs_ratio: float) -> int:
    if cascade_len <= 1:
        return 0
    count = int(math.ceil(cascade_len * float(obs_ratio)))
    return min(max(1, count), cascade_len - 1)


def trend_label_counts(cascade_len: int, observed_count: int, trend_steps: int) -> tuple[float, ...]:
    """Create monotonic future cumulative-count labels from the same cascade only."""

    steps = max(1, int(trend_steps))
    if cascade_len <= observed_count:
        return tuple(float(observed_count) for _ in range(steps))
    labels: list[float] = []
    remaining = cascade_len - observed_count
    for step in range(1, steps + 1):
        labels.append(float(observed_count + math.ceil(remaining * step / steps)))
    return tuple(labels)


def build_prefix_window(
    cascade: Sequence[tuple[int, int]],
    *,
    split: str,
    cascade_index: int,
    obs_ratio: float,
    vocabulary: TrainingUserVocabulary,
    trend_steps: int,
) -> PrefixWindow | None:
    count = observation_count(len(cascade), obs_ratio)
    if count <= 0 or count >= len(cascade):
        return None
    observed = list(cascade[:count])
    target_user = int(cascade[count][0])
    target_vocab = vocabulary.encode(target_user)
    return PrefixWindow(
        split=split,
        cascade_index=int(cascade_index),
        obs_ratio=float(obs_ratio),
        observed=observed,
        observed_user_ids=tuple(int(user_id) for user_id, _timestamp in observed),
        observed_vocab_ids=tuple(vocabulary.encode(user_id) for user_id, _timestamp in observed),
        observed_times=tuple(int(timestamp) for _user_id, timestamp in observed),
        target_user_id=target_user,
        target_vocab_id=target_vocab,
        target_is_oov=target_vocab == UNK_USER_ID,
        observed_size=count,
        final_size=len(cascade),
        trend_counts=trend_label_counts(len(cascade), count, trend_steps),
    )


def build_prefix_windows(
    cascades: Sequence[Cascade],
    *,
    split: str,
    obs_ratios: Sequence[float],
    vocabulary: TrainingUserVocabulary,
    trend_steps: int,
) -> list[PrefixWindow]:
    windows: list[PrefixWindow] = []
    for cascade_index, cascade in enumerate(cascades):
        for obs_ratio in obs_ratios:
            window = build_prefix_window(
                cascade,
                split=split,
                cascade_index=cascade_index,
                obs_ratio=float(obs_ratio),
                vocabulary=vocabulary,
                trend_steps=trend_steps,
            )
            if window is not None:
                windows.append(window)
    return windows


def vocabulary_oov_report(cascades: Sequence[Cascade], vocabulary: TrainingUserVocabulary) -> dict[str, float]:
    total_events = 0
    oov_events = 0
    oov_users: set[int] = set()
    for cascade in cascades:
        for user_id, _timestamp in cascade:
            total_events += 1
            if vocabulary.encode(user_id) == UNK_USER_ID:
                oov_events += 1
                oov_users.add(int(user_id))
    return {
        "total_events": total_events,
        "oov_events": oov_events,
        "oov_event_rate": float(oov_events / total_events) if total_events else 0.0,
        "oov_unique_users": len(oov_users),
    }


def _as_float_array(values: Sequence[float]) -> np.ndarray:
    return np.asarray(list(values), dtype=np.float64)


def msle(y_true: Sequence[float], y_pred: Sequence[float]) -> float:
    true = np.maximum(_as_float_array(y_true), 1.0)
    pred = np.maximum(_as_float_array(y_pred), 1.0)
    return float(np.mean(np.square(np.log1p(pred) - np.log1p(true)))) if len(true) else 0.0


def mae(y_true: Sequence[float], y_pred: Sequence[float]) -> float:
    true = _as_float_array(y_true)
    pred = _as_float_array(y_pred)
    return float(np.mean(np.abs(true - pred))) if len(true) else 0.0


def rmse(y_true: Sequence[float], y_pred: Sequence[float]) -> float:
    true = _as_float_array(y_true)
    pred = _as_float_array(y_pred)
    return float(np.sqrt(np.mean(np.square(true - pred)))) if len(true) else 0.0


def mape(y_true: Sequence[float], y_pred: Sequence[float]) -> float:
    true = _as_float_array(y_true)
    pred = _as_float_array(y_pred)
    return float(np.mean(np.abs((true - pred) / np.maximum(true, 1.0))) * 100.0) if len(true) else 0.0


def smape(y_true: Sequence[float], y_pred: Sequence[float]) -> float:
    true = _as_float_array(y_true)
    pred = _as_float_array(y_pred)
    denominator = np.maximum((np.abs(true) + np.abs(pred)) / 2.0, 1.0)
    return float(np.mean(np.abs(true - pred) / denominator) * 100.0) if len(true) else 0.0


def direction_accuracy(
    y_true: Sequence[float],
    y_pred: Sequence[float],
    observed: Sequence[float],
    *,
    threshold: float = 0.1,
) -> float:
    true = _as_float_array(y_true)
    pred = _as_float_array(y_pred)
    obs = _as_float_array(observed)
    if not len(true):
        return 0.0
    true_growth = true >= obs * (1.0 + threshold)
    pred_growth = pred >= obs * (1.0 + threshold)
    return float(np.mean(true_growth == pred_growth))


def compute_macro_metrics(
    *,
    observed_sizes: Sequence[float],
    final_sizes: Sequence[float],
    predicted_sizes: Sequence[float],
    trend_true: Sequence[Sequence[float]] | None = None,
    trend_pred: Sequence[Sequence[float]] | None = None,
) -> dict[str, float]:
    metrics = {
        "msle": msle(final_sizes, predicted_sizes),
        "mae": mae(final_sizes, predicted_sizes),
        "rmse": rmse(final_sizes, predicted_sizes),
        "mape_percent": mape(final_sizes, predicted_sizes),
        "smape_percent": smape(final_sizes, predicted_sizes),
        "direction_accuracy": direction_accuracy(final_sizes, predicted_sizes, observed_sizes),
    }
    if trend_true is not None and trend_pred is not None and len(trend_true):
        true_flat = np.asarray(trend_true, dtype=np.float64).reshape(-1)
        pred_flat = np.asarray(trend_pred, dtype=np.float64).reshape(-1)
        metrics["trend_mae"] = mae(true_flat, pred_flat)
        metrics["trend_rmse"] = rmse(true_flat, pred_flat)
    else:
        metrics["trend_mae"] = 0.0
        metrics["trend_rmse"] = 0.0
    return metrics


def _average_precision_at_k(labels: np.ndarray, relevant_count: int) -> float:
    precision_sum = 0.0
    relevant_seen = 0
    for index, label in enumerate(labels, start=1):
        if int(label) == 1:
            relevant_seen += 1
            precision_sum += relevant_seen / index
    return float(precision_sum / max(relevant_count, 1))


def _ndcg_at_k(labels: np.ndarray, relevant_count: int) -> float:
    dcg = 0.0
    for index, label in enumerate(labels, start=1):
        if int(label) == 1:
            dcg += 1.0 / math.log2(index + 1)
    ideal_hits = min(relevant_count, len(labels))
    idcg = sum(1.0 / math.log2(index + 1) for index in range(1, ideal_hits + 1))
    return float(dcg / idcg) if idcg else 0.0


def compute_micro_metrics(
    score_rows: Sequence[Mapping[int, float]],
    target_vocab_ids: Sequence[int],
    *,
    candidate_ids: Sequence[int],
    k_list: Sequence[int] = DEFAULT_K_LIST,
) -> dict[str, float]:
    candidate_set = {int(candidate_id) for candidate_id in candidate_ids if int(candidate_id) >= FIRST_REAL_USER_ID}
    requested = len(target_vocab_ids)
    covered_targets = [int(target) in candidate_set for target in target_vocab_ids]
    evaluable_indices = [index for index, covered in enumerate(covered_targets) if covered]
    metrics: dict[str, float] = {
        "candidate_recall": float(len(evaluable_indices) / requested) if requested else 0.0,
        "candidate_recall_full": float(len(evaluable_indices) / requested) if requested else 0.0,
        "target_oov_count": float(requested - len(evaluable_indices)),
        "evaluated_micro_count": float(len(evaluable_indices)),
    }
    for k in k_list:
        metrics[f"hits@{k}"] = 0.0
        metrics[f"map@{k}"] = 0.0
        metrics[f"ndcg@{k}"] = 0.0
    metrics["mrr"] = 0.0
    if not evaluable_indices:
        return metrics

    candidate_order = sorted(candidate_set)
    accum = {key: 0.0 for key in metrics if key.startswith(("hits@", "map@", "ndcg@"))}
    mrr_total = 0.0
    for index in evaluable_indices:
        row = score_rows[index]
        target = int(target_vocab_ids[index])
        ranked = sorted(candidate_order, key=lambda candidate: float(row.get(candidate, -np.inf)), reverse=True)
        labels = np.asarray([1 if candidate == target else 0 for candidate in ranked], dtype=np.int32)
        positions = np.flatnonzero(labels == 1)
        if len(positions):
            mrr_total += 1.0 / float(positions[0] + 1)
        for k in k_list:
            top_k = labels[:k]
            accum[f"hits@{k}"] += float(top_k.sum())
            accum[f"map@{k}"] += _average_precision_at_k(top_k, 1)
            accum[f"ndcg@{k}"] += _ndcg_at_k(top_k, 1)
    denominator = float(len(evaluable_indices))
    for key, value in accum.items():
        metrics[key] = value / denominator
    metrics["mrr"] = mrr_total / denominator
    return metrics


def build_fair_protocol_audit(
    *,
    train_cascades: Sequence[Cascade],
    valid_cascades: Sequence[Cascade],
    test_cascades: Sequence[Cascade],
    vocabulary: TrainingUserVocabulary,
    uses_original_splits: bool,
    uses_train_only_vocabulary: bool,
    uses_hash_buckets: bool,
    uses_proxy_ranking: bool,
    candidate_generation_reads_future_tail: bool,
    future_nodes_injected: bool,
    model_score_source: str,
    social_graph_status: str,
) -> dict[str, object]:
    split_counts = {
        "train": len(train_cascades),
        "valid": len(valid_cascades),
        "test": len(test_cascades),
    }
    audit: dict[str, object] = {
        "protocol_id": PROTOCOL_ID,
        "split_policy": "original cascade.txt/cascadevalid.txt/cascadetest.txt",
        "split_files": dict(SPLIT_FILENAMES),
        "split_counts": split_counts,
        "uses_original_splits": bool(uses_original_splits),
        "vocabulary_source": "train split only",
        "uses_train_only_vocabulary": bool(uses_train_only_vocabulary),
        "reserved_user_ids": {"pad": PAD_USER_ID, "eos": EOS_USER_ID, "unk": UNK_USER_ID},
        "train_user_count": vocabulary.train_user_count,
        "vocabulary_size": vocabulary.size,
        "vocabulary_overflow_user_count": vocabulary.overflow_user_count,
        "valid_oov": vocabulary_oov_report(valid_cascades, vocabulary),
        "test_oov": vocabulary_oov_report(test_cascades, vocabulary),
        "uses_hash_buckets": bool(uses_hash_buckets),
        "uses_proxy_ranking": bool(uses_proxy_ranking),
        "model_score_source": model_score_source,
        "candidate_generation_reads_future_tail": bool(candidate_generation_reads_future_tail),
        "future_nodes_injected": bool(future_nodes_injected),
        "social_graph_status": social_graph_status,
        "leakage_check_passed": (
            bool(uses_original_splits)
            and bool(uses_train_only_vocabulary)
            and not uses_hash_buckets
            and not uses_proxy_ranking
            and not candidate_generation_reads_future_tail
            and not future_nodes_injected
        ),
    }
    audit["fair_protocol_passed"] = bool(
        audit["leakage_check_passed"]
        and split_counts["train"] > 0
        and (split_counts["valid"] > 0 or split_counts["test"] > 0)
    )
    return audit


def gate_fair_protocol(audit: Mapping[str, object]) -> bool:
    return bool(audit.get("fair_protocol_passed"))


__all__ = [
    "Cascade",
    "DEFAULT_K_LIST",
    "EOS_USER_ID",
    "FIRST_REAL_USER_ID",
    "PAD_USER_ID",
    "PROTOCOL_ID",
    "PrefixWindow",
    "SPLIT_FILENAMES",
    "TrainingUserVocabulary",
    "UNK_USER_ID",
    "build_fair_protocol_audit",
    "build_prefix_window",
    "build_prefix_windows",
    "build_training_user_vocabulary",
    "compute_macro_metrics",
    "compute_micro_metrics",
    "direction_accuracy",
    "gate_fair_protocol",
    "load_forest_cascades",
    "load_original_cascade_splits",
    "mae",
    "mape",
    "msle",
    "observation_count",
    "parse_forest_cascade",
    "rmse",
    "smape",
    "trend_label_counts",
    "vocabulary_oov_report",
]
